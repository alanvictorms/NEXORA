from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.contracts import ProjectCore, ProjectSpec
from app.domain.models import Project, ProjectSpecVersion, Question
from app.services.common import checksum
from app.services.events import EventService


class DiscoveryService:
    def __init__(self, db: Session):
        self.db = db
        self.events = EventService(db)

    def extract_patch(self, text: str) -> dict:
        lowered = text.lower()
        modules: list[dict] = []
        taxonomy = {
            "autenticação": ["login", "autentica", "cadastro", "senha"],
            "pagamentos": ["pagamento", "pix", "stripe", "asaas", "gateway"],
            "admin": ["admin", "painel", "dashboard", "gestão"],
            "notificações": ["notifica", "push", "email", "whatsapp"],
            "tempo real": ["websocket", "tempo real", "realtime", "chat"],
            "arquivos": ["upload", "imagem", "vídeo", "documento", "pdf"],
            "relatórios": ["relatório", "analytics", "métrica", "indicador"],
        }
        for name, keywords in taxonomy.items():
            if any(keyword in lowered for keyword in keywords):
                modules.append({"key": name.replace(" ", "_"), "name": name.title(), "source": "discovery"})

        target_users: list[str] = []
        for label, keywords in {
            "administradores": ["admin", "gestor", "equipe"],
            "clientes": ["cliente", "usuário", "visitante"],
            "operadores": ["operador", "atendente", "garçom", "corretor"],
        }.items():
            if any(k in lowered for k in keywords):
                target_users.append(label)

        identity_required = any(k in lowered for k in ["login", "cadastro", "senha", "autentica"])
        integrations = []
        for name in ["Evolution API", "WhatsApp", "Stripe", "Asaas", "OpenAI"]:
            if name.lower() in lowered:
                integrations.append({"name": name, "required": True, "source": "discovery"})

        sentences = [s.strip() for s in re.split(r"[.!?]\s+|\n+", text) if len(s.strip()) > 12]
        return {
            "project": {
                "summary": text[:500],
                "problem": sentences[0] if sentences else text[:500],
                "target_users": target_users,
            },
            "modules": modules,
            "functional_requirements": [
                {"id": f"fr-{i + 1}", "description": sentence, "source": "conversation"}
                for i, sentence in enumerate(sentences[:12])
            ],
            "identity": {
                "required": identity_required if identity_required else None,
                "methods": ["email_password"] if identity_required else [],
            },
            "integrations": integrations,
        }

    def apply_message(self, project: Project, text: str, source: str = "discovery") -> ProjectSpecVersion:
        current = self.current(project.id)
        patch = self.extract_patch(text)
        if current:
            data = deepcopy(current.spec)
            for key, value in patch.items():
                if isinstance(value, dict) and isinstance(data.get(key), dict):
                    data[key].update(value)
                elif isinstance(value, list):
                    existing = data.get(key, [])
                    seen = {str(item) for item in existing}
                    data[key] = existing + [item for item in value if str(item) not in seen]
                else:
                    data[key] = value
        else:
            data = ProjectSpec(project=ProjectCore(name=project.name)).model_dump(mode="json")
            for key, value in patch.items():
                if isinstance(value, dict) and isinstance(data.get(key), dict):
                    data[key].update(value)
                else:
                    data[key] = value

        validated = ProjectSpec.model_validate(data).model_dump(mode="json")
        version = project.current_spec_version + 1
        item = ProjectSpecVersion(
            project_id=project.id,
            version=version,
            spec=validated,
            patch=patch,
            source=source,
            checksum=checksum(validated),
        )
        project.current_spec_version = version
        project.status = "DISCOVERY"
        self.db.add(item)
        self.db.flush()
        self.analyze_gaps(project, validated)
        self.events.emit(project.id, "spec.updated", f"ProjectSpec v{version} compilado", payload={"version": version})
        self.db.commit()
        return item

    def current(self, project_id: str) -> ProjectSpecVersion | None:
        return self.db.scalar(
            select(ProjectSpecVersion)
            .where(ProjectSpecVersion.project_id == project_id)
            .order_by(ProjectSpecVersion.version.desc())
            .limit(1)
        )

    def analyze_gaps(self, project: Project, spec: dict) -> list[Question]:
        existing = {
            q.key: q
            for q in self.db.scalars(
                select(Question).where(Question.project_id == project.id, Question.status == "OPEN")
            )
        }
        rules = []
        if not spec["project"].get("target_users"):
            rules.append(
                ("target_users", "IMPORTANT", "Quem usará a aplicação?", "Define jornadas e autorização.",
                 ["Somente equipe interna", "Equipe e clientes", "Público geral"], "Equipe e clientes")
            )
        if spec["identity"].get("required") is None:
            rules.append(
                ("identity_required", "IMPORTANT", "A aplicação exige login?", "Afeta dados, papéis e segurança.",
                 ["Sim, email e senha", "Sim, acesso social", "Não"], "Sim, email e senha")
            )
        if not spec.get("production_requirements"):
            rules.append(
                ("production_requirements", "ASSUMABLE", "Qual a expectativa inicial de produção?",
                 "Dimensiona infraestrutura e custo.", ["Baixo volume", "Volume médio", "Alta escala"], "Baixo volume")
            )

        created: list[Question] = []
        for key, severity, question, reason, options, recommended in rules[:5]:
            if key in existing:
                created.append(existing[key])
                continue
            item = Question(
                project_id=project.id,
                key=key,
                severity=severity,
                question=question,
                reason=reason,
                options=options,
                recommended=recommended,
            )
            self.db.add(item)
            self.db.flush()
            created.append(item)
            self.events.emit(
                project.id, "spec.question.required", question, payload={"question_id": item.id, "severity": severity}
            )
        return created

    def answer_question(self, project: Project, question: Question, answer: str) -> ProjectSpecVersion:
        question.answer = answer
        question.status = "ANSWERED"
        from app.domain.models import utcnow

        question.answered_at = utcnow()
        text = f"Decisão de discovery ({question.key}): {answer}"
        return self.apply_message(project, text, source="question_answer")


def next_graph_version(db: Session, model: Any, project_id: str) -> int:
    return int(db.scalar(select(func.coalesce(func.max(model.version), 0)).where(model.project_id == project_id)) or 0) + 1

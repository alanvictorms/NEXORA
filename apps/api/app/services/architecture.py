from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import ArchitectureSpecVersion, Project, ProjectSpecVersion
from app.services.common import checksum
from app.services.events import EventService
from app.services.specs import next_graph_version


class ArchitectureService:
    def __init__(self, db: Session):
        self.db = db
        self.events = EventService(db)

    def generate(self, project: Project, spec_version: ProjectSpecVersion) -> ArchitectureSpecVersion:
        spec = spec_version.spec
        modules = [item.get("name", item.get("key", "Módulo")) for item in spec.get("modules", [])]
        needs_realtime = bool(spec.get("realtime")) or any("tempo real" in m.lower() for m in modules)
        needs_storage = any(
            word in str(spec).lower() for word in ["upload", "imagem", "vídeo", "documento", "arquivo"]
        )
        decisions = [
            {
                "key": "application_shape",
                "decision": "modular_monolith",
                "reason": "Reduz complexidade operacional sem perder limites de domínio.",
            },
            {
                "key": "frontend",
                "decision": "React + Vite + TypeScript",
                "reason": "Stack Policy padrão e build reproduzível.",
            },
            {
                "key": "backend",
                "decision": "FastAPI + Python 3.12",
                "reason": "Stack Policy padrão e contratos tipados.",
            },
            {
                "key": "database",
                "decision": "PostgreSQL + SQLAlchemy + Alembic",
                "reason": "Concorrência, integridade e migrations desde zero.",
            },
        ]
        architecture = {
            "schema_version": 1,
            "project_spec_version_id": spec_version.id,
            "style": "modular_monolith",
            "frontend": {"framework": "react", "bundler": "vite", "language": "typescript"},
            "backend": {"framework": "fastapi", "language": "python", "version": "3.12"},
            "database": {"engine": "postgresql", "orm": "sqlalchemy", "migrations": "alembic"},
            "object_storage": {"required": needs_storage, "interface": "s3_compatible"},
            "redis": {"required": False, "reason": "Somente quando coordenação/cache não durável justificar."},
            "realtime": {"required": needs_realtime, "transport": "websocket" if needs_realtime else None},
            "modules": modules,
            "security": {
                "identity_required": spec.get("identity", {}).get("required", False),
                "tenant_isolation": "organization_id",
                "secrets": "reference_only",
            },
            "runtime": {"container": "oci", "healthcheck": "/health", "non_root": True},
            "decisions": decisions,
        }
        version = next_graph_version(self.db, ArchitectureSpecVersion, project.id)
        item = ArchitectureSpecVersion(
            project_id=project.id,
            project_spec_version_id=spec_version.id,
            version=version,
            spec=architecture,
            decisions=decisions,
            checksum=checksum(architecture),
        )
        project.current_architecture_version = version
        project.status = "ARCHITECTING"
        self.db.add(item)
        self.db.flush()
        self.events.emit(
            project.id,
            "architecture.completed",
            f"ArchitectureSpec v{version} concluída",
            payload={"version": version},
        )
        self.db.commit()
        return item

    def current(self, project_id: str) -> ArchitectureSpecVersion | None:
        return self.db.scalar(
            select(ArchitectureSpecVersion)
            .where(ArchitectureSpecVersion.project_id == project_id)
            .order_by(ArchitectureSpecVersion.version.desc())
            .limit(1)
        )


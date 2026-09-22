from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import Project, Question
from app.services.architecture import ArchitectureService
from app.services.design import DesignSpecService
from app.services.events import EventService
from app.services.execution import ExecutionService
from app.services.preview import PreviewService
from app.services.production import ProductionPlanner
from app.services.specs import DiscoveryService
from app.services.task_graphs import TaskGraphService
from app.services.validation import ValidationEngine


class BlockingGaps(RuntimeError):
    pass


class ProjectPipeline:
    def __init__(self, db: Session):
        self.db = db
        self.events = EventService(db)

    async def run(self, project_id: str) -> dict:
        project = self.db.get(Project, project_id)
        if not project:
            raise ValueError("Projeto não encontrado")
        spec = DiscoveryService(self.db).current(project.id)
        if not spec:
            raise ValueError("Projeto ainda não possui ProjectSpec")
        blockers = list(
            self.db.scalars(
                select(Question).where(
                    Question.project_id == project.id,
                    Question.status == "OPEN",
                    Question.severity == "BLOCKING",
                )
            )
        )
        if blockers:
            raise BlockingGaps("Existem lacunas bloqueadoras")

        architecture = ArchitectureService(self.db).generate(project, spec)
        design = DesignSpecService(self.db).generate(project, spec)
        graph = TaskGraphService(self.db).generate(project, spec, architecture)
        commit_sha = await ExecutionService(self.db).execute_graph(project, spec, architecture, graph)
        release_validation = ValidationEngine(self.db).validate_release(project)
        if release_validation.status != "PASSED":
            raise RuntimeError("Gates finais de release falharam")
        preview = PreviewService(self.db).create(project, commit_sha)
        production = ProductionPlanner(self.db).generate(project, architecture)
        self.events.emit(project.id, "pipeline.completed", "Fluxo ponta a ponta concluído")
        self.db.commit()
        return {
            "project_id": project.id,
            "spec_version": spec.version,
            "architecture_version": architecture.version,
            "design_version": design.version,
            "task_graph_id": graph.id,
            "commit_sha": commit_sha,
            "preview_id": preview.id,
            "preview_url": preview.url,
            "monthly_credits": production.monthly_credits,
        }

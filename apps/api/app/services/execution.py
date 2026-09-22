from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.domain.models import (
    ArchitectureSpecVersion,
    Artifact,
    Execution,
    Project,
    ProjectSpecVersion,
    Task,
    TaskGraph,
    utcnow,
)
from app.integrations.executors import (
    CodeExecutionProvider,
    LocalExecutionProvider,
    OpenHandsExecutionProvider,
)
from app.services.common import checksum
from app.services.context import ContextCompiler
from app.services.events import EventService
from app.services.providers import ProviderRegistry
from app.services.repositories import GitRepositoryService
from app.services.task_graphs import TaskGraphService
from app.services.validation import ValidationEngine


class BuildFailed(RuntimeError):
    pass


class ExecutionService:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.events = EventService(db)
        self.registry = ProviderRegistry(db)
        self.repositories = GitRepositoryService()
        self.contexts = ContextCompiler(db)
        self.validation = ValidationEngine(db)
        self.adapters: dict[str, CodeExecutionProvider] = {
            "local_mock": LocalExecutionProvider(),
            "openhands_native": OpenHandsExecutionProvider(self.settings.openhands_api_key),
            "claude_code_acp": OpenHandsExecutionProvider(self.settings.openhands_api_key),
            "codex_acp": OpenHandsExecutionProvider(self.settings.openhands_api_key),
        }

    async def execute_graph(
        self,
        project: Project,
        spec: ProjectSpecVersion,
        architecture: ArchitectureSpecVersion,
        graph: TaskGraph,
    ) -> str:
        if not project.repository_path:
            repo, _ = self.repositories.initialize(project.id, project.name)
            project.repository_path = str(repo)
        repo = Path(project.repository_path)
        graph.status = "RUNNING"
        project.status = "BUILDING"
        self.events.emit(project.id, "build.started", "Execução do TaskGraph iniciada", payload={"graph_id": graph.id})
        self.db.commit()

        waves = TaskGraphService(self.db).validate_dag(graph)
        tasks = {task.id: task for task in self.db.scalars(select(Task).where(Task.task_graph_id == graph.id))}
        for wave_number, wave in enumerate(waves, start=1):
            self.events.emit(
                project.id,
                "task.wave.started",
                f"Executando wave {wave_number}/{len(waves)}",
                payload={"task_ids": wave},
            )
            self.db.commit()
            for task_id in wave:
                await self._execute_task(project, tasks[task_id], spec, architecture, repo)

        graph.status = "COMPLETED"
        project.status = "VALIDATING"
        commit_sha = self.repositories.head(repo)
        self.events.emit(
            project.id,
            "build.completed",
            "Build consolidada e rastreável em Git",
            payload={"commit_sha": commit_sha},
        )
        self.db.commit()
        return commit_sha

    async def _execute_task(
        self,
        project: Project,
        task: Task,
        spec: ProjectSpecVersion,
        architecture: ArchitectureSpecVersion,
        repo: Path,
    ) -> None:
        policy = task.provider_policy
        capability = policy.get("capability", "code_general")
        providers = self.registry.candidates(capability, policy.get("preferred"))
        if not providers:
            raise BuildFailed(f"Sem provider para {capability}")

        worktree, branch, base_sha = self.repositories.create_worktree(repo, task.id)
        task.base_commit_sha = base_sha
        attempted: list[str] = []
        last_error = ""
        for provider in providers:
            if attempted and not policy.get("allow_fallback", True):
                break
            attempted.append(provider.id)
            execution = Execution(
                project_id=project.id,
                task_id=task.id,
                provider_id=provider.id,
                correlation_id=str(uuid.uuid4()),
                status="RUNNING",
                attempt=len(attempted),
                started_at=utcnow(),
            )
            self.db.add(execution)
            task.status = "RUNNING"
            self.db.flush()
            self.events.emit(
                project.id,
                "task.started",
                f"Executando: {task.objective}",
                execution_id=execution.id,
                payload={"task_id": task.id, "provider": provider.adapter},
            )
            self.db.commit()
            context = self.contexts.compile(task, project.id, str(worktree), spec, architecture)
            adapter = self.adapters.get(provider.adapter)
            if not adapter:
                last_error = f"Adapter não implementado: {provider.adapter}"
                execution.status = "FAILED"
                execution.error_message = last_error
                execution.finished_at = utcnow()
                self.db.commit()
                continue
            try:
                result = await adapter.execute(provider, context, worktree)
            except Exception as exc:
                result = None
                last_error = str(exc)
            if result and result.status == "SUCCEEDED":
                execution.external_execution_id = result.external_execution_id
                execution.metrics = result.metrics
                task_commit = self.repositories.commit(worktree, task.key)
                validation = self.validation.validate_task(project, worktree, execution.id)
                if validation.status != "PASSED":
                    last_error = "Validation gates falharam"
                    execution.status = "FAILED"
                    execution.error_message = last_error
                    execution.finished_at = utcnow()
                    self.db.commit()
                    continue
                merged_sha = self.repositories.merge_and_cleanup(repo, worktree, branch)
                task.result_commit_sha = merged_sha
                task.status = "COMPLETED"
                execution.status = "SUCCEEDED"
                execution.finished_at = utcnow()
                artifact_path = repo / ".nexora" / "tasks" / f"{task.id}.json"
                if artifact_path.exists():
                    data = artifact_path.read_bytes()
                    artifact = Artifact(
                        project_id=project.id,
                        execution_id=execution.id,
                        kind="task_receipt",
                        name=artifact_path.name,
                        uri=str(artifact_path),
                        media_type="application/json",
                        checksum=checksum(data.decode("utf-8")),
                        size_bytes=len(data),
                        artifact_metadata={"task_id": task.id, "task_commit": task_commit},
                    )
                    self.db.add(artifact)
                self.events.emit(
                    project.id,
                    "task.completed",
                    f"Tarefa concluída: {task.key}",
                    execution_id=execution.id,
                    payload={"task_id": task.id, "commit_sha": merged_sha},
                )
                self.db.commit()
                return
            last_error = (result.error or "Falha sem detalhe") if result else last_error
            execution.status = "FAILED"
            execution.error_message = last_error
            execution.finished_at = utcnow()
            self.events.emit(
                project.id,
                "task.provider.failed",
                f"Provider {provider.name} falhou; avaliando fallback",
                execution_id=execution.id,
                visibility="TECHNICAL_LOG",
            )
            self.db.commit()
        task.status = "FAILED"
        self.db.commit()
        raise BuildFailed(f"Tarefa {task.key} falhou: {last_error}")

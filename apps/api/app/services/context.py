from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contracts import ExecutionContextManifest, ProviderPolicy, TaskSpec
from app.domain.models import ArchitectureSpecVersion, Artifact, ProjectSpecVersion, Task, TaskDependency


class ContextCompiler:
    def __init__(self, db: Session):
        self.db = db

    def compile(
        self,
        task: Task,
        project_id: str,
        repository_path: str,
        spec: ProjectSpecVersion,
        architecture: ArchitectureSpecVersion,
    ) -> ExecutionContextManifest:
        dependencies = list(
            self.db.scalars(
                select(TaskDependency.depends_on_task_id).where(TaskDependency.task_id == task.id)
            )
        )
        artifacts = list(
            self.db.scalars(
                select(Artifact).where(Artifact.project_id == project_id).order_by(Artifact.created_at.desc()).limit(20)
            )
        )
        relevant_artifacts = [
            {"id": artifact.id, "kind": artifact.kind, "name": artifact.name, "uri": artifact.uri}
            for artifact in artifacts
            if not dependencies or artifact.artifact_metadata.get("task_id") in dependencies
        ]
        task_spec = TaskSpec(
            id=task.id,
            project_id=project_id,
            spec_version_id=spec.id,
            architecture_version_id=architecture.id,
            task_type=task.task_type,
            objective=task.objective,
            base_commit_sha=task.base_commit_sha,
            dependencies=dependencies,
            context_refs=task.context_refs,
            allowed_paths=task.allowed_paths,
            forbidden_paths=task.forbidden_paths,
            inputs=task.inputs,
            secret_refs=task.secret_refs,
            acceptance_criteria=task.acceptance_criteria,
            commands_to_validate=task.validation_commands,
            expected_artifacts=task.expected_artifacts,
            provider_policy=ProviderPolicy.model_validate(task.provider_policy),
            timeout_seconds=task.timeout_seconds,
            max_attempts=task.max_attempts,
            retry_policy=task.retry_policy,
        )
        project_excerpt = {
            "project": spec.spec.get("project"),
            "modules": spec.spec.get("modules", []),
            "functional_requirements": spec.spec.get("functional_requirements", []),
            "acceptance_criteria": spec.spec.get("acceptance_criteria", []),
            "identity": spec.spec.get("identity", {}),
            "design": spec.spec.get("design", {}),
        }
        architecture_excerpt = {
            key: architecture.spec.get(key)
            for key in ["style", "frontend", "backend", "database", "security", "modules", "runtime"]
        }
        return ExecutionContextManifest(
            task=task_spec,
            project_spec_excerpt=project_excerpt,
            architecture_excerpt=architecture_excerpt,
            dependency_artifacts=relevant_artifacts,
            repository_path=repository_path,
            secret_names=task.secret_refs,
        )


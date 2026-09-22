from __future__ import annotations

import pytest
from app.core.database import SessionLocal
from app.domain.models import Project, Task, TaskDependency
from app.services.architecture import ArchitectureService
from app.services.bootstrap import seed_system
from app.services.repositories import GitRepositoryService
from app.services.secrets import SecretAccessDenied, SecretStore
from app.services.specs import DiscoveryService
from app.services.task_graphs import TaskGraphService
from sqlalchemy import select


def _project(db):
    org, user = seed_system(db)
    project = Project(
        organization_id=org.id,
        created_by_id=user.id,
        name="Projeto de teste",
        slug="projeto-de-teste",
    )
    db.add(project)
    db.flush()
    repo, _ = GitRepositoryService().initialize(project.id, project.name)
    project.repository_path = str(repo)
    db.commit()
    return project


def test_secret_scope_is_enforced_and_plaintext_is_not_persisted() -> None:
    with SessionLocal() as db:
        project = _project(db)
        store = SecretStore(db)
        secret = store.put(project.organization_id, project.id, "PAYMENT_TOKEN", "never-store-plain", ["backend_feature"])
        assert secret.encrypted_value != "never-store-plain"
        assert store.resolve(secret.id, "backend_feature") == "never-store-plain"
        with pytest.raises(SecretAccessDenied):
            store.resolve(secret.id, "frontend_feature")


def test_generated_task_graph_has_three_waves_and_rejects_cycles() -> None:
    with SessionLocal() as db:
        project = _project(db)
        spec = DiscoveryService(db).apply_message(
            project,
            "Aplicação para clientes e administradores com login, dashboard e relatórios.",
        )
        architecture = ArchitectureService(db).generate(project, spec)
        service = TaskGraphService(db)
        graph = service.generate(project, spec, architecture)
        waves = service.validate_dag(graph)
        assert [len(wave) for wave in waves] == [1, 2, 1]

        tasks = {task.key: task for task in db.scalars(select(Task).where(Task.task_graph_id == graph.id))}
        db.add(TaskDependency(task_id=tasks["bootstrap"].id, depends_on_task_id=tasks["tests"].id))
        db.flush()
        with pytest.raises(ValueError, match="ciclo"):
            service.validate_dag(graph)


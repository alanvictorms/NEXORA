from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from app.core.database import SessionLocal
from app.domain.models import (
    ArchitectureSpecVersion,
    Execution,
    PreviewSession,
    Project,
    ProjectSpecVersion,
    Task,
    TaskGraph,
    ValidationRun,
    utcnow,
)
from app.main import app
from app.services.pipeline import ProjectPipeline
from app.services.preview import PreviewService
from fastapi.testclient import TestClient
from sqlalchemy import func, select


@pytest.mark.asyncio
async def test_full_local_pipeline_builds_auditable_preview() -> None:
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/projects",
            json={
                "name": "Mesa Ágil",
                "initial_message": (
                    "Quero um sistema web para garçons e gestores com login, painel admin, "
                    "pedidos em tempo real, pagamento Pix e relatórios operacionais."
                ),
            },
        )
        assert created.status_code == 201
        project_id = created.json()["project"]["id"]

        questions = client.get(f"/api/v1/projects/{project_id}/questions").json()
        for question in questions:
            response = client.post(
                f"/api/v1/projects/{project_id}/questions/{question['id']}/answer",
                json={"use_recommendation": True},
            )
            assert response.status_code == 200

    with SessionLocal() as db:
        result = await ProjectPipeline(db).run(project_id)
        project = db.get(Project, project_id)
        assert project is not None
        assert project.status == "PREVIEW_READY"
        assert result["monthly_credits"] > 0
        assert Path(project.repository_path or "").joinpath("generated-app/index.html").exists()
        assert db.scalar(
            select(func.count()).select_from(ProjectSpecVersion).where(ProjectSpecVersion.project_id == project_id)
        ) >= 2
        assert db.scalar(
            select(func.count())
            .select_from(ArchitectureSpecVersion)
            .where(ArchitectureSpecVersion.project_id == project_id)
        ) == 1
        graph = db.scalar(select(TaskGraph).where(TaskGraph.project_id == project_id))
        assert graph is not None and graph.status == "COMPLETED"
        assert set(db.scalars(select(Task.status).where(Task.task_graph_id == graph.id))) == {"COMPLETED"}
        assert db.scalar(
            select(func.count()).select_from(Execution).where(Execution.project_id == project_id)
        ) == 4
        assert db.scalar(
            select(func.count()).select_from(ValidationRun).where(ValidationRun.project_id == project_id)
        ) >= 5

        preview = db.scalar(select(PreviewSession).where(PreviewSession.project_id == project_id))
        assert preview is not None and preview.state == "ACTIVE"
        assert PreviewService(db).pause_if_idle(preview, now=utcnow() + timedelta(seconds=6))
        assert preview.state == "PAUSED"
        PreviewService(db).resume(preview)
        assert preview.state == "ACTIVE"

    with TestClient(app) as client:
        detail = client.get(f"/api/v1/projects/{project_id}")
        assert detail.status_code == 200
        body = detail.json()
        assert body["architecture"]["backend"]["framework"] == "fastapi"
        assert len(body["task_graph"]["tasks"]) == 4
        preview_page = client.get(body["preview"]["url"].replace("http://localhost:8000", ""))
        assert preview_page.status_code == 200
        assert "Mesa Ágil" in preview_page.text

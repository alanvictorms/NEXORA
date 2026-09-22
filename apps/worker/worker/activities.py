from __future__ import annotations

from app.core.database import SessionLocal
from app.domain.models import PreviewSession
from app.services.pipeline import ProjectPipeline
from app.services.preview import PreviewService
from temporalio import activity


@activity.defn
async def run_project_pipeline(project_id: str) -> dict:
    with SessionLocal() as db:
        return await ProjectPipeline(db).run(project_id)


@activity.defn
async def pause_preview(preview_id: str) -> bool:
    with SessionLocal() as db:
        preview = db.get(PreviewSession, preview_id)
        if not preview:
            return False
        preview.state = "PAUSED"
        db.commit()
        return True


@activity.defn
async def resume_preview(preview_id: str) -> bool:
    with SessionLocal() as db:
        preview = db.get(PreviewSession, preview_id)
        if not preview:
            return False
        PreviewService(db).resume(preview)
        return True


from __future__ import annotations

from datetime import UTC, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.domain.models import Artifact, PreviewSession, Project, utcnow
from app.services.common import checksum
from app.services.environments import LocalEnvironmentProvider
from app.services.events import EventService


class PreviewService:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.events = EventService(db)
        self.provider = LocalEnvironmentProvider(self.settings.preview_base_url)

    def create(self, project: Project, commit_sha: str) -> PreviewSession:
        if not project.repository_path:
            raise ValueError("Projeto sem repositório")
        index = Path(project.repository_path) / "generated-app" / "index.html"
        if not index.exists():
            raise ValueError("Build artifact não encontrado")
        raw = index.read_bytes()
        artifact = Artifact(
            project_id=project.id,
            kind="preview_build",
            name="index.html",
            uri=str(index),
            media_type="text/html",
            checksum=checksum(raw.decode("utf-8")),
            size_bytes=len(raw),
            artifact_metadata={"commit_sha": commit_sha},
        )
        self.db.add(artifact)
        self.db.flush()
        now = utcnow()
        active = list(
            self.db.scalars(
                select(PreviewSession)
                .where(
                    PreviewSession.project_id == project.id,
                    PreviewSession.state.in_(["ACTIVE", "IDLE", "RESUMING"]),
                )
                .order_by(PreviewSession.created_at)
            )
        )
        while len(active) >= self.settings.max_active_previews_per_project:
            oldest = active.pop(0)
            self.provider.pause(oldest.id)
            oldest.state = "PAUSED"
        preview = PreviewSession(
            project_id=project.id,
            build_artifact_id=artifact.id,
            state="ACTIVE",
            provider="local",
            url="pending",
            last_activity_at=now,
            idle_timeout_seconds=self.settings.preview_idle_timeout_seconds,
            retained_until=now + timedelta(days=self.settings.preview_retention_days),
            preview_metadata={"commit_sha": commit_sha, "database_isolation": "logical_database_contract"},
        )
        self.db.add(preview)
        self.db.flush()
        allocation = self.provider.allocate(project.id, preview.id)
        preview.provider = allocation.provider
        preview.url = allocation.url
        preview.database_name = allocation.database_name
        preview.database_role = allocation.database_role
        project.status = "PREVIEW_READY"
        self.events.emit(
            project.id,
            "preview.ready",
            "Preview temporário disponível",
            payload={"preview_id": preview.id, "url": preview.url},
        )
        self.db.commit()
        return preview

    def pause_if_idle(self, preview: PreviewSession, now=None) -> bool:
        now = now or utcnow()
        last_activity = preview.last_activity_at
        # SQLite drops timezone information; production Postgres preserves it.
        if last_activity.tzinfo is None:
            last_activity = last_activity.replace(tzinfo=UTC)
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)
        elapsed = (now - last_activity).total_seconds()
        if preview.state in {"ACTIVE", "IDLE"} and elapsed >= preview.idle_timeout_seconds:
            self.provider.pause(preview.id)
            preview.state = "PAUSED"
            self.events.emit(preview.project_id, "preview.paused", "Preview pausado por inatividade")
            self.db.commit()
            return True
        if preview.state == "ACTIVE" and elapsed > max(1, preview.idle_timeout_seconds // 2):
            preview.state = "IDLE"
            self.db.commit()
        return False

    def resume(self, preview: PreviewSession) -> PreviewSession:
        if preview.state not in {"PAUSED", "ARCHIVED", "IDLE"}:
            return preview
        preview.state = "RESUMING"
        self.db.flush()
        self.provider.resume(preview.id)
        preview.state = "ACTIVE"
        preview.last_activity_at = utcnow()
        self.events.emit(preview.project_id, "preview.resumed", "Preview retomado")
        self.db.commit()
        return preview

    def activity(self, preview: PreviewSession) -> None:
        if preview.state == "ACTIVE":
            preview.last_activity_at = utcnow()
            self.db.commit()

    def latest(self, project_id: str) -> PreviewSession | None:
        return self.db.scalar(
            select(PreviewSession)
            .where(PreviewSession.project_id == project_id)
            .order_by(PreviewSession.created_at.desc())
            .limit(1)
        )

    def cleanup_expired(self, now=None) -> int:
        now = now or utcnow()
        expired = list(
            self.db.scalars(
                select(PreviewSession).where(
                    PreviewSession.retained_until.is_not(None),
                    PreviewSession.retained_until < now,
                    PreviewSession.state.not_in(["DELETED"]),
                )
            )
        )
        for preview in expired:
            self.provider.destroy(preview.id)
            preview.state = "DELETED"
            self.events.emit(preview.project_id, "preview.deleted", "Preview removido após retenção")
        if expired:
            self.db.commit()
        return len(expired)

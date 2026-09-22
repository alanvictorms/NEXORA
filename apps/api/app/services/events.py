from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.models import ExecutionEvent
from app.services.common import redact


class EventService:
    def __init__(self, db: Session):
        self.db = db

    def emit(
        self,
        project_id: str,
        event_type: str,
        message: str,
        *,
        execution_id: str | None = None,
        visibility: str = "PUBLIC_PROGRESS",
        payload: dict | None = None,
    ) -> ExecutionEvent | None:
        if visibility == "SECRET":
            return None
        max_sequence = self.db.scalar(
            select(func.coalesce(func.max(ExecutionEvent.sequence), 0)).where(
                ExecutionEvent.project_id == project_id
            )
        )
        event = ExecutionEvent(
            project_id=project_id,
            execution_id=execution_id,
            sequence=int(max_sequence or 0) + 1,
            event_type=event_type,
            visibility=visibility,
            message=redact(message),
            payload=payload or {},
        )
        self.db.add(event)
        self.db.flush()
        return event


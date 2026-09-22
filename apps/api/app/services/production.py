from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.domain.models import ArchitectureSpecVersion, ProductionPlan, Project
from app.services.events import EventService


class ProductionPlanner:
    POLICY_VERSION = "2026-09-v1"

    def __init__(self, db: Session):
        self.db = db
        self.events = EventService(db)

    def generate(self, project: Project, architecture: ArchitectureSpecVersion) -> ProductionPlan:
        spec = architecture.spec
        resources: dict[str, Any] = {
            "runtime": {"cpu": 0.5, "memory_mb": 512, "replicas": 1},
            "database": {"engine": "postgres", "class": "shared-standard", "new_database": True},
            "storage": {"object_storage": bool(spec.get("object_storage", {}).get("required"))},
            "redis": {"required": bool(spec.get("redis", {}).get("required"))},
            "workers": [],
            "cron": [],
            "websocket": bool(spec.get("realtime", {}).get("required")),
            "backup": {"policy": "daily"},
            "preview_database_promoted": False,
        }
        credits = 100 + 60 + 20
        if resources["storage"]["object_storage"]:
            credits += 25
        if resources["redis"]["required"]:
            credits += 35
        if resources["websocket"]:
            credits += 20
        plan = ProductionPlan(
            project_id=project.id,
            architecture_spec_version_id=architecture.id,
            resources=resources,
            monthly_credits=credits,
            pricing_policy_version=self.POLICY_VERSION,
        )
        self.db.add(plan)
        self.events.emit(
            project.id,
            "production.plan.ready",
            f"Plano de produção estimado em {credits} créditos/mês",
            payload={"monthly_credits": credits},
        )
        self.db.commit()
        return plan

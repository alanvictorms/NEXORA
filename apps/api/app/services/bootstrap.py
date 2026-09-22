from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.domain.models import Organization, ProviderConfig, User


def seed_system(db: Session) -> tuple[Organization, User]:
    settings = get_settings()
    org = db.scalar(select(Organization).limit(1))
    if not org:
        org = Organization(name=settings.default_organization_name)
        db.add(org)
        db.flush()
    user = db.scalar(select(User).where(User.email == settings.default_user_email))
    if not user:
        user = User(organization_id=org.id, email=settings.default_user_email, role="owner")
        db.add(user)
        db.flush()

    defaults = [
        {
            "name": "Local deterministic executor",
            "kind": "code_executor",
            "adapter": "local_mock",
            "priority": 10,
            "capabilities": ["code_backend", "code_frontend", "code_test", "bootstrap"],
            "allowed_task_types": [],
            "health_status": "HEALTHY",
            "enabled": True,
        },
        {
            "name": "OpenHands native",
            "kind": "code_executor",
            "adapter": "openhands_native",
            "priority": 20,
            "capabilities": ["code_backend", "code_frontend", "code_test", "bootstrap"],
            "allowed_task_types": [],
            "health_status": "UNKNOWN",
            "base_url": settings.openhands_base_url,
            "auth_mode": "session_api_key",
            "enabled": True,
            "provider_metadata": {},
        },
        {
            "name": "Claude Code ACP",
            "kind": "code_executor",
            "adapter": "claude_code_acp",
            "priority": 30,
            "capabilities": ["code_backend", "code_frontend", "code_test", "bootstrap"],
            "allowed_task_types": [],
            "health_status": "UNKNOWN",
            "base_url": settings.openhands_base_url,
            "auth_mode": "secret_ref",
            "enabled": True,
            "provider_metadata": {
                "acp_server": "claude-code",
                "acp_command": ["claude", "--acp"],
            },
        },
        {
            "name": "Codex ACP",
            "kind": "code_executor",
            "adapter": "codex_acp",
            "priority": 40,
            "capabilities": ["code_backend", "code_frontend", "code_test", "bootstrap"],
            "allowed_task_types": [],
            "health_status": "UNKNOWN",
            "base_url": settings.openhands_base_url,
            "auth_mode": "secret_ref",
            "enabled": True,
            "provider_metadata": {
                "acp_server": "codex",
                "acp_command": ["codex", "--acp"],
            },
        },
    ]

    reconcile_keys = [
        "capabilities", "priority", "base_url", "auth_mode",
        "provider_metadata", "enabled", "health_status",
    ]
    for item in defaults:
        existing = db.scalar(select(ProviderConfig).where(ProviderConfig.name == item["name"]))
        if existing:
            for key in reconcile_keys:
                if key in item:
                    setattr(existing, key, item[key])
        else:
            db.add(ProviderConfig(**item))
    db.commit()
    return org, user

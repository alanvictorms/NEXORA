from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.domain.models import SecretMetadata


class SecretAccessDenied(RuntimeError):
    pass


class SecretStore:
    def __init__(self, db: Session):
        self.db = db
        settings = get_settings()
        if settings.app_env == "production" and not settings.secret_encryption_key:
            raise RuntimeError("SECRET_ENCRYPTION_KEY é obrigatória em produção")
        raw = settings.secret_encryption_key or "nexora-development-key-change-me"
        key = base64.urlsafe_b64encode(hashlib.sha256(raw.encode()).digest())
        self.fernet = Fernet(key)

    def put(
        self,
        organization_id: str,
        project_id: str | None,
        name: str,
        value: str,
        scopes: list[str],
    ) -> SecretMetadata:
        encrypted = self.fernet.encrypt(value.encode()).decode()
        fingerprint = hashlib.sha256(value.encode()).hexdigest()[:16]
        secret = SecretMetadata(
            organization_id=organization_id,
            project_id=project_id,
            name=name,
            encrypted_value=encrypted,
            scopes=scopes,
            fingerprint=fingerprint,
        )
        self.db.add(secret)
        self.db.commit()
        return secret

    def resolve(self, secret_id: str, task_type: str) -> str:
        secret = self.db.scalar(select(SecretMetadata).where(SecretMetadata.id == secret_id))
        if not secret or not secret.active:
            raise SecretAccessDenied("Secret inexistente ou inativo")
        if secret.scopes and task_type not in secret.scopes:
            raise SecretAccessDenied("Task não autorizada para este secret")
        return self.fernet.decrypt(secret.encrypted_value.encode()).decode()



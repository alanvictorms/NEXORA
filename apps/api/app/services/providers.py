from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import ProviderConfig


class ProviderUnavailable(RuntimeError):
    pass


class ProviderRegistry:
    def __init__(self, db: Session):
        self.db = db

    def candidates(self, capability: str, preferred: str | None = None) -> list[ProviderConfig]:
        providers = list(
            self.db.scalars(
                select(ProviderConfig)
                .where(ProviderConfig.kind == "code_executor", ProviderConfig.enabled.is_(True))
                .order_by(ProviderConfig.priority.asc())
            )
        )
        eligible = [p for p in providers if capability in p.capabilities or not p.capabilities]
        if preferred:
            eligible.sort(key=lambda p: (p.adapter != preferred and p.name != preferred, p.priority))
        return eligible

    def choose(self, capability: str, preferred: str | None = None) -> ProviderConfig:
        candidates = self.candidates(capability, preferred)
        if not candidates:
            raise ProviderUnavailable(f"Nenhum provider habilitado para {capability}")
        return candidates[0]

    def fallback_chain(self, capability: str, attempted: Iterable[str]) -> list[ProviderConfig]:
        attempted_ids = set(attempted)
        return [p for p in self.candidates(capability) if p.id not in attempted_ids]


from __future__ import annotations

from typing import Protocol

from app.domain.models import ProductionPlan


class DeploymentProvider(Protocol):
    async def validate(self, plan: ProductionPlan) -> list[str]: ...
    async def provision(self, plan: ProductionPlan) -> dict: ...
    async def status(self, external_id: str) -> dict: ...
    async def destroy(self, external_id: str) -> None: ...


class DeploymentNotConfigured(RuntimeError):
    pass


class PlanningOnlyDeploymentProvider:
    """Safe default: planning is complete, commercial provisioning requires explicit configuration."""

    async def validate(self, plan: ProductionPlan) -> list[str]:
        return ["Nenhum DeploymentProvider comercial configurado"]

    async def provision(self, plan: ProductionPlan) -> dict:
        raise DeploymentNotConfigured("Provisionamento externo não configurado")

    async def status(self, external_id: str) -> dict:
        raise DeploymentNotConfigured("Provisionamento externo não configurado")

    async def destroy(self, external_id: str) -> None:
        raise DeploymentNotConfigured("Provisionamento externo não configurado")

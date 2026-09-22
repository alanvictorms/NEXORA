from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class EnvironmentAllocation:
    provider: str
    url: str
    database_name: str
    database_role: str


class EnvironmentProvider(Protocol):
    def allocate(self, project_id: str, preview_id: str) -> EnvironmentAllocation: ...
    def pause(self, preview_id: str) -> None: ...
    def resume(self, preview_id: str) -> None: ...
    def destroy(self, preview_id: str) -> None: ...


class LocalEnvironmentProvider:
    """Development provider; production implementations can map this contract to OCI runtimes."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def allocate(self, project_id: str, preview_id: str) -> EnvironmentAllocation:
        short = project_id.replace("-", "")[:12]
        return EnvironmentAllocation(
            provider="local",
            url=f"{self.base_url}/{preview_id}/content",
            database_name=f"pv_{short}_db",
            database_role=f"pv_{short}_role",
        )

    def pause(self, preview_id: str) -> None:
        return None

    def resume(self, preview_id: str) -> None:
        return None

    def destroy(self, preview_id: str) -> None:
        return None

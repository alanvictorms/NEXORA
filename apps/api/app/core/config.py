from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "NEXORA Agentic Builder"
    app_env: str = "development"
    api_prefix: str = "/api/v1"
    database_url: str = "sqlite+pysqlite:///./data/nexora.db"
    auto_create_schema: bool = True
    workflow_backend: str = "local"
    temporal_address: str = "localhost:7233"
    temporal_namespace: str = "default"
    temporal_task_queue: str = "nexora-control-plane"
    openhands_base_url: str = "http://localhost:3000"
    openhands_api_key: str | None = None
    openhands_agent_kind: str = "openhands_native"
    secret_encryption_key: str | None = None
    repository_root: Path = Path("data/repos")
    artifact_root: Path = Path("data/artifacts")
    preview_idle_timeout_seconds: int = Field(default=1800, ge=5)
    preview_retention_days: int = Field(default=7, ge=1)
    max_active_previews_per_project: int = Field(default=1, ge=1)
    preview_base_url: str = "http://localhost:8000/api/v1/previews"
    cors_origins: str = "http://localhost:5173"
    default_organization_name: str = "FlowTech"
    default_user_email: str = "admin@nexora.local"

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

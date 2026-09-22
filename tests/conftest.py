from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

RUNTIME = Path("/tmp/nexora-agentic-builder-tests")
os.environ.update(
    {
        "DATABASE_URL": f"sqlite+pysqlite:///{RUNTIME / 'test.db'}",
        "REPOSITORY_ROOT": str(RUNTIME / "repos"),
        "ARTIFACT_ROOT": str(RUNTIME / "artifacts"),
        "PREVIEW_IDLE_TIMEOUT_SECONDS": "5",
        "WORKFLOW_BACKEND": "local",
        "AUTO_CREATE_SCHEMA": "true",
    }
)

from app.core.database import Base, engine  # noqa: E402


@pytest.fixture(autouse=True)
def clean_runtime():
    engine.dispose()
    if RUNTIME.exists():
        shutil.rmtree(RUNTIME)
    RUNTIME.mkdir(parents=True)
    Base.metadata.create_all(engine)
    yield

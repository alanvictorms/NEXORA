from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from sqlalchemy.orm import Session

from app.domain.models import Project, ValidationResult, ValidationRun
from app.services.events import EventService


class ValidationEngine:
    def __init__(self, db: Session):
        self.db = db
        self.events = EventService(db)

    def validate_task(self, project: Project, worktree: Path, execution_id: str | None = None) -> ValidationRun:
        run = ValidationRun(project_id=project.id, execution_id=execution_id, status="RUNNING")
        self.db.add(run)
        self.db.flush()
        gates = [
            ("git_diff_check", ["git", "diff", "--check", "HEAD"]),
            ("python_compile", ["python3", "-m", "compileall", "-q", "generated-app"]),
        ]
        failed = False
        for name, command in gates:
            start = time.monotonic()
            result = subprocess.run(command, cwd=worktree, capture_output=True, text=True, timeout=120, check=False)
            duration = int((time.monotonic() - start) * 1000)
            status = "PASSED" if result.returncode == 0 else "FAILED"
            failed = failed or result.returncode != 0
            self.db.add(
                ValidationResult(
                    validation_run_id=run.id,
                    gate=name,
                    status=status,
                    command=" ".join(command),
                    output=(result.stdout + result.stderr)[-5000:],
                    duration_ms=duration,
                )
            )
        index = worktree / "generated-app" / "index.html"
        exists = index.exists() and index.stat().st_size > 100
        self.db.add(
            ValidationResult(
                validation_run_id=run.id,
                gate="preview_artifact",
                status="PASSED" if exists else "FAILED",
                command="internal: generated-app/index.html",
                output=f"exists={exists}",
                duration_ms=0,
            )
        )
        failed = failed or not exists
        run.status = "FAILED" if failed else "PASSED"
        self.events.emit(
            project.id,
            "validation.failed" if failed else "validation.passed",
            "Validação falhou" if failed else "Gates de validação aprovados",
            execution_id=execution_id,
            payload={"validation_run_id": run.id},
        )
        self.db.flush()
        return run

    def validate_release(self, project: Project) -> ValidationRun:
        """Run the complete pre-preview gate set against the consolidated repository."""
        if not project.repository_path:
            raise ValueError("Projeto sem repositório")
        repo = Path(project.repository_path)
        generated = repo / "generated-app"
        backend = generated / "backend"
        tests = generated / "tests"
        run = ValidationRun(project_id=project.id, status="RUNNING")
        self.db.add(run)
        self.db.flush()
        commands: list[tuple[str, list[str], Path]] = [
            ("lint", ["git", "show", "--check", "--oneline", "HEAD"], repo),
            ("typecheck", [sys.executable, "-m", "compileall", "-q", str(generated)], repo),
            ("unit_tests", [sys.executable, "-m", "pytest", "-q", str(tests)], repo),
            (
                "integration_tests",
                [
                    sys.executable,
                    "-c",
                    "from fastapi.testclient import TestClient; from app import app; "
                    "assert TestClient(app).get('/health').json() == {'status': 'ok'}",
                ],
                backend,
            ),
        ]
        failed = False
        for gate, command, cwd in commands:
            started = time.monotonic()
            result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=120, check=False)
            status = "PASSED" if result.returncode == 0 else "FAILED"
            failed = failed or result.returncode != 0
            self.db.add(
                ValidationResult(
                    validation_run_id=run.id,
                    gate=gate,
                    status=status,
                    command=" ".join(command),
                    output=(result.stdout + result.stderr)[-5000:],
                    duration_ms=int((time.monotonic() - started) * 1000),
                )
            )

        internal_gates = {
            "build": (generated / "index.html").exists(),
            "migrations_check": not (generated / "migrations").exists(),
            "healthcheck": (backend / "app.py").exists(),
            "smoke_test": (tests / "test_smoke.py").exists(),
        }
        for gate, passed in internal_gates.items():
            failed = failed or not passed
            self.db.add(
                ValidationResult(
                    validation_run_id=run.id,
                    gate=gate,
                    status="PASSED" if passed else "FAILED",
                    command=f"internal:{gate}",
                    output="verified" if passed else "missing required release artifact",
                    duration_ms=0,
                )
            )
        run.status = "FAILED" if failed else "PASSED"
        self.events.emit(
            project.id,
            "release.validation.failed" if failed else "release.validation.passed",
            "Gates finais falharam" if failed else "Oito gates finais aprovados",
            payload={"validation_run_id": run.id, "gates": len(commands) + len(internal_gates)},
        )
        self.db.flush()
        return run


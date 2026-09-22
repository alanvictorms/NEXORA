from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path

from app.core.database import SessionLocal, init_schema
from app.domain.models import EvaluationFixture, Project
from app.services.bootstrap import seed_system
from app.services.common import slugify
from app.services.repositories import GitRepositoryService
from app.services.specs import DiscoveryService
from sqlalchemy import select

SECRET_PATTERN = re.compile(
    r"(?im)(api[_ -]?key|token|password|senha|secret|authorization)(\s*[:=]\s*)([^\s,;]+)"
)


def sanitize(value: str | None) -> str:
    return SECRET_PATTERN.sub(r"\1\2[REDACTED]", value or "")


def import_database(path: Path, dry_run: bool = False) -> dict[str, int]:
    if not path.is_file():
        raise FileNotFoundError(path)
    legacy = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    legacy.row_factory = sqlite3.Row
    stats = {"projects": 0, "prompts": 0, "references": 0}
    if dry_run:
        stats["projects"] = legacy.execute("SELECT count(*) FROM projects").fetchone()[0]
        stats["prompts"] = legacy.execute("SELECT count(*) FROM prompt_generations").fetchone()[0]
        stats["references"] = legacy.execute("SELECT count(*) FROM project_references").fetchone()[0]
        legacy.close()
        return stats
    init_schema()
    with SessionLocal() as db:
        org, user = seed_system(db)
        for row in legacy.execute(
            "SELECT id, title, description, client_brief, layout_notes, platform, "
            "auth_enabled, auth_type, gateway_enabled, gateway_provider, "
            "external_api_enabled, external_api_provider, websocket_enabled, websocket_events, "
            "permissions_enabled, permissions_profiles FROM projects ORDER BY id"
        ):
            marker = f"legacy:{row['id']}"
            existing = db.scalar(
                select(EvaluationFixture).where(EvaluationFixture.fixture_metadata["import_key"].as_string() == marker)
            )
            if existing:
                continue
            text = "\n".join(
                filter(
                    None,
                    [
                        sanitize(row["description"]),
                        sanitize(row["client_brief"]),
                        sanitize(row["layout_notes"]),
                        f"Plataforma histórica: {row['platform']}",
                        f"Autenticação: {row['auth_type']}" if row["auth_enabled"] else "",
                        f"Gateway: {row['gateway_provider']}" if row["gateway_enabled"] else "",
                        f"API externa: {row['external_api_provider']}" if row["external_api_enabled"] else "",
                        f"Eventos realtime: {sanitize(row['websocket_events'])}" if row["websocket_enabled"] else "",
                        f"Perfis: {sanitize(row['permissions_profiles'])}" if row["permissions_enabled"] else "",
                    ],
                )
            )
            project = Project(
                organization_id=org.id,
                created_by_id=user.id,
                name=f"[Legado] {row['title']}",
                slug=slugify(f"legacy-{row['id']}-{row['title']}"),
                status="IMPORTED_FIXTURE",
            )
            db.add(project)
            db.flush()
            repo, _ = GitRepositoryService().initialize(project.id, project.name)
            project.repository_path = str(repo)
            DiscoveryService(db).apply_message(project, text or str(row["title"]), source="legacy_import")
            project.status = "IMPORTED_FIXTURE"
            db.add(
                EvaluationFixture(
                    project_id=project.id,
                    legacy_project_id=row["id"],
                    kind="briefing",
                    content=text,
                    fixture_metadata={"import_key": marker, "source": "legacy_sqlite", "sanitized": True},
                )
            )
            for prompt in legacy.execute(
                "SELECT id, platform, model, title, generated_text FROM prompt_generations WHERE project_id = ?",
                (row["id"],),
            ):
                db.add(
                    EvaluationFixture(
                        project_id=project.id,
                        legacy_project_id=row["id"],
                        kind="historical_prompt",
                        content=sanitize(prompt["generated_text"]),
                        fixture_metadata={
                            "legacy_prompt_id": prompt["id"],
                            "platform": prompt["platform"],
                            "model": prompt["model"],
                            "title": prompt["title"],
                            "sanitized": True,
                        },
                    )
                )
                stats["prompts"] += 1
            for reference in legacy.execute(
                "SELECT id, original_name, file_type, file_size, notes FROM project_references WHERE project_id = ?",
                (row["id"],),
            ):
                db.add(
                    EvaluationFixture(
                        project_id=project.id,
                        legacy_project_id=row["id"],
                        kind="design_reference_metadata",
                        content=sanitize(reference["notes"]),
                        fixture_metadata={
                            "legacy_reference_id": reference["id"],
                            "original_name": reference["original_name"],
                            "file_type": reference["file_type"],
                            "file_size": reference["file_size"],
                        },
                    )
                )
                stats["references"] += 1
            stats["projects"] += 1
        db.commit()
    legacy.close()
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Importa inteligência sanitizada do SQLite legado")
    parser.add_argument("database", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(json.dumps(import_database(args.database, args.dry_run), ensure_ascii=False))


if __name__ == "__main__":
    main()

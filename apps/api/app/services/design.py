from __future__ import annotations

from sqlalchemy.orm import Session

from app.domain.models import DesignSpecVersion, Project, ProjectSpecVersion
from app.services.common import checksum
from app.services.events import EventService
from app.services.specs import next_graph_version


class DesignSpecService:
    """Compiles stable design tokens and reference lineage from discovery evidence."""

    def __init__(self, db: Session):
        self.db = db
        self.events = EventService(db)

    def generate(self, project: Project, project_spec: ProjectSpecVersion) -> DesignSpecVersion:
        source = project_spec.spec.get("design", {})
        notes = source.get("notes", [])
        spec = {
            "schema_version": 1,
            "project_spec_version_id": project_spec.id,
            "direction": "editorial_technical",
            "tokens": {
                "color": {"background": "#07111d", "surface": "#102033", "accent": "#42e8c8"},
                "radius": {"panel": 18, "control": 10},
                "spacing_base": 4,
                "typography": {"family": "Inter, system-ui, sans-serif", "scale": "fluid"},
            },
            "accessibility": {"minimum_contrast": "WCAG_AA", "keyboard_navigation": True},
            "notes": notes,
        }
        item = DesignSpecVersion(
            project_id=project.id,
            project_spec_version_id=project_spec.id,
            version=next_graph_version(self.db, DesignSpecVersion, project.id),
            spec=spec,
            source_artifact_ids=source.get("reference_artifact_ids", []),
            checksum=checksum(spec),
        )
        self.db.add(item)
        self.db.flush()
        self.events.emit(project.id, "design.completed", f"DesignSpec v{item.version} compilada")
        self.db.commit()
        return item

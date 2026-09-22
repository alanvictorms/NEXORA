from __future__ import annotations

from app.contracts import ProjectCore, ProjectSpec, TaskSpec


def test_project_spec_is_strictly_round_trippable() -> None:
    spec = ProjectSpec(
        project=ProjectCore(name="Mesa Ágil", target_users=["garçons", "gestores"]),
        modules=[{"key": "pedidos", "name": "Pedidos"}],
        identity={"required": True, "methods": ["email_password"]},
    )
    restored = ProjectSpec.model_validate_json(spec.model_dump_json())
    assert restored.project.name == "Mesa Ágil"
    assert restored.identity.required is True


def test_task_spec_requires_provider_capability() -> None:
    schema = TaskSpec.model_json_schema()
    provider = schema["$defs"]["ProviderPolicy"]
    assert "capability" in provider["required"]


from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ProjectCore(BaseModel):
    name: str
    summary: str = ""
    problem: str = ""
    goals: list[str] = Field(default_factory=list)
    non_goals: list[str] = Field(default_factory=list)
    target_users: list[str] = Field(default_factory=list)
    product_type: str = "web_app"


class IdentitySpec(BaseModel):
    required: bool | None = None
    methods: list[str] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=list)
    permissions: list[dict[str, Any]] = Field(default_factory=list)


class DesignRefSpec(BaseModel):
    reference_artifact_ids: list[str] = Field(default_factory=list)
    design_spec_version_id: str | None = None
    notes: list[str] = Field(default_factory=list)


class ProjectSpec(BaseModel):
    schema_version: int = 1
    project: ProjectCore
    actors: list[dict[str, Any]] = Field(default_factory=list)
    journeys: list[dict[str, Any]] = Field(default_factory=list)
    modules: list[dict[str, Any]] = Field(default_factory=list)
    functional_requirements: list[dict[str, Any]] = Field(default_factory=list)
    business_rules: list[dict[str, Any]] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    non_functional_requirements: dict[str, Any] = Field(default_factory=dict)
    identity: IdentitySpec = Field(default_factory=IdentitySpec)
    data: dict[str, Any] = Field(default_factory=dict)
    integrations: list[dict[str, Any]] = Field(default_factory=list)
    payments: dict[str, Any] = Field(default_factory=dict)
    notifications: dict[str, Any] = Field(default_factory=dict)
    realtime: dict[str, Any] = Field(default_factory=dict)
    background_jobs: list[dict[str, Any]] = Field(default_factory=list)
    admin_requirements: dict[str, Any] = Field(default_factory=dict)
    analytics: dict[str, Any] = Field(default_factory=dict)
    design: DesignRefSpec = Field(default_factory=DesignRefSpec)
    constraints: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    architecture_preferences: dict[str, Any] = Field(default_factory=dict)
    production_requirements: dict[str, Any] = Field(default_factory=dict)


class ProviderPolicy(BaseModel):
    capability: str
    preferred: str | None = None
    fallback: list[str] = Field(default_factory=list)
    allow_fallback: bool = True


class TaskSpec(BaseModel):
    id: str
    project_id: str
    spec_version_id: str
    architecture_version_id: str
    task_type: str
    objective: str
    base_commit_sha: str | None = None
    dependencies: list[str] = Field(default_factory=list)
    context_refs: list[str] = Field(default_factory=list)
    allowed_paths: list[str] = Field(default_factory=list)
    forbidden_paths: list[str] = Field(default_factory=list)
    inputs: dict[str, Any] = Field(default_factory=dict)
    secret_refs: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    commands_to_validate: list[str] = Field(default_factory=list)
    expected_artifacts: list[dict[str, Any]] = Field(default_factory=list)
    provider_policy: ProviderPolicy
    timeout_seconds: int = 1800
    max_attempts: int = 2
    retry_policy: dict[str, Any] = Field(
        default_factory=lambda: {"backoff": "exponential", "initial_seconds": 2, "maximum_seconds": 60}
    )


class ExecutionContextManifest(BaseModel):
    task: TaskSpec
    project_spec_excerpt: dict[str, Any]
    architecture_excerpt: dict[str, Any]
    dependency_artifacts: list[dict[str, Any]] = Field(default_factory=list)
    repository_path: str
    secret_names: list[str] = Field(default_factory=list)


class ExecutionResult(BaseModel):
    status: Literal["SUCCEEDED", "FAILED"]
    external_execution_id: str | None = None
    commit_sha: str | None = None
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class ProjectCreate(BaseModel):
    name: str = Field(min_length=2, max_length=220)
    initial_message: str = Field(min_length=10)


class MessageCreate(BaseModel):
    content: str = Field(min_length=1)


class AnswerCreate(BaseModel):
    answer: str | None = None
    use_recommendation: bool = False


class SecretCreate(BaseModel):
    name: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,127}$")
    value: str = Field(min_length=1)
    scopes: list[str] = Field(default_factory=list)

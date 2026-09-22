from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(UTC)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class Organization(TimestampMixin, Base):
    __tablename__ = "organizations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200), nullable=False)


class User(TimestampMixin, Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    role: Mapped[str] = mapped_column(String(40), default="owner", nullable=False)


class Project(TimestampMixin, Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    created_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(220), nullable=False)
    slug: Mapped[str] = mapped_column(String(240), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="DRAFT", nullable=False, index=True)
    repository_path: Mapped[str | None] = mapped_column(String(1000))
    current_spec_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    current_architecture_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    specs: Mapped[list[ProjectSpecVersion]] = relationship(back_populates="project", cascade="all, delete-orphan")
    conversations: Mapped[list[Conversation]] = relationship(back_populates="project", cascade="all, delete-orphan")


class ProjectSpecVersion(TimestampMixin, Base):
    __tablename__ = "project_spec_versions"
    __table_args__ = (UniqueConstraint("project_id", "version", name="uq_project_spec_version"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    spec: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    patch: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    source: Mapped[str] = mapped_column(String(80), default="discovery", nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    project: Mapped[Project] = relationship(back_populates="specs")


class Conversation(TimestampMixin, Base):
    __tablename__ = "conversations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), default="ACTIVE", nullable=False)
    project: Mapped[Project] = relationship(back_populates="conversations")
    messages: Mapped[list[Message]] = relationship(back_populates="conversation", cascade="all, delete-orphan")


class Message(TimestampMixin, Base):
    __tablename__ = "messages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(30), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    structured_patch: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class Question(TimestampMixin, Base):
    __tablename__ = "questions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(120), nullable=False)
    severity: Mapped[str] = mapped_column(String(30), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    recommended: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="OPEN", nullable=False)
    answer: Mapped[str | None] = mapped_column(Text)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ArchitectureSpecVersion(TimestampMixin, Base):
    __tablename__ = "architecture_spec_versions"
    __table_args__ = (UniqueConstraint("project_id", "version", name="uq_architecture_spec_version"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    project_spec_version_id: Mapped[str] = mapped_column(ForeignKey("project_spec_versions.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    spec: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    decisions: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)


class DesignSpecVersion(TimestampMixin, Base):
    __tablename__ = "design_spec_versions"
    __table_args__ = (UniqueConstraint("project_id", "version", name="uq_design_spec_version"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    project_spec_version_id: Mapped[str] = mapped_column(ForeignKey("project_spec_versions.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    spec: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    source_artifact_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)


class TaskGraph(TimestampMixin, Base):
    __tablename__ = "task_graphs"
    __table_args__ = (UniqueConstraint("project_id", "version", name="uq_task_graph_version"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    architecture_spec_version_id: Mapped[str] = mapped_column(
        ForeignKey("architecture_spec_versions.id"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="PLANNED", nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    tasks: Mapped[list[Task]] = relationship(back_populates="graph", cascade="all, delete-orphan")


class Task(TimestampMixin, Base):
    __tablename__ = "tasks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    task_graph_id: Mapped[str] = mapped_column(ForeignKey("task_graphs.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(120), nullable=False)
    task_type: Mapped[str] = mapped_column(String(80), nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    context_refs: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    allowed_paths: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    forbidden_paths: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    inputs: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    secret_refs: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    acceptance_criteria: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    validation_commands: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    expected_artifacts: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    provider_policy: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=1800, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    retry_policy: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="PENDING", nullable=False, index=True)
    base_commit_sha: Mapped[str | None] = mapped_column(String(64))
    result_commit_sha: Mapped[str | None] = mapped_column(String(64))
    graph: Mapped[TaskGraph] = relationship(back_populates="tasks")


class TaskDependency(Base):
    __tablename__ = "task_dependencies"
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), primary_key=True)
    depends_on_task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), primary_key=True)


class ProviderConfig(TimestampMixin, Base):
    __tablename__ = "provider_configs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    adapter: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False, unique=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    capabilities: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    allowed_task_types: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    model_policy: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    auth_mode: Mapped[str] = mapped_column(String(50), default="none", nullable=False)
    secret_refs: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    base_url: Mapped[str | None] = mapped_column(String(1000))
    concurrency_limit: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    max_task_runtime_seconds: Mapped[int] = mapped_column(Integer, default=1800, nullable=False)
    cost_profile: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    health_status: Mapped[str] = mapped_column(String(40), default="UNKNOWN", nullable=False)
    fallback_provider_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    provider_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)


class Execution(TimestampMixin, Base):
    __tablename__ = "executions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    task_id: Mapped[str | None] = mapped_column(ForeignKey("tasks.id"), index=True)
    provider_id: Mapped[str | None] = mapped_column(ForeignKey("provider_configs.id"))
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), default="QUEUED", nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    external_execution_id: Mapped[str | None] = mapped_column(String(200))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class ExecutionEvent(Base):
    __tablename__ = "execution_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    execution_id: Mapped[str | None] = mapped_column(ForeignKey("executions.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    visibility: Mapped[str] = mapped_column(String(30), default="PUBLIC_PROGRESS", nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Artifact(TimestampMixin, Base):
    __tablename__ = "artifacts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    execution_id: Mapped[str | None] = mapped_column(ForeignKey("executions.id"))
    kind: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(260), nullable=False)
    uri: Mapped[str] = mapped_column(String(1200), nullable=False)
    media_type: Mapped[str | None] = mapped_column(String(200))
    checksum: Mapped[str | None] = mapped_column(String(64))
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    artifact_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)


class ValidationRun(TimestampMixin, Base):
    __tablename__ = "validation_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    execution_id: Mapped[str | None] = mapped_column(ForeignKey("executions.id"))
    status: Mapped[str] = mapped_column(String(40), default="RUNNING", nullable=False)
    commit_sha: Mapped[str | None] = mapped_column(String(64))


class ValidationResult(TimestampMixin, Base):
    __tablename__ = "validation_results"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    validation_run_id: Mapped[str] = mapped_column(ForeignKey("validation_runs.id"), nullable=False, index=True)
    gate: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    command: Mapped[str | None] = mapped_column(Text)
    output: Mapped[str | None] = mapped_column(Text)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class PreviewSession(TimestampMixin, Base):
    __tablename__ = "preview_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    build_artifact_id: Mapped[str | None] = mapped_column(ForeignKey("artifacts.id"))
    state: Mapped[str] = mapped_column(String(40), default="BUILDING", nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(80), default="local", nullable=False)
    url: Mapped[str | None] = mapped_column(String(1200))
    database_name: Mapped[str | None] = mapped_column(String(200))
    database_role: Mapped[str | None] = mapped_column(String(200))
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    idle_timeout_seconds: Mapped[int] = mapped_column(Integer, default=1800, nullable=False)
    retained_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    preview_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)


class ProductionPlan(TimestampMixin, Base):
    __tablename__ = "production_plans"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    architecture_spec_version_id: Mapped[str] = mapped_column(
        ForeignKey("architecture_spec_versions.id"), nullable=False
    )
    resources: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    monthly_credits: Mapped[int] = mapped_column(Integer, nullable=False)
    pricing_policy_version: Mapped[str] = mapped_column(String(40), nullable=False)


class SecretMetadata(TimestampMixin, Base):
    __tablename__ = "secret_metadata"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    encrypted_value: Mapped[str] = mapped_column(Text, nullable=False)
    scopes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"), index=True)
    actor_id: Mapped[str | None] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(160), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class EvaluationFixture(TimestampMixin, Base):
    __tablename__ = "evaluation_fixtures"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    legacy_project_id: Mapped[int | None] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(80), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    fixture_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)

from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contracts import AnswerCreate, MessageCreate, ProjectCreate, SecretCreate
from app.core.config import get_settings
from app.core.database import SessionLocal, get_db
from app.domain.models import (
    ArchitectureSpecVersion,
    Conversation,
    DesignSpecVersion,
    ExecutionEvent,
    Message,
    PreviewSession,
    ProductionPlan,
    Project,
    ProjectSpecVersion,
    ProviderConfig,
    Question,
    Task,
    TaskGraph,
)
from app.services.bootstrap import seed_system
from app.services.common import slugify
from app.services.pipeline import ProjectPipeline
from app.services.preview import PreviewService
from app.services.repositories import GitRepositoryService
from app.services.secrets import SecretStore
from app.services.specs import DiscoveryService

router = APIRouter()


def project_or_404(db: Session, project_id: str) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Projeto não encontrado")
    return project


def serialize_project(project: Project) -> dict:
    return {
        "id": project.id,
        "name": project.name,
        "slug": project.slug,
        "status": project.status,
        "current_spec_version": project.current_spec_version,
        "current_architecture_version": project.current_architecture_version,
        "created_at": project.created_at,
        "updated_at": project.updated_at,
    }


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "nexora-control-plane"}


@router.post("/projects", status_code=201)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)) -> dict:
    org, user = seed_system(db)
    project = Project(
        organization_id=org.id,
        created_by_id=user.id,
        name=payload.name,
        slug=slugify(payload.name),
        status="DISCOVERY",
    )
    db.add(project)
    db.flush()
    repo, _ = GitRepositoryService().initialize(project.id, project.name)
    project.repository_path = str(repo)
    conversation = Conversation(project_id=project.id)
    db.add(conversation)
    db.flush()
    message = Message(conversation_id=conversation.id, role="user", content=payload.initial_message)
    db.add(message)
    db.flush()
    spec = DiscoveryService(db).apply_message(project, payload.initial_message)
    db.refresh(project)
    return {"project": serialize_project(project), "conversation_id": conversation.id, "spec": spec.spec}


@router.get("/projects")
def list_projects(db: Session = Depends(get_db)) -> list[dict]:
    return [serialize_project(p) for p in db.scalars(select(Project).order_by(Project.updated_at.desc()))]


@router.get("/projects/{project_id}")
def get_project(project_id: str, db: Session = Depends(get_db)) -> dict:
    project = project_or_404(db, project_id)
    spec = DiscoveryService(db).current(project_id)
    architecture = db.scalar(
        select(ArchitectureSpecVersion)
        .where(ArchitectureSpecVersion.project_id == project_id)
        .order_by(ArchitectureSpecVersion.version.desc())
        .limit(1)
    )
    design = db.scalar(
        select(DesignSpecVersion)
        .where(DesignSpecVersion.project_id == project_id)
        .order_by(DesignSpecVersion.version.desc())
        .limit(1)
    )
    graph = db.scalar(
        select(TaskGraph).where(TaskGraph.project_id == project_id).order_by(TaskGraph.version.desc()).limit(1)
    )
    preview = PreviewService(db).latest(project_id)
    production = db.scalar(
        select(ProductionPlan)
        .where(ProductionPlan.project_id == project_id)
        .order_by(ProductionPlan.created_at.desc())
        .limit(1)
    )
    return {
        "project": serialize_project(project),
        "spec": spec.spec if spec else None,
        "architecture": architecture.spec if architecture else None,
        "design": design.spec if design else None,
        "task_graph": {
            "id": graph.id,
            "version": graph.version,
            "status": graph.status,
            "tasks": [
                {
                    "id": task.id,
                    "key": task.key,
                    "type": task.task_type,
                    "status": task.status,
                    "objective": task.objective,
                }
                for task in db.scalars(select(Task).where(Task.task_graph_id == graph.id))
            ],
        }
        if graph
        else None,
        "preview": {
            "id": preview.id,
            "state": preview.state,
            "url": preview.url,
            "idle_timeout_seconds": preview.idle_timeout_seconds,
        }
        if preview
        else None,
        "production_plan": {
            "monthly_credits": production.monthly_credits,
            "resources": production.resources,
        }
        if production
        else None,
    }


@router.post("/projects/{project_id}/messages", status_code=201)
def add_message(project_id: str, payload: MessageCreate, db: Session = Depends(get_db)) -> dict:
    project = project_or_404(db, project_id)
    conversation = db.scalar(select(Conversation).where(Conversation.project_id == project_id).limit(1))
    if not conversation:
        conversation = Conversation(project_id=project_id)
        db.add(conversation)
        db.flush()
    db.add(Message(conversation_id=conversation.id, role="user", content=payload.content))
    spec = DiscoveryService(db).apply_message(project, payload.content)
    return {"spec_version": spec.version, "spec": spec.spec}


@router.get("/projects/{project_id}/specs")
def list_specs(project_id: str, db: Session = Depends(get_db)) -> list[dict]:
    project_or_404(db, project_id)
    return [
        {"id": item.id, "version": item.version, "source": item.source, "checksum": item.checksum, "spec": item.spec}
        for item in db.scalars(
            select(ProjectSpecVersion)
            .where(ProjectSpecVersion.project_id == project_id)
            .order_by(ProjectSpecVersion.version.desc())
        )
    ]


@router.get("/projects/{project_id}/questions")
def list_questions(project_id: str, db: Session = Depends(get_db)) -> list[dict]:
    project_or_404(db, project_id)
    return [
        {
            "id": q.id,
            "key": q.key,
            "severity": q.severity,
            "question": q.question,
            "reason": q.reason,
            "options": q.options,
            "recommended": q.recommended,
            "status": q.status,
            "answer": q.answer,
        }
        for q in db.scalars(select(Question).where(Question.project_id == project_id).order_by(Question.created_at))
    ]


@router.post("/projects/{project_id}/questions/{question_id}/answer")
def answer_question(
    project_id: str, question_id: str, payload: AnswerCreate, db: Session = Depends(get_db)
) -> dict:
    project = project_or_404(db, project_id)
    question = db.get(Question, question_id)
    if not question or question.project_id != project_id:
        raise HTTPException(404, "Pergunta não encontrada")
    answer = question.recommended if payload.use_recommendation else payload.answer
    if not answer:
        raise HTTPException(422, "Resposta obrigatória")
    spec = DiscoveryService(db).answer_question(project, question, answer)
    return {"question_id": question.id, "status": question.status, "spec_version": spec.version}


async def _run_pipeline_background(project_id: str) -> None:
    with SessionLocal() as db:
        try:
            await ProjectPipeline(db).run(project_id)
        except Exception as exc:
            project = db.get(Project, project_id)
            if project:
                project.status = "FAILED"
                from app.services.events import EventService

                EventService(db).emit(project.id, "pipeline.failed", f"Pipeline falhou: {exc}")
                db.commit()


@router.post("/projects/{project_id}/pipeline", status_code=202)
async def run_pipeline(
    project_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)
) -> dict:
    project = project_or_404(db, project_id)
    if project.status in {"BUILDING", "VALIDATING", "ARCHITECTING"}:
        raise HTTPException(409, "Pipeline já está em execução")
    settings = get_settings()
    if settings.workflow_backend == "temporal":
        from temporalio.client import Client
        from worker.workflows import BuildWorkflow

        client = await Client.connect(
            settings.temporal_address,
            namespace=settings.temporal_namespace,
        )
        workflow_id = f"build-{project_id}-{uuid.uuid4()}"
        await client.start_workflow(
            BuildWorkflow.run,
            project_id,
            id=workflow_id,
            task_queue=settings.temporal_task_queue,
        )
        return {"status": "accepted", "project_id": project_id, "workflow_id": workflow_id}
    background_tasks.add_task(_run_pipeline_background, project_id)
    return {"status": "accepted", "project_id": project_id}


@router.get("/projects/{project_id}/events")
def list_events(project_id: str, after: int = 0, db: Session = Depends(get_db)) -> list[dict]:
    project_or_404(db, project_id)
    return [
        {
            "id": event.id,
            "sequence": event.sequence,
            "type": event.event_type,
            "visibility": event.visibility,
            "message": event.message,
            "payload": event.payload,
            "created_at": event.created_at,
        }
        for event in db.scalars(
            select(ExecutionEvent)
            .where(
                ExecutionEvent.project_id == project_id,
                ExecutionEvent.sequence > after,
                ExecutionEvent.visibility == "PUBLIC_PROGRESS",
            )
            .order_by(ExecutionEvent.sequence)
        )
    ]


@router.get("/projects/{project_id}/events/stream")
async def stream_events(project_id: str, request: Request, after: int = 0) -> StreamingResponse:
    async def generator():
        cursor = after
        while not await request.is_disconnected():
            with SessionLocal() as session:
                events = list(
                    session.scalars(
                        select(ExecutionEvent)
                        .where(
                            ExecutionEvent.project_id == project_id,
                            ExecutionEvent.sequence > cursor,
                            ExecutionEvent.visibility == "PUBLIC_PROGRESS",
                        )
                        .order_by(ExecutionEvent.sequence)
                    )
                )
                for event in events:
                    cursor = event.sequence
                    data = json.dumps(
                        {"sequence": event.sequence, "type": event.event_type, "message": event.message, "payload": event.payload},
                        ensure_ascii=False,
                    )
                    yield f"id: {cursor}\nevent: progress\ndata: {data}\n\n"
            yield ": keepalive\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(generator(), media_type="text/event-stream")


@router.get("/providers")
def list_providers(db: Session = Depends(get_db)) -> list[dict]:
    return [
        {
            "id": p.id,
            "name": p.name,
            "kind": p.kind,
            "adapter": p.adapter,
            "enabled": p.enabled,
            "priority": p.priority,
            "capabilities": p.capabilities,
            "health_status": p.health_status,
            "base_url": p.base_url,
        }
        for p in db.scalars(select(ProviderConfig).order_by(ProviderConfig.priority))
    ]


@router.post("/projects/{project_id}/secrets", status_code=201)
def create_secret(project_id: str, payload: SecretCreate, db: Session = Depends(get_db)) -> dict:
    project = project_or_404(db, project_id)
    secret = SecretStore(db).put(
        project.organization_id, project.id, payload.name, payload.value, payload.scopes
    )
    return {
        "id": secret.id,
        "name": secret.name,
        "scopes": secret.scopes,
        "fingerprint": secret.fingerprint,
        "active": secret.active,
    }


@router.post("/previews/{preview_id}/activity", status_code=204)
def preview_activity(preview_id: str, db: Session = Depends(get_db)) -> None:
    preview = db.get(PreviewSession, preview_id)
    if not preview:
        raise HTTPException(404, "Preview não encontrado")
    PreviewService(db).activity(preview)


@router.post("/previews/{preview_id}/pause")
def pause_preview(preview_id: str, db: Session = Depends(get_db)) -> dict:
    preview = db.get(PreviewSession, preview_id)
    if not preview:
        raise HTTPException(404, "Preview não encontrado")
    preview.state = "PAUSED"
    db.commit()
    return {"id": preview.id, "state": preview.state}


@router.post("/previews/{preview_id}/resume")
def resume_preview(preview_id: str, db: Session = Depends(get_db)) -> dict:
    preview = db.get(PreviewSession, preview_id)
    if not preview:
        raise HTTPException(404, "Preview não encontrado")
    PreviewService(db).resume(preview)
    return {"id": preview.id, "state": preview.state, "url": preview.url}


@router.get("/previews/{preview_id}/content", response_class=HTMLResponse)
def preview_content(preview_id: str, db: Session = Depends(get_db)) -> HTMLResponse:
    preview = db.get(PreviewSession, preview_id)
    if not preview:
        raise HTTPException(404, "Preview não encontrado")
    if preview.state in {"PAUSED", "ARCHIVED"}:
        return HTMLResponse(
            "<main style='font-family:system-ui;padding:4rem'><h1>Preview pausado</h1>"
            "<p>Retome o ambiente pelo NEXORA para continuar.</p></main>",
            status_code=423,
        )
    project = db.get(Project, preview.project_id)
    if not project or not project.repository_path:
        raise HTTPException(404, "Artifact não encontrado")
    path = Path(project.repository_path) / "generated-app" / "index.html"
    if not path.exists():
        raise HTTPException(404, "Artifact não encontrado")
    PreviewService(db).activity(preview)
    return HTMLResponse(path.read_text(encoding="utf-8"))

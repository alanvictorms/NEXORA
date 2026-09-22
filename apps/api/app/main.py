from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.api.routes import router
from app.core.config import get_settings
from app.core.database import SessionLocal, init_schema
from app.domain.models import PreviewSession
from app.services.bootstrap import seed_system
from app.services.preview import PreviewService

settings = get_settings()


async def reconcile_previews() -> None:
    """Keep the local preview lifecycle useful even without an external scheduler."""
    while True:
        await asyncio.sleep(5)
        with SessionLocal() as db:
            service = PreviewService(db)
            previews = db.scalars(
                select(PreviewSession).where(PreviewSession.state.in_(["ACTIVE", "IDLE"]))
            )
            for preview in previews:
                service.pause_if_idle(preview)
            service.cleanup_expired()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.auto_create_schema:
        init_schema()
    with SessionLocal() as db:
        seed_system(db)
    reconciler = asyncio.create_task(reconcile_previews())
    try:
        yield
    finally:
        reconciler.cancel()
        await asyncio.gather(reconciler, return_exceptions=True)


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router, prefix=settings.api_prefix)

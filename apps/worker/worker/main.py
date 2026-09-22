from __future__ import annotations

import asyncio

from app.core.config import get_settings
from temporalio.client import Client
from temporalio.worker import Worker

from worker.activities import pause_preview, resume_preview, run_project_pipeline
from worker.workflows import (
    ArchitectureWorkflow,
    BuildWorkflow,
    ChangeRequestWorkflow,
    PreviewLifecycleWorkflow,
    ProductionDeploymentWorkflow,
    ProjectDiscoveryWorkflow,
)


async def main() -> None:
    settings = get_settings()
    client = await Client.connect(settings.temporal_address, namespace=settings.temporal_namespace)
    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[
            ProjectDiscoveryWorkflow,
            ArchitectureWorkflow,
            BuildWorkflow,
            ChangeRequestWorkflow,
            PreviewLifecycleWorkflow,
            ProductionDeploymentWorkflow,
        ],
        activities=[run_project_pipeline, pause_preview, resume_preview],
    )
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())


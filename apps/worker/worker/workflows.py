from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from worker.activities import pause_preview, resume_preview, run_project_pipeline


@workflow.defn
class BuildWorkflow:
    @workflow.run
    async def run(self, project_id: str) -> dict:
        return await workflow.execute_activity(
            run_project_pipeline,
            project_id,
            start_to_close_timeout=timedelta(hours=4),
            heartbeat_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(maximum_attempts=2),
        )


@workflow.defn
class ProjectDiscoveryWorkflow:
    @workflow.run
    async def run(self, project_id: str) -> dict:
        return {"project_id": project_id, "state": "SPEC_READY"}


@workflow.defn
class ArchitectureWorkflow:
    @workflow.run
    async def run(self, project_id: str) -> dict:
        return {"project_id": project_id, "state": "ARCHITECTURE_READY"}


@workflow.defn
class ChangeRequestWorkflow:
    @workflow.run
    async def run(self, project_id: str) -> dict:
        return await workflow.execute_child_workflow(BuildWorkflow.run, project_id)


@workflow.defn
class ProductionDeploymentWorkflow:
    @workflow.run
    async def run(self, project_id: str) -> dict:
        return {"project_id": project_id, "state": "PRODUCTION_PLAN_READY", "deployment": "provider_required"}


@dataclass
class PreviewLifecycleInput:
    preview_id: str
    idle_timeout_seconds: int = 1800


@workflow.defn
class PreviewLifecycleWorkflow:
    def __init__(self) -> None:
        self._resume_requested = False
        self._activity_received = False

    @workflow.signal
    async def activity(self) -> None:
        self._activity_received = True

    @workflow.signal
    async def resume(self) -> None:
        self._resume_requested = True

    @workflow.run
    async def run(self, payload: PreviewLifecycleInput) -> str:
        while True:
            self._activity_received = False
            try:
                await workflow.wait_condition(
                    lambda: self._activity_received,
                    timeout=timedelta(seconds=payload.idle_timeout_seconds),
                )
                continue
            except TimeoutError:
                await workflow.execute_activity(
                    pause_preview,
                    payload.preview_id,
                    start_to_close_timeout=timedelta(minutes=2),
                )
                self._resume_requested = False
                await workflow.wait_condition(lambda: self._resume_requested)
                await workflow.execute_activity(
                    resume_preview,
                    payload.preview_id,
                    start_to_close_timeout=timedelta(minutes=2),
                )


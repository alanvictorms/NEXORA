from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Protocol

import httpx

from app.contracts import ExecutionContextManifest, ExecutionResult
from app.domain.models import ProviderConfig


class AgentNotConfigured(RuntimeError):
    """No agent selector available for a StartConversationRequest."""


class CodeExecutionProvider(Protocol):
    async def execute(
        self, provider: ProviderConfig, context: ExecutionContextManifest, worktree: Path
    ) -> ExecutionResult: ...

    async def interrupt(self, provider: ProviderConfig, external_execution_id: str) -> None: ...

    async def health(self, provider: ProviderConfig) -> str: ...


class LocalExecutionProvider:
    async def execute(
        self, provider: ProviderConfig, context: ExecutionContextManifest, worktree: Path
    ) -> ExecutionResult:
        return await asyncio.to_thread(self._write_task, context, worktree)

    def _write_task(self, context: ExecutionContextManifest, worktree: Path) -> ExecutionResult:
        generated = worktree / "generated-app"
        generated.mkdir(parents=True, exist_ok=True)
        task = context.task
        project = context.project_spec_excerpt.get("project") or {}
        project_name = project.get("name", "Aplicação")
        modules = context.project_spec_excerpt.get("modules") or []
        if task.task_type == "bootstrap":
            (generated / "README.md").write_text(
                "# Aplicação gerada\n\nBase criada a partir de ProjectSpec e ArchitectureSpec versionados.\n",
                encoding="utf-8",
            )
            (generated / "index.html").write_text(self._html(project_name, modules), encoding="utf-8")
        elif task.task_type == "backend_feature":
            backend = generated / "backend"
            backend.mkdir(parents=True, exist_ok=True)
            (backend / "app.py").write_text(
                "from fastapi import FastAPI\n\napp = FastAPI(title='Generated App')\n\n"
                "@app.get('/health')\ndef health():\n    return {'status': 'ok'}\n",
                encoding="utf-8",
            )
            (backend / "requirements.txt").write_text("fastapi>=0.115\nuvicorn>=0.34\n", encoding="utf-8")
        elif task.task_type == "frontend_feature":
            frontend = generated / "frontend"
            frontend.mkdir(parents=True, exist_ok=True)
            (frontend / "app.tsx").write_text(
                "export const App = () => <main><h1>" + self._escape(project_name) + "</h1></main>;\n",
                encoding="utf-8",
            )
            (generated / "index.html").write_text(self._html(project_name, modules), encoding="utf-8")
        elif task.task_type == "test_generation":
            tests = generated / "tests"
            tests.mkdir(parents=True, exist_ok=True)
            (tests / "test_smoke.py").write_text(
                "from pathlib import Path\n\ndef test_generated_preview_exists():\n"
                "    assert (Path(__file__).parents[1] / 'index.html').exists()\n",
                encoding="utf-8",
            )
        receipt = worktree / ".nexora" / "tasks" / f"{task.id}.json"
        receipt.parent.mkdir(parents=True, exist_ok=True)
        receipt.write_text(json.dumps(task.model_dump(mode="json"), ensure_ascii=False, indent=2), encoding="utf-8")
        return ExecutionResult(
            status="SUCCEEDED",
            external_execution_id=f"local-{task.id}",
            artifacts=[{"kind": "task_receipt", "path": str(receipt.relative_to(worktree))}],
            metrics={"provider": "local_mock", "deterministic": True},
        )

    @staticmethod
    def _escape(value: str) -> str:
        return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def _html(self, name: str, modules: list[dict]) -> str:
        cards = "".join(
            f"<article><span>{index:02}</span><h2>{self._escape(str(module.get('name', 'Módulo')))}</h2>"
            "<p>Escopo compilado do discovery.</p></article>"
            for index, module in enumerate(modules or [{"name": "Fluxo principal"}], start=1)
        )
        return f"""<!doctype html><html lang=\"pt-BR\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width\"><title>{self._escape(name)}</title><style>
        :root{{--bg:#07111d;--panel:#102033;--line:#23384f;--cyan:#42e8c8;--text:#eef7ff;--muted:#8ba1b6}}*{{box-sizing:border-box}}body{{margin:0;background:radial-gradient(circle at 80% 0,#163b4b,transparent 35%),var(--bg);color:var(--text);font:16px Inter,system-ui;min-height:100vh}}main{{max-width:1100px;margin:auto;padding:72px 24px}}.eyebrow{{color:var(--cyan);letter-spacing:.2em;text-transform:uppercase;font-size:12px}}h1{{font-size:clamp(40px,8vw,88px);line-height:.95;max-width:850px;margin:18px 0}}.lead{{color:var(--muted);max-width:620px;font-size:20px;line-height:1.6}}section{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px;margin-top:54px}}article{{background:linear-gradient(145deg,#12263a,#0d1a29);border:1px solid var(--line);border-radius:18px;padding:24px;min-height:170px}}article span{{color:var(--cyan);font-size:12px}}article h2{{font-size:20px;margin-top:28px}}article p{{color:var(--muted)}}
        </style></head><body><main><div class=\"eyebrow\">Preview gerado por NEXORA</div><h1>{self._escape(name)}</h1><p class=\"lead\">Uma primeira versão executável derivada de especificações versionadas, tarefas auditáveis e gates reais.</p><section>{cards}</section></main></body></html>"""

    async def interrupt(self, provider: ProviderConfig, external_execution_id: str) -> None:
        return None

    async def health(self, provider: ProviderConfig) -> str:
        return "HEALTHY"


class OpenHandsExecutionProvider:
    """REST adapter for the OpenHands Agent Server contract (validated against 1.49.3).

    Agent payload remains provider metadata because native/ACP schemas evolve independently
    from NEXORA. The server is always below our deterministic orchestration layer.
    """

    #: ``ConversationExecutionStatus`` as published by the Agent Server OpenAPI.
    SUCCESS_STATES = frozenset({"finished"})
    FAILURE_STATES = frozenset({"error", "stuck", "paused", "deleting"})
    PENDING_STATES = frozenset({"idle", "running", "waiting_for_confirmation"})

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key

    def _headers(self, provider: ProviderConfig) -> dict[str, str]:
        if not self.api_key:
            return {}
        header = provider.provider_metadata.get("auth_header", "X-Session-API-Key")
        return {header: self.api_key}

    @staticmethod
    def _tag_key(value: str) -> str:
        """Agent Server only accepts lowercase alphanumeric tag keys."""
        return "".join(ch for ch in value.lower() if ch.isalnum())

    def _agent_selector(self, provider: ProviderConfig) -> dict:
        """Agent Server 1.49.3 requires exactly one of these three keys.

        Confirmed live: omitting all three returns
        ``One of `agent`, `agent_settings`, or `agent_profile_id` must be provided``.
        """
        metadata = provider.provider_metadata
        if metadata.get("agent_payload"):
            return {"agent": dict(metadata["agent_payload"])}
        if metadata.get("agent_profile_id"):
            return {"agent_profile_id": metadata["agent_profile_id"]}
        if metadata.get("agent_settings") is not None:
            return {"agent_settings": dict(metadata["agent_settings"])}
        if provider.adapter in {"claude_code_acp", "codex_acp"}:
            acp_command = metadata.get("acp_command")
            if not acp_command:
                raise AgentNotConfigured(
                    f"{provider.adapter}: acp_command ausente em provider_metadata. "
                    "Reconcilie os providers (reinicie a API) ou defina manualmente."
                )
            agent: dict = {
                "kind": "ACPAgent",
                "acp_server": metadata.get(
                    "acp_server", "claude-code" if provider.adapter == "claude_code_acp" else "codex"
                ),
                "acp_command": list(acp_command),
            }
            for key in ("acp_args", "acp_model", "acp_session_mode"):
                if metadata.get(key) is not None:
                    agent[key] = metadata[key]
            return {"agent": agent}
        raise AgentNotConfigured(
            f"{provider.adapter}: nenhum agent configurado; defina agent_payload, "
            "agent_settings ou agent_profile_id em provider_metadata"
        )

    def build_start_payload(self, provider: ProviderConfig, context, worktree: Path) -> dict:
        """``StartConversationRequest`` for ``POST /api/conversations``."""
        payload: dict = {
            "workspace": {"kind": "LocalWorkspace", "working_dir": str(worktree)},
            "initial_message": {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(context.model_dump(mode="json"), ensure_ascii=False),
                    }
                ],
                "run": True,
            },
            "max_iterations": provider.provider_metadata.get("max_iterations", 100),
            "stuck_detection": True,
            "tags": {
                "orchestrator": "nexora",
                self._tag_key("task_id"): context.task.id,
            },
        }
        payload.update(self._agent_selector(provider))
        return payload

    async def execute(
        self, provider: ProviderConfig, context: ExecutionContextManifest, worktree: Path
    ) -> ExecutionResult:
        if not provider.base_url:
            return ExecutionResult(status="FAILED", error="OpenHands base_url não configurada")
        try:
            payload = self.build_start_payload(provider, context, worktree)
        except AgentNotConfigured as exc:
            return ExecutionResult(status="FAILED", error=str(exc))
        timeout = httpx.Timeout(30, read=60)
        async with httpx.AsyncClient(base_url=provider.base_url.rstrip("/"), timeout=timeout) as client:
            response = await client.post("/api/conversations", json=payload, headers=self._headers(provider))
            response.raise_for_status()
            info = response.json()
            conversation_id = info.get("id") or info.get("conversation_id")
            if not conversation_id:
                return ExecutionResult(status="FAILED", error="Agent Server não retornou conversation id")
            deadline = time.monotonic() + context.task.timeout_seconds
            seen_running = False
            while time.monotonic() < deadline:
                await asyncio.sleep(1)
                state = await client.get(
                    f"/api/conversations/{conversation_id}", headers=self._headers(provider)
                )
                state.raise_for_status()
                final_info = state.json()
                status = str(final_info.get("execution_status", "")).lower()
                if status == "running":
                    # `idle` is also the *initial* status, so it only means "done" after a run.
                    seen_running = True
                    continue
                if status in self.FAILURE_STATES:
                    return ExecutionResult(
                        status="FAILED", external_execution_id=conversation_id, error=f"OpenHands: {status}"
                    )
                if status in self.SUCCESS_STATES or (status == "idle" and seen_running):
                    return ExecutionResult(
                        status="SUCCEEDED",
                        external_execution_id=conversation_id,
                        metrics={"agent_server_status": status, "stats": final_info.get("stats", {})},
                    )
            await self.interrupt(provider, conversation_id)
            return ExecutionResult(status="FAILED", external_execution_id=conversation_id, error="timeout")

    async def interrupt(self, provider: ProviderConfig, external_execution_id: str) -> None:
        if not provider.base_url:
            return
        async with httpx.AsyncClient(base_url=provider.base_url.rstrip("/"), timeout=15) as client:
            headers = self._headers(provider)
            # 1.49.3 has no `/stop`: `/interrupt` cancels the in-flight LLM call,
            # `/pause` is the graceful variant kept as fallback.
            response = await client.post(
                f"/api/conversations/{external_execution_id}/interrupt", headers=headers
            )
            if response.status_code == 404:
                await client.post(
                    f"/api/conversations/{external_execution_id}/pause", headers=headers
                )

    async def health(self, provider: ProviderConfig) -> str:
        if not provider.base_url:
            return "UNHEALTHY"
        async with httpx.AsyncClient(base_url=provider.base_url.rstrip("/"), timeout=5) as client:
            for endpoint in ("/health", "/alive", "/server_info"):
                try:
                    response = await client.get(endpoint, headers=self._headers(provider))
                    if response.status_code < 500:
                        return "HEALTHY"
                except httpx.HTTPError:
                    continue
        return "UNHEALTHY"

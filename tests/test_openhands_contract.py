"""Contract test: NEXORA adapter vs. OpenHands Agent Server 1.49.3.

The offline half asserts the payload we build against the facts published by the
Agent Server OpenAPI. The online half re-reads those facts from a live server and
fails when upstream drifts; it is skipped unless ``OPENHANDS_CONTRACT_URL`` is set.
"""

from __future__ import annotations

import os
from pathlib import Path

import httpx
import pytest
from app.contracts import ExecutionContextManifest, ProviderPolicy, TaskSpec
from app.domain.models import ProviderConfig
from app.integrations.executors import OpenHandsExecutionProvider

# Facts read from GET /openapi.json of agent-server 1.49.3.
EXECUTION_STATUS_ENUM = {
    "idle",
    "running",
    "paused",
    "waiting_for_confirmation",
    "finished",
    "error",
    "stuck",
    "deleting",
}
AUTH_HEADER = "X-Session-API-Key"
START_REQUIRED = {"workspace"}


def _context() -> ExecutionContextManifest:
    task = TaskSpec(
        id="task-1",
        project_id="proj-1",
        spec_version_id="spec-1",
        architecture_version_id="arch-1",
        task_type="bootstrap",
        objective="Criar base",
        provider_policy=ProviderPolicy(capability="bootstrap"),
    )
    return ExecutionContextManifest(
        task=task,
        project_spec_excerpt={"project": {"name": "Demo"}},
        architecture_excerpt={},
        repository_path="/app/data/repos/proj-1",
    )


def _provider(adapter: str = "openhands_native", **metadata) -> ProviderConfig:
    return ProviderConfig(
        name=f"test-{adapter}",
        kind="code_executor",
        adapter=adapter,
        priority=99,
        base_url="http://claw3d_nexora-agent-server:8000",
        provider_metadata=metadata,
    )


def test_start_payload_matches_start_conversation_request():
    payload = OpenHandsExecutionProvider().build_start_payload(
        _provider(), _context(), Path("/app/data/repos/proj-1/wt")
    )

    assert START_REQUIRED <= set(payload)
    assert payload["workspace"] == {
        "kind": "LocalWorkspace",
        "working_dir": "/app/data/repos/proj-1/wt",
    }

    # initial_message is a SendMessageRequest, never a bare string.
    message = payload["initial_message"]
    assert isinstance(message, dict)
    assert message["role"] == "user"
    assert message["run"] is True, "sem run=True o agent loop não inicia"
    assert [c["type"] for c in message["content"]] == ["text"]
    assert message["content"][0]["text"]

    assert payload["max_iterations"] >= 1
    assert payload["stuck_detection"] is True

    # Tag keys must be lowercase alphanumeric or the server returns 422.
    for key in payload["tags"]:
        assert key.isalnum() and key.islower(), key


def test_native_provider_omits_agent_until_an_llm_is_wired():
    payload = OpenHandsExecutionProvider().build_start_payload(
        _provider(), _context(), Path("/tmp/wt")
    )
    assert "agent" not in payload


def test_acp_agent_payload_uses_the_real_discriminator_and_required_field():
    provider = _provider(
        "claude_code_acp", acp_server="claude-code", acp_command=["npx", "-y", "@zed-industries/claude-code-acp"]
    )
    agent = OpenHandsExecutionProvider().build_start_payload(provider, _context(), Path("/tmp/wt"))["agent"]
    assert agent["kind"] == "ACPAgent"
    assert agent["acp_command"], "acp_command é obrigatório em ACPAgent-Input"
    assert agent["acp_server"] == "claude-code"


def test_acp_without_command_falls_back_to_server_default_agent():
    provider = _provider("codex_acp")
    payload = OpenHandsExecutionProvider().build_start_payload(provider, _context(), Path("/tmp/wt"))
    assert "agent" not in payload


def test_terminal_states_are_a_partition_of_the_published_enum():
    cls = OpenHandsExecutionProvider
    covered = cls.SUCCESS_STATES | cls.FAILURE_STATES | cls.PENDING_STATES
    assert covered == EXECUTION_STATUS_ENUM
    assert not (cls.SUCCESS_STATES & cls.FAILURE_STATES)
    # `idle` is the initial status too, so it can never be an unconditional success.
    assert "idle" not in cls.SUCCESS_STATES


@pytest.mark.skipif(
    not os.getenv("OPENHANDS_CONTRACT_URL"), reason="defina OPENHANDS_CONTRACT_URL para o teste online"
)
def test_live_agent_server_still_matches_the_pinned_contract():
    base = os.environ["OPENHANDS_CONTRACT_URL"].rstrip("/")
    spec = httpx.get(f"{base}/openapi.json", timeout=30).raise_for_status().json()
    schemas = spec["components"]["schemas"]
    paths = spec["paths"]

    assert set(schemas["ConversationExecutionStatus"]["enum"]) == EXECUTION_STATUS_ENUM
    assert set(schemas["StartConversationRequest"]["required"]) == START_REQUIRED
    assert spec["components"]["securitySchemes"]["APIKeyHeader"]["name"] == AUTH_HEADER

    start_props = schemas["StartConversationRequest"]["properties"]
    for field in ("workspace", "initial_message", "agent", "max_iterations", "stuck_detection", "tags"):
        assert field in start_props

    assert "post" in paths["/api/conversations"]
    assert "/api/conversations/{conversation_id}/interrupt" in paths
    assert "/api/conversations/{conversation_id}/pause" in paths
    assert "/api/conversations/{conversation_id}/stop" not in paths, "o adapter não deve usar /stop"
    assert set(schemas["LocalWorkspace-Input"]["required"]) == {"working_dir"}
    assert schemas["Agent-Input"]["properties"]["kind"]["const"] == "Agent"
    assert schemas["ACPAgent-Input"]["properties"]["kind"]["const"] == "ACPAgent"
    assert "acp_command" in schemas["ACPAgent-Input"]["required"]

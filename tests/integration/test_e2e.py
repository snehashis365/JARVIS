"""End-to-End Integration Tests for Jarvis Assistant.

Verifies complete multi-component workflows: conversational streaming,
tool execution through interactive permission approval, memory persistence,
and personality management.
"""

import json
from pathlib import Path
import pytest

from jarvis.config import AutonomyMode, Settings
from jarvis.core.profiler import HardwareProfiler
from jarvis.core.session import SessionManager
from jarvis.models.messages import ToolCall
from jarvis.security.permissions import PermissionManager
from jarvis.security.policy import ActionType
from jarvis.tools.builtin.fs import WriteFileTool


def test_hardware_profiler():
    """Verify hardware profiler inspects environment and assigns resource profile."""
    prof = HardwareProfiler.profile()
    assert prof.os_name is not None
    assert prof.cpu_cores >= 1
    assert prof.recommended_profile in ("low_resource", "balanced", "performance")
    assert prof.max_concurrent_tasks >= 1
    assert prof.recommended_context_tokens >= 4096


@pytest.mark.asyncio
async def test_e2e_conversational_workflow(async_client):
    """Verify session creation, message sending, and token streaming."""
    # 1. Create new session
    create_res = await async_client.post("/api/sessions", json={"title": "E2E Test Chat"})
    assert create_res.status_code == 200
    session_id = create_res.json()["session_id"]

    # 2. Stream conversation turn
    stream_res = await async_client.post("/api/chat/stream", json={
        "session_id": session_id,
        "message": "Hello Jarvis, test conversational stream.",
        "force_fast_path": True,
    })
    assert stream_res.status_code == 200
    lines = stream_res.text.split("\n")
    data_lines = [l for l in lines if l.startswith("data: ")]
    assert len(data_lines) > 0

    events = [json.loads(l[6:]) for l in data_lines]
    event_types = [e["event_type"] for e in events]
    assert "route" in event_types
    assert "token" in event_types or "done" in event_types

    # 3. Verify session history updated on server
    sess_res = await async_client.get(f"/api/sessions/{session_id}")
    assert sess_res.status_code == 200
    history = sess_res.json()["messages"]
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[1]["role"] == "assistant"


@pytest.mark.asyncio
async def test_e2e_tool_gating_and_approval_workflow(tmp_path: Path):
    """Verify tool action in Agent Decides mode requires approval, can be approved and executed."""
    workspace = tmp_path / "e2e_workspace"
    workspace.mkdir()

    settings = Settings(
        project_root=workspace,
        JARVIS_AUTONOMY_MODE=AutonomyMode.AGENT_DECIDES
    )
    pm = PermissionManager(app_settings=settings)
    write_tool = WriteFileTool()

    # 1. Action is attempted -> waiting for approval
    res_pending = await write_tool.execute(
        {"file_path": "notes.md", "content": "# Autonomous Notes\nVerified."},
        permission_manager=pm
    )
    assert res_pending.status == "waiting_approval"
    assert not (workspace / "notes.md").exists()

    # 2. Inspect pending approvals
    pending = pm.get_pending_approvals()
    assert len(pending) == 1
    req = pending[0]
    assert req.tool_name == "workspace_write_file"
    assert req.action_type == ActionType.WRITE

    # 3. User approves action
    pm.resolve_approval(req.request_id, approved=True)

    # 4. Action executes with approval token
    res_success = await write_tool.execute(
        {"file_path": "notes.md", "content": "# Autonomous Notes\nVerified."},
        permission_manager=pm,
        approval_token=req.request_id
    )
    assert res_success.status == "success"
    assert (workspace / "notes.md").exists()
    assert "# Autonomous Notes" in (workspace / "notes.md").read_text()


@pytest.mark.asyncio
async def test_e2e_settings_and_personality_roundtrip(async_client):
    """Verify personality and status inspection roundtrip via API."""
    # 1. Health and status
    health_res = await async_client.get("/api/health")
    assert health_res.status_code == 200
    assert health_res.json()["status"] == "healthy"

    # 2. Update personality
    update_res = await async_client.put("/api/personality", json={
        "name": "E2EAssistant",
        "tone": "methodical",
        "humor": 0.5
    })
    assert update_res.status_code == 200
    assert update_res.json()["name"] == "E2EAssistant"

    # 3. Verify retrieved personality reflects changes
    get_res = await async_client.get("/api/personality")
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "E2EAssistant"
    assert get_res.json()["tone"] == "methodical"

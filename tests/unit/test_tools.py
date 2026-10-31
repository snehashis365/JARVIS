"""Unit tests for Phase 5 Tools, Skills, and MCP Integrations.

Verifies workspace filesystem tools, web search, system diagnostics,
SkillManager lifecycle, MCP adapter, and permission gating.
"""

from pathlib import Path
import pytest

from jarvis.config import AutonomyMode, Settings
from jarvis.models.messages import ToolCall
from jarvis.security.permissions import PermissionManager
from jarvis.security.policy import ActionType, PathTraversalError
from jarvis.tools.builtin.fs import ListDirectoryTool, ReadFileTool, WriteFileTool
from jarvis.tools.builtin.search import WebSearchTool
from jarvis.tools.builtin.system import SystemDiagnosticsTool
from jarvis.tools.mcp.client import MCPManager, MockMCPClient
from jarvis.tools.registry import ToolRegistry
from jarvis.tools.skills.manager import SkillManager
from jarvis.tools.skills.manifest import SkillManifest


@pytest.mark.asyncio
async def test_read_file_tool(tmp_path: Path):
    """Verify ReadFileTool reads files safely inside workspace."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    test_file = workspace / "sample.txt"
    test_file.write_text("Line 1\nLine 2\nLine 3")

    settings = Settings(project_root=workspace, JARVIS_AUTONOMY_MODE=AutonomyMode.AUTO)
    pm = PermissionManager(app_settings=settings)
    tool = ReadFileTool()

    # Successful read
    res = await tool.execute({"file_path": "sample.txt"}, permission_manager=pm)
    assert res.status == "success"
    assert "Line 1" in res.output

    # File not found
    res_missing = await tool.execute({"file_path": "missing.txt"}, permission_manager=pm)
    assert res_missing.status == "error"
    assert "not found" in res_missing.error_message.lower()

    # Traversal attempt
    with pytest.raises(PathTraversalError):
        await tool.execute({"file_path": "../../etc/passwd"}, permission_manager=pm)


@pytest.mark.asyncio
async def test_write_file_tool_permissions(tmp_path: Path):
    """Verify WriteFileTool requires approval in Agent Decides and is rejected in Plan mode."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # 1. Agent Decides Mode -> Waiting Approval
    settings_ad = Settings(project_root=workspace, JARVIS_AUTONOMY_MODE=AutonomyMode.AGENT_DECIDES)
    pm_ad = PermissionManager(app_settings=settings_ad)
    tool = WriteFileTool()

    res_pending = await tool.execute(
        {"file_path": "new_file.txt", "content": "hello world"},
        permission_manager=pm_ad
    )
    assert res_pending.status == "waiting_approval"

    # Approve request
    pending = pm_ad.get_pending_approvals()
    assert len(pending) == 1
    req_id = pending[0].request_id
    pm_ad.resolve_approval(req_id, approved=True)

    # Re-execute with approved token
    res_approved = await tool.execute(
        {"file_path": "new_file.txt", "content": "hello world"},
        permission_manager=pm_ad,
        approval_token=req_id
    )
    assert res_approved.status == "success"
    assert (workspace / "new_file.txt").read_text() == "hello world"

    # 2. Plan Mode -> Rejected
    settings_plan = Settings(project_root=workspace, JARVIS_AUTONOMY_MODE=AutonomyMode.PLAN)
    pm_plan = PermissionManager(app_settings=settings_plan)
    res_plan = await tool.execute(
        {"file_path": "blocked.txt", "content": "nope"},
        permission_manager=pm_plan
    )
    assert res_plan.status == "rejected"
    assert not (workspace / "blocked.txt").exists()


@pytest.mark.asyncio
async def test_list_directory_and_system_tools(tmp_path: Path):
    """Verify ListDirectoryTool and SystemDiagnosticsTool."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "a.txt").write_text("a")
    (workspace / "b.txt").write_text("b")

    settings = Settings(project_root=workspace, JARVIS_AUTONOMY_MODE=AutonomyMode.AUTO)
    pm = PermissionManager(app_settings=settings)

    list_tool = ListDirectoryTool()
    res_list = await list_tool.execute({"directory_path": "."}, permission_manager=pm)
    assert res_list.status == "success"
    names = [e["name"] for e in res_list.output]
    assert "a.txt" in names
    assert "b.txt" in names

    sys_tool = SystemDiagnosticsTool()
    res_sys = await sys_tool.execute({}, permission_manager=pm)
    assert res_sys.status == "success"
    assert "os" in res_sys.output
    assert "python_version" in res_sys.output


@pytest.mark.asyncio
async def test_web_search_tool():
    """Verify WebSearchTool returns search synthesis."""
    tool = WebSearchTool()
    pm = PermissionManager()
    res = await tool.execute({"query": "python asyncio tutorial"}, permission_manager=pm)
    # In agent_decides, network is mutating/external -> requires approval
    assert res.status in ("waiting_approval", "success")


def test_skill_manager_lifecycle():
    """Verify SkillManager registration, enable/disable, and instruction compiling."""
    manager = SkillManager()
    skills = manager.list_skills()
    assert len(skills) >= 2
    names = [s.name for s in skills]
    assert "workspace_analyzer" in names
    assert "web_researcher" in names

    # Instructions contain active skills
    instructions = manager.get_active_instructions()
    assert "workspace_analyzer" in instructions

    # Disable skill
    assert manager.disable("workspace_analyzer") is True
    instructions_disabled = manager.get_active_instructions()
    assert "workspace_analyzer" not in instructions_disabled

    # Re-enable
    assert manager.enable("workspace_analyzer") is True
    assert "workspace_analyzer" in manager.get_active_instructions()

    # Parse new skill from JSON
    custom_json = """{
        "name": "custom_summarizer",
        "description": "Summarizes documents",
        "instructions": "Be ultra concise.",
        "required_tools": ["workspace_read_file"]
    }"""
    loaded = manager.load_from_json(custom_json)
    assert loaded.name == "custom_summarizer"
    assert manager.get("custom_summarizer") is not None


@pytest.mark.asyncio
async def test_mcp_adapter():
    """Verify MCPManager adapts MCP client tools into Jarvis BaseTools."""
    mock_client = MockMCPClient()
    adapters = await MCPManager.create_adapters_from_client(mock_client)
    assert len(adapters) == 1
    tool = adapters[0]
    assert tool.name == "mcp_sqlite_query"

    pm = PermissionManager(app_settings=Settings(JARVIS_AUTONOMY_MODE=AutonomyMode.AUTO))
    res = await tool.execute({"query": "SELECT 1;"}, permission_manager=pm)
    assert res.status == "success"
    assert res.output["status"] == "mcp_executed"


@pytest.mark.asyncio
async def test_tools_and_skills_api(async_client):
    """Verify /api/tools and /api/skills endpoints."""
    # List tools
    tools_res = await async_client.get("/api/tools")
    assert tools_res.status_code == 200
    tools_data = tools_res.json()
    assert len(tools_data) >= 5

    # List skills
    skills_res = await async_client.get("/api/skills")
    assert skills_res.status_code == 200
    skills_data = skills_res.json()
    assert len(skills_data) >= 2

    # Disable skill
    disable_res = await async_client.post("/api/skills/workspace_analyzer/disable")
    assert disable_res.status_code == 200
    assert disable_res.json()["disabled"] is True

    # Enable skill
    enable_res = await async_client.post("/api/skills/workspace_analyzer/enable")
    assert enable_res.status_code == 200
    assert enable_res.json()["enabled"] is True

    # Test Direct Tool Execution Endpoint (e.g. calculate_expression)
    calc_res = await async_client.post("/api/tools/execute", json={
        "tool_name": "calculate_expression",
        "arguments": {"expression": "25 * 40"}
    })
    assert calc_res.status_code == 200
    calc_data = calc_res.json()
    assert calc_data["status"] == "success"
    assert calc_data["output"]["result"] == 1000

    # Test alias 'name' instead of 'tool_name'
    calc_res_alias = await async_client.post("/api/tools/execute", json={
        "name": "calculate_expression",
        "arguments": {"expression": "100 + 42"}
    })
    assert calc_res_alias.status_code == 200
    assert calc_res_alias.json()["output"]["result"] == 142

    # Test DateTimeNowTool
    time_res = await async_client.post("/api/tools/execute", json={
        "tool_name": "datetime_now",
        "arguments": {}
    })
    assert time_res.status_code == 200
    assert "iso_timestamp" in time_res.json()["output"]

    # Test workspace_search_files
    search_res = await async_client.post("/api/tools/execute", json={
        "tool_name": "workspace_search_files",
        "arguments": {"pattern": "*.py"}
    })
    assert search_res.status_code == 200
    assert isinstance(search_res.json()["output"], list)

    # Test WebSearchTool with live scraping (Google & DuckDuckGo, 0 API keys)
    web_res = await async_client.post("/api/tools/execute", json={
        "tool_name": "web_search",
        "arguments": {"query": "python news", "limit": 2}
    })
    assert web_res.status_code == 200
    assert len(web_res.json()["output"]) > 0
    assert "url" in web_res.json()["output"][0]

    # Test Mutating Tool Approval & Execution Resolution Flow
    write_pending = await async_client.post("/api/tools/execute", json={
        "tool_name": "workspace_write_file",
        "arguments": {"file_path": "approval_test.txt", "content": "approval verified"}
    })
    assert write_pending.status_code == 200
    assert write_pending.json()["status"] == "waiting_approval"

    # Fetch pending approvals
    approvals_res = await async_client.get("/api/approvals")
    assert approvals_res.status_code == 200
    approvals = approvals_res.json()
    assert len(approvals) >= 1
    req_id = approvals[0]["request_id"]
    assert approvals[0]["target"] is not None

    # Resolve approval with approved=True -> Executes tool
    resolve_res = await async_client.post(f"/api/approvals/{req_id}/resolve", json={"approved": True})
    assert resolve_res.status_code == 200
    resolve_data = resolve_res.json()
    assert resolve_data["status"] == "APPROVED"
    assert resolve_data["tool_result"]["status"] == "success"

    # Test Audit Logs endpoint
    audit_res = await async_client.get("/api/audit/logs")
    assert audit_res.status_code == 200
    assert isinstance(audit_res.json(), list)

    # Test Voice status endpoint
    voice_res = await async_client.get("/api/voice/status")
    assert voice_res.status_code == 200
    assert "state" in voice_res.json()

    # Test Voice synthesize endpoint (Kokoro TTS)
    synth_res = await async_client.post("/api/voice/synthesize", json={
        "text": "Jarvis online."
    })
    assert synth_res.status_code == 200
    assert synth_res.headers["content-type"] == "audio/wav"
    assert len(synth_res.content) > 44  # Valid WAV header + PCM samples

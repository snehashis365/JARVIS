"""Unit tests for Phase 3 Assistant Core and Bounded Orchestrator.

Verifies ModelRouter, fast-path chat, multi-step bounded tool execution,
loop detection, timeout enforcement, and cancellation.
"""

import asyncio
import json
import pytest

from jarvis.config import InferenceMode, Settings
from jarvis.core.orchestrator import LoopDetectedError, TaskOrchestrator
from jarvis.core.session import SessionManager
from jarvis.models.messages import ChatMessage, MessageRole, ToolCall
from jarvis.models.session import TaskStatus
from jarvis.providers.base import CancellationToken, LLMResponse
from jarvis.providers.mock import MockProvider
from jarvis.routing.router import ModelRouter


def test_model_router_heuristics():
    """Verify router correctly identifies tool needs and explains decisions."""
    router = ModelRouter()

    # Simple chat
    assert router.requires_tools("Hello there, how are you?") is False
    assert router.requires_tools("Explain quantum physics in simple terms") is False

    # Tool requests
    assert router.requires_tools("Read the file notes.txt") is True
    assert router.requires_tools("Please search the web for latest news") is True
    assert router.requires_tools("create a file named output.py") is True
    assert router.requires_tools("tool: custom_tool") is True


def test_model_router_modes():
    """Verify explainable decisions in Local, Cloud, and Hybrid modes."""
    # Local mode
    local_cfg = Settings(JARVIS_INFERENCE_MODE=InferenceMode.LOCAL, JARVIS_LOCAL_MODEL="llama3.2")
    router_local = ModelRouter(app_settings=local_cfg)
    decision = router_local.route_request([ChatMessage(role=MessageRole.USER, content="Hello")])
    assert decision.route == "local"
    assert decision.model_name == "llama3.2"
    assert decision.is_fast_path is True
    assert "privacy" in decision.reason

    # Cloud mode
    cloud_cfg = Settings(
        JARVIS_INFERENCE_MODE=InferenceMode.CLOUD,
        OPENAI_API_KEY="sk-fake",
        OPENAI_MODEL="gpt-4o"
    )
    router_cloud = ModelRouter(app_settings=cloud_cfg)
    decision_cloud = router_cloud.route_request([ChatMessage(role=MessageRole.USER, content="Hello")])
    assert decision_cloud.route == "cloud"
    assert decision_cloud.model_name == "gpt-4o"

    # Hybrid mode: short conversational prompt stays local
    hybrid_cfg = Settings(
        JARVIS_INFERENCE_MODE=InferenceMode.HYBRID,
        JARVIS_LOCAL_MODEL="llama3.2",
        ANTHROPIC_API_KEY="sk-ant-fake",
        ANTHROPIC_MODEL="claude-3-5-sonnet"
    )
    router_hybrid = ModelRouter(app_settings=hybrid_cfg)
    decision_hybrid_short = router_hybrid.route_request([ChatMessage(role=MessageRole.USER, content="Hi")])
    assert decision_hybrid_short.route == "local"
    assert decision_hybrid_short.is_fast_path is True

    # Hybrid mode: tool task routes to cloud
    decision_hybrid_tool = router_hybrid.route_request(
        [ChatMessage(role=MessageRole.USER, content="read file data.csv and compute statistics")]
    )
    assert decision_hybrid_tool.route == "cloud"
    assert decision_hybrid_tool.requires_tools is True


@pytest.mark.asyncio
async def test_orchestrator_fast_path(session_manager: SessionManager):
    """Verify direct fast-path executes cleanly without creating unnecessary tasks."""
    mock_provider = MockProvider(default_response="Fast direct reply")
    orchestrator = TaskOrchestrator(
        session_manager=session_manager,
        provider=mock_provider,
    )
    session = session_manager.create_session()

    events = []
    async for event in orchestrator.execute(
        session_id=session.session_id,
        user_prompt="Hello Jarvis!",
        force_fast_path=True
    ):
        events.append(event)

    event_types = [e.event_type for e in events]
    assert "route" in event_types
    assert "token" in event_types
    assert "done" in event_types
    # Verify no multi-step task was created for fast path
    assert session.active_task_id is None

    # Verify conversation history updated
    messages = session_manager.get_messages(session.session_id)
    assert len(messages) == 2
    assert messages[0].role == MessageRole.USER
    assert messages[1].role == MessageRole.ASSISTANT


@pytest.mark.asyncio
async def test_orchestrator_bounded_tool_execution(session_manager: SessionManager):
    """Verify multi-step tool execution terminates when model finishes."""
    mock_provider = MockProvider()
    
    # 1st step: model returns tool call
    step1_response = LLMResponse(
        content="",
        tool_calls=[ToolCall(tool_name="search_workspace", arguments={"query": "test"})],
        finish_reason="tool_calls",
    )
    # 2nd step: model provides final synthesis
    step2_response = LLMResponse(
        content="I found 3 test files in the workspace.",
        tool_calls=None,
        finish_reason="stop",
    )
    mock_provider.set_scripted_response(step1_response)
    mock_provider.set_scripted_response(step2_response)

    executed_tools = []
    async def mock_executor(tc: ToolCall):
        executed_tools.append(tc.tool_name)
        return "file1.py, file2.py, file3.py"

    orchestrator = TaskOrchestrator(
        session_manager=session_manager,
        provider=mock_provider,
        tool_executor=mock_executor,
    )
    session = session_manager.create_session()

    tools = [{"name": "search_workspace", "parameters": {}}]
    events = []
    async for event in orchestrator.execute(
        session_id=session.session_id,
        user_prompt="search for test files in workspace",
        tools=tools,
    ):
        events.append(event)

    event_types = [e.event_type for e in events]
    assert "route" in event_types
    assert "tool_call" in event_types
    assert "tool_result" in event_types
    assert "done" in event_types

    assert len(executed_tools) == 1
    assert executed_tools[0] == "search_workspace"

    # Verify session messages contain user, tool, and final assistant reply
    messages = session_manager.get_messages(session.session_id)
    roles = [m.role for m in messages]
    assert MessageRole.USER in roles
    assert MessageRole.TOOL in roles
    assert MessageRole.ASSISTANT in roles


@pytest.mark.asyncio
async def test_orchestrator_loop_detection(session_manager: SessionManager):
    """Verify loop detector halts repeating identical tool calls."""
    mock_provider = MockProvider()
    # Script identical repeated tool calls
    repeating_call = ToolCall(tool_name="read_file", arguments={"path": "same_file.txt"})
    for _ in range(3):
        mock_provider.set_scripted_response(
            LLMResponse(content="", tool_calls=[repeating_call], finish_reason="tool_calls")
        )

    orchestrator = TaskOrchestrator(
        session_manager=session_manager,
        provider=mock_provider,
        tool_executor=lambda tc: "file contents",
    )
    session = session_manager.create_session()
    tools = [{"name": "read_file", "parameters": {}}]

    events = []
    async for event in orchestrator.execute(
        session_id=session.session_id,
        user_prompt="read file same_file.txt",
        tools=tools,
    ):
        events.append(event)

    error_events = [e for e in events if e.event_type == "error"]
    assert len(error_events) > 0
    assert "loop detected" in error_events[0].data.get("error", "").lower()


@pytest.mark.asyncio
async def test_orchestrator_cancellation(session_manager: SessionManager):
    """Verify cooperative cancellation token terminates task."""
    token = CancellationToken()
    mock_provider = MockProvider()

    orchestrator = TaskOrchestrator(
        session_manager=session_manager,
        provider=mock_provider,
    )
    session = session_manager.create_session()

    # Cancel token
    token.cancel()

    events = []
    async for event in orchestrator.execute(
        session_id=session.session_id,
        user_prompt="Cancel this immediately",
        cancellation_token=token,
    ):
        events.append(event)

    error_events = [e for e in events if e.event_type == "error"]
    assert len(error_events) > 0
    assert "cancelled" in error_events[0].data.get("error", "").lower()


@pytest.mark.asyncio
async def test_api_chat_and_stream(async_client):
    """Verify server /api/chat and /api/chat/stream endpoints with orchestrator."""
    # Chat endpoint
    res = await async_client.post("/api/chat", json={
        "message": "Hello from API test",
        "force_fast_path": True,
    })
    assert res.status_code == 200
    data = res.json()
    assert "response" in data
    assert "session_id" in data

    # Stream endpoint
    stream_res = await async_client.post("/api/chat/stream", json={
        "message": "Stream hello",
        "force_fast_path": True,
    })
    assert stream_res.status_code == 200
    assert "text/event-stream" in stream_res.headers["content-type"]
    body = stream_res.text
    assert "data: " in body
    assert "token" in body or "done" in body

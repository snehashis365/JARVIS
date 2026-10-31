"""Unit tests for Phase 1 Foundation components.

Verifies configuration, secret redaction, data models, session lifecycle,
and basic server health endpoints.
"""

import logging
import pytest
from jarvis.config import AutonomyMode, InferenceMode, Settings
from jarvis.core.session import SessionManager
from jarvis.logging import redact_secrets, setup_logging
from jarvis.models import ChatMessage, MessageRole, TaskStatus


def test_settings_initialization(test_settings: Settings):
    """Verify settings defaults and directory properties."""
    assert test_settings.env == "test"
    assert test_settings.assistant_name == "Jarvis"
    assert test_settings.inference_mode == InferenceMode.LOCAL
    assert test_settings.autonomy_mode == AutonomyMode.AGENT_DECIDES
    assert test_settings.data_dir.exists()
    assert test_settings.logs_dir.exists()


def test_secret_redaction():
    """Verify regex redacts various secrets and API keys."""
    raw_texts = [
        "Authorization: Bearer my-secret-jwt-token-1234567890",
        "OpenAI Key: sk-proj-1234567890abcdefghijklmnop",
        "Google Key: AIzaSyD1234567890abcdefghijklmnopqr",
        "config: api_key='supersecretpassword123'",
        "db: password=mysecretpassword123",
    ]

    for raw in raw_texts:
        redacted = redact_secrets(raw)
        assert "my-secret-jwt-token" not in redacted
        assert "sk-proj-1234567890" not in redacted
        assert "AIzaSyD1234567890" not in redacted
        assert "supersecretpassword123" not in redacted
        assert "mysecretpassword123" not in redacted
        assert "REDACTED" in redacted


def test_secret_redacting_logger(tmp_path):
    """Verify logger output stream redacts secrets."""
    logger = setup_logging(log_level="DEBUG", log_dir=tmp_path, log_to_file=True)
    secret_msg = "Attempting connect with Bearer abcdef1234567890 and sk-1234567890abcdef12345"
    logger.info(secret_msg)

    # Read log file to verify redaction on disk
    log_file = tmp_path / "jarvis.log"
    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert "abcdef1234567890" not in content
    assert "REDACTED" in content


def test_session_lifecycle(session_manager: SessionManager):
    """Verify session creation, message appending, and deletion."""
    session = session_manager.create_session(title="Test Chat")
    assert session.session_id is not None
    assert session.title == "Test Chat"
    assert len(session.messages) == 0

    # Add messages
    user_msg = ChatMessage(role=MessageRole.USER, content="Hello")
    session_manager.add_message(session.session_id, user_msg)

    assistant_msg = ChatMessage(role=MessageRole.ASSISTANT, content="Hi there!")
    session_manager.add_message(session.session_id, assistant_msg)

    messages = session_manager.get_messages(session.session_id)
    assert len(messages) == 2
    assert messages[0].content == "Hello"
    assert messages[1].content == "Hi there!"

    # Test limit
    recent = session_manager.get_messages(session.session_id, limit=1)
    assert len(recent) == 1
    assert recent[0].content == "Hi there!"

    # Delete session
    assert session_manager.delete_session(session.session_id) is True
    assert session_manager.get_session(session.session_id) is None


def test_task_lifecycle(session_manager: SessionManager):
    """Verify task creation, progression updates, and completion."""
    session = session_manager.create_session()
    task = session_manager.create_task(
        session_id=session.session_id,
        goal="Analyze workspace files",
        max_steps=5
    )

    assert task.task_id is not None
    assert task.status == TaskStatus.PENDING
    assert task.current_step == 0

    # Progress update
    prog = session_manager.update_task_progress(
        task_id=task.task_id,
        step=1,
        current_action="Reading directory tree",
        status=TaskStatus.RUNNING
    )
    assert prog.step == 1
    assert prog.status == TaskStatus.RUNNING

    # Complete task
    completed = session_manager.complete_task(task.task_id)
    assert completed.status == TaskStatus.COMPLETED


@pytest.mark.asyncio
async def test_health_and_config_endpoints(async_client):
    """Verify FastAPI /api/health and /api/config endpoints."""
    # Health check
    res = await async_client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "inference_mode" in data

    # Safe config
    res_cfg = await async_client.get("/api/config")
    assert res_cfg.status_code == 200
    cfg = res_cfg.json()
    assert "assistant_name" in cfg
    # Ensure no secrets leaked
    assert "openai_api_key" not in cfg
    assert "anthropic_api_key" not in cfg
    assert "gemini_api_key" not in cfg


@pytest.mark.asyncio
async def test_chat_and_session_api(async_client):
    """Verify session creation and conversational chat via HTTP API."""
    # Create session
    create_res = await async_client.post("/api/sessions", json={"title": "Test Session"})
    assert create_res.status_code == 200
    session_data = create_res.json()
    session_id = session_data["session_id"]

    # Send chat message
    chat_res = await async_client.post("/api/chat", json={
        "session_id": session_id,
        "message": "Hello Jarvis!"
    })
    assert chat_res.status_code == 200
    chat_data = chat_res.json()
    assert chat_data["session_id"] == session_id
    assert "Echo: Test response" in chat_data["response"] or "Hello Jarvis!" in chat_data["response"]

    # Retrieve session details
    get_res = await async_client.get(f"/api/sessions/{session_id}")
    assert get_res.status_code == 200
    sess = get_res.json()
    assert len(sess["messages"]) == 2  # user + assistant

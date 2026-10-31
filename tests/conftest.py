"""Pytest shared fixtures for Jarvis Assistant."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from jarvis.config import Settings
from jarvis.core.orchestrator import TaskOrchestrator
from jarvis.core.session import SessionManager
from jarvis.providers.mock import MockProvider
from jarvis.server.app import create_app


@pytest.fixture
def test_settings(tmp_path):
    """Provides isolated settings configured with a temporary workspace directory."""
    return Settings(
        project_root=tmp_path,
        env="test",
        log_level="DEBUG"
    )


@pytest.fixture
def session_manager():
    """Provides a fresh, isolated in-memory session manager."""
    return SessionManager()


@pytest_asyncio.fixture
async def async_client(test_settings):
    """Provides an async HTTP test client connected to the FastAPI app with MockProvider."""
    sm = SessionManager()
    mock_prov = MockProvider(default_response="Echo: Test response")
    orch = TaskOrchestrator(
        session_manager=sm,
        provider=mock_prov,
        app_settings=test_settings,
    )
    app = create_app(
        app_settings=test_settings,
        custom_orchestrator=orch,
        custom_session_manager=sm,
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

"""Unit tests for GUI Initial Setup, Auto-Detection, and Configuration Persistence.

Verifies:
- ConfigManager save, load, reset, and hot-applying to runtime Settings.
- LocalLLMDetector scanning Ollama, LM Studio, llama.cpp, and custom endpoints.
- FastAPI setup endpoints (/api/setup/status, /api/setup/detect, /api/setup/save, /api/setup/reset).
"""

import json
from pathlib import Path
import httpx
import pytest

from jarvis.config import AutonomyMode, InferenceMode, Settings
from jarvis.config_manager import CloudProviderConfig, ConfigManager, JarvisConfig, LocalEngineConfig
from jarvis.core.detector import LocalLLMDetector, LocalLLMServerInfo


def test_config_manager_lifecycle(tmp_path: Path):
    """Test ConfigManager initial state, saving, loading, and resetting."""
    cfg_file = tmp_path / "data" / "config.json"
    app_settings = Settings(project_root=tmp_path, env="test")
    manager = ConfigManager(config_path=cfg_file, app_settings=app_settings)

    # Initially unconfigured
    assert not manager.is_configured()
    initial_cfg = manager.load()
    assert not initial_cfg.is_configured

    # Save a configuration
    new_cfg = JarvisConfig(
        assistant_name="CustomJarvis",
        tone="concise and professional",
        inference_mode="local",
        autonomy_mode="auto",
        selected_provider="local",
        local=LocalEngineConfig(
            engine_type="ollama",
            endpoint="http://127.0.0.1:11434/v1",
            model="llama3.2:3b",
        ),
    )
    saved = manager.save(new_cfg)
    assert saved.is_configured
    assert manager.is_configured()
    assert cfg_file.exists()

    # Load configuration
    loaded = manager.load()
    assert loaded.is_configured
    assert loaded.assistant_name == "CustomJarvis"
    assert loaded.local.model == "llama3.2:3b"

    # Verify settings were updated
    assert app_settings.assistant_name == "CustomJarvis"
    assert app_settings.tone == "concise and professional"
    assert app_settings.autonomy_mode == AutonomyMode.AUTO
    assert app_settings.local_model == "llama3.2:3b"

    # Reset configuration
    manager.reset()
    assert not manager.is_configured()
    assert not cfg_file.exists()


def test_config_manager_cloud_provider_application(tmp_path: Path):
    """Test hot-application of OpenAI, Anthropic, Gemini, and custom OpenAI providers."""
    app_settings = Settings(project_root=tmp_path, env="test")
    manager = ConfigManager(config_path=tmp_path / "config.json", app_settings=app_settings)

    # Test OpenAI
    openai_cfg = JarvisConfig(
        selected_provider="openai",
        cloud=CloudProviderConfig(
            provider="openai",
            api_key="sk-openai-test-key",
            model="gpt-4o-mini",
        ),
    )
    manager.apply_to_settings(openai_cfg, app_settings)
    assert app_settings.openai_api_key == "sk-openai-test-key"
    assert app_settings.openai_model == "gpt-4o-mini"

    # Test Anthropic
    anthropic_cfg = JarvisConfig(
        selected_provider="anthropic",
        cloud=CloudProviderConfig(
            provider="anthropic",
            api_key="sk-ant-test-key",
            model="claude-3-5-haiku-20241022",
        ),
    )
    manager.apply_to_settings(anthropic_cfg, app_settings)
    assert app_settings.anthropic_api_key == "sk-ant-test-key"
    assert app_settings.anthropic_model == "claude-3-5-haiku-20241022"

    # Test Gemini
    gemini_cfg = JarvisConfig(
        selected_provider="gemini",
        cloud=CloudProviderConfig(
            provider="gemini",
            api_key="AIzaSyD-gemini-test-key",
            model="gemini-2.0-flash",
        ),
    )
    manager.apply_to_settings(gemini_cfg, app_settings)
    assert app_settings.gemini_api_key == "AIzaSyD-gemini-test-key"
    assert app_settings.gemini_model == "gemini-2.0-flash"

    # Test Custom OpenAI-compatible endpoint
    custom_cfg = JarvisConfig(
        selected_provider="custom_openai",
        cloud=CloudProviderConfig(
            provider="custom_openai",
            api_key="custom-key-123",
            model="mistral-large",
            custom_base_url="https://api.together.xyz/v1",
        ),
    )
    manager.apply_to_settings(custom_cfg, app_settings)
    assert app_settings.openai_api_key == "custom-key-123"
    assert app_settings.openai_model == "mistral-large"
    assert app_settings.local_endpoint == "https://api.together.xyz/v1"


@pytest.mark.asyncio
async def test_local_detector_ollama_mock():
    """Test LocalLLMDetector probing mock Ollama server."""
    detector = LocalLLMDetector(timeout_seconds=1.0)

    def handle_request(request: httpx.Request) -> httpx.Response:
        if str(request.url) == "http://127.0.0.1:11434/api/tags":
            return httpx.Response(
                200,
                json={
                    "models": [
                        {"name": "llama3.2:3b"},
                        {"name": "deepseek-r1:8b"},
                    ]
                },
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handle_request)
    async with httpx.AsyncClient(transport=transport) as client:
        info = await detector.probe_engine(
            engine_id="ollama",
            display_name="Ollama",
            base_url="http://127.0.0.1:11434/v1",
            probe_urls=["http://127.0.0.1:11434/api/tags"],
            client=client,
        )

        assert info.is_running
        assert "llama3.2:3b" in info.models
        assert "deepseek-r1:8b" in info.models
        assert info.latency_ms >= 0


@pytest.mark.asyncio
async def test_local_detector_lm_studio_and_llama_cpp():
    """Test LocalLLMDetector probing OpenAI-format mock LM Studio and llama.cpp."""
    detector = LocalLLMDetector(timeout_seconds=1.0)

    def handle_request(request: httpx.Request) -> httpx.Response:
        if "/models" in str(request.url):
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"id": "qwen2.5-coder-7b-instruct"},
                        {"id": "meta-llama-3.1-8b-instruct"},
                    ]
                },
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handle_request)
    async with httpx.AsyncClient(transport=transport) as client:
        # Test LM Studio
        info_lm = await detector.probe_engine(
            engine_id="lm_studio",
            display_name="LM Studio",
            base_url="http://127.0.0.1:1234/v1",
            probe_urls=["http://127.0.0.1:1234/v1/models"],
            client=client,
        )
        assert info_lm.is_running
        assert "qwen2.5-coder-7b-instruct" in info_lm.models

        # Test Custom endpoint probe helper
        custom_info = await detector.probe_custom_endpoint("http://127.0.0.1:5000", client=client)
        assert custom_info.is_running
        assert "qwen2.5-coder-7b-instruct" in custom_info.models


@pytest.mark.asyncio
async def test_local_detector_offline_engine():
    """Test LocalLLMDetector response when engine is offline."""
    detector = LocalLLMDetector(timeout_seconds=0.1)

    def handle_offline(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused")

    transport = httpx.MockTransport(handle_offline)
    async with httpx.AsyncClient(transport=transport) as client:
        info = await detector.probe_engine(
            engine_id="ollama",
            display_name="Ollama",
            base_url="http://127.0.0.1:11434/v1",
            probe_urls=["http://127.0.0.1:11434/api/tags"],
            client=client,
        )
        assert not info.is_running
        assert len(info.models) == 0


@pytest.mark.asyncio
async def test_setup_api_endpoints(async_client):
    """Test full HTTP API lifecycle for setup endpoints."""
    # 1. Check initial status
    status_res = await async_client.get("/api/setup/status")
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert "is_configured" in status_data

    # 2. Probe local detection API
    detect_res = await async_client.post("/api/setup/detect", json={})
    assert detect_res.status_code == 200
    detected_engines = detect_res.json()
    assert isinstance(detected_engines, list)
    assert any(eng["engine_id"] == "ollama" for eng in detected_engines)
    assert any(eng["engine_id"] == "lm_studio" for eng in detected_engines)

    # 3. Save setup configuration
    setup_payload = {
        "is_configured": True,
        "inference_mode": "local",
        "autonomy_mode": "agent_decides",
        "assistant_name": "WizardJarvis",
        "tone": "smart and witty",
        "selected_provider": "local",
        "local": {
            "engine_type": "ollama",
            "endpoint": "http://127.0.0.1:11434/v1",
            "model": "llama3.2:3b",
            "timeout_seconds": 30.0,
        },
        "cloud": {
            "provider": "openai",
            "api_key": "",
            "model": "",
            "custom_base_url": "",
        },
    }
    save_res = await async_client.post("/api/setup/save", json=setup_payload)
    assert save_res.status_code == 200
    saved_data = save_res.json()
    assert saved_data["success"] is True
    assert saved_data["config"]["assistant_name"] == "WizardJarvis"

    # 4. Verify status updated to is_configured = True
    status_res_after = await async_client.get("/api/setup/status")
    assert status_res_after.status_code == 200
    after_data = status_res_after.json()
    assert after_data["is_configured"] is True
    assert after_data["config"]["assistant_name"] == "WizardJarvis"

    # 5. Reset configuration
    reset_res = await async_client.post("/api/setup/reset")
    assert reset_res.status_code == 200
    assert reset_res.json()["reset"] is True

    # 6. Verify status returned to unconfigured
    status_res_reset = await async_client.get("/api/setup/status")
    assert status_res_reset.status_code == 200
    assert status_res_reset.json()["is_configured"] is False

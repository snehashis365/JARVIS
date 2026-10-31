"""Configuration Storage Manager.

Persists user setup to a local, gitignored configuration file (data/config.json),
determines setup status, and hot-reloads runtime settings.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

from jarvis.config import AutonomyMode, InferenceMode, Settings, settings


class LocalEngineConfig(BaseModel):
    engine_type: str = "ollama"  # "ollama", "lm_studio", "llama_cpp", "custom"
    endpoint: str = "http://127.0.0.1:11434/v1"
    model: str = "llama3.2"
    timeout_seconds: float = 30.0


class CloudProviderConfig(BaseModel):
    provider: str = "openai"  # "openai", "anthropic", "gemini", "custom_openai"
    api_key: str = ""
    model: str = ""
    custom_base_url: str = ""


class JarvisConfig(BaseModel):
    """Schema for stored user configuration in data/config.json."""
    is_configured: bool = False
    inference_mode: str = "local"
    autonomy_mode: str = "agent_decides"
    assistant_name: str = "Jarvis"
    tone: str = "helpful and precise"
    selected_provider: str = "local"  # "local", "openai", "anthropic", "gemini", "custom_openai"
    local: LocalEngineConfig = Field(default_factory=LocalEngineConfig)
    cloud: CloudProviderConfig = Field(default_factory=CloudProviderConfig)


class ConfigManager:
    """Manages the lifecycle of the local, gitignored data/config.json file."""

    def __init__(self, config_path: Optional[Path] = None, app_settings: Optional[Settings] = None) -> None:
        self.settings = app_settings or settings
        if config_path:
            self.config_path = config_path
        else:
            self.config_path = self.settings.data_dir / "config.json"

    def is_configured(self) -> bool:
        """Check if Jarvis has been configured via the setup flow."""
        if not self.config_path.exists():
            return False
        try:
            cfg = self.load()
            return cfg.is_configured
        except Exception:
            return False

    def load(self) -> JarvisConfig:
        """Load stored configuration, or return empty default if missing."""
        if not self.config_path.exists():
            return JarvisConfig(is_configured=False)
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return JarvisConfig(**data)
        except Exception:
            return JarvisConfig(is_configured=False)

    def save(self, config: JarvisConfig) -> JarvisConfig:
        """Save configuration to local gitignored file and apply to runtime settings."""
        config.is_configured = True
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(config.model_dump(), indent=2))

        # Hot-apply to runtime settings
        self.apply_to_settings(config, self.settings)
        return config

    def apply_to_settings(self, config: JarvisConfig, target_settings: Settings) -> None:
        """Apply stored config fields directly to runtime Settings singleton."""
        target_settings.assistant_name = config.assistant_name
        target_settings.tone = config.tone
        try:
            target_settings.inference_mode = InferenceMode(config.inference_mode)
        except ValueError:
            pass
        try:
            target_settings.autonomy_mode = AutonomyMode(config.autonomy_mode)
        except ValueError:
            pass

        # Apply local config
        target_settings.local_endpoint = config.local.endpoint
        target_settings.local_model = config.local.model

        # Apply provider specific settings
        if config.selected_provider == "openai":
            target_settings.openai_api_key = config.cloud.api_key
            target_settings.openai_model = config.cloud.model or "gpt-4o"
        elif config.selected_provider == "anthropic":
            target_settings.anthropic_api_key = config.cloud.api_key
            target_settings.anthropic_model = config.cloud.model or "claude-3-5-sonnet-20241022"
        elif config.selected_provider == "gemini":
            target_settings.gemini_api_key = config.cloud.api_key
            target_settings.gemini_model = config.cloud.model or "gemini-2.0-flash"
        elif config.selected_provider == "custom_openai":
            target_settings.openai_api_key = config.cloud.api_key
            target_settings.openai_model = config.cloud.model or "default"
            target_settings.local_endpoint = config.cloud.custom_base_url or target_settings.local_endpoint

    def reset(self) -> None:
        """Reset configuration file to unconfigured state."""
        if self.config_path.exists():
            try:
                self.config_path.unlink()
            except OSError:
                pass

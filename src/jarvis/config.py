"""Jarvis Configuration Management.

Handles application configuration, paths, assistant identity, operating modes,
and provider settings using Pydantic Settings.
"""

from enum import Enum
from pathlib import Path
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class InferenceMode(str, Enum):
    """Inference execution mode."""
    LOCAL = "local"
    CLOUD = "cloud"
    HYBRID = "hybrid"


class AutonomyMode(str, Enum):
    """Deterministic autonomy level."""
    PLAN = "plan"
    AGENT_DECIDES = "agent_decides"
    AUTO = "auto"
    SANDBOX_ONLY = "sandbox_only"


class FormalityLevel(str, Enum):
    """Assistant tone formality level."""
    CASUAL = "casual"
    BALANCED = "balanced"
    FORMAL = "formal"


class VerbosityLevel(str, Enum):
    """Assistant response verbosity level."""
    TERSE = "terse"
    CONCISE = "concise"
    DETAILED = "detailed"


class Settings(BaseSettings):
    """Application-wide configuration settings."""

    # Project paths
    project_root: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent.parent.parent
    )

    # Server settings
    env: str = Field(default="development", alias="JARVIS_ENV")
    host: str = Field(default="127.0.0.1", alias="JARVIS_HOST")
    port: int = Field(default=8000, alias="JARVIS_PORT")
    log_level: str = Field(default="INFO", alias="JARVIS_LOG_LEVEL")

    # Assistant Identity & Personality
    assistant_name: str = Field(default="Jarvis", alias="JARVIS_NAME")
    tone: str = Field(default="helpful and precise", alias="JARVIS_TONE")
    formality: FormalityLevel = Field(default=FormalityLevel.BALANCED, alias="JARVIS_FORMALITY")
    verbosity: VerbosityLevel = Field(default=VerbosityLevel.CONCISE, alias="JARVIS_VERBOSITY")
    proactivity: float = Field(default=0.5, ge=0.0, le=1.0, alias="JARVIS_PROACTIVITY")

    # Operating & Autonomy Modes
    inference_mode: InferenceMode = Field(default=InferenceMode.LOCAL, alias="JARVIS_INFERENCE_MODE")
    autonomy_mode: AutonomyMode = Field(default=AutonomyMode.AGENT_DECIDES, alias="JARVIS_AUTONOMY_MODE")

    # Local Provider Settings
    local_endpoint: str = Field(default="http://127.0.0.1:11434/v1", alias="JARVIS_LOCAL_ENDPOINT")
    local_model: str = Field(default="llama3.2", alias="JARVIS_LOCAL_MODEL")
    local_timeout_seconds: float = Field(default=30.0, alias="JARVIS_LOCAL_TIMEOUT")

    # Hosted Providers (Optional)
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o", alias="OPENAI_MODEL")

    anthropic_api_key: Optional[str] = Field(default=None, alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(default="claude-3-5-sonnet-20241022", alias="ANTHROPIC_MODEL")

    gemini_api_key: Optional[str] = Field(default=None, alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-2.0-flash", alias="GEMINI_MODEL")

    # Execution Bounds
    max_orchestrator_steps: int = Field(default=10, alias="JARVIS_MAX_STEPS")
    orchestrator_timeout_seconds: float = Field(default=60.0, alias="JARVIS_TIMEOUT_SECONDS")

    # Cloud Sync Settings (Optional)
    sync_enabled: bool = Field(default=False, alias="JARVIS_SYNC_ENABLED")
    sync_server_url: Optional[str] = Field(default=None, alias="JARVIS_SYNC_SERVER_URL")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True
    )

    @property
    def data_dir(self) -> Path:
        """Absolute path to application data directory inside project root."""
        d = self.project_root / "data"
        try:
            d.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        return d

    @property
    def db_path(self) -> Path:
        """Absolute path to SQLite database."""
        return self.data_dir / "jarvis.db"

    @property
    def logs_dir(self) -> Path:
        """Absolute path to logs directory inside project root."""
        d = self.project_root / "logs"
        try:
            d.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        return d


# Global settings singleton
settings = Settings()

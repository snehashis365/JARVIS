"""LLM Provider Factory.

Instantiates and configures provider adapters according to active settings,
locality, and model capabilities.
"""

from typing import Optional
from jarvis.config import InferenceMode, Settings, settings
from jarvis.providers.anthropic import AnthropicProvider
from jarvis.providers.base import BaseLLMProvider
from jarvis.providers.gemini import GeminiProvider
from jarvis.providers.mock import MockProvider
from jarvis.providers.openai_compatible import OpenAICompatibleProvider


class ProviderFactory:
    """Creates provider adapter instances."""

    @staticmethod
    def get_provider(
        app_settings: Optional[Settings] = None,
        force_mock: bool = False,
        prefer_cloud: bool = False,
        model_override: Optional[str] = None
    ) -> BaseLLMProvider:
        """Resolve and instantiate the appropriate provider."""
        cfg = app_settings or settings

        if force_mock or cfg.env == "test":
            return MockProvider(model_name=model_override or "mock-model")

        mode = cfg.inference_mode

        # If in Cloud mode or Hybrid requesting cloud
        if mode == InferenceMode.CLOUD or (mode == InferenceMode.HYBRID and prefer_cloud):
            # Check configured hosted keys
            if cfg.anthropic_api_key:
                return AnthropicProvider(
                    api_key=cfg.anthropic_api_key,
                    model_name=model_override or cfg.anthropic_model
                )
            if cfg.gemini_api_key:
                return GeminiProvider(
                    api_key=cfg.gemini_api_key,
                    model_name=model_override or cfg.gemini_model
                )
            if cfg.openai_api_key:
                return OpenAICompatibleProvider(
                    base_url="https://api.openai.com/v1",
                    api_key=cfg.openai_api_key,
                    model_name=model_override or cfg.openai_model,
                    provider_name="openai"
                )

        # Default: Local Provider (Ollama / LM Studio / llama.cpp)
        return OpenAICompatibleProvider(
            base_url=cfg.local_endpoint,
            model_name=model_override or cfg.local_model,
            timeout_seconds=cfg.local_timeout_seconds,
            provider_name="local_openai_compatible"
        )

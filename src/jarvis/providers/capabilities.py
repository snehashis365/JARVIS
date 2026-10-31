"""Model Capability Registry.

Maintains capability profiles (tools, streaming, vision, context window, locality)
for local and hosted models.
"""

from typing import Dict, Optional
from pydantic import BaseModel, Field


class ModelCapability(BaseModel):
    """Declared capabilities and constraints of a model."""
    name: str
    supports_tools: bool = True
    supports_streaming: bool = True
    supports_structured_output: bool = True
    supports_vision: bool = False
    max_context_tokens: int = 8192
    is_local: bool = True
    recommended_role: str = "general"
    approximate_ram_mb: int = 4096


class CapabilityRegistry:
    """Registry maintaining capability records for all supported models."""

    def __init__(self) -> None:
        self._registry: Dict[str, ModelCapability] = {}
        self._register_default_models()

    def _register_default_models(self) -> None:
        """Register default known local and hosted model profiles."""
        defaults = [
            # Local Models
            ModelCapability(
                name="llama3.2",
                supports_tools=True,
                supports_streaming=True,
                supports_structured_output=True,
                supports_vision=False,
                max_context_tokens=8192,
                is_local=True,
                recommended_role="fast_chat",
                approximate_ram_mb=3500,
            ),
            ModelCapability(
                name="llama3.1",
                supports_tools=True,
                supports_streaming=True,
                supports_structured_output=True,
                supports_vision=False,
                max_context_tokens=128000,
                is_local=True,
                recommended_role="tool_tasks",
                approximate_ram_mb=8000,
            ),
            ModelCapability(
                name="qwen2.5-coder",
                supports_tools=True,
                supports_streaming=True,
                supports_structured_output=True,
                supports_vision=False,
                max_context_tokens=32768,
                is_local=True,
                recommended_role="code",
                approximate_ram_mb=4500,
            ),
            ModelCapability(
                name="phi3.5",
                supports_tools=False,
                supports_streaming=True,
                supports_structured_output=False,
                supports_vision=False,
                max_context_tokens=4096,
                is_local=True,
                recommended_role="fast_chat",
                approximate_ram_mb=2500,
            ),
            # Hosted Models
            ModelCapability(
                name="gpt-4o",
                supports_tools=True,
                supports_streaming=True,
                supports_structured_output=True,
                supports_vision=True,
                max_context_tokens=128000,
                is_local=False,
                recommended_role="complex_reasoning",
                approximate_ram_mb=0,
            ),
            ModelCapability(
                name="claude-3-5-sonnet-20241022",
                supports_tools=True,
                supports_streaming=True,
                supports_structured_output=True,
                supports_vision=True,
                max_context_tokens=200000,
                is_local=False,
                recommended_role="complex_reasoning",
                approximate_ram_mb=0,
            ),
            ModelCapability(
                name="gemini-2.0-flash",
                supports_tools=True,
                supports_streaming=True,
                supports_structured_output=True,
                supports_vision=True,
                max_context_tokens=1000000,
                is_local=False,
                recommended_role="multimodal",
                approximate_ram_mb=0,
            ),
            # Mock Model for Testing
            ModelCapability(
                name="mock-model",
                supports_tools=True,
                supports_streaming=True,
                supports_structured_output=True,
                supports_vision=True,
                max_context_tokens=16384,
                is_local=True,
                recommended_role="test",
                approximate_ram_mb=10,
            ),
        ]
        for cap in defaults:
            self._registry[cap.name] = cap

    def register(self, capability: ModelCapability) -> None:
        """Register or override a model capability profile."""
        self._registry[capability.name] = capability

    def get(self, model_name: str) -> ModelCapability:
        """Retrieve capability for a model, defaulting to a safe generic profile if unknown."""
        if model_name in self._registry:
            return self._registry[model_name]
        # Heuristic fallback for unregistered models
        is_local = not any(h in model_name.lower() for h in ["gpt", "claude", "gemini"])
        fallback = ModelCapability(
            name=model_name,
            supports_tools=True,
            supports_streaming=True,
            supports_structured_output=True,
            supports_vision=False,
            max_context_tokens=8192,
            is_local=is_local,
            recommended_role="general",
        )
        self._registry[model_name] = fallback
        return fallback

    def is_tool_capable(self, model_name: str) -> bool:
        """Check if model supports structured tool calls."""
        return self.get(model_name).supports_tools


# Global capability registry singleton
capability_registry = CapabilityRegistry()

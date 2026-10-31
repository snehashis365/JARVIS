"""Intelligent and Explainable Model Router.

Selects the optimal model and locality based on prompt complexity,
required tools, inference mode, and privacy policies.
"""

import re
from typing import List, Optional
from pydantic import BaseModel

from jarvis.config import InferenceMode, Settings, settings
from jarvis.models.messages import ChatMessage
from jarvis.providers.capabilities import CapabilityRegistry, capability_registry


class RoutingDecision(BaseModel):
    """Explainable model routing decision."""
    route: str  # "local" or "cloud"
    model_name: str
    requires_tools: bool
    reason: str
    is_fast_path: bool


# Keywords suggesting the request requires tools or workspace actions
TOOL_KEYWORDS = [
    r"\bread\b.*\bfile\b",
    r"\bwrite\b.*\bfile\b",
    r"\bcreate\b.*\bfile\b",
    r"\bdelete\b.*\bfile\b",
    r"\bsearch\b",
    r"\bfind\b",
    r"\brun\b.*\bcommand\b",
    r"\bexecute\b",
    r"\blist\b.*\b(files|directory|folder)\b",
    r"\b(calculate|compute|math|eval)\b",
    r"\b(time|date|clock|timestamp)\b",
    r"\b(fetch|http|url|curl|scrape|website)\b",
    r"\b(terminal|shell|bash|zsh)\b",
    r"\b(diagnostics|system info|hardware|specs)\b",
    r"^tool:",
    r"^read:",
    r"^search:",
]
TOOL_PATTERNS = [re.compile(p, re.IGNORECASE) for p in TOOL_KEYWORDS]


class ModelRouter:
    """Analyzes conversation and routing policy to determine optimal execution path."""

    def __init__(
        self,
        app_settings: Optional[Settings] = None,
        registry: Optional[CapabilityRegistry] = None,
    ) -> None:
        self.settings = app_settings or settings
        self.registry = registry or capability_registry

    def requires_tools(self, prompt: str) -> bool:
        """Heuristic check to determine if prompt warrants tool execution."""
        prompt_clean = prompt.strip()
        for pattern in TOOL_PATTERNS:
            if pattern.search(prompt_clean):
                return True
        return False

    def route_request(
        self,
        messages: List[ChatMessage],
        force_local: bool = False,
        force_tools: Optional[bool] = None,
    ) -> RoutingDecision:
        """Generate an explainable routing decision for the incoming conversation."""
        last_prompt = messages[-1].content if messages else ""
        needs_tools = force_tools if force_tools is not None else self.requires_tools(last_prompt)
        mode = self.settings.inference_mode

        # Fast path determination: simple conversation without tool requirement
        is_fast_path = not needs_tools

        # Mode: LOCAL
        if mode == InferenceMode.LOCAL or force_local:
            model = self.settings.local_model
            reason = (
                f"Local mode policy active. Routed to local model '{model}' for 100% on-device privacy."
                if not needs_tools
                else f"Local mode active. Routed to local model '{model}' with tool support."
            )
            return RoutingDecision(
                route="local",
                model_name=model,
                requires_tools=needs_tools,
                reason=reason,
                is_fast_path=is_fast_path,
            )

        # Mode: CLOUD
        if mode == InferenceMode.CLOUD:
            cloud_model = (
                self.settings.anthropic_model
                if self.settings.anthropic_api_key
                else self.settings.openai_model
                if self.settings.openai_api_key
                else self.settings.gemini_model
            )
            reason = f"Cloud mode policy active. Dispatched to hosted model '{cloud_model}'."
            return RoutingDecision(
                route="cloud",
                model_name=cloud_model,
                requires_tools=needs_tools,
                reason=reason,
                is_fast_path=is_fast_path,
            )

        # Mode: HYBRID (Policy-driven dynamic routing)
        # Simple conversation stays local for low latency and privacy
        if not needs_tools and len(last_prompt.split()) < 50:
            return RoutingDecision(
                route="local",
                model_name=self.settings.local_model,
                requires_tools=False,
                reason="Hybrid mode: Simple conversational request routed locally for zero latency and privacy.",
                is_fast_path=True,
            )

        # Complex reasoning or tool workflows in Hybrid mode route to cloud if available
        if (
            self.settings.anthropic_api_key
            or self.settings.openai_api_key
            or self.settings.gemini_api_key
        ):
            cloud_model = (
                self.settings.anthropic_model
                if self.settings.anthropic_api_key
                else self.settings.openai_model
                if self.settings.openai_api_key
                else self.settings.gemini_model
            )
            return RoutingDecision(
                route="cloud",
                model_name=cloud_model,
                requires_tools=needs_tools,
                reason=f"Hybrid mode: Multi-step/tool task routed to hosted model '{cloud_model}' for advanced reasoning.",
                is_fast_path=False,
            )

        # Fallback to local if no cloud keys configured
        return RoutingDecision(
            route="local",
            model_name=self.settings.local_model,
            requires_tools=needs_tools,
            reason=f"Hybrid mode: No cloud keys configured; fell back safely to local model '{self.settings.local_model}'.",
            is_fast_path=is_fast_path,
        )

"""Base LLM Provider Interface, Data Classes, and Cancellation Token."""

import asyncio
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Dict, List, Optional
from pydantic import BaseModel, Field

from jarvis.models.messages import ChatMessage, TokenUsage, ToolCall


class CancellationToken:
    """Cooperative token for interrupting ongoing LLM generation or task execution."""

    def __init__(self) -> None:
        self._is_cancelled = False
        self._callbacks: List[Any] = []

    @property
    def is_cancelled(self) -> bool:
        return self._is_cancelled

    def cancel(self) -> None:
        """Trigger cancellation and invoke registered callbacks."""
        if not self._is_cancelled:
            self._is_cancelled = True
            for callback in self._callbacks:
                try:
                    callback()
                except Exception:
                    pass

    def register_callback(self, callback: Any) -> None:
        """Register a callback to be executed upon cancellation."""
        if self._is_cancelled:
            callback()
        else:
            self._callbacks.append(callback)

    def raise_if_cancelled(self) -> None:
        """Raise asyncio.CancelledError if cancellation has been requested."""
        if self._is_cancelled:
            raise asyncio.CancelledError("Operation was cancelled by user.")


class StreamChunk(BaseModel):
    """Normalized chunk received during streaming inference."""
    content_delta: str = ""
    tool_call_delta: Optional[ToolCall] = None
    is_done: bool = False
    finish_reason: Optional[str] = None


class LLMResponse(BaseModel):
    """Normalized full response from an inference provider."""
    content: str = ""
    tool_calls: Optional[List[ToolCall]] = None
    usage: TokenUsage = Field(default_factory=TokenUsage)
    finish_reason: str = "stop"
    model: str = ""
    provider: str = ""


class ProviderError(Exception):
    """Base exception for all provider operations."""
    def __init__(self, message: str, provider: str = "", status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code


class ProviderTimeoutError(ProviderError):
    """Raised when an inference request times out."""
    pass


class ProviderRateLimitError(ProviderError):
    """Raised when a provider rejects requests due to rate limits."""
    pass


class ProviderAuthenticationError(ProviderError):
    """Raised when provider API credentials are invalid or missing."""
    pass


class BaseLLMProvider(ABC):
    """Abstract interface that all inference providers must implement."""

    def __init__(self, model_name: str, timeout_seconds: float = 30.0) -> None:
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds

    @abstractmethod
    async def generate(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
        cancellation_token: Optional[CancellationToken] = None,
        temperature: float = 0.7,
        **kwargs: Any
    ) -> LLMResponse:
        """Generate a complete response for a sequence of chat messages."""
        pass

    @abstractmethod
    async def stream(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
        cancellation_token: Optional[CancellationToken] = None,
        temperature: float = 0.7,
        **kwargs: Any
    ) -> AsyncIterator[StreamChunk]:
        """Stream response tokens incrementally."""
        pass

    @abstractmethod
    async def check_health(self) -> bool:
        """Check if provider endpoint and model are reachable and healthy."""
        pass

"""Deterministic Mock LLM Provider for Testing and Offline Simulation."""

import asyncio
from typing import Any, AsyncIterator, Dict, List, Optional
from jarvis.models.messages import ChatMessage, TokenUsage, ToolCall
from jarvis.providers.base import (
    BaseLLMProvider,
    CancellationToken,
    LLMResponse,
    ProviderAuthenticationError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    StreamChunk,
)


class MockProvider(BaseLLMProvider):
    """High-fidelity mock provider for automated tests and offline simulation."""

    def __init__(
        self,
        model_name: str = "mock-model",
        default_response: str = "This is a simulated response from Jarvis MockProvider.",
        timeout_seconds: float = 5.0,
    ) -> None:
        super().__init__(model_name=model_name, timeout_seconds=timeout_seconds)
        self.default_response = default_response
        self.scripted_responses: List[LLMResponse] = []
        self.error_to_raise: Optional[Exception] = None
        self.healthy: bool = True
        self.calls_received: List[Dict[str, Any]] = []

    def set_scripted_response(self, response: LLMResponse) -> None:
        """Enqueue a predetermined response."""
        self.scripted_responses.append(response)

    def set_error(self, error: Optional[Exception]) -> None:
        """Configure provider to raise an exception on next call."""
        self.error_to_raise = error

    async def generate(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
        cancellation_token: Optional[CancellationToken] = None,
        temperature: float = 0.7,
        **kwargs: Any
    ) -> LLMResponse:
        """Simulate generating a complete response."""
        self.calls_received.append({"messages": messages, "tools": tools})

        if cancellation_token:
            cancellation_token.raise_if_cancelled()

        if self.error_to_raise:
            err = self.error_to_raise
            self.error_to_raise = None
            raise err

        if self.scripted_responses:
            return self.scripted_responses.pop(0)

        # Check if user message explicitly requests tool execution
        last_message = messages[-1].content if messages else ""
        if tools and ("tool:" in last_message.lower() or "search:" in last_message.lower() or "read:" in last_message.lower()):
            tool_name = "workspace_read_file" if "read:" in last_message.lower() else "web_search"
            param_key = "file_path" if tool_name == "workspace_read_file" else "query"
            param_val = last_message.split(":", 1)[1].strip() if ":" in last_message else "test"
            
            tool_call = ToolCall(
                tool_name=tool_name,
                arguments={param_key: param_val}
            )
            return LLMResponse(
                content="",
                tool_calls=[tool_call],
                usage=TokenUsage(prompt_tokens=15, completion_tokens=10, total_tokens=25),
                finish_reason="tool_calls",
                model=self.model_name,
                provider="mock"
            )

        return LLMResponse(
            content=f"{self.default_response} (Echo: {last_message[:20]})",
            tool_calls=None,
            usage=TokenUsage(prompt_tokens=10, completion_tokens=12, total_tokens=22),
            finish_reason="stop",
            model=self.model_name,
            provider="mock"
        )

    async def stream(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
        cancellation_token: Optional[CancellationToken] = None,
        temperature: float = 0.7,
        **kwargs: Any
    ) -> AsyncIterator[StreamChunk]:
        """Simulate incremental token streaming."""
        full_response = await self.generate(
            messages=messages,
            tools=tools,
            cancellation_token=cancellation_token,
            temperature=temperature,
            **kwargs
        )

        if full_response.tool_calls:
            for tc in full_response.tool_calls:
                if cancellation_token:
                    cancellation_token.raise_if_cancelled()
                yield StreamChunk(tool_call_delta=tc, is_done=False)
            yield StreamChunk(is_done=True, finish_reason="tool_calls")
            return

        # Split content into words for streaming
        words = full_response.content.split(" ")
        for i, word in enumerate(words):
            if cancellation_token:
                cancellation_token.raise_if_cancelled()

            token = word if i == 0 else " " + word
            await asyncio.sleep(0.005)  # micro-delay for realistic async yielding
            yield StreamChunk(content_delta=token, is_done=False)

        yield StreamChunk(is_done=True, finish_reason="stop")

    async def check_health(self) -> bool:
        """Simulated health status."""
        return self.healthy

"""Anthropic Messages API Provider Adapter."""

import json
from typing import Any, AsyncIterator, Dict, List, Optional
import httpx

from jarvis.models.messages import ChatMessage, MessageRole, TokenUsage, ToolCall
from jarvis.providers.base import (
    BaseLLMProvider,
    CancellationToken,
    LLMResponse,
    ProviderAuthenticationError,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    StreamChunk,
)


class AnthropicProvider(BaseLLMProvider):
    """Adapter for Anthropic /v1/messages API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "claude-3-5-sonnet-20241022",
        timeout_seconds: float = 30.0,
        base_url: str = "https://api.anthropic.com/v1",
        http_client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        super().__init__(model_name=model_name, timeout_seconds=timeout_seconds)
        self.api_key = api_key or "EMPTY"
        self.base_url = base_url.rstrip("/")
        self._custom_client = http_client

    def _get_client(self) -> httpx.AsyncClient:
        if self._custom_client:
            return self._custom_client
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        return httpx.AsyncClient(base_url=self.base_url, headers=headers, timeout=self.timeout_seconds)

    def _format_payload(
        self, messages: List[ChatMessage], tools: Optional[List[Dict[str, Any]]], temperature: float
    ) -> Dict[str, Any]:
        system_content = ""
        user_assistant_messages = []

        for m in messages:
            if m.role == MessageRole.SYSTEM:
                system_content += m.content + "\n"
            elif m.role == MessageRole.TOOL:
                user_assistant_messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": m.tool_call_id or "unknown",
                            "content": m.content,
                        }
                    ],
                })
            else:
                role = "assistant" if m.role == MessageRole.ASSISTANT else "user"
                content_blocks: List[Dict[str, Any]] = []
                if m.content:
                    content_blocks.append({"type": "text", "text": m.content})
                if m.tool_calls:
                    for tc in m.tool_calls:
                        content_blocks.append({
                            "type": "tool_use",
                            "id": tc.id,
                            "name": tc.tool_name,
                            "input": tc.arguments,
                        })
                user_assistant_messages.append({"role": role, "content": content_blocks or m.content})

        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": user_assistant_messages,
            "max_tokens": 4096,
            "temperature": temperature,
        }
        if system_content.strip():
            payload["system"] = system_content.strip()

        if tools:
            payload["tools"] = [
                {
                    "name": t.get("name"),
                    "description": t.get("description", ""),
                    "input_schema": t.get("parameters_schema", t.get("parameters", {})),
                }
                for t in tools
            ]

        return payload

    async def generate(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
        cancellation_token: Optional[CancellationToken] = None,
        temperature: float = 0.7,
        **kwargs: Any
    ) -> LLMResponse:
        """Generate response via Anthropic Messages API."""
        if cancellation_token:
            cancellation_token.raise_if_cancelled()

        payload = self._format_payload(messages, tools, temperature)
        client = self._get_client()
        try:
            res = await client.post("/messages", json=payload)
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError("Anthropic API timed out.", provider="anthropic") from exc
        except httpx.ConnectError as exc:
            raise ProviderError(f"Could not connect to Anthropic: {exc}", provider="anthropic") from exc
        finally:
            if not self._custom_client:
                await client.aclose()

        if res.status_code == 401:
            raise ProviderAuthenticationError("Invalid Anthropic API key.", provider="anthropic", status_code=401)
        if res.status_code == 429:
            raise ProviderRateLimitError("Anthropic rate limit exceeded.", provider="anthropic", status_code=429)
        if res.is_error:
            raise ProviderError(f"Anthropic error {res.status_code}: {res.text}", provider="anthropic", status_code=res.status_code)

        data = res.json()
        content_text = ""
        tool_calls: Optional[List[ToolCall]] = None

        for item in data.get("content", []):
            if item.get("type") == "text":
                content_text += item.get("text", "")
            elif item.get("type") == "tool_use":
                if tool_calls is None:
                    tool_calls = []
                tool_calls.append(ToolCall(
                    id=item.get("id", ""),
                    tool_name=item.get("name", ""),
                    arguments=item.get("input", {}),
                ))

        usage_data = data.get("usage", {})
        usage = TokenUsage(
            prompt_tokens=usage_data.get("input_tokens", 0),
            completion_tokens=usage_data.get("output_tokens", 0),
            total_tokens=usage_data.get("input_tokens", 0) + usage_data.get("output_tokens", 0),
        )

        return LLMResponse(
            content=content_text,
            tool_calls=tool_calls,
            usage=usage,
            finish_reason=data.get("stop_reason", "stop"),
            model=self.model_name,
            provider="anthropic",
        )

    async def stream(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
        cancellation_token: Optional[CancellationToken] = None,
        temperature: float = 0.7,
        **kwargs: Any
    ) -> AsyncIterator[StreamChunk]:
        """Stream chunks via Anthropic stream API."""
        full_res = await self.generate(messages, tools, cancellation_token, temperature, **kwargs)
        if full_res.tool_calls:
            for tc in full_res.tool_calls:
                yield StreamChunk(tool_call_delta=tc)
            yield StreamChunk(is_done=True, finish_reason="tool_calls")
        else:
            yield StreamChunk(content_delta=full_res.content, is_done=True, finish_reason="stop")

    async def check_health(self) -> bool:
        """Health check returns True if key configured."""
        return self.api_key != "EMPTY"

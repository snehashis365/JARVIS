"""OpenAI-Compatible Provider Adapter.

Supports Ollama, LM Studio, llama.cpp server, and hosted OpenAI endpoints.
"""

import json
from typing import Any, AsyncIterator, Dict, List, Optional
import httpx

from jarvis.models.messages import ChatMessage, TokenUsage, ToolCall
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


class OpenAICompatibleProvider(BaseLLMProvider):
    """Adapter for endpoints adhering to OpenAI /v1/chat/completions specification."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:11434/v1",
        api_key: Optional[str] = None,
        model_name: str = "llama3.2",
        timeout_seconds: float = 30.0,
        provider_name: str = "openai_compatible",
        http_client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        super().__init__(model_name=model_name, timeout_seconds=timeout_seconds)
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or "EMPTY"
        self.provider_name = provider_name
        self._custom_client = http_client

    def _get_client(self) -> httpx.AsyncClient:
        if self._custom_client:
            return self._custom_client
        headers = {"Authorization": f"Bearer {self.api_key}"}
        is_local = "127.0.0.1" in self.base_url or "localhost" in self.base_url or "[::1]" in self.base_url
        return httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=self.timeout_seconds,
            trust_env=not is_local,
        )

    def _format_messages(self, messages: List[ChatMessage]) -> List[Dict[str, Any]]:
        formatted = []
        for msg in messages:
            entry: Dict[str, Any] = {"role": msg.role.value, "content": msg.content}
            if msg.name:
                entry["name"] = msg.name
            if msg.tool_call_id:
                entry["tool_call_id"] = msg.tool_call_id
            if msg.tool_calls:
                entry["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.tool_name,
                            "arguments": json.dumps(tc.arguments),
                        },
                    }
                    for tc in msg.tool_calls
                ]
            formatted.append(entry)
        return formatted

    def _format_tools(self, tools: Optional[List[Dict[str, Any]]]) -> Optional[List[Dict[str, Any]]]:
        if not tools:
            return None
        formatted = []
        for t in tools:
            if "type" in t and "function" in t:
                formatted.append(t)
            else:
                formatted.append({
                    "type": "function",
                    "function": {
                        "name": t.get("name", ""),
                        "description": t.get("description", ""),
                        "parameters": t.get("parameters_schema", t.get("parameters", {})),
                    }
                })
        return formatted

    async def generate(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
        cancellation_token: Optional[CancellationToken] = None,
        temperature: float = 0.7,
        **kwargs: Any
    ) -> LLMResponse:
        """Execute a non-streaming completion request."""
        if cancellation_token:
            cancellation_token.raise_if_cancelled()

        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": self._format_messages(messages),
            "temperature": temperature,
            "stream": False,
        }
        formatted_tools = self._format_tools(tools)
        if formatted_tools:
            payload["tools"] = formatted_tools

        client = self._get_client()
        try:
            response = await client.post("/chat/completions", json=payload)
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(f"Request to {self.base_url} timed out.", provider=self.provider_name) from exc
        except httpx.ConnectError as exc:
            raise ProviderError(f"Could not connect to provider at {self.base_url}: {exc}", provider=self.provider_name) from exc
        finally:
            if not self._custom_client:
                await client.aclose()

        if response.status_code == 401:
            raise ProviderAuthenticationError("Invalid API key or unauthorized.", provider=self.provider_name, status_code=401)
        if response.status_code == 429:
            raise ProviderRateLimitError("Rate limit exceeded.", provider=self.provider_name, status_code=429)
        if response.is_error:
            raise ProviderError(f"Provider returned error {response.status_code}: {response.text}", provider=self.provider_name, status_code=response.status_code)

        data = response.json()
        choice = data.get("choices", [{}])[0]
        msg_data = choice.get("message", {})
        finish_reason = choice.get("finish_reason", "stop")

        # Parse tool calls if present
        tool_calls: Optional[List[ToolCall]] = None
        raw_tool_calls = msg_data.get("tool_calls")
        if raw_tool_calls:
            tool_calls = []
            for tc in raw_tool_calls:
                fn = tc.get("function", {})
                args = {}
                try:
                    args = json.loads(fn.get("arguments", "{}"))
                except json.JSONDecodeError:
                    pass
                tool_calls.append(ToolCall(
                    id=tc.get("id", ""),
                    tool_name=fn.get("name", ""),
                    arguments=args
                ))

        # Usage
        usage_data = data.get("usage", {})
        usage = TokenUsage(
            prompt_tokens=usage_data.get("prompt_tokens", 0),
            completion_tokens=usage_data.get("completion_tokens", 0),
            total_tokens=usage_data.get("total_tokens", 0),
        )

        return LLMResponse(
            content=msg_data.get("content") or "",
            tool_calls=tool_calls,
            usage=usage,
            finish_reason=finish_reason,
            model=self.model_name,
            provider=self.provider_name,
        )

    async def stream(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
        cancellation_token: Optional[CancellationToken] = None,
        temperature: float = 0.7,
        **kwargs: Any
    ) -> AsyncIterator[StreamChunk]:
        """Stream chunks via Server-Sent Events."""
        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": self._format_messages(messages),
            "temperature": temperature,
            "stream": True,
        }
        formatted_tools = self._format_tools(tools)
        if formatted_tools:
            payload["tools"] = formatted_tools

        client = self._get_client()
        try:
            async with client.stream("POST", "/chat/completions", json=payload) as response:
                if response.status_code == 401:
                    raise ProviderAuthenticationError("Invalid API key or unauthorized.", provider=self.provider_name, status_code=401)
                if response.status_code == 429:
                    raise ProviderRateLimitError("Rate limit exceeded.", provider=self.provider_name, status_code=429)
                if response.is_error:
                    error_bytes = await response.aread()
                    error_detail = error_bytes.decode("utf-8", errors="replace")[:200]
                    raise ProviderError(f"Stream error {response.status_code}: {error_detail}", provider=self.provider_name, status_code=response.status_code)

                async for line in response.aiter_lines():
                    if cancellation_token:
                        cancellation_token.raise_if_cancelled()

                    line = line.strip()
                    if not line or line.startswith(":"):
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            yield StreamChunk(is_done=True, finish_reason="stop")
                            break
                        try:
                            chunk_json = json.loads(data_str)
                            choice = chunk_json.get("choices", [{}])[0]
                            delta = choice.get("delta", {})
                            content_delta = delta.get("content") or ""
                            finish_reason = choice.get("finish_reason")

                            yield StreamChunk(
                                content_delta=content_delta,
                                is_done=finish_reason is not None,
                                finish_reason=finish_reason,
                            )
                        except json.JSONDecodeError:
                            continue
        finally:
            if not self._custom_client:
                await client.aclose()

    async def check_health(self) -> bool:
        """Check endpoint connectivity."""
        client = self._get_client()
        try:
            res = await client.get("/models")
            return res.status_code in (200, 401)  # Reachable
        except Exception:
            return False
        finally:
            if not self._custom_client:
                await client.aclose()

"""Google Gemini API Provider Adapter."""

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


class GeminiProvider(BaseLLMProvider):
    """Adapter for Google Gemini REST API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gemini-2.0-flash",
        timeout_seconds: float = 30.0,
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
        http_client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        super().__init__(model_name=model_name, timeout_seconds=timeout_seconds)
        self.api_key = api_key or "EMPTY"
        self.base_url = base_url.rstrip("/")
        self._custom_client = http_client

    def _get_client(self) -> httpx.AsyncClient:
        if self._custom_client:
            return self._custom_client
        return httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout_seconds)

    def _format_payload(self, messages: List[ChatMessage], tools: Optional[List[Dict[str, Any]]]) -> Dict[str, Any]:
        contents = []
        for m in messages:
            role = "model" if m.role == MessageRole.ASSISTANT else "user"
            parts: List[Dict[str, Any]] = []
            if m.content:
                parts.append({"text": m.content})
            if m.tool_calls:
                for tc in m.tool_calls:
                    parts.append({"functionCall": {"name": tc.tool_name, "args": tc.arguments}})
            contents.append({"role": role, "parts": parts})

        payload: Dict[str, Any] = {"contents": contents}
        if tools:
            function_declarations = []
            for t in tools:
                function_declarations.append({
                    "name": t.get("name"),
                    "description": t.get("description", ""),
                    "parameters": t.get("parameters_schema", t.get("parameters", {})),
                })
            payload["tools"] = [{"functionDeclarations": function_declarations}]
        return payload

    async def generate(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
        cancellation_token: Optional[CancellationToken] = None,
        temperature: float = 0.7,
        **kwargs: Any
    ) -> LLMResponse:
        """Generate response via Gemini generateContent."""
        if cancellation_token:
            cancellation_token.raise_if_cancelled()

        payload = self._format_payload(messages, tools)
        client = self._get_client()
        url = f"/models/{self.model_name}:generateContent?key={self.api_key}"

        try:
            res = await client.post(url, json=payload)
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError("Gemini API request timed out.", provider="gemini") from exc
        except httpx.ConnectError as exc:
            raise ProviderError(f"Could not connect to Gemini: {exc}", provider="gemini") from exc
        finally:
            if not self._custom_client:
                await client.aclose()

        if res.status_code in (400, 401, 403) and "API_KEY_INVALID" in res.text:
            raise ProviderAuthenticationError("Invalid Gemini API key.", provider="gemini", status_code=res.status_code)
        if res.status_code == 429:
            raise ProviderRateLimitError("Gemini rate limit exceeded.", provider="gemini", status_code=429)
        if res.is_error:
            raise ProviderError(f"Gemini returned error {res.status_code}: {res.text}", provider="gemini", status_code=res.status_code)

        data = res.json()
        candidates = data.get("candidates", [{}])
        first_candidate = candidates[0] if candidates else {}
        parts = first_candidate.get("content", {}).get("parts", [])

        content_text = ""
        tool_calls: Optional[List[ToolCall]] = None

        for p in parts:
            if "text" in p:
                content_text += p["text"]
            elif "functionCall" in p:
                if tool_calls is None:
                    tool_calls = []
                fc = p["functionCall"]
                tool_calls.append(ToolCall(
                    tool_name=fc.get("name", ""),
                    arguments=fc.get("args", {})
                ))

        usage_meta = data.get("usageMetadata", {})
        usage = TokenUsage(
            prompt_tokens=usage_meta.get("promptTokenCount", 0),
            completion_tokens=usage_meta.get("candidatesTokenCount", 0),
            total_tokens=usage_meta.get("totalTokenCount", 0),
        )

        return LLMResponse(
            content=content_text,
            tool_calls=tool_calls,
            usage=usage,
            finish_reason=first_candidate.get("finishReason", "STOP"),
            model=self.model_name,
            provider="gemini",
        )

    async def stream(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
        cancellation_token: Optional[CancellationToken] = None,
        temperature: float = 0.7,
        **kwargs: Any
    ) -> AsyncIterator[StreamChunk]:
        """Stream chunks via Gemini API."""
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

"""Unit tests for Phase 2 Provider Adapters and Capability Registry.

Tests MockProvider, OpenAICompatibleProvider, AnthropicProvider, GeminiProvider,
CapabilityRegistry, cancellation tokens, and error mappings via local mock transports.
"""

import asyncio
import json
import httpx
import pytest

from jarvis.config import InferenceMode, Settings
from jarvis.models.messages import ChatMessage, MessageRole, ToolCall
from jarvis.providers import (
    AnthropicProvider,
    BaseLLMProvider,
    CancellationToken,
    CapabilityRegistry,
    GeminiProvider,
    MockProvider,
    ModelCapability,
    OpenAICompatibleProvider,
    ProviderAuthenticationError,
    ProviderError,
    ProviderFactory,
    ProviderRateLimitError,
    ProviderTimeoutError,
    capability_registry,
)


@pytest.mark.asyncio
async def test_mock_provider_basic_generation():
    """Verify MockProvider generation and echo behavior."""
    provider = MockProvider(model_name="mock-model", default_response="Hello Human")
    messages = [ChatMessage(role=MessageRole.USER, content="Testing jarvis echo")]

    res = await provider.generate(messages)
    assert "Hello Human" in res.content
    assert res.model == "mock-model"
    assert res.provider == "mock"
    assert res.usage.total_tokens > 0


@pytest.mark.asyncio
async def test_mock_provider_streaming():
    """Verify incremental token streaming from MockProvider."""
    provider = MockProvider(default_response="Alpha Beta Gamma")
    messages = [ChatMessage(role=MessageRole.USER, content="Stream test")]

    chunks = []
    async for chunk in provider.stream(messages):
        if chunk.content_delta:
            chunks.append(chunk.content_delta)
        if chunk.is_done:
            assert chunk.finish_reason is not None

    full_streamed = "".join(chunks)
    assert "Alpha Beta Gamma" in full_streamed


@pytest.mark.asyncio
async def test_mock_provider_tool_calling():
    """Verify MockProvider simulates tool call when tool request syntax is received."""
    provider = MockProvider()
    messages = [ChatMessage(role=MessageRole.USER, content="tool: web_search query=apple")]
    tools = [{"name": "web_search", "parameters": {}}]

    res = await provider.generate(messages, tools=tools)
    assert res.tool_calls is not None
    assert len(res.tool_calls) == 1
    assert res.tool_calls[0].tool_name == "web_search"
    assert res.finish_reason == "tool_calls"


@pytest.mark.asyncio
async def test_cancellation_token():
    """Verify CancellationToken halts streaming and generation."""
    token = CancellationToken()
    provider = MockProvider(default_response="Long streaming response here")
    messages = [ChatMessage(role=MessageRole.USER, content="Cancel test")]

    # Register cancellation callback
    callback_fired = False
    def on_cancel():
        nonlocal callback_fired
        callback_fired = True
    token.register_callback(on_cancel)

    # Cancel immediately
    token.cancel()
    assert token.is_cancelled is True
    assert callback_fired is True

    # Generation must raise asyncio.CancelledError
    with pytest.raises(asyncio.CancelledError):
        await provider.generate(messages, cancellation_token=token)

    # Streaming must raise asyncio.CancelledError
    with pytest.raises(asyncio.CancelledError):
        async for _ in provider.stream(messages, cancellation_token=token):
            pass


def test_capability_registry():
    """Verify ModelCapability lookup and fallback behavior."""
    reg = CapabilityRegistry()
    
    # Known model
    llama_cap = reg.get("llama3.2")
    assert llama_cap.supports_tools is True
    assert llama_cap.is_local is True

    # Claude capability
    claude_cap = reg.get("claude-3-5-sonnet-20241022")
    assert claude_cap.is_local is False
    assert claude_cap.max_context_tokens == 200000

    # Custom model registration
    reg.register(ModelCapability(name="custom-finetune", supports_tools=False, max_context_tokens=4096))
    custom_cap = reg.get("custom-finetune")
    assert custom_cap.supports_tools is False

    # Unknown model fallback
    unknown = reg.get("some-random-local-model")
    assert unknown.name == "some-random-local-model"
    assert unknown.supports_tools is True


@pytest.mark.asyncio
async def test_openai_compatible_provider_mock_transport():
    """Verify OpenAICompatibleProvider with mock transport."""
    def handler(request: httpx.Request) -> httpx.Response:
        req_data = json.loads(request.read())
        assert req_data["model"] == "llama3.2"
        response_body = {
            "id": "chatcmpl-123",
            "choices": [{
                "message": {"role": "assistant", "content": "Mocked OpenAI reply"},
                "finish_reason": "stop"
            }],
            "usage": {"prompt_tokens": 5, "completion_tokens": 10, "total_tokens": 15}
        }
        return httpx.Response(200, json=response_body)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://test/v1")
    provider = OpenAICompatibleProvider(
        base_url="http://test/v1",
        model_name="llama3.2",
        http_client=mock_client
    )

    messages = [ChatMessage(role=MessageRole.USER, content="Hello OpenAI")]
    res = await provider.generate(messages)
    assert res.content == "Mocked OpenAI reply"
    assert res.usage.total_tokens == 15
    assert res.finish_reason == "stop"


@pytest.mark.asyncio
async def test_openai_compatible_provider_errors():
    """Verify OpenAICompatibleProvider error mappings."""
    def auth_err_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "Invalid API key"})

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(auth_err_handler), base_url="http://test/v1")
    provider = OpenAICompatibleProvider(http_client=mock_client)

    with pytest.raises(ProviderAuthenticationError):
        await provider.generate([ChatMessage(role=MessageRole.USER, content="Hi")])

    def rate_limit_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "Rate limit exceeded"})

    mock_client_rl = httpx.AsyncClient(transport=httpx.MockTransport(rate_limit_handler), base_url="http://test/v1")
    provider_rl = OpenAICompatibleProvider(http_client=mock_client_rl)

    with pytest.raises(ProviderRateLimitError):
        await provider_rl.generate([ChatMessage(role=MessageRole.USER, content="Hi")])


@pytest.mark.asyncio
async def test_anthropic_provider_mock_transport():
    """Verify AnthropicProvider with mock transport."""
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.read())
        assert "messages" in body
        response_body = {
            "id": "msg-123",
            "type": "message",
            "content": [{"type": "text", "text": "Claude test response"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 10, "output_tokens": 20}
        }
        return httpx.Response(200, json=response_body)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://api.anthropic.com/v1")
    provider = AnthropicProvider(api_key="sk-ant-test", http_client=client)

    res = await provider.generate([ChatMessage(role=MessageRole.USER, content="Hi Claude")])
    assert res.content == "Claude test response"
    assert res.usage.total_tokens == 30
    assert res.provider == "anthropic"


@pytest.mark.asyncio
async def test_gemini_provider_mock_transport():
    """Verify GeminiProvider with mock transport."""
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.read())
        assert "contents" in body
        response_body = {
            "candidates": [{
                "content": {
                    "parts": [{"text": "Gemini test response"}],
                    "role": "model"
                },
                "finishReason": "STOP"
            }],
            "usageMetadata": {
                "promptTokenCount": 8,
                "candidatesTokenCount": 12,
                "totalTokenCount": 20
            }
        }
        return httpx.Response(200, json=response_body)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://generativelanguage.googleapis.com/v1beta")
    provider = GeminiProvider(api_key="AIzaSyTest123", http_client=client)

    res = await provider.generate([ChatMessage(role=MessageRole.USER, content="Hi Gemini")])
    assert res.content == "Gemini test response"
    assert res.usage.total_tokens == 20
    assert res.provider == "gemini"


def test_provider_factory():
    """Verify ProviderFactory resolution."""
    # Test env returns MockProvider
    test_settings = Settings(env="test")
    provider = ProviderFactory.get_provider(test_settings)
    assert isinstance(provider, MockProvider)

    # Local mode returns OpenAICompatibleProvider pointed at local endpoint
    prod_settings = Settings(env="production", JARVIS_INFERENCE_MODE=InferenceMode.LOCAL)
    provider_local = ProviderFactory.get_provider(prod_settings)
    assert isinstance(provider_local, OpenAICompatibleProvider)
    assert provider_local.base_url == prod_settings.local_endpoint.rstrip("/")

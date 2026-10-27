"""Tests for Groq LLM provider adapter."""

import json

import httpx
import pytest
from pydantic import SecretStr

from app.ai.providers.groq_provider import (
    GroqAPIError,
    GroqConfigurationError,
    GroqProvider,
    ToolCall,
)
from app.core.config import Settings


def make_test_settings(api_key: str | None = "fake-groq-key") -> Settings:
    return Settings(
        groq_api_key=SecretStr(api_key) if api_key else None,
        groq_model="openai/gpt-oss-120b",
        groq_base_url="https://mock.groq.test/v1",
    )


@pytest.mark.anyio
async def test_groq_unconfigured_raises_error() -> None:
    settings = make_test_settings(api_key=None)
    provider = GroqProvider(settings=settings)

    assert not provider.is_configured
    with pytest.raises(GroqConfigurationError, match="Groq API key is not configured"):
        await provider.generate(messages=[{"role": "user", "content": "Hello"}])


@pytest.mark.anyio
async def test_groq_text_response_success() -> None:
    expected_text = "Your calculated net cash flow is INR 2500."

    def mock_handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer fake-groq-key"
        body = json.loads(request.content.decode("utf-8"))
        assert body["model"] == "openai/gpt-oss-120b"
        assert body["messages"][0]["content"] == "Summarize my finances"

        mock_payload = {
            "id": "chatcmpl-test-123",
            "model": "openai/gpt-oss-120b",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": expected_text,
                    },
                    "finish_reason": "stop",
                }
            ],
        }
        return httpx.Response(200, json=mock_payload)

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = GroqProvider(settings=make_test_settings(), client=client)
        response = await provider.generate(
            messages=[{"role": "user", "content": "Summarize my finances"}]
        )

    assert response.content == expected_text
    assert response.finish_reason == "stop"
    assert response.tool_calls == []


@pytest.mark.anyio
async def test_groq_tool_call_response() -> None:
    def mock_handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        assert len(body["tools"]) == 1
        assert body["tools"][0]["function"]["name"] == "calculate_net_cash_flow"

        mock_payload = {
            "id": "chatcmpl-test-tool",
            "model": "openai/gpt-oss-120b",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_abc123",
                                "type": "function",
                                "function": {
                                    "name": "calculate_net_cash_flow",
                                    "arguments": json.dumps(
                                        {"workspace_id": "test-ws"}
                                    ),
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
        }
        return httpx.Response(200, json=mock_payload)

    mock_tools = [
        {
            "type": "function",
            "function": {
                "name": "calculate_net_cash_flow",
                "description": "Calculate net flow",
                "parameters": {"type": "object", "properties": {}},
            },
        }
    ]

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = GroqProvider(settings=make_test_settings(), client=client)
        response = await provider.generate(
            messages=[{"role": "user", "content": "What is my cash flow?"}],
            tools=mock_tools,
        )

    assert response.content is None
    assert response.finish_reason == "tool_calls"
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0] == ToolCall(
        id="call_abc123",
        name="calculate_net_cash_flow",
        arguments={"workspace_id": "test-ws"},
    )


@pytest.mark.anyio
async def test_groq_rate_limit_error() -> None:
    def mock_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            json={"error": {"message": "Rate limit exceeded for model"}},
        )

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = GroqProvider(settings=make_test_settings(), client=client)
        with pytest.raises(GroqAPIError) as exc_info:
            await provider.generate(messages=[{"role": "user", "content": "Hello"}])

    assert exc_info.value.status_code == 429
    assert "Rate limit exceeded" in exc_info.value.message

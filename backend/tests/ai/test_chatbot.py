"""Unit tests for the Conversational Assistant (chatbot.py)."""

import json
from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr

from app.ai.chatbot import AIValidationError, chat_with_workspace
from app.ai.providers.groq_provider import GroqProvider
from app.core.config import Settings


def load_fixture(filename: str) -> dict:
    repo_root = Path(__file__).resolve().parents[3]
    fixture_path = repo_root / "contracts" / "examples" / filename
    with open(fixture_path, encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.anyio
async def test_chat_greeting_offline() -> None:
    data = load_fixture("bank-statement.json")
    unconfigured_provider = GroqProvider(settings=Settings(groq_api_key=None))

    response = await chat_with_workspace(
        message="Hello! Who are you?",
        workspace_data=data,
        provider=unconfigured_provider,
    )

    assert "FinGenie" in response.text
    assert response.calculation_ids == []
    assert response.source_refs == []
    assert response.disclaimer == "This is not financial advice."


@pytest.mark.anyio
async def test_chat_financial_query_offline() -> None:
    data = load_fixture("bank-statement.json")
    unconfigured_provider = GroqProvider(settings=Settings(groq_api_key=None))

    response = await chat_with_workspace(
        message="What is my net cash flow this month?",
        workspace_data=data,
        provider=unconfigured_provider,
    )

    assert "2500" in response.text
    assert "bank.net_cash_flow.v1" in response.calculation_ids
    assert len(response.source_refs) == 1
    assert response.source_refs[0].source_rows == [6, 7, 8]
    assert response.disclaimer == "This is not financial advice."


@pytest.mark.anyio
async def test_chat_balance_sheet_working_capital_offline() -> None:
    data = load_fixture("balance-sheet.json")
    unconfigured_provider = GroqProvider(settings=Settings(groq_api_key=None))

    response = await chat_with_workspace(
        message="Calculate my working capital please",
        workspace_data=data,
        provider=unconfigured_provider,
    )

    assert "7000000" in response.text
    assert "balance_sheet.working_capital.v1" in response.calculation_ids
    assert response.disclaimer == "This is not financial advice."


@pytest.mark.anyio
async def test_chat_tool_calling_loop_with_mocked_groq() -> None:
    data = load_fixture("bank-statement.json")
    call_count = 0

    def mock_handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        body = json.loads(request.content.decode("utf-8"))

        if call_count == 1:
            # Turn 1: Groq asks to run the 'bank_net_cash_flow' tool
            mock_payload = {
                "id": "chatcmpl-turn-1",
                "model": "openai/gpt-oss-120b",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_cashflow_1",
                                    "type": "function",
                                    "function": {
                                        "name": "bank_net_cash_flow",
                                        "arguments": "{}",
                                    },
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
            }
            return httpx.Response(200, json=mock_payload)

        # Turn 2: Groq receives tool execution output and synthesizes plain English
        assert len(body["messages"]) >= 3
        tool_msg = [m for m in body["messages"] if m.get("role") == "tool"][0]
        assert tool_msg["name"] == "bank_net_cash_flow"
        assert "2500" in tool_msg["content"]

        mock_payload = {
            "id": "chatcmpl-turn-2",
            "model": "openai/gpt-oss-120b",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "You saved money! Your net cash flow is positive at INR 2500.",
                    },
                    "finish_reason": "stop",
                }
            ],
        }
        return httpx.Response(200, json=mock_payload)

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        settings = Settings(
            groq_api_key=SecretStr("mock-key"),
            groq_base_url="https://mock.groq.test/v1",
        )
        provider = GroqProvider(settings=settings, client=client)

        response = await chat_with_workspace(
            message="Did I save money this month?",
            workspace_data=data,
            provider=provider,
        )

    assert call_count == 2
    assert "Your net cash flow is positive at INR 2500" in response.text
    assert "bank.net_cash_flow.v1" in response.calculation_ids
    assert len(response.source_refs) == 1
    assert response.source_refs[0].source_rows == [6, 7, 8]
    assert response.disclaimer == "This is not financial advice."


@pytest.mark.anyio
async def test_chat_empty_message_raises_error() -> None:
    data = load_fixture("bank-statement.json")
    with pytest.raises(ValueError, match="Message must not be empty"):
        await chat_with_workspace("   ", data)


@pytest.mark.anyio
async def test_chat_message_too_long_raises_error() -> None:
    data = load_fixture("bank-statement.json")
    with pytest.raises(ValueError, match="Message exceeds maximum length"):
        await chat_with_workspace("a" * 2001, data)


@pytest.mark.anyio
async def test_chat_unsupported_metric_refusal_offline() -> None:
    data = load_fixture("bank-statement.json")
    unconfigured_provider = GroqProvider(settings=Settings(groq_api_key=None))

    for query in ["What is my credit score?", "How much cryptocurrency did I buy?"]:
        response = await chat_with_workspace(
            message=query,
            workspace_data=data,
            provider=unconfigured_provider,
        )
        assert "I do not have a tool to calculate" in response.text
        assert response.calculation_ids == []
        assert response.source_refs == []


@pytest.mark.anyio
async def test_chat_validation_retry_success() -> None:
    data = load_fixture("bank-statement.json")
    call_count = 0

    def mock_handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        body = json.loads(request.content.decode("utf-8"))

        if call_count == 1:
            # Turn 1: tool call
            return httpx.Response(
                200,
                json={
                    "id": "chatcmpl-turn-1",
                    "model": "openai/gpt-oss-120b",
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": None,
                                "tool_calls": [
                                    {
                                        "id": "call_1",
                                        "type": "function",
                                        "function": {
                                            "name": "bank_net_cash_flow",
                                            "arguments": "{}",
                                        },
                                    }
                                ],
                            },
                            "finish_reason": "tool_calls",
                        }
                    ],
                },
            )

        if call_count == 2:
            # Turn 2: LLM produces a hallucinated number (99999)
            return httpx.Response(
                200,
                json={
                    "id": "chatcmpl-turn-2",
                    "model": "openai/gpt-oss-120b",
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "Your net cash flow is INR 99999.",
                            },
                            "finish_reason": "stop",
                        }
                    ],
                },
            )

        # Turn 3: Guard re-prompted LLM with corrective feedback, LLM corrects itself
        user_correction = body["messages"][-1]["content"]
        assert "SECURITY REJECTION" in user_correction
        assert "99999" in user_correction

        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-turn-3",
                "model": "openai/gpt-oss-120b",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "Your verified net cash flow is positive at INR 2500.",
                        },
                        "finish_reason": "stop",
                    }
                ],
            },
        )

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        settings = Settings(
            groq_api_key=SecretStr("mock-key"),
            groq_base_url="https://mock.groq.test/v1",
        )
        provider = GroqProvider(settings=settings, client=client)

        response = await chat_with_workspace(
            message="Did I save money?",
            workspace_data=data,
            provider=provider,
        )

    assert call_count == 3
    assert "INR 2500" in response.text


@pytest.mark.anyio
async def test_chat_validation_retry_failure_raises_ai_validation_error() -> None:
    data = load_fixture("bank-statement.json")
    call_count = 0

    def mock_handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1

        if call_count == 1:
            return httpx.Response(
                200,
                json={
                    "id": "chatcmpl-turn-1",
                    "model": "openai/gpt-oss-120b",
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": None,
                                "tool_calls": [
                                    {
                                        "id": "call_1",
                                        "type": "function",
                                        "function": {
                                            "name": "bank_net_cash_flow",
                                            "arguments": "{}",
                                        },
                                    }
                                ],
                            },
                            "finish_reason": "tool_calls",
                        }
                    ],
                },
            )

        # Persistently hallucinate across all retries
        return httpx.Response(
            200,
            json={
                "id": f"chatcmpl-turn-{call_count}",
                "model": "openai/gpt-oss-120b",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": f"Your net cash flow is INR {call_count * 10000}.",
                        },
                        "finish_reason": "stop",
                    }
                ],
            },
        )

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        settings = Settings(
            groq_api_key=SecretStr("mock-key"),
            groq_base_url="https://mock.groq.test/v1",
        )
        provider = GroqProvider(settings=settings, client=client)

        with pytest.raises(AIValidationError, match="failed numeric verification"):
            await chat_with_workspace(
                message="Did I save money?",
                workspace_data=data,
                provider=provider,
            )

    # Initial turn + 1st tool answer + 2 retries = 4 calls total
    assert call_count == 4

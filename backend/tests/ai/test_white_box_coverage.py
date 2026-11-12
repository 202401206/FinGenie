"""White-box testing suite for FinGenie AI module.

Targets 100% statement, branch, and condition coverage across:
- app.ai.chatbot
- app.ai.guard_retry
- app.ai.summary
- app.ai.tools
- app.ai.providers.groq_provider
- app.api.routes.ai
"""

import json
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.ai.chatbot import _offline_chat_fallback, chat_with_workspace
from app.ai.guard_retry import verify_and_retry_text
from app.ai.providers.groq_provider import (
    GroqAPIError,
    GroqProvider,
    GroqResponse,
    ToolCall,
)
from app.ai.summary import generate_summary
from app.ai.tools import (
    SourceRef,
    ToolExecutionError,
    ToolResult,
    _execute_balance_sheet_tool,
    _execute_bank_tool,
    _metric_dict_to_tool_result,
    execute_tool,
)
from app.api.routes.ai import (
    _FIXTURE_STORE,
    _handle_provider_error,
    _load_contract_fixture,
    get_workspace_data,
)
from app.core.config import Settings


def make_test_settings(api_key: str | None = "fake-groq-key") -> Settings:
    return Settings(
        groq_api_key=SecretStr(api_key) if api_key else None,
        groq_model="openai/gpt-oss-120b",
        groq_base_url="https://mock.groq.test/v1",
    )


# ---------------------------------------------------------------------------
# 1. White-box tests for guard_retry.py (Line 64)
# ---------------------------------------------------------------------------
@pytest.mark.anyio
async def test_guard_retry_succeeds_on_second_attempt() -> None:
    """Branch coverage for guard_retry: Initial fails, retry attempt 1 succeeds."""
    tool_result = ToolResult(
        name="bank_total_credit",
        value=Decimal("5000"),
        unit="INR",
        calculation_id="bank.total_credit.v1",
        source_refs=[
            SourceRef(
                document_id="doc-1",
                sheet_name="Statement",
                source_rows=[1],
                field_paths=["transactions[0].credit"],
            )
        ],
    )

    mock_llm = MagicMock()
    # Retry response contains ONLY the valid number 5000
    mock_llm.generate = AsyncMock(
        return_value=GroqResponse(
            content="Total credits are INR 5000.",
            tool_calls=[],
            finish_reason="stop",
            model="openai/gpt-oss-120b",
        )
    )

    # Initial text has an unsupported number (9999)
    result = await verify_and_retry_text(
        initial_text="Total deposits were INR 9999.",
        tool_results=[tool_result],
        messages=[{"role": "user", "content": "What are my deposits?"}],
        llm=mock_llm,
        max_retries=2,
    )
    assert "5000" in result
    assert "9999" not in result


# ---------------------------------------------------------------------------
# 2. White-box tests for summary.py (Lines 121-138)
# ---------------------------------------------------------------------------
@pytest.mark.anyio
async def test_generate_summary_balance_sheet_online_configured() -> None:
    """Branch coverage for balance sheet summary with online configured provider."""
    bs_data = {
        "currency": "INR",
        "unit_scale": 1,
        "assets": {
            "current": [{"line_item": "Cash", "value": 500000, "source_row": 1}],
            "total": 1500000,
        },
        "liabilities": {
            "current": [{"line_item": "Payables", "value": 200000, "source_row": 2}],
            "total": 1000000,
        },
        "equity": {"total": 500000},
    }

    mock_llm = MagicMock()
    mock_llm.is_configured = True
    mock_llm.generate = AsyncMock(
        return_value=GroqResponse(
            content="The balance sheet is verified and reconciled. Working capital is INR 300000 with a current ratio of 2.5.",
            tool_calls=[],
            finish_reason="stop",
            model="openai/gpt-oss-120b",
        )
    )

    resp = await generate_summary(bs_data, provider=mock_llm)
    assert resp.disclaimer == "This is not financial advice."
    assert "reconciled" in resp.text
    assert len(resp.calculation_ids) >= 2


# ---------------------------------------------------------------------------
# 3. White-box tests for groq_provider.py
# ---------------------------------------------------------------------------
@pytest.mark.anyio
async def test_groq_provider_ephemeral_client() -> None:
    """Branch coverage for GroqProvider when _client is None (lines 102-103)."""
    settings = make_test_settings()
    provider = GroqProvider(settings=settings)
    provider._client = None

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {"content": "Ephemeral client response", "tool_calls": []},
                "finish_reason": "stop",
            }
        ],
        "model": "openai/gpt-oss-120b",
    }

    with patch("httpx.AsyncClient.post", AsyncMock(return_value=mock_resp)):
        res = await provider.generate(messages=[{"role": "user", "content": "hi"}])
        assert res.content == "Ephemeral client response"


@pytest.mark.anyio
async def test_groq_provider_network_error() -> None:
    """Branch coverage for httpx.RequestError (lines 114-118)."""
    settings = make_test_settings()
    provider = GroqProvider(settings=settings)
    mock_client = MagicMock()
    mock_client.post = AsyncMock(
        side_effect=httpx.ConnectError("Connection refused by peer")
    )
    provider._client = mock_client

    with pytest.raises(GroqAPIError) as exc_info:
        await provider.generate(messages=[{"role": "user", "content": "hi"}])
    assert exc_info.value.status_code == 503
    assert "Network error" in exc_info.value.message


@pytest.mark.anyio
async def test_groq_provider_non_json_error() -> None:
    """Branch coverage for non-200 non-JSON response (lines 126-131)."""
    settings = make_test_settings()
    provider = GroqProvider(settings=settings)
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 502
    mock_resp.text = "<html>502 Bad Gateway</html>"
    mock_resp.json.side_effect = json.JSONDecodeError("Expecting value", "doc", 0)
    mock_client.post = AsyncMock(return_value=mock_resp)
    provider._client = mock_client

    with pytest.raises(GroqAPIError) as exc_info:
        await provider.generate(messages=[{"role": "user", "content": "hi"}])
    assert exc_info.value.status_code == 502
    assert "502 Bad Gateway" in exc_info.value.message


@pytest.mark.anyio
async def test_groq_provider_malformed_tool_args_and_empty_choices() -> None:
    """Branch coverage for invalid tool arguments JSON (lines 151-152) and missing choices (168-172)."""
    settings = make_test_settings()
    provider = GroqProvider(settings=settings)
    mock_client = MagicMock()

    # 1. Invalid tool args JSON
    mock_resp_invalid_args = MagicMock()
    mock_resp_invalid_args.status_code = 200
    mock_resp_invalid_args.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "function": {
                                "name": "bank_total_credit",
                                "arguments": "{invalid json",
                            },
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ],
        "model": "openai/gpt-oss-120b",
    }
    mock_client.post = AsyncMock(return_value=mock_resp_invalid_args)
    provider._client = mock_client

    resp = await provider.generate(
        messages=[{"role": "user", "content": "hi"}], tools=[{}]
    )
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0].arguments == {}

    # 2. Missing choices (empty list or missing key)
    mock_resp_empty = MagicMock()
    mock_resp_empty.status_code = 200
    mock_resp_empty.json.return_value = {"choices": []}
    mock_client.post = AsyncMock(return_value=mock_resp_empty)

    with pytest.raises(GroqAPIError) as exc_info:
        await provider.generate(messages=[{"role": "user", "content": "hi"}])
    assert exc_info.value.status_code == 502
    assert "Malformed response format" in exc_info.value.message


# ---------------------------------------------------------------------------
# 4. White-box tests for chatbot.py
# ---------------------------------------------------------------------------
@pytest.mark.anyio
async def test_chatbot_invalid_workspace_data() -> None:
    """Branch coverage for unsupported workspace data structure (line 55)."""
    with pytest.raises(ValueError, match="Unsupported or unrecognized"):
        await chat_with_workspace("Hello", {"invalid": 123})


@pytest.mark.anyio
async def test_chatbot_verbose_mode_direct_and_tools() -> None:
    """Branch coverage for verbose=True logging (lines 81, 88-89, 116-121)."""
    bank_data = {
        "currency": "INR",
        "transactions": [
            {"date": "2026-10-01", "credit": 5000, "debit": 0, "source_row": 1}
        ],
    }

    mock_llm = MagicMock()
    mock_llm.is_configured = True
    # Turn 0 calls a tool, Turn 1 synthesizes directly
    turn_0 = GroqResponse(
        content=None,
        tool_calls=[ToolCall(id="call_1", name="bank_total_credit", arguments={})],
        finish_reason="tool_calls",
        model="openai/gpt-oss-120b",
    )
    turn_1 = GroqResponse(
        content="Total credits amount to INR 5000.",
        tool_calls=[],
        finish_reason="stop",
        model="openai/gpt-oss-120b",
    )
    mock_llm.generate = AsyncMock(side_effect=[turn_0, turn_1])

    resp = await chat_with_workspace(
        "What is total credit?", bank_data, provider=mock_llm, verbose=True
    )
    assert "5000" in resp.text


@pytest.mark.anyio
async def test_chatbot_tool_execution_exception_handled() -> None:
    """Branch coverage for tool execution throwing an exception in loop (lines 122-126)."""
    bank_data = {
        "currency": "INR",
        "transactions": [],
    }

    mock_llm = MagicMock()
    mock_llm.is_configured = True
    turn_0 = GroqResponse(
        content=None,
        tool_calls=[
            ToolCall(id="call_bad", name="nonexistent_broken_tool", arguments={})
        ],
        finish_reason="tool_calls",
        model="openai/gpt-oss-120b",
    )
    turn_1 = GroqResponse(
        content="The tool could not be executed.",
        tool_calls=[],
        finish_reason="stop",
        model="openai/gpt-oss-120b",
    )
    mock_llm.generate = AsyncMock(side_effect=[turn_0, turn_1])

    with patch("app.ai.chatbot.execute_tool", side_effect=ValueError("Tool crash")):
        resp = await chat_with_workspace(
            "Run bad tool", bank_data, provider=mock_llm, verbose=True
        )
        assert resp.disclaimer == "This is not financial advice."


@pytest.mark.anyio
async def test_chatbot_max_turns_exceeded_handled() -> None:
    """Branch coverage for while loop exceeding max_turns (line 136)."""
    bank_data = {
        "currency": "INR",
        "transactions": [
            {"date": "2026-10-01", "credit": 5000, "debit": 0, "source_row": 1}
        ],
    }

    mock_llm = MagicMock()
    mock_llm.is_configured = True
    infinite_tool_call = GroqResponse(
        content=None,
        tool_calls=[ToolCall(id="call_inf", name="bank_total_credit", arguments={})],
        finish_reason="tool_calls",
        model="openai/gpt-oss-120b",
    )
    mock_llm.generate = AsyncMock(return_value=infinite_tool_call)

    resp = await chat_with_workspace(
        "Loop forever", bank_data, provider=mock_llm, max_turns=2
    )
    assert (
        "could not complete the calculation within the allowed reasoning turns"
        in resp.text
    )


def test_fallback_chat_all_branches() -> None:
    """Branch coverage for _offline_chat_fallback bank and balance sheet keywords."""
    bank_data = {
        "currency": "INR",
        "transactions": [
            {
                "date": "2026-10-01",
                "credit": 5000,
                "debit": 2000,
                "balance": 15000,
                "source_row": 1,
            }
        ],
    }

    # Bank branches
    r_credit = _offline_chat_fallback("What was my salary and income?", bank_data)
    assert "credits" in r_credit.text
    r_debit = _offline_chat_fallback("How much did I spend or withdrawal?", bank_data)
    assert "debits" in r_debit.text
    r_balance = _offline_chat_fallback(
        "What is my remaining closing balance?", bank_data
    )
    assert "closing balance" in r_balance.text
    r_unknown = _offline_chat_fallback("What is the weather outside?", bank_data)
    assert "I do not have a tool to calculate that" in r_unknown.text

    # Balance sheet branches
    bs_data_balanced = {
        "currency": "INR",
        "unit_scale": 1,
        "assets": {
            "current": [{"line_item": "Cash", "value": 500000, "source_row": 1}],
            "total": 1000000,
        },
        "liabilities": {
            "current": [{"line_item": "Payables", "value": 200000, "source_row": 2}],
            "total": 500000,
        },
        "equity": {"total": 500000},
    }
    r_wc = _offline_chat_fallback("What is the working capital?", bs_data_balanced)
    assert "working capital" in r_wc.text
    r_ratio = _offline_chat_fallback(
        "What is the liquidity and current ratio?", bs_data_balanced
    )
    assert "current ratio" in r_ratio.text
    r_rec_ok = _offline_chat_fallback(
        "Check if it is balanced and reconciled", bs_data_balanced
    )
    assert "reconciled and balanced" in r_rec_ok.text

    # Balance sheet discrepancy branch
    bs_data_unbalanced = {
        "currency": "INR",
        "unit_scale": 1,
        "assets": {
            "current": [{"line_item": "Cash", "value": 500000, "source_row": 1}],
            "total": 1200000,
        },
        "liabilities": {
            "current": [{"line_item": "Payables", "value": 200000, "source_row": 2}],
            "total": 500000,
        },
        "equity": {"total": 500000},
    }
    r_rec_warn = _offline_chat_fallback("Reconciliation check", bs_data_unbalanced)
    assert "Warning: The balance sheet does not balance" in r_rec_warn.text
    r_bs_unknown = _offline_chat_fallback("What is Bitcoin?", bs_data_balanced)
    assert "I do not have a tool to calculate that" in r_bs_unknown.text


# ---------------------------------------------------------------------------
# 5. White-box tests for tools.py (Pure Fallback Implementations & Edge Cases)
# ---------------------------------------------------------------------------
def test_tools_pure_fallback_implementations() -> None:
    """Branch coverage for tools.py standalone fallback functions."""
    # 1. Unrecognized workspace structure
    with pytest.raises(ToolExecutionError, match="Unsupported or unrecognized"):
        execute_tool("bank_total_credit", {}, {"unknown_data": 123})

    # 2. Metric conversion when value is not a valid Decimal
    res_invalid_metric = _metric_dict_to_tool_result(
        "custom_metric", {"value": "invalid_decimal_string"}
    )
    assert res_invalid_metric.value is None

    bank_data = {
        "currency": "INR",
        "document_id": "doc-fb",
        "sheet_name": "Sheet1",
        "transactions": [
            {
                "date": "2026-10-01",
                "credit": 10000,
                "debit": 0,
                "balance": 10000,
                "source_row": 1,
            },
            {
                "date": "2026-10-02",
                "credit": 0,
                "debit": 3000,
                "balance": 7000,
                "source_row": 2,
            },
        ],
        "closing_balance": 7000,
        "closing_balance_source_row": 2,
    }

    with patch("app.ai.tools.bank_kpis", None):
        res_credit = _execute_bank_tool("bank_total_credit", {}, bank_data)
        assert res_credit.value == Decimal("10000")

        res_debit = _execute_bank_tool("bank_total_debit", {}, bank_data)
        assert res_debit.value == Decimal("3000")

        res_ncf = _execute_bank_tool("bank_net_cash_flow", {}, bank_data)
        assert res_ncf.value == Decimal("7000")

        res_cb = _execute_bank_tool("bank_closing_balance", {}, bank_data)
        assert res_cb.value == Decimal("7000")

        # Missing closing balance in data
        no_closing_data = {"currency": "INR", "transactions": []}
        res_no_closing = _execute_bank_tool("bank_closing_balance", {}, no_closing_data)
        assert res_no_closing.status == "unavailable"

        # Unknown tool
        with pytest.raises(ToolExecutionError):
            _execute_bank_tool("unknown_tool", {}, bank_data)

        # Missing currency
        no_curr = {"transactions": []}
        res_no_curr = _execute_bank_tool("bank_total_credit", {}, no_curr)
        assert res_no_curr.status == "unavailable"

    # Balance sheet fallbacks
    bs_data = {
        "currency": "INR",
        "unit_scale": 1,
        "document_id": "bs-fb",
        "assets": {
            "current": [{"line_item": "Cash", "value": 500000, "source_row": 10}],
            "total": 1000000,
        },
        "liabilities": {
            "current": [{"line_item": "Payables", "value": 250000, "source_row": 20}],
            "total": 600000,
        },
        "equity": {"total": 400000},
    }

    with patch("app.ai.tools.balance_sheet_kpis", None):
        res_wc = _execute_balance_sheet_tool(
            "balance_sheet_working_capital", {}, bs_data
        )
        assert res_wc.value == Decimal("250000")

        res_cr = _execute_balance_sheet_tool("balance_sheet_current_ratio", {}, bs_data)
        assert res_cr.value == Decimal("2.0")

        res_rec = _execute_balance_sheet_tool(
            "balance_sheet_verify_reconciliation", {}, bs_data
        )
        assert res_rec.value == Decimal("0")

        # Missing total in balance sheet reconciliation
        bs_missing_total = {
            "currency": "INR",
            "unit_scale": 1,
            "assets": {"current": []},
            "liabilities": {"current": []},
            "equity": {},
        }
        res_rec_missing = _execute_balance_sheet_tool(
            "balance_sheet_verify_reconciliation", {}, bs_missing_total
        )
        assert res_rec_missing.status == "unavailable"

        # Zero liabilities ratio
        bs_zero_liab = dict(bs_data)
        bs_zero_liab["liabilities"] = {"current": []}
        res_cr_zero = _execute_balance_sheet_tool(
            "balance_sheet_current_ratio", {}, bs_zero_liab
        )
        assert res_cr_zero.status == "unavailable"

        # Missing currency
        bs_no_curr = {"unit_scale": 1}
        res_no_curr_bs = _execute_balance_sheet_tool(
            "balance_sheet_working_capital", {}, bs_no_curr
        )
        assert res_no_curr_bs.status == "unavailable"

        # Missing unit_scale
        bs_no_scale = {"currency": "INR"}
        res_no_scale = _execute_balance_sheet_tool(
            "balance_sheet_working_capital", {}, bs_no_scale
        )
        assert res_no_scale.status == "unavailable"

        # Unknown tool
        with pytest.raises(ToolExecutionError):
            _execute_balance_sheet_tool("unknown_bs_tool", {}, bs_data)


# ---------------------------------------------------------------------------
# 6. White-box tests for app.api.routes.ai
# ---------------------------------------------------------------------------
def test_routes_ai_fixtures_and_error_branches() -> None:
    """Branch coverage for ai.py routes internal helpers and error branches."""
    # 1. Non-existent fixture file
    empty_fixture = _load_contract_fixture("non_existent_fixture_file_123.json")
    assert empty_fixture == {}

    # 2. Custom fixture lookup in _FIXTURE_STORE
    custom_ws_id = uuid4()
    _FIXTURE_STORE[custom_ws_id] = {"custom": "data"}
    assert get_workspace_data(custom_ws_id) == {"custom": "data"}
    del _FIXTURE_STORE[custom_ws_id]

    # 3. Provider error handler with unexpected base GroqError (line 104)
    from app.ai.providers.groq_provider import GroqError

    exc_base = _handle_provider_error(GroqError("Generic unhandled error"))
    assert isinstance(exc_base, HTTPException)
    assert exc_base.status_code == 502
    assert exc_base.detail["message"] == "AI service failed unexpectedly."


def test_routes_ai_summary_value_error_endpoint() -> None:
    """Branch coverage for summary endpoint catching ValueError and raising 422 (line 131)."""
    from app.core.security import CurrentUser, require_user
    from app.main import app

    # Override authentication dependency to permit test request
    app.dependency_overrides[require_user] = lambda: CurrentUser(
        id=uuid4(), email="tester@example.com", is_authenticated=True
    )

    bad_ws_id = uuid4()
    # Workspace data lacking transactions or assets triggers ValueError in generate_summary
    _FIXTURE_STORE[bad_ws_id] = {"invalid_key": "unsupported_data"}

    client = TestClient(app)
    response = client.post(f"/api/workspaces/{bad_ws_id}/summary")

    del _FIXTURE_STORE[bad_ws_id]
    app.dependency_overrides.clear()

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_workspace_data"

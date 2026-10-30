"""Unit tests for the AI Summary engine."""

import json
from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr

from app.ai.providers.groq_provider import GroqProvider
from app.ai.summary import generate_summary
from app.core.config import Settings


def load_fixture(filename: str) -> dict:
    repo_root = Path(__file__).resolve().parents[3]
    fixture_path = repo_root / "contracts" / "examples" / filename
    with open(fixture_path, encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.anyio
async def test_bank_summary_offline_fallback() -> None:
    data = load_fixture("bank-statement.json")
    unconfigured_settings = Settings(groq_api_key=None)
    provider = GroqProvider(settings=unconfigured_settings)

    summary = await generate_summary(data, provider=provider)

    assert "5000" in summary.text
    assert "2500" in summary.text
    assert "12500" in summary.text
    assert summary.disclaimer == "This is not financial advice."
    assert "bank.total_credit.v1" in summary.calculation_ids
    assert "bank.net_cash_flow.v1" in summary.calculation_ids
    assert len(summary.source_refs) == 1
    # Rows 6 (salary), 7 (rent), 8 (groceries), 9 (closing balance)
    assert 6 in summary.source_refs[0].source_rows
    assert 7 in summary.source_refs[0].source_rows
    assert 8 in summary.source_refs[0].source_rows


@pytest.mark.anyio
async def test_bank_summary_with_mocked_groq() -> None:
    data = load_fixture("bank-statement.json")
    llm_generated_text = (
        "During January 2026, total deposits reached INR 5000 against withdrawals of INR 2500, "
        "yielding a positive cash flow of INR 2500."
    )

    def mock_handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        user_prompt = body["messages"][1]["content"]
        assert "Total Deposits / Credits: 5000 INR" in user_prompt
        assert "Total Withdrawals / Debits: 2500 INR" in user_prompt

        mock_payload = {
            "id": "chatcmpl-test-summary",
            "model": "openai/gpt-oss-120b",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": llm_generated_text,
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
        summary = await generate_summary(data, provider=provider)

    assert summary.text == llm_generated_text
    assert summary.disclaimer == "This is not financial advice."
    assert "bank.net_cash_flow.v1" in summary.calculation_ids


@pytest.mark.anyio
async def test_balance_sheet_summary_balanced() -> None:
    data = load_fixture("balance-sheet.json")
    unconfigured_settings = Settings(groq_api_key=None)
    provider = GroqProvider(settings=unconfigured_settings)

    summary = await generate_summary(data, provider=provider)

    assert "reconciled and balanced" in summary.text
    assert "7000000" in summary.text
    assert "1.88" in summary.text
    assert summary.disclaimer == "This is not financial advice."
    assert "balance_sheet.working_capital.v1" in summary.calculation_ids
    assert "balance_sheet.current_ratio.v1" in summary.calculation_ids


@pytest.mark.anyio
async def test_balance_sheet_unreliable_warning() -> None:
    data = load_fixture("balance-sheet.json")
    # Tamper with total assets so Assets != Liabilities + Equity
    tampered_data = dict(data)
    tampered_data["assets"] = dict(data["assets"])
    tampered_data["assets"]["total"] = 999  # Should be 300

    unconfigured_settings = Settings(groq_api_key=None)
    provider = GroqProvider(settings=unconfigured_settings)

    summary = await generate_summary(tampered_data, provider=provider)

    assert "Warning: This balance sheet is unreliable" in summary.text
    assert summary.disclaimer == "This is not financial advice."


@pytest.mark.anyio
async def test_unsupported_document_type() -> None:
    with pytest.raises(ValueError, match="Unsupported or unrecognized"):
        await generate_summary({"random_key": "some_data"})

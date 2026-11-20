"""Balance snapshot validation, exact serialization and safe save outcomes."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
import simplejson

from app.services.source_errors import (
    ParsedDocumentRejected,
    SourceOutcomeUnknown,
)
from tests.db.test_parsed_documents import run_save, saved_receipt
from tests.source_fixtures import OTHER, make_attempt


def balance_statement(attempt):
    fixture = (
        Path(__file__).resolve().parents[3] / "contracts/examples/balance-sheet.json"
    )
    statement = simplejson.loads(fixture.read_text(encoding="utf-8"), use_decimal=True)
    statement["source_metadata"]["document_id"] = str(attempt.document_id)
    return statement


def balance_attempt(**changes):
    return make_attempt(user_type="business", document_type="balance_sheet", **changes)


@pytest.mark.parametrize("currency,scale", [("INR", 100000), ("USD", 1), (None, None)])
def test_balance_save_keeps_reported_units_unknown_fields_and_zero_rows(
    currency, scale
):
    attempt = balance_attempt()
    statement = balance_statement(attempt)
    amount = Decimal("12345678901234567890.1234567890123456789")
    statement.update(
        currency=currency, unit_scale=scale, reporting_date=date(2026, 1, 31)
    )
    statement["assets"]["current"][0]["value"] = amount
    statement["assets"]["total"] = None
    statement["equity"]["retained_earnings"] = Decimal("-0.1234567890123456789")
    statement["prior_period"] = {"total": amount, "reporting_date": "2025-01-31"}
    statement["warnings"] = [{"code": "unknown_metadata", "source_row": 3}]

    def handle(request):
        assert request.url.path == "/rest/v1/rpc/finalize_balance_sheet"
        assert request.headers["authorization"] == "Bearer synthetic-token"
        assert request.headers["apikey"] == "sb_publishable_synthetic"
        payload = simplejson.loads(request.content, use_decimal=True)
        assert set(payload) == {"p_workspace_id", "p_document_id", "p_parsed_json"}
        saved = payload["p_parsed_json"]
        assert saved["assets"]["current"][0]["value"] == amount
        assert saved["assets"]["total"] is None
        assert saved["equity"]["retained_earnings"] == Decimal("-0.1234567890123456789")
        assert saved["currency"] == currency
        assert saved["unit_scale"] == scale
        assert saved["reporting_date"] == "2026-01-31"
        assert saved["prior_period"] == statement["prior_period"]
        assert saved["warnings"] == statement["warnings"]
        assert "transactions" not in saved
        assert "period_start" not in saved and "period_end" not in saved
        return httpx.Response(200, json=saved_receipt(attempt, count=0))

    assert run_save(handle, attempt, statement).transaction_count == 0


@pytest.mark.parametrize(
    "path,value",
    [
        (("assets", "current", 0, "value"), True),
        (("assets", "current", 0, "value"), 0.1),
        (("assets", "total"), Decimal("NaN")),
        (("equity", "total"), Decimal("Infinity")),
        (("equity", "share_capital"), False),
        (("assets", "current", 0, "source_row"), 1.5),
        (("assets", "current", 0, "source_row"), True),
        (("unit_scale",), 2),
        (("unit_scale",), True),
        (("unit_scale",), 1.0),
        (("currency",), "EUR"),
        (("reporting_date",), "2026-02-30"),
        (("source_metadata", "document_id"), str(OTHER)),
        (("unmapped",), ["not an object"]),
    ],
)
def test_invalid_balance_data_stops_before_network(path, value):
    attempt = balance_attempt()
    statement = balance_statement(attempt)
    target = statement
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ParsedDocumentRejected):
        run_save(
            lambda request: pytest.fail("Invalid data reached the database"),
            attempt,
            statement,
        )


@pytest.mark.parametrize("extra", [0.1, Decimal("NaN"), object()])
def test_extra_balance_fields_must_be_exact_valid_json(extra):
    attempt = balance_attempt()
    statement = balance_statement(attempt)
    statement["prior_period"] = {"total": extra}
    with pytest.raises(ParsedDocumentRejected):
        run_save(
            lambda request: pytest.fail("Invalid extras reached the database"),
            attempt,
            statement,
        )


@pytest.mark.parametrize("count", [1, True, -1])
def test_balance_receipt_must_confirm_exactly_zero_transaction_rows(count):
    attempt = balance_attempt()
    with pytest.raises(SourceOutcomeUnknown):
        run_save(
            lambda request: httpx.Response(
                200, json=saved_receipt(attempt, count=count)
            ),
            attempt,
            balance_statement(attempt),
        )


def test_lost_balance_save_response_is_not_retried_or_cleaned_up():
    attempt = balance_attempt()
    calls = []

    def timeout(request):
        calls.append(request)
        raise httpx.ReadTimeout("Synthetic lost response", request=request)

    with pytest.raises(SourceOutcomeUnknown):
        run_save(timeout, attempt, balance_statement(attempt))
    assert len(calls) == 1

"""Balance recovery uses the same exact stored contract and zero-row receipts."""

from decimal import Decimal

import httpx
import pytest
import simplejson

from app.services.source_errors import ParsedDocumentRejected, SourceOutcomeUnknown
from tests.db.test_balance_document_saves import balance_attempt, balance_statement
from tests.db.test_parsed_documents import run_save, saved_receipt
from tests.db.test_upload_recovery import call
from tests.source_fixtures import OTHER


def test_balance_save_and_recovery_normalize_the_same_exact_snapshot():
    attempt = balance_attempt()
    statement = balance_statement(attempt)
    exact = Decimal("12345678901234567890.1234567890123456789")
    statement.update(currency=None, unit_scale=None)
    statement["assets"]["current"][0]["value"] = exact
    statement["prior_period"] = {"total": exact, "missing": None}
    bodies = {}

    def handle(request):
        assert request.headers["authorization"] == "Bearer synthetic-token"
        assert request.headers["apikey"] == "sb_publishable_synthetic"
        payload = simplejson.loads(request.content, use_decimal=True)
        if request.url.path.endswith("/finalize_balance_sheet"):
            bodies["saved"] = payload["p_parsed_json"]
            return httpx.Response(200, json=saved_receipt(attempt, count=0))
        assert request.url.path == "/rest/v1/rpc/begin_balance_sheet_recovery"
        assert payload["p_workspace_id"] == str(attempt.workspace_id)
        assert payload["p_document_id"] == str(attempt.document_id)
        assert "p_user_id" not in payload
        bodies["recovered"] = payload["p_expected_json"]
        return httpx.Response(
            200, json={"state": "completed", "receipt": saved_receipt(attempt, count=0)}
        )

    run_save(handle, attempt, statement)
    assert call(handle, attempt, statement).receipt.transaction_count == 0
    assert bodies["saved"] == bodies["recovered"]
    assert bodies["recovered"]["prior_period"]["total"] == exact
    assert "transactions" not in bodies["recovered"]


@pytest.mark.parametrize(
    "case",
    [
        "foreign",
        "wrong_source",
        "float",
        "boolean",
        "nonfinite",
        "bad_scale",
        "unsupported_currency",
        "bad_extra",
    ],
)
def test_invalid_balance_recovery_context_is_rejected_before_access(case):
    attempt = balance_attempt(user_id=OTHER) if case == "foreign" else balance_attempt()
    statement = balance_statement(attempt)
    if case == "wrong_source":
        statement["source_metadata"]["document_id"] = str(OTHER)
    elif case == "float":
        statement["prior_period"] = {"value": 0.1}
    elif case == "boolean":
        statement["equity"]["total"] = True
    elif case == "nonfinite":
        statement["assets"]["total"] = Decimal("NaN")
    elif case == "bad_scale":
        statement["unit_scale"] = 2
    elif case == "unsupported_currency":
        statement["currency"] = "EUR"
    elif case == "bad_extra":
        statement["extra"] = object()
    with pytest.raises(ValueError if case == "foreign" else ParsedDocumentRejected):
        call(
            lambda request: pytest.fail("Invalid recovery context reached Supabase"),
            attempt,
            statement,
        )


@pytest.mark.parametrize(
    "case",
    ["nonzero_count", "bool_count", "wrong_workspace", "wrong_document", "bad_status"],
)
def test_balance_completion_receipt_must_match_original_ids_and_zero_count(case):
    attempt = balance_attempt()
    receipt = saved_receipt(attempt, count=0)
    if case == "nonzero_count":
        receipt["transaction_count"] = 1
    elif case == "bool_count":
        receipt["transaction_count"] = False
    elif case == "wrong_workspace":
        receipt["workspace_id"] = str(OTHER)
    elif case == "wrong_document":
        receipt["document_id"] = str(OTHER)
    else:
        receipt["status"] = "failed"
    with pytest.raises(SourceOutcomeUnknown):
        call(
            lambda request: httpx.Response(
                200, json={"state": "completed", "receipt": receipt}
            ),
            attempt,
            balance_statement(attempt),
        )


def test_balance_cleanup_uses_existing_original_id_release_contract():
    attempt = balance_attempt()

    def handle(request):
        assert request.url.path == "/rest/v1/rpc/release_failed_upload"
        assert simplejson.loads(request.content) == {
            "p_workspace_id": str(attempt.workspace_id),
            "p_document_id": str(attempt.document_id),
            "p_file_extension": "csv",
        }
        return httpx.Response(200, json={"released": True})

    call(handle, attempt, balance_statement(attempt), release=True)

"""End-to-end API route tests for AI Summary and Chatbot endpoints."""

from collections.abc import Iterator
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.ai.chatbot import AIValidationError
from app.ai.providers.groq_provider import GroqAPIError, GroqConfigurationError
from app.db.dependencies import get_workspace_repository
from app.db.errors import DatabaseUnavailable, DocumentNotReady, WorkspaceNotFound
from app.db.models import WorkspaceRecord
from app.db.parsed_models import ParsedBankStatement
from app.db.parsed_read_models import ParsedBalanceSheet, ParsedDocumentContext
from app.main import app
from tests.db.test_parsed_document_reads import DOCUMENT, document, workspace

BANK_WS = "20000000-0000-4000-8000-000000000007"
BALANCE_SHEET_WS = "20000000-0000-4000-8000-000000000008"
NONEXISTENT_WS = "00000000-0000-0000-0000-000000000099"


@pytest.fixture
def ai_contexts():
    return {
        BANK_WS: ("bank_statement", document()),
        BALANCE_SHEET_WS: ("balance_sheet", document("balance_sheet")),
    }


@pytest.fixture
def auth_client(monkeypatch, ai_contexts) -> Iterator[TestClient]:
    """Inject explicit owned results. Use only offline providers in route tests."""

    async def read(workspace_id: UUID) -> ParsedDocumentContext:
        entry = ai_contexts.get(str(workspace_id))
        if entry is None:
            raise WorkspaceNotFound()
        kind, row = entry
        if row.get("db_error"):
            raise DatabaseUnavailable("private SQL detail")
        if row["status"] != "parsed":
            raise DocumentNotReady()
        model = ParsedBankStatement if kind == "bank_statement" else ParsedBalanceSheet
        return ParsedDocumentContext(
            workspace=WorkspaceRecord.model_validate(
                workspace(kind) | {"id": workspace_id}
            ),
            document_id=DOCUMENT,
            parsed_json=model.model_validate(row["parsed_json"]),
        )

    monkeypatch.setitem(
        app.dependency_overrides,
        get_workspace_repository,
        lambda: SimpleNamespace(get_parsed_document=read),
    )
    for module in ("summary", "chatbot"):
        monkeypatch.setattr(
            f"app.ai.{module}.GroqProvider",
            lambda: SimpleNamespace(is_configured=False),
        )
    with TestClient(app) as client:
        yield client


# --- Authentication Security Tests (Leader Review Point 1) ---


def test_post_summary_missing_token_401() -> None:
    with TestClient(app) as client:
        response = client.post(f"/api/workspaces/{BANK_WS}/summary")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["detail"]["code"] == "unauthorized"


def test_post_chat_missing_token_401() -> None:
    with TestClient(app) as client:
        response = client.post(
            f"/api/workspaces/{BANK_WS}/chat",
            json={"message": "What is my net cash flow this month?"},
        )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["detail"]["code"] == "unauthorized"


def test_post_chat_invalid_token_header_401() -> None:
    with TestClient(app) as client:
        response = client.post(
            f"/api/workspaces/{BANK_WS}/chat",
            headers={"Authorization": "Basic invalid_credentials"},
            json={"message": "What is my net cash flow this month?"},
        )

    assert response.status_code == 401


# --- Authenticated Functional Endpoint Tests ---


def test_post_summary_bank_workspace_200(auth_client: TestClient) -> None:
    response = auth_client.post(f"/api/workspaces/{BANK_WS}/summary")

    assert response.status_code == 200
    data = response.json()
    assert "text" in data
    # Flexible check for online (e.g. "5,000") and offline ("5000") formatting
    assert "5000" in data["text"] or "5,000" in data["text"]
    assert "2500" in data["text"] or "2,500" in data["text"]
    assert "bank.total_credit.v1" in data["calculation_ids"]
    assert "bank.net_cash_flow.v1" in data["calculation_ids"]
    assert data["disclaimer"] == "This is not financial advice."
    assert len(data["source_refs"]) >= 1


def test_post_summary_balance_sheet_workspace_200(
    auth_client: TestClient,
) -> None:
    response = auth_client.post(f"/api/workspaces/{BALANCE_SHEET_WS}/summary")

    assert response.status_code == 200
    data = response.json()
    assert "reconcil" in data["text"].lower() or "balanced" in data["text"].lower()
    assert "7000000" in data["text"] or "7,000,000" in data["text"]
    assert "balance_sheet.working_capital.v1" in data["calculation_ids"]
    assert data["disclaimer"] == "This is not financial advice."


def test_post_chat_bank_workspace_200(auth_client: TestClient) -> None:
    response = auth_client.post(
        f"/api/workspaces/{BANK_WS}/chat",
        json={"message": "What is my net cash flow this month?"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "2500" in data["text"] or "2,500" in data["text"]
    assert "bank.net_cash_flow.v1" in data["calculation_ids"]
    assert data["disclaimer"] == "This is not financial advice."


def test_post_chat_greeting_200(auth_client: TestClient) -> None:
    response = auth_client.post(
        f"/api/workspaces/{BANK_WS}/chat",
        json={"message": "Hello FinGenie"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["text"]) > 0
    assert any(
        w in data["text"].lower() for w in ["hello", "assist", "help", "fingenie"]
    )
    assert data["calculation_ids"] == []


def test_post_summary_nonexistent_workspace_404(
    auth_client: TestClient,
) -> None:
    response = auth_client.post(f"/api/workspaces/{NONEXISTENT_WS}/summary")

    assert response.status_code == 404
    data = response.json()
    assert data["detail"]["code"] == "workspace_not_found"


@pytest.mark.parametrize(
    "workspace_id,change,status,code",
    [
        (BANK_WS, "uploaded", 409, "document_not_ready"),
        (BANK_WS, "failed", 409, "document_not_ready"),
        (BANK_WS, "db_error", 503, "database_unavailable"),
        (BANK_WS, "currency", 409, "analysis_not_ready"),
        (BANK_WS, "closing_balance", 409, "analysis_not_ready"),
        (BALANCE_SHEET_WS, "currency", 409, "analysis_not_ready"),
        (BALANCE_SHEET_WS, "unit_scale", 409, "analysis_not_ready"),
        (BALANCE_SHEET_WS, "unreconciled", 409, "analysis_not_ready"),
        (BALANCE_SHEET_WS, "current_ratio", 409, "analysis_not_ready"),
        (BALANCE_SHEET_WS, "missing_current_amount", 409, "analysis_not_ready"),
    ],
)
def test_summary_requires_owned_ready_document_and_metrics(
    auth_client, ai_contexts, workspace_id, change, status, code
):
    _, row = ai_contexts[workspace_id]
    parsed = row["parsed_json"]
    if change in {"uploaded", "failed"}:
        row["status"] = change
    elif change == "db_error":
        row["db_error"] = True
    elif change == "unreconciled":
        parsed["assets"]["total"] = 999
    elif change == "current_ratio":
        parsed["liabilities"]["current"][0]["value"] = 0
    elif change == "missing_current_amount":
        parsed["assets"]["current"][0]["value"] = None
    else:
        parsed[change] = None
    with patch("app.api.routes.ai.generate_summary") as generate:
        response = auth_client.post(f"/api/workspaces/{workspace_id}/summary")
    assert response.status_code == status, response.text
    assert response.json()["detail"]["code"] == code
    assert "private SQL detail" not in response.text
    generate.assert_not_called()


def test_post_chat_empty_message_422(auth_client: TestClient) -> None:
    response = auth_client.post(
        f"/api/workspaces/{BANK_WS}/chat",
        json={"message": ""},
    )

    assert response.status_code == 422


def test_post_chat_whitespace_message_422(auth_client: TestClient) -> None:
    response = auth_client.post(
        f"/api/workspaces/{BANK_WS}/chat",
        json={"message": "   "},
    )

    assert response.status_code == 422
    data = response.json()
    assert data["detail"]["code"] == "invalid_chat_request"


def test_post_chat_message_too_long_422(auth_client: TestClient) -> None:
    response = auth_client.post(
        f"/api/workspaces/{BANK_WS}/chat",
        json={"message": "a" * 2001},
    )

    assert response.status_code == 422


@patch("app.api.routes.ai.chat_with_workspace")
def test_post_chat_rate_limit_error_429(mock_chat, auth_client: TestClient) -> None:
    mock_chat.side_effect = GroqAPIError(status_code=429, message="Rate limit exceeded")
    response = auth_client.post(
        f"/api/workspaces/{BANK_WS}/chat",
        json={"message": "What is my cash flow?"},
    )

    assert response.status_code == 429
    data = response.json()
    assert data["detail"]["code"] == "rate_limit_exceeded"
    assert "rate limit reached" in data["detail"]["message"].lower()


@patch("app.api.routes.ai.chat_with_workspace")
def test_post_chat_provider_unavailable_503(mock_chat, auth_client: TestClient) -> None:
    mock_chat.side_effect = GroqAPIError(status_code=503, message="Groq outage")
    response = auth_client.post(
        f"/api/workspaces/{BANK_WS}/chat",
        json={"message": "What is my cash flow?"},
    )

    assert response.status_code == 503
    data = response.json()
    assert data["detail"]["code"] == "provider_unavailable"
    assert "temporarily unavailable" in data["detail"]["message"].lower()


@patch("app.api.routes.ai.chat_with_workspace")
def test_post_chat_upstream_error_502(mock_chat, auth_client: TestClient) -> None:
    mock_chat.side_effect = GroqAPIError(status_code=500, message="Internal Groq Error")
    response = auth_client.post(
        f"/api/workspaces/{BANK_WS}/chat",
        json={"message": "What is my cash flow?"},
    )

    assert response.status_code == 502
    data = response.json()
    assert data["detail"]["code"] == "ai_provider_error"


@patch("app.api.routes.ai.generate_summary")
def test_post_summary_configuration_error_503(
    mock_summary, auth_client: TestClient
) -> None:
    mock_summary.side_effect = GroqConfigurationError("Missing API key")
    response = auth_client.post(f"/api/workspaces/{BANK_WS}/summary")

    assert response.status_code == 503
    data = response.json()
    assert data["detail"]["code"] == "provider_unavailable"


@patch("app.api.routes.ai.generate_summary")
def test_post_summary_upstream_error_502(mock_summary, auth_client: TestClient) -> None:
    mock_summary.side_effect = GroqAPIError(
        status_code=500, message="private upstream body"
    )
    response = auth_client.post(f"/api/workspaces/{BANK_WS}/summary")
    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "ai_provider_error"
    assert "private upstream body" not in response.text


@patch("app.api.routes.ai.chat_with_workspace")
def test_post_chat_validation_failed_502(mock_chat, auth_client: TestClient) -> None:
    mock_chat.side_effect = AIValidationError("Numeric verification failed: '99999'")
    response = auth_client.post(
        f"/api/workspaces/{BANK_WS}/chat",
        json={"message": "What is my cash flow?"},
    )

    assert response.status_code == 502
    data = response.json()
    assert data["detail"]["code"] == "ai_validation_failed"
    assert "Numeric verification failed" in data["detail"]["message"]
    assert "99999" not in response.text


@patch("app.api.routes.ai.generate_summary")
def test_post_summary_validation_failed_502(
    mock_summary, auth_client: TestClient
) -> None:
    mock_summary.side_effect = AIValidationError("Numeric verification failed: '2026'")
    response = auth_client.post(f"/api/workspaces/{BANK_WS}/summary")

    assert response.status_code == 502
    data = response.json()
    assert data["detail"]["code"] == "ai_validation_failed"
    assert "Numeric verification failed" in data["detail"]["message"]
    assert "2026" not in response.text

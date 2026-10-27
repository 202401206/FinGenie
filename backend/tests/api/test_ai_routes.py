"""End-to-end API route tests for AI Summary and Chatbot endpoints."""

from fastapi.testclient import TestClient

from app.main import app

BANK_WS = "20000000-0000-4000-8000-000000000001"
BALANCE_SHEET_WS = "20000000-0000-4000-8000-000000000002"
NONEXISTENT_WS = "00000000-0000-0000-0000-000000000099"


def test_post_summary_bank_workspace_200() -> None:
    with TestClient(app) as client:
        response = client.post(f"/api/workspaces/{BANK_WS}/summary")

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


def test_post_summary_balance_sheet_workspace_200() -> None:
    with TestClient(app) as client:
        response = client.post(f"/api/workspaces/{BALANCE_SHEET_WS}/summary")

    assert response.status_code == 200
    data = response.json()
    assert "reconcil" in data["text"].lower() or "balanced" in data["text"].lower()
    assert "7000000" in data["text"] or "7,000,000" in data["text"]
    assert "balance_sheet.working_capital.v1" in data["calculation_ids"]
    assert data["disclaimer"] == "This is not financial advice."


def test_post_chat_bank_workspace_200() -> None:
    with TestClient(app) as client:
        response = client.post(
            f"/api/workspaces/{BANK_WS}/chat",
            json={"message": "What is my net cash flow this month?"},
        )

    assert response.status_code == 200
    data = response.json()
    assert "2500" in data["text"] or "2,500" in data["text"]
    assert "bank.net_cash_flow.v1" in data["calculation_ids"]
    assert data["disclaimer"] == "This is not financial advice."


def test_post_chat_greeting_200() -> None:
    with TestClient(app) as client:
        response = client.post(
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


def test_post_summary_nonexistent_workspace_404() -> None:
    with TestClient(app) as client:
        response = client.post(f"/api/workspaces/{NONEXISTENT_WS}/summary")

    assert response.status_code == 404
    data = response.json()
    assert data["detail"]["code"] == "workspace_not_found"


def test_post_chat_empty_message_422() -> None:
    with TestClient(app) as client:
        response = client.post(
            f"/api/workspaces/{BANK_WS}/chat",
            json={"message": ""},
        )

    assert response.status_code == 422

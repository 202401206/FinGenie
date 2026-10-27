"""FastAPI routes for AI Summary and Conversational Assistant."""

import json
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.ai.chatbot import chat_with_workspace
from app.ai.summary import generate_summary
from app.schemas.requests import ChatRequest
from app.schemas.responses import ChatResponse, SummaryResponse

router = APIRouter(prefix="/workspaces", tags=["ai"])

# Official synthetic workspace UUIDs defined in contracts/api/README.md
SYNTHETIC_BANK_WORKSPACE_ID = UUID("20000000-0000-4000-8000-000000000001")
SYNTHETIC_BALANCE_SHEET_WORKSPACE_ID = UUID("20000000-0000-4000-8000-000000000002")

# In-memory registry for testing and development fixtures
_FIXTURE_STORE: dict[UUID, dict[str, Any]] = {}


def _load_contract_fixture(filename: str) -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[4]
    fixture_path = repo_root / "contracts" / "examples" / filename
    if not fixture_path.exists():
        return {}
    with open(fixture_path, encoding="utf-8") as f:
        return json.load(f)


def get_workspace_data(workspace_id: UUID) -> dict[str, Any]:
    """Retrieve workspace document data from DB or development fixtures."""
    # 1. Check custom in-memory fixture overrides (used in tests)
    if workspace_id in _FIXTURE_STORE:
        return _FIXTURE_STORE[workspace_id]

    # 2. Check standard contract fixtures for offline development
    if workspace_id == SYNTHETIC_BANK_WORKSPACE_ID:
        data = _load_contract_fixture("bank-statement.json")
        if data:
            return data
    elif workspace_id == SYNTHETIC_BALANCE_SHEET_WORKSPACE_ID:
        data = _load_contract_fixture("balance-sheet.json")
        if data:
            return data

    # 3. Not found
    raise HTTPException(
        status_code=404,
        detail={
            "code": "workspace_not_found",
            "message": f"Workspace '{workspace_id}' not found.",
        },
    )


@router.post("/{workspace_id}/summary", response_model=SummaryResponse)
async def get_summary_endpoint(workspace_id: UUID) -> SummaryResponse:
    """Generate an executive financial summary for the specified workspace."""
    data = get_workspace_data(workspace_id)
    try:
        return await generate_summary(data)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_workspace_data", "message": str(exc)},
        ) from exc


@router.post("/{workspace_id}/chat", response_model=ChatResponse)
async def chat_endpoint(
    workspace_id: UUID,
    request: ChatRequest,
) -> ChatResponse:
    """Ask a question about the workspace financial data using tool calling."""
    data = get_workspace_data(workspace_id)
    try:
        return await chat_with_workspace(request.message, data)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_chat_request", "message": str(exc)},
        ) from exc

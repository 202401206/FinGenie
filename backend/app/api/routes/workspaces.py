"""Authenticated workspace HTTP routes."""

from datetime import date
from typing import Annotated
from uuid import UUID

import simplejson
from fastapi import APIRouter, Query, Response

from app.api.workspace_dependencies import (
    Repository,
    read_owned_document,
    workspace_errors,
)
from app.schemas.analysis_responses import WorkspaceAnalysisResponse
from app.schemas.workspace_responses import (
    TransactionPageResponse,
    WorkspaceDetailsResponse,
    WorkspacePageResponse,
)
from app.services.workspace_analysis import build_workspace_analysis

router = APIRouter(prefix="/workspaces", tags=["workspaces"])

Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


@router.get("", response_model=WorkspacePageResponse)
async def list_workspaces(
    repository: Repository, limit: Limit = 50, offset: Offset = 0
) -> WorkspacePageResponse:
    with workspace_errors():
        page = await repository.list_workspaces(limit=limit, offset=offset)
    return WorkspacePageResponse.model_validate(page, from_attributes=True)


@router.get("/{id}", response_model=WorkspaceDetailsResponse)
async def get_workspace(id: UUID, repository: Repository) -> WorkspaceDetailsResponse:
    with workspace_errors():
        details = await repository.get_workspace(id)
    return WorkspaceDetailsResponse.model_validate(details)


def encode_transaction_value(value: object) -> str:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    raise TypeError(f"Unexpected transaction value type: {type(value).__name__}")


@router.get("/{id}/transactions", response_model=TransactionPageResponse)
async def list_transactions(
    id: UUID, repository: Repository, limit: Limit = 50, offset: Offset = 0
) -> Response:
    with workspace_errors():
        page = await repository.list_transactions(id, limit=limit, offset=offset)

    # Validate before returning Response, which bypasses FastAPI's serialization.
    payload = TransactionPageResponse.model_validate(page, from_attributes=True)
    return Response(
        content=simplejson.dumps(
            payload.model_dump(mode="python"),
            use_decimal=True,
            default=encode_transaction_value,
        ),
        media_type="application/json",
    )


@router.get("/{id}/analysis", response_model=WorkspaceAnalysisResponse)
async def get_workspace_analysis(id: UUID, repository: Repository) -> Response:
    context = await read_owned_document(id, repository)
    payload = build_workspace_analysis(context)
    return Response(content=payload.to_wire_json(), media_type="application/json")

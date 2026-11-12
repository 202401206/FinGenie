"""Authenticated workspace HTTP routes."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from typing import Annotated
from uuid import UUID

import simplejson
from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.core.security import unauthorized
from app.db.dependencies import get_workspace_repository
from app.db.errors import (
    DatabaseUnauthorized,
    DatabaseUnavailable,
    UnsupportedDocumentType,
    WorkspaceNotFound,
)
from app.db.repositories.workspaces import WorkspaceRepository
from app.schemas.workspace_responses import (
    TransactionPageResponse,
    WorkspaceDetailsResponse,
    WorkspacePageResponse,
)

router = APIRouter(prefix="/workspaces", tags=["workspaces"])

Repository = Annotated[WorkspaceRepository, Depends(get_workspace_repository)]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


@contextmanager
def workspace_errors() -> Iterator[None]:
    try:
        yield
    except DatabaseUnauthorized:
        raise unauthorized() from None
    except DatabaseUnavailable:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "database_unavailable",
                "message": "Workspace data is unavailable.",
            },
        ) from None
    except WorkspaceNotFound:
        raise HTTPException(
            status_code=404,
            detail={"code": "workspace_not_found", "message": "Workspace not found."},
        ) from None
    except UnsupportedDocumentType:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "unsupported_document_type",
                "message": "Transactions are available only for bank statements.",
            },
        ) from None


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

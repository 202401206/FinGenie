"""Authenticated workspace HTTP routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.security import unauthorized
from app.db.dependencies import get_workspace_repository
from app.db.errors import DatabaseUnauthorized, DatabaseUnavailable
from app.db.repositories.workspaces import WorkspaceRepository
from app.schemas.workspace_responses import (
    WorkspacePageResponse,
    WorkspaceResponse,
)

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.get("", response_model=WorkspacePageResponse)
async def list_workspaces(
    repository: Annotated[WorkspaceRepository, Depends(get_workspace_repository)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> WorkspacePageResponse:
    try:
        page = await repository.list_workspaces(limit=limit, offset=offset)
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

    return WorkspacePageResponse(
        items=[WorkspaceResponse.model_validate(workspace) for workspace in page.items],
        limit=page.limit,
        offset=page.offset,
        total=page.total,
    )

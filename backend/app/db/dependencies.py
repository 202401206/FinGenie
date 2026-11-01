"""Authentication runs before constructing a request's read repository."""

from typing import Annotated

import httpx
from fastapi import Depends

from app.core.security import get_auth_client, require_bearer, require_user
from app.db.repositories.workspaces import WorkspaceRepository
from app.schemas.responses import CurrentUser


def get_workspace_repository(
    user: Annotated[CurrentUser, Depends(require_user)],
    token: Annotated[str, Depends(require_bearer)],
    client: Annotated[httpx.AsyncClient, Depends(get_auth_client)],
) -> WorkspaceRepository:
    # FastAPI caches these dependencies within this request. The client already
    # carries the project's publishable key; each query sends this caller's JWT.
    return WorkspaceRepository(client, user.id, token)

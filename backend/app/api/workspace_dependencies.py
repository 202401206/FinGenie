"""Common HTTP dependencies for saved workspace routes."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException

from app.core.security import unauthorized
from app.db.dependencies import get_workspace_repository
from app.db.errors import (
    DatabaseUnauthorized,
    DatabaseUnavailable,
    DocumentNotReady,
    UnsupportedDocumentType,
    WorkspaceNotFound,
)
from app.db.parsed_read_models import ParsedDocumentContext
from app.db.repositories.workspaces import WorkspaceRepository

Repository = Annotated[WorkspaceRepository, Depends(get_workspace_repository)]


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
    except DocumentNotReady:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "document_not_ready",
                "message": "The document is not ready for analysis.",
            },
        ) from None
    except UnsupportedDocumentType:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "unsupported_document_type",
                "message": "Transactions are available only for bank statements.",
            },
        ) from None


async def read_owned_document(
    workspace_id: UUID, repository: WorkspaceRepository
) -> ParsedDocumentContext:
    with workspace_errors():
        return await repository.get_parsed_document(workspace_id)

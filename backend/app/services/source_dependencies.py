"""Request-scoped upload helpers for the future upload service and API routes."""

from dataclasses import dataclass
from typing import Annotated

import httpx
from fastapi import Depends

from app.core.security import get_auth_client, require_bearer, require_user
from app.db.repositories.source_uploads import SourceReservationRepository
from app.schemas.responses import CurrentUser
from app.services.source_storage import SourceStorage


@dataclass(frozen=True)
class SourceUploadAccess:
    user: CurrentUser
    reservations: SourceReservationRepository
    storage: SourceStorage


def get_source_upload_access(
    user: Annotated[CurrentUser, Depends(require_user)],
    token: Annotated[str, Depends(require_bearer)],
    client: Annotated[httpx.AsyncClient, Depends(get_auth_client)],
) -> SourceUploadAccess:
    return SourceUploadAccess(
        user=user,
        reservations=SourceReservationRepository(client, user.id, token),
        storage=SourceStorage(client, user.id, token),
    )

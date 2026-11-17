"""Request-scoped upload helpers for the future upload service and API routes."""

from dataclasses import dataclass
from typing import Annotated

import httpx
from fastapi import Depends, HTTPException

from app.core.security import (
    get_auth_client,
    require_bearer,
    require_user,
    unauthorized,
)
from app.db.repositories.source_uploads import SourceReservationRepository
from app.db.repositories.upload_recovery import UploadRecoveryRepository
from app.schemas.responses import CurrentUser
from app.services.source_errors import (
    SourceConflict,
    SourceUnauthorized,
    SourceUnavailable,
)
from app.services.source_storage import SourceStorage
from app.services.upload_recovery import UploadRecoveryService


@dataclass(frozen=True)
class SourceUploadAccess:
    user: CurrentUser
    reservations: SourceReservationRepository
    storage: SourceStorage
    upload_generation: int = 0


async def get_source_upload_access(
    user: Annotated[CurrentUser, Depends(require_user)],
    token: Annotated[str, Depends(require_bearer)],
    client: Annotated[httpx.AsyncClient, Depends(get_auth_client)],
) -> SourceUploadAccess:
    reservations = SourceReservationRepository(client, user.id, token)
    try:
        generation = await reservations.get_generation()
    except SourceUnauthorized:
        raise unauthorized() from None
    except SourceConflict:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "data_deletion_in_progress",
                "message": "Finish financial data deletion before uploading.",
            },
        ) from None
    except SourceUnavailable:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "upload_unavailable",
                "message": "Upload access is unavailable.",
            },
        ) from None
    return SourceUploadAccess(
        user=user,
        reservations=reservations,
        storage=SourceStorage(client, user.id, token),
        upload_generation=generation,
    )


def get_upload_recovery_service(
    user: Annotated[CurrentUser, Depends(require_user)],
    token: Annotated[str, Depends(require_bearer)],
    client: Annotated[httpx.AsyncClient, Depends(get_auth_client)],
) -> UploadRecoveryService:
    return UploadRecoveryService(
        UploadRecoveryRepository(client, user.id, token),
        SourceStorage(client, user.id, token),
    )

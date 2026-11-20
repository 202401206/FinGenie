"""Owned upload history and explicit recovery of a stored attempt."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from app.core.security import unauthorized
from app.db.repositories.upload_attempts import UploadAttemptNotFound
from app.schemas.error_responses import UploadErrorResponse
from app.schemas.upload_attempt_responses import (
    RecoverUploadRequest,
    UploadAttemptPage,
    UploadRecoveryResponse,
)
from app.services.source_dependencies import get_upload_attempt_service
from app.services.source_errors import (
    ParsedDocumentRejected,
    SourceConflict,
    SourceUnauthorized,
    SourceUnavailable,
)
from app.services.upload_attempt_models import UploadAttemptSummary
from app.services.upload_attempts import UploadAttemptService


class UploadAttemptRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def validated(request):
            try:
                return await handler(request)
            except RequestValidationError:
                return JSONResponse(
                    status_code=422,
                    content={
                        "detail": {
                            "code": "invalid_upload_attempt_request",
                            "message": "Check the attempt ID or pagination. Recovery accepts an empty JSON object.",
                        }
                    },
                )

        return validated


router = APIRouter(
    prefix="/upload-attempts",
    tags=["upload"],
    route_class=UploadAttemptRoute,
    responses={
        401: {"model": UploadErrorResponse, "description": "Authentication required."},
        409: {
            "model": UploadErrorResponse,
            "description": "Upload attempt state conflict.",
        },
        422: {
            "model": UploadErrorResponse,
            "description": "Invalid ID, pagination, or recovery request.",
        },
        503: {
            "model": UploadErrorResponse,
            "description": "Attempt state unavailable or recovery pending.",
        },
    },
)
ATTEMPT_NOT_FOUND = {
    "model": UploadErrorResponse,
    "description": "Upload attempt not found.",
}
Attempts = Annotated[UploadAttemptService, Depends(get_upload_attempt_service)]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]

RECOVERY_ERRORS = {
    "auth_required": (401, "Sign in again to recover this upload attempt."),
    "reconciliation_required": (503, "Upload recovery could not be confirmed."),
    "cleanup_required": (503, "Upload cleanup could not be confirmed."),
    "state_conflict": (409, "The upload attempt needs review."),
}


def recovery_error(code: str, attempt_id: UUID | None) -> HTTPException:
    status, message = RECOVERY_ERRORS[code]
    detail = {"code": code, "message": message}
    if attempt_id is not None:
        detail["attempt_id"] = str(attempt_id)
    return HTTPException(
        status_code=status,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"} if status == 401 else None,
    )


@contextmanager
def attempt_errors(attempt_id: UUID | None = None) -> Iterator[None]:
    try:
        yield
    except SourceUnauthorized:
        raise unauthorized() from None
    except UploadAttemptNotFound:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "upload_attempt_not_found",
                "message": "Upload attempt not found.",
            },
        ) from None
    except SourceConflict:
        raise recovery_error("state_conflict", attempt_id) from None
    except (SourceUnavailable, ParsedDocumentRejected):
        raise recovery_error("reconciliation_required", attempt_id) from None


@router.get("", response_model=UploadAttemptPage)
async def list_upload_attempts(
    attempts: Attempts, limit: Limit = 50, offset: Offset = 0
) -> UploadAttemptPage:
    with attempt_errors():
        page = await attempts.journal.list_attempts(limit=limit, offset=offset)
    return UploadAttemptPage.model_validate(page, from_attributes=True)


@router.get(
    "/{attempt_id}",
    response_model=UploadAttemptSummary,
    responses={404: ATTEMPT_NOT_FOUND},
)
async def get_upload_attempt(
    attempt_id: UUID, attempts: Attempts
) -> UploadAttemptSummary:
    with attempt_errors(attempt_id):
        return await attempts.journal.get_summary(attempt_id)


@router.post(
    "/{attempt_id}/recover",
    response_model=UploadRecoveryResponse,
    responses={404: ATTEMPT_NOT_FOUND},
)
async def recover_upload_attempt(
    attempt_id: UUID, attempts: Attempts, body: RecoverUploadRequest
) -> UploadRecoveryResponse:
    with attempt_errors(attempt_id):
        result = await attempts.recover(attempt_id)
    if result.reason is not None:
        raise recovery_error(result.reason, attempt_id)
    return UploadRecoveryResponse(
        attempt_id=attempt_id, status=result.status, receipt=result.receipt
    )

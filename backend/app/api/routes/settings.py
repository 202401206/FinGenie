"""Preferences and explicitly confirmed financial-data deletion."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from app.core.security import unauthorized
from app.db.dependencies import get_settings_repository
from app.db.errors import DatabaseUnauthorized, DatabaseUnavailable
from app.db.repositories.settings import (
    DeletionConflict,
    DeletionPending,
    SettingsRepository,
    delete_financial_data,
)
from app.schemas.settings import DataDeleted, PreferencesPatch, UserPreferences


class SettingsRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def validated(request):
            try:
                return await handler(request)
            except RequestValidationError:
                code = (
                    "invalid_preference"
                    if request.url.path.endswith("/preferences")
                    else "invalid_request"
                )
                return JSONResponse(
                    status_code=422,
                    content={
                        "detail": {
                            "code": code,
                            "message": "Invalid settings request or preference value.",
                        }
                    },
                )

        return validated


router = APIRouter(prefix="/me", tags=["settings"], route_class=SettingsRoute)
Repository = Annotated[SettingsRepository, Depends(get_settings_repository)]


@contextmanager
def settings_errors() -> Iterator[None]:
    try:
        yield
    except DatabaseUnauthorized:
        raise unauthorized() from None
    except DatabaseUnavailable:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "settings_unavailable",
                "message": "Settings or deletion status could not be confirmed. Retry with the same deletion key if applicable.",
            },
        ) from None
    except DeletionPending as error:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "data_deletion_pending",
                "message": "Deletion is incomplete. Retry this deletion with the same operation ID.",
                "operation_id": str(error.operation_id),
            },
        ) from None
    except DeletionConflict as error:
        raise HTTPException(
            status_code=409,
            detail={
                "code": error.code,
                "message": "Another deletion is active, or this completed deletion key does not cover newly uploaded data.",
            },
        ) from None


@router.get("/preferences", response_model=UserPreferences)
async def get_preferences(repository: Repository) -> UserPreferences:
    with settings_errors():
        return await repository.get_preferences()


@router.patch("/preferences", response_model=UserPreferences)
async def patch_preferences(
    patch: PreferencesPatch, repository: Repository
) -> UserPreferences:
    with settings_errors():
        return await repository.patch_preferences(patch)


@router.delete("/data", response_model=DataDeleted)
async def delete_data(
    repository: Repository,
    operation_id: Annotated[UUID | None, Header(alias="Idempotency-Key")] = None,
) -> DataDeleted:
    with settings_errors():
        await delete_financial_data(repository, operation_id)
    return DataDeleted()

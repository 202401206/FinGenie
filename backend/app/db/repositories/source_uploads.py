"""Reserve owned workspace/document metadata in one database transaction."""

from uuid import UUID

import httpx
from pydantic import SecretStr, ValidationError

from app.services.source_errors import (
    SourceConflict,
    SourceOutcomeUnknown,
    SourceUnauthorized,
    SourceUnavailable,
)
from app.services.source_models import SourceAttempt, SourceReservation


class SourceReservationRepository:
    def __init__(
        self, client: httpx.AsyncClient, user_id: UUID, access_token: str
    ) -> None:
        self._client = client
        self._user_id = user_id
        self._token = SecretStr(access_token)

    async def get_generation(self) -> int:
        try:
            response = await self._client.post(
                "/rest/v1/rpc/get_upload_generation",
                headers={"Authorization": f"Bearer {self._token.get_secret_value()}"},
                json={},
            )
        except httpx.RequestError:
            raise SourceUnavailable() from None
        if response.status_code == 401:
            raise SourceUnauthorized()
        if response.status_code == 409:
            raise SourceConflict()
        if response.status_code != 200:
            raise SourceUnavailable()
        try:
            value = response.json()["generation"]
            if type(value) is not int or value < 0:
                raise ValueError()
            return value
        except (ValueError, KeyError, TypeError):
            raise SourceUnavailable() from None

    async def reserve(self, attempt: SourceAttempt) -> SourceReservation:
        if attempt.user_id != self._user_id:
            raise ValueError("Upload owner must be the verified caller.")
        payload = {
            "p_workspace_id": str(attempt.workspace_id),
            "p_document_id": str(attempt.document_id),
            "p_user_type": attempt.user_type.value,
            "p_document_type": attempt.document_type.value,
            "p_name": attempt.name,
            "p_original_filename": attempt.original_filename,
            "p_file_extension": attempt.kind.value,
            "p_generation": attempt.upload_generation,
        }
        try:
            response = await self._client.post(
                "/rest/v1/rpc/reserve_source_upload_at_generation",
                headers={"Authorization": f"Bearer {self._token.get_secret_value()}"},
                json=payload,
            )
        except httpx.RequestError:
            raise SourceOutcomeUnknown("reservation") from None
        if response.status_code == 401:
            raise SourceUnauthorized()
        if response.status_code == 409:
            raise SourceConflict()
        if response.status_code >= 500:
            raise SourceOutcomeUnknown("reservation")
        if response.status_code != 200:
            raise SourceUnavailable()
        try:
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError()
            return SourceReservation.model_validate({**payload, "attempt": attempt})
        except (ValueError, ValidationError):
            # The transaction may already have committed despite a bad receipt.
            raise SourceOutcomeUnknown("reservation") from None

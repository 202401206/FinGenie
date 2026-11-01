"""Private, immutable file operations using the caller's Supabase access token."""

from typing import Literal
from uuid import UUID

import httpx
from pydantic import SecretStr

from app.services.source_errors import (
    SourceConflict,
    SourceOutcomeUnknown,
    SourceTooLarge,
    SourceUnauthorized,
    SourceUnavailable,
)
from app.services.source_models import SOURCE_BUCKET, SourceAttempt, SourceReservation


class SourceStorage:
    def __init__(
        self, client: httpx.AsyncClient, user_id: UUID, access_token: str
    ) -> None:
        self._client = client
        self._user_id = user_id
        self._token = SecretStr(access_token)

    async def upload(
        self, reservation: SourceReservation, content: bytes, *, max_bytes: int
    ) -> None:
        attempt = reservation.attempt
        self._check_owner(attempt)
        if type(max_bytes) is not int or max_bytes < 1:
            raise ValueError("An agreed positive byte limit is required.")
        if not isinstance(content, bytes) or not content:
            raise ValueError("A nonempty, validated source is required.")
        if len(content) > max_bytes:
            raise SourceTooLarge()
        response = await self._request(
            "POST",
            f"/storage/v1/object/{SOURCE_BUCKET}/{attempt.path}",
            operation="upload",
            content=content,
            headers={
                "Content-Type": attempt.kind.content_type,
                "x-upsert": "false",
            },
        )
        try:
            result = response.json()
            if not isinstance(result, dict) or result.get("Key") != (
                f"{SOURCE_BUCKET}/{attempt.path}"
            ):
                raise ValueError()
        except ValueError:
            raise SourceOutcomeUnknown("upload") from None

    async def remove(self, attempt: SourceAttempt) -> bool:
        """Remove only this source after the caller confirms it should be discarded.

        This also supports orphan cleanup without document metadata. It must not
        be called blindly after a lost upload/finalization response. False means
        Storage returned no removed object; it is not a proof of absence.
        """
        self._check_owner(attempt)
        response = await self._request(
            "DELETE",
            f"/storage/v1/object/{SOURCE_BUCKET}",
            operation="removal",
            json={"prefixes": [attempt.path]},
        )
        try:
            result = response.json()
            if not isinstance(result, list):
                raise ValueError()
            if not result:
                return False
            if len(result) != 1 or not isinstance(result[0], dict):
                raise ValueError()
            if result[0].get("name") != attempt.path:
                raise ValueError()
            return True
        except ValueError:
            raise SourceOutcomeUnknown("removal") from None

    def _check_owner(self, attempt: SourceAttempt) -> None:
        if attempt.user_id != self._user_id:
            raise ValueError("Source owner must be the verified caller.")

    async def _request(
        self,
        method: str,
        path: str,
        *,
        operation: Literal["upload", "removal"],
        **kwargs,
    ) -> httpx.Response:
        headers = {
            "Authorization": f"Bearer {self._token.get_secret_value()}",
            **kwargs.pop("headers", {}),
        }
        try:
            response = await self._client.request(
                method, path, headers=headers, **kwargs
            )
        except httpx.RequestError:
            raise SourceOutcomeUnknown(operation) from None
        if response.status_code == 401:
            raise SourceUnauthorized()
        if response.status_code in (200, 201):
            return response
        # Older Storage responses report duplicate/auth errors inside HTTP 400.
        try:
            body = response.json()
        except ValueError:
            body = {}
        if isinstance(body, dict):
            if (
                body.get("error") in ("Duplicate", "ResourceAlreadyExists")
                or body.get("code") == "ResourceAlreadyExists"
            ):
                raise SourceConflict()
            if str(body.get("statusCode")) == "401":
                raise SourceUnauthorized()
        if response.status_code == 409:
            raise SourceConflict()
        if response.status_code == 413:
            raise SourceTooLarge()
        if response.status_code >= 500:
            raise SourceOutcomeUnknown(operation)
        raise SourceUnavailable()

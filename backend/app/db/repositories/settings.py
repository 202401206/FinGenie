"""User-scoped settings and durable deletion RPCs through the existing client."""

from typing import Literal
from uuid import UUID

import httpx
from pydantic import BaseModel, ConfigDict, SecretStr

from app.db.errors import DatabaseUnauthorized, DatabaseUnavailable
from app.schemas.settings import PreferencesPatch, UserPreferences


class DeletionConflict(Exception):
    """Another deletion is active, or the old key no longer covers current data."""

    def __init__(self, code: str = "data_deletion_conflict"):
        self.code = code
        super().__init__("Financial data deletion conflicts with current state.")


class DeletionPending(Exception):
    """The operation is durable but cleanup has not been confirmed."""

    def __init__(self, operation_id: UUID):
        self.operation_id = operation_id
        super().__init__("Financial data deletion is pending.")


class DeletionJob(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    status: Literal["pending", "completed"]


class DeletionSources(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    sources: list[str]


class SettingsRepository:
    def __init__(self, client: httpx.AsyncClient, user_id: UUID, token: str):
        self._client = client
        self.user_id = user_id
        self._token = SecretStr(token)

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token.get_secret_value()}"}

    async def _request(self, method: str, path: str, **kwargs) -> object:
        try:
            response = await self._client.request(
                method, path, headers=self.headers, **kwargs
            )
        except httpx.RequestError:
            raise DatabaseUnavailable() from None
        if response.status_code == 401:
            raise DatabaseUnauthorized()
        if response.status_code == 409:
            code = (
                "data_deletion_in_progress"
                if path.endswith("/begin_financial_data_deletion")
                else "data_deletion_conflict"
            )
            raise DeletionConflict(code)
        if response.status_code == 410:
            raise DeletionConflict("deletion_request_outdated")
        if response.status_code != 200:
            raise DatabaseUnavailable()
        try:
            return response.json()
        except ValueError:
            raise DatabaseUnavailable() from None

    async def _rpc(self, name: str, body: dict) -> object:
        return await self._request("POST", f"/rest/v1/rpc/{name}", json=body)

    async def get_preferences(self) -> UserPreferences:
        rows = await self._request(
            "GET",
            "/rest/v1/user_preferences",
            params={
                "select": "default_currency,theme",
                "user_id": f"eq.{self.user_id}",
                "limit": "1",
            },
        )
        try:
            if not isinstance(rows, list) or len(rows) > 1:
                raise ValueError()
            return self._preferences(rows[0]) if rows else UserPreferences()
        except ValueError:
            raise DatabaseUnavailable() from None

    async def patch_preferences(self, patch: PreferencesPatch) -> UserPreferences:
        result = await self._rpc(
            "patch_user_preferences", {"p_patch": patch.model_dump(exclude_unset=True)}
        )
        try:
            return self._preferences(result)
        except ValueError:
            raise DatabaseUnavailable() from None

    @staticmethod
    def _preferences(result: object) -> UserPreferences:
        if not isinstance(result, dict) or set(result) != {"default_currency", "theme"}:
            raise ValueError()
        return UserPreferences.model_validate(result)

    async def begin_deletion(self, operation_id: UUID | None) -> DeletionJob:
        result = await self._rpc(
            "begin_financial_data_deletion",
            {
                "p_operation_id": str(operation_id) if operation_id else None,
            },
        )
        try:
            job = DeletionJob.model_validate(result)
            if operation_id and job.id != operation_id:
                raise ValueError()
            return job
        except ValueError:
            raise DatabaseUnavailable() from None

    async def deletion_sources(self, operation_id: UUID) -> list[str]:
        result = await self._rpc(
            "get_financial_data_deletion_sources",
            {
                "p_operation_id": str(operation_id),
                "p_limit": 100,
            },
        )
        try:
            batch = DeletionSources.model_validate(result)
            if batch.id != operation_id or len(batch.sources) > 100:
                raise ValueError()
            for path in batch.sources:
                if not path.startswith(f"{self.user_id}/"):
                    raise ValueError()
            return batch.sources
        except ValueError:
            raise DatabaseUnavailable() from None

    async def remove_sources(self, paths: list[str]) -> None:
        # Paths originate from the persisted owned manifest, never from the API caller.
        try:
            response = await self._client.request(
                "DELETE",
                "/storage/v1/object/financial-documents",
                headers=self.headers,
                json={"prefixes": paths},
            )
        except httpx.RequestError:
            raise DatabaseUnavailable() from None
        if response.status_code == 401:
            raise DatabaseUnauthorized()
        if response.status_code not in (200, 201):
            raise DatabaseUnavailable()
        # The next RPC checks actual metadata absence, even for an empty receipt.

    async def confirm_sources(self, operation_id: UUID, paths: list[str]) -> None:
        result = await self._rpc(
            "confirm_financial_data_sources_removed",
            {
                "p_operation_id": str(operation_id),
                "p_paths": paths,
            },
        )
        if (
            not isinstance(result, dict)
            or set(result) != {"confirmed"}
            or result["confirmed"] is not True
        ):
            raise DatabaseUnavailable()

    async def finish_deletion(self, operation_id: UUID) -> None:
        result = await self._rpc(
            "finish_financial_data_deletion", {"p_operation_id": str(operation_id)}
        )
        if result != {"status": "deleted"}:
            raise DatabaseUnavailable()


async def delete_financial_data(
    repository: SettingsRepository, operation_id: UUID | None
) -> None:
    job = await repository.begin_deletion(operation_id)
    if job.status == "completed":
        return
    try:
        paths = await repository.deletion_sources(job.id)
        if paths:
            await repository.remove_sources(paths)
            await repository.confirm_sources(job.id, paths)
        # Bound each request to 100 objects; resume the same operation for more.
        if await repository.deletion_sources(job.id):
            raise DeletionPending(job.id)
        await repository.finish_deletion(job.id)
    except (DatabaseUnavailable, DeletionConflict):
        raise DeletionPending(job.id) from None

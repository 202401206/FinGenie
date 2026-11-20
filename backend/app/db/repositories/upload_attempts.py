"""Owned durable context through the existing authenticated Data API client."""

from uuid import UUID

import httpx
import simplejson
from pydantic import SecretStr

from app.db.models import Page
from app.db.repositories.parsed_documents import (
    encode_date_or_uuid,
    reject_float_values,
    validate_document_data,
)
from app.services.recovery_models import RecoveryDecision
from app.services.source_errors import (
    ParsedDocumentRejected,
    SourceConflict,
    SourceOutcomeUnknown,
    SourceUnauthorized,
    SourceUnavailable,
)
from app.services.source_models import SourceAttempt
from app.services.upload_attempt_models import (
    AttemptError,
    AttemptStatus,
    StoredUploadAttempt,
    UploadAttemptSummary,
)

SUMMARY_COLUMNS = (
    "attempt_id:id,workspace_id,document_id,document_type,status,last_error_code,"
    "receipt,created_at,updated_at"
)
CONTEXT_COLUMNS = (
    "id,user_id,workspace_id,document_id,upload_generation,user_type,document_type,"
    "kind,name,original_filename,expected_json,status,last_error_code,receipt,"
    "revision,created_at,updated_at"
)
MAX_JOURNAL_BYTES = 16 * 1024 * 1024


class UploadAttemptNotFound(Exception):
    """Missing and foreign attempts deliberately have the same result."""


class UploadAttemptRepository:
    def __init__(self, client: httpx.AsyncClient, user_id: UUID, token: str):
        self._client = client
        self._user_id = user_id
        self._token = SecretStr(token)

    async def _request(self, method: str, path: str, **kwargs) -> object:
        try:
            response = await self._client.request(
                method,
                path,
                headers={
                    "Authorization": f"Bearer {self._token.get_secret_value()}",
                    "Content-Type": "application/json",
                },
                **kwargs,
            )
        except httpx.RequestError:
            raise SourceOutcomeUnknown("journal") from None
        if response.status_code == 401:
            raise SourceUnauthorized()
        if response.status_code == 404:
            raise UploadAttemptNotFound()
        if response.status_code == 409:
            raise SourceConflict()
        if response.status_code == 422:
            raise ParsedDocumentRejected()
        if response.status_code >= 500:
            raise SourceOutcomeUnknown("journal")
        if response.status_code != 200:
            raise SourceUnavailable()
        try:
            # Decode monetary tokens directly; response.json() first would round them.
            return simplejson.loads(response.content, use_decimal=True, allow_nan=False)
        except (ValueError, UnicodeError):
            raise SourceOutcomeUnknown("journal") from None

    async def _rpc(self, name: str, body: dict[str, object]) -> object:
        return await self._request(
            "POST",
            f"/rest/v1/rpc/{name}",
            content=simplejson.dumps(
                body, use_decimal=True, allow_nan=False, default=encode_date_or_uuid
            ),
        )

    async def create(
        self,
        attempt: SourceAttempt,
        parsed_data: dict[str, object],
        *,
        attempt_id: UUID,
    ) -> UploadAttemptSummary:
        if attempt.user_id != self._user_id:
            raise ValueError("Journal owner must be the verified caller.")
        try:
            reject_float_values(parsed_data)
            statement = validate_document_data(attempt.document_type, parsed_data)
            if statement.source_metadata.document_id != attempt.document_id:
                raise ValueError()
            parsed = statement.model_dump(mode="python")
            wire = simplejson.dumps(
                parsed, use_decimal=True, allow_nan=False, default=encode_date_or_uuid
            )
            if len(wire.encode("utf-8")) > MAX_JOURNAL_BYTES:
                raise ValueError()
            simplejson.loads(wire, use_decimal=True, allow_nan=False)
        except (ValueError, TypeError):
            raise ParsedDocumentRejected() from None
        result = await self._rpc(
            "create_upload_attempt",
            {
                "p_attempt_id": str(attempt_id),
                "p_context": attempt.model_dump(mode="json"),
                "p_expected_json": parsed,
            },
        )
        summary = self._summary(result, attempt_id)
        if (
            summary.workspace_id != attempt.workspace_id
            or summary.document_id != attempt.document_id
            or summary.document_type != attempt.document_type
            or summary.status != "pending"
        ):
            raise SourceOutcomeUnknown("journal")
        return summary

    @staticmethod
    def _summary(value: object, attempt_id: UUID | None = None) -> UploadAttemptSummary:
        try:
            result = UploadAttemptSummary.model_validate(value)
            if attempt_id is not None and result.attempt_id != attempt_id:
                raise ValueError()
            return result
        except ValueError:
            raise SourceOutcomeUnknown("journal") from None

    async def _rows(self, columns: str, **params: str) -> list[object]:
        rows = await self._request(
            "GET",
            "/rest/v1/upload_attempts",
            params={"select": columns, "user_id": f"eq.{self._user_id}", **params},
        )
        if not isinstance(rows, list):
            raise SourceUnavailable()
        return rows

    async def list_attempts(
        self, *, limit: int = 50, offset: int = 0
    ) -> Page[UploadAttemptSummary]:
        if (
            type(limit) is not int
            or type(offset) is not int
            or not 1 <= limit <= 100
            or offset < 0
        ):
            raise ValueError("Use a limit of 1 to 100 and a nonnegative offset.")
        result = await self._rpc(
            "list_upload_attempts", {"p_limit": limit, "p_offset": offset}
        )
        if (
            not isinstance(result, dict)
            or set(result) != {"items", "limit", "offset", "total"}
            or type(result["total"]) is not int
            or result["total"] < 0
            or type(result["limit"]) is not int
            or result["limit"] != limit
            or type(result["offset"]) is not int
            or result["offset"] != offset
            or not isinstance(result["items"], list)
            or len(result["items"]) > limit
            or (result["items"] and offset + len(result["items"]) > result["total"])
        ):
            raise SourceUnavailable()
        return Page(
            items=[self._summary(row) for row in result["items"]],
            limit=limit,
            offset=offset,
            total=result["total"],
        )

    async def get_summary(self, attempt_id: UUID) -> UploadAttemptSummary:
        rows = await self._rows(SUMMARY_COLUMNS, id=f"eq.{attempt_id}", limit="1")
        if not rows:
            raise UploadAttemptNotFound()
        if len(rows) != 1:
            raise SourceUnavailable()
        return self._summary(rows[0], attempt_id)

    async def get(self, attempt_id: UUID) -> StoredUploadAttempt:
        rows = await self._rows(CONTEXT_COLUMNS, id=f"eq.{attempt_id}", limit="1")
        if not rows:
            raise UploadAttemptNotFound()
        if len(rows) != 1 or not isinstance(rows[0], dict):
            raise SourceUnavailable()
        row = rows[0]
        try:
            context = SourceAttempt.model_validate(
                {key: row[key] for key in SourceAttempt.model_fields}
            )
            if context.user_id != self._user_id or row["id"] != str(attempt_id):
                raise ValueError()
            statement = validate_document_data(
                context.document_type, row["expected_json"]
            )
            if statement.source_metadata.document_id != context.document_id:
                raise ValueError()
            summary_data = {
                key: row[key]
                for key in UploadAttemptSummary.model_fields
                if key != "attempt_id"
            }
            summary_data["attempt_id"] = row["id"]
            summary = self._summary(summary_data, attempt_id)
            if (
                summary.receipt is not None
                and context.document_type.value == "bank_statement"
            ):
                if summary.receipt.transaction_count != len(statement.transactions):
                    raise ValueError()
            return StoredUploadAttempt(
                summary=summary,
                attempt=context,
                parsed_data=statement.model_dump(mode="python"),
                revision=row["revision"],
            )
        except (KeyError, TypeError, ValueError):
            raise SourceUnavailable() from None

    async def begin_recovery(self, record: StoredUploadAttempt) -> RecoveryDecision:
        result = await self._rpc(
            "begin_journal_recovery",
            {
                "p_attempt_id": str(record.summary.attempt_id),
                "p_revision": record.revision,
            },
        )
        try:
            decision = RecoveryDecision.model_validate(result)
            if decision.receipt is not None and (
                decision.receipt.workspace_id != record.attempt.workspace_id
                or decision.receipt.document_id != record.attempt.document_id
                or decision.receipt.transaction_count
                != (
                    len(record.parsed_data["transactions"])
                    if record.attempt.document_type.value == "bank_statement"
                    else 0
                )
            ):
                raise ValueError()
            return decision
        except ValueError:
            raise SourceOutcomeUnknown("journal") from None

    async def settle(
        self,
        attempt_id: UUID,
        *,
        revision: int,
        status: AttemptStatus,
        error_code: AttemptError | None = None,
    ) -> UploadAttemptSummary:
        result = await self._rpc(
            "settle_upload_attempt",
            {
                "p_attempt_id": str(attempt_id),
                "p_revision": revision,
                "p_status": status,
                "p_error_code": error_code,
            },
        )
        summary = self._summary(result, attempt_id)
        if summary.status != status or summary.last_error_code != error_code:
            raise SourceOutcomeUnknown("journal")
        return summary

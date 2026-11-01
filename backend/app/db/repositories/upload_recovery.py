"""Claim a failed attempt safely and release metadata only after source removal."""

from uuid import UUID

import httpx
import simplejson
from pydantic import SecretStr

from app.db.errors import UnsupportedDocumentType
from app.db.parsed_models import ParsedBankStatement
from app.db.repositories.parsed_documents import encode_date_or_uuid
from app.schemas.common import DocumentType
from app.services.recovery_models import RecoveryDecision
from app.services.source_errors import (
    ParsedDocumentRejected,
    SourceConflict,
    SourceOutcomeUnknown,
    SourceUnauthorized,
    SourceUnavailable,
)
from app.services.source_models import SourceAttempt


class UploadRecoveryRepository:
    def __init__(
        self, client: httpx.AsyncClient, user_id: UUID, access_token: str
    ) -> None:
        self._client = client
        self._user_id = user_id
        self._token = SecretStr(access_token)

    def _attempt_parameters(self, attempt: SourceAttempt) -> dict[str, object]:
        if attempt.user_id != self._user_id:
            raise ValueError("Recovery owner must be the verified caller.")
        if attempt.document_type != DocumentType.BANK_STATEMENT:
            raise UnsupportedDocumentType()
        return {
            "p_workspace_id": str(attempt.workspace_id),
            "p_document_id": str(attempt.document_id),
            "p_file_extension": attempt.kind.value,
        }

    async def begin(
        self, attempt: SourceAttempt, parsed_data: dict[str, object]
    ) -> RecoveryDecision:
        parameters = self._attempt_parameters(attempt)
        try:
            statement = ParsedBankStatement.model_validate(parsed_data)
            if statement.source_metadata.document_id != attempt.document_id:
                raise ValueError()
            parameters["p_expected_json"] = statement.model_dump(mode="python")
            body = simplejson.dumps(
                parameters,
                use_decimal=True,
                allow_nan=False,
                default=encode_date_or_uuid,
            )
            simplejson.loads(body, use_decimal=True, allow_nan=False)
        except (ValueError, TypeError):
            raise ParsedDocumentRejected() from None

        result = await self._call("begin_upload_recovery", body)
        try:
            decision = RecoveryDecision.model_validate(result)
            if decision.receipt is not None:
                receipt = decision.receipt
                if (
                    receipt.workspace_id != attempt.workspace_id
                    or receipt.document_id != attempt.document_id
                    or receipt.transaction_count != len(statement.transactions)
                ):
                    raise ValueError()
            return decision
        except ValueError:
            raise SourceOutcomeUnknown("recovery") from None

    async def release(self, attempt: SourceAttempt) -> None:
        body = simplejson.dumps(self._attempt_parameters(attempt))
        result = await self._call("release_failed_upload", body)
        if not isinstance(result, dict) or result.get("released") is not True:
            raise SourceOutcomeUnknown("recovery")

    async def _call(self, function_name: str, body: str) -> object:
        try:
            response = await self._client.post(
                f"/rest/v1/rpc/{function_name}",
                content=body,
                headers={
                    "Authorization": f"Bearer {self._token.get_secret_value()}",
                    "Content-Type": "application/json",
                },
            )
        except httpx.RequestError:
            raise SourceOutcomeUnknown("recovery") from None
        if response.status_code == 401:
            raise SourceUnauthorized()
        if response.status_code == 409:
            raise SourceConflict()
        if response.status_code == 422:
            raise ParsedDocumentRejected()
        if response.status_code >= 500:
            raise SourceOutcomeUnknown("recovery")
        if response.status_code != 200:
            raise SourceUnavailable()
        try:
            return response.json()
        except ValueError:
            raise SourceOutcomeUnknown("recovery") from None

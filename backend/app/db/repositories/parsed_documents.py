"""Save a bank statement and its transactions through one database call."""

from datetime import date
from uuid import UUID

import httpx
import simplejson
from pydantic import SecretStr, ValidationError

from app.db.errors import UnsupportedDocumentType, WorkspaceNotFound
from app.db.parsed_models import ParsedBankStatement, ParsedSaveReceipt
from app.schemas.common import DocumentType
from app.services.source_errors import (
    ParsedDocumentRejected,
    SourceConflict,
    SourceOutcomeUnknown,
    SourceUnauthorized,
    SourceUnavailable,
)
from app.services.source_models import SourceReservation


def encode_date_or_uuid(value: object) -> str:
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    raise TypeError("Parsed data contains an unsupported JSON value.")


class ParsedDocumentRepository:
    def __init__(
        self, client: httpx.AsyncClient, user_id: UUID, access_token: str
    ) -> None:
        self._client = client
        self._user_id = user_id
        self._token = SecretStr(access_token)

    async def finalize(
        self, reservation: SourceReservation, parsed_data: dict[str, object]
    ) -> ParsedSaveReceipt:
        attempt = reservation.attempt
        if attempt.user_id != self._user_id:
            raise ValueError("Document owner must be the verified caller.")
        if attempt.document_type != DocumentType.BANK_STATEMENT:
            raise UnsupportedDocumentType()

        try:
            statement = ParsedBankStatement.model_validate(parsed_data)
            if statement.source_metadata.document_id != attempt.document_id:
                raise ValueError("Parsed source does not match the reserved document.")

            # Keep Decimal values as JSON numbers. float() would lose precision.
            body = simplejson.dumps(
                {
                    "p_workspace_id": str(attempt.workspace_id),
                    "p_document_id": str(attempt.document_id),
                    "p_parsed_json": statement.model_dump(mode="python"),
                },
                use_decimal=True,
                allow_nan=False,
                default=encode_date_or_uuid,
            )
            # Unknown fields are kept too, but they still have to be valid JSON.
            simplejson.loads(body, use_decimal=True, allow_nan=False)
        except (ValueError, TypeError):
            raise ParsedDocumentRejected() from None

        try:
            response = await self._client.post(
                "/rest/v1/rpc/finalize_bank_statement",
                headers={
                    "Authorization": f"Bearer {self._token.get_secret_value()}",
                    "Content-Type": "application/json",
                },
                content=body,
            )
        except httpx.RequestError:
            raise SourceOutcomeUnknown("finalization") from None

        if response.status_code == 401:
            raise SourceUnauthorized()
        if response.status_code == 404:
            # A missing RPC is configuration failure, not a missing workspace.
            try:
                missing_workspace = response.json().get("code") == "PT404"
            except (ValueError, AttributeError):
                missing_workspace = False
            if missing_workspace:
                raise WorkspaceNotFound()
            raise SourceUnavailable()
        if response.status_code == 409:
            raise SourceConflict()
        if response.status_code == 422:
            raise ParsedDocumentRejected()
        if response.status_code >= 500:
            raise SourceOutcomeUnknown("finalization")
        if response.status_code != 200:
            raise SourceUnavailable()

        try:
            receipt = ParsedSaveReceipt.model_validate(response.json())
            if (
                receipt.workspace_id != attempt.workspace_id
                or receipt.document_id != attempt.document_id
                or receipt.transaction_count != len(statement.transactions)
            ):
                raise ValueError()
            return receipt
        except (ValueError, ValidationError):
            # The save may have completed even though the receipt is unusable.
            raise SourceOutcomeUnknown("finalization") from None

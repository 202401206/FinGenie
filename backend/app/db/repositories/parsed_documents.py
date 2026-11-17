"""Save a validated document through its atomic database function."""

from datetime import date
from uuid import UUID

import httpx
import simplejson
from pydantic import SecretStr, ValidationError

from app.db.errors import UnsupportedDocumentType, WorkspaceNotFound
from app.db.parsed_models import ParsedBankStatement, ParsedSaveReceipt
from app.db.parsed_read_models import ParsedBalanceSheet
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


def reject_float_values(value: object) -> None:
    """Prior-period and extra balance fields must keep exact numbers too."""
    if isinstance(value, float):
        raise ValueError("Use Decimal values rather than binary floats.")
    if isinstance(value, dict):
        for item in value.values():
            reject_float_values(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            reject_float_values(item)


def validate_document_data(
    document_type: DocumentType, parsed_data: dict[str, object]
) -> ParsedBankStatement | ParsedBalanceSheet:
    """Use the same stored contract for saving and recovery reconciliation."""
    if document_type == DocumentType.BANK_STATEMENT:
        return ParsedBankStatement.model_validate(parsed_data)
    if document_type == DocumentType.BALANCE_SHEET:
        reject_float_values(parsed_data)
        statement = ParsedBalanceSheet.model_validate(parsed_data)
        if statement.currency not in (None, "INR", "USD"):
            raise ValueError("Unsupported balance-sheet currency.")
        return statement
    raise UnsupportedDocumentType()


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
        try:
            statement = validate_document_data(attempt.document_type, parsed_data)
            if attempt.document_type == DocumentType.BANK_STATEMENT:
                function = "finalize_bank_statement"
                transaction_count = len(statement.transactions)
            elif attempt.document_type == DocumentType.BALANCE_SHEET:
                function = "finalize_balance_sheet"
                transaction_count = 0
            else:
                raise UnsupportedDocumentType()
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
                f"/rest/v1/rpc/{function}",
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
                or receipt.transaction_count != transaction_count
            ):
                raise ValueError()
            return receipt
        except (ValueError, ValidationError):
            # The save may have completed even though the receipt is unusable.
            raise SourceOutcomeUnknown("finalization") from None

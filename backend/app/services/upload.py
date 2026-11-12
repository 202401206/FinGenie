"""One upload workflow, with an explicitly supplied bank parser."""

from datetime import UTC, date, datetime
from typing import Protocol
from uuid import UUID

import simplejson
from pydantic import BaseModel
from pydantic_core import PydanticSerializationError
from starlette.concurrency import run_in_threadpool

from app.db.errors import (
    DatabaseUnauthorized,
    DatabaseUnavailable,
    UnsupportedDocumentType,
    WorkspaceNotFound,
)
from app.db.parsed_models import ParsedBankStatement, ParsedSaveReceipt
from app.db.repositories.parsed_documents import ParsedDocumentRepository
from app.db.repositories.workspaces import WorkspaceRepository
from app.parsers.errors import BankStatementParserError
from app.schemas.upload_responses import UploadResponse
from app.services.source_dependencies import SourceUploadAccess
from app.services.source_errors import (
    ParsedDocumentRejected,
    SourceConflict,
    SourceOutcomeUnknown,
    SourceTooLarge,
    SourceUnauthorized,
    SourceUnavailable,
)
from app.services.source_models import SourceAttempt, SourceReservation
from app.services.upload_recovery import UploadRecoveryService
from app.services.upload_validation import (
    DEFAULT_POLICY,
    UploadPolicy,
    UploadReader,
    validate_upload,
)


class BankParser(Protocol):
    def __call__(
        self, content: bytes, *, file_kind: str, document_id: UUID
    ) -> BaseModel: ...


class UploadProcessingError(Exception):
    """Safe HTTP-facing error with an internal attempt for reconciliation."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        attempt: SourceAttempt | None = None,
    ):
        self.status_code = status_code
        self.code = code
        self.attempt = attempt
        super().__init__(message)


def encode_parsed_value(value: object) -> str:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    raise TypeError("Unsupported parsed value.")


def validate_parsed(
    model: BaseModel, attempt: SourceAttempt, policy: UploadPolicy
) -> dict[str, object]:
    try:
        statement = ParsedBankStatement.model_validate(
            model.model_dump(mode="python", warnings="error")
        )
        if statement.source_metadata.document_id != attempt.document_id:
            raise ValueError()
        if len(statement.transactions) > policy.max_rows:
            raise ValueError()
        payload = statement.model_dump(mode="python")
        # Validate unknown fields too, before any reservation. Keep Decimal intact.
        wire = simplejson.dumps(
            payload, use_decimal=True, allow_nan=False, default=encode_parsed_value
        )
        simplejson.loads(wire, use_decimal=True, allow_nan=False)
        return payload
    except (ValueError, TypeError, AttributeError, PydanticSerializationError):
        raise UploadProcessingError(
            422, "invalid_parsed_document", "The parsed statement is invalid."
        ) from None


def checked_receipt(
    value: ParsedSaveReceipt, attempt: SourceAttempt, parsed: dict[str, object]
) -> ParsedSaveReceipt:
    try:
        receipt = ParsedSaveReceipt.model_validate(value)
    except ValueError:
        raise SourceOutcomeUnknown("finalization") from None
    if (
        receipt.workspace_id != attempt.workspace_id
        or receipt.document_id != attempt.document_id
        or receipt.transaction_count != len(parsed["transactions"])
    ):
        raise SourceOutcomeUnknown("finalization")
    return receipt


def original_failure(error: Exception, attempt: SourceAttempt) -> UploadProcessingError:
    if isinstance(error, SourceUnauthorized):
        return UploadProcessingError(
            401, "unauthorized", "A valid access token is required.", attempt
        )
    if isinstance(error, SourceTooLarge):
        return UploadProcessingError(
            413,
            "file_too_large",
            "The file exceeds the supported upload size.",
            attempt,
        )
    if isinstance(error, SourceConflict):
        return UploadProcessingError(
            409, "upload_conflict", "The upload conflicts with existing data.", attempt
        )
    if isinstance(error, (ParsedDocumentRejected, UnsupportedDocumentType)):
        return UploadProcessingError(
            422,
            "invalid_parsed_document",
            "The parsed statement was rejected.",
            attempt,
        )
    if isinstance(error, WorkspaceNotFound):
        return UploadProcessingError(
            404, "workspace_not_found", "Workspace not found.", attempt
        )
    return UploadProcessingError(
        503, "upload_unavailable", "The upload could not be completed.", attempt
    )


class UploadService:
    def __init__(
        self,
        parser: BankParser,
        access: SourceUploadAccess,
        save_repository: ParsedDocumentRepository,
        recovery: UploadRecoveryService,
        workspace_repository: WorkspaceRepository,
        *,
        policy: UploadPolicy = DEFAULT_POLICY,
    ):
        self.parser = parser
        self.access = access
        self.save_repository = save_repository
        self.recovery = recovery
        self.workspace_repository = workspace_repository
        self.policy = policy

    async def process(
        self, file: UploadReader, *, user_type: str, document_type: str
    ) -> UploadResponse:
        upload = await validate_upload(
            file, user_type=user_type, document_type=document_type, policy=self.policy
        )
        attempt = SourceAttempt(
            user_id=self.access.user.id,
            user_type=upload.user_type,
            document_type=upload.document_type,
            original_filename=upload.filename,
            kind=upload.kind,
            name=f"Bank statement {datetime.now(UTC).date().isoformat()}",
        )
        try:
            model = await run_in_threadpool(
                self.parser,
                upload.content,
                file_kind=attempt.kind.value,
                document_id=attempt.document_id,
            )
        except BankStatementParserError:
            raise UploadProcessingError(
                422,
                "statement_parse_failed",
                "The statement format or contents are unsupported.",
            ) from None
        parsed = validate_parsed(model, attempt, self.policy)

        reservation = None
        try:
            reservation = await self.access.reservations.reserve(attempt)
            await self.access.storage.upload(
                reservation, upload.content, max_bytes=self.policy.max_bytes
            )
            receipt = checked_receipt(
                await self.save_repository.finalize(reservation, parsed),
                attempt,
                parsed,
            )
        except SourceOutcomeUnknown as error:
            # This subclass must precede SourceUnavailable. Recovery decides state.
            return await self.recover(attempt, parsed, reservation, error)
        except (
            SourceUnauthorized,
            SourceTooLarge,
            SourceConflict,
            SourceUnavailable,
            ParsedDocumentRejected,
            WorkspaceNotFound,
            UnsupportedDocumentType,
        ) as error:
            return await self.recover(attempt, parsed, reservation, error)
        return UploadResponse(
            workspace=reservation.workspace,
            document={"id": receipt.document_id, "status": receipt.status},
        )

    async def recover(
        self,
        attempt: SourceAttempt,
        parsed: dict[str, object],
        reservation: SourceReservation | None,
        error: Exception,
    ) -> UploadResponse:
        try:
            result = await self.recovery.recover(attempt, parsed)
        except (
            SourceOutcomeUnknown,
            SourceUnavailable,
            SourceUnauthorized,
            SourceConflict,
        ):
            raise UploadProcessingError(
                503,
                "reconciliation_required",
                "Upload completion could not be confirmed.",
                attempt,
            ) from None
        if result.status == "cleaned":
            raise original_failure(error, attempt) from None
        if result.status == "pending":
            if result.reason == "auth_required":
                raise UploadProcessingError(
                    401, "unauthorized", "A valid access token is required.", attempt
                )
            raise UploadProcessingError(
                503, result.reason, "Upload recovery needs follow-up.", attempt
            )
        try:
            receipt = checked_receipt(result.receipt, attempt, parsed)
        except SourceOutcomeUnknown:
            raise UploadProcessingError(
                503,
                "reconciliation_required",
                "Upload completion could not be confirmed.",
                attempt,
            ) from None
        if reservation is None:
            try:
                details = await self.workspace_repository.get_workspace(
                    attempt.workspace_id
                )
            except (DatabaseUnauthorized, DatabaseUnavailable, WorkspaceNotFound):
                raise UploadProcessingError(
                    503,
                    "upload_unavailable",
                    "Saved workspace details are unavailable.",
                    attempt,
                ) from None
            workspace = details.workspace
            if (
                workspace.id != attempt.workspace_id
                or workspace.name != attempt.name
                or workspace.user_type != attempt.user_type
                or workspace.document_type != attempt.document_type
            ):
                raise UploadProcessingError(
                    503,
                    "reconciliation_required",
                    "Saved workspace details could not be confirmed.",
                    attempt,
                )
        else:
            workspace = reservation.workspace
        return UploadResponse(
            workspace=workspace,
            document={"id": receipt.document_id, "status": receipt.status},
        )

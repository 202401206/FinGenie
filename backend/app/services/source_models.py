"""Internal source-upload context. None of these models are public API responses."""

from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.db.models import WorkspaceRecord
from app.schemas.common import DocumentType, UserType

SOURCE_BUCKET = "financial-documents"


class SourceKind(StrEnum):
    CSV = "csv"
    XLSX = "xlsx"

    @property
    def content_type(self) -> str:
        return {
            SourceKind.CSV: "text/csv",
            SourceKind.XLSX: (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
        }[self]


class SourceAttempt(BaseModel):
    """Generate once on the server, then retain these IDs if a response is lost."""

    model_config = ConfigDict(frozen=True)

    user_id: UUID
    workspace_id: UUID = Field(default_factory=uuid4)
    document_id: UUID = Field(default_factory=uuid4)
    user_type: UserType
    document_type: DocumentType
    name: str = Field(min_length=1, max_length=255)
    original_filename: str = Field(min_length=1, max_length=255)
    kind: SourceKind

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value or any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError(
                "Use a nonempty workspace name without control characters."
            )
        return value

    @field_validator("original_filename", mode="before")
    @classmethod
    def sanitize_filename(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        # Strip either platform's directory components. Names never become paths.
        basename = value.replace("\\", "/").rsplit("/", 1)[-1]
        basename = "".join(
            "_" if ord(char) < 32 or ord(char) == 127 else char for char in basename
        ).strip()
        if basename in ("", ".", ".."):
            raise ValueError("A source filename is required.")
        return basename

    @model_validator(mode="after")
    def validate_context(self) -> "SourceAttempt":
        if (
            self.user_type == UserType.PERSONAL
            and self.document_type != DocumentType.BANK_STATEMENT
        ):
            raise ValueError("Personal workspaces only support bank statements.")
        if not self.original_filename.lower().endswith(f".{self.kind.value}"):
            raise ValueError("Filename extension must match the validated file kind.")
        return self

    @property
    def path(self) -> str:
        return (
            f"{self.user_id}/{self.workspace_id}/{self.document_id}/"
            f"source.{self.kind.value}"
        )


class ReservedDocument(BaseModel):
    id: UUID
    file_path: str
    status: str


class SourceReservation(BaseModel):
    attempt: SourceAttempt
    workspace: WorkspaceRecord
    document: ReservedDocument

    @model_validator(mode="after")
    def validate_receipt(self) -> "SourceReservation":
        attempt = self.attempt
        if (
            self.workspace.id != attempt.workspace_id
            or self.workspace.name != attempt.name
            or self.workspace.user_type != attempt.user_type
            or self.workspace.document_type != attempt.document_type
            or self.document.id != attempt.document_id
            or self.document.file_path != attempt.path
            or self.document.status != "uploaded"
        ):
            raise ValueError("Reservation receipt does not match the upload attempt.")
        return self

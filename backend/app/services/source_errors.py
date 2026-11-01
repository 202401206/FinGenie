"""Safe source-operation errors. Never attach upstream bodies or credentials."""

from typing import Literal


class SourceUnavailable(Exception):
    """A dependency rejected a request or could not provide a usable response."""


class SourceUnauthorized(Exception):
    """The caller's token was rejected. Re-authenticate before continuing."""


class SourceConflict(Exception):
    """An ID or immutable source object already exists; do not overwrite it."""


class SourceTooLarge(Exception):
    """The source exceeds the caller's agreed bound or the Storage limit."""


class SourceOutcomeUnknown(SourceUnavailable):
    """A write may have succeeded. Reconcile the same IDs before any retry/cleanup."""

    def __init__(
        self, operation: Literal["reservation", "upload", "removal", "finalization"]
    ) -> None:
        self.operation = operation
        super().__init__("The source operation outcome could not be confirmed.")


class ParsedDocumentRejected(Exception):
    """Parsed data did not meet the save contract; no partial save is allowed."""

"""Shared synthetic upload fixtures; no real account data."""

from uuid import UUID

from app.services.source_models import SourceAttempt, SourceReservation

OWNER = UUID("10000000-0000-4000-8000-000000000001")
OTHER = UUID("10000000-0000-4000-8000-000000000002")


def make_attempt(**changes):
    return SourceAttempt(
        **{
            "user_id": OWNER,
            "user_type": "personal",
            "document_type": "bank_statement",
            "name": "Synthetic statement",
            "original_filename": "synthetic.csv",
            "kind": "csv",
            **changes,
        }
    )


def receipt(attempt):
    return {
        "workspace": {
            "id": str(attempt.workspace_id),
            "name": attempt.name,
            "user_type": attempt.user_type.value,
            "document_type": attempt.document_type.value,
            "created_at": "2026-10-31T09:00:00Z",
        },
        "document": {
            "id": str(attempt.document_id),
            "status": "uploaded",
            "file_path": attempt.path,
        },
    }


def reserved(attempt):
    return SourceReservation(attempt=attempt, **receipt(attempt))

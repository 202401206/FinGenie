"""Controlled upload collaborators used only by milestone 4 tests."""

import io
import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

from pydantic import BaseModel
from starlette.datastructures import UploadFile

from app.db.parsed_models import ParsedBankStatement, ParsedSaveReceipt
from app.schemas.responses import CurrentUser
from app.services.recovery_models import RecoveryResult
from app.services.source_dependencies import SourceUploadAccess
from tests.source_fixtures import OWNER, reserved


class UploadHarness:
    def __init__(
        self, *, stage=None, error=None, recovery_status="cleaned", reason=None
    ):
        self.calls = []
        self.stage = stage
        self.error = error
        self.recovery_status = recovery_status
        self.reason = reason
        self.attempt = None
        self.parsed = None
        self.content = b"Date,Credit\n2026-01-01,12.30\n"
        self.access = SourceUploadAccess(
            CurrentUser(id=OWNER),
            SimpleNamespace(reserve=self.reserve),
            SimpleNamespace(upload=self.upload),
        )
        self.save = SimpleNamespace(finalize=self.finalize)
        self.recovery = SimpleNamespace(recover=self.recover)
        self.reads = SimpleNamespace(get_workspace=self.get_workspace)

    def parse(self, content: bytes, *, file_kind: str, document_id: UUID) -> BaseModel:
        self.calls.append("parse")
        assert content == self.content and file_kind == "csv"
        self.document_id = document_id
        if self.stage == "parse":
            raise self.error
        fixture = (
            Path(__file__).resolve().parents[2]
            / "contracts/examples/bank-statement.json"
        )
        data = json.loads(fixture.read_text(encoding="utf-8"), parse_float=Decimal)
        data["source_metadata"]["document_id"] = document_id
        return ParsedBankStatement.model_validate(data)

    def fail(self, stage):
        self.calls.append(stage)
        if self.stage == stage:
            raise self.error

    async def reserve(self, attempt):
        self.attempt = attempt
        assert attempt.document_id == self.document_id
        assert attempt.user_id == self.access.user.id
        self.fail("reserve")
        return reserved(attempt)

    async def upload(self, reservation, content, *, max_bytes):
        assert reservation.attempt is self.attempt
        assert content == self.content and max_bytes == 5 * 1024 * 1024
        self.fail("upload")

    def receipt(self):
        return ParsedSaveReceipt(
            workspace_id=self.attempt.workspace_id,
            document_id=self.attempt.document_id,
            status="parsed",
            transaction_count=len(self.parsed["transactions"]),
        )

    async def finalize(self, reservation, parsed):
        assert reservation.attempt is self.attempt
        self.parsed = parsed
        assert isinstance(parsed["opening_balance"], Decimal)
        self.fail("finalize")
        return self.receipt()

    async def recover(self, attempt, parsed):
        assert attempt is self.attempt
        self.calls.append("recover")
        self.parsed = parsed
        if self.recovery_status == "raises":
            raise self.error
        return RecoveryResult(
            status=self.recovery_status,
            receipt=self.receipt() if self.recovery_status == "completed" else None,
            reason=self.reason,
        )

    async def get_workspace(self, workspace_id):
        self.calls.append("read")
        assert workspace_id == self.attempt.workspace_id
        return SimpleNamespace(workspace=reserved(self.attempt).workspace)

    def file(self):
        return UploadFile(io.BytesIO(self.content), filename="statement.csv")

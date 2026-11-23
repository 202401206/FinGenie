"""Explicit post-integration suite; requires Dhaval's real parser branch.

Run: python -m pytest verification/test_balance_parser_persistence.py -q
This is deliberately outside the normal tests/ path. Missing dependencies fail
instead of being replaced with a parser stub or silently skipped.
"""

import asyncio
import csv
import io
from pathlib import Path
from uuid import uuid4

import pytest
from openpyxl import Workbook

from app.analysis.balance_sheet_kpis import analyze_balance_sheet
from app.db.errors import WorkspaceNotFound
from app.db.repositories.parsed_documents import ParsedDocumentRepository
from app.db.repositories.source_uploads import SourceReservationRepository
from app.db.repositories.workspaces import WorkspaceRepository
from app.parsers.balance_sheet import parse_balance_sheet
from tests.db.test_balance_document_saves import balance_attempt
from tests.integration.test_persistence_recovery import database as database
from tests.integration.test_persistence_recovery import helpers
from tests.integration.test_settings import SettingsSupabase
from tests.integration.test_upload_journal import service
from tests.source_fixtures import OTHER, OWNER


def balance_bytes(layout, kind):
    path = (
        Path(__file__).resolve().parents[1]
        / "tests/parsers/fixtures"
        / f"synthetic_balance_sheet_layout_{layout}.csv"
    )
    content = path.read_bytes()
    if kind == "csv":
        return content
    workbook = Workbook()
    workbook.active.title = "Synthetic balance"
    for row in csv.reader(io.StringIO(content.decode("utf-8"))):
        workbook.active.append(row)
    output = io.BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


@pytest.mark.parametrize("layout", ["a", "b"])
@pytest.mark.parametrize("kind", ["csv", "xlsx"])
def test_real_balance_parser_journal_save_read_analysis_and_recovery(
    database, layout, kind
):
    server = SettingsSupabase(database)
    content = balance_bytes(layout, kind)
    attempt = balance_attempt(kind=kind, original_filename=f"synthetic.{kind}")
    statement = parse_balance_sheet(
        content, file_kind=kind, document_id=attempt.document_id
    )
    parsed = statement.model_dump(mode="python")

    async def run():
        async with helpers(server) as (client, _):
            current = service(client)
            identifier = uuid4()
            await current.prepare(attempt, parsed, attempt_id=identifier)
            reservation = await SourceReservationRepository(
                client, OWNER, "token-a"
            ).reserve(attempt)
            await current.storage.upload(
                reservation, content, max_bytes=5 * 1024 * 1024
            )
            receipt = await ParsedDocumentRepository(client, OWNER, "token-a").finalize(
                reservation, parsed
            )
            assert receipt.transaction_count == 0
            await current.confirm_completed(identifier)
            saved = await WorkspaceRepository(
                client, OWNER, "token-a"
            ).get_parsed_document(attempt.workspace_id)
            assert saved.document_id == attempt.document_id
            data = saved.parsed_json.model_dump(mode="python")
            assert data == parsed
            assert data["source_metadata"]["document_id"] == attempt.document_id
            if layout == "b":
                assert any(
                    item["reason"] == "prior_period_value" for item in data["unmapped"]
                )
            analysis = analyze_balance_sheet(
                data, str(attempt.workspace_id), include_current_ratio=True
            )
            assert analysis["reliability"] == "valid"
            working_capital = next(
                m for m in analysis["metrics"] if m["key"] == "working_capital"
            )
            assert working_capital["value"] == (7000000 if layout == "a" else 400000000)
            for _ in range(2):
                assert (await current.recover(identifier)).status == "completed"
                assert server.files[attempt.path] == content
            assert (
                await WorkspaceRepository(client, OWNER, "token-a").get_workspace(
                    attempt.workspace_id
                )
            ).documents[0].period_start is None
            rows = database(
                "select count(*)::int as count from public.transactions where document_id=$1",
                [str(attempt.document_id)],
                OWNER,
            )
            assert rows["rows"][0]["count"] == 0
        async with helpers(server, "token-b") as (client, _):
            with pytest.raises(WorkspaceNotFound):
                await WorkspaceRepository(client, OTHER, "token-b").get_parsed_document(
                    attempt.workspace_id
                )

    asyncio.run(run())

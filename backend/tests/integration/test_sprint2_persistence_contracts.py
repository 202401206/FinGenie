"""Lead-owned boundaries: persisted data feeds pure analysis, not fixture routes.

Balance inputs here are validated contract fixtures. Real balance parser and
public A2-A4 integration are verified separately after their branches meet.
"""

import asyncio
from decimal import Decimal
from uuid import uuid4

import pytest

from app.ai.providers.groq_provider import GroqProvider
from app.ai.summary import generate_summary
from app.analysis.balance_sheet_kpis import analyze_balance_sheet
from app.analysis.bank_kpis import analyze_bank_statement
from app.core.config import Settings
from app.db.errors import WorkspaceNotFound
from app.db.repositories.settings import SettingsRepository, delete_financial_data
from app.db.repositories.source_uploads import SourceReservationRepository
from app.db.repositories.upload_attempts import UploadAttemptNotFound
from app.db.repositories.workspaces import WorkspaceRepository
from app.services.source_errors import SourceOutcomeUnknown
from tests.integration.test_persistence_recovery import database as database
from tests.integration.test_persistence_recovery import helpers, store
from tests.integration.test_settings import SettingsSupabase
from tests.integration.test_upload_journal import context, service
from tests.source_fixtures import OTHER, OWNER


@pytest.mark.parametrize("balance", [False, True])
def test_owned_saved_data_reaches_pure_analysis_and_offline_summary(database, balance):
    server = SettingsSupabase(database)
    attempt, parsed = context(balance)
    identifier = uuid4()
    exact = Decimal("12345678901234567890.1234567890123456789")
    parsed["prior_period"] = {"traceable_total": exact}

    async def run():
        async with helpers(server) as (client, _):
            attempts = service(client)
            await attempts.prepare(attempt, parsed, attempt_id=identifier)
            await store(client, OWNER, "token-a", attempt, parsed)
            await attempts.confirm_completed(identifier)
            saved = await WorkspaceRepository(
                client, OWNER, "token-a"
            ).get_parsed_document(attempt.workspace_id)
            assert saved.document_id == attempt.document_id
            data = saved.parsed_json.model_dump(mode="python")
            assert data["prior_period"]["traceable_total"] == exact
            analyze = analyze_balance_sheet if balance else analyze_bank_statement
            analysis = analyze(data, str(saved.workspace.id))
            assert analysis["workspace_id"] == str(attempt.workspace_id)
            assert analysis["reliability"] == "valid"
            assert analysis["currency"] == parsed["currency"]
            for metric in analysis["metrics"]:
                assert not isinstance(metric["value"], float)
                for reference in metric["source_refs"]:
                    assert str(reference["document_id"]) == str(attempt.document_id)
            # Explicitly unconfigured provider: no network or live key is consulted.
            summary = await generate_summary(
                data, provider=GroqProvider(settings=Settings(groq_api_key=None))
            )
            assert summary.disclaimer == "This is not financial advice."
            assert summary.calculation_ids and summary.source_refs
            assert all(
                ref.document_id == str(attempt.document_id)
                for ref in summary.source_refs
            )
        async with helpers(server, "token-b") as (client, _):
            with pytest.raises(WorkspaceNotFound):
                await WorkspaceRepository(client, OTHER, "token-b").get_parsed_document(
                    attempt.workspace_id
                )
            with pytest.raises(UploadAttemptNotFound):
                await service(client, OTHER, "token-b").recover(identifier)
        assert attempt.path in server.files

    asyncio.run(run())


@pytest.mark.parametrize("balance", [False, True])
def test_lost_save_recovery_and_deletion_share_original_ids_without_reviving_data(
    database, balance
):
    server = SettingsSupabase(database)

    async def run():
        async with helpers(server) as (client, _):
            generation = await SourceReservationRepository(
                client, OWNER, "token-a"
            ).get_generation()
            attempt, parsed = context(balance, upload_generation=generation)
            identifier = uuid4()
            current = service(client)
            await current.prepare(attempt, parsed, attempt_id=identifier)
            server.timeout_after = (
                "finalize_balance_sheet" if balance else "finalize_bank_statement"
            )
            with pytest.raises(SourceOutcomeUnknown):
                await store(client, OWNER, "token-a", attempt, parsed)
            assert (await service(client).recover(identifier)).status == "completed"
            assert attempt.path in server.files
            await delete_financial_data(
                SettingsRepository(client, OWNER, "token-a"), uuid4()
            )
            with pytest.raises(UploadAttemptNotFound):
                await service(client).recover(identifier)
            with pytest.raises(WorkspaceNotFound):
                await WorkspaceRepository(client, OWNER, "token-a").get_parsed_document(
                    attempt.workspace_id
                )
            assert attempt.path not in server.files
            assert (
                await SettingsRepository(client, OWNER, "token-a").get_preferences()
            ).theme == "light"

    asyncio.run(run())

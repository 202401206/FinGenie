"""Durable recovery with real repositories/SQL/RLS and synthetic Auth/Storage."""

import asyncio
from decimal import Decimal
from uuid import uuid4

import httpx
import pytest

from app.db.repositories.settings import (
    DeletionConflict,
    SettingsRepository,
    delete_financial_data,
)
from app.db.repositories.source_uploads import SourceReservationRepository
from app.db.repositories.upload_attempts import (
    UploadAttemptNotFound,
    UploadAttemptRepository,
)
from app.db.repositories.upload_recovery import UploadRecoveryRepository
from app.db.repositories.workspaces import WorkspaceRepository
from app.services.source_errors import (
    SourceConflict,
    SourceOutcomeUnknown,
)
from app.services.source_storage import SourceStorage
from app.services.upload import UploadProcessingError, UploadService
from app.services.upload_attempts import UploadAttemptService
from tests.db.test_balance_document_saves import balance_attempt, balance_statement
from tests.db.test_parsed_documents import parsed_statement
from tests.integration.test_persistence_recovery import database as database
from tests.integration.test_persistence_recovery import helpers, store
from tests.integration.test_settings import SettingsSupabase
from tests.source_fixtures import OTHER, OWNER, make_attempt
from tests.upload_fixtures import UploadHarness


def service(client, owner=OWNER, token="token-a"):
    return UploadAttemptService(
        UploadAttemptRepository(client, owner, token),
        UploadRecoveryRepository(client, owner, token),
        SourceStorage(client, owner, token),
    )


def context(balance=False, **changes):
    attempt = (balance_attempt if balance else make_attempt)(**changes)
    return attempt, (balance_statement if balance else parsed_statement)(attempt)


@pytest.mark.parametrize("balance", [False, True])
def test_journal_survives_restart_and_lost_finalization_with_exact_money(
    database, balance
):
    server = SettingsSupabase(database)
    attempt, parsed = context(balance)
    identifier = uuid4()
    exact = Decimal("12345678901234567890.1234567890123456789")
    parsed["prior_period"] = {"total": exact}

    async def run():
        async with helpers(server) as (client, _):
            first = service(client)
            await first.prepare(attempt, parsed, attempt_id=identifier)
            # A repeat of an identical, still-pending journal creation is idempotent.
            await first.prepare(attempt, parsed, attempt_id=identifier)
            server.timeout_after = (
                "finalize_balance_sheet" if balance else "finalize_bank_statement"
            )
            with pytest.raises(SourceOutcomeUnknown):
                await store(client, OWNER, "token-a", attempt, parsed)
        # New authenticated client and service: no request-local attempt or token replay.
        async with helpers(server) as (fresh, _):
            restarted = service(fresh)
            record = await restarted.journal.get(identifier)
            assert record.attempt == attempt
            assert record.parsed_data["prior_period"]["total"] == exact
            summaries = await restarted.journal.list_attempts(limit=100)
            assert identifier in [s.attempt_id for s in summaries.items]
            for _ in range(2):
                result = await restarted.recover(identifier)
                assert result.status == "completed"
                assert result.receipt.workspace_id == attempt.workspace_id
                assert result.receipt.document_id == attempt.document_id
                assert result.receipt.transaction_count == (0 if balance else 3)
                assert attempt.path in server.files
            summary = await restarted.journal.get_summary(identifier)
            assert summary.status == "completed"
            assert set(summary.model_dump()) == {
                "attempt_id",
                "workspace_id",
                "document_id",
                "document_type",
                "status",
                "last_error_code",
                "receipt",
                "created_at",
                "updated_at",
            }
            assert "expected_json" not in summary.model_dump()

    asyncio.run(run())


@pytest.mark.parametrize("balance", [False, True])
@pytest.mark.parametrize(
    "fault",
    [
        "none",
        "storage",
        "begin_journal_recovery",
        "release_failed_upload",
        "settle_upload_attempt",
    ],
)
def test_pending_cleanup_and_lost_replies_can_be_resumed_repeatedly(
    database, balance, fault
):
    server = SettingsSupabase(database)
    attempt, parsed = context(balance)
    identifier = uuid4()

    async def run():
        async with helpers(server) as (client, _):
            current = service(client)
            await current.prepare(attempt, parsed, attempt_id=identifier)
            reservation = await SourceReservationRepository(
                client, OWNER, "token-a"
            ).reserve(attempt)
            await current.storage.upload(reservation, b"synthetic", max_bytes=100)
            server.reject_delete = fault == "storage"
            server.timeout_after = fault if fault not in ("none", "storage") else None
            first = await current.recover(identifier)
            assert first.status == ("cleaned" if fault == "none" else "pending")
            server.reject_delete = False
            # A new instance settles the same original IDs, including a lost settlement reply.
            for _ in range(2):
                assert (await service(client).recover(identifier)).status == "cleaned"
            assert attempt.path not in server.files
            assert (await current.journal.get_summary(identifier)).status == "cleaned"
            with pytest.raises(SourceConflict):
                await SourceReservationRepository(client, OWNER, "token-a").reserve(
                    attempt
                )

    asyncio.run(run())


@pytest.mark.parametrize("balance", [False, True])
def test_foreign_and_missing_attempts_share_not_found_and_cannot_clean_sources(
    database, balance
):
    server = SettingsSupabase(database)
    attempt, parsed = context(balance)
    identifier = uuid4()

    async def run():
        async with helpers(server) as (client, _):
            await service(client).prepare(attempt, parsed, attempt_id=identifier)
            await store(client, OWNER, "token-a", attempt, parsed)
        async with helpers(server, "token-b") as (client, _):
            other = service(client, OTHER, "token-b")
            for value in (identifier, uuid4()):
                for method in (
                    other.journal.get,
                    other.journal.get_summary,
                    other.recover,
                ):
                    with pytest.raises(UploadAttemptNotFound):
                        await method(value)
            assert identifier not in [
                s.attempt_id for s in (await other.journal.list_attempts()).items
            ]
        assert attempt.path in server.files

    asyncio.run(run())


@pytest.mark.parametrize("balance", [False, True])
def test_conflicts_are_sticky_and_preserve_saved_source_and_context(database, balance):
    server = SettingsSupabase(database)
    attempt, parsed = context(balance)
    identifier = uuid4()

    async def run():
        async with helpers(server) as (client, _):
            current = service(client)
            await current.prepare(attempt, parsed, attempt_id=identifier)
            await store(client, OWNER, "token-a", attempt, parsed)
            result = database(
                "update public.documents set currency='USD' where id=$1",
                [str(attempt.document_id)],
                OWNER,
            )
            assert "error" not in result
            for _ in range(2):
                recovery = await current.recover(identifier)
                assert (
                    recovery.status == "pending" and recovery.reason == "state_conflict"
                )
                assert attempt.path in server.files
            assert (
                await current.journal.get_summary(identifier)
            ).status == "needs_review"
            assert (await current.journal.get(identifier)).parsed_data[
                "currency"
            ] == parsed["currency"]

    asyncio.run(run())


@pytest.mark.parametrize("balance", [False, True])
def test_completed_marker_is_rechecked_and_never_authorizes_later_cleanup(
    database, balance
):
    server = SettingsSupabase(database)
    attempt, parsed = context(balance)
    identifier = uuid4()

    async def run():
        async with helpers(server) as (client, _):
            current = service(client)
            await current.prepare(attempt, parsed, attempt_id=identifier)
            await store(client, OWNER, "token-a", attempt, parsed)
            await current.confirm_completed(identifier)
            # Simulate conflicting external metadata loss while the original file remains.
            assert "error" not in database(
                "delete from public.transactions where document_id=$1",
                [str(attempt.document_id)],
                OWNER,
            )
            assert "error" not in database(
                "delete from public.documents where id=$1",
                [str(attempt.document_id)],
                OWNER,
            )
            assert "error" not in database(
                "delete from public.workspaces where id=$1",
                [str(attempt.workspace_id)],
                OWNER,
            )
            result = await current.recover(identifier)
            assert result.status == "pending" and result.reason == "state_conflict"
            assert attempt.path in server.files
            rows = database(
                "select * from public.upload_cancellations where workspace_id=$1",
                [str(attempt.workspace_id)],
                OWNER,
            )
            assert (
                rows["rows"] == []
            )  # The protective subtransaction undid attempted cancellation.
            assert (
                await current.journal.get_summary(identifier)
            ).status == "needs_review"

    asyncio.run(run())


def test_stale_revision_and_unverified_completion_cannot_overwrite_evidence(database):
    server = SettingsSupabase(database)
    attempt, parsed = context()
    identifier = uuid4()

    async def run():
        async with helpers(server) as (client, _):
            current = service(client)
            await current.prepare(attempt, parsed, attempt_id=identifier)
            with pytest.raises(SourceConflict):
                await current.confirm_completed(identifier)
            # Failed evidence checks roll back cancellation; the real upload can still finish.
            await store(client, OWNER, "token-a", attempt, parsed)
            await current.confirm_completed(identifier)
            with pytest.raises(SourceConflict):
                await current.journal.settle(
                    identifier,
                    revision=0,
                    status="pending",
                    error_code="cleanup_required",
                )
            assert (await current.journal.get_summary(identifier)).status == "completed"
            assert attempt.path in server.files

    asyncio.run(run())


@pytest.mark.parametrize("stage", ["create_upload_attempt", "settle_upload_attempt"])
def test_real_upload_service_stops_on_unknown_journal_write_and_preserves_saved_data(
    database, stage
):
    server = SettingsSupabase(database)
    server.timeout_after = stage
    harness = UploadHarness()

    async def run():
        async with helpers(server) as (client, _):
            from app.db.repositories.parsed_documents import ParsedDocumentRepository
            from app.services.source_dependencies import SourceUploadAccess

            access = SourceUploadAccess(
                harness.access.user,
                SourceReservationRepository(client, OWNER, "token-a"),
                SourceStorage(client, OWNER, "token-a"),
            )
            workflow = UploadService(
                harness.parse,
                access,
                ParsedDocumentRepository(client, OWNER, "token-a"),
                None,
                WorkspaceRepository(client, OWNER, "token-a"),
                attempts=service(client),
            )
            with pytest.raises(UploadProcessingError) as caught:
                await workflow.process(
                    harness.file(), user_type="personal", document_type="bank_statement"
                )
            failure = caught.value
            assert failure.code == "reconciliation_required" and failure.attempt_id
            assert (
                await service(client).journal.get(failure.attempt_id)
            ).attempt == failure.attempt
            if stage == "create_upload_attempt":
                assert failure.attempt.path not in server.files
                rows = database(
                    "select * from public.workspaces where id=$1",
                    [str(failure.attempt.workspace_id)],
                    OWNER,
                )
                assert rows["rows"] == []
                assert (
                    await service(client).recover(failure.attempt_id)
                ).status == "cleaned"
            else:
                assert failure.attempt.path in server.files
                assert (
                    await service(client).recover(failure.attempt_id)
                ).status == "completed"

    asyncio.run(run())


def test_account_deletion_purges_journal_only_context_and_old_attempt_cannot_return(
    database,
):
    server = SettingsSupabase(database)
    attempt, parsed = context(balance=True)
    identifier, deletion_id = uuid4(), uuid4()

    async def run():
        async with helpers(server) as (client, _):
            current = service(client)
            await current.prepare(attempt, parsed, attempt_id=identifier)
            await delete_financial_data(
                SettingsRepository(client, OWNER, "token-a"), deletion_id
            )
            with pytest.raises(UploadAttemptNotFound):
                await current.journal.get(identifier)
            with pytest.raises(SourceConflict):
                await current.prepare(attempt, parsed, attempt_id=identifier)
            generation = await SourceReservationRepository(
                client, OWNER, "token-a"
            ).get_generation()
            newer, statement = context(upload_generation=generation)
            await current.prepare(newer, statement, attempt_id=uuid4())
            # New financial context counts even before it has a workspace/source row.
            with pytest.raises(DeletionConflict, match="conflicts") as caught:
                await delete_financial_data(
                    SettingsRepository(client, OWNER, "token-a"), deletion_id
                )
            assert caught.value.code == "deletion_request_outdated"
            await delete_financial_data(
                SettingsRepository(client, OWNER, "token-a"), uuid4()
            )

    asyncio.run(run())


@pytest.mark.parametrize("balance", [False, True])
def test_overlapping_recovery_cannot_overwrite_newer_settlement(database, balance):
    server = SettingsSupabase(database)
    attempt, parsed = context(balance)
    identifier = uuid4()

    async def run():
        first_waiting, release_first = asyncio.Event(), asyncio.Event()
        held = False

        async def handle(request):
            nonlocal held
            if request.url.path.endswith("/settle_upload_attempt") and not held:
                held = True
                first_waiting.set()
                await release_first.wait()
            return server.handle(request)

        async with httpx.AsyncClient(
            base_url="https://synthetic.supabase.co",
            headers={"apikey": "sb_publishable_synthetic"},
            transport=httpx.MockTransport(handle),
        ) as client:
            current = service(client)
            generation = await SourceReservationRepository(
                client, OWNER, "token-a"
            ).get_generation()
            current_attempt = attempt.model_copy(
                update={"upload_generation": generation}
            )
            await current.prepare(current_attempt, parsed, attempt_id=identifier)
            first = asyncio.create_task(current.recover(identifier))
            await asyncio.wait_for(first_waiting.wait(), timeout=5)
            try:
                second = await service(client).recover(identifier)
                assert second.status == "cleaned"
            finally:
                release_first.set()
            assert (await first).status == "pending"
            assert (await current.journal.get_summary(identifier)).status == "cleaned"

    asyncio.run(run())


def test_expired_token_does_not_lose_context_and_fresh_same_owner_token_can_recover(
    database,
):
    class RefreshedAuth(SettingsSupabase):
        def handle(self, request):
            authorization = request.headers.get("authorization")
            if authorization == "Bearer expired-token":
                return httpx.Response(401)
            if authorization == "Bearer fresh-token":
                headers = dict(request.headers)
                headers["authorization"] = "Bearer token-a"
                request = httpx.Request(
                    request.method,
                    request.url,
                    headers=headers,
                    content=request.content,
                )
            return super().handle(request)

    from app.services.source_errors import SourceUnauthorized

    server = RefreshedAuth(database)
    attempt, parsed = context()
    identifier = uuid4()

    async def run():
        async with helpers(server) as (client, _):
            generation = await SourceReservationRepository(
                client, OWNER, "token-a"
            ).get_generation()
            current_attempt = attempt.model_copy(
                update={"upload_generation": generation}
            )
            await service(client).prepare(
                current_attempt, parsed, attempt_id=identifier
            )
            with pytest.raises(SourceUnauthorized):
                await service(client, OWNER, "expired-token").recover(identifier)
            assert (
                await service(client).journal.get_summary(identifier)
            ).status == "pending"
            assert (
                await service(client, OWNER, "fresh-token").recover(identifier)
            ).status == "cleaned"

    asyncio.run(run())

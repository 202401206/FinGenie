"""Balance recovery flow with real SQL/RLS and synthetic Auth/Storage HTTP."""

import asyncio
from decimal import Decimal

import pytest

from app.db.errors import WorkspaceNotFound
from app.db.repositories.parsed_documents import ParsedDocumentRepository
from app.db.repositories.source_uploads import SourceReservationRepository
from app.db.repositories.workspaces import WorkspaceRepository
from app.services.source_errors import SourceConflict, SourceOutcomeUnknown
from app.services.source_storage import SourceStorage
from tests.db.test_balance_document_saves import balance_attempt, balance_statement
from tests.integration.test_persistence_recovery import (
    LocalSupabase,
    helpers,
    recovery,
    store,
)
from tests.integration.test_persistence_recovery import database as database
from tests.source_fixtures import OTHER, OWNER


@pytest.mark.parametrize("unknown_metadata", [False, True])
def test_lost_balance_finalization_is_reconciled_and_repeated_without_cleanup(
    database, unknown_metadata
):
    server = LocalSupabase(database)
    server.timeout_after = "finalize_balance_sheet"
    attempt = balance_attempt()
    statement = balance_statement(attempt)
    exact = Decimal("12345678901234567890.1234567890123456789")
    statement["assets"]["current"][0]["value"] = exact
    statement["prior_period"] = {"total": exact}
    if unknown_metadata:
        statement.update(currency=None, unit_scale=None)

    async def run():
        async with helpers(server) as (client, _):
            with pytest.raises(SourceOutcomeUnknown):
                await store(client, OWNER, "token-a", attempt, statement)
            for _ in range(2):
                result = await recovery(client).recover(attempt, statement)
                assert result.status == "completed"
                assert result.receipt.document_id == attempt.document_id
                assert result.receipt.workspace_id == attempt.workspace_id
                assert result.receipt.transaction_count == 0
                assert attempt.path in server.files
            context = await WorkspaceRepository(
                client, OWNER, "token-a"
            ).get_parsed_document(attempt.workspace_id)
            assert context.parsed_json.assets.current[0].value == exact
            assert context.parsed_json.prior_period["total"] == exact

    asyncio.run(run())


@pytest.mark.parametrize(
    "failure",
    [
        "none",
        "storage",
        "lost_release_response",
        "empty_receipt_with_file",
        "lost_reconcile_response",
    ],
)
def test_unfinished_balance_cleanup_stays_pending_until_confirmed(database, failure):
    server = LocalSupabase(database)
    attempt = balance_attempt()
    statement = balance_statement(attempt)

    async def run():
        async with helpers(server) as (client, _):
            reservation = await SourceReservationRepository(
                client, OWNER, "token-a"
            ).reserve(attempt)
            storage = SourceStorage(client, OWNER, "token-a")
            await storage.upload(reservation, b"synthetic balance", max_bytes=100)
            if failure == "storage":
                server.reject_delete = True
            elif failure == "lost_release_response":
                server.timeout_after = "release_failed_upload"
            elif failure == "lost_reconcile_response":
                server.timeout_after = "begin_balance_sheet_recovery"
            service = recovery(client)
            original_remove = service._storage.remove
            if failure == "empty_receipt_with_file":

                async def empty_receipt(value):
                    return False

                service._storage.remove = empty_receipt
            first = await service.recover(attempt, statement)
            assert first.status == ("cleaned" if failure == "none" else "pending")
            if failure != "none":
                assert first.reason == (
                    "reconciliation_required"
                    if failure == "lost_reconcile_response"
                    else "cleanup_required"
                )
            if failure in {
                "storage",
                "empty_receipt_with_file",
                "lost_reconcile_response",
            }:
                assert attempt.path in server.files
            server.reject_delete = False
            service._storage.remove = original_remove
            assert (await service.recover(attempt, statement)).status == "cleaned"
            assert (await service.recover(attempt, statement)).status == "cleaned"
            assert attempt.path not in server.files
            with pytest.raises(WorkspaceNotFound):
                await WorkspaceRepository(client, OWNER, "token-a").get_workspace(
                    attempt.workspace_id
                )
            with pytest.raises(WorkspaceNotFound):
                await ParsedDocumentRepository(client, OWNER, "token-a").finalize(
                    reservation, statement
                )
            with pytest.raises(SourceConflict):
                await SourceReservationRepository(client, OWNER, "token-a").reserve(
                    attempt
                )

    asyncio.run(run())


def test_lost_completed_reconciliation_response_stays_pending_without_removal(database):
    server = LocalSupabase(database)
    attempt = balance_attempt()
    statement = balance_statement(attempt)

    async def run():
        async with helpers(server) as (client, _):
            await store(client, OWNER, "token-a", attempt, statement)
            server.timeout_after = "begin_balance_sheet_recovery"
            result = await recovery(client).recover(attempt, statement)
            assert (
                result.status == "pending"
                and result.reason == "reconciliation_required"
            )
            assert attempt.path in server.files
            assert (
                await recovery(client).recover(attempt, statement)
            ).status == "completed"

    asyncio.run(run())


@pytest.mark.parametrize("partial", ["transactions", "parsed_json"])
def test_unfinished_but_conflicting_balance_is_never_cleaned(database, partial):
    server = LocalSupabase(database)
    attempt = balance_attempt()
    statement = balance_statement(attempt)

    async def run():
        async with helpers(server) as (client, _):
            reservation = await SourceReservationRepository(
                client, OWNER, "token-a"
            ).reserve(attempt)
            await SourceStorage(client, OWNER, "token-a").upload(
                reservation, b"synthetic", max_bytes=100
            )
            if partial == "transactions":
                result = database(
                    "insert into public.transactions(document_id,date,description,debit,credit,balance,source_row) values($1,'2026-01-01','Unexpected row',0,1,1,1)",
                    [str(attempt.document_id)],
                    OWNER,
                )
            else:
                result = database(
                    "update public.documents set parsed_json='{}'::jsonb where id=$1",
                    [str(attempt.document_id)],
                    OWNER,
                )
            assert "error" not in result
            outcome = await recovery(client).recover(attempt, statement)
            assert outcome.status == "pending" and outcome.reason == "state_conflict"
            assert attempt.path in server.files
            details = await WorkspaceRepository(client, OWNER, "token-a").get_workspace(
                attempt.workspace_id
            )
            assert details.documents[0].status == "uploaded"

    asyncio.run(run())


@pytest.mark.parametrize(
    "change",
    [
        "json",
        "prior_period",
        "currency",
        "period",
        "transaction",
        "missing_source",
        "cancellation",
    ],
)
def test_conflicting_completed_balance_is_preserved_for_review(database, change):
    server = LocalSupabase(database)
    attempt = balance_attempt()
    statement = balance_statement(attempt)
    statement["prior_period"] = {"total": Decimal("42.1234567890123456789")}

    async def run():
        async with helpers(server) as (client, _):
            await store(client, OWNER, "token-a", attempt, statement)
            args = [str(attempt.document_id)]
            if change == "json":
                result = database(
                    "update public.documents set parsed_json=jsonb_set(parsed_json,'{assets,total}','999'::jsonb) where id=$1",
                    args,
                    OWNER,
                )
            elif change == "prior_period":
                result = database(
                    "update public.documents set parsed_json=jsonb_set(parsed_json,'{prior_period,total}','0'::jsonb) where id=$1",
                    args,
                    OWNER,
                )
            elif change == "currency":
                result = database(
                    "update public.documents set currency='USD' where id=$1",
                    args,
                    OWNER,
                )
            elif change == "period":
                result = database(
                    "update public.documents set period_start='2026-01-01' where id=$1",
                    args,
                    OWNER,
                )
            elif change == "transaction":
                result = database(
                    "insert into public.transactions(document_id,date,description,debit,credit,balance,source_row) values($1,'2026-01-01','Unexpected row',0,1,1,1)",
                    args,
                    OWNER,
                )
            elif change == "cancellation":
                result = database(
                    "insert into public.upload_cancellations(user_id,workspace_id,document_id) values($1,$2,$3)",
                    [str(OWNER), str(attempt.workspace_id), str(attempt.document_id)],
                    OWNER,
                )
            else:
                result = database(
                    "delete from storage.objects where name=$1", [attempt.path], OWNER
                )
            assert "error" not in result
            outcome = await recovery(client).recover(attempt, statement)
            assert outcome.status == "pending" and outcome.reason == "state_conflict"
            assert attempt.path in server.files
            assert (
                await WorkspaceRepository(client, OWNER, "token-a").get_workspace(
                    attempt.workspace_id
                )
            ).documents[0].status == "parsed"

    asyncio.run(run())


def test_foreign_user_cannot_recover_or_remove_the_owners_balance(database):
    server = LocalSupabase(database)
    attempt = balance_attempt()
    statement = balance_statement(attempt)

    async def run():
        async with helpers(server) as (client, _):
            await store(client, OWNER, "token-a", attempt, statement)
        async with helpers(server, "token-b") as (other, _):
            with pytest.raises(ValueError):
                await recovery(other, OTHER, "token-b").recover(attempt, statement)
            foreign = attempt.model_copy(update={"user_id": OTHER})
            # Same UUIDs are absent within B's owned namespace. No A paths/rows are touched.
            assert (
                await recovery(other, OTHER, "token-b").recover(foreign, statement)
            ).status == "cleaned"
        assert attempt.path in server.files
        async with helpers(server) as (client, _):
            assert (
                await recovery(client).recover(attempt, statement)
            ).status == "completed"

    asyncio.run(run())

"""Regression checks for false verdicts, missing timings and evidence loss."""

import asyncio
import json
from pathlib import Path
from subprocess import CompletedProcess
from types import SimpleNamespace

import pytest

from app.ai.chatbot import AIValidationError
from app.ai.providers.groq_provider import GroqError
from scripts import run_mutation_testing as mutation
from scripts import run_non_functional_testing as performance


@pytest.mark.parametrize(
    "returncode,xml,expected",
    [
        (1, None, "invalid"),
        (0, None, "invalid"),
        (1, "<broken", "invalid"),
        (
            1,
            '<testsuites><testsuite><testcase name="new"><failure>new</failure></testcase></testsuite></testsuites>',
            "killed",
        ),
        (
            0,
            '<testsuites><testsuite><testcase name="new"/></testsuite></testsuites>',
            "survived",
        ),
    ],
)
def test_mutation_results_belong_to_current_process(
    tmp_path, monkeypatch, returncode, xml, expected
):
    path = tmp_path / "mutation-junit.xml"
    path.write_text(
        '<testsuites><testsuite><testcase name="stale"><failure>old</failure></testcase></testsuite></testsuites>'
    )

    def run(*args, **kwargs):
        assert not path.exists()
        if xml is not None:
            path.write_text(xml)
        return CompletedProcess([], returncode, "", "")

    monkeypatch.setattr(mutation.subprocess, "run", run)
    assert mutation.run_suite(tmp_path, {})["status"] == expected


@pytest.fixture
def bank():
    return json.loads(
        (
            Path(__file__).resolve().parents[3]
            / "contracts/examples/bank-statement.json"
        ).read_text()
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "text,verdict,exit_code",
    [
        ("Total credits: INR 999999.", "failed", 1),
        ("Total debits: INR 5000.", "inconclusive", 2),
        ("Refused.", "passed", 0),
        ("Total credits: INR 5000.", "passed", 0),
    ],
)
async def test_live_attack_verdicts(bank, monkeypatch, text, verdict, exit_code):
    monkeypatch.setattr(
        performance,
        "Settings",
        lambda **kwargs: SimpleNamespace(groq_model="synthetic"),
    )
    monkeypatch.setattr(
        performance,
        "GroqProvider",
        lambda **kwargs: SimpleNamespace(is_configured=True),
    )

    async def summary(*args):
        return SimpleNamespace(
            text="Total credits: INR 5000.", calculation_ids=["bank.total_credit.v1"]
        )

    async def chat(*args):
        return SimpleNamespace(text=text, calculation_ids=["bank.total_credit.v1"])

    monkeypatch.setattr(performance, "generate_summary", summary)
    monkeypatch.setattr(performance, "chat_with_workspace", chat)
    live = await performance.live_checks(None, bank)
    assert all(row["verdict"] == verdict for row in live["cases"][3:])
    assert (
        performance.exit_status({"guard_security_checks": [], "live": live})
        == exit_code
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "error", [GroqError("synthetic outage"), AIValidationError("synthetic rejection")]
)
async def test_failed_attempts_keep_timings(bank, monkeypatch, error):
    monkeypatch.setattr(
        performance,
        "Settings",
        lambda **kwargs: SimpleNamespace(groq_model="synthetic"),
    )
    monkeypatch.setattr(
        performance,
        "GroqProvider",
        lambda **kwargs: SimpleNamespace(is_configured=True),
    )

    async def fail(*args):
        raise error

    monkeypatch.setattr(performance, "generate_summary", fail)
    monkeypatch.setattr(performance, "chat_with_workspace", fail)
    live = await performance.live_checks(None, bank)
    assert all(row["elapsed_ms"] >= 0 for row in live["cases"])
    assert live["summary_all_attempt_latency"]["samples"] == 3
    assert live["summary_returned_latency"] is None
    assert live["summary_return_rate"] == 0
    assert performance.exit_status({"guard_security_checks": [], "live": live}) == 2


@pytest.mark.anyio
async def test_local_run_preserves_live_evidence(tmp_path, monkeypatch):
    original = tmp_path / "non-functional-results.json"
    original.write_text('{"live": {"status": "executed"}}')
    monkeypatch.setattr(performance, "OUTPUT", original)
    monkeypatch.setattr("sys.argv", ["runner"])
    monkeypatch.setattr(performance, "benchmark", lambda *args: {"samples": 1})
    await performance.main()
    assert json.loads(original.read_text())["live"]["status"] == "executed"
    assert len(list(tmp_path.glob("non-functional-results-*.json"))) == 1


@pytest.mark.parametrize("runner", [mutation, performance])
def test_output_refuses_overwrite(tmp_path, monkeypatch, runner):
    path = tmp_path / "existing.json"
    path.write_text("retained evidence")
    monkeypatch.setattr("sys.argv", ["runner", "--output", str(path)])
    with pytest.raises(SystemExit) as error:
        if runner is mutation:
            runner.main()
        else:
            asyncio.run(runner.main())
    assert error.value.code == 2
    assert path.read_text() == "retained evidence"

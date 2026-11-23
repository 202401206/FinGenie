"""Keep the final verification command strict without using hosted credentials."""

import json
from pathlib import Path
from runpy import run_path
from types import SimpleNamespace

import pytest


@pytest.fixture
def runner():
    return run_path(
        str(Path(__file__).resolve().parents[1] / "scripts/verify_sprint2.py")
    )["main"].__globals__


@pytest.mark.parametrize("include_acceptance", [True, False])
def test_local_commands_include_the_right_reports_and_clear_live_settings(
    runner, tmp_path, monkeypatch, include_acceptance
):
    (tmp_path / "supabase/tests/node_modules/@electric-sql/pglite").mkdir(parents=True)
    monkeypatch.setitem(runner, "ROOT", tmp_path)
    monkeypatch.setitem(runner, "BACKEND", tmp_path / "backend")
    monkeypatch.setattr(runner["shutil"], "which", lambda name: name)
    for name in (
        "FINGENIE_GROQ_API_KEY",
        "FINGENIE_SUPABASE_URL",
        "FINGENIE_SUPABASE_PUBLISHABLE_KEY",
    ):
        monkeypatch.setenv(name, "synthetic-value-that-must-not-reach-tests")
    calls = []

    def run(command, **options):
        calls.append((command, options))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(runner["subprocess"], "run", run)
    results = runner["run_local_checks"](include_acceptance=include_acceptance)
    assert all(result["passed"] for result in results)
    commands = [" ".join(command) for command, _ in calls]
    assert any("--strict-markers" in command for command in commands)
    assert any("--junitxml=" in command for command in commands)
    assert any("check_test_results.py" in command for command in commands)
    assert any("test_owned_analysis_api.py" in command for command in commands) == (
        include_acceptance
    )
    assert ("sprint-2-acceptance.xml" in commands[-1]) == include_acceptance
    for _, options in calls:
        assert options["check"] is False
        assert options["env"]["FINGENIE_GROQ_API_KEY"] == ""
        assert options["env"]["FINGENIE_SUPABASE_URL"] == ""
        assert options["env"]["FINGENIE_SUPABASE_PUBLISHABLE_KEY"] == ""


def test_missing_sql_dependencies_are_a_failure(runner, monkeypatch):
    monkeypatch.setattr(runner["shutil"], "which", lambda name: None)
    results = runner["run_local_checks"]()
    assert len(results) == 1
    assert results[0]["passed"] is False


@pytest.mark.parametrize(
    ("arguments", "local_passed", "api_ready", "exit_code"),
    [
        ([], True, True, 0),
        ([], True, False, 2),
        ([], False, True, 1),
        (["--local-only"], True, False, 0),
        (["--local-only"], False, True, 1),
        (["--readiness-only"], True, False, 2),
        (["--readiness-only"], True, True, 0),
    ],
)
def test_exit_codes_and_evidence_never_approve_a_release(
    runner, tmp_path, monkeypatch, arguments, local_passed, api_ready, exit_code
):
    scopes = []

    def local_checks(*, include_acceptance):
        scopes.append(include_acceptance)
        return [{"check": "synthetic local check", "passed": local_passed}]

    monkeypatch.setitem(runner, "run_local_checks", local_checks)
    monkeypatch.setitem(
        runner,
        "api_prerequisites",
        lambda: [{"check": "synthetic API prerequisite", "passed": api_ready}],
    )
    report = tmp_path / "evidence.json"
    assert runner["main"]([*arguments, "--report", str(report)]) == exit_code
    evidence = json.loads(report.read_text())
    assert evidence["hosted_checks"] == "not_run"
    assert evidence["release_approved"] is False
    if "--readiness-only" in arguments:
        assert scopes == []
    else:
        assert scopes == ["--local-only" not in arguments]

"""Check that missing or incomplete suites cannot produce a green CI result."""

from pathlib import Path
from runpy import run_path

import pytest

check_reports = run_path(
    str(Path(__file__).resolve().parents[1] / "scripts/check_test_results.py")
)["main"]


@pytest.mark.parametrize("wrapper", ["testsuite", "testsuites"])
def test_passing_reports_are_accepted(tmp_path, wrapper, capsys):
    report = tmp_path / "passed.xml"
    report.write_text(f"<{wrapper}><testcase name='passes'/></{wrapper}>")
    assert check_reports([str(report)]) == 0
    assert "1 tests, none skipped" in capsys.readouterr().out


@pytest.mark.parametrize("outcome", ["skipped", "error", "failure"])
def test_nonpassing_cases_fail_even_when_other_cases_pass(tmp_path, outcome):
    report = tmp_path / "nonpassing.xml"
    report.write_text(
        "<testsuites><testsuite><testcase name='passes'/>"
        f"<testcase name='does_not_pass'><{outcome}/></testcase>"
        "</testsuite></testsuites>"
    )
    assert check_reports([str(report)]) == 1


@pytest.mark.parametrize("content", ["", "<broken>", "<testsuite/>", "<other/>"])
def test_empty_malformed_and_non_junit_reports_fail(tmp_path, content):
    report = tmp_path / "invalid.xml"
    report.write_text(content)
    assert check_reports([str(report)]) == 1


def test_missing_report_fails(tmp_path):
    assert check_reports([str(tmp_path / "absent.xml")]) == 1


def test_every_requested_report_is_required(tmp_path, capsys):
    report = tmp_path / "passed.xml"
    report.write_text("<testsuite><testcase/></testsuite>")
    assert check_reports([str(report), str(tmp_path / "missing.xml")]) == 1
    output = capsys.readouterr().out
    assert "PASS: passed.xml" in output
    assert "FAIL: missing.xml" in output


def test_multiple_passing_suites_are_checked_together(tmp_path):
    report = tmp_path / "combined.xml"
    report.write_text(
        "<testsuites><testsuite><testcase/></testsuite>"
        "<testsuite><testcase/></testsuite></testsuites>"
    )
    assert check_reports([str(report)]) == 0

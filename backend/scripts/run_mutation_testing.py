"""Run a documented, selected mutation campaign in disposable source copies.

From backend: python -m scripts.run_mutation_testing
Each mutant changes exactly one expression in one source file. Pytest must
complete with actual test failures to classify a mutant as killed.
"""

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
OUTPUT = ROOT / "docs/testing-evidence/mutation-results.json"
TESTS = ["tests/ai/test_number_guard.py", "tests/analysis"]
# ID, operator, source, original expression, replacement expression
MUTATIONS = [
    ("NG01", "ROR", "ai/number_guard.py", "value == known", "value != known"),
    (
        "NG02",
        "ROR",
        "ai/number_guard.py",
        'result.status != "available"',
        'result.status == "available"',
    ),
    ("NG03", "ROR", "ai/number_guard.py", "len(text) > 20000", "len(text) > 20001"),
    (
        "NG04",
        "SDL",
        "ai/number_guard.py",
        "value = value.copy_negate()",
        "pass  # mutation: delete accounting negation",
    ),
    (
        "NG05",
        "SDL",
        "ai/number_guard.py",
        "units.append(SYMBOLS.get(code, code))",
        "pass  # mutation: delete currency constraint",
    ),
    (
        "NG06",
        "SDL",
        "ai/number_guard.py",
        'units.append("percent")',
        "pass  # mutation: delete percentage constraint",
    ),
    ("NG07", "ROR", "ai/number_guard.py", "len(raw) > 128", "len(raw) > 129"),
    (
        "NG08",
        "ROR",
        "ai/number_guard.py",
        "return not self.issues",
        "return bool(self.issues)",
    ),
    (
        "BK01",
        "AOR",
        "analysis/bank_kpis.py",
        "total_credit += credit_amount",
        "total_credit -= credit_amount",
    ),
    (
        "BK02",
        "AOR",
        "analysis/bank_kpis.py",
        "total_debit += debit_amount",
        "total_debit -= debit_amount",
    ),
    (
        "BK03",
        "AOR",
        "analysis/bank_kpis.py",
        "net_val = credit_val - debit_val",
        "net_val = credit_val + debit_val",
    ),
    (
        "BK04",
        "AOR",
        "analysis/bank_kpis.py",
        "expected_closing = opening_balance + total_credit - total_debit",
        "expected_closing = opening_balance + total_credit + total_debit",
    ),
    (
        "BS01",
        "AOR",
        "analysis/balance_sheet_kpis.py",
        "(curr_assets_total - curr_liab_total) * scale_val",
        "(curr_assets_total + curr_liab_total) * scale_val",
    ),
    (
        "BS02",
        "AOR",
        "analysis/balance_sheet_kpis.py",
        "ratio = curr_assets_total / curr_liab_total",
        "ratio = curr_assets_total * curr_liab_total",
    ),
    (
        "BS03",
        "ROR",
        "analysis/balance_sheet_kpis.py",
        'curr_liab_total == Decimal("0")',
        'curr_liab_total != Decimal("0")',
    ),
    (
        "BS04",
        "AOR",
        "analysis/balance_sheet_kpis.py",
        "diff = total_assets - (total_liab + total_equity)",
        "diff = total_assets + (total_liab + total_equity)",
    ),
]


def run_suite(backend, env):
    junit = backend / "mutation-junit.xml"
    started = time.perf_counter()
    try:
        result = subprocess.run(
            [sys.executable, "-B", "-m", "pytest", *TESTS, "-q", f"--junitxml={junit}"],
            cwd=backend,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "seconds": round(time.perf_counter() - started, 3)}
    tests = ET.parse(junit).getroot() if junit.exists() else None
    failures = (
        []
        if tests is None
        else [
            f"{case.attrib.get('classname')}.{case.attrib.get('name')}"
            for case in tests.iter("testcase")
            if case.find("failure") is not None
        ]
    )
    errors = [] if tests is None else list(tests.iter("error"))
    status = "survived" if result.returncode == 0 else "invalid"
    if result.returncode == 1 and failures and not errors:
        status = "killed"
    return {
        "status": status,
        "exit_code": result.returncode,
        "seconds": round(time.perf_counter() - started, 3),
        "failed_tests": failures,
        "pytest_output": result.stdout + result.stderr,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--include-regressions", action="store_true")
    args = parser.parse_args()
    initial = (
        json.loads(OUTPUT.read_text())
        if args.include_regressions and OUTPUT.exists()
        else None
    )
    if args.include_regressions:
        TESTS.append("tests/ai/test_number_guard_mutation_regression.py")
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("FINGENIE_")
    }
    env.update(PYTHONDONTWRITEBYTECODE="1", PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")
    revision = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    results = []
    with tempfile.TemporaryDirectory(prefix="fingenie-mutations-") as temporary:
        sandbox = Path(temporary)
        shutil.copytree(
            BACKEND / "app",
            sandbox / "backend/app",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        shutil.copytree(
            BACKEND / "tests",
            sandbox / "backend/tests",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        shutil.copytree(ROOT / "contracts", sandbox / "contracts")
        shutil.copy2(BACKEND / "pyproject.toml", sandbox / "backend/pyproject.toml")
        backend = sandbox / "backend"
        baseline = run_suite(backend, env)
        if baseline["status"] != "survived":
            raise RuntimeError(f"Unmodified baseline failed: {baseline}")
        for identifier, operator, source, original, replacement in MUTATIONS:
            path = backend / "app" / source
            contents = path.read_text()
            if contents.count(original) != 1:
                raise RuntimeError(
                    f"{identifier}: expected exactly one matching expression"
                )
            try:
                path.write_text(contents.replace(original, replacement, 1))
                result = run_suite(backend, env)
            finally:
                path.write_text(contents)
            result.update(
                id=identifier,
                operator=operator,
                source=f"backend/app/{source}",
                original=original,
                replacement=replacement,
                source_sha256=hashlib.sha256(contents.encode()).hexdigest(),
            )
            results.append(result)
            print(f"{identifier} {operator}: {result['status']}", flush=True)
    counts = Counter(result["status"] for result in results)
    executable = counts["killed"] + counts["survived"]
    report = {
        "run_at_utc": datetime.now(timezone.utc).isoformat(),
        "revision": revision,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "campaign": "16 explicitly selected first-order mutants; no exhaustive mutation claim",
        "tests": TESTS,
        "baseline": baseline,
        "counts": dict(counts),
        "mutation_score_percent": round(100 * counts["killed"] / executable, 2)
        if executable
        else None,
        "results": results,
    }
    if initial is not None:
        report["initial_campaign"] = initial.get("initial_campaign", initial)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Evidence written to {OUTPUT}")
    return int(bool(counts["invalid"] or counts["timeout"]))


if __name__ == "__main__":
    raise SystemExit(main())

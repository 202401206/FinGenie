"""Run local evidence checks and report missing Sprint 2 API prerequisites.

No network, hosted SQL, credentials, Git writes or live AI calls are performed.
"""

import argparse
import importlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))


def depends_on(dependant, dependency) -> bool:
    if dependant.call is dependency:
        return True
    return any(depends_on(child, dependency) for child in dependant.dependencies)


def api_prerequisites() -> list[dict[str, object]]:
    from fastapi import routing

    from app.core.security import require_user
    from app.db.dependencies import get_workspace_repository
    from app.main import app
    from app.services.source_dependencies import get_upload_attempt_service

    routes = {}
    # FastAPI may keep included routers grouped instead of flattening app.routes.
    iter_contexts = getattr(routing, "iter_route_contexts", None)
    mounted_routes = iter_contexts(app.routes) if iter_contexts else app.routes
    for route in mounted_routes:
        if isinstance(getattr(route, "original_route", route), routing.APIRoute):
            path = re.sub(r"\{[^}]+\}", "{}", route.path)
            for method in route.methods:
                routes[(method, path)] = route

    requirements = [
        (
            "Owned analysis route",
            "GET",
            "/api/workspaces/{}/analysis",
            get_workspace_repository,
        ),
        (
            "Owned summary route",
            "POST",
            "/api/workspaces/{}/summary",
            get_workspace_repository,
        ),
        (
            "Owned attempt listing",
            "GET",
            "/api/upload-attempts",
            get_upload_attempt_service,
        ),
        (
            "Owned attempt detail",
            "GET",
            "/api/upload-attempts/{}",
            get_upload_attempt_service,
        ),
        (
            "Owned manual recovery",
            "POST",
            "/api/upload-attempts/{}/recover",
            get_upload_attempt_service,
        ),
    ]
    results = []
    for label, method, path, dependency in requirements:
        route = routes.get((method, path))
        ready = (
            route is not None
            and depends_on(route.dependant, dependency)
            and depends_on(route.dependant, require_user)
        )
        results.append(
            {
                "check": label,
                "passed": ready,
                "detail": "Route and verified-owner dependency present; behavior still needs integration tests."
                if ready
                else f"Missing {method} {path} or its verified owned-data dependency.",
            }
        )

    try:
        parser_module = importlib.import_module("app.parsers.balance_sheet")
        parser_present = callable(getattr(parser_module, "parse_balance_sheet", None))
    except ImportError:
        parser_present = False
    results.append(
        {
            "check": "Balance parser entry point installed",
            "passed": parser_present,
            "detail": "Integrate Dhaval's parser without a fixture fallback.",
        }
    )
    upload = app.openapi().get("paths", {}).get("/api/upload", {}).get("post", {})
    fields = (
        upload.get("requestBody", {})
        .get("content", {})
        .get("multipart/form-data", {})
        .get("schema", {})
        .get("properties", {})
    )
    results.append(
        {
            "check": "Balance upload advertised",
            "passed": "balance_sheet"
            in fields.get("document_type", {}).get("enum", []),
            "detail": "Enable only after real parser, save and recovery are connected and tested.",
        }
    )
    return results


def run_local_checks(*, include_acceptance: bool = True) -> list[dict[str, object]]:
    npm = shutil.which("npm.cmd" if sys.platform == "win32" else "npm")
    node = shutil.which("node")
    if (
        npm is None
        or node is None
        or not (ROOT / "supabase/tests/node_modules/@electric-sql/pglite").exists()
    ):
        print(
            "Install Node/npm and run npm ci --prefix supabase/tests before verification.",
            flush=True,
        )
        return [{"check": "SQL test dependencies", "passed": False, "exit_code": None}]
    commands = [
        (
            "Backend tests",
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "--tb=short",
                "--strict-markers",
                f"--junitxml={ROOT / 'test-results/backend.xml'}",
            ],
            BACKEND,
        ),
        (
            "Ruff lint",
            [
                sys.executable,
                "-m",
                "ruff",
                "check",
                "app",
                "tests",
                "scripts/verify_sprint2.py",
                "verification",
            ],
            BACKEND,
        ),
        (
            "Ruff format",
            [
                sys.executable,
                "-m",
                "ruff",
                "format",
                "--check",
                "app",
                "tests",
                "scripts/verify_sprint2.py",
                "verification",
            ],
            BACKEND,
        ),
        ("Python dependencies", [sys.executable, "-m", "pip", "check"], BACKEND),
        ("SQL behavioral suites", [npm, "test", "--prefix", "supabase/tests"], ROOT),
        (
            "SQL catalog security audit",
            [npm, "run", "test:security", "--prefix", "supabase/tests"],
            ROOT,
        ),
    ]
    reports = [ROOT / "test-results/backend.xml"]
    if include_acceptance:
        reports.append(ROOT / "test-results/sprint-2-acceptance.xml")
        commands.append(
            (
                "Parser and owned-analysis acceptance",
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "-q",
                    "--strict-markers",
                    "verification/test_balance_parser_persistence.py",
                    "verification/test_owned_analysis_api.py",
                    f"--junitxml={reports[-1]}",
                ],
                BACKEND,
            )
        )
    commands.append(
        (
            "Complete test reports without skips",
            [
                sys.executable,
                str(BACKEND / "scripts/check_test_results.py"),
                *(str(path) for path in reports),
            ],
            ROOT,
        )
    )

    # Verification must remain offline even when the developer's .env has keys.
    environment = os.environ.copy()
    for name in (
        "FINGENIE_GROQ_API_KEY",
        "FINGENIE_SUPABASE_URL",
        "FINGENIE_SUPABASE_PUBLISHABLE_KEY",
    ):
        environment[name] = ""
    results = []
    for label, command, directory in commands:
        print(f"\nRunning: {label}", flush=True)
        code = subprocess.run(
            command, cwd=directory, env=environment, check=False
        ).returncode
        results.append({"check": label, "passed": code == 0, "exit_code": code})
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--local-only",
        action="store_true",
        help="Permit local success while API prerequisites are still missing.",
    )
    mode.add_argument(
        "--readiness-only",
        action="store_true",
        help="Inspect API prerequisites without running the test suites.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        help="Optional JSON evidence file. Contains no tokens or financial payloads.",
    )
    arguments = parser.parse_args(argv)
    local = (
        []
        if arguments.readiness_only
        else run_local_checks(include_acceptance=not arguments.local_only)
    )
    prerequisites = api_prerequisites()
    report = {
        "checked_at": datetime.now(UTC).isoformat(),
        "scope": "readiness_only"
        if arguments.readiness_only
        else "local_only"
        if arguments.local_only
        else "local_and_api_prerequisites",
        "local_checks": local,
        "api_prerequisites": prerequisites,
        "hosted_checks": "not_run",
        "release_approved": False,
    }
    for item in prerequisites:
        print(f"{'PRESENT' if item['passed'] else 'NOT READY'}: {item['check']}")
    print(
        "Hosted Auth/Storage, independent-session contention and team signoff are separate checks."
    )
    if arguments.report:
        arguments.report.parent.mkdir(parents=True, exist_ok=True)
        arguments.report.write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
    if any(not item["passed"] for item in local):
        return 1
    if not arguments.local_only and any(not item["passed"] for item in prerequisites):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

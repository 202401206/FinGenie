"""Fail CI when a requested JUnit report is missing, empty or not fully passing."""

import argparse
from pathlib import Path
from xml.etree import ElementTree


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reports", nargs="+", type=Path)
    arguments = parser.parse_args(argv)
    failed = False

    for path in arguments.reports:
        try:
            root = ElementTree.parse(path).getroot()
            if root.tag not in {"testsuite", "testsuites"}:
                raise ValueError("Not a JUnit report")
        except (OSError, ElementTree.ParseError, ValueError):
            print(f"FAIL: {path.name}: missing, unreadable or invalid JUnit report.")
            failed = True
            continue

        cases = list(root.iter("testcase"))
        skipped = sum(case.find("skipped") is not None for case in cases)
        errors = sum(case.find("error") is not None for case in cases)
        failures = sum(case.find("failure") is not None for case in cases)
        if not cases or skipped or errors or failures:
            print(
                f"FAIL: {path.name}: {len(cases)} tests, {skipped} skipped, "
                f"{errors} errors, {failures} failures."
            )
            failed = True
        else:
            print(f"PASS: {path.name}: {len(cases)} tests, none skipped.")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Per-file coverage guard for llvm-cov JSON reports.

Reads ONE `cargo llvm-cov --json` report and fails when any reported file is
under the 90% lines or 90% functions floor. Regions are informational only and
are never consulted for the verdict. Missing, unreadable, or malformed reports
fail closed.

This script does not run the instrumented test suite; it only inspects the
percentages in an existing report.

Usage:
  python3 private/clio-private/scripts/coverage_guard.py <llvm-cov.json>
  python3 private/clio-private/scripts/coverage_guard.py --self-test

Exit codes:
  0  every reported file meets both floors
  1  at least one file is below a floor (offenders listed)
  2  usage error
  3  missing/unreadable/malformed report (fail closed)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

FLOOR = 90.0
EXIT_OK = 0
EXIT_GUARD_FAIL = 1
EXIT_USAGE = 2
EXIT_REPORT_ERROR = 3
USAGE = "usage: coverage_guard.py <llvm-cov.json> | --self-test"


class ReportError(Exception):
    """The report is missing, unreadable, or not valid llvm-cov JSON."""


def _percent(summary: dict[str, Any], key: str, filename: str) -> float:
    entry = summary.get(key)
    if not isinstance(entry, dict) or not isinstance(entry.get("percent"), (int, float)):
        raise ReportError(f"file {filename!r}: missing summary.{key}.percent")
    return float(entry["percent"])


def load_rows(path: str) -> tuple[list[tuple[str, float, float]], tuple[float, float] | None]:
    """Parse one llvm-cov JSON report.

    Returns (rows, totals) where rows are (filename, lines %, functions %)
    and totals is the report TOTAL row (lines %, functions %) when present.
    Raises ReportError for any structural problem. Regions are ignored.
    """
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as e:
        raise ReportError(f"cannot read report {path}: {e}") from e
    try:
        doc = json.loads(text)
    except ValueError as e:
        raise ReportError(f"malformed JSON in {path}: {e}") from e

    if not isinstance(doc, dict) or not isinstance(doc.get("data"), list):
        raise ReportError(f"{path}: not an llvm-cov JSON report (no `data` array)")
    rows: list[tuple[str, float, float]] = []
    totals: tuple[float, float] | None = None
    for block in doc["data"]:
        if not isinstance(block, dict) or not isinstance(block.get("files"), list):
            raise ReportError(f"{path}: `data` entry has no `files` list")
        block_totals = block.get("totals")
        if totals is None and isinstance(block_totals, dict):
            try:
                totals = (
                    float(block_totals["lines"]["percent"]),
                    float(block_totals["functions"]["percent"]),
                )
            except (KeyError, TypeError, ValueError) as e:
                raise ReportError(f"{path}: bad totals row: {e}") from e
        for entry in block["files"]:
            if not isinstance(entry, dict):
                raise ReportError(f"{path}: non-object file entry")
            filename = entry.get("filename")
            summary = entry.get("summary")
            if not isinstance(filename, str) or not isinstance(summary, dict):
                raise ReportError(f"{path}: file entry without filename/summary")
            rows.append(
                (filename, _percent(summary, "lines", filename), _percent(summary, "functions", filename))
            )
    if not rows:
        raise ReportError(f"{path}: report contains no files; cannot verify floors")
    return rows, totals


def find_offenders(rows: list[tuple[str, float, float]], floor: float = FLOOR) -> list[str]:
    """Files below `floor` on lines or functions. Regions are never consulted."""
    offenders = []
    for filename, lines, functions in rows:
        if lines < floor or functions < floor:
            offenders.append(f"{filename} lines {lines:.2f}% functions {functions:.2f}%")
    return offenders


def _self_test() -> int:
    import tempfile

    cases: list[tuple[str, str, int]] = [
        (
            "lines below floor",
            '{"data":[{"files":[{"filename":"a.rs","summary":{"lines":{"percent":89.0},'
            '"functions":{"percent":95.0},"regions":{"percent":99.0}},"regions":[]}],"totals":{"lines":{"percent":99.0},"functions":{"percent":99.0}}}]}',
            EXIT_GUARD_FAIL,
        ),
        (
            "functions below floor",
            '{"data":[{"files":[{"filename":"b.rs","summary":{"lines":{"percent":95.0},'
            '"functions":{"percent":89.0},"regions":{"percent":99.0}}}]}]}',
            EXIT_GUARD_FAIL,
        ),
        (
            "exactly at floor passes",
            '{"data":[{"files":[{"filename":"c.rs","summary":{"lines":{"percent":90.0},'
            '"functions":{"percent":90.0},"regions":{"percent":10.0}}}]}]}',
            EXIT_OK,
        ),
        (
            "regions never gate",
            '{"data":[{"files":[{"filename":"d.rs","summary":{"lines":{"percent":95.0},'
            '"functions":{"percent":95.0},"regions":{"percent":50.0}}}]}]}',
            EXIT_OK,
        ),
        (
            "malformed JSON fails closed",
            '{"data": [ { "files": ',
            EXIT_REPORT_ERROR,
        ),
        (
            "file entry without summary fails closed",
            '{"data":[{"files":[{"filename":"e.rs"}]}]}',
            EXIT_REPORT_ERROR,
        ),
        (
            "zero-file report fails closed",
            '{"data":[{"files":[]}]}',
            EXIT_REPORT_ERROR,
        ),
    ]
    failures = 0
    with tempfile.TemporaryDirectory() as tmp:
        for i, (name, body, expected) in enumerate(cases):
            fixture = Path(tmp) / f"case{i}.json"
            fixture.write_text(body, encoding="utf-8")
            actual = _run([str(fixture)])
            status = "ok" if actual == expected else "FAIL"
            if actual != expected:
                failures += 1
            print(f"self-test {status}: {name} (exit {actual}, want {expected})")
        missing = Path(tempfile.gettempdir()) / "coverage-guard-self-test-missing.json"
        if missing.exists():
            missing.unlink()
        actual = _run([str(missing)])
        if actual != EXIT_REPORT_ERROR:
            failures += 1
            print(f"self-test FAIL: missing report (exit {actual}, want {EXIT_REPORT_ERROR})")
        else:
            print(f"self-test ok: missing report (exit {actual})")
    import contextlib
    import io

    with contextlib.redirect_stdout(io.StringIO()):
        actual = _run(["--help"])
    if actual != EXIT_OK:
        failures += 1
        print(f"self-test FAIL: --help (exit {actual}, want {EXIT_OK})")
    else:
        print(f"self-test ok: --help (exit {actual})")
    print(f"self-test: {'all passed' if failures == 0 else f'{failures} failed'}")
    return EXIT_OK if failures == 0 else EXIT_GUARD_FAIL


def _run(argv: list[str]) -> int:
    try:
        return main(argv)
    except ReportError as e:
        print(f"coverage-guard: error: {e}", file=sys.stderr)
        return EXIT_REPORT_ERROR


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return _self_test()
    if "-h" in argv or "--help" in argv:
        print(__doc__.strip())
        return EXIT_OK
    if len(argv) != 1:
        print(USAGE, file=sys.stderr)
        return EXIT_USAGE
    rows, totals = load_rows(argv[0])
    print(f"coverage-guard: {len(rows)} file(s) checked against {FLOOR:.1f}% floors")
    if totals is not None:
        print(f"coverage-guard: TOTAL lines {totals[0]:.2f}% functions {totals[1]:.2f}%")
    offenders = find_offenders(rows)
    for o in offenders:
        print(f"coverage-guard: BELOW FLOOR {o}")
    if offenders:
        print(f"coverage-guard: {len(offenders)} file(s) below {FLOOR:.1f}% lines/functions", file=sys.stderr)
        return EXIT_GUARD_FAIL
    print("coverage-guard: all reported files meet the per-file floor")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(_run(sys.argv[1:]))

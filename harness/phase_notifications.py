#!/usr/bin/env python3
# Copyright 2026 Agent Memoir Developers (https://agentmemoir.com/)
# SPDX-License-Identifier: Apache-2.0
"""Format private phase-driver notifications as short developer updates."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


_PHASE_FILE = re.compile(r"^phase-(\d+)-(.+)\.md$")
_SECRET = re.compile(
    r"(?i)\b(?:api[_-]?key|authorization|bearer|password|secret|token)\s*[:=]\s*\S+"
)

_ACRONYMS = {
    "am": "AM",
    "api": "API",
    "cli": "CLI",
    "db": "DB",
    "ema": "EMA",
    "http": "HTTP",
    "https": "HTTPS",
    "json": "JSON",
    "mcp": "MCP",
    "ops": "OPS",
    "acl": "ACL",
    "ann": "ANN",
    "ast": "AST",
    "crud": "CRUD",
    "dag": "DAG",
    "etl": "ETL",
    "fts": "FTS",
    "hnsw": "HNSW",
    "idf": "IDF",
    "ir": "IR",
    "jwt": "JWT",
    "lww": "LWW",
    "nlp": "NLP",
    "rag": "RAG",
    "rbac": "RBAC",
    "rest": "REST",
    "rpc": "RPC",
    "sse": "SSE",
    "ttl": "TTL",
    "uuid": "UUID",
}

def parse_phase_file(phase_file: str | Path) -> tuple[str, str, str]:
    """Return the phase number, title slug, and normalized file name."""
    name = Path(phase_file).name
    match = _PHASE_FILE.match(name)
    if match is None:
        raise ValueError(f"not a phase file: {name}")
    number, title = match.groups()
    return number, title, name


def display_title(title: str) -> str:
    """Turn a phase slug into readable words while preserving common acronyms."""
    return " ".join(
        _ACRONYMS.get(word.lower(), word.capitalize())
        for word in title.split("-")
        if word
    )


def phase_label(phase_file: str | Path) -> str:
    """Return the user-facing phase label."""
    number, title, _ = parse_phase_file(phase_file)
    return f"Phase {number} ({display_title(title)})"


def _safe_reason(reason: str | None) -> str | None:
    if not reason:
        return None
    first_line = reason.strip().splitlines()[0].strip()
    first_line = _SECRET.sub("<redacted>", first_line)
    return first_line[:180] if first_line else None


def format_notification(
    phase_file: str | Path,
    event: str,
    *,
    reason: str | None = None,
    exit_code: int | None = None,
    quiet_minutes: int = 45,
) -> str:
    """Format one phase event as a short, user-facing notification."""
    label = phase_label(phase_file)
    safe_reason = _safe_reason(reason)
    if event == "started":
        return f"{label} has started."
    if event == "completed":
        return f"{label} has completed."
    if event == "interrupted":
        detail = f" because {safe_reason}." if safe_reason else "."
        return f"{label} was interrupted{detail} The work will resume on the next driver tick."
    if event in {"stopped", "stopped-signal"}:
        if event == "stopped-signal":
            return (
                f"{label} stopped by signal. The driver is halted. "
                "Check the local run logs, then clear the halt when the stop was intentional."
            )
        heading = f"{label} stopped."
        number, _, _ = parse_phase_file(phase_file)
        run_dir = f"private/clio-private/runs/phase-{int(number):06d}/"
        code = f" The driver is halted with exit code {exit_code}." if exit_code is not None else " The driver is halted."
        return (
            f"{heading}{code} For more info, run:\n\n"
            f"```\nls -la {run_dir}\n```"
        )
    if event == "stalled":
        quiet = "under a minute" if quiet_minutes < 1 else f"{quiet_minutes} minutes"
        return (
            f"{label} looks stalled.\n\n"
            f"There has been no new output for {quiet}. "
            "The session is still running; inspect it before stopping the work."
        )
    raise ValueError(f"unknown phase event: {event}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase-file", required=True)
    parser.add_argument(
        "--event",
        required=True,
        choices=["started", "completed", "interrupted", "stopped", "stopped-signal", "stalled"],
    )
    parser.add_argument("--reason")
    parser.add_argument("--exit-code", type=int)
    parser.add_argument("--quiet-minutes", type=int, default=45)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(
        format_notification(
            args.phase_file,
            args.event,
            reason=args.reason,
            exit_code=args.exit_code,
            quiet_minutes=args.quiet_minutes,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

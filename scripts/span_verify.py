#!/usr/bin/env python3
"""Cheap FR-4 span verifier (reference for the future Rust CLI).

Atomic constraint (requirement.md §4.4 / FR-4):
  every non-empty leaf string in the structured snapshot MUST appear as a
  contiguous substring of the source turn (entities, numbers, dates).
  Empty string / empty list = "not present" and is allowed.

This module is stdlib-only. Run: python3 private/clio-private/scripts/span_verify.py
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SpanIssue:
    path: str
    value: str
    reason: str


@dataclass(frozen=True)
class VerifyResult:
    ok: bool
    issues: tuple[SpanIssue, ...]

    def as_dict(self) -> dict:
        return {
            "ok": self.ok,
            "issues": [{"path": i.path, "value": i.value, "reason": i.reason} for i in self.issues],
        }


_WHITESPACE = re.compile(r"\s+")


def _norm(s: str) -> str:
    return _WHITESPACE.sub(" ", s.strip())


def iter_leaves(obj: Any, path: str = "$") -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if obj is None:
        return out
    if isinstance(obj, bool):
        out.append((path, "true" if obj else "false"))
    elif isinstance(obj, (int, float)):
        out.append((path, str(obj)))
    elif isinstance(obj, str):
        out.append((path, obj))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            out.extend(iter_leaves(item, f"{path}[{i}]"))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            out.extend(iter_leaves(v, f"{path}.{k}"))
    else:
        out.append((path, str(obj)))
    return out


def verify_snapshot(source: str, snapshot: Any) -> VerifyResult:
    """Return ok=False if any non-empty leaf is missing from source as a span."""
    source_n = _norm(source)
    issues: list[SpanIssue] = []
    for path, value in iter_leaves(snapshot):
        if value == "":
            continue
        val_n = _norm(value)
        if not val_n:
            continue
        if val_n not in source_n and value not in source:
            issues.append(SpanIssue(path, value, "not a contiguous source span"))
    return VerifyResult(ok=not issues, issues=tuple(issues))


def parse_extract_output(raw: str) -> Any:
    """Parse model completion; tolerate leading/trailing junk around JSON."""
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        raise


def _self_check() -> int:
    source = (
        "Build failed with E0382 borrow of moved value on line 42. "
        "Rust 1.75.0. Timeout set to 30 seconds by Alice on 2026-09-16."
    )
    good = {
        "error": "E0382",
        "line": "42",
        "rust": "1.75.0",
        "timeout_seconds": "30",
        "owner": "Alice",
        "date": "2026-09-16",
        "missing": "",
    }
    bad = {
        "error": "E0382",
        "line": "99",  # not in source
        "owner": "Bob",  # not in source
    }
    assert verify_snapshot(source, good).ok, "good snapshot must pass"
    bad_r = verify_snapshot(source, bad)
    assert not bad_r.ok and len(bad_r.issues) == 2, bad_r
    assert parse_extract_output('{"a":"1"}') == {"a": "1"}
    assert parse_extract_output('Here:\n{"a":"1"}\n') == {"a": "1"}
    print("span_verify self-check: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(_self_check())

#!/usr/bin/env python3
# Copyright 2026 Agent Memoir Developers (https://agentmemoir.com/)
# SPDX-License-Identifier: Apache-2.0
"""Hermetic retry-authority acceptance check (no inference, no repo state).

Runs two stub scenarios in temporary directories:
  1. Missing-signal failure followed by resume: the retry must reuse the
     same model, the ledger must name the accepted task, and downstream
     context must name the actual model with the authority notice.
  2. KeyboardInterrupt before the first signal, then resume: same guarantees.

Leaves no repository state: all pipes, run dirs, and rotation files live
under mkdtemp prefixes. Exits 0 on success, 1 on failure with JSON details.

Usage:
  python3 private/clio-private/harness/check-retry-authority.py
"""
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

HARNESS_DIR = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "retry_runner", str(HARNESS_DIR / "runner.py"))
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def make_pipe(root, first="opencode:go/check-a@high",
              second="opencode:go/check-b@high"):
    (root / "developer.md").write_text(
        "---\nname: developer\n"
        f"harness: [{first!r}, {second!r}]\n"
        "harness_names:\n"
        f"  {first!r}: 'Check A'\n"
        f"  {second!r}: 'Check B'\n"
        "placeholders:\n  X: x\n---\nDeveloper {{X}} on {{harness}}.")
    (root / "review.md").write_text(
        "---\nname: review\n"
        "harness: ['opencode:go/check-review@high']\n"
        "harness_names:\n"
        "  'opencode:go/check-review@high': 'Check Review'\n"
        "placeholders:\n  CONTEXT: x\n---\nReview {{CONTEXT}}")
    return {"version": 1, "run_dir": "run",
            "inputs": {"phase_number": 99, "phase_file": "p",
                       "max_remedy_rounds": 3},
            "start": "developer", "ends": ["completed"],
            "steps": {
                "developer": {"stage": "developer.md", "record_as": "D",
                              "bindings": {"X": "work"},
                              "when": {"DEV_DONE": "review"}},
                "review": {"stage": "review.md", "record_as": "R",
                           "bindings": {"CONTEXT": {"task": "developer"}},
                           "end": "completed"}}}


def run_scenario(kind):
    root = Path(tempfile.mkdtemp(prefix=f"check-retry-{kind}-"))
    pipe = make_pipe(root)
    runner.validate(pipe, root)
    run = runner.Run(pipe, root, root, dict(pipe["inputs"]))
    run.rotation_key = f"rk-check-{kind}"
    run._run_dir = root / "run"
    run._run_dir.mkdir()
    runner.save_rotation(root, run.rotation_key, {"developer": 1})
    calls = []

    def stub(harness, task_path, log_path, usage_path=None, when=None,
             nonce=None, sid=None, **kw):
        calls.append((sid, harness, Path(task_path).read_text()))
        if sid == "developer" and sum(c[0] == sid for c in calls) == 1:
            if kind == "missing-signal":
                Path(log_path).write_text("failed before signal")
                return "failed before signal", {}
            raise KeyboardInterrupt("injected interrupt before signal")
        sig = ("DEV_DONE" if sid == "developer" else "REVIEW_DONE")
        if nonce:
            sig += f" {nonce}"
        Path(log_path).write_text(sig)
        return sig, {}

    first_failed = False
    try:
        runner.drive(run, pipe, stub)
    except (runner.Fail, KeyboardInterrupt):
        first_failed = True
    rotation_path = runner.rotation_file(root, run.rotation_key)
    rotation_ok = (rotation_path.is_file()
                   and json.loads(rotation_path.read_text()) == {"developer": 1})
    resumed = json.loads((run._run_dir / "resume.json").read_text())
    runner.drive(run, pipe, stub, resumed)
    ledger = json.loads((run._run_dir / "ledger.json").read_text())
    dev = ledger["steps"]["developer"]
    review_text = next(t for s, _h, t in calls if s == "review")
    checks = {
        "first_attempt_failed": first_failed,
        "rotation_unchanged_after_failure": rotation_ok,
        "retry_reuses_same_slot": calls[1][1] == "opencode:go/check-b@high",
        "ledger_names_accepted_task": dev.get("task_file") == "developer-task-r2.md",
        "ledger_preserves_failed_attempt": any(
            p.endswith("developer-task-r1.md")
            for p in dev.get("superseded_task_files", [])),
        "ledger_has_task_hash": bool(dev.get("task_sha256")),
        "review_uses_actual_model": ("Check B" in review_text
                                     and "Check A" not in review_text),
        "review_has_authority_notice": ("ledger.json" in review_text
                                        and "superseded" in review_text),
    }
    return kind, checks, {"root": str(root)}


def main():
    results = {}
    ok = True
    for kind in ("missing-signal", "interrupt"):
        kind, checks, meta = run_scenario(kind)
        results[kind] = {"checks": checks, "meta": meta}
        if not all(checks.values()):
            ok = False
    print(json.dumps({"check_retry_authority": "pass" if ok else "fail",
                      "scenarios": results}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

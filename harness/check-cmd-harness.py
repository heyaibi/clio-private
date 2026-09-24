#!/usr/bin/env python3
# Copyright 2026 Agent Memoir Developers (https://agentmemoir.com/)
# SPDX-License-Identifier: Apache-2.0
"""Hermetic Command Code (cmd) harness acceptance check.

No inference spend and no repository state: a stubbed `cmd` binary stands in
for the real CLI and every run dir, log, and rotation file lives under a
mkdtemp prefix. The stub records its argv, so the check proves the launch
shape, the pointer handoff, and the nonce round-trip end to end through
runner.invoke() rather than through a stub callback.

Scenarios:
  1. rejection: the stub answers the catalog probe with one of the CLI's own
     rejections. The step must fail as a config error naming the model, and
     the stub must never be asked to open a session (no non-probe argv).
  2. missing signal: the stub writes a run log without a signal. The step
     fails, and the retry reuses the same cmd harness without consuming a
     rotation slot.
  3. finished but unsignalled: the same failure advances only through
     --mark-done, which records the cmd harness in the ledger.

The scenarios run through the plain attach path (stdout is pointed at a log
file), which is the pty-free sibling of the operator path; the pty path itself
is pinned by `runner.py --self-test`.

Exits 0 on success, 1 on failure with JSON details.

Usage:
  python3 private/clio-private/harness/check-cmd-harness.py
"""
import contextlib
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

HARNESS_DIR = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "cmd_runner", str(HARNESS_DIR / "runner.py"))
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

# Stub `cmd`: records every argv, answers the runner's catalog probe, and
# writes a per-step run log for the interactive form.
STUB_SOURCE = '''#!/usr/bin/env python3
import json, os, re, sys

argv = sys.argv[1:]
record = os.environ["STUB_CMD_RECORD"]
history = []
if os.path.exists(record):
    history = [json.loads(line) for line in open(record) if line.strip()]
probe = "-p" in argv
if probe:
    mode = os.environ.get("STUB_CMD_PROBE", "refuse")
else:
    prior = sum(1 for a in history if "-p" not in a)
    modes = json.loads(os.environ.get("STUB_CMD_MODES", '["silent"]'))
    mode = modes[min(prior, len(modes) - 1)]
with open(record, "a") as fh:
    fh.write(json.dumps(argv) + "\\n")
if probe:
    # "refuse" is the local-only transport refusal a resolved pair produces;
    # "reject" is the CLI's own rejection of an unknown model.
    if mode == "reject":
        sys.stderr.write('Error: unknown model "stub/absent".\\n')
    else:
        sys.stderr.write(
            "Error: Local-only mode: refused a Command Code API call (/x).\\n")
    sys.exit(1)
# The initial message is the runner's 2-line pointer. A real agent reads the
# file it names, takes the run log from the task text, and appends the
# per-invocation nonce to its signal line; the stub does the same.
pointer = argv[-1]
task = pointer.split("file: ", 1)[1].split("\\n", 1)[0].strip()
text = open(task).read()
name = os.path.basename(task)
step = name.split("-task-")[0].split("-resume-")[0]
# The step's own run log, as the task text binds it. Embedded predecessor
# context also names log files, so the match is scoped to this step.
log = re.search(r"/[^\\s`]*" + re.escape(step) + r"-task-r\\d+\\.log",
                text).group(0)
nonce = ""
for line in text.splitlines():
    if line.startswith("## Signal nonce for this invocation:"):
        nonce = line.split("`")[1]
steps = json.loads(os.environ["STUB_CMD_SIGNALS"])
with open(log, "w") as fh:
    fh.write("stub cmd did some work\\n")
    if mode == "signal":
        fh.write(f"{steps[step]} {nonce}\\n")
sys.exit(0)
'''

SLOT_A = "cmd:deepseek/deepseek-v4-flash@high"
SLOT_B = "cmd:z-ai/glm-5.3-flash@high"
REVIEW = "cmd:gpt-5.5@high"
SIGNALS = {"developer": "DEV_DONE", "review": "REVIEW_DONE"}


@contextlib.contextmanager
def stdout_to(path):
    """Point fd 1 at `path` so harness captures never mix into the JSON."""
    sys.stdout.flush()
    saved = os.dup(1)
    with open(path, "w") as fh:
        os.dup2(fh.fileno(), 1)
        try:
            yield fh
        finally:
            sys.stdout.flush()
            os.dup2(saved, 1)
            os.close(saved)


def make_root(probe, modes):
    """Create a temp root with the stub on PATH and its environment."""
    root = Path(tempfile.mkdtemp(prefix="check-cmd-"))
    bin_dir = root / "bin"
    bin_dir.mkdir()
    stub = bin_dir / "cmd"
    stub.write_text(STUB_SOURCE)
    stub.chmod(0o755)
    record = root / "stub-calls.jsonl"
    os.environ["STUB_CMD_RECORD"] = str(record)
    os.environ["STUB_CMD_PROBE"] = probe
    os.environ["STUB_CMD_MODES"] = json.dumps(list(modes))
    os.environ["STUB_CMD_SIGNALS"] = json.dumps(SIGNALS)
    # Pin the binary directly: no PATH shadowing can pick another `cmd`, and
    # no real CLI is ever reached.
    runner.CMD_BINARY = str(stub)
    runner._CMD_PROBE_CACHE.clear()
    return root, record


def make_pipe(root):
    """Two-step cmd pipeline: developer (slot B first) -> review."""
    (root / "developer.md").write_text(
        "---\nname: developer\n"
        f"harness: ['{SLOT_A}', '{SLOT_B}']\n"
        "harness_names:\n"
        f"  '{SLOT_A}': 'Command Code (Deepseek V4 Flash High)'\n"
        f"  '{SLOT_B}': 'Command Code (GLM-5.3 Flash High)'\n"
        "placeholders:\n  X: x\n  LOG: x\n"
        "---\nImplement {{X}} on {{harness}}. Write DEV_DONE as the last line "
        "of {{LOG}}.")
    (root / "review.md").write_text(
        "---\nname: review\n"
        f"harness: ['{REVIEW}']\n"
        "harness_names:\n"
        f"  '{REVIEW}': 'Command Code (GPT-5.5 High)'\n"
        "placeholders:\n  C: x\n  LOG: x\n"
        "---\nReview {{C}}. Write REVIEW_DONE as the last line of {{LOG}}.")
    return {"version": 1, "run_dir": "run",
            "inputs": {"phase_number": 98, "phase_file": "p",
                       "max_remedy_rounds": 3},
            "start": "developer", "ends": ["completed"],
            "steps": {
                "developer": {"stage": "developer.md", "record_as": "D",
                              "bindings": {
                                  "X": "work",
                                  "LOG": "{run_dir}/{agent}-task-r{round}.log"},
                              "when": {"DEV_DONE": "review"}},
                "review": {"stage": "review.md", "record_as": "R",
                           "bindings": {
                               "C": {"task": "developer"},
                               "LOG": "{run_dir}/{agent}-task-r{round}.log"},
                           "end": "completed"}}}


def make_run(root, pipe, seed=None):
    runner.validate(pipe, root)
    run = runner.Run(pipe, root, root, dict(pipe["inputs"]))
    run.rotation_key = "rk-check-cmd"
    run._run_dir = root / "run"
    run._run_dir.mkdir(exist_ok=True)
    if seed is not None:
        runner.save_rotation(root, run.rotation_key, seed)
    return run


def probe_calls(record):
    """Split the stub's recorded argv into probe and session invocations."""
    calls = [json.loads(line) for line in record.read_text().splitlines()]
    return ([c for c in calls if "-p" in c], [c for c in calls if "-p" not in c])


def scenario_rejection():
    """An unknown model fails as a config error, before any session starts."""
    root, record = make_root(probe="reject", modes=["signal"])
    pipe = make_pipe(root)
    run = make_run(root, pipe)
    error = None
    with stdout_to(root / "runner-out.log"):
        try:
            runner.drive(run, pipe, run.invoke)
        except runner.Fail as exc:
            error = str(exc)
    probes, sessions = probe_calls(record)
    model_arg = (probes[0][probes[0].index("-m") + 1] if probes and "-m" in probes[0]
                 else None)
    checks = {
        "config_error_names_the_model": (error is not None
                                         and "deepseek/deepseek-v4-flash" in error
                                         and "stub/absent" in error),
        "catalog_probe_ran_once": len(probes) == 1,
        "probe_asked_about_the_declared_model": model_arg == "deepseek/deepseek-v4-flash",
        "no_session_started": not sessions,
        "no_run_log_written": not (root / "run" / "developer-task-r1.log").is_file(),
    }
    return checks, {"error": error, "probes": probes, "sessions": sessions}


def scenario_retry():
    """A missing signal retries the same slot; only success consumes it."""
    root, record = make_root(probe="refuse", modes=["silent", "signal"])
    pipe = make_pipe(root)
    # One slot in, so the accepted harness is deliberately not slot 0.
    run = make_run(root, pipe, seed={"developer": 1})
    failed = None
    with stdout_to(root / "runner-out.log"):
        try:
            runner.drive(run, pipe, run.invoke)
        except runner.Fail as exc:
            failed = str(exc)
        rotation_after_failure = json.loads(
            runner.rotation_file(root, run.rotation_key).read_text())
        resumed = json.loads((run._run_dir / "resume.json").read_text())
        result = runner.drive(run, pipe, run.invoke, resumed)
    rotation = json.loads(runner.rotation_file(root, run.rotation_key).read_text())
    ledger = json.loads((run._run_dir / "ledger.json").read_text())
    entry = ledger["steps"]["developer"]
    _probes, sessions = probe_calls(record)
    models = [a[a.index("-m") + 1] for a in sessions if "-m" in a]
    nonce_line = (run._run_dir / "developer-task-r2.md").read_text()
    nonce = nonce_line.split("## Signal nonce for this invocation: `")[1].split("`")[0]
    pointer = sessions[0][-1] if sessions else ""
    checks = {
        "first_attempt_failed_on_the_signal": (failed is not None
                                               and "missing expected signal" in failed),
        "failure_consumed_no_slot": rotation_after_failure == {"developer": 1},
        "retry_reused_the_same_slot": len(models) >= 2 and models[0] == models[1]
        == "z-ai/glm-5.3-flash",
        "success_consumed_exactly_one_slot": rotation == {"developer": 2, "review": 1},
        "ledger_names_the_cmd_harness": entry.get("harness") == SLOT_B,
        "ledger_names_the_accepted_task": entry.get("task_file") == "developer-task-r2.md",
        "failed_attempt_kept_as_history": any(
            p.endswith("developer-task-r1.md")
            for p in entry.get("superseded_task_files", [])),
        "signal_carried_the_invocation_nonce": entry.get("signal")
        == f"DEV_DONE {nonce}",
        "pointer_names_the_first_task_file": (
            f"Your full task instructions are in this file: "
            f"{run._run_dir / 'developer-task-r1.md'}" in pointer),
        "run_completed": result.get("state") == "completed",
    }
    return checks, {"error": failed, "rotation": rotation, "models": models,
                    "nonce": nonce}


def scenario_mark_done():
    """A finished-but-unsignalled attempt advances only via --mark-done."""
    root, record = make_root(probe="refuse", modes=["silent"])
    pipe = make_pipe(root)
    run = make_run(root, pipe, seed={"developer": 1})
    failures = []
    with stdout_to(root / "runner-out.log"):
        for _ in range(2):
            resumed = None
            rpath = run._run_dir / "resume.json"
            if rpath.is_file():
                resumed = json.loads(rpath.read_text())
            try:
                runner.drive(run, pipe, run.invoke, resumed)
            except runner.Fail as exc:
                failures.append(str(exc))
        resumed_before = json.loads((run._run_dir / "resume.json").read_text())
        marked = runner.mark_done(run, "developer", "DEV_DONE")
        resumed_after = json.loads((run._run_dir / "resume.json").read_text())
    ledger = json.loads((run._run_dir / "ledger.json").read_text())
    entry = ledger["steps"]["developer"]
    checks = {
        "plain_drive_never_advances": all("missing expected signal" in f
                                          for f in failures) and len(failures) == 2,
        "resume_stays_on_the_step": resumed_before.get("current") == "developer",
        "mark_done_advances": (marked.get("advanced_to") == "review"
                               and resumed_after.get("current") == "review"),
        "mark_done_records_the_cmd_harness": (entry.get("harness") == SLOT_B
                                              and entry.get("via") == "mark-done"),
        "mark_done_invokes_nothing_extra": len(probe_calls(record)[1]) == 2,
    }
    return checks, {"failures": failures, "marked": marked.get("advanced_to")}


def main():
    results, ok = {}, True
    for name, fn in (("rejection-before-session", scenario_rejection),
                     ("missing-signal-retry", scenario_retry),
                     ("finished-but-unsignalled", scenario_mark_done)):
        try:
            checks, meta = fn()
        except Exception as exc:  # noqa: BLE001 - report, never traceback out
            checks, meta = {"scenario_ran": False}, {"error": f"{type(exc).__name__}: {exc}"}
        results[name] = {"checks": checks, "meta": meta}
        if not all(checks.values()):
            ok = False
    print(json.dumps({"check_cmd_harness": "pass" if ok else "fail",
                      "scenarios": results}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

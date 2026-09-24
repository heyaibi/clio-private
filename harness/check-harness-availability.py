#!/usr/bin/env python3
# Copyright 2026 Agent Memoir Developers (https://agentmemoir.com/)
# SPDX-License-Identifier: Apache-2.0
"""Hermetic harness-availability acceptance check.

No inference spend and no repository state: stub harness binaries stand on a
fake PATH (HOME and PATH both point at a temp root, so the runner's own PATH
prepend cannot reach a real CLI) and every run dir, log, and rotation file
lives under a mkdtemp prefix. The stubs record their argv, so the checks prove
the real `runner.invoke()` path, not a stub callback.

Scenarios:
  1. skip-then-use-next: a step whose head harness is missing runs the next
     installed one. The skip is reported (banner, event, rotation) and the
     missing head is never invoked; the accepted run consumes past the skip.
  2. halt-when-none: every listed harness is missing. The run halts as a
     fail-closed config error naming the step and each missing binary, before
     any task, log, ledger, or resume file is written, and invokes nothing.
  3. cmd probe stays fail-closed: an available `cmd` whose model the CLI
     rejects remains a hard config error, not a silent skip.

Exits 0 on success, 1 on failure with JSON details.

Usage:
  python3 private/clio-private/harness/check-harness-availability.py
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
    "avail_runner", str(HARNESS_DIR / "runner.py"))
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

SLOT_MISSING = "agy:gemini-3.8-flash-high"
SLOT_OK = "opencode:go/ok-model@high"
SLOT_NONE_B = "hermes:not-installed"

# Stub harness: records argv, answers the cmd catalog probe, then (for a real
# session) reads its task pointer, finds its own run log in the task text, and
# writes a nonce-bearing signal exactly as an agent would.
STUB_SOURCE = '''#!__PYTHON__
import json, os, re, sys

name = os.path.basename(sys.argv[0])
argv = sys.argv[1:]
record = os.environ["STUB_RECORD"]
with open(record, "a") as fh:
    fh.write(json.dumps([name] + argv) + "\\n")
if name == "cmd" and "-p" in argv:
    if os.environ.get("STUB_CMD_PROBE", "refuse") == "reject":
        sys.stderr.write('Error: unknown model "stub/absent".\\n')
    else:
        sys.stderr.write(
            "Error: Local-only mode: refused a Command Code API call (/x).\\n")
    sys.exit(1)
pointer = argv[-1]
task = pointer.split("file: ", 1)[1].split("\\n", 1)[0].strip()
text = open(task).read()
step = os.path.basename(task).split("-task-")[0].split("-resume-")[0]
log = re.search(r"/[^\\s`]+" + re.escape(step) + r"-task-r\\d+\\.log",
                text).group(0)
nonce = ""
for line in text.splitlines():
    if line.startswith("## Signal nonce for this invocation:"):
        nonce = line.split("`")[1]
with open(log, "w") as fh:
    fh.write("stub harness did some work\\n")
    fh.write(f"{os.environ.get('STUB_SIGNAL', 'BYE_DONE')} {nonce}\\n")
sys.exit(0)
'''


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


@contextlib.contextmanager
def fake_harness_env(root, binaries):
    """Temp PATH with only the named stub binaries; HOME points at the root.

    Both together guarantee no real CLI is reachable: the runner's own PATH
    prepend uses HOME, which is the empty temp root here.
    """
    bin_dir = root / "bin"
    bin_dir.mkdir(exist_ok=True)
    for name in binaries:
        stub = bin_dir / name
        stub.write_text(STUB_SOURCE.replace("__PYTHON__", sys.executable))
        stub.chmod(0o755)
    saved = {k: os.environ.get(k) for k in ("HOME", "PATH", "STUB_RECORD",
                                            "STUB_SIGNAL", "STUB_CMD_PROBE")}
    os.environ["HOME"] = str(root)
    os.environ["PATH"] = f"{bin_dir}:/usr/bin:/bin"
    os.environ["STUB_RECORD"] = str(root / "stub-calls.jsonl")
    os.environ["STUB_SIGNAL"] = "BYE_DONE"
    runner.CMD_BINARY = str(bin_dir / "cmd")
    runner._CMD_PROBE_CACHE.clear()
    try:
        yield root / "stub-calls.jsonl"
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        runner.CMD_BINARY = "cmd"
        runner._CMD_PROBE_CACHE.clear()


def make_run(root, harnesses, step="d"):
    (root / f"{step}.md").write_text(
        f"---\nname: {step}\nharness: {harnesses!r}\n"
        "harness_names:\n"
        + "".join(f"  {h!r}: {h!r}\n" for h in harnesses)
        + "placeholders:\n  X: x\n  LOG: x\n"
        f"---\nImplement {{{{X}}}} on {{{{harness}}}}. Write BYE_DONE as the "
        f"last line of {{{{LOG}}}}.")
    pipe = {"version": 1, "run_dir": "run",
            "inputs": {"phase_number": 91, "phase_file": "p",
                       "max_remedy_rounds": 3},
            "start": step, "ends": ["completed"],
            "steps": {step: {"stage": f"{step}.md", "record_as": "D",
                             "bindings": {
                                 "X": "work",
                                 "LOG": "{run_dir}/{agent}-task-r{round}.log"},
                             "end": "completed"}}}
    runner.validate(pipe, root)
    run = runner.Run(pipe, root, root, dict(pipe["inputs"]))
    run.rotation_key = "rk-check-avail"
    run._run_dir = root / "run"
    run._run_dir.mkdir(exist_ok=True)
    return pipe, run


def calls(record):
    if not record.is_file():
        return []
    return [json.loads(line) for line in record.read_text().splitlines() if line.strip()]


def scenario_skip_then_next():
    """A missing head uses the next harness; the skip is reported."""
    root = Path(tempfile.mkdtemp(prefix="check-avail-skip-"))
    with fake_harness_env(root, ["opencode"]) as record:
        pipe, run = make_run(root, [SLOT_MISSING, SLOT_OK])
        picked = run.select_harness("d")
        with stdout_to(root / "runner-out.log"):
            result = runner.drive(run, pipe, run.invoke)
        banner_text = (root / "runner-out.log").read_text()
    logged = calls(record)
    sessions = [c for c in logged if c[0] != "cmd"]
    event = result["events"][0]
    rotation = json.loads(
        runner.rotation_file(root, run.rotation_key).read_text())
    ledger = json.loads((run._run_dir / "ledger.json").read_text())
    checks = {
        "missing_head_reported_by_selector": (
            picked[0] == SLOT_OK and picked[2] == 1
            and picked[1] == [(SLOT_MISSING, "agy")]),
        "missing_head_never_invoked": all(c[0] == "opencode" for c in sessions),
        "the_next_harness_is_what_ran": (
            result["state"] == "completed"
            and result["transcript"][0]["harness"] == SLOT_OK),
        "ledger_names_the_next_harness": ledger["steps"]["d"]["harness"] == SLOT_OK,
        "event_records_the_skip": event.get("skipped") == [
            {"harness": SLOT_MISSING, "missing_binary": "agy"}],
        "banner_shows_the_skip_and_why": (
            "SKIPPED" in banner_text and SLOT_MISSING in banner_text
            and "agy not on PATH" in banner_text),
        "one_attempt_only": sorted(p.name for p in run._run_dir.iterdir()) == [
            "d-task-r1.log", "d-task-r1.md", "ledger.json", "resume.json"],
        "accepted_run_consumes_past_the_skip": rotation == {"d": 2},
    }
    return checks, {"root": str(root), "rotation": rotation,
                    "sessions": [c[0] for c in sessions]}


def scenario_halt_when_none():
    """Every harness missing halts as a config error, touching no state."""
    root = Path(tempfile.mkdtemp(prefix="check-avail-halt-"))
    with fake_harness_env(root, []) as record:
        pipe, run = make_run(root, [SLOT_MISSING, SLOT_NONE_B])
        halted = None
        with stdout_to(root / "runner-out.log"):
            try:
                runner.drive(run, pipe, run.invoke)
            except runner.HarnessUnavailable as exc:
                halted = exc
        payload = runner.config_error_payload(halted) if halted else {}
    checks = {
        "halt_is_a_config_error": halted is not None,
        "halt_names_the_step": payload.get("step") == "d",
        "halt_names_every_harness_and_binary": payload.get("harnesses") == [
            {"harness": SLOT_MISSING, "missing_binary": "agy"},
            {"harness": SLOT_NONE_B, "missing_binary": "hermes"}],
        "halt_invokes_nothing": calls(record) == [],
        "halt_writes_no_state": not list(run._run_dir.iterdir()),
        "halt_advances_no_rotation": not
        runner.rotation_file(root, run.rotation_key).exists(),
    }
    return checks, {"root": str(root), "error": str(halted) if halted else None}


def scenario_cmd_probe_fail_closed():
    """An available cmd with a rejected model stays a hard config error."""
    root = Path(tempfile.mkdtemp(prefix="check-avail-cmd-"))
    with fake_harness_env(root, ["cmd"]) as record:
        os.environ["STUB_CMD_PROBE"] = "reject"
        pipe, run = make_run(root, ["cmd:stub-model@high"])
        error, exc_type = None, None
        with stdout_to(root / "runner-out.log"):
            try:
                runner.drive(run, pipe, run.invoke)
            except runner.HarnessUnavailable as exc:
                exc_type, error = "HarnessUnavailable", str(exc)
            except runner.Fail as exc:
                exc_type, error = "Fail", str(exc)
    logged = calls(record)
    probes = [c for c in logged if "-p" in c]
    sessions = [c for c in logged if "-p" not in c]
    checks = {
        "probe_rejection_is_a_config_error": (
            exc_type == "Fail" and error is not None
            and "stub-model" in error and "stub/absent" in error),
        "probe_rejection_is_not_a_skip": exc_type != "HarnessUnavailable",
        "only_the_probe_ran": len(probes) == 1 and not sessions,
    }
    return checks, {"root": str(root), "error": error, "exc_type": exc_type}


def main():
    results, ok = {}, True
    for name, fn in (("skip-then-use-next", scenario_skip_then_next),
                     ("halt-when-none", scenario_halt_when_none),
                     ("cmd-probe-fail-closed", scenario_cmd_probe_fail_closed)):
        try:
            checks, meta = fn()
        except Exception as exc:  # noqa: BLE001 - report, never traceback out
            checks = {"scenario_ran": False}
            meta = {"error": f"{type(exc).__name__}: {exc}"}
        results[name] = {"checks": checks, "meta": meta}
        if not all(checks.values()):
            ok = False
    print(json.dumps({"check_harness_availability": "pass" if ok else "fail",
                      "scenarios": results}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

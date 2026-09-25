#!/usr/bin/env python3
# Copyright 2026 Agent Memoir Developers (https://agentmemoir.com/)
# SPDX-License-Identifier: Apache-2.0
"""Hermetic per-run harness-plan acceptance check.

No inference spend and no repository state: stub harness binaries stand on a
fake PATH (HOME and PATH both point at a temp root, so the runner's own PATH
prepend cannot reach a real CLI) and every run dir, plan, log, and rotation
file lives under a mkdtemp prefix. The stubs record their argv and check that
`harnesses.json` was already on disk when they ran, so the checks prove the
real `runner.invoke()` path, not a stub callback.

Scenarios:
  1. decided-before-start: the plan names every stage, is on disk before the
     first harness runs, and the run uses exactly what it says.
  2. one-harness-per-stage: a loop step's rounds all use the planned harness
     (the plan is per run, not per round), and the slot is consumed once.
  3. operator-choice: `--customize-harness` through a real pty; the typed pick
     drives the run and is saved before it starts.
  4. declined-plan: answering no at the confirmation starts nothing.
  5. resume-keeps-plan: a missing-signal failure then a resume reuses the
     saved plan and the same harness, without rewriting the file.

Exits 0 on success, 1 on failure with JSON details.

Usage:
  python3 private/clio-private/harness/check-harness-plan.py
"""
import contextlib
import importlib.util
import json
import os
import pty
import select
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HARNESS_DIR = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "plan_runner", str(HARNESS_DIR / "runner.py"))
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

SLOTS = ["opencode:go/plan-a@high", "opencode:go/plan-b@high",
         "opencode:go/plan-c@high"]
# Stub harness: records argv plus whether the plan was already on disk, then
# reads its task pointer, finds its own run log in the task text, and writes a
# nonce-bearing signal exactly as an agent would (or, with STUB_NO_SIGNAL, a log
# with no signal at all, to drive the resume scenario).
STUB_SOURCE = '''#!__PYTHON__
import json, os, re, sys

argv = sys.argv[1:]
record = os.environ["STUB_RECORD"]
with open(record, "a") as fh:
    fh.write(json.dumps(argv) + "\\n")
task = None
for arg in argv:
    match = re.search(r"(/[^\\s]*-(?:task|resume)-r\\d+\\.md)", arg)
    if match:
        task = match.group(1)
if task is None:
    sys.exit(9)
text = open(task).read()
step = os.path.basename(task).split("-task-")[0].split("-resume-")[0]
log = re.search(r"/[^\\s`]+" + re.escape(step) + r"-task-r\\d+\\.log",
                text).group(0)
nonce = ""
for line in text.splitlines():
    if line.startswith("## Signal nonce for this invocation:"):
        nonce = line.split("`")[1]
run_dir = os.path.dirname(log)
with open(os.path.join(run_dir, "stub-plan-probe.jsonl"), "a") as fh:
    fh.write(json.dumps({
        "step": step,
        "plan_on_disk": os.path.isfile(os.path.join(run_dir, "harnesses.json")),
        "planned_harness": json.load(open(os.path.join(
            run_dir, "harnesses.json")))["steps"][step]["harness"]
        if os.path.isfile(os.path.join(run_dir, "harnesses.json")) else None,
        "named_in_prompt": step in text,
    }) + "\\n")
if os.environ.get("STUB_NO_SIGNAL") == "1":
    with open(log, "w") as fh:
        fh.write("stub harness finished but wrote no signal\\n")
else:
    with open(log, "w") as fh:
        fh.write("stub harness did some work\\n")
        fh.write(f"{os.environ.get('STUB_SIGNAL', 'BYE_DONE')} {nonce}\\n")
sys.exit(0)
'''

# The launcher runs the real main() with only the network-bound and
# coordination-bound pieces stubbed. Everything the plan touches is the
# runner's own code, in a temp repo.
LAUNCHER = '''import importlib.util, os, sys
from pathlib import Path

H = Path({harness_dir!r})
spec = importlib.util.spec_from_file_location("r", str(H / "runner.py"))
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)
r.gitsync.sync_all = lambda *a, **k: {{"ok": True, "summary": "stubbed"}}
r.gitsync.commit_leftover_run_state = lambda *a, **k: {{
    "ok": True, "summary": "stubbed"}}
def _no_claim(run, **k):
    run.reservation = None
r._prepare_reservation = _no_claim
r._finish_reservation = lambda run, result, receipt_path=None: result
r._publish_completion_evidence = lambda run: None
r._write_pending_completion = lambda run, result: None
_orig_invoke = r.Run.invoke
def _invoke(self, harness, *a, **k):
    os.environ["STUB_WHICH"] = harness
    return _orig_invoke(self, harness, *a, **k)
r.Run.invoke = _invoke
r.main()
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
def stub_env(root, binaries, **extra):
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
    keys = ("HOME", "PATH", "STUB_RECORD", "STUB_SIGNAL", "STUB_NO_SIGNAL")
    saved = {k: os.environ.get(k) for k in keys}
    os.environ["HOME"] = str(root)
    os.environ["PATH"] = f"{bin_dir}:/usr/bin:/bin"
    os.environ["STUB_RECORD"] = str(root / "stub-calls.jsonl")
    os.environ["STUB_SIGNAL"] = "BYE_DONE"
    os.environ.pop("STUB_NO_SIGNAL", None)
    os.environ.update(extra)
    try:
        yield bin_dir
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def write_stage(root, step_id, slots, extra_body=""):
    (root / f"{step_id}.md").write_text(
        f"---\nname: {step_id}\nharness: {slots!r}\nharness_names:\n"
        + "".join(f"  {h!r}: {h.split('/')[1].split('@')[0]!r}\n" for h in slots)
        + "placeholders:\n  X: x\n  LOG: x\n---\n"
        "Do {{X}} as {{harness}}, then write BYE_DONE to "
        "{{LOG}}%s." % extra_body)


def make_root(step_id="dev", slots=None, phase=80):
    """A temp repo with one stub-harness stage and a launcher for main()."""
    root = Path(tempfile.mkdtemp(prefix="check-plan-"))
    slots = slots if slots is not None else SLOTS
    write_stage(root, step_id, slots)
    pipe = {"version": 1, "run_dir": "run",
            "inputs": {"phase_number": phase, "phase_file": "p",
                       "max_remedy_rounds": 3},
            "start": step_id, "ends": ["completed"],
            "steps": {step_id: {"stage": f"{step_id}.md", "record_as": "D",
                                "bindings": {
                                    "X": "work",
                                    "LOG": "{run_dir}/{agent}-task-r{round}.log"},
                                "end": "completed"}}}
    (root / "pipeline.yaml").write_text(json.dumps(pipe))
    (root / "launcher.py").write_text(LAUNCHER.format(harness_dir=str(HARNESS_DIR)))
    # The live runner validates phase_file against the roadmap; a temp roadmap
    # with the canonical name keeps that check real instead of stubbed.
    roadmap = root / "private" / "clio-private" / "roadmap"
    roadmap.mkdir(parents=True)
    (roadmap / f"phase-{phase:06d}-check-plan.md").write_text("plan fixture\n")
    return root, phase


def launch(root, phase, extra=(), env=None, answers=None, timeout=180):
    """Run main() in the temp repo; answer a pty prompt when asked.

    With `answers` the run goes through a real pty and each prompt is answered
    with the next line, so the interactive path is exercised end to end.
    Returns (exit_code, terminal_output).
    """
    argv = [sys.executable, "launcher.py", "--pipeline", "pipeline.yaml",
            "--input", f"phase_number={phase}", "--input",
            "phase_file=private/clio-private/roadmap/"
            f"phase-{phase:06d}-check-plan.md", *extra]
    environ = {**os.environ, **(env or {})}
    if answers is None:
        done = subprocess.run(argv, cwd=root, env=environ, capture_output=True,
                              text=True, timeout=timeout)
        return done.returncode, done.stdout + done.stderr
    master, slave = pty.openpty()
    proc = subprocess.Popen(argv, stdin=slave, stdout=slave, stderr=slave,
                            cwd=root, env=environ, close_fds=True)
    os.close(slave)
    out = b""
    pending = list(answers)
    deadline = time.time() + timeout
    while time.time() < deadline:
        readable, _, _ = select.select([master], [], [], 0.5)
        if readable:
            try:
                chunk = os.read(master, 65536)
            except OSError:
                break
            if not chunk:
                break
            out += chunk
        if pending and (b"choose 1-" in out or b"[y/N]" in out):
            os.write(master, (pending.pop(0) + "\n").encode())
        if proc.poll() is not None and not readable:
            break
    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()
    os.close(master)
    return proc.returncode, out.decode("utf-8", "replace")


def _last_json_object(text):
    """The last complete JSON object in a pty transcript.

    A pty interleaves prompts, the runner's stderr JSON, and box-drawing
    characters, so the payload is located by brace balance rather than by a
    fixed prefix.
    """
    depth = start = None
    for index, char in enumerate(text):
        if char == "{":
            if depth is None:
                depth, start = 0, index
            depth += 1
        elif char == "}" and depth:
            depth -= 1
            if depth == 0:
                try:
                    payload = json.loads(text[start:index + 1])
                except ValueError:
                    payload = None
                if isinstance(payload, dict) and "state" in payload:
                    return payload
    return {}


def probe(root, step_id="dev"):
    path = root / "run" / "stub-plan-probe.jsonl"
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text().splitlines()
            if line.strip()]


def plan_of(root):
    path = root / "run" / "harnesses.json"
    return json.loads(path.read_text()) if path.is_file() else None


def run_dir_files(root):
    run_dir = root / "run"
    return sorted(p.name for p in run_dir.iterdir()) if run_dir.is_dir() else []


def scenario_decided_before_start():
    """The plan names every stage and is on disk before the first harness."""
    root, phase = make_root()
    with stub_env(root, ["opencode"]) as _bin:
        code, _out = launch(root, phase)
    plan = plan_of(root)
    seen = probe(root)
    checks = {
        "run_completed": code == 0,
        "plan_saved_before_any_harness": all(c["plan_on_disk"] for c in seen)
        and bool(seen),
        "plan_names_the_stage": plan is not None and "dev" in plan["steps"],
        "harness_saw_the_same_model_it_ran": bool(seen)
        and all(c["planned_harness"] == SLOTS[0] for c in seen),
        "ledger_agrees_with_the_plan": json.loads(
            (root / "run" / "ledger.json").read_text())["steps"]["dev"]["harness"]
        == plan["steps"]["dev"]["harness"],
        "plan_records_every_option": len(plan["steps"]["dev"]["options"]) == 3,
        "plan_is_the_only_new_run_state": "harnesses.json" in run_dir_files(root),
    }
    return checks, {"root": str(root), "planned": plan["steps"]["dev"]["harness"],
                    "probe": seen}


def scenario_one_harness_per_stage():
    """A loop step's rounds all use the planned harness; one slot consumed."""
    root, phase = make_root(step_id="fix", phase=81)
    # dev -> fix ⇄ dev, so `fix` runs three times in one run.
    write_stage(root, "dev", SLOTS)
    pipe = {"version": 1, "run_dir": "run",
            "inputs": {"phase_number": 81, "phase_file": "p",
                       "max_remedy_rounds": 3},
            "start": "dev", "ends": ["completed", "rejected"],
            "steps": {
                "dev": {"stage": "dev.md", "record_as": "D",
                        "bindings": {"X": "work",
                                     "LOG": "{run_dir}/{agent}-task-r{round}.log"},
                        "when": {"BYE_DONE": "fix"}},
                "fix": {"stage": "fix.md", "record_as": "F", "max_rounds": 3,
                        "bindings": {"X": "work",
                                     "LOG": "{run_dir}/{agent}-task-r{round}.log"},
                        "on_exhausted": "rejected",
                        "when": {"BYE_DONE": "dev"}}}}
    (root / "pipeline.yaml").write_text(json.dumps(pipe))
    with stub_env(root, ["opencode"]) as _bin:
        code, _out = launch(root, 81)
    plan = plan_of(root)
    seen = probe(root)
    fix_rounds = [c for c in seen if c["step"] == "fix"]
    rotation_file = runner.rotation_file(root, runner.rotation_key_for(
        (root / "pipeline.yaml").resolve()))
    rotation = json.loads(rotation_file.read_text()) if rotation_file.is_file() else None
    checks = {
        "run_ended_as_rejected": code == 1,
        "the_loop_ran_three_rounds": len(fix_rounds) == 3,
        "every_round_used_the_planned_harness": bool(fix_rounds)
        and all(c["planned_harness"] == plan["steps"]["fix"]["harness"]
                for c in fix_rounds),
        "no_round_switched_model": len({c["planned_harness"] for c in seen}) == 1,
        "one_slot_consumed_per_stage_for_the_whole_run": rotation
        == {"dev": 1, "fix": 1},
    }
    return checks, {"root": str(root), "rounds": len(fix_rounds),
                    "rotation": rotation}


def scenario_operator_choice():
    """--customize-harness: the typed pick drives and is saved before the run."""
    root, phase = make_root(phase=82)
    with stub_env(root, ["opencode"]) as _bin:
        code, out = launch(root, 82, extra=["--customize-harness"],
                           answers=["3", "y"])
    plan = plan_of(root)
    seen = probe(root)
    checks = {
        "options_were_shown": "choose 1-3" in out,
        "the_map_was_confirmed": "start the run with this plan?" in out,
        "run_completed": code == 0,
        "the_pick_was_saved": plan["steps"]["dev"]["harness"] == SLOTS[2]
        and plan["source"] == "custom"
        and plan["steps"]["dev"]["selected_by"] == "operator",
        "the_pick_is_saved_before_any_harness": bool(seen)
        and all(c["plan_on_disk"] and c["planned_harness"] == SLOTS[2]
                for c in seen),
        "the_run_used_the_pick": bool(seen)
        and all(c["planned_harness"] == SLOTS[2] for c in seen),
    }
    return checks, {"root": str(root),
                    "planned": plan["steps"]["dev"]["harness"] if plan else None}


def scenario_declined_plan():
    """Answering no at the confirmation starts nothing."""
    root, phase = make_root(phase=83)
    with stub_env(root, ["opencode"]) as _bin:
        code, out = launch(root, 83, extra=["--customize-harness"],
                           answers=["1", "n"])
    payload = _last_json_object(out)
    checks = {
        "nothing_ran": probe(root) == [] and "HARNESS" not in out,
        "no_plan_was_saved": plan_of(root) is None,
        "no_run_state_was_written": not any(
            name in run_dir_files(root)
            for name in ("ledger.json", "run.json", "resume.json")),
        "reported_as_aborted": payload.get("state") == "aborted",
        "exits_two": code == 2,
    }
    return checks, {"root": str(root), "payload": payload}


def scenario_resume_keeps_plan():
    """A missing signal then a resume reuses the saved plan and harness."""
    root, phase = make_root(phase=84)
    with stub_env(root, ["opencode"]) as _bin:
        first, _out1 = launch(root, 84, env={"STUB_NO_SIGNAL": "1"})
        saved = plan_of(root)
        before = (root / "run" / "harnesses.json").stat().st_mtime_ns
        second, _out2 = launch(root, 84)
        after = (root / "run" / "harnesses.json").stat().st_mtime_ns
    seen = probe(root)
    ledger = json.loads((root / "run" / "ledger.json").read_text())
    checks = {
        "first_attempt_failed_on_the_signal": first == 2,
        "resume_completed": second == 0,
        "the_retry_used_the_same_harness": len(seen) == 2
        and seen[0]["planned_harness"] == seen[1]["planned_harness"] == SLOTS[0],
        "the_plan_was_not_rewritten": before == after,
        "the_ledger_records_the_planned_harness":
            ledger["steps"]["dev"]["harness"] == saved["steps"]["dev"]["harness"],
    }
    return checks, {"root": str(root), "attempts": len(seen)}


def main():
    results, ok = {}, True
    for name, fn in (("decided-before-start", scenario_decided_before_start),
                     ("one-harness-per-stage", scenario_one_harness_per_stage),
                     ("operator-choice", scenario_operator_choice),
                     ("declined-plan", scenario_declined_plan),
                     ("resume-keeps-plan", scenario_resume_keeps_plan)):
        try:
            checks, meta = fn()
        except Exception as exc:  # noqa: BLE001 - report, never traceback out
            checks = {"scenario_ran": False}
            meta = {"error": f"{type(exc).__name__}: {exc}"}
        results[name] = {"checks": checks, "meta": meta}
        if not all(checks.values()):
            ok = False
    print(json.dumps({"check_harness_plan": "pass" if ok else "fail",
                      "scenarios": results}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

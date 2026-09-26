#!/usr/bin/env python3
# Copyright 2026 Agent Memoir Developers (https://agentmemoir.com/)
# SPDX-License-Identifier: Apache-2.0
"""Generic stage-pipeline runner.

Reads a pipeline YAML (see private/clio-private/workflow/pipelines/default.yaml
for the contract), renders each step's stage file by binding its {{PLACEHOLDERS}},
invokes the stage's harness CLI, matches the final-line signal, and routes.

Usage (run from the repo root):
  python3 private/clio-private/harness/runner.py --pipeline private/clio-private/workflow/pipelines/default.yaml \
      --input phase_number=100060 --input phase_file=private/clio-private/roadmap/phase-100060-parallel-write-canonical-consolidation.md

  --dry-run validates everything and prints rendered prompts without
  invoking any harness. --self-test checks harness binaries and model
  slugs statically (--live adds one-word inference probes). --fuzz N runs
  N randomized router property trials.

Conventions (load-bearing, do not change silently):
  - `agent` is the step id (developer.log, not record_as). Finalize is
    attributed Developer but logs to finalize.log; that split is intended.
  - Repo root is the process working directory. run_dir resolves against it.
  - Exit codes: 0 completed, 1 terminal non-complete (rejected/blocked),
    2 config_error, 3 WAIT_FOR_CLAIM, 4 FENCED (machine-readable JSON on
    stdout in all cases).
  - Parked phase numbers (>= 900000) are roadmap-only; runner rejects them
    and next_phase.py never selects them.
  - Every live run claims the exact phase in the private coordination board
    before invoking a harness. A server passes its claim through the driver;
    a local run claims it directly. An active claim by another machine returns
    WAIT_FOR_CLAIM, and stale machine/reservation/generation tokens are fenced.
  - No runner timeouts, but agy enforces its own --print-timeout
    (default 5m) inside the harness; long reviews near that ceiling need
    an explicit harness-side decision, not a runner change.
  - The ledger's task_file/harness pair is the authority for completed
    attempts; other task files remain historical records.

Foreground: every harness runs attached in the operator's terminal with
inherited stdio; the runner polls the step's run log and closes the
session ~15 s after the final signal lands. Ctrl-C kills
the step; rerunning the same command resumes. See runner.md.
"""
import argparse
import hashlib
import json
import os
import re
import secrets
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

try:
    import fcntl
    import pty
    import select
    import termios
    import tty
    _HAVE_PTY = True
except ImportError:
    _HAVE_PTY = False

import yaml

# Host helpers moved to ../scripts. Keep both directories importable so the
# engine still loads when run as a script or imported. Untangling these
# imports is tracked extraction work, not this change.
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "pipeline"))
import gitsync  # noqa: E402 - path set just above
from phase_policy import PARKED_PHASE_FLOOR, is_runnable_phase  # noqa: E402
import check_incidental_policy  # noqa: E402
from phase_reservations import (  # noqa: E402
    CoordinationError,
    ReservationConflict,
    ReservationFenced,
    ReservationStore,
    load_reservation_file,
    reservation_file,
    reservation_from_environment,
    save_reservation_file,
)

TOKEN_RE = re.compile(r"\{\{([A-Za-z_][A-Za-z0-9_]*)\}\}")
HARNESS_RE = re.compile(r"[a-z0-9_-]+:[^\s:]+")
INT_INPUTS = {"phase_number", "max_remedy_rounds"}

EFFORTS = {"none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra"}

# Auto-exit: TUI harnesses idle after finishing, so the runner
# polls the run log and closes the session once the final signal is stable.
AUTOEXIT_POLL_S = 1.0
AUTOEXIT_STABLE_POLLS = 2
AUTOEXIT_GRACE_S = 15.0
AUTOEXIT_TERM_S = 10.0
AUTOEXIT_KILL_S = 5.0
# Signal scan-back: the completion signal is matched against the last
# SIGNAL_SCAN_LINES non-empty log lines (bottom-up), not just the final
# line, so a trailing summary or blank line cannot hide it. The normative
# rule stays "signal last, nothing after it" (stage files); the scan is
# tolerance, not permission.
SIGNAL_SCAN_LINES = 10
# Idle nudge: when the log shows no signal and stops growing for this long,
# the runner prints the exact recovery line to stderr so a forgotten log
# signal never sits silent (a missing signal alone must not hang the run
# unnoticed). No timeout: the step still runs until it signals.
IDLE_NUDGE_S = 300.0
# Agent-facing idle reminder: when both the run log and the console stop
# growing with no completion signal, the runner types a short reminder into
# the harness's own input (the pty) and submits it, so an agent that finished
# but forgot the log line can still be told to write it. The text is
# signal-safe: it carries no per-run nonce and no token ending in BLOCKED, so
# the console-mirror scan can never mistake it for a completion signal. It is
# delivered only on the pty path (that is where an interactive agent input
# exists) and only for harnesses that run with permissions auto-approved
# (REMINDER_CLIS), so it is never typed into a confirmation dialog. The stderr
# warning above stays in both paths as the fallback. It is rate-limited: first
# reminder after IDLE_REMIND_S quiet, each later one IDLE_REMIND_BACKOFF times
# further out, capped at IDLE_REMIND_MAX per invocation, skipped once the
# operator has typed at all (an attended session is handled by the human), and
# skipped when the console tail looks like an unanswered prompt. If the first
# Enter appears swallowed it presses Enter once more after IDLE_REMIND_RESUBMIT_S
# (the existing auto-submit relies on the same tolerance). It never fabricates
# a signal and never writes to the run log.
IDLE_REMIND_S = 300.0
IDLE_REMIND_BACKOFF = 2.0
IDLE_REMIND_MAX = 3
IDLE_REMIND_RESUBMIT_S = 2.0
IDLE_REMIND_TEXT = (
    "Pipeline runner reminder: if your task is finished, write the final "
    "signal line described in your task file as the last line of your run "
    "log now. If you are still working, ignore this message and continue.")
IDLE_REMIND_PLAN = {
    "first_s": IDLE_REMIND_S,
    "backoff": IDLE_REMIND_BACKOFF,
    "max": IDLE_REMIND_MAX,
    "resubmit_s": IDLE_REMIND_RESUBMIT_S,
    "text": IDLE_REMIND_TEXT,
    "enabled": True,
}
# Harnesses whose stages run with permissions auto-approved (opencode --auto,
# agy --dangerously-skip-permissions, cmd --yolo). The reminder targets only
# these: a harness that may be waiting at a confirmation dialog is never typed
# into. cursor and hermes are excluded because they can prompt the operator.
REMINDER_CLIS = {"opencode", "agy", "cmd"}
# TUI auto-submit: `opencode --prompt` pre-fills the input box but does not
# send it, so the runner presses Enter repeatedly until the stage starts
# (detected by the run log growing). A single press is unreliable: the TUI is
# still loading for the first several seconds and swallows it.
SUBMIT_FIRST_S = 10.0
SUBMIT_RETRY_S = 5.0
SUBMIT_MAX_S = 120.0
# Per-invocation signal nonce: every harness invocation gets a fresh
# random token appended to its task file. Non-*_BLOCKED* signal lines must
# carry it as a separate token, so a mid-run echo of the bare signal word
# can neither close the session nor route the pipeline. *_BLOCKED lines
# need no nonce (ending as blocked is always operator-visible).
NONCE_BYTES = 4
RESERVATION_HEARTBEAT_S = 300.0
NONCE_FOOTER = (
    "\n\n## Signal nonce for this invocation: `{nonce}`\n\n"
    "Append this nonce as a separate token after your signal word, e.g. "
    "`REMEDIATOR_DONE {nonce}` (use your own step's signal word; for "
    "signals with arguments put the nonce last, e.g. `ADVERSARY_DONE "
    "findings=<path> {nonce}`). A signal line without this exact nonce "
    "is ignored. Nonces quoted from earlier prompts are stale: use only "
    "this one. `*_BLOCKED` lines need no nonce.\n")
END_TOKENS = ("_DONE", "_APPROVED", "_REJECTED")
# OpenCode v2 full TUI: stages run in the real interface, which stays open
# until the stage signals. The v2 root TUI has no --model/--agent, so the model
# and reasoning effort are injected via OPENCODE_CONFIG_CONTENT.
OPENCODE_AGENT = "am_pipeline_stage"


def parse_harness(h):
    """Split '<cli>:<provider>/<model>[@<effort>]' into
    (cli, provider, model, effort). Provider is the segment before the
    first '/'; effort is the segment after the last '@'. Both are None
    when absent. A present but unknown '@effort' is a config error."""
    cli, rest = h.split(":", 1)
    effort = None
    if "@" in rest:
        rest, tail = rest.rsplit("@", 1)
        if tail not in EFFORTS:
            raise Fail(f"unknown effort {tail!r} in harness {h!r}")
        effort = tail
    if "/" in rest:
        provider, model = rest.split("/", 1)
        if not provider or not model:
            raise Fail(f"bad harness ref {h!r}: want "
                       f"'<cli>:<provider>/<model>[@<effort>]'")
    else:
        provider, model = None, rest
    if not cli or not model:
        raise Fail(f"bad harness ref {h!r}: want "
                   f"'<cli>:<provider>/<model>[@<effort>]'")
    return cli, provider, model, effort


# Display-name registry, derived — never hand-edited. Each stage file
# declares `harness_names:` alongside its `harness:` list; load_stage merges
# them here. One file per harness change. Anything unmapped falls back to
# the raw id rather than failing.
HARNESS_DISPLAY = {}


def display_name(harness):
    return HARNESS_DISPLAY.get(harness, harness)


# Durable rotation state, one file per pipeline: {step_id: slots consumed}.
# Fresh runs seed from it, every consume writes through, resume max-merges.
# This is what makes round-robin span executions instead of restarting at
# slot 0. Different pipeline files rotate independently.
def rotation_file(repo, key):
    # Run state lives under private/clio-private/runs/.
    return repo / "private/clio-private/runs" / f".harness-rotation-{key}.json"


def rotation_key_for(pipe_path):
    """Namespace rotation by pipeline path, not just stem."""
    stem = Path(pipe_path).stem
    digest = hashlib.sha1(str(pipe_path).encode()).hexdigest()[:8]
    return f"{stem}-{digest}"


def load_rotation(repo, key):
    """Read durable rotation counts.

    A missing file means no rotation has been recorded yet. Any present
    but unusable file fails closed: rotation determines model identity,
    so silently resetting to zero could repeat a model and recreate the
    confusion this runner prevents. Repair with --reset-rotation after
    confirming no resumable run depends on the counts.
    """
    fp = rotation_file(repo, key)
    try:
        data = json.loads(fp.read_text())
    except FileNotFoundError:
        return {}
    except OSError as e:
        raise Fail(f"rotation: {fp.name} unreadable ({e}); "
                   f"repair or use --reset-rotation") from e
    except ValueError as e:
        raise Fail(f"rotation: {fp.name} does not parse ({e}); "
                   f"repair or use --reset-rotation") from e
    try:
        counts = {str(k): int(v) for k, v in dict(data).items()}
    except (TypeError, ValueError) as e:
        raise Fail(f"rotation: {fp.name} has bad counts ({e}); "
                   f"repair or use --reset-rotation") from e
    for sid, count in counts.items():
        if not isinstance(count, int) or count < 0:
            raise Fail(f"rotation: {fp.name} has invalid count for {sid!r}; "
                       f"repair or use --reset-rotation")
        # bool is an int subclass; rotation counts must be real integers.
        if isinstance(count, bool):
            raise Fail(f"rotation: {fp.name} has invalid count for {sid!r}; "
                       f"repair or use --reset-rotation")
    return counts


def save_rotation(repo, key, harness_use):
    # Single-operator assumption: runs are foreground and sequential, so an
    # atomic replacement is enough; concurrent runs are last-writer-wins.
    # Rotation determines model identity, so a write failure fails the
    # completion instead of silently continuing without durable state.
    fp = rotation_file(repo, key)
    try:
        fp.parent.mkdir(parents=True, exist_ok=True)
        write_json_atomic(fp, harness_use)
    except (Fail, OSError) as e:
        raise Fail(f"rotation: cannot write {fp.name} ({e})") from e


# Per-run harness plan: the whole step -> harness map, decided once before the
# job starts and saved beside the run state as <run_dir>/harnesses.json, so one
# file per phase run dir names the model every stage will use. One harness per
# stage for the whole run, so every round of a loop, every retry, and every
# rendered prompt names the same model. The durable rotation file still
# supplies the starting offset, so consecutive runs keep alternating; a step
# consumes its slot once per run, when the step is accepted. Without the flag
# the runner decides this map on its own; with --customize-harness the operator
# picks each stage's slot from the options that stage declares.
PLAN_FILENAME = "harnesses.json"
PLAN_VERSION = 1


def plan_path(run):
    """Where the run's harness map lives (one file per phase run dir).

    None while the run has no directory yet: a caller that drives a Run in
    memory (the hermetic checks) keeps its map in memory only and writes
    nothing.
    """
    run_dir = getattr(run, "_run_dir", None)
    return None if run_dir is None else Path(run_dir) / PLAN_FILENAME


def plan_options(run, sid, lookup=shutil.which):
    """The stage's declared harness list with live availability, in order.

    The list is the stage file's rotation order. Availability is binary
    presence only, exactly as the invoke-time skip uses it, so the plan can
    never name a CLI that is not installed.
    """
    return [{"harness": h, "display": display_name(h),
             "binary": binary_for(h),
             "available": is_harness_available(h, lookup)}
            for h in run.harnesses(sid)]


def _stored_options(options):
    return [{k: o[k] for k in ("harness", "display", "binary", "available")}
            for o in options]


def plan_entry(run, sid, offset, options=None, lookup=shutil.which):
    """Decide one step's harness: the first installed option from `offset`.

    Same walk as the invoke-time selection (start at the offset, wrap, take the
    first installed entry), recorded with what it walked over, so the banner,
    the event, and the saved plan all name the same skips. Raises
    HarnessUnavailable when nothing is installed, which halts the run before
    any harness is invoked.
    """
    options = plan_options(run, sid, lookup) if options is None else options
    idx = select_harness([o["harness"] for o in options], offset, lookup)
    if idx is None:
        raise HarnessUnavailable(sid, [o["harness"] for o in options])
    walked = (idx - offset) % len(options)
    chosen = options[idx]
    return {
        "stage": run.steps[sid].get("stage", sid),
        "name": run.stages[sid][0].get("name", sid),
        "record_as": run.steps[sid].get("record_as", sid),
        "harness": chosen["harness"],
        "display": chosen["display"],
        "offset": offset,
        "index": idx,
        "next_count": offset + walked + 1,
        "skipped": [{"harness": options[(offset + off) % len(options)]["harness"],
                     "missing_binary": options[(offset + off) % len(options)]["binary"]}
                    for off in range(walked)],
        "options": _stored_options(options),
        "selected_by": "runner",
    }


def _usable_plan_counts(recorded, options):
    """True when a recorded entry's index and next counter can be trusted."""
    index = recorded.get("index")
    nxt = recorded.get("next_count")
    for value in (index, nxt):
        if not isinstance(value, int) or isinstance(value, bool):
            return False
    if nxt < 0 or not 0 <= index < len(options):
        return False
    if options[index]["harness"] != recorded.get("harness"):
        return False
    return isinstance(recorded.get("skipped", []), list)


def planned_entry(run, sid, offset, recorded=None, lookup=shutil.which):
    """One step's planned entry, keeping a recorded choice that still holds.

    A saved plan is the run's model map, so a recorded harness survives as long
    as the stage still declares it and its CLI is still installed. The entry is
    re-decided from the rotation offset only when the run has no plan for this
    step, when a pipeline edit dropped the id, or when the binary went away;
    availability in the record is always refreshed from the live PATH.
    """
    options = plan_options(run, sid, lookup)
    if isinstance(recorded, dict) and _usable_plan_counts(recorded, options):
        chosen = next((o for o in options
                       if o["harness"] == recorded["harness"]), None)
        if chosen is not None and chosen["available"]:
            entry = dict(recorded)
            entry["stage"] = run.steps[sid].get("stage", entry.get("stage", sid))
            entry["name"] = run.stages[sid][0].get("name", entry.get("name", sid))
            entry["display"] = chosen["display"]
            entry["options"] = _stored_options(options)
            return entry
    return plan_entry(run, sid, offset, options, lookup)


def plan_offsets(run, resumed=None):
    """Rotation offsets a fresh plan decision starts from.

    The durable file is the record of consumed slots. A resume max-merges it
    with resume.json exactly as drive() does, so a plan decided mid-run starts
    from the slot the run itself would have used.
    """
    offsets = {}
    if run.persist_rotation and run.rotation_key:
        offsets.update(load_rotation(run.repo, run.rotation_key))
    for sid, count in dict((resumed or {}).get("harness_use", {})).items():
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            continue
        offsets[sid] = max(offsets.get(sid, 0), count)
    return offsets


def _plan_run_id(run):
    try:
        return (f"{run.inputs.get('run_label', 'phase')}"
                f"-{int(run.inputs['phase_number']):06d}")
    except (KeyError, TypeError, ValueError):
        return str(run.inputs.get("run_label", "phase"))


def decide_harness_plan(run, *, saved=None, offsets=None, resumed=None,
                        lookup=shutil.which):
    """Build the run's whole harness map from the stage files.

    `saved` is the plan already on disk (its steps win wherever they still
    hold), `offsets` the rotation offsets for the steps that need a decision.
    Nothing is prompted and nothing is written: the caller decides whether to
    ask the operator and when to persist the result.
    """
    if offsets is None:
        offsets = plan_offsets(run, resumed)
    recorded = saved["steps"] if saved else {}
    return {
        "version": PLAN_VERSION,
        "run_id": _plan_run_id(run),
        "pipeline": str(getattr(run, "pipe_path", "") or ""),
        "rotation_key": run.rotation_key,
        "created_at": (saved or {}).get("created_at")
        or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": (saved or {}).get("source", "auto"),
        "steps": {sid: planned_entry(run, sid, int(offsets.get(sid, 0)),
                                     recorded.get(sid), lookup)
                  for sid in run.steps},
    }


def plan_harnesses(run, *, custom=False, fresh=False, resumed=None, offsets=None,
                   lookup=shutil.which):
    """Decide the run's whole harness map and return it with a changed flag.

    A run that already saved a plan keeps it (a resume must not change
    models), as does every step a saved plan still covers. Missing steps are
    decided from the durable rotation offset. `custom` asks the operator to
    pick each stage's slot from that stage's installed options. The `changed`
    flag is False when the saved plan already says exactly this, so the caller
    leaves the file untouched. Nothing is written here: the caller saves the
    plan once, after --fresh has archived the previous run dir.
    """
    ensure_harness_path()
    saved = None if fresh else load_harness_plan(run)
    if offsets is None:
        offsets = plan_offsets(run, resumed)
    plan = decide_harness_plan(run, saved=saved, offsets=offsets, lookup=lookup)
    if custom:
        prompt_harness_plan(run, plan)
    changed = (saved is None
               or saved.get("steps") != plan["steps"]
               or saved.get("source") != plan["source"]
               or saved.get("rotation_key") != plan["rotation_key"]
               or saved.get("pipeline") != plan["pipeline"])
    return plan, changed


def load_harness_plan(run):
    """The run's saved harness map, or None when it has none yet.

    Fail-closed like the rotation file: a present but unusable plan must not
    fall back to a fresh decision, because that would switch a stage's model
    in the middle of a run. Repair by deleting the file (the next run replans)
    or with --fresh.
    """
    path = plan_path(run)
    if path is None:
        return None
    try:
        raw = path.read_text()
    except FileNotFoundError:
        return None
    except OSError as e:
        raise Fail(f"plan: {path.name} unreadable ({e}); delete it to replan "
                   f"this run, or use --fresh") from e
    try:
        data = json.loads(raw)
    except ValueError as e:
        raise Fail(f"plan: {path.name} does not parse ({e}); delete it to "
                   f"replan this run, or use --fresh") from e
    if (not isinstance(data, dict) or data.get("version") != PLAN_VERSION
            or not isinstance(data.get("steps"), dict)):
        raise Fail(f"plan: {path.name} has an unusable shape (expected "
                   f"version {PLAN_VERSION} and a steps mapping); delete it "
                   f"to replan this run, or use --fresh")
    return data


def save_harness_plan(run, plan):
    """Persist the run's harness map. Called once, before the job starts.

    A write failure fails the run: the plan names the model for every stage,
    so an unsaved plan must not start the job.
    """
    path = plan_path(run)
    if path is None:
        raise Fail("plan: the run has no run directory to save the harness "
                   "map into")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        write_json_atomic(path, plan)
    except (Fail, OSError) as e:
        raise Fail(f"plan: cannot write {path.name} ({e})") from e


def _completed_harnesses(run):
    """step -> harness for every step ledger.json already proves complete."""
    try:
        ledger = run._ledger()
    except Fail:
        return {}
    steps = ledger.get("steps") if isinstance(ledger, dict) else None
    if not isinstance(steps, dict):
        return {}
    return {sid: entry["harness"] for sid, entry in steps.items()
            if isinstance(entry, dict) and isinstance(entry.get("harness"), str)
            and entry["harness"]}


def _read_choice(prompt):
    """One answer from the operator's terminal (prompt on stderr, read stdin).

    stdout stays machine-readable JSON. EOF is refused rather than treated as
    the default: a plan nobody answered must not start a run.
    """
    sys.stderr.write(prompt)
    sys.stderr.flush()
    line = sys.stdin.readline()
    if line == "":
        raise Fail("--customize-harness: stdin closed before the harness plan "
                   "was confirmed; nothing was started")
    return line.strip()


def _apply_plan_choice(entry, index, selected_by):
    """Point one plan entry at an option and keep its rotation counters sound.

    An operator pick advances the rotation past the chosen slot and records no
    availability skip: the choice was made, not forced by a missing binary.
    """
    option = entry["options"][index]
    entry["index"] = index
    entry["harness"] = option["harness"]
    entry["display"] = option["display"]
    entry["offset"] = index
    entry["next_count"] = index + 1
    entry["skipped"] = []
    entry["selected_by"] = selected_by


def _resolve_plan_answer(answer, entry):
    """Map one typed answer to an option index plus a complaint.

    Returns (None, "") when the operator aborted. The option number, the
    harness id, and the display name are all accepted, so the operator can type
    whichever they can see; an empty answer keeps the current choice.
    """
    if answer.lower() in ("q", "quit", "abort"):
        return None, ""
    options = entry["options"]
    if not answer:
        return entry["index"], ""
    if answer.isdigit() and 1 <= int(answer) <= len(options):
        index = int(answer) - 1
    else:
        index = next((i for i, o in enumerate(options)
                      if answer in (o["harness"], o["display"])), -1)
        if index < 0:
            return index, f"{answer!r} is not one of the options"
    if not options[index]["available"]:
        return index, (f"option {index + 1} is not installed: "
                       f"{options[index]['binary']} is not on PATH")
    return index, ""


def _choose_plan_step(run, plan, sid, entry, locked_harness=None):
    """Show one stage's options and record the operator's choice."""
    print(f"\n  stage {sid} [{entry['stage']}] "
          f"({entry.get('record_as', entry.get('name', sid))})",
          file=sys.stderr)
    if locked_harness:
        # The ledger is the authority for a completed step: its harness is part
        # of the completion record, so re-planning cannot rewrite it.
        entry["harness"] = locked_harness
        entry["display"] = display_name(locked_harness)
        entry["locked"] = True
        entry["selected_by"] = "ledger"
        print(f"    already completed as {entry['display']} "
              f"[{locked_harness}] - kept from ledger.json", file=sys.stderr)
        return
    entry.pop("locked", None)
    for number, option in enumerate(entry["options"], 1):
        state = ("available" if option["available"]
                 else f"MISSING binary: {option['binary']} not on PATH")
        print(f"    {number}) {option['display']} [{option['harness']}] "
              f"- {state}", file=sys.stderr)
    options = entry["options"]
    installed = [i for i, o in enumerate(options) if o["available"]]
    if not installed:
        # plan_entry already halted on this; never reached with a saved plan.
        raise HarnessUnavailable(sid, [o["harness"] for o in options])
    if len(installed) == 1:
        _apply_plan_choice(entry, installed[0], "operator")
        print(f"    only installed option; using it without asking",
              file=sys.stderr)
        return
    while True:
        answer = _read_choice(f"    choose 1-{len(options)} (Enter keeps "
                              f"{entry['index'] + 1}, q aborts): ")
        index, complaint = _resolve_plan_answer(answer, entry)
        if index is None:
            raise Aborted(f"operator aborted the harness choice for stage {sid}")
        if complaint:
            print(f"    {complaint}", file=sys.stderr)
            continue
        _apply_plan_choice(entry, index, "operator")
        return


def prompt_harness_plan(run, plan, isatty=None):
    """Let the operator choose the harness for every stage, then confirm.

    Only the options the stage itself declares are offered, and only the ones
    whose CLI is installed: a plan picks this run's rotation slot, it never
    invents a harness id (stage files own those, with their display names and
    effort checks). A stage the ledger already completed is shown and kept.
    The whole map is printed and confirmed before the job starts, and
    declining starts nothing. `isatty` is injectable so the prompt is
    testable; it defaults to the real terminal check, because a piped run
    must fail rather than wait for a keystroke that will never come.
    """
    has_terminal = sys.stdin.isatty() if isatty is None else bool(isatty)
    if not has_terminal:
        raise Fail("--customize-harness needs an interactive terminal (stdin "
                   "is not a tty); run it from the operator terminal")
    locked = _completed_harnesses(run)
    print("runner: choosing one harness per stage for this run", file=sys.stderr)
    for sid, entry in plan["steps"].items():
        _choose_plan_step(run, plan, sid, entry, locked.get(sid))
    print("\nrunner: harness plan for this run", file=sys.stderr)
    for sid, entry in plan["steps"].items():
        print(f"    {sid} -> {entry['display']} [{entry['harness']}]",
              file=sys.stderr)
    answer = _read_choice("  start the run with this plan? [y/N] ")
    if answer.lower() not in ("y", "yes"):
        raise Aborted(f"operator declined the harness plan (answered {answer!r})")
    plan["source"] = "custom"
    plan["confirmed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return plan


def render_plan(plan, path=None):
    """One line per stage, with the availability skips named."""
    lines = [f"harness plan for {plan.get('run_id') or 'this run'} "
             f"(source: {plan.get('source', 'auto')})"]
    for sid, entry in plan["steps"].items():
        lines.append(f"  {sid}: {entry['harness']} ({entry['display']})")
        for skipped in entry.get("skipped", []):
            lines.append(f"      skipped {skipped['harness']}: "
                         f"{skipped['missing_binary']} not on PATH")
    if path is not None:
        lines.append(f"  saved: {path}")
    return "\n".join(lines)


def opencode_launch(model, effort, pointer, stage_name=OPENCODE_AGENT):
    """Build the opencode full-TUI launch command and environment.

    Full TUI (not `opencode run`) so the session stays open until the stage
    emits its final signal; the runner watches the pty capture and closes it
    once the signal is stable (v1 behavior). `opencode run` exits when the
    session goes idle, which drops the signal whenever an agent pauses (for
    example while a background worker runs). The v2 root TUI has no
    --model/--agent flags, so the model and the stage's reasoning effort
    (variant) are injected through OPENCODE_CONFIG_CONTENT: the root `model`
    carries provider/model, and an effort adds a default primary agent whose
    model selector is `provider/model#variant`. --standalone gives the TUI its
    own server so it reads that injected config; without it the TUI attaches
    to the shared background service and ignores it. --auto auto-approves
    permissions (mandated by the stages). Returns (cmd, env)."""
    cmd = ["opencode", "--standalone", "--auto", "--prompt", pointer]
    env = dict(os.environ)
    cfg = {}
    if model != "auto":
        cfg["model"] = model
        if effort:
            cfg["default_agent"] = stage_name
            cfg["agents"] = {
                stage_name: {"mode": "primary",
                             "model": f"{model}#{effort}"}}
    if cfg:
        env["OPENCODE_CONFIG_CONTENT"] = json.dumps(cfg)
    return cmd, env

TOP_KEYS = {"version", "run_dir", "inputs", "start",
            "ends", "steps"}
STEP_KEYS = {"stage", "record_as", "bindings", "when", "end",
             "require_file", "skip_when_empty", "snapshot", "max_rounds",
             "on_exhausted"}
SOURCE_KEYS = {"output", "task", "join", "prev_output"}
STAGE_KEYS = {"name", "harness", "harness_names", "placeholders",
              "description", "role"}
KNOWN_CLIS = {"cursor", "agy", "hermes", "opencode", "cmd"}

# Provider aliases, resolved per CLI before invoking. `go` under the
# opencode CLI always means the installed `opencode-go` provider, and
# `together` always means `togetherai`, so stage files can write the
# short forms (opencode:go/..., opencode:together/...).
OPENCODE_PROVIDER_ALIASES = {"go": "opencode-go", "together": "togetherai"}


def resolve_provider(cli, provider):
    if cli == "opencode" and provider in OPENCODE_PROVIDER_ALIASES:
        return OPENCODE_PROVIDER_ALIASES[provider]
    return provider


# Model aliases, keyed by RESOLVED provider: each registry names the same
# model its own way (Together: 'zai-org/GLM-5.3-Flash' and
# 'deepseek-ai/DeepSeek-V4.1-Flash'; OpenRouter: 'deepseek/...' prefix;
# opencode-go: bare lowercase slugs), so one global mapping would send the
# wrong slug to at least one provider. Missing entries are identity: the
# model part is already the full slug.
OPENCODE_MODEL_ALIASES = {
    ("togetherai", "glm-5.3-flash"): "zai-org/GLM-5.3-Flash",
    ("togetherai", "deepseek-v4.1-flash"): "deepseek-ai/DeepSeek-V4.1-Flash",
    ("openrouter", "deepseek-v4.1-flash"): "deepseek/deepseek-v4.1-flash",
}


def resolve_model(cli, provider, model):
    if cli == "opencode":
        return OPENCODE_MODEL_ALIASES.get((provider, model), model)
    return model


# Command Code (`cmd`) runs in its interactive form, with the task pointer as
# the positional initial message. Headless `-p` ends when the turn ends, which
# would drop the signal whenever an agent pauses (the same reason opencode uses
# its full TUI). --trust skips the project trust prompt, --yolo auto-approves
# permissions (the stages mandate unattended tool use, and the idle reminder is
# only safe to type when no approval dialog can appear), and --skip-onboarding
# is for automated runs. Stage entries carry native catalog model ids only:
# opencode's provider and model aliases never apply here, and a BYOK custom
# provider id must not appear in a stage file.
CMD_BINARY = "cmd"
CMD_PROBE_TIMEOUT_S = 120
# `cmd -p` with local-only forced resolves one (model, effort) pair exactly as
# a real invocation does and then refuses the transport, so the check sends
# nothing, starts no session, and costs nothing. A resolved pair prints the
# refusal; a rejected pair prints its rejection instead (see cmd_probe_problem).
CMD_LOCAL_ONLY_REFUSAL = "local-only mode"
CMD_PROBE_REJECTIONS = ("unknown model", "has no adjustable reasoning effort",
                        'unknown effort "')
# Model rows in `cmd --list-models`: an id column padded to the description.
# Section headings ("Open Source") have a single space, so they do not match.
CMD_ROW_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._:/+-]*)\s{2,}\S")
# Self-test probe targets: the CLI's default model (always listed and carries
# efforts), an id no catalog serves, an effort level the CLI never accepts,
# and a listed model with no adjustable effort at all.
CMD_PROBE_MODEL = "deepseek/deepseek-v4-flash"
CMD_UNKNOWN_MODEL = "bogus/not-a-real-model"
CMD_UNKNOWN_EFFORT = "ultra"
CMD_NO_EFFORT_MODEL = "poolside/laguna-s-2.1-free"


def cmd_launch(model, effort, pointer):
    """Build the interactive Command Code launch command.

    The pointer is the positional initial message, so it must come last."""
    cmd = [CMD_BINARY, "--trust", "--yolo", "--skip-onboarding", "-m", model]
    if effort:
        cmd += ["--effort", effort]
    cmd.append(pointer)
    return cmd


# Availability for the skip is binary presence only: the CLI word a harness
# id names, mapped to the executable `shutil.which` must find. Model-catalog
# and effort checks stay where they are today (self-test and the cmd
# invoke-time probe); a catalog command that is itself unavailable never
# marks a harness unavailable here.
HARNESS_BINARIES = {"cursor": "agent", "agy": "agy", "hermes": "hermes",
                    "opencode": "opencode", "cmd": CMD_BINARY}


def binary_for(harness):
    """The CLI executable a harness id invokes ('cursor' is `agent`)."""
    cli = harness.split(":", 1)[0]
    return HARNESS_BINARIES.get(cli, cli)


def is_harness_available(harness, lookup=shutil.which):
    """True when the harness's CLI binary is on PATH.

    `lookup` is injectable so the selection logic can be pinned without a
    real PATH. Availability deliberately ignores the model and effort: the
    CLI reports a bad pair itself (the cmd invoke-time probe fails closed),
    and that stays a hard config error rather than a silent skip.
    """
    return bool(lookup(binary_for(harness)))


def select_harness(harnesses, count, lookup=shutil.which):
    """Pick the first available harness from the rotation offset, wrapping.

    Returns the index of the first entry whose binary is on PATH, or None
    when every entry is missing one. Order is preserved from the offset; the
    caller consumes the slot past the skips so the next run does not retry a
    known-missing head.
    """
    n = len(harnesses)
    for step in range(n):
        idx = (count + step) % n
        if is_harness_available(harnesses[idx], lookup):
            return idx
    return None


def ensure_harness_path():
    """Add the harness install dirs to PATH (idempotent).

    Applied before the availability check and before every invocation so the
    skip sees the same PATH the harness would run under.
    """
    home = str(Path.home())
    prefix = f"{home}/.local/bin:{home}/.opencode/bin"
    os.environ["PATH"] = f"{prefix}:{os.environ['PATH']}"


def _first_text_line(text, limit=200):
    for line in (text or "").splitlines():
        if line.strip():
            return line.strip()[:limit]
    return ""


_CMD_PROBE_CACHE = {}


def cmd_probe_problem(model, effort):
    """Return the Command Code CLI's own rejection of one (model, effort) pair.

    Returns the CLI's rejection line, or None when the pair resolves or the
    probe is inconclusive. An inconclusive probe cannot let a bad pair through:
    the CLI refuses an unknown model and an unsupported effort itself, before
    any inference, so nothing is spent and no session starts either way.
    Cached per pair: a remedy loop re-invokes the same step, and the pair
    cannot change mid-run.
    """
    key = (model, effort)
    if key not in _CMD_PROBE_CACHE:
        _CMD_PROBE_CACHE[key] = _cmd_probe(model, effort)
    return _CMD_PROBE_CACHE[key]


def _cmd_probe(model, effort):
    probe = [CMD_BINARY, "-p", "--no-session", "-m", model]
    if effort:
        probe += ["--effort", effort]
    probe.append("Reply with exactly: SELFTEST_OK")
    env = dict(os.environ, CMD_LOCAL_ONLY="1")
    try:
        result = subprocess.run(probe, capture_output=True, text=True,
                                timeout=CMD_PROBE_TIMEOUT_S, env=env)
    except (OSError, subprocess.TimeoutExpired):
        return None
    out = f"{result.stdout}\n{result.stderr}"
    low = out.lower()
    if CMD_LOCAL_ONLY_REFUSAL in low:
        return None
    for marker in CMD_PROBE_REJECTIONS:
        if marker in low:
            return _first_text_line(out)
    return None


def cmd_catalog_ids(text):
    """Model ids from one `cmd --list-models` listing, lowercased.

    Model rows pad the id column; headings switch sections. The listing
    lowercases ids while the catalog spells some of them mixed-case
    (`zai-org/GLM-5.3`); the CLI accepts either spelling, so ids are compared
    case-insensitively. Decision models are listed under a "(headless only)"
    heading and are excluded: an interactive stage entry naming one would be
    refused at launch, so it must not validate here.
    """
    ids, headless_only = set(), False
    for line in (text or "").splitlines():
        if "·" in line:              # header: "Available models · N models"
            continue
        match = CMD_ROW_RE.match(line)
        if match:
            model_id = match.group(1)
            if not model_id.endswith(":") and not headless_only:
                ids.add(model_id.lower())
            continue
        stripped = line.strip()
        if stripped:
            headless_only = "headless only" in stripped.lower()
    return ids


def cmd_catalog_models():
    """Return the ids `cmd --list-models` advertises.

    None when the catalog command itself is unavailable, which self-test
    reports as skipped rather than failed.
    """
    try:
        result = subprocess.run([CMD_BINARY, "--list-models"],
                                capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return cmd_catalog_ids(result.stdout)


def cmd_catalog_check(model, effort):
    """Static, spend-free catalog check for one `cmd` model (and effort).

    Returns (ok, detail): True when the model is listed and the effort
    resolves, False when the CLI rejects either, None when the catalog command
    itself is unavailable (reported as skipped, not failed)."""
    models = cmd_catalog_models()
    if not models:
        return None, "cmd model catalog unavailable"
    problem = cmd_probe_problem(model, effort)
    if problem:
        return False, problem
    if model.lower() not in models:
        return False, f"{model} not in cmd --list-models"
    return True, "slug in cmd --list-models" + (
        " + effort resolves" if effort else "")


class Fail(Exception):
    pass


class HarnessUnavailable(Fail):
    """No harness for a step has its CLI binary on PATH (fail-closed halt)."""

    def __init__(self, step, harnesses):
        self.step = step
        self.harnesses = harnesses
        listing = ", ".join(f"{h} ({binary_for(h)})" for h in harnesses)
        super().__init__(
            f"step {step}: no harness is available (all listed CLIs are "
            f"missing from PATH): {listing}")


class Aborted(Fail):
    """The operator declined the harness plan; nothing was started."""


def load_stage(path):
    text = path.read_text()
    parts = text.split("---", 2)
    if len(parts) < 3 or not parts[0].strip() == "":
        raise Fail(f"{path}: missing frontmatter delimited by ---")
    meta = yaml.safe_load(parts[1])
    if not isinstance(meta, dict):
        raise Fail(f"{path}: frontmatter is not a mapping")
    for k in meta:
        if k not in STAGE_KEYS:
            raise Fail(f"{path}: unknown stage key {k!r}")
    for k in ("name", "harness", "placeholders"):
        if k not in meta:
            raise Fail(f"{path}: stage missing {k!r}")
    hs = meta["harness"] if isinstance(meta["harness"], list) else [meta["harness"]]
    if not hs or not all(isinstance(h, str) and HARNESS_RE.fullmatch(h) for h in hs):
        raise Fail(f"{path}: harness must be '<cli>:<provider>/<model>[@<effort>]' "
                   f"(provider and effort optional) or a list of them")
    for h in hs:
        if h.split(":", 1)[0] not in KNOWN_CLIS:
            raise Fail(f"{path}: unknown harness cli in {h!r}")
        parse_harness(h)
    names = meta.get("harness_names", {})
    if not isinstance(names, dict):
        raise Fail(f"{path}: harness_names must be a mapping")
    if not names:
        raise Fail(f"{path}: missing harness_names; every harness id needs "
                   f"its display name beside the harness list")
    for h in hs:
        if h not in names:
            raise Fail(f"{path}: harness {h!r} has no display name in this "
                       f"file's harness_names; add it beside the harness list")
    HARNESS_DISPLAY.update(names)
    if not isinstance(meta["placeholders"], dict):
        raise Fail(f"{path}: placeholders must be a mapping")
    return meta, parts[2]


def validate(pipe, pipe_dir):
    if not isinstance(pipe, dict):
        raise Fail("pipeline is not a mapping")
    if pipe.get("version") != 1:
        raise Fail(f"unsupported pipeline version {pipe.get('version')!r} (runner handles 1)")
    for k in pipe:
        if k not in TOP_KEYS:
            raise Fail(f"unknown pipeline key {k!r}")
    for k in ("run_dir", "inputs", "start", "ends", "steps"):
        if k not in pipe:
            raise Fail(f"pipeline missing {k!r}")
    if not isinstance(pipe["inputs"], dict) or not isinstance(pipe["steps"], dict):
        raise Fail("pipeline inputs and steps must be mappings")
    steps = pipe["steps"]
    if pipe["start"] not in steps:
        raise Fail(f"start {pipe['start']!r} resolves to no step")
    for e in pipe["ends"]:
        if e in steps:
            raise Fail(f"end state {e!r} collides with a step id")
    for sid, s in steps.items():
        for k in s:
            if k not in STEP_KEYS:
                raise Fail(f"step {sid}: unknown key {k!r}")
        for k in ("stage", "record_as", "bindings"):
            if k not in s:
                raise Fail(f"step {sid}: missing {k!r}")
        if bool("when" in s) == bool("end" in s):
            raise Fail(f"step {sid}: needs exactly one of when/end")
        if "end" in s and s["end"] not in pipe["ends"]:
            raise Fail(f"step {sid}: end {s['end']!r} not in ends")
        if "when" in s:
            if not isinstance(s["when"], dict) or not s["when"]:
                raise Fail(f"step {sid}: when must be a non-empty mapping")
            for sig, tgt in s["when"].items():
                if tgt not in steps and tgt not in pipe["ends"]:
                    raise Fail(f"step {sid}: edge target {tgt!r} resolves nowhere")
        for tgt_key in ("skip_when_empty", "on_exhausted"):
            if tgt_key in s:
                tgt = s[tgt_key]
                if tgt not in steps and tgt not in pipe["ends"]:
                    raise Fail(f"step {sid}: {tgt_key} {tgt!r} resolves nowhere")
        if "max_rounds" in s and (not isinstance(s["max_rounds"], int) or s["max_rounds"] <= 0):
            raise Fail(f"step {sid}: max_rounds must be a positive int")
        if not isinstance(s["bindings"], dict):
            raise Fail(f"step {sid}: bindings must be a mapping")
        stage_path = (pipe_dir / s["stage"]).resolve()
        if not stage_path.is_file():
            raise Fail(f"step {sid}: stage file missing: {stage_path}")
        meta, body = load_stage(stage_path)
        declared = set(meta["placeholders"])
        bound = set(s["bindings"])
        # {{harness}} is runner-provided, resolved per invocation from the
        # stage frontmatter list: never declared, never bound.
        if "harness" in bound or "harness" in declared:
            raise Fail(f"step {sid}: harness is runner-provided, "
                       f"not a placeholder or pipeline binding")
        if declared - bound:
            raise Fail(f"step {sid}: unbound placeholders {sorted(declared - bound)}")
        if bound - declared:
            raise Fail(f"step {sid}: bindings for undeclared {sorted(bound - declared)}")
        used = set(TOKEN_RE.findall(body))
        if used - declared - {"harness"}:
            raise Fail(f"step {sid}: body tokens not in placeholders {sorted(used - declared - {'harness'})}")
        for name, src in s["bindings"].items():
            check_source(sid, name, src, steps)
        if "snapshot" in s and set(s["snapshot"]) != {"from", "to"}:
            raise Fail(f"step {sid}: snapshot needs exactly from/to")


def check_source(sid, name, src, steps):
    if isinstance(src, str):
        return
    kinds = [k for k in SOURCE_KEYS if k in src]
    if not isinstance(src, dict) or len(kinds) != 1 \
            or set(src) - SOURCE_KEYS - {"sep"} \
            or ("sep" in src and "join" not in src):
        raise Fail(f"step {sid}: binding {name!r} has unknown source {src!r}")
    if "output" in src and src["output"] not in steps:
        raise Fail(f"step {sid}: binding {name!r} output step resolves nowhere")
    if "task" in src and src["task"] not in steps:
        raise Fail(f"step {sid}: binding {name!r} task step resolves nowhere")
    if "join" in src:
        if not isinstance(src["join"], list) or not src["join"]:
            raise Fail(f"step {sid}: binding {name!r} join needs a non-empty list")
        if "sep" in src and not isinstance(src["sep"], str):
            raise Fail(f"step {sid}: binding {name!r} sep must be a string")
        for sub in src["join"]:
            check_source(sid, name, sub, steps)


class Run:
    def __init__(self, pipe, pipe_dir, repo, inputs):
        self.pipe = pipe
        self.pipe_dir = pipe_dir
        self.repo = repo
        self.inputs = inputs
        self.steps = pipe["steps"]
        self.outputs = {}
        self.visits = {}
        self.harness_use = {}
        # The run's harness map (harnesses.json). main() decides it before the
        # job starts and saves it; a caller that drives a Run directly gets the
        # same map built in memory by ensure_plan().
        self.plan = None
        self.persist_rotation = True
        self.rotation_key = None
        # Set by main(); recorded in the saved plan, never load-bearing.
        self.pipe_path = None
        self.prev_step = None
        # Use a completed ledger entry for prior steps whenever one exists.
        # The dry-run path explicitly disables this for planned previews.
        self.require_authoritative = True
        self.stages = {}
        for sid, s in self.steps.items():
            meta, body = load_stage((pipe_dir / s["stage"]).resolve())
            self.stages[sid] = (meta, body)

    def ctx(self, sid):
        s = self.steps[sid]
        max_rounds = s.get("max_rounds", self.inputs.get("max_remedy_rounds", 1))
        return dict(self.inputs, phase=int(self.inputs["phase_number"]),
                    run_id=f"{self.inputs.get('run_label', 'phase')}-{int(self.inputs['phase_number']):06d}",
                    run_dir=str(self.run_dir),
                    agent=sid, round=self.visits.get(sid, 1), rounds=max_rounds)

    @property
    def run_dir(self):
        return self._run_dir

    def resolve(self, sid, src, ctx, seen):
        if isinstance(src, str):
            try:
                return src.format(**ctx)
            except (KeyError, ValueError, IndexError) as e:
                raise Fail(f"step {sid}: binding {src!r} formats badly ({e})")
        if "output" in src:
            return self.outputs.get(src["output"], "")
        if "prev_output" in src:
            return self.outputs.get(self.prev_step, "") if self.prev_step else ""
        if "task" in src:
            # A completed step is attributed to its authoritative task
            # snapshot, not to the first rotation slot. The snapshot file
            # named by the ledger is the exact prompt the successful agent
            # saw; re-rendering the current stage template could inject a
            # mutated stage or a different model name.
            source_sid = src["task"]
            if source_sid in seen:
                raise Fail(f"task reference cycle at step {source_sid}")
            attempt = (self.authoritative_attempt(source_sid)
                       if self.require_authoritative else None)
            if attempt is not None:
                task_rel = attempt.get("task_file")
                if not isinstance(task_rel, str) or not task_rel:
                    raise Fail(f"ledger.json entry for {source_sid!r} has no task file")
                run_dir = Path(self._run_dir).resolve()
                candidate = Path(task_rel)
                if not candidate.is_absolute():
                    candidate = run_dir / candidate
                try:
                    task_path = candidate.resolve()
                    task_path.relative_to(run_dir)
                except (OSError, ValueError, RuntimeError) as exc:
                    raise Fail(f"ledger.json task file for {source_sid!r} escapes "
                               f"the run directory") from exc
                try:
                    content = task_path.read_text()
                except OSError as exc:
                    raise Fail(f"authoritative task for {source_sid!r} unreadable: "
                               f"{exc}") from exc
                expected_sha = attempt.get("task_sha256")
                if isinstance(expected_sha, str) and expected_sha:
                    if sha_str(content) != expected_sha:
                        raise Fail(f"authoritative task for {source_sid!r} changed since "
                                   f"completion; refusing to use a tampered snapshot")
                # Stale nonces must never be reusable as signal tokens.
                return strip_nonce_footer(content)
            if self.require_authoritative and source_sid in self.outputs:
                raise Fail(
                    f"task reference {source_sid!r} has output but no valid "
                    "ledger entry; refusing to guess its harness")
            source_harness = self.preview_harness(source_sid)
            return self.render_task(
                source_sid, seen | {sid},
                harness_name=display_name(source_harness),
                include_authority=False)
        subs = [self.resolve(sid, sub, ctx, seen) for sub in src["join"]]
        return src.get("sep", "\n\n").join(subs)

    def render_task(self, sid, seen=..., harness_name=None,
                    include_authority=True):
        if seen is ...:
            seen = {sid}
        elif sid in seen:
            raise Fail(f"task reference cycle at step {sid}")
        meta, body = self.stages[sid]
        s = self.steps[sid]
        sub = dict(self.ctx(sid), agent=sid,
                   round=self.visits.get(sid, 1))
        values = {n: self.resolve(sid, src, sub, seen | {sid})
                  for n, src in s["bindings"].items()}
        # {{harness}} always resolves: the actual invocation name when
        # given, else this step's planned name. Never a pipeline binding.
        values["harness"] = (harness_name if harness_name is not None
                             else display_name(self.preview_harness(sid)))

        def sub_token(m):
            tok = m.group(1)
            if tok not in values:
                raise Fail(f"step {sid}: unbound body token {tok!r}")
            return values[tok]

        rendered = TOKEN_RE.sub(sub_token, body)
        return (ATTEMPT_AUTHORITY + "\n\n" + rendered
                if include_authority else rendered)

    def _ledger(self):
        """Read and validate the run ledger when it exists.

        The ledger is deliberately fail-closed: malformed completion data
        must not silently fall back to a planned model, because that would
        recreate the attribution confusion this runner is meant to prevent.
        """
        run_dir = getattr(self, "_run_dir", None)
        if run_dir is None:
            return None
        path = Path(run_dir) / "ledger.json"
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError) as exc:
            raise Fail(f"ledger.json cannot be read: {path} ({exc})") from exc
        if (not isinstance(data, dict)
                or not isinstance(data.get("order"), list)
                or not isinstance(data.get("steps"), dict)):
            raise Fail(f"ledger.json has an invalid shape: {path}")
        return data

    def authoritative_attempt(self, sid):
        """Return the validated completion record for *sid*, if any.

        New entries carry task_file, task_sha256, and authoritative=True.
        Legacy entries without those fields are migrated deterministically
        when unambiguous; ambiguous legacy state fails closed with an
        explicit recovery command.
        """
        ledger = self._ledger()
        if ledger is None:
            return None
        entry = ledger["steps"].get(sid)
        if entry is None:
            return None
        if not isinstance(entry, dict):
            raise Fail(f"ledger.json entry for {sid!r} is not an object")
        needs_migration = (
            entry.get("authoritative") is not True
            or "task_file" not in entry
            or "task_sha256" not in entry)
        if needs_migration:
            return self._migrate_legacy_entry(sid, ledger, entry)
        authoritative = entry.get("authoritative", False)
        if authoritative is not True and "authoritative" in entry:
            raise Fail(f"ledger.json entry for {sid!r} is not authoritative")
        harness = entry.get("harness")
        if not isinstance(harness, str) or not harness:
            raise Fail(f"ledger.json entry for {sid!r} has no valid harness")
        signal = entry.get("signal")
        if "signal" in entry and (not isinstance(signal, str) or not signal):
            raise Fail(f"ledger.json entry for {sid!r} has no valid signal")
        if authoritative is True and "signal" not in entry:
            raise Fail(f"ledger.json entry for {sid!r} has no valid signal")
        agent = entry.get("agent")
        if authoritative is True and agent != display_name(harness):
            raise Fail(
                f"ledger.json harness and agent disagree for {sid!r}")
        try:
            _cli, _provider, _model, _effort = parse_harness(harness)
        except (Fail, ValueError) as exc:
            raise Fail(
                f"ledger.json entry for {sid!r} has an invalid harness "
                f"{harness!r}") from exc
        # Older private run ledgers may contain harness identifiers from a
        # retired CLI. Keep their displayable raw identifier usable for
        # forensic context; current invocations are still restricted by
        # pipeline validation.
        task_file = entry.get("task_file")
        if task_file is not None:
            if not isinstance(task_file, str) or not task_file:
                raise Fail(f"ledger.json entry for {sid!r} has an invalid task_file")
            run_dir = Path(self._run_dir).resolve()
            try:
                task_candidate = Path(task_file)
                if not task_candidate.is_absolute():
                    task_candidate = run_dir / task_candidate
                task_path = task_candidate.resolve()
                task_path.relative_to(run_dir)
            except (OSError, ValueError, RuntimeError) as exc:
                raise Fail(
                    f"ledger.json task_file for {sid!r} escapes the run directory"
                ) from exc
            if not task_path.is_file():
                raise Fail(
                    f"ledger.json task_file for {sid!r} is missing: {task_path}")
            if (not task_path.name.startswith(f"{sid}-task-r")
                    or not task_path.name.endswith(".md")):
                raise Fail(
                    f"ledger.json task_file for {sid!r} has the wrong name")
            task_sha = entry.get("task_sha256")
            if not isinstance(task_sha, str) or not task_sha:
                raise Fail(f"ledger.json entry for {sid!r} has no task hash")
            try:
                actual_sha = sha_file(task_path)
            except OSError as exc:
                raise Fail(f"ledger.json task file unreadable for {sid!r}: {exc}") from exc
            if actual_sha != task_sha:
                raise Fail(f"ledger.json task file for {sid!r} changed since completion "
                           f"(expected {task_sha[:12]}, got {actual_sha[:12]}); "
                           f"the authoritative snapshot no longer matches")
        superseded = entry.get("superseded_task_files", [])
        if not isinstance(superseded, list) or not all(
                isinstance(item, str) for item in superseded):
            raise Fail(
                f"ledger.json entry for {sid!r} has invalid superseded task files")
        return entry

    def _migrate_legacy_entry(self, sid, ledger, entry, persist=False):
        """Backfill task_file/task hash for pre-authority ledger entries.

        Deterministic cases (visits points at an existing task file, or a
        single task file exists) are migrated. Ambiguous cases fail closed
        with the exact recovery command. Persistence is explicit: read-only
        contexts must never mutate run state, so only live resume and
        --migrate-ledger pass persist=True.
        """
        run_dir = Path(self._run_dir).resolve()
        candidates = sorted(
            run_relative_path(self, p)
            for p in Path(self._run_dir).glob(f"{sid}-task-r*.md")
            if "-resume-" not in p.name)
        if not candidates:
            raise Fail(f"ledger.json entry for {sid!r} has no task file and no "
                       f"task candidates exist; recover with "
                       f"--mark-done {sid} SIGNAL or re-run the step")
        visits = entry.get("visits")
        chosen = None
        if isinstance(visits, int) and visits >= 1:
            wanted = f"{sid}-task-r{visits}.md"
            if wanted in candidates:
                chosen = wanted
        if chosen is None and len(candidates) == 1:
            chosen = candidates[0]
        if chosen is None:
            raise Fail(f"ledger.json entry for {sid!r} is ambiguous: "
                       f"{len(candidates)} task candidates {candidates}; "
                       f"run with --migrate-ledger to review, or recover with "
                       f"--mark-done {sid} SIGNAL")
        task_path = (run_dir / chosen) if not Path(chosen).is_absolute() else Path(chosen)
        try:
            task_sha = sha_file(task_path.resolve())
        except OSError as exc:
            raise Fail(f"ledger.json migration for {sid!r} cannot read {chosen} ({exc})") from exc
        # Preserve existing fields, add authority fields. Do not invent a
        # stage hash for legacy runs; record that migration was post-hoc.
        migrated = dict(entry)
        migrated["task_file"] = chosen
        migrated["task_sha256"] = task_sha
        migrated["authoritative"] = True
        migrated["migrated_legacy"] = True
        if "agent" not in migrated or not migrated.get("agent"):
            try:
                migrated["agent"] = display_name(migrated.get("harness", ""))
            except Exception:  # noqa: BLE001 - display fallback is best-effort
                pass
        if "superseded_task_files" not in migrated:
            migrated["superseded_task_files"] = [c for c in candidates if c != chosen]
        stage_sha = stage_fingerprint(self, sid)
        if stage_sha is not None:
            migrated["stage_sha256"] = stage_sha
            migrated["stage_migrated_posthoc"] = True
        ledger["steps"][sid] = migrated
        if persist:
            try:
                write_json_atomic(Path(self._run_dir) / "ledger.json", ledger)
            except Fail as exc:
                raise Fail(f"ledger.json migration for {sid!r} cannot persist ({exc})") from exc
        return migrated

    def harnesses(self, sid):
        """The stage's declared harness list, normalized to a list."""
        meta, _ = self.stages[sid]
        hs = meta["harness"]
        return hs if isinstance(hs, list) else [hs]

    def planned_harness(self, sid):
        """Return the first rotation slot for previews without completion data."""
        return self.harnesses(sid)[0]

    def ensure_plan(self, offsets=None):
        """The run's harness map, built in memory on first use.

        main() decides the map before the job starts and saves it to
        <run_dir>/harnesses.json. A caller that drives a Run directly (the
        hermetic checks) gets the same map here, decided once for the whole run
        from the rotation offsets already loaded onto harness_use.
        """
        if self.plan is None:
            self.plan, _changed = plan_harnesses(
                self, offsets=offsets if offsets is not None
                else dict(self.harness_use))
        return self.plan

    def preview_harness(self, sid):
        """The harness a preview names: the planned one once a plan is loaded.

        Without a plan this falls back to the stage's first declared slot, so
        a preview never depends on live availability.
        """
        entry = (self.plan or {}).get("steps", {}).get(sid)
        return entry["harness"] if entry else self.planned_harness(sid)

    def harness_for(self, sid):
        """Peek the step's planned harness without consuming anything.

        Used for attribution of an already-finished step (--mark-done), so it
        reports the planned map rather than probing the live PATH: a saved
        plan is what the run decided, and drive() invokes from that same map.
        Without a plan it reads the recorded offset, exactly as before. A slot
        is consumed only after a signal and all completion gates pass, so
        interrupted, blocked, and otherwise failed attempts retry the same
        harness; the visits counter still increments so each attempt gets a
        distinct forensic task/log file.
        """
        entry = (self.plan or {}).get("steps", {}).get(sid)
        if entry:
            return entry["harness"]
        hs = self.harnesses(sid)
        return hs[self.harness_use.get(sid, 0) % len(hs)]

    def select_harness(self, sid):
        """Return this step's planned (harness, skipped, index, next_count).

        The map is decided once per run, before the job starts, so every round
        of a loop step, every retry, and every rendered prompt names the same
        harness:

        - harness: the entry this run planned for the step.
        - skipped: the entries the availability walk passed over, as
          (harness_id, missing_binary) pairs; empty when the head was up.
        - used_index: the index of the planned entry. The caller records it in
          the pre-invocation resume state so a failed attempt's retry and an
          operator --mark-done both reproduce the exact harness.
        - next_count: the rotation counter the *accepted* invocation persists,
          past any skips, so a later run does not retry a known-missing head.

        When no entry for the step can be installed this raises
        HarnessUnavailable naming the step and the whole list; no harness is
        invoked and no state is written.
        """
        entry = self.ensure_plan()["steps"][sid]
        skipped = [(s["harness"], s["missing_binary"])
                   for s in entry.get("skipped", [])]
        return entry["harness"], skipped, entry["index"], entry["next_count"]

    def invoke(self, harness, task_path, log_path, usage_path=None, when=None,
               nonce=None, sid=None, skipped=None):
        """Run the harness attached in the foreground: inherited stdio, the
        operator watches and approves prompts, the runner closes the session
        ~15 s after the final signal lands in the run log.
        The log text doubles as the step output. Returns (log_text, meta)."""
        cli, provider, model, effort = parse_harness(harness)
        provider = resolve_provider(cli, provider)
        model = resolve_model(cli, provider, model)
        ensure_harness_path()
        pointer = TASK_POINTER.format(path=task_path)
        env = None
        autosubmit = False
        full = f"{provider}/{model}" if provider else model
        if cli == "cursor":
            cmd = ["agent"] + (["--model", full] if full != "auto" else []) + [pointer]
        elif cli == "opencode":
            stage_name = self.stages[sid][0]["name"] if sid else OPENCODE_AGENT
            cmd, env = opencode_launch(full, effort, pointer, stage_name)
            autosubmit = True
        elif cli == "agy":
            # -i takes the prompt as its value: it must come last or it
            # swallows the next token (e.g. --model) as prompt text.
            cmd = (["agy", "--dangerously-skip-permissions", "--model", full]
                   + (["--effort", effort] if effort else []) + ["-i", pointer])
        elif cli == "cmd":
            # Reject a bad model or effort here, before the session starts:
            # the CLI reports both for free, so the run stops as a config
            # error with the CLI's own reason instead of a missing run log.
            problem = cmd_probe_problem(full, effort)
            if problem:
                raise Fail(f"cmd rejected model {full!r}"
                           + (f" with effort {effort!r}" if effort else "")
                           + f": {problem}")
            cmd = cmd_launch(full, effort, pointer)
        elif cli == "hermes":
            # --usage-file is a top-level flag: it goes before the chat subcommand.
            cmd = ["hermes"]
            if usage_path:
                cmd += ["--usage-file", str(usage_path)]
            cmd += ["chat", "--query-file", str(task_path)]
            if provider:
                cmd += ["--provider", provider, "-m", model]
            elif model != "auto":
                cmd += ["-m", model]
            if effort:
                cmd += ["--reasoning", effort]
        else:
            raise Fail(f"no command mapping for cli {cli!r}")
        banner(cli, harness, task_path, log_path, skipped=skipped)
        reminder = dict(IDLE_REMIND_PLAN, enabled=cli in REMINDER_CLIS)
        text, rc, info = run_attached(cmd, log_path, when, nonce,
                                      cwd=self.repo, env=env,
                                      autosubmit=autosubmit, reminder=reminder)
        if rc != 0 and not log_done(text, when, nonce) \
                and not info.get("mirror_signal"):
            raise Fail(f"{cmd[0]} exited {rc} (step failed; rerun to resume)")
        meta = {"usage_file": str(usage_path)} if usage_path else {}
        meta.update({k: v for k, v in info.items() if v is not None})
        return text, meta


def resume_frame(run, sid):
    """Build the resume preamble: git/file evidence of partial progress."""
    lines = ["## RESUMED ATTEMPT — read this first", "",
             "Your previous attempt at this step was interrupted (runner crash",
             "or harness failure). The full original instructions follow below.",
             "Do NOT redo work that is already done. Inspect the state described",
             "here first, then continue from where the previous attempt stopped.",
             "The previous task file is history unless `ledger.json` names it "
             "as the completed task. Ignore model names in every other attempt "
             "file; the ledger entry is authoritative.", ""]
    try:
        st = subprocess.run(["git", "status", "--porcelain=v1", "--untracked-files=no"],
                            cwd=run.repo, capture_output=True, text=True, timeout=30)
        touched = [ln for ln in st.stdout.splitlines() if ln.strip()][:20]
    except Exception:  # noqa: BLE001 - evidence is best-effort
        touched = None
    if touched is None:
        lines.append("- Working tree state: unavailable (git did not respond).")
    elif not touched:
        lines.append("- Working tree (tracked files): clean, no partial edits visible.")
    else:
        lines.append(f"- Working tree: {len(touched)} tracked file(s) touched (showing up to 20):")
        lines += [f"  {t}" for t in touched]
    try:
        df = subprocess.run(["git", "diff", "--stat"], cwd=run.repo,
                            capture_output=True, text=True, timeout=30)
        stat = [ln for ln in df.stdout.splitlines() if ln.strip()][-8:]
    except Exception:  # noqa: BLE001 - evidence is best-effort
        stat = None
    if stat:
        lines.append("- Diff stat:")
        lines += [f"  {t}" for t in stat]
    req = run.steps[sid].get("require_file")
    if req:
        fp = run._run_dir / req
        if fp.is_file() and fp.stat().st_size > 0:
            lines.append(f"- Expected artifact {req}: PRESENT ({fp.stat().st_size} bytes) — build on it.")
        else:
            lines.append(f"- Expected artifact {req}: MISSING — it was never written; produce it.")
    lines += ["- Your previous reply for this step was lost; only the file state above is trustworthy.",
              "- Finish with the same final-line signal the original instructions demand.", ""]
    return "\n".join(lines)


def assess(run, sid):
    """Operator-facing worthiness verdict for resuming sid. Advisory only."""
    if sid not in run.steps:
        return {"step": sid, "verdict": "corrupt (step resolves nowhere; start fresh)"}
    req = run.steps[sid].get("require_file")
    info = {"step": sid, "require_file": None, "tracked_touched": 0,
            "verdict": "fresh (nothing to continue from; step re-runs cleanly)"}
    if req:
        fp = run._run_dir / req
        info["require_file"] = {"path": str(fp), "exists": fp.is_file(),
                                "bytes": fp.stat().st_size if fp.is_file() else 0}
    try:
        st = subprocess.run(["git", "status", "--porcelain=v1", "--untracked-files=no"],
                            cwd=run.repo, capture_output=True, text=True, timeout=30)
        touched = [ln for ln in st.stdout.splitlines() if ln.strip()]
        info["tracked_touched"] = len(touched)
    except Exception:  # noqa: BLE001 - evidence is best-effort
        pass
    if info["require_file"] and info["require_file"]["bytes"] > 0:
        info["verdict"] = "resumable (partial artifact present; harness continues from file state)"
    elif info["tracked_touched"] > 0:
        info["verdict"] = (f"resumable ({info['tracked_touched']} tracked files touched; "
                           "harness continues from working tree)")
    return info


def sha_str(s):
    return hashlib.sha256(s.encode()).hexdigest()


def sha_file(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def write_json_atomic(path, value):
    """Replace a JSON record without leaving a half-written authority file."""
    path = Path(path)
    tmp = path.with_name(f".{path.name}.{secrets.token_hex(6)}.tmp")
    try:
        tmp.write_text(json.dumps(value, indent=2))
        tmp.replace(path)
    except (OSError, TypeError, ValueError) as exc:
        raise Fail(f"cannot write {path.name}: {exc}") from exc
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass


COMMIT_VERSION = 1


def pending_commit_path(run):
    return Path(run._run_dir) / ".pending-commit.json"


def stage_fingerprint(run, sid):
    """Hash the stage file that produced a task, for forensics.

    The authoritative task snapshot itself is the source of downstream
    context, so a stage change does not alter history. The fingerprint
    records which stage version the snapshot came from.
    """
    try:
        stage_path = (Path(run.pipe_dir) / run.steps[sid]["stage"]).resolve()
        return sha_file(stage_path)
    except (OSError, KeyError):
        return None


def strip_nonce_footer(text):
    """Remove the per-invocation nonce footer from a stored task snapshot.

    The nonce is valid only for its own invocation. Downstream context
    must not see a stale nonce as a usable signal token.
    """
    marker = "\n\n## Signal nonce for this invocation:"
    idx = (text or "").find(marker)
    if idx < 0:
        return text or ""
    return (text[:idx].rstrip() + "\n")


def latest_run_log(run, sid):
    """Return the latest run log for a step, excluding console mirrors."""
    logs = sorted(p for p in Path(run._run_dir).glob(f"{sid}-task-r*.log")
                  if not p.name.endswith(".tui.log"))
    return logs[-1] if logs else None


def write_pending_commit(run, record):
    write_json_atomic(pending_commit_path(run), record)


def read_pending_commit(run):
    path = pending_commit_path(run)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise Fail(f"pending commit cannot be read: {path} ({exc})") from exc
    if not isinstance(data, dict) or data.get("version") != COMMIT_VERSION:
        raise Fail(f"pending commit has unsupported version: {path}")
    for key in ("step", "signal", "harness", "task_file", "resume_after"):
        if key not in data:
            raise Fail(f"pending commit missing {key!r}: {path}")
    return data


def clear_pending_commit(run):
    try:
        pending_commit_path(run).unlink()
    except FileNotFoundError:
        pass
    except OSError as exc:
        raise Fail(f"cannot clear pending commit ({exc})") from exc


def apply_pending_commit(run, record):
    """Idempotently apply a pending completion to ledger, rotation, resume.

    Safe to call multiple times: ledger writes overwrite the same entry,
    rotation writes set the same counts, and resume writes replace the same
    snapshot. Used both for the normal commit path and for crash recovery.
    The record carries the full accepted output so ledger hashing works
    even after memory was cleared by a crash.
    """
    step = record["step"]
    resume_after = record.get("resume_after")
    if not isinstance(resume_after, dict):
        raise Fail("pending commit has no resume snapshot")
    # Restore in-memory state from the commit snapshot so ledger hashing
    # uses the accepted output even after a crash cleared memory.
    if "output" in record:
        outputs = dict(resume_after.get("outputs", {}))
        outputs[step] = record["output"]
        resume_after = dict(resume_after, outputs=outputs)
    run.outputs = dict(resume_after.get("outputs", {}))
    try:
        run.visits = {k: int(v) for k, v in dict(resume_after.get("visits", {})).items()}
        run.harness_use = {k: int(v) for k, v in dict(resume_after.get("harness_use", {})).items()}
    except (TypeError, ValueError) as exc:
        raise Fail(f"pending commit has bad counts ({exc})") from exc
    run.prev_step = resume_after.get("prev_step")
    task_file = record.get("task_file")
    task_path = Path(task_file) if task_file else None
    if task_path is not None and not task_path.is_absolute():
        task_path = Path(run._run_dir) / task_path
    note_completion(run, step, record["signal"], record["harness"],
                    task_path=task_path,
                    via=record.get("via"), routed_to=record.get("routed_to"))
    if run.persist_rotation:
        if not run.rotation_key:
            raise Fail("rotation persistence needs a key")
        save_rotation(run.repo, run.rotation_key, dict(run.harness_use))
    write_json_atomic(Path(run._run_dir) / "resume.json", resume_after)
    return resume_after


def run_relative_path(run, path):
    """Return a run-dir-relative path, rejecting escapes and broken links."""
    run_dir = Path(run._run_dir).resolve()
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = run_dir / candidate
    try:
        return str(candidate.resolve().relative_to(run_dir))
    except (OSError, ValueError, RuntimeError) as exc:
        raise Fail(f"path escapes run directory: {path}") from exc


def git_head(run):
    try:
        r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=run.repo,
                           capture_output=True, text=True, timeout=30)
        return r.stdout.strip() or None
    except Exception:  # noqa: BLE001 - forensics are best-effort
        return None


def _reservation_store(repo):
    return ReservationStore(repo)


def _reservation_path(run):
    return reservation_file(run.repo, run.inputs["phase_number"])


def _reservation_from_run(run):
    """Load the phase token from the driver environment or run directory."""
    try:
        from_env = reservation_from_environment(run.inputs["phase_number"])
    except CoordinationError:
        raise
    sidecar = load_reservation_file(_reservation_path(run))
    if from_env is not None:
        if sidecar is not None:
            if any(sidecar.get(field) != from_env.get(field)
                   for field in ("phase", "machine_id", "reservation_id", "generation")):
                raise Fail("driver and run reservation tokens disagree")
            return {**sidecar, **from_env}
        return from_env
    return sidecar


def _validate_phase_file(repo, phase, value):
    """Bind the operator's phase number to one canonical roadmap file."""
    if not isinstance(value, str) or not value:
        raise Fail("phase_file is required for a live run")
    path = Path(value)
    if not path.is_absolute():
        path = repo / path
    path = path.resolve()
    import next_phase
    roadmap = next_phase.roadmap_dir(repo)
    if roadmap is None:
        raise Fail("no private roadmap directory is available")
    try:
        path.relative_to(roadmap.resolve())
    except ValueError as exc:
        raise Fail("phase_file is outside the private roadmap directory") from exc
    match = next_phase.PHASE_RE.fullmatch(path.name)
    if not match or int(match.group(1)) != int(phase):
        raise Fail(
            f"phase_file {path.name!s} does not match phase_number={phase}")
    if not path.is_file():
        raise Fail(f"phase_file does not exist: {path}")
    return value


def _has_completion_marker(run):
    """Check existing roadmap/run evidence without trusting a reservation."""
    try:
        import next_phase
        phase = int(run.inputs["phase_number"])
        path = Path(run.inputs["phase_file"])
        if not path.is_absolute():
            path = run.repo / path
        return next_phase.is_done(
            run.repo, phase, path, next_phase.index_complete(run.repo))
    except (OSError, TypeError, ValueError):
        return False


def _prepare_reservation(run, *, resumed, fresh=False, machine_id=None,
                         takeover=False):
    """Acquire or verify the phase fence before any harness can start."""
    machine_id = machine_id or os.environ.get("CLIO_MACHINE_ID", "local-01")
    store = _reservation_store(run.repo)
    current = _reservation_from_run(run)
    if current is None and not resumed and not fresh and not takeover:
        state, _commit = store.read()
        key = f"{int(run.inputs['phase_number']):06d}"
        if key not in state.get("phases", {}) and _has_completion_marker(run):
            raise Fail(
                "phase already has completion evidence; use an explicit fresh "
                "operator decision before rerunning it")
    if current is not None:
        current_machine = current.get("machine_id")
        if current_machine != machine_id:
            raise Fail(
                f"phase reservation belongs to {current_machine!r}, "
                f"not this machine {machine_id!r}")
        if fresh and not takeover:
            raise Fail(
                "--fresh would discard an active phase reservation; "
                "use --takeover only after confirming the old owner stopped")
        if takeover:
            reservation = store.takeover(
                run.inputs["phase_number"], machine_id, confirm=True,
                run_id=f"phase-{int(run.inputs['phase_number']):06d}",
                expected_reservation_id=current["reservation_id"],
                expected_generation=current["generation"])
        else:
            record = store.assert_owner(current)
            if record.get("status") in {"completed", "rejected"}:
                raise Fail(
                    f"phase reservation is already {record.get('status')}; "
                    "use an explicit operator decision before rerunning it")
            reservation = current
    elif resumed:
        raise Fail(
            "resume has no phase reservation token; register the existing "
            "server-owned claim before resuming")
    elif takeover:
        state, _commit = store.read()
        key = f"{int(run.inputs['phase_number']):06d}"
        current_record = state.get("phases", {}).get(key)
        if current_record is None:
            reservation = store.reserve(
                run.inputs["phase_number"], machine_id,
                run_id=f"phase-{key}")
        else:
            reservation = store.takeover(
                run.inputs["phase_number"], machine_id, confirm=True,
                run_id=f"phase-{key}",
                expected_reservation_id=current_record["reservation_id"],
                expected_generation=current_record["generation"])
    else:
        reservation = store.reserve(
            run.inputs["phase_number"], machine_id,
            run_id=f"phase-{int(run.inputs['phase_number']):06d}")

    # Persist the token before the first harness invocation. If this write
    # fails, the shared claim remains visible and the operator can recover it;
    # no unclaimed process is launched.
    save_reservation_file(_reservation_path(run), reservation)
    store.set_status(reservation, "running")
    run.reservation = reservation
    run.reservation_store = store
    run.reservation_heartbeat = ReservationHeartbeat(store, reservation)
    run.reservation_heartbeat.start()
    return reservation


class ReservationHeartbeat:
    """Best-effort audit heartbeat; lost ownership is checked by the runner."""

    def __init__(self, store, reservation):
        self.store = store
        self.reservation = reservation
        try:
            self.interval = float(os.environ.get(
                "CLIO_RESERVATION_HEARTBEAT_S", RESERVATION_HEARTBEAT_S))
        except ValueError:
            self.interval = RESERVATION_HEARTBEAT_S
        self.stop_event = threading.Event()
        self.error = None
        self.thread = None

    def start(self):
        if self.interval <= 0:
            return
        self.thread = threading.Thread(
            target=self._run, name="phase-reservation-heartbeat", daemon=True)
        self.thread.start()

    def _run(self):
        while not self.stop_event.wait(self.interval):
            try:
                self.store.renew(self.reservation)
            except Exception as exc:  # noqa: BLE001 - surfaced by check()
                self.error = str(exc)
                return

    def check(self):
        if self.error:
            raise Fail(f"phase reservation heartbeat failed: {self.error}")

    def stop(self):
        self.stop_event.set()
        if self.thread is not None:
            self.thread.join(timeout=max(1.0, min(self.interval + 1.0, 5.0)))


def _set_reservation_state(run, status, *, evidence_path=None):
    if not getattr(run, "reservation", None):
        return
    run.reservation_store.set_status(
        run.reservation, status, evidence_path=evidence_path)


def _publish_completion_evidence(run):
    """Run the claim-checked publication helper and return its receipt."""
    if not getattr(run, "reservation", None):
        return None
    evidence = gitsync.publish_phase(
        run.repo, run.inputs["phase_number"])
    _record_sync(run, "sync-after-completion", evidence)
    if not evidence.get("ok") or evidence.get("state") != "PUBLISHED":
        detail = evidence.get("error", evidence.get("summary", "unknown error"))
        if evidence.get("dirty"):
            detail += f" (dirty: {evidence['dirty']})"
        raise Fail(f"completion evidence was not published: {detail}")
    receipt = evidence.get("receipt")
    if not isinstance(receipt, dict) or not receipt.get("path"):
        raise Fail("publication helper returned no completion receipt")
    return receipt["path"]


def _write_pending_completion(run, result):
    pending = dict(result)
    pending["state"] = "publishing"
    pending["publication_pending"] = True
    (run._run_dir / "run.json").write_text(json.dumps(pending, indent=2))


def _mark_publication_failed(run, error):
    path = getattr(run, "_run_dir", None)
    if path is None:
        return
    marker = path / "run.json"
    try:
        data = json.loads(marker.read_text())
    except (OSError, ValueError):
        return
    if data.get("state") != "publishing":
        return
    data["state"] = "blocked"
    data["publication_pending"] = False
    data["publication_error"] = str(error)
    marker.write_text(json.dumps(data, indent=2))


def _finish_reservation(run, result, *, receipt_path=None):
    """Retain the reservation and record the terminal state after evidence."""
    if not getattr(run, "reservation", None):
        return result
    state = result.get("state")
    if state == "completed":
        if not receipt_path:
            raise Fail("completed run has no publication receipt")
        _set_reservation_state(
            run, "completed", evidence_path=receipt_path)
    elif state == "rejected":
        _set_reservation_state(run, "rejected")
    elif state == "blocked":
        _set_reservation_state(run, "blocked")
    result = dict(result)
    result["reservation"] = {
        "machine_id": run.reservation["machine_id"],
        "reservation_id": run.reservation["reservation_id"],
        "generation": run.reservation["generation"],
        "state": state,
    }
    return result


def artifact_is_empty(path):
    """Return whether a required artifact has no actionable content.

    Findings reports are actionable when either defect findings or directly
    in-scope issue candidates remain. Other JSON/text artifacts keep the original
    non-empty behavior.
    """
    try:
        text = path.read_text()
    except OSError as error:
        raise Fail(f"required artifact is unreadable: {path}") from error
    try:
        report = json.loads(text)
    except ValueError:
        return not text.strip()
    if isinstance(report, dict) and "findings" in report:
        return not report.get("findings") and not report.get("addressed_issues")
    return not text.strip()


def note_completion(run, sid, sig, harness, task_path=None, via=None, routed_to=None):
    """Record one authoritative completion proof for a step.

    The signal, harness, and task snapshot are recorded together so
    downstream context can use the exact attempt that completed. Older task
    files remain on disk and are listed as superseded rather than deleted.
    The task file hash makes tampering fail closed; the stage fingerprint
    records which stage version produced the snapshot. via/routed_to records
    the routing decision so crash recovery can replay advancement.
    """
    s = run.steps[sid]
    arts = {}
    for rel in [s.get("require_file"), (s.get("snapshot") or {}).get("to")]:
        if not rel:
            continue
        fp = run._run_dir / rel
        if fp.is_file():
            arts[rel] = {"bytes": fp.stat().st_size, "sha256": sha_file(fp)}
    lp = run._run_dir / "ledger.json"
    if lp.is_file():
        try:
            ledger = json.loads(lp.read_text())
        except (OSError, ValueError) as exc:
            raise Fail(f"ledger.json cannot be read: {lp} ({exc})") from exc
        if (not isinstance(ledger, dict)
                or not isinstance(ledger.get("order"), list)
                or not isinstance(ledger.get("steps"), dict)):
            raise Fail(f"ledger.json has an invalid shape: {lp}")
    else:
        ledger = {"order": [], "steps": {}}
    if sid not in ledger["order"]:
        ledger["order"].append(sid)
    current_task = (run_relative_path(run, task_path)
                    if task_path is not None else None)
    task_sha = None
    if task_path is not None:
        task_candidate = Path(task_path)
        if not task_candidate.is_absolute():
            task_candidate = Path(run._run_dir) / task_candidate
        if not task_candidate.is_file():
            raise Fail(f"completion task file is missing: {task_path}")
        try:
            task_sha = sha_file(task_candidate)
        except OSError as exc:
            raise Fail(f"completion task file unreadable: {task_path} ({exc})") from exc
    task_files = sorted(
        run_relative_path(run, path)
        for path in run._run_dir.glob(f"{sid}-task-r*.md")
        if "-resume-" not in path.name
        and run_relative_path(run, path) != current_task)
    entry = {"signal": sig, "harness": harness,
             "authoritative": True,
             "agent": display_name(harness),
             "visits": run.visits.get(sid, 0),
             "output_sha256": sha_str(run.outputs.get(sid, "")),
             "artifacts": arts, "git_head": git_head(run),
             "superseded_task_files": task_files}
    if task_path is not None:
        entry["task_file"] = current_task
        entry["task_sha256"] = task_sha
    stage_sha = stage_fingerprint(run, sid)
    if stage_sha is not None:
        entry["stage_sha256"] = stage_sha
    if via is not None:
        entry["via"] = via
    if routed_to is not None:
        entry["routed_to"] = routed_to
    ledger["steps"][sid] = entry
    write_json_atomic(lp, ledger)


def _already_completed(run, sid):
    """Return the ledger entry when a step's output already proves completion.

    Used for crash recovery when advancement never landed: ledger plus
    matching output hash means the harness already succeeded and must not
    be re-invoked. Returns None when the step still needs to run.
    """
    try:
        attempt = run.authoritative_attempt(sid)
    except Fail:
        return None
    if attempt is None:
        return None
    if sid not in run.outputs:
        return None
    output_sha = attempt.get("output_sha256")
    if not isinstance(output_sha, str) or not output_sha:
        return None
    try:
        if sha_str(run.outputs[sid]) != output_sha:
            return None
    except Exception:  # noqa: BLE001 - hashing must not crash recovery
        return None
    return attempt


def verify_ledger(run, outputs, current=None):
    """Re-prove every ledger entry against current state. Raises Fail
    naming the exact gap. Later steps may dirty the tree, so only
    outputs, artifacts, and HEAD movement are checked. Files that a
    later step intentionally rewrites (a snapshot's `from`, e.g.
    findings.json edited by the remediator) are exempt from the artifact
    pin: their history is versioned by the snapshot `to` backup instead.
    The resumed `current` step is exempt from the output pin: its saved
    output is the interrupted/blocked attempt, and the step re-runs."""
    lp = run._run_dir / "ledger.json"
    if not lp.is_file():
        return
    try:
        ledger = json.loads(lp.read_text())
    except (OSError, ValueError) as exc:
        raise Fail(f"ledger.json does not parse: {exc}") from exc
    if (not isinstance(ledger, dict)
            or not isinstance(ledger.get("order"), list)
            or not isinstance(ledger.get("steps"), dict)):
        raise Fail("ledger.json has an invalid shape")
    mutable = {(run.steps[sid].get("snapshot") or {}).get("from")
               for sid in run.steps} - {None}
    head_now = git_head(run)
    for sid in ledger["order"]:
        if not isinstance(sid, str):
            raise Fail("ledger: order contains a non-string step id")
        if sid not in run.steps or sid not in ledger["steps"]:
            raise Fail(f"ledger: entry for unknown step {sid!r}")
        e = ledger["steps"][sid]
        if not isinstance(e, dict):
            raise Fail(f"ledger: entry for {sid!r} is not an object")
        run.authoritative_attempt(sid)
        if sid not in outputs:
            raise Fail(f"ledger: step {sid} completed earlier but its output is gone")
        output_sha = e.get("output_sha256")
        if not isinstance(output_sha, str) or not output_sha:
            raise Fail(f"ledger: step {sid} has no valid output hash")
        if sid != current and sha_str(outputs[sid]) != output_sha:
            raise Fail(f"ledger: step {sid} output changed since completion")
        artifacts = e.get("artifacts", {})
        if not isinstance(artifacts, dict):
            raise Fail(f"ledger: step {sid} has invalid artifacts")
        for rel, a in artifacts.items():
            if not isinstance(rel, str) or not isinstance(a, dict) \
                    or not isinstance(a.get("sha256"), str) or not a.get("sha256"):
                raise Fail(f"ledger: step {sid} has an invalid artifact record")
            if rel in mutable:
                continue
            fp = run._run_dir / rel
            if not fp.is_file():
                raise Fail(f"ledger: step {sid} artifact {rel} is gone")
            if sha_file(fp) != a["sha256"]:
                raise Fail(f"ledger: step {sid} artifact {rel} changed since completion")
        if e.get("git_head") and head_now and e["git_head"] != head_now:
            raise Fail(f"ledger: git HEAD moved since step {sid} completed "
                       f"({e['git_head'][:8]} -> {head_now[:8]})")


def repin_ledger(run, reason):
    """Re-point every ledger step's ``git_head`` at the current HEAD.

    ``verify_ledger`` compares each step's recorded ``git_head`` to the live
    HEAD as a plain string, so an operator baseline change (a merge, a rebase)
    invalidates a resume. The ``head_repin`` key in the ledger has always
    recorded *why* that happened, but nothing read it: it looked like the
    mechanism and was only a note. This is the mechanism.

    Every step is re-pinned to the same HEAD, because a single resume runs
    against one tree. Step outputs and artifacts stay pinned by sha256 and are
    not touched, so this asserts only that the recorded commit moved; it does
    not re-verify that the old outputs still describe the new tree. The
    ``reason`` is required and is stored, so the ledger always says which
    operator decision authorised the move.
    """
    run_dir = Path(run._run_dir)
    ledger_path = run_dir / "ledger.json"
    if not ledger_path.is_file():
        raise Fail("repin: no ledger.json in run directory")
    if not isinstance(reason, str) or not reason.strip():
        raise Fail("repin: --repin-reason is required and must say why HEAD moved")
    try:
        ledger = json.loads(ledger_path.read_text())
    except (OSError, ValueError) as exc:
        raise Fail(f"repin: ledger.json cannot be read ({exc})") from exc
    steps = ledger.get("steps")
    if not isinstance(steps, dict) or not steps:
        raise Fail("repin: ledger.json has no steps mapping")
    head = git_head(run)
    if not head:
        raise Fail("repin: cannot read the current HEAD")
    previous = sorted({e.get("git_head") for e in steps.values()
                       if isinstance(e, dict) and e.get("git_head")})
    changed = []
    for sid, entry in steps.items():
        if not isinstance(entry, dict):
            continue
        was = entry.get("git_head")
        if was != head:
            changed.append({"step": sid, "from": was, "to": head})
        entry["git_head"] = head
    ledger["head_repin"] = {
        "from": previous[0] if len(previous) == 1 else previous,
        "to": head,
        "reason": reason.strip(),
        "rejected_at": time.strftime("%Y-%m-%d"),
        "note": ("Written by runner.py --repin-ledger. verify_ledger compares "
                 "each step's git_head string to the current HEAD; this key is "
                 "the audit record for that move, not the mechanism."),
    }
    write_json_atomic(ledger_path, ledger)
    return {"repin": "ok", "run_dir": str(run_dir), "git_head": head,
            "steps": sorted(steps), "changed": changed,
            "unchanged": [c["step"] for c in changed if c["from"] == head]}


def audit_or_migrate_ledger(run, migrate=False):
    """Report authority gaps and optionally backfill deterministic entries.

    Returns a report with migrated, already_authoritative, ambiguous, and
    errors lists, plus a migration-report.json path when files were scanned.
    Ambiguous steps are never guessed; recover them with --mark-done.
    """
    run_dir = Path(run._run_dir)
    ledger_path = run_dir / "ledger.json"
    report = {"run_dir": str(run_dir), "migrated": [], "already_authoritative": [],
              "ambiguous": [], "errors": []}
    if not ledger_path.is_file():
        report["errors"].append("no ledger.json in run directory")
        return report
    try:
        ledger = json.loads(ledger_path.read_text())
    except (OSError, ValueError) as exc:
        report["errors"].append(f"ledger.json cannot be read ({exc})")
        return report
    if not isinstance(ledger, dict) or not isinstance(ledger.get("steps"), dict):
        report["errors"].append("ledger.json has an invalid shape")
        return report
    for sid in list(ledger.get("order", [])):
        entry = ledger["steps"].get(sid)
        if not isinstance(entry, dict):
            report["errors"].append(f"{sid}: entry is not an object")
            continue
        if entry.get("authoritative") is True and "task_file" in entry and "task_sha256" in entry:
            report["already_authoritative"].append(sid)
            continue
        candidates = sorted(
            p.name for p in run_dir.glob(f"{sid}-task-r*.md")
            if "-resume-" not in p.name)
        visits = entry.get("visits")
        deterministic = None
        if isinstance(visits, int) and visits >= 1:
            wanted = f"{sid}-task-r{visits}.md"
            if wanted in candidates:
                deterministic = wanted
        if deterministic is None and len(candidates) == 1:
            deterministic = candidates[0]
        if deterministic is None:
            if not candidates:
                report["errors"].append(f"{sid}: no task candidates exist")
            else:
                report["ambiguous"].append({"step": sid, "candidates": candidates,
                                            "detail": f"{len(candidates)} task candidates",
                                            "recovery": f"--mark-done {sid} SIGNAL"})
            continue
        if not migrate:
            # Audit only: report what would migrate without changing files.
            report["migrated"].append(f"{sid} (would backfill {deterministic})")
            continue
        try:
            fresh_ledger = json.loads(ledger_path.read_text())
            fresh_entry = fresh_ledger["steps"].get(sid)
            run._migrate_legacy_entry(sid, fresh_ledger, fresh_entry, persist=True)
            report["migrated"].append(sid)
        except Fail as exc:
            report["errors"].append(f"{sid}: {exc}")
    report_path = run_dir / "migration-report.json"
    try:
        if migrate or report["ambiguous"] or report["migrated"]:
            report_path.write_text(json.dumps(report, indent=2))
            report["report_path"] = str(report_path)
    except OSError as exc:
        report["errors"].append(f"cannot write migration report ({exc})")
    return report


def mark_done(run, step, signal, force=False):
    """Operator recovery for a step whose work is finished but whose run
    log never received the bare final-signal line (so auto-exit never
    fired and routing failed). Appends the bare signal to the step's
    latest run log, records the completion exactly as drive() would
    (output, transcript, event, ledger), and advances resume.json to the
    routed target. No harness is invoked and rotation is untouched
    (no new invocation happened). max_rounds/on_exhausted IS honored
    unless force=True: the operator override stays explicit."""
    if step not in run.steps:
        raise Fail(f"--mark-done {step!r} resolves to no step")
    s = run.steps[step]
    line = (signal or "").strip()
    if not line:
        raise Fail("--mark-done needs a non-empty signal")
    head = line.split()[0].rstrip(":")
    blocked = head.endswith("BLOCKED")
    if "when" in s:
        key = match_signal(line, s["when"])
        if key is None and not blocked:
            raise Fail(f"--mark-done: signal {line!r} matches none of "
                       f"{sorted(s['when'])}")
        target = "blocked" if blocked else s["when"][key]
    else:
        key = None
        if not (blocked or head.endswith(END_TOKENS)):
            raise Fail(f"--mark-done: signal {line!r} is not a "
                       f"DONE/APPROVED/REJECTED signal")
        target = "blocked" if blocked else s["end"]
    logs = sorted(p for p in run._run_dir.glob(f"{step}-task-r*.log")
                  if not p.name.endswith(".tui.log"))
    if not logs:
        raise Fail(f"--mark-done: no run log for step {step}")
    log_path = logs[-1]
    rpath = run._run_dir / "resume.json"
    if not rpath.is_file():
        raise Fail(f"--mark-done: no resume state at {rpath}")
    try:
        resumed = json.loads(rpath.read_text())
    except ValueError as e:
        raise Fail(f"resume.json does not parse ({e})")
    if resumed.get("current") != step:
        raise Fail(f"--mark-done: resume is at {resumed.get('current')!r}, "
                   f"not {step!r}")
    run.outputs = resumed.get("outputs", {})
    run.visits = resumed.get("visits", {})
    run.harness_use = resumed.get("harness_use", {})
    run.prev_step = resumed.get("prev_step")
    verify_ledger(run, resumed.get("outputs", {}), step)
    # Terminate the previous line if the log lacks a trailing newline,
    # or the signal glues onto it and matches nothing (not even us).
    with open(log_path, "a+") as fh:
        fh.seek(0, 2)
        if fh.tell() > 0:
            fh.seek(fh.tell() - 1)
            if fh.read(1) != "\n":
                fh.write("\n")
        fh.write(line + "\n")
    text = log_path.read_text()
    if not text.strip():
        raise Fail(f"run log empty: {log_path}")
    vh = list(s["when"]) if "when" in s else None
    if find_signal(text, vh) is None:
        raise Fail(f"--mark-done: appended signal is not parseable "
                   f"from {log_path}; refusing to advance")
    # require_file gate, mirroring drive(): refuse to advance past missing
    # work. skip_when_empty reroutes instead of failing.
    skip_to = None
    if "require_file" in s or "skip_when_empty" in s:
        fpath = run._run_dir / s["require_file"] if s.get("require_file") else None
        if fpath is None:
            empty = True
        elif not fpath.is_file():
            raise Fail(f"--mark-done: signal given but {fpath} missing")
        else:
            empty = artifact_is_empty(fpath)
        if "skip_when_empty" in s and empty:
            skip_to = s["skip_when_empty"]
    if skip_to is not None:
        target = skip_to
    if (not force and not blocked and "max_rounds" in s
            and target not in run.pipe["ends"] and target in run.visits
            and run.visits.get(step, 0) >= s["max_rounds"]):
        raise Fail(f"--mark-done: step {step} is at max_rounds "
                   f"({s['max_rounds']}); routing to {target} would end as "
                   f"{s.get('on_exhausted', 'config_error')}. Add --force "
                   f"to override.")
    # The harness that did the work is the one peeked before this step's
    # invocation, i.e. at the saved (pre-invoke) rotation count.
    harness = run.harness_for(step)
    agent = display_name(harness)
    run.outputs[step] = text
    tasks = sorted(p for p in run._run_dir.glob(f"{step}-task-r*.md")
                   if "-resume-" not in p.name)
    task_path = tasks[-1] if tasks else log_path.with_suffix(".md")
    try:
        prompt = task_path.read_text()
        task_mtime = task_path.stat().st_mtime
    except OSError:
        prompt, task_mtime = "", log_path.stat().st_mtime
    phase = int(run.inputs["phase_number"])
    run_id = f"{run.inputs.get('run_label', 'phase')}-{phase:06d}"
    transcript = resumed.get("transcript", [])
    events = resumed.get("events", [])
    event = {"step": step, "harness": harness, "agent": agent,
             "task_file": str(task_path),
             "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
             "duration_s": round(log_path.stat().st_mtime - task_mtime, 3),
             "visits": run.visits.get(step, 0), "signal": line,
             "via": "mark-done"}
    transcript.append({"step": step, "harness": harness,
                       "agent": agent, "signal": line})
    done_path = run._run_dir / "run.json"
    if blocked:
        event["routed_to"] = "blocked"
        events.append(event)
        write_json_atomic(rpath, {
            "current": step, "outputs": run.outputs, "visits": run.visits,
            "harness_use": run.harness_use, "prev_step": run.prev_step,
            "transcript": transcript, "events": events})
        result = {"run_id": run_id, "phase": f"{phase:06d}",
                  "state": "blocked", "transcript": transcript,
                  "events": events}
        write_json_atomic(done_path, result)
        return result
    # Journal the operator recovery the same way as drive() completions so a
    # crash between ledger and resume cannot strand the run. Rotation is
    # untouched (no new invocation happened).
    via_mark = "mark-done"
    if target in run.pipe["ends"]:
        event["routed_to"] = target
        events.append(event)
        resume_after = {"current": step, "outputs": dict(run.outputs),
                        "visits": dict(run.visits),
                        "harness_use": dict(run.harness_use),
                        "prev_step": run.prev_step,
                        "transcript": list(transcript), "events": list(events)}
        record = {"version": COMMIT_VERSION, "kind": "terminal",
                  "step": step, "signal": line, "harness": harness,
                  "task_file": run_relative_path(run, task_path),
                  "output": run.outputs[step],
                  "via": via_mark, "routed_to": target,
                  "harness_use_after": dict(run.harness_use),
                  "resume_after": resume_after,
                  "terminal_state": target,
                  "transcript_after": list(transcript),
                  "events_after": list(events)}
        write_pending_commit(run, record)
        apply_pending_commit(run, record)
        clear_pending_commit(run)
        result = {"run_id": run_id, "phase": f"{phase:06d}",
                  "state": target, "transcript": transcript,
                  "events": events}
        write_json_atomic(done_path, result)
        # Keep resume.json until the terminal publication path succeeds. If
        # publication fails, the next invocation can resume this step.
        return result
    event["routed_to"] = target
    events.append(event)
    run.prev_step, nxt = step, target
    resume_after = {"current": nxt, "outputs": dict(run.outputs),
                    "visits": dict(run.visits),
                    "harness_use": dict(run.harness_use),
                    "prev_step": run.prev_step,
                    "transcript": list(transcript), "events": list(events)}
    record = {"version": COMMIT_VERSION, "kind": "advance",
              "step": step, "signal": line, "harness": harness,
              "task_file": run_relative_path(run, task_path),
              "output": run.outputs[step],
              "via": via_mark, "routed_to": target,
              "harness_use_after": dict(run.harness_use),
              "resume_after": resume_after,
              "next_current": nxt}
    write_pending_commit(run, record)
    apply_pending_commit(run, record)
    clear_pending_commit(run)
    return {"run_id": run_id, "phase": f"{phase:06d}", "state": "advanced",
            "advanced_to": nxt, "transcript": transcript, "events": events}


def dominators(pipe):
    """Steps that every start→S walk must pass through (per S). Used to
    prove --from targets: --from S needs ledger entries for all of them."""
    steps = pipe["steps"]
    succ = {sid: set() for sid in steps}
    for sid, s in steps.items():
        tgts = list(s.get("when", {}).values()) + [s.get("skip_when_empty")]
        for tgt in tgts:
            if tgt in steps:
                succ[sid].add(tgt)
    dom = {sid: set(steps) for sid in steps}
    dom[pipe["start"]] = {pipe["start"]}
    changed = True
    while changed:
        changed = False
        for sid in steps:
            if sid == pipe["start"]:
                continue
            new = set(steps)
            for p in steps:
                if sid in succ[p]:
                    new &= dom[p]
            new |= {sid}
            if new != dom[sid]:
                dom[sid] = new
                changed = True
    return dom


# Leading ISO-8601 timestamp (log-entry style) that agents may prefix to the
# final signal line; stripped before signal matching.
TS_PREFIX_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?\s+")


def last_line(text):
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    if not lines:
        return ""
    return TS_PREFIX_RE.sub("", lines[-1], count=1)


# Leading pipe-journal segments ("| r1 | finish | ...") that agents invent
# despite the bare-signal rule; stripped before signal matching. Only
# leading "| xxx |" chunks are removed, so a table row mentioning a signal
# mid-line still does not match (match_signal anchors at the start).
JOURNAL_SEG_RE = re.compile(r"^\|\s*[^|]{1,32}\|\s*")


def _signal_tokens(line):
    """Normalize one raw log line into the text the matcher sees: a JSON
    signal object ({"signal": ..., "nonce": ...}) becomes its tokens, so
    agents may emit the signal structured or bare. Anything else passes
    through untouched."""
    s = (line or "").strip()
    if len(s) >= 2 and s.startswith("{") and s.endswith("}"):
        try:
            d = json.loads(s)
        except ValueError:
            return s
        if isinstance(d, dict) and isinstance(d.get("signal"), str):
            extra = d.get("nonce", "")
            extra = extra if isinstance(extra, str) else ""
            return f"{d['signal']} {extra}".strip()
    return s


def clean_line(line):
    """Strip one timestamp prefix, unfold a JSON signal object, then strip
    any journal prefixes, for matching."""
    line = TS_PREFIX_RE.sub("", (line or "").strip(), count=1)
    line = _signal_tokens(line)
    prev = None
    while prev != line:
        prev = line
        line = JOURNAL_SEG_RE.sub("", line, count=1)
    return line.strip()


def find_signal(text, when, nonce=None):
    """Bottom-up scan of the last SIGNAL_SCAN_LINES non-empty lines for a
    completion signal. Returns the cleaned signal line, or None. When a
    nonce is given, non-*_BLOCKED* matches must carry it as a separate
    token; *_BLOCKED* lines are exempt. The same predicate serves the
    auto-exit poll and the routing decision, so a session the runner
    would close is a session it can route."""
    lines = [ln for ln in (text or "").splitlines() if ln.strip()]
    for raw in reversed(lines[-SIGNAL_SCAN_LINES:]):
        line = clean_line(raw)
        if not line:
            continue
        head = line.split()[0].rstrip(":") if line.split() else ""
        if head.endswith("BLOCKED"):
            return line
        if nonce is not None and nonce not in line.split():
            continue
        if when and match_signal(line, when):
            return line
        if not when and head.endswith(END_TOKENS):
            return line
    return None


TASK_POINTER = ("Your full task instructions are in this file: {path}\n"
                    "Read that file FIRST and follow it exactly. When finished, "
                    "write the required final-line signal (defined in the file) "
                    "as the last line of your run log: on its own line, without "
                    "a timestamp prefix, with nothing after it. Your task file "
                    "ends with a per-run signal nonce: append it after your "
                    "signal word. If you already "
                    "summarized in chat, still append that signal line to "
                    "the log file: chat text alone never counts.")


ATTEMPT_AUTHORITY = """## ATTEMPT AUTHORITY

The file containing this notice is the active attempt. This run keeps one
task file per attempt for forensics. `ledger.json` is the only authoritative
completion record: for any other completed step, use only the `task_file` named
in that step's ledger entry. Use the entry keyed by the step id, not the
newest-looking file. Every other task file is an incomplete or
superseded attempt. Never treat a superseded task file as a live requirement,
instruction, or model attribution. If task files disagree, the ledger entry
wins. A model-name difference between attempts is historical information, never
a finding and never a request to switch models.
"""


BANNER_ART = r"""
  ____   _____  _____  ____
 / ___| |_   _|| ____||  _ \
 \___ \   | |  |  _|  | |_) |
  ___) |  | |  | |___ |  __/
 |____/   |_|  |______|_|
"""


def banner(cli, harness, task_path, log_path, skipped=None):
    """Announce the start of a new foreground harness step.

    `skipped` is the (harness_id, missing_binary) list walked over before the
    chosen harness, printed so an operator sees which entries were missing and
    why the model under HARNESS is not the head of the stage list.
    """
    bar = "=" * 76
    print(f"\n{bar}{BANNER_ART}{bar}")
    print(f"  STEP     {Path(task_path).stem}      HARNESS  {harness}")
    if skipped:
        print("  SKIPPED  " + ", ".join(
            f"{h} ({binary} not on PATH)" for h, binary in skipped))
    print(f"  TASK     {task_path}")
    print(f"  LOG      {log_path}")
    print(f"  Watch it work in this pane (--auto approves permissions). "
          f"Ctrl-C kills the step;\n  rerunning the same command resumes it.")
    print(bar, flush=True)


def match_signal(line, when):
    for sig in when:
        if line == sig or line.startswith(sig + " ") or line.startswith(sig + ":"):
            return sig
    return None


def log_done(text, when, nonce=None):
    """True when a completion signal is visible in the run log: a `when`
    key, any *_BLOCKED, or (for end steps with no `when`) a *_DONE /
    *_APPROVED / *_REJECTED-style first token. Scans back over trailing
    lines (see find_signal); a nonce, when given, is required on
    non-*_BLOCKED* lines."""
    return find_signal(text, when, nonce) is not None


def _poll_stable(done, grew, stable):
    """Stability counter for the auto-exit poll. Any log growth resets it:
    only a quiescent log showing a signal accumulates stability, so a
    mid-run signal echo followed by more work cannot close the session."""
    if grew:
        return 0
    return stable + 1 if done else 0


def _terminate(proc):
    """Escalating shutdown: SIGINT, then SIGTERM, then SIGKILL. The signal
    is already durable in the run log, so even a hard kill loses nothing."""
    for sig, wait_s in ((signal.SIGINT, AUTOEXIT_TERM_S),
                        (signal.SIGTERM, AUTOEXIT_KILL_S)):
        if proc.poll() is not None:
            return
        try:
            proc.send_signal(sig)
            proc.wait(timeout=wait_s)
        except (subprocess.TimeoutExpired, ProcessLookupError, OSError):
            continue
    if proc.poll() is None:
        proc.kill()
        try:
            proc.wait(timeout=5)
        except (subprocess.TimeoutExpired, OSError):
            pass


# Console-mirror scanning: TUI output carries ANSI escapes and \r redraws,
# which are stripped before matching. Only the tail is scanned.
TUI_TAIL_BYTES = 65536
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)"
                     r"|\x1b[()][0-9A-B]|\x1b[78>=<]|\r")


def _clean_mirror(data):
    """Decode console bytes and strip escape sequences for matching."""
    if isinstance(data, (bytes, bytearray)):
        text = bytes(data).decode("utf-8", errors="replace")
    else:
        text = data or ""
    return ANSI_RE.sub("", text)


def _tail_text(path, limit=TUI_TAIL_BYTES):
    """Last `limit` bytes of a file, decoded lossily ("" when unreadable)."""
    try:
        with open(path, "rb") as fh:
            fh.seek(0, 2)
            fh.seek(max(0, fh.tell() - limit))
            return fh.read().decode("utf-8", errors="replace")
    except OSError:
        return ""


class _KillStep(Exception):
    pass


def reminder_due(now, quiet_since, sent, last_operator, plan, started=True):
    """True when an agent-facing idle reminder is due. Pure scheduling:
    enough quiet, budget left, the reminder enabled for this harness, the
    agent input exists (`started`), and the operator has not typed in this
    invocation. Any operator keystroke marks the session as attended; a
    present human is the intended handler, so the runner never injects into
    their input. `plan` is IDLE_REMIND_PLAN (or a test override with the
    same keys)."""
    if not started or not plan.get("enabled", True) or sent >= plan["max"]:
        return False
    if last_operator:
        return False
    return now - quiet_since >= plan["first_s"] * (plan["backoff"] ** sent)


# Console tails that look like an unanswered confirmation or input prompt.
# The reminder is skipped rather than typed into one: a false skip only costs
# a nudge (the stderr warning stays), while a false send could answer a
# dialog. Deliberately narrow: only explicit yes/no and "press" shapes.
PROMPT_TAIL_RE = re.compile(
    r"(?:\[[yYnN]/[yYnN]?\]|\([yYnN]/[yYnN]?\)|\b[yY]/[nN]\b|"
    r"press (?:any key|enter))", re.IGNORECASE)


def _looks_like_prompt(mirror):
    """True when the last non-empty console line looks like a prompt the
    reminder must not answer. Conservative by design."""
    lines = [ln.strip() for ln in (mirror or "").splitlines() if ln.strip()]
    if not lines:
        return False
    return PROMPT_TAIL_RE.search(lines[-1]) is not None


def _deliver_reminder(master, text):
    """Send one reminder to the harness input. Default: type the text and
    press Enter on the pty master (the operator's own channel). Returns True
    when the bytes were written. This is the single seam a harness-native
    sender (for example an OpenCode server call) can replace without touching
    the schedule or the safety rules; the pty write stays the fallback."""
    try:
        os.write(master, text.encode() + b"\r")
    except OSError:
        return False
    return True


def _report_reminder(log_path, n, quiet_s, text):
    """Audit one delivered agent-facing reminder. Best-effort: a failed
    report must never disturb the run, and the text is recorded only in a
    run-level sidecar, never in the run log the pipeline scans for signals."""
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    line = (f"{stamp} {Path(log_path).name}: reminder #{n} after "
            f"{int(quiet_s)}s quiet to agent input: {text}")
    try:
        print(f"runner: {line}", file=sys.stderr, flush=True)
    except Exception:  # noqa: BLE001 - audit must never break the run
        pass
    try:
        p = Path(log_path).parent / "reminders.log"
        with open(p, "a") as fh:
            fh.write(line + "\n")
    except Exception:  # noqa: BLE001 - audit must never break the run
        pass


class _PtyUnavailable(Exception):
    """The pty could not be set up, so the plain spawn is a safe fallback.
    Raised only before a child is spawned; anything after that fails the
    step instead of re-spawning the harness."""


def _pty_set_size(master, stdin_fd):
    """Mirror the operator's terminal size into the pty (best-effort)."""
    try:
        size = fcntl.ioctl(stdin_fd, termios.TIOCGWINSZ, b"\0" * 8)
    except OSError:
        return
    try:
        fcntl.ioctl(master, termios.TIOCSWINSZ, size)
    except OSError:
        pass


def _run_attached_pty(cmd, log_path, tui_path, when, nonce, cwd, env,
                      stdin_fd, out_fd=None, autosubmit=False, reminder=None):
    """Run cmd under a pty, forwarding stdin->pty and pty->stdout while
    capturing all console output to tui_path. The operator experience is
    unchanged; the runner additionally scans the capture with the same
    signal predicate (nonce included). Operator Ctrl-C keeps today's
    contract (kills the step): the byte still reaches the child first,
    exactly like a tty interrupt, then the step is torn down. `reminder`
    overrides IDLE_REMIND_PLAN for tests.

    Setup failures raise _PtyUnavailable so the caller may fall back to a
    plain spawn. Any failure after the child is spawned terminates it and
    re-raises: a started harness is never silently re-run."""
    try:
        master, slave = pty.openpty()
    except OSError as e:
        raise _PtyUnavailable(f"openpty failed: {e}")
    _pty_set_size(master, stdin_fd)
    try:
        proc = subprocess.Popen(cmd, stdin=slave, stdout=slave,
                                stderr=slave, cwd=cwd, env=env,
                                start_new_session=True)
    except FileNotFoundError:
        os.close(master)
        os.close(slave)
        raise Fail(f"harness binary missing ({cmd[0]} not on PATH)")
    except OSError as e:
        os.close(master)
        os.close(slave)
        raise _PtyUnavailable(f"spawn failed: {e}")
    os.close(slave)
    if out_fd is None:
        out_fd = sys.stdout.fileno()
    try:
        return _pty_forward(proc, master, stdin_fd, out_fd, log_path,
                            tui_path, when, nonce, autosubmit, reminder)
    except _KillStep:
        raise
    except BaseException:
        _terminate(proc)     # never leave a half-driven child behind
        raise
    finally:
        try:
            os.close(master)
        except OSError:
            pass


def _pty_forward(proc, master, stdin_fd, out_fd, log_path, tui_path,
                 when, nonce, autosubmit=False, reminder=None):
    try:
        orig_attrs = termios.tcgetattr(stdin_fd)
    except termios.error:
        orig_attrs = None
    if orig_attrs is not None:
        tty.setraw(stdin_fd)
    resize = False

    def _on_winch(signum, frame):
        nonlocal resize
        resize = True

    try:
        old_winch = signal.signal(signal.SIGWINCH, _on_winch)
    except (ValueError, OSError):
        old_winch = None
    fh = open(tui_path, "wb")
    cap = bytearray()
    stable = 0
    last_key = (-1, -1)
    last_change = time.time()
    next_nudge = last_change + IDLE_NUDGE_S
    plan = reminder or IDLE_REMIND_PLAN
    remind_sent = 0
    resubmit_at = None
    last_operator = 0.0
    submit_next = (time.time() + SUBMIT_FIRST_S) if autosubmit else None
    submit_stop = time.time() + SUBMIT_MAX_S
    try:
        submit_base = Path(log_path).stat().st_size
    except OSError:
        submit_base = -1
    want = ("one of " + "/".join(when)) if when else "a *_DONE/*_APPROVED/*_REJECTED signal"
    if nonce is not None:
        want += f" carrying nonce {nonce}"
    stdin_open = True
    try:
        while True:
            if resize:
                resize = False
                _pty_set_size(master, stdin_fd)
            watched = [master] + ([stdin_fd] if stdin_open else [])
            try:
                r, _, _ = select.select(watched, [], [], AUTOEXIT_POLL_S)
            except (OSError, ValueError):
                r = []
            if stdin_fd in r:
                try:
                    data = os.read(stdin_fd, 65536)
                except OSError:
                    data = b""
                if not data:
                    stdin_open = False
                else:
                    last_operator = time.time()
                    try:
                        os.write(master, data)
                    except OSError:
                        pass
                    if b"\x03" in data:
                        raise _KillStep()
            if master in r:
                try:
                    chunk = os.read(master, 65536)
                except OSError:
                    chunk = b""
                if chunk:
                    try:
                        os.write(out_fd, chunk)
                    except OSError:
                        pass
                    fh.write(chunk)
                    fh.flush()
                    cap += chunk
                    if len(cap) > TUI_TAIL_BYTES:
                        del cap[:len(cap) - TUI_TAIL_BYTES]
            try:
                log_text = Path(log_path).read_text()
                log_size = Path(log_path).stat().st_size
            except OSError:
                log_text, log_size = "", -1
            if submit_next is not None:
                if log_size > submit_base and log_size > 0:
                    submit_next = None      # stage started; stop pressing Enter
                elif time.time() >= submit_next:
                    if time.time() >= submit_stop:
                        submit_next = None
                    else:
                        try:
                            os.write(master, b"\r")
                        except OSError:
                            pass
                        submit_next = time.time() + SUBMIT_RETRY_S
            try:
                tui_size = tui_path.stat().st_size
            except OSError:
                tui_size = -1
            key = (log_size, tui_size)
            grew = key != last_key
            if grew:
                last_key, last_change = key, time.time()
                next_nudge = last_change + IDLE_NUDGE_S
            mirror = _clean_mirror(cap)
            done = (log_done(log_text, when, nonce)
                    or log_done(mirror, when, nonce))
            stable = _poll_stable(done, grew, stable)
            rc = proc.poll()
            if rc is None and stable >= AUTOEXIT_STABLE_POLLS:
                time.sleep(AUTOEXIT_GRACE_S)
                _terminate(proc)
                rc = proc.poll()
            if rc is not None:
                break
            now = time.time()
            if rc is None and not done:
                try:
                    # A reminder must never abort the pty run: an exception
                    # here would otherwise make run_attached re-spawn the
                    # harness. Everything below is best-effort.
                    started = log_size > 0
                    if resubmit_at is not None and now >= resubmit_at:
                        # The first Enter looked swallowed (no signal yet):
                        # press it once more, then stop. Safe because the
                        # reminder is only sent when the operator has never
                        # typed, so no partial human input can be submitted.
                        if not done:
                            try:
                                os.write(master, b"\r")
                            except OSError:
                                pass
                        resubmit_at = None
                    if not _looks_like_prompt(mirror) and reminder_due(
                            now, last_change, remind_sent, last_operator,
                            plan, started=started):
                        if _deliver_reminder(master, plan["text"]):
                            remind_sent += 1
                            rs = plan.get("resubmit_s", 0)
                            resubmit_at = now + rs if rs else None
                            _report_reminder(log_path, remind_sent,
                                             now - last_change, plan["text"])
                        else:
                            remind_sent = plan["max"]   # stop trying this run
                except Exception:  # noqa: BLE001 - never abort the pty run
                    pass
                if now >= next_nudge:
                    print(f"runner: still no completion signal ({want}) in "
                          f"{log_path} after {int(IDLE_NUDGE_S)} s idle. If the "
                          f"agent says it is done, tell it to run: "
                          f"printf '%s\\n' '<SIGNAL>{' ' + nonce if nonce else ''}'"
                          f" >> {log_path}",
                          file=sys.stderr, flush=True)
                    next_nudge = now + IDLE_NUDGE_S
    except _KillStep:
        _terminate(proc)
        raise KeyboardInterrupt()
    finally:
        if old_winch is not None:
            signal.signal(signal.SIGWINCH, old_winch)
        if orig_attrs is not None:
            termios.tcsetattr(stdin_fd, termios.TCSADRAIN, orig_attrs)
        fh.close()
    # Drain any output the child wrote just before exiting.
    for _ in range(20):
        try:
            r, _, _ = select.select([master], [], [], 0)
        except (OSError, ValueError):
            break
        if master not in r:
            break
        try:
            chunk = os.read(master, 65536)
        except OSError:
            break
        if not chunk:
            break
        try:
            os.write(out_fd, chunk)
        except OSError:
            pass
        with open(tui_path, "ab") as fh2:
            fh2.write(chunk)
    rc = proc.poll()
    if rc is None:
        try:
            rc = proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            rc = proc.wait(timeout=5)
    if not Path(log_path).is_file():
        raise Fail(f"run log missing: {log_path} (agent never wrote it)")
    text = Path(log_path).read_text()
    if not text.strip():
        raise Fail(f"run log empty: {log_path}")
    mirror_signal = None
    if find_signal(text, when, nonce) is None:
        mirror_signal = find_signal(
            _clean_mirror(_tail_text(tui_path)), when, nonce)
    return text, rc, {"tui_log": str(tui_path), "mirror_signal": mirror_signal}


# Terminal restore: full-screen TUI harnesses enable mouse reporting on the
# operator's real terminal (forwarded through the pty). If the session is
# closed before the harness disables it, scrolls keep arriving as escape
# sequences (numbers and characters printed on the terminal). Re-disabling
# after every attached run is harmless when already off.
_TERM_RESTORE = (b"\x1b[?1000l\x1b[?1002l\x1b[?1003l\x1b[?1006l\x1b[?1015l"
                 b"\x1b[?25h")


def _restore_term():
    """Disable mouse reporting and reshow the cursor (best-effort)."""
    try:
        if sys.stdout.isatty():
            sys.stdout.buffer.write(_TERM_RESTORE)
            sys.stdout.buffer.flush()
    except (OSError, ValueError):
        pass


def run_attached(cmd, log_path, when, nonce=None, cwd=None, env=None,
                 autosubmit=False, reminder=None):
    """Run a harness attached in the foreground and wait for its signal.

    Under a terminal the child runs under a pty: the operator sees the
    identical interface, while all console output is also captured to
    `<step>-task-r<N>.tui.log` and scanned with the same signal predicate
    (a console-only signal still routes, marked signal_via="mirror"). Without a
    terminal, or when the pty is unavailable, falls back to a plain
    attached spawn with inherited stdio (no agent input channel, so no
    agent-facing idle reminder there; only the stderr warning).

    Once the final signal is stable on a quiescent log (AUTOEXIT_STABLE_POLLS
    consecutive polls with no growth), wait AUTOEXIT_GRACE_S so the operator
    can read the on-screen summary, then close the session
    (SIGINT -> SIGTERM -> SIGKILL). Operator Ctrl-C kills the step;
    the KeyboardInterrupt propagates (runner exits 130, resume kept).
    Returns (log_text, returncode, info) where info carries tui_log, the
    chosen attach mode, and an optional mirror_signal.

    The plain spawn is a fallback only for pty *setup* failure. If the pty
    child already started, a failure fails the step instead of re-spawning
    the harness (a double run would double-spend and race on the run dir)."""
    pty_ok = _HAVE_PTY and sys.stdin.isatty() and sys.stdout.isatty()
    print(f"runner: attach mode: {'pty (console capture on)' if pty_ok else 'plain (no console capture)'}",
          file=sys.stderr, flush=True)
    try:
        tui_path = Path(log_path).with_name(Path(log_path).stem + ".tui.log")
        if pty_ok:
            try:
                text, rc, info = _run_attached_pty(
                    cmd, log_path, tui_path, when, nonce,
                    cwd, env, sys.stdin.fileno(),
                    None, autosubmit, reminder)
                info["attach"] = "pty"
                return text, rc, info
            except _PtyUnavailable as e:
                print(f"runner: pty unavailable ({e}); plain spawn",
                      file=sys.stderr, flush=True)
        text, rc, info = _run_attached_plain(cmd, log_path, when, nonce, cwd, env)
        info["attach"] = "plain"
        return text, rc, info
    finally:
        _restore_term()


def _run_attached_plain(cmd, log_path, when, nonce, cwd, env):
    """Attached spawn with inherited stdio (no console capture)."""
    try:
        proc = subprocess.Popen(cmd, cwd=cwd, env=env)
    except FileNotFoundError:
        raise Fail(f"harness binary missing ({cmd[0]} not on PATH)")
    _poll_loop(proc, log_path, when, nonce, lambda: None)
    if not Path(log_path).is_file():
        # No log and no terminal is the common shape here: several harness
        # CLIs refuse to start without a TTY and exit before writing anything,
        # so the bare "agent never wrote it" sends the operator looking for a
        # stuck agent instead of at the pipe they started the runner through.
        hint = ""
        if not (sys.stdin.isatty() and sys.stdout.isatty()):
            hint = (". This step ran without a TTY, and some harness CLIs "
                    "refuse to start in that mode. Start the runner from a "
                    "real terminal, or launch it through phase-driver.sh, "
                    "which provides the pty; do not pipe or redirect it")
        raise Fail(f"run log missing: {log_path} (agent never wrote it){hint}")
    text = Path(log_path).read_text()
    if not text.strip():
        raise Fail(f"run log empty: {log_path}")
    return text, proc.returncode, {"tui_log": None, "mirror_signal": None}


def _poll_loop(proc, log_path, when, nonce, mirror_size):
    """Shared auto-exit poll: quiescence-gated stability plus the idle
    nudge. mirror_size() reports the console-capture size (0 when none);
    any growth in either channel resets stability. Returns when the child
    exits; closes it after the grace window once the signal is stable."""
    stable = 0
    last_key = (-1, -1)
    last_change = time.time()
    next_nudge = last_change + IDLE_NUDGE_S
    want = ("one of " + "/".join(when)) if when else "a *_DONE/*_APPROVED/*_REJECTED signal"
    if nonce is not None:
        want += f" carrying nonce {nonce}"
    try:
        while proc.poll() is None:
            time.sleep(AUTOEXIT_POLL_S)
            try:
                cur_size = Path(log_path).stat().st_size
            except OSError:
                cur_size = -1
            key = (cur_size, mirror_size())
            grew = key != last_key
            if grew:
                last_key, last_change = key, time.time()
                next_nudge = last_change + IDLE_NUDGE_S
            try:
                done = log_done(Path(log_path).read_text(), when, nonce)
            except OSError:
                done = False
            stable = _poll_stable(done, grew, stable)
            if stable >= AUTOEXIT_STABLE_POLLS:
                time.sleep(AUTOEXIT_GRACE_S)
                _terminate(proc)
            if proc.poll() is None and time.time() >= next_nudge and not done:
                # The agent may have finished in chat but forgotten the log
                # line. Nudge, repeat.
                print(f"runner: still no completion signal ({want}) in "
                      f"{log_path} after {int(IDLE_NUDGE_S)} s idle. If the "
                      f"agent says it is done, tell it to run: "
                      f"printf '%s\\n' '<SIGNAL>{' ' + nonce if nonce else ''}'"
                      f" >> {log_path}",
                      file=sys.stderr, flush=True)
                next_nudge = time.time() + IDLE_NUDGE_S
    except KeyboardInterrupt:
        _terminate(proc)
        raise


def _record_sync(run, name, res):
    """Persist one sync result beside the run state and echo it to stderr."""
    try:
        (run._run_dir / f"{name}.json").write_text(json.dumps(res, indent=2))
    except OSError:
        pass
    print(json.dumps(res, indent=2), file=sys.stderr)


def preflight_sync(run, commit_run_state=False):
    """Bring both checkouts in line with their remotes before a fresh start.

    Fails closed: a base that cannot be brought in line raises Fail so the
    run stops with a clear message instead of starting on it. Never discards
    or rewrites local work (see gitsync).

    commit_run_state remains available for callers that already own the
    reservation. The normal runner calls it only after its exact phase claim
    succeeds."""
    res = gitsync.sync_all(run.repo, "start")
    _record_sync(run, "sync-before-start", res)
    if not res["ok"]:
        raise Fail(f"sync blocked before start: {res['summary']}")
    if commit_run_state:
        clean = gitsync.commit_leftover_run_state(
            run.repo,
            f"pipeline: commit leftover run state before phase "
            f"{int(run.inputs['phase_number'])}",
            phase=run.inputs["phase_number"])
        _record_sync(run, "sync-before-start-clean", clean)
        if not clean["ok"]:
            raise Fail(f"dirty working tree before start: {clean['summary']}")
    return res


def commit_start_run_state(run):
    """Publish only this phase's run leftovers after its claim is secured."""
    clean = gitsync.commit_leftover_run_state(
        run.repo,
        f"pipeline: commit leftover run state before phase "
        f"{int(run.inputs['phase_number'])}",
        phase=run.inputs["phase_number"])
    _record_sync(run, "sync-before-start-clean", clean)
    if not clean["ok"]:
        raise Fail(f"dirty working tree before start: {clean['summary']}")
    return clean


def drive(run, pipe, invoke, resumed=None):
    """Execute the routing loop. invoke(harness, task_path, log_path,
    usage_path, when, nonce) returns (output_text, meta).

    resumed restores a previous attempt (outputs, visits, harness_use,
    prev_step, transcript, events, current). After every routing decision
    the state is saved to run_dir/resume.json; completed/rejected leave no
    resume file behind (main() deletes it), but blocked keeps it so the
    operator can fix the blocker and --resume.
    """
    phase = int(run.inputs["phase_number"])
    run_id = f"{run.inputs.get('run_label', 'phase')}-{phase:06d}"
    # Once a live invocation begins, prior-step context must come from the
    # completion ledger rather than a planned rotation slot.
    run.require_authoritative = True
    if run.persist_rotation and not run.rotation_key:
        raise Fail("rotation persistence needs a key; main() sets it "
                   "from the pipeline path")
    if resumed:
        if not isinstance(resumed, dict) or resumed.get("current") not in run.steps:
            raise Fail("resume.json is corrupt or its step resolves nowhere")
        run.outputs = resumed.get("outputs", {})
        run.visits = resumed.get("visits", {})
        run.harness_use = resumed.get("harness_use", {})
        if run.persist_rotation:
            for sid, n in load_rotation(run.repo, run.rotation_key).items():
                run.harness_use[sid] = max(run.harness_use.get(sid, 0), n)
        run.prev_step = resumed.get("prev_step")
        current = resumed["current"]
        transcript = resumed.get("transcript", [])
        events = resumed.get("events", [])
        # Crash recovery: a pending commit means the previous invocation
        # accepted a signal and wrote its intent before all durable files
        # landed. Replay it idempotently instead of re-invoking the harness.
        pending = read_pending_commit(run)
        if pending is not None:
            resume_after = apply_pending_commit(run, pending)
            clear_pending_commit(run)
            transcript = list(resume_after.get("transcript", []))
            events = list(resume_after.get("events", []))
            if pending.get("kind") == "terminal":
                return {"run_id": run_id, "phase": f"{phase:06d}",
                        "state": pending.get("terminal_state", "completed"),
                        "transcript": transcript, "events": events}
            current = resume_after.get("current", current)
            run.prev_step = resume_after.get("prev_step")
        # Idempotency fallback: the completed step's ledger entry and output
        # are both durable, but advancement never landed (e.g. crash after
        # clearing a pending commit for a terminal step). Re-derive routing
        # from the ledger instead of re-running the harness.
        else:
            completed = _already_completed(run, current)
            if completed is not None:
                via, routed_to = completed.get("via"), completed.get("routed_to")
                if routed_to in pipe["ends"]:
                    # Terminal already completed; return without re-invoking.
                    return {"run_id": run_id, "phase": f"{phase:06d}",
                            "state": routed_to, "transcript": transcript,
                            "events": events}
                if isinstance(routed_to, str) and routed_to in run.steps:
                    run.prev_step, current = current, routed_to
                    write_json_atomic(run._run_dir / "resume.json", {
                        "current": current, "outputs": run.outputs,
                        "visits": run.visits, "harness_use": run.harness_use,
                        "prev_step": run.prev_step,
                        "transcript": transcript, "events": events})
        verify_ledger(run, run.outputs, current)
        # Persist deterministic legacy migrations on live resume so the
        # on-disk ledger becomes authoritative. Ambiguous histories already
        # failed closed in verify_ledger above.
        try:
            ledger_now = run._ledger()
        except Fail:
            ledger_now = None
        if ledger_now is not None:
            for sid in list(ledger_now.get("order", [])):
                entry_now = ledger_now["steps"].get(sid)
                if not isinstance(entry_now, dict):
                    continue
                if entry_now.get("authoritative") is True and "task_sha256" in entry_now:
                    continue
                try:
                    fresh = run._ledger()
                    run._migrate_legacy_entry(sid, fresh, fresh["steps"][sid], persist=True)
                    ledger_now = run._ledger()
                except Fail:
                    # verify_ledger already proved this cannot happen for
                    # deterministic entries; any failure here is re-raised
                    # as an explicit recovery error below.
                    raise
    else:
        current, transcript, events = pipe["start"], [], []
        if run.persist_rotation:
            run.harness_use = load_rotation(run.repo, run.rotation_key)
        # A stale pending commit without resume state means a previous fresh
        # start crashed mid-commit. Replay it before starting over when it
        # names a valid step; otherwise fail closed.
        pending = read_pending_commit(run)
        if pending is not None:
            resume_after = apply_pending_commit(run, pending)
            clear_pending_commit(run)
            transcript = list(resume_after.get("transcript", []))
            events = list(resume_after.get("events", []))
            if pending.get("kind") == "terminal":
                return {"run_id": run_id, "phase": f"{phase:06d}",
                        "state": pending.get("terminal_state", "completed"),
                        "transcript": transcript, "events": events}
            current = resume_after.get("current", current)
            run.prev_step = resume_after.get("prev_step")
    reframe = resumed is not None
    # The harness map is decided once for the whole run, before the first
    # invocation: every round of a loop step, every retry, and every prompt
    # names the same model. main() has already saved it to the run dir; here
    # it is built (or reused) from the rotation offsets loaded above, so a
    # step with nothing installed halts before any task, log, ledger, or
    # resume file is written.
    run.ensure_plan()

    def save(nxt):
        write_json_atomic(run._run_dir / "resume.json", {
            "current": nxt, "outputs": run.outputs, "visits": run.visits,
            "harness_use": run.harness_use, "prev_step": run.prev_step,
            "transcript": transcript, "events": events})

    Guard = 10000
    while True:
        if len(events) >= Guard:
            raise Fail("routing loop exceeded 10000 steps (uncapped cycle?)")
        heartbeat = getattr(run, "reservation_heartbeat", None)
        if heartbeat is not None:
            heartbeat.check()
        s = run.steps[current]
        # The planned harness for this run, with the availability skips the
        # plan recorded. A halt here has touched no task, log, snapshot,
        # ledger, or resume file. The used index is recorded in the
        # pre-invocation resume state (persisted by save below) so a retry
        # and an operator --mark-done both reproduce the exact harness; only
        # the accepted invocation advances the counter past the skips
        # (next_count), so a failed attempt re-skips and a later run does not
        # retry a known-missing head.
        harness, skipped, used_index, next_count = run.select_harness(current)
        run.harness_use[current] = used_index
        run.visits[current] = run.visits.get(current, 0) + 1
        t0 = time.time()
        if "snapshot" in s:
            src = run._run_dir / s["snapshot"]["from"]
            dst = run._run_dir / s["snapshot"]["to"]
            if not dst.exists() and src.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
        agent = display_name(harness)
        prompt = run.render_task(current, harness_name=agent)
        # Fresh nonce per invocation, appended to the invoked file: only a
        # signal line carrying it counts (see find_signal).
        nonce = secrets.token_hex(NONCE_BYTES)
        prompt += NONCE_FOOTER.format(nonce=nonce)
        task_path = run._run_dir / f"{current}-task-r{run.visits[current]}.md"
        try:
            task_path.write_text(prompt)
        except OSError as e:
            raise Fail(f"step {current}: cannot write task file {task_path} ({e})")
        n = run.visits[current]
        invoke_path, resume_file = task_path, None
        if reframe:
            reframe = False
            framed = resume_frame(run, current) + "\n\n" + prompt
            resume_path = run._run_dir / f"{current}-resume-r{n}.md"
            try:
                resume_path.write_text(framed)
            except OSError as e:
                raise Fail(f"step {current}: cannot write resume file ({e})")
            invoke_path, resume_file = resume_path, str(resume_path)
        save(current)
        log_path = task_path.with_suffix(".log")
        usage_path = (run._run_dir / f"{current}-usage-r{n}.json"
                      if harness.split(":", 1)[0] == "hermes" else None)
        when_keys = list(s["when"]) if "when" in s else None
        output, meta = invoke(harness, invoke_path, log_path, usage_path, when_keys,
                              nonce, sid=current, skipped=skipped)
        heartbeat = getattr(run, "reservation_heartbeat", None)
        if heartbeat is not None:
            heartbeat.check()
        # The rotation slot is consumed only after the signal and all
        # completion gates pass below. A failed, blocked, or interrupted
        # attempt must retry the same harness.
        run.outputs[current] = output
        sig = find_signal(output, when_keys, nonce)
        via_mirror = False
        if sig is None and meta.get("mirror_signal"):
            # The agent signalled on its console but never wrote the run
            # log: route on the captured line, labelled as such. The log
            # text stays the recorded output, annotated with provenance.
            sig = meta["mirror_signal"]
            via_mirror = True
            run.outputs[current] = (
                output
                + f"\n[signal observed on harness console, not in run log: "
                f"{sig}]\nFull console capture: {meta.get('tui_log')}\n")
        if sig is None:
            raise Fail(f"step {current}: missing expected signal; last line was: "
                       f"{last_line(output)}")
        head = sig.split()[0].rstrip(":") if sig.split() else ""
        event = {"step": current, "harness": harness, "agent": agent,
                 "task_file": str(task_path),
                 "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                 "duration_s": round(time.time() - t0, 3),
                 "visits": run.visits[current], "signal": sig}
        if skipped:
            event["skipped"] = [{"harness": h, "missing_binary": b}
                                for h, b in skipped]
        if resume_file:
            event["resume_file"] = resume_file
        event.update({k: v for k, v in meta.items() if v is not None})
        if via_mirror:
            event["signal_via"] = "mirror"
        if head.endswith("BLOCKED"):
            event["via"] = "blocked"
            event["routed_to"] = "blocked"
            transcript.append({"step": current, "harness": harness,
                               "agent": agent, "signal": sig})
            events.append(event)
            # Blocked is resumable: persist the blocked step's output and
            # visits so the operator can fix the blocker and --resume.
            save(current)
            return {"run_id": run_id, "phase": f"{phase:06d}",
                    "state": "blocked", "transcript": transcript, "events": events}
        if "end" in s:
            event["via"] = "end"
            event["routed_to"] = s["end"]
            transcript.append({"step": current, "harness": harness,
                               "agent": agent, "signal": sig})
            events.append(event)
            harness_use_after = dict(run.harness_use)
            harness_use_after[current] = next_count
            resume_after = {"current": current, "outputs": dict(run.outputs),
                            "visits": dict(run.visits),
                            "harness_use": dict(harness_use_after),
                            "prev_step": run.prev_step,
                            "transcript": list(transcript), "events": list(events)}
            record = {"version": COMMIT_VERSION, "kind": "terminal",
                      "step": current, "signal": sig, "harness": harness,
                      "task_file": run_relative_path(run, task_path),
                      "output": run.outputs[current],
                      "via": "end", "routed_to": s["end"],
                      "harness_use_after": dict(harness_use_after),
                      "resume_after": resume_after,
                      "terminal_state": s["end"],
                      "transcript_after": list(transcript),
                      "events_after": list(events)}
            write_pending_commit(run, record)
            run.harness_use = dict(harness_use_after)
            apply_pending_commit(run, record)
            clear_pending_commit(run)
            return {"run_id": run_id, "phase": f"{phase:06d}",
                    "state": s["end"], "transcript": transcript, "events": events}
        key = match_signal(sig, s["when"])
        if key is None:
            raise Fail(f"step {current}: missing expected signal; last line was: {sig}")
        transcript.append({"step": current, "harness": harness,
                           "agent": agent, "signal": sig})
        if "require_file" in s or "skip_when_empty" in s:
            fpath = run._run_dir / s["require_file"] if s.get("require_file") else None
            if fpath is None:
                empty = True
            elif not fpath.is_file():
                raise Fail(f"step {current}: signal received but {fpath} missing")
            else:
                empty = artifact_is_empty(fpath)
            if "skip_when_empty" in s and empty:
                event["via"] = "skip"
                event["routed_to"] = s["skip_when_empty"]
                events.append(event)
                nxt = s["skip_when_empty"]
                harness_use_after = dict(run.harness_use)
                harness_use_after[current] = next_count
                resume_after = {"current": nxt, "outputs": dict(run.outputs),
                                "visits": dict(run.visits),
                                "harness_use": dict(harness_use_after),
                                "prev_step": current,
                                "transcript": list(transcript), "events": list(events)}
                record = {"version": COMMIT_VERSION, "kind": "advance",
                          "step": current, "signal": sig, "harness": harness,
                          "task_file": run_relative_path(run, task_path),
                          "output": run.outputs[current],
                          "via": "skip", "routed_to": nxt,
                          "harness_use_after": dict(harness_use_after),
                          "resume_after": resume_after,
                          "next_current": nxt}
                write_pending_commit(run, record)
                run.harness_use = dict(harness_use_after)
                run.prev_step, current = current, nxt
                apply_pending_commit(run, record)
                clear_pending_commit(run)
                if current in pipe["ends"]:
                    return {"run_id": run_id, "phase": f"{phase:06d}",
                            "state": current, "transcript": transcript, "events": events}
                continue
        target = s["when"][key]
        loop_exhausted = (target in run.visits and "max_rounds" in s
                          and run.visits[current] >= s["max_rounds"])
        if loop_exhausted and "on_exhausted" not in s:
            raise Fail(f"step {current}: loop cap hit with no on_exhausted")
        event["via"] = "edge"
        event["routed_to"] = target
        events.append(event)
        harness_use_after = dict(run.harness_use)
        harness_use_after[current] = next_count
        if target in pipe["ends"]:
            event["via"] = "edge-end"
            # Mutating the appended dict keeps transcript/events consistent;
            # rebuild the stored copies from the mutated lists.
            resume_after = {"current": current, "outputs": dict(run.outputs),
                            "visits": dict(run.visits),
                            "harness_use": dict(harness_use_after),
                            "prev_step": run.prev_step,
                            "transcript": list(transcript), "events": list(events)}
            record = {"version": COMMIT_VERSION, "kind": "terminal",
                      "step": current, "signal": sig, "harness": harness,
                      "task_file": run_relative_path(run, task_path),
                      "output": run.outputs[current],
                      "via": "edge-end", "routed_to": target,
                      "harness_use_after": dict(harness_use_after),
                      "resume_after": resume_after,
                      "terminal_state": target,
                      "transcript_after": list(transcript),
                      "events_after": list(events)}
            write_pending_commit(run, record)
            run.harness_use = dict(harness_use_after)
            apply_pending_commit(run, record)
            clear_pending_commit(run)
            return {"run_id": run_id, "phase": f"{phase:06d}",
                    "state": target, "transcript": transcript, "events": events}
        if loop_exhausted:
            event["via"] = "exhausted"
            resume_after = {"current": current, "outputs": dict(run.outputs),
                            "visits": dict(run.visits),
                            "harness_use": dict(harness_use_after),
                            "prev_step": run.prev_step,
                            "transcript": list(transcript), "events": list(events)}
            record = {"version": COMMIT_VERSION, "kind": "terminal",
                      "step": current, "signal": sig, "harness": harness,
                      "task_file": run_relative_path(run, task_path),
                      "output": run.outputs[current],
                      "via": "exhausted", "routed_to": s["on_exhausted"],
                      "harness_use_after": dict(harness_use_after),
                      "resume_after": resume_after,
                      "terminal_state": s["on_exhausted"],
                      "transcript_after": list(transcript),
                      "events_after": list(events)}
            write_pending_commit(run, record)
            run.harness_use = dict(harness_use_after)
            apply_pending_commit(run, record)
            clear_pending_commit(run)
            return {"run_id": run_id, "phase": f"{phase:06d}",
                    "state": s["on_exhausted"], "transcript": transcript, "events": events}
        nxt = target
        resume_after = {"current": nxt, "outputs": dict(run.outputs),
                        "visits": dict(run.visits),
                        "harness_use": dict(harness_use_after),
                        "prev_step": current,
                        "transcript": list(transcript), "events": list(events)}
        record = {"version": COMMIT_VERSION, "kind": "advance",
                  "step": current, "signal": sig, "harness": harness,
                  "task_file": run_relative_path(run, task_path),
                  "output": run.outputs[current],
                  "via": "edge", "routed_to": nxt,
                  "harness_use_after": dict(harness_use_after),
                  "resume_after": resume_after,
                  "next_current": nxt}
        write_pending_commit(run, record)
        run.harness_use = dict(harness_use_after)
        run.prev_step, current = current, nxt
        apply_pending_commit(run, record)
        clear_pending_commit(run)


def self_test(run, live=False):
    """Static harness checks (no inference spend) plus optional live probes."""
    ensure_harness_path()
    seen, checks = set(), []

    def check(name, ok, detail=""):
        checks.append({"check": name,
                       "ok": None if ok is None else bool(ok), "detail": detail})

    for sid in run.steps:
        meta, _ = run.stages[sid]
        hs = meta["harness"] if isinstance(meta["harness"], list) else [meta["harness"]]
        for h in hs:
            if h in seen:
                continue
            seen.add(h)
            cli, provider, model, effort = parse_harness(h)
            provider = resolve_provider(cli, provider)
            model = resolve_model(cli, provider, model)
            binary = {"cursor": "agent", "agy": "agy", "hermes": "hermes",
                      "opencode": "opencode", "cmd": CMD_BINARY}[cli]
            path = shutil.which(binary)
            check(f"{h} binary", path is not None, path or "not on PATH")
            if path is None:
                continue
            full = f"{provider}/{model}" if provider else model
            if cli == "agy":
                try:
                    result = subprocess.run(["agy", "models"], capture_output=True,
                                             text=True, timeout=60)
                    if result.returncode != 0:
                        check(f"{h} model listed", None,
                              "agy model catalog unavailable")
                    else:
                        out = result.stdout
                        check(f"{h} model listed", full in out,
                              "slug in agy models" if full in out else "slug missing")
                except subprocess.TimeoutExpired:
                    check(f"{h} model listed", False, "agy models timed out")
            elif cli == "opencode" and provider:
                try:
                    # v2 only: `opencode models` takes no provider argument;
                    # it lists every configured provider's catalog at once.
                    result = subprocess.run(["opencode", "models"],
                                             capture_output=True, text=True,
                                             timeout=120)
                    if result.returncode != 0:
                        check(f"{h} model listed", None,
                              "opencode model catalog unavailable")
                    else:
                        out = result.stdout
                        check(f"{h} model listed", model in out,
                              "slug in opencode models" if model in out else "slug missing")
                except subprocess.TimeoutExpired:
                    check(f"{h} model listed", False, "opencode models timed out")
            elif cli == "cmd":
                cmd_ok, cmd_detail = cmd_catalog_check(full, effort)
                check(f"{h} model listed", cmd_ok, cmd_detail)
            elif cli == "hermes":
                check(f"{h} model listed", None, "not statically verifiable; needs live probe")
            if live:
                # Print-mode probes: self-test must not open interactive
                # TUIs, so each cli gets its non-interactive form.
                if cli == "cursor":
                    cmd = (["agent", "-p"] + (["--model", full]
                            if full != "auto" else [])
                           + ["Reply with exactly: SELFTEST_OK"])
                elif cli == "agy":
                    cmd = ["agy", "--model", full,
                           "-p", "Reply with exactly: SELFTEST_OK"]
                elif cli == "cmd":
                    # Headless probe (never the interactive form): --yolo so
                    # the probe can act if the model chooses to, one-word reply.
                    cmd = ([CMD_BINARY, "-p", "--yolo", "--skip-onboarding",
                            "--no-session"]
                           + (["-m", full] if full != "auto" else [])
                           + (["--effort", effort] if effort else [])
                           + ["Reply with exactly: SELFTEST_OK"])
                elif cli == "hermes":
                    cmd = ["hermes", "-z", "Reply with exactly: SELFTEST_OK"]
                    if provider:
                        cmd += ["--provider", provider, "-m", model]
                    elif model != "auto":
                        cmd += ["-m", model]
                else:
                    cmd = (["opencode", "run"]
                           + (["-m", full] if full != "auto" else [])
                           + ["Reply with exactly: SELFTEST_OK"])
                try:
                    import concurrent.futures as cf
                    with cf.ThreadPoolExecutor(max_workers=1) as ex:
                        fut = ex.submit(subprocess.run, cmd, capture_output=True,
                                        text=True, timeout=300)
                        out = fut.result().stdout
                    check(f"{h} live probe", "SELFTEST_OK" in out,
                          last_line(out)[:120])
                except Exception as e:  # noqa: BLE001 - probe must report, not crash
                    check(f"{h} live probe", False, f"{type(e).__name__}: {e}")

    import io
    import tempfile
    # Signal convention: last_line strips one leading ISO-8601 timestamp from
    # the final log line, then match_signal matches on the bare signal word.
    check("phase policy: parked floor", not is_runnable_phase(PARKED_PHASE_FLOOR)
          and is_runnable_phase(PARKED_PHASE_FLOOR - 1))
    check("signal parse: bare", match_signal(
        last_line("work done\nDEVELOPER_DONE"), ["DEVELOPER_DONE"]) == "DEVELOPER_DONE")
    check("signal parse: timestamped", match_signal(
        last_line("2026-09-18T02:48:45+05:30 ADVERSARY_DONE findings=/r/findings.json"),
        ["ADVERSARY_DONE"]) == "ADVERSARY_DONE")
    check("signal parse: timestamped blocked", last_line(
        "2026-09-18T00:00:00Z DEVELOPER_BLOCKED: reason").startswith("DEVELOPER_BLOCKED"))
    check("signal parse: timestamped non-signal rejected", match_signal(
        last_line("2026-09-18T00:00:00Z FINISH report ready"), ["ADVERSARY_DONE"]) is None)
    check("signal parse: bare timestamp untouched",
          last_line("2026-09-18T00:00:00Z") == "2026-09-18T00:00:00Z")

    # Scan-back tolerance (missing-signal hang fix): journal prefixes and
    # trailing lines cannot hide a signal; table rows still do not match.
    check("signal scan: journal-prefixed", find_signal(
        "2026-09-18T14:55:29Z | r1 | REMEDIATOR_DONE",
        ["REMEDIATOR_DONE"]) == "REMEDIATOR_DONE")
    check("signal scan: trailing summary tolerated", find_signal(
        "REMEDIATOR_DONE\nall cleaned up\n",
        ["REMEDIATOR_DONE"]) == "REMEDIATOR_DONE")
    check("signal scan: table row is not a signal", find_signal(
        "| Remediator | r1 | OpenCode CLI | done |",
        ["REMEDIATOR_DONE"]) is None)
    check("signal scan: summary without signal is None", find_signal(
        "2026-09-18T14:55:29Z | r1 | finish | F-01 stuff",
        ["REMEDIATOR_DONE"]) is None)

    # Nonce enforcement: only the invoked run's token counts; BLOCKED is
    # exempt; JSON signal objects unfold to their tokens.
    check("signal nonce: matching token accepted", find_signal(
        "REMEDIATOR_DONE 9f3a2b1c", ["REMEDIATOR_DONE"], "9f3a2b1c")
        == "REMEDIATOR_DONE 9f3a2b1c")
    check("signal nonce: bare echo rejected", find_signal(
        "REMEDIATOR_DONE", ["REMEDIATOR_DONE"], "9f3a2b1c") is None)
    check("signal nonce: wrong token rejected", find_signal(
        "REMEDIATOR_DONE 00000000", ["REMEDIATOR_DONE"], "9f3a2b1c") is None)
    check("signal nonce: blocked exempt", find_signal(
        "X_BLOCKED: reason", ["SOME_DONE"], "9f3a2b1c")
        == "X_BLOCKED: reason")
    check("signal nonce: args then token accepted", find_signal(
        "ADVERSARY_DONE findings=/r/f.json 9f3a2b1c", ["ADVERSARY_DONE"],
        "9f3a2b1c") == "ADVERSARY_DONE findings=/r/f.json 9f3a2b1c")
    check("signal json: object accepted", find_signal(
        '{"signal": "REMEDIATOR_DONE", "nonce": "9f3a2b1c"}',
        ["REMEDIATOR_DONE"], "9f3a2b1c") == "REMEDIATOR_DONE 9f3a2b1c")
    check("signal json: wrong nonce rejected", find_signal(
        '{"signal": "REMEDIATOR_DONE", "nonce": "00000000"}',
        ["REMEDIATOR_DONE"], "9f3a2b1c") is None)
    check("signal json: non-signal object ignored", find_signal(
        '{"findings": []}', ["REMEDIATOR_DONE"], "9f3a2b1c") is None)

    # Console-mirror cleaning: ANSI escapes and carriage redraws vanish.
    check("mirror clean: strips ansi",
          _clean_mirror("\x1b[32mDONE a1b2c3d4\x1b[0m\r\n")
          == "DONE a1b2c3d4\n")
    check("mirror clean: ansi signal matches",
          find_signal(_clean_mirror("\x1b[32mDONE a1b2c3d4\x1b[0m"),
                      ["DONE"], "a1b2c3d4") == "DONE a1b2c3d4")

    # Pty mirror path, pinned: a fast script's console output lands in the
    # capture file while the log signal routes normally. Direct call with
    # /dev/null stdin (no terminal in self-test).
    if _HAVE_PTY:
        pt = Path(tempfile.mkdtemp(prefix="pty"))
        tlog = pt / "s-task-r1.log"
        tui = pt / "s-task-r1.tui.log"
        (pt / "fak.py").write_text(
            "import sys\n"
            "open(sys.argv[1], 'w').write('WORK DONE a1b2c3d4\\n')\n"
            "print('chat summary here')\n")
        devnull = os.open(os.devnull, os.O_RDONLY)
        devnull_w = os.open(os.devnull, os.O_WRONLY)
        try:
            ptext, prc, pinfo = _run_attached_pty(
                [sys.executable, str(pt / "fak.py"), str(tlog)],
                tlog, tui, ["WORK_DONE"], "a1b2c3d4", str(pt), None,
                devnull, devnull_w)
        finally:
            os.close(devnull)
            os.close(devnull_w)
        check("pty mirror: runs and captures",
              prc == 0 and "chat summary here" in tui.read_text()
              and ptext.splitlines()[-1] == "WORK DONE a1b2c3d4"
              and pinfo.get("mirror_signal") is None,
              "console captured, log signal wins")

    # Idle reminder, pinned: a quiet pty harness with no signal receives the
    # reminder on its own input (stdin), the reminder lands in a sidecar audit
    # file and never in the scanned run log, and the text is never a signal.
    if _HAVE_PTY:
        rp = Path(tempfile.mkdtemp(prefix="remind"))
        rlog = rp / "s-task-r1.log"
        rtui = rp / "s-task-r1.tui.log"
        rseen = rp / "seen.bin"
        (rp / "wait.py").write_text(
            "import os, select, sys, time\n"
            "open(sys.argv[1], 'w').write('working, no signal yet\\n')\n"
            "seen = open(sys.argv[2], 'wb')\n"
            "end = time.time() + 10\n"
            "while time.time() < end:\n"
            "    r, _, _ = select.select([0], [], [], 0.2)\n"
            "    if not r:\n"
            "        continue\n"
            "    data = os.read(0, 4096)\n"
            "    if not data:\n"
            "        break\n"
            "    seen.write(data)\n"
            "    seen.flush()\n"
            "    if b'\\n' in data or b'\\r' in data:\n"
            "        break\n"
            "seen.close()\n")
        fast = dict(IDLE_REMIND_PLAN, first_s=0.4, backoff=2.0, max=2,
                    text="NUDGE_MARKER_XYZ")
        rdevnull = os.open(os.devnull, os.O_RDONLY)
        rdevnull_w = os.open(os.devnull, os.O_WRONLY)
        # Keep these two fds open for every sub-test below: closing and
        # reopening devnull can hand a later pty the same fd number, which
        # would feed the console capture back into the pty master.
        rtext, rrc, rinfo = _run_attached_pty(
            [sys.executable, str(rp / "wait.py"), str(rlog), str(rseen)],
            rlog, rtui, ["DEVELOPER_DONE"], "a1b2c3d4", str(rp), None,
            rdevnull, rdevnull_w, reminder=fast)
        rgot = rseen.read_bytes().decode("utf-8", "replace")
        check("reminder: reaches agent input on quiet pty",
              "NUDGE_MARKER_XYZ" in rgot and "\n" in rgot
              and rgot.count("NUDGE_MARKER_XYZ") <= fast["max"],
              f"agent stdin saw {rgot!r}")
        check("reminder: audited in a run-level sidecar, not the log",
              (rp / "reminders.log").is_file()
              and "NUDGE_MARKER_XYZ" in (rp / "reminders.log").read_text()
              and "NUDGE_MARKER_XYZ" not in rlog.read_text(),
              "one sidecar per run; run log signal-free")
        check("reminder: text is never a signal",
              rinfo.get("mirror_signal") is None
              and find_signal("NUDGE_MARKER_XYZ", ["DEVELOPER_DONE"],
                              "a1b2c3d4") is None,
              "mirror scan sees no completion")

        # The reminder is advisory only: an agent that gets nudged and then
        # writes the real nonce-bearing signal still routes on the run log.
        rlog2 = rp / "s2-task-r1.log"
        rtui2 = rp / "s2-task-r1.tui.log"
        (rp / "signal.py").write_text(
            "import os, select, sys, time\n"
            "open(sys.argv[1], 'w').write('working, no signal yet\\n')\n"
            "end = time.time() + 10\n"
            "while time.time() < end:\n"
            "    r, _, _ = select.select([0], [], [], 0.2)\n"
            "    if not r:\n"
            "        continue\n"
            "    data = os.read(0, 4096)\n"
            "    if not data:\n"
            "        break\n"
            "    if b'\\n' in data or b'\\r' in data:\n"
            "        open(sys.argv[1], 'a').write('WORK_DONE ' + sys.argv[2] + '\\n')\n"
            "        break\n"
            "time.sleep(0.2)\n")
        r2devnull = os.open(os.devnull, os.O_RDONLY)
        r2devnull_w = os.open(os.devnull, os.O_WRONLY)
        try:
            r2text, r2rc, r2info = _run_attached_pty(
                [sys.executable, str(rp / "signal.py"), str(rlog2), "a1b2c3d4"],
                rlog2, rtui2, ["WORK_DONE"], "a1b2c3d4", str(rp), None,
                r2devnull, r2devnull_w, reminder=fast)
        finally:
            os.close(r2devnull)
            os.close(r2devnull_w)
        check("reminder: a later real signal still routes",
              r2rc == 0 and log_done(r2text, ["WORK_DONE"], "a1b2c3d4")
              and r2info.get("mirror_signal") is None,
              "run log signal wins after the reminder")

        # Operator typing marks the session attended: no reminder is injected
        # into a human's input. A pipe stands in for the operator's stdin; the
        # byte arrives shortly after start.
        import threading
        rlog3 = rp / "s3-task-r1.log"
        rtui3 = rp / "s3-task-r1.tui.log"
        rseen3 = rp / "seen3.bin"
        (rp / "opwait.py").write_text(
            "import os, select, sys, time\n"
            "open(sys.argv[1], 'w').write('working, no signal yet\\n')\n"
            "seen = open(sys.argv[2], 'wb')\n"
            "end = time.time() + 2.5\n"
            "while time.time() < end:\n"
            "    r, _, _ = select.select([0], [], [], 0.2)\n"
            "    if not r:\n"
            "        continue\n"
            "    data = os.read(0, 4096)\n"
            "    if not data:\n"
            "        break\n"
            "    seen.write(data)\n"
            "    seen.flush()\n"
            "seen.close()\n")
        op_r, op_w = os.pipe()
        op_timer = threading.Timer(0.2, os.write, (op_w, b"x"))
        op_timer.start()
        try:
            _run_attached_pty(
                [sys.executable, str(rp / "opwait.py"), str(rlog3), str(rseen3)],
                rlog3, rtui3, ["DEVELOPER_DONE"], "a1b2c3d4", str(rp), None,
                op_r, rdevnull_w, reminder=fast)
        finally:
            op_timer.cancel()
            os.close(op_r)
            os.close(op_w)
        check("reminder: operator typing suppresses injection",
              "NUDGE_MARKER_XYZ" not in rseen3.read_bytes().decode("utf-8", "replace"),
              "no reminder once a human has typed")

        # A console tail that looks like a confirmation prompt is skipped: the
        # reminder is never typed into a dialog.
        rlog4 = rp / "s4-task-r1.log"
        rtui4 = rp / "s4-task-r1.tui.log"
        (rp / "prompt.py").write_text(
            "import sys, time\n"
            "open(sys.argv[1], 'w').write('working, no signal yet\\n')\n"
            "print('Overwrite config? [y/N]', flush=True)\n"
            "time.sleep(2.0)\n")
        r4devnull = os.open(os.devnull, os.O_RDONLY)
        try:
            _run_attached_pty(
                [sys.executable, str(rp / "prompt.py"), str(rlog4)],
                rlog4, rtui4, ["DEVELOPER_DONE"], "a1b2c3d4", str(rp), None,
                r4devnull, rdevnull_w, reminder=fast)
        finally:
            os.close(r4devnull)
        check("reminder: skipped on a confirmation prompt",
              "NUDGE_MARKER_XYZ" not in rtui4.read_text(),
              "no reminder typed into a dialog")

        # A swallowed first Enter is retried once: a harness that ignores the
        # first newline still receives the extra Enter.
        rlog5 = rp / "s5-task-r1.log"
        rtui5 = rp / "s5-task-r1.tui.log"
        rseen5 = rp / "seen5.bin"
        (rp / "ignore.py").write_text(
            "import os, select, sys, time\n"
            "open(sys.argv[1], 'w').write('working, no signal yet\\n')\n"
            "seen = open(sys.argv[2], 'wb')\n"
            "end = time.time() + 3.0\n"
            "while time.time() < end:\n"
            "    r, _, _ = select.select([0], [], [], 0.2)\n"
            "    if not r:\n"
            "        continue\n"
            "    data = os.read(0, 4096)\n"
            "    if not data:\n"
            "        break\n"
            "    seen.write(data)\n"
            "    seen.flush()\n"
            "seen.close()\n")
        fast5 = dict(fast, resubmit_s=0.2, first_s=0.1, max=1)
        r5devnull = os.open(os.devnull, os.O_RDONLY)
        try:
            _run_attached_pty(
                [sys.executable, str(rp / "ignore.py"), str(rlog5), str(rseen5)],
                rlog5, rtui5, ["DEVELOPER_DONE"], "a1b2c3d4", str(rp), None,
                r5devnull, rdevnull_w, reminder=fast5)
        finally:
            os.close(r5devnull)
        r5got = rseen5.read_bytes().decode("utf-8", "replace")
        check("reminder: swallowed Enter is retried once",
              r5got.count("NUDGE_MARKER_XYZ") == 1 and r5got.count("\n") >= 2,
              f"text once, Enter twice: {r5got!r}")
        os.close(rdevnull)
        os.close(rdevnull_w)

    # Quiescence-gated stability: growth resets, quiet + signal accumulates,
    # quiet without signal stays at zero.
    check("poll stable: growth resets", _poll_stable(True, True, 5) == 0)
    check("poll stable: quiet signal accumulates",
          _poll_stable(True, False, 1) == 2)
    check("poll stable: quiet no-signal stays zero",
          _poll_stable(False, False, 3) == 0)

    # Idle reminder schedule: first after the quiet interval, repeats back off,
    # the budget caps, a disabled plan stays silent, a started-but-quiet agent
    # is eligible, any operator typing suppresses injection, and prompt-like
    # console tails are skipped so the reminder never fights input or dialogs.
    rp0 = dict(IDLE_REMIND_PLAN)
    check("reminder: due after first interval",
          reminder_due(300.0, 0.0, 0, 0.0, rp0)
          and not reminder_due(299.0, 0.0, 0, 0.0, rp0))
    check("reminder: repeats back off",
          not reminder_due(599.0, 0.0, 1, 0.0, rp0)
          and reminder_due(600.0, 0.0, 1, 0.0, rp0))
    check("reminder: budget caps",
          not reminder_due(1e6, 0.0, IDLE_REMIND_MAX, 0.0, rp0))
    check("reminder: not started stays silent",
          not reminder_due(1e6, 0.0, 0, 0.0, rp0, started=False))
    check("reminder: disabled for a prompting harness stays silent",
          not reminder_due(1e6, 0.0, 0, 0.0, dict(rp0, enabled=False)))
    check("reminder: any operator typing suppresses",
          not reminder_due(400.0, 0.0, 0, 1.0, rp0)
          and not reminder_due(1e6, 0.0, 0, 1.0, rp0))
    check("reminder: prompt-like tail is skipped",
          _looks_like_prompt("Overwrite config? [y/N]")
          and _looks_like_prompt("Continue? (y/n)")
          and _looks_like_prompt("Press any key to continue")
          and not _looks_like_prompt("all tests passed, exiting")
          and not _looks_like_prompt(""))
    check("reminder: default text is never a signal",
          find_signal(IDLE_REMIND_TEXT, ["DEVELOPER_DONE"], "a1b2c3d4") is None
          and find_signal(IDLE_REMIND_TEXT, None, "a1b2c3d4") is None
          and not any(t.endswith("BLOCKED") for t in IDLE_REMIND_TEXT.split()),
          "no nonce, no signal word, no BLOCKED token")

    # opencode full-TUI shape (v2): `--auto --prompt`, no `run`, no -m. The
    # model is injected through OPENCODE_CONFIG_CONTENT; an effort adds a
    # default primary agent whose model selector carries the #variant.
    cmd_h, env_h = opencode_launch("togetherai/zai-org/GLM-5.3-Flash", "high",
                                   "PTR", "am_implement")
    cfg_h = json.loads(env_h["OPENCODE_CONFIG_CONTENT"])
    check("opencode tui cmd (effort)",
          cmd_h == ["opencode", "--standalone", "--auto", "--prompt", "PTR"]
          and cfg_h["model"] == "togetherai/zai-org/GLM-5.3-Flash"
          and cfg_h["default_agent"] == "am_implement"
          and cfg_h["agents"]["am_implement"] == {
              "mode": "primary",
              "model": "togetherai/zai-org/GLM-5.3-Flash#high"})
    cmd_p, env_p = opencode_launch("togetherai/zai-org/GLM-5.3-Flash", None, "PTR")
    check("opencode tui cmd (no effort)",
          cmd_p == ["opencode", "--standalone", "--auto", "--prompt", "PTR"]
          and json.loads(env_p["OPENCODE_CONFIG_CONTENT"]) == {
              "model": "togetherai/zai-org/GLM-5.3-Flash"})
    # model "auto" injects no config at all.
    cmd_a, env_a = opencode_launch("auto", "high", "PTR")
    check("opencode tui cmd (auto model)",
          cmd_a == ["opencode", "--standalone", "--auto", "--prompt", "PTR"]
          and "OPENCODE_CONFIG_CONTENT" not in env_a)

    # Alias resolution, pinned: short stage names expand to each
    # provider's own slug; unknown models pass through untouched.
    check("alias: together glm",
          resolve_model("opencode", resolve_provider(
              "opencode", "together"), "glm-5.3-flash") == "zai-org/GLM-5.3-Flash")
    check("alias: together deepseek",
          resolve_model("opencode", resolve_provider(
              "opencode", "together"), "deepseek-v4.1-flash") == "deepseek-ai/DeepSeek-V4.1-Flash")
    check("alias: openrouter deepseek",
          resolve_model("opencode", "openrouter",
                        "deepseek-v4.1-flash") == "deepseek/deepseek-v4.1-flash")
    check("alias: go deepseek is identity",
          resolve_model("opencode", resolve_provider(
              "opencode", "go"), "deepseek-v4.1-flash") == "deepseek-v4.1-flash")
    check("alias: unknown model passes through",
          resolve_model("opencode", "togetherai", "other-model") == "other-model")

    # Command Code (cmd): the id, the binary, and the native catalog resolve,
    # and both an unknown model and an unsupported effort are rejected without
    # inference. These run whether or not a stage declares cmd, so the mapping
    # stays pinned before the first cmd stage lands.
    check("cmd: harness id parses without a provider",
          parse_harness("cmd:deepseek/deepseek-v4-flash@high")
          == ("cmd", "deepseek", "deepseek-v4-flash", "high")
          and parse_harness("cmd:gpt-5.5") == ("cmd", None, "gpt-5.5", None))
    check("cmd: opencode provider and model aliases never apply",
          resolve_provider("cmd", "go") == "go"
          and resolve_provider("cmd", "together") == "together"
          and resolve_model("cmd", "togetherai", "glm-5.3-flash") == "glm-5.3-flash"
          and resolve_model("cmd", "openrouter", "deepseek-v4.1-flash")
          == "deepseek-v4.1-flash",
          "aliases stay scoped to cli == 'opencode'")
    check("cmd: launch is the interactive form with auto-approved permissions",
          cmd_launch("deepseek/deepseek-v4-flash", "high", "PTR")
          == ["cmd", "--trust", "--yolo", "--skip-onboarding",
              "-m", "deepseek/deepseek-v4-flash", "--effort", "high", "PTR"]
          and cmd_launch("gpt-5.5", None, "PTR")
          == ["cmd", "--trust", "--yolo", "--skip-onboarding",
              "-m", "gpt-5.5", "PTR"],
          "no -p: the session must stay open for the runner to close")
    check("cmd: reminder eligible only because permissions auto-approve",
          "cmd" in REMINDER_CLIS and "--yolo" in cmd_launch("m", None, "PTR")
          and "cursor" not in REMINDER_CLIS and "hermes" not in REMINDER_CLIS,
          "reminder never reaches a prompting harness")
    check("cmd catalog: parser reads model rows only",
          cmd_catalog_ids(
              "Available models  ·  2 models\n\nOpen Source\n\n"
              "deepseek/deepseek-v4-flash   fast hybrid-attention reasoning\n"
              "Moonshotai/Kimi-K3   long-horizon coding\n\n"
              "Pass the full id, or just the short name after the last \"/\":\n"
              "cmd --model kimi-k3\n\n"
              "Docs:  https://commandcode.ai/docs/reference/cli/models\n\n"
              "Decision models (headless only)\n"
              "typesafe/jev  typed questions in, probabilities out\n")
          == {"deepseek/deepseek-v4-flash", "moonshotai/kimi-k3"},
          "rows lowercased; headings, footer, and headless-only ids excluded")
    cmd_path = shutil.which(CMD_BINARY)
    check("cmd binary", cmd_path is not None, cmd_path or "not on PATH")
    if cmd_path is not None:
        cmd_ids = cmd_catalog_models()
        check("cmd catalog: model list readable",
              bool(cmd_ids), f"{len(cmd_ids)} ids" if cmd_ids
              else "cmd --list-models unavailable")
        if cmd_ids:
            listed = CMD_PROBE_MODEL.lower() in cmd_ids
            check("cmd catalog: known model listed", listed,
                  f"{CMD_PROBE_MODEL} " + ("listed" if listed else "missing"))
            unknown = cmd_probe_problem(CMD_UNKNOWN_MODEL, None)
            check("cmd rejection: unknown model", bool(unknown),
                  unknown or "no rejection reported")
            level = cmd_probe_problem(CMD_PROBE_MODEL, CMD_UNKNOWN_EFFORT)
            check("cmd rejection: unknown effort level", bool(level),
                  level or "no rejection reported")
            model_effort = cmd_probe_problem(CMD_NO_EFFORT_MODEL, "max")
            check("cmd rejection: effort the model does not support",
                  bool(model_effort), model_effort or "no rejection reported")
            resolved = cmd_probe_problem(CMD_PROBE_MODEL, "high")
            check("cmd resolution: supported pair resolves without spend",
                  resolved is None, resolved or "resolved with no transport")

    # Harness-token guarantee: every stage-declared harness id is mapped,
    # and {{harness}} resolves to exactly one real name per invocation.
    map_ok = True
    for sid in run.steps:
        meta, _ = run.stages[sid]
        hs = meta["harness"] if isinstance(meta["harness"], list) else [meta["harness"]]
        if any(h not in HARNESS_DISPLAY for h in hs):
            map_ok = False
    check("harness token: display map covers stage harness ids", map_ok,
          "all mapped" if map_ok else "unmapped harness id present")
    remediator_display = (display_name(run.planned_harness("remediator"))
                          if "remediator" in run.steps else "")
    t = (run.render_task("remediator", harness_name=remediator_display)
         if remediator_display else "")
    check("harness token: resolves single harness",
          "remediator" not in run.steps or (
              remediator_display in t
              and "{{harness}}" not in t
              and ") / OpenCode" not in t),
          "remediator prompt carries one real harness")
    check("harness token: unknown id falls back raw",
          display_name("mystery_cli:whatever") == "mystery_cli:whatever",
          "fallback returns raw id")

    # Harness availability skip, pinned without touching the host PATH:
    # selection walks from the rotation offset and wraps; a missing head
    # uses the next installed entry; none available returns None (the caller
    # halts). The CLI-to-binary map is part of the contract.
    fake = lambda name: name == "opencode"          # noqa: E731 - test predicate
    check("harness availability: cli maps to its binary",
          binary_for("cursor:m") == "agent" and binary_for("agy:m") == "agy"
          and binary_for("opencode:go/m@high") == "opencode"
          and binary_for("cmd:m") == CMD_BINARY,
          "cursor -> agent, cmd -> cmd")
    check("harness selection: available head is used",
          select_harness(["opencode:go/a@high", "agy:b"], 0, fake) == 0,
          "no skip when the head is up")
    check("harness selection: missing head uses the next entry",
          select_harness(["agy:a", "opencode:go/b@high", "cmd:c"], 0, fake) == 1,
          "walk 0 (agy) -> 1 (opencode)")
    check("harness selection: wraps past a missing tail",
          select_harness(["opencode:go/b@high", "agy:a"], 1, fake) == 0,
          "offset 1 (agy) wraps to 0 (opencode)")
    check("harness selection: none available returns None",
          select_harness(["agy:a", "cmd:c"], 0, fake) is None,
          "caller halts fail-closed")

    # Stub binaries on a fake PATH in a temp dir (hermetic: HOME points at
    # the temp root so the runner's own PATH prepend cannot reach a real
    # CLI). A missing entry uses the next installed one; when every entry is
    # missing the selector returns None; the method reports the skips and the
    # counter that passes them.
    avail_root = Path(tempfile.mkdtemp(prefix="harness-avail-"))
    avail_bin = avail_root / "bin"
    avail_bin.mkdir()
    for name in ("opencode", "cmd"):
        stub = avail_bin / name
        stub.write_text("#!/bin/sh\nexit 0\n")
        stub.chmod(0o755)
    (avail_root / "sel.md").write_text(
        "---\nname: sel\nharness: ['agy:a', 'opencode:go/b@high', 'cmd:c']\n"
        "harness_names:\n  'agy:a': 'A'\n  'opencode:go/b@high': 'B'\n"
        "  'cmd:c': 'C'\nplaceholders:\n  X: x\n---\nDo {{X}}.")
    sel_pipe = {"version": 1, "run_dir": "run",
                "inputs": {"phase_number": 2, "phase_file": "p",
                           "max_remedy_rounds": 3},
                "start": "sel", "ends": ["completed"],
                "steps": {"sel": {"stage": "sel.md", "record_as": "S",
                                  "bindings": {"X": "x"}, "end": "completed"}}}
    validate(sel_pipe, avail_root)
    sel_run = Run(sel_pipe, avail_root, avail_root, dict(sel_pipe["inputs"]))
    saved_home, saved_path = os.environ.get("HOME"), os.environ.get("PATH")
    os.environ["HOME"] = str(avail_root)
    os.environ["PATH"] = f"{avail_bin}:/usr/bin:/bin"
    try:
        check("harness availability: stub on PATH is found",
              is_harness_available("opencode:go/m@high")
              and is_harness_available("cmd:m"), "stub binaries visible")
        check("harness availability: absent CLI is not found",
              not is_harness_available("agy:m")
              and not is_harness_available("hermes:m"),
              "no real CLI reachable under the fake HOME/PATH")
        picked = sel_run.select_harness("sel")
        check("harness availability: stub-PATH skip uses the next",
              picked[0] == "opencode:go/b@high" and picked[2] == 1,
              "missing agy skipped for the opencode stub")
        check("harness availability: skip reports the missing binary",
              picked[1] == [("agy:a", "agy")],
              f"skipped {picked[1]!r}")
        check("harness availability: accepted run passes the skips",
              picked[3] == 2, "next counter is offset+skips+1")
        check("harness availability: all-missing halts fail-closed",
              select_harness(["agy:a", "hermes:b"], 0) is None,
              "no usable harness -> None")

        # Per-run harness plan: every stage's harness is decided once, before
        # the first invocation, and saved to <run_dir>/harnesses.json. A plan
        # already on disk is reused (a resume must not change models), a step
        # whose planned CLI went away is re-decided, a new step a pipeline edit
        # added is filled in, and a corrupt plan fails closed instead of
        # silently replanning mid-run.
        plan_root = Path(tempfile.mkdtemp(prefix="harness-plan-"))

        def stub_path(name, binaries):
            """A PATH directory holding only the named stub CLIs."""
            directory = plan_root / ("bin-" + "-".join(sorted(binaries)))
            directory.mkdir(exist_ok=True)
            for cli in binaries:
                stub = directory / cli
                stub.write_text("#!/bin/sh\nexit 0\n")
                stub.chmod(0o755)
            return directory

        # Which CLIs are "installed" per scenario: agy alone forces the plan
        # to skip step one's opencode head; opencode+agy gives the operator a
        # real choice; cmd alone proves a vanished CLI is re-decided.
        agy_only = stub_path("agy", ["agy"])
        opencode_agy = stub_path("both", ["opencode", "agy"])
        cmd_only = stub_path("cmd", ["cmd"])
        (plan_root / "one.md").write_text(
            "---\nname: one\nharness: ['opencode:go/one-a@high', "
            "'agy:one-b', 'opencode:go/one-c@high']\n"
            "harness_names:\n  'opencode:go/one-a@high': 'One A'\n"
            "  'agy:one-b': 'One B'\n  'opencode:go/one-c@high': 'One C'\n"
            "placeholders:\n  X: x\n---\nDo {{X}} on {{harness}}.")
        (plan_root / "two.md").write_text(
            "---\nname: two\nharness: ['opencode:go/two-a@high', 'agy:two-b']\n"
            "harness_names:\n  'opencode:go/two-a@high': 'Two A'\n"
            "  'agy:two-b': 'Two B'\n"
            "placeholders:\n  Y: x\n---\nDo {{Y}} on {{harness}}.")
        (plan_root / "three.md").write_text(
            "---\nname: three\nharness: ['opencode:go/three-a@high']\n"
            "harness_names:\n  'opencode:go/three-a@high': 'Three A'\n"
            "placeholders:\n  Z: x\n---\nDo {{Z}} on {{harness}}.")
        plan_inputs = {"phase_number": 42, "phase_file": "p",
                       "max_remedy_rounds": 3}

        def plan_pipe(steps, name="one"):
            return {"version": 1, "run_dir": "run",
                    "inputs": dict(plan_inputs), "start": name,
                    "ends": ["completed"], "steps": steps}

        plan_step_one = {"stage": "one.md", "record_as": "One",
                         "bindings": {"X": "x"}, "when": {"ONE_DONE": "two"}}
        plan_step_two = {"stage": "two.md", "record_as": "Two",
                         "bindings": {"Y": {"output": "one"}},
                         "end": "completed"}

        def make_plan_run(steps, name="one", run_dir="run"):
            pipe = plan_pipe(steps, name)
            validate(pipe, plan_root)
            run = Run(pipe, plan_root, plan_root, dict(plan_inputs))
            run.rotation_key = "rk-plan"
            run.pipe_path = plan_root / "plan.yaml"
            run._run_dir = plan_root / run_dir
            run._run_dir.mkdir(exist_ok=True)
            return pipe, run

        # Only `agy` is installed here, so step one skips to its agy slot and
        # the plan records the skip, the slot index, and the counter that
        # passes it.
        os.environ["PATH"] = f"{agy_only}:/usr/bin:/bin"
        two_step = make_plan_run({"one": plan_step_one, "two": plan_step_two})
        first_plan, first_changed = plan_harnesses(two_step[1])
        one_entry = first_plan["steps"]["one"]
        check("harness plan: decided for every stage before the run starts",
              set(first_plan["steps"]) == {"one", "two"}
              and first_plan["steps"]["two"]["harness"] == "agy:two-b"
              and first_changed,
              f"one={one_entry['harness']} two={first_plan['steps']['two']['harness']}")
        check("harness plan: availability skip is recorded, not lost",
              one_entry["skipped"] == [
                  {"harness": "opencode:go/one-a@high", "missing_binary": "opencode"}]
              and one_entry["index"] == 1 and one_entry["next_count"] == 2,
              f"skipped={one_entry['skipped']} next={one_entry['next_count']}")
        check("harness plan: every option is offered with its availability",
              [(o["harness"], o["available"]) for o in one_entry["options"]]
              == [("opencode:go/one-a@high", False), ("agy:one-b", True),
                  ("opencode:go/one-c@high", False)],
              "options carry the availability the prompt shows")
        save_harness_plan(two_step[1], first_plan)
        saved_plan = json.loads(plan_path(two_step[1]).read_text())
        again, again_changed = plan_harnesses(two_step[1])
        check("harness plan: a saved plan is reused, not replanned",
              again["steps"] == first_plan["steps"] and not again_changed,
              "resume keeps the same map and leaves the file alone")
        check("harness plan: saved per run, with the model for each stage",
              saved_plan["version"] == PLAN_VERSION
              and saved_plan["run_id"] == "phase-000042"
              and saved_plan["steps"]["one"]["display"] == "One B",
              f"{plan_path(two_step[1]).name} in {plan_path(two_step[1]).parent.name}")
        plan_twice = make_plan_run({"one": plan_step_one, "two": plan_step_two})[1]
        plan_twice.plan = None
        check("harness plan: a fresh Run reuses the run's saved map",
              plan_twice.select_harness("one")[0] == "agy:one-b",
              "the saved plan, not a fresh rotation decision")
        # agy is not installed now, but cmd is: the saved agy slot cannot be
        # honoured, so the plan is re-decided from the stage list and the
        # file is rewritten, never a missing binary invoked.
        (plan_root / "four.md").write_text(
            "---\nname: four\nharness: ['opencode:go/four-a@high', "
            "'cmd:four-b@high']\n"
            "harness_names:\n  'opencode:go/four-a@high': 'Four A'\n"
            "  'cmd:four-b@high': 'Four B'\n"
            "placeholders:\n  W: x\n---\nDo {{W}} on {{harness}}.")
        four_steps = {"four": {"stage": "four.md", "record_as": "Four",
                               "bindings": {"W": "w"}, "end": "completed"}}
        four_step = make_plan_run(four_steps, name="four", run_dir="four")
        os.environ["PATH"] = f"{opencode_agy}:/usr/bin:/bin"
        four_plan, _ = plan_harnesses(four_step[1])
        save_harness_plan(four_step[1], four_plan)
        os.environ["PATH"] = f"{cmd_only}:/usr/bin:/bin"
        replan, replan_changed = plan_harnesses(four_step[1])
        check("harness plan: a vanished CLI is re-decided, not invoked",
              four_plan["steps"]["four"]["harness"] == "opencode:go/four-a@high"
              and replan["steps"]["four"]["harness"] == "cmd:four-b@high"
              and replan["steps"]["four"]["skipped"] == [
                  {"harness": "opencode:go/four-a@high",
                   "missing_binary": "opencode"}]
              and replan_changed,
              "re-decided from the stage list; changed=True so it is saved")
        # A stage the saved plan does not know yet is filled in from the
        # rotation offset instead of failing the run.
        os.environ["PATH"] = f"{opencode_agy}:/usr/bin:/bin"
        three_step = make_plan_run({"one": plan_step_one, "two": plan_step_two,
                                    "three": {"stage": "three.md",
                                              "record_as": "Three",
                                              "bindings": {"Z": "z"},
                                              "end": "completed"}})
        save_harness_plan(three_step[1], first_plan)
        filled, filled_changed = plan_harnesses(three_step[1])
        check("harness plan: a step a pipeline edit added is filled in",
              filled["steps"]["three"]["harness"] == "opencode:go/three-a@high"
              and filled["steps"]["one"]["harness"] == one_entry["harness"]
              and filled_changed,
              "new step planned, existing steps untouched")
        plan_path(three_step[1]).write_text("{not-json")
        try:
            plan_harnesses(three_step[1])
            corrupt_refused = False
        except Fail:
            corrupt_refused = True
        check("harness plan: a corrupt plan fails closed",
              corrupt_refused, "delete it or use --fresh; never replan mid-run")

        # The operator's own choice: a typed answer picks a stage's slot, the
        # whole map is confirmed, and a decline starts nothing. Driven with a
        # scripted stdin, so no terminal and no harness is involved.
        plan_prompt_pipe, plan_prompt_run = make_plan_run(
            {"one": plan_step_one, "two": plan_step_two}, run_dir="prompt")
        four_prompt_pipe, four_prompt_run = make_plan_run(
            four_steps, name="four", run_dir="four-prompt")
        os.environ["PATH"] = f"{opencode_agy}:/usr/bin:/bin"

        def with_stdin(answers, body):
            """Run body() with a scripted stdin; nothing is typed for real."""
            saved_stdin = sys.stdin
            sys.stdin = io.StringIO(answers)
            try:
                return body()
            finally:
                sys.stdin = saved_stdin

        # One installed CLI only: the plan is decided without a keystroke.
        os.environ["PATH"] = f"{cmd_only}:/usr/bin:/bin"
        os.environ["PATH"] = f"{opencode_agy}:/usr/bin:/bin"
        # Stage one takes the typed answer, stage two keeps its default on an
        # empty line, then the map is confirmed.
        chosen = with_stdin("3\n\ny\n", lambda: prompt_harness_plan(
            plan_prompt_run, decide_harness_plan(plan_prompt_run), isatty=True))
        one_chosen = chosen["steps"]["one"]
        two_chosen = chosen["steps"]["two"]
        check("harness plan: an operator choice drives the map",
              one_chosen["harness"] == "opencode:go/one-c@high"
              and one_chosen["index"] == 2 and one_chosen["skipped"] == []
              and one_chosen["selected_by"] == "operator"
              and two_chosen["harness"] == "opencode:go/two-a@high"
              and chosen["source"] == "custom",
              f"picked {one_chosen['harness']} (next slot "
              f"{one_chosen['next_count']}), Enter kept the default for two")
        check("harness plan: a single installed option is not asked about",
              with_stdin("y\n", lambda: prompt_harness_plan(
                  four_prompt_run, decide_harness_plan(four_prompt_run),
                  isatty=True))["steps"]["four"]["selected_by"] == "operator",
              "no per-stage keystroke needed when there is nothing to choose")
        results = {}
        for label, answers in (("decline", "2\n\nn\n"), ("quit", "q\n")):
            try:
                with_stdin(answers, lambda: prompt_harness_plan(
                    plan_prompt_run, decide_harness_plan(plan_prompt_run),
                    isatty=True))
                results[label] = None
            except Aborted as exc:
                results[label] = exc
        check("harness plan: a declined plan starts nothing",
              results["decline"] is not None
              and config_error_payload(results["decline"])["state"] == "aborted",
              "aborted before any state is written")
        check("harness plan: 'q' aborts the choice",
              results["quit"] is not None,
              "no stage is silently accepted")
        try:
            with_stdin("", lambda: prompt_harness_plan(
                plan_prompt_run, decide_harness_plan(plan_prompt_run),
                isatty=False))
            piped_refused = False
        except Fail as exc:
            piped_refused = "interactive terminal" in str(exc)
        check("harness plan: a piped run cannot hang on the prompt",
              piped_refused, "refused without reading stdin")
        os.environ["PATH"] = f"{avail_bin}:/usr/bin:/bin"

        # End to end through drive(): the missing head is skipped, the
        # installed stub runs, the skip is recorded, and the accepted run
        # consumes past it. A stub invoke keeps this hermetic (no binary is
        # executed; only the availability check reads PATH).
        def drive_pipe(name, harnesses):
            (avail_root / f"{name}.md").write_text(
                f"---\nname: {name}\nharness: {harnesses!r}\n"
                "harness_names:\n"
                + "".join(f"  {h!r}: {h!r}\n" for h in harnesses)
                + "placeholders:\n  X: x\n---\nDo {{X}}.")
            return {"version": 1, "run_dir": "run",
                    "inputs": {"phase_number": 3, "phase_file": "p",
                               "max_remedy_rounds": 3},
                    "start": "d", "ends": ["completed"],
                    "steps": {"d": {"stage": f"{name}.md", "record_as": "D",
                                    "bindings": {"X": "x"},
                                    "end": "completed"}}}

        skip_pipe = drive_pipe("skip", ["agy:missing@high", "opencode:go/ok@high"])
        validate(skip_pipe, avail_root)
        skip_run = Run(skip_pipe, avail_root, avail_root, dict(skip_pipe["inputs"]))
        skip_run.rotation_key = "rk-avail"
        skip_run._run_dir = avail_root / "run"
        skip_run._run_dir.mkdir(exist_ok=True)
        ran = []

        def skip_stub(harness, task_path, log_path, usage_path=None, when=None,
                      nonce=None, **kw):
            ran.append(harness)
            sig = "BYE_DONE" + (f" {nonce}" if nonce else "")
            Path(log_path).write_text(sig)
            return sig, {}
        skip_res = drive(skip_run, skip_pipe, skip_stub)
        check("harness availability: drive skips the missing head",
              ran == ["opencode:go/ok@high"] and skip_res["state"] == "completed",
              f"invoked {ran}")
        check("harness availability: event records the skip",
              skip_res["events"][0].get("skipped")
              == [{"harness": "agy:missing@high", "missing_binary": "agy"}],
              f"skipped={skip_res['events'][0].get('skipped')}")
        check("harness availability: skip writes no task or log file",
              sorted(p.name for p in skip_run._run_dir.iterdir())
              == ["d-task-r1.log", "d-task-r1.md", "ledger.json", "resume.json"],
              "one attempt file per step: "
              f"{sorted(p.name for p in skip_run._run_dir.iterdir())}")
        check("harness availability: accepted run consumes past the skip",
              json.loads(rotation_file(avail_root, "rk-avail").read_text())
              == {"d": 2}, "offset 0 + one skip + the accept = 2")

        halt_pipe = drive_pipe("halt", ["agy:missing@high", "hermes:missing2"])
        validate(halt_pipe, avail_root)
        halt_run = Run(halt_pipe, avail_root, avail_root, dict(halt_pipe["inputs"]))
        halt_run.rotation_key = "rk-halt"
        halt_run._run_dir = avail_root / "halt"
        halt_run._run_dir.mkdir()
        invoked = []

        def halt_stub(*a, **k):
            invoked.append(a)
            return "", {}
        halted = None
        try:
            drive(halt_run, halt_pipe, halt_stub)
        except HarnessUnavailable as exc:
            halted = exc
        check("harness availability: all-missing halts before invoking",
              halted is not None and halted.step == "d"
              and not invoked and set(halted.harnesses)
              == {"agy:missing@high", "hermes:missing2"},
              str(halted))
        check("harness availability: halt writes no state",
              not list(halt_run._run_dir.iterdir())
              and not rotation_file(avail_root, "rk-halt").exists(),
              "no task, log, ledger, resume, or rotation file")
    finally:
        os.environ["HOME"] = saved_home
        os.environ["PATH"] = saved_path

    # Rotation persistence, pinned: consecutive drives alternate, resume
    # max-merges the file over resume.json, corrupt state restarts at zero,
    # and pipeline keys rotate independently. Stub harness, tmp repo: no
    # inference spend and no contact with live rotation files.
    rd = Path(tempfile.mkdtemp(prefix="rotation"))
    (rd / "s0.md").write_text(
        "---\nname: n\nharness: ['opencode:togetherai/zai-org/GLM-5.3-Flash@high', 'opencode:go/deepseek-v4.1-flash@high']\n"
        + "harness_names:\n"
        + "  'opencode:togetherai/zai-org/GLM-5.3-Flash@high': \"GLM\"\n"
        + "  'opencode:go/deepseek-v4.1-flash@high': \"Deepseek\"\n"
        + "placeholders:\n  A: x\n---\nDo {{A}}. You are {{harness}}.")

    def rot_pipe(n, steps):
        return {"version": 1, "run_dir": f"rd{n}",
                "inputs": {"phase_number": n, "phase_file": "phase.md",
                           "max_remedy_rounds": 3, "run_label": "z"},
                "start": "s0", "ends": ["completed"], "steps": steps}

    rot_end = {"s0": {"stage": "s0.md", "record_as": "R0",
                      "bindings": {"A": "x"}, "end": "completed"}}

    def rot_stub(harness, task_path, log_path, usage_path=None, when=None,
                 nonce=None, **kw):
        Path(log_path).write_text("BYE_DONE" + (f" {nonce}" if nonce else ""))
        return Path(log_path).read_text(), {}

    def rot_drive(n, key, steps, resumed=None, stub=rot_stub):
        p = rot_pipe(n, steps)
        validate(p, rd)
        rr = Run(p, rd, rd, dict(p["inputs"]))
        rr.rotation_key = key
        rr._run_dir = rd / f"rd{n}"
        rr._run_dir.mkdir(exist_ok=True)
        return drive(rr, p, stub, resumed)

    picks = [rot_drive(n, "rk-a", rot_end)["transcript"][0]["harness"]
             for n in (1, 2)]
    check("rotation: consecutive drives alternate",
          picks == ["opencode:togetherai/zai-org/GLM-5.3-Flash@high",
                    "opencode:go/deepseek-v4.1-flash@high"],
          "slots 0 then 1")
    check("rotation: durable file holds counts",
          json.loads(rotation_file(rd, "rk-a").read_text()) == {"s0": 2},
          rotation_file(rd, "rk-a").name)
    other = [rot_drive(n, "rk-b", rot_end)["transcript"][0]["harness"]
             for n in (3, 4)]
    check("rotation: pipeline keys independent",
          other[0].endswith("GLM-5.3-Flash@high") and other[0] != other[1],
          "rk-b alternates from zero on its own file")
    rotation_file(rd, "rk-a").write_text("{oops")
    try:
        rot_drive(5, "rk-a", rot_end)
        corrupt_refused = False
    except Fail:
        corrupt_refused = True
    check("rotation: corrupt file fails closed",
          corrupt_refused, "repair or --reset-rotation instead of silent reset")
    rotation_file(rd, "rk-neg").write_text(json.dumps({"s0": -1}))
    try:
        rot_drive(7, "rk-neg", rot_end)
        negative_refused = False
    except Fail:
        negative_refused = True
    check("rotation: negative count fails closed",
          negative_refused, "no silent model switch")
    rotation_file(rd, "rk-bad").write_text(json.dumps({"s0": "one"}))
    try:
        rot_drive(8, "rk-bad", rot_end)
        badcount_refused = False
    except Fail:
        badcount_refused = True
    check("rotation: non-integer count fails closed",
          badcount_refused, "no silent model switch")

    rot_loop = {
        "s0": {"stage": "s0.md", "record_as": "R0",
               "bindings": {"A": "x"}, "when": {"SIG0": "s1"}},
        "s1": {"stage": "s0.md", "record_as": "R1",
               "bindings": {"A": "x"}, "end": "completed"}}
    save_rotation(rd, "rk-m", {"s0": 5})

    def rot_stub2(harness, task_path, log_path, usage_path=None, when=None,
                  nonce=None, **kw):
        sig = "SIG0" if task_path.name.startswith("s0") else "BYE_DONE"
        if nonce:
            sig += f" {nonce}"
        Path(log_path).write_text(sig)
        return sig, {}

    resumed = {"current": "s0", "outputs": {}, "visits": {},
               "harness_use": {"s0": 1}, "prev_step": None,
               "transcript": [], "events": []}
    resm = rot_drive(6, "rk-m", rot_loop, resumed, rot_stub2)
    check("rotation: resume max-merges file over resume.json",
          resm["transcript"][0]["harness"]
          == "opencode:go/deepseek-v4.1-flash@high",
          "file count 5 beats resume count 1 (slot 5 % 2 = 1)")

    # Failed attempts retain history but reuse their rotation slot. The
    # successful task is recorded in the ledger, and downstream context uses
    # its actual harness rather than the first planned slot.
    retry_dir = Path(tempfile.mkdtemp(prefix="retry-authority"))
    (retry_dir / "developer.md").write_text(
        "---\nname: developer\n"
        "harness: ['opencode:go/retry-first@high', 'opencode:go/retry-second@high']\n"
        "harness_names:\n"
        "  'opencode:go/retry-first@high': 'Retry first'\n"
        "  'opencode:go/retry-second@high': 'Retry second'\n"
        "placeholders:\n  X: x\n---\nDeveloper {{X}} on {{harness}}.")
    (retry_dir / "review.md").write_text(
        "---\nname: review\n"
        "harness: ['opencode:go/retry-review@high']\n"
        "harness_names:\n"
        "  'opencode:go/retry-review@high': 'Retry review'\n"
        "placeholders:\n  CONTEXT: x\n---\nReview: {{CONTEXT}}")
    retry_pipe = {"version": 1, "run_dir": "run",
                  "inputs": {"phase_number": 7, "phase_file": "phase.md",
                             "max_remedy_rounds": 3},
                  "start": "developer", "ends": ["completed"],
                  "steps": {
                      "developer": {"stage": "developer.md", "record_as": "D",
                                    "bindings": {"X": "work"},
                                    "when": {"DEV_DONE": "review"}},
                      "review": {"stage": "review.md", "record_as": "R",
                                 "bindings": {"CONTEXT": {"task": "developer"}},
                                 "end": "completed"}}}
    validate(retry_pipe, retry_dir)
    retry_run = Run(retry_pipe, retry_dir, retry_dir, dict(retry_pipe["inputs"]))
    retry_run.rotation_key = "rk-retry"
    retry_run._run_dir = retry_dir / "run"
    retry_run._run_dir.mkdir()
    # Start one slot in so the accepted retry is deliberately not the first
    # planned slot; this catches a planned-name regression in rebuilt context.
    save_rotation(retry_dir, "rk-retry", {"developer": 1})
    retry_calls = []

    def retry_stub(harness, task_path, log_path, usage_path=None, when=None,
                   nonce=None, **kw):
        sid = kw.get("sid")
        retry_calls.append((sid, harness, Path(task_path).read_text()))
        if sid == "developer" and sum(c[0] == sid for c in retry_calls) == 1:
            Path(log_path).write_text("attempt failed before signal")
            return "attempt failed before signal", {}
        signal = "DEV_DONE" if sid == "developer" else "REVIEW_DONE"
        if nonce:
            signal += " " + nonce
        Path(log_path).write_text(signal)
        return signal, {}

    first_failed = False
    try:
        drive(retry_run, retry_pipe, retry_stub)
    except Fail:
        first_failed = True
    retry_rotation = rotation_file(retry_dir, "rk-retry")
    check("retry: failed attempt does not consume rotation",
          first_failed and retry_rotation.is_file()
          and json.loads(retry_rotation.read_text()) == {"developer": 1},
          "same non-first slot remains")
    resumed_retry = json.loads((retry_run._run_dir / "resume.json").read_text())
    drive(retry_run, retry_pipe, retry_stub, resumed_retry)
    review_prompt = next(text for sid, _h, text in retry_calls if sid == "review")
    retry_ledger = json.loads((retry_run._run_dir / "ledger.json").read_text())
    developer_entry = retry_ledger["steps"]["developer"]
    check("retry: successful attempt is authoritative",
          retry_calls[1][1] == "opencode:go/retry-second@high"
          and developer_entry["task_file"].endswith("developer-task-r2.md")
          and any(path.endswith("developer-task-r1.md")
                  for path in developer_entry["superseded_task_files"]),
          "ledger names the accepted attempt and preserves the failed one")
    check("retry: downstream context uses actual harness",
          "Retry second" in review_prompt and "Retry first" not in review_prompt
          and "ledger.json" in review_prompt and "superseded" in review_prompt,
          "no model-name conflict is presented as live context")
    bad_authority_dir = Path(tempfile.mkdtemp(prefix="retry-bad-ledger"))
    (bad_authority_dir / "ledger.json").write_text("{not-json")
    bad_authority = Run(retry_pipe, retry_dir, bad_authority_dir,
                        dict(retry_pipe["inputs"]))
    bad_authority._run_dir = bad_authority_dir
    bad_authority.require_authoritative = True
    try:
        bad_authority.render_task("review")
        bad_authority_refused = False
    except Fail:
        bad_authority_refused = True
    check("retry: malformed authority fails closed",
          bad_authority_refused, "no planned-model fallback")

    # Crash journal: fault injection at each durable boundary must recover
    # without re-invoking the completed harness or switching models.
    for boundary in ("after-ledger", "after-rotation", "after-resume"):
        crash_dir = Path(tempfile.mkdtemp(prefix=f"crash-{boundary}-"))
        (crash_dir / "s.md").write_text(
            "---\nname: s\nharness: ['opencode:go/crash-a@high', 'opencode:go/crash-b@high']\n"
            "harness_names:\n  'opencode:go/crash-a@high': 'Crash A'\n"
            "  'opencode:go/crash-b@high': 'Crash B'\n"
            "placeholders:\n  X: x\n---\nDo {{X}} on {{harness}}.")
        crash_pipe = {"version": 1, "run_dir": "run",
                      "inputs": {"phase_number": 9, "phase_file": "p",
                                 "max_remedy_rounds": 3},
                      "start": "s", "ends": ["completed"],
                      "steps": {"s": {"stage": "s.md", "record_as": "S",
                                      "bindings": {"X": "x"}, "end": "completed"}}}
        validate(crash_pipe, crash_dir)
        crash_run = Run(crash_pipe, crash_dir, crash_dir, dict(crash_pipe["inputs"]))
        crash_run.rotation_key = f"rk-crash-{boundary}"
        crash_run._run_dir = crash_dir / "run"
        crash_run._run_dir.mkdir()
        save_rotation(crash_dir, crash_run.rotation_key, {"s": 1})

        def crash_stub(harness, task_path, log_path, usage_path=None, when=None,
                       nonce=None, **kw):
            sig = "BYE_DONE" + (f" {nonce}" if nonce else "")
            Path(log_path).write_text(sig)
            return sig, {}

        orig_note = note_completion
        orig_save_rot = save_rotation
        orig_write_atomic = write_json_atomic

        def fail_after_ledger(*a, **k):
            out = orig_note(*a, **k)
            if boundary == "after-ledger":
                raise KeyboardInterrupt("injected crash after ledger")
            return out

        def fail_after_rotation(*a, **k):
            out = orig_save_rot(*a, **k)
            if boundary == "after-rotation":
                raise KeyboardInterrupt("injected crash after rotation")
            return out

        def fail_after_resume(path, value):
            out = orig_write_atomic(path, value)
            if boundary == "after-resume" and Path(path).name == "resume.json":
                # Only crash on the commit's resume write (which carries the
                # accepted output), not on the pre-invoke save with empty outputs.
                try:
                    outputs = value.get("outputs", {}) if isinstance(value, dict) else {}
                    has_output = any(isinstance(v, str) and "BYE_DONE" in v
                                     for v in outputs.values())
                except Exception:  # noqa: BLE001 - test helper must not crash
                    has_output = False
                if has_output:
                    raise KeyboardInterrupt("injected crash after resume")
            return out

        import builtins as _builtins
        globals()["note_completion"] = fail_after_ledger
        globals()["save_rotation"] = fail_after_rotation
        globals()["write_json_atomic"] = fail_after_resume
        crashed = False
        try:
            drive(crash_run, crash_pipe, crash_stub)
        except (KeyboardInterrupt, Fail):
            crashed = True
        finally:
            globals()["note_completion"] = orig_note
            globals()["save_rotation"] = orig_save_rot
            globals()["write_json_atomic"] = orig_write_atomic
        resumed_crash = json.loads((crash_run._run_dir / "resume.json").read_text()) \
            if (crash_run._run_dir / "resume.json").is_file() else None
        # Pending commit must exist for all three boundaries (written before
        # ledger), so recovery replays instead of re-invoking.
        pending_exists = pending_commit_path(crash_run).is_file()
        calls_after = []
        def crash_stub2(harness, task_path, log_path, usage_path=None, when=None,
                        nonce=None, **kw):
            calls_after.append(harness)
            sig = "BYE_DONE" + (f" {nonce}" if nonce else "")
            Path(log_path).write_text(sig)
            return sig, {}
        if resumed_crash is not None:
            # Fresh Run object to simulate a new process after crash.
            crash_run2 = Run(crash_pipe, crash_dir, crash_dir, dict(crash_pipe["inputs"]))
            crash_run2.rotation_key = crash_run.rotation_key
            crash_run2._run_dir = crash_run._run_dir
            result = drive(crash_run2, crash_pipe, crash_stub2, resumed_crash)
            recovered = result.get("state") == "completed" and not calls_after
        else:
            # Crash before any resume was saved (should not happen for
            # journaled commits which save resume via pending replay, but
            # treat as failed attempt and retry same harness).
            recovered = False
        check(f"journal: crash {boundary} recovers without re-invoke",
              crashed and pending_exists and recovered,
              "pending replay, same model, no duplicate harness call")

    # Task snapshot integrity: tampering with the authoritative task fails.
    tamper_dir = Path(tempfile.mkdtemp(prefix="task-tamper-"))
    (tamper_dir / "s.md").write_text(
        "---\nname: s\nharness: ['opencode:go/tamper@high']\n"
        "harness_names:\n  'opencode:go/tamper@high': 'Tamper'\n"
        "placeholders:\n  X: x\n---\nDo {{X}}.")
    tamper_pipe = {"version": 1, "run_dir": "run",
                   "inputs": {"phase_number": 11, "phase_file": "p",
                              "max_remedy_rounds": 3},
                   "start": "s", "ends": ["completed"],
                   "steps": {"s": {"stage": "s.md", "record_as": "S",
                                   "bindings": {"X": "x"}, "end": "completed"}}}
    validate(tamper_pipe, tamper_dir)
    tamper_run = Run(tamper_pipe, tamper_dir, tamper_dir, dict(tamper_pipe["inputs"]))
    tamper_run.rotation_key = "rk-tamper"
    tamper_run._run_dir = tamper_dir / "run"
    tamper_run._run_dir.mkdir()

    def tamper_stub(harness, task_path, log_path, usage_path=None, when=None,
                    nonce=None, **kw):
        sig = "BYE_DONE" + (f" {nonce}" if nonce else "")
        Path(log_path).write_text(sig)
        return sig, {}
    drive(tamper_run, tamper_pipe, tamper_stub)
    tamper_task = tamper_run._run_dir / "s-task-r1.md"
    tamper_task.write_text(tamper_task.read_text() + "\nTampered.")
    try:
        tamper_run.authoritative_attempt("s")
        tamper_refused = False
    except Fail:
        tamper_refused = True
    check("authority: tampered task snapshot fails closed",
          tamper_refused, "hash mismatch refuses")

    # Stage mutation: downstream context uses the stored snapshot, not the
    # mutated stage template.
    stage_dir = Path(tempfile.mkdtemp(prefix="stage-mutation-"))
    (stage_dir / "dev.md").write_text(
        "---\nname: dev\nharness: ['opencode:go/stage-a@high', 'opencode:go/stage-b@high']\n"
        "harness_names:\n  'opencode:go/stage-a@high': 'Stage A'\n"
        "  'opencode:go/stage-b@high': 'Stage B'\n"
        "placeholders:\n  X: x\n---\nOriginal {{X}} on {{harness}}.")
    (stage_dir / "rev.md").write_text(
        "---\nname: rev\nharness: ['opencode:go/rev@high']\n"
        "harness_names:\n  'opencode:go/rev@high': 'Rev'\n"
        "placeholders:\n  C: x\n---\nReview {{C}}")
    stage_pipe = {"version": 1, "run_dir": "run",
                  "inputs": {"phase_number": 12, "phase_file": "p",
                             "max_remedy_rounds": 3},
                  "start": "dev", "ends": ["completed"],
                  "steps": {"dev": {"stage": "dev.md", "record_as": "D",
                                    "bindings": {"X": "work"},
                                    "when": {"DEV_DONE": "rev"}},
                            "rev": {"stage": "rev.md", "record_as": "R",
                                    "bindings": {"C": {"task": "dev"}},
                                    "end": "completed"}}}
    validate(stage_pipe, stage_dir)
    stage_run = Run(stage_pipe, stage_dir, stage_dir, dict(stage_pipe["inputs"]))
    stage_run.rotation_key = "rk-stage"
    stage_run._run_dir = stage_dir / "run"
    stage_run._run_dir.mkdir()
    save_rotation(stage_dir, "rk-stage", {"dev": 1})

    def stage_stub(harness, task_path, log_path, usage_path=None, when=None,
                   nonce=None, **kw):
        sid = kw.get("sid")
        sig = ("DEV_DONE" if sid == "dev" else "REVIEW_DONE") + (f" {nonce}" if nonce else "")
        Path(log_path).write_text(sig)
        return sig, {}
    drive(stage_run, stage_pipe, stage_stub)
    # Mutate the stage file after completion; downstream rendering happens
    # in a fresh Run object that re-reads stages from disk.
    (stage_dir / "dev.md").write_text(
        "---\nname: dev\nharness: ['opencode:go/stage-a@high', 'opencode:go/stage-b@high']\n"
        "harness_names:\n  'opencode:go/stage-a@high': 'Stage A'\n"
        "  'opencode:go/stage-b@high': 'Stage B'\n"
        "placeholders:\n  X: x\n---\nMUTATED {{X}} on {{harness}}.")
    stage_run2 = Run(stage_pipe, stage_dir, stage_dir, dict(stage_pipe["inputs"]))
    stage_run2.rotation_key = "rk-stage"
    stage_run2._run_dir = stage_run._run_dir
    stage_run2.require_authoritative = True
    snap_text = stage_run2.resolve("rev", {"task": "dev"},
                                   stage_run2.ctx("rev"), {"rev"})
    check("authority: stage mutation does not alter snapshot",
          "Original" in snap_text and "MUTATED" not in snap_text
          and "Stage B" in snap_text and "Stage A" not in snap_text,
          "exact completed task is the source")

    # Legacy migration: deterministic backfill succeeds, ambiguous fails.
    legacy_dir = Path(tempfile.mkdtemp(prefix="legacy-migrate-"))
    (legacy_dir / "s.md").write_text(
        "---\nname: s\nharness: ['opencode:go/leg-a@high', 'opencode:go/leg-b@high']\n"
        "harness_names:\n  'opencode:go/leg-a@high': 'Leg A'\n"
        "  'opencode:go/leg-b@high': 'Leg B'\n"
        "placeholders:\n  X: x\n---\nDo {{X}}.")
    legacy_pipe = {"version": 1, "run_dir": "run",
                   "inputs": {"phase_number": 13, "phase_file": "p",
                              "max_remedy_rounds": 3},
                   "start": "s", "ends": ["completed"],
                   "steps": {"s": {"stage": "s.md", "record_as": "S",
                                   "bindings": {"X": "x"}, "end": "completed"}}}
    validate(legacy_pipe, legacy_dir)
    legacy_run = Run(legacy_pipe, legacy_dir, legacy_dir, dict(legacy_pipe["inputs"]))
    legacy_run._run_dir = legacy_dir / "run"
    legacy_run._run_dir.mkdir()
    (legacy_run._run_dir / "s-task-r1.md").write_text("old attempt")
    (legacy_run._run_dir / "s-task-r2.md").write_text("successful attempt")
    (legacy_run._run_dir / "ledger.json").write_text(json.dumps({
        "order": ["s"], "steps": {"s": {
            "signal": "BYE_DONE", "harness": "opencode:go/leg-b@high",
            "visits": 2, "output_sha256": "x", "artifacts": {}}}}))
    legacy_run.require_authoritative = True
    try:
        migrated = legacy_run.authoritative_attempt("s")
        legacy_ok = (migrated.get("task_file") == "s-task-r2.md"
                     and migrated.get("authoritative") is True
                     and "task_sha256" in migrated)
    except Fail:
        legacy_ok = False
    check("migration: deterministic legacy backfill succeeds",
          legacy_ok, "visits selects the authoritative task")
    amb_dir = Path(tempfile.mkdtemp(prefix="legacy-ambiguous-"))
    (amb_dir / "s.md").write_text((legacy_dir / "s.md").read_text())
    amb_pipe = {"version": 1, "run_dir": "run",
                "inputs": {"phase_number": 14, "phase_file": "p",
                           "max_remedy_rounds": 3},
                "start": "s", "ends": ["completed"],
                "steps": {"s": {"stage": "s.md", "record_as": "S",
                                "bindings": {"X": "x"}, "end": "completed"}}}
    validate(amb_pipe, amb_dir)
    amb_run = Run(amb_pipe, amb_dir, amb_dir, dict(amb_pipe["inputs"]))
    amb_run._run_dir = amb_dir / "run"
    amb_run._run_dir.mkdir()
    (amb_run._run_dir / "s-task-r1.md").write_text("a")
    (amb_run._run_dir / "s-task-r2.md").write_text("b")
    (amb_run._run_dir / "ledger.json").write_text(json.dumps({
        "order": ["s"], "steps": {"s": {
            "signal": "BYE_DONE", "harness": "opencode:go/leg-a@high",
            "output_sha256": "x", "artifacts": {}}}}))
    amb_run.require_authoritative = True
    try:
        amb_run.authoritative_attempt("s")
        amb_refused = False
    except Fail as e:
        amb_refused = "--migrate-ledger" in str(e) or "ambiguous" in str(e)
    check("migration: ambiguous legacy fails closed",
          amb_refused, "explicit recovery, no guessing")

    # Rotation write failure fails the completion instead of silently continuing.
    rotfail_dir = Path(tempfile.mkdtemp(prefix="rotfail-"))
    (rotfail_dir / "s.md").write_text(
        "---\nname: s\nharness: ['opencode:go/one@high']\n"
        "harness_names:\n  'opencode:go/one@high': 'One'\n"
        "placeholders:\n  X: x\n---\nDo {{X}}.")
    rotfail_pipe = {"version": 1, "run_dir": "run",
                    "inputs": {"phase_number": 15, "phase_file": "p",
                               "max_remedy_rounds": 3},
                    "start": "s", "ends": ["completed"],
                    "steps": {"s": {"stage": "s.md", "record_as": "S",
                                    "bindings": {"X": "x"}, "end": "completed"}}}
    validate(rotfail_pipe, rotfail_dir)
    rotfail_run = Run(rotfail_pipe, rotfail_dir, rotfail_dir, dict(rotfail_pipe["inputs"]))
    rotfail_run.rotation_key = "rk-rotfail"
    rotfail_run._run_dir = rotfail_dir / "run"
    rotfail_run._run_dir.mkdir()

    def rotfail_stub(harness, task_path, log_path, usage_path=None, when=None,
                     nonce=None, **kw):
        sig = "BYE_DONE" + (f" {nonce}" if nonce else "")
        Path(log_path).write_text(sig)
        return sig, {}
    orig_save = save_rotation
    def fail_save(*a, **k):
        raise Fail("injected rotation write failure")
    globals()["save_rotation"] = fail_save
    try:
        drive(rotfail_run, rotfail_pipe, rotfail_stub)
        rotfail_completed = True
    except Fail:
        rotfail_completed = False
    finally:
        globals()["save_rotation"] = orig_save
    check("rotation: write failure fails completion",
          not rotfail_completed, "no silent success without durable rotation")

    # Adversarial fixture: multiple plausible model names and stale
    # requirements must not leak into downstream context.
    adv_dir = Path(tempfile.mkdtemp(prefix="adversarial-fixture-"))
    (adv_dir / "dev.md").write_text(
        "---\nname: dev\nharness: ['opencode:go/adv-a@high', 'opencode:go/adv-b@high']\n"
        "harness_names:\n  'opencode:go/adv-a@high': 'Adv Model Alpha'\n"
        "  'opencode:go/adv-b@high': 'Adv Model Beta'\n"
        "placeholders:\n  X: x\n---\nBuild {{X}} with {{harness}}. REQUIREMENT: use database X.")
    (adv_dir / "rev.md").write_text(
        "---\nname: rev\nharness: ['opencode:go/adv-rev@high']\n"
        "harness_names:\n  'opencode:go/adv-rev@high': 'Adv Review'\n"
        "placeholders:\n  C: x\n---\nReview {{C}}")
    adv_pipe = {"version": 1, "run_dir": "run",
                "inputs": {"phase_number": 16, "phase_file": "p",
                           "max_remedy_rounds": 3},
                "start": "dev", "ends": ["completed"],
                "steps": {"dev": {"stage": "dev.md", "record_as": "D",
                                  "bindings": {"X": "work"},
                                  "when": {"DEV_DONE": "rev"}},
                          "rev": {"stage": "rev.md", "record_as": "R",
                                  "bindings": {"C": {"task": "dev"}},
                                  "end": "completed"}}}
    validate(adv_pipe, adv_dir)
    adv_run = Run(adv_pipe, adv_dir, adv_dir, dict(adv_pipe["inputs"]))
    adv_run.rotation_key = "rk-adv"
    adv_run._run_dir = adv_dir / "run"
    adv_run._run_dir.mkdir()
    save_rotation(adv_dir, "rk-adv", {"dev": 1})
    adv_calls = []
    def adv_stub(harness, task_path, log_path, usage_path=None, when=None,
                 nonce=None, **kw):
        sid = kw.get("sid")
        text = Path(task_path).read_text()
        adv_calls.append((sid, harness, text))
        if sid == "dev" and sum(c[0] == sid for c in adv_calls) == 1:
            Path(log_path).write_text("failed, no signal")
            return "failed, no signal", {}
        sig = ("DEV_DONE" if sid == "dev" else "REVIEW_DONE") + (f" {nonce}" if nonce else "")
        Path(log_path).write_text(sig)
        return sig, {}
    try:
        drive(adv_run, adv_pipe, adv_stub)
    except Fail:
        resumed_adv = json.loads((adv_run._run_dir / "resume.json").read_text())
        drive(adv_run, adv_pipe, adv_stub, resumed_adv)
    adv_review = next(t for s, _h, t in adv_calls if s == "rev")
    # The failed r1 file contains Alpha; the successful r2 uses Beta. The
    # reviewer must see only Beta and the authority notice, never Alpha as
    # a live requirement.
    check("adversarial: stale model and requirement do not leak",
          "Adv Model Beta" in adv_review and "Adv Model Alpha" not in adv_review
          and "ledger.json" in adv_review and "superseded" in adv_review,
          "exact snapshot wins")

    # --mark-done recovery, pinned: a finished-but-unsignalled step advances
    # without invoking any harness; a wrong signal is refused.
    md = Path(tempfile.mkdtemp(prefix="markdone"))
    (md / "s0.md").write_text(
        "---\nname: n\nharness: ['opencode:go/deepseek-v4.1-flash@high']\n"
        + "harness_names:\n"
        + "  'opencode:go/deepseek-v4.1-flash@high': \"Deepseek\"\n"
        + "placeholders:\n  A: x\n---\nDo {{A}}.")
    (md / "s1.md").write_text((md / "s0.md").read_text())
    mp = {"version": 1, "run_dir": "rd",
          "inputs": {"phase_number": 1, "phase_file": "f",
                     "max_remedy_rounds": 3, "run_label": "z"},
          "start": "s0", "ends": ["completed"],
          "steps": {
              "s0": {"stage": "s0.md", "record_as": "R0",
                     "bindings": {"A": "x"}, "when": {"SIG0": "s1"}},
              "s1": {"stage": "s1.md", "record_as": "R1",
                     "bindings": {"A": "x"}, "end": "completed"}}}
    validate(mp, md)
    mr = Run(mp, md, md, dict(mp["inputs"]))
    mr.rotation_key = "rk-md"
    mr._run_dir = md / "rd"
    mr._run_dir.mkdir(exist_ok=True)
    (mr._run_dir / "s0-task-r1.md").write_text("Do x.")
    (mr._run_dir / "s0-task-r1.log").write_text("work done, forgot signal\n")
    (mr._run_dir / "resume.json").write_text(json.dumps({
        "current": "s0", "outputs": {}, "visits": {"s0": 1},
        "harness_use": {"s0": 1}, "prev_step": None,
        "transcript": [], "events": []}))
    res_md = mark_done(mr, "s0", "SIG0")
    check("mark-done: advances to routed target",
          res_md.get("advanced_to") == "s1"
          and (mr._run_dir / "s0-task-r1.log").read_text().splitlines()[-1] == "SIG0"
          and json.loads((mr._run_dir / "resume.json").read_text())["current"] == "s1",
          "resume at s1, signal appended")
    mark_done_ledger = json.loads((mr._run_dir / "ledger.json").read_text())
    check("mark-done: ledger proves the step",
          "s0" in mark_done_ledger["steps"]
          and mark_done_ledger["steps"]["s0"].get("task_file")
          == "s0-task-r1.md",
          "s0 entry points at the recovered task")
    try:
        mark_done(mr, "s1", "NOPE")
        check("mark-done: wrong signal refused", False, "no Fail raised")
    except Fail:
        check("mark-done: wrong signal refused", True, "Fail raised")

    # mark-done newline guard: an unterminated log still gets a clean
    # signal line that the matcher accepts.
    (mr._run_dir / "s0-task-r1.log").write_bytes(b"work, no newline")
    cur_res = json.loads((mr._run_dir / "resume.json").read_text())
    (mr._run_dir / "resume.json").write_text(json.dumps({
        "current": "s0", "outputs": cur_res.get("outputs", {}),
        "visits": {"s0": 2, "s1": 1}, "harness_use": {"s0": 2, "s1": 1},
        "prev_step": "s1", "transcript": cur_res.get("transcript", []),
        "events": cur_res.get("events", [])}))
    res_nl = mark_done(mr, "s0", "SIG0")
    check("mark-done: unterminated log gets clean signal",
          res_nl.get("advanced_to") == "s1"
          and (mr._run_dir / "s0-task-r1.log").read_text().splitlines()[-1] == "SIG0",
          "signal on its own line")

    # mark-done honors max_rounds unless --force.
    md2 = Path(tempfile.mkdtemp(prefix="markdone-force"))
    (md2 / "s0.md").write_text((md / "s0.md").read_text())
    (md2 / "s1.md").write_text((md / "s0.md").read_text())
    import copy as _copy
    mfp = _copy.deepcopy(mp)
    mfp["steps"]["s0"]["max_rounds"] = 1
    mfp["steps"]["s0"]["on_exhausted"] = "completed"
    validate(mfp, md2)
    mr2 = Run(mfp, md2, md2, dict(mfp["inputs"]))
    mr2.rotation_key = "rk-md2"
    mr2._run_dir = md2 / "rd"
    mr2._run_dir.mkdir(exist_ok=True)
    (mr2._run_dir / "s0-task-r1.md").write_text("Do x.")
    (mr2._run_dir / "s0-task-r1.log").write_text("work\n")
    (mr2._run_dir / "resume.json").write_text(json.dumps({
        "current": "s0", "outputs": {}, "visits": {"s0": 1, "s1": 1},
        "harness_use": {"s0": 1}, "prev_step": "s1",
        "transcript": [], "events": []}))
    try:
        mark_done(mr2, "s0", "SIG0")
        check("mark-done: loop cap refused without force", False, "no Fail raised")
    except Fail as e:
        check("mark-done: loop cap refused without force", "--force" in str(e),
              "names --force")
    res_f = mark_done(mr2, "s0", "SIG0", force=True)
    check("mark-done: force overrides loop cap",
          res_f.get("advanced_to") == "s1", "advanced with force")

    # mark-done ignores the console mirror sidecar when selecting the run log.
    md_tui = Path(tempfile.mkdtemp(prefix="markdone-tui"))
    (md_tui / "s0.md").write_text((md / "s0.md").read_text())
    (md_tui / "s1.md").write_text((md / "s0.md").read_text())
    import copy as _copy_tui
    mtui_pipe = _copy_tui.deepcopy(mp)
    validate(mtui_pipe, md_tui)
    mtui = Run(mtui_pipe, md_tui, md_tui, dict(mtui_pipe["inputs"]))
    mtui.rotation_key = "rk-md-tui"
    mtui._run_dir = md_tui / "rd"
    mtui._run_dir.mkdir(exist_ok=True)
    (mtui._run_dir / "s0-task-r1.md").write_text("Do x.")
    (mtui._run_dir / "s0-task-r1.log").write_text("real work, forgot signal\n")
    (mtui._run_dir / "s0-task-r1.tui.log").write_text("console mirror\n")
    (mtui._run_dir / "resume.json").write_text(json.dumps({
        "current": "s0", "outputs": {}, "visits": {"s0": 1},
        "harness_use": {"s0": 0}, "prev_step": None,
        "transcript": [], "events": []}))
    res_tui = mark_done(mtui, "s0", "SIG0")
    tui_ledger = json.loads((mtui._run_dir / "ledger.json").read_text())
    check("mark-done: ignores console mirror sidecar",
          res_tui.get("advanced_to") == "s1"
          and "SIG0" in (mtui._run_dir / "s0-task-r1.log").read_text()
          and "SIG0" not in (mtui._run_dir / "s0-task-r1.tui.log").read_text()
          and tui_ledger["steps"]["s0"]["output_sha256"] == sha_str(
              (mtui._run_dir / "s0-task-r1.log").read_text()),
          "run log is the provenance source, not the mirror")

    with tempfile.TemporaryDirectory(prefix="artifact-empty") as artifact_tmp:
        artifact_dir = Path(artifact_tmp)
        empty_findings = artifact_dir / "empty.json"
        issue_only = artifact_dir / "issue-only.json"
        actionable = artifact_dir / "actionable.json"
        empty_findings.write_text(json.dumps({"findings": [], "addressed_issues": []}))
        issue_only.write_text(json.dumps({"findings": [], "addressed_issues": [{"number": 1}]}))
        actionable.write_text(json.dumps({"findings": [{"id": "F-1"}], "addressed_issues": []}))
        check("artifact: empty findings and issue audit skip",
              artifact_is_empty(empty_findings))
        check("artifact: issue-only report stays actionable",
              not artifact_is_empty(issue_only))
        check("artifact: finding report stays actionable",
              not artifact_is_empty(actionable))

    with tempfile.TemporaryDirectory(prefix="phase-file-binding") as phase_tmp:
        phase_root = Path(phase_tmp)
        phase_roadmap = phase_root / "private" / "clio-private" / "roadmap"
        phase_roadmap.mkdir(parents=True)
        phase_ok = phase_roadmap / "phase-100440-test.md"
        phase_ok.write_text("x")
        phase_bad = phase_roadmap / "phase-100460-test.md"
        phase_bad.write_text("x")
        try:
            valid_phase_file = _validate_phase_file(
                phase_root, 100440, str(phase_ok))
            mismatch_refused = False
        except Fail:
            valid_phase_file = None
            mismatch_refused = True
        if valid_phase_file is not None:
            try:
                _validate_phase_file(phase_root, 100440, str(phase_bad))
                mismatch_refused = False
            except Fail:
                mismatch_refused = True
        check("phase file binding rejects mismatched phase",
              valid_phase_file is not None and mismatch_refused,
              "canonical match required")

    with tempfile.TemporaryDirectory(prefix="publication-failure") as failure_tmp:
        failure_dir = Path(failure_tmp)
        failure_run = type("FailureRun", (), {"_run_dir": failure_dir})()
        (failure_dir / "run.json").write_text(json.dumps({
            "state": "publishing", "publication_pending": True}))
        _mark_publication_failed(failure_run, Fail("injected publication failure"))
        failed_marker = json.loads((failure_dir / "run.json").read_text())
        check("publication failure leaves resumable blocked marker",
              failed_marker.get("state") == "blocked"
              and not failed_marker.get("publication_pending"),
              str(failed_marker.get("state")))

        publication_run = type("PublicationRun", (), {
            "repo": failure_run._run_dir,
            "inputs": {"phase_number": 100440},
            "reservation": {"phase": "100440", "machine_id": "local-01",
                            "reservation_id": "rsv-test",
                            "generation": 1},
        })()
        publication_run._run_dir = failure_run._run_dir
        old_publish = gitsync.publish_phase
        gitsync.publish_phase = lambda *a, **k: {
            "ok": False, "state": "COORDINATION_UNAVAILABLE",
            "error": "injected publication failure"}
        try:
            try:
                _publish_completion_evidence(publication_run)
                publication_refused = False
            except Fail:
                publication_refused = True
        finally:
            gitsync.publish_phase = old_publish
        check("publication helper failure is surfaced to the runner",
              publication_refused, "failure path")

    # Fail-closed sync: stubbed-remote checks live in gitsync.py so the same
    # gate runs standalone (`gitsync.py --self-test`) and here.
    checks += gitsync.self_test_checks()
    checks += check_incidental_policy.self_test_checks()

    ok = all(c["ok"] for c in checks if c["ok"] is not None)
    print(json.dumps({"self_test": "pass" if ok else "fail", "checks": checks}, indent=2))
    sys.exit(0 if ok else 1)


def fuzz(n):
    """Randomized router property test: random graphs, scripted signals."""
    import random
    import tempfile
    ends = ["completed", "rejected"]
    for trial in range(n):
        rng = random.Random(trial)
        d = Path(tempfile.mkdtemp(prefix="fuzz"))
        k = rng.randint(2, 4)
        ids = [f"s{i}" for i in range(k)]
        steps = {}
        for i, sid in enumerate(ids):
            refs = [{"output": j} for j in ids[:i]]
            refs += [{"prev_output": True}]
            pick = rng.random()
            if pick < 0.4:
                bindings = {"P": "const"}
            elif pick < 0.7:
                bindings = {"P": "{phase_file}"}
            else:
                bindings = {"P": {"join": refs[:2]}}
            if rng.random() < 0.3 and i > 0:
                bindings["T"] = {"task": rng.choice(ids[:i])}
            body = " ".join(["{{P}}"] + (["{{T}}"] if "T" in bindings else []))
            (d / f"{sid}.md").write_text(
                "---\nname: n\nharness: ['opencode:go/deepseek-v4.1-flash@high', 'agy-x']\n"
                .replace("agy-x", "agy:gemini-3.8-flash-high")
                + "harness_names:\n"
                + "  'opencode:go/deepseek-v4.1-flash@high':"
                + " \"OpenCode (Go . Deepseek V4.1 Flash High)\"\n"
                + "  'agy:gemini-3.8-flash-high':"
                + " \"agy (Gemini 3.8 Flash)\"\n"
                + "placeholders:\n  P: x\n" + ("  T: x\n" if "T" in bindings else "")
                + f"---\n{body}")
            wl = {}
            for q in range(rng.randint(1, 2)):
                tgt = rng.choice(ids + ends)
                wl[f"SIG{q}"] = tgt
            st = {"stage": f"{sid}.md", "record_as": "R",
                  "bindings": bindings}
            if rng.random() < 0.25 or i == k - 1:
                st["end"] = rng.choice(ends)
            else:
                st["when"] = wl
                if rng.random() < 0.4:
                    st["max_rounds"] = rng.randint(1, 3)
                    st["on_exhausted"] = rng.choice(ends)
            if rng.random() < 0.3:
                st["require_file"] = "f.json"
                if rng.random() < 0.5:
                    st["skip_when_empty"] = rng.choice(ids + ends)
                if rng.random() < 0.7:
                    (d / "rd").mkdir(exist_ok=True)
            steps[sid] = st
        pipe = {"version": 1, "run_dir": "rd",
                "inputs": {"phase_number": 1, "phase_file": "f", "a": "A",
                           "max_remedy_rounds": 3, "run_label": "z"},
                "start": "s0", "ends": ends, "steps": steps}
        validate(pipe, d)
        repo = Path.cwd()
        run = Run(pipe, d, repo, dict(pipe["inputs"]))
        run.persist_rotation = False
        run._run_dir = d / "rd"
        run._run_dir.mkdir(exist_ok=True)
        if rng.random() < 0.5:
            (run._run_dir / "f.json").write_text(
                json.dumps({"findings": [] if rng.random() < 0.5 else [{"id": "F-1"}]}))

        def stub(harness, task_path, log_path, usage_path=None, when=None, nonce=None,
             _r=rng, _steps=steps, **kw):
            r = _r.random()
            if r < 0.08:
                return "garbage with no signal", {}
            if r < 0.16:
                return "SOMETHING_BLOCKED: boom", {}
            keys = []
            for sid, s in _steps.items():
                if "when" in s:
                    keys += list(s["when"])
            sig = (rng.choice(keys) if keys else "SIG0")
            # Some harnesses prefix the signal with a timestamped log entry;
            # the router must strip it (see clean_line).
            if rng.random() < 0.25:
                sig = "2026-09-18T02:48:45+05:30 " + sig
            # Journal prefixes and trailing summaries must not hide it
            # (see find_signal).
            r2 = rng.random()
            if r2 < 0.15:
                sig = "| r1 | " + sig
            # The live pipeline requires the per-invocation nonce on every
            # non-BLOCKED signal; usually comply, sometimes forget (the
            # router must then fail the step instead of routing).
            if nonce and rng.random() < 0.9:
                sig += f" {nonce}"
            if r2 >= 0.15 and r2 < 0.25:
                sig = sig + "\ncleaned up, exiting"
            return sig, {}

        try:
            res = drive(run, pipe, stub)
        except Fail as e:
            assert "missing expected signal" in str(e) or "no parseable" in str(e) \
                or "missing" in str(e), (trial, e)
            continue
        assert res["state"] in ends + ["blocked"], (trial, res["state"])
        for ev in res["events"]:
            st = steps[ev["step"]]
            if "end" in st:
                continue
            sig = ev["signal"]
            head = sig.split()[0].rstrip(":") if sig.split() else ""
            assert head.endswith("BLOCKED") or match_signal(sig, st["when"]), (trial, ev)
            if ev.get("via") == "exhausted":
                assert ev["visits"] >= st["max_rounds"], (trial, ev)
        evs = res["events"]
        for a, b in zip(evs, evs[1:]):
            if a.get("via") == "edge":
                assert b["step"] == a["routed_to"], (trial, a, b)
    print(json.dumps({"fuzz_trials": n, "ok": True}, indent=2))


def autoexit_test():
    """Scripted auto-exit checks (no inference spend):
    a fake harness that writes its final signal then sleeps must be closed
    by the runner (~grace + stability polls); a fake harness that exits
    nonzero without a signal must stay a step failure."""
    import tempfile
    d = Path(tempfile.mkdtemp(prefix="autoexit-test"))
    results = []

    cases = [
        ("signal-then-sleep closed", ["DEVELOPER_DONE"],
         "import time, sys\n"
         "time.sleep(3)\n"
         "open(sys.argv[1], 'w').write('2026-09-18T00:00:00+05:30 DEVELOPER_DONE a1b2c3d4\\n')\n"
         "time.sleep(300)\n"),
        ("blocked-signal closed", ["DEVELOPER_DONE"],
         "import sys\n"
         "open(sys.argv[1], 'a').write('2026-09-18T00:00:00Z DEVELOPER_BLOCKED: nope\\n')\n"
         "time.sleep(300)\n"),
        ("no-signal nonzero stays failure", ["DEVELOPER_DONE"],
         "import sys\n"
         "open(sys.argv[1], 'w').write('still working\\n')\n"
         "raise SystemExit(3)\n"),
        ("end-step DONE closed (no when)", None,
         "import sys\n"
         "open(sys.argv[1], 'w').write('FINALIZE_DONE a1b2c3d4\\n')\n"
         "time.sleep(300)\n"),
        ("signal-plus-trailing-summary closed", ["DEVELOPER_DONE"],
         "import sys\n"
         "open(sys.argv[1], 'w').write('DEVELOPER_DONE a1b2c3d4\\ncleaned up, exiting\\n')\n"
         "time.sleep(300)\n"),
        ("bare-signal-without-nonce ignored", ["DEVELOPER_DONE"],
         "import sys, time\n"
         "open(sys.argv[1], 'w').write('DEVELOPER_DONE\\n')\n"
         "time.sleep(3)\n"),
    ]
    for name, when, body in cases:
        log = d / f"{name.split()[0].lower()}-task-r1.log"
        script = d / f"{abs(hash(name)) % 10**8}.py"
        script.write_text("import sys, time\n" + body)
        t0 = time.time()
        text, rc, _info = run_attached([sys.executable, str(script), str(log)],
                                log, when, "a1b2c3d4", cwd=str(d))
        dt = round(time.time() - t0, 2)
        sig = last_line(text)
        if "no-signal" in name:
            ok = rc == 3 and not log_done(text, when, "a1b2c3d4")
        elif "without-nonce" in name:
            ok = rc == 0 and not log_done(text, when, "a1b2c3d4")
        else:
            ok = rc != 0 and dt < 45 and log_done(text, when, "a1b2c3d4")
        results.append({"case": name, "ok": bool(ok), "elapsed_s": dt,
                        "rc": rc, "last_line": sig[:80]})
    ok = all(r["ok"] for r in results)
    print(json.dumps({"autoexit_test": "pass" if ok else "fail",
                      "cases": results}, indent=2))
    sys.exit(0 if ok else 1)


def config_error_payload(error):
    """Machine-readable exit-2 payload for a config error.

    A HarnessUnavailable halt additionally names the step and every harness
    tried with the missing binary, so an operator can install one and resume
    (resume.json is untouched and retries the same step). A declined or
    aborted harness plan reports state "aborted" instead: nothing ran and
    nothing was claimed.
    """
    if isinstance(error, Aborted):
        return {"state": "aborted", "reason": str(error)}
    payload = {"state": "config_error", "error": str(error)}
    if isinstance(error, HarnessUnavailable):
        payload["step"] = error.step
        payload["harnesses"] = [
            {"harness": h, "missing_binary": binary_for(h)}
            for h in error.harnesses]
    return payload


def main():
    ap = argparse.ArgumentParser(description="Run a stage pipeline.")
    ap.add_argument("--pipeline", default=None)
    ap.add_argument("--input", action="append", default=[], metavar="k=v")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--show-prompts", action="store_true",
                    help="with --dry-run, print full rendered prompts")
    ap.add_argument("--self-test", action="store_true",
                    help="static harness checks (no inference spend)")
    ap.add_argument("--live", action="store_true",
                    help="with --self-test, also send one-word live probes (spends inference)")
    ap.add_argument("--fuzz", type=int, default=0, metavar="N",
                    help="run N randomized router property trials and exit")
    ap.add_argument("--autoexit-test", action="store_true",
                    help="scripted auto-exit checks with a fake harness (no spend)")
    ap.add_argument("--resume", action="store_true",
                    help="continue from run_dir/resume.json instead of start")
    ap.add_argument("--from-step", dest="from_step", default=None, metavar="STEP",
                    help="resume at STEP (all dominator predecessors need ledger proof)")
    ap.add_argument("--mark-done", nargs=2, default=None, metavar=("STEP", "SIGNAL"),
                    help="record STEP as finished with SIGNAL (bare signal the agent "
                         "meant but never wrote to its run log) and advance "
                         "resume.json to the routed target without invoking any "
                         "harness; use after verifying the work is really done")
    ap.add_argument("--force", action="store_true",
                    help="with --mark-done, allow advancing past max_rounds loop caps")
    ap.add_argument("--fresh", action="store_true",
                    help="archive any existing run dir and start over")
    ap.add_argument("--reset-rotation", action="store_true",
                    help="delete this pipeline's rotation file and exit "
                         "(rotation restarts at slot 0)")
    ap.add_argument("--customize-harness", dest="customize_harness",
                    action="store_true",
                    help="before the run starts, show every stage's installed "
                         "harness options, pick one per stage, save the whole "
                         "map to <run_dir>/harnesses.json, and start only once "
                         "the map is confirmed; without it the runner decides "
                         "the same map from the rotation order on its own")
    ap.add_argument("--audit-ledger", action="store_true",
                    help="report ledger authority gaps for this run without changing files")
    ap.add_argument("--migrate-ledger", action="store_true",
                    help="backfill deterministic task_file/task hashes for legacy ledger "
                         "entries; ambiguous steps are reported, not guessed")
    ap.add_argument("--repin-ledger", action="store_true",
                    help="re-point every ledger step's git_head at the current "
                         "HEAD so a resume survives an operator baseline "
                         "change; requires --repin-reason")
    ap.add_argument("--repin-reason", default=None, metavar="TEXT",
                    help="why HEAD moved, recorded in the ledger head_repin entry")
    ap.add_argument("--machine-id", default=None,
                    help="stable host ID for the shared phase reservation")
    ap.add_argument("--takeover", action="store_true",
                    help="explicitly take over a retained phase reservation; "
                         "requires an operator decision")
    args = ap.parse_args()

    if args.customize_harness and (args.fuzz or args.autoexit_test
                                   or args.self_test or args.audit_ledger
                                   or args.migrate_ledger or args.mark_done
                                   or args.reset_rotation or args.repin_ledger):
        # These paths never start a job, so there is no map to decide. Fail
        # loudly rather than silently ignoring the flag.
        ap.error("--customize-harness applies only to a run that starts "
                 "harnesses: not with --fuzz, --autoexit-test, --self-test, "
                 "--audit-ledger, --migrate-ledger, --repin-ledger, "
                 "--mark-done, or --reset-rotation")
    if args.fuzz:
        fuzz(args.fuzz)
        return
    if args.autoexit_test:
        autoexit_test()
        return

    if not args.pipeline:
        ap.error("--pipeline is required")

    pipe_path = Path(args.pipeline).resolve()
    pipe_dir = pipe_path.parent
    repo = Path.cwd()
    if args.reset_rotation:
        fp = rotation_file(repo, rotation_key_for(pipe_path))
        fp.unlink(missing_ok=True)
        print(json.dumps({"reset_rotation": fp.name, "reset": True}))
        return
    run = None
    try:
        try:
            pipe = yaml.safe_load(pipe_path.read_text())
        except yaml.YAMLError as e:
            raise Fail(f"pipeline YAML does not parse ({e})")
        validate(pipe, pipe_dir)
        inputs = {}
        for k, spec in pipe["inputs"].items():
            if isinstance(spec, dict):
                if "default" in spec:
                    inputs[k] = spec["default"]
            else:
                inputs[k] = spec
        for item in args.input:
            if "=" not in item:
                raise Fail(f"--input needs k=v, got {item!r}")
            k, v = item.split("=", 1)
            if k not in pipe["inputs"]:
                raise Fail(f"unknown input {k!r}")
            inputs[k] = int(v) if k in INT_INPUTS and re.fullmatch(r"-?\d+", v) else v
        for k, spec in pipe["inputs"].items():
            if k not in inputs and isinstance(spec, dict) and spec.get("required"):
                raise Fail(f"missing required input {k!r}")

        run = Run(pipe, pipe_dir, repo, inputs)
        # Rotation key namespaces by pipeline path, not just stem: two
        # pipeline files with the same stem in different directories are
        # different workflows and rotate independently.
        run.rotation_key = rotation_key_for(pipe_path)
        # The pipeline this plan belongs to, recorded in harnesses.json so a
        # saved map says which workflow it was decided for.
        run.pipe_path = pipe_path
        try:
            phase = int(inputs["phase_number"])
        except (ValueError, TypeError):
            raise Fail(f"input phase_number={inputs['phase_number']!r} is not an integer")
        if not is_runnable_phase(phase):
            raise Fail(
                f"input phase_number={phase} is parked at or above "
                f"{PARKED_PHASE_FLOOR}; the pipeline ignores parked phases")
        if not args.self_test and "phase_file" in inputs:
            inputs["phase_file"] = _validate_phase_file(
                repo, phase, inputs["phase_file"])
            run.inputs["phase_file"] = inputs["phase_file"]
        try:
            run._run_dir = (repo / pipe["run_dir"].format(phase=phase)).resolve()
        except (KeyError, ValueError, IndexError) as e:
            raise Fail(f"run_dir template formats badly ({e})")
        if args.self_test:
            self_test(run, live=args.live)
            return
        if args.audit_ledger or args.migrate_ledger:
            report = audit_or_migrate_ledger(run, migrate=args.migrate_ledger)
            print(json.dumps(report, indent=2))
            sys.exit(0 if not report.get("ambiguous") and not report.get("errors") else 1)
        if args.repin_ledger:
            print(json.dumps(repin_ledger(run, args.repin_reason), indent=2))
            return
        had_run_dir = run._run_dir.exists()
        if not args.dry_run:
            run._run_dir.mkdir(parents=True, exist_ok=True)

        if args.dry_run:
            # A preview shows the same harness map a live run would use: the
            # run's saved plan when it has one, otherwise the plan the runner
            # would decide now (prompting with --customize-harness). A dry run
            # saves nothing, so a previewed choice is not kept.
            run.require_authoritative = False
            plan, _changed = plan_harnesses(
                run, custom=args.customize_harness, fresh=args.fresh)
            run.plan = plan
            print(render_plan(plan) + "\n  (dry run: nothing saved)",
                  file=sys.stderr)
            for sid in run.steps:
                entry = plan["steps"][sid]
                prompt = run.render_task(sid, harness_name=entry["display"])
                print(f"===== step {sid} =====")
                print(f"harness: {[o['harness'] for o in entry['options']]}")
                print(f"planned: {entry['harness']} ({entry['display']})")
                if entry["skipped"]:
                    print("skipped (CLI binary not on PATH): "
                          + ", ".join(f"{s['harness']} ({s['missing_binary']})"
                                      for s in entry["skipped"]))
                print(f"prompt: {len(prompt.encode())} bytes -> "
                      f"{run._run_dir}/{sid}-task-r1.md")
                if args.show_prompts:
                    print(prompt)
            print("dry-run ok: pipeline validates, all steps render")
            return

        done_path = run._run_dir / "run.json"
        if done_path.is_file() and not args.fresh:
            try:
                state = json.loads(done_path.read_text()).get("state", "?")
            except ValueError:
                state = "unparseable"
            if state != "blocked":
                raise Fail(f"run already finished as {state}; --fresh to start over")
            # Blocked is resumable: drop the stale terminal marker and fall
            # through to the resume flow below (which needs resume.json).
            done_path.unlink()
        resumed = None
        rpath = run._run_dir / "resume.json"
        want_from = args.from_step
        if want_from and want_from not in run.steps:
            raise Fail(f"--from {want_from!r} resolves to no step")
        if not args.fresh and (args.resume or want_from or rpath.is_file()):
            if not rpath.is_file():
                raise Fail(f"no resume state at {rpath} (nothing to continue)")
            try:
                resumed = json.loads(rpath.read_text())
            except ValueError as e:
                raise Fail(f"resume.json does not parse ({e})")
            verify_ledger(run, resumed.get("outputs", {}), resumed.get("current"))
            if want_from:
                dom = dominators(pipe)[want_from] - {want_from}
                lp = run._run_dir / "ledger.json"
                proven = set(json.loads(lp.read_text()).get("steps", {})) if lp.is_file() else set()
                missing = sorted(dom - proven)
                if missing:
                    raise Fail(f"--from {want_from}: unproven predecessors {missing} "
                               f"(no completion record)")
                resumed["current"] = want_from
                for e in reversed(resumed.get("events", [])):
                    if e.get("routed_to") == want_from:
                        resumed["prev_step"] = e["step"]
                        break
            auto = not args.resume and not want_from
            print(json.dumps({"resuming": resumed["current"], "auto": auto,
                              **assess(run, resumed.get("current"))}), file=sys.stderr)

        # Every stage's harness is chosen here, before the job starts: the
        # runner decides from the rotation order, or the operator picks each
        # stage's slot with --customize-harness. A saved plan wins, so a resume
        # keeps the models the run already committed to. Deciding before the
        # sync and the phase claim means a plan this run cannot honour (no
        # harness installed, a declined plan) stops the run having claimed
        # nothing and synced nothing.
        plan, plan_changed = plan_harnesses(
            run, custom=args.customize_harness, fresh=args.fresh, resumed=resumed)
        run.plan = plan

        if resumed is None:
            # A fresh phase must refresh both checkouts before its base
            # revision is recorded or any reservation is acquired.
            preflight_sync(run, commit_run_state=False)
        _prepare_reservation(
            run, resumed=resumed is not None, fresh=args.fresh,
            machine_id=args.machine_id, takeover=args.takeover)
        if args.fresh and had_run_dir:
            backup = Path(str(run._run_dir) + f".prev-{int(time.time())}")
            shutil.move(str(run._run_dir), str(backup))
            run._run_dir.mkdir(parents=True, exist_ok=True)
            # The token was written before the archive and moved with it;
            # restore it in the new run directory before any harness starts.
            if run.reservation:
                save_reservation_file(_reservation_path(run), run.reservation)
            print(json.dumps({"fresh": True, "archived": str(backup)}), file=sys.stderr)
        # One write, after any --fresh archive: the plan is the run's model
        # map, so it must be on disk before the first harness starts. An
        # unchanged resume leaves the saved file alone.
        if plan_changed:
            save_harness_plan(run, plan)
        print(render_plan(plan, plan_path(run)), file=sys.stderr)
        if resumed is None:
            commit_start_run_state(run)

        try:
            if args.mark_done:
                step, sig = args.mark_done
                result = mark_done(run, step, sig, force=args.force)
                if result["state"] in {"completed", "blocked", "rejected"}:
                    receipt_path = None
                    if result["state"] == "completed":
                        # Keep a nonterminal marker until the claim-checked
                        # publication and state transition both succeed.
                        _write_pending_completion(run, result)
                        receipt_path = _publish_completion_evidence(run)
                    result = _finish_reservation(
                        run, result, receipt_path=receipt_path)
                    if result["state"] != "blocked":
                        (run._run_dir / "resume.json").unlink(missing_ok=True)
                print(json.dumps(result, indent=2))
                sys.exit(0 if result["state"] in ("completed", "advanced")
                         else 1)
            result = drive(run, pipe, run.invoke, resumed)
            heartbeat = getattr(run, "reservation_heartbeat", None)
            if heartbeat is not None:
                heartbeat.check()
        except KeyboardInterrupt:
            if getattr(run, "reservation", None):
                _mark_publication_failed(run, "interrupted during publication")
                try:
                    _set_reservation_state(run, "paused")
                except CoordinationError as exc:
                    print(f"runner: could not mark reservation paused: {exc}",
                          file=sys.stderr)
            # Operator Ctrl-C killed the step. resume.json was saved before
            # the invocation; keep it so the same command resumes.
            print(json.dumps({"state": "interrupted",
                              "resume": str(run._run_dir / "resume.json")},
                             indent=2))
            sys.exit(130)
        finally:
            heartbeat = getattr(run, "reservation_heartbeat", None)
            if heartbeat is not None:
                heartbeat.stop()
        # Write a nonterminal marker before publication. The publication
        # helper verifies the claim and creates a receipt; only after that
        # succeeds do we change the shared record to completed.
        if result.get("state") == "completed":
            _write_pending_completion(run, result)
            receipt_path = _publish_completion_evidence(run)
        else:
            receipt_path = None
            (run._run_dir / "run.json").write_text(json.dumps(result, indent=2))
        result = _finish_reservation(
            run, result, receipt_path=receipt_path)
        (run._run_dir / "run.json").write_text(json.dumps(result, indent=2))
        if result["state"] != "blocked":
            (run._run_dir / "resume.json").unlink(missing_ok=True)
        print(json.dumps(result, indent=2))
        sys.exit(0 if result["state"] == "completed" else 1)
    except ReservationConflict as e:
        print(json.dumps({"state": "WAIT_FOR_CLAIM", "phase": e.phase,
                          "owner": e.record.get("machine_id"),
                          "status": e.record.get("status"),
                          "error": str(e)}, indent=2))
        sys.exit(3)
    except ReservationFenced as e:
        print(json.dumps({"state": "FENCED", "error": str(e)}, indent=2))
        sys.exit(4)
    except (Fail, CoordinationError) as e:
        if run is not None and getattr(run, "reservation", None):
            _mark_publication_failed(run, e)
            try:
                _set_reservation_state(run, "blocked")
            except CoordinationError as reservation_error:
                print(f"runner: could not mark reservation blocked: "
                      f"{reservation_error}", file=sys.stderr)
        print(json.dumps(config_error_payload(e), indent=2))
        sys.exit(2)


if __name__ == "__main__":
    main()

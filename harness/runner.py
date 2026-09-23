#!/usr/bin/env python3
# Copyright 2026 Agent Memoir Developers (https://agentmemoir.com/)
# SPDX-License-Identifier: Apache-2.0
"""Generic stage-pipeline runner.

Reads a pipeline YAML (see private/clio-private/harness/pipelines/default.yaml
for the contract), renders each step's stage file by binding its {{PLACEHOLDERS}},
invokes the stage's harness CLI, matches the final-line signal, and routes.

Usage (run from the repo root):
  python3 private/clio-private/harness/runner.py --pipeline private/clio-private/harness/pipelines/default.yaml \
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
    2 config_error (machine-readable JSON on stdout in all cases).
  - No runner timeouts, but agy enforces its own --print-timeout
    (default 5m) inside the harness; long reviews near that ceiling need
    an explicit harness-side decision, not a runner change.

Foreground: every harness runs attached in the operator's terminal with
inherited stdio; the runner polls the step's run log and closes the
session ~15 s after the final signal lands. Ctrl-C kills
the step; rerunning the same command resumes. See instruction.md.
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
# Per-invocation signal nonce: every harness invocation gets a fresh
# random token appended to its task file. Non-*_BLOCKED* signal lines must
# carry it as a separate token, so a mid-run echo of the bare signal word
# can neither close the session nor route the pipeline. *_BLOCKED lines
# need no nonce (ending as blocked is always operator-visible).
NONCE_BYTES = 4
NONCE_FOOTER = (
    "\n\n## Signal nonce for this invocation: `{nonce}`\n\n"
    "Append this nonce as a separate token after your signal word, e.g. "
    "`REMEDIATOR_DONE {nonce}` (use your own step's signal word; for "
    "signals with arguments put the nonce last, e.g. `ADVERSARY_DONE "
    "findings=<path> {nonce}`). A signal line without this exact nonce "
    "is ignored. Nonces quoted from earlier prompts are stale: use only "
    "this one. `*_BLOCKED` lines need no nonce.\n")
END_TOKENS = ("_DONE", "_APPROVED", "_REJECTED")
# OpenCode v2 only: stages run headless via `opencode run`. Reasoning effort
# joins the model selector after `#` (provider/model#variant).
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
    """Read durable rotation counts. A missing file starts at zero; a
    corrupt one warns and starts empty: a cosmetic counter never blocks."""
    fp = rotation_file(repo, key)
    try:
        data = json.loads(fp.read_text())
    except OSError:
        return {}
    except ValueError as e:
        print(f"rotation: {fp.name} does not parse ({e}); "
              f"starting at zero", file=sys.stderr)
        return {}
    try:
        counts = {str(k): int(v) for k, v in dict(data).items()}
    except (TypeError, ValueError) as e:
        print(f"rotation: {fp.name} has bad counts ({e}); "
              f"starting at zero", file=sys.stderr)
        return {}
    return counts


def save_rotation(repo, key, harness_use):
    # Single-operator assumption: runs are foreground and sequential, so a
    # plain write is enough; concurrent runs are last-writer-wins.
    fp = rotation_file(repo, key)
    try:
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(json.dumps(harness_use, indent=2))
    except OSError as e:
        print(f"rotation: cannot write {fp.name} ({e})",
              file=sys.stderr)


def opencode_launch(model, effort, pointer, stage_name=OPENCODE_AGENT):
    """Build the opencode headless `run` command and environment.

    OpenCode v2 only: the v2 root TUI takes no model/agent/prompt flags,
    so every stage runs headless via `opencode run`. --auto auto-approves
    permissions (mandated by the stages). Reasoning effort joins the model
    after `#` (v2 selector syntax: provider/model#variant). No --agent:
    v2 hard-errors on unknown agent names ("Agent not found") instead of
    falling back, and the stage names carry no system prompt (the task
    file holds it), so every stage runs as the default agent. Output
    streams to the tmux pane, which the driver pipe-panes into the
    session log; the runner still closes the step once the final signal
    lands in the run log. Returns (cmd, env)."""
    cmd = ["opencode", "run", "--auto"]
    env = dict(os.environ)
    if model != "auto":
        cmd += ["-m", f"{model}#{effort}" if effort else model]
    cmd += [pointer]
    return cmd, env

TOP_KEYS = {"version", "run_dir", "inputs", "start",
            "ends", "steps"}
STEP_KEYS = {"stage", "record_as", "bindings", "when", "end",
             "require_file", "skip_when_empty", "snapshot", "max_rounds",
             "on_exhausted"}
SOURCE_KEYS = {"output", "task", "join", "prev_output"}
STAGE_KEYS = {"name", "harness", "harness_names", "placeholders",
              "description", "role"}
KNOWN_CLIS = {"cursor", "agy", "hermes", "opencode"}

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


class Fail(Exception):
    pass


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
        self.persist_rotation = True
        self.rotation_key = None
        self.prev_step = None
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
            # Quoted prior prompt renders with that step's planned r1 name:
            # context, not a recording instruction.
            return self.render_task(
                src["task"], seen | {sid},
                harness_name=display_name(self.planned_harness(src["task"])))
        subs = [self.resolve(sid, sub, ctx, seen) for sub in src["join"]]
        return src.get("sep", "\n\n").join(subs)

    def render_task(self, sid, seen=..., harness_name=None):
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
        # given, else this step's planned r1 name. Never a pipeline binding.
        values["harness"] = (harness_name if harness_name is not None
                             else display_name(self.planned_harness(sid)))

        def sub_token(m):
            tok = m.group(1)
            if tok not in values:
                raise Fail(f"step {sid}: unbound body token {tok!r}")
            return values[tok]

        return TOKEN_RE.sub(sub_token, body)

    def planned_harness(self, sid):
        """First rotation slot: the planned r1 harness for previews and
        quoted context. The single source is the stage frontmatter list."""
        meta, _ = self.stages[sid]
        hs = meta["harness"] if isinstance(meta["harness"], list) else [meta["harness"]]
        return hs[0]

    def harness_for(self, sid):
        """Peek the harness for the next invocation WITHOUT consuming a
        rotation slot. The slot is consumed only after a successful invoke
        (see drive()), so a crash between render and invoke retries the
        same harness instead of silently shifting the rotation. Note: the
        visits counter still pre-increments, so a retried render lands in
        an rN+1 task file running the same harness — cosmetic only."""
        meta, _ = self.stages[sid]
        hs = meta["harness"] if isinstance(meta["harness"], list) else [meta["harness"]]
        return hs[self.harness_use.get(sid, 0) % len(hs)]

    def invoke(self, harness, task_path, log_path, usage_path=None, when=None,
               nonce=None, sid=None):
        """Run the harness attached in the foreground: inherited stdio, the
        operator watches and approves prompts, the runner closes the session
        ~15 s after the final signal lands in the run log.
        The log text doubles as the step output. Returns (log_text, meta)."""
        cli, provider, model, effort = parse_harness(harness)
        provider = resolve_provider(cli, provider)
        model = resolve_model(cli, provider, model)
        home = str(Path.home())
        os.environ["PATH"] = f"{home}/.local/bin:{home}/.opencode/bin:{os.environ['PATH']}"
        pointer = TASK_POINTER.format(path=task_path)
        env = None
        full = f"{provider}/{model}" if provider else model
        if cli == "cursor":
            cmd = ["agent"] + (["--model", full] if full != "auto" else []) + [pointer]
        elif cli == "opencode":
            stage_name = self.stages[sid][0]["name"] if sid else OPENCODE_AGENT
            cmd, env = opencode_launch(full, effort, pointer, stage_name)
        elif cli == "agy":
            # -i takes the prompt as its value: it must come last or it
            # swallows the next token (e.g. --model) as prompt text.
            cmd = (["agy", "--dangerously-skip-permissions", "--model", full]
                   + (["--effort", effort] if effort else []) + ["-i", pointer])
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
        banner(cli, harness, task_path, log_path)
        text, rc, info = run_attached(cmd, log_path, when, nonce,
                                      cwd=self.repo, env=env)
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
             "here first, then continue from where the previous attempt stopped.", ""]
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


def git_head(run):
    try:
        r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=run.repo,
                           capture_output=True, text=True, timeout=30)
        return r.stdout.strip() or None
    except Exception:  # noqa: BLE001 - forensics are best-effort
        return None


def note_completion(run, sid, sig, harness):
    """Record a step's completion proof: signal, output hash, artifact
    hashes, git HEAD. Called for every step whose signal was accepted."""
    s = run.steps[sid]
    arts = {}
    for rel in [s.get("require_file"), (s.get("snapshot") or {}).get("to")]:
        if not rel:
            continue
        fp = run._run_dir / rel
        if fp.is_file():
            arts[rel] = {"bytes": fp.stat().st_size, "sha256": sha_file(fp)}
    lp = run._run_dir / "ledger.json"
    try:
        ledger = json.loads(lp.read_text())
    except (OSError, ValueError):
        ledger = {"order": [], "steps": {}}
    if sid not in ledger["order"]:
        ledger["order"].append(sid)
    ledger["steps"][sid] = {"signal": sig, "harness": harness,
                            "agent": display_name(harness),
                            "visits": run.visits.get(sid, 0),
                            "output_sha256": sha_str(run.outputs.get(sid, "")),
                            "artifacts": arts, "git_head": git_head(run)}
    lp.write_text(json.dumps(ledger, indent=2))


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
    except ValueError:
        raise Fail("ledger.json does not parse")
    mutable = {(run.steps[sid].get("snapshot") or {}).get("from")
               for sid in run.steps} - {None}
    head_now = git_head(run)
    for sid in ledger.get("order", []):
        e = ledger["steps"][sid]
        if sid not in outputs:
            raise Fail(f"ledger: step {sid} completed earlier but its output is gone")
        if sid != current and sha_str(outputs[sid]) != e["output_sha256"]:
            raise Fail(f"ledger: step {sid} output changed since completion")
        for rel, a in e.get("artifacts", {}).items():
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
    logs = sorted(run._run_dir.glob(f"{step}-task-r*.log"))
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
            try:
                empty = not json.loads(fpath.read_text()).get("findings")
            except (ValueError, AttributeError):
                empty = not fpath.read_text().strip()
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
        rpath.write_text(json.dumps({
            "current": step, "outputs": run.outputs, "visits": run.visits,
            "harness_use": run.harness_use, "prev_step": run.prev_step,
            "transcript": transcript, "events": events}, indent=2))
        result = {"run_id": run_id, "phase": f"{phase:06d}",
                  "state": "blocked", "transcript": transcript,
                  "events": events}
        done_path.write_text(json.dumps(result, indent=2))
        return result
    note_completion(run, step, line, harness)
    if target in run.pipe["ends"]:
        event["routed_to"] = target
        events.append(event)
        result = {"run_id": run_id, "phase": f"{phase:06d}",
                  "state": target, "transcript": transcript,
                  "events": events}
        done_path.write_text(json.dumps(result, indent=2))
        rpath.unlink(missing_ok=True)
        return result
    event["routed_to"] = target
    events.append(event)
    run.prev_step, nxt = step, target
    rpath.write_text(json.dumps({
        "current": nxt, "outputs": run.outputs, "visits": run.visits,
        "harness_use": run.harness_use, "prev_step": run.prev_step,
        "transcript": transcript, "events": events}, indent=2))
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


BANNER_ART = r"""
  ____   _____  _____  ____
 / ___| |_   _|| ____||  _ \
 \___ \   | |  |  _|  | |_) |
  ___) |  | |  | |___ |  __/
 |____/   |_|  |______|_|
"""


def banner(cli, harness, task_path, log_path):
    """Announce the start of a new foreground harness step."""
    bar = "=" * 76
    print(f"\n{bar}{BANNER_ART}{bar}")
    print(f"  STEP     {Path(task_path).stem}      HARNESS  {harness}")
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
                      stdin_fd, out_fd=None):
    """Run cmd under a pty, forwarding stdin->pty and pty->stdout while
    capturing all console output to tui_path. The operator experience is
    unchanged; the runner additionally scans the capture with the same
    signal predicate (nonce included). Operator Ctrl-C keeps today's
    contract (kills the step): the byte still reaches the child first,
    exactly like a tty interrupt, then the step is torn down."""
    master, slave = pty.openpty()
    _pty_set_size(master, stdin_fd)
    try:
        proc = subprocess.Popen(cmd, stdin=slave, stdout=slave,
                                stderr=slave, cwd=cwd, env=env,
                                start_new_session=True)
    except FileNotFoundError:
        os.close(master)
        os.close(slave)
        raise Fail(f"harness binary missing ({cmd[0]} not on PATH)")
    os.close(slave)
    if out_fd is None:
        out_fd = sys.stdout.fileno()
    try:
        return _pty_forward(proc, master, stdin_fd, out_fd, log_path,
                            tui_path, when, nonce)
    finally:
        try:
            os.close(master)
        except OSError:
            pass


def _pty_forward(proc, master, stdin_fd, out_fd, log_path, tui_path,
                 when, nonce):
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
            if rc is None and time.time() >= next_nudge and not done:
                print(f"runner: still no completion signal ({want}) in "
                      f"{log_path} after {int(IDLE_NUDGE_S)} s idle. If the "
                      f"agent says it is done, tell it to run: "
                      f"printf '%s\\n' '<SIGNAL>{' ' + nonce if nonce else ''}'"
                      f" >> {log_path}",
                      file=sys.stderr, flush=True)
                next_nudge = time.time() + IDLE_NUDGE_S
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


def run_attached(cmd, log_path, when, nonce=None, cwd=None, env=None):
    """Run a harness attached in the foreground and wait for its signal.

    Under a terminal the child runs under a pty: the operator sees the
    identical interface, while all console output is also captured to
    `<step>-task-r<N>.tui.log` and scanned with the same signal predicate
    (a console-only signal still routes, marked signal_via="mirror"). Without a
    terminal, or when the pty is unavailable, falls back to a plain
    attached spawn with inherited stdio.

    Once the final signal is stable on a quiescent log (AUTOEXIT_STABLE_POLLS
    consecutive polls with no growth), wait AUTOEXIT_GRACE_S so the operator
    can read the on-screen summary, then close the session
    (SIGINT -> SIGTERM -> SIGKILL). Operator Ctrl-C kills the step;
    the KeyboardInterrupt propagates (runner exits 130, resume kept).
    Returns (log_text, returncode, info) where info carries tui_log and an
    optional mirror_signal."""
    try:
        tui_path = Path(log_path).with_name(Path(log_path).stem + ".tui.log")
        if _HAVE_PTY and sys.stdin.isatty() and sys.stdout.isatty():
            try:
                return _run_attached_pty(cmd, log_path, tui_path, when, nonce,
                                         cwd, env, sys.stdin.fileno())
            except Exception as e:  # noqa: BLE001 - foreground must survive
                print(f"runner: pty mirror unavailable ({e}); plain spawn",
                      file=sys.stderr, flush=True)
        return _run_attached_plain(cmd, log_path, when, nonce, cwd, env)
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
        raise Fail(f"run log missing: {log_path} (agent never wrote it)")
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
            # The file normally leads (every consume writes through);
            # max-merge keeps both orders safe.
            for sid, n in load_rotation(run.repo, run.rotation_key).items():
                run.harness_use[sid] = max(run.harness_use.get(sid, 0), n)
        run.prev_step = resumed.get("prev_step")
        current = resumed["current"]
        transcript = resumed.get("transcript", [])
        events = resumed.get("events", [])
        verify_ledger(run, resumed.get("outputs", {}), current)
    else:
        current, transcript, events = pipe["start"], [], []
        if run.persist_rotation:
            run.harness_use = load_rotation(run.repo, run.rotation_key)
    reframe = resumed is not None

    def save(nxt):
        (run._run_dir / "resume.json").write_text(json.dumps({
            "current": nxt, "outputs": run.outputs, "visits": run.visits,
            "harness_use": run.harness_use, "prev_step": run.prev_step,
            "transcript": transcript, "events": events}, indent=2))
    Guard = 10000
    while True:
        if len(events) >= Guard:
            raise Fail("routing loop exceeded 10000 steps (uncapped cycle?)")
        s = run.steps[current]
        run.visits[current] = run.visits.get(current, 0) + 1
        t0 = time.time()
        if "snapshot" in s:
            src = run._run_dir / s["snapshot"]["from"]
            dst = run._run_dir / s["snapshot"]["to"]
            if not dst.exists() and src.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
        harness = run.harness_for(current)
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
                              nonce, sid=current)
        # Consume the rotation slot only now: a crash before this point
        # retries the same harness instead of shifting the rotation.
        run.harness_use[current] = run.harness_use.get(current, 0) + 1
        if run.persist_rotation:
            save_rotation(run.repo, run.rotation_key, run.harness_use)
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
            note_completion(run, current, sig, harness)
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
                try:
                    empty = not json.loads(fpath.read_text()).get("findings")
                except (ValueError, AttributeError):
                    empty = not fpath.read_text().strip()
            if "skip_when_empty" in s and empty:
                event["via"] = "skip"
                event["routed_to"] = s["skip_when_empty"]
                events.append(event)
                note_completion(run, current, sig, harness)
                run.prev_step, current = current, s["skip_when_empty"]
                save(current)
                if current in pipe["ends"]:
                    return {"run_id": run_id, "phase": f"{phase:06d}",
                            "state": current, "transcript": transcript, "events": events}
                continue
        target = s["when"][key]
        event["via"] = "edge"
        event["routed_to"] = target
        events.append(event)
        note_completion(run, current, sig, harness)
        if target in pipe["ends"]:
            event["via"] = "edge-end"
            return {"run_id": run_id, "phase": f"{phase:06d}",
                    "state": target, "transcript": transcript, "events": events}
        if target in run.visits and "max_rounds" in s \
                and run.visits[current] >= s["max_rounds"]:
            if "on_exhausted" not in s:
                raise Fail(f"step {current}: loop cap hit with no on_exhausted")
            event["via"] = "exhausted"
            return {"run_id": run_id, "phase": f"{phase:06d}",
                    "state": s["on_exhausted"], "transcript": transcript, "events": events}
        run.prev_step, current = current, target
        save(current)


def self_test(run, live=False):
    """Static harness checks (no inference spend) plus optional live probes."""
    home = str(Path.home())
    os.environ["PATH"] = f"{home}/.local/bin:{home}/.opencode/bin:{os.environ['PATH']}"
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
            binary = {"cursor": "agent", "agy": "agy",
                      "hermes": "hermes", "opencode": "opencode"}[cli]
            path = shutil.which(binary)
            check(f"{h} binary", path is not None, path or "not on PATH")
            if path is None:
                continue
            full = f"{provider}/{model}" if provider else model
            if cli == "agy":
                try:
                    out = subprocess.run(["agy", "models"], capture_output=True,
                                         text=True, timeout=60).stdout
                    check(f"{h} model listed", full in out,
                          "slug in agy models" if full in out else "slug missing")
                except subprocess.TimeoutExpired:
                    check(f"{h} model listed", False, "agy models timed out")
            elif cli == "opencode" and provider:
                try:
                    # v2 only: `opencode models` takes no provider argument;
                    # it lists every configured provider's catalog at once.
                    out = subprocess.run(["opencode", "models"],
                                         capture_output=True, text=True,
                                         timeout=120).stdout
                    check(f"{h} model listed", model in out,
                          "slug in opencode models" if model in out else "slug missing")
                except subprocess.TimeoutExpired:
                    check(f"{h} model listed", False, "opencode models timed out")
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

    import tempfile
    # Signal convention: last_line strips one leading ISO-8601 timestamp from
    # the final log line, then match_signal matches on the bare signal word.
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

    # Quiescence-gated stability: growth resets, quiet + signal accumulates,
    # quiet without signal stays at zero.
    check("poll stable: growth resets", _poll_stable(True, True, 5) == 0)
    check("poll stable: quiet signal accumulates",
          _poll_stable(True, False, 1) == 2)
    check("poll stable: quiet no-signal stays zero",
          _poll_stable(False, False, 3) == 0)

    # opencode headless run shape (v2 only): `run` subcommand, --auto,
    # -m provider/model with effort joined as #variant, message last,
    # never --agent (v2 hard-errors on the stage names).
    cmd_h, env_h = opencode_launch("togetherai/zai-org/GLM-5.3-Flash", "high",
                                   "PTR", "am_implement")
    check("opencode run cmd (effort)",
          cmd_h[:3] == ["opencode", "run", "--auto"]
          and cmd_h[cmd_h.index("-m") + 1] == "togetherai/zai-org/GLM-5.3-Flash#high"
          and "--agent" not in cmd_h
          and cmd_h[-1] == "PTR"
          and "OPENCODE_CONFIG_CONTENT" not in env_h)
    cmd_p, env_p = opencode_launch("togetherai/zai-org/GLM-5.3-Flash", None, "PTR")
    check("opencode run cmd (no effort)",
          cmd_p[cmd_p.index("-m") + 1] == "togetherai/zai-org/GLM-5.3-Flash"
          and cmd_p[-1] == "PTR"
          and "OPENCODE_CONFIG_CONTENT" not in env_p)
    # stage_name is accepted but unused: no --agent is ever passed.
    cmd_f, env_f = opencode_launch("togetherai/zai-org/GLM-5.3-Flash", "high",
                                   "PTR")
    check("opencode run cmd (no agent flag)", "--agent" not in cmd_f)

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
    t = (run.render_task("remediator",
                         harness_name=display_name(
                             "opencode:togetherai/zai-org/GLM-5.3-Flash@high"))
         if "remediator" in run.steps else "")
    check("harness token: resolves single harness",
          "remediator" not in run.steps or (
              "OpenCode CLI (Together . GLM-5.3 Flash High)" in t
              and "{{harness}}" not in t
              and ") / OpenCode" not in t),
          "remediator prompt carries one real harness")
    check("harness token: unknown id falls back raw",
          display_name("mystery_cli:whatever") == "mystery_cli:whatever",
          "fallback returns raw id")

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
    rec = rot_drive(5, "rk-a", rot_end)
    check("rotation: corrupt file restarts at zero",
          rec["transcript"][0]["harness"].endswith("GLM-5.3-Flash@high"),
          "warned and completed on slot 0")

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
    check("mark-done: ledger proves the step",
          "s0" in json.loads(
              (mr._run_dir / "ledger.json").read_text())["steps"],
          "s0 entry present")
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
    args = ap.parse_args()

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
        try:
            phase = int(inputs["phase_number"])
        except (ValueError, TypeError):
            raise Fail(f"input phase_number={inputs['phase_number']!r} is not an integer")
        try:
            run._run_dir = (repo / pipe["run_dir"].format(phase=phase)).resolve()
        except (KeyError, ValueError, IndexError) as e:
            raise Fail(f"run_dir template formats badly ({e})")
        if args.self_test:
            self_test(run, live=args.live)
            return
        if not args.dry_run:
            run._run_dir.mkdir(parents=True, exist_ok=True)

        if args.dry_run:
            for sid in run.steps:
                meta, _ = run.stages[sid]
                hs = meta["harness"] if isinstance(meta["harness"], list) else [meta["harness"]]
                # Preview shows the planned r1 name (first rotation slot),
                # matching what the first live invocation receives.
                prompt = run.render_task(sid, harness_name=display_name(hs[0]))
                print(f"===== step {sid} =====")
                print(f"harness: {hs}")
                print(f"prompt: {len(prompt.encode())} bytes -> "
                      f"{run._run_dir}/{sid}-task-r1.md")
                if args.show_prompts:
                    print(prompt)
            print("dry-run ok: pipeline validates, all steps render")
            return

        if args.fresh and run._run_dir.exists():
            backup = Path(str(run._run_dir) + f".prev-{int(time.time())}")
            shutil.move(str(run._run_dir), str(backup))
            print(json.dumps({"fresh": True, "archived": str(backup)}), file=sys.stderr)
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

        try:
            if args.mark_done:
                step, sig = args.mark_done
                result = mark_done(run, step, sig, force=args.force)
                print(json.dumps(result, indent=2))
                sys.exit(0 if result["state"] in ("completed", "advanced")
                         else 1)
            result = drive(run, pipe, run.invoke, resumed)
        except KeyboardInterrupt:
            # Operator Ctrl-C killed the step. resume.json was saved before
            # the invocation; keep it so the same command resumes.
            print(json.dumps({"state": "interrupted",
                              "resume": str(run._run_dir / "resume.json")},
                             indent=2))
            sys.exit(130)
        (run._run_dir / "run.json").write_text(json.dumps(result, indent=2))
        if result["state"] != "blocked":
            (run._run_dir / "resume.json").unlink(missing_ok=True)
        print(json.dumps(result, indent=2))
        sys.exit(0 if result["state"] == "completed" else 1)
    except Fail as e:
        print(json.dumps({"state": "config_error", "error": str(e)}, indent=2))
        sys.exit(2)


if __name__ == "__main__":
    main()

# Pipeline runner (`runner.py`)

The runner executes a stage pipeline: it renders each step's stage file by binding its placeholders, invokes the step's harness CLI attached in the operator's terminal, reads the step's final-line signal from its run log, and routes to the next step. Start with `instruction.md` for the operator workflow; this file is the reference for the runner itself.

## Commands

```bash
python3 private/clio-private/harness/runner.py --pipeline private/clio-private/harness/pipelines/default.yaml --input phase_number=100060 --input phase_file=private/clio-private/roadmap/phase-100060.md --dry-run
python3 private/clio-private/harness/runner.py --pipeline private/clio-private/harness/pipelines/default.yaml --input phase_number=100060 --input phase_file=private/clio-private/roadmap/phase-100060.md
python3 private/clio-private/harness/runner.py --pipeline private/clio-private/harness/pipelines/default.yaml --input phase_number=100060 --input phase_file=private/clio-private/roadmap/phase-100060.md --self-test
python3 private/clio-private/harness/runner.py --pipeline private/clio-private/harness/pipelines/default.yaml --input phase_number=100060 --input phase_file=private/clio-private/roadmap/phase-100060.md --resume
python3 private/clio-private/harness/runner.py --pipeline private/clio-private/harness/pipelines/default.yaml --input phase_number=100060 --input phase_file=private/clio-private/roadmap/phase-100060.md --from-step remediator
python3 private/clio-private/harness/runner.py --pipeline private/clio-private/harness/pipelines/default.yaml --input phase_number=100060 --input phase_file=private/clio-private/roadmap/phase-100060.md --mark-done remediator REMEDIATOR_DONE
python3 private/clio-private/harness/runner.py --pipeline private/clio-private/harness/pipelines/default.yaml --input phase_number=100060 --input phase_file=private/clio-private/roadmap/phase-100060.md --fresh
python3 private/clio-private/harness/runner.py --pipeline private/clio-private/harness/pipelines/default.yaml --reset-rotation
python3 private/clio-private/harness/runner.py --fuzz 50
python3 private/clio-private/harness/runner.py --autoexit-test
```

`--dry-run` validates everything and prints rendered-prompt sizes without invoking any harness (`--show-prompts` also prints full prompts). `--self-test` runs static harness checks with no inference spend (`--live` adds one-word inference probes, which spend). `--mark-done STEP SIGNAL` records STEP as finished with SIGNAL (for work that is done but whose run log never got the bare signal line) and advances `resume.json` to the routed target without invoking any harness; verify the work first, then `--resume` continues. `--fuzz N` runs N randomized router property trials in temp dirs. `--autoexit-test` runs scripted fake-harness checks of the auto-exit logic. `--fresh` archives the existing run dir to `<run_dir>.prev-<timestamp>` and starts over. `--reset-rotation` deletes the pipeline's rotation file and exits. `--pipeline` is always required. Run from the repo root: the repo root is the process working directory and `run_dir` resolves against it.

Exit codes: 0 completed, 1 terminal non-complete (rejected/blocked), 2 config error (machine-readable JSON on stdout in all cases), 130 operator Ctrl-C.

Parked phase numbers are `>= 900000`. They remain in the roadmap for planning, but `next_phase.py` never selects them and `runner.py` rejects them with a config error instead of launching a run. See `phase_policy.py` for the shared floor.

## Harness identifiers

Each stage file declares `harness:` as one identifier or a list of them. Format: `<CLI>:<Provider>/<Model>[@<Effort>]`, where provider and effort are optional. Examples: `opencode:together/glm-5.3-flash@high`, `opencode:go/deepseek-v4.1-flash@high`, `agy:gemini-3.8-flash-high`, `opencode:openrouter/deepseek-v4.1-flash@max`.

Known CLIs: `opencode`, `agy`, `cursor`, `hermes`. A present but unknown `@effort` is a config error; known efforts are none, minimal, low, medium, high, xhigh, max, ultra. Full (unaliased) identifiers work identically: anything not in the alias tables resolves to itself, so both styles can be mixed.

Provider aliases (opencode CLI only): `go` always means the installed `opencode-go` provider, `together` always means `togetherai`. Model aliases are keyed by resolved provider, because each registry names the same model its own way: on `togetherai`, `glm-5.3-flash` expands to `zai-org/GLM-5.3-Flash` and `deepseek-v4.1-flash` expands to `deepseek-ai/DeepSeek-V4.1-Flash`; on `openrouter`, `deepseek-v4.1-flash` expands to `deepseek/deepseek-v4.1-flash`; on `opencode-go` the bare slugs are already full. Unmapped models pass through untouched, and aliases apply to the opencode CLI only.

How each CLI is invoked (all attached in the foreground with inherited stdio; the harness receives a 2-line pointer to its task file, never prompt text): `agy --dangerously-skip-permissions --model <model> [--effort <effort>] -i <pointer>`; `opencode run --auto [-m <provider/model[#variant]>] <pointer>` (v2 headless; output streams to the pane, which the driver pipe-panes into the session log); `agent [--model <model>] <pointer>` for cursor; `hermes [--usage-file <file>] chat --query-file <taskfile> [--provider <p> -m <m>] [--reasoning <effort>]` for hermes (usage files only for hermes). The runner polls the step's run log and closes the session about 15 s after the final signal lands. A nonzero harness exit fails the step only when the run log carries no valid final signal; a missing or empty log always fails.

A list of identifiers means round-robin: each invocation of that step uses the next entry, wrapping around. Repeating an identifier gives it proportional weight; interleave repeated entries with other identifiers when the desired ratio permits it. Counters persist across runs in `private/clio-private/runs/.harness-rotation-<pipeline>-<hash>.json` (one file per pipeline file, keyed by pipeline path), so consecutive runs keep alternating. Rotation slots are consumed only after a successful invoke, so a crash between render and invoke retries the same harness. `--fresh` does not reset rotation.

Current step selections: developer rotates `opencode:go/deepseek-v4.1-flash@max`, `agy:gemini-3.8-flash-high`, and `opencode:together/glm-5.3-flash@high`; adversary rotates `opencode:go/space-bunny-free@max`, `agy:gemini-3.8-flash-high`, `opencode:go/space-bunny-free@max`, and `opencode:openrouter/deepseek-v4.1-flash@max`; remediator and finalize use `opencode:together/glm-5.3-flash@high`; approver rotates `opencode:go/space-bunny-free@max`, `agy:gemini-3.8-flash-high`, and `opencode:go/space-bunny-free@max`.

Each stage file also declares `harness_names:` mapping every harness id to its display name, which is what `{{harness}}` renders to in prompts and what lands in Attribution rows and the ledger. Anything unmapped falls back to the raw id.

## Pipeline files

`pipelines/default.yaml` holds the whole workflow: `version` (must be 1), `run_dir` (a format template, currently `private/clio-private/runs/phase-{phase:06d}`), `inputs` (defaults or `{required: true}` markers; `--input k=v` overrides, `phase_number` and `max_remedy_rounds` parse as ints), `start`, `ends`, and `steps`. Each step names a `stage` file, a `record_as` label, `bindings`, and exactly one of `when` (signal-to-target routing map) or `end` (a terminal state from `ends`). Optional keys: `require_file`, `skip_when_empty`, `snapshot` (exactly `from`/`to`), `max_rounds` with `on_exhausted`.

Binding values are format strings over inputs plus run builtins (`phase`, `run_id`, `run_dir`, `agent`, `round`, `rounds`), `{output: <step>}` (that step's last output text), `{task: <step>}` (that step's rendered stage text), `{join: [...]}` with optional `sep`, or `{prev_output: true}` (the output of whatever step routed here). `{{harness}}` is runner-provided per invocation and must be neither declared in the stage's `placeholders` nor bound in the pipeline.

Validation is strict: unknown keys; start, edge targets, `skip_when_empty`/`on_exhausted`, and binding source steps that resolve nowhere; non-positive `max_rounds`; a step with neither or both of `when`/`end`; end states outside `ends`; unbound or over-bound placeholders; body tokens outside placeholders plus `{{harness}}`; missing stage files; unknown harness CLIs or malformed harness ids.

## Signals and routing

Signal matching is a prefix match scanned bottom-up over the last 10 non-empty run-log lines: the line equals a `when` key or starts with the key plus a space or colon. One leading ISO-8601 timestamp plus any `| ... |` journal prefixes are stripped before matching, and a `{"signal": ..., "nonce": ...}` JSON line counts the same as its bare form. Every invocation carries a fresh random nonce (appended to the task file); non-`*_BLOCKED*` signal lines must carry it as a separate token, so a mid-run echo of the bare signal word neither closes the session nor routes the pipeline. A signal printed only in chat never counts toward the log match, but under a terminal the runner also captures the harness console to `<step>-task-r<N>.tui.log` and a console-only signal still routes (marked `signal_via: mirror`). If the log stops growing with no signal for 5 minutes the runner prints the exact `printf ... >> <log>` recovery line to stderr and keeps waiting; on the pty path it also types a short reminder into the harness's own input and submits it (Enter), so an agent that finished but forgot the log line can be told to write it. The reminder targets only harnesses that run with permissions auto-approved (`opencode`, `agy`) and is skipped when the console tail looks like a confirmation prompt, so it is never typed into a dialog. The text is signal-safe (no nonce, no token ending in BLOCKED), rate-limited (first after 5 minutes, each later one twice as far out, at most three per invocation, skipped once the operator has typed at all, and one extra Enter if the first appears swallowed), audited to a run-level `reminders.log`, and never written to the run log; it can never complete the step. Any signal whose first token ends in `BLOCKED` ends the run as blocked from any step. End steps (no `when`) accept a `*_DONE` / `*_APPROVED` / `*_REJECTED`-style first token the same way. A matched edge into an already-visited target caps at the current step's `max_rounds` and then ends with `on_exhausted`.

### Idle-reminder capability by harness

| CLI | Permissions | Reminder | Why |
|-----|-------------|----------|-----|
| `opencode` | `--auto` | on | Full TUI with an input box; tools run in separate processes, so injected stdin reaches the TUI, not a running tool. |
| `agy` | `--dangerously-skip-permissions` | on | Interactive input with permissions auto-approved. |
| `cursor` (`agent`) | operator approves | off | May wait at an approval dialog; never typed into. |
| `hermes` | operator | off | Chat input; not in the default pipeline. |

The pty write is the only delivery today; `_deliver_reminder` is the seam a harness-native sender (for example an OpenCode server call) could replace, keeping the pty write as the fallback.

After the signal, `require_file` is verified before routing: for a findings report the runner parses the JSON and treats it as empty only when both `findings` and `addressed_issues` are empty; otherwise it checks the file is non-empty. With `skip_when_empty`, an empty artifact routes to the skip target instead. `snapshot` copies run-dir `from` to `to` before the step unless the target already exists. Conventions that must not change silently: `agent` is the step id, and finalize is attributed Developer but logs to `finalize.log`.

## Open issues and incidental bugs

The adversary triages every open issue through `harness/github_issues.py list-open` (light records: title, body, labels, comment count, no comment bodies) and fetches the full thread with `view` for every plausibly related issue. It records only fully resolved, directly in-scope issues in `findings.json:addressed_issues`, with the digest taken from `view`. The remediator preserves and revalidates that list; the approver rejects changed, closed, related-only, or partial candidates. Finalize receives `findings.json` through `ISSUE_AUDIT_PATH` and may close only approved candidates, after both repositories push; an empty candidate list is valid and means close nothing. The close helper checks the issue digest, uses a retry-safe public commit marker, and never closes on a mismatch.

Every main stage files a public, sanitized GitHub bug report when it confirms a new bug not already named by the task or current findings. It first reads the run-local `reported-bugs.json` ledger (a ledger hit counts as an equivalent even when search misses it), then searches for an equivalent open issue, and never duplicates one. After a successful report it appends to the ledger. Reporting is incidental: stages confirm the trigger and impact, but do not hunt for unrelated root causes or fix unrelated bugs. All public titles, bodies, close comments, and ledger files are kept as run evidence under per-stage filenames and never deleted. `harness/github_issues.py --self-test` is hermetic and does not access credentials or the network.

The helper is the only pipeline boundary to GitHub. It reads the credential through `git credential fill` in a subprocess and keeps it in memory. Stages never run `git credential fill`, authenticated `curl`, or `gh`; they never print, log, or pass the credential. Helper rejection or failure blocks the stage.

## Run state

Each run dir holds `<step>-task-r<N>.md` prompts with matching `<step>-task-r<N>.log` run logs, `<step>-resume-r<N>.md` resume prompts, `resume.json`, `ledger.json`, `run.json`, `reservation.json`, `publication.json`, and the step artifacts (`findings.json`, `findings.original.json`). `resume.json` (outputs, visits, harness use, transcript, events, current step) is saved before every invocation and after every routing decision; it is deleted on a clean finish but kept after Ctrl-C, step failure, or a blocked ending so the same command resumes. A finished non-blocked run refuses to rerun (use `--fresh`); a blocked run drops its stale `run.json` marker and resumes. `--from-step S` resumes at S after proving every dominator predecessor of S has a ledger entry, and inherits the previous step from the last event that routed into S.

`ledger.json` records per-step completion proofs (signal, harness, visits, output hash, artifact hashes, git HEAD). On resume every entry is re-proven: outputs and artifacts must hash identically (files a later step intentionally rewrites via a snapshot `from` are exempt), and later steps moving git HEAD fail the check. The resumed current step is exempt from the output pin since its saved output is the interrupted attempt.

## Sync gate (fail-closed)

Both checkouts must not run on a stale or diverged base. `harness/gitsync.py`
owns this; the runner calls it and the finalize stage calls it directly.

## Shared phase reservations

A live runner invocation must hold the exact phase on the private coordination
board before it invokes a harness. The board is `coordination/state.json` in
the nested private repository on the configured branch (currently `master`).
The server driver uses `next_phase.py --server`, which returns `RESERVED` only
after a normal fast-forward push succeeds. A local runner claims the operator's
exact phase directly. `WAIT_FOR_CLAIM` means another machine owns the lowest
unfinished phase; the runner does not invoke a harness or select a later phase.
A future local reservation therefore does not move the server past unfinished
lower phases.

The reservation record contains `machine_id`, `reservation_id`, `generation`,
timestamps, `run_id`, and base revisions. Every renewal, resume, completion,
publication, and takeover checks all three ownership fields. The selected
policy has no automatic expiry. Interrupted, blocked, and rejected work keeps
its claim; an operator must explicitly use `phase_reservations.py takeover`
with the old reservation ID and generation plus `--confirm` after confirming
that the old owner is gone. The old token then fails renew, resume, completion,
and publication. A takeover retry with the old expected token is rejected
instead of fencing the replacement owner.

Run-state cleanup and final publication are phase-scoped. Finalize uses:

```bash
python3 private/clio-private/harness/gitsync.py --root . --mode publish --phase <N>
```

That command rechecks the claim, takes the short shared publication lock,
commits only `runs/phase-<N>` leftovers, syncs both checkouts, and performs
normal pushes. The helper writes and pushes `runs/phase-<N>/publication.json`; the
runner requires that receipt before it changes the shared record to
`completed`. It never force-pushes, rebases,
resets, stashes, or hides a conflict. A publication lock left by a crashed
process is not taken over
implicitly; inspect the state and use the explicit
`phase_reservations.py release-publication --confirm` command with the recorded
triple.

- **Before a fresh start** the runner syncs the public root and nested
  `private/clio-private` (`gitsync.sync_all(repo, "start")`). It fetches each
  repo from its own upstream, fast-forwards a strictly-behind branch with
  `git merge --ff-only`, and merges a diverged branch with a plain merge
  commit that keeps every local commit and accepts the remote changes.
  Giving up is the last resort: only a real merge conflict, a staged change,
  a detached HEAD, or a missing upstream stops the run with exit 2 (config
  error) and the driver halts. It never rebases, force-pushes, resets,
  stashes, or discards local work, and never runs `git pull` (the public repo
  sets `pull.rebase = true`, which would rewrite history). Local commits
  ahead of the remote do not block a start; the remote has nothing new.
- **A fresh start then cleans up only its phase's run state.** The runner
  commits and pushes the private repo's `runs/phase-<N>` leftovers, so another
  phase's partial records are never swept into this phase. Any staged path
  outside that phase still stops the run for operator review.
- **Resume is deliberately not synced.** A resume must keep the history its
  ledger already attests to (`git HEAD` per step), so a sync that moved HEAD
  would invalidate the completion proofs.
- **Before finalize** the finalize agent commits the phase's product work and
  runs `gitsync.py --root . --mode publish --phase <N>`. The helper verifies
  the phase's three-part fence, takes the short publication lock, commits only
  the current phase's run leftovers, fetches both checkouts, and confirms each
  normal push will fast-forward. A genuine conflict is left in place (not
  aborted): the agent resolves the named files, `git add`s them, completes the
  merge, and reruns the helper. If it cannot resolve them confidently, the run
  blocks before anything is pushed.
- **The private checkout is normally dirty after a phase**: the runner writes
  `ledger.json` and `run.json` after finalize's commit. `start` mode treats
  that as expected — when local HEAD already equals the remote it is a no-op,
  and a fast-forward or merge preserves dirty artifacts it does not touch,
  refusing only overlapping ones. It never requires a clean working tree,
  only a clean index.
- **Every sync attempt is recorded**: the runner writes `sync-before-start.json`,
  `sync-before-start-clean.json`, and `sync-after-completion.json` beside the
  run state (git-ignored evidence), and a merge's own commit is durable in git
  history.
- **Cross-checkout safety**: effective public/private fetch and push destinations are compared, including `pushurl`; both are refused if they overlap, so private content cannot cross into the public checkout.

Standalone check (stubbed remotes, no repo state touched); it also runs inside
`runner.py --self-test`:

```bash
python3 private/clio-private/harness/gitsync.py --self-test
```

## Verify

`--dry-run`, `--self-test`, and `--fuzz` create nothing in the repo. `--self-test` checks harness binaries and model slugs statically (plus signal parsing, the opencode TUI command shape, harness display-name coverage, alias expansion, the idle reminder's schedule, signal safety, pty delivery, prompt-tail skipping, operator-typing suppression, the swallowed-Enter retry, and rotation persistence with a stub harness in a temp dir). If the model-catalog command itself is unavailable, those checks are reported as skipped rather than falsely failed; resolve that environment exception before deployment. `--fuzz` asserts router properties over random graphs: terminal states are terminal, every routed edge matches the taken signal, exhaustion respects `max_rounds`, and consecutive events chain step-to-step.

Manual idle-reminder check (needs a terminal, not part of the automated gate): run a step with a stub harness that writes its run log and then sleeps without a signal, wait for the quiet interval, and confirm the reminder appears in the harness input and that the run log stays signal-free. `reminders.log` in the run dir records each reminder; `runner: attach mode: pty (console capture on)` on stderr confirms the pty path was chosen. On a real idle `opencode` session, confirm the submitted reminder is accepted (issue #20529 can swallow it; the stderr recovery line and `--mark-done` remain the fallback).

## Worker contract (birth-die)

Stage files stay lean orchestrators; execution detail lives in `harness/workers/*.md`, which the runner never loads. Rules: stages reference workers by exact relative path; every referenced file must exist; every worker defines its per-spawn slots under `## You own` and ends with `## Report back`; workers never signal, touch the index, run full gates, or spawn subworkers (depth cap is main -> worker). Static check (dry-run does not cover workers/): `python3 private/clio-private/harness/check-workers.py`. Run it after any stage/worker edit.

Baseline 2026-09-23 (dry-run, phase 100060): developer 7624 B, adversary 13970 B, remediator 13469 B, approver 4798 B, finalize 5399 B. Re-capture after stage edits when claiming context savings.

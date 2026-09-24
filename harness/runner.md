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
python3 private/clio-private/harness/runner.py --pipeline private/clio-private/harness/pipelines/default.yaml --input phase_number=100060 --input phase_file=private/clio-private/roadmap/phase-100060.md --audit-ledger
python3 private/clio-private/harness/runner.py --pipeline private/clio-private/harness/pipelines/default.yaml --input phase_number=100060 --input phase_file=private/clio-private/roadmap/phase-100060.md --migrate-ledger
python3 private/clio-private/harness/check-retry-authority.py
python3 private/clio-private/harness/check-cmd-harness.py
python3 private/clio-private/harness/check-harness-availability.py
python3 private/clio-private/harness/runner.py --fuzz 50
python3 private/clio-private/harness/runner.py --autoexit-test
```

`--dry-run` validates everything and prints rendered-prompt sizes without invoking any harness (`--show-prompts` also prints full prompts). `--self-test` runs static harness checks with no inference spend (`--live` adds one-word inference probes, which spend). `--mark-done STEP SIGNAL` records STEP as finished with SIGNAL (for work that is done but whose run log never got the bare signal line) and advances `resume.json` to the routed target without invoking any harness; verify the work first, then `--resume` continues. `--fuzz N` runs N randomized router property trials in temp dirs. `--autoexit-test` runs scripted fake-harness checks of the auto-exit logic. `--fresh` archives the existing run dir to `<run_dir>.prev-<timestamp>` and starts over. `--reset-rotation` deletes the pipeline's rotation file and exits. `--audit-ledger` reports ledger authority gaps without changing files; `--migrate-ledger` backfills deterministic task pointers and writes `migration-report.json`, leaving ambiguous steps for `--mark-done`. `check-retry-authority.py` is the hermetic retry acceptance check (missing-signal and interrupt scenarios in temp dirs, no repo state). `check-cmd-harness.py` is the hermetic Command Code acceptance check: a stubbed `cmd` proves the launch shape, the pointer handoff, the nonce round-trip, the pre-session rejection of a bad model, the no-rotation-on-failure retry, and the `--mark-done`-only advance, with no inference spend and no repo state. `check-harness-availability.py` is the hermetic availability acceptance check: stub harnesses on a fake PATH (HOME and PATH both point at a temp root, so no real CLI is reachable) prove skip-then-use-next, the fail-closed halt when none remain, and that a `cmd` probe rejection stays a config error, all with no inference spend and no repo state. `--pipeline` is always required. Run from the repo root: the repo root is the process working directory and `run_dir` resolves against it.

Exit codes: 0 completed, 1 terminal non-complete (rejected/blocked), 2 config error (machine-readable JSON on stdout in all cases), 130 operator Ctrl-C.

Parked phase numbers are `>= 900000`. They remain in the roadmap for planning, but `next_phase.py` never selects them and `runner.py` rejects them with a config error instead of launching a run. See `phase_policy.py` for the shared floor.

## Harness identifiers

Each stage file declares `harness:` as one identifier or a list of them. Format: `<CLI>:<Provider>/<Model>[@<Effort>]`, where provider and effort are optional. Examples: `opencode:together/glm-5.3-flash@high`, `opencode:go/deepseek-v4.1-flash@high`, `agy:gemini-3.8-flash-high`, `opencode:openrouter/deepseek-v4.1-flash@max`.

Known CLIs: `opencode`, `agy`, `cursor`, `hermes`, `cmd` (Command Code). A present but unknown `@effort` is a config error; known efforts are none, minimal, low, medium, high, xhigh, max, ultra. Full (unaliased) identifiers work identically: anything not in the alias tables resolves to itself, so both styles can be mixed.

Provider aliases (opencode CLI only): `go` always means the installed `opencode-go` provider, `together` always means `togetherai`. Model aliases are keyed by resolved provider, because each registry names the same model its own way: on `togetherai`, `glm-5.3-flash` expands to `zai-org/GLM-5.3-Flash` and `deepseek-v4.1-flash` expands to `deepseek-ai/DeepSeek-V4.1-Flash`; on `openrouter`, `deepseek-v4.1-flash` expands to `deepseek/deepseek-v4.1-flash`; on `opencode-go` the bare slugs are already full. Unmapped models pass through untouched, and aliases apply to the opencode CLI only.

How each CLI is invoked (all attached in the foreground with inherited stdio; the harness receives a 2-line pointer to its task file, never prompt text): `agy --dangerously-skip-permissions --model <model> [--effort <effort>] -i <pointer>`; `opencode run --auto [-m <provider/model[#variant]>] <pointer>` (v2 headless; output streams to the pane, which the driver pipe-panes into the session log); `agent [--model <model>] <pointer>` for cursor; `hermes [--usage-file <file>] chat --query-file <taskfile> [--provider <p> -m <m>] [--reasoning <effort>]` for hermes (usage files only for hermes); `cmd --trust --yolo --skip-onboarding -m <model> [--effort <effort>] <pointer>` for cmd (interactive, permissions auto-approved, pointer last as the initial message). The runner polls the step's run log and closes the session about 15 s after the final signal lands. A nonzero harness exit fails the step only when the run log carries no valid final signal; a missing or empty log always fails.

Command Code entries (`cmd`) name native catalog models only, spelled as `cmd --list-models` lists them (matched case-insensitively, so the catalog's mixed-case spelling also works), optionally with an `@effort` that model supports. Opencode's provider and model aliases never apply, and a BYOK custom provider id must not appear in a stage file (custom providers stay exclusive to opencode). Command Code accepts `low`, `medium`, `high`, `xhigh`, and `max`, but only the subset each model declares, so `@max` is not automatically valid everywhere. `--self-test` reads `cmd --list-models` statically and checks each declared model and effort with a local-only probe that sends nothing, starts no session, and spends nothing; the same probe runs before each cmd invocation, so an unknown model or an unsupported effort fails as a config error with the CLI's own reason before the session starts. The interactive form requires a terminal (`Interactive mode requires a TTY terminal` otherwise), like the other TUI harnesses, so a cmd step must run attached. A catalog id containing a colon (`inclusionai/ling-3.0-flash-sante:free`) cannot be written as a harness id and must not be used.

A list of identifiers means round-robin: each invocation of that step uses the next entry, wrapping around. Repeating an identifier gives it proportional weight; interleave repeated entries with other identifiers when the desired ratio permits it. Counters persist across runs in `private/clio-private/runs/.harness-rotation-<pipeline>-<hash>.json` (one file per pipeline file, keyed by pipeline path), so consecutive runs keep alternating. A slot is consumed only after the step emits an accepted signal and all completion gates pass. A missing signal, blocked result, missing required artifact, or interrupted attempt leaves the slot unchanged, so its retry uses the same harness.

Before invoking, the runner checks availability and skips an entry whose CLI binary is not on PATH (`opencode`, `agy`, `agent` for cursor, `hermes`, `cmd`). It walks the list from the rotation offset, wrapping, and uses the first installed harness; an installed harness is never skipped because another entry is missing. Availability is binary presence only: the model and effort are still checked by `cmd`'s own pre-session probe (self-test and invoke-time), and a `cmd` model or effort rejection stays a hard config error, not a skip. A skip writes no task or log file and invokes nothing; the step banner, the event, and `--dry-run` name the skipped ids and their missing binaries, and the accepted invocation records the used harness in `ledger.json` and advances the counter past the skips so a later run does not retry a known-missing head. When every entry for the step is missing its binary the run halts then and there as a config error (exit 2) whose JSON names the step and every missing binary; nothing is invoked, no ledger entry or rotation advance is written, and `resume.json` stays on the step so installing a harness and resuming retries it.

Rotation state is fail-closed: a missing file starts at zero, but a corrupt file, negative count, or unwritable file fails the run with an explicit repair (`--reset-rotation` after confirming no resumable run depends on it) instead of silently resetting. `--fresh` does not reset rotation.

Current step selections (kept in sync with the operator-owned `preference.md`, which is the source of truth for these lists; edit the stage frontmatter to match it, never the reverse): developer rotates `opencode:go/deepseek-v4.1-flash@max`, `agy:gemini-3.8-flash-high`, and `opencode:together/glm-5.3-flash@high`; adversary rotates `opencode:go/space-bunny-free@max`, `agy:gemini-3.8-flash-high`, `opencode:go/space-bunny-free@max`, and `opencode:openrouter/deepseek-v4.1-flash@max`; remediator rotates `opencode:together/glm-5.3-flash@high` and `cmd:deepseek/deepseek-v4-flash@max`; approver rotates `opencode:go/space-bunny-free@max`, `agy:gemini-3.8-flash-high`, `opencode:go/space-bunny-free@max`, and `cmd:deepseek/deepseek-v4.1-flash@max`; finalize rotates `opencode:together/glm-5.3-flash@high` and `cmd:deepseek/deepseek-v4-flash@max`.

Each stage file also declares `harness_names:` mapping every harness id to its display name, which is what `{{harness}}` renders to in prompts and what lands in Attribution rows and the ledger. Anything unmapped falls back to the raw id.

## Attempt authority

The run directory keeps one task and log file per attempt. `ledger.json` is the single authoritative completion record: its per-step `task_file`, `task_sha256`, `harness`, signal, `via`/`routed_to`, and stage fingerprint identify the exact attempt that completed, while `superseded_task_files` lists older task files without deleting them. Downstream `{task: step}` context reads the stored task snapshot directly (with the stale per-invocation nonce stripped) and verifies its hash; it never re-renders the current stage template, so a later stage edit cannot alter history. Its authority notice tells reviewers to ignore model names and instructions from every other attempt; a model-name difference is never a finding. If a referenced step has output but its ledger entry is missing, malformed, tampered, or points outside the run directory, live prompt rebuilding fails closed instead of guessing from the first rotation slot.

Completions are journaled: every accepted signal first writes `.pending-commit.json` (versioned), then applies ledger, rotation, and resume idempotently, then clears the pending file. A crash at any boundary replays the pending commit without re-invoking the harness. `--mark-done` uses the same journal and ignores `*.tui.log` mirrors when selecting the run log. Legacy ledgers without task pointers are migrated deterministically by visits (or by a single candidate) via `--migrate-ledger`; ambiguous histories are reported in `migration-report.json` for `--mark-done` recovery, never guessed.

## Pipeline files

`pipelines/default.yaml` holds the whole workflow: `version` (must be 1), `run_dir` (a format template, currently `private/clio-private/runs/phase-{phase:06d}`), `inputs` (defaults or `{required: true}` markers; `--input k=v` overrides, `phase_number` and `max_remedy_rounds` parse as ints), `start`, `ends`, and `steps`. Each step names a `stage` file, a `record_as` label, `bindings`, and exactly one of `when` (signal-to-target routing map) or `end` (a terminal state from `ends`). Optional keys: `require_file`, `skip_when_empty`, `snapshot` (exactly `from`/`to`), `max_rounds` with `on_exhausted`.

Binding values are format strings over inputs plus run builtins (`phase`, `run_id`, `run_dir`, `agent`, `round`, `rounds`), `{output: <step>}` (that step's last output text), `{task: <step>}` (that step's rendered stage text), `{join: [...]}` with optional `sep`, or `{prev_output: true}` (the output of whatever step routed here). `{{harness}}` is runner-provided per invocation and must be neither declared in the stage's `placeholders` nor bound in the pipeline.

Validation is strict: unknown keys; start, edge targets, `skip_when_empty`/`on_exhausted`, and binding source steps that resolve nowhere; non-positive `max_rounds`; a step with neither or both of `when`/`end`; end states outside `ends`; unbound or over-bound placeholders; body tokens outside placeholders plus `{{harness}}`; missing stage files; unknown harness CLIs or malformed harness ids.

## Signals and routing

Signal matching is a prefix match scanned bottom-up over the last 10 non-empty run-log lines: the line equals a `when` key or starts with the key plus a space or colon. One leading ISO-8601 timestamp plus any `| ... |` journal prefixes are stripped before matching, and a `{"signal": ..., "nonce": ...}` JSON line counts the same as its bare form. Every invocation carries a fresh random nonce (appended to the task file); non-`*_BLOCKED*` signal lines must carry it as a separate token, so a mid-run echo of the bare signal word neither closes the session nor routes the pipeline. A signal printed only in chat never counts toward the log match, but under a terminal the runner also captures the harness console to `<step>-task-r<N>.tui.log` and a console-only signal still routes (marked `signal_via: mirror`). If the log stops growing with no signal for 5 minutes the runner prints the exact `printf ... >> <log>` recovery line to stderr and keeps waiting; on the pty path it also types a short reminder into the harness's own input and submits it (Enter), so an agent that finished but forgot the log line can be told to write it. The reminder targets only harnesses that run with permissions auto-approved (`opencode`, `agy`, `cmd`) and is skipped when the console tail looks like a confirmation prompt, so it is never typed into a dialog. The text is signal-safe (no nonce, no token ending in BLOCKED), rate-limited (first after 5 minutes, each later one twice as far out, at most three per invocation, skipped once the operator has typed at all, and one extra Enter if the first appears swallowed), audited to a run-level `reminders.log`, and never written to the run log; it can never complete the step. Any signal whose first token ends in `BLOCKED` ends the run as blocked from any step. End steps (no `when`) accept a `*_DONE` / `*_APPROVED` / `*_REJECTED`-style first token the same way. A matched edge into an already-visited target caps at the current step's `max_rounds` and then ends with `on_exhausted`.

### Idle-reminder capability by harness

| CLI | Permissions | Reminder | Why |
|-----|-------------|----------|-----|
| `opencode` | `--auto` | on | Full TUI with an input box; tools run in separate processes, so injected stdin reaches the TUI, not a running tool. |
| `agy` | `--dangerously-skip-permissions` | on | Interactive input with permissions auto-approved. |
| `cmd` | `--yolo` | on | Interactive input with permissions auto-approved, so no approval dialog can be answered by the reminder. |
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

`ledger.json` records per-step completion proofs (authoritative flag, signal, harness, visits, output hash, task snapshot hash, stage fingerprint, via/routed_to, artifact hashes, git HEAD, authoritative `task_file`, and superseded task-file paths). On resume every entry is re-proven: outputs, task snapshots, artifacts, and the authoritative task file must remain present and unchanged where applicable (files a later step intentionally rewrites via a snapshot `from` are exempt), and later steps moving git HEAD fail the check. The resumed current step is exempt from the output pin since its saved output is the interrupted attempt, unless its ledger entry already proves completion with a matching output hash (crash after commit replays advancement instead of re-running).

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

`--dry-run`, `--self-test`, and `--fuzz` create nothing in the repo. `--self-test` checks harness binaries and model slugs statically (plus signal parsing, the opencode TUI command shape, the Command Code launch shape, catalog parsing, and the live rejection of an unknown model and an unsupported effort, harness display-name coverage, alias expansion and its opencode-only scoping, the harness-availability skip and wrap-around selection with stub binaries on a fake HOME/PATH, the idle reminder's schedule, signal safety, pty delivery, prompt-tail skipping, operator-typing suppression, the swallowed-Enter retry, rotation persistence with fail-closed corrupt/negative/write-failure cases, crash-journal recovery at ledger/rotation/resume boundaries, task snapshot and stage-mutation integrity, legacy migration, mark-done mirror filtering, and adversarial stale-model fixtures with a stub harness in a temp dir). If a model-catalog command itself is unavailable, those checks are reported as skipped rather than falsely failed; resolve that environment exception before deployment. `--fuzz` asserts router properties over random graphs: terminal states are terminal, every routed edge matches the taken signal, exhaustion respects `max_rounds`, and consecutive events chain step-to-step.

The Command Code catalog checks are spend-free: `cmd --list-models` supplies the model list, and a `cmd -p` probe with local-only forced resolves one `(model, effort)` pair and is then refused at the transport, so nothing leaves the machine and no session starts. That probe is also the pre-invocation gate, and it fails open: if the CLI's output is unrecognisable (a reworded refusal, a timeout), the step proceeds and the CLI's own pre-inference rejection remains the backstop.

Manual idle-reminder check (needs a terminal, not part of the automated gate): run a step with a stub harness that writes its run log and then sleeps without a signal, wait for the quiet interval, and confirm the reminder appears in the harness input and that the run log stays signal-free. `reminders.log` in the run dir records each reminder; `runner: attach mode: pty (console capture on)` on stderr confirms the pty path was chosen. On a real idle `opencode` session, confirm the submitted reminder is accepted (issue #20529 can swallow it; the stderr recovery line and `--mark-done` remain the fallback).

Manual retry-authority check (hermetic, no inference spend, no repo state): `python3 private/clio-private/harness/check-retry-authority.py` runs missing-signal and interrupt scenarios in temp dirs and asserts same-model retry, ledger task pointer with hash, and reviewer prompt with authority notice. The automated self-test pins the same sequences plus crash-journal, tamper, stage-mutation, migration, mirror-filtering, rotation-failure, and adversarial-fixture cases in temporary run directories.

Command Code harness check (hermetic, no inference spend, no repo state): `python3 private/clio-private/harness/check-cmd-harness.py` puts a stubbed `cmd` on PATH and drives a two-step `cmd` pipeline through `runner.invoke()`, asserting the launch shape (`--trust --yolo --skip-onboarding`, pointer last, never `-p`), the pointer handoff, the per-invocation nonce round-trip into the ledger signal, a pre-session config-error rejection of a model the CLI refuses, a missing-signal retry that reuses the same slot without consuming rotation, and a finished-but-unsignalled attempt that advances only through `--mark-done`. It exercises the plain attach path; the pty path is pinned by `--self-test`. On a real terminal, the equivalent manual check is to run one `cmd` stage, confirm `runner: attach mode: pty (console capture on)` on stderr, verify the Command Code session was seeded with the task pointer and closed ~15 s after the signal, and confirm the run log carries the nonce-bearing signal.

Harness-availability check (hermetic, no inference spend, no repo state): `python3 private/clio-private/harness/check-harness-availability.py` writes stub harness binaries into a temp PATH and points HOME at the same temp root, so no real CLI is reachable, then drives `runner.invoke()`. It asserts skip-then-use-next (the missing head is never invoked, the next installed harness runs, the banner and event record the skip, and the accepted run consumes past it), halt-when-none (a config error names the step and every missing binary, invokes nothing, and writes no task, log, ledger, resume, or rotation file), and that an available `cmd` whose model the CLI rejects stays a hard config error rather than a skip.

## Worker contract (birth-die)

Stage files stay lean orchestrators; execution detail lives in `harness/workers/*.md`, which the runner never loads. Rules: stages reference workers by exact relative path; every referenced file must exist; every worker defines its per-spawn slots under `## You own` and ends with `## Report back`; workers never signal, touch the index, run full gates, or spawn subworkers (depth cap is main -> worker). Static check (dry-run does not cover workers/): `python3 private/clio-private/harness/check-workers.py`. Run it after any stage/worker edit.

Baseline 2026-09-24 (dry-run, phase 100060): developer 11982 B, adversary 24349 B, remediator 21900 B, approver 10055 B, finalize 10921 B. Re-capture after stage edits when claiming context savings. The runtime attempt-authority notice adds a fixed prompt section, so current dry-run sizes are authoritative.

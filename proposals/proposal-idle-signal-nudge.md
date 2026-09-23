# Proposal: remind idle agents to write their exit signal

Status: implemented (2026-09-23). Scope: harness only. No stage or pipeline changes.

## Problem

Agents sometimes finish the work but never write the final signal line to the run log. The runner then waits with no signal. The stuck finalizer on the server is one instance. Prompt rules alone cannot fix this because model obedience is not guaranteed.

## Proposal

Detect a quiet stage with no completion signal and deliver a short reminder where the agent reads input: if done, write the signal now, and if still working, ignore this and carry on. Improve or replace this proposal if your local and external validation finds a safer or more reliable fix.

## Hypothesis (non-binding)

When a stage has gone quiet for a long time with no completion signal, deliver a short reminder where the agent can see it, telling it to write the signal if done and to ignore the reminder if still working.

This document states the problem and the safety properties only. It deliberately prescribes no implementation. The implementer owns the design after validation below.

## What the implementer must validate locally

Do not trust this proposal on where things live. Read the code first and confirm or correct each point.

- Find how the runner currently waits for the signal, what counts as quiet, and where the existing idle warning goes. Confirm who can see that warning and who cannot.
- Find how console output is captured, if at all, and under what conditions the runner falls back to a path with no capture. Confirm what the server normally uses under tmux versus a local run without a terminal.
- Find how a signal is recognised, including any per-run token and any console fallback. Confirm what text could be mistaken for a signal so the reminder never triggers a false completion.
- Find how a finished step is recorded and resumed, including any operator recovery command. Confirm what the runner must never fabricate on the agent's behalf.
- Read the stage files and pipeline docs for the signal contract before changing anything.

## What the implementer must validate externally

Search first. Do not invent terminal handling.

- Search for established patterns for sending follow-up input to an interactive terminal child (pty input versus display-only output), including failure modes when the operator is typing at the same time.
- Search for how common coding harnesses accept mid-run follow-up prompts, and whether a reminder needs an explicit submit keystroke or arrives as plain text.
- Look for better-established alternatives to an in-TUI reminder (for example watchdog sidecars, harness-native messaging, or terminal multiplexer commands) and compare them honestly against the reminder idea on reliability, CLI generality, and risk of corrupting the session.

## Safety properties

- The reminder must never look like a completion signal and must never complete the step by itself.
- The reminder must be rate-limited so it cannot spam the agent context or fight operator input.
- A failed reminder must never crash or stall the run. The existing operator-visible warning stays as the fallback.
- Every reminder is reported to the operator log so nudges are auditable.
- Normal work is unaffected. A busy agent that is still producing output or log lines is left alone.

## Acceptance

- Add an automated check that a quiet harness with no signal gets reminded, and that the reminder text itself is never recognised as a signal.
- Add a manual check with a stub harness: reminder appears where the agent reads input, and a later real signal still routes normally.
- State what was verified locally and externally, and list anything that could not be verified.

## Open questions

- What quiet interval should trigger the first reminder, and should repeats back off?
- How many reminders per invocation before staying silent except to the operator?

---

# Implementation record

## Local validation (confirmed against the code)

All file references are `private/clio-private/harness/runner.py` unless stated. Line numbers are from the revision read during validation; the post-audit changes are listed at the end.

- **How the runner waits and what counts as quiet.** `run_attached` (line 1353) runs the harness attached. Under a terminal it takes the pty path `_run_attached_pty` (1119) → `_pty_forward` (1151); without a terminal it takes `_run_attached_plain` (1387) → `_poll_loop` (1402). Both poll the run log; the pty path additionally captures and scans the harness console. "Quiet" is tracked by `last_change`, reset whenever either the run log size or the console-capture size changes (`key = (log_size, tui_size)`); the threshold is `IDLE_NUDGE_S = 300` (82).
- **Where the existing idle warning goes, and who sees it.** It is a `print(..., file=sys.stderr)` at 1278-1285 (pty) and 1435-1443 (plain). Only the operator sees it: under tmux the driver's `pipe-pane` copies the pane to `session-<N>.log`, but the harness TUI never receives it. It is display-only output, not input to the agent. This is the exact gap the proposal describes.
- **Console capture and the no-capture fallback.** The pty path writes all child output to `<step>-task-r<N>.tui.log` (1372) and scans its tail as a second signal channel (mirror). The plain path has no capture (`tui_log: None`, 1398). On the server the driver launches the runner inside a tmux pane (`phase-driver.sh`, `tmux new-session -d`), so `sys.stdin.isatty()` and `sys.stdout.isatty()` are true and the **pty path is what normally runs**. A local run without a terminal (piped, or cron without a pane) takes the plain path, where no agent input channel exists.
- **Signal recognition and false positives.** `find_signal` (944) scans the last 10 non-empty lines bottom-up. `clean_line` strips one ISO-8601 timestamp, unfolds a `{"signal": ..., "nonce": ...}` object, and strips leading `| ... |` journal prefixes. Every non-`*_BLOCKED*` match must carry the per-invocation nonce as a separate token; `*_BLOCKED*` lines are exempt from the nonce. End steps (no `when`) accept a first token ending in `_DONE`/`_APPROVED`/`_REJECTED`, still nonce-gated. The only text that can be mistaken for a signal without the nonce is a first token ending in `BLOCKED`; the reminder therefore contains no nonce and no token ending in `BLOCKED` (also no signal word), and a self-test asserts this.
- **Recording, resume, and what must never be fabricated.** `note_completion` (653) writes the per-step proof to `ledger.json`. `mark_done` (717) is the operator recovery: it appends the bare signal to the run log and advances `resume.json` without invoking a harness. The runner must never write a signal on the agent's behalf; the reminder writes only to the harness input (the pty master), never to the run log, and cannot route.
- **Pre-existing issue found while reading (reported, not fixed).** `mark_done` collects logs with `glob(f"{step}-task-r*.log")` (719); that also matches the console sidecar `<step>-task-r<N>.tui.log`, and `sorted(...)[-1]` then selects the `.tui.log` rather than the run log. The reminder audit is a run-level `reminders.log` (not `*.log` beside the step) so it does not join that glob. Fixing the `.tui.log` match is out of scope for this harness-only proposal.

## External validation (what established practice says)

- **Input to an interactive child is a pty concern, not display output.** Typed input to a pty child is delivered by writing to the pty master; the terminal driver echoes it. Writing to stdout/display is one-way and the child never sees it. Sources: "Detecting when a child process is waiting for input" (Stack Overflow) and the ptyprocess documentation. This confirms the reminder must go to the master fd the runner already owns.
- **tmux `send-keys` is the common way to drive TUI agents, but it is fire-and-forget.** It has no receipt: keys are typed, not acknowledged, and land somewhere unexpected if the pane is busy. The runner is already inside the pty and forwards operator keystrokes to the master, so writing the master is the same mechanism without the tmux dependency and it also works for local runs outside tmux. Source: "tmux: orchestrating agents with send-keys and capture-pane" (mager.co, 2026-08-23).
- **A submitted follow-up can be swallowed, so retries and a fallback are needed.** OpenCode issue #20529, "TUI follow-up prompt is not submitted after agent becomes idle until CLI restart" (closed as not planned), is exactly this failure mode. The `opencode-queue` plugin shows queued follow-ups are a plugin concern and are hidden from a busy agent; OpenCode does not expose native queue hooks. Claude Code queues text typed while busy and runs it when the session pauses or finishes. Conclusion: the reminder is best-effort, needs bounded repeats, and the stderr warning plus `--mark-done` stay as the fallback.
- **Alternatives considered.**
  - *Watchdog sidecar that writes the signal.* Rejected: it fabricates a completion, violating the core safety property. `--mark-done` is the explicit, operator-owned version of that.
  - *`tmux send-keys` from a sidecar.* Rejected: only works under tmux, adds a dependency and a session name the runner does not need, and has the same no-receipt risk. No advantage over the master write we already perform.
  - *Harness-native messaging (for example an OpenCode plugin/API).* Not adopted for the default path: OpenCode-only, which breaks the runner's CLI generality. The pty write stays the only delivery, but `_deliver_reminder` is a single seam a harness-native sender could replace while keeping the same safety rules.

## Design (chosen)

Deliver the reminder where the agent reads input, on the pty path only:

- **Channel.** Type `IDLE_REMIND_TEXT` plus a carriage return to the pty master (the same channel as the operator's keystrokes and the existing autosubmit Enter). `_deliver_reminder` is the single seam a harness-native sender could replace, with the pty write as the fallback.
- **Scope.** The reminder is enabled only for harnesses that auto-approve permissions (`REMINDER_CLIS = {"opencode", "agy"}`), so it is never typed into a confirmation dialog. A console tail that looks like a prompt (`_looks_like_prompt`) also skips it.
- **Schedule.** `reminder_due`: first reminder after `IDLE_REMIND_S = 300` seconds of quiet, each later one `IDLE_REMIND_BACKOFF = 2` times further out (300 s, 600 s, 1200 s), capped at `IDLE_REMIND_MAX = 3` per invocation, only once the agent has started (run log non-empty), and skipped once the operator has typed at all (an attended session is handled by the human). Activity on either channel pushes the next reminder out; it does not reset the budget, so the total per invocation stays bounded.
- **Swallowed Enter.** If the first Enter appears swallowed, one extra Enter is sent after `IDLE_REMIND_RESUBMIT_S = 2` s, matching the tolerance the auto-submit already relies on.
- **Signal-safe text.** `IDLE_REMIND_TEXT` carries no nonce, no signal word, and no token ending in `BLOCKED`, so the console-mirror scan can never treat it as a completion.
- **Audit.** `_report_reminder` prints an operator line to stderr and appends the same line to a run-level `reminders.log`. The run log is never touched.
- **Best-effort.** The whole reminder block is wrapped in `try/except Exception`; a failed write disables further reminders for that run but never raises or stalls. The plain path keeps only the existing stderr warning, because there is no agent input channel there.

## How each safety property is met

- *Never looks like a signal, never completes the step.* Text is nonce-free and BLOCKED-free; the reminder writes only to the pty master, never to the run log, so it cannot route. Asserted by self-test.
- *Rate-limited, never fights operator input.* Cap of 3, doubling spacing, and reminders stop entirely once the operator has typed in this invocation. Asserted by self-test, including a pty test that injects an operator byte.
- *Never typed into a dialog.* Enabled only for auto-approving harnesses, and skipped when the console tail looks like a prompt. Asserted by self-test.
- *Failed reminder never crashes or stalls.* The whole reminder block is exception-guarded, and a pty failure after the child starts terminates it and fails the step instead of re-spawning the harness.
- *Every reminder is auditable.* Each one is printed to stderr and appended to the run-level `reminders.log`.
- *Normal work is unaffected.* Any growth on the run log or console pushes the next reminder out, so a busy agent is left alone.

## Verification

Local, on macOS, against `private/clio-private/harness/runner.py`:

- `python3 -m py_compile` on the runner: clean.
- `--self-test` with the default pipeline: all 15 reminder checks pass, including:
  - `reminder: reaches agent input on quiet pty` — a stub harness that goes quiet receives the reminder on its own stdin and the Enter is delivered.
  - `reminder: audited in a run-level sidecar, not the log` — `reminders.log` exists and the run log stays signal-free.
  - `reminder: text is never a signal` and `reminder: default text is never a signal` — `find_signal` returns None for both a `when` list and an end step, and no token ends in BLOCKED.
  - `reminder: a later real signal still routes` — after the reminder, a real nonce-bearing signal in the run log is accepted and the mirror stays empty.
  - `reminder: operator typing suppresses injection` — a byte on the operator's stdin stops the reminder (pty test).
  - `reminder: skipped on a confirmation prompt` — a `[y/N]` console tail stops the reminder (pty test).
  - `reminder: swallowed Enter is retried once` — text once, Enter twice (pty test).
  - `reminder: due after first interval`, `repeats back off`, `budget caps`, `not started stays silent`, `disabled for a prompting harness stays silent`, `any operator typing suppresses`, `prompt-like tail is skipped` — the schedule and gates.
- `--autoexit-test`: pass (all six cases), so the plain path and auto-exit are unchanged.
- `--fuzz 100`: pass, so routing is unchanged.

The three pre-existing `--self-test` failures on this host are `opencode ... model listed` slug checks; they are environmental (the local `opencode models` catalog does not list those slugs) and are unrelated to this change.

Not verified:

- Live server behaviour under tmux with the real harnesses (opencode/agy). The pty path is the same code path, but real TUI input handling, the OpenCode swallowed-Enter issue, and the actual stuck-finalizer case were not exercised end to end. The runner now logs `runner: attach mode: pty (console capture on)` at invocation start, which is the operational way to confirm the path on the server.
- A real interactive manual check with a human at the keyboard. The operator-suppression and prompt-skip cases are covered by automated pty tests, not by a live two-actor session.
- Any non-macOS host. The runner's pty code is platform-specific and was only exercised here.

## Post-audit fixes (adversarial review)

A skeptical self-review found nine issues. All were addressed:

1. *Keystroke injection could reach a modal prompt or a silent tool.* Fixed by enabling the reminder only for auto-approving harnesses (`opencode`, `agy`) and skipping prompt-like console tails (`_looks_like_prompt`).
2. *The 20 s operator-typing guard was a heuristic.* Replaced with a hard rule: any operator keystroke disables reminders for that invocation.
3. *Effectiveness on the real opencode harness was unverified.* Mitigated with one extra Enter when the first appears swallowed; live verification on the server is still outstanding.
4. *An exception in the reminder path could re-spawn the harness.* The reminder block is now fully exception-guarded, and `run_attached` falls back to a plain spawn only on `_PtyUnavailable` (before a child starts); a post-spawn failure terminates the child and fails the step.
5. *The acceptance's manual check was automated.* The behaviour is now covered by three pty tests, and a manual procedure is documented in `runner.md`; a live manual run is still outstanding.
6. *The tmux-pty claim was inferred.* The runner now logs the chosen attach mode at invocation start so it can be confirmed on the server.
7. *Only two of five stage files were read.* All five were reviewed; they share the same nonce-bearing signal contract with no TUI-specific assumptions that conflict with the reminder.
8. *The audit write caught only `OSError`.* Broadened to `Exception`.
9. *The per-step `.reminders` sidecar added run-dir noise.* Moved to one run-level `reminders.log`.

## Open questions (resolved)

- *Quiet interval and backoff.* 300 s to match the existing operator warning, then doubling (300/600/1200 s). Rationale: long enough not to interrupt a slow tool call, short enough to recover an idle agent before a human notices.
- *How many reminders per invocation.* Three. After that the runner stays silent toward the agent and only the stderr operator warning (every 300 s) remains, so a wedged agent cannot be spammed.

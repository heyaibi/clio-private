# Auto-exit for foreground harnesses

Status: implemented in `runner.py` (`run_attached`/`log_done`/`_terminate`).
Scripted checks: `--autoexit-test` (fake harness writes its signal then
sleeps; the runner closes it after the grace window; a no-signal nonzero
exit still fails the step). The opencode step now launches the full TUI;
its reasoning effort rides in as a per-agent variant via
`OPENCODE_CONFIG_CONTENT` (see `foreground.md`, "opencode variant gap").

Interactive sessions stay. The operator spectates (and may interject) in
their terminal; only the *closing* is automated: the runner ends the
harness session once the agent is demonstrably done. No harness-native
"exit after the initial prompt" flag exists that stays interactive
(agy exits on `/quit` or Ctrl-D x2; cursor, opencode, hermes interactive
modes just idle), so the runner ends the session itself.

## Mechanism

`invoke()` keeps spawning attached with inherited stdio, but replaces the
bare block-on-exit with a poll loop (~1s) over the step's run log
(`<step>-task-r<N>.log`):

1. The agent's final signal is matched bottom-up over the last 10
   non-empty lines of the run log (timestamp plus any `| ... |` journal
   prefixes stripped; a `{"signal", "nonce"}` JSON line counts the same).
   Non-`*_BLOCKED*` lines must carry the invocation's nonce. Done = a
   scanned line matches one of the step's `when` signals, or its first
   token ends in `BLOCKED`. Under a terminal the harness console is
   mirrored to `<step>-task-r<N>.tui.log` and scanned with the same
   predicate as a second channel.
2. The match must be stable across 2 consecutive polls (~2s) so a mid-run
   log entry cannot trigger it.
3. On done: grace window of **15 seconds** (lets the operator read the
   on-screen summary), then SIGINT; SIGTERM after ~10s more; SIGKILL
   after ~5s more. The signal is already durable in the log, so even a
   hard kill loses nothing. Exit code of the killed session is ignored.
4. Exit-code contract relaxes accordingly: nonzero exit is a step failure
   only when the run log carries no valid final-signal line. Missing or
   empty log stays a step failure.
5. Operator Ctrl-C mid-work still hits the foreground process group:
   child dies, runner exits 130 with `resume.json` kept; the same command
   resumes.
6. No signal and no log growth for 5 minutes prints the exact
   `printf '%s\n' <SIGNAL> >> <log>` recovery line to stderr and repeats
   until the signal lands: a forgotten log line stays visible instead of
   hanging silent. If the work is already done, `--mark-done STEP SIGNAL`
   records it and advances without invoking any harness.

`drive()` passes the step's expected signals (`when` keys) into
`invoke()`; the fuzz stub signature gains the parameter. End steps
(`finalize`) have no `when`, so their auto-exit relies on the
`*_BLOCKED` rule plus a `*_DONE`/`*_APPROVED`/`*_REJECTED`-style first
token, matching the stage signal convention.

## Grace window

15 s after the signal lands, the runner closes the session. Interactive
UIs can wipe scrollback on exit; anything not re-read in that window is
still in the run log and task files. The window is a constant in the
runner, not config.

## Docs

`instruction.md` + `foreground.md`: sessions close themselves ~15 s after
the final signal lands in the run log; quitting earlier is always fine;
Ctrl-C kills the step and rerunning the same command resumes.

## Verify

`--fuzz`, `--dry-run`, `--self-test`; scripted fake-harness checks of the
poll/kill logic (signal-bearing log then sleep = runner ends it; no
signal = step still fails); real TUI behavior confirmed on the next
foreground run.
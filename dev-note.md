# dev-note — running the phase pipeline unattended

Canonical layout: the pipeline lives in the nested private repo at
`private/clio-private/`, with harness code in `harness/` and run state
in `runs/`. Run every command below from the repo root.

## What runs
Every 10 minutes cron runs `private/clio-private/harness/phase-driver.sh`. It does nothing while a phase
is running or while the line is halted. Otherwise it starts the **lowest uncompleted
roadmap phase** in the tmux session `development`, where `private/clio-private/harness/runner.py`
drives developer → adversary → remediator ⇄ approver → finalize.
One phase at a time. A phase that ends blocked/rejected/crashed, or that is stopped
by a signal, writes a halt marker and stops the line until you clear it.

## Files
- `private/clio-private/harness/next_phase.py` — picks the next phase (done = `run.json: completed`, a
  checked "Required approval is obtained" box, or Complete in `private/clio-private/roadmap/index.md`).
- `private/clio-private/harness/phase-driver.sh` — guard + launcher + notifier + stop + self-test.
- `private/clio-private/runs/.driver/` — runtime state: `driver.log`, `halted`, `stalled`,
  `notify-broken`, `current`, `pid`, `driver.lock`, `session-<N>.log`.
- `private/clio-private/runs/.driver.env` — optional untracked overrides (see Config below).
- `private/clio-private/runs/phase-<N>/` — per-phase run state (`run.json`, logs, `findings.json`).

## Install (once, on the server)
crontab entry (absolute paths; cron has a minimal PATH). The log path's directory
already exists, so the redirect works on a fresh clone:
```
*/10 * * * * /path/to/clio/private/clio-private/harness/phase-driver.sh >> /path/to/clio/private/clio-private/runs/.driver-cron.log 2>&1
```
Requires: `tmux`, `flock`, `python3`, `curl` (for the optional heartbeat), and the
Hermes profile `not-james-gosling` with Discord configured. The harnesses also need
their own auth (opencode, agy, and git push for finalize).

## Watch
```
ssh <server>
tmux attach -t development          # detach with Ctrl-b then d
tmux capture-pane -pt development | tail -40   # read without attaching
tail -f private/clio-private/runs/.driver/driver.log
```

## Stop / resume
```
private/clio-private/harness/phase-driver.sh --stop      # writes the halt marker and sends Ctrl-C
```
or attach and press **Ctrl-C**. Both hit the session's signal trap, which writes the
halt marker and sends a "STOPPED" message. Then clear the marker to resume:
```
rm private/clio-private/runs/.driver/halted        # next tick resumes the same phase
```
**Do not use `tmux kill-session` to stop.** It destroys the session without signalling
the pane, leaving the run orphaned. The driver detects that on the next tick (live PID,
no session) and halts rather than start a duplicate — but it is the messy path.

## Halted (blocked / rejected / config error / stop)
The driver writes `private/clio-private/runs/.driver/halted` and stops. After fixing the cause:
```
rm private/clio-private/runs/.driver/halted        # next tick resumes the same phase
```
A **rejected** phase is terminal and cannot resume — rerun it manually with `--fresh`,
or reset its phase state, then clear the halt.

## Stalled (watchdog)
If a live session writes no output for `STALE_AFTER_SEC` (default 45 min), the driver
sends one "looks STALLED" message and writes `private/clio-private/runs/.driver/stalled`. It does not
kill the run (a slow step can be legitimate). Clear the marker once you have looked:
```
rm private/clio-private/runs/.driver/stalled
```

## Notifications (Discord #tech-team)
Start, end, halt, stop and stall messages go through the Hermes profile:
```
hermes -p not-james-gosling send --to discord:1546601332276727828 "[clio] test"
```
A failed send is retried once, then sent to `DISCORD_FALLBACK_CHANNEL` if set. If all
fail, `private/clio-private/runs/.driver/notify-broken` is written — check it if you stop seeing
messages.

**Notifications are best-effort and never block or halt the run.** Sends are bounded
by a timeout, run with stdin closed (a hung or interactive `hermes` cannot stall the
pipeline), and after a total failure the channel is marked unavailable for that
process so we stop retrying. A dead profile or dead Discord only costs you the
messages, never the work.

## Troubleshooting
- **A run dies within seconds:** read `private/clio-private/runs/.driver/session-<N>.log` (the pane
  capture — the traceback lands there). The driver auto-selects a `python3` that has
  PyYAML (runner.py needs it); `--check` shows which one.
- **Running the driver by hand seems to do nothing:** it now prints one line per
  decision (launched / skipped / halted); the rest goes to `private/clio-private/runs/.driver/driver.log`.
- **Run refused with "halted":** a prior run left `private/clio-private/runs/.driver/halted`; fix the
  cause and `rm` it.

## Heartbeat (optional dead-man's switch)
Set `HEARTBEAT_URL` (e.g. an ntfy.sh or healthchecks.io URL) and the driver pings it
after every tick. If the whole box or cron stops, the missing ping alerts you — the
one failure a halt message cannot catch.

## Config (`private/clio-private/runs/.driver.env`, untracked)
```
HERMES_PROFILE_NAME=not-james-gosling
DISCORD_CHANNEL=1546601332276727828
DISCORD_FALLBACK_CHANNEL=
HEARTBEAT_URL=
STALE_AFTER_SEC=2700
LOG_KEEP_DAYS=7
```

## Check / dry-run / self-test
```
python3 private/clio-private/harness/next_phase.py             # which phase is next (exit 1 = none left)
bash private/clio-private/harness/phase-driver.sh --check      # tools, profile, config readiness
bash private/clio-private/harness/phase-driver.sh --dry-run    # what the driver would do; touches nothing
bash private/clio-private/harness/phase-driver.sh --self-test  # hermetic guard/halt/stop/orphan/notify test
```

## Test locally (Mac, no cron)
Cron is server-only; test on the Mac by running the driver by hand.
```
bash private/clio-private/harness/phase-driver.sh --self-test
DISABLE_NOTIFY=1 DRIVER_STUB_RC=0 DRIVER_STUB_SLEEP=2 bash private/clio-private/harness/phase-driver.sh
DISABLE_NOTIFY=1 DRIVER_STUB_RC=1 bash private/clio-private/harness/phase-driver.sh   # exercise halt
rm private/clio-private/runs/.driver/halted

# real run with Discord pings switched off:
DISABLE_DISCORD=1 bash private/clio-private/harness/phase-driver.sh && tmux attach -t development
```
`DISABLE_NOTIFY=1` (or `DISABLE_DISCORD=1`) logs messages instead of sending them;
both reach the tmux session, so they silence the start/end/halt messages too. On
macOS there is no `flock`; the double-start guard then falls back to the tmux session
check.

## Design decisions
- **Shell-only, no Hermes skill.** The original ask was a Hermes skill that picks the
  next task. We renegotiated to a plain `sh` driver: selection and launch are fully
  deterministic, so an LLM in the loop would add cost and nondeterminism for no
  capability. Hermes is used only to *send* notifications. If you later want an agent
  to triage blocked phases, add it as a branch in the driver, not as the main loop.
- **Fail closed.** Unknown errors, signals and orphans halt the line rather than
  advance or retry.

## Manual single phase
```
python3 private/clio-private/harness/runner.py --pipeline private/clio-private/harness/pipelines/default.yaml \
  --input phase_number=100060 --input phase_file=private/clio-private/roadmap/phase-100060-parallel-write-canonical-consolidation.md
```

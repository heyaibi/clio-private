# Proposal: one plug for all am-bench notifications

Status: draft. Date: 2026-09-25. Scope: `benchmarks/am_bench` only. No scorer, judge, adapter, or dataset changes. Goes with `proposal-am-bench-natural-notifications.md` (that file owns wording; this file owns sending).

Note: on implementation, move this file to implemented/ with its implementation record.

## Problem

The runner can make a message but has no clean way to send it. If we hardcode Hermes or Discord in `runner.py:main()`, we get three problems. Adding a new channel means editing the runner. Private details like profile names and channel targets leak into public code. Each failure path behaves differently.

The harness already does this right in one place: `harness/phase-driver.sh:146-186` sends with Hermes with stdin closed, a 20s limit, one retry, one fallback channel, and a dead flag so a broken channel stops trying. `harness/dev-note.md:116-129` states the rule: sending never blocks work. am-bench needs the same rule in Python, without locking to Discord or Hermes.

Checked 2026-09-25: `benchmarks/am_bench/` has no sender today. Search for `discord` and `webhook` finds nothing. Only network use is `llm.py:82` and `fetch.py:48`. This is new code.

## Goal

The runner makes the text once and hands it to a plug. Hermes is the first plug. A direct Discord bot or anything else fits the same plug later. No runner change needed. Nothing here is Discord-only. A target is just a string the plug understands.

## Plan

New folder `benchmarks/am_bench/notify/` (public, no private paths, no secrets):

```
benchmarks/am_bench/notify/
  __init__.py    # picks the plug
  base.py        # message, result, plug shape
  hermes.py      # Hermes plug (build now)
  stdout.py      # prints to log (tests)
  null.py        # sends nowhere (off)
```

### 1. The plug shape

`base.py` holds three items.

A message: the final text plus `severity` (info, success, failure), `event` (start, done, failed), `run_id`, and `dedup_key`.

A result: `ok`, `provider` name, redacted `destination` (never a token), `message_id`, `error`, and `retriable` (can we try again).

A plug with three methods: `send`, `healthcheck`, `close`.

Rules for every plug:

- `send()` never throws into the runner. Errors come back as a result. The exit code stays the same.
- `send()` always has a time limit (20s, same as harness). No waiting forever.
- No shell. Argv list only, stdin closed.
- One event is one post. Long text is cut with a marker that points to the report file.
- Bad mentions are stripped in `base.py`. `@everyone` and `@here` are off by default.
- The runner never reads the target string. The factory maps `--notify-to` and env to a plug plus target. A bad name stops the run before it starts (exit 2).
- Tests use the `stdout` and `null` plugs. No network, no Hermes binary needed.

Factory:

```python
def build_provider(spec: str) -> tuple[NotificationProvider, str]:
    # spec is "hermes", "stdout", "null", later "discord-bot".
    # Target comes from env like AM_BENCH_NOTIFY_TO, never from code.
```

Only `main()` uses the plug: build once, send start, run suites, send done or failed, close. `run_suite()` and `progress()` never see it.

### 2. Hermes plug (build now)

`hermes.py` runs what you already run by hand:

```
hermes -p <profile> send --to <destination> <text>
```

Rules, copied from the harness:

- Profile from `HERMES_PROFILE_NAME`. Target from `AM_BENCH_NOTIFY_TO`. Fallback from `AM_BENCH_NOTIFY_FALLBACK_TO`. Nothing hardcoded in public code.
- `DISABLE_NOTIFY=1` means skip and log. Same for `DISABLE_DISCORD=1`.
- Missing `hermes` binary means skip and log. Never fails the run.
- 20s limit per try, stdin closed, output kept in debug log only.
- Try primary once, retry once, then fallback once if set. If all fail, mark dead for this process. Later sends return at once with no new process.
- Timeout means retry is allowed. Bad args or missing binary means do not retry.
- Logs show plug name and redacted target only. No tokens in logs, posts, or reports.

### 3. Later plugs

A new plug is one new file plus one factory line. No runner or wording change. Next in line: `discord_bot.py` (token from `DISCORD_BOT_TOKEN`, channel from `AM_BENCH_NOTIFY_TO`). Thread replies can use `message_id` then.

Flags (v1): `--notify hermes|stdout|null|off`, default `off`. `--notify-to` overrides env. Bad value stops before the run.

## Decision: default flag

Q: What default should `--notify` have before the wording proposal lands: `off`, or auto-`null` with a hint?

A: `off`.

Why: `off` means the runner acts exactly like today unless you ask. `null` with a hint means extra code runs and prints an extra line for no benefit yet. There is no message text to preview until wording lands. Keep it `off` now. Revisit the hint after wording ships.

## What the builder must check locally

Do not trust this file on paths. Read the code and fix as needed.

- The only send points are in `runner.py:377-482` (`main()`). `run_suite()` and `progress()` stay clean. A failed send leaves exit code and report files unchanged.
- Re-read `phase-driver.sh:146-186` and `dev-note.md:116-129`. List any place where the Python plug behaves differently on purpose.
- Subprocess uses a list, no `shell=True`, `stdin=DEVNULL`, a hard timeout each try, capped output, and no profile, channel, or token in output or reports.
- `benchmarks/am_bench/notify/` holds no `private/` path, no real profile name, no channel ID, no token, no run state. All of that comes from env or flags.
- Tests drive the full `main()` path with `stdout` and `null` plugs only, including the dead-plug shortcut.

## What the builder must check by search

Search first. Do not invent.

- Small Python sender contracts: `Protocol` plus `Result` plus factory. Keep the smallest shape where `send()` cannot throw into the runner.
- Running a CLI from Python: `subprocess.run` timeout, `DEVNULL`, no shell, output caps. Confirm 20s and one retry is sane.
- Discord limits: 2000 chars, rate limits. Confirm cut-plus-pointer and one-post-per-event is enough. Note what a future bot plug must add.
- Log redaction: what to strip so tokens and URLs never land in logs.

## Safety

- Sending never changes the score, the files, or the exit code. Errors are results, not crashes.
- Every send has a time limit. A stuck helper cannot stall the run.
- A dead plug stops trying for the rest of the process.
- One event is one post. No per-probe posts under any flag.
- No secrets in code, posts, logs, or reports. A bad plug name fails before the run starts.

## Acceptance

- No `hermes` on PATH: run passes, send is skipped in the log, exit code and reports match a run with notify off.
- Fake Hermes fails once then works: two tries on primary, one post. Always fails with fallback set: primary, retry, fallback, then dead. Later sends stop at once.
- Long text is cut to the cap with a pointer to the report, still one post. `@everyone` is stripped by default.
- `build_provider("nope")` fails fast and lists valid names.
- Manual: `DISABLE_NOTIFY=1` is silent except one skipped line. With Hermes set, start and done posts read in natural tone from the wording proposal.
- State what was checked and what could not be checked.

## Left open

- One plug per run in v1. No `hermes,stdout` chains yet.
- `dedup_key` and `run_id` are stored but unused until `discord_bot.py` needs threads. No threading work now.

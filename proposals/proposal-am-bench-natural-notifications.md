# Proposal: natural lifecycle notifications for am-bench

Status: draft. Date: 2026-09-25. Scope: `benchmarks/am_bench` only. No scorer, judge, adapter, or dataset changes.

Note: on implementation, move this file to implemented/ with its implementation record.

## Problem

The am-bench runner has no notification channel today. What it has is noisy when watched:

- `runner.py:413-414` prints one `stderr` line per probe when `--verbose`: `[{suite}] {probe_id} accuracy=...`. A full run floods the log.
- `runner.py:477-480` prints one `stdout` summary line: `am-bench: suites=... accuracy=...`.
- `runner.py:237-278` `render_markdown()` writes a full scorecard table.

Any naive Discord webhook hooked to the per-probe `progress()` callback inherits that flood. It reads as spam: many templated posts, repeated edits, pings, emoji, tables pasted verbatim. The operator still needs start / finish / fail signals, but they should read like one developer posting to a channel.

Verified 2026-09-25: repo-wide case-insensitive search for `discord` and `webhook` returns zero matches. The only outbound HTTP in `benchmarks/am_bench/` is `llm.py:82` (judge/generator chat) and `fetch.py:48` (dataset download). There is no existing notifier to fix. This is a new module.

## Goal

One run yields at most three short posts: started, finished, failed. Each reads like a developer typed it. Notifications never change the score, the report files, or the exit code.

## Proposal

Add a small separate module, e.g. `benchmarks/am_bench/notify.py`, owned by formatting only. The runner owns orchestration. Call it only from `main()` in `runner.py:377-482`, never from `run_suite()` or the per-probe loop.

Three functions:

- `format_start(run_meta) -> str` — what is running, where, how long it should take.
- `format_done(report) -> str` — what finished, headline numbers, one notable detail, where the full report lives.
- `format_failed(error, run_meta) -> str` — what broke, whether a score was written, what happens next.

Send policy: start once at run start, done once after `_write_outputs()` succeeds, failed once on abort paths (`PinError`, `MissingSnapshotError`, `ChatClientError`, `JudgeError`, `ClioAdapterError`). Batch both suites into one done message. No per-probe sends. No `@everyone`. No table paste. Point to the `.md` / `.json` files instead.

Delivery is best-effort and out of band: wrap the send in try/except, log to `stderr` on failure, keep the original exit code. A dead channel never fails a benchmark.

## Generation method: deterministic templates, not an LLM

Do not generate these posts with an LLM.

- Numbers must match `build_report()` output exactly. Templates cannot hallucinate. An LLM can round or invent a score.
- The runner already fails loudly on judge/generator outages. Another model call adds another failure point for a 2-sentence post.
- Templates are unit-testable with a fixed dict. LLM wording is not.
- No extra cost or latency on runs that already take minutes.

Wording: 2-3 hand-written variants per event, picked by `seed` from `run_meta`, not by a model. That is enough variation to avoid robotic repetition without losing determinism.

An LLM polish step is allowed later only as an optional second pass: template first, rewrite second, reject the rewrite unless every number from the report still appears verbatim, fall back to the template on any failure. Do not start there.

## Examples from past runs (temporary mockups, never sent)

Generated 2026-09-25 from real `run` metadata in `benchmarks/reports/baseline-locomo.json` and `benchmarks/reports/baseline-longmemeval.json` using `report["run"]` fields (`suites`, `partition`, `seed`, `max_probes`, `adapter`, `judge.model`).

Start, locomo past config:

> kicking off locomo on canary (seed 100480, 5 probes, clio adapter, qwen2.5-1.5b-instruct). ~12 min, will post when done.

Start, longmemeval past config:

> kicking off longmemeval on canary (seed 100480, 6 probes, clio adapter, qwen2.5-1.5b-instruct). ~12 min, will post when done.

Done, same runs (headline numbers from `overall`):

> done. locomo 0.23 acc / 0.21 F1, longmemeval 0.0 acc / 0.15 F1. temporal still weak on both. full scorecard is in `benchmarks/reports/`. nothing urgent.

Failed:

> failed — judge endpoint timed out after 40s on locomo probe 3/5. no score written. I'll retry with tier1 locally, no action needed from you.

## What the implementer must validate locally

Do not trust this proposal on where things live. Read the code first and confirm or correct each point.

- Confirm `build_report()` in `runner.py:201-234` is the single source for numbers used in `format_done()`, and that `run_meta` in `runner.py:454-464` has every field the start message needs. List any missing field before adding it.
- Confirm the only call sites are in `main()`: start before the suite loop, done after `_write_outputs()`, failed on each `return 2` abort path. Confirm `run_suite()`, `select_work()`, and `progress()` stay untouched.
- Confirm notification failure cannot change behavior: stub the sender to raise, run a passing and a failing suite, and show exit codes and report files are identical with the sender on or off.
- Confirm batching: a `--suite both` run sends one done message, not one per suite. Confirm `--verbose` per-probe lines stay on `stderr` and never reach the channel.
- Confirm secrets handling: webhook URL comes from env only, never from `pins.json`, logs, or the report. Confirm the URL never appears in `stdout`, report files, or error text.

## What the implementer must validate externally

Search first. Do not invent alerting behavior.

- Search for alert-fatigue guidance on lifecycle vs per-event notifications for batch jobs, and compare a 3-message budget against per-probe updates.
- Search for webhook best-practice for CI/benchmark bots: single post vs thread updates, when to edit vs post anew, and why `@here`/`@everyone` and emoji floods read as spam.
- Search for precedent on deterministic status templates with seed-picked variants versus LLM-generated status text, including hallucination and testability trade-offs.

## Rejected alternative

Avenue B (single batched digest only, no start/fail posts) was considered: one message per run after all suites finish. It is quieter but leaves long runs silent while they execute and merges failure into silence. Keep it as a config flag (`--notify digest`) later if operators want it, not as the default. Default is Avenue A lifecycle.

## Safety properties

- At most three posts per run across all paths, then silence.
- A failed send never blocks, delays, or changes the run outcome, exit code, or report contents.
- Posted numbers always equal the written report numbers verbatim.
- No secrets in posts, logs, or reports. Webhook URL from env only.
- No per-probe channel traffic under any flag combination.

## Acceptance

- Automated check with stubbed sender: a two-suite pass yields exactly one start plus one done; a judge outage yields exactly one start plus one failed; per-probe `progress()` calls never invoke the sender.
- Automated check: `format_done()` output contains the exact `accuracy` and `token_f1` strings from `build_report()` for a fixture report.
- Manual check: run `locomo --max-probes 5 --verbose` with a stubbed channel, observe one start and one done in natural tone, confirm no per-probe posts and exit code 0. Break the judge URL, observe one failed post and exit code 2 with no score file claimed as valid.
- State what was verified locally and externally, and list anything that could not be verified.

## Open questions

- What time estimate should `format_start()` show when duration history is missing for a new suite/adapter pair?
- Should the sender edit the start post with the result or post anew, given channel threading behavior?
- Is a `--notify off| lifecycle | digest` flag worth it now, or ship lifecycle-only first?

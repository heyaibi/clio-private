# Proposal: natural, low-noise am-bench notifications

Status: draft. Date: 2026-09-25. Scope: `benchmarks/am_bench` notification wording and notification frequency only. This proposal pairs with `proposal-am-bench-notification-providers.md`, which owns how messages are sent. Neither proposal changes benchmark scoring, datasets, judges, generators, adapters, or report contents.

## Problem

The runner currently has no notification sender. If notifications are added directly to `runner.py`, they will likely look like copied log lines:

```text
[clio] benchmark starting
[clio] benchmark finished
[clio] benchmark failed
```

That wording is technically clear but not natural. It sounds like a program printing status, not like a developer reporting the result to another developer. Repeated start and finish messages also create notification fatigue.

The wording must answer the reader's practical questions without making them open the logs or report first:

- What ran?
- Is it still running?
- Did it finish cleanly?
- What happened if it failed?
- Where is the result?

## Goals

- Make each notification read like a short developer update.
- Keep the message useful when read outside the terminal.
- Send few enough messages that the channel remains readable.
- Make success, failure, and incomplete runs visually and semantically clear.
- Keep notification failure separate from benchmark failure.
- Keep wording independent from the notification provider.

## Non-goals

- Do not send one notification per probe.
- Do not add Discord-specific wording or Discord code to `runner.py`.
- Do not put secrets, profile names, channel IDs, or private configuration into messages.
- Do not let a notification failure change the score, report, or exit code.
- Do not use an AI model to generate routine messages.
- Do not change benchmark execution behavior in this proposal.

## Notification events

The first version supports three events:

### Started

Use this for the beginning of a benchmark run. The message should tell the reader that work has started without sounding like a command-line log.

Example:

```text
Started the am-bench run for LoCoMo and LongMemEval on the canary partition. I’ll report back when it finishes.
```

The message may include:

- suite names
- partition
- adapter name

It should not include private paths, credentials, or environment details.

### Completed

Use this after the runner has written the score report successfully. The message should lead with the result, then include enough context to decide whether to inspect the report.

Example:

```text
am-bench finished successfully.

LoCoMo and LongMemEval: 240 probes scored
Overall accuracy: 0.7421
Token F1: 0.6814
Report: benchmarks/reports/2026-09-25-canary.json
```

The runner should use values from the assembled report rather than reconstructing them from partial state. A completion notification must not claim that a report exists unless `_write_outputs` succeeded or no output path was requested.

If no report path was requested, the message may omit the report line. It must not invent a path.

### Failed

Use this when the benchmark stops before producing a usable score. The message should state what happened and whether a report was produced.

Example:

```text
am-bench stopped before producing a score.

The judge service did not respond after the configured timeout. No score report was written.
```

For an unexpected internal error, use a short, safe summary:

```text
am-bench stopped unexpectedly.

The run failed while processing the benchmark. The error was recorded in the local run logs; no score report was written.
```

Do not send a full traceback in the notification. The notification should help the reader decide what to do. Detailed errors remain in the local log.

## Writing rules

Messages should follow these rules:

1. Use ordinary sentences, not status labels and bracketed prefixes.
2. Lead with the event: started, finished, or stopped.
3. Put the result before secondary metadata.
4. Use plain words such as “failed” and “stopped” rather than vague words such as “encountered an issue.”
5. State the consequence for the score report.
6. Include a report path only when the report was actually written.
7. Keep messages short enough to scan in Discord.
8. Do not use emojis, decorative punctuation, or fake enthusiasm.
9. Do not address the reader as if the run is a long-running personal conversation.
10. Do not claim that the system will do something it will not do.

The first version should use deterministic templates. A template is predictable, testable, cheap, and cannot invent benchmark facts. An AI-generated message is unnecessary for these fixed events.

## Frequency and anti-spam policy

The first version sends one notification per event and no per-probe notifications:

- One start notification.
- One completion notification.
- One failure notification if the run cannot produce a score.
- No notification for an individual probe.
- No automatic notification for every suite when the suites are part of one command.

A multi-suite run therefore produces one start message and one final result, not one start and one result per suite.

Notification delivery has its own retry and dead-channel policy in the provider proposal. Those rules must not turn a single event into repeated visible posts. Retries should use the same deduplication key and should not send the same event as a new message.

Long-running runs do not need repeated progress notifications. If a future stall notification is added, it must have a quiet period and a maximum repeat frequency. That policy belongs in the phase driver or run supervisor, not in the benchmark scorer.

## Proposed module boundary

Add a notification package beside the runner:

```text
benchmarks/am_bench/notify/
  __init__.py
  base.py
  messages.py
  hermes.py
  stdout.py
  null.py
```

`messages.py` owns wording. It receives facts from the runner and returns a `Notification` object. It does not send anything and does not know whether the destination is Discord, Hermes, stdout, or a test double.

`runner.py` owns event creation only:

1. Create a run identifier before the work starts.
2. Create a start message and pass it to the provider.
3. Run the suites.
4. Create either a completion or failure message from the result.
5. Pass that message to the provider.
6. Close the provider in a `finally` block.

`run_suite()` and `progress()` must not receive the provider and must not send messages themselves.

## Suggested message API

The message layer should use structured facts rather than accepting a preformatted string from arbitrary call sites. A small shape is enough:

```python
@dataclass(frozen=True)
class Notification:
    event: str
    text: str
    severity: str
    run_id: str
    dedup_key: str
```

The wording functions should be small and pure:

```python
def started_message(run_meta: dict, report_hint: str | None = None) -> Notification:
    ...

def completed_message(report: dict, report_path: Path | None) -> Notification:
    ...

def failed_message(reason: str, report_written: bool) -> Notification:
    ...
```

The exact API may follow the provider proposal's existing `Notification` and `NotificationResult` types. The important boundary is that wording has no network or subprocess calls.

## Safety and failure behavior

Notification delivery is best effort. It must never:

- change the benchmark exit code;
- change the score report;
- delay the benchmark without a hard timeout;
- expose credentials in logs, messages, or reports;
- cause the runner to retry a benchmark operation;
- produce a visible duplicate for the same event.

If the provider is unavailable, the runner should log a short notification failure and continue. If the benchmark itself fails, the runner should try to send one failure notification, but the original benchmark error remains authoritative.

## Tests and acceptance

The implementation should add tests for:

- a natural start message containing the suite and partition;
- a successful completion message containing scored probes, accuracy, token F1, and the real report path;
- a completion message without a fake report path when no output file was requested;
- a failure message that says no report was written when appropriate;
- a failure message that does not include a traceback or secret;
- one start and one final event for a multi-suite run;
- no notification calls from `run_suite()` or `progress()`;
- a provider failure leaving the benchmark exit code and report unchanged;
- deterministic output for the same report and run metadata.

Manual review should compare the messages with the actual runner output and confirm that each one reads naturally in Discord. The reviewer should be able to understand the status without opening the terminal.

## Decision

Use deterministic, developer-style messages with a strict event limit. Send one start message and one final message for a benchmark command. Keep the wording in `notify/messages.py`, sending in a provider plug, and benchmark facts in `runner.py`.

The separate phase-driver notification wording is not changed by this proposal. If phase-driver messages are also rewritten, they should get their own proposal because they have different events, spam controls, and halt behavior.

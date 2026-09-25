# Proposal: natural, low-noise phase-driver notifications

Status: implemented (2026-09-25). Scope: `harness/phase-driver.sh` notification wording and notification frequency only. This proposal does not change phase selection, reservations, runner behavior, pipeline behavior, halt behavior, or the Hermes transport.

The previous `proposal-am-bench-natural-notifications.md` was withdrawn. The words “am-bench” in that filename and in the historical messages identify the phase or feature being worked on at the time. They do not identify a separate benchmark notification system. The notifications shown by the current driver are phase-driver notifications. This proposal describes the notifications that the driver actually sends.

## Problem

The phase driver currently sends messages that read like copied log lines:

```text
[clio] phase 100480 starting (private/clio-private/roadmap/phase-100480-benchmark-runner-build.md)
[clio] phase 100500 finished: completed
[clio] phase 100520 HALTED: exit 2. Line stopped; see private/clio-private/runs/phase-100520/
```

The messages are technically clear, but they are hard to scan outside the terminal. They expose internal paths, use status labels, and do not consistently explain whether the work is still running, whether it finished, or what the operator should do next.

The driver also makes notification decisions in several branches. Without one clear event policy, a future branch can easily add another start, halt, or retry message and create noise.

## Goals

- Make each message read like a short developer update.
- State the phase and the outcome first.
- Make success, interruption, halt, signal stop, and stall visually and semantically clear.
- Tell the reader whether work is still running.
- Tell the reader what action, if any, is needed next.
- Keep notifications useful when read outside the terminal.
- Send one clear message per notification event and avoid repeated cron noise.
- Keep notification delivery failure separate from phase-driver failure.

## Non-goals

- Do not change which phase is selected or when a phase starts.
- Do not change reservation, routing, retry, halt, or pipeline behavior.
- Do not change Hermes, Discord, profiles, channels, retries, or dead-channel handling.
- Do not add notifications to `harness/runner.py`.
- Do not send one notification for every cron tick or every internal decision.
- Do not include private paths, profile names, channel IDs, credentials, or environment values in a message.
- Do not send a full log excerpt or traceback in a notification.
- Do not let notification failure change the phase result, halt marker, or exit code.
- Do not use an AI model to generate these routine messages.

## Notification events

The first version covers the events currently emitted by `run_session()` and `check_stall()`.

### Started

Use once when a phase session is launched.

The message must name the phase and say that work is running. It must not include the private phase-file path.

Example:

```text
Phase 100520 started.

The work is running. I’ll report when it finishes.
```

The message may include the short phase name when the driver has a safe, already-loaded name. It must not read a private file or build a new title from an unchecked path.

### Completed

Use once after the phase exits successfully and the driver records the completed state.

The message must lead with completion and state what the driver can do next. It must not claim that another phase has started. Cron decides that on a later tick.

Example:

```text
Phase 100520 finished successfully.

The run state is completed. The driver can continue on its next tick.
```

### Interrupted

Use when the phase exits with the existing interrupt status and is expected to resume on a later tick.

Example:

```text
Phase 100520 was interrupted.

The work is not complete. It will resume on the next driver tick.
```

The message must not say that the phase failed permanently or that a retry has already happened.

### Halted

Use when a phase ends in a blocked, rejected, or otherwise terminal state that writes the halt marker.

The message must state the phase outcome, the exit code when it is known, and the fact that the driver is halted. It must point to the local run logs without putting a private filesystem path in the message.

Example:

```text
Phase 100520 stopped before the line could continue.

The run returned exit 2. The driver is halted; inspect the local run logs before retrying.
```

The message must not claim that retrying is safe. The operator must inspect the cause first.

### Stopped by signal

Use when the operator stops the live session or the session receives a termination signal.

This is different from an ordinary interrupt. The line is halted and requires operator action.

Example:

```text
Phase 100520 stopped by signal.

The driver is halted. Check the local run logs, then clear the halt when the stop was intentional.
```

The message must not claim that the phase will resume automatically.

### Stalled

Use once when the watchdog first marks a live phase as stalled. The current marker prevents repeated stall notifications on later cron ticks.

Example:

```text
Phase 100520 looks stalled.

There has been no new output for 45 minutes. The session is still running; inspect it before stopping the work.
```

The message must not claim that the process is dead. The current watchdog only knows that output has been quiet.

## Writing rules

Messages must follow these rules:

1. Use ordinary sentences. Do not use bracketed prefixes such as `[clio]`.
2. Lead with the phase and the event: started, finished, interrupted, stopped, or looks stalled.
3. Put the result before secondary metadata.
4. Use plain words such as “failed,” “stopped,” and “halted” rather than vague phrases such as “encountered an issue.”
5. State whether the work is still running.
6. State the consequence for the driver: it can continue, it will resume, or it is halted.
7. Include a filesystem path only when the path is necessary and safe. The phase-driver notification should point to “the local run logs” instead.
8. Do not include a profile name, channel ID, credential, environment value, or full command.
9. Do not include a full traceback or copied log line.
10. Keep each message short enough to scan in Discord.
11. Do not use emojis, decorative punctuation, or fake enthusiasm.
12. Do not claim that the driver has done something it has not done.

## Frequency and anti-spam policy

The first version has a strict event limit:

- Send one start message after one successful phase launch.
- Send one final message for each launched phase: completed, interrupted, halted, or stopped by signal.
- Send one stall message for each stall episode. The existing stall marker must prevent later cron ticks from sending the same message again.
- Send no message for a skipped tick, a busy session, a refused launch, or a line that is already halted, unless a later implementation explicitly adds a separate event for that case.
- Send no per-step, per-log-line, or per-cron-tick notifications.
- A retry of the same send must keep the same event identity and must not create a second visible post.
- A new phase launch starts a new event identity even if the phase number is the same after a deliberate retry.

The driver may continue to log internal decisions locally. It does not send those decisions as notifications.

## Safety and failure behavior

Notification delivery is best effort. It must never:

- change the phase-driver exit code;
- change the runner result or phase state;
- clear or create a halt marker;
- delay a phase launch without a hard timeout;
- cause a phase retry;
- expose credentials in messages or logs;
- produce a visible duplicate for one event.

If Hermes is unavailable or a send fails, the driver should log a short notification failure and continue. The existing dead-channel behavior remains authoritative. Notification failure must not turn a successful phase into a halt or an interrupted phase into a permanent failure.

## Module boundary

This proposal changes wording and frequency only. The send path remains in `harness/phase-driver.sh` unless a separate provider proposal changes it.

The driver owns:

- deciding which event occurred;
- choosing the structured facts for that event;
- calling the existing send function once for that event;
- preventing repeated sends for the same stall or final event.

The send path owns:

- Hermes invocation;
- timeout, retry, fallback, and dead-channel behavior;
- profile and channel configuration.

`harness/runner.py` owns no phase-driver notifications. It must not receive a notification provider or send messages on behalf of the driver.

## Validation to perform before implementation

The implementer must read the current driver and confirm every send site before changing wording. In particular, verify:

- the exact events emitted by `run_session()`;
- the signal-stop path in `on_stop()`;
- the one-time stall path in `check_stall()`;
- how the halt marker and stall marker prevent repeated notifications;
- how the existing self-test captures logged messages;
- which values are safe to include without reading private paths or environment files;
- whether existing tests or log greps depend on the old `[clio]` prefix and old status strings.

If the current code has a send path that is not listed here, document the event before deciding whether it belongs in scope. Do not silently add a new notification while changing wording.

## Acceptance

- A launched phase produces one start message and exactly one final message.
- A completed phase message says that work finished and that the driver can continue on a later tick.
- An interrupted phase message says that the work will resume on a later tick.
- A halted phase message says that the driver is halted and tells the operator to inspect local logs before retrying.
- A signal-stop message does not claim automatic resumption.
- A stalled phase produces one stall message and later cron ticks do not repeat it while the stall marker remains.
- Messages contain no private paths, profile names, channel IDs, credentials, or traceback text.
- Notification transport failure does not change the phase result, halt state, or exit code.
- The existing self-test and notification logging checks pass after their assertions are updated to the new wording.
- A manual review compares the actual messages with a real driver run and confirms that the reader can understand the state without opening the terminal.

## Decision

Use deterministic, developer-style messages for phase-driver events. Send one start and one final message for each launched phase, plus one message for each distinct stall episode. Keep event selection in the driver and keep Hermes delivery behavior unchanged.

The am-bench notification proposals do not describe this system and must not be used as the implementation source for these messages. If benchmark notifications are needed later, they require a separate proposal tied to the benchmark runner that actually exists.

---

# Implementation record

## Changes

- Added `harness/phase_notifications.py` to parse phase filenames, build readable titles, preserve common acronyms, and format each event without sending anything itself.
- Updated `harness/phase-driver.sh` to use the formatter for start, completion, interrupt, halt, signal-stop, and stall messages.
- Removed the `[clio]` message prefix.
- Rewrote start, completion, interrupt, halt, signal-stop, and stall messages as short developer updates.
- Removed the private phase-file path from the start message and the private run path from the halt message.
- Kept Hermes configuration, retry, fallback, timeout, and dead-channel behavior unchanged.
- Kept the stall marker as the one-time guard for stall notifications.
- Removed the notification for a phase that returns `WAIT_FOR_CLAIM`; that path does not launch phase work and the proposal excludes refused launches.
- Updated the driver self-test for the new wording and added checks for one start message, one final completion message, no old prefix, and one non-repeating stall message.
- Updated `harness/dev-note.md` to describe the new wording and frequency.

## Verification

- `bash -n harness/phase-driver.sh` passed.
- `bash harness/phase-driver.sh --self-test` passed. The test used disabled delivery and verified the logged message text and counts.
- `python3 -m unittest discover -s harness -p 'test_phase_notifications.py'` passed all 5 formatter tests.
- `python3 -m unittest discover -s benchmarks/tests` passed all 116 tests.
- `shellcheck` was not installed, so shellcheck lint was not run.
- No real Hermes or Discord send was performed. The transport path was left unchanged and was not part of this wording-and-frequency change.

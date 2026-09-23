# Proposal: limited halt reminders per unique halt

Status: draft. Date: 2026-09-23. Scope: driver only. No runner, stage, or pipeline changes.

## Problem

The driver notifies once when the line halts, then stays silent on later ticks while halted. If the operator misses that one message, the line sits stuck with no further signal until someone reads the log.

## Proposal

On each invocation that finds the line halted, resend at most a small configurable number of extra reminders for that same halt, then stay silent. A new halt resets the budget. Improve or replace this proposal if your local and external validation finds a safer or less noisy fix.

## Hypothesis (non-binding)

Treat each distinct halt as one episode with a fixed reminder budget shared across invocations, and spend it slowly enough to catch attention without spamming the channel.

This document states the problem and the safety properties only. It deliberately prescribes no implementation. The implementer owns the design after validation below.

## What the implementer must validate locally

Do not trust this proposal on where things live. Read the code first and confirm or correct each point.

- Find every path that creates the halt marker and every path that only observes it. Confirm which tick sends the original notification and which ticks stay silent today.
- Find how to recognise the same halt across invocations versus a new halt, including what changes when the cause, phase, or timestamp changes. Confirm what must reset the reminder budget.
- Find where per-episode reminder state could live without changing halt semantics, and how it is cleaned when the halt clears. Confirm concurrent ticks cannot double-spend the budget.
- Find how notification settings and overrides are read, and add the reminder limit and spacing there with safe defaults. Confirm the default extra budget is three and that zero restores today's behavior.
- Confirm reminders stay best-effort like existing notifications and can never block, delay, or clear the halt.

## What the implementer must validate externally

Search first. Do not invent alerting behavior.

- Search for established reminder and backoff patterns for stuck automation, including fixed budgets versus time-based decay and per-episode deduplication.
- Search for alert-fatigue guidance on reminder counts and spacing for low-urgency stuck lines, and compare a small fixed budget against repeated or escalating alerts.
- Look for failure modes where reminders hide a new cause by reusing an old episode identity, and how others key episode identity to avoid that.

## Safety properties

- The original halt notification still goes out exactly as today.
- Each unique halt yields at most the configured number of extra reminders across all invocations, then silence until the halt clears or a new halt appears.
- Clearing the halt clears the reminder debt. A new halt starts a fresh budget.
- A failed reminder send never blocks the tick and counts conservatively so a dead channel cannot burn the budget silently.
- Spacing between reminders is bounded from below so ticks every few minutes cannot burst the whole budget at once.

## Acceptance

- Add an automated check with stubbed sends: one halt episode yields one original plus at most the configured extras across many invocations, and a changed halt resets the budget.
- Add a manual check: halt the line, observe the original plus limited reminders on later ticks, clear the halt, and confirm no further reminders.
- State what was verified locally and externally, and list anything that could not be verified.

## Open questions

- What spacing between reminders balances attention against spam for the current tick interval?
- Should the budget count sends attempted or sends confirmed, given the channel is best-effort?

# Proposal: remind idle agents to write their exit signal

Status: draft. Date: 2026-09-23. Scope: harness only. No stage or pipeline changes.

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

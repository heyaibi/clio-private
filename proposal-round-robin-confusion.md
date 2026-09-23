# Proposal: stop harness rotation from confusing agents

Status: draft. Date: 2026-09-23. Scope: harness only. No stage or pipeline changes.

## Problem

Stages rotate between models across attempts and phases. When an early attempt fails and a later attempt retries, the run directory keeps both task files with different model names. Downstream agents read both files, treat the difference as a real conflict, and waste time or write wrong findings about which model ran or what was required.

## Proposal

Make the successful attempt the single obvious source of truth and teach downstream prompts to ignore superseded attempts. Improve or replace this proposal if your local and external validation finds a safer or more reliable fix.

## Hypothesis (non-binding)

Separate per-attempt history from the authoritative record, keep retries from looking like new requirements, and tell reviewers exactly which record wins when task files disagree.

This document states the problem and the safety properties only. It deliberately prescribes no implementation. The implementer owns the design after validation below.

## What the implementer must validate locally

Do not trust this proposal on where things live. Read the code first and confirm or correct each point.

- Find how the next model is picked, when that choice is recorded, and whether a failed attempt advances the rotation. Confirm what the retry uses after an interrupt or a missing signal.
- Find what task files remain on disk after a retry and what each one claims about the model and the round. Confirm which file the successful run actually used.
- Find how downstream prompts rebuild earlier context, and whether that rebuilt context names the planned model or the model that really ran. Confirm against the run transcript and completion record.
- Find how the attribution record is written on normal completion versus retries. Confirm whether stale attempts can leave rows or text that a later reviewer could mistake for requirements.
- Read the stage and pipeline docs for the rotation and signal contract before changing anything.

## What the implementer must validate externally

Search first. Do not invent scheduling or prompt design.

- Search for established patterns for rotating models or workers across retries, including when rotation should advance on failure versus only on success.
- Search for provenance patterns that keep one authoritative record of what ran while preserving per-attempt history for forensics.
- Search for prompt designs that prevent reviewers from treating superseded context as requirements, including explicit authority ordering and stale-context guards.

## Safety properties

- History is preserved for forensics but never reads as a live requirement.
- The successful attempt and the completion record always agree on what ran.
- A failed attempt never advances rotation in a way that makes retries look like intentional model switches.
- Reviewers are told which record wins on disagreement, and model-name differences between attempts are never findings.
- Normal rotation across phases still alternates as intended.

## Acceptance

- Add an automated check that a failed attempt followed by a retry leaves one clear authoritative record, and that rebuilt downstream context names the model that really ran.
- Add a manual check with a stub harness: interrupt once, resume, then confirm a reviewer prompt no longer presents two competing model names as a conflict.
- State what was verified locally and externally, and list anything that could not be verified.

## Open questions

- Should a retry reuse the same model or advance, and what should the transcript say in each case?
- Should superseded task files be marked, moved, or left as-is with stronger prompt guards?

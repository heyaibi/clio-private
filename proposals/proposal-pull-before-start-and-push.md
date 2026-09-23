# Proposal: pull before start and before final push

Status: draft. Date: 2026-09-23. Scope: pipeline startup and finalization only. No other stage changes.

## Problem

A phase can start from a stale local checkout and finalize can push without checking the remote first. The push then fails on divergence, or two repos drift apart, and recovery becomes manual across both checkouts.

## Proposal

Sync from the remote (both `clio` and `private/clio-private`) before starting a phase, and in finalization sync again before pushing, resolving any conflict first and pushing only when the tree is clean and intended. Improve or replace this proposal if your local and external validation finds a safer fix.

## Hypothesis (non-binding)

Treat a fresh sync as a precondition for starting work and for publishing it, with conflicts resolved explicitly rather than forced through.

This document states the problem and the safety properties only. It deliberately prescribes no implementation. The implementer owns the design after validation below.

## What the implementer must validate locally

Do not trust this proposal on where things live. Read the code first and confirm or correct each point.

- Find where a phase run starts and what local state it assumes, including staged changes, unstaged work, and completion records from prior runs.
- Find where finalization stages, commits, and pushes, including how both checkouts are handled and what happens today when the remote has moved.
- Find how completion proofs and resume state treat repository history, and whether a sync mid-run would invalidate them.
- Find the private and public boundary rules and confirm no sync change can stage, publish, or log private paths in the wrong place.
- Read the driver, runner, and finalize docs for the fail-closed contract before changing anything.

## What the implementer must validate externally

Search first. Do not invent git automation.

- Search for established patterns for sync-before-start and sync-before-push in unattended pipelines, including fast-forward-only versus merge versus rebase choices.
- Search for safe conflict handling in automation, including when to stop and alert versus when a mechanical resolution is acceptable.
- Look for failure modes where an automatic sync loses local work, rewrites published history, or publishes the wrong checkout, and how others guard against each one.

## Safety properties

- Local work is never discarded or rewritten silently to satisfy a sync.
- A conflict stops the line for an operator decision unless the resolution is mechanical, recorded, and within the documented rules.
- History is never rewritten after publishing, and private content never moves to the public checkout in either direction.
- A failed sync blocks progress with a clear message rather than starting or pushing on a stale base.
- Completion and resume records stay consistent with the history they attest to.

## Acceptance

- Add an automated check with stubbed remotes: stale start is refused or synced, diverged final push syncs first, and a conflict halts without pushing.
- Add a manual check on both checkouts: start stale, finalize diverged, and confirm no work is lost and no private path leaks.
- State what was verified locally and externally, and list anything that could not be verified.

## Open questions

- Which sync strategy fits the fail-closed pipeline for each checkout?
- What conflict evidence must the halt message carry so the operator can resolve it quickly?

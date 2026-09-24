# Proposal: skip unavailable harnesses, halt when a stage has none

Status: draft. Date: 2026-09-24. Scope: runner only. No stage, pipeline, or rotation-file format changes.
Source: merged from `wayfinder-harness-skip/` (map plus tickets 01–04, all open, none decided). The folder was removed after this merge, so this file is now the single record.

Note: on implementation, move this file to implemented/ with its implementation record.

## Problem

A step lists several harnesses in its stage frontmatter. Today the runner tries the rotation slot and fails the whole run when that CLI binary is missing, even when the next harness in the same list is installed. The request: skip the missing harness, use the next available one, and halt then and there only when no harness for that stage is available.

## Proposal

Check availability before invoking. For each step invocation, walk the stage harness list starting at the current rotation offset, wrapping around, and use the first harness whose CLI binary is on PATH. When every entry is missing its binary, halt the run at that step with a config error that names the step and the missing binaries. No harness is invoked in the halt case.

Availability in v1 means binary presence only (`shutil.which` on the CLI word: `opencode`, `agy`, `agent` for cursor, `hermes`, `cmd`). Model catalog and effort checks stay where they are today (self-test and the existing `cmd` invoke-time probe). A catalog command that is itself unavailable never marks a harness unavailable; the binary check decides.

## Hypothesis (non-binding)

This document states the problem and the safety properties only. It deliberately prescribes no implementation. The implementer owns the design after validation below. One consistent reading:

- Order is preserved from the rotation offset with wrap-around. Skipped entries do not consume a rotation slot on their own; the successful invocation consumes past the skips so the next run does not retry a known-missing head every time.
- A skip writes no task or log file and increments visits once, for the harness actually used. The step event and transcript record the skipped ids and their missing binaries.
- The all-unavailable halt is fail-closed: exit 2 (`config_error`) with machine-readable JSON naming the step and every harness tried, `resume.json` kept at the current step, no ledger entry, no rotation advance. Resume retries the same step after the operator installs a harness.
- `dry-run` and the step banner show which harnesses were skipped and why. `self-test` keeps its current per-harness binary checks and gains stub-PATH cases for skip-then-use-next and halt-when-none.

## What the implementer must validate locally

Do not trust this proposal on where things live. Read the code first and confirm or correct each point.

- Find the exact fail point for a missing binary today (`Run.invoke` spawn, `run_attached` fallback) and confirm the drive loop does not catch it, so the run stops even when a later list entry is installed.
- Find `harness_for`, the rotation consume points in `drive`, and every `mark-done` peek at rotation, and confirm a skip path that neither double-consumes nor strands the offset.
- Find how `visits`, task/log filenames, transcript events, and `resume.json` interact for a step that examines several harnesses but invokes one, and confirm skipped entries leave no ledger or artifact trace.
- Find the halt shapes available (`config_error` exit 2 versus terminal states) and confirm the all-unavailable halt uses the fail-closed config error with the step and binary names, and that resume lands on the same step.
- Confirm the `cmd` invoke-time probe stays fail-closed as today and is not silently converted into a skip when inconclusive, or justify the change explicitly.

## What the implementer must validate externally

Search first. Do not invent availability semantics.

- Search for established skip-unavailable patterns for multi-backend runners, including binary-presence checks versus capability probes and fail-closed halts when no backend remains.
- Compare treating unknown models and unsupported efforts as unavailable against treating only missing binaries as unavailable, including flakiness and spend for each probe.
- Look for failure modes where a skip masks a real misconfiguration (wrong binary name, broken PATH) and how others surface skipped backends loudly enough to notice.

## Safety properties

- An installed harness is never skipped because another entry is missing.
- List order and weighting beyond skipping do not change.
- A skip never writes a ledger entry and never presents a skipped harness as the completing model.
- The halt invokes nothing, advances no rotation, and names the step and every missing binary.
- A failed availability check fails closed instead of guessing an available harness.

## Acceptance

- Add an automated check with stub binaries on a fake PATH in temp dirs: missing-head uses next, all-missing halts as config error with the step named, no inference spend, no repo state touched.
- Run `dry-run`, `self-test`, and the new checks, and state what was verified and anything that could not be verified.

## Open questions

- Should a `cmd` model or effort rejection (spend-free probe) also count as unavailable, or stay a hard config error?
- When a catalog command is unavailable, should the harness count as available and fail later, or halt earlier?
- Exact banner and `dry-run` wording for skips, and whether skipped ids belong in the transcript event.

## Out of scope

- Changing round-robin ordering or weighting beyond skipping.
- Retrying a skipped harness later in the same run after install.
- Automatic installation of missing harnesses.

## Appendix: merged wayfinder map and tickets

The sections below are the verbatim map and ticket bodies from
`wayfinder-harness-skip/`, kept so no context is lost.

### Map: Harness availability skip in the stage-pipeline runner

Private-local map. No public issue was created: the target code lives
under `private/`, so a public tracker entry would leak private paths.

Destination: the runner skips a harness whose CLI is not installed,
tries the next harness in the same workflow stage, and halts the
pipeline then and there only when no harness for that stage is
available.

Decisions so far: none yet.

Not yet specified:

- Whether model-level rejection (unknown model, unsupported effort)
  counts as unavailable, or whether only a missing binary does.
- Exact skip accounting: rotation slot, visits, task/log files,
  transcript events for a skipped harness.
- Exact halt shape when a stage has zero available harnesses: exit
  code, `run.json` / `resume.json` state, operator message.
- What `dry-run` and `self-test` report for skipped versus halted
  stages, and which automated checks pin the behavior.
- Later fog: per-model probes that cost nothing, catalog-unavailable
  handling, UX banner wording for skips.

### Ticket 01: What counts as an unavailable harness

Type: grilling (HITL). Frontier, no blockers.

Question: what counts as unavailable for the skip: only a missing CLI
binary on PATH, or also a listed model the CLI rejects and an
unsupported effort level? `Run.invoke` today fails on a missing binary.
`self-test` already distinguishes binary-missing from model-unlisted
and from `cmd` probe rejections, without spending inference. The
decision fixes which of those checks the live skip reuses, and what
happens when a catalog command itself is unavailable.

### Ticket 02: Skip semantics against rotation, visits, and ledger

Type: grilling (HITL). Blocked by ticket 01.

Question: when a harness is skipped, what does the runner record: does
the skip consume a rotation slot, increment visits, write a task/log
file, or append a transcript event, and how does the ledger stay
authoritative? Today a slot is consumed only after an accepted signal,
and a failed attempt retries the same harness. A skip is neither a
success nor a harness failure. The decision fixes where the
availability check lives (pre-step filter versus invoke-time fallback)
and what forensic trace a skip leaves.

### Ticket 03: Halt behavior when a stage has no available harness

Type: grilling (HITL). Blocked by ticket 01.

Question: when every harness for a workflow stage is unavailable, how
does the pipeline halt then and there: which exit code, which `run.json`
/ `resume.json` state, and which operator-facing message names the stage
and the missing harnesses? The request says halt then and there. The
runner already has terminal states (`completed`, `rejected`, `blocked`,
`config_error`) and exit codes 0/1/2. The decision fixes which halt
shape a fully unavailable stage uses, and whether resume retries the
same stage.

### Ticket 04: Reporting and automated checks for skips and halts

Type: task (AFK once tickets 01–03 close). Blocked by tickets 01–03.

Question: do the reporting and test work the prior decisions unblock:
show skipped harnesses in the step banner, `dry-run`, and `self-test`
output, and pin skip-then-use-next plus halt-when-none with stub
harnesses in temp dirs (no inference spend, no repo state)? Resolved
when the reporting surface and the checks exist and the map can hand off
to implementation.

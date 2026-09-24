# Proposal: stop harness rotation from confusing agents

Status: implemented (2026-09-24). Scope: harness only. No stage or pipeline changes.

## Problem

Stages rotate between models across attempts and phases. When an early attempt fails and a later attempt retries, the run directory keeps both task files with different model names. Downstream agents read both files, treat the difference as a real conflict, and waste time or write wrong findings about which model ran or what was required.

## Proposal

Make the successful attempt the single obvious source of truth and teach downstream prompts to ignore superseded attempts. Improve or replace this proposal if your local and external validation finds a safer or more reliable fix.

## Hypothesis (non-binding)

Separate per-attempt history from the authoritative record, keep retries from looking like new requirements, and tell reviewers exactly which record wins when task files disagree.

At proposal time, this document stated the problem and the safety properties only. It deliberately prescribed no implementation. The implementer owned the design after validation below.

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

---

# Implementation record

## Local validation and reproduction

The runner had two independent causes:

- `harness_for()` selected the next rotation slot before the signal was checked. A missing-signal attempt therefore advanced the durable counter.
- `Run.resolve()` rebuilt `{task: <step>}` with `planned_harness()`, which always used the first rotation slot. It ignored the harness that the step actually used and could put a different model name into downstream context.

The pre-fix reproduction used a temporary two-step pipeline and a stub invocation. The first attempt returned `attempt failed before signal`; the runner raised `step developer: missing expected signal`. The rotation file advanced to `{"developer": 1}`, the retry used the second model, and the reviewer task contained the first model rather than the second.

## Design

- A rotation slot is consumed only after an accepted signal, required-artifact checks, and completion recording. Failed, blocked, and interrupted attempts retry the same harness. Rotation files are fail-closed: corrupt, negative, or unwritable counts block with an explicit repair instead of silently resetting.
- Every accepted signal first writes a versioned `.pending-commit.json` journal, then applies ledger, rotation, and resume idempotently, then clears the pending file. A crash at ledger, rotation, or resume boundaries replays without re-invoking the harness; terminal completions return without rerunning.
- `ledger.json` records the accepted `task_file`, `task_sha256`, stage fingerprint, harness, signal, `via`/`routed_to`, and all older `superseded_task_files`. It is written atomically and malformed, tampered, or out-of-run-directory records fail closed.
- Live `{task: <step>}` reads the stored task snapshot directly (stale nonce stripped, hash verified) instead of re-rendering the current stage template, so stage edits cannot alter history.
- Every live task receives an `ATTEMPT AUTHORITY` section. It names `ledger.json` as the winner, tells reviewers to ignore superseded task files and model-name differences, and leaves the old files in place for forensics.
- `mark_done` uses the same journal, records the same task pointer with hash, and ignores `*.tui.log` mirrors when selecting the run log.
- Legacy ledgers without task pointers migrate deterministically by visits (or by a single candidate) via `--migrate-ledger` with `migration-report.json`; ambiguous histories fail closed for `--mark-done` recovery and are never guessed.

## External validation

- Microsoft's retry guidance says to log early failed attempts without treating them as a new successful operation, and to keep the retry policy separate from the business attempt history: https://learn.microsoft.com/en-us/azure/architecture/patterns/retry
- W3C PROV-DM distinguishes entities, activities, and agents, and says provenance supports trust decisions. The ledger/task split follows that separation: task files are attempt history; the ledger is the completion attribution: https://www.w3.org/TR/prov-dm/
- Temporal's retry documentation treats each retry as another attempt and continues from the successful activity result. The runner applies the same rule to model rotation: a failed attempt does not consume the next slot: https://docs.temporal.io/encyclopedia/retry-policies
- Prompt-context guidance recommends labeling and curating retrieved context instead of merging raw history; the fixed authority notice and explicit ledger pointer follow that pattern: https://deepchecks.com/question/context-ordering-impact-on-llm-responses and https://www.patronus.ai/llm-reliability/ai-context

## Resolved choices

- A retry reuses the current rotation slot. The accepted attempt consumes exactly one slot, so normal completed attempts still rotate.
- Superseded task files stay in place for forensics. The ledger lists them, and live prompts explicitly subordinate them to the ledger.

## Verification

- `python3 -m py_compile private/clio-private/harness/runner.py` — passed.
- `python3 private/clio-private/harness/runner.py --self-test` — passed; checks cover failed-attempt rotation, authoritative snapshots, downstream model context, malformed authority, crash-journal recovery at each boundary, task tamper, stage-mutation snapshots, deterministic and ambiguous legacy migration, mirror filtering, rotation corrupt/negative/write-failure cases, and adversarial stale-model fixtures. Model-catalog checks remained unavailable on this host and are reported as skipped by the existing self-test.
- `python3 private/clio-private/harness/check-retry-authority.py` — passed; hermetic missing-signal and interrupt scenarios in temp dirs with no repo state.
- `python3 private/clio-private/harness/runner.py --fuzz 100` — passed.
- `python3 private/clio-private/harness/runner.py --autoexit-test` — passed.
- `python3 private/clio-private/harness/check-workers.py` — passed.
- `python3 private/clio-private/harness/github_issues.py --self-test` and `python3 private/clio-private/harness/gitsync.py --self-test` — passed.
- `python3 private/clio-private/harness/runner.py ... --dry-run` — passed.
- `python3 private/clio-private/harness/runner.py ... --audit-ledger` and `--migrate-ledger` paths exercised via legacy fixtures in self-test; ambiguous histories produce `migration-report.json` for `--mark-done` recovery.
- A hermetic stub-harness reproduction was rerun after the change: the failed attempt left no rotation-file increment, the retry used the original model, the ledger named `developer-task-r2.md` with hash, and the reviewer prompt used the exact snapshot with authority notice. A second stub run raised `KeyboardInterrupt` before the first signal, resumed, and produced the same-model retry and authoritative reviewer context.

Not verified: a live real-model retry under the interactive server harness, a human-operated tmux session, and non-macOS hosts. Corrupt rotation files now fail closed with explicit repair instead of silent reset; ambiguous legacy ledgers fail closed with explicit `--mark-done` recovery instead of guessing.

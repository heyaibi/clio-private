# AGENTS.md

## Core Principles

- **Be honest.** Never claim work is complete, tested, verified, or correct when it is not.
- **Do the work properly.** Never cut corners, skip necessary steps, or provide superficial implementations.
- **Correct me when I am wrong.** Challenge technically incorrect, incomplete, or harmful instructions. Explain why and propose a correction.
- **Do not make material assumptions.** Ask for clarification when requirements, constraints, intent, or acceptance criteria are unclear in a way that could materially affect behavior, scope, safety, or correctness. For minor implementation details, use reasonable engineering judgment.
- **Question unrealistic constraints.** If a requested constraint makes the stated requirements impossible or materially risks correctness, explain the conflict and ask for a decision. Otherwise, use reasonable engineering judgment rather than stopping unnecessarily.
- **Verify your work.** Run appropriate checks and tests when possible. Clearly state what was and was not verified.

## Branch and Pull Request Workflow (mandatory)

- **Check the branch before any code or documentation edit.** Run `git branch --show-current` first and report the branch before changing files.
- **Work on `master` by default.** Unless the user explicitly asks for a feature branch or fix branch, do not create a branch. If the current branch is not `master`, stop before editing and ask the user what to do.
- **Create a fix or feature branch only when requested.** Create it before making the requested changes, and use the branch name the user requested.
- **Use descriptive branch names.** Use `fix/<short-behavior>` for bug fixes and `feat/<short-behavior>` for features. Do not use an issue number alone; include the behavior being changed. For example, use `fix/memtree-cov-concurrent-refresh` for issue #16.
- **A fix or feature branch means a pull request is required.** Finish the branch with a pull request unless the user changes that instruction. Follow the repository's approval rules before running commit, push, or pull-request commands.
- **Work on `master` means merge and push are expected.** Do not create a branch for that workflow unless the user asks for one.

## Reproduce Before You Fix (mandatory)

A passing test is not proof that a reported bug is fixed. Reproduce the report first, then change code.

1. **Read the report and restate the symptom.** Quote the exact command and the exact error from the issue or message.
2. **Reproduce with the real entry point.** Build and run the actual binary or service, not only an in-process unit test. For this CLI: `make compile` (or `make install`) and run the reported commands.
3. **Use realistic state.** If the report can occur against existing data, reproduce against an existing database too. A fix that only works on a fresh install is not a fix.
4. **See the failure before editing.** Save the before output. Do not start refactoring or expanding scope before you have reproduced it.
5. **Re-run the same reproduction after the change.** Show before and after from the same commands and the same kind of data. Do not substitute an easier scenario and call it done.
6. **Say exactly what you ran and what you did not.** If you did not reproduce the report end to end, say so plainly and do not call the issue fixed.

A test that exercises a helper inside one process is not the same as the reported cross-process or persisted-state path. Prove the reported path.

When a fix cannot restore data that was already lost (for example, a key that was never persisted), say that explicitly and immediately. Never present a fix as making the old case work when it only changes future behavior.

## Bug Detection and Reporting (mandatory)

Finding and reporting bugs is part of every task. Do not limit bug detection to the exact code you were asked to change.

While working, actively pay attention to incorrect behavior, broken assumptions, missing validation, unsafe behavior, data corruption or loss, race conditions, error handling failures, security problems, regressions, and inconsistencies with documented behavior.

When you encounter behavior that may be a bug:

1. **Investigate it.** Do not dismiss it merely because it is outside the task.
2. **Determine whether it is actually a bug.** Check the relevant code, requirements, tests, documentation, and runtime behavior as needed.
3. **Reproduce it when practical.** Use the real entry point and realistic state. Do not claim reproduction unless you actually reproduced it.
4. **Separate facts from conclusions.** Record what you observed separately from what you believe causes it.
5. **Report confirmed unrelated bugs immediately.** Do not defer reporting until the end of the task.
6. **Report credible but unconfirmed bugs as unconfirmed.** If you cannot establish the behavior, say exactly what you observed and what remains unverified.
7. **Do not suppress a bug because fixing it would expand the task.** The scope rule controls whether you fix it, not whether you report it.
8. **Do not fix unrelated bugs.** Create the issue and continue with the assigned task unless the bug blocks the task.
9. **Do not manufacture bugs to satisfy this requirement.** Every issue must be supported by actual evidence.

### Required bug report contents

Every reported bug MUST include:

- **Summary:** one sentence describing the incorrect behavior.
- **Observed behavior:** what actually happened.
- **Expected behavior:** what should have happened and why.
- **Evidence:** the relevant command, input, output, error, test result, code path, or other evidence.
- **Reproduction:** exact steps when reproduction was possible.
- **Verification status:** clearly state whether the bug was reproduced, inferred from code, or remains unconfirmed.
- **Location:** exact file and line or the smallest relevant code location.
- **Impact:** what can go wrong and under what conditions. Do not exaggerate impact.
- **Cause:** the cause when established. If unknown, say that it is unknown.
- **Proposed fix:** the likely fix when one is reasonably clear. Do not present a guess as an established solution.

Never claim that a bug was reproduced, tested, verified, or understood when it was not.

If the evidence is insufficient to establish that the behavior is a bug, do not present it as a confirmed bug. Report it as unconfirmed only when there is enough concrete evidence to justify further investigation.

## Stay on the Task (mandatory)

Work only on the task you were given. Do not turn it into a bug-fixing session.

Bug detection and bug reporting are not scope expansion. Fixing an unrelated bug is scope expansion; reporting it is not.

- When you find an unrelated bug, **do not fix it**. Immediately create a GitHub issue that records the observed symptom, the exact file and line, how to reproduce it or clearly states that reproduction was not possible, the impact, the evidence supporting the report, and the proposed fix or investigation path.
- Do not expand scope to fix the bug, add tests for it, or refactor around it.
- If the bug blocks the task, say so and ask before changing scope.
- Keep the branch scoped to the task. A deferred bug belongs in its issue, not in this change. Revert in-progress edits for a bug you are deferring.

## Private / Public Boundary

You run from the repo root, but this file lives in `private/clio-private/` — a separate private repo (`heyaibi/clio-private`) accessible to a few people only. The root repo (`heyaibi/clio`) is public. Everything under `private/` stays on this machine and in the private remote. Never let it leak into the public repo.

What stays private — the entire `private/` directory:

- `baseline/requirement.md`, `baseline/coverage.md`, `baseline/hardware.md`, this `AGENTS.md`
- `roadmap/`, `runs/`, `harness/`, `scripts/`, `harness/dev-note.md`, `baseline/benchmark.md`, `baseline/crates.md`
- Rotation state, run ledgers, run logs, finalize logs, approval markers

What you must never do:

1. Never commit or push anything under `private/` to the public repo. The folder is git-ignored globally; never `git add -f` it and never weaken that ignore rule.
2. Never reference `private/...` paths in any public file: docs, code comments, Makefile, CI workflows, SQL, compose files. Past scrubs removed them all; keep it that way.
3. Never paste private file contents (requirement text, roadmap phases, worker prompts, run logs) into public files, issues, PRs, or CI output. CI logs are public — never `cat` a private file from a workflow step.
4. Never create root symlinks into `private/`. The root currently has exactly one — the git-ignored `AGENTS.md` convenience link. Keep it at one.
5. This `AGENTS.md` itself is private. Never copy it to the repo root.

## Glide repository

- The `glide` checkout lives at `private/clio-private/glide/`.
- It is a separate repo. The private repo ignores it with `/glide`.
- When your task touches files under `glide/`, read `private/clio-private/glide/AGENTS.md` first. Follow it for glide work.
- Glide is public. Never commit host paths, host names, phase numbers, run state, secrets, or operator docs there. When in doubt, ask.
- Host Rust rules do not apply inside `glide/`. No 450-line Rust limit, no Rust header, no `make coverage`. Use the Python rules from the glide agent file instead.
- Run git commands inside `glide/` for glide work. The private repo will not show those changes. Never force-add glide files to the private repo. Never weaken the ignore rule.

## How you write (always)

- Always use simple English. No exceptions. Not for security. Not for design. Not for onboarding.
- Start with the answer. No hello. No filler.
- Use short sentences. One idea in each sentence.
- Use a full sentence when a short phrase is unclear.
- Say what happened in plain words. Do not hide it behind a hard name.
- Say why it happened in plain words when you know why.
- Explain what the numbers mean. Do not just report numbers, percentages, or metrics.
- If you must use a hard word, explain it the first time in plain language.
- Do not use corporate, managerial, or AI-sounding language when a normal word works.
- Avoid phrases like `leverage`, `optimize the workflow`, `drive alignment`, `unlock efficiency`, `operationalize`, `surface area`, `moving forward`, `the key takeaway`, and `this suggests an opportunity to`.
- Say the actual problem directly. Do not soften it with vague language.
- Say who did what. Use I, you, and the name of the part or tool. Do not hide the actor.
- Bad: `The order was canceled.` Good: `I canceled the order.`
- Bad: `The system exhibited repeated remediation cycles.` Good: `The review ran three times because the first two fixes were rejected.`
- Bad: `This increased operational overhead.` Good: `This added 2 hours of work.`
- Bad: `There is an opportunity to optimize verification.` Good: `The checker reruns the same tests even when the code has not changed.`
- When explaining a process, tell the reader what happened first, then why it happened, then what should change.
- Separate facts from guesses. Say what you observed. Then say what you think it means.
- Keep useful technical details such as filenames, line numbers, commands, counts, timings, and identifiers. Make the explanation around them simpler instead of removing the details.
- Do not assume the reader knows internal terms. Explain a term the first time you use it.
- Use concrete examples when they make the point easier to understand.
- Do not turn a simple observation into elaborate analysis.
- If something went wrong, say why in direct terms.
- If something worked correctly, say that too. Do not weaken a check just because it found a problem.
- Write like a calm senior engineer explaining the situation to another engineer at a whiteboard.
- Ask one clear question at a time. Shape: `What should happen if X?`
- Order: 1. Correct. 2. Honest. 3. Clear. 4. Simple. 5. Short.
- Simple words beat clever words.
- Before sending, ask: `Could a busy engineer understand what happened, why it happened, and what should change after reading this once?` If not, rewrite it.

## Coverage Gate

Before starting and after completing any phase that modifies Rust crates, follow **`private/clio-private/baseline/coverage.md`**.

The workspace Makefile enforces **≥90% aggregate LLVM coverage** for functions and lines. Agents must additionally verify that **every reported Rust source file** has:

- ≥90% function coverage
- ≥90% line coverage

Run `make coverage` and follow any additional procedure required by `private/clio-private/baseline/coverage.md`.

`make coverage` is incremental (`cargo llvm-cov --no-clean`): it keeps the warm instrumented build in `target/llvm-cov-target`, so repeated gates reuse unchanged crates. Run `make coverage-clean` for an authoritative from-scratch gate after large refactors, or when per-file numbers look wrong. Raw `cargo llvm-cov` commands must also pass `--no-clean`.

Region coverage is **not** gated. Do not invent unreachable `Err` arms or process-global SQLite hacks solely to increase region coverage.

A passing aggregate coverage check is not sufficient if any individual reported file is below 90%.

## Source File Size Constraint

Every Rust source file, whether newly created or refactored, MUST remain at or below **450 total lines**.

Count all lines, including:

- File-level header comments
- Module documentation
- Imports
- Implementation code
- Tests contained within the file
- Blank lines

This is a hard constraint, not a recommendation.

Before adding substantial code to a file near the limit, estimate the resulting size and plan any required decomposition.

Never complete a change that leaves a newly created or refactored Rust source file above 450 lines.

If a change would exceed the limit:

1. Stop before introducing the violation.
2. Identify a reasonable decomposition into separate modules/files.
3. Preserve clear ownership and cohesion of each extracted component.
4. Avoid artificial line reduction through compressed formatting, removal of meaningful documentation, or omission of required tests.
5. Request approval if no clean decomposition is possible.

Existing oversized files are pre-existing violations. They are not permission to make them larger.

When modifying an existing oversized file, the agent should normally refactor it into multiple files so that the resulting files are at or below 450 lines. If no clean decomposition is possible, explain the constraint and request approval before proceeding.

## File Header

Every Rust source file MUST use the following header structure:

```rs
// Copyright 2026 Agent Memoir Developers (https://agentmemoir.com/)
// SPDX-License-Identifier: Apache-2.0
//
//! # Responsibility
//!
//! This module is responsible for <ONE clear responsibility>.
//!
//! ## Owns
//! - <thing this module is responsible for>
//! - <thing this module is responsible for>
//!
//! ## Does not own
//! - <related concern handled elsewhere>
//! - <related concern handled elsewhere>
//!
//! ## Boundary
//!
//! Changes to <responsibility> should normally require changes here.
//! Changes to <other concern> should not require changes here.
//!
//! Keep this module focused on <a single responsibility>.
````

The responsibility and ownership statements MUST accurately describe the actual module. Do not copy placeholder text into production files.

## Editing `baseline/requirement.md`

The normative requirements live in `private/clio-private/baseline/requirement.md` (singular). Treat every edit as a consistency change, not a local append.

### Before adding or changing a requirement

1. **Locate related material.** Search for related requirements, terminology, and cross-references under:
   Read the relevant passages before drafting.

   * Problem IDs (`P*`)
   * Principles (`PR-*`)
   * Sections such as `§2` tensions and `§4` mechanisms, where present
   * Functional requirements (`FR-*`)
   * Non-functional requirements (`NFR-*`)
   * Risks, glossary entries, and other referenced sections
2. **Detect conflicts.** A conflict exists if the new text would force an implementer to violate an existing `MUST`, `MUST NOT`, `SHALL`, or `SHALL NOT`, or if two requirements prescribe incompatible behavior for the same case.
3. **Do not silently override.** Never add a contradictory `MUST` or `SHALL` while leaving the old requirement standing. Do not make one rule appear to override another merely by placing it later in the document.
4. **Resolve conflicts explicitly.** Prefer one of:

   * Amend or narrow the older requirement in the same change.
   * Add a `§2` governing principle that explicitly scopes which rule applies and when, such as by attribute type, layer, automatic versus explicit tool call, or other relevant condition.
   * Ask me which rule should win, quoting the two conflicting requirements and identifying the case that creates the conflict.
5. **Keep IDs coherent.** If you change the meaning of a `PR`, `FR`, or `NFR`, update every affected cross-reference, including references in `§9` risks and the glossary. Do not cite a requirement as establishing a property that it does not state.
6. **Keep examples consistent.** Examples are illustrative, but they MUST comply with the normative requirements. Examples MUST obey `PR-2`, `§4.10`/`§4.11` `epistemic_kind` rules, and other applicable constraints. A contradictory example is a defect.
7. **Report leftovers.** After an edit, list any remaining tensions or inconsistencies you noticed but did not fix.

## Final Verification

Before declaring a phase complete:

* Verify the relevant tests and checks.
* Verify the Rust source-file size constraint for every Rust file created or refactored.
* If the phase touched Rust crates, complete the required `private/clio-private/baseline/coverage.md` procedure and verify both aggregate coverage and the per-file ≥90% function and line thresholds.
* For `private/clio-private/baseline/requirement.md` changes, verify related requirements, cross-references, IDs, examples, risks, and glossary entries for consistency.
* Review the work for bugs encountered during implementation, testing, review, and verification.
* Verify that every unrelated bug discovered during the phase has a GitHub issue, unless it was fixed within the requested scope.
* Clearly state what was verified and identify anything that could not be verified.
* If no additional bugs were found, state that no additional bugs were found during the work and briefly state what was checked.

## Agent skills

### Issue tracker

Issues live in GitHub Issues for heyaibi/clio. See `private/clio-private/issue-tracker/issue-tracker.md`.

### Domain docs

Single-context: root `CONTEXT.md` and `private/clio-private/docs/adr/`. See `private/clio-private/issue-tracker/domain.md`.

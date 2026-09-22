# AGENTS.md

## Core Principles

- **Be honest.** Never claim work is complete, tested, verified, or correct when it is not.
- **Do the work properly.** Never cut corners, skip necessary steps, or provide superficial implementations.
- **Correct me when I am wrong.** Challenge technically incorrect, incomplete, or harmful instructions. Explain why and propose a correction.
- **Do not make material assumptions.** Ask for clarification when requirements, constraints, intent, or acceptance criteria are unclear in a way that could materially affect behavior, scope, safety, or correctness. For minor implementation details, use reasonable engineering judgment.
- **Question unrealistic constraints.** If a requested constraint makes the stated requirements impossible or materially risks correctness, explain the conflict and ask for a decision. Otherwise, use reasonable engineering judgment rather than stopping unnecessarily.
- **Verify your work.** Run appropriate checks and tests when possible. Clearly state what was and was not verified.

## Private / Public Boundary

You run from the repo root, but this file lives in `private/clio-private/` — a separate private repo (`heyaibi/clio-private`) accessible to a few people only. The root repo (`heyaibi/clio`) is public. Everything under `private/` stays on this machine and in the private remote. Never let it leak into the public repo.

What stays private — the entire `private/` directory:

- `baseline/requirement.md`, `baseline/coverage.md`, `hardware.md`, this `AGENTS.md`
- `roadmap/`, `runs/`, `harness/`, `scripts/`, `dev-note.md`, `baseline/benchmark.md`, `baseline/crates.md`
- Rotation state, run ledgers, run logs, finalize logs, approval markers

What you must never do:

1. Never commit or push anything under `private/` to the public repo. The folder is git-ignored globally; never `git add -f` it and never weaken that ignore rule.
2. Never reference `private/...` paths in any public file: docs, code comments, Makefile, CI workflows, SQL, compose files. Past scrubs removed them all; keep it that way.
3. Never paste private file contents (requirement text, roadmap phases, worker prompts, run logs) into public files, issues, PRs, or CI output. CI logs are public — never `cat` a private file from a workflow step.
4. Never create root symlinks into `private/`. The root currently has exactly one — the git-ignored `AGENTS.md` convenience link. Keep it at one.
5. This `AGENTS.md` itself is private. Never copy it to the repo root.

Pushing the private repo to its own private remote is fine and expected. Pushing the root repo must only ever carry public content.

## Communication

- Speak in **plain, concise English**.
- Lead with the answer. Skip ceremony, filler, and unnecessary context.
- Prefer short, direct sentences.
- Use full sentences when a terse phrase could be unclear.
- Keep technical explanations simple. Assume the reader is smart but may not know the domain.
- Describe what actually happens, not just the name of a bug or pattern.
- Avoid unexplained jargon, acronyms, and shorthand. Define necessary technical terms once.


## Avoid Cleverness

- Act like a careful teammate, not a debate club or security paper.
- Do not use clever, adversarial, or show-off language.
- Do not stack jargon labels, fake taxonomies, or unnecessary option catalogs.
- Ask one concrete question at a time.
- Prefer: `What should happen if X?`
- Avoid dense shorthand such as: `OCO dual-fill race`, `account-global free base`, or `idempotent refill-by-sync`.
- State the actual behavior instead: `Two sell orders can fill before the system cancels one.`

## Ownership and Agency

- Use active voice and clearly identify who did what.
- Do not hide the responsible actor behind vague passive wording.
- When describing bugs or behavior, identify the responsible component, process, user action, or external system when known.

## Explanation Depth

Use terse mode by default. Switch to normal explanatory prose when needed:

- **Security findings:** Explain impact, cause, exploit conditions, fix, and relevant references.
- **Architectural disagreements:** Explain reasoning, trade-offs, and the recommendation.
- **Onboarding:** Explain why something works before giving instructions.

After explaining the necessary reasoning, return to concise answers unless the user asks for more detail.

## Priority

1. Correctness
2. Honesty
3. Clarity
4. Proper completion
5. Simplicity
6. Brevity

Plain English beats clever phrasing.

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
```

 The responsibility and ownership statements MUST accurately describe the actual module. Do not copy placeholder text into production files.

 ## Editing `baseline/requirement.md`

 The normative requirements live in `private/clio-private/baseline/requirement.md` (singular). Treat every edit as a consistency change, not a local append.

 ### Before adding or changing a requirement

 1. **Locate related material.** Search for related requirements, terminology, and cross-references under:
     Read the relevant passages before drafting.
   - Problem IDs (`P*`)
   - Principles (`PR-*`)
   - Sections such as `§2` tensions and `§4` mechanisms, where present
   - Functional requirements (`FR-*`)
   - Non-functional requirements (`NFR-*`)
   - Risks, glossary entries, and other referenced sections
2. **Detect conflicts.** A conflict exists if the new text would force an implementer to violate an existing `MUST`, `MUST NOT`, `SHALL`, or `SHALL NOT`, or if two requirements prescribe incompatible behavior for the same case.
3. **Do not silently override.** Never add a contradictory `MUST` or `SHALL` while leaving the old requirement standing. Do not make one rule appear to override another merely by placing it later in the document.
4. **Resolve conflicts explicitly.** Prefer one of:
   - Amend or narrow the older requirement in the same change.
   - Add a `§2` governing principle that explicitly scopes which rule applies and when, such as by attribute type, layer, automatic versus explicit tool call, or other relevant condition.
   - Ask me which rule should win, quoting the two conflicting requirements and identifying the case that creates the conflict.
5. **Keep IDs coherent.** If you change the meaning of a `PR`, `FR`, or `NFR`, update every affected cross-reference, including references in `§9` risks and the glossary. Do not cite a requirement as establishing a property that it does not state.
6. **Keep examples consistent.** Examples are illustrative, but they MUST comply with the normative requirements. Examples MUST obey `PR-2`, `§4.10`/`§4.11` `epistemic_kind` rules, and other applicable constraints. A contradictory example is a defect.
7. **Report leftovers.** After an edit, list any remaining tensions or inconsistencies you noticed but did not fix.

 ## Final Verification

 Before declaring a phase complete:

 - Verify the relevant tests and checks.
- Verify the Rust source-file size constraint for every Rust file created or refactored.
- If the phase touched Rust crates, complete the required `private/clio-private/baseline/coverage.md` procedure and verify both aggregate coverage and the per-file ≥90% function and line thresholds.
- For `private/clio-private/baseline/requirement.md` changes, verify related requirements, cross-references, IDs, examples, risks, and glossary entries for consistency.
- Clearly state what was verified and identify anything that could not be verified.

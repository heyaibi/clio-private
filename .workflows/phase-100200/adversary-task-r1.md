

You are the Adversary agent for the Clio project. Another agent
implemented a phase; you perform hostile, evidence-based adversarial review of
that session. You did not write the code and you must never fix it.

## Task

Here's the original prompt:

`````markdown


You are the Developer agent for the Clio project (phase 100200). You implement one
roadmap phase, exactly as specified by the task message you receive. The task
message is authoritative for scope; these rules govern how you work.

## Task

Implement Phase 100200 according to roadmap/phase-100200-additive-harness-workspace-tools.md.

Throughout the implementation, follow the `rust-best-practices`, `rust-async-patterns`, and `bloat-buster` skills.

### Phase document

- Read the whole phase file where necessary, especially "Acceptance Criteria and Evidence", "Definition of Done", and "Completion Evidence" sections, and update them with real results only.
- Treat `./roadmap/` as temporary guidance only; the isolation constraints below define the rules.

### Research

Before and during implementation:

- Conduct adequate online research to identify additional insights, best practices, technical considerations, and implementation details that could meaningfully improve the implementation.
- Apply relevant findings where appropriate.

## Before coding

- Read `AGENTS.md`, `requirement.md` (relevant sections cited by the task),
  and `crates.md` for crate structure. Read the phase file the task names.
- Check existing per-file code coverage (function and line) BEFORE changing
  anything. Run the full gate once for this baseline and save the report
  (`cargo llvm-cov --workspace --locked --json --output-path /tmp/cov-baseline.json`
  with the `DATABASE_URL` env from `./coverage.md`) so later per-file
  numbers come from re-reading it, not re-running. If any Rust file is
  already below 90% on either metric, stop and
  signal `DEVELOPER_BLOCKED` with the offending files - do not fix old debt
  unprompted.

## Hard rules

- Implement only what the task message asks. No drive-by refactors or
  reformatting.
- Every Rust file you create or modify stays at or below 450 total lines
  (including header comments and tests).
- New/modified Rust files use the exact header structure required by
  AGENTS.md, with ownership statements that match reality.
- After changing any Rust crate, follow `./coverage.md` and verify aggregate
  AND per-file coverage (>=90% function and line) before finishing.
- Roadmap isolation: never reference `./roadmap/`, phase numbers, or roadmap
  files from code or comments. The codebase must work after `roadmap/` is
  deleted.
- Do not reference `crates.md` in code comments.
- SQL: edit schema files directly; do not create migrations.
- Git: NEVER commit, push, or stash. When your work is complete, stage
  your changes with exactly `git add -- . ':!.workflows/'` - the
  pathspec excludes the pipeline run dir by construction, so run logs
  and task files can never land in the index. The next agent reviews
  the staged diff.
- Vocabulary clash or requirement conflict: stop immediately, do not guess.
  Signal `DEVELOPER_BLOCKED` with two options (2 pros, 2 cons each), naming
  your recommended option first.
- Conditional out-of-scope bullets are scope decisions, not skips. A bullet
  under "Explicitly Out of Scope" that carries a condition ("if not already
  present", "unless X") is owed work whenever its condition holds. Implement
  it if unambiguous; if implementing it is itself a scope question, stop and
  signal `DEVELOPER_BLOCKED` with two options. Never mark the phase complete
  while such an item is silently skipped.
- Known-limitations wording: every limitation states (a) what is missing or
  deferred, (b) why, and (c) which phase owns the debt. A limitation must
  never read as "implemented with boundary X" when it actually means "not
  implemented at all". If a downstream phase depends on the missing
  capability, that is a blocker, not a limitation.
- If you hit any other blocker, same protocol: two options, recommendation
  first, then stop.

## Coverage efficiency

The full gate (`make coverage`) builds and runs the whole workspace and is
slow. Never run it in a fix loop. The full gate runs exactly twice per
phase: once as the pre-change baseline (see "Before coding"), once as the
final verification before finishing.

Between those two runs, verify per file of interest, not per workspace:

- Scoped run for the crate you touched:
  `cargo llvm-cov --package <crate> --locked --summary-only` (narrow
  further with `--lib` or `--test <name>`), then read the per-file rows
  for your files. Use the same `DATABASE_URL` env as the gate so results
  are comparable.
- Or re-read the baseline JSON you saved and, after edits, one fresh
  workspace JSON run (`cargo llvm-cov --workspace --locked --json
  --output-path /tmp/cov.json`), extracting per-file rows from it instead
  of re-running.
- Batch your edits, run one scoped pass, fix, then one scoped pass to
  confirm. Same one-diagnostic-run discipline `./coverage.md` requires
  for `make check`.

## Parallel coverage work via scoped subagents

When coverage work is large (several files below 90%, or one file needing
substantial test additions), split it across subagents instead of grinding
through it serially in your own context:

- Partition by file or crate. One subagent owns one file (or one crate's
  test module). Two subagents never share a file or a test helper.
- Each subagent task states, in writing: (a) the exact files it owns,
  (b) the gate (>=90% function + line on those files), (c) the scoped
  coverage command to verify with, (d) the coding constraints (450-line
  limit, AGENTS.md header format, `*_tests.rs` naming, `PG_TEST_LOCK`
  serialization, roadmap isolation, no migrations, no git staging), and
  (e) the expected output: the files changed plus a coverage report with
  real command output for each owned file.
- Spawn subagents whose work areas are disjoint in parallel; serialize any
  that share a Postgres or SQLite fixture.
- You keep ownership: review each subagent's diff, re-verify with your own
  scoped run, then run the final full gate yourself. Phase-file updates,
  attribution, run log, and the finish signal are never delegated.

## Update the phase file

- Fill in "Acceptance Criteria and Evidence", "Definition of Done", and
  "Completion Evidence" sections with real results only.
- In "Attribution", append `| Developer | r1 | OpenCode CLI (Together . GLM-5.3 Flash High) | done |`
  (`blocked` instead of `done` if you end blocked). Leave other rows
  untouched.

## Run log

Log timestamped entries to /Users/aiuser/Documents/projects/agentmemoir/clio/.workflows/phase-100200/developer-task-r2.log as you work (fresh file for this
invocation, beside your task file): start and finish, each command with a one-line
result, and blockers with options. Never write secrets or tokens.

## Finish

Summarize: what you implemented, what you verified (real test/coverage
output), what you could not verify. The FINAL line of your reply must be
exactly one of:

- `DEVELOPER_DONE`
- `DEVELOPER_BLOCKED: <one-line reason>`

Write that same signal as the very last line of your run log (/Users/aiuser/Documents/projects/agentmemoir/clio/.workflows/phase-100200/developer-task-r2.log),
on its own line, with no timestamp prefix and nothing after it; the pipeline
matches that final log line against the exact signals above. Do it with a
tool call as your final action: `printf '%s %s\n' 'DEVELOPER_DONE' '<nonce
from the Signal nonce section at the end of your task file>' >>
/Users/aiuser/Documents/projects/agentmemoir/clio/.workflows/phase-100200/developer-task-r2.log` (or your full `DEVELOPER_BLOCKED: ...` line instead, which
needs no nonce). A chat
summary alone never counts. The "timestamped
entries" rule applies to every other log line. The pipeline parses that log
line, and nothing after the signal is read.


2026-09-20 00:44:42 START developer-task-r2 phase-100200 (resumed; prior r1 work present in tree)
2026-09-20 00:44:42 inspected state: 20 tracked + 21 new files; cargo check clean; clippy clean; fmt clean
2026-09-20 00:44:42 split oversized crates/clio-store/src/batch_tests.rs (639 lines) into batch_tests.rs/batch_pg_tests.rs/batch_test_support_tests.rs (all <=450)
2026-09-20 00:44:42 added AGENTS.md headers to 7 new *_tests.rs files
2026-09-20 00:44:42 cargo test --workspace: 875 passed
2026-09-20 00:56:14 verified resumed state: cargo check + clippy -D warnings + fmt clean; workspace tests green
2026-09-20 00:56:14 added tests/additive_tools_conformance_test.rs (mixed 7-op batch, admission rollback, scratchpad_clear, shared_retrieve/shared_discard, explicit canonical item id)
2026-09-20 00:56:14 fixed per-file function coverage: additive_tools.rs 100%, batch_preflight.rs 93.75%, batch_preflight_records.rs 100%
2026-09-20 00:56:14 cargo test --workspace: 880 passed (37 suites); cargo test -p clio-mcp: 149 passed
2026-09-20 00:56:14 make coverage exit 0: aggregate lines 94.65% functions 98.71%; no reported file below 90% funcs/lines
2026-09-20 00:56:14 updated phase-100200 Acceptance/DoD/Completion Evidence + attribution (Developer r1 done)
2026-09-20 00:56:14 all changed/new Rust files <=450 lines; no roadmap/crates.md refs in code; staging with git add -- . :!.workflows/
DEVELOPER_DONE 294c447d

`````

The developer agent (another coding assistant) has indicated that it has completed the task according to the above prompt. The files are git staged for review.

`.workflows/` is pipeline-internal and out of scope: review only
non-workflow paths with `git diff --cached -- . ':!.workflows/'`, and
never file findings on `.workflows/` entries in any git state
(staged, unstaged, or untracked).

Perform adversarial review of this session per the rules below, and write the report as instructed there.

## Review scope and method

- Review the STAGED diff (`git diff --cached -- . ':!.workflows/'`)
  plus the surrounding code it depends on - a diff-only review misses
  broken invariants in unchanged callers. Check `git status` to
  understand what is staged vs unstaged (ignoring `.workflows/` paths)
  and say so in the report.
- Verify every claim independently. Run `make test`, `make lint`, `make
  check`, and `make coverage` yourself as needed and quote real output as
  evidence. Never trust the developer's summary; re-verify it.
- Hunt for: requirement violations (against `requirement.md` and the phase
  doc's own acceptance criteria), missing or fudged acceptance criteria,
  test gaps, coverage below the 90% per-file bar, spec inconsistencies,
  unsafe changes, 450-line violations, header/ownership inaccuracies,
  roadmap-isolation violations, and unverified claims.
- Omission audit (read the phase doc the task names; the diff alone cannot
  show skipped work): enumerate every "In Scope" bullet, including
  conditionally-phrased ones ("if not already present", "unless X" — such
  bullets are owed work whenever the condition holds). Each bullet needs
  code + test evidence in the staged diff or the pre-existing repo; an
  in-scope bullet with no evidence is a high-severity finding. Every
  conditionally-phrased out-of-scope bullet must be explicitly resolved in
  the completion evidence (implemented or escalated), never silently
  skipped. Verify each "Definition of Done" checkbox against real evidence,
  and re-verify the phase's downstream guarantees ("slice N can bind X")
  by inspecting the repo for the claimed capability. A known-limitation
  that could read as "implemented with boundary X" while it actually means
  "not implemented at all" is itself a finding.

## Deliverables

- Write `findings.json` to /Users/aiuser/Documents/projects/agentmemoir/clio/.workflows/phase-100200/findings.json. Schema:

  {
    "run": "<run id from task message>",
    "phase": "<phase number>",
    "findings": [
      {"id": "F-01", "severity": "critical|high|medium|low",
       "title": "...", "evidence": "<file:line or command output>",
       "requirement_ref": "<requirement/section or null>",
       "recommendation": "..."}
    ],
    "plan_1hr": ["..."],
    "plan_unlimited": ["..."]
  }

  Validate the JSON parses before finishing. Every finding needs evidence;
  no evidence, no finding.
- If your harness provides an `/adversarial-review` skill, run it and follow
  its artifact flow (including copying HTML artifacts into /Users/aiuser/Documents/projects/agentmemoir/clio/.workflows/phase-100200);
  treat its JSON as the findings.json required above, adding any missing keys.
  Otherwise produce findings.json exactly per the schema above.
- Copy any HTML/report artifacts to /Users/aiuser/Documents/projects/agentmemoir/clio/.workflows/phase-100200. Do not modify any
  other file.
- In the phase file "Attribution", append
  `| Adversary | r1 | OpenCode CLI (OpenRouter . Deepseek V4.1 Flash Max) | done |` (`blocked` instead of `done` if
  you end blocked). That is your only edit to the phase file.

## Run log

Log timestamped entries to /Users/aiuser/Documents/projects/agentmemoir/clio/.workflows/phase-100200/adversary-task-r1.log as you work (fresh file for this
invocation, beside your task file): start and finish, each command with a one-line
result, and each finding with file:line evidence. Never write secrets or
tokens.

## Finish

The FINAL line of your reply must be exactly one of:

- `ADVERSARY_DONE findings=<absolute path to findings.json>`
- `ADVERSARY_BLOCKED: <one-line reason>`

Write that same signal as the very last line of your run log (/Users/aiuser/Documents/projects/agentmemoir/clio/.workflows/phase-100200/adversary-task-r1.log),
on its own line, with no timestamp prefix and nothing after it; the pipeline
matches that final log line against the exact signals above. Do it with a
tool call as your final action: `printf '%s %s\n' 'ADVERSARY_DONE
findings=/Users/aiuser/Documents/projects/agentmemoir/clio/.workflows/phase-100200/findings.json' '<nonce from the Signal nonce section at the
end of your task file>' >> /Users/aiuser/Documents/projects/agentmemoir/clio/.workflows/phase-100200/adversary-task-r1.log` (or your full
`ADVERSARY_BLOCKED: ...` line instead, which needs no nonce). A chat summary alone never counts.
The "timestamped
entries" rule applies to every other log line. The pipeline parses that log
line. Do not fix anything. Do not commit. Do not restage.


## Signal nonce for this invocation: `7b1a187a`

Append this nonce as a separate token after your signal word, e.g. `REMEDIATOR_DONE 7b1a187a` (use your own step's signal word; for signals with arguments put the nonce last, e.g. `ADVERSARY_DONE findings=<path> 7b1a187a`). A signal line without this exact nonce is ignored. Nonces quoted from earlier prompts are stale: use only this one. `*_BLOCKED` lines need no nonce.

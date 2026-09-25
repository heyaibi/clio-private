# Phase 100760 — manual run to-do

Attended, you plus one agent. The phase file is the reference; this is the order of work.

**Keep the phase file.** Do not delete it when done. Mark it complete like any other phase.

## Before you start

- [ ] Read the goal: `docs/extraction-fidelity.md` says undeclared non-empty leaves are rejected. `crates/clio-write/src/verify.rs` only checks declared fields. That gap is the phase.
- [ ] Decide the rule. **Reject** undeclared non-empty leaves, or **ignore** them. This is a trust decision about what a snapshot may contain. You make it, not the agent.
- [ ] Write the decision down before any code. One sentence, and why.

## 1. Reproduce first

- [ ] Build the real binary (`make compile`). Do not test in-process only.
- [ ] Run the real path with a snapshot that has an undeclared non-empty leaf. Save the command and the output.
- [ ] Confirm it commits today. That is the behavior you are changing.
- [ ] Keep the "before" output. You need it as evidence.

## 2. Implement

- [ ] Apply the chosen rule in `crates/clio-write/src/verify.rs`.
- [ ] Cover all three shapes: top-level, nested, list.
- [ ] Leave declared-field span verification and retry-once-then-refuse unchanged.
- [ ] Watch the 450-line cap on anything you touch.

## 3. Tests

- [ ] T100760-01 undeclared top-level leaf
- [ ] T100760-02 undeclared nested leaf
- [ ] T100760-03 undeclared list leaf
- [ ] T100760-04 declared-field failure still rejected (unchanged)
- [ ] T100760-05 declared valid, no undeclared leaves, still commits (unchanged)

## 4. Make the docs agree

- [ ] Update `docs/extraction-fidelity.md` to state the rule you chose.
- [ ] Re-read the module header and any doc comments you touched. All must match the code.
- [ ] State the trust rule for `entities[]` explicitly.

This is the step that burned 100606. Four of its seven round-3 rejections were comments or docs asserting things the code did not do. Check every sentence against the code.

## 5. Gates

- [ ] `make check` and `make coverage` green. Per-file ≥90% on anything you touched.
- [ ] `cargo fmt` and clippy clean.
- [ ] No new `clio-write` file over 450 lines.

## 6. Close out

- [ ] Fill the phase file DoD boxes, including "Required approval is obtained".
- [ ] Set the Attribution rows to what happened, not TBD.
- [ ] Set the status in `roadmap/index.md` to Complete.
- [ ] Attach evidence: before/after output, the decision record, test output, doc diff.

## Do not

- Do not touch span verification, entity matching, or retry policy.
- Do not touch `entities[]` or entity linking. That is 100680 and 100700.
- Do not change the snapshot schema.
- If something outside this list looks necessary, stop and ask. Do not widen scope yourself.

## Why this is cheap, and how to keep it that way

100606 stalled for twelve hours partly because the developer produced 171 files
before review started, and every remedy round then re-read all of them. Across 43
phases, developer time predicts remedy time (r = 0.46). This phase is one crate
and about seven files, so it should stay far below that.

- [ ] After your first pass, count the files you changed. If it is over roughly 20, that is a signal something wider crept in. Stop and check.

## Notes

- One crate, small. This should be a single session.
- If the agent proposes something outside the scope list, that is the signal to stop and check, not to go wider.
- Out of scope by design: any other doc/code disagreement you notice. Note it, move on.

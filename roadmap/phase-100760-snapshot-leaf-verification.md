# Phase 100760: Snapshot Leaf Verification — Reconcile Docs and Code

### Attribution
Rounds below record plan authorship; implementation sign-off is in §12.
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | OpenCode CLI (Together . GLM-5.3 Flash High) | done |
| Adversary | r1 | OpenCode CLI (Go . Space Bunny Free Max) | done |
| Remediator | r1 | Command Code (Space Bunny Alpha High) | done |
| Remedy Approver | r1 | OpenCode CLI (Go . Space Bunny Free Max) | approved |
| Finalize | r1 | Command Code (DeepSeek V4 Flash (latest) Max) | done |

**Capability phase 100760** · **Effort:** ~1–2 days · **Status:** Plan ready · **Parent:** gap analysis `gaps/recall-result-fidelity-gap-analysis.md` §9.7, §7, §10.2; requirement FR-4 / §4.4, PR-4

### Vocabulary (read first) — zero shared moniker

| Term | Meaning in this phase | Must not be confused with |
|------|------------------------|----------------------------|
| **declared field** | A snapshot leaf named in the extraction field policy and verified for span/subtype | Any key that happens to appear in the snapshot JSON |
| **undeclared leaf** | A non-empty snapshot key not in the declared field policy | A nested leaf inside a declared field |
| **fail closed** | Reject the snapshot rather than commit unverified structure | Fail open (accept and ignore) |

This phase reconciles a documentation claim with the implementation. It changes trust in the snapshot, so the chosen rule must be explicit.

---

## 1. Objective

### Goal
Resolve the disagreement between `docs/extraction-fidelity.md`, which states that an undeclared non-empty snapshot leaf fails verification, and production `verify_snapshot`, which iterates only the declared fields and never inspects unlisted leaves. Reproduce the actual behavior end to end, choose one rule deliberately (reject undeclared non-empty leaves, or ignore them), implement it, and align docs, tests, and the `entities[]` trust assumption.

### Expected Outcome
- The actual current behavior is reproduced and saved before any change (per `AGENTS.md` "Reproduce Before You Fix").
- One rule is chosen and recorded: either undeclared non-empty leaves cause verification failure, or they are explicitly ignored and the docs are corrected.
- `verify_snapshot` and `docs/extraction-fidelity.md` agree after the change.
- Tests cover the chosen rule for top-level and nested/list leaves.
- The trust level of the snapshot (and therefore the Phase 100680 `entities[]` source) is stated unambiguously.

### Parent Requirement
`requirement.md` — FR-4 / §4.4 (every entity/number/date in the snapshot MUST be grounded in a locatable source span before commit; the snapshot MUST NOT be committed unverified). Gap source: `gaps/recall-result-fidelity-gap-analysis.md` §9.7.

### Design References (source-verified at plan time)
- `docs/extraction-fidelity.md` states (around lines 132-135): "The verifier also fails closed on scope. Every other non-empty snapshot leaf, including nested and list leaves, is rejected because no typed field policy exists for it."
- Production `verify_snapshot` (`crates/clio-write/src/verify.rs:92-115`) loops `for field in fields` over the **declared** fields and never inspects undeclared leaves.
- Default field policy is `crates/clio-write/src/schema.rs:59-65`; entity verification is `crates/clio-write/src/verify_entity.rs:28`.
- This disagreement was found by reading, not reproduced with a live run; gap analysis §11 lists it as unverified. Reproduction is mandatory first.
- Sizes: `verify.rs` 151, `verify_entity.rs` 48, `schema.rs` 79.

---

## 2. Scope Boundaries

### In Scope
- Reproducing the current behavior with the real entry point and realistic state.
- Choosing and recording the single rule for undeclared non-empty leaves.
- Implementing the chosen rule (reject or explicitly ignore) and aligning docs and tests.
- Covering top-level, nested, and list leaves.

### Explicitly Out of Scope
- Changing declared-field span verification, entity/number/date matching rules, or retry policy.
- Entity extraction, `entities[]`, or entity linking (Phases 100680/100700).
- Changing admission, storage, or retrieval behavior.
- Changing the snapshot schema or adding a field policy for new types.
- Any other documented/implementation disagreement not about snapshot leaf scope.

### Must Not Change
- FR-4 span verification for declared fields (contiguous substring / parseable value).
- The retry-once-then-refuse-commit behavior.
- The non-authoritative status of the gist and the authority of the verified snapshot.
- Existing declared-field policies.
- Audit/rejection logging behavior except as the chosen rule requires.

### Scope Expansion Rule
If work outside this scope appears necessary:
1. Stop.
2. Document the reason.
3. Request clarification or approval.
4. Do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- The write/extraction path is intact and can be driven end to end with a real entry point.
- The chosen rule is decided by the owner, since it changes what the snapshot may contain.

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| `verify_snapshot` | Iterates declared fields only | `verify.rs:92-115` inspection |
| Docs claim | States undeclared leaves are rejected | `docs/extraction-fidelity.md` inspection |
| Field policy | Default fields defined | `schema.rs:59-65` inspection |
| Real entry point | The reported path can be exercised | CLI/MCP extraction run |
| Rule decision | Reject vs ignore | This phase's design record; owner approval |

---

## 4. Existing-System Discovery

The agent MUST reproduce the report before editing.

### Required Discovery
- Quote the exact doc sentence and the exact `verify_snapshot` loop.
- Build and run the real entry point; attempt to commit a snapshot with an undeclared non-empty leaf and a declared-field-valid remainder; save the before output.
- Determine whether an undeclared leaf is currently ignored, causes failure elsewhere, or is stripped before commit.
- Confirm the field policy and how declared fields are enumerated.
- Confirm existing tests that pin snapshot verification behavior.
- Confirm `verify.rs` size against the 450-line limit.

### Discovery Output
Before implementation, the agent must report:

- The exact doc sentence and its line number
- The exact `verify_snapshot` behavior with a quote
- The reproduced before output (command + result)
- Relevant subsystems identified
- Existing test coverage
- Assumptions confirmed/contradicted
- Questions requiring clarification

### Current Repository Findings at Plan Time
- Docs assert undeclared non-empty leaves are rejected; code iterates only declared fields.
- The observation is reading-level; live reproduction is required to confirm what actually happens on the real path.
- The default policy has three fields, so undeclared-leaf behavior affects any non-default snapshot content.

### Repository Adaptation Rule
The agent must determine the concrete implementation location from the actual repository. The plan requires one rule and doc/code agreement; it does not prescribe the mechanism.

---

## 5. Implementation Specification

### Task 1: Reproduce and Record the Current Behavior

#### Intent
See the actual behavior before changing anything.

#### Required Capability or Behavior
- A snapshot containing an undeclared non-empty leaf plus declared valid fields is driven through the real write/extraction entry point.
- The before output is captured and saved.
- The reproduction uses realistic state (an existing database, not only a fresh in-process test).

#### Architectural Responsibility
The verification is owned by `clio-write`; the reproduction exercises the real CLI/MCP path.

#### Required Changes
1. Capture the before output and state the exact command.
2. State plainly whether the doc claim or the code behavior is correct.

#### Implementation Constraints
- No code change in this task.
- Do not weaken any security control to reproduce.

#### Expected Result
A recorded before/after reproduction as required by `AGENTS.md`.

### Task 2: Choose and Implement the Rule

#### Intent
Make the code and docs agree on one explicit rule.

#### Required Capability or Behavior
- The owner-approved rule is implemented: either undeclared non-empty leaves fail verification, or they are explicitly ignored/stripped and documented as such.
- Declared-field span verification is unchanged.
- The failure or ignore path is deterministic and covered for top-level, nested, and list leaves.
- Rejection is logged consistently with existing rejection logging.

#### Architectural Responsibility
`clio-write` owns snapshot verification.

#### Required Changes
1. Implement the chosen rule in `verify_snapshot`.
2. Add tests for top-level, nested, and list undeclared leaves.
3. Preserve retry-once-then-refuse commit, or align logging if the rule does not reject.
4. Keep `verify.rs` ≤450 lines.

#### Implementation Constraints
- Do not change declared-field policies.
- Do not silently strip content in a way that hides a verification failure without documenting it.
- No new dependency.

#### Expected Result
An undeclared non-empty leaf either deterministically rejects the snapshot or is explicitly documented as ignored.

### Task 3: Align Documentation and State the Trust Level

#### Intent
Remove the doc/code disagreement and tell downstream consumers what the snapshot guarantees.

#### Required Capability or Behavior
- `docs/extraction-fidelity.md` matches the implemented rule exactly.
- The trust level of the snapshot (and its `entity` leaf, which Phase 100680 exposes) is stated unambiguously.
- Any other sentence in the same doc that depends on the old rule is corrected.

#### Architectural Responsibility
Docs are owned with the verification code; the phase updates both together.

#### Required Changes
1. Update the doc to the implemented rule.
2. Add or update a test pinning the documented behavior.
3. Record the trust consequence for `entities[]`.

#### Implementation Constraints
- No other documentation-scope changes.
- Keep the change scoped to snapshot leaf scope.

#### Expected Result
Docs and code agree; the `entities[]` trust assumption is grounded.

### Implementation Freedom
The agent may choose the implementation mechanism (reject vs ignore) within the owner's decision, and the test organization, provided declared-field verification is unchanged and doc/code agree.

---

## 6. Agent Execution Rules

### Allowed Actions
- Reproduce with the real entry point; modify `verify_snapshot`, its tests, and the doc.
- Record the owner's rule decision.

### Forbidden Actions
- Change declared-field span verification, retry policy, or admission.
- Change `entities[]` or entity extraction (other phases).
- Broaden the fix to unrelated doc/code disagreements.
- Delete tests, weaken security controls, or claim completion without evidence.

### Agent Decision Boundary
The agent must request approval for: choosing the rule if the owner has not decided, because it changes what the snapshot may contain; any change to declared-field policies; or any broader doc audit. The agent may decide test organization and the implementation mechanism within the chosen rule.

### Mandatory Stop Conditions
Stop and report if: the behavior cannot be reproduced end to end; the chosen rule is undecided; implementing the rule would require weakening FR-4 verification; or correctness cannot be verified.

---

## 7. Security Constraints

### Required Controls
- Verification remains fail-closed for declared-field failures.
- No content is logged on rejection beyond existing safe diagnostics.
- Bank isolation and authorization unchanged.

### Sensitive Data Rules
- Never log raw snapshot or source text on rejection.
- Never commit secrets.

### Security Acceptance Conditions
- A rejected snapshot leaves no committed snapshot and logs no raw content.
- Existing FR-4 tests remain green.

---

## 8. Test and Verification Strategy

### Required Tests
- [ ] Unit tests (undeclared top-level, nested, list leaves; declared valid remainder)
- [ ] Integration tests (real write/extraction path)
- [ ] Contract tests (declared-field verification unchanged; retry behavior)
- [ ] End-to-end tests (before/after reproduction with real state)
- [ ] Regression tests (existing snapshot tests; non-default fields)
- [ ] Security tests (no raw content on rejection)
- [ ] Failure-mode tests (mixed declared/undeclared content)

### Required Test Scenarios

| Test ID | Scenario | Expected Result |
|---------|----------|-----------------|
| T100760-01 | Undeclared non-empty top-level leaf | Chosen rule applied deterministically |
| T100760-02 | Undeclared nested leaf | Chosen rule applied |
| T100760-03 | Undeclared list leaf | Chosen rule applied |
| T100760-04 | Declared-field failure | Still rejected (unchanged) |
| T100760-05 | Declared valid, no undeclared leaves | Committed (unchanged) |
| T100760-06 | Real entry-point reproduction | Before recorded; after matches doc |
| T100760-07 | Docs vs code | No remaining disagreement |
| T100760-08 | Workspace suite, coverage, clippy, fmt, size | Green; per-file ≥90%; files ≤450 lines |

### Negative Testing
Verify no valid snapshot is newly rejected (or, if the reject rule is chosen, only undeclared non-empty leaves are), no content leaks, and declared-field failures still fail closed.

### Verification Rule
Implementation claims must be supported by actual test output, inspection results, and the before/after reproduction required by `AGENTS.md`.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-100760-01 | Current behavior reproduced with the real entry point | T100760-06 | Before output; exact command |
| AC-100760-02 | One rule chosen and recorded for undeclared non-empty leaves | Inspection | Decision record |
| AC-100760-03 | Implemented rule is deterministic for top-level, nested, and list leaves | T100760-01…T100760-03 | Test output |
| AC-100760-04 | Docs and code agree; snapshot trust stated | T100760-07 | Doc diff; test |
| AC-100760-05 | Declared-field verification and retry unchanged | T100760-04, T100760-05 | Regression test output |
| AC-100760-06 | No regression; size/coverage gates pass | T100760-08 | Workspace suite; coverage report; size check |

### Definition of Done
- [x] All in-scope behavior is implemented.
- [x] All acceptance criteria pass.
- [x] Required tests pass.
- [x] No unauthorized changes were introduced.
- [x] Existing behavior remains intact.
- [x] Security checks pass.
- [x] Documentation is updated where required.
- [x] Evidence is collected.
- [x] Verification is completed.
- [x] Required approval is obtained.

### Rule Decision Record (AC-100760-02)

The owner was asked directly during the Developer r1 run (2026-09-26), with both
options and their consequences stated, and chose **reject (fail closed)**:
every non-empty undeclared snapshot leaf — top-level, nested, or list — fails
verification, and the snapshot is not committed. This matches the pre-existing
doc claim and FR-4/§4.4 (an unverified snapshot MUST NOT be committed). The
implemented reason string is `unlisted snapshot leaf rejected`, identical to the
reference harness in `scripts/extract_quality.py`, so the cross-language
verifier contract stays aligned. Declared-field span verification, the
retry-once-then-refuse behavior, and admission are unchanged.

### Evidence (recorded r1; remedy r1 revised the rejection label, test names, and parity cases)

- **Before reproduction (AC-100760-01):** real entry point `clio mcp stdio`
  (SQLite database, existing-store runs), driver `store` tool call with
  `item.snapshot = {"entity":"Ada","amount":1000,"invented_note":"unverified
  paraphrase"}` and matching `source_text`. Result: `verify_ok`, admitted
  (`pass=true`), and `get_snapshot` returned the authoritative snapshot
  **including** `invented_note` — the undeclared leaf was ignored and committed
  unverified; the doc claim was false. Saved output: run evidence
  `before.log` alongside this phase's run record.
- **After reproduction (AC-100760-03, T100760-06):** same driver, same entry
  point: control (declared-valid only) still stored; top-level, nested
  (`invented.deep`), and list (`invented_list.0`, `invented_list.1`) undeclared
  leaves each rejected with `span_verify: <unlisted leaf #N>: unlisted snapshot
  leaf rejected` — the failure names the walk position, never the caller-supplied
  key or path, so a caller-controlled key cannot ride the rejection surface;
  nothing committed; rejection logged through the existing admission event path.
- **Tests (AC-100760-03/04/05):** `cargo test -p clio-write` 182 passed;
  `cargo test -p clio-mcp` 329+ passed (no regression). New rule coverage:
  `verify_tests.rs` — `unlisted_top_level_leaf_rejected`,
  `unlisted_nested_leaf_rejected`, `unlisted_list_leaf_rejected`,
  `unlisted_leaf_failure_never_echoes_caller_key`,
  `empty_unlisted_leaves_ignored`, `non_object_snapshot_fails`,
  `mixed_declared_and_unlisted_failures`; `ingest_tests.rs` —
  `spo_candidates_refused_under_default_fields`; `clio-mcp`
  `write_scope_tests.rs` — `store_rejects_unlisted_snapshot_leaf_and_writes_nothing`,
  `admit_preview_rejects_unlisted_snapshot_leaf`,
  `canonical_put_rejects_unlisted_snapshot_leaf`,
  `batch_store_rejects_unlisted_snapshot_leaf`,
  `tool_response_and_rejection_never_echo_the_caller_snapshot_key`; `clio-write`
  `store_path_scope_tests.rs` — `unlisted_leaf_rejection_carries_no_caller_key`.
  Declared-field matcher tests (`verify_tests.rs`, `verify_edge_tests.rs`)
  unchanged and green.
- **Parity (T100760-07):** `python3 scripts/extract_quality.py --parity` →
  20/20 cases match (both the Rust verifier and the Python reference evaluate
  every case); `--unit-only` → PASS (fidelity 1.0000). The parity cases are
  metadata only; the numbering of the positional labels is not machine-pinned
  across languages, only the pass/fail verdict is.
- **Workspace and coverage (AC-100760-06, T100760-08):** `make coverage`
  (aggregate + per-file guard) green on the committed tree — remedy r1 gate log
  `logs/remediator-coverage.log`, approver r1 re-run on the identical tree
  `logs/approver-coverage.log` (353 reported files, all ≥90% lines and
  functions; TOTAL lines 97.89%, functions 98.71%). Largest touched files:
  `write_tools.rs` 418 lines, `extract_chat.rs` 322, `verify_tests.rs` 318,
  `ingest_tests.rs` 313, `verify.rs` 230 — all ≤450. Clippy `-D warnings` and
  `cargo fmt --check` clean for the touched crates.

### Completion Evidence
- Before/after reproduction (exact commands, saved output): see "Evidence
  (recorded r1)" above.
- Rule decision record: see "Rule Decision Record (AC-100760-02)" above.
- Changed-component summary: `crates/clio-write/src/verify.rs` (undeclared-leaf
  scope check + non-object snapshot guard + positional failure label),
  `verify_tests.rs` (rule tests), `ingest_tests.rs` (fields parameter on the
  test helper; SPO fixture declared via test-only fields; new refusal test under
  production default fields), `store_path.rs` + `store_path_scope_tests.rs`
  (gated-store rejection surface), `extract_chat.rs` + `extract_chat_egress_tests.rs`
  (verify feedback scrubbed before hosted egress), `docs/extraction-fidelity.md`
  (scope paragraph aligned to implemented rule; snapshot trust level and the
  unverified correct/import tier stated), `crates/clio-mcp/src/schema_defs.rs` +
  `schema_additive_defs.rs` (snapshot description names the three allowed
  leaves), `write_tools.rs` + `write_scope_tests.rs` (tool-layer rule tests),
  `scripts/extract_quality.py` (Python mirror of the rule and the label), and
  `scripts/verifier_parity.json` (6 undeclared-leaf cases).
- Test execution output: `cargo test -p clio-write`, `cargo test -p clio-mcp`,
  parity and unit-only harness runs, `make check`, `make coverage` — all recorded
  in run logs.
- Doc diff: `docs/extraction-fidelity.md` scope and trust paragraphs.
- Verification report: this section plus the Developer r1 run log.
- Known limitations: unchanged from §12 (only snapshot leaf scope reconciled;
  the unchosen ignore behavior is explicitly not the contract).

---

## 10. Failure Handling and Recovery

### Expected Failure Modes

| Failure | Detection | Recovery |
|---------|-----------|----------|
| Behavior not reproducible | Discovery | Stop; report; do not guess |
| Rule undecided | Discovery | Stop; request the owner's decision |
| Chosen rule weakens FR-4 | Contract test | Do not implement; escalate |
| Valid snapshot newly rejected | Regression test | Narrow the rule |
| File approaches 450 lines | Size check | Decompose |

### Rollback Strategy
Revert `verify_snapshot` and the doc to the previous, documented state; no data migration is involved. If the reject rule was implemented, reverting restores the prior accepted-snapshot behavior.

### Partial Completion Policy
If the behavior is reproduced but no rule is implemented, do not claim completion. If code changes without doc alignment, do not claim completion.

---

## 11. Traceability

| Parent Requirement | Implementation Task | Verification | Acceptance Criterion |
|--------------------|---------------------|--------------|-----------------------|
| FR-4 / §4.4 (verified snapshot before commit) | Task 2 | T100760-01…T100760-05 | AC-100760-03, AC-100760-05 |
| PR-4 (snapshot authority) | Task 3 | T100760-07 | AC-100760-04 |
| Gap §9.7 (docs vs code) | Task 1, Task 3 | T100760-06, T100760-07 | AC-100760-01, AC-100760-04 |
| `AGENTS.md` reproduce-before-fix | Task 1 | T100760-06 | AC-100760-01 |
| Regression / quality contract | All | T100760-08 | AC-100760-06 |

Required chain:

```text
Requirement → Capability → Implementation → Test → Evidence
```

---

## 12. Phase Exit Contract

### Outputs Produced
- A reproduced before/after record of undeclared-leaf behavior.
- One implemented rule for undeclared non-empty snapshot leaves.
- Docs, code, and tests in agreement, with the snapshot trust level stated.

### Guarantees Provided to Downstream Phases
After this phase is accepted:
- Phase 100680's `entities[]` source (`entity`) rests on a documented, verified snapshot guarantee.
- The snapshot's scope verification is unambiguous for all consumers.

### Known Limitations
- Only snapshot leaf scope is reconciled; other doc/code disagreements are out of scope.
- The rule choice (reject vs ignore) is recorded; whichever is chosen, the other behavior is explicitly documented as not the contract.
- A caller-supplied snapshot on a span-verifying tool is limited to the declared
  extractive field set, which for the public memory-event tools is exactly
  `entity`, `amount`, and `date`. This rejects snapshots that were accepted before
  the rule, and it is a deliberate fail-closed break rather than a regression.
  There is no way for a caller to declare an extra key: a per-bank or per-tool
  field policy, or an explicit declared-path tool parameter, would be the fix and
  is not owned by this phase. Until it exists, extra content belongs in `gist`.
- Two write paths remain outside the guarantee by design: an operator correction
  (`correct`/`update`) and a bundle import commit the caller's snapshot without a
  span check. Their tier is documented rather than changed.
- An unlisted-leaf rejection identifies the offending leaf by walk position
  (`<unlisted leaf #N>`), never by its key or path, because a snapshot key is
  caller-controlled and can be sensitive. The cost is that the rejection no
  longer names the offending key, so diagnosing which leaf was refused needs the
  caller's own snapshot.

### Downstream Prerequisites
- Phase 100680 may rely on the documented snapshot trust level.
- Any future write that depends on undeclared snapshot content must use the implemented rule.

### Final Status
PASS

### Verification Sign-Off
- Implementer: Developer r1 (OpenCode CLI, GLM-5.3 Flash High); remedy r1
  (Command Code, Space Bunny Alpha High)
- Verifier: Adversary r1 (6 findings) and Remedy Approver r1 (approved; owned
  `make check` and `make coverage` runs on the identical tree, plus a fresh
  `clio mcp stdio` reproduction of the rejection and the no-key-echo property)
- Human Approver: rule decision obtained during the r1 run (owner chose
  reject/fail-closed); remedy approval recorded in approver r1
- Date: 2026-09-26

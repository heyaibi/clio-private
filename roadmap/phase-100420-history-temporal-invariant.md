# Phase 100420: History Close-Out and the Open-Edge Temporal Invariant

### Attribution
Rounds below record plan authorship; implementation sign-off is in §12.
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | [TBD] | [TBD] |
| Adversary | r1 | [TBD] | [TBD] |
| Remediator | r1 | [TBD] | [TBD] |
| Remedy Approver | r1 | [TBD] | [TBD] |
| Finalize | r1 | [TBD] | [TBD] |

**Remediation phase 100420 · **Effort:** ~3–5 days · **Gaps:** G-05, G-07, G-08, G-09 · **Source:** `gap/requirement-gaps.md` §2, §3

## 1. Objective

### Goal
Close the historical-evidence gaps and give the bi-temporal open-edge invariant a database backstop: record the missing Phase 100060 close-out verdict, run an adversary pass over Phases 003 and 005, add or prove the open-edge exclusion constraint on both backends, and decide MemTree ancestor distillation.

### Expected Outcome
- Phase 100060 has a recorded close-out verdict reconstructed from existing logs or a re-run finalize gate.
- Phases 003 and 005 have an adversary pass with findings filed and remedied or accepted.
- Two open triples for the same `(bank_id, subject, predicate)` cannot coexist on either backend, enforced by a database constraint, or a backend-impossibility proof is recorded.
- MemTree ancestor summarization has either minimal real distillation or a documented exception.

### Parent Requirement
`requirement.md` — §4.6 / FR-24 / NFR-4 (bi-temporal identity and open-edge uniqueness, "Supersession identity (normative)"), §4.3 (MemTree write path and ancestor refresh), PR-6 (invalidation not delete). Process gaps G-05 and G-07 are workflow evidence, not normative behavior.

### Design References
- §4.6 normative text: the open-edge identity key is `subject` + `predicate`; a contradicting open edge invalidates the prior edge rather than deleting it.
- `sql/001_core.sql` already carries non-unique partial indexes `triples_bank_id_subject_predicate_open_inx` (WHERE `valid_until IS NULL`) and `triples_bank_id_subject_predicate_open_both_inx` (WHERE `valid_until IS NULL AND tx_until IS NULL`); the latter is the natural unique-constraint candidate.
- Schema version is `10` in `crates/clio-store/src/migrate.rs` and seeded in `sql/001_core.sql`; schema edits are direct (no migrations) per the implement-stage rule.

---

## 2. Scope Boundaries

### In Scope
- Phase 100060 close-out verdict reconstruction or re-run.
- Adversary pass over Phases 003 and 005 with findings filed.
- The open-edge uniqueness constraint on both backends (or proof), plus a schema-version bump and tests.
- The MemTree distillation decision and, if chosen, a minimal real summarizer.

### Explicitly Out of Scope
- Reworking Phase 100060's parallel write path itself.
- Changing supersession semantics, the identity key, or `as_of` behavior.
- Broad MemTree redesign or multi-tree-per-bank restructuring.
- Any change to triples beyond the open-edge uniqueness invariant.

### Must Not Change
- Invalidation-not-delete semantics (PR-6): closing an edge sets `valid_time.end` and `transaction_time.end`; rows are retained.
- The identity key `subject` + `predicate` (bank-scoped).
- Existing `as_of` / `time_axis` query results for already-closed edges.
- The 450-line file limit and AGENTS.md headers for any Rust file touched.

### Scope Expansion Rule
If work outside this scope appears necessary: stop, document the reason, request clarification or approval, and do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- Phase 100360 accepted (coverage guard).
- Compose Postgres reachable for the two-backend constraint tests.

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| Phase 100060 run dir | Logs, findings, ledger present | `runs/phase-100060/` |
| Phases 003/005 files | Implementation plans present | `roadmap/phase-0000{3,5}-*.md` |
| Triples DDL | Partial indexes exist | `sql/001_core.sql` |
| Triple write path | Closes/inserts in a known order | `clio-store` triple tests |
| Backend parity | Postgres + SQLite both open | `make compose up mac` |

---

## 4. Existing-System Discovery

The agent MUST re-verify the following; the facts below were confirmed at plan time.

### Required Discovery
- Confirm Phase 100060 lacks `finalize-task-r1.log` while the other 30 phase dirs have it, and identify the log sources to reconstruct the verdict.
- Confirm Phases 003 and 005 adversary history and the highest-risk areas (003 ungated create path / legacy `put_item`; 005 fixtures-only live extractor).
- Confirm the current triples partial indexes and whether they are unique.
- Determine the write order in the triple supersession path: does it close the prior edge before inserting the new one within the same transaction?
- Confirm how ancestor summaries are produced today and how many episodic trees per bank exist.
- Confirm the schema-version bump mechanism.

### Discovery Output
- **006 close-out missing.** Of 31 workflow phase dirs, 30 carry `FINALIZE_DONE`; `runs/phase-100060/` has developer/adversary/approver logs plus `finalize-task-r1.md` and `ledger.json` but no `finalize-task-r1.log`.
- **003/005 predate the pipeline.** Phase 100030 shows only Developer + Adversary rows; Phase 100050 shows a fuller set. The gap flags 003 (ungated repo create path, legacy `put_item`) and 005 (fixtures-only live extractor in CI) as the highest risks.
- **No unique constraint; only non-unique partial indexes.** `sql/001_core.sql:246-255` defines `triples_bank_id_subject_predicate_inx`, `triples_bank_id_subject_predicate_open_inx` (`WHERE valid_until IS NULL`), and `triples_bank_id_subject_predicate_open_both_inx` (`WHERE valid_until IS NULL AND tx_until IS NULL`) — all with `CREATE INDEX`, none unique. Two open edges for the same `(bank_id, subject, predicate)` are prevented by code alone.
- **"Open" is defined here as both ends NULL.** The requirement's supersession rule sets both `valid_time.end` and `transaction_time.end` on invalidation, so a current edge has both `valid_until IS NULL` and `tx_until IS NULL`. This phase treats that both-NULL state as the open-edge identity case. A partially closed edge (one end set) and valid-time-range overlap are outside this constraint's predicate; if the requirement is meant to cover those, that needs a separate range/exclusion approach and operator confirmation (see Task 3).
- **Schema bootstrap uses `IF NOT EXISTS`, and there are no migrations.** `sql/001_core.sql` is applied at `open_store` (`crates/clio-store/src/bootstrap.rs:113-126`) with `SCHEMA_VERSION` asserted in `crates/clio-store/src/migrate.rs:8,111`. Consequence for Task 3: reusing an existing index name under `CREATE ... IF NOT EXISTS` is a **no-op** when that name already exists (SQLite and Postgres both document this), so a unique index must use a **new name**; and `CREATE UNIQUE INDEX` validates existing rows, so a legacy database with duplicate open edges would fail to open unless the phase handles it.
- **MemTree summaries are templates.** Ancestor summaries are not real distillations, and there is one episodic tree per bank; §4.3's "what have I tried" answers are thinner than promised.

### Repository Adaptation Rule
The agent must determine concrete implementation locations from the actual repository. The plan does not prescribe file paths or module names unless they are an externally required contract.

---

## 5. Implementation Specification

### Task 1: Phase 100060 Close-Out Verdict (G-05)

#### Intent
Restore the missing close-out record.

#### Required Capability or Behavior
- A verdict is recorded for Phase 100060, sourced from the existing developer/adversary/approver logs, `findings.json`, and `ledger.json`, or from a re-run of the finalize gate.
- The phase file's §12 and attribution reflect the verdict.

#### Architectural Responsibility
Workflow evidence and `roadmap/phase-100060-*.md` documentation only.

#### Required Changes
1. Reconstruct the verdict from the logs and record it (with the log sources cited).
2. If reconstruction is inconclusive, re-run the finalize gate.

#### Expected Result
Phase 100060 has a recorded close-out verdict.

### Task 2: Adversary Pass over Phases 003 and 005 (G-07)

#### Intent
Give the two highest-risk pre-pipeline phases independent scrutiny.

#### Required Capability or Behavior
- An adversary pass over Phase 100030 and Phase 100050 implementations, with findings filed in the standard findings shape.
- Each finding is remedied or recorded as an accepted risk.
- Highest-risk areas are explicitly examined: the ungated repo create path and legacy `put_item` (003); the fixtures-only live extractor in CI (005).

#### Architectural Responsibility
Adversary role; remediation touches the relevant crates only as findings require.

#### Required Changes
1. Run the adversary review over 003 and 005.
2. File findings; remedy or accept each.
3. Update the phase files' attribution.

#### Expected Result
003 and 005 have findings filed and dispositions recorded.

### Task 3: Open-Edge Uniqueness Constraint (G-08)

#### Intent
Back the code-only invariant with a database constraint, without breaking existing deployments.

#### Required Capability or Behavior
- On both Postgres and SQLite, two open triples with the same `(bank_id, subject, predicate)` cannot coexist, where "open" means `valid_until IS NULL AND tx_until IS NULL` (the interpretation recorded in §4).
- The constraint is enforced on a database that already exists and already carries the old non-unique index — not only on a freshly created database.
- Superseding an existing open edge succeeds: the prior edge is closed and the new edge inserted in one transaction without a constraint violation.
- After an edge is closed, a new open edge for the same subject+predicate is allowed.
- A database that already contains duplicate open edges (from an earlier bug, manual SQL, or a sync apply) fails to open with a named, actionable diagnostic — not a raw driver error — and the phase documents the operator-confirmed repair path.
- If a backend genuinely cannot express the constraint, a written proof documents why, and the code-only guard is recorded as the mitigation.

#### Architectural Responsibility
`clio-store` owns triples DDL and the write path; the schema lives in `sql/001_core.sql`.

#### Required Changes
1. Add the uniqueness as a **new-named** partial unique index (for example `triples_open_uniq` on `(bank_id, subject, predicate)` `WHERE valid_until IS NULL AND tx_until IS NULL`). Do **not** reuse the existing `triples_bank_id_subject_predicate_open_both_inx` name: `CREATE ... IF NOT EXISTS` with an existing name is a no-op, so the uniqueness would never be applied to an existing database. Decide and document the fate of the old non-unique index (leave it, or drop it after confirming query plans).
2. Add a pre-flight duplicate scan before creating the unique index: group open edges by `(bank_id, subject, predicate)` with `HAVING count(*) > 1`; if any exist, fail with a named diagnostic (count plus a sample key, never content) and document an operator-confirmed close-then-retry repair. A raw `CREATE UNIQUE INDEX` failure must not be the first the operator hears of it.
3. Verify the supersession write closes the prior edge before inserting the new one within the transaction; if it inserts first, adjust the ordering (this is the main correctness risk, and it is what makes the constraint compatible with supersession).
4. Bump `SCHEMA_VERSION` and the seeded `'schema_version'` value **together with** the two existing assertions/seed that pin them: the seed at `sql/001_core.sql:30` and the `migrate.rs:111` assertion that `SQL_CORE` contains `'schema_version', '10'`. The phase is not complete while either is stale.
5. Add two-backend tests: duplicate open edge rejected; close-then-reopen allowed; different predicate allowed; and an **existing-database upgrade test** that opens a store with the old schema (non-unique index), confirms the new unique index is present under its new name, and confirms a duplicate is rejected.
6. If infeasible on a backend, write the proof and record it.

#### Implementation Constraints
- SQL is edited directly in the schema files; no migrations.
- Invalidation remains close-not-delete (PR-6).
- The unique index must use a new name; a same-named `IF NOT EXISTS` edit is prohibited because it silently no-ops.
- Do not drop or rewrite the existing non-unique indexes without checking their query plans.
- No destructive data cleanup without operator confirmation (see the pre-existing-data policy in §12).

#### Expected Result
The invariant has a database backstop on both backends, applied to existing databases, with a safe, named failure for legacy duplicate rows; or a recorded proof.

### Task 4: MemTree Distillation Decision (G-09)

#### Intent
Decide whether ancestor summaries become real or stay templated.

#### Required Capability or Behavior
- Either a minimal real ancestor distillation (fold child summaries into ancestor text using the existing distill machinery) ships, or a documented exception states the §4.3 shortfall and the workaround.
- The decision is explicit and recorded; no silent acceptance.

#### Architectural Responsibility
`clio-write` / `clio-index` MemTree maintenance if implemented; documentation if excepted.

#### Required Changes
1. Implement minimal real distillation, or record the exception.
2. If implemented, test that a long-session "what have I tried" query returns a synthesized answer.

#### Expected Result
A recorded decision; if implemented, a passing synthesis test.

### Implementation Freedom
The agent may choose the constraint form, test placement, and distillation scope provided the invariant and boundaries are respected.

---

## 6. Agent Execution Rules

### Allowed Actions
- Reconstruct workflow evidence; run an adversary pass; edit schema DDL directly; add tests; implement minimal distillation.
- Refactor a triple write path only as needed to satisfy the ordering constraint.

### Forbidden Actions
- Run migrations; change supersession semantics or the identity key; delete triple rows on invalidation.
- Broaden the constraint beyond the open-edge identity.
- Claim completion without two-backend evidence.

### Agent Decision Boundary
The agent may decide the constraint syntax and distillation scope. The agent must request approval for changing the schema version contract in a way downstream phases depend on, or for a destructive data operation.

### Mandatory Stop Conditions
Stop and report if: the supersession write order cannot be made constraint-safe without a semantic change; a backend cannot express the constraint and the proof is inconclusive; or adversary findings require out-of-scope rework.

---

## 7. Security Constraints

### Required Controls
- Constraint tests run against a private/serialized Postgres schema per `coverage.md` §4.4.
- No destructive DDL on `public`.
- Adversary findings touching authorization must be remedied before close-out.

### Sensitive Data Rules
- Never commit secrets; test data uses synthetic subjects/predicates.

### Security Acceptance Conditions
- No test mutates shared tables destructively.
- Findings with security impact are remedied, not merely accepted.

---

## 8. Test and Verification Strategy

### Required Tests
- [ ] Unit tests (constraint-enabled write paths)
- [ ] Integration tests (two-backend duplicate/close/reopen)
- [ ] Contract tests (as_of/time_axis unchanged; invalidation still closes, not deletes)
- [ ] End-to-end tests (supersession under the constraint)
- [ ] Regression tests (workspace green)
- [ ] Security tests (adversary findings with security impact)
- [ ] Failure-mode tests (constraint violation surfaces as a structured error, not a panic; legacy duplicate rows produce a named diagnostic)

### Required Test Scenarios

| Test ID | Scenario | Expected Result |
|---------|----------|-----------------|
| T100420-01 | Insert two open edges, same bank+subject+predicate | Second rejected |
| T100420-02 | Supersede an open edge (close + insert) | Succeeds in one transaction |
| T100420-03 | Close an edge, then open the same subject+predicate | Allowed |
| T100420-04 | Open edges with different predicates | Both allowed |
| T100420-05 | Postgres and SQLite parity | Same outcomes |
| T100420-06 | `as_of` read before/after supersession | Prior belief still answerable |
| T100420-07 | Phase 100060 verdict reconstruction | Verdict recorded with log sources |
| T100420-08 | Adversary findings disposition | Every finding remedied or accepted |
| T100420-09 | MemTree decision | Implemented with a synthesis test, or exception recorded |
| T100420-10 | Open a store created with the old schema (non-unique index) | New unique index present under its new name; a duplicate is rejected on the upgraded DB |
| T100420-11 | Legacy DB already containing two open edges | Store open fails with a named diagnostic and a documented repair path, not a raw driver error |

### Negative Testing
Verify constraint violations surface as structured errors, no partial state remains, and invalidation never deletes rows.

### Verification Rule
Implementation claims must be supported by actual test output on both backends, not inspection alone.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-100420-01 | Phase 100060 verdict recorded | T100420-07 | Verdict + cited logs |
| AC-100420-02 | 003/005 adversary findings filed and dispositioned | T100420-08 | `findings.json` |
| AC-100420-03 | Duplicate open edges rejected on both backends | T100420-01, T100420-05 | Test output |
| AC-100420-04 | Supersession works under the constraint | T100420-02 | Test output |
| AC-100420-05 | Invalidation remains close-not-delete and `as_of` intact | T100420-06 | Test output |
| AC-100420-06 | MemTree decision recorded; if implemented, synthesis test passes | T100420-09 | Test output / decision note |
| AC-100420-07 | Uniqueness is enforced on a pre-existing database, not only a fresh one | T100420-10 | Test output |
| AC-100420-08 | Legacy duplicate open edges fail with a named diagnostic | T100420-11 | Test output |

### Definition of Done
- [ ] All in-scope behavior implemented.
- [ ] All acceptance criteria pass.
- [ ] Required tests pass.
- [ ] No unauthorized changes introduced.
- [ ] Existing behavior remains intact.
- [ ] Security checks pass.
- [ ] Documentation updated.
- [ ] Evidence collected and verification completed.
- [ ] Required approval obtained (schema-version change if required).

### Completion Evidence
- Implementation summary
- Schema diff and version bump
- Two-backend test output
- Adversary findings and dispositions
- Phase 100060 verdict record
- MemTree decision
- Known limitations

---

## 10. Failure Handling and Recovery

### Expected Failure Modes
| Failure | Detection | Recovery |
|---------|-----------|----------|
| Constraint breaks supersession | T100420-02 | Fix write order; do not drop the constraint |
| Backend cannot express the constraint | Discovery/test | Write the impossibility proof; keep the code guard |
| 006 verdict inconclusive | Log review | Re-run the finalize gate |
| Adversary finding needs out-of-scope rework | Findings review | Stop and request scope approval |
| `as_of` regression | T100420-06 | Revert the constraint change |

### Rollback Strategy
Revert the schema diff and the version bump; the prior non-unique indexes remain valid. No data is deleted.

### Partial Completion Policy
Do not claim completion if the constraint lands on one backend only without a proof, or if adversary findings are filed but undispositioned.

---

## 11. Traceability

| Parent Requirement | Implementation Task | Verification | Acceptance Criterion |
|--------------------|---------------------|--------------|-----------------------|
| §4.6 / FR-24 / NFR-4 (open-edge identity) | Task 3 | T100420-01…T100420-06, T100420-10, T100420-11 | AC-100420-03…AC-100420-05, AC-100420-07, AC-100420-08 |
| §4.3 (MemTree ancestor refresh) | Task 4 | T100420-09 | AC-100420-06 |
| PR-6 (invalidation not delete) | Task 3 | T100420-06 | AC-100420-05 |
| G-05 / G-07 (workflow history) | Tasks 1–2 | T100420-07, T100420-08 | AC-100420-01, AC-100420-02 |

Every acceptance criterion (AC-100420-01…AC-100420-08) is traceable to a task, a test, and a required evidence artifact; the rows above cover the full set.

Required chain:

```text
Requirement → Capability → Implementation → Test → Evidence
```

---

## 12. Phase Exit Contract

### Outputs Produced
- Phase 100060 close-out verdict.
- Adversary findings and dispositions for Phases 003 and 005.
- Open-edge uniqueness constraint (or proof) on both backends.
- MemTree distillation decision.

### Guarantees Provided to Downstream Phases
After this phase is accepted:
- The open-edge invariant is enforced by the database, not only by code.
- `as_of` and invalidation semantics remain intact under the constraint.

### Known Limitations
- MemTree ancestor summaries may remain templated if the exception is chosen.
- A backend-impossibility proof is an accepted alternative to a constraint.
- The unique index covers the both-NULL open-edge identity only; partially closed edges and valid-time-range overlap are out of its predicate (see §4).

### Pre-existing-Data Compatibility Policy (applies to Phases 042 and 052)
Any schema change in a phase that touches `sql/001_core.sql` must state and satisfy all of:
1. **New names for new objects.** A constraint or index added under an existing name via `IF NOT EXISTS` is a silent no-op on existing databases; use a new name and state the fate of the old object.
2. **Existing-data validation.** A new `UNIQUE`/constraint must be validated against existing rows before it is applied; on violation, fail with a named, actionable diagnostic and a documented operator-confirmed repair — never a raw driver error at open.
3. **Version pinning updated in the same change.** `SCHEMA_VERSION` (`crates/clio-store/src/migrate.rs:8`), the `sql/001_core.sql:30` seed, and the `migrate.rs:111` assertion move together.
4. **Upgrade test.** At least one test opens a database created with the previous schema and asserts the new object is present and effective.
Phase 100520 applies the same four rules to any schema-affecting ceiling change (for example a hygiene relevance column or index).

### Downstream Prerequisites
- No later phase may reopen or restructure triples without accounting for the unique open-edge constraint.

### Final Status
PASS | PASS WITH DOCUMENTED LIMITATIONS | BLOCKED | FAILED

### Verification Sign-Off
- Implementer: [TBD]
- Verifier: [TBD]
- Human Approver: required only for a schema-version contract change
- Date: [TBD]

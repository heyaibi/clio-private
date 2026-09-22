# Phase 100080: Bi-Temporal Triples and Supersession

### Attribution
| Role | Agent |
|------|-------|
| Developer | Cursor Agent CLI (auto) |
| Adversary | Antigravity CLI (Gemini 3.8 Flash) |
| Remediator | OpenCode CLI (Go . Deepseek V4.1 Flash High) / OpenCode CLI (Together . GLM-5.3 Flash High) |
| Remediator (r2) | OpenCode CLI (GLM-5.3 Flash High) / Hermes CLI (GLM-5.3 Flash High) |
| Remediator (r3) | OpenCode CLI (Go . Deepseek V4.1 Flash High) / OpenCode CLI (Together . GLM-5.3 Flash High) |
| Remedy Approver | Antigravity CLI (Gemini 3.8 Flash) |

**Index slice 100080 · **Effort:** `1×` · **Scope:** `roadmap/index.md` slice 100080 (authoritative)

## 1. Objective

### Goal
Implement subject–predicate–object edges with **valid-time** and **transaction-time**, supersession via **invalidation (not delete)**, and point-in-time query (`as_of`, `time_axis`) (§4.6 / PR-6 / FR-12 / FR-24 / NFR-4). **Identity key for open-edge supersession is `subject`+`predicate`** (object is the changing payload—see appendix). On supersede/retract, close **both** time axes on the prior edge. Reject continuous/scalar updates on this path (PR-2 / FR-11 foreshadow; full EMA engine is slice 100090).

### Expected Outcome
- Durable SPO triples aligned with §7.2, including `epistemic_kind`, optional `source_type` for beliefs, half-open `valid_time` / `transaction_time`, and optional `snapshot_ref` / `gist_ref`.
- `triple_add` writes a gated edge; default supersede closes prior open edges for the same **subject+predicate** (not subject+object).
- `triple_end` expires SPO edges; `invalidate(item_id)` closes item-shaped discrete records—both retain history.
- `triple_query` supports pattern match and point-in-time via `as_of` + `time_axis` (`valid` default | `transaction`), including cases where the two axes diverge after late correction.
- Continuous/scalar payloads on the triple/invalidation path are rejected with a structured error pointing at the continuous update model (slice 100090).
- Ops `discard` remains a separate path and is **not** implemented as silent supersession.

### Parent Requirement
`requirement.md` (current) — P10, PR-2, PR-6, §4.6 (supersession identity + dual-axis close), §4.9.4.A `invalidate` / `update` update_rule split, §4.9.4.E `triple_*`, §7.2, FR-11, FR-12, FR-15 spirit, FR-24, NFR-4. Interval algebra: `roadmap/phase-100080-appendix-bitemporal-intervals.md`.

### Design references (non-normative)
- Agent-memory bi-temporal edges + invalidate-don’t-delete: [Graphiti temporal model](https://getzep-graphiti.mintlify.app/concepts/temporal-model); implementation: [edge_operations.py](https://github.com/getzep/graphiti/blob/main/graphiti_core/utils/maintenance/edge_operations.py).
- Half-open intervals and assert/retract/correct operators: [TGMS](https://arxiv.org/html/2607.10265).
- Contradiction = same subject+predicate, different object, overlapping valid time: [TOKI](https://arxiv.org/html/2606.06240).
- Classical bi-temporal RDF constraints: [BiTemporal RDF](https://www.mdpi.com/2227-7390/13/13/2109).

---

## 2. Scope Boundaries

### In Scope
- Triple record model with bi-temporal half-open intervals (§7.2 / appendix).
- Tools (in-process OK): `triple_add`, `triple_query`, `triple_end`, and `invalidate(item_id, replacement_id?)` for **item-shaped** discrete records (not as a substitute for `triple_end`).
- Default supersession on `triple_add` when `supersede` defaults true: close prior open **subject+predicate** edges on **both** time axes.
- Point-in-time reads: `as_of` + `time_axis`, including divergent-axis fixtures (appendix §4.3).
- Rejection of continuous/scalar update attempts on this discrete path (FR-11).
- Gating: `triple_add` MUST pass Phase 100040 episodic admission path (type `triple`) / matrix (§4.9.3).
- Telemetry on add/invalidate/end with prior/new id linkage (FR-15 spirit).
- Optional link to Phase 100050 snapshots via `snapshot_ref`.

### Explicitly Out of Scope
- Shared continuous EMA update engine (slice 100090).
- Belief confidence trajectories UI/`belief_observe` (slice 100100)—`epistemic_kind=belief` field MAY be stored; trajectory API not required for exit.
- Co-activation association weights (slice 100130).
- Persona stable/preference objects (slice 100140)—but discrete persona will later reuse invalidation semantics.
- MemTree structural maintenance (slice 100070) except optional cross-links; triples are not MemTree nodes.
- Hybrid retrieve orchestration (slice 100120)—`triple_query` is the graph pattern/as-of API.
- Compliance erase / crypto-shred (slice 100190).
- `discard` full ops tool if not already present—do not implement delete-as-supersede.

### Must Not Change
- PR-6: supersession never deletes the prior edge.
- PR-2: discrete invalidation and continuous EMA stay separate mechanisms.
- Phase 100040 gates on long-term triple writes.
- Phase 100020 encryption for any content payloads referenced by triples.
- Leaf-first episodic readability from slices 100060–7.

### Scope Expansion Rule
If work outside this scope appears necessary:
1. Stop.
2. Document the reason.
3. Request clarification or approval.
4. Do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- Phase 100040 accepted: gated writes + episodic type `triple`.
- Phase 100020–003 accepted: durable storage; items for snapshot_ref targets.
- Phase 100050 recommended when snapshot_ref used for exact values.
- Phase 100060–007 helpful but not strictly required for triple CRUD; discover whether graph metadata tables already exist from Phase 100020.

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| Gated write / episodic admit | `triple` type path works | Phase 100040 tests |
| Persistence | Can store graph edges + intervals | Phase 100020 |
| Clock / time source | Deterministic in tests | Injectable clock |
| Telemetry | Can emit invalidate/add events | Assert in tests |

---

## 4. Existing-System Discovery

The agent MUST inspect the existing system before deciding
where or how to implement the changes.

### Required Discovery
- Identify the subsystem(s) responsible for the relevant behavior.
- Locate the existing implementation of related capabilities.
- Identify existing interfaces, contracts, schemas, and boundaries.
- Identify relevant tests and verification mechanisms.
- Identify architectural conventions that must be followed.
- Confirm that the current system supports the proposed change.
- Check Phase 100020 graph-metadata hooks and any placeholder triple tables.

### Discovery Output
Before implementation, the agent must report:

- Relevant subsystems identified
- Existing implementation approach
- Relevant contracts/interfaces
- Existing test coverage
- Architectural constraints discovered
- Assumptions confirmed
- Assumptions contradicted
- Questions requiring clarification

### Repository Adaptation Rule
The agent must determine the concrete implementation locations
from the actual repository. The plan does not prescribe file paths,
class names, module names, or directory structures unless they
are explicitly part of an externally required contract.

---

## 5. Implementation Specification

### Task 1: Bi-Temporal Triple Data Model

#### Intent
Persist SPO edges with valid-time and transaction-time intervals (§4.6 / §7.2).

#### Required Capability or Behavior
- Fields: subject, predicate, object, epistemic_kind, source_type (required iff belief), valid_time{start,end}, transaction_time{start,end}, confidence?, snapshot_ref?, gist_ref?, bank, ids.
- **Intervals:** half-open `[start, end)` per appendix; `end = null` open-ended.
- Indexes supporting subject/predicate lookups and as-of filters on both axes.
- Dual-backend behavioral parity.
- Invariant: under overlapping transaction time, open valid intervals for the same subject+predicate MUST NOT overlap after a successful supersede transaction.

#### Architectural Responsibility
Graph / triple repository on Phase 100020 storage.

#### Required Changes
1. Schema/migrations for triples with both interval pairs.
2. Repository create/read/update-interval (no hard delete on supersede path).
3. Enforce half-open as_of predicate in one shared helper used by all queries.

#### Implementation Constraints
- Never DELETE row on supersession; only close intervals.
- Ciphertext rules apply to any embedded content blobs; refs preferred.

#### Expected Result
Round-trip persist; inspection shows closed prior edge still present.

### Task 2: `triple_add` with Default Supersede

#### Intent
Write new edges and supersede prior open subject+predicate facts (FR-12).

#### Required Capability or Behavior
- `triple_add(..., supersede?, valid_from?, valid_until?, ...)` gated via Phase 100040.
- Default `supersede=true`: find open edges matching **subject+predicate** (bank-scoped); set **both** `valid_time.end` and `transaction_time.end` on each prior edge; insert new edge atomically (appendix §3–§4.1).
- `supersede=false` allows coexistence only when intervals make it legal; otherwise reject with structured error.
- Span-verify snapshots if creating/linking snapshot content via extract path.

#### Architectural Responsibility
Triple write service + admission integration.

#### Required Changes
1. Gated add API.
2. Supersession transaction: dual-axis close old + insert new atomically.
3. Telemetry event for add + invalidate side effects (prior_edge_id, new_edge_id).

#### Implementation Constraints
- Atomicity: no window where two contradicting open edges share subject+predicate after commit.
- Do not call ops discard.
- Belief vs fact: enforce FR-14 source_type rules on belief epistemic_kind triples.
- Object is never part of the identity key for default supersede.

#### Expected Result
Add “lives_in Boston” then “lives_in NYC” → one current edge NYC; Boston edge retained with **both** intervals closed; as_of on valid vs transaction axes behaves per appendix examples.

### Task 3: `triple_end` and `invalidate(item_id)`

#### Intent
Expire without replacement; close both axes without erase (PR-6). Keep tool identities distinct (appendix §5).

#### Required Capability or Behavior
- `triple_end(subject, predicate, object?, valid_until?)` closes matching **open SPO** edge(s) by setting both `valid_time.end` and `transaction_time.end`.
- `invalidate(item_id, replacement_id?)` closes both time axes on an **item-shaped** discrete record (Phase 100030 item / persona-stable style ids)—MUST NOT be overloaded as the only SPO API; SPO expiry uses `triple_end`.
- Both emit telemetry with optional `replacement_id` / prior linkage.
- Idempotent end on already-closed targets: documented no-op success or structured already_ended.

#### Architectural Responsibility
Mutator path (matrix: N/A for category scoring; still FR-11 `update_rule` enforcement + audit).

#### Required Changes
1. `triple_end` and `invalidate(item_id)` as separate handlers.
2. Tests that rows remain selectable for history.
3. Test that calling `invalidate` with a triple edge id is rejected or clearly routed—prefer reject with hint to use `triple_end`.

#### Implementation Constraints
- Invalidation ≠ compliance erasure.
- Invalidation ≠ hygiene discard.
- Do not DELETE.

#### Expected Result
After end/invalidate, current as-of now returns empty for that fact; historical as-of still returns the edge/item.

### Task 4: Point-in-Time `triple_query`

#### Intent
Satisfy NFR-4 / FR-24 for discrete facts via `as_of` + `time_axis`.

#### Required Capability or Behavior
- `triple_query(subject?, predicate?, object?, as_of?, time_axis?)`.
- `time_axis=valid` (default): edge included if valid interval contains `as_of` (or is open and started ≤ as_of).
- `time_axis=transaction`: edge included if transaction interval contains `as_of`—“what did the system believe/record then.”
- Omitting `as_of` means “current” on that axis (document exact current definition).
- Pattern wildcards: missing SPO fields are unconstrained.

#### Architectural Responsibility
Query engine over triple repository.

#### Required Changes
1. Filter predicates for both axes.
2. Deterministic ordering for stable tests.
3. Bank scoping.

#### Implementation Constraints
- Explicit `triple_query` runs even if a future intent gate would skip background retrieve (FR-24).
- Do not require MemTree for triple as-of.

#### Expected Result
Fixture timeline answers “true then” and “believed then” differently when valid vs transaction diverge (e.g. late correction).

### Task 5: Reject Continuous/Scalar Updates on This Path

#### Intent
Enforce PR-2 / FR-11 boundary early: discrete triple path must not accept EMA-style updates.

#### Required Capability or Behavior
- If `update(..., update_rule=continuous)` or a numeric preference-style payload is directed at the triple/invalidation API, return structured error `{code: wrong_update_rule, ...}`.
- Attribute schemas that declare `update_rule=continuous` MUST NOT be written via `triple_add` supersession blending.
- Discrete path remains invalidation-only.
- Do not confuse `epistemic_kind` (`fact`|`belief`) with `update_rule`—see `requirement.md` §10.

#### Architectural Responsibility
Write-path `update_rule` guard (shared with future slice 100090 splitter).

#### Required Changes
1. Class guard on triple mutators / generic update entry if exposed.
2. Tests for rejection.
3. Error message points to continuous engine (slice 100090) without implementing EMA.

#### Implementation Constraints
- Do not silently coerce a float affinity into an SPO object string without policy—reject or require explicit discrete object string.
- Do not implement EMA here.

#### Expected Result
Continuous update attempt fails closed; discrete supersession still works.

### Implementation Freedom
The agent may choose the concrete implementation structure,
file locations, naming, and internal design provided that:
- The required behavior is satisfied.
- Architectural boundaries are respected.
- Existing contracts are preserved.
- All acceptance criteria pass.
- No prohibited changes are introduced.

---

## 6. Agent Execution Rules

### Allowed Actions
- Inspect and modify the repository as required to implement
  the in-scope capabilities.
- Add or update implementation components where appropriate.
- Add or update tests required to verify the behavior.
- Refactor locally when necessary to implement the specified
  capability without changing unrelated behavior.

### Forbidden Actions
- Change public contracts without approval.
- Delete or bypass tests.
- Disable security controls.
- Introduce unrelated features.
- Perform unrelated broad refactoring.
- Upgrade dependencies without approval.
- Commit secrets.
- Claim completion without evidence.
- Implement supersession as DELETE.
- Implement EMA in this phase.

### Agent Decision Boundary
The agent may decide:
- Concrete file/module/class placement.
- Char vs byte offsets only where referenced from snapshot_ref tooling.
- Test organization.
- Non-breaking implementation details.

The agent must request approval for:
- Architecture changes beyond the stated scope.
- Breaking API or data-contract changes.
- Security-sensitive policy decisions.
- Destructive data operations.
- Changes affecting downstream phase assumptions.
- Soft-deleting edges while claiming PR-6 compliance.
- Changing supersession identity away from subject+predicate.
- Collapsing `invalidate` and `triple_end` into one overloaded API.

### Mandatory Stop Conditions
Stop and report if:
- Requirements are ambiguous.
- Repository facts contradict the plan.
- Required dependencies are missing.
- Scope expansion is required.
- A destructive migration is necessary but unspecified.
- Existing architecture cannot support the intended behavior
  without an unapproved structural change.
- Correctness cannot be verified.
- As-of queries cannot distinguish valid vs transaction axes with the chosen schema.

---

## 7. Security Constraints

### Required Controls
- Triple writes bank-scoped; gated admission on add.
- Actor attribution on add/end/invalidate.
- Belief source_type enforced when epistemic_kind=belief.

### Sensitive Data Rules
- Never log DEKs; mask secrets in subject/object if they look like credentials.
- Never commit secrets.
- Snapshot refs must not bypass encryption on the referenced item.

### Security Acceptance Conditions
- Cross-bank triple_query fails closed.
- Supersession cannot delete history rows.

---

## 8. Test and Verification Strategy

### Required Tests
- [ ] Unit tests
- [x] Integration tests
- [x] Contract tests
- [ ] End-to-end tests
- [x] Regression tests
- [ ] Security tests
- [x] Failure-mode tests

### Required Test Scenarios

| Test ID | Scenario | Expected Result |
|---------|----------|-----------------|
| T100080-01 | `triple_add` new edge | Persisted with open valid/transaction ends |
| T100080-02 | Superseding add same subject+predicate | Prior edge closed on **both** axes, not deleted; new edge current |
| T100080-03 | `triple_query` as_of on valid axis | Returns fact true at that world time |
| T100080-04 | `triple_query` as_of on transaction axis | Returns what system recorded/believed then |
| T-04b | Late correction fixture (appendix §4.3) | Valid-axis and transaction-axis as_of **diverge** as specified |
| T100080-05 | `triple_end` | Edge no longer current; both axes closed; history retained |
| T100080-06 | `invalidate(item_id)` | Item validity+transaction closed; row remains; not an SPO delete |
| T100080-07 | Continuous/scalar update on triple path | Structured `wrong_update_rule` error |
| T100080-08 | `triple_add` without gates | Impossible / rejected |
| T100080-09 | Belief triple without source_type | Rejected (FR-14) |
| T100080-10 | Dual-backend parity sample | Same as-of results on Postgres and SQLite |
| T100080-11 | Concurrent supersede same key | One winner open; no double-open contradiction (transactional) |
| T100080-12 | Telemetry on invalidate/add | Event observable |

### Negative Testing
Verify that:
- Invalid SPO / intervals are rejected.
- Unauthorized bank actions are blocked.
- Partial failures roll back supersede transactions.
- Duplicate end is safe per documented idempotency.
- Existing item/MemTree behavior remains intact.
- Failure does not DELETE superseded edges.

### Verification Rule
Implementation claims must be supported by actual test output,
inspection results, or other concrete evidence.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-100080-01 | Bi-temporal SPO model persisted | T100080-01, T100080-10 | `t01_triple_add_persists_open_ends`, `t10_postgres_as_of_parity_sample` PASS; `triples` indexes in `sql/001_core.sql` (schema_version `4`) |
| AC-100080-02 | FR-12 supersession via dual-axis invalidation not delete | T100080-02, T100080-06 | `t02_supersede_closes_both_axes_not_delete`, `t06_invalidate_item_not_spo` PASS (prior rows retained, both axes closed) |
| AC-100080-03 | FR-24 / NFR-4 as_of + time_axis (incl. divergent axes) | T100080-03, T100080-04, T-04b | `t03_t04_t04b_as_of_axes_diverge_on_late_correction` PASS |
| AC-100080-04 | `triple_end` / `invalidate` retain history | T100080-05, T100080-06 | `t05_triple_end_retains_history`, `t06_invalidate_item_not_spo` PASS |
| AC-100080-05 | FR-11 continuous rejected on this path | T100080-07 | `t07_continuous_rejected` (store) + `t07_t12_continuous_and_telemetry` (write) → `wrong_update_rule` PASS |
| AC-100080-06 | Gated `triple_add` | T100080-08, T100080-09 | `t08_ungated_impossible_via_triple_add`, `t09_belief_requires_source_type` PASS |
| AC-100080-07 | Atomic supersede under concurrency | T100080-11 | `t11_concurrent_supersede_one_open` PASS |
| AC-100080-08 | Telemetry on mutators | T100080-12 | `t07_t12_continuous_and_telemetry` PASS (add/invalidate/end events with prior/new linkage) |

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

### Completion Evidence
- **Implementation summary:** Bi-temporal SPO triples with half-open `[start,end)` valid/transaction intervals; `triple_add` (gated episodic `triple` via admission) supersedes by closing prior open **subject+predicate** edges on both axes; `triple_query` with `as_of` + `time_axis`; `triple_end` and item `invalidate` retain history; continuous/scalar path rejects with `ErrorCode::WrongUpdateRule`. Dual-backend store CRUD (SQLite + Postgres) via atomic `commit_triple_add`.
- **Discovered/affected architectural components:** `clio-types` triple model; `clio-store` Store trait + SQLite/Postgres triple write/read; `clio-write` tools; `clio-lib` re-exports; `sql/001_core.sql` triple indexes / schema_version `4`.
- **Changed-component summary:** New `clio-types/src/triple.rs`; store `sqlite_triple*`, `postgres_triple*`, `triple_map`, dual-backend tests; `clio-write/src/triple.rs` + clio-store dependency; WrongUpdateRule error code.
- **Test execution output:** `cargo test -p clio-store -p clio-write --lib triple` → 17 PASS (T100080-01..T100080-12 + guards); `make check` PASS earlier in run; `make coverage` PASS — TOTAL functions **99.38%** lines **98.59%**; every reported file ≥90% functions and lines (incl. `sqlite_triple.rs` / `postgres_triple.rs` at 100% functions after map_err/belief hits).
- **Interval convention note:** Half-open `[start, end)` on both axes; open end represented as NULL/`None`; as_of membership is `start <= as_of < end` (or open).
- **Verification report:** Late-correction fixture diverges valid vs transaction as_of; PG/SQLite parity sample matches; concurrent supersede leaves one open edge; ungated add rejected; belief without `source_type` rejected.
- **Known limitations:** Continuous EMA engine deferred to later slice; ops `discard` not implemented as supersession; no exclusion-constraint DDL beyond transactional supersede + open-edge query; in-process tools (no separate HTTP surface).

---

## 10. Failure Handling and Recovery

### Expected Failure Modes

| Failure | Detection | Recovery |
|---------|-----------|----------|
| Supersede race | Unique/exclusion constraint or txn conflict | Retry transaction; ensure single open edge |
| Invalid interval (end &lt; start) | Validation | Reject write |
| Missing snapshot_ref target | FK / existence check | Reject or allow dangling per documented rule—prefer reject |
| Gate/verify fail | Admission/verify | No edge written |

### Rollback Strategy
Revert code; interval-closed edges remain valid history (safe). Avoid migrations that DELETE historical edges. If schema must change, additive columns preferred.

### Partial Completion Policy
If only part of the phase is complete:
- Do not claim full completion.
- Record completed and incomplete work separately.
- Document remaining work.
- Do not leave undocumented broken state.

---

## 11. Traceability

| Parent Requirement | Implementation Task | Verification | Acceptance Criterion |
|--------------------|---------------------|--------------|-----------------------|
| §4.6 / §7.2 bi-temporal | Task 1 | T100080-01 | AC-100080-01 |
| FR-12 / PR-6 supersession | Tasks 2–3 | T100080-02, T100080-06 | AC-100080-02 |
| FR-24 / NFR-4 as_of | Task 4 | T100080-03, T100080-04 | AC-100080-03 |
| §4.9.4.E triple_end | Task 3 | T100080-05 | AC-100080-04 |
| FR-11 / PR-2 `update_rule` split | Task 5 | T100080-07 | AC-100080-05 |
| §4.9.3 gated triple_add | Task 2 | T100080-08, T100080-09 | AC-100080-06 |
| FR-15 spirit telemetry | Tasks 2–3 | T100080-12 | AC-100080-08 |
| Dual-backend parity | Task 1 | T100080-10 | AC-100080-01 |

Required chain:

```text
Requirement → Capability → Implementation → Test → Evidence
```

Every acceptance criterion must be traceable.

---

## 12. Phase Exit Contract

### Outputs Produced
- Bi-temporal triple store with invalidation-based supersession.
- `triple_add` / `triple_query` / `triple_end` / `invalidate`.
- Point-in-time query on valid and transaction axes.
- Hard reject of continuous updates on the discrete path.

### Guarantees Provided to Downstream Phases
After this phase is accepted:
- Slice 100090 can own EMA without overlapping invalidation semantics.
- Slice 100100 can attach belief trajectories to propositions without changing supersession rules for facts.
- Slice 100120 retrieve can pass `as_of` / `time_axis` through to triple/graph search.
- Slice 100140 `persona_put_stable` can reuse invalidation patterns.
- Slice 100180 `audit_trail` can read invalidation history already stored.

### Known Limitations
- EMA / continuous engine not implemented (slice 100090).
- `belief_observe` / full confidence trajectory API not required here (slice 100100).
- Co-activation graph weights not implemented (slice 100130).
- Full `audit_trail` tool UX deferred (slice 100180).
- Interval examples and operator algebra live in `roadmap/phase-100080-appendix-bitemporal-intervals.md` (normative for this phase).

### Downstream Prerequisites
- Slice 100090 MUST reject discrete invalidation on continuous attributes (symmetric to Task 5).
- Slice 100120 MUST honor FR-24 args when wiring hybrid retrieve.
- Compliance erase MUST NOT use supersession (slice 100190).

### Final Status
PASS | PASS WITH DOCUMENTED LIMITATIONS | BLOCKED | FAILED

### Verification Sign-Off
- Implementer: [Name/Agent]
- Verifier: [Name/Agent]
- Human Approver: [Name, if required]
- Date: [YYYY-MM-DD]

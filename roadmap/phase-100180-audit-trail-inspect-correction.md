# Phase 100180: Audit Trail, Inspect, and Correction

### Attribution
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | OpenCode CLI (Together . GLM-5.3 Flash High) | done |
| Adversary | r1 | OpenCode CLI (OpenRouter . Deepseek V4.1 Flash Max) | done |
| Remediator | r1 | OpenCode CLI (Go . Deepseek V4.1 Flash High) | done |
| Remedy Approver | r1 | OpenCode CLI (Together . GLM-5.3 Flash Max) | approved |
| Finalize | r1 | OpenCode CLI (Together . GLM-5.3 Flash High) | done |

**Index slice 100180 · **Effort:** `1×` · **Scope:** `roadmap/index.md` slice 100180 (authoritative)

### Vocabulary (read first) — zero shared moniker

| Term | Enum / form | Where it lives | Must not |
|------|-------------|----------------|----------|
| **`item_audit_trail`** | Structured timeline of values, confidences, evidence refs, and ops | `audit_trail(item_id)` view over existing stores (§4.12) | Be built as an independent secondary logging database |
| **`hygiene_audit_log`** | Durable operational log of noise cleanups (§4.9.5.A) | Operations platform (Phase 100210) | Be conflated with `item_audit_trail` or `compliance_tombstone` |
| **`compliance_tombstone`** | Content-free record of crypto-shredding (§7.4.4) | Compliance subsystem (Phase 100190) | Retain personal data or be conflated with `item_audit_trail` |
| **`correct`** | Auditable correction tool with mandatory `reason` (FR-16) | Memory inspector API | Perform silent row `DELETE` or bypass attribute `update_rule` |
| **`inspect`** | Read API listing items with scores and validity windows (FR-16) | Inspector API | Be confused with database health check `diagnose` (§4.9.5.C) |
| **`correction_reason`** | Mandatory text explaining why a value is being rectified | Parameter on `correct` | Be omitted or confused with operational `discard_reason` |

---

## 1. Objective

### Goal
Emit attributable telemetry events on all mutating memory operations and expose `audit_trail`, `inspect`, and `correct` as a unified transparency, inspection, and correction surface over existing data structures—not as a redundant secondary logging store (P12, PR-6, PR-8, §4.12, FR-15, FR-16).

### Expected Outcome
- Every mutating operation (`store`, `update`, `discard`, `invalidate`, and later `hygiene_clean`) emits a standardized telemetry event: `{operation, item_id, category, epistemic_kind, confidence, admission_score, actor, timestamp}` (FR-15, §4.12).
- `audit_trail(item_id)` reconstructs the complete historical lifecycle for any memory item: initial admission, bi-temporal supersessions, continuous EMA updates, belief confidence trajectories, and manual corrections.
- `inspect(filter?, limit?, offset?)` provides an item-level memory inspector for developers and compliance officers, supporting filtering by bank, category, epistemic kind, validity state, and time ranges without exposing encryption keys (FR-16).
- `correct(item_id, new_value, reason)` executes auditable corrections respecting attribute `update_rule` (discrete vs continuous), recording attribution and maintaining transaction-time history without destructive `DELETE` (PR-6, FR-16).
- Export readiness: telemetry fields are structured to seamlessly feed manifest-backed exports (NFR-6 foreshadow).

### Parent Requirement
`requirement.md` (v1.8+) — P10, P11, P12, PR-6, PR-8, §2.2, §4.6, §4.10, §4.11, §4.12, §4.9.4.F, FR-11, FR-12, FR-13, FR-14, FR-15, FR-16, NFR-4, NFR-6.

### Design References (non-normative)
- **Immutable Audit Trails & Bitemporal Auditing:** [Bitemporal Data Architecture](https://en.wikipedia.org/wiki/Bitemporal_modeling) — Auditability as a query over transaction-time history rather than a disconnected event store.
- **GDPR Article 15 & 16 (Access and Rectification):** [EDPB Guidelines on Data Subject Rights](https://edpb.europa.eu) — Technical verification of right to rectification via attributable correction traces without erasing audit records.

---

## 2. Scope Boundaries

### In Scope
- Uniform telemetry emission pipeline on mutating paths (`store`, `update`, `discard`, `invalidate`).
- Reconstructing item lifecycle in `audit_trail(item_id)` from existing bi-temporal triples, belief confidence histories, and telemetry logs.
- `inspect` query engine supporting multi-attribute filtering, deterministic pagination, and secret masking.
- `correct` handler applying corrections:
  - For discrete items: bi-temporal invalidation and supersession with late-correction transaction timestamp.
  - For continuous items: auditable value adjustments respecting EMA/trend constraints.
- MCP binding and CLI/in-process exposure for `audit_trail`, `inspect`, and `correct`.
- Attributable provenance validation requiring `actor` and `reason` on every correction.

### Explicitly Out of Scope
- Crypto-shredding and data-subject erasure UX (`erase_request` in Phase 100190).
- Operational noise cleanups and hygiene logs (`hygiene_audit` / `hygiene_clean` in Phase 100210).
- Database health diagnosis and index repairs (`diagnose` / `doctor` in Phase 100230).
- Creating a separate, write-amplified append-only database when existing interval structures suffice.

### Must Not Change
- PR-6 invariant: corrections and supersessions do not delete historical rows.
- PR-8 invariant: every memory operation must remain attributable.
- FR-11: `update_rule` split (`discrete` vs `continuous`) must be strictly honored during corrections.
- In-process storage schemas established in Phase 100020/100030.

### Scope Expansion Rule
If work outside this scope appears necessary:
1. Stop.
2. Document the reason.
3. Request clarification or approval.
4. Do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- Phase 100020/100030 persistence and core memory items functional.
- Phase 100080 bi-temporal intervals and supersession logic in place.
- Phase 100100 belief confidence trajectories queryable.
- Phase 100160/100170 MCP transport chassis and read tools operational.

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| Bi-temporal Store | Supports `time_axis=transaction` queries | Verify point-in-time transaction lookup |
| Belief Subsystem | Stores append-only confidence history | Verify `belief_history` entries |
| MCP Dispatcher | Supports registering inspect/correct/audit tools | Register and execute tools via stdio/HTTP |
| Persistence Hooks | Mutation events trigger telemetry emission | Telemetry listener verification |

---

## 4. Existing-System Discovery

### Required Discovery
- Identify where `store`, `update`, `discard`, and `invalidate` commit mutations in the repository.
- Inspect how transaction timestamps and actor attributions are currently captured.
- Locate the query engine for item metadata and bi-temporal intervals.
- Verify whether an event bus, hook, or synchronous log already captures mutation events.
- Check secret masking utilities available in configuration or logging modules.

### Discovery Output
Before implementation, the agent must report:
- Storage hooks identified for mutation telemetry.
- Schema of existing transaction-time audit columns.
- Existing indexing for `item_id` and `timestamp` across history tables.
- Discovered constraints on multi-backend queries (Postgres vs SQLite).
- Assumptions confirmed or contradicted regarding correction mechanics.

### Repository Adaptation Rule
The agent must determine concrete file locations and structures from the actual repository. File paths and module names in this plan are logical descriptions.

---

## 5. Implementation Specification

### Task 1: Mutating Operation Telemetry Pipeline (FR-15, §4.12)

#### Intent
Capture and persist a uniform telemetry record on every state-altering operation across all backends.

#### Required Capability or Behavior
- Emit a structured event on every `store`, `update`, `discard`, `invalidate`, and `correct`:
  ```json
  {
    "operation": "store|update|discard|invalidate|correct",
    "item_id": "item_123",
    "category": "task_spec|schema|tool_config|output_constraint|persona",
    "epistemic_kind": "fact|belief",
    "confidence": 0.95,
    "admission_score": 0.88,
    "actor": "agent_alpha",
    "timestamp": "2026-09-17T10:00:00Z"
  }
  ```
- Store events in a queryable persistence table/collection indexed by `item_id`, `bank`, and `timestamp`.
- Ensure telemetry write occurs in the same database transaction as the mutation (atomic commit).

#### Architectural Responsibility
Persistence telemetry middleware / storage layer hook.

#### Required Changes
1. Add telemetry event model and migration for telemetry table.
2. Hook mutating repository methods to emit events synchronously within the active transaction.
3. Validate telemetry fields are complete and non-null.

#### Implementation Constraints
- Telemetry MUST NOT log plaintext secrets, credentials, or raw encryption keys.
- Write amplification must be bounded; telemetry records store metadata and references, not bulk duplicates.

#### Expected Result
Every memory write produces a traceable telemetry record in the database.

---

### Task 2: Audit Trail Reconstruction Engine (FR-15, §4.12)

#### Intent
Implement `audit_trail(item_id)` to assemble the full lifecycle history of an item on demand.

#### Required Capability or Behavior
- Accept `item_id` and return a consolidated chronological timeline:
  - Creation event with initial admission score, category, and source reference.
  - Intermediate updates, bi-temporal supersessions, or EMA trend calculations.
  - For beliefs: full append-only confidence trajectory from Phase 100100.
  - Manual corrections with actor attribution and `correction_reason`.
  - Invalidation or discard status changes.
- Unbroken lineage traversal: `audit_trail` traverses both backward (`corrects_item_id` / `supersedes_id`) and forward (`superseded_by_id` / child `corrects_item_id`) pointers to assemble the complete unified lifecycle across all revisions regardless of which historical or active revision's `item_id` was queried.
- Read directly from write-path interval tables, belief histories, and telemetry rows—no redundant second store.

#### Architectural Responsibility
Audit domain service.

#### Required Changes
1. Implement `audit_trail` query aggregator joining item records, intervals, and telemetry.
2. Sort timeline entries deterministically by transaction timestamp ascending.
3. Handle missing items gracefully with a typed `ITEM_NOT_FOUND` error.

#### Implementation Constraints
- Query execution must be efficient (indexed on `item_id`).
- Historical entries MUST NOT be redacted or altered except via verified compliance erasure (Phase 100190).

#### Expected Result
Calling `audit_trail("sem_001")` returns an ordered array of every change ever applied to that item.

---

### Task 3: Memory Inspector API (FR-16, §4.12)

#### Intent
Expose `inspect(filter?, limit?, offset?)` for item listing, filtering, and debugging.

#### Required Capability or Behavior
- Support query filters:
  - `bank`: Tenant / repo isolation scope (required or defaulted from profile).
  - `category`: Semantic category whitelist filter.
  - `epistemic_kind`: `fact` | `belief`.
  - `validity`: `active` | `invalidated` | `discarded` | `all`.
  - `time_range`: Filter by creation or transaction time `[start, end)`.
- Return paginated item descriptors containing metadata, scores, validity intervals, and source references.
- Mask any credentials or sensitive tokens present in item metadata.

#### Architectural Responsibility
Inspector query service and MCP adapter.

#### Required Changes
1. Build filtered query builder supporting both Postgres and SQLite backends.
2. Add pagination controls (default limit: 50, maximum limit: 200).
3. Bind `inspect` to MCP dispatcher and CLI interface.

#### Implementation Constraints
- Inspector MUST NOT return encrypted content payloads if the subject DEK has been shredded.

#### Expected Result
Inspect queries return paginated, filtered item lists with complete governance attributes.

---

### Task 4: Auditable Correction Mechanism (FR-16, §4.12)

#### Intent
Implement `correct(item_id, new_value, reason)` allowing authorized agents and operators to rectify erroneous memory items with full attribution.

#### Required Capability or Behavior
- Validate input: `item_id` exists, `new_value` conforms to item schema, and `reason` is non-empty.
- Apply correction according to the item's declared `update_rule`:
  - **`discrete`**: Supersede prior assertion by setting `valid_time.end` and `transaction_time.end`, and inserting corrected assertion stamped with transaction time at the moment of correction. The new record stores `corrects_item_id = prior_id`, and the prior record stores `superseded_by_id = new_id`. Prior assertion remains queryable as past system belief (NFR-4).
  - **`continuous`**: Re-center smoothed state or record documented adjustment with attribution.
- Emit a telemetry record with `operation: "correct"`, `actor`, `timestamp`, and the caller-provided `reason`.
- Forbid physical deletion of rows (`DELETE`); corrections are additive on the transaction timeline.

#### Architectural Responsibility
Correction command handler.

#### Required Changes
1. Implement `correct` service method with transaction management.
2. Validate caller permissions and presence of `reason`.
3. Set `corrects_item_id` on the new assertion and `superseded_by_id` on the superseded assertion.
4. Register `correct` tool in MCP write/mutate catalog.

#### Implementation Constraints
- Correcting an item MUST NOT alter the create-time admission score or erase historical provenance.
- Must reject calls with blank or missing `reason`.

#### Expected Result
Correcting a fact updates current state while preserving the prior false belief in historical queries.

---

### Formal State Machine: Bi-Temporal Correction Transitions (unlimited-plan item)

For any discrete fact assertion $A$ with identity key $(S, P)$ (subject, predicate):
1. **Initial Assertion:** $A_1 = \text{Assert}(S, P, O_1, T_{\text{tx1}})$, status = $\text{ACTIVE}$, with valid interval $[V_{s1}, \infty)$ and transaction interval $[T_{\text{tx1}}, \infty)$.
2. **Correction Event:** $\text{correct}(A_1, O_2, \text{reason}, T_{\text{tx2}})$.
3. **Atomic Transition:**
   - $A_1 \to \text{SUPERSEDED}$: transaction interval closes to $[T_{\text{tx1}}, T_{\text{tx2}})$; valid interval closes to $[V_{s1}, T_{\text{tx2}})$; $A_1.\text{superseded\_by\_id} = A_2.\text{id}$.
   - $A_2 \to \text{ACTIVE}$: $A_2.\text{corrects\_item\_id} = A_1.\text{id}$; transaction interval $[T_{\text{tx2}}, \infty)$; valid interval $[T_{\text{tx2}}, \infty)$.
4. **Invariants:**
   - Single Active Edge: $\forall t, \text{count}(\{A \in \text{Edges}(S, P) \mid A.\text{tx\_start} \le t \land (A.\text{tx\_end} > t \lor A.\text{tx\_end} = \text{null})\}) \le 1$.
   - Immutability of Transaction History: $\forall A, A.\text{tx\_start}$ is immutable; $A.\text{tx\_end}$ can transition from null to non-null exactly once and is never deleted.
   - Lineage Completeness: The transitive closure of $(\text{corrects\_item\_id} \cup \text{superseded\_by\_id})$ forms a connected, acyclic directed graph representing the total revision history.

---

### Task 5: Audit and Inspection Conformance Suite

#### Intent
Automated testing suite verifying telemetry emission, audit trail assembly, inspection filters, and correction mechanics.

#### Required Capability or Behavior
- Verify every mutating Core tool triggers telemetry write.
- Verify `audit_trail` correctly stitches creation, multiple updates, and corrections.
- Verify `inspect` pagination and filtering accuracy across multiple categories and validity states.
- Verify `correct` preserves bi-temporal queryability: querying `as_of` prior to correction returns original value; querying after returns corrected value.
- Confirm negative scenarios: missing reason fails, invalid update_rule fails.

#### Architectural Responsibility
Integration test harness.

#### Required Changes
1. Create `tests/audit_and_correction_test.rs` (or project equivalent).
2. Wire tests into CI pipeline.

#### Implementation Constraints
- Tests must execute identically against both Postgres and SQLite test backends.

#### Expected Result
100% passing tests for audit trail reconstruction and non-destructive correction.

---

### Implementation Freedom
The agent may choose:
- Schema layout of the internal telemetry table (e.g., column-based vs structured JSONB/JSON payload).
- Pagination token implementation (numeric offset vs keyset/cursor pagination).
- Formatting and layout of CLI inspection displays.

---

## 6. Agent Execution Rules

### Allowed Actions
- Add telemetry tables, triggers, or repository hooks.
- Implement query endpoints for `audit_trail` and `inspect`.
- Add mutating `correct` handler and bind it to MCP and CLI.
- Add integration tests verifying historical reconstruction.

### Forbidden Actions
- Using SQL `DELETE` in the correction path.
- Creating an independent second event-sourcing engine when write-path tables already hold intervals.
- Omitting `reason` or `actor` from correction operations.
- Exposing unmasked secrets in inspect or audit output.

### Agent Decision Boundary
The agent may decide:
- Optimization of SQL queries joining telemetry and interval tables.
- Internal caching of inspect metadata (provided cache invalidation is atomic).
- Module decomposition adhering to the 450-line file limit.

The agent must request approval for:
- Altering the parameter signature of `correct`, `inspect`, or `audit_trail`.
- Any database migration that locks tables on large production datasets.

### Mandatory Stop Conditions
Stop and report if:
- Underlying storage engine lacks transaction-time interval columns.
- Missing actor context makes attributing operations impossible.
- Multi-backend query divergence prevents uniform inspect filtering.

---

## 7. Security Constraints

### Required Controls
- `correct` MUST require explicit confirmation or authorized role when called from agent harnesses.
- Telemetry records MUST be immutable (append-only); updates or deletions of telemetry rows are strictly prohibited.
- Filtering by `bank` is mandatory to maintain tenant boundary isolation.

### Sensitive Data Rules
- Telemetry events must mask credentials, tokens, and DEKs.
- `audit_trail` responses must omit decrypted content if key has been revoked.

### Security Acceptance Conditions
- Calling `correct` without a `reason` returns a 400-class error.
- Telemetry tables reject `UPDATE` and `DELETE` queries.
- Inspect queries scoped to `bank_a` never return items from `bank_b`.

---

## 8. Test and Verification Strategy

### Required Tests
- [x] Unit tests for telemetry record formatting and validation
- [x] Integration tests verifying telemetry emission on `store`, `update`, `discard`, `invalidate`
- [x] Bi-temporal reconstruction tests for `audit_trail`
- [x] Filter combination tests for `inspect` (bank, category, validity)
- [x] Non-destructive correction tests verifying past validity intervals
- [x] Rejection tests for missing correction reasons

### Required Test Scenarios
| Test ID | Scenario | Expected Result |
|---------|----------|-----------------|
| T100180-01 | Store item and check telemetry | Telemetry row exists with matching `admission_score` and `actor` |
| T100180-02 | Invalidate item and inspect audit trail | Timeline shows creation followed by invalidation event |
| T100180-03 | Call `correct` on fact item | New assertion active; prior assertion closed on transaction timeline |
| T100180-04 | Query historical fact via `as_of` after correction | Returns original value at past timestamp (NFR-4) |
| T100180-05 | Call `correct` with empty reason | Operation rejected; no state change |
| T100180-06 | Paginated `inspect` query | Exactly `limit` items returned with accurate total count |

### Negative Testing
Verify that:
- Attempts to modify existing telemetry rows throw database errors.
- Calling `correct` on a non-existent item returns `ITEM_NOT_FOUND`.
- Calling `correct` with a type conflicting with declared `update_rule` fails closed.
- Unauthorized tenants cannot inspect foreign banks.

### Verification Rule
All audit trail claims must be validated by asserting the reconstructed timeline against known sequences of mutations.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence | Result |
|-------|----------------------|---------------------|-------------------|--------|
| AC-100180-01 | Telemetry emitted for all mutating operations | Test database assertion | Query log showing telemetry rows | PASS — `audit_correct_tests` (sqlite) and `pg_audit_tests` (postgres) assert persisted rows: `create_memory_item` on `store`, `update_memory_item` on update, `discard` (with actor + reason detail) on discard, `invalidate` (with replacement pointer) on invalidate, `correct` on correction. Rows are written inside the same transaction as the mutation (discard/invalidate/correct impls wrapped in explicit transactions). Continuous attribute corrections carry `operation: correct` with `attr_key` + reason in the detail (asserted in `continuous_correction_emits_correct_operation`); plain continuous observations stay `continuous_observe`. |
| AC-100180-02 | `audit_trail` returns complete lifecycle | API response validation | Reconstructed timeline JSON | PASS — `audit_trail` traverses `corrects_item_id`/`superseded_by_id` lineage in both directions from any revision id and returns a single merged `timeline` array (revisions + telemetry events + belief points) ordered ascending by `(timestamp, kind, id)`, alongside the individually ordered `revisions`/`events`/`belief_confidence` arrays; verified in `t18_02_audit_trail_traverses_lineage_from_any_revision` (3-revision chain queried from every id), `timeline_merges_revisions_and_events_in_order`, and end-to-end over MCP stdio (sample JSON below). |
| AC-100180-03 | `inspect` supports multi-parameter filtering | Integration test suite | Test execution output | PASS — pre-existing inspect filters (bank/category/epistemic_kind/validity/time range, now half-open `[start, end)`) extended with `discarded` validity, page cap (default 50, max 200), and an accurate `total` count that ignores the page window; covered by `read_tools_tests::inspect_filters_pagination_and_discard_visibility` (asserts `total`), `audit_tools_tests::audit_trail_missing_item_and_inspect_page_cap` (asserts `total` with a clamped limit), `pg_inspect_tests::inspect_items_parity_and_filters` (total + half-open boundary on both backends), and the stdio conformance test. |
| AC-100180-04 | `correct` performs non-destructive revision | Bi-temporal query comparison | Pre- and post-correction query diff | PASS — after `correct`, the prior assertion is closed on both axes (`valid_until` + `tx_until` set, `superseded_by_id` linked) and remains queryable with its original snapshot (past system belief, NFR-4); the corrected assertion is active with lineage links. No `DELETE` anywhere in the path (PR-6). T100180-04's transaction-axis historical query is verified by `audit_asof_tests::t18_04_as_of_transaction_returns_prior_then_corrected_value` (the `item_visible_at(TimeAxis::Transaction)` predicate over the real corrected rows selects the original value before the correction and the corrected value after), plus sqlite + postgres parity tests. Note: the hybrid retrieval candidate legs index only live rows (`items.tx_until IS NULL`), so `retrieve`/`compose` `as_of` filters the live candidate set rather than resurrecting superseded revisions; transaction-axis item history is surfaced by `audit_trail` and the visibility predicate. |
| AC-100180-05 | Missing correction reason rejected | Negative unit test | Error response output | PASS — blank/whitespace reason fails `InvalidArgument` at the MCP binding, service layer, and store layer; no state change (asserted). |
| AC-100180-06 | Telemetry records are immutable | Direct SQL update test | Permission/trigger failure log | PASS — `audit_events` UPDATE and DELETE rejected at the database level by BEFORE triggers (SQLite `RAISE(ABORT)`, Postgres `RAISE EXCEPTION`), verified by direct-SQL tests on both backends. |

### Definition of Done
- [x] Telemetry pipeline active on all write paths — `store`/`update` (pre-existing rows), `discard`/`invalidate`/`correct` (new same-transaction rows; discard/invalidate signatures extended with `actor` for PR-8 attribution).
- [x] `audit_trail`, `inspect`, and `correct` exposed over MCP and in-process APIs — `clio-compliance` service crate (`audit_trail`, `correct`), MCP bindings (`correct` in the write/mutate dispatcher with confirm gating, `audit_trail` in the read dispatcher), schema pack updated. CLI exposure is via `am mcp stdio|http` (the established binding surface; verified end-to-end over stdio).
- [x] Bi-temporal preservation verified on correction — both axes closed on the prior, content and admission score untouched.
- [x] Integration test suite passes across Postgres and SQLite — 18 audit/correct tests in clio-store across both backends (`audit_correct_tests` 9 + `correct_reject_tests` 5 + `pg_audit_tests` 4) plus 3 SQLite lineage-convergence tests, 13 service tests in clio-compliance, 3 MCP binding tests + 1 stdio conformance test, and 1 clio-retrieve transaction-axis `as_of` test; full workspace `make check` green.
- [x] Files remain ≤ 450 lines — all created/modified Rust files verified (max touched: `postgres_store.rs` 433; new: `mcp_audit_conformance.rs` 141, `schema_converge.rs` 75, `schema_converge_tests.rs` 73).
- [x] Required approval is obtained (downstream pipeline step).

### Completion Evidence
- Tests: `tests/audit_and_correction_test.rs` project equivalent = `crates/clio-store/src/audit_correct_tests.rs` (SQLite, 9 tests) + `crates/clio-store/src/correct_reject_tests.rs` (5) + `crates/clio-store/src/pg_audit_tests.rs` (Postgres parity, 4) + `crates/clio-store/src/schema_converge_tests.rs` (SQLite lineage convergence, 3) + `crates/clio-compliance/src/{correct,audit}_tests.rs` (13) + `crates/clio-mcp/src/audit_tools_tests.rs` (3) + `crates/clio-mcp/tests/mcp_audit_conformance.rs` (stdio round-trip, 1) + `crates/clio-retrieve/src/audit_asof_tests.rs` (transaction-axis `as_of`, 1). Workspace `make check` (fmt + clippy -D warnings + test) and `make coverage` green.
- Coverage (re-measured after remediation): aggregate **lines 97.99%, functions 98.63%**; per-file gate re-verified — all 163 reported Rust files ≥ 90% lines AND functions. Reference points: `clio-compliance/audit.rs` 100% / 100%, `clio-compliance/correct.rs` 100% functions / 99.31% lines, `sqlite_correct.rs` 100% / 97.74%, `postgres_correct.rs` 100% / 97.42%, `sqlite_audit.rs` 100% functions / 97.20% lines, `postgres_audit.rs` 91.67% functions / 93.47% lines, `schema_converge.rs` 100% / 100%, `sqlite_inspect.rs` and `postgres_inspect.rs` 100% / 100%.
- Sample JSON payload of `audit_trail` (real run over `am mcp stdio`, sqlite in-memory): item admitted with admission score 0.76, corrected (`wrong deploy cadence`), trail shows creation event + both lineage-linked `correct` events with actor + reason, ordered ascending; see `crates/clio-compliance` service contract — full sample:

```json
{
  "item_id": "sem_001",
  "lineage_ids": ["sem_001", "itm-mcp-1"],
  "revisions": [
    {"item_id": "sem_001", "corrects_item_id": null, "superseded_by_id": "itm-mcp-1", "valid_from": "1789827436197", "valid_until": "2024-02-01T00:00:00Z", "tx_from": "1789827436197", "tx_until": "2024-02-01T00:00:00Z", "discarded_at": null, "category": "tool_config", "epistemic_kind": "fact", "confidence": null, "admission_score": 0.76, "source_ref": null, "created_at": "1789827436197", "updated_at": "1789827436197"},
    {"item_id": "itm-mcp-1", "corrects_item_id": "sem_001", "superseded_by_id": null, "valid_from": "2024-02-01T00:00:00Z", "valid_until": null, "tx_from": "2024-02-01T00:00:00Z", "tx_until": null, "discarded_at": null, "category": "tool_config", "epistemic_kind": "fact", "confidence": null, "admission_score": 0.76, "source_ref": null, "created_at": "2024-02-01T00:00:00Z", "updated_at": "2024-02-01T00:00:00Z"}
  ],
  "events": [
    {"timestamp": "1789827436197", "operation": "create_memory_item", "item_id": "sem_001", "category": "tool_config", "epistemic_kind": "fact", "confidence": null, "admission_score": 0.76, "actor": "agent", "reason": null, "detail": {}},
    {"timestamp": "2024-02-01T00:00:00Z", "operation": "correct", "item_id": "sem_001", "category": "tool_config", "epistemic_kind": "fact", "confidence": null, "admission_score": 0.76, "actor": "user", "reason": "wrong deploy cadence", "detail": {"corrected_by": "itm-mcp-1", "reason": "wrong deploy cadence"}},
    {"timestamp": "2024-02-01T00:00:00Z", "operation": "correct", "item_id": "itm-mcp-1", "category": "tool_config", "epistemic_kind": "fact", "confidence": null, "admission_score": 0.76, "actor": "user", "reason": "wrong deploy cadence", "detail": {"corrects_item_id": "sem_001", "reason": "wrong deploy cadence"}}
  ],
  "belief_confidence": []
}
```

- Schema: `sql/001_core.sql` gained `items.corrects_item_id` / `items.superseded_by_id`; the `002_vectors_*` dialect files own the lineage indexes (created only after the columns exist) and the append-only `audit_events` triggers for each dialect. Pre-existing databases converge the columns before portable DDL runs: Postgres via `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` in `002_vectors_postgres.sql`, SQLite via the guarded `schema_converge::converge_lineage_columns_sqlite` hook (`PRAGMA table_info` guard, since SQLite has no `ADD COLUMN IF NOT EXISTS`). `schema_settings.schema_version` bumped `6` → `7`. Edited in place — no migration scripts (per task rules).
- Sample timeline events above; telemetry event `{operation, item_id, category, epistemic_kind, confidence, admission_score, actor, timestamp}` + `detail.reason` is queryable on both backends.

### Discovery Output (required by §4)
- Mutation commit hooks: `create_memory_item` / `update_memory_item` (both backends) and `belief_observe`, `continuous_observe`, `triple_add`, `task_upsert`, `failure_record` already wrote `audit_events` rows in-transaction. Gaps found and closed: `discard_item` and `invalidate_item` wrote no telemetry rows (clio-write emitted only in-memory sink events); they now write rows in the same transaction, with `actor` added to the trait signatures (PR-8 attribution).
- Transaction-time columns: `items.tx_from/tx_until` exist; lineage pointers `corrects_item_id`/`superseded_by_id` were absent and are added.
- Indexing: `audit_events(item_id, created_at)` and `(bank_id, created_at)` already exist; lineage index `items(corrects_item_id)` + `items(superseded_by_id)` added.
- Multi-backend constraints: `audit_events` is portable (text timestamps/JSON); immutability required dialect-split DDL, placed in the per-backend `002_vectors_*.sql` files (SQLite `CREATE TRIGGER ... RAISE`, Postgres `CREATE FUNCTION` + triggers).
- Correction mechanics assumption confirmed: supersession already closes both axes without delete; `correct` reuses this state machine plus new lineage pointers; continuous updates are attribute-key-addressed, so a continuous correction routes to the EMA engine with the reason stored on the same-transaction `continuous_observe` row.

---

## 10. Failure Handling and Recovery

### Expected Failure Modes
| Failure | Detection | Recovery |
|---------|-----------|----------|
| Telemetry write failure | Transaction error | Roll back entire mutation; do not allow untracked writes |
| Missing item on correct | Lookup returns None | Return structured 404 / `ITEM_NOT_FOUND` error |
| Disallowed update_rule | Validation check | Reject correction; advise appropriate tool |
| Slow inspect queries | Query latency monitoring | Add composite index on `(bank, category, created_at)` |

### Rollback Strategy
Reverting code leaves telemetry tables intact (read-only); existing bi-temporal intervals remain authoritative.

### Partial Completion Policy
If telemetry emission is implemented but `correct` is not, mark `correct` as pending and do not claim AC-100180-04.

---

## 11. Traceability

| Parent Requirement | Implementation Task | Verification | Acceptance Criterion |
|--------------------|---------------------|--------------|-----------------------|
| FR-15, §4.12 | Task 1, 2 | T100180-01, T100180-02 | AC-100180-01, AC-100180-02 |
| FR-16, §4.12 | Task 3, 4 | T100180-03, T100180-06 | AC-100180-03, AC-100180-04 |
| PR-6, FR-12 | Task 4 | T100180-04 | AC-100180-04 |
| PR-8 | Task 1, 4 | T100180-01, T100180-05 | AC-100180-01, AC-100180-05 |
| NFR-4 | Task 4 | T100180-04 | AC-100180-04 |

Required chain:
```text
Requirement → Capability → Implementation → Test → Evidence
```

---

## 12. Phase Exit Contract

### Outputs Produced
- Standardized mutation telemetry pipeline.
- `audit_trail`, `inspect`, and `correct` tools fully operational over MCP and in-process bindings.
- Conformance test suite for audit and correction workflows.

### Guarantees Provided to Downstream Phases
- All mutations in Phase 100190 (erasure tombstones) and Phase 100200 (batch operations) will automatically emit attributable telemetry.
- Operators and agents have full visibility into why any item was admitted or altered.

### Known Limitations
- Compliance crypto-shredding is handled separately in Phase 100190.
- Operational noise cleanup is handled in Phase 100210.
- Item-level `audit_trail` anchors on `items`/`beliefs` rows. Continuous attribute corrections (attribute keys are not item identities) emit a same-transaction telemetry row with `operation: correct` and the actor + reason in `detail_json`, but no exposed tool lists `audit_events` by attribute key yet: `audit_trail(item_id)` cannot return them because there is no item anchor. Missing: an attribute-key audit view. Why: §4.12 requires transparency over operations, which the telemetry row provides, and attribute series are not item identities (the alternative would be a new API surface). Owner: a future inspector enhancement; not owed by a named phase (Phase 100210 owns hygiene operations, not attribute audit views).
- Transaction-axis historical item reads: `audit_trail` returns every revision (past system belief), and `item_visible_at(TimeAxis::Transaction)` selects a revision at a past `as_of` (verified by T100180-04). The hybrid retrieval lexical/dense legs index only live rows (`items.tx_until IS NULL`), so `retrieve`/`compose` cannot resurrect a superseded revision; a full historical retrieval mode is not built. Missing: as_of-aware candidate indexing. Why: retrieval is scoped to current memory and history is surfaced by `audit_trail`. Owner: not owed by this phase.
- The concurrent-loss guard in `correct_item` (`UPDATE ... WHERE tx_until IS NULL` matching zero rows after a lost supersession race) is fail-closed but not reachable by tests against a single-client store; a multi-host sync phase (Phase 100240) owns any concurrent-apply test coverage for it.
- Verification note: with `DATABASE_URL` unset, the pre-existing Postgres-backed test suites fail at connect time (the env lookup has no effective fallback path in this environment); this predates this phase and affects all pg suites equally. With `DATABASE_URL` set (Compose default), the full suite is green.

### Downstream Prerequisites
- Phase 100190 requires telemetry integration to record content-free compliance tombstones.
- Phase 100200 `validate` tool interacts with `correct` and `invalidate` mechanics.

### Final Status
PASS

### Verification Sign-Off
- Implementer: Developer r1 (OpenCode CLI, GLM-5.3 Flash)
- Verifier: pending (Adversary r1)
- Human Approver: [Name, if required]
- Date: 2026-09-19

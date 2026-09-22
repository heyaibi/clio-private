# Phase 100200: Additive Harness Workspace Tools

### Attribution
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | OpenCode CLI (Go . Deepseek V4.1 Flash High) | done |
| Adversary | r1 | OpenCode CLI (OpenRouter . Deepseek V4.1 Flash Max) | done |
| Remediator | r1 | OpenCode CLI (Go . Deepseek V4.1 Flash High) | done |
| Remedy Approver | r1 | Antigravity CLI (Gemini 3.8 Flash) | approved |
| Finalize | r1 | OpenCode CLI (Together . GLM-5.3 Flash High) | done |

**Index slice 100200 · **Effort:** `1×` · **Scope:** `roadmap/index.md` slice 100200 (authoritative)

### Vocabulary (read first) — zero shared moniker

| Term | Enum / form | Where it lives | Must not |
|------|-------------|----------------|----------|
| **`ephemeral_scratchpad`** | Size-bounded, in-memory or session-scoped transient buffer | Harness workspace (§4.9.5.A) | Be written to long-term memory or auto-injected into model context |
| **`canonical_slot`** | Single-slot key-value tool pair (`canonical_put` / `canonical_get`) | Additive convenience tool | Be confused with write-pipeline **`canonical_consolidation`** (§4.3) |
| **`canonical_consolidation`** | Merging parallel-extracted chunks into a stable leaf | Phase 100060 write pipeline | Be confused with single-slot `canonical_slot` tools |
| **`shared_bank`** | Cross-agent surface bank (`shared_store`, `shared_retrieve`) | Multi-agent namespace (§4.9.5.A) | Bypass category whitelist or admission scoring gates |
| **`batch_transaction`** | Atomic execution of Core write mutations (`batch`) | Harness tool (FR-23) | Be confused with multi-host replication `sync_payload` (§4.9.5.D) |
| **`peer_validate`** | Collaborative reviewer tool (`validate`) with attest/update/discard | Multi-agent reviewer loop | Be confused with ops health `verify` (§4.9.5.C) or `span_verification` |

---

## 1. Objective

### Goal
Deliver coding-agent operability and collaboration tools (§4.9.5.A, FR-10, FR-21, FR-22, FR-23): atomic multi-mutation `batch`, ephemeral size-bounded scratchpad (`scratchpad_*`), single-slot `canonical_*` convenience tools, cross-agent `shared_*` surface bank, collaborative `validate`, and system `stats`. **Admission gates remain strictly enforced on all long-term writes; the scratchpad MUST NOT enter long-term stores or context injection** (PR-1, PR-3, PR-5, FR-21, FR-23).

### Expected Outcome
- `batch(operations, dry_run?)`: executes multiple Core write mutations within a single atomic database transaction. If any operation fails admission or validation, the entire batch rolls back. Returns per-operation results or structured dry-run report (FR-23).
- `scratchpad_write(key, content)`, `scratchpad_read(key?)`, `scratchpad_clear(key?)`: provides an ephemeral, size-capped working memory buffer for intermediate agent reasoning. Does not touch durable storage or vector indexes; auto-clears on session exit.
- `canonical_put(key, value, ...)` and `canonical_get(key)`: single-slot upsert/read abstraction with automated bi-temporal supersession history. Gated by §4.1 category and §4.2 admission scoring.
- `shared_store`, `shared_retrieve`, `shared_discard`: cross-agent collaboration bank namespace (`bank="shared"` or dedicated prefix) with identical gate enforcement as primary bank stores.
- `validate(item_id, action, note?, new_content?)`: enables collaborative reviewer loops supporting actions `attest`, `update`, `invalidate`, and `discard` with full audit trail logging.
- `stats(bank?)`: reports memory counts by bank, tier, and category for operational telemetry.
- Machine-readable MCP schemas published and registered on stdio and Streamable HTTP for all additive tools in this slice.

### Parent Requirement
`requirement.md` (v1.8+) — P1, P6, P7, P8, P10, PR-1, PR-3, PR-5, PR-6, PR-8, §4.1, §4.2, §4.6, §4.9.3, §4.9.5.A, §4.9.6, FR-10, FR-21, FR-22, FR-23.

### Design References (non-normative)
- **Agent Working Memory Patterns:** [Working Memory in Autonomous Agents](https://arxiv.org/abs/2303.11366) — Ephemeral scratchpads prevent long-term memory bloat (P1) by keeping intermediate reasoning out of persistent indices.
- **Transactional Tool Batches:** [Database Transaction Semantics for AI Agents](https://digitalapplied.com) — Atomic end-of-turn write batches prevent partial state corruption.
- **Multi-Agent Shared Memory:** [Collaborative Memory in Agent Swarms](https://arxiv.org/abs/2504.19413) — Namespaced shared banks for cross-agent coordination without permission bleed.

---

## 2. Scope Boundaries

### In Scope
- Transactional `batch` engine wrapping Core write tools (`store`, `triple_add`, `persona_put_stable`, `task_upsert`, `failure_record`).
- Ephemeral in-memory/session-scoped scratchpad with hard token/byte capacity limits and TTL eviction.
- Single-slot `canonical_put` / `canonical_get` applying bi-temporal supersession under the hood.
- Multi-agent `shared_*` tools enforcing admission gates inside a designated shared bank namespace.
- Reviewer `validate` tool executing peer attestations, updates, invalidations, or discards with attributable audit logging.
- Read-only `stats` reporter aggregating counts across banks and categories.
- MCP schema publication and binding on stdio and Streamable HTTP transports.

### Explicitly Out of Scope
- Multi-host client/server synchronization protocol (`sync_*` owned by Phase 100240).
- Operational noise cleanups (`hygiene_audit` / `hygiene_clean` owned by Phase 100210).
- JSON export and import with completeness manifests (owned by Phase 100220).
- Doctor repair commands and index rebuilds (`doctor` / `repair` / `reindex` owned by Phase 100230).
- Bypassing admission gates for batch or shared writes.

### Must Not Change
- PR-1 / FR-21: Scratchpad contents must never be written to long-term stores or indexed for vector retrieval.
- PR-5: Every long-term write inside `batch`, `canonical_put`, or `shared_store` must pass category and admission gates.
- Core tool semantics from prior phases.
- Pinned MCP transport revision `2025-11-25`.

### Scope Expansion Rule
If work outside this scope appears necessary:
1. Stop.
2. Document the reason.
3. Request clarification or approval.
4. Do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- Phase 100160/100170 completed: MCP server infrastructure, dispatcher, and Core tools operational.
- Phase 100040 completed: Category whitelist and five-factor admission scoring gates available.
- Phase 100080 completed: Bi-temporal invalidation and supersession mechanics available.
- Phase 100180 completed: Telemetry pipeline available for `validate` and `batch` operations.

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| Database Transaction Engine | Supports nested/atomic transactions | Verify rollback on simulated failure |
| Admission Gates | Programmatically callable per operation | Test admission scoring inside batch |
| MCP Dispatcher | Extensible tool registry | Register and call additive tools |
| Telemetry Subsystem | Emits audit events for `validate` | Verify telemetry row created |

---

## 4. Existing-System Discovery

### Required Discovery
- Inspect how database transactions are scoped and committed across Postgres and SQLite backends.
- Identify how session state and ephemeral memory are managed in the process runtime.
- Check how `bank` namespaces are partitioned in repository queries.
- Verify existing schema generation mechanism for additive tools in the `tool_schema` pack.
- Check existing rate-limiting, size-bounding, or TTL cleanup utilities.

### Discovery Output
Before implementation, the agent must report:
- Transaction management abstractions available for `batch`.
- In-memory cache or key-value store suitable for `ephemeral_scratchpad`.
- Shared bank namespace convention (e.g., `__shared__` vs `shared`).
- Validation rules for reviewer actions in `peer_validate`.
- Assumptions confirmed or contradicted regarding batch rollback behavior.

### Repository Adaptation Rule
The agent must determine concrete file and module locations from the actual repository. Component names in this plan represent logical responsibilities.

---

## 5. Implementation Specification

### Task 1: Atomic Multi-Mutation Batch Engine (FR-23, §4.9.5.A)

#### Intent
Implement `batch(operations, dry_run?)` allowing agents to submit multiple write mutations in a single atomic transaction.

#### Required Capability or Behavior
- Accept an ordered array of operations:
  ```json
  {
    "operations": [
      {"tool": "store", "params": {...}},
      {"tool": "triple_add", "params": {...}}
    ],
    "dry_run": false
  }
  ```
- Validate every operation:
  - Tool must be a recognized mutating Core tool (`store`, `triple_add`, `persona_put_stable`, `task_upsert`, `failure_record`, `canonical_put`).
  - Run category gate and admission scoring for each candidate write.
- Intra-batch reference substitution: Operations support topological reference resolution using provisional reference tokens (`$ref:<index>.id`). For example, operation 0 can be `store` returning `{id: "sem_001"}`, and operation 1 can be `graph_link` referencing `source_id: "$ref:0.id"`. The batch engine resolves references in topological execution order within the transaction. Alternatively, callers MAY provide client-generated deterministic UUIDs upfront.
- Atomic commit:
  - If any operation fails admission or validation, the entire transaction rolls back; zero rows are written.
  - If `dry_run=true`, execute scoring and validation, return would-commit status and predicted admission scores without persisting.
- Return structured array of per-operation results: `[{status: "COMMITTED" | "REJECTED", id, admission_score, rejection_reason?}]`.

#### Architectural Responsibility
Batch orchestration controller.

#### Required Changes
1. Implement `BatchService` managing transaction lifecycle.
2. Add reference token substitution pre-processor for `$ref:<index>.id` parameters.
3. Route individual operations through existing in-process write handlers.
4. Bind `batch` tool to MCP write surface.

#### Implementation Constraints
- Maximum operations per batch MUST be capped (default: 50) to prevent transaction lock contention.
- No partial writes allowed on failure.

#### Expected Result
Submitting a batch with one valid and one invalid item rolls back completely with descriptive error.

---

### Task 2: Ephemeral Size-Bounded Scratchpad Workspace (FR-21, §4.9.5.A)

#### Intent
Implement `scratchpad_write`, `scratchpad_read`, and `scratchpad_clear` providing transient working memory.

#### Required Capability or Behavior
- `scratchpad_write(key, content)`:
  - Stores string or JSON content under `key`.
  - Scoped to the current agent session and bank.
  - Enforces hard capacity limits: max 64 KB total scratchpad size, max 100 keys per session.
  - Overwrites existing key or appends.
- `scratchpad_read(key?)`:
  - If `key` provided, returns content for that key.
  - If omitted, returns all key-value pairs in the current session's scratchpad.
- `scratchpad_clear(key?)`:
  - If `key` provided, removes that key.
  - If omitted, purges entire scratchpad for the session.
- Ephemeral lifecycle & session persistence boundary:
  - Scratchpad resides in an unindexed transient session-keyed store (e.g. database temp table or session-keyed cache with TTL) keyed by `(interaction_session, bank, key)`. This guarantees availability across multi-turn agent turns on both stdio and Streamable HTTP.
  - Scratchpad contents are NEVER admitted to long-term semantic/episodic stores and NEVER indexed for vector retrieval (FR-21).
  - Automatically evicted upon session termination or after TTL expiration (default: 4 hours of inactivity).

#### Architectural Responsibility
Session scratchpad manager.

#### Required Changes
1. Create in-memory or transient session key-value store.
2. Implement size tracking and quota enforcement.
3. Bind `scratchpad_write`, `scratchpad_read`, `scratchpad_clear` to MCP catalog.

#### Implementation Constraints
- Scratchpad MUST NOT be included in `retrieve` search domains or auto-injected context.

#### Expected Result
Agents can write and read transient working notes without polluting persistent memory stores.

---

### Task 3: Single-Slot Canonical Memory Interface (§4.9.5.A)

#### Intent
Implement `canonical_put` and `canonical_get` providing single-slot key-value semantics with automatic supersession history.

#### Required Capability or Behavior
- `canonical_put(key, value, category, epistemic_kind, ...)`:
  - Represents a named, single-slot memory unit (e.g. `primary_database_host`).
  - Gated by §4.1 category whitelist and §4.2 admission scoring.
  - Under the hood, if an active entry exists for `(bank, key)`:
    - Closes `valid_time` and `transaction_time` of prior record (bi-temporal supersession).
    - Inserts new record stamped with current validity.
  - Emits telemetry record with operation `canonical_put`.
- `canonical_get(key)`:
  - Returns the currently active value for `key` in the current bank.
  - Supports optional `as_of` argument to fetch historical values at a past point in time.

#### Architectural Responsibility
Canonical memory adapter.

#### Required Changes
1. Implement single-slot key indexing and supersession logic.
2. Integrate with admission scoring gate before committing.
3. Bind tools to MCP catalog.

#### Implementation Constraints
- Must not bypass category whitelist; category must be one of the five whitelisted categories.

#### Expected Result
Calling `canonical_put` with a new value invalidates the old value and makes the new value immediately readable via `canonical_get`.

---

### Task 4: Cross-Agent Shared Surface Bank (§4.9.5.A)

#### Intent
Implement `shared_store`, `shared_retrieve`, and `shared_discard` for multi-agent collaboration.

#### Required Capability or Behavior
- Route operations to a dedicated shared bank namespace (e.g. `bank="shared"` or configured shared prefix).
- `shared_store(item, category, ...)`:
  - Enforces standard §4.1 category gate and §4.2 five-factor admission scoring.
  - Requires caller attribution (`actor`).
- `shared_retrieve(query, ...)`:
  - Executes hybrid search scoped exclusively to the shared bank.
- `shared_discard(item_id, reason)`:
  - Requires explicit confirmation and emits telemetry.
- Strict tenant boundary: access to shared bank requires explicit permission in agent profile.

#### Architectural Responsibility
Shared bank routing adapter.

#### Required Changes
1. Add shared bank routing logic in storage layer.
2. Expose `shared_store`, `shared_retrieve`, `shared_discard` in MCP tool catalog.
3. Enforce admission gates on shared writes.

#### Implementation Constraints
- Shared bank writes MUST pass admission scoring; no relaxed criteria for multi-agent operations.

#### Expected Result
Multiple agents can share conventions and schemas via `shared_*` tools without mixing workspace banks.

---

### Task 5: Collaborative Reviewer Validate Tool (§4.9.5.A)

#### Intent
Implement `validate(item_id, action, note?, new_content?)` for agent-reviewer workflows.

#### Required Capability or Behavior
- Accept parameters:
  - `item_id`: Target memory item ID.
  - `action`: `attest` | `update` | `invalidate` | `discard`.
  - `note`: Optional review observation or reasoning.
  - `new_content`: Required if action is `update`.
- Execution semantics:
  - `attest`: Boosts item confidence or records reviewer attestation in telemetry without changing content.
  - `update`: Executes auditable correction/update adhering to item `update_rule`.
  - `invalidate`: Closes validity interval (supersedes).
  - `discard`: Marks item discarded with reviewer reason.
- Emits structured telemetry event with `actor`, `action`, `note`, and timestamp.

#### Architectural Responsibility
Reviewer validation controller.

#### Required Changes
1. Implement `ValidateService` executing reviewer actions.
2. Route actions to underlying update/invalidate/discard handlers.
3. Bind `validate` to MCP catalog.

#### Implementation Constraints
- Reviewer actions must require non-empty `note` when taking destructive or corrective actions.

#### Expected Result
Reviewer agent can attest or invalidate memory items with full attribution.

---

### Task 6: Additive Tools MCP Schemas and Conformance Suite

#### Intent
Publish machine-readable schemas and verify all additive tools across stdio and Streamable HTTP.

#### Required Capability or Behavior
- Publish `tool_schema` definitions for `batch`, `scratchpad_*`, `canonical_*`, `shared_*`, `validate`, and `stats`.
- Test suite verifying:
  - Atomic rollback of `batch` on admission rejection.
  - Scratchpad size enforcement and isolation from `retrieve`.
  - `canonical_put` supersession history.
  - `shared_*` bank isolation.
  - `validate` reviewer actions.
  - `stats` reporting accuracy.

#### Architectural Responsibility
Conformance test harness.

#### Required Changes
1. Update schema export script to include additive tools.
2. Create `tests/additive_tools_test.rs`.
3. Wire tests into CI matrix.

#### Implementation Constraints
- Zero network dependencies.

#### Expected Result
Passing test suite confirming all Additive tools adhere to governance, atomicity, and MCP transport rules.

---

### Implementation Freedom
The agent may choose:
- In-memory data structure for ephemeral scratchpad (e.g. `DashMap`, `RwLock<HashMap>`, or SQLite temporary table).
- Internal routing mechanism for shared bank segregation.
- Exact JSON structure returned by `stats`.

---

## 6. Agent Execution Rules

### Allowed Actions
- Implement batch transaction controller with rollback support.
- Implement ephemeral scratchpad manager with size quotas.
- Add canonical memory and shared bank adapters.
- Register all additive tools on the MCP dispatcher.
- Add integration tests verifying atomicity and isolation.

### Forbidden Actions
- Allowing scratchpad data to be indexed in vector or lexical stores.
- Skipping category or admission gates during `batch` or `shared_store`.
- Allowing partial commits in a failed `batch`.
- Treating `scratchpad` as durable long-term storage.

### Agent Decision Boundary
The agent may decide:
- TTL eviction strategy for inactive scratchpads.
- Specific error message phrasing for batch validation failures.
- Module layout adhering to the 450-line file limit.

The agent must request approval for:
- Altering the parameter signatures of any additive tool.
- Increasing the default 64 KB scratchpad size limit.

### Mandatory Stop Conditions
Stop and report if:
- Database driver does not support transaction rollback.
- Admission scoring cannot be invoked in dry-run mode within a transaction.
- Scratchpad isolation cannot be guaranteed.

---

## 7. Security Constraints

### Required Controls
- Batch operations MUST enforce a maximum operation count to prevent denial-of-service via lock starvation.
- Scratchpads MUST enforce byte and key limits to prevent memory exhaustion.
- Multi-agent `shared_*` tools MUST validate caller authorization before accessing shared banks.

### Sensitive Data Rules
- Scratchpad data MUST be cleared from memory upon session termination.
- Mask credentials in batch error reports and stats summaries.

### Security Acceptance Conditions
- Submitting a batch exceeding maximum operation limit is rejected with 400.
- Exceeding scratchpad quota returns `QUOTA_EXCEEDED` error without crashing.
- Unauthorized tenants cannot read foreign shared banks.

---

## 8. Test and Verification Strategy

### Required Tests
- [x] Unit tests for scratchpad capacity enforcement and key operations
- [x] Transactional atomicity tests for `batch` (verify all-or-nothing rollback)
- [x] Bi-temporal supersession verification for `canonical_put`
- [x] Isolation tests for `shared_store` and `shared_retrieve`
- [x] Reviewer action tests for `validate` (`attest`, `update`, `invalidate`, `discard`)
- [x] Stats count verification tests
- [x] Negative tests: scratchpad isolation from vector search

### Required Test Scenarios
| Test ID | Scenario | Expected Result |
|---------|----------|-----------------|
| T100200-01 | Submit batch with 3 valid items | All 3 committed atomically; status 200 |
| T100200-02 | Submit batch where 3rd item fails admission | Transaction rolls back; 0 items written; error returned (FR-23) |
| T100200-03 | Write to scratchpad then query `retrieve` | Scratchpad content is NOT returned in search results (FR-21) |
| T100200-04 | Exceed 64 KB scratchpad quota | Write rejected with `QUOTA_EXCEEDED` |
| T100200-05 | `canonical_put` twice on same key | Prior value closed on valid/transaction timeline; new value active |
| T100200-06 | `validate` with `action="invalidate"` | Target item marked invalidated with reviewer note in telemetry |

### Negative Testing
Verify that:
- Scratchpad contents cannot be retrieved across different sessions or banks.
- Batch operations containing invalid tool names fail closed.
- `shared_store` with invalid semantic category is rejected.
- `canonical_put` scoring below admission threshold is rejected.

### Verification Rule
Atomicity claims must be supported by database query assertions proving zero state change following an aborted batch.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-100200-01 | `batch` executes atomically with full rollback | Integration failure test | PASS — `clio-store::batch_tests::sqlite_batch_is_atomic` and `clio-store::batch_pg_tests::postgres_batch_parity` assert `count_items == 0` after a duplicate-id abort; `tests/additive_tools_test.rs::batch_rollback_transcript_leaves_zero_rows` asserts bank row diff == 0 on an unknown-tool abort. |
| AC-100200-02 | Scratchpad is size-bounded and ephemeral | Unit test | PASS — `clio-compliance::scratchpad_tests` covers byte/key caps, overwrite, TTL, and session/bank isolation; `tests/additive_tools_test.rs::scratchpad_quota_and_isolation` returns `quota_exceeded` / `QUOTA_EXCEEDED` on a 64 KiB+1 write. |
| AC-100200-03 | Scratchpad never leaks to search/long-term | Hybrid retrieval query | PASS — `tests/additive_tools_test.rs::scratchpad_isolated_from_long_term_storage` asserts the durable row count is unchanged after a scratchpad write; `additive_tools_tests::scratchpad_content_never_reachable_via_retrieve` indexes a durable probe row, writes a distinct pad-only token, asserts `retrieve` returns the durable hit with no hit carrying the pad token, and asserts a query for the pad-only token returns zero hits. |
| AC-100200-04 | `canonical_put` manages bi-temporal history | Bi-temporal interval query | PASS — `clio-compliance::canonical_tests` and `tests/additive_tools_test.rs::canonical_supersession_transcript` assert two revisions persist (one active, one closed) and `canonical_get` returns the new value; prior row keeps `tx_until`. `batch_tools_canonical_tests::two_canonical_puts_one_key_in_one_batch_leave_one_active_revision` and `batch_tests::sqlite_canonical_put_effect_supersedes_in_transaction` prove two puts on one key in one batch leave exactly one active revision. |
| AC-100200-05 | `shared_*` enforces standard admission gates | Gated write test | PASS — `tests/additive_tools_test.rs::shared_bank_gates` (disabled → `forbidden`) and `additive_tools_shared_tests::shared_store_routes_and_requires_actor_attribution` (bank override and missing `actor` → `invalid_argument`; writes land only in `shared`); `additive_tools_shared_tests::shared_store_rejects_invalid_semantic_category` (unknown category → `invalid_argument`) and `shared_bank_is_unreachable_through_generic_tools_when_disabled` / `batch_tools_canonical_tests::batch_cannot_reach_shared_bank_when_surface_disabled` prove the permission gate is enforced at bank resolution, not only on the `shared_*` wrappers. |
| AC-100200-06 | `validate` logs reviewer attestation | Telemetry query | PASS — `tests/additive_tools_test.rs::validate_actions_transcript` asserts the `validate_invalidate` audit row carries the reviewer note (`"stale"`); `clio-compliance::validate_tests` covers attest/update/invalidate/discard and the note-required rule. |

### Definition of Done
- [x] All Additive tools implemented and bound to MCP stdio and HTTP.
- [x] `tool_schema` pack updated with additive tool schemas.
- [x] Batch atomicity verified.
- [x] Scratchpad isolation verified.
- [x] Tests pass across Postgres and SQLite backends.
- [x] Rust files strictly ≤ 450 lines.
- [x] Required approval is obtained (downstream pipeline step).

### Completion Evidence
- Test output for `tests/additive_tools_test.rs` and `tests/additive_tools_conformance_test.rs`: `cargo test --locked -p clio-mcp` → 156 passed; `cargo test --workspace --locked` → 892 passed (37 suites).
- JSON-RPC transcript of atomic `batch` execution and rollback: `tests/additive_tools_test.rs::batch_atomic_commit_transcript` (2 COMMITTED, bank count 2) and `batch_rollback_transcript_leaves_zero_rows` (unknown-tool abort, bank count 0); `tests/additive_tools_conformance_test.rs::batch_mixed_op_types_commit_transcript` commits all seven op types (`store`, `triple_add`, `canonical_put`, `persona_put_stable`, `task_upsert`, `failure_record`, `graph_link` via `$ref`) in one transaction.
- Schema validation report for additive tool schemas: `additive_tools_are_registered_and_published` asserts `tools/list` returns `batch`, `scratchpad_write`, `scratchpad_read`, `scratchpad_clear`, `canonical_put`, `canonical_get`, `shared_store`, `shared_retrieve`, `shared_discard`, `validate`, and `stats` from the shared catalog served by both stdio and Streamable HTTP.
- Coverage gate: `make coverage` exits 0; aggregate functions 98.71%, lines 97.87% (regions 94.69%); no reported file below 90% functions or lines.

---

## 10. Failure Handling and Recovery

### Expected Failure Modes
| Failure | Detection | Recovery |
|---------|-----------|----------|
| Batch operation failure | Admission or SQL error | Roll back database transaction; return failure report |
| Scratchpad memory exhaustion | Size check before write | Reject write; return `QUOTA_EXCEEDED` |
| Lock contention in batch | DB lock timeout | Fail closed; suggest retry with smaller batch |
| Invalid validate action | Enum validation check | Reject call with invalid parameter error |

### Rollback Strategy
All database mutations inside `batch` run inside explicit database transactions; rollback is guaranteed by the underlying ACID database engine. Scratchpad operations are in-memory and revert on error.

### Partial Completion Policy
If `batch` is complete but `validate` is pending, report partial completion and do not mark Phase 100200 as finished.

---

## 11. Traceability

| Parent Requirement | Implementation Task | Verification | Acceptance Criterion |
|--------------------|---------------------|--------------|-----------------------|
| FR-10, §4.9.5.A | Tasks 1–5 | Integration suite | AC-100200-01–AC-100200-06 |
| FR-21, PR-1 | Task 2 | T100200-03, T100200-04 | AC-100200-02, AC-100200-03 |
| FR-22, §4.9.6 | Tasks 1–5 | MCP tools/list | AC-100200-01 |
| FR-23 | Task 1 | T100200-01, T100200-02 | AC-100200-01 |
| PR-5 | Tasks 1, 3, 4 | T100200-02 | AC-100200-01, AC-100200-05 |
| PR-6 | Task 3, 5 | T100200-05, T100200-06 | AC-100200-04, AC-100200-06 |

Required chain:
```text
Requirement → Capability → Implementation → Test → Evidence
```

---

## 12. Phase Exit Contract

### Outputs Produced
- Operational Additive tools: `batch`, `scratchpad_*`, `canonical_*`, `shared_*`, `validate`, `stats`.
- Published MCP schemas for all Additive tools.
- Conformance test suite verifying atomicity, isolation, and admission governance.

### Guarantees Provided to Downstream Phases
- Coding agents have high-ergonomic batch and ephemeral workspace capabilities.
- Operations phases (021 hygiene, 022 import/export, 023 doctor) can rely on consistent bank statistics and atomic mutators.

### Known Limitations
- Multi-host synchronization for shared banks is deferred. The shared surface is single-host because cross-host replication depends on the client/server sync protocol, which is not built yet; Phase 100240 owns this debt.
- Scratchpad contents do not survive process restarts. The buffer is deliberately process-local and session-scoped so it never enters durable storage or vector indexes (PR-1 / FR-21); no phase owns a durable scratchpad because persistence is out of scope by design.
- `batch` runs on one backend transaction; concurrent batches on the same bank can contend on row locks and fail closed (retry with a smaller batch). No later phase owns lock-contention mitigation.

### Downstream Prerequisites
- Phase 100210 hygiene tools can use `batch` for atomic confirmed cleanups.
- Phase 100220 import tools use `batch` transaction semantics for bulk item ingest.

### Final Status
PASS WITH DOCUMENTED LIMITATIONS

### Verification Sign-Off
- Implementer: OpenCode CLI (Deepseek V4.1 Flash High)
- Verifier: [Name/Agent]
- Human Approver: [Name, if required]
- Date: 2026-09-20

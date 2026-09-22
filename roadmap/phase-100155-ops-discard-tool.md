# Phase 100155: Operations `discard` Tool (Gap Remediation)

### Attribution
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | OpenCode CLI (Go . Deepseek V4.1 Flash High) | done |
| Adversary | r1 | Antigravity CLI (Gemini 3.8 Flash) | done |
| Remediator | r1 | OpenCode CLI (Together . GLM-5.3 Flash High) | done |
| Remedy Approver | r1 | OpenCode CLI (OpenRouter . Deepseek V4.1 Flash Max) | approved |
| Finalize | r1 | OpenCode CLI (Go . Deepseek V4.1 Flash High) | done |

**Index slice 100155 (remediation insert between slices 100150 and 16) · **Effort:** `1×` · **Scope:** remediation slice added 2026-09-19; not part of the original index slice plan (see Provenance).

**Runner invocation note:** the runner formats integer phase numbers (`{phase:03d}`), so this slice runs with `phase_number=100155` and its run dir is `runs/phase-100155`. The roadmap slice number is 15.5; this file is the authoritative definition regardless of the numeric prompt placeholder.

### Provenance (why this slice exists)

- `roadmap/phase-100080-bitemporal-triples-supersession.md` line 59 placed a conditionally in-scope item ("`discard` full ops tool if not already present") under "Explicitly Out of Scope". Discard was not already present, so phase 100080 owed the tool and did not deliver it; its completion evidence recorded the ambiguous limitation "ops `discard` not implemented as supersession" and marked the phase done.
- The schema was built for it (phase 100020/100030): the `items` table carries `discarded_at` / `discard_reason` columns (sql/001_core.sql), and read paths already exclude discarded items (`discarded_at IS NULL` visibility filters in clio-store). No code writes those columns.
- Phase 100160 developer r1 hit this as a hard blocker on 2026-09-19 (BLOCKED before implementation): the MCP write surface minimum set requires binding `discard`, and the phase's stop conditions forbid MCP stubs. This slice closes the gap before phase 100160 re-runs.

### Vocabulary (read first) — zero shared moniker

| Term | Enum / form | Where it lives | Must not |
|------|-------------|----------------|----------|
| **`discard(item_id, reason)`** | Logged ops removal from active use | Core mutator catalog (§4.9.4.A) | Supersede a fact, alias compliance erasure, or bypass telemetry |
| **`invalidate`** | Supersession-adjacent item invalidation | Existing tool (phase 100060/100080 path) | Be silently redirected to or from `discard` |
| **`erase_request` / compliance erase** | Legal crypto-shred of subject DEK (§7.4) | Phase 100190 | Be reachable by calling `discard` |
| **hygiene `discard` action** | Action value inside `hygiene_clean` | Phase 100210 | Be implemented here or conflated with this tool |
| **`discarded_at` / `discard_reason`** | Existing `items` columns | sql/001_core.sql | Be duplicated into a parallel "discards" table |

## 1. Objective

### Goal
Implement the in-process operations `discard` tool (requirement.md §4.9.4.A: logged removal of an item from active use), writing the already-existing `discarded_at` / `discard_reason` columns on both backends, with FR-15 telemetry and §4.9.2 confirmation semantics — so slice 100160 can bind the full 14-tool minimum write set over MCP without a stub.

### Expected Outcome
- `discard(item_id, reason, confirm?)` exists as an in-process tool handler routed through the same tool surface as `update`, `invalidate`, `triple_add`, and friends.
- A confirmed call atomically sets `discarded_at` (UTC timestamp) and `discard_reason` on the target `items` row in both SQLite and Postgres; an unconfirmed call is a dry-run that performs zero writes and returns a structured would-discard response (phase 100160 Task T100155-10 expects exactly this policy).
- Every mutating discard emits a PII-safe FR-15 telemetry event `{operation: "discard", item_id, category, epistemic_kind, actor, timestamp}`.
- Discarded items stay invisible to default reads with no new read-path code (the existing `discarded_at IS NULL` visibility filters already guarantee this); a test proves it end to end.
- The path never touches subject DEKs, item content, or supersession edges (PR-6, §7.4).
- Dual-backend parity tests and the standard coverage gate pass.

### Parent Requirement
`requirement.md` (current) — §4.9.4.A (`discard(item_id, reason)` row), §4.9.2 (destructive-tool confirmation), §7.4 (operations removal path), PR-6, PR-8 (auditable), FR-15, FR-23; phase-100160 minimum write set (Task 5 matrix).

### Design references (non-normative)
- Phase 100210 will route its `hygiene_clean` `discard` action through this path ("ops removal via existing discard path") — keep the tool callable from other in-process callers.
- Phase 100190 asserts `discard` does not shred keys — do not add anything that could.

## 2. Scope Boundaries

### In Scope
- Store-level discard mutation on both backends (atomic `UPDATE items SET discarded_at, discard_reason` semantics behind the existing store trait).
- In-process `discard` tool handler: argument validation (`item_id` required, `reason` required non-empty), confirm-gated mutation with unconfirmed dry-run, structured errors.
- FR-15 telemetry event emission on the mutating path, consistent with how `update` / `invalidate` emit theirs today.
- Idempotency policy for an already-discarded item: pick one (reject with structured error, or succeed as a no-op returning the prior discard), document the choice, and test it.
- Tests: dual-backend, visibility exclusion, telemetry, invalidation independence, dry-run, bank isolation.
- Schema is unchanged: the columns already exist; no migration is required.

### Explicitly Out of Scope
- MCP transport binding (slice 100160 — this slice only makes the in-process tool bindable).
- `hygiene_clean` and its `flag`/`archive` actions (slice 100210).
- Compliance erase / `erase_request` (slice 100190).
- `audit_trail` / `inspect` / `correct` surfaces (slice 100180) — telemetry emission only; the read surface comes later.
- Physical deletion of dense/lexical index entries for discarded items. Reads already filter `discarded_at IS NULL`, so discarded rows never surface; if index cleanup is cheap to hook, MAY do it, otherwise document as a known limitation (phase 100110 permitted async index maintenance on discard paths).
- `batch` composition (slice 100200).
- Archive/soft-delete variants beyond the two columns specified.

### Must Not Change
- PR-6 / FR-12: supersession and invalidation paths are untouched; `discard` is a separate, logged operations path.
- FR-19 / FR-23: `discard` never destroys DEKs and never satisfies `erase_request`.
- Phase 100040 admission gates and existing retrieve filters (including the `discarded_at IS NULL` visibility predicate).
- Existing tool contracts (`update`, `invalidate`, triple tools).
- Bank isolation guarantees on all reads/writes.

### Scope Expansion Rule
If work outside this scope appears necessary:
1. Stop.
2. Document the reason.
3. Request clarification or approval.
4. Do not silently expand scope.

## 3. Preconditions and Dependencies

### Preconditions
- Phases 002/003 accepted: `items` schema carries `discarded_at` / `discard_reason` (verified present in sql/001_core.sql).
- Phases 006/008 accepted: an in-process mutator pattern (`update`, `invalidate`, `triple_add`) exists to follow for validation, telemetry, and store-commit structure.
- Phase 100120 accepted: hybrid retrieve visibility excludes discarded items (verified by the existing SQL predicates; a test must still prove it).

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| `items.discarded_at` / `discard_reason` columns | Present in both backends | Phase 100020 schema |
| In-process mutator pattern | Exists (`update` / `invalidate`) | Phase 100060/100080 code |
| Visibility filter | `discarded_at IS NULL` on reads | clio-store SQL predicates |
| Coverage gate | `make coverage` ≥90% aggregate and per-file | repo Makefile / coverage.md |

If any precondition fails discovery, stop and report (mandatory stop condition) — do not stub.

## 4. Existing-System Discovery

The agent MUST inspect the existing system before deciding where or how to implement the changes.

### Required Discovery
- Where `update` / `invalidate` validate, commit, and emit telemetry — the discard handler mirrors that structure.
- The store trait method surface: whether a discard mutation exists, and where the SQLite/Postgres implementations belong.
- How existing mutators seal/encrypt content (discard must seal `discard_reason` under the same content-protection path used by comparable fields, if any — verify and follow the established pattern; the reason column may be stored plaintext if that is the established convention for operational metadata — document what you find and follow it).
- How FR-15 telemetry events are emitted on other mutating paths.
- Current visibility predicates (`discarded_at IS NULL`) and which read paths they cover.

### Discovery Output
Before implementation, the agent must report: relevant subsystems identified; existing implementation approach; relevant contracts/interfaces; existing test coverage; architectural constraints discovered; assumptions confirmed; assumptions contradicted; questions requiring clarification.

### Repository Adaptation Rule
The agent must determine the concrete implementation locations from the actual repository. The plan does not prescribe file paths, class names, module names, or directory structures unless they are explicitly part of an externally required contract.

## 5. Implementation Specification

### Task 1: Store-Level Discard Mutation (Dual Backend)

#### Intent
One audited operations-removal write behind the existing store abstraction (§7.4).

#### Required Capability or Behavior
- A store operation that atomically sets `discarded_at` (UTC) and `discard_reason` on the target `items` row, scoped to the caller's bank.
- Unknown `item_id` → structured not-found error; cross-bank `item_id` → not found (never leak existence).
- Already-discarded item → apply the documented idempotency policy from In Scope.
- Content payloads and DEKs are untouched; no rows are deleted.
- SQLite and Postgres implementations with parity tests.

#### Architectural Responsibility
Discard write path in the store layer (both backends) + tool handler.

#### Required Changes
1. Store trait + SQLite/Postgres implementations.
2. Tool handler with validation, confirm gate, telemetry.
3. Tests listed in section 8.

#### Implementation Constraints
- No migration; columns exist.
- Do not implement delete-as-supersede and do not touch triple edges (PR-6).
- Emit telemetry only on confirmed mutations (a dry-run writes nothing and logs nothing mutable — a SHOULD-level dry-run telemetry event is acceptable if the existing telemetry pattern prefers it; document the choice).

#### Expected Result
A confirmed discard on SQLite and on Postgres marks the row; the item disappears from default visibility; telemetry shows one `discard` event.

### Task 2: In-Process `discard` Tool with Confirmation Semantics

#### Intent
The §4.9.4.A mutator, gated per §4.9.2, ready for slice-16 MCP binding.

#### Required Capability or Behavior
- `discard(item_id, reason, confirm?)`: without `confirm=true`, zero writes and a structured dry-run response (would-discard with the resolved item identity); with `confirm=true`, the mutation of Task 1.
- Reason is required and non-empty (structured error otherwise).
- The handler follows the same routing/validation pattern as the other in-process write tools so the slice-16 schema/dispatcher binds it without rework.
- Telemetry event per FR-15 with `operation: "discard"`.
- A boundary note (code-level check or documented invariant) that discard performs no key destruction and no content shredding — the phase-100190 negative tests will pin this from their side.

#### Architectural Responsibility
Tool handler layer; store mutation from Task 1.

#### Required Changes
1. Handler + argument validation + confirm gate.
2. Telemetry emission.
3. Handler-level tests (dry-run, confirm, error shapes).

#### Implementation Constraints
- Not a hygiene action (no noise scoring); not compliance erasure.
- Harness-invocation confirmation plumbing (transport-level) belongs to slice 100160 (§4.9.2); the in-process confirm flag is the mechanism it will drive.

#### Expected Result
`discard` without confirm returns counts/identity and changes nothing; `discard` with confirm performs exactly the Task-1 mutation.

### Task 3: Visibility, Isolation, and Coverage Verification

#### Intent
Prove the removal is real and the blast radius is contained.

#### Required Capability or Behavior
- End-to-end: admitted item → discard (confirmed) → default retrieve/search/hybrid path no longer returns it; `as_of`/temporal reads behave per the established convention (document what a discarded item does for point-in-time triple reads if the item participates in triples — do not silently change those semantics).
- Bank isolation: discard in bank A never affects or reveals bank B.
- Invalidate independence: an invalidated item can still be discarded and vice versa; the two paths never alias.
- `make check` and `make coverage` pass with the per-file ≥90% gate.

#### Architectural Responsibility
Test layer + coverage procedure.

#### Required Changes
1. Tests per section 8.
2. Any store/handler adjustments the tests expose.

#### Implementation Constraints
- Do not weaken existing visibility filters to make tests pass.
- Do not add a parallel discards table; the columns are the SoT.

#### Expected Result
All listed tests pass; coverage gate green.

### Implementation Freedom
The agent may choose the concrete implementation structure, file locations, naming, and internal design provided that: the required behavior is satisfied; architectural boundaries are respected; existing contracts are preserved; all acceptance criteria pass; no prohibited changes are introduced.

## 6. Agent Execution Rules

### Allowed Actions
- Inspect and modify the repository as required to implement the in-scope capabilities.
- Add or update implementation components where appropriate.
- Add or update tests required to verify the behavior.
- Refactor locally when necessary to implement the specified capability without changing unrelated behavior.

### Forbidden Actions
- Change public contracts without approval.
- Delete or bypass tests.
- Disable security controls.
- Introduce unrelated features.
- Perform unrelated broad refactoring.
- Upgrade dependencies without approval.
- Commit secrets.
- Claim completion without evidence.
- Ship an MCP binding or stub for `discard` (slice 100160 owns that surface).
- Touch DEKs, content payloads, or supersession edges from the discard path.

### Agent Decision Boundary
The agent may decide: concrete file/module/class placement; idempotency policy for repeat discard (documented); dry-run response shape; test organization; non-breaking implementation details.

The agent must request approval for: architecture changes beyond the stated scope; breaking API or data-contract changes; security-sensitive policy decisions; changes affecting downstream phase assumptions (especially the §4.9.2 confirmation contract slice 100160 will bind).

### Mandatory Stop Conditions
Stop and report (BLOCKED) if:
- Requirements are ambiguous.
- Repository facts contradict the plan (e.g. the columns or the visibility predicates are missing).
- Required dependencies are missing.
- Scope expansion is required.
- Existing architecture cannot support the intended behavior without an unapproved structural change.
- Correctness cannot be verified.

## 7. Security Constraints

### Required Controls
- Bank isolation on the discard write and any readback.
- Confirm gate per §4.9.2 (unconfirmed = dry-run, zero writes).
- PII-safe telemetry: ids and operation only — never log `reason` content in telemetry (it may contain personal data); length may be logged.
- No content deletion, no DEK interaction, no key destruction on this path (§7.4 separation).

### Sensitive Data Rules
- Never log the full `reason` text in telemetry or run logs; mask if echoed.
- Never commit secrets.

### Security Acceptance Conditions
- No unconfirmed write path exists.
- Cross-bank discard is impossible (not-found, never partial).
- The discard path performs no crypto operations.

## 8. Test and Verification Strategy

### Required Tests
- [ ] Unit tests
- [ ] Integration tests
- [ ] Contract tests
- [ ] End-to-end tests
- [ ] Regression tests
- [ ] Security tests
- [ ] Failure-mode tests

### Required Test Scenarios

| Test ID | Scenario | Expected Result |
|---------|----------|-----------------|
| T100155-01 | Confirmed discard sets `discarded_at` + `discard_reason` | Row marked; UTC timestamp; reason persisted |
| T100155-02 | Unconfirmed `discard` (no confirm) | Dry-run: zero writes, structured would-discard response |
| T100155-03 | Discarded item excluded from default visibility | Retrieve/search return it in no default domain |
| T100155-04 | Unknown item_id | Structured not-found; no write; no telemetry event |
| T100155-05 | Cross-bank item_id | Not found; no existence leak; no write |
| T100155-06 | Repeat discard of an already-discarded item | Documented policy applied (reject or no-op), tested |
| T100155-07 | FR-15 telemetry on confirmed discard | One `discard` event with required fields; reason absent |
| T100155-08 | Discard does not touch DEKs or content | Content payload intact; keys unaffected |
| T100155-09 | Invalidate independence | Invalidate and discard compose without aliasing |
| T100155-10 | Bank isolation | Bank-scoped write/read only |
| T100155-11 | Dual-backend parity | SQLite and Postgres behave identically on T100155-01/T100155-02/T100155-06 |
| T100155-12 | Telemetry on dry-run is write-free | Dry-run emits no mutating event (per documented policy) |

### Negative Testing
Verify that: invalid input is rejected with structured errors; a discard with an empty `reason` is rejected; no path from `discard` destroys keys or content; existing retrieve/visibility tests remain intact; no parallel discards table appears.

### Verification Rule
Implementation claims must be supported by actual test output, inspection results, or other concrete evidence.

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence | Result |
|-------|----------------------|---------------------|-------------------|--------|
| AC-100155-01 | In-process `discard` tool exists with §4.9.2 confirm semantics | T100155-01, T100155-02 | Tests | PASS — `clio-write/src/discard_tests.rs`: `dry_run_writes_nothing` (unconfirmed = zero writes, no telemetry), `confirmed_emits_one_pii_safe_event` (confirm mutates) |
| AC-100155-02 | Dual-backend store mutation with parity | T100155-01, T100155-10 | Tests | PASS — `clio-store/src/discard_tests.rs`: `sqlite_discard_contract` + `postgres_discard_contract` run the identical suite (mutation, not-found, cross-bank, repeat, content-intact) |
| AC-100155-03 | FR-15 telemetry on the mutating path | T100155-06, T100155-07, T100155-12 | Tests | PASS — one `DiscardEvent` per confirmed discard with `{operation,bank,actor,timestamp,item_id,category,epistemic_kind,reason_len}` and no reason text; dry-run and rejected repeats emit none |
| AC-100155-04 | Visibility exclusion proven end to end | T100155-03 | Test + inspection | PASS — `suite_visibility` (both backends): lexical + dense search, `indexable_items`, `count_indexable_items`, and `index_coverage` all exclude the discarded row while the row survives |
| AC-100155-05 | PR-6/§7.4 boundaries held (no supersession, no key interaction) | T100155-08, T100155-09 | Tests | PASS — `suite_discard` asserts snapshot/gist and `content_ciphertext` unchanged; `invalidate_and_discard_are_independent` proves the paths never alias |
| AC-100155-06 | Coverage gate (aggregate and per-file ≥90% functions/lines) | `make coverage` | Coverage output | PASS — exit `0`; TOTAL lines `95.38%`, functions `98.85%`; every reported file ≥90% on both metrics |

### Definition of Done
- [x] All in-scope behavior is implemented.
- [x] All acceptance criteria pass with evidence.
- [x] Required tests pass (`make check`).
- [x] No unauthorized changes were introduced (only the new discard path; existing tool contracts untouched).
- [x] Existing behavior remains intact (full workspace suite green, clippy `-D warnings` clean).
- [x] Security checks pass (bank-scoped write/readback, confirm gate, PII-safe telemetry, no DEK/content access).
- [x] Documentation updated (Attribution table, Completion Evidence).
- [x] Verification completed (`make check`, `make coverage` per `./coverage.md`).
- [x] Required approval is obtained (downstream pipeline step).

### Completion Evidence

**Implementation summary**
- New `clio-store` `Store` methods `get_item_identity` (bank-scoped identity columns, no content/DEK access) and `discard_item` (atomic `UPDATE items SET discarded_at, discard_reason, updated_at WHERE id AND bank_id AND discarded_at IS NULL`), implemented per backend in `sqlite_discard.rs` / `postgres_discard.rs` and delegated from `sqlite_store.rs` / `postgres_store.rs`. New `clio_store::ItemIdentity` model type.
- New `clio-write` module `discard.rs`: `discard(DiscardArgs)` handler with argument validation (`item_id`, non-empty `reason`), §4.9.2 confirm gate, `DiscardOutcome::{DryRun,Discarded}`, and `DiscardEvent`/`DiscardSink`/`DiscardVecSink` FR-15 telemetry. Re-exported from `clio-write::lib`.
- No schema change: `items.discarded_at` / `discard_reason` already exist (sql/001_core.sql). No parallel discards table.

**Policy decisions (documented)**
- **Repeat discard:** rejected with `InvalidArgument` ("already discarded"); enforced atomically by the store. Tested per backend.
- **Dry-run:** zero writes and zero telemetry (`DiscardOutcome::DryRun` returns the resolved identity); the SHOULD-level dry-run event was declined to keep the mutating telemetry stream clean.
- **Timestamp:** the caller-provided UTC timestamp (mutator convention, as with `invalidate`) is written to `discarded_at`; `updated_at` is stamped server-side via `now_iso()`.
- **`discard_reason` storage:** plaintext. It is operational metadata like `source_ref`/`hygiene_flag`/`audit_events.detail_json`; only content halves are DEK-sealed. It never enters telemetry (only `reason_len` does).
- **Audit record:** FR-15 emission is via the shared telemetry-sink pattern used by `invalidate`/`triple_end`; no `audit_events` row is written (that read surface belongs to the audit-trail phase). The `items` columns are the source of truth.
- **Index cleanup:** derived dense/lexical rows are not physically deleted; reads already filter `discarded_at IS NULL` (proven end to end). Deferred per the phase's known-limitations allowance.

**Test execution output**
- `make check` (fmt + clippy `-D warnings` + `cargo test --locked --workspace`) exit `0`; 26 test binaries green.
- `cargo test --locked -p clio-store discard`: `sqlite_discard_contract`, `postgres_discard_contract` pass. `cargo test --locked -p clio-write discard`: `dry_run_writes_nothing`, `confirmed_emits_one_pii_safe_event`, `validation_and_not_found`, `invalidate_and_discard_are_independent` pass.
- `make coverage` exit `0`: TOTAL lines `95.38%`, functions `98.85%`; no reported file below 90% on functions or lines. New-file per-file (functions / lines): `clio-store/src/sqlite_discard.rs` `100%` / `94.94%`; `clio-store/src/postgres_discard.rs` `100%` / `95.00%`; `clio-write/src/discard.rs` `100%` / `100%`; `clio-store/src/model.rs` `100%` / `100%`.

**Not verified / limitations**
- MCP transport binding is out of scope (slice 100160); the tool is in-process only.
- Point-in-time triple reads for a discarded item are unchanged (no triple-edge interaction on this path).

## 10. Failure Handling and Recovery

### Expected Failure Modes
| Failure | Detection | Recovery |
|---------|-----------|----------|
| Unknown / cross-bank item | Structured not-found | Caller corrects the id |
| Repeat discard | Documented idempotency policy | Structured error or no-op |
| Unconfirmed call | Dry-run response | Caller re-invokes with confirm |
| Telemetry write failure | Propagated error | Mutation fails; no untracked discard |

### Rollback Strategy
Revert code; the columns return to their pre-phase state (all NULL). No migration to undo.

### Partial Completion Policy
If only part of the phase is complete: do not claim full completion; record completed and incomplete work separately; document remaining work; do not leave undocumented broken state.

## 11. Traceability

| Parent Requirement | Implementation Task | Verification | Acceptance Criterion |
|--------------------|---------------------|--------------|-----------------------|
| §4.9.4.A `discard(item_id, reason)` | Task 2 | T100155-01, T100155-02, T100155-06 | AC-100155-01 |
| §4.9.2 destructive confirmation | Task 2 | T100155-02, T100155-12 | AC-100155-01 |
| §7.4 ops removal path | Task 1 | T100155-01, T100155-08 | AC-100155-02 |
| PR-6 / FR-12 / FR-23 boundaries | Tasks 1–2 | T100155-08, T100155-09 | AC-100155-05 |
| FR-15 telemetry | Task 2 | T100155-06, T100155-07, T100155-12 | AC-100155-03 |
| Phase-100160 minimum write set | Task 3 | T100155-03 + phase-100160 re-run | AC-100155-04 |

Required chain: Requirement → Capability → Implementation → Test → Evidence. Every acceptance criterion must be traceable.

## 12. Phase Exit Contract

### Outputs Produced
- In-process `discard` tool: dual-backend store mutation, confirm-gated handler, FR-15 telemetry.

### Guarantees Provided to Downstream Phases
After this phase is accepted:
- Slice 100160 can bind the full 14-tool minimum write set (its phase-100160 r1 blocker is resolved); `discard` confirmation rides the same §4.9.2 mechanism as other destructive tools.
- Slice 100180 telemetry includes `discard` events on the uniform pipeline.
- Slice 100210's `hygiene_clean` can route its `discard` action through this path.
- Slice 100190's negative tests (`discard` does not shred keys) have a real path to exercise.

### Known Limitations
- Dense/lexical index entries for discarded items are not physically deleted by default (reads already exclude discarded rows); cleanup MAY be hooked if cheap, else deferred and documented.
- Point-in-time semantics for triples referencing a discarded item follow the existing convention and are not changed by this slice.

### Final Status
PENDING

### Verification Sign-Off
- Implementer: (pipeline Developer step, this run)
- Verifier: (pipeline Adversary/Remediator steps, this run)
- Human Approver: (if required)
- Date: 2026-09-19
# Phase 100030: Memory Item Core and Dual Representations

### Attribution
| Role | Agent |
|------|-------|
| Developer | Cursor (Auto) |
| Adversary | Cursor (Auto) |
| Adversary (phase-100420 r1 pass) | OpenCode CLI (OpenRouter . Deepseek V4.1 Flash Max); 7 findings filed (`runs/phase-100420/findings-task2-003-005.json`), 6 remedied with tests, F-04 accepted risk (live-model CI exercise, unowned), F-07 build-time validation accepted as designed |

**Index slice 100030 · **Effort:** `1×` · **Scope:** `roadmap/index.md` slice 100030 (authoritative)

## 1. Objective

### Goal
Ship repository create/read/update for **semantic** and **episodic** memory items with provenance, confidence, admission-related fields, and separate **snapshot** vs **gist** storage. Exact-value consumers always read snapshots; gists stay non-authoritative (PR-4). These are **repository primitives only**—no public harness write may bypass the admission gates delivered in Phase 100040.

### Expected Outcome
- Durable item model aligned with §7.1 / operational dual-representation needs (FR-5, FR-26).
- APIs (in-process repository and/or internal services) to create/read/update items and to `get_snapshot` / `get_gist` separately.
- Provenance, confidence, `epistemic_kind`, and admission-score fields exist on the record even if scoring is not yet enforced at a public gate.
- **FR-14:** when `epistemic_kind = belief`, `source_type` is **mandatory** (`user_stated` | `agent_inferred` | `third_party`); when `epistemic_kind = fact`, `source_type` MUST NOT be required (and SHOULD be absent).
- No public long-term write path that commits without going through a clearly marked “ungated/internal” boundary reserved for Phase 100040 wrapping.

### Parent Requirement
`requirement.md` (current) — PR-4, §2.5, §4.4 dual representation, §7.1, FR-5, FR-14, FR-26; foreshadow provenance for FR-15 / PR-8.

---

## 2. Scope Boundaries

### In Scope
- Semantic and episodic item repository CRUD on Phase 100020 storage.
- Separate snapshot and gist content slots (encrypted via DEK path).
- Mandatory metadata: provenance/`source_ref`, confidence, `epistemic_kind` (`fact`|`belief`), **`source_type` required iff `epistemic_kind = belief`** (FR-14), admission_score field, timestamps / validity placeholders as schema allows.
- Read APIs: get by id, get_snapshot, get_gist.
- Clear internal vs future public write boundary documentation in code (gates arrive in Phase 100040).

### Explicitly Out of Scope
- Category whitelist enforcement and five-factor scoring decisions (Phase 100040).
- Span verification / extraction (slice 100050).
- Parallel write path, MemTree, consolidation (slices 100060–7).
- Bi-temporal triple supersession engine (slice 100080).
- Public MCP `store` tool (slice 100160) — repository only.
- Treating gist as authoritative for exact values.

### Must Not Change
- Phase 100020 ciphertext and dual-backend contracts.
- Phase 100010 `bank` / `actor` / config contracts.
- PR-4 rule: snapshot authoritative; gist non-authoritative.

### Scope Expansion Rule
If work outside this scope appears necessary:
1. Stop.
2. Document the reason.
3. Request clarification or approval.
4. Do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- Phase 100020 accepted: shared persistence + DEK encrypt/decrypt available.
- Phase 100010 accepted: `bank` / `actor` context.

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| Phase 100020 repository contract | CRUD + ciphertext works | Prior phase exit evidence / tests |
| DEK provider | Encrypt/decrypt operational | Round-trip test |
| Schema for items | Extensible for snapshot/gist refs | Migration apply |

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

### Task 1: Item Domain Model

#### Intent
Encode semantic vs episodic items and dual representations in the domain model.

#### Required Capability or Behavior
- Semantic items carry category field (enum values from §4.1) without enforcing the gate yet.
- Episodic items carry an episodic type tag (`triple` | `gist` | `task` | `failure` | `temporal`) rather than inventing a sixth semantic category (§4.9.4 `store` notes).
- Every operational unit can hold snapshot and gist as separate fields/refs (FR-5).
- `epistemic_kind` is mandatory (`fact`|`belief`). **FR-14:** if `epistemic_kind = belief`, `source_type` MUST be one of `user_stated` | `agent_inferred` | `third_party`; if `epistemic_kind = fact`, `source_type` MUST NOT be required (reject or strip if present, document the chosen rule). Append-only confidence_history for beliefs may land fully in slice 100100; Phase 100030 MUST still refuse belief writes that omit `source_type`.

#### Architectural Responsibility
Domain / model layer above persistence.

#### Required Changes
1. Define item structs/enums matching §7.1 spirit and dual-representation needs.
2. Validation for structural well-formedness (not admission scoring).
3. Map model ↔ storage envelopes from Phase 100020.

#### Implementation Constraints
- Do not auto-admit on construction.
- Do not blend snapshot and gist into one field.

#### Expected Result
Unit tests for serialization/model invariants.

### Task 2: Repository Create / Read / Update

#### Intent
Provide durable CRUD primitives scoped by bank.

#### Required Capability or Behavior
- Create item with provenance, confidence, epistemic_kind, admission_score (may be unset/zero until Phase 100040 fills it).
- Read by id within bank.
- Update mutable fields under explicit rules (do not silently destroy history semantics needed later — prefer additive fields; do not implement full invalidate engine yet).
- All content fields pass through DEK encryption.

#### Architectural Responsibility
Memory item repository (application service over persistence port).

#### Required Changes
1. Create/read/update APIs.
2. Bank isolation checks.
3. Actor stamped on write for future FR-15.

#### Implementation Constraints
- Mark APIs as **ungated repository primitives**; Phase 100040 must wrap public writes.
- No MCP exposure required in this phase.

#### Expected Result
Integration tests on at least one backend (prefer both if CI allows) for CRUD.

### Task 3: Snapshot and Gist Separation

#### Intent
Enforce PR-4 at the read API boundary.

#### Required Capability or Behavior
- `get_snapshot(item_id)` returns structured snapshot only (FR-26).
- `get_gist(item_id)` returns prose gist only.
- Exact-value oriented helpers/docs MUST point at snapshot, not gist.
- Missing snapshot vs missing gist are distinct outcomes.

#### Architectural Responsibility
Read API / item service.

#### Required Changes
1. Separate getters.
2. Tests proving gist cannot be the sole returned payload from snapshot API.
3. Store both halves when provided on create/update.

#### Implementation Constraints
- Span verification of snapshot contents is out of scope (slice 100050); store what the caller provides structurally.
- Summarize/regenerate gist tooling out of scope except storing a provided gist.

#### Expected Result
Tests: snapshot get ≠ gist get; consumers needing exact values use snapshot API.

### Task 4: Public Write Boundary Guardrails

#### Intent
Prevent accidental bypass of Phase 100040 gates in harness packaging.

#### Required Capability or Behavior
- Coding-agent profile / tool inventory MUST NOT expose a long-term `store` that writes around gates.
- If a temporary internal write helper exists for tests, it is clearly named and not registered as a Core tool.

#### Architectural Responsibility
Packaging boundary between repository and future tool layer.

#### Required Changes
1. Audit Phase 100010 tool inventory: `store` remains stub or absent until gated.
2. Document in code comments / module docs that repository writes are ungated primitives.
3. Add a test or lint-style check that Core `store` is not wired to raw repository create without an admission hook seam.

#### Implementation Constraints
- Do not implement Phase 100040 scoring here.
- Do not delete repository create — gates wrap it next phase.

#### Expected Result
Inventory/guard test fails if ungated `store` is publicly wired.

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

### Agent Decision Boundary
The agent may decide:
- Concrete file/module/class placement.
- Internal implementation structure.
- Local refactoring required for the phase.
- Test organization.
- Non-breaking implementation details.

The agent must request approval for:
- Architecture changes beyond the stated scope.
- Breaking API or data-contract changes.
- Security-sensitive policy decisions.
- Destructive data operations.
- Changes affecting downstream phase assumptions.

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

---

## 7. Security Constraints

### Required Controls
- All snapshot/gist payloads encrypted via Phase 100020 DEK path.
- Bank-scoped access on read/write.
- Actor attribution recorded on mutating repository calls.

### Sensitive Data Rules
- Never log full snapshot/gist plaintext in tests beyond fixtures; prefer redaction in debug logs.
- Never commit secrets.
- Use approved configuration for any fixture KMS keys.

### Security Acceptance Conditions
- Cross-bank get returns not-found / forbidden.
- Ciphertext remains opaque at storage inspection layer.

---

## 8. Test and Verification Strategy

### Required Tests
- [x] Unit tests
- [x] Integration tests
- [x] Contract tests
- [x] End-to-end tests
- [x] Regression tests
- [x] Security tests
- [x] Failure-mode tests

### Required Test Scenarios

| Test ID | Scenario | Expected Result |
|---------|----------|-----------------|
| T100030-01 | Create semantic item with snapshot+gist | Persisted; both halves readable separately |
| T100030-02 | Create episodic item with type tag | Persisted without forging sixth semantic category |
| T100030-03 | `get_snapshot` | Structured snapshot only |
| T100030-04 | `get_gist` | Gist only; documented non-authoritative |
| T100030-05 | Missing snapshot | Distinct error from missing gist |
| T100030-06 | Cross-bank read | Denied / not found |
| T100030-07 | Public `store` wiring check | Not bound to ungated create |
| T100030-08 | Create belief without source_type | Rejected (FR-14) |
| T100030-09 | Create belief with valid source_type | Persisted |
| T100030-10 | Create fact with source_type present | Rejected or stripped per documented rule |

### Negative Testing
Verify that:
- Invalid input is rejected at structural validation.
- Unauthorized bank access is blocked.
- Partial failures are handled safely.
- Duplicate id behavior is defined and tested.
- Prior phase tests remain intact.
- Failure does not leave plaintext content in the DB.

### Verification Rule
Implementation claims must be supported by actual test output,
inspection results, or other concrete evidence.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-100030-01 | Semantic + episodic CRUD works | Integration tests | Test output |
| AC-100030-02 | Snapshot and gist stored and fetched separately | T100030-01, T100030-03, T100030-04 | Test output |
| AC-100030-03 | Provenance, confidence, epistemic_kind present; belief source_type mandatory (FR-14) | Unit/integration T100030-08–T100030-10 | Schema/assertions |
| AC-100030-04 | Exact-value read path is snapshot API | T100030-03 + docs/inspection | Evidence note |
| AC-100030-05 | No public ungated long-term `store` | T100030-07 | Guard test output |
| AC-100030-06 | Content remains encrypted at rest | Security inspection/test | Pass log |

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
- **Implementation summary:** Typed `MemoryItem` model (`clio-types`) + `Store` create/read/update, `get_snapshot` / `get_gist` on SQLite and Postgres; DualContent ciphertext via DEK path; FR-14 belief `source_type` rules; inventory guard keeps public `store` stubbed.
- **Discovered/affected:** `clio-types` item model, `clio-store` memory CRUD + schema reshape `class`→`epistemic_kind`, `gate_boundary_tests` / inventory contract.
- **Test execution:** `memory_item_tests` suites both backends; FR-14 unit/integration; `make coverage` gate.
- **Known limitations:** see §12 (ungated repository create; legacy `put_item`; destructive empty-DB reshape).

---

## 10. Failure Handling and Recovery

### Expected Failure Modes

| Failure | Detection | Recovery |
|---------|-----------|----------|
| Decrypt failure | Read error | Fail closed; do not return partial plaintext |
| Invalid epistemic_kind/category shape | Validation error | Reject write |
| Partial update failure | Transaction abort | No half-written dual representation |
| Accidental public ungated store | Guard test | Block phase exit until fixed |

### Rollback Strategy
Revert code; roll back item-schema migrations if needed. Encrypted payloads remain inert without DEKs.

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
| FR-5 / PR-4 | Tasks 1, 3 | T100030-01, T100030-03, T100030-04 | AC-100030-02, AC-100030-04 |
| FR-26 | Task 3 | T100030-03, T100030-04 | AC-100030-02 |
| FR-14 | Task 1 | T100030-08–T100030-10 | AC-100030-03 |
| PR-8 provenance fields | Task 2 | T100030-01 | AC-100030-03 |
| FR-21 foreshadow / index §3 | Task 4 | T100030-07 | AC-100030-05 |
| §7.1 model | Task 1 | Model tests | AC-100030-01, AC-100030-03 |

Required chain:

```text
Requirement → Capability → Implementation → Test → Evidence
```

Every acceptance criterion must be traceable.

---

## 12. Phase Exit Contract

### Outputs Produced
- Item repository with semantic/episodic CRUD.
- Dual snapshot/gist representations and separate getters.
- Ungated-primitive boundary ready for Phase 100040 wrapping.

### Guarantees Provided to Downstream Phases
After this phase is accepted:
- Phase 100040 can call repository create only after gates pass.
- Later extraction can fill snapshot/gist slots without redesigning item storage.
- FR-26 read split exists before MCP read surface.

### Known Limitations
- Admission not enforced on repository create.
- No span verification.
- No MemTree / triples engine / MCP `store`.

### Downstream Prerequisites
- Phase 100040 MUST wrap all public long-term writes.
- Slice 100050 MUST verify spans before treating snapshots as admitted facts.

### Final Status
**PASS WITH DOCUMENTED LIMITATIONS** (2026-09-17)

### Verification Sign-Off

- Implementer: Cursor (Auto)
- Verifier: adversarial-review findings remediations (2026-09-17)
- Human Approver: approved (2026-09-17)
- Date: 2026-09-17

### Documented limitations (exit)
- Admission gates are not enforced on repository create (Phase 100040).
- `put_item` remains a legacy opaque-envelope path; typed reads require DualContent via `create_memory_item`.
- Schema reshape for `class` → `epistemic_kind` wipes undeployed DBs (SQLite user tables / Postgres `public`); replace with non-destructive migrations before production.

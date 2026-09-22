# Phase 100372: Full CLI Safe Workspace and Harness Write Surface

### Attribution
Rounds below record plan authorship; implementation sign-off is in §12.
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | [TBD] | [TBD] |
| Adversary | r1 | [TBD] | [TBD] |
| Remediator | r1 | [TBD] | [TBD] |
| Remedy Approver | r1 | [TBD] | [TBD] |
| Finalize | r1 | [TBD] | [TBD] |

**Follow-up phase 100372 · **Effort:** ~3 days · **Gaps:** `gaps/full-cli.md` §6, §7 step 2 (harness/workspace writes)

## 1. Objective

### Goal
Expose the additive harness/workspace tools on the CLI: persona writes, task/failure writes, scratchpad, canonical, shared-surface, `validate`, and atomic `batch` — all with the same semantics and gating as MCP, and with `--dry-run` where a mutation is possible.

### Expected Outcome
- These run standalone: `persona put`/`persona observe`, `task upsert`, `failure record`, `scratchpad write|read|clear`, `canonical put|get`, `shared store|retrieve|discard`, `validate <id> --action ...`, `batch --file ops.json`.
- Scratchpad never writes long-term stores (FR-21); shared/scratchpad are not treated as durable memory.
- `batch` reads operations from a file (and `--file -` from stdin); malformed input fails closed before any write.

### Parent Requirement
`gaps/full-cli.md` §6, §7 step 2; `requirement.md` §4.9.2 item 2, FR-21 (scratchpad must not write long-term), the additive-tool requirements (Phase 100200), FR-10/FR-20.

### Design References
- Phase 100366 output/exit contract and in-process dispatch; Phase 100370 write pattern.
- Catalog/schemas: `bound_tools()` (`crates/clio-mcp/src/lib.rs:158`), `schema_pack()`.
- Additive tool semantics: Phase 100200 (`phase-100200-additive-harness-workspace-tools.md`).
- Masking/redaction: `clio_config::secret`, `clio_ops::redact_credentials`.

---

## 2. Scope Boundaries

### In Scope
- `clio persona stable|observe` → `persona_put_stable` / `persona_observe_preference`. (`clio persona get` is a read and is delivered by Phase 100368; it is not owned here.)
- `clio task upsert`, `clio failure record`.
- `clio scratchpad write|read|clear`.
- `clio canonical put|get`.
- `clio shared store|retrieve|discard`.
- `clio validate ID --action attest|update|invalidate|delete`.
- `clio batch --file ops.json [--dry-run]` (batch atomic).
- `--dry-run` on mutating commands where the underlying tool supports preview.

### Explicitly Out of Scope
- Destructive long-term mutations (`update`, `invalidate`, `discard`, `correct`) — Phase 100374.
- Hygiene/export/import/erase — Phase 100376; config/ranking/sync — Phase 100378.
- New memory semantics or categories.

### Must Not Change
- Gating, masking, bank/actor semantics.
- MCP names/arguments/semantics.
- Scratchpad must remain ephemeral; the ADR that shared/scratchpad are not durable memory stands.

### Scope Expansion Rule
If work outside this scope appears necessary: stop, document the reason, request clarification or approval, and do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- Phase 100366 accepted; Phase 100370 accepted (write pattern + gated dispatch).
- The additive tools exist over MCP (Phase 100200).

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| In-process dispatch | Additive tools callable | `crates/clio-mcp/src/lib.rs` |
| `batch` atomicity | All-or-nothing apply | Phase 100200 semantics |
| Coverage guard | Per-file floor | `make coverage` |

---

## 4. Existing-System Discovery

The agent MUST re-verify the following; the facts below were confirmed at plan time.

### Required Discovery
- Enumerate the additive tools and their schemas for 1:1 flag mirroring.
- Confirm `batch` input shape and atomicity (roll back on any failure).
- Confirm scratchpad storage is separate from long-term stores (FR-21).
- Confirm `validate` action semantics and authorization.
- Confirm which additive mutations support a preview/`--dry-run`.

### Discovery Output
- **Additive tools are MCP-bound** (`bound_tools()`); the CLI is an additional binding with identical names/semantics.
- **`batch` takes a file of operations**, which avoids argv-JSON pain and is the safe bulk path.
- **Scratchpad is explicitly non-long-term** (FR-21 / §4.9); the CLI must not turn it into a durable write.
- **`validate` changes a memory the caller may not have authored**, preserving original authorship (collaborative ownership).
- **`--dry-run` support varies** by tool; expose it uniformly where the tool supports preview.

### Repository Adaptation Rule
The agent must determine concrete implementation locations from the actual repository.

---

## 5. Implementation Specification

### Task 1: Persona, Task, and Failure Writes

#### Intent
Bind the entity/history write tools.

#### Required Capability or Behavior
- `clio persona stable KEY VALUE ...` and `clio persona observe KEY VALUE ...` map to `persona_put_stable`/`persona_observe_preference`; discrete stables use invalidation-style puts; continuous preferences use the shared EMA engine (no second implementation).
- `clio task upsert` and `clio failure record` write history records with length caps where applicable.
- Flags mirror the MCP schema 1:1.

#### Architectural Responsibility
`clio-lib` renders; persona/task semantics stay in existing crates.

#### Required Changes
1. Add a group module and tests.

#### Implementation Constraints
- No re-implementation of EMA or history logic.
- No dependency; no semantic divergence.

#### Expected Result
Persona/task/failure writes work standalone and identically to MCP.

### Task 2: Scratchpad, Canonical, Shared, Validate, and Batch

#### Intent
Bind the workspace/additive tools with correct isolation.

#### Required Capability or Behavior
- `clio scratchpad write|read|clear` operates only on ephemeral storage.
- `clio canonical put|get` and `clio shared store|retrieve|discard` behave as MCP.
- `clio validate ID --action attest|update|invalidate|delete` preserves original authorship.
- `clio batch --file ops.json [--dry-run]` applies operations atomically; `--file -` reads stdin; malformed input fails closed before any write.

#### Architectural Responsibility
`clio-lib` renders; the additive crates own semantics and atomicity.

#### Required Changes
1. Add group modules and tests, including batch atomicity and stdin input.

#### Implementation Constraints
- Scratchpad must not touch long-term stores.
- `batch` dry-run performs zero writes and reports the plan.
- No new dependency.

#### Expected Result
All additive/workspace writes are CLI-reachable with unchanged semantics.

### Implementation Freedom
The agent may choose module layout and flag spellings, provided semantics, isolation, and atomicity hold.

---

## 6. Agent Execution Rules

### Allowed Actions
- Add additive-write modules, `--dry-run`, batch file/stdin handling, tests, and help.
- Reuse the Phase 100366 contract.

### Forbidden Actions
- Make scratchpad durable; bypass gating; change MCP semantics.
- Add dependencies; add destructive long-term mutations (Phase 100374 owns them).

### Agent Decision Boundary
The agent may decide parsing/rendering. The agent must request approval for a semantic change or a new required input format.

### Mandatory Stop Conditions
Stop and report if scratchpad cannot be kept separate from long-term stores, if `batch` cannot be made atomic, or if a tool cannot be reached in-process.

---

## 7. Security Constraints

### Required Controls
- Validate batch input before any write; all-or-nothing apply.
- Mask secrets in errors; never print plaintext credentials.
- Preserve `validate`'s collaborative-ownership rule (original author retained).

### Sensitive Data Rules
- Never log secrets or tokens.

### Security Acceptance Conditions
- A malformed batch writes nothing (test).
- Scratchpad writes leave long-term stores unchanged (test).

---

## 8. Test and Verification Strategy

### Required Tests
- [ ] Unit tests (flag mapping, batch parse)
- [ ] Integration tests (persona/task/failure/scratchpad/canonical/shared round trips)
- [ ] Contract tests (semantics identical to MCP)
- [ ] End-to-end tests (golden output)
- [ ] Regression tests (previous phases unchanged)
- [ ] Security/failure-mode tests (batch atomicity; scratchpad isolation; validate authorship)

### Required Test Scenarios

| Test ID | Scenario | Expected Result |
|---------|----------|-----------------|
| T100372-01 | `persona stable` then `persona get` (delivered by Phase 100368) | Value present |
| T100372-02 | `persona observe` twice | EMA update; not a new item |
| T100372-03 | `task upsert` / `failure record` | History record written |
| T100372-04 | `scratchpad write/read` | Round trip; long-term store unchanged |
| T100372-05 | `canonical put/get`, `shared store/retrieve` | Behave as MCP |
| T100372-06 | `validate --action update` | Original author preserved |
| T100372-07 | `batch --file ops.json --dry-run` | Plan; zero writes |
| T100372-08 | Malformed batch file | Fails closed; zero writes |
| T100372-09 | Regression + coverage | Workspace green; per-file ≥90% |

### Negative Testing
Verify batch rollback, scratchpad isolation, and no secret leaks.

### Verification Rule
Implementation claims must be supported by actual command output and `make coverage`.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-100372-01 | Additive writes bound with identical semantics | T100372-01…T100372-06 | Command output |
| AC-100372-02 | Scratchpad isolated from long-term stores | T100372-04 | Store check |
| AC-100372-03 | `batch` atomic; dry-run zero-write | T100372-07, T100372-08 | Output + store check |
| AC-100372-04 | `validate` preserves authorship | T100372-06 | Output |
| AC-100372-05 | No regression; coverage green | T100372-09 | `make check`, `make coverage` |

### Definition of Done
- [ ] All in-scope behavior implemented.
- [ ] All acceptance criteria pass.
- [ ] Required tests pass.
- [ ] No unauthorized changes introduced.
- [ ] Existing behavior remains intact.
- [ ] Security checks pass.
- [ ] Documentation updated.
- [ ] Evidence collected and verification completed.

### Completion Evidence
- Implementation summary
- Module diffs
- Batch atomicity evidence
- Scratchpad isolation evidence
- Coverage report
- Known limitations

---

## 10. Failure Handling and Recovery

### Expected Failure Modes
| Failure | Detection | Recovery |
|---------|-----------|----------|
| Batch partially applied | Atomicity test | Fix before claiming completion |
| Scratchpad durable leak | Isolation test | Fix before claiming completion |
| Semantic drift from MCP | Contract test | Fix before claiming completion |
| Coverage below floor | `make coverage` | Add tests |

### Rollback Strategy
Remove the additive-write modules; prior phases remain. Test writes are confined to temp stores.

### Partial Completion Policy
Do not claim completion if only some additive groups landed. Record each separately.

---

## 11. Traceability

| Parent Requirement | Implementation Task | Verification | Acceptance Criterion |
|--------------------|---------------------|--------------|-----------------------|
| `gaps/full-cli.md` §7 step 2 | Tasks 1–2 | T100372-01…T100372-08 | AC-100372-01, AC-100372-03, AC-100372-04 |
| `requirement.md` §4.9.2 item 2 | Tasks 1–2 | T100372-01…T100372-06 | AC-100372-01 |
| FR-21 (scratchpad not long-term) | Task 2 | T100372-04 | AC-100372-02 |
| Phase 100200 additive semantics | Tasks 1–2 | T100372-05, T100372-06 | AC-100372-01, AC-100372-04 |
| Coverage gate | Both | T100372-09 | AC-100372-05 |

Required chain:

```text
Gap → Additive write bindings → Modules + batch → Isolation/atomicity tests → Evidence
```

---

## 12. Phase Exit Contract

### Outputs Produced
- CLI persona/task/failure/scratchpad/canonical/shared/validate/batch commands.

### Guarantees Provided to Downstream Phases
After this phase is accepted:
- The additive catalog is CLI-reachable with unchanged semantics and isolation.
- `batch` provides the safe bulk-write path for scripts.

### Known Limitations
- `--dry-run` exists only where the underlying tool supports preview.
- Batch operations are validated before apply but not executed in parallel.

### Downstream Prerequisites
- Phases 100374/100376/100378 assume the additive write surface exists.

### Final Status
PASS | PASS WITH DOCUMENTED LIMITATIONS | BLOCKED | FAILED

### Verification Sign-Off
- Implementer: [TBD]
- Verifier: [TBD]
- Human Approver: not required
- Date: [TBD]

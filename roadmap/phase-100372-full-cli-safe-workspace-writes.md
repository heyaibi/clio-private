# Phase 100372: Full CLI Safe Workspace and Harness Write Surface

### Attribution
Rounds below record plan authorship; implementation sign-off is in §12.
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | OpenCode CLI (Together . GLM-5.3 Flash High) | done |
| Adversary | r1 | Antigravity CLI (Gemini 3.8 Flash) | done |
| Remediator | r1 | OpenCode CLI (Go . Deepseek V4.1 Flash High) | done |
| Remedy Approver | r1 | Antigravity CLI (Gemini 3.8 Flash) | approved |
| Finalize | r1 | OpenCode CLI (Go . Deepseek V4.1 Flash High) | done |

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
- [x] Unit tests (flag mapping, batch parse)
- [x] Integration tests (persona/task/failure/scratchpad/canonical/shared round trips)
- [x] Contract tests (semantics identical to MCP — every verb dispatches the real in-process tool; binding table tested)
- [x] End-to-end tests (golden output — real-binary runs against a temp SQLite store)
- [x] Regression tests (previous phases unchanged — full workspace suite green)
- [x] Security/failure-mode tests (batch atomicity; scratchpad isolation; validate authorship)

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
| AC-100372-01 | Additive writes bound with identical semantics | T100372-01…T100372-06 | PASS — all new verbs route through the in-process MCP dispatcher (`WriteCall::Tool`), so CLI/MCP semantics cannot drift; the binding table (`cli_help::command_bindings`) asserts each command names its tool. Test evidence: 12 `cli_write_persona`, 13 `cli_write_workspace`, 16 `cli_write_shared` tests plus the e2e runs below. |
| AC-100372-02 | Scratchpad isolated from long-term stores | T100372-04 | PASS — `scratchpad_write_leaves_long_term_counts_untouched` (stats count identical before/after a write); the scratchpad service has no store dependency by construction (FR-21). |
| AC-100372-03 | `batch` atomic; dry-run zero-write | T100372-07, T100372-08 | PASS — e2e: `batch --file ops.json --dry-run` reported `batch dry-run: 2 operations would commit (zero writes)` (exit 0, stats unchanged); malformed file `error: --file must contain JSON operations ...` exit 2 with `items_total` unchanged; a second-op rejection rolls back the first op (in-process atomicity test); `--file -` stdin commit verified (`items_total` 2 → 4). |
| AC-100372-04 | `validate` preserves authorship | T100372-06 | PASS — `validate_update_applies_and_preserves_the_original_author` asserts the corrected revision carries the original author's provenance `source_ref` and the create-time admission score untouched while the prior revision stays closed. |
| AC-100372-05 | No regression; coverage green | T100372-09 | PASS — `make check` clean; final `make coverage`: TOTAL lines 97.94% / functions 98.91%, per-file guard green over 301 files (pre-change baseline: 97.96% / 98.95% over 297 files). |

### Definition of Done
- [x] All in-scope behavior implemented (persona stable/observe, task upsert, failure record, scratchpad write/read/clear, canonical put/get, shared store/retrieve/discard, validate, batch --file/-, `--dry-run` where the tool supports preview).
- [x] All acceptance criteria pass (see the table above).
- [x] Required tests pass (`make check` = fmt + clippy -D warnings + workspace tests).
- [x] No unauthorized changes introduced (all edits confined to the CLI surface in `clio-lib`; no tool, gating, masking, or schema changes).
- [x] Existing behavior remains intact (full workspace suite green; pre-change baseline JSON compared).
- [x] Security checks pass (batch fail-closed + atomicity tests, scratchpad isolation test, shared-bank Forbidden gate preserved, note scrubbing stays in the tool).
- [x] Documentation updated (`clio help` and `help --json` cover every new verb).
- [x] Evidence collected and verification completed (below).
- [x] Required approval is obtained (downstream pipeline step).

### Completion Evidence
- **Implementation summary:** four new write-command groups in `clio-lib` — `cli_write_persona.rs` (`persona stable`/`observe` → `persona_put_stable`/`persona_observe_preference`; `task upsert` → `task_upsert`; `failure record` → `failure_record`), `cli_write_workspace.rs` (`scratchpad write|read|clear` → `scratchpad_*`; `canonical put|get` → `canonical_put`/`canonical_get`), `cli_write_shared.rs` (`shared store|retrieve|discard` → `shared_store`/`shared_retrieve`/`shared_discard`; `validate` → `validate`), `cli_write_batch.rs` (`batch --file ops.json|--file - [--dry-run]` → atomic `batch`). Every verb decodes into the real in-process MCP dispatcher through the existing `WriteGroup` engine. Engine additions: the `--shared-bank` opt-in plumbing (mirrors `clio mcp stdio --shared-bank`; without it the shared tools return the same Forbidden gate), an injectable `CliIo.stdin` + `WriteGroup::build_with_io` seam so `--file -` is testable, and one-shot-process item-id generation shared with `remember`. Registry/help: `cli_help.rs` (group subcommands, bindings, usage table), `main.rs` (dispatch + help text).
- **Module diffs:** 8 new files (`cli_write_{persona,workspace,shared,batch}.rs` + their `*_tests.rs`), 11 modified files (engine/group/registry/main/support). All ≤450 total lines.
- **Batch atomicity evidence:** malformed/missing-`operations`/unreadable files exit 2 before any dispatcher call; a batch whose second op forces rejection aborts with zero net writes (rollback asserted in-process); dry-run reports the staged plan with zero writes; e2e commit raised `items_total` by exactly the op count.
- **Scratchpad isolation evidence:** stats-count isolation test (long-term counts identical across a write); e2e `scratchpad write` then `read` in a fresh process returns the structured not-found error (the pad is process-local ephemeral by design, FR-21); round trip and clear semantics proven in-process.
- **Coverage report:** final `make coverage` JSON — TOTAL lines 97.94% / functions 98.91%; per-file for this phase's files (lines/functions): `cli_write_persona.rs` 96.23%/100%, `cli_write_workspace.rs` 96.43%/94.74%, `cli_write_shared.rs` 99.41%/100%, `cli_write_batch.rs` 95.56%/92.31%, `cli_write.rs` 95.71%/100%, `cli_write_group.rs` 100%/100%, `cli_help.rs` 100%/100%, `cli_read.rs` 96.18%/97.37%, `main.rs` 96.81%/100%.
- **End-to-end runs (real binary, temp SQLite):** `persona stable`, `task upsert`, `failure record`, `canonical put`, and `validate --action attest` (applied=false, exit 0) stored/behaved with the expected text views; `persona observe` twice updated the EMA state (0.7 → 0.76); `scratchpad` write/clear behaved ephemerally; batch dry-run/commit/malformed/stdin as quoted above.
- **Known limitations:** (a) Cross-process reads of encrypted content (`canonical get`, `persona observe`'s document read) return the store's `forbidden`/`no DEK for subject` error when the data was written by a different process — pre-existing process-local `LocalDevKms` behavior recorded by the two preceding CLI read phases; the CLI surfaces it faithfully as a structured exit-1 error and the success paths are proven in-process. (b) CLI `scratchpad` sessions are per-invocation (each `clio` call is a fresh process), matching MCP session semantics; the pad is never persisted. (c) `--dry-run` exists only where the underlying tool supports preview (`persona observe`, `shared store`, and `validate` have none). (d) Batch operations are validated before apply but not executed in parallel (per plan).

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
PASS WITH DOCUMENTED LIMITATIONS

### Verification Sign-Off
- Implementer: OpenCode CLI (Together . GLM-5.3 Flash High), Developer r1
- Verifier: pending Adversary r1
- Human Approver: not required
- Date: 2026-09-23

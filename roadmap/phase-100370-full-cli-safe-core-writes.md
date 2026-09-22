# Phase 100370: Full CLI Safe Core Write Surface

### Attribution
Rounds below record plan authorship; implementation sign-off is in §12.
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | [TBD] | [TBD] |
| Adversary | r1 | [TBD] | [TBD] |
| Remediator | r1 | [TBD] | [TBD] |
| Remedy Approver | r1 | [TBD] | [TBD] |
| Finalize | r1 | [TBD] | [TBD] |

**Follow-up phase 100370 · **Effort:** ~3 days · **Gaps:** `gaps/full-cli.md` §6, §7 step 2 (flagship write + gated core writes)

## 1. Objective

### Goal
Make the flagship promise real — `clio remember "x"` then `clio recall "x"` — and bind the safe core write tools (`store`, `admit_preview`, `summarize`, `triple_add`/`triple_end`, `belief_observe`, `graph_link`) to the CLI with the same gates MCP uses and a `--dry-run` preview on every mutation.

### Expected Outcome
- `clio remember "prefers aisle seats" --category persona --bank demo` writes one gated item; `clio recall "seat preference" --bank demo` returns it, with no MCP client and no env vars beyond a fresh temp `HOME`.
- `clio remember --dry-run` and `clio admit ...` print score and factors without writing.
- `clio triple add`, `clio belief observe`, `clio graph link`, `clio summarize`, `clio consolidate`, and `clio admit --file ops.json` work standalone with mirrored flags.
- Admission/category/span gating is identical to the MCP path; a rejected write is reported with the same reason.

### Parent Requirement
`gaps/full-cli.md` §6, §7 step 2; `requirement.md` §4.9.2 item 2 (identical semantics across bindings), FR-10/FR-20 (catalog), FR-21 (write gating on the long-term path; `admit_preview` exposes the same decision without writing), PR-3/PR-5.

### Design References
- Phase 100366 output/exit contract and in-process dispatch seam; Phase 100368 read surface.
- `clio-mcp::runtime::{now_utc, build_ops_embedder}` (`crates/clio-lib/src/ops_cli.rs:140-141`) for the runtime the write path needs.
- The catalog/schemas: `bound_tools()` (`crates/clio-mcp/src/lib.rs:158`), `schema_pack()`.
- Redaction/masking: `clio_ops::redact_credentials`, `clio_config::secret`.

### Name and Binding-Syntax Note
`requirement.md` §4.9.2 item 2 states "Binding syntax MAY differ; names and semantics MUST NOT." This plan reads CLI verbs as binding syntax: `clio remember` invokes `store`, `clio admit` invokes `admit_preview`, `clio consolidate` invokes `consolidate`. Each verb's tool name MUST be printed in `clio help` and `clio help --json`. If the operator prefers strict name parity, the fallback is to use the tool names as verbs.

---

## 2. Scope Boundaries

### In Scope
- `clio remember TEXT --category C [--bank B] [--actor A] [--epistemic-kind fact|belief] [--dry-run]` → `store` (dry-run → `admit_preview`).
- `clio admit TEXT --category C ...` → `admit_preview`; `clio admit --file ops.json` → `admit_preview_batch` (read-only batch preview).
- `clio summarize [--scope ...]` → `summarize`.
- `clio consolidate [--scope ...]` → `consolidate` (maintenance write; non-blocking structure work).
- `clio triple add S P O ...`, `clio triple end S P [--object O]`.
- `clio belief observe PROP --confidence C --evidence E --source S`.
- `clio graph link A B --relationship R`.
- `--dry-run` on every mutating command, writing nothing and exiting 0.

### Explicitly Out of Scope
- Destructive/confirmed mutations `update`, `invalidate`, `discard`, `correct` (Phase 100374).
- Workspace/harness writes (Phase 100372).
- Hygiene, export/import, erase (Phase 100376); config/ranking/sync (Phase 100378).
- New memory semantics, categories, admission factors, or schema.

### Must Not Change
- Admission and category gates, span verification, masking, bank/actor semantics.
- MCP tool names/arguments/semantics and gate behavior.
- Snapshots are never written by `summarize`.

### Scope Expansion Rule
If work outside this scope appears necessary: stop, document the reason, request clarification or approval, and do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- Phase 100366 accepted (contract + dispatch seam); Phase 100368 accepted (read surface).
- MCP write tools (`store`, `triple_add`, `belief_observe`, `summarize`, `graph_link`) exist and are gated.

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| In-process write dispatch | Callable with gating intact | `crates/clio-mcp/src/lib.rs` |
| Admission preview | Same decision, no write | `admit_preview` semantics |
| Runtime/embedder | Available to CLI | `clio-mcp::runtime` |
| Coverage guard | Per-file floor | `make coverage` |

---

## 4. Existing-System Discovery

The agent MUST re-verify the following; the facts below were confirmed at plan time.

### Required Discovery
- Confirm the in-process write dispatch and that it enforces admission/category/span gates that the CLI must not bypass.
- Confirm `admit_preview` writes nothing and returns score + factors.
- Confirm `summarize` regenerates gists only and leaves snapshots byte-immutable.
- Confirm the runtime/embedder construction the write path needs and reuse it.
- Confirm `--epistemic-kind` handling for facts vs beliefs (belief creation follows §4.9.3).

### Discovery Output
- **Gating lives inside the tools.** The CLI must call the same dispatch, not a parallel store write, so gates cannot be skipped.
- **`admit_preview` is the dry-run primitive** and already returns the decision without writing (FR-21).
- **`summarize` is snapshot-safe by contract** (Phase 100380 binds it; this phase only exposes it).
- **Extraction/embedding may be async.** The CLI write returns after the gated write; background index drain stays off the response path (per `gaps/full-cli.md` §8).
- **No writes without gates.** There is no public write path bypassing admission.

### Repository Adaptation Rule
The agent must determine concrete implementation locations from the actual repository.

---

## 5. Implementation Specification

### Task 1: Flagship Write and Dry-Run

#### Intent
Ship `remember`/`admit` with a zero-write preview.

#### Required Capability or Behavior
- `clio remember TEXT --category C [--bank B] [--actor A] [--epistemic-kind fact|belief] [--dry-run]` writes one gated item.
- `--dry-run` maps to `admit_preview` and prints score plus factors, writing nothing, exit 0.
- A refused write reports the same reason the MCP path would and exits 1 (domain refusal) or 2 (usage).
- No inference of `--category`: it is required, keeping PR-3/PR-5 loud (per §11 open question 1).

#### Architectural Responsibility
`clio-lib` parses/renders; the in-process write dispatch owns gating and persistence.

#### Required Changes
1. Add a write-command module with `remember`/`admit` under the 450-line cap.
2. Route through the gated dispatch; implement `--dry-run`.
3. Golden tests: successful write, preview (no write), refusal.

#### Implementation Constraints
- Never write the long-term store on `--dry-run`.
- Never bypass admission/category gates.
- Reuse the shared resolver, masker, and redactor.

#### Expected Result
One command saves a memory; the dry-run previews the exact decision without writing.

### Task 2: Triples, Beliefs, Graph, and Summarize

#### Intent
Bind the remaining safe core writes.

#### Required Capability or Behavior
- `clio triple add` / `clio triple end`, `clio belief observe`, `clio graph link`, `clio summarize` run standalone with mirrored flags.
- `triple add` rejects continuous/scalar updates (§4.9.4.E); `belief observe` appends to existing identities without re-scoring novelty (§4.9.3).
- `summarize` regenerates gists only.

#### Architectural Responsibility
`clio-lib` renders; semantics stay in the existing crates.

#### Required Changes
1. Add group modules and tests.
2. Assert snapshot immutability for `summarize`; assert append semantics for beliefs.

#### Implementation Constraints
- No new dependency; no semantic divergence from MCP.
- Snapshot columns never written by `summarize`.

#### Expected Result
All safe core writes are reachable from the CLI with identical behavior.

### Implementation Freedom
The agent may choose module layout and flag spellings, provided semantics and gating are unchanged.

---

## 6. Agent Execution Rules

### Allowed Actions
- Add write modules, `--dry-run`, tests, and help.
- Reuse the Phase 100366 contract and the shared runtime.

### Forbidden Actions
- Bypass admission/category/span gates; write on `--dry-run`.
- Change MCP names/semantics; add dependencies; add destructive commands.

### Agent Decision Boundary
The agent may decide parsing/rendering details. The agent must request approval for any semantic change or a new required flag.

### Mandatory Stop Conditions
Stop and report if a write path exists that bypasses gating, if `--dry-run` cannot be made write-free, or if the write runtime cannot be reached in-process.

---

## 7. Security Constraints

### Required Controls
- All writes pass the same gates as MCP; `--dry-run` performs zero writes.
- Mask secrets in errors; never echo raw content beyond the item itself.
- No internal retries hiding failures (caller decides); the background index drain stays as-is.

### Sensitive Data Rules
- Never log plaintext credentials, tokens, or secrets.
- Prefer env over argv for any future secret-bearing input.

### Security Acceptance Conditions
- A rejected write leaves the store unchanged (test).
- `--dry-run` leaves the store unchanged (test).

---

## 8. Test and Verification Strategy

### Required Tests
- [ ] Unit tests (flag mapping, dry-run routing)
- [ ] Integration tests (remember→recall round trip; triple/belief/graph writes)
- [ ] Contract tests (gating identical to MCP; same refusal reasons)
- [ ] End-to-end tests (golden output for write + preview)
- [ ] Regression tests (read commands unchanged)
- [ ] Security/failure-mode tests (gate bypass impossibility; dry-run no-write; snapshot immutability)

### Required Test Scenarios

| Test ID | Scenario | Expected Result |
|---------|----------|-----------------|
| T100370-01 | `remember` then `recall` in temp HOME | Item returned |
| T100370-02 | `remember --dry-run` | Score+factors; store unchanged; exit 0 |
| T100370-03 | Low-utility rejected write | Refusal; same reason as MCP; store unchanged |
| T100370-04 | `triple add` then `triple query` | Edge present |
| T100370-05 | `belief observe` twice | Append; audit emitted; no novelty re-score |
| T100370-06 | `graph link` then `graph query` | Edge present |
| T100370-07 | `summarize` | Gists regenerated; snapshots byte-identical |
| T100370-08 | Regression + coverage | Workspace green; per-file ≥90% |

### Negative Testing
Verify no gate bypass, no dry-run writes, correct refusals, and unchanged snapshots.

### Verification Rule
Implementation claims must be supported by actual command output and `make coverage`.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-100370-01 | `remember`→`recall` works with no MCP client | T100370-01 | Command output |
| AC-100370-02 | `--dry-run` writes nothing, exits 0 | T100370-02 | Output + store check |
| AC-100370-03 | Gating identical to MCP | T100370-03 | Refusal comparison |
| AC-100370-04 | Triples/beliefs/graph/summarize bound | T100370-04…T100370-07 | Command output |
| AC-100370-05 | No regression; coverage green | T100370-08 | `make check`, `make coverage` |

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
- Write-module diffs
- Round-trip command transcript
- Snapshot-immutability evidence
- Coverage report
- Known limitations

---

## 10. Failure Handling and Recovery

### Expected Failure Modes
| Failure | Detection | Recovery |
|---------|-----------|----------|
| Gate bypass discovered | Audit/test | Stop; remove the bypass |
| `--dry-run` writes | Test | Fix before claiming completion |
| Snapshot mutated by `summarize` | Immutability test | Fix before claiming completion |
| Coverage below floor | `make coverage` | Add tests |

### Rollback Strategy
Remove the write modules; reads remain. Writes performed during testing are confined to temp stores.

### Partial Completion Policy
Do not claim completion if `remember` landed but the other safe writes did not. Record each separately.

---

## 11. Traceability

| Parent Requirement | Implementation Task | Verification | Acceptance Criterion |
|--------------------|---------------------|--------------|-----------------------|
| `gaps/full-cli.md` §7 step 2 | Tasks 1–2 | T100370-01…T100370-07 | AC-100370-01, AC-100370-04 |
| `requirement.md` §4.9.2 item 2 | Tasks 1–2 | T100370-03, T100370-04 | AC-100370-03 |
| FR-21 (`admit_preview` no write; long-term gating) | Task 1 | T100370-02, T100370-03 | AC-100370-02, AC-100370-03 |
| PR-3 / PR-5 (loud category) | Task 1 | T100370-01 | AC-100370-01 |
| Coverage gate | Both | T100370-08 | AC-100370-05 |

Required chain:

```text
Gap → Gated write bindings → CLI modules + dry-run → Round-trip tests → Evidence
```

---

## 12. Phase Exit Contract

### Outputs Produced
- CLI `remember`/`admit` (with `--dry-run`), `triple add|end`, `belief observe`, `graph link`, `summarize`.

### Guarantees Provided to Downstream Phases
After this phase is accepted:
- The flagship write→read loop works from the CLI.
- All safe core writes are CLI-reachable with unchanged gating.

### Known Limitations
- Category is required; no inference.
- Background indexing remains asynchronous and off the response path.

### Downstream Prerequisites
- Phase 100372/100374/100376 build their write/confirm behavior on this contract.

### Final Status
PASS | PASS WITH DOCUMENTED LIMITATIONS | BLOCKED | FAILED

### Verification Sign-Off
- Implementer: [TBD]
- Verifier: [TBD]
- Human Approver: not required
- Date: [TBD]

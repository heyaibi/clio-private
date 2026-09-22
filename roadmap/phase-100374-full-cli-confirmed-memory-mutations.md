# Phase 100374: Full CLI Confirmed Memory Mutation Surface

### Attribution
Rounds below record plan authorship; implementation sign-off is in §12.
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | [TBD] | [TBD] |
| Adversary | r1 | [TBD] | [TBD] |
| Remediator | r1 | [TBD] | [TBD] |
| Remedy Approver | r1 | [TBD] | [TBD] |
| Finalize | r1 | [TBD] | [TBD] |

**Follow-up phase 100374 · **Effort:** ~2 days · **Gaps:** `gaps/full-cli.md` §6, §7 step 3 (confirmed/destructive memory mutations)

## 1. Objective

### Goal
Expose the confirmed memory mutations — `update`, `invalidate`, `discard`, `correct` — over the CLI with hardened confirm gates: off a TTY they refuse without `--confirm`, they preview blast radius under `--dry-run`, and they never proceed silently.

### Expected Outcome
- `clio update ID VALUE --rule discrete|continuous`, `clio invalidate ID [--replacement ID]`, `clio discard ID --reason R --confirm`, and `clio correct ID VALUE --reason R` run standalone.
- Without a TTY and without `--confirm`, a destructive command exits 2 and names the missing flag.
- `--dry-run` prints exactly what would change (target, scope, irreversibility note) and writes nothing.
- `discard` sets the existing discarded columns; `update` uses the shared EMA engine for continuous rules; `correct` records an attributable correction.

### Parent Requirement
`gaps/full-cli.md` §7 step 3, §8 (security and safety); `requirement.md` §4.9.2 item 2 (identical semantics), FR-30 (non-interactive exit-code contract), FR-21 (discrete vs continuous update rules), the §4.9.2 confirmation requirement.

### Design References
- Phases 100366/100370 establish the contract, dispatch, and write pattern.
- `update` rule splitting and the EMA engine: Phase 100090 (`phase-100090-shared-continuous-ema-update-engine.md`).
- `discard`: Phase 100155 (`phase-100155-ops-discard-tool.md`) writes `discarded_at`/`discard_reason`.
- Confirmation precedent: `repair`/`reindex` require `--confirm` (`crates/clio-lib/src/ops_cli.rs:48-53`).
- Redaction/masking: `clio_ops::redact_credentials`, `clio_config::secret`.

---

## 2. Scope Boundaries

### In Scope
- `clio update ID VALUE --rule discrete|continuous`.
- `clio invalidate ID [--replacement ID]`.
- `clio discard ID --reason R --confirm`.
- `clio correct ID VALUE --reason R`.
- Confirm-gate hardening: refuse off-TTY without `--confirm`; `--dry-run` blast-radius preview.
- A red-team review of the confirm gates per the security-bug-finder skill before sign-off.

### Explicitly Out of Scope
- `hygiene_clean`, `erase_request`, `export`, `import` (Phase 100376).
- `doctor`/`repair`/`reindex` (already bound in `ops`; no change).
- New memory semantics; compliance erasure.

### Must Not Change
- Confirmation requirements and the exit-code contract.
- `doctor` never mutates; `repair`/`reindex` keep their existing gates.
- Discrete vs continuous rule separation (EMA only for continuous).

### Scope Expansion Rule
If work outside this scope appears necessary: stop, document the reason, request clarification or approval, and do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- Phase 100366 (contract) and Phase 100370 (write pattern) accepted.
- The mutation tools (`update`, `invalidate`, `discard`, `correct`) exist and are gated over MCP.

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| In-process mutation dispatch | Callable, gated | `crates/clio-mcp/src/lib.rs` |
| EMA engine | Shared, not reimplemented | Phase 100090 |
| Discard columns | Present both backends | Phase 100155 |
| Coverage guard | Per-file floor | `make coverage` |

---

## 4. Existing-System Discovery

The agent MUST re-verify the following; the facts below were confirmed at plan time.

### Required Discovery
- Confirm each mutation tool's `inputSchema` and required arguments.
- Confirm the existing confirm convention (`--confirm`, off-TTY refusal) from `ops` and reuse it rather than inventing a second.
- Confirm `update` rejects continuous rules on triples and uses the shared EMA engine.
- Confirm `discard` writes `discarded_at`/`discard_reason` and is distinct from compliance erase.
- Confirm `correct` is attributable and preserves history.

### Discovery Output
- **A confirm precedent exists.** `repair`/`reindex` require `--confirm` and refuse otherwise (`ops_cli.rs:48-53`); the CLI reuses that shape.
- **`update` is rule-sensitive.** Continuous updates use the shared EMA engine; discrete updates invalidate. Triples reject continuous/scalar updates (§4.9.4.E).
- **`discard` is not erase.** It sets discarded columns; compliance erasure (DEK destruction) is Phase 100376/§7.4 and must stay distinct.
- **`correct` is attributable.** It records a corrected value plus reason over existing history.
- **The exit-code contract is fixed**: 0 ok, 1 operational failure, 2 usage/refusal.

### Repository Adaptation Rule
The agent must determine concrete implementation locations from the actual repository.

---

## 5. Implementation Specification

### Task 1: Update, Invalidate, Correct

#### Intent
Bind the non-erasure mutations with rule-aware behavior.

#### Required Capability or Behavior
- `clio update ID VALUE --rule discrete|continuous` applies the correct rule; continuous uses the EMA engine, discrete invalidates.
- `clio invalidate ID [--replacement ID]` closes the current value and optionally chains a replacement.
- `clio correct ID VALUE --reason R` records an attributable correction.
- Flags mirror the MCP schema 1:1.

#### Architectural Responsibility
`clio-lib` renders; semantics stay in existing crates.

#### Required Changes
1. Add a mutation group module and tests.
2. Assert rule separation and EMA reuse.

#### Implementation Constraints
- No second EMA implementation.
- No dependency; no semantic divergence.

#### Expected Result
Update/invalidate/correct work standalone and identically to MCP.

### Task 2: Confirmed Discard and Confirm-Gate Hardening

#### Intent
Make destructive actions safe and non-blocking.

#### Required Capability or Behavior
- `clio discard ID --reason R --confirm` sets the discard columns.
- Without a TTY and without `--confirm`, `discard` exits 2 and prints `hint: pass --confirm` (or `--yes`).
- `--dry-run` prints blast radius (target id, bank scope, irreversibility note) and writes nothing.
- The same gate is applied consistently to all future destructive CLI commands.

#### Architectural Responsibility
`clio-lib` owns the confirm gate; `discard` semantics stay in the ops/write path.

#### Required Changes
1. Add the shared confirm-gate helper and apply it to `discard`.
2. Add tests for TTY/non-TTY confirmation and dry-run.

#### Implementation Constraints
- Never proceed silently off-TTY.
- `doctor` purity unchanged; no writes on dry-run.

#### Expected Result
Destructive mutation is explicit, previewable, and script-safe.

### Implementation Freedom
The agent may choose module layout and help wording, provided confirmation and exit codes are preserved.

---

## 6. Agent Execution Rules

### Allowed Actions
- Add mutation modules, the confirm-gate helper, tests, and help.
- Reuse the Phase 100366 contract and the EMA engine.

### Forbidden Actions
- Bypass confirmation; alias `discard` to compliance erase.
- Change exit codes; add dependencies; add new memory semantics.

### Agent Decision Boundary
The agent may decide rendering and helper placement. The agent must request approval for any change to the confirm contract.

### Mandatory Stop Conditions
Stop and report if a mutation cannot be invoked in-process, if confirmation cannot be enforced off-TTY, or if `discard` and erase cannot be kept distinct.

---

## 7. Security Constraints

### Required Controls
- Confirmation required for destructive actions off-TTY; never silently proceed.
- `--dry-run` performs zero writes and states irreversibility for erase-adjacent paths.
- Mask secrets in errors; redact credentials.

### Sensitive Data Rules
- Never log plaintext credentials or secrets.
- Do not echo more memory content than necessary for the operation.

### Security Acceptance Conditions
- Off-TTY `discard` without `--confirm` exits 2 and writes nothing (test).
- `--dry-run` writes nothing (test).

---

## 8. Test and Verification Strategy

### Required Tests
- [ ] Unit tests (rule selection, confirm-gate decision)
- [ ] Integration tests (update/invalidate/correct/discard round trips)
- [ ] Contract tests (semantics identical to MCP; exit codes)
- [ ] End-to-end tests (golden output for refusal and dry-run)
- [ ] Regression tests (prior phases unchanged)
- [ ] Security/failure-mode tests (off-TTY refusal; dry-run no-write; erase distinctness)

### Required Test Scenarios

| Test ID | Scenario | Expected Result |
|---------|----------|-----------------|
| T100374-01 | `update --rule continuous` | EMA applied; not a new item |
| T100374-02 | `update --rule discrete` | Prior value invalidated |
| T100374-03 | `invalidate --replacement` | Closed; replacement chained |
| T100374-04 | `correct --reason` | Attributable correction recorded |
| T100374-05 | `discard` off-TTY without `--confirm` | Exit 2; names flag; no write |
| T100374-06 | `discard --confirm` | Discard columns set |
| T100374-07 | `discard --dry-run` | Blast radius printed; no write |
| T100374-08 | Regression + coverage | Workspace green; per-file ≥90% |

### Negative Testing
Verify no silent destructive action, no dry-run writes, and no confusion with erase.

### Verification Rule
Implementation claims must be supported by actual command output, the red-team review, and `make coverage`.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-100374-01 | Update/invalidate/correct/discard bound | T100374-01…T100374-04, T100374-06 | Command output |
| AC-100374-02 | Off-TTY destructive requires `--confirm` | T100374-05 | Command output |
| AC-100374-03 | `--dry-run` zero-write with blast radius | T100374-07 | Output + store check |
| AC-100374-04 | Discard distinct from erase | T100374-06 + inspection | Docs + behavior |
| AC-100374-05 | No regression; coverage green | T100374-08 | `make check`, `make coverage` |
| AC-100374-06 | Red-team review completed | Inspection | Review notes |

### Definition of Done
- [ ] All in-scope behavior implemented.
- [ ] All acceptance criteria pass.
- [ ] Required tests pass.
- [ ] No unauthorized changes introduced.
- [ ] Existing behavior remains intact.
- [ ] Security checks pass (red-team review done).
- [ ] Documentation updated.
- [ ] Evidence collected and verification completed.

### Completion Evidence
- Implementation summary
- Mutation-module diffs
- Confirm-gate and dry-run transcripts
- Red-team review notes
- Coverage report
- Known limitations

---

## 10. Failure Handling and Recovery

### Expected Failure Modes
| Failure | Detection | Recovery |
|---------|-----------|----------|
| Destructive proceeds off-TTY | Gate test | Fix before claiming completion |
| Dry-run writes | Test | Fix before claiming completion |
| Discard confused with erase | Review | Clarify help and behavior |
| Coverage below floor | `make coverage` | Add tests |

### Rollback Strategy
Remove the mutation modules; prior phases remain. Test writes are confined to temp stores.

### Partial Completion Policy
Do not claim completion if the confirm gate landed but a mutation did not, or vice versa. Record each separately.

---

## 11. Traceability

| Parent Requirement | Implementation Task | Verification | Acceptance Criterion |
|--------------------|---------------------|--------------|-----------------------|
| `gaps/full-cli.md` §7 step 3, §8 | Tasks 1–2 | T100374-01…T100374-07 | AC-100374-01, AC-100374-02, AC-100374-03 |
| `requirement.md` §4.9.2 item 2 | Task 1 | T100374-01…T100374-04 | AC-100374-01 |
| FR-30 (non-interactive exit codes) | Task 2 | T100374-05 | AC-100374-02 |
| FR-21 (discrete vs continuous) | Task 1 | T100374-01, T100374-02 | AC-100374-01 |
| Phase 100155 (discard columns) | Task 2 | T100374-06 | AC-100374-04 |
| Coverage gate | Both | T100374-08 | AC-100374-05 |

Required chain:

```text
Gap → Mutation bindings + confirm gate → CLI modules → Confirm/dry-run tests → Evidence
```

---

## 12. Phase Exit Contract

### Outputs Produced
- CLI `update`, `invalidate`, `correct`, `discard` with a shared confirm gate.

### Guarantees Provided to Downstream Phases
After this phase is accepted:
- All non-erasure memory mutations are CLI-reachable with enforced confirmation.
- A reusable confirm-gate helper exists for later destructive commands.

### Known Limitations
- Interactive prompts are not added; confirmation is flag-based.
- `discard` remains reversible-ish by design and is not compliance erasure.

### Downstream Prerequisites
- Phase 100376 reuses the confirm gate for `hygiene_clean` and `erase_request`.

### Final Status
PASS | PASS WITH DOCUMENTED LIMITATIONS | BLOCKED | FAILED

### Verification Sign-Off
- Implementer: [TBD]
- Verifier: [TBD]
- Human Approver: not required (unless the confirm contract changes)
- Date: [TBD]

# Phase 100500: First Real Provider Ingest Adapter (Spike-Gated)

### Attribution
Rounds below record plan authorship; implementation sign-off is in §12.
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | [TBD] | [TBD] |
| Adversary | r1 | [TBD] | [TBD] |
| Remediator | r1 | [TBD] | [TBD] |
| Remedy Approver | r1 | [TBD] | [TBD] |
| Finalize | r1 | [TBD] | [TBD] |

**Remediation phase 100500 · **Effort:** ~5–7 days · **Gap:** G-03 · **Source:** `gap/requirement-gaps.md` §2, §3

## 1. Objective

### Goal
Replace the compliant first-release `import_provider` stub with one real provider adapter, so migration from an external memory system is proven end to end, while the stub remains for the other four providers.

### Expected Outcome
- A short spike picks one provider (Mem0 or Hindsight) and records why.
- That provider imports end to end: pull → gating → store with provenance and idempotency.
- Credentials are masked in all logs and reports; a dry-run report precedes any write.
- The stub remains for the other four providers.

### Parent Requirement
`requirement.md` FR-29 / §4.9.5.B: "When a provider adapter is implemented, it SHALL mask credentials in all logs/reports and SHALL offer the same dry-run report before writing. First release MAY stub `import_provider` as non-writing." Gap G-03. §4.1–§4.2 gates apply to imported items.

### Design References
- `crates/clio-mcp/src/portability_tools.rs:113-123` holds the non-writing stub and `PROVIDER_IMPORT_UNSUPPORTED`; `masked_credentials` already masks accepted credential params.
- `import_provider`'s `provider` argument names a memory system, not a chat vendor (glossary "Provider (ingest)"): `hindsight | mem0 | mnemosyne | honcho | supermemory`.
- The JSON export/import bundle path (Phase 100220) is the reference shape for manifests, dry-run reports, and idempotency.

---

## 2. Scope Boundaries

### In Scope
- A spike comparing Mem0 and Hindsight pull shape, auth, and idempotency keys, with a recorded pick.
- One provider adapter: pull, credential masking, JSON-shaped dry-run report, §4.1–§4.2 gating, `belief`/`third_party` defaults, `provider:<id>` provenance, external-id idempotency, tests, docs.

### Explicitly Out of Scope
- Adapters for the other four providers (a follow-up at roughly 3–4× this phase's effort).
- Changes to admission or category gates.
- A new credential mechanism or a new transport.
- Sync, export/import changes beyond reuse.

### Must Not Change
- §4.1–§4.2 gating still applies to imported items.
- Credentials are masked in every log/report; no plaintext secret.
- `import_provider` idempotency and dry-run semantics match the JSON import path.
- The stub behavior for unimplemented providers remains.

### Scope Expansion Rule
If work outside this scope appears necessary: stop, document the reason, request clarification or approval, and do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- Phase 100360 accepted (coverage guard).
- Phase 100380 accepted (binding closure; pack-approval pattern).
- Provider API access/credentials available for the spike and end-to-end test (synthetic account acceptable).

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| Stub + masking | Present | `portability_tools.rs` |
| Import bundle path | Manifest + dry-run shape | Phase 100220 |
| Admission gates | Reachable for imported items | `clio-admission` |
| Credential masking | Shared mechanism | `clio_config::secret` |

---

## 4. Existing-System Discovery

The agent MUST re-verify the following; the facts below were confirmed at plan time.

### Required Discovery
- Confirm the stub's exact behavior, code, and masking.
- Read the JSON import path's manifest, dry-run, and idempotency semantics to mirror them.
- Identify the provider API surfaces (pull shape, auth, external id, pagination) for Mem0 and Hindsight.
- Confirm where `provider:<id>` provenance and `belief`/`third_party` defaults are set on imported items.
- Confirm the §4.1–§4.2 gates are enforced on the import write path.

### Discovery Output
- **Stub is compliant but non-writing.** `import_provider` returns `PROVIDER_IMPORT_UNSUPPORTED`, masks credentials, and writes nothing.
- **Reference semantics exist.** The JSON import bundle already defines manifest, dry-run report, and idempotency by external id; the adapter should reuse them.
- **Provider identity is a memory system.** The `provider` argument is one of the five memory systems; adapters are per-system.
- **Gates apply.** Imported items must pass §4.1–§4.2; no bypass.

### Repository Adaptation Rule
The agent must determine concrete implementation locations from the actual repository. The plan does not prescribe file paths or module names unless they are an externally required contract.

---

## 5. Implementation Specification

### Task 0: Provider Spike

#### Intent
Pick one provider on evidence.

#### Required Capability or Behavior
- Compare Mem0 and Hindsight on pull shape, auth model, and idempotency keys.
- Record the pick and the reasons; note the trade-offs for the deferred provider.

#### Architectural Responsibility
Phase documentation and a small spike.

#### Required Changes
1. Investigate both provider APIs.
2. Record the pick with rationale.

#### Expected Result
A recorded provider decision.

### Task 1: Provider Adapter

#### Intent
Import from the chosen provider end to end.

#### Required Capability or Behavior
- Pull items from the provider using the provider's API and pagination.
- Produce a JSON-shaped dry-run report with zero writes, then perform gated writes.
- Apply §4.1–§4.2 gating; set `belief`/`third_party` defaults where the source is not first-person or not user-asserted.
- Tag provenance as `provider:<id>`.
- Idempotent by external id: re-running does not duplicate.
- Mask credentials in all logs/reports.
- Leave the stub for the other four providers.

#### Architectural Responsibility
`clio-mcp` binding delegates to a provider-adapter layer; the JSON import path owns the shared bundle/report shape; admission owns gating.

#### Required Changes
1. Add the adapter (pull, map, gate, write).
2. Add the dry-run report and credential masking.
3. Add `provider:<id>` provenance and `belief`/`third_party` defaults.
4. Add external-id idempotency.
5. Add tests and docs.
6. Keep the stub for the other four.

#### Implementation Constraints
- Do not bypass admission/category gates.
- Do not add a new transport; reuse the existing JSON client.
- Never log plaintext credentials or item content.
- Do not break the existing stub contract for unimplemented providers.

#### Expected Result
One provider imports end to end, dry-run first, idempotently, with masked credentials.

### Implementation Freedom
The agent may choose adapter structure and mapping internals provided gating, masking, provenance, idempotency, and the stub boundary are respected.

---

## 6. Agent Execution Rules

### Allowed Actions
- Investigate provider APIs; add the adapter, dry-run report, provenance, idempotency, tests, and docs.
- Reuse the JSON import bundle shape.

### Forbidden Actions
- Bypass gates; log plaintext secrets or content; add a new transport or dependency without approval.
- Implement the other four providers in this phase.
- Claim end-to-end success without a real pull.

### Agent Decision Boundary
The agent may decide provider mapping and adapter structure. The agent must request approval for adding a new dependency, changing the import contract, or widening scope to a second provider.

### Mandatory Stop Conditions
Stop and report if the provider API cannot be exercised (no access), if gating cannot be applied to imported items, or if masking cannot be guaranteed.

---

## 7. Security Constraints

### Required Controls
- Credential masking in every log and report.
- §4.1–§4.2 gating on every imported item.
- Dry-run performs zero writes.
- Idempotency prevents duplicate imports.

### Sensitive Data Rules
- Never log plaintext credentials or source content.
- Never commit provider credentials; use the approved secret mechanism.

### Security Acceptance Conditions
- A planted credential is masked in all outputs.
- A dry-run writes nothing.
- Re-running imports does not duplicate items.

---

## 8. Test and Verification Strategy

### Required Tests
- [ ] Unit tests (mapping, provenance, `belief`/`third_party` defaults, idempotency key)
- [ ] Integration tests (dry-run zero writes; gated write path)
- [ ] Contract tests (stub unchanged for the other four; import report shape matches JSON import)
- [ ] End-to-end tests (real pull → gate → store → retrieve)
- [ ] Regression tests (workspace green)
- [ ] Security tests (masking; gate non-bypass; dry-run no writes)
- [ ] Failure-mode tests (auth failure, rate limit, partial page, duplicate external id)

### Required Test Scenarios

| Test ID | Scenario | Expected Result |
|---------|----------|-----------------|
| T100500-01 | Dry-run against the provider | JSON report; zero writes |
| T100500-02 | Real pull of a small set | Items stored with `provider:<id>` provenance |
| T100500-03 | Re-run the same import | No duplicates |
| T100500-04 | Imported item failing admission | Rejected and logged, no write |
| T100500-05 | Planted credential in args | Masked in every output |
| T100500-06 | Auth failure / rate limit | Structured error; no partial corruption |
| T100500-07 | Unimplemented provider | Still returns the stub code |
| T100500-08 | Regression suite | Workspace green |

### Negative Testing
Verify dry-run writes nothing, duplicates are prevented, failed gates leave no partial state, and credentials never leak.

### Verification Rule
Implementation claims must be supported by an actual provider pull and test output, not mocks alone.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-100500-01 | Provider picked with recorded rationale | Task 0 | Decision note |
| AC-100500-02 | One provider imports end to end | T100500-02 | Test output |
| AC-100500-03 | Dry-run writes nothing | T100500-01 | Test output |
| AC-100500-04 | Idempotent by external id | T100500-03 | Test output |
| AC-100500-05 | §4.1–§4.2 gating enforced | T100500-04 | Test output |
| AC-100500-06 | Credentials masked everywhere | T100500-05 | Test output |
| AC-100500-07 | Stub remains for the other four | T100500-07 | Test output |

### Definition of Done
- [ ] All in-scope behavior implemented.
- [ ] All acceptance criteria pass.
- [ ] Required tests pass.
- [ ] No unauthorized changes introduced.
- [ ] Existing behavior remains intact.
- [ ] Security checks pass.
- [ ] Documentation updated.
- [ ] Evidence collected and verification completed.
- [ ] Required approval obtained (new dependency or contract change, if any).

### Completion Evidence
- Implementation summary
- Provider decision and rationale
- Dry-run and real-import output
- Masking evidence
- Idempotency evidence
- Known limitations

---

## 10. Failure Handling and Recovery

### Expected Failure Modes
| Failure | Detection | Recovery |
|---------|-----------|----------|
| Provider auth failure | API error | Structured error; no writes |
| Rate limit / partial page | API error | Bounded retry; resume by external id |
| Duplicate external id | Idempotency check | Skip, do not duplicate |
| Admission rejects an item | Gate | Log reject; continue the batch |
| Credential leak risk | Masking test | Fix before claiming completion |

### Rollback Strategy
Remove the adapter and restore the stub for the chosen provider; the stub path is unchanged. Imported data remains valid but can be erased through the compliance path.

### Partial Completion Policy
Do not claim completion if only the dry-run path works. Record dry-run and real-import states separately; never leave a state where imports appear to work but write ungated.

---

## 11. Traceability

| Parent Requirement | Implementation Task | Verification | Acceptance Criterion |
|--------------------|---------------------|--------------|-----------------------|
| FR-29 / §4.9.5.B (provider adapter, masking, dry-run) | Task 1 | T100500-01…T100500-06 | AC-100500-02…AC-100500-06 |
| §4.1–§4.2 (gates apply) | Task 1 | T100500-04 | AC-100500-05 |
| Glossary "Provider (ingest)" | Task 0 | Decision note | AC-100500-01 |
| First-release stub carve-out | Task 1 | T100500-07 | AC-100500-07 |

Required chain:

```text
Requirement → Capability → Implementation → Test → Evidence
```

---

## 12. Phase Exit Contract

### Outputs Produced
- A recorded provider decision.
- One real provider adapter with dry-run, gating, provenance, idempotency, and masking.
- The stub preserved for the other four providers.

### Guarantees Provided to Downstream Phases
After this phase is accepted:
- Provider migration is proven for at least one real system.
- The adapter pattern is available for the remaining four at roughly 3–4× this effort.

### Known Limitations
- Four providers remain stubbed.
- The adapter depends on the chosen provider's API stability.

### Downstream Prerequisites
- A follow-up provider phase may add the remaining adapters using the same pattern; it must keep the stub for any still-unimplemented provider.

### Final Status
PASS | PASS WITH DOCUMENTED LIMITATIONS | BLOCKED | FAILED

### Verification Sign-Off
- Implementer: [TBD]
- Verifier: [TBD]
- Human Approver: required only for a new dependency or contract change
- Date: [TBD]

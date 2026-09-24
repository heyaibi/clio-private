# Phase 100740: Read-Surface De-Drift — Derive the `explain` Trace from the Hit

### Attribution
Rounds below record plan authorship; implementation sign-off is in §12.
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | [TBD] | proposed |
| Adversary | r1 | [TBD] | [TBD] |
| Remediator | r1 | [TBD] | [TBD] |
| Remedy Approver | r1 | [TBD] | [TBD] |
| Finalize | r1 | [TBD] | [TBD] |

**Capability phase 100740** · **Effort:** ~1–1.5 days · **Status:** Plan ready · **Parent:** gap analysis `gaps/recall-result-fidelity-gap-analysis.md` §3.4, §9.2, §7, §10.2; requirement §4.9.4.G, §4.12 (transparency), §4.9.5.C (health PII), FR-20 / §4.9.2 item 2

### Vocabulary (read first) — zero shared moniker

| Term | Meaning in this phase | Must not be confused with |
|------|------------------------|----------------------------|
| **explain trace** | The `explain` diagnostic payload that carries the score/domain/hop trace | The full read payload; a content surface |
| **shared projection** | One function/mask that turns a `ScoredHit` into the explain hit shape | Serializing the whole hit unconditionally |
| **volatile mask** | A defined set of fields the conformance test treats as varying | An authorization filter |

This phase changes where the trace's shape is defined, not what it contains.

---

## 1. Objective

### Goal
Make the `explain` hit projection derive from one shared source instead of the hand-written field list, so a new `ScoredHit` field cannot silently fail to appear in (or accidentally leak into) the trace. The trace stays PII-safe: entity names and any other content-derived field are excluded by an explicit mask, and a guard test fails if the shared projection and the trace disagree.

### Expected Outcome
- The `explain` hit shape is derived from a single projection over the hit structure.
- The trace still contains only ids, ranks, scores, counts, and timings; content-derived fields such as `entities` are excluded by an explicit allowlist/mask.
- A guard test detects drift between the shared projection and the trace shape.
- The trace's existing fields and values are unchanged for existing inputs.
- Adding a future non-content field requires a deliberate decision rather than accidental omission.

### Parent Requirement
`requirement.md` — §4.9.4.G (`explain` returns the score/domain/hop trace); §4.12 and §7.4 (transparency and content boundary) with §4.9.5.C (health-surface PII; diagnostic surfaces stay content-free); FR-20 / §4.9.2 item 2 (binding identity). Gap source: `gaps/recall-result-fidelity-gap-analysis.md` §9.2.

### Design References (source-verified at plan time)
- `retrieve_explanation` rebuilds a hit list field by field (`crates/clio-mcp/src/read_retrieve.rs:118-150`); the per-hit JSON is `:119-132` with keys `item_id`, `score`, `dense_rank`, `lexical_rank`, `consolidated`, `source_ids`.
- The module documents the trace as "PII-safe retrieval trace: ids, ranks, scores, counts, timings only" (`read_retrieve.rs:113`).
- The MCP conformance volatile mask already treats `score`/`metrics` as volatile (`crates/clio-mcp/tests/mcp_read_conformance.rs:196-228`).
- The finalized hit is built at `crates/clio-retrieve/src/finalize.rs:100-112`; the bindings project it separately.
- Adding `entities[]` (Phase 100680) is exactly the kind of field that must not enter the trace, which is why the shared projection must be an explicit mask, not whole-struct serialization.
- `read_retrieve.rs` is 271 lines.

---

## 2. Scope Boundaries

### In Scope
- One shared projection/mask that defines the `explain` hit shape from the hit structure.
- An explicit exclusion of content-derived fields (entities and any future equivalents).
- A guard test that detects drift.
- Updating call sites and the conformance/volatile handling.

### Explicitly Out of Scope
- Changing what the trace contains semantically, or its values.
- Adding `scores` to the trace (allowed later because scores are PII-safe, but not required here; if added, it must go through the shared projection).
- Entity extraction or the entity reason (Phases 100680/100700).
- Changing the read payload shape or the frozen contract.
- Cross-binding trace parity beyond the existing MCP trace.

### Must Not Change
- The trace remains content-free: no entity names, gist text, snapshot values, or query text in `explanation`.
- Existing trace fields and values for existing inputs.
- The volatile-mask semantics that keep conformance stable.
- Bank isolation and authorization.
- The frozen `RetrieveHit` contract.

### Scope Expansion Rule
If work outside this scope appears necessary:
1. Stop.
2. Document the reason.
3. Request clarification or approval.
4. Do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- Phase 100620 accepted: the hit structure carries the new display fields, so the drift surface is real.
- The PII boundary for the trace is recorded (gap analysis §6, §8 decision 5).
- The MCP retrieve response and CLI JSON serialize `RetrieveOutcome` wholesale; this phase owns only the `explain` trace projection, not the payload fields.

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| Hit structure | Carries the new fields | Phase 100620 acceptance |
| Trace projection | Hand-written today | `read_retrieve.rs:118-150` inspection |
| Trace doc | "ids, ranks, scores, counts, timings only" | `read_retrieve.rs:113` inspection |
| Conformance mask | Volatile fields defined | `mcp_read_conformance.rs:196-228` inspection |

---

## 4. Existing-System Discovery

The agent MUST re-verify the following before editing; the facts below were confirmed at plan time.

### Required Discovery
- Confirm the exact fields the trace includes today and where each comes from.
- Confirm the trace excludes content today (there is no entity field yet; Phase 100680 introduces one).
- Confirm the conformance test structure and volatile mask.
- Confirm the size of `read_retrieve.rs` and any shared projection location.
- Confirm whether the in-process or CLI paths expose an explain trace that must also derive from the same source.

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

### Current Repository Findings at Plan Time
- The trace is a separate hand-written projection; nothing enforces agreement with the hit shape.
- The trace is documented as PII-safe, so the shared projection must exclude `entities`.
- The volatile mask already anticipates score volatility.

### Repository Adaptation Rule
The agent must determine the concrete projection placement from the actual repository. The plan requires one source of truth and an explicit content mask; it does not prescribe the mechanism (shared function, serde skip list, or a dedicated view struct).

---

## 5. Implementation Specification

### Task 1: One Shared Explain Projection

#### Intent
Define the trace hit shape once, derived from the hit, with content excluded.

#### Required Capability or Behavior
- The explain hit shape comes from a single shared projection over the hit structure.
- The projection uses an explicit allowlist/mask; content-derived fields are excluded.
- The trace's existing keys and values are unchanged.
- Adding a new hit field either appears in the trace (if PII-safe and listed) or is excluded (if content-derived), by deliberate choice in one place.

#### Architectural Responsibility
`clio-mcp` owns the trace projection; if a shared view lives in `clio-retrieve`, that is acceptable, provided all trace consumers derive from it.

#### Required Changes
1. Introduce the single projection and route `retrieve_explanation` through it.
2. Explicitly exclude content-derived fields (entities and equivalents).
3. Keep the trace values identical for existing inputs.

#### Implementation Constraints
- Do not serialize the whole hit unconditionally.
- Do not add content to the trace.
- Keep `read_retrieve.rs` ≤450 lines.

#### Expected Result
The trace is produced from one definition; a content field cannot leak in by default.

### Task 2: Guard Against Drift

#### Intent
Fail a test if the shared projection and the trace shape diverge.

#### Required Capability or Behavior
- A guard test asserts the trace keys equal the projection's declared set.
- The test fails if a new non-content field is added to the hit and not deliberately classified.
- Existing conformance behavior is preserved.

#### Architectural Responsibility
`clio-mcp` owns the guard test at the trace owner's boundary.

#### Required Changes
1. Add the guard test.
2. Update the volatile mask or conformance expectations only as required by the projection refactor.
3. Document how a future field is classified.

#### Implementation Constraints
- Do not weaken the conformance test.
- Do not use process-global state.

#### Expected Result
A future field addition cannot drift silently; it forces a one-line classification.

### Implementation Freedom
The agent may choose the projection mechanism (shared function, view struct, serde attributes) and the guard-test form, provided the trace stays content-free, values are unchanged, and drift is detected.

---

## 6. Agent Execution Rules

### Allowed Actions
- Refactor the trace projection and update its tests.
- Update the conformance volatile mask as required by the refactor.

### Forbidden Actions
- Add content (entities, gist, snapshot, query) to the trace.
- Change trace values or the read payload.
- Weaken the conformance test.
- Delete tests or claim completion without evidence.

### Agent Decision Boundary
The agent may decide the projection mechanism and test placement. The agent must request approval for: adding a PII-safe field to the trace, changing trace semantics, or serializing the whole hit.

### Mandatory Stop Conditions
Stop and report if: the projection cannot exclude content without special-casing; existing trace values would change; or correctness cannot be verified.

---

## 7. Security Constraints

### Required Controls
- The trace remains content-free and PII-safe.
- No entity names, gist, snapshot, or query text may enter `explanation`.
- Authorization and bank isolation unchanged.

### Sensitive Data Rules
- Never log content or entity names in the trace.
- Never commit secrets.

### Security Acceptance Conditions
- A boundary test with an entity-bearing hit proves `explanation` contains no entity name.
- Existing redaction tests remain green.

---

## 8. Test and Verification Strategy

### Required Tests
- [ ] Unit tests (projection output matches the declared key set)
- [ ] Integration tests (trace through the MCP read path)
- [ ] Contract tests (existing trace values unchanged; content excluded)
- [ ] End-to-end tests (real MCP `retrieve` with `explain`)
- [ ] Regression tests (conformance suite green)
- [ ] Security tests (no entity/content in the trace)
- [ ] Failure-mode tests (hit without optional fields)

### Required Test Scenarios

| Test ID | Scenario | Expected Result |
|---------|----------|-----------------|
| T100740-01 | Existing hit | Trace keys/values identical to before |
| T100740-02 | Entity-bearing hit | No entity name in `explanation` |
| T100740-03 | New non-content field added (simulated) | Guard test fails until classified |
| T100740-04 | Hit with missing optional fields | Trace stable |
| T100740-05 | MCP conformance suite | Green |
| T100740-06 | Workspace suite, coverage, clippy, fmt, size | Green; per-file ≥90%; files ≤450 lines |

### Negative Testing
Verify content cannot enter the trace by default, trace values do not change, and the guard fails on unclassified fields.

### Verification Rule
Implementation claims must be supported by actual test output, inspection results, or other concrete evidence.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-100740-01 | Trace derives from one shared projection | T100740-01 | Source inspection; test output |
| AC-100740-02 | Trace stays content-free (no entities) | T100740-02 | Boundary test |
| AC-100740-03 | Drift is detected by a guard test | T100740-03 | Guard test output |
| AC-100740-04 | Existing trace values unchanged | T100740-01 | Before/after test output |
| AC-100740-05 | No regression; size/coverage gates pass | T100740-06 | Workspace suite; coverage report; size check |

### Definition of Done
- [ ] All in-scope behavior is implemented.
- [ ] All acceptance criteria pass.
- [ ] Required tests pass.
- [ ] No unauthorized changes were introduced.
- [ ] Existing behavior remains intact.
- [ ] Security checks pass.
- [ ] Documentation is updated where required.
- [ ] Evidence is collected.
- [ ] Verification is completed.
- [ ] Required approval is obtained.

### Completion Evidence
- Implementation summary
- Changed-component summary
- Test execution output (drift guard, content boundary)
- Verification report
- Known limitations

---

## 10. Failure Handling and Recovery

### Expected Failure Modes

| Failure | Detection | Recovery |
|---------|-----------|----------|
| Content leaks into the trace | Boundary test | Stop; add exclusion; treat as a security failure |
| Existing trace changed | Before/after test | Restore values; refactor only the shape's source |
| Guard test too weak | Review/test mutation | Strengthen the assertion |
| File approaches 450 lines | Size check | Decompose |

### Rollback Strategy
Revert the projection refactor; the previously hand-written projection is behavior-identical for existing inputs, so rollback is safe.

### Partial Completion Policy
If the projection is shared but the content exclusion or guard is missing, do not claim completion.

---

## 11. Traceability

| Parent Requirement | Implementation Task | Verification | Acceptance Criterion |
|--------------------|---------------------|--------------|-----------------------|
| §4.9.4.G (`explain` score/domain/hop trace) | Task 1 | T100740-01 | AC-100740-01 |
| §4.9.5.C (health PII) / §4.12 + §7.4 (content-free diagnostics) | Task 1, Task 2 | T100740-02 | AC-100740-02 |
| FR-20 / §4.9.2 item 2 (binding identity) | Task 1 | T100740-05 | AC-100740-01 |
| Gap §9.2 (projection drift) | Task 2 | T100740-03 | AC-100740-03 |
| Regression / quality contract | All | T100740-06 | AC-100740-05 |

Required chain:

```text
Requirement → Capability → Implementation → Test → Evidence
```

---

## 12. Phase Exit Contract

### Outputs Produced
- A single shared `explain` hit projection with explicit content exclusion.
- A drift guard test.

### Guarantees Provided to Downstream Phases
After this phase is accepted:
- Any future hit field is deliberately classified as trace-visible or content-excluded.
- The trace remains PII-safe as the result contract grows.

### Known Limitations
- `scores` is not required to appear in the trace by this phase; if added later, it must go through the shared projection.
- Only the MCP trace is in scope; other diagnostic surfaces are protected by their own tests.

### Downstream Prerequisites
- Phase 100780, if it touches diagnostic surfaces, must respect the shared projection's content exclusion.

### Final Status
PASS | PASS WITH DOCUMENTED LIMITATIONS | BLOCKED | FAILED

### Verification Sign-Off
- Implementer: [TBD]
- Verifier: [TBD]
- Human Approver: [TBD, if required]
- Date: [TBD]

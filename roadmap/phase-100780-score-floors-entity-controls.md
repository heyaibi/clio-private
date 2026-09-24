# Phase 100780: Score Floors and Entity Inclusion Controls

### Attribution
Rounds below record plan authorship; implementation sign-off is in §12.
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | [TBD] | proposed |
| Adversary | r1 | [TBD] | [TBD] |
| Remediator | r1 | [TBD] | [TBD] |
| Remedy Approver | r1 | [TBD] | [TBD] |
| Finalize | r1 | [TBD] | [TBD] |

**Extension phase 100780** · **Effort:** ~3–4 days · **Status:** Plan ready (extension; include only if scope is meant to cover the reference surface) · **Parent:** gap analysis `gaps/recall-result-fidelity-gap-analysis.md` §9.5, §7, §10.3; requirement §4.5, FR-20 / §4.9.2 item 2, PR-4, §4.9.5.C (health PII) / §4.12 + §7.4 (content boundary)

### Vocabulary (read first) — zero shared moniker

| Term | Meaning in this phase | Must not be confused with |
|------|------------------------|----------------------------|
| **score floor** | An optional minimum applied to a named score before a candidate is returned | A change to fusion or admission |
| **arm-local floor** | A floor on `semantic` or `keyword` that constrains only that arm's contribution | A global relevance floor over `final` |
| **entity inclusion** | An optional toggle/summary controlling whether entity names are returned | A ranking signal or a content surface |

These controls are additive and off by default. They do not change the default result for any existing call.

---

## 1. Objective

### Goal
Add optional `min_scores` floors over `semantic`, `keyword`, `reranker`, and `final`, and add entity-inclusion controls (a toggle plus a top-level entity summary) that mirror the reference surface. Every control is opt-in; the default behavior of `retrieve` is unchanged, and floors never silently widen or narrow a caller's explicit parameters.

### Expected Outcome
- `min_scores` accepts optional per-field floors (`semantic`, `keyword`, `reranker`, `final`); omitted floors are no-ops.
- An arm-local floor constrains only its own arm and is documented as such; a `final` floor applies to the returned set after ranking.
- Floors do not backfill freed slots: a floored query may return fewer results than `limit`, and it must not widen scope or exceed the budget to compensate.
- Entity inclusion can be disabled; a top-level entity summary can be requested.
- Entity names remain excluded from `warnings`, the `explain` trace, telemetry, and health.
- The relative-score caveats are documented; floors are not presented as calibrated thresholds.
- Default calls are byte-for-byte unchanged.

### Parent Requirement
`requirement.md` — §4.5 (relative, rank-fused retrieval; an arm-local floor must not become a cross-arm score comparison); FR-20 / §4.9.2 item 2 (binding identity); PR-4 / §4.5 (never present a relative score as calibrated); §4.9.5.C (health PII) and §4.12/§7.4 (content boundary). Gap source: `gaps/recall-result-fidelity-gap-analysis.md` §9.5.

### Design References (source-verified at plan time)
- The reference exposes `min_scores` floors over semantic/keyword/reranker/final, a top-level `entities` dict keyed by canonical name, and an `include.entities` toggle (gap analysis §1, §9.5).
- Clio's `scores` object and `entities[]` are delivered by Phases 100620, 100640, and 100680.
- Keyword values are backend-dependent (SQLite `-bm25` vs Postgres `ts_rank_cd`), so an arm-local `keyword` floor is backend-dependent by construction and must be documented; gap analysis §9.3.
- Fusion consumes ranks, not raw scores (`crates/clio-retrieve/src/fusion.rs:21-28`); an arm-local floor filters an arm's candidates before ranking and must not become a raw-score cross-arm comparison.
- The frozen `RetrieveHit` and the read payload shape are out of scope; controls are request parameters, and the entity summary is response metadata.

---

## 2. Scope Boundaries

### In Scope
- Optional `min_scores` floors over the four named scores.
- Arm-local floor semantics and documentation (each arm floor constrains its own arm).
- An entity-inclusion toggle and an optional top-level entity summary.
- Request-schema additions across bindings and their defaults.
- Tests for defaults, floors, toggles, and the content boundary.

### Explicitly Out of Scope
- Changing fusion, ranking order, candidate generation, or admission.
- Changing the score transforms (Phases 100620/100640).
- Entity linking, canonicalization beyond Phase 100680, or any ranking use.
- Making floors calibrated or cross-backend comparable.
- A temporal arm (Phase 100800).
- Persisting floors or entities.

### Must Not Change
- Default call behavior (no floors, entities as delivered by Phase 100680).
- Rank-fused ordering.
- The frozen `RetrieveHit` contract.
- The entity content boundary (no entities in `warnings`/trace/telemetry/health).
- Explicit caller parameters: a floor must not silently override `limit`, `budget`, or scope.
- Secret masking and config precedence.

### Scope Expansion Rule
If work outside this scope appears necessary:
1. Stop.
2. Document the reason.
3. Request clarification or approval.
4. Do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- Phases 100620 and 100640 accepted: the `scores` object and normalized `reranker` exist.
- Phase 100680 accepted: `entities[]` exists with documented coverage.
- The arm-local floor semantics decision is recorded.

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| `scores` object | Present and documented | Phase 100620/100640 acceptance |
| `entities[]` | Present with coverage limits | Phase 100680 acceptance |
| Request schema | Retrieval parameters published | Schema inspection |
| Fusion | Rank-only | `fusion.rs:21-28` inspection |
| Bindings | MCP/in-process/CLI parity | Parity tests |

---

## 4. Existing-System Discovery

The agent MUST re-verify the following before editing; the facts below were confirmed at plan time.

### Required Discovery
- Confirm the retrieval request schema across bindings and where optional parameters are validated.
- Confirm where a floor can be applied without entering `rrf_fuse` as a raw cross-arm score.
- Confirm the entity summary can be assembled without leaking content into disallowed surfaces.
- Confirm the default-call payload so "unchanged" is provable.
- Confirm which files are near the 450-line limit.

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
- Fusion is rank-only; floors must filter before ranking per arm.
- Keyword floors are backend-dependent and cannot claim parity.
- Default behavior must remain unchanged; the implementation must short-circuit when no floor/toggle is supplied.

### Repository Adaptation Rule
The agent must determine the concrete parameter placement from the actual repository. The plan requires opt-in controls, arm-local semantics, and default-call invariance.

---

## 5. Implementation Specification

### Task 1: Optional Score Floors

#### Intent
Let a caller request minimum per-stage scores without changing default results.

#### Required Capability or Behavior
- `min_scores` accepts optional `semantic`, `keyword`, `reranker`, `final` values.
- A `semantic`/`keyword`/`reranker` floor constrains only that arm's candidates before ranking; a `final` floor applies to the returned set.
- Absent floors leave behavior unchanged.
- Floors do not backfill freed slots; a floored query may return fewer results than `limit`.
- Floors are deterministic and validated (reject nonsensical values with the established error shape).
- A `keyword` floor is documented as backend-dependent.
- Floors never silently widen a caller's scope or exceed the token budget.

#### Architectural Responsibility
`clio-retrieve` owns floor application and ranking; bindings own parameter validation and passthrough.

#### Required Changes
1. Add the optional floor parameters and their validation.
2. Apply arm-local floors pre-fusion (per arm) and the `final` floor post-ranking.
3. Document arm-local vs global semantics and the relative-score caveat.
4. Add tests for each floor and the default no-op.

#### Implementation Constraints
- No raw-score cross-arm comparison.
- No change to fusion weights or ordering beyond removing below-floor candidates.
- Keep files ≤450 lines.

#### Expected Result
With floors supplied, only candidates meeting the named floor survive; without floors, output is unchanged.

### Task 2: Entity Inclusion Controls and Summary

#### Intent
Let a caller suppress entities and optionally request a top-level entity summary.

#### Required Capability or Behavior
- An entity-inclusion toggle can suppress `entities[]` in the response.
- An optional top-level entity summary lists entities present in the page.
- The summary is assembled from the already-delivered `entities[]`; no new extraction.
- Entity names remain excluded from `warnings`, the `explain` trace, telemetry, and health.
- Default behavior (entities present per Phase 100680) is unchanged.

#### Architectural Responsibility
`clio-retrieve` owns the summary; bindings project it consistently.

#### Required Changes
1. Add the toggle and summary parameter(s).
2. Assemble the summary deterministically.
3. Keep the content boundary.
4. Add parity and boundary tests.

#### Implementation Constraints
- No entity ranking or scoring.
- No content in disallowed surfaces.
- Keep files ≤450 lines.

#### Expected Result
A caller can suppress entities or request a summary; defaults are unchanged.

### Implementation Freedom
The agent may choose the parameter names, the summary shape, and where floors are applied, provided arm-local semantics, default-call invariance, cross-binding identity, and the content boundary hold.

---

## 6. Agent Execution Rules

### Allowed Actions
- Add the optional controls, validation, tests, and documentation.
- Refactor locally to stay within the 450-line limit.

### Forbidden Actions
- Change defaults, fusion, ordering, or admission.
- Make floors calibrated or cross-backend comparable.
- Add entity ranking or leak entities into diagnostics.
- Add dependencies, delete tests, or claim completion without evidence.

### Agent Decision Boundary
The agent may decide parameter names and internal application points. The agent must request approval for: changing default behavior, changing fusion, making a floor global across arms, or adding a dependency.

### Mandatory Stop Conditions
Stop and report if: default behavior cannot remain unchanged; an arm-local floor would require raw-score fusion changes; entities cannot stay out of disallowed surfaces; or correctness cannot be verified.

---

## 7. Security Constraints

### Required Controls
- Floors are request metadata and carry no content.
- Entity summary remains authorized-read-only and excludes disallowed surfaces.
- Bank isolation and authorization unchanged.

### Sensitive Data Rules
- Never log entity names or query text outside the authorized payload.
- Never commit secrets.

### Security Acceptance Conditions
- A boundary test proves entities/summary are absent from `warnings`, trace, telemetry, and health.
- Oversized/invalid floor values are rejected.

---

## 8. Test and Verification Strategy

### Required Tests
- [ ] Unit tests (each floor; arm-local vs final; validation; entity toggle/summary)
- [ ] Integration tests (floors through the retrieve path)
- [ ] Contract tests (default payload unchanged; binding parity)
- [ ] End-to-end tests (real CLI/MCP with floors and toggle)
- [ ] Regression tests (no-floor behavior; Phase 100620–100680 suites)
- [ ] Security tests (entity boundary; invalid input)
- [ ] Failure-mode tests (nonsensical floor; empty after flooring)

### Required Test Scenarios

| Test ID | Scenario | Expected Result |
|---------|----------|-----------------|
| T100780-01 | No floors supplied | Default payload unchanged |
| T100780-02 | `semantic` floor | Only arm-local survivors; other arms unaffected |
| T100780-03 | `keyword` floor on SQLite vs Postgres | Applied per backend; backend-dependence documented |
| T100780-04 | `reranker` floor with rerank disabled | No-op / documented behavior |
| T100780-05 | `final` floor | Returned set filtered post-ranking; budget respected |
| T100780-06 | Entity toggle off | `entities[]` suppressed consistently |
| T100780-07 | Entity summary requested | Deterministic summary; no disallowed surface |
| T100780-08 | Invalid floor value | Rejected with usage error |
| T100780-09 | Workspace suite, coverage, clippy, fmt, size | Green; per-file ≥90%; files ≤450 lines |

### Negative Testing
Verify defaults are unchanged, floors never widen scope, entities never leak, and invalid inputs fail closed.

### Verification Rule
Implementation claims must be supported by actual test output, inspection results, or other concrete evidence.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-100780-01 | Optional floors work; arm-local semantics documented | T100780-02…T100780-05 | Test output; docs |
| AC-100780-02 | Keyword floor backend-dependence documented, no parity claimed | T100780-03 | Test output; docs |
| AC-100780-03 | Entity toggle and summary work; boundary preserved | T100780-06, T100780-07 | Test output |
| AC-100780-04 | Default call unchanged | T100780-01 | Before/after test output |
| AC-100780-05 | Cross-binding identity | T100780-06 | Parity test output |
| AC-100780-06 | Invalid input rejected; no regression; size/coverage gates pass | T100780-08, T100780-09 | Workspace suite; coverage report; size check |

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
- Arm-local floor decision record
- Changed-component summary
- Test execution output
- Verification report
- Known limitations

---

## 10. Failure Handling and Recovery

### Expected Failure Modes

| Failure | Detection | Recovery |
|---------|-----------|----------|
| Floor becomes a cross-arm score comparison | Ordering/fusion test | Restrict to arm-local filtering |
| Default payload changed | Before/after test | Short-circuit when no control supplied |
| Entity leaks into a diagnostic surface | Boundary test | Remove it; treat as a security failure |
| Invalid floor accepted | Validation test | Fail closed |
| Empty result after flooring | Handling test | Return an empty page, do not widen silently |

### Rollback Strategy
Remove the optional controls; default behavior already proved unchanged, so rollback is behavior-preserving. No data migration.

### Partial Completion Policy
If floors work but entity controls do not (or vice versa), do not claim completion. Record partial work and keep the tree green.

---

## 11. Traceability

| Parent Requirement | Implementation Task | Verification | Acceptance Criterion |
|--------------------|---------------------|--------------|-----------------------|
| §4.5 (relative, rank-fused retrieval) | Task 1 | T100780-02, T100780-04 | AC-100780-01 |
| Gap §9.3 (backend keyword scales) | Task 1 | T100780-03 | AC-100780-02 |
| FR-20 / §4.9.2 item 2 (binding identity) | Task 2 | T100780-06 | AC-100780-05 |
| §4.12 + §7.4 (content boundary) / §4.9.5.C (health PII) | Task 2 | T100780-07 | AC-100780-03 |
| PR-4 / §4.5 (not calibrated) | Task 1 | T100780-01 | AC-100780-04 |
| Regression / quality contract | All | T100780-09 | AC-100780-06 |

Required chain:

```text
Requirement → Capability → Implementation → Test → Evidence
```

---

## 12. Phase Exit Contract

### Outputs Produced
- Optional per-score floors with arm-local semantics.
- Entity-inclusion toggle and top-level entity summary.

### Guarantees Provided to Downstream Phases
After this phase is accepted:
- Callers can constrain their own arm's candidates and control entity exposure without changing defaults.
- The reference `min_scores`/`include.entities` surface has a Clio equivalent.

### Known Limitations
- Keyword floors are backend-dependent; no cross-backend parity.
- Floors are relative filters, not calibrated relevance thresholds.
- No entity ranking or linking.
- `reranker` floors interact with the fail-open rerank policy and are documented accordingly.

### Downstream Prerequisites
- No later phase in this set depends on 100780; it is an independent extension.

### Final Status
PASS | PASS WITH DOCUMENTED LIMITATIONS | BLOCKED | FAILED

### Verification Sign-Off
- Implementer: [TBD]
- Verifier: [TBD]
- Human Approver: [TBD, if required]
- Date: [TBD]

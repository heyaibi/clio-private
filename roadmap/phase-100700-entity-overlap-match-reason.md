# Phase 100700: Entity-Overlap Match Reason (Display-Only)

### Attribution
Rounds below record plan authorship; implementation sign-off is in §12.
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | [TBD] | proposed |
| Adversary | r1 | [TBD] | [TBD] |
| Remediator | r1 | [TBD] | [TBD] |
| Remedy Approver | r1 | [TBD] | [TBD] |
| Finalize | r1 | [TBD] | [TBD] |

**Capability phase 100700** · **Effort:** ~2–3 days · **Status:** Plan ready · **Parent:** gap analysis `gaps/recall-result-fidelity-gap-analysis.md` §4.2, §7, §8 decision 4, §10.2; requirement FR-4 / §4.4, PR-4, §4.5, FR-20 / §4.9.2 item 2

### Vocabulary (read first) — zero shared moniker

| Term | Meaning in this phase | Must not be confused with |
|------|------------------------|----------------------------|
| **entity overlap** | The query text contains one of the hit's entity names under a documented, deterministic match rule | An entity-based ranking signal or a boost |
| **match reason** | A displayed, clearly labelled *derived* note ("entity match") | A span-verified fact or a retrieval-provenance reason |
| **derived** | Computed at retrieval/display time, not verified against a source span | The verified snapshot `entity` value itself |

This phase adds an explanation, not a ranking input. The hit set and order are unchanged.

---

## 1. Objective

### Goal
Add a deterministic, display-only entity-overlap reason: when the query text contains one of a hit's entity names under a documented match rule, mark that hit with a derived, non-authoritative `[entity match]` reason. The match never affects ordering, scoring, or filtering, and the reason is labelled derived everywhere it appears.

### Expected Outcome
- A hit whose `entities[]` contains a name present in the query text is marked with a derived entity-match reason.
- The match rule is deterministic (documented normalization; no fuzzy matching) and case handling is documented and tested.
- The reason is labelled derived and non-authoritative; it is not present in `warnings`, telemetry, or health surfaces (only the authorized read payload and the reserved text slot).
- Ordering, `scores`, and the hit set are unchanged by the presence of a match.
- The display-only vs rank-based decision is recorded; a ranking leg is explicitly not delivered here.
- The reason appears in the recall text view via the Phase 100660 slot, consistently across bindings.

### Parent Requirement
`requirement.md` — FR-4 / §4.4 (snapshot entities are span-verified; an inferred overlap is not); PR-4 / §4.4 (a derived reason must not be presented as a verified fact); §4.5 (an entity ranking leg would have to fuse by rank and is out of scope); FR-20 / §4.9.2 item 2 (binding identity). Gap source: `gaps/recall-result-fidelity-gap-analysis.md` §4.2.

### Design References (source-verified at plan time)
- No entity matching, overlap, or boost exists today in `crates/clio-retrieve`; boosts present are importance/temporal, and "overlap" in dedup is token overlap, not entity overlap.
- `recall_reason` (`crates/clio-lib/src/cli_read_render.rs:78-85`) maps `dense_rank`/`lexical_rank` to provenance text; the entity reason should follow the same display shape and be visually distinguishable as derived.
- The reserved slot is delivered by Phase 100660 (`crates/clio-lib/src/cli_read_render.rs:36-67`).
- Query text is available at retrieval time (`crates/clio-retrieve/src/hybrid.rs:179-282`, the `retrieve` request carries the query).
- Entity names are on the hit after Phase 100680.
- Determinism requirement: identical input/config MUST produce identical ordering and reason (risk §9 ranking-drift).

---

## 2. Scope Boundaries

### In Scope
- A deterministic entity-overlap match between query text and the hit's `entities[]`.
- A per-hit derived reason exposed on the authorized read surface and rendered in the text slot.
- Documented normalization and case handling.
- Tests for determinism and case sensitivity.
- A recorded decision: display-only (recommended) vs a future rank-based leg.

### Explicitly Out of Scope
- Any entity-based boost, ranking leg, or fusion change.
- Entity linking, canonicalization, or resolution beyond Phase 100680.
- Adding entity names to `warnings`, the `explanation`/`explain` trace, telemetry, or health.
- Query-time entity recognition beyond matching against the hit's names.
- Changing `recall_reason` provenance semantics.
- Entity-inclusion toggles (Phase 100780).

### Must Not Change
- Ordering, `scores`, candidate set, or budgets.
- The verified snapshot `entity` (the reason is derived, the value is not).
- The PII/content boundary and read authorization.
- The frozen `RetrieveHit` contract.
- Existing provenance reasons.

### Scope Expansion Rule
If work outside this scope appears necessary:
1. Stop.
2. Document the reason.
3. Request clarification or approval.
4. Do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- Phase 100680 accepted: hits carry `entities[]`.
- Phase 100660 accepted: the text view has the reserved entity-reason slot.
- The display-only decision is recorded (gap analysis §8 decision 4).
- Phases 100366/100368 (complete) own the CLI read path and the `recall_reason` rendering this phase extends (`command-ownership.md`).

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| `entities[]` | Present on hits | Phase 100680 acceptance |
| Text slot | Reserved in recall text | Phase 100660 acceptance |
| Query text | Available to the reason computation | `hybrid.rs` retrieve request inspection |
| Bindings | MCP/in-process/CLI projections | Parity tests |
| Match rule | Documented and deterministic | This phase's design record |

---

## 4. Existing-System Discovery

The agent MUST re-verify the following before editing; the facts below were confirmed at plan time.

### Required Discovery
- Confirm where the query text is available and whether the reason is computed in retrieval (shared) or only in the text renderer.
- Confirm the Phase 100660 slot and the `recall_reason` shape.
- Confirm how a derived reason can be exposed without leaking entity names into disallowed surfaces.
- Confirm the determinism test approach (identical input/config twice).
- Confirm which crates' files are near the 450-line limit.

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
- No entity matching exists; the reason is new.
- The query is available during retrieval, which is the natural shared place for cross-binding identity; a renderer-only computed reason would diverge JSON from text.
- `recall_reason` gives the display precedent.
- Determinism is already a requirement of the ranking contract (identical input/config), so the reason must be a pure function of the query and the hit's entities.

### Repository Adaptation Rule
The agent must determine the concrete computation location (shared retrieval vs binding) from the actual repository, provided the chosen placement yields identical names and semantics across bindings (FR-20).

---

## 5. Implementation Specification

### Task 1: Deterministic Entity-Overlap Match

#### Intent
Decide, deterministically, whether the query text contains one of the hit's entity names.

#### Required Capability or Behavior
- The match is a documented, deterministic function of the query text and the hit's `entities[]`.
- Normalization (for example Unicode case folding and trim) is documented; no fuzzy, stemmed, or approximate matching.
- Empty `entities[]` yields no match.
- Identical input/config yields identical match results.
- The match does not read or alter `scores`, ranks, or ordering.

#### Architectural Responsibility
`clio-retrieve` owns retrieval and MUST compute the derived flag once there; every binding (MCP, in-process, CLI text, and CLI JSON) projects that same flag. A renderer-only computation is not permitted because it would let JSON and text diverge (FR-20).

#### Required Changes
1. Implement the match function and document the normalization/case rule.
2. Attach a per-hit derived reason when a match occurs.
3. Ensure the function is pure and deterministic.
4. Add unit tests for case handling, whitespace, substrings, and multi-entity hits.
5. Compute the derived flag once in `clio-retrieve` and project it identically in every binding; add a parity test that CLI JSON and CLI text agree.

#### Implementation Constraints
- No ranking effect.
- No entity value in disallowed surfaces.
- No new dependency.
- Keep files ≤450 lines; `hybrid.rs` is 416.

#### Expected Result
A hit whose entity name appears in the query carries a derived entity-match flag; all others do not.

### Task 2: Display the Derived Reason and Record the Decision

#### Intent
Render the reason in the reserved slot, clearly labelled derived, and record the display-only decision.

#### Required Capability or Behavior
- The recall text shows the entity-match reason in the reserved slot, distinguishable from provenance reasons and labelled derived.
- The reason is identical across bindings on the authorized read surface.
- The reason does not appear in `warnings`, the `explanation`/`explain` trace, telemetry, or health.
- A short decision record states display-only was chosen and why a rank-based leg is deferred.

#### Architectural Responsibility
`clio-retrieve` owns the flag; `clio-lib` renders it; all bindings project it consistently.

#### Required Changes
1. Render the reason in the text slot; add a derived label.
2. Consume the single `clio-retrieve` flag in every binding (MCP, in-process, CLI text and JSON) and add a JSON/text parity test.
3. Add the boundary test for disallowed surfaces.
4. Record the display-only decision and the rank-based prerequisites.

#### Implementation Constraints
- Do not change provenance reasons or the disclaimer.
- Do not present the reason as verified.
- Keep test files ≤450 lines.

#### Expected Result
Text and JSON show the same derived reason; no disallowed surface contains entity names; the decision is recorded.

### Implementation Freedom
The agent may choose the match representation (boolean flag vs reason enum), the exact normalization, and where the reason is computed, provided determinism, cross-binding identity, derived labelling, and the no-ranking effect hold.

---

## 6. Agent Execution Rules

### Allowed Actions
- Add the match function, the derived reason, rendering, and tests.
- Record the display-only decision in the phase evidence.

### Forbidden Actions
- Add entity ranking, boosting, or fusion changes.
- Put entity names into `warnings`, trace, telemetry, or health.
- Change ordering, `scores`, budgets, provenance reasons, or the disclaimer.
- Add dependencies, delete tests, or claim completion without evidence.

### Agent Decision Boundary
The agent may decide the match representation and computation placement. The agent must request approval for: any ranking effect, any fuzzy matching, or adding entity data to a diagnostic surface.

A rank-based entity leg is **not** approved by this phase; if the agent believes it is needed, it must stop and request a separate phase (it would require rank-based fusion and benchmark validation).

### Mandatory Stop Conditions
Stop and report if: the match cannot be made deterministic; the reason cannot be exposed without leaking entity names into a disallowed surface; a ranking effect would be required; or correctness cannot be verified.

---

## 7. Security Constraints

### Required Controls
- The reason is computed against the query the caller already supplied; no new data access.
- Entity names remain content; the reason stays on the authorized read surface only.
- No entity name in `warnings`, trace, telemetry, or health.
- Bank isolation and read authorization unchanged.

### Sensitive Data Rules
- Never log the query text or entity names.
- Never commit secrets.

### Security Acceptance Conditions
- A boundary test proves the reason/entities are absent from `warnings`, the explain trace, telemetry, and health.
- No query text is echoed into any error or log by this phase.

---

## 8. Test and Verification Strategy

### Required Tests
- [ ] Unit tests (exact match, case difference, substring, whitespace, multiple entities, empty entities)
- [ ] Integration tests (flag reaches the hit and the text slot)
- [ ] Contract tests (binding parity; ordering/scores unchanged)
- [ ] End-to-end tests (real CLI/MCP `recall` shows the derived reason)
- [ ] Regression tests (provenance reasons and disclaimer unchanged)
- [ ] Security tests (no entity/query in disallowed surfaces)
- [ ] Failure-mode tests (empty entities; query absent)

### Required Test Scenarios

| Test ID | Scenario | Expected Result |
|---------|----------|-----------------|
| T100700-01 | Query contains an entity name (same case) | Derived entity-match reason shown |
| T100700-02 | Case differs | Match per documented case rule (deterministic) |
| T100700-03 | Query does not contain any entity name | No reason |
| T100700-04 | Hit has empty `entities[]` | No reason |
| T100700-05 | Identical input/config run twice | Identical reason and ordering |
| T100700-06 | Ordering and `scores` before/after | Unchanged |
| T100700-07 | MCP/in-process/CLI for same store | Identical reason |
| T100700-08 | Warnings/trace/telemetry/health | No entity name or reason |
| T100700-09 | Workspace suite, coverage, clippy, fmt, size | Green; per-file ≥90%; files ≤450 lines |

### Negative Testing
Verify the reason never changes ranking, is never presented as verified, and never leaks into a diagnostic surface.

### Verification Rule
Implementation claims must be supported by actual test output, inspection results, or other concrete evidence.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-100700-01 | Deterministic entity-overlap match with documented normalization | T100700-01, T100700-02, T100700-05 | Test output; design record |
| AC-100700-02 | Reason is shown labelled derived and non-authoritative | T100700-01 | Golden/test output |
| AC-100700-03 | Ordering, `scores`, and hit set unchanged | T100700-06 | Before/after test output |
| AC-100700-04 | Identical reason across bindings; absent from disallowed surfaces | T100700-07, T100700-08 | Parity/boundary tests |
| AC-100700-05 | Display-only decision recorded; no ranking leg delivered | Inspection | Decision record |
| AC-100700-06 | No regression; size/coverage gates pass | T100700-09 | Workspace suite; coverage report; size check |

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
- Display-only decision record with rank-based prerequisites
- Changed-component summary
- Test execution output (determinism, boundaries, parity)
- Verification report
- Known limitations

---

## 10. Failure Handling and Recovery

### Expected Failure Modes

| Failure | Detection | Recovery |
|---------|-----------|----------|
| Match is nondeterministic | Repeat-run test | Restrict normalization; remove nondeterministic input |
| Reason changes ranking | Before/after ordering test | Remove any ranking use |
| Entity leaks into a diagnostic surface | Boundary test | Remove it; treat as a security failure |
| Binding divergence | Parity test | Fix the projection |
| Reason presented as verified | Read/review | Add the derived label |

### Rollback Strategy
Remove the reason and its rendering; entity names remain only in `entities[]`, and ranking was never affected, so rollback is behavior-preserving.

### Partial Completion Policy
If the match works but the label/boundary is incomplete, do not claim completion. A derived reason without a derived label is a defect.

---

## 11. Traceability

| Parent Requirement | Implementation Task | Verification | Acceptance Criterion |
|--------------------|---------------------|--------------|-----------------------|
| FR-4 / §4.4 (verified vs inferred) | Task 1, Task 2 | T100700-01, T100700-02 | AC-100700-01, AC-100700-02 |
| PR-4 / §4.4 (non-authoritative) | Task 2 | T100700-01 | AC-100700-02 |
| §4.5 (ranking is rank-fused) | Task 1 | T100700-06 | AC-100700-03 |
| FR-20 / §4.9.2 item 2 (binding identity) | Task 2 | T100700-07 | AC-100700-04 |
| §4.12 + §7.4 (content boundary) / §4.9.5.C (health PII) | Task 2 | T100700-08 | AC-100700-04 |
| Regression / quality contract | All | T100700-09 | AC-100700-06 |

Required chain:

```text
Requirement → Capability → Implementation → Test → Evidence
```

---

## 12. Phase Exit Contract

### Outputs Produced
- A deterministic, derived, display-only entity-overlap reason.
- A recorded display-only decision and rank-based prerequisites.

### Guarantees Provided to Downstream Phases
After this phase is accepted:
- A consumer can see why an entity-bearing hit appeared, without any ranking change.
- Phase 100780 may build an entity-inclusion toggle on the stable `entities[]`/reason shape.

### Known Limitations
- Display-only; entity overlap confers no ranking advantage.
- Deterministic exact/substring-style matching only; no fuzzy or semantic entity match.
- Coverage is bounded by the Phase 100680 snapshot coverage.
- A rank-based entity leg remains a separate, unapproved capability requiring rank fusion and benchmark validation.

### Downstream Prerequisites
- Phase 100780 may rely on the derived reason shape and `entities[]`.
- Any future rank-based entity leg must reference this decision record and not retrofit ranking into this reason.

### Final Status
PASS | PASS WITH DOCUMENTED LIMITATIONS | BLOCKED | FAILED

### Verification Sign-Off
- Implementer: [TBD]
- Verifier: [TBD]
- Human Approver: [TBD, if required]
- Date: [TBD]

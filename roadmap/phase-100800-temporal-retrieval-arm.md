# Phase 100800: Temporal (Relative-Date) Retrieval Arm

### Attribution
Rounds below record plan authorship; implementation sign-off is in §12.
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | [TBD] | proposed |
| Adversary | r1 | [TBD] | [TBD] |
| Remediator | r1 | [TBD] | [TBD] |
| Remedy Approver | r1 | [TBD] | [TBD] |
| Finalize | r1 | [TBD] | [TBD] |

**Extension phase 100800** · **Effort:** ~5–8 days · **Status:** Plan ready (extension; larger than the rest and arguably its own track) · **Parent:** gap analysis `gaps/recall-result-fidelity-gap-analysis.md` §9.6, §7, §10.3; requirement §4.5, §4.6, FR-24, PR-4, §9 ranking-drift

### Vocabulary (read first) — zero shared moniker

| Term | Meaning in this phase | Must not be confused with |
|------|------------------------|----------------------------|
| **temporal expression** | A relative date/time phrase in the query (for example "last week", "yesterday") | An absolute `as_of` timestamp |
| **anchor** | The timestamp a relative expression is resolved against | "Now" at display time; the stored item timestamp |
| **temporal arm** | A rank-based candidate source that retrieves within the resolved window | A filter applied after fusion; an admission change |
| **window** | The resolved time interval the arm searches | A validity/tx interval on a triple |

The absolute `as_of`/`time_axis` controls already exist and are unchanged; this phase adds relative resolution.

---

## 1. Objective

### Goal
Add a temporal retrieval arm: parse relative temporal expressions from the query, resolve them against a defined anchor timestamp into a concrete window, retrieve candidates within that window, and fuse the arm by rank alongside dense, lexical, and graph. The arm is an extension of the existing retrieval path; it does not replace the absolute `as_of`/`time_axis` controls.

### Expected Outcome
- Relative temporal expressions in a query are parsed into a deterministic time window against a documented anchor.
- The temporal arm retrieves candidates in that window as a separate arm and fuses by rank; raw scores are never mixed.
- With no temporal expression, the arm is a no-op and results are unchanged.
- The temporal arm requires an explicit caller-supplied anchor (`query_anchor`, the Hindsight `query_timestamp` equivalent); an absent anchor means the arm does not run (or the request is rejected at validation), so server time is never a hidden input.
- Timezone and locale handling are documented and fail closed on ambiguity.
- The arm remains bounded and respects the token budget and explicit caller parameters.

### Parent Requirement
`requirement.md` — §4.5 (adaptive retrieval: dense + lexical + graph, then rerank; an added arm must fuse by rank); §4.6 (bi-temporal graph semantics); FR-24 (`retrieve` honors `as_of`/`time_axis`; explicit reads run); PR-4 / §4.5 (no calibrated/raw cross-leg comparison); §9 ranking-drift and the §9 retrieval temporal-anchor determinism rule (explicit anchor; no implicit server clock). Gap source: `gaps/recall-result-fidelity-gap-analysis.md` §9.6.

### Design References (source-verified at plan time)
- Clio's only temporal retrieval control is the absolute `as_of`/`time_axis` pair (`crates/clio-retrieve/src/types.rs:76-79`); there is no query-time temporal parsing.
- Fusion consumes ranks, not raw scores (`crates/clio-retrieve/src/fusion.rs:21-28`); `FusedHit` carries a rank vector (`fusion.rs:46-54`). Any new arm must contribute ranks.
- The dense/lexical legs return item ids and are composed in `retrieve` (`crates/clio-retrieve/src/hybrid.rs:179-282`); the graph arm is bounded expansion.
- The reference parses relative temporal expressions and anchors them to a query timestamp (gap analysis §9.6).
- Determinism: `§9` requires deterministic behavior for identical inputs and configuration, and the new §9 retrieval temporal-anchor determinism rule explicitly forbids an implicit server clock; the anchor is therefore an explicit request input, and the same input plus anchor must produce the same window.
- This is a new retrieval arm and query parser: the gap analysis rates confidence low-medium and sizes it at 5–8 days.

---

## 2. Scope Boundaries

### In Scope
- A query-time parser for relative temporal expressions.
- A documented anchor rule and window resolution.
- A rank-based temporal arm that retrieves in the window and fuses by rank.
- Timezone/locale handling and fail-closed ambiguity.
- Bounded resource use, budget compliance, and no-op behavior without a temporal expression.
- Request-schema additions across bindings and parity tests.

### Explicitly Out of Scope
- Changing the absolute `as_of`/`time_axis` controls.
- Changing bi-temporal storage, triple interval algebra, or validity semantics.
- Changing dense/lexical/graph legs or the rerank stage.
- Relative-date parsing on writes, or storing a parsed temporal field.
- Replacing fusion or scoring; the arm must fuse by rank.
- Temporal ranking enhancements beyond the bounded window (for example recency boosting is separate).

### Must Not Change
- Rank-fused ordering and the rule that raw cross-leg scores are never mixed.
- The absolute `as_of`/`time_axis` behavior.
- Budgets and explicit caller parameters; the arm must not exceed them or silently widen scope.
- The frozen `RetrieveHit` contract.
- Admission, taxonomy, and confidence semantics.
- Determinism for identical input and configuration (including the defined anchor).

### Scope Expansion Rule
If work outside this scope appears necessary:
1. Stop.
2. Document the reason.
3. Request clarification or approval.
4. Do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- Phase 100620 accepted: per-arm provenance is carried in one structure, which a new arm must join.
- The anchor parameter name/shape and the supported expression set are decided and recorded; the §9 retrieval temporal-anchor determinism rule is the parent constraint.
- The bi-temporal query semantics are understood on both backends.

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| Fusion | Rank-only | `fusion.rs:21-28` inspection |
| Per-arm structure | Carries per-arm rank | Phase 100620 acceptance |
| Absolute temporal controls | `as_of`/`time_axis` present | `types.rs:76-79` inspection |
| Bi-temporal storage | Queryable intervals on both backends | §4.6 tests |
| Anchor input | Explicit caller-supplied value; no server-time default | §9 retrieval temporal-anchor determinism; `requirement.md` |
| Bindings | Request schema parity | Parity tests |

---

## 4. Existing-System Discovery

The agent MUST re-verify the following before editing; the facts below were confirmed at plan time.

### Required Discovery
- Confirm how the existing legs add candidates and how a fourth arm would join the rank maps without changing fusion.
- Confirm the absolute `as_of`/`time_axis` plumbing so the temporal arm composes with, not against, it.
- Confirm the bi-temporal query support on both backends.
- Confirm where request parameters are validated across bindings.
- Confirm where an explicit caller-supplied anchor can be threaded and validated across the bindings' request schemas.
- Confirm determinism tests and the rotation/clock surface, if any.

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
- No relative-date parsing exists; only absolute controls.
- Fusion is rank-only, so the arm must produce a ranking, not scores.
- The anchor problem is the main determinism risk: "last week" depends on "now". The §9 retrieval temporal-anchor determinism rule settles it: the anchor is an explicit caller-supplied input and there is no server-time default.

### Repository Adaptation Rule
The agent must determine the concrete parser and arm placement from the actual repository. The plan requires rank-based participation, an explicit caller-supplied anchor (no server-time default), and no change to the absolute controls.

---

## 5. Implementation Specification

### Task 1: Parse Relative Temporal Expressions Against a Defined Anchor

#### Intent
Turn a relative phrase into a concrete window deterministically.

#### Required Capability or Behavior
- A supported set of relative expressions is parsed into a window.
- The request carries an explicit caller-supplied anchor (`query_anchor`); there is no server-time default. A relative expression with no anchor fails closed (no arm contribution) or is rejected at validation, deterministically.
- The same query, anchor, and configuration produce the same window.
- Unsupported or ambiguous expressions fail closed (no arm contribution) rather than guessing.
- Timezone and day-boundary handling are documented; ambiguous forms fail closed.
- No temporal expression means no arm contribution.

#### Architectural Responsibility
`clio-retrieve` owns query parsing and window resolution. Bindings add the explicit anchor to the request schema and pass it through unchanged.

#### Required Changes
1. Implement the parser and the supported-expression set.
2. Add the explicit anchor parameter to the request across bindings and thread it deterministically; do not read a server clock.
3. Implement fail-closed handling for ambiguity and for a relative expression with no anchor.
4. Add unit tests for supported, unsupported, ambiguous, timezone, and no-anchor cases.

#### Implementation Constraints
- No new dependency unless approved.
- Keep files ≤450 lines.
- Do not alter the absolute `as_of`/`time_axis` semantics.

#### Expected Result
A supported relative phrase yields a deterministic window; anything else yields no window.

### Task 2: Add the Temporal Arm and Fuse by Rank

#### Intent
Retrieve within the window as one arm among the existing legs.

#### Required Capability or Behavior
- The arm produces a ranked candidate list for the window on both backends.
- It joins the existing legs; fusion still consumes ranks only.
- Bounded: the arm respects candidate limits, budgets, and bank scope.
- With no window, the arm is a no-op and results are unchanged.
- The arm composes with the absolute `as_of`/`time_axis` controls without contradicting them.

#### Architectural Responsibility
`clio-retrieve` owns the arm and its rank contribution; storage backends provide the window query.

#### Required Changes
1. Implement the window retrieval on both backends.
2. Add the arm to the rank maps before fusion.
3. Ensure no raw score enters fusion.
4. Add integration tests for window membership and rank contribution.

#### Implementation Constraints
- No fusion weight changes without approval; if a weight is needed, request approval and update the appendix.
- No raw-score mixing.
- Keep files ≤450 lines; `hybrid.rs` is 416 and may need decomposition.

#### Expected Result
A temporal query returns window candidates ranked alongside the other arms; a non-temporal query is unchanged.

### Task 3: Exposure, Parity, and Determinism

#### Intent
Expose the arm consistently and prove determinism and no-op behavior.

#### Required Capability or Behavior
- The temporal arm's participation is observable (for example via `explain` if the shared projection admits it).
- MCP, in-process, and CLI accept the same parameters and produce the same results.
- Identical query and anchor produce identical windows and results.
- The no-window default is byte-for-byte unchanged.

#### Architectural Responsibility
`clio-retrieve` and the binding crates; the explain projection (Phase 100740) owns any trace addition.

#### Required Changes
1. Add parameters and validation across bindings.
2. Add determinism and no-op regression tests.
3. Add parity tests.

#### Implementation Constraints
- Do not leak query text or content into diagnostics beyond existing practice.
- Keep files ≤450 lines.

#### Expected Result
Same inputs and anchor give the same result; no temporal expression leaves behavior unchanged.

### Implementation Freedom
The agent may choose the supported expression set, the anchor parameter name/shape, the window-resolution rules, and the backend query shape, provided the anchor is explicit (no server-time default), rank-only fusion, budget compliance, and no-op defaults hold, and the absolute controls are unchanged.

---

## 6. Agent Execution Rules

### Allowed Actions
- Add the parser, the arm, backend window queries, parameters, tests, and documentation.
- Refactor locally, including decomposing `hybrid.rs`, to stay within 450 lines.

### Forbidden Actions
- Change fusion to mix raw scores, or change the absolute `as_of`/`time_axis`.
- Change dense/lexical/graph legs, rerank, admission, or storage semantics.
- Let an ambiguous expression guess a window.
- Exceed budgets or widen scope silently.
- Add dependencies without approval; delete tests; claim completion without evidence.

### Agent Decision Boundary
The agent may decide the expression set and window rules within the recorded decision. The agent must request approval for: a fusion weight change, a new dependency, changing the absolute controls, or a broader temporal feature (for example relative-date writes).

### Mandatory Stop Conditions
Stop and report if: the anchor cannot be threaded explicitly (a server-time default cannot be avoided in the request path); the arm cannot join without raw-score mixing; the absolute controls would have to change; the requirement's deterministic-policy rule cannot be met; or correctness cannot be verified.

---

## 7. Security Constraints

### Required Controls
- Bank isolation and read authorization unchanged.
- Parser input is bounded; malformed expressions fail closed.
- The arm cannot bypass scope or budget.
- No query text or content in diagnostics beyond existing practice.

### Sensitive Data Rules
- Never log query text or item content.
- Never commit secrets.

### Security Acceptance Conditions
- A malformed or ambiguous expression yields no window and no error leakage.
- The arm cannot return candidates outside the caller's bank/scope.

---

## 8. Test and Verification Strategy

### Required Tests
- [ ] Unit tests (supported/unsupported/ambiguous expressions; timezone boundaries; anchor handling)
- [ ] Integration tests (window membership on SQLite and Postgres; rank contribution)
- [ ] Contract tests (rank-only fusion; absolute controls unchanged; no-op default)
- [ ] End-to-end tests (real CLI/MCP temporal query)
- [ ] Regression tests (non-temporal query unchanged; existing suites)
- [ ] Security tests (malformed input; scope/budget containment)
- [ ] Failure-mode tests (unsupported expression; empty window; backend divergence)

### Required Test Scenarios

| Test ID | Scenario | Expected Result |
|---------|----------|-----------------|
| T100800-01 | "last week" with a fixed anchor | Deterministic window; window candidates ranked |
| T100800-02 | Same query and anchor twice | Identical window and results |
| T100800-03 | Unsupported phrase | No window; unchanged behavior |
| T100800-04 | Ambiguous/timezone-ambiguous phrase | Fail closed; no guessed window |
| T100800-04b | Relative expression with no anchor supplied | Arm does not run (or usage error); no server-time fallback |
| T100800-05 | Query with no temporal expression | Byte-for-byte unchanged default |
| T100800-06 | Absolute `as_of`/`time_axis` combined | Existing semantics preserved |
| T100800-07 | SQLite vs Postgres window | Same logical membership |
| T100800-08 | Budget/scope limits | Arm respects them; no silent widening |
| T100800-09 | MCP/in-process/CLI | Same parameters and results |
| T100800-10 | Workspace suite, coverage, clippy, fmt, size | Green; per-file ≥90%; files ≤450 lines |

### Negative Testing
Verify ambiguous expressions never guess, the arm never mixes raw scores, budgets are never exceeded, absolute controls are unchanged, and non-temporal queries are unchanged.

### Verification Rule
Implementation claims must be supported by actual test output, inspection results, or other concrete evidence.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-100800-01 | Relative expressions resolve deterministically against an explicit caller-supplied anchor; no server-time default | T100800-01, T100800-02, T100800-04b | Test output; design record |
| AC-100800-02 | Temporal arm fuses by rank; no raw-score mixing | T100800-01 | Test output; inspection |
| AC-100800-03 | No expression → no-op; absolute controls unchanged | T100800-05, T100800-06 | Regression test output |
| AC-100800-04 | Ambiguity fails closed; budgets and scope respected | T100800-04, T100800-08 | Test output |
| AC-100800-05 | Backend and binding parity | T100800-07, T100800-09 | Parity test output |
| AC-100800-06 | No regression; size/coverage gates pass | T100800-10 | Workspace suite; coverage report; size check |

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
- Anchor and expression-set decision record
- Fusion-weight decision (if any)
- Changed-component summary
- Test execution output
- Verification report
- Known limitations

---

## 10. Failure Handling and Recovery

### Expected Failure Modes

| Failure | Detection | Recovery |
|---------|-----------|----------|
| Nondeterministic window / hidden clock | Repeat-run test; no-anchor test | Thread the explicit anchor; reject a relative expression with no anchor |
| Raw score enters fusion | Fusion test | Remove it; the arm must rank by rank |
| Ambiguous phrase guessed | Fail-closed test | Reject the phrase |
| Budget exceeded | Budget test | Bound the arm; do not widen scope |
| Backend divergence | Parity test | Fix the window query on the offending backend |
| `hybrid.rs` exceeds 450 lines | Size check | Decompose before exceeding |

### Rollback Strategy
Disable the temporal arm; with no temporal expression it is already a no-op, so rollback is behavior-preserving for non-temporal queries. No data migration.

### Partial Completion Policy
If parsing works but the arm does not fuse by rank, or vice versa, do not claim completion. Record partial work and keep the tree green.

---

## 11. Traceability

| Parent Requirement | Implementation Task | Verification | Acceptance Criterion |
|--------------------|---------------------|--------------|-----------------------|
| §4.5 (adaptive retrieval arms; rank fusion) | Task 2 | T100800-01, T100800-02 | AC-100800-02 |
| §4.6 (bi-temporal semantics) | Task 2 | T100800-06 | AC-100800-03 |
| FR-24 (`as_of`/`time_axis`; explicit reads) | Task 2, Task 3 | T100800-06 | AC-100800-03 |
| §9 ranking-drift (deterministic policy) | Task 1 | T100800-02 | AC-100800-01 |
| FR-20 / §4.9.2 item 2 (binding identity) | Task 3 | T100800-09 | AC-100800-05 |
| Regression / quality contract | All | T100800-10 | AC-100800-06 |

Required chain:

```text
Requirement → Capability → Implementation → Test → Evidence
```

---

## 12. Phase Exit Contract

### Outputs Produced
- A deterministic relative temporal-expression parser with an explicit caller-supplied anchor and no server-time default.
- A rank-based temporal retrieval arm composed with the existing legs.

### Guarantees Provided to Downstream Phases
After this phase is accepted:
- Temporal queries retrieve within a resolved window without changing non-temporal behavior.
- The absolute `as_of`/`time_axis` controls still work as before.

### Known Limitations
- The supported relative-expression set is bounded; unsupported/ambiguous phrases fail closed.
- The arm requires an explicit caller-supplied anchor; without one, a relative expression does not run. Results for a relative phrase vary only with the anchor, never within a fixed anchor, so §9 determinism holds.
- No relative-date write semantics; this is a read-side arm only.
- No fusion weight was added unless approved; the arm participates at the existing default weight if none is configured.
- Effort and uncertainty are the highest in this phase set; it is arguably its own track.

### Downstream Prerequisites
- No later phase in this set depends on 100800.
- Any future temporal ranking enhancement must reference this anchor decision.

### Final Status
PASS | PASS WITH DOCUMENTED LIMITATIONS | BLOCKED | FAILED

### Verification Sign-Off
- Implementer: [TBD]
- Verifier: [TBD]
- Human Approver: [TBD, if required]
- Date: [TBD]

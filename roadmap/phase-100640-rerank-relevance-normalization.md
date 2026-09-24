# Phase 100640: Rerank Relevance Capture and Normalization

### Attribution
Rounds below record plan authorship; implementation sign-off is in §12.
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | [TBD] | proposed |
| Adversary | r1 | [TBD] | [TBD] |
| Remediator | r1 | [TBD] | [TBD] |
| Remedy Approver | r1 | [TBD] | [TBD] |
| Finalize | r1 | [TBD] | [TBD] |

**Capability phase 100640** · **Effort:** ~3–4 days · **Status:** Plan ready · **Parent:** gap analysis `gaps/recall-result-fidelity-gap-analysis.md` §3.3, §7, §8 decision 1, §10.2; requirement §4.5 item 3, FR-20 / §4.9.2 item 2, PR-4

### Vocabulary (read first) — zero shared moniker

| Term | Meaning in this phase | Must not be confused with |
|------|------------------------|----------------------------|
| **rerank relevance** | The cross-encoder score the provider produced for a candidate | The fused RRF `final`; a calibrated probability |
| **normalization** | A documented per-provider transform of the raw provider score into the exposed `reranker` value and range | Changing which candidate wins |
| **permutation** | The best-first order of document indices the reranker returns | The scores attached to those indices |
| **passthrough** | No reranker configured, so `scores.reranker` stays `null` | A rerank that ran and returned zero scores |

This phase captures a score that already arrives over the wire and is currently discarded. It does not change how the shortlist is reordered.

---

## 1. Objective

### Goal
Change the rerank seam so a reranker returns both an order and a score per candidate, parse the score that every supported provider response already carries, normalize it per provider into a documented range, and write it into the `scores.reranker` field added by Phase 100620. The fail-open policy is unchanged: a rerank error keeps the fused order and sets no score.

### Expected Outcome
- `Reranker::rerank` returns ordered `(index, score)` pairs instead of a bare index permutation.
- The TEI bare array, the `results[]` shape, and the `scores[]` shape all yield scores; none are discarded.
- `apply_rerank` writes the normalized `reranker` value onto the reordered hits' `scores` object.
- A documented per-provider normalization exists (TEI's default sigmoid score vs Cohere `relevance_score`), with the exposed range and the `null`-on-passthrough rule stated.
- The fail-open behavior is preserved: on any rerank error, order and scores are unchanged from the fused result.
- The TEI wire contract from Phase 100421 still passes its regression coverage.

### Parent Requirement
`requirement.md` — §4.5 item 3 (rerank stage); §4.9.2 item 2 / FR-20 (binding identity); PR-4 / §4.5 (`final` stays relative; the rerank value is display metadata). Gap source: `gaps/recall-result-fidelity-gap-analysis.md` §3.3, §8 decision 1.

### Design References (source-verified at plan time)
- `Reranker::rerank(...) -> Result<Vec<usize>, AmError>` returns a permutation only (`crates/clio-retrieve/src/rerank.rs:49-60`).
- `HttpReranker` (`rerank.rs:107-127`) and `CohereReranker` (`rerank.rs:188-212`) are the production adapters; test doubles are `ReverseReranker`/`FailReranker` (`crates/clio-retrieve/src/fixtures_tests.rs:218-243`).
- `parse_rerank_response` (`rerank.rs:296-354`) reads only `index`: bare array `301-304`, `results[]` `312-315`, and `scores[]` discards each f64 at `330`.
- `apply_rerank` (`crates/clio-retrieve/src/hybrid_rank.rs:84-127`) reorders `FusedHit` clones and never writes a score.
- Production attach is `crates/clio-mcp/src/runtime_open.rs:137-149`.
- **Provider score semantics (verified against TEI source).** TEI's `/rerank` request has `raw_scores` defaulting to `false`, and TEI applies sigmoid when `raw_scores` is false (`core/src/infer.rs`), so a request like Clio's that omits the field receives normalized scores in approximately `[0,1]`; raw logits appear only when `raw_scores=true`, which Clio does not send. Cohere `relevance_score` is also approximately `[0,1]`. The residual difference is calibration (TEI per-pair logistic vs Cohere's calibrated relevance), not range. This phase pins `raw_scores=false` explicitly in the request so behavior cannot drift with a server-default change. **Contract amendment:** Phase 100300 lists the `Reranker` trait signature and `parse_rerank_response` semantics under "Must Not Change". This phase deliberately amends **only** the trait's return shape and the parser's retention of scores; the full-permutation and fail-closed index guarantees remain. The amendment requires owner approval (see §3 and §6) and must be recorded in the completion evidence and the roadmap index, as Phase 100421 recorded its correction to Phase 100300.
- `crates/clio-retrieve/src/rerank.rs` is 358 lines; `hybrid_rank.rs` 127; `fixtures_tests.rs` is small.

---

## 2. Scope Boundaries

### In Scope
- Changing the `Reranker` trait/return shape to ordered `(index, score)` pairs.
- Parsing scores from the TEI bare array, `results[]`, and `scores[]`.
- A documented per-provider normalization and the exposed `reranker` range.
- Writing the normalized value into `scores.reranker` in `apply_rerank`.
- Updating adapters, test doubles, call sites, and tests.
- Preserving the Phase 100421 TEI contract regression coverage.

### Explicitly Out of Scope
- Score floors over `reranker` (Phase 100780).
- Changing the fail-open policy, the full-permutation guarantee, retry classification, or candidate-count policy.
- Provider adapters beyond TEI/Cohere.
- Changing the fusion weights or `final`.
- Making `reranker` authoritative or calibrated.
- Reranking in the live path (already wired by Phase 100350).

### Must Not Change
- Fail-open: a rerank error keeps the fused order and drops no candidate.
- The full-permutation guarantee: omitted documents append in original order; out-of-range or duplicate indices fail closed.
- The `results[]`/`scores[]`/bare-array compatibility semantics (now also reading scores).
- Retry classification substrings and the 401/403 body-suppression rule.
- Existing MCP tool names/schemas beyond the `scores.reranker` value.
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
- Phase 100620 accepted: the `scores` object and its `reranker: null` slot exist.
- Phase 100421 accepted: the TEI `{query,texts}` request and bare-array response are in place and covered.
- Owner approval for the `Reranker` trait return-shape change is obtained, and the Phase 100300 "Must Not Change" entry amendment is recorded (completion evidence + roadmap index).

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| `scores` object | Present on `ScoredHit` with `reranker: null` | Phase 100620 acceptance |
| `Reranker` trait | Permutation-only today | `rerank.rs:49-60` inspection |
| Adapters | TEI and Cohere implementations | `rerank.rs` inspection |
| Fail-open orchestrator | Keeps fused order on error | `hybrid_rank.rs:119-125` inspection |
| Provider score semantics | TEI sigmoid default (`raw_scores=false`) and Cohere `relevance_score` range | TEI `router/src/http/types.rs` + `core/src/infer.rs`; Cohere docs |
| Normalization decision | Chosen range and transform per provider | Gap analysis §8 decision 1; owner approval |

---

## 4. Existing-System Discovery

The agent MUST re-verify the following before editing; the facts below were confirmed at plan time.

### Required Discovery
- Confirm every call site of `Reranker::rerank` and `parse_rerank_response`, including the test doubles.
- Confirm exactly where each provider response carries a score and how it is currently discarded.
- Confirm the fail-open branch in `apply_rerank` and the warning it emits.
- Confirm the Phase 100421 regression tests that must keep passing.
- Confirm `rerank.rs` size against the 450-line limit.
- Re-verify the provider score semantics: TEI scales with sigmoid by default (`raw_scores=false`); Cohere `relevance_score` is approximately `[0,1]`. Record the residual calibration difference.

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
- The trait returns `Vec<usize>`; both adapters and the parser funnel through `parse_rerank_response`, which keeps only indices.
- `apply_rerank` reorders clones and has no score assignment.
- `FailReranker` and `ReverseReranker` are the only test doubles; both must adopt the new return shape.
- Phase 100421's bare-array parse and TEI request-capture tests are the contract regression to preserve.
- `rerank.rs` is 358 lines; the change must fit or decompose.

### Repository Adaptation Rule
The agent must determine concrete implementation locations from the actual repository. The plan does not prescribe file paths or module names unless they are an externally required contract. The provider wire shapes are external contracts and remain normative.

---

## 5. Implementation Specification

### Task 1: Carry Scores Through the Reranker Seam

#### Intent
Make the reranker return the score it already receives, so `apply_rerank` can expose it.

#### Required Capability or Behavior
- `Reranker::rerank` returns ordered `(index, score)` pairs (or an equivalent ordered structure) instead of `Vec<usize>`.
- Every adapter and test double implements the new shape.
- The full-permutation guarantee still holds; the score carried for an appended (omitted) document is defined and documented.
- Empty shortlists short-circuit without a request.

#### Architectural Responsibility
`clio-retrieve` owns the trait and the adapters.

#### Required Changes
1. Change the trait return type and update all implementors.
2. Update every call site to accept the pairs while preserving the order it uses today.
3. Define the score carried by documents a provider omitted.

#### Implementation Constraints
- Do not change the ordering the pairs impose.
- Do not add dependencies.
- Keep files ≤450 lines.

#### Expected Result
The orchestrator receives both order and score, and uses the order exactly as before.

### Task 2: Parse and Normalize Provider Scores

#### Intent
Read the score from each supported response shape and map it to the exposed `reranker` value.

#### Required Capability or Behavior
- The TEI bare array `[{"index","score"}, ...]` yields both index and score.
- The `results[]` and `scores[]` shapes yield both index and score.
- The TEI request pins `raw_scores=false`, so TEI returns its sigmoid score; the documented per-provider normalization maps the provider score into the exposed range and is deterministic for identical inputs.
- A malformed or missing score fails closed as before (never a fabricated value); a provider that returns no score (passthrough) leaves `scores.reranker` as `null`.
- The existing best-first order and the fail-closed index checks are unchanged.

#### Architectural Responsibility
`clio-retrieve` owns parsing and normalization; `clio-index` owns transport only.

#### Required Changes
1. Extend the parser to retain each score alongside its index for all three shapes.
2. Implement the per-provider normalization and document the range and the provider→exposed transform.
3. Keep out-of-range/duplicate index handling fail-closed and non-regressing.
4. Add unit tests for each shape and the transform boundaries.
5. Pin `raw_scores=false` in the TEI request body so the default cannot drift.
6. Build a provider-contract test harness with fake TEI and Cohere servers exercised through the real adapters, and write a short score-normalization spec (input range, transform, output range, `null` rules) that the tests assert.

#### Implementation Constraints
- Do not weaken fail-closed index validation.
- Do not invent a score when the provider omits one.
- No new egress; reuse the Phase 100280 transport.
- Keep the module docs accurate.

#### Expected Result
Every supported provider response yields a documented `reranker` value; an omitted score is `null`.

### Task 3: Write the Normalized Value and Preserve Fail-Open

#### Intent
Attach the normalized rerank value to the reordered hits without changing failure behavior.

#### Required Capability or Behavior
- On success, `apply_rerank` writes the normalized `reranker` value onto each reordered hit's `scores` object and keeps the existing order semantics.
- On any error, the fused order is kept, no `reranker` value is written, and the existing warning is emitted.
- `scores.final` remains the RRF value; the reranker value does not replace it.

#### Architectural Responsibility
`clio-retrieve::hybrid_rank` owns orchestration and the fail-open branch.

#### Required Changes
1. Assign the per-hit score when rerank succeeds.
2. Leave the error branch byte-for-byte behaviorally identical except that `reranker` stays `null`.
3. Add tests for success, passthrough, and failure.

#### Implementation Constraints
- Do not change the fail-open policy or the warning contract except to keep it accurate.
- Do not let the reranker value influence ordering beyond the provider's own order.

#### Expected Result
With a reranker configured, hits carry a normalized `reranker` value; without one, or on error, the value is `null` and order is unchanged from today.

### Implementation Freedom
The agent may choose the pair type, the normalization formula and exposed range (within the approved decision), helper placement, and test organization, provided the required behavior, boundaries, and contracts hold.

---

## 6. Agent Execution Rules

### Allowed Actions
- Change the `Reranker` trait return shape and the adapters/parser; update the orchestrator, test doubles, and tests.
- Refactor locally, including decomposing `rerank.rs` to stay within 450 lines.
- Research provider score semantics and document the normalization.

### Forbidden Actions
- Weaken fail-open, the full-permutation guarantee, or fail-closed index handling.
- Change retry classification or the 401/403 body suppression.
- Make the reranker value override `final` or the provider's own order.
- Add dependencies, delete tests, or claim completion without evidence.
- Expand into floors (100780) or provider adapters (100500).

### Agent Decision Boundary
The agent may decide the pair representation and internal normalization mechanics. The agent must obtain owner approval before changing the `Reranker` trait return shape (a breaking API change that amends Phase 100300's "Must Not Change" entry), and must request approval for: changing the fail-open policy, the full-permutation contract, a different exposed `reranker` range, or adding a dependency. The Phase 100300 amendment must be recorded in the completion evidence (§9) and the roadmap index.

### Mandatory Stop Conditions
Stop and report if: a provider's score cannot be normalized deterministically; the parser cannot retain scores without weakening fail-closed checks; the trait change cannot preserve ordering; or correctness cannot be verified.

---

## 7. Security Constraints

### Required Controls
- The rerank request continues to go only to the configured `rerank.url`; no new egress.
- Errors carry no key material, no response bodies for 401/403, and no document text.
- Bounded timeouts and the response size cap are preserved.
- The `reranker` value is numeric metadata and contains no content.

### Sensitive Data Rules
- Never log the key or full document text; log counts and timing only.
- Never commit secrets.

### Security Acceptance Conditions
- No key appears in any rerank error (test).
- 401/403 responses still omit the body (test).
- `scores.reranker` is numeric or `null` and contains no content.

---

## 8. Test and Verification Strategy

### Required Tests
- [ ] Unit tests (each response shape yields scores; normalization boundaries; omitted-score → `null`)
- [ ] Integration tests (mock TEI and mock Cohere through the real adapter; value reaches the hit)
- [ ] Contract tests (trait return shape; full permutation; fail-open; Phase 100421 TEI contract regression)
- [ ] End-to-end tests (real CLI/MCP `recall` with a configured reranker shows `scores.reranker`)
- [ ] Regression tests (existing TEI/Cohere tests; ordering unchanged on failure)
- [ ] Security tests (no key in errors; 401/403 suppression)
- [ ] Failure-mode tests (malformed body; duplicate/out-of-range index; dead sidecar keeps fused order and `null` reranker)

### Required Test Scenarios

| Test ID | Scenario | Expected Result |
|---------|----------|-----------------|
| T100640-01 | TEI bare array with scores | Order preserved; `scores.reranker` populated per documented transform |
| T100640-02 | `results[]` and `scores[]` bodies | Same index order as before; scores populated |
| T100640-03 | Provider omits a score | `scores.reranker` is `null`, never fabricated |
| T100640-04 | Normalization boundaries (TEI negative logit; Cohere 0 and 1) | Values within the documented range; deterministic |
| T100640-05 | Rerank error / dead sidecar | Fused order kept; `scores.reranker` `null`; warning emitted |
| T100640-06 | No reranker configured | `scores.reranker` `null`; behavior unchanged |
| T100640-07 | Duplicate/out-of-range index | Fail-closed; fused order kept |
| T100640-08 | Phase 100421 TEI request/parse regression | Still green |
| T100640-09 | Workspace suite, coverage, clippy, fmt, size | Green; per-file ≥90%; files ≤450 lines |

### Negative Testing
Verify malformed bodies fail closed, omitted scores never become fabricated values, the reranker value never overrides `final`, and existing TEI/Cohere behavior is intact.

### Verification Rule
Implementation claims must be supported by actual test output, inspection results, or other concrete evidence.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-100640-01 | Reranker seam carries scores; all implementors updated | T100640-01, T100640-02 | Test output; source inspection |
| AC-100640-02 | All supported response shapes yield scores; omitted score is `null` | T100640-02, T100640-03 | Parser tests |
| AC-100640-03 | Per-provider normalization is documented and deterministic | T100640-04 | Transform tests; module docs |
| AC-100640-04 | `scores.reranker` is written on success and `null` on passthrough/failure | T100640-05, T100640-06 | Payload test output |
| AC-100640-05 | Fail-open, full permutation, and fail-closed indices unchanged | T100640-05, T100640-07 | Contract tests |
| AC-100640-06 | Phase 100421 TEI contract regression intact | T100640-08 | Test output |
| AC-100640-07 | No regression; size/coverage gates pass | T100640-09 | Workspace suite; coverage report; size check |

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
- Implementation summary, including the recorded Phase 100300 trait correction
- Discovered/affected architectural components
- Changed-component summary
- Test execution output
- Provider normalization evidence (docs or observed values)
- Verification report
- Known limitations

---

## 10. Failure Handling and Recovery

### Expected Failure Modes

| Failure | Detection | Recovery |
|---------|-----------|----------|
| Trait change breaks a call site | Compile error / test | Update the call site; do not fork the trait |
| Missing score becomes `0` | Omitted-score test | Emit `null`; never fabricate |
| Normalization undefined for a provider | Transform tests | Stop; obtain the normalization decision before shipping |
| Fail-open weakened | Contract tests | Revert; keep the fused order on any error |
| TEI regression | Phase 100421 tests | Fix the change; do not relax the regression |

### Rollback Strategy
Revert the trait/parser/orchestrator changes. The prior behavior (rerank reorders; score discarded; fail-open on error) remains safe. No data migration is involved.

### Partial Completion Policy
If only some response shapes carry scores, do not claim completion. Record which shapes work and keep the tree green.

---

## 11. Traceability

| Parent Requirement | Implementation Task | Verification | Acceptance Criterion |
|--------------------|---------------------|--------------|-----------------------|
| §4.5 item 3 (rerank stage) | Task 1, Task 3 | T100640-01, T100640-04 | AC-100640-01, AC-100640-03 |
| FR-20 / §4.9.2 item 2 (binding identity) | Task 3 | T100640-04 | AC-100640-04 |
| PR-4 / §4.5 (relative score) | Task 2, Task 3 | T100640-06 | AC-100640-04 |
| Phase 100300 recorded trait contract (corrected) | Task 1 | Inspection + evidence | AC-100640-01 |
| Phase 100421 TEI contract regression | Task 2, Task 3 | T100640-08 | AC-100640-06 |
| Regression / quality contract | All | T100640-09 | AC-100640-07 |

Required chain:

```text
Requirement → Capability → Implementation → Test → Evidence
```

---

## 12. Phase Exit Contract

### Outputs Produced
- A reranker seam that returns order and score.
- Parsed and normalized provider scores for TEI and Cohere.
- A provider-contract test harness (fake TEI and Cohere servers exercised through the real adapters) and a written score-normalization spec.
- A populated `scores.reranker` on reranked hits, `null` otherwise.

### Guarantees Provided to Downstream Phases
After this phase is accepted:
- Phase 100660 can render the rerank stage value.
- Phase 100780 can add an optional `reranker` floor over the normalized value.
- Fail-open and ordering are unchanged; `final` remains the RRF value.

### Known Limitations
- The exposed `reranker` value is a normalized display/metadata signal, not a calibrated relevance.
- TEI default scores are sigmoid-normalized and Cohere `relevance_score` is approximately `[0,1]`; the exposed values are not cross-provider comparable because the two are calibrated differently, which the normalization spec documents.
- The trait change supersedes Phase 100300's frozen trait entry; the full-permutation and fail-open contracts remain.
- The value is not persisted.

### Downstream Prerequisites
- Phase 100660 may rely on `scores.reranker` being numeric when rerank ran and `null` otherwise.
- Phase 100780 may rely on a documented, deterministic normalization to define a floor.

### Final Status
PASS | PASS WITH DOCUMENTED LIMITATIONS | BLOCKED | FAILED

### Verification Sign-Off
- Implementer: [TBD]
- Verifier: [TBD]
- Human Approver: [TBD, if required]
- Date: [TBD]

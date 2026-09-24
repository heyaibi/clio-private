# Phase 100620: Retrieval Stage Scores (Dense + Lexical) and the `scores` Object

### Attribution
Rounds below record plan authorship; implementation sign-off is in §12.
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | [TBD] | proposed |
| Adversary | r1 | [TBD] | [TBD] |
| Remediator | r1 | [TBD] | [TBD] |
| Remedy Approver | r1 | [TBD] | [TBD] |
| Finalize | r1 | [TBD] | [TBD] |

**Capability phase 100620** · **Effort:** ~4–5 days · **Status:** Plan ready · **Parent:** gap analysis `gaps/recall-result-fidelity-gap-analysis.md` §3.1–3.4, §7, §10.2; requirement §4.5 item 3, FR-20 / §4.9.2 item 2, P12 / §4.12, §4.9.4.G

### Vocabulary (read first) — zero shared moniker

| Term | Meaning in this phase | Must not be confused with |
|------|------------------------|----------------------------|
| **per-stage score** | The raw score a single retrieval arm produced for a hit (dense cosine similarity, lexical score) | The fused `final` score, which is a rank-fusion value |
| **`scores` object** | A nested per-hit object `{final, reranker, semantic, keyword}` exposed alongside the existing top-level `score` | A replacement for the top-level `score`; a calibrated relevance |
| **`semantic`** | Cosine similarity `1 - distance`, clamped to the documented range | Raw cosine distance (`[0,2]`, possibly negative after transform) |
| **`keyword`** | The lexical arm's raw or normalized score | A cross-backend-comparable BM25 value; it is backend-dependent in this phase |
| **`final`** | The existing weighted RRF score, unchanged and still relative | A rerank relevance; a probability |

This phase surfaces computed stage signals. It does not change how any candidate is ranked.

---

## 1. Objective

### Goal
Thread the dense cosine distance and the lexical score that retrieval already computes out of the candidate-generation legs and onto the returned hit, and add a nested per-result `scores {final, reranker, semantic, keyword}` object on `ScoredHit`. `final` keeps the existing weighted RRF `score`; `reranker` is `null` until Phase 100640; `semantic` is `clamp(1 - distance, 0, 1)` (cosine similarity in `[0,1]`); `keyword` is the backend's raw lexical score, with the SQLite/Postgres sign/scale divergence documented and no cross-backend comparability claimed. The change is display/metadata only: nothing about ranking, ordering, or filtering changes.

### Expected Outcome
- `ScoredHit` carries a nested `scores` object with `final`, `reranker` (`null`), `semantic`, and `keyword`.
- The top-level `score` field is preserved unchanged for backward compatibility.
- `final` equals the pre-change fused `score` for identical inputs and configuration.
- Dense cosine distance is converted to `semantic = clamp(1 - distance, 0, 1)`, with `null` when the dense arm did not score the hit.
- The lexical `keyword` value is surfaced with the SQLite `-bm25` vs Postgres `ts_rank_cd` scale difference documented, and no cross-backend comparability is claimed.
- The per-stage signals are exposed identically on MCP, in-process, and CLI JSON reads (FR-20).
- `FusedHit.ranks` and the new per-list scores are consolidated into one structure so the code has one place for per-arm provenance.

### Parent Requirement
`requirement.md` — §4.5 item 3 (adaptive retrieval: dense + lexical + graph, then rerank); §4.9.2 item 2 / FR-20 (bindings expose identical names and semantics); §4.9.4.G (`explain` returns the score/domain/hop trace); P12 / §4.12 (diagnostic visibility); PR-4 / §4.5 (`final` stays relative, never presented as calibrated). Gap source: `gaps/recall-result-fidelity-gap-analysis.md` §3.1, §3.2, §3.4, §7.

### Design References (source-verified at plan time)
- `ScoredHit` is `crates/clio-retrieve/src/types.rs:117-140`: `#[serde(flatten)] hit: RetrieveHit` plus `score`, `dense_rank`, `lexical_rank`, `snapshot_ref`, `consolidated`, `source_ids`.
- `RetrieveHit` (`crates/clio-types/src/read.rs:118-145`) is the frozen fact/belief response contract. Per the gap analysis §10.1 and this phase's placement decision, `scores` goes on `ScoredHit`, **not** on `RetrieveHit`.
- Dense raw signal: `KnnHit { item_id, distance }` at `crates/clio-store/src/model.rs:292-297`; dropped at `crates/clio-retrieve/src/hybrid.rs:344` (`.map(|h| h.item_id)`); `dense_leg` returns `Vec<String>` at `hybrid.rs:318-350`.
- Lexical raw signal: `SearchHit { item_id, score }` at `model.rs:304-310`; dropped at `hybrid.rs:362`.
- Backend scales: SQLite returns `-bm25(items_fts)` (`crates/clio-store/src/sqlite_index.rs:142`); Postgres returns `ts_rank_cd` (`crates/clio-store/src/postgres_index.rs:141`); the divergence is documented at `postgres_index.rs:24-27`.
- Fusion consumes ranks, not raw scores (`crates/clio-retrieve/src/fusion.rs:21-28`); `FusedHit` is `{id, score, ranks}` (`fusion.rs:46-54`); `ranks` is written in `rrf_fuse` (`fusion.rs:74-75`).
- Dedup and finalize clone `FusedHit` fields verbatim and never mint scores (`crates/clio-retrieve/src/dedup.rs:201-340`; `crates/clio-retrieve/src/finalize.rs:83-113`), so a new field survives that path once added.
- Cross-binding propagation is automatic for the JSON payload: MCP serializes the whole outcome (`crates/clio-mcp/src/read_retrieve.rs:90`, `serde_json::to_value(&outcome)`), the in-process surface returns `ToolResult<RetrieveOutcome>` (`crates/clio-retrieve/src/surface.rs:207`), and the CLI dispatches through that surface (`crates/clio-lib/src/cli_read_core.rs:90-107`), so a new `ScoredHit` field reaches MCP/in-process/CLI JSON by serde. The hand-written projection is the `explain` trace only (`read_retrieve.rs:119-132`), de-drifted in Phase 100740; the CLI text renderer is Phase 100660.
- Size budget: `crates/clio-retrieve/src/hybrid.rs` is **416 lines** at plan time, near the 450-line cap; the change must stay within it or decompose.

---

## 2. Scope Boundaries

### In Scope
- Carrying the dense cosine distance and the lexical score from `dense_leg`/`lexical_leg` into the fused hit and the finalized `ScoredHit`.
- A nested `scores` object on `ScoredHit` with `final`, `reranker` (always `null` in this phase), `semantic`, and `keyword`.
- A documented dense distance→similarity transform with an explicit clamp for the negative part of the cosine-distance range.
- The backend's raw lexical score surfaced as-is, with the SQLite `-bm25` vs Postgres `ts_rank_cd` sign/scale divergence and the no-parity rule documented.
- Consolidating `FusedHit.ranks` and the new per-list scores into one structure.
- Updating all three bindings (MCP, in-process, CLI JSON) together, and the text renderer only where it must not break.

### Explicitly Out of Scope
- **Rerank relevance capture** — Phase 100640. This phase sets `reranker: null` unconditionally.
- **Score floors / `min_scores`** — Phase 100780.
- **Entity names or entity reasons** — Phases 100680/100700.
- **CLI text breakdown** — Phase 100660.
- **Temporal retrieval arm** — Phase 100800.
- Changing fusion weights, ranking order, candidate-count policy, or the `RetrieveHit` frozen contract.
- Backend parity normalization that would change which candidates pass a floor (no floors exist in this phase).
- Persisting scores to storage.

### Must Not Change
- The frozen `RetrieveHit` fact/belief field contract (`crates/clio-types/src/read.rs`).
- The top-level `score` field and its value; `final` MUST equal the pre-change `score`.
- Rank-fused ordering: raw per-leg scores MUST NOT enter fusion or influence order. `fusion.rs` states raw cross-leg scores "are never mixed; only ranks are".
- The fail-open rerank policy and the `Reranker` trait (Phase 100640 owns that).
- Existing MCP tool names and schemas beyond adding the `scores` object to read payloads.
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
- Phase 100421 accepted: the TEI rerank contract runs; this phase does not depend on it but builds on the same read path.
- The current retrieval pipeline is intact (`hybrid.rs` dense/lexical legs, `fusion.rs`, `finalize.rs`, `dedup.rs`).
- The three bindings expose `ScoredHit` today.
- Phases 100366 (CLI core plumbing and retrieval reads) and 100368 (history/graph reads) are complete; Phase 100366 owns the `clio recall` CLI command and the read path this phase extends (`command-ownership.md`).

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| `ScoredHit` | Present with the fields listed in §1 | `crates/clio-retrieve/src/types.rs` inspection |
| Dense leg | Returns item ids only; distance available before mapping | `hybrid.rs:318-350` inspection |
| Lexical leg | Returns item ids only; score available before mapping | `hybrid.rs` inspection |
| Fusion | Consumes ranks only | `fusion.rs:21-28` inspection |
| Bindings | MCP/in-process/CLI serialize the whole retrieve outcome (fields propagate by serde) | `read_retrieve.rs:90`, `surface.rs:207` inspection |
| CLI read path | `clio recall` owned by Phase 100366 (complete) | `command-ownership.md` |
| Placements decision | `scores` on `ScoredHit`, not `RetrieveHit` | Gap analysis §10.1; no conflict with Phase 100601 |

---

## 4. Existing-System Discovery

The agent MUST re-verify the following before editing; the facts below were confirmed at plan time.

### Required Discovery
- Confirm the exact dense and lexical leg signatures and where the raw value is currently discarded.
- Confirm how `FusedHit` flows through `rrf_fuse` → `apply_rerank` → `select_page` → `dedupe_candidates` → `finalize`, and where a new field must be carried.
- Confirm the three serialization sites and the existing conformance/volatile-mask tests.
- Confirm the `hybrid.rs` line count and whether the change fits under 450 lines.
- Confirm whether `FusedHit.ranks` is read anywhere outside tests (gap analysis §9.4 says it is not).

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
- The dense distance is available in `dense_leg` and discarded at `hybrid.rs:344`; the lexical score is discarded at `hybrid.rs:362`.
- `FusedHit` carries a `ranks` vector that is populated but unread outside `fusion_tests.rs`.
- `finalize` is the single place the final `ScoredHit` is built (`finalize.rs:100-112`); dedup clones fused fields without rewriting them.
- `score` is treated as volatile by the MCP conformance mask (`crates/clio-mcp/tests/mcp_read_conformance.rs:196-228`), so a new nested field must be considered for that mask.
- `docs/recall-scope-and-dedup.md:35` guarantees that a plain call keeps its pre-scope payload byte-for-byte except for the omitted dedup block; adding `scores` intentionally changes the plain-call payload and that documentation must be updated.
- `hybrid.rs` is 416 lines; `dedup.rs` 369, `finalize.rs` 146, `types.rs` 192.

### Repository Adaptation Rule
The agent must determine concrete implementation locations from the actual repository. The plan does not prescribe file paths, class names, or module names unless they are an externally required contract. The `scores` field names and their relative semantics are the externally required contract for this phase.

---

## 5. Implementation Specification

### Task 1: Thread Per-Stage Scores Through Candidate Generation and Fusion

#### Intent
Stop discarding the dense distance and the lexical score; carry them, keyed by item id, from the legs to the fused/finalized hit.

#### Required Capability or Behavior
- `dense_leg` and `lexical_leg` return the item id plus its raw dense/lexical value (or a parallel map keyed by item id), without changing candidate selection or order.
- `FusedHit` (or its consolidated replacement) carries the per-arm rank and the per-arm raw score for each hit.
- The fused `score` is computed exactly as before; no raw score enters `rrf_fuse`.
- The value survives `apply_rerank`, `select_page`, `dedupe_candidates`, and `finalize`.

#### Architectural Responsibility
`clio-retrieve` owns candidate generation, fusion, and hit construction. `clio-store`/`clio-index` already produce the raw values and are not changed to carry them past their boundary.

#### Required Changes
1. Change the dense and lexical legs to retain the raw value instead of mapping to `item_id` only.
2. Carry the per-arm score into the fused hit structure; keep `rrf_fuse` rank-only.
3. Preserve the value through dedup and finalize.
4. Keep the fused `score` byte-for-byte equal to the pre-change value for identical inputs and configuration.

#### Implementation Constraints
- Do not change fusion weights, ordering, or candidate counts.
- Do not store scores; they are response metadata only.
- Keep every touched file at or below 450 lines; `hybrid.rs` is at 416 and may need a small decomposition.
- No new dependency.

#### Expected Result
A finalized hit can report each arm's raw signal for that item id, with ranking unchanged.

### Task 2: Add the `scores` Object with a Documented Transform

#### Intent
Expose `scores {final, reranker, semantic, keyword}` on `ScoredHit` with defined meanings and ranges.

#### Required Capability or Behavior
- `scores.final` equals the existing top-level `score` (weighted RRF, relative).
- `scores.reranker` is `null` in this phase.
- `scores.semantic` is `clamp(1 - distance, 0.0, 1.0)` (cosine similarity in `[0,1]`); an absent dense value is `null`, not `0`, and no negative value is emitted.
- `scores.keyword` is the backend's raw lexical score (SQLite `-bm25`, Postgres `ts_rank_cd`); sign and scale may differ by backend, cross-backend comparability is NOT claimed, and an absent lexical value is `null`, not `0`.
- The top-level `score` is unchanged.
- The `scores` field appears identically in MCP, in-process, and CLI JSON.

#### Architectural Responsibility
`clio-retrieve` owns the score object and its documented semantics. The binding crates own faithful serialization; they must not reinterpret the values.

#### Required Changes
1. Add the `scores` struct/object and attach it during hit construction.
2. Implement and document the dense transform and the `null`-when-absent rule.
3. Document the lexical scale decision (per-backend) at the point of production or in module docs.
4. Confirm the new fields propagate through MCP, in-process, and CLI JSON by serde (they serialize `RetrieveOutcome` wholesale); update only the `explain` trace handling and any conformance volatile mask, and add/refresh binding parity assertions.
5. Update `docs/recall-scope-and-dedup.md` where it promises a byte-for-byte payload for plain calls, and any volatile-mask test that must tolerate the new field.

#### Implementation Constraints
- `final` MUST NOT be presented as calibrated; keep the "relative, not calibrated" wording.
- Do not add `scores` to the `explanation` trace in this phase; Phase 100740 de-drifts the trace. If the trace must carry it later, `scores` is PII-safe metadata and may.
- Do not place `scores` on the frozen `RetrieveHit`.
- Keep the `reranker` key present and `null` so the object shape is stable for Phase 100640.

#### Expected Result
Every returned hit carries a nested `scores` object whose `final` matches the old `score`, with `semantic`/`keyword` populated when the producing arm scored the hit and `null` otherwise.

### Task 3: Consolidate `FusedHit.ranks` with the Per-Stage Score Vector

#### Intent
Remove the two-parallel-fields smell: one structure holds per-arm rank and per-arm score provenance.

#### Required Capability or Behavior
- A single per-hit structure carries the per-arm rank vector and the per-arm raw score vector.
- Existing readers that only need ranks keep working; `ranks` semantics do not change.
- The consolidation does not alter ordering or fusion.

#### Architectural Responsibility
`clio-retrieve` owns `FusedHit`. This is an internal structure change, not a wire-contract change.

#### Required Changes
1. Introduce the consolidated structure and migrate `rrf_fuse`, dedup, finalize, and any tests.
2. Preserve the rank vector semantics exactly.
3. Remove or clearly deprecate the now-redundant `ranks` field.

#### Implementation Constraints
- No change to the computed ranks or the fused score.
- No public wire change beyond `scores`.
- Keep files ≤450 lines.

#### Expected Result
One structure describes per-arm provenance, used by both ranking and display.

### Implementation Freedom
The agent may choose whether legs return pairs or a side map, the concrete name and module of the consolidated per-arm structure, and where the transform helpers live, provided the required behavior, boundaries, and contracts hold and all acceptance criteria pass.

---

## 6. Agent Execution Rules

### Allowed Actions
- Inspect and modify `clio-retrieve`, the three binding crates' read projections, and their tests.
- Add the `scores` object, the transform helpers, the consolidated per-arm structure, and focused tests.
- Refactor locally, including a small `hybrid.rs` decomposition, to stay within the 450-line limit.

### Forbidden Actions
- Change the frozen `RetrieveHit` contract, the top-level `score`, fusion weights, ordering, or candidate counts.
- Put raw scores into fusion.
- Present `final` as calibrated or `keyword`/`semantic` as cross-backend comparable.
- Add dependencies, delete tests, or claim completion without evidence.
- Implement rerank score capture (Phase 100640), entity fields (100680), text breakdown (100660), or floors (100780).

### Agent Decision Boundary
The agent may decide leg return shapes, the consolidated structure's name/layout, transform helper placement, and test organization. The agent must request approval for: a different `scores` field set, a different dense transform range, changing the frozen contract, or adding a dependency.

### Mandatory Stop Conditions
Stop and report if: the raw values cannot be carried without changing fusion; `hybrid.rs` cannot fit under 450 lines without an unapproved structural change; the bindings cannot expose identical names/semantics; or correctness cannot be verified.

---

## 7. Security Constraints

### Required Controls
- Scores are PII-safe numeric metadata and fit the existing ids/ranks/scores trace category.
- No content, entity name, or query text may be added to any new field in this phase.
- Bank isolation and read authorization are unchanged.

### Sensitive Data Rules
- Never log decrypted content or query text alongside scores.
- Never commit secrets.
- Reuse existing serialization and masking; do not hand-roll a second mechanism.

### Security Acceptance Conditions
- A `scores` payload contains only `final`, `reranker`, `semantic`, `keyword` (numeric or null) and no content.
- Existing authorization/redaction tests remain green.

---

## 8. Test and Verification Strategy

### Required Tests
- [ ] Unit tests (dense transform including negative distance; lexical passthrough; null-when-absent; clamp boundaries)
- [ ] Integration tests (per-stage values survive fuse → dedup → finalize)
- [ ] Contract tests (top-level `score` unchanged; `final == score`; MCP/in-process/CLI JSON parity)
- [ ] End-to-end tests (real CLI/MCP `recall` row shows the `scores` object)
- [ ] Regression tests (ordering and ranks unchanged; existing suites green)
- [ ] Security tests (no content/query text in `scores`)
- [ ] Failure-mode tests (missing arm value → `null`, not `0`; empty recall unchanged)

### Required Test Scenarios

| Test ID | Scenario | Expected Result |
|---------|----------|-----------------|
| T100620-01 | Normal dense+lexical hit | `semantic` and `keyword` populated; `final == score` |
| T100620-02 | Cosine distance > 1 (negative similarity before clamp) | `semantic` clamped to the documented lower bound; no negative value |
| T100620-03 | Hit from only one arm | The absent arm's field is `null`, not `0` |
| T100620-04 | Reranker configured | `scores.reranker` is `null` (capture is Phase 100640); order uses fused order |
| T100620-05 | Identical inputs/config pre/post change | Fused `score` and ordering identical; `ranks` identical |
| T100620-06 | MCP, in-process, and CLI JSON for the same store | `scores` names and values identical |
| T100620-07 | Empty recall | Output unchanged |
| T100620-08 | Workspace suite, coverage, clippy, fmt, size | Green; per-file ≥90%; files ≤450 lines |

### Negative Testing
Verify that ordering never depends on a raw stage score, that a missing arm value cannot become a fake `0`, that the top-level `score` is untouched, and that no content leaks into `scores`.

### Verification Rule
Implementation claims must be supported by actual test output, inspection results, or other concrete evidence.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-100620-01 | Dense and lexical stage values are carried to the finalized hit | T100620-01, T100620-03 | Test output; source inspection |
| AC-100620-02 | `scores {final, reranker, semantic, keyword}` exists on `ScoredHit`; `reranker` is `null` | T100620-04 | JSON payload; test output |
| AC-100620-03 | `final` equals the pre-change top-level `score`; ordering unchanged | T100620-05 | Before/after test output |
| AC-100620-04 | Dense transform is `clamp(1 - distance, 0, 1)`; absent arm is `null` | T100620-02, T100620-03 | Transform unit tests; module docs |
| AC-100620-05 | Keyword scale/back-end divergence is documented, no parity claimed | Inspection | Module docs; test asserting documented values |
| AC-100620-06 | MCP, in-process, and CLI JSON expose identical `scores` | T100620-06 | Binding parity test output |
| AC-100620-07 | No regression; size/coverage gates pass | T100620-07, T100620-08 | Workspace suite; coverage report; size check |

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
- Discovered/affected architectural components
- Changed-component summary
- Test execution output
- API/schema evidence for the `scores` object
- Verification report
- Known limitations

---

## 10. Failure Handling and Recovery

### Expected Failure Modes

| Failure | Detection | Recovery |
|---------|-----------|----------|
| Raw score accidentally affects fusion | Ordering-diff regression test | Stop; remove the value from the fusion input |
| Clamp hides a real distance bug | Transform unit tests at boundaries | Re-derive the transform; document the chosen range |
| `null` vs `0` confusion | Missing-arm test | Emit `null`; never fabricate a score |
| Bindings diverge | Binding parity test | Fix the projection; do not ship partial |
| `hybrid.rs` exceeds 450 lines | Size check | Decompose before exceeding |

### Rollback Strategy
Remove the `scores` object and the carried per-stage values; the top-level `score` and ordering are untouched, so rollback is behavior-preserving. No data migration is involved.

### Partial Completion Policy
If the value is carried but the object is not exposed (or vice versa), do not claim completion. Record completed and incomplete tasks separately and keep the tree green.

---

## 11. Traceability

| Parent Requirement | Implementation Task | Verification | Acceptance Criterion |
|--------------------|---------------------|--------------|-----------------------|
| §4.5 item 3 (dense + lexical + rerank shape) | Task 1, Task 2 | T100620-01, T100620-05 | AC-100620-01, AC-100620-03 |
| FR-20 / §4.9.2 item 2 (binding identity) | Task 2 | T100620-06 | AC-100620-06 |
| §4.9.4.G (`explain` trace category) | Task 2 | Inspection | AC-100620-02 |
| P12 / §4.12 (diagnostic visibility) / PR-4 (relative score) | Task 2 | T100620-04, T100620-05 | AC-100620-02, AC-100620-03 |
| Gap §9.4 (`FusedHit.ranks` unread) | Task 3 | Inspection/tests | AC-100620-01 |
| Regression / quality contract | All | T100620-07, T100620-08 | AC-100620-07 |

Required chain:

```text
Requirement → Capability → Implementation → Test → Evidence
```

---

## 12. Phase Exit Contract

### Outputs Produced
- Per-stage dense and lexical values carried to the finalized hit.
- A nested `scores {final, reranker, semantic, keyword}` object on `ScoredHit`, identical across bindings.
- A consolidated per-arm rank/score structure replacing the parallel `FusedHit.ranks`.

### Guarantees Provided to Downstream Phases
After this phase is accepted:
- Phase 100640 can write a normalized `reranker` value into the existing `scores` object.
- Phase 100660 can render the per-stage breakdown without re-deriving values.
- Phase 100740 can derive the `explain` hit projection from one shared source.
- Phase 100780 can add optional floors over `semantic`/`keyword`/`reranker`/`final`.
- `final` and ordering are provably unchanged for identical inputs and configuration.

### Known Limitations
- `keyword` values are backend-dependent (SQLite `-bm25` vs Postgres `ts_rank_cd`); no cross-backend comparability is claimed.
- `scores.reranker` is always `null` until Phase 100640.
- `scores` is on `ScoredHit`, not on the frozen `RetrieveHit`.
- Scores are not persisted; they exist only in the response.

### Downstream Prerequisites
- Phase 100640 may rely on the `scores` object shape and the carried per-arm provenance.
- Phase 100660 may rely on `semantic`/`keyword` being present or `null`.
- If a later decision moves `scores` onto `RetrieveHit`, this phase must be re-sequenced after Phase 100601 (gap analysis §10.1).

### Final Status
PASS | PASS WITH DOCUMENTED LIMITATIONS | BLOCKED | FAILED

### Verification Sign-Off
- Implementer: [TBD]
- Verifier: [TBD]
- Human Approver: [TBD, if required]
- Date: [TBD]

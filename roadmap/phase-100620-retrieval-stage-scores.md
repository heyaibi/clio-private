# Phase 100620: Retrieval Stage Scores (Dense + Lexical) and the `scores` Object

### Attribution
Rounds below record plan authorship; implementation sign-off is in §12.
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | [TBD] | proposed |
| Developer | r1 | OpenCode CLI (OpenRouter . Deepseek V4.1 Flash Max) | done |
| Adversary | r1 | OpenCode CLI (Go . Space Bunny Free Max) | done |
| Remediator | r1 | [TBD] | [TBD] |
| Remediator | r1 | Command Code (DeepSeek V4 Flash (latest) Max) | done |
| Remedy Approver | r1 | [TBD] | [TBD] |
| Remedy Approver | r1 | OpenCode CLI (Go . Space Bunny Free Max) | approved |
| Finalize | r1 | [TBD] | [TBD] |
| Finalize | r1 | Command Code (DeepSeek V4 Flash (latest) Max) | done |

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
- `score` is treated as volatile by the MCP conformance mask (`crates/clio-mcp/tests/mcp_read_conformance.rs:196-228` at plan time; that mask now lives in `crates/clio-mcp/tests/mcp_read_transport_conformance.rs`), so a new nested field must be considered for that mask.
- `docs/recall-scope-and-dedup.md:35` guarantees that a plain call keeps its pre-scope payload byte-for-byte except for the omitted dedup block; adding `scores` intentionally changes the plain-call payload and that documentation must be updated.
- `hybrid.rs` is 416 lines; `dedup.rs` 369, `finalize.rs` 146, `types.rs` 192.

### Repository Adaptation Rule
The agent must determine concrete implementation locations from the actual repository. The plan does not prescribe file paths, class names, or module names unless they are an externally required contract. The `scores` field names and their relative semantics are the externally required contract for this phase.

### Discovery Output (implementation time, 2026-09-26)

- **Relevant subsystems identified:** `clio-retrieve` legs (`hybrid.rs`), fusion (`fusion.rs`, `hybrid_rank.rs`), dedup (`dedup.rs`), finalize (`finalize.rs`), DTOs (`types.rs`); `clio-store` hit shapes (`KnnHit`, `SearchHit`); `clio-index` search facades; MCP read binding (`clio-mcp/src/read_retrieve.rs`); CLI read path (`clio-lib/src/cli_read_core.rs`, `cli_read.rs`).
- **Existing implementation approach:** the dense leg mapped `KnnHit` to `item_id` and discarded `distance` (`hybrid.rs:344`); the lexical leg mapped `SearchHit` to `item_id` and discarded `score` (`hybrid.rs:362`). `rrf_fuse` consumed rank lists and computed `FusedHit.score` from ranks only. `finalize` was the single `ScoredHit` construction site. MCP and CLI serialize the whole `RetrieveOutcome` by serde.
- **Contracts/interfaces:** `RetrieveHit` (clio-types) is frozen and untouched. `ScoredHit` is the placement for `scores`. `FusedHit`/`RankList` are public in `clio-retrieve` but read outside tests nowhere. The MCP `explanation` trace is a hand-written projection and is intentionally unchanged in this phase.
- **Existing test coverage:** measured before the change with `git grep -c '#[test]' HEAD -- <paths>` (commit `9a0876c`): 150 `clio-retrieve` tests, 343 `clio-mcp` tests, and 63 `clio-lib` read tests (`crates/clio-lib/src/cli_read*_tests.rs`). After the change the same trees (counted with `git grep --untracked -c '#[test]'`) hold 162 `clio-retrieve`, 348 `clio-mcp`, and 65 `clio-lib` read tests, matching the suites that run them (`cargo test -p clio-retrieve --locked` 162 passed, `cargo test -p clio-mcp --locked` 348 passed, `cargo test -p clio --locked cli_read` 65 passed). The conformance volatile mask already treated `score` as non-deterministic.
- **Architectural constraints discovered:** `hybrid.rs` was 416 lines at plan time. Keeping `retrieve()` within clippy's 100-line function limit plus the 450-line file cap required a small decomposition: the leg fetch calls moved to a new `hybrid_legs.rs` module, and two small private helpers (`newly_expanded`, thin `dense_leg`/`lexical_leg` wrappers) kept `retrieve()` at 95 lines. `mcp_read_conformance.rs` was exactly 450 lines, so the mask edit had to stay net-zero lines (remediation r1 split that file; see AC-100620-07).
- **Assumptions confirmed:** the raw dense distance and lexical score are available before the id mapping; `FusedHit.ranks` is unread outside `fusion_tests.rs`; dedup and finalize clone fused fields verbatim, so a new field survives that path; all three bindings propagate a new `ScoredHit` field by serde.
- **Assumptions contradicted:** none material. Two plan-time expectations needed the anticipated small handling: `hybrid.rs` needed the leg decomposition, and the conformance volatile mask needed `"final"` added.
- **Questions requiring clarification:** none.

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
- [x] Unit tests (dense transform including negative distance; lexical passthrough; null-when-absent; clamp boundaries)
- [x] Integration tests (per-stage values survive fuse → dedup → finalize)
- [x] Contract tests (top-level `score` unchanged; `final == score`; MCP/in-process/CLI JSON parity)
- [x] End-to-end tests (real CLI/MCP `recall` row shows the `scores` object)
- [x] Regression tests (ordering and ranks unchanged; existing suites green)
- [x] Security tests (no content/query text in `scores`)
- [x] Failure-mode tests (missing arm value → `null`, not `0`; empty recall unchanged)

Evidence per test class is in §9 "Evidence (actual, 2026-09-26)".

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

#### Evidence (actual, 2026-09-26)

| AC ID | Result | Evidence |
|-------|--------|----------|
| AC-100620-01 | PASS | Dense and lexical stage values reach the finalized hit. `per_stage_scores_survive_fuse_dedup_and_finalize` (in `clio-retrieve/src/stage_score_tests.rs`) compares `scores.semantic` to `semantic_from_distance` of the real `dense_search` distance and `scores.keyword` to the real `lexical_search` score, through fuse → dedup → finalize. `absent_arm_scores_are_null_not_zero` covers single-arm hits. `cargo test -p clio-retrieve --locked` → 162 passed / 0 failed. |
| AC-100620-02 | PASS | `scores {final, reranker, semantic, keyword}` is on every hit and `reranker` is `null`. `scores_object_serializes_the_documented_shape`, `top_level_score_stays_equal_to_final_for_every_hit`, MCP `lexical_only_hits_report_null_semantic_and_numeric_keyword`, CLI `recall_json_scores_match_mcp_retrieve`; the MCP conformance matrix stays green. Real binary run: `./target/debug/clio --db <tmp> --backend sqlite --bank e2e recall "ECONNRESET" --output json` returned `"score":0.011823769943815867,"scores":{"final":0.011823769943815867,"keyword":1e-6,"reranker":null,"semantic":null}`. |
| AC-100620-03 | PASS | **Before/after test output (real binaries, same store).** A pre-change binary built from HEAD (`9a0876c`, target dir outside the repo at `~/adv-scratch/pre/target/debug/clio`) and the post-change `target/debug/clio` were both run against ONE freshly seeded SQLite store (4 items, item timestamps in the future so the recency term is exactly `1.0` and the fused score is bit-reproducible): `./clio --db <shared.db> --backend sqlite --bank cmpbank recall "deploy retry backoff fusion scoring" --output json --limit 10`. Result: `pre_scores == post_scores == [0.01182377049180328, 0.011609345351043642, 0.011448412698412699]` — byte-identical top-level `score`s, identical hit order, identical `dense_rank`/`lexical_rank`/`consolidated`/`dedup`; `pre_has_scores_object=false`; the new `scores` object is the only payload difference (`"final":0.01182377049180328,"keyword":2.4821624004032445,"reranker":null,"semantic":null`). Two more scenarios agree the same way: `"postgres bm25 ranking fusion"` → 2 hits, identical scores; `"quantum chromodynamics lattice"` → 0 hits. Harness and output kept in this run directory (`remediator-compare-pre-post.py`, `remediator-pre-post-compare.json`, `failures: []`, exit 0). The absolute values differ from the round-1 adversary's run only because a fresh store was seeded (the store-to-store `admission_score` variance reported as issue #29); inside one store the two binaries agree exactly. **Post-change tests:** `final == score` is asserted for every hit in unit, retriever, MCP, and CLI tests. Ordering is unchanged: `reranker_keeps_scores_and_existing_order_behavior` (reverse-reranker order equals the reverse of the plain run; per-id scores identical before/after rerank) and `identical_inputs_produce_identical_scores_and_ranks` (two runs with a frozen clock produce identical ids/scores/ranks). `raw_scores_are_recorded_per_list_and_never_change_the_fused_score` runs `rrf_fuse` with and without score lists and gets identical fused scores and order, proving raw values never enter fusion. |
| AC-100620-04 | PASS | `semantic_from_distance` unit test pins the transform at 0.0, 0.25, 1.0, 1.5, and 2.0 (clamped, never negative); the end-to-end `dense_distance_above_one_clamps_similarity_to_zero` uses an anti-parallel vector fixture, asserts the measured distance is > 1, and gets `semantic == 0.0`. Absent arm is `null` in `absent_arm_values_serialize_as_null_not_zero` and end to end. Module docs in `stage_score.rs` state `clamp(1 - distance, 0, 1)`. |
| AC-100620-05 | PASS | `stage_score.rs` module docs and the `keyword` field docs state the SQLite `-bm25(items_fts)` vs Postgres `ts_rank_cd` sign/scale divergence and that no cross-backend comparability is claimed. `keyword` is the store's value as-is: the end-to-end test compares it against `lexical_search`'s own `SearchHit.score`. |
| AC-100620-06 | PASS | MCP vs in-process parity: `mcp_payload_and_in_process_surface_expose_identical_scores` (same hit set, exact key set, exact `semantic`/`keyword`, `final == score` inside each payload). CLI vs MCP parity: `recall_json_scores_match_mcp_retrieve` (now `cli_read_scores_tests.rs`). Populated-arm parity (remediation r1, deterministic stub embedder): `dense_arm_populates_semantic_in_mcp_payload_with_parity` (MCP payload vs in-process surface, `semantic` numeric on both) and `recall_json_semantic_is_populated_with_live_embedder` (CLI `recall --output json` vs MCP `retrieve`, same `semantic` for the same item). Real Postgres payload: `postgres_retrieve_scores_observes_ts_rank_cd_keyword_end_to_end` observed `keyword=0.10000000149011612`, equal to the `clio_index::lexical_search` value, with `semantic`/`reranker` null and `final == score`. Transport parity kept green by masking the wall-clock-sensitive `scores.final` like `score` in `mask_volatile` (now `crates/clio-mcp/tests/mcp_read_transport_conformance.rs`; the same 10 read-conformance tests pass across the two split binaries). `cargo test -p clio-mcp --locked` → 348 passed / 0 failed. |
| AC-100620-07 | PASS | `cargo fmt --all --check` clean; `cargo clippy --workspace --all-targets --all-features --locked -- -D warnings` clean; `make check` (fmt + clippy + `cargo test --locked --workspace`) exit 0 — 36 test binaries plus 16 doc-test suites, 2445 tests passed, 0 failed; final `make coverage` exit 0 → `coverage-guard: 349 file(s) checked against 90.0% floors`, guard-printed `TOTAL lines 97.88% functions 98.70%`, `all reported files meet the per-file floor`. Per-file rows for the files this phase touched (remediation r1 run of the same JSON): `stage_score.rs` 100.00/100.00, `hybrid_legs.rs` 98.28/100.00, `fusion.rs` 100.00/100.00, `hybrid.rs` 99.23/100.00, `hybrid_rank.rs` 97.73/100.00, `hybrid_util.rs` 98.25/100.00, `finalize.rs` 97.87/100.00, `types.rs` 100.00/100.00, `dedup.rs` 99.02/100.00, `read_retrieve.rs` 98.88/100.00; zero files below 90% on either metric. Every touched Rust file ≤ 450 lines (largest: `read_scores_tests.rs` 430, `stage_score_tests.rs` 419, `cli_read_tests.rs` 398; remediation r1 split `mcp_read_conformance.rs` 450 → 177 into `mcp_read_transport_conformance.rs` 259 + `mcp_read_support/mod.rs` 114). |

### Definition of Done
- [x] All in-scope behavior is implemented.
- [x] All acceptance criteria pass.
- [x] Required tests pass.
- [x] No unauthorized changes were introduced.
- [x] Existing behavior remains intact.
- [x] Security checks pass.
- [x] Documentation is updated where required.
- [x] Evidence is collected.
- [x] Verification is completed.
- [x] Required approval is obtained (downstream pipeline step). (Remedy Approver r1 verdict REMEDY_APPROVED; findings F-01..F-07 resolved and independently reproduced.)

### Completion Evidence
- **Implementation summary:** the dense leg now returns each candidate's raw cosine distance and the lexical leg its raw backend score (`hybrid_legs.rs`, `StageHit`); `FusedHit` carries one `ArmSignal { rank, score }` per arm (`fusion.rs`), replacing the old `ranks: Vec<Option<usize>>` with a `ranks()` rank-only projection; only ranks enter the RRF sum. `finalize` attaches the nested `scores {final, reranker, semantic, keyword}` object to every `ScoredHit`: `final` mirrors the unchanged top-level `score`, `reranker` is always `null`, `semantic` is `clamp(1 - distance, 0, 1)` with `null` when the dense arm did not score the hit, and `keyword` is the backend's raw lexical score with `null` when the lexical arm did not score the hit. `RetrieveHit`, fusion weights, ordering, candidate counts, and the fail-open rerank policy are untouched.
- **Discovered/affected architectural components:** `clio-retrieve` (`hybrid`, `hybrid_legs`, `hybrid_rank`, `hybrid_util`, `fusion`, `finalize`, `types`, `stage_score`), `clio-mcp` read binding, `clio-lib` CLI read tests, `docs/recall-scope-and-dedup.md`. The `explanation` trace is deliberately unchanged (owned by a later phase).
- **Changed-component summary:** production — new `crates/clio-retrieve/src/stage_score.rs` (75 lines) and `hybrid_legs.rs` (110); modified `fusion.rs` (135), `hybrid.rs` (398), `hybrid_rank.rs` (142), `hybrid_util.rs` (97), `finalize.rs` (162), `types.rs` (196), `lib.rs` (127); `clio-mcp/src/read_retrieve.rs` (275) gained only the test-module registration. Tests — `stage_score_tests.rs` (419, new), `fusion_tests.rs` (256), `dedup_tests.rs` (415), `clio-mcp/src/read_scores_tests.rs` (430, new), `clio-mcp/tests/mcp_read_conformance.rs` (177), `clio-mcp/tests/mcp_read_transport_conformance.rs` (259, new), `clio-mcp/tests/mcp_read_support/mod.rs` (114, new), `clio-mcp/tests/mcp_read_scores_postgres_test.rs` (243, new), `clio-lib/src/cli_read_tests.rs` (398), `clio-lib/src/cli_read_scores_tests.rs` (258, new). Docs — `docs/recall-scope-and-dedup.md` byte-for-byte sentences corrected (`:31` and `:35`), and `docs/recall-scores.md` added as the operator note for the `scores` object and its `null` rules. Remediation r1 changed only headers, docs, and test files: no production behavior changed.
- **Test execution output:** `cargo test -p clio-retrieve --locked` → 162 passed / 0 failed; `cargo test -p clio-mcp --locked` → 348 passed / 0 failed; `cargo test -p clio --locked cli_read` → 65 passed / 0 failed; `make check` → exit 0, 2445 tests passed / 0 failed across 36 test binaries plus 16 doc-test suites; all suites also green under the final instrumented `make coverage` run.
- **API/schema evidence for the `scores` object:** per hit `"scores":{"final":<f64>,"reranker":null,"semantic":<f64|null>,"keyword":<f64|null>}`; the exact key set and the numbers-or-null property are pinned by tests in `clio-retrieve`, `clio-mcp`, and `clio-lib`. Real binary evidence quoted under AC-100620-02.
- **Verification report:** pre-change baseline (workspace JSON at `/tmp/cov-baseline.json`, guard-printed) TOTAL lines 97.87% / functions 98.70%, 347 files, guard green. Final `make coverage` (remediation r1 re-run) → 349 files, guard-printed TOTAL lines 97.88% / functions 98.70%, `all reported files meet the per-file floor` (zero files below 90% lines or functions). The raw percentages behind those guard lines are 48422/49472 = 97.8796% lines and 98.7010% functions. Per-file rows for every touched file are listed under AC-100620-07.
- **Verification limits:** three gaps remain. (1) The populated `semantic` in a binding payload is observed with a deterministic stub embedder — a local fake TEI double returning one fixed 384-dim unit vector — not with a real embedding model; the real-binary runs (no embedder configured) still show `semantic: null`, so the real-model scale of `semantic` is not exercised end to end. (2) `scores.reranker` is `null` everywhere by design (rerank relevance capture is not implemented), so no reranker-populated payload exists to check. (3) The Postgres `keyword` scale is observed through the live payload test `postgres_retrieve_scores_observes_ts_rank_cd_keyword_end_to_end`, but only for one query shape, and no cross-backend comparability is claimed or tested.
- **Known limitations:** see §12.

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
- **Missing:** a cross-backend-comparable lexical value. **Why:** SQLite surfaces `-bm25(items_fts)` and Postgres surfaces `ts_rank_cd`; their sign and scale differ, and no floor or threshold exists in this phase that would justify normalizing them. **Debt owner:** none assigned; no phase claims cross-backend `keyword` parity. A later phase that needs comparable lexical values must define the normalization explicitly.
- **Missing:** rerank relevance capture. **Why:** deliberately out of scope here; the `reranker` key stays present and `null` so the object shape is stable. **Debt owner:** Phase 100640.
- **Missing:** `scores` on the frozen `RetrieveHit`. **Why:** the placement decision keeps the fact/belief contract unchanged; `scores` live on `ScoredHit`. **Debt owner:** none; if a later decision moves them, this phase must be re-sequenced after Phase 100601 (gap analysis §10.1).
- **Missing:** `scores` in the `explanation` trace. **Why:** the trace is hand-projected and intentionally left unchanged to avoid de-drift conflicts. **Debt owner:** Phase 100740.
- **Missing:** persisted scores. **Why:** scores are response metadata only; no storage contract is defined. **Debt owner:** none assigned; persistence is out of scope.

### Downstream Prerequisites
- Phase 100640 may rely on the `scores` object shape and the carried per-arm provenance.
- Phase 100660 may rely on `semantic`/`keyword` being present or `null`.
- If a later decision moves `scores` onto `RetrieveHit`, this phase must be re-sequenced after Phase 100601 (gap analysis §10.1).

### Final Status
PASS WITH DOCUMENTED LIMITATIONS — Remedy Approver r1 approved (REMEDY_APPROVED) with all 7 findings resolved and independently reproduced; the three limits disclosed in §9 `Verification limits` stay open and are the reason for the qualifier.

### Verification Sign-Off
- Implementer: Developer r1 — OpenCode CLI (OpenRouter . Deepseek V4.1 Flash Max), 2026-09-26
- Verifier: [TBD]
- Human Approver: [TBD, if required]
- Date: 2026-09-26

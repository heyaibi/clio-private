# Phase 100120: Intent Gate, Hybrid Retrieve, and Compose

### Attribution
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | OpenCode CLI (Go . Deepseek V4.1 Flash High) | done |
| Adversary | r1 | OpenCode CLI (OpenRouter . Deepseek V4.1 Flash Max) | done |
| Remediator | r1 | OpenCode CLI (Together . GLM-5.3 Flash High) | done |
| Remedy Approver | r1 | OpenCode CLI (OpenRouter . Deepseek V4.1 Flash Max) | approved |
| Finalize | r1 | OpenCode CLI (Go . Deepseek V4.1 Flash High) | done |

**Index slice 100120 · **Effort:** `1.5×` · **Scope:** `roadmap/index.md` slice 100120 (authoritative)

## 1. Objective

### Goal
Combine the per-turn **intent gate** (skip unneeded search; **never** gate persona), **hybrid dense + lexical + optional graph** retrieval with reranking, and **`compose_context`** under fixed token budgets (P4, P1, §4.5, PR-1, PR-7, FR-6, FR-7, FR-24, FR-28, NFR-1, NFR-3). Honor domain filters and bi-temporal query args. **Storage size stays independent of injection size.**

### Expected Outcome
- `intent_gate(turn_text)` → `{retrieval_needed, domains[]}` within NFR-1 (p95 ≤ 50 ms for the gate itself).
- Automatic background retrieval skipped when gate says no; **explicit** `retrieve` / `triple_query` / history reads still run (FR-24).
- Persona / stable-preference channel is **always eligible for injection** and is never subject to the intent gate (§2.7 / FR-7)—even if full persona object lands in slice 100140, this phase must reserve the always-on channel and budget seam.
- `retrieve(...)` runs dense + lexical (+ optional bounded graph), fuses candidates, optional cross-encoder/sidecar rerank, returns hits with Phase 100100 epistemic_kind/belief fields.
- `compose_context(query?, domains?, budget_tokens)` returns the bounded pack the system would inject (persona channel + selected memories) without full-history replay (PR-1).
- Domain filters and `as_of` / `time_axis` honored on retrieve.
- Ranking weights come from Phase 100010 `ranking_env_*`.

### Parent Requirement
`requirement.md` (current) — P1, P4, PR-1, PR-7, §2.1, §2.7, §4.5, §4.9.4.B, FR-6, FR-7, FR-8 spirit, FR-24, FR-28, NFR-1, NFR-3, NFR-4; belief fields from Phase 100100; index legs from Phase 100110. Fusion/budget details: `roadmap/phase-100120-appendix-hybrid-fusion-and-budgets.md`.

### Design references (non-normative)
- Adaptive retrieval necessity (retrieve only when needed): [FLARE / active RAG](https://arxiv.org/html/2305.06983v2), [Adaptive-RAG](https://aclanthology.org/2024.naacl-long.389/), [UAR](https://arxiv.org/html/2406.12534v4), [TARG training-free gating](https://ar5iv.labs.arxiv.org/html/2511.09803). Prefer a **lightweight** gate (rules + small classifier / heuristics) to hit NFR-1—not a full LLM round-trip on the host.
- Hybrid pipeline: dense ∥ lexical → **RRF (rank fusion)** → optional cross-encoder rerank shortlist: [Hybrid search reference 2026](https://www.digitalapplied.com/blog/hybrid-search-bm25-vector-reranking-reference-2026), [RRF pipeline notes](https://codexpedite.dev/articles/hybrid-retrieval-pipeline-rrf-reranking).
- Requirement acceptance note: track false-negative skip rate more strictly than false-positive (§8 / retrieval-skip precision).

---

## 2. Scope Boundaries

### In Scope
- `intent_gate` diagnostic tool + automatic gate on the default retrieve-on-turn path.
- `retrieve` hybrid orchestration: domains, limit, as_of, time_axis, expand_graph?, budget_tokens?.
- Candidate generation via Phase 100110 dense + lexical primitives; optional bounded graph expansion using Phase 100080 triples / existing graph metadata (full co-activation weight updates are slice 100130—**read** existing edges if present; do not require Hebbian write loop for exit).
- Fusion via RRF (or documented equivalent rank fusion); optional rerank sidecar.
- Hit DTOs include Phase 100100 `epistemic_kind` / belief fields.
- `compose_context` with separate persona budget + memory budget; truncation by admission/ranking score.
- Consume `ranking_env_*` weights (dense, lexical, importance, temporal) and intent thresholds.
- Metrics: gate decision, retrieve latency breakdown, skip rate (PII-safe).

### Explicitly Out of Scope
- Full persona document CRUD (slice 100140)—compose MUST still implement the **channel + budget**; persona payload may be empty/stub until slice 100140 fills it.
- Co-activation saturating growth / hub distillation writes (slice 100130)—optional read of edges only.
- MCP transport binding (slices 100160–17)—in-process tools suffice.
- Task/failure history packaging (slice 100150) beyond domain filters that already exist.
- Training a heavy Self-RAG model on the host.

### Must Not Change
- Intent gate MUST NOT gate persona injection (§2.7).
- Explicit tools MUST run even when gate would skip (FR-24).
- PR-1: injection bounded; storage unbounded relative to injection.
- Phase 100110: index lag must not make id fetch fail; retrieve may return fewer vector hits while pending.
- Phase 100080/100100: as_of / epistemic_kind fields semantics.

### Scope Expansion Rule
If work outside this scope appears necessary:
1. Stop.
2. Document the reason.
3. Request clarification or approval.
4. Do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- Phase 100110 accepted: dense + lexical search primitives.
- Phase 100100 accepted: belief/fact fields on hits.
- Phase 100080 accepted: as_of / time_axis for temporal filtering where applicable.
- Phase 100010 accepted: `ranking_env_*`, injection budget config.
- Phase 100040 admission scores available for compose ranking/truncation.

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| Dense/lexical search | Primitives return candidates | Phase 100110 tests |
| Ranking env | Weights readable | Phase 100010 |
| Belief/fact DTO | Fields defined | Phase 100100 contract |
| Rerank sidecar (optional) | Health or disable flag | Config |
| Clock | Deterministic as_of tests | Injectable clock |

---

## 4. Existing-System Discovery

The agent MUST inspect the existing system before deciding
where or how to implement the changes.

### Required Discovery
- How “per-turn automatic retrieval” is invoked today (middleware vs tool-only).
- Existing `intent_gate` / `retrieve` / `compose_context` stubs from Phase 100010 catalog.
- Graph expansion hooks available without slice 100130 writes.
- Token counting approach already used (tiktoken-like vs char heuristic)—pick one and document.
- Rerank sidecar URL in compose profiles.

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

### Repository Adaptation Rule
The agent must determine the concrete implementation locations
from the actual repository. The plan does not prescribe file paths,
class names, module names, or directory structures unless they
are explicitly part of an externally required contract.

---

## 5. Implementation Specification

### Task 1: Intent Gate (FR-6 / NFR-1)

#### Intent
Skip expensive retrieval on self-contained turns without starving companions of persona.

#### Required Capability or Behavior
- `intent_gate(turn_text) -> {retrieval_needed: bool, domains: Domain[]}`.
- Gate p95 ≤ 50 ms (NFR-1); **no** embedding search or graph traversal inside the gate.
- Default automatic path: if `retrieval_needed=false`, skip background retrieve (no embed/graph latency beyond gate).
- Persona channel unaffected.
- Prefer high recall on “needs memory” (minimize false-negative skips); false positives only cost latency (requirement §8 note).
- Implementation MAY be heuristic + tiny model/sidecar; MUST NOT require host-local large LLM inference for Profile C.

#### Architectural Responsibility
Retrieval control-plane (before hybrid search).

#### Required Changes
1. Gate implementation + config thresholds in `ranking_env_*`.
2. Wire automatic skip path.
3. Latency tests / budget assertions in CI with deterministic stub.

#### Implementation Constraints
- Explicit `retrieve` ignores skip decision (still runs).
- Gate is inspectable via the tool (FR-28).
- Do not use gate to drop persona.

#### Expected Result
“hi” / “thanks” fixtures → skip; “what city did I say I live in?” → retrieve with domains including episodic/semantic as appropriate.

### Task 2: Hybrid Candidate Generation + Fusion

#### Intent
Implement §4.5 adaptive retrieval dense + lexical (+ optional graph) with sound fusion.

#### Required Capability or Behavior
- Parallel dense + lexical candidate lists (Phase 100110).
- Fuse with **weighted RRF** (default k=60; reduces to classic Cormack RRF when all weights are 1) or documented equivalent; **do not** naïvely average incompatible raw scores (appendix).
- Apply `ranking_env` weights as RRF list weights `w_i` (weighted extension—not claimed identical to the 2009 unweighted paper formula).
- Optional importance / temporal boosts using item metadata and `as_of`.
- Domain filter: `semantic` | `episodic` | `task` | `failure` | `temporal` | `persona`.
- `as_of` + `time_axis` filter candidates (FR-24 / NFR-4).
- `expand_graph?`: bounded hop expansion; if graph weights missing, no-op gracefully.

#### Architectural Responsibility
Retrieval orchestrator.

#### Required Changes
1. Orchestrator pipeline.
2. Fusion module with unit tests from appendix fixtures.
3. Domain + temporal filters.

#### Implementation Constraints
- Bank scoping everywhere.
- Missing vectors: fall back to lexical-only rather than failing hard when dense coverage incomplete.
- Co-activation **writes** deferred to slice 100130 (MAY no-op update hooks).

#### Expected Result
Hybrid beats dense-only and lexical-only on a small labeled fixture set (document metric).

### Task 3: Optional Rerank Stage

#### Intent
Second-stage precision on a shortlist without making rerank the first-stage retriever.

#### Required Capability or Behavior
- Take fused top-M (e.g. 50–100) → rerank sidecar → top-k.
- If rerank disabled/unavailable: return fused order; structured warning optional.
- Rerank via HTTP sidecar (Profile C), not host model load.
- Latency isolated in metrics.

#### Architectural Responsibility
Rerank client in retrieval pipeline.

#### Required Changes
1. Client + feature flag.
2. Tests with fake reranker (identity / reverse order).
3. Fail-open vs fail-closed policy documented (prefer fail-open to fused list).

#### Implementation Constraints
- Never rerank the entire corpus.
- Do not block compose forever on rerank timeout—budget a deadline.

#### Expected Result
With fake reverse reranker, hit order reverses; with sidecar down, fused results still return.

### Task 4: `retrieve` Tool Surface

#### Intent
Expose §4.9.4.B `retrieve` semantics end to end.

#### Required Capability or Behavior
- Parameters: `query, domains?, limit?, as_of?, time_axis?, expand_graph?, budget_tokens?`.
- Returns ordered hits with content refs + `epistemic_kind` (+ belief fields) + scores/ranks.
- Honors budgets when trimming returned pack.
- Runs even when intent gate would skip.
- Deterministic ordering for ties (NFR-5 spirit).

#### Architectural Responsibility
Public retrieve API (in-process).

#### Required Changes
1. Tool handler.
2. Contract tests including FR-24 explicit-call case after gate=skip.
3. Dual-backend sample parity on hit ids (ranks may differ).

#### Implementation Constraints
- Do not return gist-only as authoritative for exact value queries—include snapshot ref when available (PR-4).
- Do not inject unbounded results.

#### Expected Result
Contract fixtures for skip-override, domain filter, as_of filter, belief-field presence.

### Task 5: `compose_context` Budgets (PR-1 / FR-7 / FR-28)

#### Intent
Produce the bounded injection pack without full-log replay.

#### Required Capability or Behavior
- Always include persona channel section within **persona token budget** (NFR-3); empty stub OK until slice 100140.
- Fill remaining **memory budget** from retrieve (or internal retrieve) under `budget_tokens`.
- **`compose_context` is an explicit tool:** it MUST NOT inherit the automatic intent-gate skip. If a query/memory section is requested, compose MAY/MUST run retrieve semantics even when a prior `intent_gate` said `retrieval_needed=false` (FR-24 spirit). Gate skip only affects background/auto injection—not explicit compose/retrieve.
- Truncate by ranking/admission score; never silently grow past budget.
- Storage size of the bank MUST NOT force larger injection—cold history stays cold (PR-1).
- Return inspectable pack structure (sections, token estimates, truncated ids).

#### Architectural Responsibility
Context composer above retrieve + persona channel.

#### Required Changes
1. Token accounting helper.
2. Dual-budget packing algorithm (appendix).
3. Tests: oversize corpus still respects budget; persona present when gate skips memory; **compose after gate=skip still retrieves for memory section when query present**.

#### Implementation Constraints
- Automatic background path: gate skip ⇒ no auto memory inject; persona section still present.
- Explicit `compose_context` / `retrieve`: never blocked by gate skip.
- Do not auto-inject scratchpad or full MemTree.
- Secret masking in returned previews if any.

#### Expected Result
Compose on a huge bank still returns ≤ budget tokens; persona channel reserved; explicit compose ignores automatic skip.

### Implementation Freedom
The agent may choose the concrete implementation structure,
file locations, naming, and internal design provided that:
- The required behavior is satisfied.
- Architectural boundaries are respected.
- Existing contracts are preserved.
- All acceptance criteria pass.
- No prohibited changes are introduced.
- Rust sources stay ≤450 lines per file.

---

## 6. Agent Execution Rules

### Allowed Actions
- Inspect and modify the repository as required to implement
  the in-scope capabilities.
- Add or update implementation components where appropriate.
- Add or update tests required to verify the behavior.
- Refactor locally when necessary to implement the specified
  capability without changing unrelated behavior.

### Forbidden Actions
- Change public contracts without approval.
- Delete or bypass tests.
- Disable security controls.
- Introduce unrelated features.
- Perform unrelated broad refactoring.
- Upgrade dependencies without approval.
- Commit secrets.
- Claim completion without evidence.
- Gate persona behind intent_gate.
- Skip explicit `retrieve` because the gate said no.
- Average BM25/`ts_rank` with cosine as if on one scale without rank fusion.

### Agent Decision Boundary
The agent may decide:
- Gate heuristic/model details (within NFR-1).
- RRF k and shortlist sizes (document defaults).
- Token estimator.
- Whether compose calls retrieve internally or accepts precomputed hits.
- Test organization.

The agent must request approval for:
- Architecture changes beyond the stated scope.
- Breaking API or data-contract changes.
- Requiring host-local LLM for every gate decision in Profile C.
- Security-sensitive policy decisions.
- Destructive data operations.
- Making co-activation writes mandatory before slice 100130.

### Mandatory Stop Conditions
Stop and report if:
- Requirements are ambiguous.
- Repository facts contradict the plan.
- Required dependencies are missing.
- Scope expansion is required.
- Gate cannot meet NFR-1 without unapproved infra.
- Existing architecture cannot separate persona channel from gated search.
- Correctness cannot be verified.

---

## 7. Security Constraints

### Required Controls
- Bank-scoped retrieve/compose.
- Domain filters cannot be used to escalate across banks.
- Rerank/embed sidecars authenticated; secrets masked.

### Sensitive Data Rules
- Never log full compose packs at info when they may contain secrets—ids + scores OK.
- Never commit secrets.
- Mask credentials in gate/retrieve debug traces.

### Security Acceptance Conditions
- Cross-bank retrieve fails closed.
- Compose budget cannot be bypassed by large stored history alone.

---

## 8. Test and Verification Strategy

### Required Tests
- [x] Unit tests
- [x] Integration tests
- [x] Contract tests
- [x] End-to-end tests
- [x] Regression tests
- [x] Security tests
- [x] Failure-mode tests

### Required Test Scenarios

| Test ID | Scenario | Expected Result |
|---------|----------|-----------------|
| T100120-01 | Gate on greeting | `retrieval_needed=false`; no dense/lexical calls on auto path |
| T100120-02 | Gate on memory-needed turn | `retrieval_needed=true` with non-empty domains |
| T100120-03 | Gate latency budget | p95 ≤ 50 ms in test harness (stub OK) |
| T100120-04 | Explicit retrieve after gate=skip | Retrieve still returns (FR-24) |
| T100120-05 | Persona channel with gate=skip (auto path) | Auto inject skips memory; persona section still present |
| T-05b | `compose_context` after gate=skip with query | Memory section may still retrieve (explicit tool; FR-24) |
| T100120-06 | Hybrid vs dense-only fixture | Hybrid includes lexical-only exact id hit |
| T100120-07 | RRF fusion fixture | Appendix expected order |
| T100120-08 | Rerank sidecar down | Fused results returned (fail-open) |
| T100120-09 | `as_of` + `time_axis` | Hits respect bi-temporal filter |
| T100120-10 | Belief/fact fields on hits | Phase 100100 contract present |
| T100120-11 | Compose oversize bank | Token estimate ≤ budget |
| T100120-12 | Domain filter | Only requested domains returned |
| T100120-13 | Bank isolation | No cross-bank hits |
| T100120-14 | ranking_env weight change | Order/scores change deterministically |

### Negative Testing
Verify that:
- Invalid domains/time_axis rejected.
- Unauthorized bank blocked.
- Partial dense coverage does not hard-fail retrieve.
- Duplicate retrieve is safe.
- Existing write paths intact.
- Failure does not inject unbounded context.

### Verification Rule
Implementation claims must be supported by actual test output,
inspection results, or other concrete evidence.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence | Result (real) |
|-------|----------------------|---------------------|-------------------|---------------|
| AC-100120-01 | FR-6 intent gate + NFR-1 | T100120-01–T100120-03 | Tests + latency note | PASS — `intent_tests::{t01_gate_on_greeting_skips, t01_gate_on_acknowledgement_skips, t02_gate_on_memory_needed_turn_retrieves_with_domains, t03_gate_latency_budget}`; gate is pure (normalize + substring checks, no embed/graph); t03 asserts p95 ≤ 50 ms over 2000 samples. Honesty note: t03 is a latency SMOKE check, not a meaningful NFR-1 bound — the gate does no I/O, so 50 ms is trivially met; the structural NFR-1 guarantee is that `intent_gate` is a pure `&str` function holding no embedder/store/graph handles, so no I/O cost can enter the gate path |
| AC-100120-02 | FR-24 explicit retrieve vs gate | T100120-04 | Test output | PASS — `hybrid_tests::t04_explicit_retrieve_runs_after_gate_skip` (gate says skip; explicit retrieve still returns the hit) |
| AC-100120-03 | FR-7 persona never gated; compose explicit vs auto | T100120-05, T-05b | Test output | PASS — `compose_tests::t05_auto_path_skips_memory_but_keeps_persona`, `compose_tests::t05b_explicit_compose_after_gate_skip_still_retrieves`, `surface_tests::compose_tool_auto_path_honors_skip` |
| AC-100120-04 | Hybrid dense+lexical(+graph opt) | T100120-06, T100120-07, T100120-12 | Test output | PASS — `hybrid_tests::t06_hybrid_includes_lexical_only_exact_hit`, `fusion_tests::t07_appendix_fixture_order`, `hybrid_tests::t12_domain_filter_returns_only_requested_domains`; graph expansion wiring covered by `hybrid_tests::graph_expansion_adds_seed_neighbors_when_enabled` |
| AC-100120-05 | Rerank optional fail-open | T100120-08 | Test output | PASS — `hybrid_tests::t08_reverse_reranker_reverses_fused_order`, `t08_rerank_failure_keeps_fused_order`, `t08_rerank_sidecar_down_keeps_fused_order`; `rerank_tests` cover response parsing and transport failures |
| AC-100120-06 | Bi-temporal retrieve args | T100120-09 | Test output | PASS — `hybrid_tests::t09_as_of_and_time_axis_filter_candidates` (valid + transaction axes) |
| AC-100120-07 | Belief/fact on hits | T100120-10 | Contract fixtures | PASS — `surface_tests::belief_and_fact_fields_serialize_per_contract` (belief carries `source_type`/`confidence`/`requires_confidence_check`; fact omits them) |
| AC-100120-08 | PR-1 / compose budgets | T100120-11 | Test output | PASS — `compose_tests::{t11_oversize_bank_respects_budget, total_tokens_never_exceeds_budget_across_sizes, budget_underflow_is_rejected}` |
| AC-100120-09 | ranking_env integration | T100120-14 | Test output | PASS — `hybrid_tests::t14_weight_change_changes_order_deterministically`, `fusion_tests::weight_change_changes_scores_deterministically` |
| AC-100120-10 | Bank isolation | T100120-13 | Test output | PASS — `hybrid_tests::t13_bank_isolation_returns_no_cross_bank_hits`; empty bank fails closed via `validate_rejects_bad_requests` |
| AC-100120-11 | Dual-backend hit-id parity | Opt-in parity test | Test output | PASS — `pg_parity_tests::postgres_and_sqlite_hit_id_parity` (run with `DATABASE_URL` + `AM_PG_RETRIEVE_PARITY=1`; 1 passed) |

### Definition of Done
- [x] All in-scope behavior is implemented.
- [x] All acceptance criteria pass.
- [x] Required tests pass.
- [x] No unauthorized changes were introduced.
- [x] Existing behavior remains intact.
- [x] Security checks pass.
- [x] Documentation is updated where required.
- [x] Evidence is collected.
- [ ] Verification is completed. (developer self-verification and the Adversary r1 review are done; Remediator/Remedy Approver verification is still pending — see Verification Sign-Off and Attribution)
- [ ] Required approval is obtained. (pending Remedy Approver and Human Approver)

### Completion Evidence
- Implementation summary: new crate `clio-retrieve` (modules `intent.rs` gate + `GateMetrics`; `hybrid.rs` orchestrator; `fusion.rs` weighted RRF; `rerank.rs` optional HTTP sidecar client; `filter.rs` domain/temporal/recency; `finalize.rs` bounded result mapping; `compose.rs` dual-budget packer + persona seam; `surface.rs` in-process JSON tool handlers; `types.rs` DTOs; `token.rs` estimator). `clio-index` re-exports `post_json`/`HttpEndpoint` so the rerank client reuses the existing std-only sidecar transport; `clio-lib` re-exports `clio_retrieve as retrieve`. In-process tools only (MCP binding remains later work).
- Gate algorithm + false-negative monitoring note: pure CPU heuristic — normalize (lowercase, strip punctuation, collapse whitespace) → memory-cue domain scan → phatic/acknowledgement check → recall-question check. Only short phatic turns with no memory cue are skipped, and only when heuristic confidence ≥ `ranking_env.intent_gate.skip_confidence` (default 0.5). Everything else retrieves (prefer false positive over wrong answer). False-negative monitoring: `GateMetrics` keeps PII-safe `evaluated`/`skipped` counters (no turn text); `intent_tests::gate_metrics_track_skips` asserts them. Labeled FN/FP evaluation (requirement §8): `evaluate_gate(labeled_turns, thresholds)` counts false negatives (needed memory, gate skipped) and false positives (unneeded, gate retrieved) SEPARATELY, with the stricter documented FN bound `DEFAULT_FALSE_NEGATIVE_BOUND = 0.05` (< any FP tolerance, because FN produces a wrong answer while FP only costs latency); `intent_tests::gate_evaluation_tracks_fn_and_fp_separately` asserts FN=0 with a nonzero FP on the labeled fixture. A deployment-scale offline evaluation corpus remains future work (Known Limitations).
- Hybrid-vs-baseline quality metric (Task 2 Expected Result): labeled two-query fixture in `hybrid_quality_tests::hybrid_recall_beats_single_leg_baselines_on_labeled_fixture`. Metric: recall@1 averaged over the labeled queries. Fixture: one lexical-only-reachable relevant item (no vector), one dense-only-reachable relevant item (no lexical doc), one vector-only distractor. Result: hybrid 1.0 vs dense-only 0.5 and lexical-only 0.5 — hybrid strictly beats each single-leg baseline because each leg alone misses exactly the relevant item only the other leg can reach.
- Retrieve budget policy (Task 4): `budget_tokens` trims trailing hits once the running `estimate_tokens` total would exceed it; the FIRST hit is always admitted even when it alone exceeds the budget — an empty result is never preferred over a relevant hit, so the budget is a soft floor for a single oversized hit, not a hard cap. Injection safety is unaffected: compose re-truncates each hit's composed text in `pack_memory`. Tested by `finalize_tests::budget_tokens_trims_returned_hits` (cap holds for normal hits) and `finalize_tests::budget_tokens_always_returns_first_hit_even_over_budget` (documents the deliberate policy and its budget consequence).
- Token-accounting note: retrieve budgets trim on the hit's lexical source text (`clio_index::lexical_text` = gist + snapshot tokens) while compose budgets trim on the composed pack text (gist, else snapshot ref, else item id). Both use the same `estimate_tokens` estimator and both stay bounded; the two budgeted representations are deliberately different (retrieve measures source size, compose measures injection size), so `RetrieveOutcome.estimated_tokens` does not describe the composed pack.
- Tool schema note: the in-process `retrieve`/`compose_context` argument structs carry `bank`, which the published §4.9.4.B caller signatures deliberately omit — `bank` is the session/transport-scoped isolation key injected by the binding layer, not a caller argument. Slices 100160–17 (MCP binding) must supply it from the session; the convention is documented on `surface.rs::RetrieveArgs::bank` / `ComposeArgs::bank`.
- Fusion parameters: weighted RRF `RRF_w(d) = Σ_i w_i / (k + rank_i(d))`, `k = DEFAULT_RRF_K = 60` (reduces to classic Cormack RRF when all weights are 1). `ranking_env.retrieval.dense/lexical` are normalized to sum 1 as list weights; `importance`/`temporal` apply a multiplicative boost `1 + w_imp·importance + w_temporal·recency` (raw scores are never averaged across legs). Deterministic tie-break: score desc, importance desc, id asc. Leg fetch = 60 (`DEFAULT_LEG_FETCH`), rerank shortlist M = 60 (`DEFAULT_SHORTLIST_M`), graph-expansion decay = 0.5 (`DEFAULT_GRAPH_DECAY`). Appendix T100120-07 note: the prose fixture table labels A/B a tie, but with `lexical=[B,D,A]` A is lexical rank 3, so the formula yields B > A > D > C; the test asserts the formula-derived order and records this.
- Rerank parameters + policy: `HttpReranker` posts `{query, documents, top_k}` to `{url}/rerank` with a 2 s deadline (`DEFAULT_RERANK_TIMEOUT`); accepts `results[].index` or `scores[]`; fail-open — any transport/parse error keeps the fused order and emits a structured warning.
- Token estimator: `estimate_tokens` = `ceil(Unicode scalar values / 4)`, documented ±25% on English prose; used consistently by retrieve budget trimming and compose packing.
- Persona vs memory budget numbers used in tests: default persona target 400 tokens (`DEFAULT_PERSONA_BUDGET_TOKENS`), pack overhead 8 tokens (`PACK_OVERHEAD_TOKENS`), default total budget 2048 (`DEFAULT_BUDGET_TOKENS`); `memory_budget = budget − overhead − persona_tokens`.
- Explicit retrieve **and** `compose_context` ignore automatic gate skip: `retrieve` never consults the gate; `Composer::compose(req, gate=None)` (explicit) always retrieves when a query is present, while `gate=Some(skip)` is the automatic path and omits only the memory section (persona section always emitted).
- Test execution output: `cargo test --workspace --locked` → 490 passed, 0 failed across 22 suites (clio-retrieve: 81 unit/integration tests; count refreshed by Remediator r1 after remediation fixes — the earlier 486/487 lines predate the final test additions). `cargo clippy --workspace --all-targets --all-features --locked -- -D warnings` clean; `cargo fmt --all` clean.
- Dual-backend sample: `pg_parity_tests::postgres_and_sqlite_hit_id_parity` — same lexical hit ids from SQLite and Postgres for a seeded bank; run opt-in with `DATABASE_URL=… AM_PG_RETRIEVE_PARITY=1 cargo test -p clio-retrieve postgres_and_sqlite_hit_id_parity` → 1 passed. The parity test is opt-in so it never contends with the serialized Postgres suites.
- Verification report (refreshed by Remediator r1): `make coverage` exit 0 → aggregate 98.50% lines / 98.80% functions; every reported Rust file ≥90% on both gated metrics (104 file rows scanned; clio-retrieve: compose 100/100, filter 100/100, finalize 100/96.97, fusion 100/100, hybrid 100/98.47, intent 95.00/95.95, rerank 100/100, surface 100/98.68, token 100/100, types 100/100). All new/modified Rust files ≤450 lines (largest: `hybrid.rs` 450, `hybrid_tests.rs` 449).
- Known limitations: persona payload is a caller-supplied stub until the persona subsystem fills the reserved channel; `expand_graph` uses a `GraphExpander` seam whose default is a no-op because association-edge listing lives with the co-activation subsystem; gate quality needs offline evaluation beyond unit fixtures; Postgres parity is opt-in rather than part of the default suite.

---

## 10. Failure Handling and Recovery

### Expected Failure Modes

| Failure | Detection | Recovery |
|---------|-----------|----------|
| Gate error | Exception | Fail **open** to retrieve (prefer extra latency over silent skip)—document |
| Dense empty | Coverage | Lexical-only path |
| Rerank timeout | Deadline | Return fused list |
| Budget underflow | Validation | Reject compose params |

### Rollback Strategy
Revert code; retrieval is read-only aside from optional slice-13 co-activation writes (disabled here). Safe rollback.

### Partial Completion Policy
If only part of the phase is complete:
- Do not claim full completion.
- Record completed and incomplete work separately.
- Document remaining work.
- Do not leave undocumented broken state.

---

## 11. Traceability

| Parent Requirement | Implementation Task | Verification | Acceptance Criterion |
|--------------------|---------------------|--------------|-----------------------|
| FR-6 / NFR-1 / PR-7 | Task 1 | T100120-01–T100120-03 | AC-100120-01 |
| FR-24 | Task 4 | T100120-04 | AC-100120-02 |
| FR-7 / §2.7 | Task 5 | T100120-05 | AC-100120-03 |
| §4.5 hybrid | Tasks 2–3 | T100120-06–T100120-08, T100120-12 | AC-100120-04, AC-100120-05 |
| FR-24 / NFR-4 as_of | Task 2, 4 | T100120-09 | AC-100120-06 |
| FR-14 surface | Task 4 | T100120-10 | AC-100120-07 |
| PR-1 / FR-28 compose | Task 5 | T100120-11 | AC-100120-08 |
| FR-32 ranking_env | Tasks 1–2 | T100120-14 | AC-100120-09 |
| Bank isolation | Task 4 | T100120-13 | AC-100120-10 |
| §4.9.4.B dual-backend parity (Phase 100110 contract) | Task 4 | Opt-in parity test | AC-100120-11 |

Required chain:

```text
Requirement → Capability → Implementation → Test → Evidence
```

Every acceptance criterion must be traceable.

---

## 12. Phase Exit Contract

### Outputs Produced
- Intent gate tool + automatic skip path.
- Hybrid `retrieve` with fusion and optional rerank.
- `compose_context` with dual budgets and persona channel seam.
- Metrics for gate/retrieve/compose.

### Guarantees Provided to Downstream Phases
After this phase is accepted:
- Slice 100130 can attach co-activation updates on retrieve result sets.
- Slice 100140 can fill the persona channel without redesigning compose budgets.
- Slices 100160–17 can bind the same tool semantics over MCP.

### Known Limitations
- Persona content may be stubbed until slice 100140.
- Co-activation weight writes may be no-op until slice 100130.
- Gate quality will need offline evaluation beyond unit fixtures.

### Downstream Prerequisites
- Slice 100130 MUST update association weights on co-retrieved sets without changing fusion correctness tests.
- Slice 100140 MUST inject into the reserved persona budget, not invent a second ungated megachannel.
- Ops slices may tune `ranking_env_*` without code changes.

### Final Status
PASS WITH DOCUMENTED LIMITATIONS

### Verification Sign-Off
- Implementer: Developer r1 — OpenCode CLI (Go . Deepseek V4.1 Flash High)
- Verifier: Adversary r1 — OpenCode CLI (OpenRouter . Deepseek V4.1 Flash Max) — findings report delivered; remediation round r1 in progress (Remedy Approver still pending)
- Human Approver: [pending]
- Date: 2026-09-18

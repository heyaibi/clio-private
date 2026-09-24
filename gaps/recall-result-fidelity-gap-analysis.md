# Gap analysis: recall result fidelity — per-stage scores, entity links, and related read-surface gaps

Status: draft gap analysis for discussion. **Not** a proposal, **not** an implementation plan; no phases, no day estimates.

- Date: 2026-09-25.
- Scope: the signals Clio computes during retrieval that consumers cannot currently see (per-stage scores, entity links, related metadata), the CLI read-output plumbing around them, and adjacent read-surface gaps found while mapping the area.
- This is a capability-area analysis. It is **not** bounded to a single ticket; the ticket that prompted it has been closed without implementation.
- Evidence basis: source reading at the current `master` working tree, public repo docs, the private requirement (`baseline/requirement.md`), and the Hindsight 0.10 recall API docs fetched 2026-09-25.
- Related prior work: the TEI rerank contract fix (`abcd0019`) makes rerank actually run, so its score is now producible — but still discarded.

---

## 1. Purpose and reference model

Clio's retrieval pipeline computes several per-stage signals, then throws most of them away, so a caller sees one opaque `score`. This analysis maps what is computed, what is exposed, and what stands between the two.

Clio's pipeline: dense (KNN) + lexical (BM25/`ts_rank_cd`) candidate generation, optional bounded graph expansion, weighted Reciprocal Rank Fusion, optional cross-encoder rerank, then dedup and page selection (`crates/clio-retrieve/src/hybrid.rs:179-282`).

Hindsight 0.10 is used as a reference for the *shape* of a richer result, not as a binding target:

- Each `results[]` entry carries `scores.final` (the value ranked by; relative, not calibrated), `scores.reranker` (normalized `0`–`1`, `null` on passthrough), `scores.semantic` (cosine similarity `0`–`1`), and `scores.keyword` (BM25, `>= 0`, unbounded), plus `entities[]` (canonical name strings).
- Hindsight also exposes `min_scores` floors, four retrieval arms (semantic, keyword, graph, temporal), a top-level `entities` dict, an `include.entities` toggle, and a `trace` object.

Clio runs three of those four arms (no temporal/relative-date arm); the extra surfaces are noted in §9.

---

## 2. Current retrieval result contract

- A returned hit is `ScoredHit` (`crates/clio-retrieve/src/types.rs:117-140`): flattened `RetrieveHit` + `score` (weighted RRF, possibly boosted/reranked) + `dense_rank` + `lexical_rank` + `snapshot_ref` + `consolidated` + `source_ids`.
- `RetrieveHit` (`crates/clio-types/src/read.rs:119-145`) is documented as the **frozen retrieval response field contract** (`read.rs:1-20`). It carries `item_id`, `bank_id`, `kind`, `category`, `episodic_type`, `epistemic_kind`, `source_type`, `confidence`, `gist`, `requires_confidence_check`.
- Fusion preserves only a per-list **rank** vector on `FusedHit` (`id`, `score`, `ranks`), and the raw per-list scores are dropped before fusion ever sees them (`crates/clio-retrieve/src/fusion.rs:46-54`).
- Dedup and finalize clone `FusedHit` fields verbatim and never mint scores (`crates/clio-retrieve/src/dedup.rs:201-340`; `crates/clio-retrieve/src/finalize.rs:83-113`), so new per-stage fields would survive that path once added.

---

## 3. Per-stage signals: current state and gaps

### 3.1 Dense (semantic) raw score — Partial

- Produced as cosine **distance**: `KnnHit { item_id, distance }` at `crates/clio-store/src/model.rs:292-297`; facade `dense_search` at `crates/clio-index/src/search.rs:55-67`; drivers `crates/clio-store/src/sqlite_knn.rs:12-58` and `crates/clio-store/src/postgres_index.rs:179-235`; cosine metric set in `crates/clio-store/src/vector_ddl.rs:106-111`.
- Dropped at `crates/clio-retrieve/src/hybrid.rs:344` (`.map(|h| h.item_id)`); `dense_leg` returns `Vec<String>` (lines 318-350).
- No distance→similarity conversion or clamp exists. A `semantic` field would need `1 - distance` plus an explicit range decision: cosine distance is `[0, 2]`, so the raw result can be negative.

### 3.2 Lexical (keyword) raw score — Partial

- Produced as `SearchHit { item_id, score }` (`crates/clio-store/src/model.rs:299-310`); facade `crates/clio-index/src/search.rs:73-85`.
- SQLite returns `-bm25(items_fts)` (`crates/clio-store/src/sqlite_index.rs:142`); Postgres returns `ts_rank_cd` (`crates/clio-store/src/postgres_index.rs:141`). The two backends are **not on the same scale** (documented at `postgres_index.rs:24-27`).
- Dropped at `crates/clio-retrieve/src/hybrid.rs:362`.
- Fusion deliberately consumes ranks, not raw scores (`fusion.rs:21-28`), so a displayed `keyword` value is backend-dependent unless normalized per backend.

### 3.3 Rerank normalized score — Partial

- The trait cannot carry it: `Reranker::rerank(...) -> Result<Vec<usize>, AmError>` returns a permutation only (`crates/clio-retrieve/src/rerank.rs:48-60`).
- The parser reads scores then drops them: TEI bare array reads only `index` (`rerank.rs:299-308`); `results[]` reads only `index` (`rerank.rs:309-319`); `scores[]` reads each f64 then discards it at `rerank.rs:330`.
- `apply_rerank` reorders `FusedHit` clones and never writes a score (`crates/clio-retrieve/src/hybrid_rank.rs:84-127`).
- Implementors: `HttpReranker` (`rerank.rs:107-127`), `CohereReranker` (`rerank.rs:188-212`), test doubles (`crates/clio-retrieve/src/fixtures_tests.rs:218-243`). Production attach: `crates/clio-mcp/src/runtime_open.rs:137-149`.
- **Scale conflict:** TEI emits raw logits (unbounded, possibly negative); Cohere `relevance_score` is roughly `[0,1]`. A `reranker` field needs a documented per-provider normalization decision.

### 3.4 Per-result score object — Missing

- There is no nested `scores` object; `ScoredHit` has one flat `score`.
- The `explain` trace is a **separate hand-written projection** of `{item_id, score, dense_rank, lexical_rank, consolidated, source_ids}` (`crates/clio-mcp/src/read_retrieve.rs:118-150`), so any added field risks trace drift (§9).
- Cross-binding identity is mandatory (§4.9.2 item 2 / FR-20): MCP (`read_retrieve.rs:89-94`), in-process (`crates/clio-retrieve/src/surface.rs:166-179`), and CLI (`crates/clio-lib/src/cli_read_core.rs:90-107`; `cli_read.rs:341-346`) must change together.
- Tests that may need updating: MCP conformance volatile mask treats `score`/`metrics` as volatile (`crates/clio-mcp/tests/mcp_read_conformance.rs:196-228`); the dedup block omits itself so a plain call keeps its pre-scope payload byte-for-byte (`docs/recall-scope-and-dedup.md:35`); CLI text fixtures (`crates/clio-lib/src/cli_read_tests.rs:127-154`).

---

## 4. Entity links and entity matching

### 4.1 Entity data — Partial / Conflict

- There is **no named-entity table, index, link, or matching** anywhere. `entity_id`/`entity_kind` in `sql/001_core.sql:640-666` are sync-row ids, not named entities. The `triples` table has no `item_id` index (`sql/001_core.sql:252-276`).
- The only named-entity-like value is the extractive `snapshot` field `entity`: default fields are `entity` (required string), `amount`, `date` (`crates/clio-write/src/schema.rs:59-65`), verified as a contiguous NFC source substring (`crates/clio-write/src/verify_entity.rs:28`; FR-4 / §4.4).
- `snapshot` is arbitrary JSON (`crates/clio-types/src/item.rs:266`) and is **not universally present**:
  - default-field writes with a snapshot carry `entity`;
  - triple carriers store `{subject, predicate, object}` (`crates/clio-write/src/triple.rs:189-193`), no `entity`;
  - hub-distill, beliefs, snapshot-less items, and non-default field lists carry no `entity`.
- The decrypted snapshot **is** in hand where hits are built: `finalize` iterates the fetched `MemoryItem` (`crates/clio-retrieve/src/finalize.rs:95-112`), loaded at `crates/clio-retrieve/src/hybrid.rs:382-415`. So exposing snapshot `entity` is a read-side change, not new storage.
- SPO triples have `subject`/`object` (`crates/clio-types/src/triple.rs:128,132`), but there is **no by-item triple query** (`crates/clio-store/src/store.rs:272,278,397`; `triple_map.rs:95-141` filters only SPO and intervals) and no `item_id` index.
- `entities` in export means the bundle's payload arrays (`crates/clio-compliance/src/bundle.rs:131-163`), unrelated to named entities.

### 4.2 Entity overlap and reason — Missing

- No entity matching, overlap, or boost exists in `crates/clio-retrieve`.
- Text match reasons cover only retrieval provenance: `recall_reason` maps `dense_rank`/`lexical_rank` to `semantic + lexical` / `semantic` / `lexical` (`crates/clio-lib/src/cli_read_render.rs:78-85`).
- Any entity reason is **derived**, not the span-verified snapshot value (PR-4): it must be labelled derived and must not be presented as a verified fact.

---

## 5. CLI read-output plumbing

### 5.1 Text breakdown — Missing

- `render_recall` prints one `score {score:.4}` and the disclaimer "score is relative (rank fusion), not calibrated relevance" (`crates/clio-lib/src/cli_read_render.rs:50-67`). No per-stage breakdown, no entity reason.

### 5.2 `-o` alias for `--output` — Missing

- The parser rejects every single-dash token except `-h` (`crates/clio-lib/src/cli_args.rs:118-128`); `output` is a long-only global value flag (`cli_args.rs:30`).
- `explicit_output` recognizes only `--output` / `--output=` (`crates/clio-lib/src/cli_output.rs:89-105`).
- `split_leading_globals` only strips `--` prefixed globals (`cli_args.rs:170-205`).
- No short-flag/alias infrastructure exists (only `-h` and top-level `-V`).
- Tests: `crates/clio-lib/src/cli_args_tests.rs:83-87`; `crates/clio-lib/src/cli_output_tests.rs:52-93`.

### 5.3 Output-mode help — Missing

- The help body is `COMMAND_CATALOG` (`crates/clio-lib/src/main.rs:187-317`); the global-flags line is `main.rs:314`. No output-mode explanation.
- The rule is implemented in `resolve_output` / `stdout_is_tty` (`crates/clio-lib/src/cli_output.rs:41-64`): explicit `--output` wins, otherwise text on a TTY and JSON when piped.
- Per-verb usage lines end in `[--output json|text]` (`crates/clio-lib/src/cli_help_usage.rs:24-273`, ~70 entries).

---

## 6. Normative constraints

None forbids richer result fields; these fence how they may be shaped.

- **Ranking is rank-fused; scores are relative.** §4.5 item 3 fixes the dense + lexical + graph + rerank shape; `fusion.rs` states raw cross-leg scores "are never mixed; only ranks are". §9's ranking-drift risk requires deterministic policy for identical inputs/config. Per-stage scores must be display/metadata; `final` must stay the RRF value and must never be presented as calibrated. An entity **ranking** leg would have to fuse by rank.
- **Frozen read contract.** `RetrieveHit` is the frozen fact/belief response contract (FR-14 / PR-8). FR-14 / §4.11 require retrieving `epistemic_kind` (+ belief `source_type`/confidence); that is a floor, so adding fields is allowed if existing fields are preserved.
- **Cross-binding identity.** §4.9.2 item 2 / FR-20: all bindings expose identical names and semantics; MCP, in-process, and CLI move together.
- **Explain trace.** §4.9.4.G requires `explain` to return the score/domain/hop trace; the code documents that trace as "ids, ranks, scores, counts, timings only" (`crates/clio-mcp/src/read_retrieve.rs:113`).
- **PII/content boundary.** `scores` are PII-safe and fit the existing ids/ranks/scores trace. `entities[]` are **content-derived names**, not PII-safe metadata: they must not enter `warnings`, the `explanation` trace, telemetry, or health surfaces (§4.9.5.C, §4.12). Persisted entity names would be content under the subject DEK (§7.4 item 1), not plaintext graph metadata.
- **Entity authority.** FR-4 / §4.4 make snapshot entities span-verified; a retrieval-side entity link is inferred and must remain non-authoritative (PR-4).

---

## 7. Gap summary matrix

| Area | Capability | State | Core blocker |
|---|---|---|---|
| Scores | Dense cosine similarity | Partial | Dropped at `hybrid.rs:344`; needs distance→similarity + clamp |
| Scores | Lexical BM25 | Partial | Dropped at `hybrid.rs:362`; backend scales differ |
| Scores | Rerank normalized relevance | Partial | Trait returns permutation only; scores dropped; normalization undefined |
| Scores | Per-result `scores` object | Missing | New field + cross-binding + frozen-contract decision |
| Entities | `entities[]` per hit | Partial / Conflict | No entity store; snapshot `entity` partial; content boundary |
| Entities | Entity-overlap reason | Missing | No matching step; derived labelling; display vs ranking |
| CLI | Scores breakdown in text view | Missing | Depends on scores + entity reason |
| CLI | `-o` alias | Missing | No short-flag support |
| CLI | Output-mode help | Missing | Wording/placement; optional per-verb updates |
| Adjacent | `context`/`source_ref` on hits | Missing | Separate native-source-context track (§9) |
| Adjacent | Temporal (relative-date) arm | Missing | No query-time temporal parsing; `as_of` is absolute only |
| Adjacent | Keyword score parity across backends | Conflict | SQLite `-bm25` vs Postgres `ts_rank_cd` scales |
| Adjacent | `explain` projection drift | Risk | Trace is hand-written, separate from `ScoredHit` |
| Adjacent | Snapshot leaf verification | Conflict | Docs claim unlisted leaves rejected; code checks only declared fields |
| Adjacent | `FusedHit.ranks` | Partial | Populated but unread outside tests |

---

## 8. Decisions required

1. **Rerank score normalization.** TEI raw logits vs Cohere `[0,1]`. Options: per-provider normalization, a shortlist-relative transform, or report raw and drop the parity expectation. Affects the wire meaning of `reranker`.
2. **Score object placement and back-compat.** Keep top-level `score` (as `final`) and add nested `scores`, or replace it? Place fields on frozen `RetrieveHit` or only `ScoredHit`? Does `explain` also carry `scores`?
3. **Entity source and coverage.** Snapshot `entity` only; plus SPO triples (needs by-item query + index); or a new entity index/NER subsystem. Which hit kinds may return empty `entities[]`? What canonicalization?
4. **Entity-overlap semantics.** Display-only reason or ranking leg? Match rule (exact/case-insensitive substring of the query)? Must be deterministic and marked derived.
5. **Entity-in-trace boundary.** Confirm `entities[]` stays out of `explanation`, telemetry, health surfaces, and `warnings`.
6. **`-o` scope.** Global only or per-verb; allowed before the verb; whether to update all ~70 usage strings.

---

## 9. Adjacent observations and related gaps

These go beyond signal surfacing. They were found while mapping the same read path and matter to any effort that touches it.

### 9.1 `RetrieveHit` does not expose the required source `context`

FR-34 / FR-35 require `retrieve` (and other reads) to surface the optional bounded `context` as metadata, and `evidence_ref` as stable source identity. `RetrieveHit` (`crates/clio-types/src/read.rs:119-145`) has neither, and `MemoryItem` (`crates/clio-types/src/item.rs:242-281`) has no `context` field either. This is a separate, already-planned track: `private/clio-private/roadmap/phase-100601-native-source-context.md` and `phase-100606-context-lifecycle-portability.md`. Any change to the hit contract should coordinate with it rather than add a second, conflicting hit shape.

### 9.2 `explain` is a hand-written projection that can drift

`retrieve_explanation` rebuilds a hit list field by field (`crates/clio-mcp/src/read_retrieve.rs:118-150`) instead of deriving it from `ScoredHit`. Every new hit field must be added in two places, and nothing enforces they agree. A single shared projection (or serializing `ScoredHit` with a volatile-field mask) would remove the drift class.

### 9.3 The keyword score is not comparable across backends

SQLite returns `-bm25` and Postgres returns `ts_rank_cd` (`sqlite_index.rs:142`; `postgres_index.rs:141`), and the code documents they are different scales. This already matters for `min_scores`-style floors and for any displayed `keyword` value; it is a parity issue, not just a display one.

### 9.4 `FusedHit.ranks` is populated but unread outside tests

`ranks` is written in `rrf_fuse` (`fusion.rs:74-75`) and used only in `fusion_tests.rs`. It is the natural neighbour of a per-stage score vector; consolidating ranks and scores into one structure would avoid two parallel, partially used fields.

### 9.5 Hindsight exposes surfaces Clio does not

Not requested anywhere yet, but relevant to "match and beat" the reference: `min_scores` floors over `semantic`/`keyword`/`reranker`/`final`; a top-level `entities` dict keyed by canonical name; an `include.entities` toggle; and a full `trace` object (query embedding, per-arm results, fusion candidates, timings). Clio already has `explain` and metrics, so these are extensions rather than new subsystems — except the four-arm retrieval model itself.

### 9.6 No temporal (relative-date) retrieval arm

Hindsight parses relative temporal expressions from the query and anchors them to a query timestamp. Clio's only temporal control is the absolute `as_of` / `time_axis` pair (`crates/clio-retrieve/src/types.rs:76-79`). This is a larger capability gap that a `scores`/temporal-display feature might imply but does not include.

### 9.7 Snapshot leaf verification: docs and code disagree

`docs/extraction-fidelity.md` states that an undeclared non-empty snapshot leaf fails verification. Production `verify_snapshot` iterates only the **declared** `fields` and never inspects unlisted leaves (`crates/clio-write/src/verify.rs:92-115`). This was found by reading, not reproduced with a live run; it is recorded as an observation, not a confirmed bug. It matters if `entities[]` reuses extraction output, because it changes how much the snapshot can be trusted.

---

## 10. Action Plan

Purpose: a manageable set of proposed phases that close every gap in §7 and every adjacent observation in §9. These are proposals only. No phase files or `roadmap/index.md` entries exist yet, and the numbers are provisional until reserved through the harness. Estimate basis is bottom-up ideal days for one senior Rust dev, matching the remediation-phase sizing, and includes the phase's own tests and coverage.

### 10.1 Design assumptions that keep the phases independent

1. Put `scores` and `entities` on `ScoredHit` (`crates/clio-retrieve/src/types.rs:117-140`), **not** on the frozen `RetrieveHit`. This leaves the fact/belief contract alone and avoids colliding with the in-flight context work in phases 100601/100606.
2. Keep the existing top-level `score` as `final` for backward compatibility; add the nested `scores` object alongside it.
3. `entities[]` initially comes from the span-verified snapshot `entity` value only. Triple-linked enrichment is deferred because there is no by-item triple query and no `item_id` index.

If a later decision moves these fields onto `RetrieveHit`, then 100620 and 100680 must sequence after 100601 instead of running in parallel.

### 10.2 Proposed phases

| Phase | Title | Depends on | Effort | Description |
|---|---|---|---|---|
| 100620 | Retrieval stage scores: dense + lexical capture and the `scores` object | — (coordinate with 100601 only if placement changes) | 4–5 days | Thread the dense cosine distance and the lexical score out of `dense_leg`/`lexical_leg` (`hybrid.rs:344,362`) into `FusedHit` and `ScoredHit`, and add `scores {final, reranker, semantic, keyword}` with `reranker: null`. `final` keeps the existing RRF `score`; `semantic = 1 - distance` with a documented clamp; define `keyword` scale/normalization per backend and document the SQLite `-bm25` vs Postgres `ts_rank_cd` divergence. Consolidate `FusedHit.ranks` and the new per-list scores into one structure. Update MCP, in-process, and CLI JSON together (FR-20). |
| 100640 | Rerank relevance capture and normalization | 100620 | 3–4 days | Change `Reranker::rerank` to return ordered `(index, score)` pairs; parse the score from TEI bare arrays, `results[]`, and `scores[]` (`rerank.rs:296-354`); write the normalized `reranker` value onto the reordered hits in `apply_rerank`. Research and document a per-provider normalization (TEI raw logits vs Cohere `[0,1]`) and keep the existing fail-open behavior. Update the test doubles and every call site, and keep the TEI contract regression coverage from `abcd0019`. |
| 100660 | CLI scores breakdown in the recall text view | 100620, 100640 | 1–1.5 days | Render the per-stage breakdown in `render_recall` (`cli_read_render.rs:50-67`) while keeping the "relative, not calibrated" disclaimer, and leave a slot for the entity reason. Update CLI fixture/golden tests; keep the empty-recall output unchanged. |
| 100680 | Entity names on recall hits (`entities[]`) | 100620 | 2–3 days | Expose `entities[]` from the item's span-verified snapshot `entity` value, with documented coverage limits (empty for triple carriers, hub-distill, beliefs, snapshot-less, and non-default-field writes) and minimal trim-only canonicalization. Keep names out of `warnings`, the `explanation` trace, telemetry, and health surfaces. Cross-binding. |
| 100700 | Entity-overlap match reason (display-only) | 100680, 100660 | 2–3 days | Add a deterministic, display-only entity-overlap reason: when the query text contains one of the hit's entity names, mark `[entity match]`, labelled derived and non-authoritative. Record the display-only vs rank-based decision (display-only recommended; a ranking leg needs rank-based fusion and benchmark validation). Tests for determinism and case handling. |
| 100720 | CLI `-o` alias and output-mode help | — | 1–2 days | Add `-o` as an alias for `--output` in the hand-rolled parser (`cli_args.rs:30,118-128,170-205`), including `explicit_output` (`cli_output.rs:89-105`) and `split_leading_globals`, and document the output-mode rule (explicit > TTY text > piped JSON) in `clio help` (`main.rs:314`). Update parser/output/help tests; decide whether to also update the ~70 per-verb usage strings (`cli_help_usage.rs:24-273`). |
| 100740 | Read-surface de-drift: derive the explain trace from the hit | 100620 | 1–1.5 days | Make the `explain` hit projection derive from one shared source instead of the hand-written field list (`read_retrieve.rs:118-150`), so new hit fields cannot drift, and add a guard test. |
| 100760 | Snapshot leaf verification: reconcile docs and code | — | 1–2 days | Reconcile `docs/extraction-fidelity.md` with `verify_snapshot` (`verify.rs:92-115`): decide whether undeclared non-empty snapshot leaves are rejected or ignored, implement the chosen rule, and align docs and tests. This determines how much the snapshot, and any future `entities[]`, can be trusted. |

### 10.3 Extension phases (larger, separate; include only if scope is meant to cover Hindsight's full surface)

| Phase | Title | Depends on | Effort | Description |
|---|---|---|---|---|
| 100780 | Score floors and entity inclusion controls | 100620, 100640, 100680 | 3–4 days | Add optional `min_scores` floors over `semantic`/`keyword`/`reranker`/`final`, and an entity-inclusion toggle plus a top-level entities summary (Hindsight parity). Document the relative-score caveats and that keyword/semantic floors constrain their own arm only. |
| 100800 | Temporal (relative-date) retrieval arm | 100620 | 5–8 days | Add a temporal arm: parse relative temporal expressions from the query anchored to a query timestamp, retrieve within the resolved window as a rank-based arm, and fuse by rank. Excludes the absolute `as_of`/`time_axis` already present. Larger than the rest and arguably its own track. |

### 10.4 Dependency order

```text
100620 ──┬── 100640 ──┬── 100660 ──┐
         │            │            ├── 100700
         │            └── 100740   │
         ├── 100680 ───────────────┘
         ├── 100780 (also needs 100640, 100680)
         └── 100800

100720  (independent)
100760  (independent)
Existing 100601 / 100606 cover the context/source_ref gap; no new phase.
```

### 10.5 Coverage check (every gap maps to a phase)

| Gap / observation | Phase |
|---|---|
| Dense cosine similarity surfaced | 100620 |
| Lexical BM25 surfaced + backend parity | 100620 |
| Rerank normalized relevance | 100640 |
| Per-result `scores` object | 100620, 100640 |
| `entities[]` per hit | 100680 |
| Entity-overlap reason | 100700 |
| Scores breakdown in text view | 100660 |
| `-o` alias | 100720 |
| Output-mode help | 100720 |
| `context`/`source_ref` on hits | Existing 100601 / 100606 |
| `explain` projection drift | 100740 |
| `FusedHit.ranks` unused | 100620 |
| Hindsight floors / entity controls | 100780 |
| Temporal retrieval arm | 100800 |
| Snapshot leaf verification disagreement | 100760 |

### 10.6 Totals and confidence

- Core phases 100620–100760: **15–22.5 ideal days**; plan **~18–24 days** including integration, cross-binding updates, and review.
- With 100780: **+3–4 days**. With 100800: **+5–8 days**.
- Confidence: medium for the core block; low-medium for 100800 (new retrieval arm and query parsing).
- Excluded from these numbers: adversary/remediation cycles beyond normal, roadmap review latency, and any requirement rewrite. Coverage-gate time is folded into each phase.

### 10.7 Decisions that gate phases

Cross-reference §8. The two that gate phase start: rerank normalization (gates 100640) and entity placement plus display-only-vs-rank (gates 100680/100700).

## 11. Verification status

Verified by source reading (file:line above) and by fetching the Hindsight 0.10 recall docs on 2026-09-25.

Not verified:
- No binary run, test run, or coverage run was performed for this analysis.
- Hindsight behavior beyond the recall API page (for example the entity JOIN/ranking details) was not inspected at source level.
- §9.7 was not reproduced with a live run; treat it as a reading-level observation.
- Requirement citations are drawn from the private baseline; if the baseline moved after 2026-09-25, recheck.

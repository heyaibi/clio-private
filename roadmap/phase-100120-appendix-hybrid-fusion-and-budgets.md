# Phase 100120 appendix: Hybrid fusion and injection budgets

**Consumers:** Phase 100120 (intent gate, hybrid retrieve, compose); Phase 100130 (co-activation on result sets); Phase 100140 (persona channel fill).

**Parent:** `requirement.md` §4.5, PR-1, §2.7, NFR-1, NFR-3; `roadmap/index.md` slice 100120.

## 1. Pipeline (normative shape)

```text
intent_gate(turn) ──skip──► (no dense/lexical/graph) + still allow persona channel
        │
        └──need──► dense_search ∥ lexical_search ─► RRF fuse ─► [optional rerank] ─► top-k
                         │
                         └── optional bounded graph expand on seeds
```

Explicit `retrieve` **bypasses** the skip branch (FR-24).

## 2. Reciprocal Rank Fusion (default)

Classic Cormack et al. (SIGIR 2009) RRF is **unweighted**:

```text
RRF(d) = Σ_i  1 / (k + rank_i(d))
```

This project uses **weighted RRF** (a common production extension) so `ranking_env` dense/lexical (and optional) weights apply:

```text
RRF_w(d) = Σ_i  w_i / (k + rank_i(d))
```

When all `w_i = 1`, weighted RRF reduces to classic Cormack RRF.

| Symbol | Default | Notes |
|--------|---------|-------|
| `k` | `60` | Cormack pilot default (near-optimal; not sacred) |
| `w_dense` | from `ranking_env` | Renormalize with other list weights |
| `w_lexical` | from `ranking_env` | |
| `rank_i(d)` | 1-based | Missing list ⇒ no term |

**Do not** compute `α·cosine + (1-α)·bm25_raw` as the primary fusion—the score scales are incompatible. Postgres `ts_rank*` vs SQLite FTS5 `bm25()` especially must not be mixed as raw scores across backends.

### Tiny fixture (for T100120-07)

Lists (rank order): dense=`[A,B,C]`, lexical=`[B,D,A]`, `k=60`, equal weights `1`:

| id | dense contrib | lexical contrib | RRF |
|----|---------------|-----------------|-----|
| A | 1/61 | 1/62 | ≈0.0325 |
| B | 1/62 | 1/61 | ≈0.0325 |
| C | 1/63 | 0 | ≈0.0159 |
| D | 0 | 1/62 | ≈0.0161 |

Tie-break `A` vs `B` by documented secondary key (higher importance, then id).

## 3. Rerank stage

| Knob | Default guidance |
|------|------------------|
| Fuse shortlist `M` | 50–100 |
| Final `k` | caller `limit` (e.g. 5–20) |
| Timeout | small fraction of retrieve SLO |
| On failure | **fail-open** to RRF order |

Rerank is precision-only; it cannot recover documents absent from the fused shortlist.

## 4. Intent gate quality

| Error type | Meaning | Priority |
|------------|---------|----------|
| False negative | Needed memory, gate skipped | **Stricter** bound—wrong answers |
| False positive | Unneeded memory, gate searched | Looser—latency only |

NFR-1: gate itself p95 ≤ 50 ms; skipped turns add no embed/graph latency beyond the gate.

Suggested starting heuristics (non-normative): short phatic utterances; pure acknowledgements; questions fully answerable from the current turn’s tool results. Prefer retrieving when uncertain.

## 5. Compose dual budgets (PR-1 / FR-7)

```text
pack =
  persona_section   # always reserved, ≤ persona_budget (default target ≤ 400 tokens)
  + memory_section  # from retrieve, ≤ memory_budget
total ≤ budget_tokens  (memory_budget = budget_tokens - tokens(persona_section) - overhead)
```

Rules:

1. Persona channel is filled **even when** intent gate skips memory.
2. If persona stub empty, still emit an empty section marker or omit content but keep budget accounting documented.
3. Truncate memory hits by fused rank / admission score until under budget.
4. Never expand injection because the bank is large—cold storage stays cold.

Token estimator: pick one (model tokenizer vs chars/4 heuristic), use it consistently in tests, document error bars.

## 6. Temporal and domain filters

- Apply `domains` before fusion when possible (pushdown) to avoid wasted candidates.
- Apply `as_of` / `time_axis` to items/triples that carry bi-temporal metadata; drop non-matching candidates before final pack.
- `time_axis` default `valid`.

## 7. What Phase 100120 completion evidence MUST include

- RRF `k` and weight source (`ranking_env`); document **weighted RRF** as extension of Cormack unweighted RRF.
- Rerank M/k/timeout/fail-open confirmation.
- Gate false-negative monitoring note (even if only a test harness counter).
- Persona vs memory budget numbers used in tests.
- Statement that explicit retrieve **and** `compose_context` ignore automatic gate skip.

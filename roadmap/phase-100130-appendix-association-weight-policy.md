# Phase 100130 Appendix: Association Weight Policy

**Normative formulas live in `requirement.md` §4.5 (v1.8+).** This appendix fixes vocabulary, defaults, and numeric fixtures for implementers. It does **not** redefine product rules.

### Vocabulary (zero shared moniker)

| Term | Meaning | Must not confuse with |
|------|---------|------------------------|
| **`assoc_edge`** | Weighted link between two **memory item ids** in **graph/structure metadata** | SPO **triple** (Phase 100080 bi-temporal fact edge); a new memory *domain*/tier |
| **`assoc_kind`** | `coactivation` \| `explicit` | Triple `predicate`; item `epistemic_kind`; `update_rule` |
| **`association_weight_policy`** | Saturating growth + lazy decay + prune + hub distill (**coactivation only**) | Attribute **`update_rule`** (`discrete` \| `continuous`); HeLa-Mem eq. (1) |
| **`η` (eta)** | Co-activation learning rate (default `0.15`) | Continuous EMA **`α`** (Phase 100090) |
| **`hub_distill`** | Distill high-degree assoc cluster → gated semantic item | MemTree ancestor **`memtree_refresh`**; Phase 100060 **canonical merge** |
| **`relationship`** | String on `graph_link` / explicit identity | Triple **`predicate`** |

Stored weight is **raw** `w_ij ∈ [0, 1]`. For coactivation, callers see **effective** weight after lazy decay unless a tool documents otherwise. Explicit edges are **sticky** (no default decay).

**Research warning:** HeLa-Mem uses `(1−λ)w + η·I`—**forbidden** here. Use §4.5 saturating growth only.

---

## 1. Defaults (must match `ranking_env` / config surface)

| Knob | Default | Notes |
|------|---------|--------|
| `η` | `0.15` | Saturating growth step |
| `half_life` | `30` days | `λ = ln(2) / half_life` (coactivation) |
| `w_min` | `0.05` | Prune when `w_eff < w_min` (coactivation) |
| `hub_degree_limit` | deployment-tunable (document chosen default, e.g. `16`) | Count of **above-threshold effective** coactivation edges (+ sticky explicit if counted—document) |
| `max_hops` (graph expand) | small bound (e.g. `2`) | Hard cap; no unbounded BFS |
| explicit decay | **off** (sticky) | Optional longer half-life only if documented |

Expose η, half_life, `w_min` via Phase 100010 `ranking_env_*` (requirement §4.9.5.E). Hub degree limit MAY live beside them or on association-engine config—document the SoT.

---

## 2. Formulas

### 2.1 Growth (on co-retrieved pair)

When items `i` and `j` both appear in the **same** `retrieve` **returned** hit set:

```text
w_ij ← w_ij + η · (1 − w_ij)
```

Clamp to `[0, 1]`. Create the edge if missing. Update `last_reinforced_at` to now. Undirected: store under canonical `(min(id_i,id_j), max(...))`.

**Must not** apply Phase 100090 EMA (`α · x + (1 − α) · prev`) to association weights.

**Durability (FR-17):** reinforce MUST be committed in the retrieve transaction or durable outbox **before/with** the response; soft-drop forbidden.

### 2.2 Lazy decay (read-time, coactivation only)

```text
w_eff(t) = w_ij · exp(−λ · Δt)
λ = ln(2) / half_life
Δt = now − last_reinforced_at
```

### 2.3 Prune (coactivation only)

If `w_eff < w_min` at evaluation: **delete** the assoc edge and **log** the deletion (operations removal).

### 2.4 Explicit sticky edges

Identity: `(bank, id_a, id_b, explicit, relationship)`. Default: no §2.2/§2.3. Multiple `relationship` values per pair allowed.

### 2.5 Hub distill trigger

If a node’s count of neighbors with above-threshold weight exceeds `hub_degree_limit`, enqueue **`hub_distill`**. Distillation re-enters §4.1/§4.2. Log anonymized-derivative decision (§7.4.5).

---

## 3. Numeric fixtures (unit-test oracles)

Assume `η = 0.15`, start `w = 0`.

| Step | After growth | Notes |
|------|--------------|--------|
| 1 | `0.15` | `0 + 0.15·(1−0)` |
| 2 | `0.2775` | `0.15 + 0.15·(1−0.15)` |
| 3 | `0.385875` | saturating |

Decay fixture: `w = 1.0`, `half_life = 30d`, `Δt = 30d` → `w_eff = 0.5`. At `Δt` such that `w_eff < 0.05`, prune deletes **coactivation** only.

Concurrency: two co-activation updates on the same pair must not lose increments (transactional RMW or equivalent).

---

## 4. Edge inventory vs triples

| Store | Identity | Time model | Weight |
|-------|----------|------------|--------|
| Triple (008) | `subject`+`predicate` (+ object payload) | Bi-temporal intervals | N/A (confidence separate) |
| `assoc_edge` coactivation | ordered pair of item ids | `last_reinforced_at` + lazy `w_eff` | saturating `w_ij` |
| `assoc_edge` explicit | pair + `relationship` | sticky (no default decay) | optional initial weight |

`graph_query` / `expand_graph` walk **`assoc_edge`**. They MUST NOT silently reinterpret SPO triples as association weights.

Erase/sync: drop edges whose endpoints were erased; include assoc mutations in multi-host sync payload.

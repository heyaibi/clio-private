# Phase 100040 appendix: Admission factor signals

**Consumers:** Phase 100040 (taxonomy + admission), `ranking_env_*` (Phase 100010), later retrieve/import paths that reuse gates.

**Normative parent:** `requirement.md` §4.2, NFR-5, §9 (weight drift is deployment-tunable).

Online admission MUST be deterministic given identical inputs and effective ranking-env.

## Score

```text
admission_score = w1·utility + w2·confidence + w3·novelty + w4·recency + w5·type_prior
```

Weights `w1…w5` come from `ranking_env_*`. Weights that must sum to 1.0 are renormalized or rejected per Phase 100010 rules. Compare to `θ_admit` keyed by **semantic category** or **episodic type**.

## Factor cookbook (Phase 100040 defaults)

| Factor | Question | Phase 100040 default signal (deterministic) | Slice 100110+ upgrade |
|--------|----------|------------------------------------------|-------------------|
| Future utility | Will this matter beyond this turn? | Heuristic in `[0,1]` from explicit tags / role: preference/decision/constraint/task markers → high; one-off chatter markers → low. Same input → same score. | Learned utility model optional later |
| Factual confidence | How sure is this? | Map `source_type` / statement kind: direct user_stated / system-of-record → high; agent_inferred → mid; speculative markers → low. Clamp to `[0,1]`. | Unchanged unless evidence model expands |
| Semantic novelty | New vs stored? | **Proxy (until embeddings):** `1 - max_jaccard(normalized_token_set(candidate), neighbors_in_bank)` over a bounded recent/index sample, or `1.0` if no neighbors. Exact duplicate token-set → `0`. | Embedding distance to nearest item (dense index) |
| Temporal recency | Fresh vs what it might supersede? | `exp(-Δt / τ)` with configurable `τ` (default 30 days) against nearest same-key or same-type prior; if none, `1.0`. | Unchanged formula |
| Content-type prior | Does this type historically help? | Lookup table per semantic category and per episodic type (defaults below). Deployment may override via ranking-env. | Empirical base rates from telemetry |

### Default `type_prior` (starting points, not certified optima)

**Semantic:** `task_spec` 0.85 · `schema` 0.80 · `tool_config` 0.80 · `output_constraint` 0.75 · `persona` 0.90

**Episodic:** `triple` 0.80 · `task` 0.75 · `failure` 0.85 · `temporal` 0.70 · `gist` 0.40

### Default `θ_admit` (starting points)

Per key, default `0.55` unless ranking-env overrides. Deployments MUST tune (§9); NFR-5 still requires determinism given a fixed config.

## Unavailable factor backend

If a required signal cannot be computed (misconfigured table, storage down mid-score):

1. Return structured error `factor_unavailable` (or equivalent).
2. Do **not** write.
3. Do **not** emit an admission **reject** event that implies scoring completed.
4. Never silent-pass and never randomize.

## Episodic vs semantic gate order

1. Discriminate candidate: semantic vs episodic.
2. Semantic → category whitelist (§4.1). Episodic → type-tag allowlist (`triple`|`gist`|`task`|`failure`|`temporal`).
3. Score with this cookbook.
4. Threshold → admit (repository create) or logged reject.

## Leftover

Empirical weight/threshold fitness remains open per `requirement.md` §9.

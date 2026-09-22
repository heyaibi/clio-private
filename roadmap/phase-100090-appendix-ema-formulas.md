# Phase 100090 appendix: EMA and trend formulas

**Consumers:** Phase 100090 (shared continuous update engine); Phase 100140 (persona preference adapter).

**Parent:** `requirement.md` §4.6 continuous/scalar rule; `roadmap/index.md` slice 100090.

## 1. Normative formulas (from requirement.md)

For a continuous attribute with prior state `s_{t-1}` and observation `x_t`:

```text
s_t = α · x_t + (1 − α) · s_{t-1}     # EMA (fast)
trend_t = mean(s_{t-N+1} … s_t)       # slower baseline over last N states
```

- `α` ∈ (0, 1], tunable per attribute (higher α → faster tracking, more noise).
- `N` ≥ 1 integer, tunable per attribute (larger N → slower trend).
- `trend_t` is the arithmetic mean of the **N most recent EMA states** (not of raw observations), unless a documented config explicitly chooses observation-window mean—default MUST be mean of states to match §4.6 “average over N most recent states.”

## 2. Cold start

| Case | Rule |
|------|------|
| No prior state | `s_0 = x_0`; `trend_0 = x_0` |
| Fewer than N states | `trend = mean(all available states)` |
| First observation after schema create | Same as no prior state |

## 3. Bounds

- Observations MUST be finite floats (reject NaN / ±Inf).
- If the attribute declares `[lo, hi]`, reject or clamp per documented policy (**prefer reject** at the trust boundary; clamp only if schema says `clamp=true`).
- If prior `s` and `x` are in `[lo, hi]` and α ∈ (0,1], `s_t` stays in `[lo, hi]` without extra clamping.

## 4. Suggested defaults (non-normative starting points)

| Knob | Default | Notes |
|------|---------|-------|
| `α` | `0.3` | Moderate tracking; tune per volatile vs stable preferences |
| `N` | `10` | Short trend window for companion preferences |
| Epsilon (tests) | `1e-9` relative or `1e-6` absolute | Document choice in tests |

These defaults live on the **attribute schema / continuous-engine config** (source of truth). A deployment MAY mirror global defaults in effective config for operators; `ranking_env_*` MUST NOT be treated as the per-attribute source of truth (it is for retrieval/admission/co-activation knobs).

## 5. Worked fixture (for T100090-02 / T100090-03)

`α = 0.5`, `N = 3`, observations `1.0, 0.0, 1.0`:

| t | x | s | window states | trend |
|--:|--:|--:|---------------|------:|
| 0 | 1.0 | 1.0 | [1.0] | 1.0 |
| 1 | 0.0 | 0.5 | [1.0, 0.5] | 0.75 |
| 2 | 1.0 | 0.75 | [1.0, 0.5, 0.75] | 0.75 |

## 6. Non-goals for this appendix

- PAMU fused `λ·SW + (1−λ)·EMA` as the **stored** state (optional diagnostic only).
- Co-activation saturating growth (`η`, half-life)—different subsystem (§4.5).
- Belief confidence trajectories—append-only list, not EMA (slice 100100).

## 7. What Phase 100090 completion evidence MUST include

- Chosen defaults for α and N.
- Confirmation that trend uses mean of last N **states**.
- Cold-start and bounds policy stated.
- Dual-backend fixture passing the worked example (or equivalent documented numbers).

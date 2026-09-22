# Phase 100210 Appendix: Hygiene Noise Scoring

**Consumers:** Phase 100210 (`hygiene_audit` / `hygiene_clean`). **Normative default profile** for first release; weights remain deployment-tunable (§4.9.5.A). The MUST is determinism under a fixed config — not immutability of these defaults.

### Vocabulary (zero shared moniker)

| Term | Meaning | Must not confuse with |
|------|---------|------------------------|
| **`hygiene_noise_score`** | `0.0`–`1.0` rank key for operational noise | **`admission_score`** (§4.2) |
| **`noise_reason`** | Explainable factor id in `noise_reasons[]` | Belief `source_type` or correction `reason` |
| **`suggested_hygiene_action`** | `flag` \| `archive` \| `discard` | Compliance `erase_request` |

---

## 1. Score composition

Given identical bank contents and config, ranking MUST be deterministic (NFR-5 spirit).

```text
hygiene_noise_score =
  clamp_01(
      w_secret   · secret_hit
    + w_pattern  · pattern_noise
    + w_dup      · near_duplicate
    + w_utility  · (1 − utility_proxy)
    + w_staleness · staleness
  )
```

Default weights (sum to 1.0; renormalize if overridden):

| Weight | Default | Signal |
|--------|---------|--------|
| `w_secret` | 0.35 | Credential / token / DEK-looking material detected |
| `w_pattern` | 0.25 | Terminal spam, stack traces, heartbeats, command dumps |
| `w_dup` | 0.15 | Near-duplicate of a higher-utility retained item |
| `w_utility` | 0.15 | Inverse of coarse utility proxy (admission utility or retrieval hits) |
| `w_staleness` | 0.10 | Age without recent retrieval / reinforce |

**Secret override:** if `secret_hit ≥ 1`, set `hygiene_noise_score = max(score, 0.90)` and include a secret-class `noise_reason`. Do **not** dampen secret hits because of “value keywords” (that hides the worst cases).

---

## 2. Pattern packs (illustrative, not exhaustive)

| `noise_reason` id | Typical evidence |
|-------------------|------------------|
| `secret_credential` | API keys, bearer tokens, private key blocks, DEK material |
| `terminal_spam` | ANSI dumps, prompt spam, shell noise |
| `stack_trace` | Multi-frame exception dumps without lesson structure |
| `heartbeat` | Periodic ping / health chatter |
| `command_dump` | Raw tool stdout with no distilled lesson |
| `near_duplicate` | High similarity to an existing active leaf |
| `low_utility` | Persistently low utility / never retrieved |
| `stale` | Old and inactive under configured half-life |

---

## 3. Suggested action policy

| Score band | Default `suggested_hygiene_action` |
|------------|-------------------------------------|
| ≥ 0.90 or any `secret_credential` | `discard` (ops removal; still not compliance erase) |
| 0.70 – 0.89 | `archive` (reversible exclusion from active retrieve) |
| 0.40 – 0.69 | `flag` (review only) |
| < 0.40 | Omit from audit unless `min_score` lowered |

Operators MAY override via `hygiene_clean` action; `keep` applies each candidate’s suggested action.

---

## 4. Preview / masking rules

- When any `noise_reasons` entry is secret-class, `preview` MUST be fully redacted (`[REDACTED]` or last-4 only for typed secrets).
- Non-secret previews MUST be truncated (≤ 240 chars) and MUST NOT include DEKs, sync tokens, or raw private keys.
- Cleanup always addresses items by `item_id`; never require plaintext secret content in the clean request.

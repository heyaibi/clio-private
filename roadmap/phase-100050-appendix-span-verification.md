# Phase 100050 appendix — Span verification rules

**Normative for Phase 100050 implementation.** Parent: `requirement.md` §4.4 / FR-4 (as amended). Companion to `roadmap/phase-100050-online-extraction-span-verification.md`.

## 1. What must be verified

Only **extractive** snapshot fields. Taxonomy labels, admission scores, `epistemic_kind`, and other policy fields are **not** span-verified here (they are gated elsewhere).

| Field kind | Pass condition | Fail condition |
|------------|----------------|----------------|
| Entity / identity string | Contiguous source substring equals the value after Unicode NFC (and documented trim of leading/trailing whitespace only) | Paraphrase, fuzzy-only match, empty required field |
| Number | A locatable source substring **parses** to the same numeric value under §2 | Normalized value matches with **no** locatable span; unparsable; empty required field |
| Date / time | A locatable source substring **parses** to the same calendar instant/date under §3 | Ambiguous date without configured policy; no locatable span; empty required field |

**Hard rule:** value-only equality against a normalized form of the whole source document is **not** sufficient. The verifier MUST record span offsets (or equivalent evidence) on success.

## 2. Number parse rules

1. Locate candidate substrings in source (prefer exact digit runs; allow adjacent grouping separators and one decimal separator).
2. Normalize for comparison only: strip currency symbols (`$`, `€`, …) and spaces; treat `,` or `.` as grouping vs decimal per a single configured locale (default: `,` grouping / `.` decimal for en-US-style; document if inverted).
3. Compare as rational/decimal equality within optional `number_tolerance` (default `0` for integers; default `0` for money unless config sets otherwise).
4. Pass only if a specific substring was chosen as evidence; attach `[start, end)` byte or char offsets (document which).

Examples (en-US default):

| Snapshot value | Source contains | Result |
|----------------|-----------------|--------|
| `1000` | `1,000 users` | Pass (span `1,000`) |
| `1000` | `about a thousand` | Fail (no parseable span) |
| `3.14` | `pi≈3.14` | Pass (span `3.14`) |
| `42` | only `41` nearby | Fail |

## 3. Date parse rules

1. Locate a date/time substring in source.
2. Parse with an explicit format preference list from config.
3. If `03/04/2026`-style ambiguous and `day_first` (or equivalent) is **unset**, **fail closed** — do not guess.
4. Compare at the precision present (date-only vs date-time). Do not invent timezones; if source lacks offset, store/compare as naive or apply one documented default zone.

## 4. Retry interaction

FR-4 retry-once applies to the **extraction** call. The verifier itself is deterministic: same source + snapshot + config → same pass/fail (NFR-5 spirit).

## 5. Non-goals

- Fuzzy string similarity as a pass path for entities.
- Second LLM “judge” as the mandatory verifier.
- Treating gist text as evidence for extractive fields.

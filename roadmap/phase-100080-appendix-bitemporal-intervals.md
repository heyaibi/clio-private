# Phase 100080 appendix — Bi-temporal intervals and operators

**Normative for Phase 100080 implementation.** Parent: `requirement.md` §4.6 / FR-12 / FR-24 / NFR-4. Companion to `roadmap/phase-100080-bitemporal-triples-supersession.md`.

## 1. Interval convention

Both `valid_time` and `transaction_time` are half-open `[start, end)` with `end = null` = open-ended.

Edge visible on axis at `as_of` iff:

```text
start <= as_of  AND  (end is null OR as_of < end)
```

## 2. Supersession identity

| Concept | Rule |
|---------|------|
| Open-edge identity key | `subject` + `predicate` (bank-scoped) |
| Contradiction signal | Same key, different `object` (or explicit supersede) |
| Object in identity? | **No** — object is the payload that changes |

Default `triple_add(..., supersede=true)` closes **all open** edges with that `subject`+`predicate` in the bank before inserting the new edge.

## 3. Dual-axis close (mandatory)

On supersede or retract of a prior open edge, set **both**:

- `valid_time.end` — typically the new fact’s `valid_from` (or `valid_until` argument for retract)
- `transaction_time.end` — supersession/retract commit timestamp (system clock)

Never DELETE the prior row.

## 4. Operator examples (assert / retract / correct)

Notation: edge `E(object)[v0,v1) × [t0,t1)`.

### 4.1 Assert / supersede (world changed)

1. Open: `lives_in=Chicago [2020-01-01, ∞) × [2024-01-01, ∞)`
2. `triple_add(lives_in, Boston, supersede=true, valid_from=2024-06-01)` at txn `2024-06-02`
3. Result:
   - Prior: `Chicago [2020-01-01, 2024-06-01) × [2024-01-01, 2024-06-02)`
   - New: `Boston [2024-06-01, ∞) × [2024-06-02, ∞)`

Queries:

| Query | Result |
|-------|--------|
| `as_of=2023-01-01`, `time_axis=valid` | Chicago |
| `as_of=2024-07-01`, `time_axis=valid` | Boston |
| `as_of=2024-06-01T12:00Z`, `time_axis=transaction` (before commit) | Chicago still believed |
| `as_of=2024-06-03`, `time_axis=transaction` | Boston |

### 4.2 Retract (no replacement)

`triple_end(subject, lives_in, valid_until=2025-01-01)` closes the open Boston edge on both axes; no new object.

### 4.3 Correct (system was wrong; late fix)

World was always Boston, but system recorded Chicago then corrects:

1. Recorded in error: `Chicago [2020-01-01, ∞) × [2024-01-01, ∞)`
2. Correction at txn `2024-09-01` with `valid_from=2020-01-01`, object Boston, supersede=true
3. Prior Chicago gets `valid_time.end` and `transaction_time.end` closed at correction policy timestamps; new Boston edge open. Historical `time_axis=transaction` before `2024-09-01` still shows Chicago as what the system believed.

## 5. Tool split

| Tool | Target | Role |
|------|--------|------|
| `invalidate(item_id, replacement_id?)` | Item-shaped discrete records (semantic items / persona stables that use item ids) | Close both time axes on that item; optional replacement link in telemetry |
| `triple_end(subject, predicate, object?, valid_until?)` | SPO edges | Expire matching open triple(s) without replacement |
| `triple_add(..., supersede=true)` | SPO edges | Assert + close prior open subject+predicate |

Telemetry MUST include prior_id / new_id (or subject+predicate+edge ids) so audit can stitch supersession chains (FR-15 spirit).

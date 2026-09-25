## Summary

Writing the same text into a fresh store twice does not always store the same
`admission_score`. The value differs in its last few digits, in about 1 run out
of 10. Nothing about the input changes: same command, same flags, same binary,
same category, empty bank each time.

Because `admission_score` feeds the retrieval importance boost
(`crates/clio-retrieve/src/hybrid_rank.rs:68-70`), two stores that hold
byte-identical content can return different fused `recall` scores, and items
whose scores differ only in those last digits can swap places.

## Cause

Not confirmed. The differing values sit at f32 precision
(`0.7582352941176471` vs `0.7582352169571681`), so the admission path is
probably summing or comparing embedding-derived values in a way whose result
depends on iteration or accumulation order. `novelty_jaccard` in
`crates/clio-admission/src/factors.rs:130-140` uses `BTreeSet` plus `f64::max`
and is order-independent, so the variance is more likely upstream of it, in the
offline embedder or in how candidate factors are combined. That part is not
verified.

## Reproduction

```bash
cargo build --locked --bin clio

T1="The staging deploy retries on ECONNRESET with exponential backoff"
T2="Postgres ts_rank_cd scoring differs from sqlite bm25 ranking"
T3="Reciprocal rank fusion uses k equal to sixty"
T4="Unrelated note about gardening and tomato varieties"

for i in $(seq 1 20); do
  db=/tmp/admx$i.db; rm -f $db
  for t in "$T1" "$T2" "$T3" "$T4"; do
    ./target/debug/clio --db $db --backend sqlite --bank cmpbank \
      remember "$t" --category task_spec >/dev/null 2>&1
  done
done

python3 - <<'PY'
import sqlite3, collections
c = collections.Counter()
for i in range(1, 21):
    con = sqlite3.connect(f"/tmp/admx{i}.db")
    vals = tuple(sorted(r[0] for r in con.execute("SELECT admission_score FROM items")))
    con.close()
    c[vals] += 1
for v, n in sorted(c.items(), key=lambda kv: -kv[1]):
    print(f"{n}x  {list(v)}")
PY
```

## Expected

Identical input into an empty bank should always produce an identical
`admission_score`, so that a stored store returns reproducible `recall` scores.

## Actual

Two distinct values for the same item, roughly 1 run in 10:

```
18x  [0.7582352941176471, 0.7700000000000001, 0.7700000000000001, 0.7700000000000001]
2x   [0.7582352169571681, 0.7700000000000001, 0.7700000000000001, 0.7700000000000001]
```

The same variance was seen with two items in the bank
(`0.7700000000000001` vs `0.7699999228395211`) and with one item in the bank
across 8 runs (no divergence seen there, so a single-item bank may not trigger
it).

## Impact

- Retrieval is not reproducible for identical stored content: the importance
  boost multiplies the fused score, so the same query against two equivalent
  stores can return slightly different `score` values.
- Near-tied hits can swap order between runs, which makes ranking regressions
  hard to tell apart from noise.
- Any test that asserts an exact `admission_score`, an exact fused score, or an
  exact hit order against seeded data can flake.

## Notes

Found incidentally while comparing `recall` output between two builds. It is not
caused by that work and was not fixed there; the retrieval crates involved were
untouched.

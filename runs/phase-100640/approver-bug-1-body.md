## Summary

`memtree::memtree_cov_tests::concurrent_writes_during_refresh_wave` in
`crates/clio-write/src/memtree_cov_tests.rs` fails intermittently when the whole
workspace test suite runs in parallel. It passes reliably on its own.

The test waits for a memtree refresh wave to drain a late write's dirty set
inside a fixed 5-second wall-clock budget. Under load the loop does not converge
in time and the test panics, which fails the whole `make check` gate for a crate
that has nothing wrong with it.

## Reproduction

Full workspace gate:

```
make check
```

Observed failure (public output):

```
test memtree::memtree_cov_tests::concurrent_writes_during_refresh_wave ... FAILED

---- memtree::memtree_cov_tests::concurrent_writes_during_refresh_wave stdout ----

thread 'memtree::memtree_cov_tests::concurrent_writes_during_refresh_wave' panicked at crates/clio-write/src/memtree_cov_tests.rs:294:9:
refresh did not converge

test result: FAILED. 170 passed; 1 failed; 0 ignored; 0 measured; 0 filtered out; finished in 5.25s
```

This reproduced on two consecutive `make check` runs (5.25 s and 5.20 s
"finished in"), and never outside a full-workspace run.

Same test in isolation, five consecutive runs, all green and fast:

```
cargo test -p clio-write --lib --locked memtree::memtree_cov_tests::concurrent_writes_during_refresh_wave
```

```
test result: ok. 1 passed; 0 failed; 0 ignored; 0 measured; 170 filtered out; finished in 0.09s
test result: ok. 1 passed; 0 failed; 0 ignored; 0 measured; 170 filtered out; finished in 0.09s
test result: ok. 1 passed; 0 failed; 0 ignored; 0 measured; 170 filtered out; finished in 0.09s
test result: ok. 1 passed; 0 failed; 0 ignored; 0 measured; 170 filtered out; finished in 0.09s
test result: ok. 1 passed; 0 failed; 0 ignored; 0 measured; 170 filtered out; finished in 0.08s
```

## Expected result

The test either passes or reports a real convergence bug. A healthy memtree
should not fail this assertion just because other crates' tests were competing
for CPU at the same moment.

## Actual result

The assertion at `crates/clio-write/src/memtree_cov_tests.rs:294` is a wall-clock
deadline check, not a behavioural check:

```rust
let deadline = Instant::now() + Duration::from_secs(5);
loop {
    // ... consolidate, then:
    let dirty_left = forest
        .lock()
        .unwrap()
        .tree("b1")
        .map_or_else(Vec::new, BankMemTree::dirty_node_ids);
    if dirty_left.is_empty() {
        break;
    }
    assert!(Instant::now() < deadline, "refresh did not converge");
    thread::sleep(Duration::from_millis(10));
}
```

Each iteration re-runs a full consolidate pass and then sleeps 10 ms. The number
of iterations needed depends on scheduling, not only on the code under test, so
the 5-second budget is consumed by a loaded machine rather than by a defect.

## Impact

- A green tree intermittently reports a red `make check` / CI run.
- The failure names `clio-write` even when the cause is unrelated machine load,
  so it sends whoever sees it looking in the wrong crate.
- It can block or delay an unrelated release or review round, as it did here: a
  full gate had to be re-run to establish that the tree was actually healthy.

## Suggested fix

Pick one:

1. Replace the wall-clock deadline with a bounded iteration count and treat
   hitting the count as a skip with a printed note, so load cannot turn into a
   failure.
2. Raise the deadline and keep the assertion, if a 5-second budget is
   genuinely too tight for a loaded CI runner.
3. Mark the test `#[ignore]` and run it from a dedicated single-threaded job,
   if the timing assumption only holds on an idle machine.

Option 1 keeps the behavioural signal while removing the load sensitivity.

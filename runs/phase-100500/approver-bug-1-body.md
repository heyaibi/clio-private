## Symptom

`concurrent_writes_during_refresh_wave` in `clio-write` fails intermittently during workspace test runs or when executed repeatedly in a loop.

The test panics with:
```
thread 'memtree::memtree_cov_tests::concurrent_writes_during_refresh_wave' panicked at crates/clio-write/src/memtree_cov_tests.rs:279:9:
refresh did not converge
```

## Where

- `crates/clio-write/src/memtree_cov_tests.rs:279`

## Reproduction

1. Run the test repeatedly in a tight loop or under parallel test load:
   `for i in {1..10}; do cargo test -p clio-write --lib memtree::memtree_cov_tests::concurrent_writes_during_refresh_wave || break; done`
2. Observe panic on iteration (reproduced on iteration 4):
   ```
   failures:

   ---- memtree::memtree_cov_tests::concurrent_writes_during_refresh_wave stdout ----

   thread 'memtree::memtree_cov_tests::concurrent_writes_during_refresh_wave' (190529) panicked at crates/clio-write/src/memtree_cov_tests.rs:279:9:
   refresh did not converge
   note: run with `RUST_BACKTRACE=1` environment variable to display a backtrace


   failures:
       memtree::memtree_cov_tests::concurrent_writes_during_refresh_wave

   test result: FAILED. 0 passed; 1 failed; 0 ignored; 0 measured; 148 filtered out; finished in 5.04s
   ```

## Impact

The test creates intermittent build/CI failures during `cargo test --workspace` or `make check` when machine resources are under load.

## Proposed fix

Increase the convergence deadline, investigate whether the refresh loop is delayed by CPU scheduling under load, or ensure `consolidate_tool` drains all pending dirty nodes deterministically.

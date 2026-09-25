## Summary

Two tests in `crates/clio-compliance` intermittently fail when they run at the
same time in the same test process. Both build their exported bundle at the
same temp path, then fail while parsing that file.

## Cause

`unique()` in `crates/clio-compliance/src/import_fixture.rs:93` builds temp
names as `{prefix}-{nanos}-{pid}`. Inside one process the pid is the same, so
two calls that land in the same nanosecond clock tick return the same name.
`write_bundle` (`crates/clio-compliance/src/import_fixture.rs:439-441`) then
writes different bundle JSON to that single path with a non-atomic
`std::fs::write`. When two writes interleave, the file ends up as one document
followed by the tail of the other, so the `serde_json::from_str` call in
`crates/clio-compliance/src/import.rs:122-127` reports `trailing characters` at
the surviving document's length plus one.

The sibling module `crates/clio-compliance/src/stats_tests.rs:30-35` already
avoids this with an `AtomicU64` counter and has a
`unique_values_are_distinct_for_adjacent_calls` test.

## Reproduction

`make check` (full workspace gate); the failing suite is
`cargo test --locked -p clio-compliance --lib`.

Observed once while a second `cargo test` run shared the machine. Both tests
pass when run alone, and 65 further isolated repeats of the suite (40 plain,
25 under extra CPU load) did not reproduce it.

Actual output from the failing run:

    test result: FAILED. 108 passed; 2 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.84s

    ---- import_restore_tests::belief_trajectory_dedupes_and_appends stdout ----
    panicked at crates/clio-compliance/src/import_restore_tests.rs:168:10:
    belief import succeeds: AmError { code: InvalidArgument, message: "bundle JSON invalid: trailing characters at line 1 column 1055" }

    ---- import_restore_tests::belief_dry_run_rejects_below_threshold_without_writes stdout ----
    panicked at crates/clio-compliance/src/import_restore_tests.rs:264:10:
    dry-run belief reject succeeds: AmError { code: InvalidArgument, message: "bundle JSON invalid: trailing characters at line 1 column 1055" }

Both tests pass in isolation:

    cargo test --locked -p clio-compliance --lib -- import_restore_tests::belief_trajectory_dedupes_and_appends import_restore_tests::belief_dry_run_rejects_below_threshold_without_writes --exact
    test result: ok. 2 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out

## Expected

Each test reads the bundle it wrote.

## Impact

False red on the workspace gate. No product or data effect; the collision only
touches test temp files.

## Proposed fix

Give `unique()` a process-wide counter (`AtomicU64`, as `stats_tests.rs` does),
or create the temp bundle as a create-new unique file so two writers can never
share one path.

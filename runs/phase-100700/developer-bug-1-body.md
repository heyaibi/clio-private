# Summary

`clio-mcp`'s `read_scores_tests::dense_arm_populates_semantic_in_mcp_payload_with_parity` fails intermittently when the test suite runs with parallel test threads. Serial runs (`--test-threads=1`) pass. The test uses `fake_tei_server` (`crates/clio-mcp/src/read_scores_tests.rs:298`), which serves exactly `expected_requests = 3` POST requests and treats any `accept` error other than `WouldBlock` as fatal (`Err(_) => break`, `read_scores_tests.rs:333`).

The failure mode is a fast, non-retryable embed failure against the double. `fake_tei_server` does a single `stream.read()` per connection (`read_scores_tests.rs:317`) and answers anything whose first line does not start with `POST /embed` with `{}` (`read_scores_tests.rs:322-327`). If that single read returns a short/partial request (TCP segmentation under parallel load) or zero bytes, the server still answers `200 {}`. On the client side, `parse_embeddings` then fails with `embed response is not a float-vector array` (`crates/clio-index/src/embed.rs:202-211`), which `is_retryable` does not classify as retryable (`crates/clio-index/src/embed.rs:191-199`), so the dense leg degrades instead of retrying.

Found incidentally while establishing a pre-change baseline for unrelated work. Not fixed.

# Reproduction

From the repository root:

```bash
CLIO_DEPLOYMENT_CONFIG=target/coverage/no-deployment-overlay.json \
  cargo test -p clio-mcp --lib --locked read_scores_tests
```

Observed failure rate: about 1 in 3 runs of just this 4-test module; with the full `clio-mcp` lib suite in parallel it failed in 3 of 3 runs. The same commands pass when serial:

```bash
CLIO_DEPLOYMENT_CONFIG=target/coverage/no-deployment-overlay.json \
  cargo test -p clio-mcp --lib --locked -- --test-threads=1
```

`make coverage` for the workspace also fails on this test (observed while taking a pre-change baseline).

# Expected result

All tests pass regardless of test-thread count; the dense leg ranks item `D` and the payload carries a populated numeric `scores.semantic`.

# Actual result

The test panics at one of its dense-leg assertions, at a different point from run to run. Two observed shapes:

```text
---- read_retrieve::read_scores_tests::dense_arm_populates_semantic_in_mcp_payload_with_parity stdout ----
thread 'read_retrieve::read_scores_tests::dense_arm_populates_semantic_in_mcp_payload_with_parity' panicked at crates/clio-mcp/src/read_scores_tests.rs:394:5:
assertion `left == right` failed: one stored vector: ProcessReport { applied: 0, lexical_only: 0, skipped: 0, failed: 1 }
  left: 0
 right: 1
```

```text
thread 'read_retrieve::read_scores_tests::dense_arm_populates_semantic_in_mcp_payload_with_parity' panicked at crates/clio-mcp/src/read_scores_tests.rs:403:5:
the dense leg ranked the hit: {"bank_id":"bank-a","category":"persona","entities":["alpha bravo charlie"],"epistemic_kind":"fact","gist":"alpha bravo charlie","item_id":"D","kind":"semantic","lexical_rank":1,"requires_confidence_check":false,"score":0.011844262295081969,"scores":{"final":0.011844262295081969,"keyword":4.1249999999999995e-6,"reranker":null,"semantic":null},"snapshot_ref":"D"}
```

In the second shape the hit is lexical-only: `lexical_rank` is set while `semantic` is `null`, i.e. the dense leg degraded under its documented failure policy instead of ranking the item.

# Impact

- `make coverage` and `make test` fail in parallel mode, so any phase whose gate runs the workspace suite can be blocked by this test alone.
- CI runs the same suites in parallel and would be red.
- Failure is intermittent (run-to-run) and location-dependent, which makes it expensive to attribute: it looked like a dense-retrieval regression until the serial run passed.

# Proposed fix

Make the test double robust instead of assuming exactly three clean requests:

1. Read until the request line is complete (or simply accumulate bytes until `\r\n` is seen) instead of a single `read()`, so a segmented request is never answered with `{}`.
2. Treat transient `accept` errors as retryable (continue after a short sleep) rather than `break`, and keep serving until the test signals completion (for example an `Arc<AtomicBool>` stop flag), rather than stopping after a fixed count.
3. Optionally return a `500` for unrecognised request lines instead of `{}`, so a mis-served request is retried by the documented retry policy rather than failing closed as a shape error.

# Provenance

Confirmed by the agent while establishing a pre-change baseline for unrelated work on this repository. Not fixed; this report is the only action taken.

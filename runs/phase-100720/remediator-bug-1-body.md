## Summary

`http_bind::tests::occupied_port_advances_to_next_free` intermittently fails with a port-in-use panic on an unchanged tree. The test picks a free successor port by binding and immediately dropping a probe, then rebinds that port later with no retry. Any other process that binds the probed port in the gap makes the test fail.

Found incidentally while running `make check` on unrelated documentation changes. Not fixed here.

## Reproduction

Run the full CLI binary test suite:

```bash
cargo test --locked -p clio --bin clio
```

It is intermittent, not deterministic. It was observed once while a second test run of this repository was executing on the same machine (both runs bind ephemeral ports). Running only the module passes:

```bash
cargo test --locked -p clio --bin clio -- http_bind::tests
```

Observed failure (full-suite run):

```text
---- http_bind::tests::occupied_port_advances_to_next_free stdout ----

thread 'http_bind::tests::occupied_port_advances_to_next_free' panicked at crates/clio-lib/src/http_bind_tests.rs:79:62:
binds the next free port: Custom { kind: AddrInUse, error: "no free port in 64178-64179 on 127.0.0.1; stop the other listener or pass --bind HOST:PORT" }

test result: FAILED. 570 passed; 1 failed; 0 ignored; 0 measured; 0 filtered out
```

Immediately after the failure, port 64179 was free again, and the same test passed in isolation (`7 passed; 0 failed`).

## Expected result

The test binds the successor port it probed and passes.

## Actual result

`bind_first_free(localhost(), busy..=free)` at `crates/clio-lib/src/http_bind_tests.rs:79` finds the whole `busy..=free` range in use and the test panics.

## Mechanism

`occupied_with_free_next` (`crates/clio-lib/src/http_bind_tests.rs:111`) holds `busy` with a listener, proves `busy + 1` is free by binding it, and drops that probe listener at `crates/clio-lib/src/http_bind_tests.rs:120` before returning. The successor port is therefore unowned between the probe drop and the rebind at line 79, so another process can take it.

The sibling test `explicit_address_is_honored` (`crates/clio-lib/src/http_bind_tests.rs:31`) hits the same window and mitigates it with a 100-attempt retry loop, with a comment saying a just-dropped probe port can be taken by a parallel thread. `occupied_port_advances_to_next_free` has no retry.

## Impact

Intermittent false failure of `cargo test -p clio --bin clio` and `make check` whenever another process binds the probed port, for example when two pipeline runs share a machine. A rerun costs several minutes and the failure looks like a real regression. Test-only; no product behavior is affected.

## Proposed fix

Retry the probe-and-bind in `occupied_port_advances_to_next_free`, or make `occupied_with_free_next` keep the successor probe listener open and hand it back instead of dropping it, matching the mitigation already used by `explicit_address_is_honored`.

Found incidentally and not fixed.

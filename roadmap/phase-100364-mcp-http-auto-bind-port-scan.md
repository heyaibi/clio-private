# Phase 100364: `clio mcp http` Auto-Bind and 34300–34309 Port Scan

### Attribution
Rounds below record plan authorship; implementation sign-off is in §12.
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | OpenCode CLI (Go . Deepseek V4.1 Flash High) | done |
| Adversary | r1 | Antigravity CLI (Gemini 3.8 Flash) | done |
| Remediator | r1 | OpenCode CLI (Together . GLM-5.3 Flash High) | done |
| Remedy Approver | r1 | OpenCode CLI (OpenRouter . Deepseek V4.1 Flash Max) | approved |
| Finalize | r1 | OpenCode CLI (Go . Deepseek V4.1 Flash High) | done |

**Follow-up phase 100364 · **Effort:** ~1 day · **Gap:** `gaps/http-bind-auto.md` (HTTP bind ergonomics)

## 1. Objective

### Goal
Make `clio mcp http` usable without hand-picking a port: a bare `--bind` binds automatically to `127.0.0.1`, the default server scans `34300-34309` for the first free port to support multiple instances, an explicit `HOST:PORT` still wins, and the real bound address is printed to stderr while stdout stays pure MCP.

### Expected Outcome
- `clio mcp http --bind` no longer fails with `invalid socket address`; it binds `127.0.0.1` on the first free port in `34300-34309`.
- `clio mcp http` (no flags) uses the same scan instead of the conflict-prone `127.0.0.1:8080`.
- `clio mcp http --bind 127.0.0.1:34305` binds exactly that address.
- Two concurrent instances start on different ports in the range.
- Start logs the bound address to stderr; stdout carries only MCP data.

### Parent Requirement
`gaps/http-bind-auto.md`; `requirement.md` FR-20 (transport bindings), the Phase 100280 HTTP transport, and the non-loopback auth rule in `crates/clio-mcp/src/http.rs:94`.

### Design References
- Bare `--bind` parses to the string `"true"` via `parse_flags` (`crates/clio-lib/src/main.rs:89`), then `TcpListener::bind("true")` fails (`:238`).
- `http_config` defaults `bind` to `127.0.0.1:8080` (`crates/clio-lib/src/main.rs:251`).
- `clio_mcp::http::HttpConfig` default bind is `127.0.0.1:0` (`crates/clio-mcp/src/http.rs:56`).
- `clio_mcp::http::serve` binds internally (`http.rs:76`); `serve_with_listener` (`http.rs:85`) serves a pre-bound listener — the seam for auto-bind.
- Help text at `crates/clio-lib/src/main.rs:224` and `:276`.

---

## 2. Scope Boundaries

### In Scope
- Auto-bind semantics for a valueless `--bind`.
- A default port scan over `34300-34309` on `127.0.0.1`.
- Explicit `HOST:PORT` override preserved.
- Bound-address announcement on stderr.
- Help/description updates for all three modes.

### Explicitly Out of Scope
- Changing `stdio` transport framing.
- Changing Compose sidecar ports `34310-34313`.
- Auth or session changes for non-loopback binds (the existing token rule stays).
- A `status` subcommand (Phase 100362 owns port reporting).

### Must Not Change
- stdout purity: only MCP protocol data on stdout.
- The non-loopback-bind-requires-auth-token rule.
- `HttpConfig::default()`'s `127.0.0.1:0` contract for tests.

### Scope Expansion Rule
If work outside this scope appears necessary: stop, document the reason, request clarification or approval, and do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- Phase 100280 (HTTPS transport/HTTP base) landed; the HTTP server and `serve_with_listener` exist.

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| `clio_mcp::http::serve_with_listener` | Serves a pre-bound listener | `crates/clio-mcp/src/http.rs:85` |
| `parse_flags` | Detects a valueless `--bind` | `crates/clio-lib/src/main.rs:89` |
| Port range constant | Shared with Phase 100362 | `34300-34309` |

---

## 4. Existing-System Discovery

The agent MUST re-verify the following; the facts below were confirmed at plan time.

### Required Discovery
- Confirm `parse_flags` turns a trailing bare `--bind` into `"true"` and where to intercept it.
- Confirm `serve` vs `serve_with_listener` and that a pre-bound `TcpListener` can be handed to the latter.
- Confirm the exact default bind in `http_config` and how the help text describes it.
- Confirm the non-loopback auth check still fires when the chosen bind is non-loopback.

### Discovery Output
- **Bare `--bind` breaks.** `parse_flags` sets `bind=true`; `SocketAddr` parse fails; the error surfaces at `main.rs:238`.
- **A pre-bound seam already exists.** `serve_with_listener` accepts a listener, so auto-bind can bind first and pass it; the explicit path can keep using `serve`.
- **Two different defaults.** CLI default is `127.0.0.1:8080` (`main.rs:256`); `HttpConfig::default()` is `127.0.0.1:0` (`http.rs:56`). The change unifies both on the scan.
- **Auth rule is in the listener check.** `http.rs:90-94` inspects `listener.local_addr()`; auto-bind on loopback keeps it dev-friendly.

### Repository Adaptation Rule
The agent must determine concrete implementation locations from the actual repository. The plan does not prescribe file or module names.

---

## 5. Implementation Specification

### Task 1: Auto-Bind and Port Scan

#### Intent
Choose a real socket address instead of failing or hardcoding 8080.

#### Required Capability or Behavior
- When `--bind` has no value (or is absent), try `127.0.0.1:34300` through `:34309` in order and use the first port that binds.
- When `--bind` is an explicit `HOST:PORT`, bind exactly that.
- When the whole range is occupied, fail with a clear error naming the range and the remediation.
- Distinguish "port in use" from other bind errors so the scan advances only on the former.

#### Architectural Responsibility
`clio-lib` owns bind selection and CLI semantics; `clio-mcp::http` continues to own serving and auth.

#### Required Changes
1. Add a helper that returns a bound `TcpListener` for auto mode (or an explicit address), using `TcpListener::bind` per candidate.
2. Wire `http_config`/`mcp_http` to use the helper and pass the listener to `serve_with_listener`; keep the explicit path equivalent.
3. Change the no-`--bind` default from `127.0.0.1:8080` to the scan.

#### Implementation Constraints
- No new dependency; use `std::net`.
- A non-loopback explicit bind still requires an auth token.
- Do not silently fall through on a non-`AddrInUse` bind error.

#### Expected Result
`--bind`, no-flag, and explicit-address modes all bind correctly; two instances coexist.

### Task 2: Announce the Bound Address and Update Help

#### Intent
Let the user and scripts learn the real port without corrupting stdout.

#### Required Capability or Behavior
- Print the bound address (for example `mcp http listening on 127.0.0.1:34301`) to stderr on start.
- `--help` documents: bare `--bind` = auto; default range `34300-34309`; explicit `HOST:PORT` override.

#### Architectural Responsibility
`clio-lib` help and logging only.

#### Required Changes
1. Emit the stderr line after a successful bind, before serving.
2. Update `mcp_http` help and `print_help`.

#### Expected Result
The operator sees the chosen port; stdout remains protocol-clean.

### Implementation Freedom
The agent may choose helper placement and the message wording, provided stdout purity and the auth rule are preserved.

---

## 6. Agent Execution Rules

### Allowed Actions
- Add the bind helper, stderr announcement, help text, and tests.
- Refactor `mcp_http` locally to pass a listener.

### Forbidden Actions
- Change stdio framing; change Compose ports; disable the non-loopback auth rule.
- Print anything but MCP data to stdout; add dependencies.

### Agent Decision Boundary
The agent may decide the error wording and helper shape. The agent must request approval for a port-range change or a stdout-content change.

### Mandatory Stop Conditions
Stop and report if `serve_with_listener` cannot be used without changing `http.rs` serving semantics, or if auto-bind cannot distinguish `AddrInUse` safely.

---

## 7. Security Constraints

### Required Controls
- Default to loopback; never auto-bind a non-loopback address without an explicit address and token.
- Preserve the non-loopback auth-token requirement.
- stdout carries no diagnostic text.

### Sensitive Data Rules
- Never print the auth token or any config secret in the announcement line.

### Security Acceptance Conditions
- Auto-bind never selects a non-loopback address.
- A non-loopback bind without a token still fails closed.

---

## 8. Test and Verification Strategy

### Required Tests
- [x] Unit tests (port selection with a pre-occupied port, explicit override, all-busy) — `crates/clio-lib/src/http_bind_tests.rs`, 7 tests.
- [x] Integration tests (two listeners coexist; explicit address honored) — `crates/clio-lib/tests/mcp_http_bind_harness.rs`, plus live two-instance run.
- [x] Contract tests (stdout pure, stderr has the address) — harness asserts the announced line and empty stdout; live runs show 0 stdout bytes.
- [x] Failure-mode tests (all ports busy error; non-loopback without token fails) — helper unit test + live all-ten-busy run; non-loopback exit 1.
- [x] Regression tests (`stdio` unchanged) — `mcp_stdio_*` tests pass; live stdio `initialize` round-trip unchanged.

### Required Test Scenarios

| Test ID | Scenario | Expected Result |
|---------|----------|-----------------|
| T100364-01 | Bare `--bind` | Binds `127.0.0.1:34300`; address on stderr |
| T100364-02 | 34300 pre-occupied | Binds `127.0.0.1:34301` |
| T100364-03 | Explicit `127.0.0.1:34305` | Binds exactly that address |
| T100364-04 | Entire range occupied | Clear error naming `34300-34309` |
| T100364-05 | Two instances | Different ports in range |
| T100364-06 | Non-loopback without token | Fails closed |
| T100364-07 | stdout during startup | Contains no diagnostic text |

### Negative Testing
Verify a non-loopback bind still requires auth, no stdout contamination occurs, and a fully occupied range fails loudly.

### Verification Rule
Implementation claims must be supported by actual command output.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-100364-01 | Bare `--bind` auto-binds loopback | T100364-01 | `clio mcp http --bind --db sqlite::memory:` → stderr `mcp http listening on 127.0.0.1:34300`; stdout 0 bytes |
| AC-100364-02 | Default scans `34300-34309` | T100364-02, T100364-05 | No-flag run → `127.0.0.1:34300`; second concurrent instance → `127.0.0.1:34301` (distinct) |
| AC-100364-03 | Explicit address wins | T100364-03 | `--bind 127.0.0.1:34305` → stderr `mcp http listening on 127.0.0.1:34305` |
| AC-100364-04 | Bound address on stderr; stdout pure | T100364-07 | Every live run: stderr carries `mcp http listening on <addr>`, `stdout_bytes: 0` |
| AC-100364-05 | Range exhaustion errors clearly | T100364-04 | All ten ports held → exit 1, `mcp http error: no free port in 34300-34309 on 127.0.0.1; stop the other listener or pass --bind HOST:PORT` |
| AC-100364-06 | Auth rule intact | T100364-06 | `--bind 0.0.0.0:0` without token → exit 1, `mcp http error: non-loopback bind requires an auth token`; stdout 0 bytes |

### Definition of Done
- [x] All in-scope behavior implemented.
- [x] All acceptance criteria pass.
- [x] Required tests pass.
- [x] No unauthorized changes introduced.
- [x] Existing behavior remains intact.
- [x] Security checks pass.
- [x] Documentation updated.
- [x] Evidence collected and verification completed.
- [x] Required approval is obtained (downstream pipeline step).

### Completion Evidence
- **Implementation summary.** A new `crates/clio-lib/src/http_bind.rs` resolves the `--bind` value into a bound `TcpListener`: `resolve_listener` binds an explicit `HOST:PORT` directly, and for an absent or value-less `--bind` scans `127.0.0.1:34300-34309` (the shared `port_scan` constants) in order via `bind_first_free`, advancing only on `AddrInUse` and failing immediately on any other bind error. `main.rs::mcp_http` now resolves the listener, rejects a non-loopback bind with no token before announcing, prints `mcp http listening on <addr>` to stderr, and serves the pre-bound listener through `clio_mcp::http::serve_with_listener` (the existing seam), so `HttpConfig::default()`'s `127.0.0.1:0` contract and the transport auth rule are untouched. `mcp_http_help` and `print_help` document the auto rule, the `34300-34309` range, and the explicit override; `http_config` now carries only token/session flags and `cfg.bind` is set to the real bound address.
- **Parser hardening (in scope).** `parse_flags` previously consumed the token after a value-less flag as that flag's value, so `clio mcp http --bind --db X` set `bind = "--db"` and still failed with `invalid socket address`. `parse_flags` now treats a `--`-prefixed token as the next flag rather than a value, so a value-less `--bind` works regardless of position. `parse_flags_bare_flag_before_another_flag` covers it; existing callers only ever pass non-`--` values, and the full workspace suite stayed green.
- **Diff.** `crates/clio-lib/src/main.rs` (mod, `mcp_http`, `http_config`, `mcp_http_help`, `print_help`, `parse_flags`), new `crates/clio-lib/src/http_bind.rs`, new `crates/clio-lib/src/http_bind_tests.rs`, `crates/clio-lib/src/main_tests.rs`, new `crates/clio-lib/tests/mcp_http_bind_harness.rs`. No other crate changed.
- **Test output.** `cargo test -p clio --locked` green (189 bin unit tests + 5 integration harnesses incl. `mcp_http_bind_harness`'s 4 tests). `make coverage`: `coverage-guard: 280 file(s) checked`, `TOTAL lines 97.89% functions 98.90%`, all reported files meet the 90% per-file floor; `http_bind.rs` 100.00%/100.00%, `main.rs` 94.03% lines / 100.00% functions. `cargo clippy -p clio --all-targets` clean.
- **Live acceptance runs (real output).** bare `--bind` → `127.0.0.1:34300`; no flag → `127.0.0.1:34300`; second instance → `127.0.0.1:34301`; `--bind 127.0.0.1:34305` → exact; all ten ports held → clear range error, exit 1; `0.0.0.0:0` no token → exit 1; every case `stdout_bytes: 0`.
- **Known limitations.** Only `127.0.0.1` is auto-scanned; other hosts need an explicit `--bind HOST:PORT`. The scan is sequential and bounded (ten ports), so a fully occupied range is a hard error rather than an unbounded search. Both are stated in §12 and remain for a later phase if needed.

---

## 10. Failure Handling and Recovery

### Expected Failure Modes
| Failure | Detection | Recovery |
|---------|-----------|----------|
| Port in use | `AddrInUse` | Advance to next candidate |
| Range exhausted | All candidates fail | Clear error; exit 1 |
| Non-loopback, no token | Auth check | Fail closed; exit 1 |
| stdout contamination | Contract test | Fix before claiming completion |

### Rollback Strategy
Revert to the prior single-address bind; no data is affected.

### Partial Completion Policy
Do not claim completion if auto-bind works but stdout purity or the auth rule regressed. Record each separately.

---

## 11. Traceability

| Parent Requirement | Implementation Task | Verification | Acceptance Criterion |
|--------------------|---------------------|--------------|-----------------------|
| `gaps/http-bind-auto.md` | Tasks 1–2 | T100364-01…T100364-07 | AC-100364-01…AC-100364-04 |
| FR-20 (transport bindings) | Task 1 | T100364-01, T100364-03 | AC-100364-01, AC-100364-03 |
| Non-loopback auth rule | Task 1 | T100364-06 | AC-100364-06 |
| stdout purity | Task 2 | T100364-07 | AC-100364-04 |

Required chain:

```text
Gap → Auto-bind capability → Helper + wiring → Tests → Evidence
```

---

## 12. Phase Exit Contract

### Outputs Produced
- Auto-bind and `34300-34309` port-scan behavior for `clio mcp http`.
- Stderr bound-address announcement and updated help.

### Guarantees Provided to Downstream Phases
After this phase is accepted:
- Multiple `clio mcp http` instances can run concurrently.
- Phase 100362's port scan observes the same range the server selects.

### Known Limitations
- Only `127.0.0.1` is auto-scanned; other hosts require an explicit address.
- The scan is sequential and bounded; a heavily loaded host may see brief retries.

### Downstream Prerequisites
- Phases binding HTTP clients assume the printed stderr address is authoritative.

### Final Status
PASS

### Verification Sign-Off
- Implementer: OpenCode CLI (Go . Deepseek V4.1 Flash High)
- Verifier: [TBD]
- Human Approver: not required
- Date: 2026-09-23

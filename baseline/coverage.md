# Coverage playbook (Agent Memoir)

**Audience:** agents and humans implementing phases under a **≥90% function + line (per file)** gate (`cargo llvm-cov` / `make coverage`).

**Why this file exists:** Phase 100020 burned ~15× the expected time chasing **region** coverage theater and flaky Postgres suites. The gate is now **lines + functions only**. Regions may still appear in reports; they are informational — **do not** invent unreachable `Err` arms to close them.

Also linked from `AGENTS.md` and `make help`.

## Mistakes to not repeat

| Mistake | Better default |
|---------|----------------|
| Treat every `?` Err as must-hit for **region** % | Gate is lines + functions. Prefer `expect` / casts for infallible paths; inject failures only at real boundaries |
| Shared DB tests without a lock + poison recovery on the **test** lock | One `PG_TEST_LOCK` + `into_inner`; no destructive DDL on `public` |
| `into_inner` + `poison_*_for_test` on **production** mutexes | Production: `.lock().expect("… poisoned")`. No poison theater |
| Name test file `*_tests_extra.rs` | Name `*_tests.rs` / `*-tests.rs` / `tests.rs` so llvm-cov path-excludes it |
| Inline `#[cfg(test)] mod tests {…}` and assume it is excluded | **Not excluded.** Only path patterns above (and `tests/` dirs) are omitted by default |
| `reset_auto_extension` in parallel tests | Don’t mutate process-global SQLite state across threads |
| Finish code, then sync vocab docs | Same change: SQL + code + roadmap + glossary |
| Makefile `DATABASE_URL` DB name ≠ Compose `POSTGRES_DB` | One canonical DB (`clio`); keep Makefile, `.env.example`, test fallbacks, and this file identical |
| CI missing `--fail-under-functions` (or still requiring regions) | CI must match Makefile: **lines + functions** only — no `--fail-under-regions` |
| Fixed SQLite KNN over-fetch (`k*8`) then claim “exact” | Widen fetch until in-bank top-k is filled or exhausted; keep a multi-bank hostile test |
| Dead error mappers only unit-tested | Wire open/registration failures through the mapper (`Result`), or delete it |
| Run `make check` / coverage in a tight loop while fixing | One diagnostic run → wholesale fix → one verify run (laptop heat) |
| `make test` / `make check` without `--workspace` | Workspace has `default-members = [clio-lib]` — always pass `--workspace` or store tests never run |
| Drop a workspace.dependency while adding another | Keep `zerocopy` (etc.) when editing `Cargo.toml`; refresh `Cargo.lock` before `--locked` builds |
| Env fallback URL unhit under coverage (DATABASE_URL always set) | Extract `postgres_url_or_default(Result<…>)` and unit-test both Ok and Err arms |
| Fixed KNN `fetch_k = k.max(32)` never widens in tests | Start at `k.max(1)` so multi-bank cases must widen; keep a hostile foreign-neighbor test |

**Gate command (authoritative):**

```bash
make coverage
# equivalent:
# cargo llvm-cov --workspace --locked --no-clean --summary-only \
#   --fail-under-lines 90 --fail-under-functions 90

# Authoritative from-scratch run (drops the warm instrumented build first):
make coverage-clean
```

`make coverage` passes `--no-clean`: the instrumented build in `target/llvm-cov-target` stays warm, so repeated gates reuse unchanged crates instead of recompiling the whole workspace. `cargo llvm-cov` **cleans build artifacts by default**, which is what made every gate a full instrumented rebuild. Use `make coverage-clean` after large refactors, when crates or tests were renamed or removed, or whenever per-file numbers look wrong; it runs `cargo llvm-cov clean --workspace` and then the normal gate. Scoped raw `cargo llvm-cov` commands below must also pass `--no-clean` for the same reason.

`DATABASE_URL` defaults (via Makefile) to Compose Postgres:

`postgres://clio:clio@127.0.0.1:34310/clio`

**Per-file floor:** Humans lowered the lasting gate from 100% to **≥90% lines and functions on every reported source file** (not only the TOTAL row). `cargo llvm-cov --fail-under-*` enforces the aggregate floor; agents MUST still scan the per-file summary and stop if any file is under 90%.

All of `coverage`, `coverage-html`, `coverage-lcov`, and `coverage-open` MUST share that env. Do not special-case only `make coverage`. CI uses the same two `--fail-under-*` floors (port may differ for the Actions service).

`make check` = `fmt` + `clippy -D warnings` + `test` (not coverage). Still keep coverage green before claiming a phase done.

---

## 1. Order of operations (do this, in this order)

1. **Baseline before edits.** Run `make coverage`. If any reported file is below **90%** lines or functions, **stop and raise**.
2. **Implement behavior first.** Green `cargo test --locked` (and Clippy `-D warnings`) before hunting coverage misses.
3. **Stabilize shared dependencies.** Postgres up (`make compose up …`), unique IDs, serialized access to shared DBs.
4. **Then** run coverage. Fix real **line/function** misses with the decision tree in §3. While iterating on specific files, verify with scoped per-crate runs or one JSON run (see §7) — reserve the full `make coverage` for the final pass.
5. **Do not** spend time closing region-only gaps. If a line is hit and the function runs, that is enough for the gate.

Do **not** open HTML / JSON coverage parsers until step 4.

---

## 2. What the gate measures

| Metric | Gated? | Meaning in practice |
|--------|--------|---------------------|
| **Functions** | **Yes — ≥90% per file** | Every compiled function in reported crates was entered at least once. |
| **Lines** | **Yes — ≥90% per file** | Every instrumented line had ≥1 hit. |
| **Regions** | **No** | LLVM can split a line into multiple regions (`a()?.b()?`, `unwrap_or`). Unhit regions may still show in HTML/JSON — **ignore for the gate**. |

`cargo llvm-cov` HTML can paint a line green when any region on that line ran. For this repo, trust the **summary lines + functions** columns against the fail-under floors.

### Column mapping and the per-file guard

`llvm-cov` reports three per-file summary columns — regions, lines, functions — and only **lines** and **functions** are gated:

| JSON path (`cargo llvm-cov --json`) | Gate? | Notes |
|-------------------------------------|-------|-------|
| `data[].files[].summary.regions.percent` | **No** | Informational; never a pass/fail input. |
| `data[].files[].summary.lines.percent` | **Yes — ≥90% per file** | Instrumented lines with ≥1 hit. |
| `data[].files[].summary.functions.percent` | **Yes — ≥90% per file** | Compiled functions entered ≥1 time. |

`--fail-under-*` flags gate only the **TOTAL** row. The per-file floor is enforced by the guard script:

```bash
python3 scripts/coverage_guard.py <llvm-cov.json>
```

It prints a TOTAL line plus any per-file offenders and exits non-zero when a reported file is under 90% lines **or** functions. `make coverage` produces one JSON report, runs the aggregate gate on it, then runs the guard on the same report (one instrumented test run per gate); CI mirrors both steps.

### What llvm-cov reports (and ignores)

Per [cargo-llvm-cov README](https://github.com/taiki-e/cargo-llvm-cov): by default the report **excludes** code under a directory named `tests` and files named `tests.rs`, `*_tests.rs`, or `*-tests.rs`.

- That exclusion is **path-based**, not “any `#[cfg(test)]` module.”
- Inline `#[cfg(test)] mod tests { … }` inside a production `.rs` file **still counts** toward the gate (unless you use `#[coverage(off)]` on nightly).
- Names like `*_tests_extra.rs` are **not** excluded → they pollute the gate. Always use `*_tests.rs` for test-only modules (e.g. `assoc_edge_tests.rs`, `async_store_tests.rs`).

### Diagnosing misses quickly

```bash
export DATABASE_URL=postgres://clio:clio@127.0.0.1:34310/clio
cargo llvm-cov --workspace --locked --no-clean --json --output-path /tmp/cov.json
# Inspect files with uncovered lines / functions (not region theater).
```

Or: `make coverage-html` / `make coverage-open` once the suite is green.

---

## 3. Decision tree for an unhit **line** or **function**

Ask once, in order:

### A. Is this code reachable in production?

| Kind | Examples | Action |
|------|----------|--------|
| **Infallible** | `serde_json::to_string` on a closed struct; ChaCha20-Poly1305 encrypt; mutex poison after a bug | Use `.expect("…")` or a cast. Do not keep decorative `Result` arms. |
| **Trust boundary** | DB execute, connect, decrypt, sqlite-vec load | Keep `Result` + `?`. Prefer one shared mapper tested Ok + Err. |
| **Process-global / parallel-hostile** | `sqlite3_reset_auto_extension` | Fail closed via `Result` / `sqlite_vec_missing`; do not race other tests. |
| **Async join / spawn_blocking cancel** | `JoinError` | Prefer `.expect("store blocking task")` unless cancel is a product path. |

### B. Matching the rest of this repo

Existing crates freely use `.expect(...)` on invariants. Do not burn hours on false arms.

### C. After two failed attempts

Stop. Paste file + line, why it cannot be hit cheaply, and ask whether to delete or add one concrete test. Do not invent schema vandalism to close an arm — especially not for region-only gaps.

---

## 4. Patterns that burned Phase 100020 (anti-patterns)

### 4.1 Dead `unwrap_or` / decorative `Result`

Prefer casts / `expect` for infallible paths. Saves line noise and avoids fake branches.

### 4.2 Poison recovery vs poison theater

```rust
// Test-only shared lock (PG_TEST_LOCK):
.lock().unwrap_or_else(|e| e.into_inner())

// Production store / KMS mutexes:
.lock().expect("sqlite store mutex poisoned")
```

### 4.3 Counting every `.am("…")?` separately

Prefer one `IntoAmError` helper. One empty-schema failure often covers the driver-error path.

### 4.4 Shared Postgres without serialization

1. Serialize with `PG_TEST_LOCK` + `into_inner`.
2. Prefer private schemas.
3. Unique row IDs.

### 4.5 `DATABASE_URL` only on one Make target / wrong DB name

One Makefile `export DATABASE_URL ?= …/clio` for all coverage recipes; match `.env.example` and Compose.

### 4.6 Process-global SQLite extension reset

Do not call `reset_auto_extension` in tests. Registration/open failures go through `sqlite_vec_missing`.

### 4.7 SQLite bank-scoped KNN

Use widening fetch (`sqlite_knn::knn_in_bank`), not a fixed `k*8` cap. Keep a hostile multi-bank test.

### 4.8 Async adapter coverage

Put async adapter tests in `async_store_tests.rs` (path-excluded). Keep sync `Store` as the behavioral contract for most tests.

### 4.9 Renames without doc sync

Vocabulary renames require the same change for roadmap, glossary, `crates.md`, and comments.

### 4.10 Region hunting (retired)

Do **not** reintroduce `--fail-under-regions`. Unhit regions on an otherwise covered line are not a gate failure.

---

## 5. Design for coverage *while* implementing (not after)

1. **Small modules** (≤450 lines).
2. **One error sink** (`IntoAmError` / `sqlite_vec_missing`).
3. **Infallible crypto/serde/mutex poison:** `expect`.
4. **Test doubles at boundaries** (`FailEncryptKms`).
5. **Parity + `*_tests.rs` edge modules.**
6. **Name test modules `*_tests.rs`.**

---

## 6. Checklist before declaring a phase done

- [ ] `make coverage` exits 0 (**lines** and **functions** ≥90% aggregate); the per-file guard in the same gate confirms **each file** ≥90% lines and functions (see §2 "Column mapping and the per-file guard").
- [ ] CI yaml matches: `--fail-under-lines 90` and `--fail-under-functions 90` only (no regions floor).
- [ ] `make coverage-html` / `coverage-open` green (same `DATABASE_URL`).
- [ ] `make check` clean with **`--workspace`** test/clippy scope (one verify run after a wholesale fix).
- [ ] `cargo test --locked` clean with `DATABASE_URL` unset (fallbacks → `clio`).
- [ ] Compose Postgres reachable when claiming Postgres parity.
- [ ] No `*_tests_extra.rs` production-reported test files.
- [ ] Phase exit / completion evidence filled when claiming phase done.
- [ ] Vocab renames reflected in docs if any occurred this phase.

---

## 7. Quick reference — commands

```bash
make compose up mac   # or: make compose up linux
make check            # fmt + clippy -D warnings + test
make coverage
make coverage-html
make coverage-open
```

While iterating on specific files, do NOT loop the full gate:

```bash
# Scoped per-crate run (fast; read the per-file rows for your files):
cargo llvm-cov --package <crate> --locked --no-clean --summary-only
# One workspace JSON run; re-read per-file rows from it instead of re-running:
cargo llvm-cov --workspace --locked --no-clean --json --output-path /tmp/cov.json
```

Both use the same `DATABASE_URL` env as `make coverage`. Final pass is
always the full `make coverage` (aggregate AND per-file floors).

### Hermetic test runs on a host with a deployment overlay

Some in-process tests assert a deployment-free effective config. If the host has
a durable overlay at `~/.config/clio/deployment.json` (for example a running
sidecar), those tests fail even though the tree is green. The `test`, `check`,
and `coverage`/`cov` targets point `CLIO_DEPLOYMENT_CONFIG` at a path that does not
exist, so the effective overlay is empty. Pass `CLIO_DEPLOYMENT_CONFIG=…` on the
`make` command line to test against a real config instead.

Do **not** use an empty value (`CLIO_DEPLOYMENT_CONFIG=''`): that disables
deployment loading, and `clio setup` tests that need a resolvable config path then
fail with `cannot resolve a config directory`.

Install if missing:

```bash
rustup component add llvm-tools-preview
cargo install cargo-llvm-cov
```

---

## 8. Phase 100020 postmortem (compressed)

| Symptom | Root cause | Fix that stuck |
|---------|------------|----------------|
| Hours on region % after lines green | Gate included regions | **Retired:** gate is lines + functions only |
| 22 pass / 9 fail on `coverage-open` | No `DATABASE_URL` on HTML + lock poison cascade | Shared Makefile export + test-lock `into_inner` |
| Suite flakes under llvm-cov | Parallel Postgres DDL on `public` | `PG_TEST_LOCK` + temp schemas |
| Coverage denominator spiked | `*_tests_extra.rs` counted | Rename to `*_tests.rs` |
| CI ≠ local functions gate | CI omitted `--fail-under-functions` | Align CI with Makefile |
| Fresh Compose vs Makefile DB | `am_store_test` not created by Compose | Standardize on `clio` |
| Bank KNN under-return | Fixed over-fetch | Widening `knn_in_bank` + hostile test |

**Time lesson:** stabilize tests first; cover lines/functions; never invent branches for region theater; one diagnostic run, wholesale fix, one verify.

---

## 9. Non-negotiables for future agents

1. Do not start a phase if any reported file is below **90%** line/function coverage — raise immediately.
2. Do not chase coverage before `cargo test` is green.
3. Do not invent unreachable `Err` arms or production poison helpers — especially not for regions.
4. Do not mutate process-global SQLite auto-extensions in parallel tests.
5. Do not leave coverage Make targets without the same env as the gate.
6. Do not reintroduce `--fail-under-regions` without an explicit human decision.
7. Keep CI `--fail-under-lines` / `--fail-under-functions` in lockstep with Makefile.
8. Keep `DATABASE_URL` DB name aligned with Compose / `.env.example`.

This file is normative for coverage work in this repo until superseded.

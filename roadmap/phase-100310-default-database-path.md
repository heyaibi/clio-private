# Phase 100310: Zero-Config Default Database Path with Full Precedence

### Attribution
Rounds below record plan authorship; implementation sign-off is in §12.
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | OpenCode CLI (Together . GLM-5.3 Flash High) | done |
| Adversary | r1 | Antigravity CLI (Gemini 3.8 Flash) | done |
| Remediator | r1 | OpenCode CLI (Go . Deepseek V4.1 Flash High) | done |
| Remedy Approver | r1 | OpenCode CLI (OpenRouter . Deepseek V4.1 Flash Max) | approved |
| Finalize | r1 | OpenCode CLI (Go . Deepseek V4.1 Flash High) | done |

**Index slice 100310 · **Effort:** `1×` · **Scope:** `gap/default-sqlite.md`, extended by operator decision to the full database-precedence chain

### Vocabulary (read first) — zero shared moniker
| Term | Enum / form | Where it lives | Must not |
|------|-------------|----------------|----------|
| **default database path** | `$XDG_DATA_HOME/am/clio.db`, else `~/.local/share/am/clio.db` | One shared resolver | Be re-implemented separately in the CLI and in config defaults |
| **`AM_DATA_DIR`** | Directory override | Env overlay + resolver | Include the filename in its value; the resolver appends `clio.db` |
| **`--db`** | CLI database URL/path | CLI options | Be overridden by any env var |
| **`--backend`** | `sqlite` \| `postgres` | CLI options | Be guessed when the URL scheme is unambiguous; explicit wins |
| **`sqlite::memory:`** | Explicit volatile opt-in | CLI value / store open | Ever be produced by the default resolver |

---

## 1. Objective

### Goal
Make `am mcp stdio` (and every other store-opening CLI command) persist to a real database file with no flags, no config file, and no environment variables, while honoring an explicit precedence chain so existing Postgres/`DATABASE_URL` and `--db` workflows keep working.

### Expected Outcome
- `am mcp stdio` with no flags persists to `$XDG_DATA_HOME/am/clio.db` (falling back to `~/.local/share/am/clio.db`).
- `AM_DATA_DIR=/tmp/test am mcp stdio` persists to `/tmp/test/clio.db`.
- `DATABASE_URL=postgres://... am mcp stdio` opens Postgres without `--db` (backend inferred from the scheme).
- `am mcp stdio --db ./x.db` and `--backend` still win over every environment variable.
- The parent directory is created automatically on first open (already implemented; confirmed by test).
- `am mcp stdio --help` and `am help` show the resolved default path, and the config system reports the same default the CLI uses.
- `sqlite::memory:` remains available only when explicitly requested.

### Parent Requirement
`requirement.md` — §4.9.5.E (effective configuration and profiles), FR-32, §4.9.2 (no schema change). Gap source: `gap/default-sqlite.md`. Operator decision: implement the full precedence chain (`--db` > `DATABASE_URL`/`AM_DATABASE_URL` > `AM_DATA_DIR` > XDG default), not the CLI-fallback-only version.

### Design References (non-trivial, validated)
- **XDG Base Directory Specification** — user data belongs under `$XDG_DATA_HOME` (default `~/.local/share`); the file lives under an application subdirectory.
- **Twelve-Factor “config in the environment”** — env vars are the portable override; the default must require none.

---

## 2. Scope Boundaries

### In Scope
- One shared, injectable default-path and precedence resolver used by the CLI and by config defaults.
- Backend inference from the database URL scheme when `--backend` is omitted.
- Config defaults agreeing with the CLI default (`store.database_url` / `store.sqlite_path`).
- `am mcp stdio --help` (and `am help`) showing the default path.
- README quick start and `.env.example` alignment.

### Explicitly Out of Scope
- Changing `EMBEDDING_DIMS`, the vector DDL, or any storage schema.
- A setup wizard or config-file writer (Phase 100330).
- Windows path conventions beyond the documented `HOME` fallback.
- Changing the retention-profile file resolution or the deployment-overlay resolution (separate paths).
- Migrating existing databases or moving user data.

### Must Not Change
- An explicit `--db` value always wins; behavior for existing `--db` users is unchanged.
- `sqlite::memory:` still opens a volatile store when explicitly requested.
- `AM_DATA_DIR` does not affect the deployment/retention config file locations.
- Postgres open behavior and its `DATABASE_URL` handling in tests/Makefile (`db_url.rs` default) are unchanged when neither `--db` nor `DATABASE_URL` is set for the MCP path in a Compose context (documented below).

### Scope Expansion Rule
If work outside this scope appears necessary: stop, document the reason, request clarification or approval, and do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- Phase 100020 (dual backend) accepted: `SqliteStore::open` and `PostgresStore::open` exist behind the backend selector.
- `ensure_parent` already creates the DB parent directory (`crates/clio-store/src/sqlite_path.rs`, verified).

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| Shared resolver location | A crate both `clio-lib` and `clio-config` depend on (or `clio-config`, which `clio-lib` depends on) | Import compiles in both |
| Effective config `store.database_url` | Allowlisted and mergeable | `validate.rs` allowlist test |
| `HOME`/`XDG_DATA_HOME` | Read via an injectable lookup for tests | Unit tests with injected env |

---

## 4. Existing-System Discovery

The agent MUST re-verify the following; the facts below were confirmed at plan time.

### Required Discovery
- Trace how `am mcp stdio` and `am mcp http` choose `database_url` and `backend`, and whether any config/env layer participates.
- Trace how `am ops *` opens its store (it must use the same resolver).
- Confirm whether config `store.database_url` / `store.sqlite_path` are consumed by the runtime, and what their defaults are.
- Confirm directory auto-creation exists and where.
- Identify existing tests that assert the `sqlite::memory:` default.

### Discovery Output
- **CLI default is volatile.** `clio-lib/src/main.rs::mcp_options` (lines ~116-134) defaults `database_url` to `"sqlite::memory:"` and `backend` to `"sqlite"`; it reads only `--db`, `--backend`, `--bank`, and `--shared-bank`. It never consults `DATABASE_URL`, `AM_DATABASE_URL`, `AM_DATA_DIR`, or config. This is the zero-config failure the gap reports, and the silent-sqlite trap for Postgres users.
- **Config already knows the env vars but the runtime does not read them.** `clio-config/src/config/mod.rs::apply_process_env` maps `DATABASE_URL`/`AM_DATABASE_URL` into `store.database_url`, and `validate.rs` allowlists `store.database_url` and `store.sqlite_path`. But `McpState::open` receives `McpOpenOptions` built solely from CLI flags, so the config value is inert for store opening.
- **Config default is a relative path.** `clio-config/src/config/merge.rs::system_defaults_json` sets `"sqlite_path": "./data/clio.db"` and `"database_url": ""`. A static JSON default cannot compute `$HOME`, so agreement requires the resolver.
- **Parent-directory creation already exists.** `SqliteStore::open` calls `ensure_parent` (`clio-store/src/sqlite.rs:28`), which `create_dir_all`s the parent and has tests. Gap item 3 is already satisfied; do not duplicate it.
- **No XDG/`AM_DATA_DIR` code exists.** Repository search for `AM_DATA_DIR`, `XDG_DATA_HOME`, `.local/share`, and `data_dir` returns nothing.
- **`--help` is top-level only.** `print_help` is reached from `am help`; `mcp stdio --help` currently parses `--help` as a flag and proceeds, so the default path is not shown for the subcommand.
- **Backend selector expects a string.** `McpOpenOptions.backend` is `"sqlite"`/`"postgres"`; unknown values fail with `OutOfRange`. Scheme inference must map `postgres://`/`postgresql://` to `postgres` and everything else to `sqlite`.
- **Test/CI Postgres path.** `clio-store/src/db_url.rs` defaults to a local Compose Postgres URL for tests; the Makefile exports `DATABASE_URL`. The new precedence must not break those suites.

### Repository Adaptation Rule
The agent must determine the concrete implementation locations from the actual repository. The plan does not prescribe file paths, class names, module names, or directory structures unless they are an externally required contract.

---

## 5. Implementation Specification

### Task 1: Shared Default-Path and Precedence Resolver

#### Intent
Give the CLI and config one function that decides the database target, so they can never disagree.

#### Required Capability or Behavior
- Resolution order, first match wins:
  1. explicit `--db` value;
  2. `DATABASE_URL`, else `AM_DATABASE_URL`;
  3. `AM_DATA_DIR` (non-empty after trim) → `<dir>/clio.db`;
  4. `XDG_DATA_HOME` (non-empty) → `<dir>/am/clio.db`;
  5. `HOME` → `<home>/.local/share/am/clio.db`;
  6. last-resort relative `clio.db` (documented).
- The resolver returns the URL string and the inferred backend (`postgres` for `postgres://`/`postgresql://`, else `sqlite`), unless an explicit `--backend` overrides the inference.
- Path joins do not produce double slashes; trailing separators are handled.
- The resolver takes an injectable environment lookup so tests need not mutate process globals.

#### Architectural Responsibility
One module in a shared location (the config crate is the natural owner since both `clio-lib` and `clio-config` can use it). No second copy of this logic in the CLI.

#### Required Changes
1. Add the resolver and its backend-inference helper.
2. Replace the `"sqlite::memory:"` fallback in `mcp_options` with the resolver; keep `--backend` precedence over inference.
3. Route every store-opening CLI command (`am mcp stdio`, `am mcp http`, `am ops *`) through the resolver.
4. Preserve explicit `sqlite::memory:` (value passes through untouched).

#### Implementation Constraints
- Pure resolution: no filesystem I/O in the resolver itself (store open owns directory creation).
- Injectability is mandatory so coverage is one code path.
- No new dependency for path handling.

#### Expected Result
Unit tests prove each precedence tier and the inference rule without touching the real environment.

### Task 2: Config Agreement

#### Intent
Make `config_get` and the CLI report the same default so a user cannot see one path in config and get another on disk.

#### Required Capability or Behavior
- The effective config's `store.database_url`/`store.sqlite_path` default reflects the resolver outcome rather than the hardcoded `./data/clio.db`.
- An explicitly configured `store.database_url` still wins over the default for config views, and the CLI still treats a config value as lower precedence than `DATABASE_URL` (documented order).
- An empty `store.database_url` is allowed as the “unset” state; validation must not reject the default.

#### Architectural Responsibility
`clio-config` merge/defaults, consuming the Task 1 resolver.

#### Required Changes
1. Derive the system default from the resolver at runtime-construction time (static JSON cannot compute `HOME`).
2. Keep `store.sqlite_path` validation for explicitly set values; do not break existing tests that set it.
3. Document the precedence in one place referenced by both the CLI help and the config docs.

#### Implementation Constraints
- Do not store a machine-specific absolute path in any committed file.
- Do not change resolution of the deployment/retention config files.

#### Expected Result
`am mcp stdio` and `config_get` agree on the default database location on the same machine.

### Task 3: Subcommand Help and Documentation

#### Intent
Make the default discoverable and remove the `--db`-every-time ritual from the docs.

#### Required Capability or Behavior
- `am mcp stdio --help`, `am mcp http --help`, and `am help` show the resolved default database path and the precedence order.
- README quick start becomes `make install` then `am mcp stdio`, stating the database location with no flags, no config file, no env vars.
- `.env.example` documents `AM_DATA_DIR` and that `DATABASE_URL` is honored by the CLI.

#### Required Changes
1. Add per-subcommand help handling for the MCP commands (and ops if cheap).
2. Update README quick start and the SQLite alternative note.
3. Update `.env.example` comments.

#### Implementation Constraints
- Help output must not print resolved secrets or the full effective config.
- Help must not require opening the database or a network.

#### Expected Result
A reader learns the default path from `--help` and the README.

### Implementation Freedom
The agent may choose concrete structure, naming, and internal design provided the required behavior is satisfied, architectural boundaries respected, existing contracts preserved, all acceptance criteria pass, and no prohibited changes are introduced.

---

## 6. Agent Execution Rules

### Allowed Actions
- Add or modify resolver, CLI option construction, config defaults, help text, and docs; add or update tests.
- Refactor locally to route all store-opening commands through one resolver.

### Forbidden Actions
- Change `EMBEDDING_DIMS`, the vector DDL, or any storage schema.
- Remove `sqlite::memory:` support; change explicit `--db` behavior; add a setup wizard or config writer (Phase 100330).
- Delete or bypass tests; disable security controls; add dependencies; commit secrets; claim completion without evidence.

### Agent Decision Boundary
The agent may decide resolver placement, exact error text, and test organization. The agent must request approval for: changing the precedence order, changing the last-resort relative fallback, or any change affecting Phase 100330's config-writer assumptions.

### Mandatory Stop Conditions
Stop and report if repository facts contradict the plan, the shared resolver cannot live in a common crate without a dependency cycle, a destructive data operation appears necessary, or correctness cannot be verified.

---

## 7. Security Constraints

### Required Controls
- The resolver treats env values as untrusted input: trim, reject empty, and reject embedded NULs before constructing a path.
- An `AM_DATA_DIR` that resolves to a non-directory (a file) fails closed with a clear error rather than writing elsewhere.
- The database file is created with the process default permissions; no world-writable directory is created.

### Sensitive Data Rules
- Never print the full `DATABASE_URL` including credentials; help and errors print the scheme/host and mask userinfo.
- No secrets are written by this phase (it writes no config files).

### Security Acceptance Conditions
- A malformed `AM_DATA_DIR` fails closed.
- Help output never echoes a credential-bearing `DATABASE_URL`.

---

## 8. Test and Verification Strategy

### Required Tests
- [x] Unit tests (each precedence tier, inference, trailing-slash handling, empty-value rejection) — `crates/clio-config/src/db_path_tests.rs` (17 tests)
- [x] Integration tests (open a real file DB at the resolved default in a temp `HOME`; auto-create parent; reopen sees prior data) — `crates/clio-lib/tests/default_db_path_test.rs` T100310-01…T100310-03
- [x] Contract tests (explicit `--db` and `--backend` still win; `sqlite::memory:` still volatile) — T100310-05, T100310-06, T100310-07 plus `main_tests::memory_value_stays_volatile`
- [x] End-to-end tests (stdio server started with no flags persists across restarts in a temp data dir) — T100310-01 (spawn `am mcp stdio`, write a row, reopen, `am ops diagnose`)
- [x] Regression tests (existing mcp/ops suites green) — full workspace suite in `make coverage`
- [x] Security tests (malformed `AM_DATA_DIR` fails closed; help does not leak credentials) — T100310-09, `main_tests::database_help_block_masks_credentials`
- [x] Failure-mode tests (unwritable directory gives a clear error) — T100310-09 (file-in-place-of-directory names the path)

### Required Test Scenarios
| Test ID | Scenario | Expected Result |
|---------|----------|-----------------|
| T100310-01 | No flags, temp `HOME` | Resolves to `<home>/.local/share/am/clio.db`; file created; data persists across reopen |
| T100310-02 | `AM_DATA_DIR` set | Resolves to `<dir>/clio.db`; parent auto-created |
| T100310-03 | `XDG_DATA_HOME` set | Resolves under it |
| T100310-04 | `DATABASE_URL=postgres://...` | Backend inferred `postgres`; no sqlite file created |
| T100310-05 | `--db` plus env | `--db` wins |
| T100310-06 | `--backend` plus inferred scheme | Explicit backend wins |
| T100310-07 | `--db sqlite::memory:` | Volatile; nothing written |
| T100310-08 | `am mcp stdio --help` | Prints resolved default path |
| T100310-09 | Malformed `AM_DATA_DIR` (points at a file) | Clear fail-closed error |
| T100310-10 | `config_get` default vs CLI default | Same path on the same machine |

### Negative Testing
Verify empty/whitespace env values are ignored, a file-in-place-of-directory fails closed, unavailable directories error clearly, existing `--db` behavior is intact, and no partial database is left in an invalid state on failure.

### Verification Rule
Implementation claims must be supported by actual test output, inspection results, or other concrete evidence.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence | Result |
|-------|----------------------|---------------------|-------------------|--------|
| AC-100310-01 | No-flag `am mcp stdio` persists to the XDG default | T100310-01 | Test output: file created; data survives restart | PASS — `t31_01_no_flags_persists_to_xdg_default` spawns `am mcp stdio` with only `HOME=<temp>`; `~/.local/share/am/clio.db` is created, a memory row is written and read back through a reopened `SqliteStore`, and a second process (`am ops diagnose`) opens the same file with exit 0 |
| AC-100310-02 | `AM_DATA_DIR` and `XDG_DATA_HOME` overrides honored | T100310-02, T100310-03 | Test output | PASS — `t31_02_am_data_dir_override_creates_parent` (nested `<dir>/clio.db`, parent auto-created) and `t31_03_xdg_data_home_override` (`<xdg>/am/clio.db`) both create the file; unit tiers in `db_path_tests` |
| AC-100310-03 | `DATABASE_URL` opens Postgres with inferred backend | T100310-04 | Test output | PASS — `t31_04_database_url_infers_postgres_backend` runs `am ops diagnose` with the Compose URL and no `--db`/`--backend`: exit 0 (Postgres reached) and no SQLite file created |
| AC-100310-04 | `--db` and `--backend` win; `sqlite::memory:` preserved | T100310-05, T100310-06, T100310-07 | Test output | PASS — `t31_05_db_flag_wins_over_env_url` (bogus `DATABASE_URL`, `--db sqlite::memory:`, exit 0), `t31_06_explicit_backend_and_db_win` (explicit file created), `t31_07_memory_db_stays_volatile` (no file under `HOME`); resolver unit tiers cover explicit-backend-over-inference |
| AC-100310-05 | Parent directory auto-created | T100310-01, T100310-02 | Test output (reuses existing `ensure_parent`) | PASS — T100310-02 uses a two-level missing path (`nested/data`) and the file appears after a no-flag start |
| AC-100310-06 | Help shows the default; config and CLI agree | T100310-08, T100310-10 | Help transcript; config sample | PASS — `t31_08_help_shows_default_without_opening_the_db` asserts `am mcp stdio --help`, `am mcp http --help`, and `am help` each print the resolved path and the precedence line with no DB file created; `db_agreement_tests` proves `config_get("store.sqlite_path")` equals the CLI resolver default, and (r1 remediation) that the effective `backend` follows the same resolver: `postgres` when `DATABASE_URL` is a Postgres URL, with an explicit `AM_BACKEND` still winning |
| AC-100310-07 | No regression in existing suites | Full workspace suite | Test output | PASS — `make coverage` (workspace, `--locked`) green; the only test edits were hermetic fixtures (explicit `--db sqlite::memory:` on two HTTP-bind tests and the stdio EOF test) |
| AC-100310-08 | Malformed data dir fails closed without credential leakage | T100310-09, help inspection | Test output | PASS — `t31_09_data_dir_that_is_a_file_fails_closed` asserts non-zero exit and that the error names the offending path; `database_help_block_masks_credentials` asserts a credential-bearing `DATABASE_URL` prints as `postgres://***@host/db` with no password |

### Definition of Done
- [x] All in-scope behavior implemented. One shared resolver (`clio-config::db_path`) serves the CLI and config defaults; backend inference, config agreement, per-subcommand help, README, and `.env.example` are done.
- [x] All acceptance criteria pass. AC-100310-01…AC-100310-08 each carry a concrete result in the table above.
- [x] Required tests pass. Unit (`crates/clio-config/src/db_path_tests.rs`), integration (`crates/clio-lib/tests/default_db_path_test.rs`), contract, security, and failure-mode tests are green; the full workspace suite is green under `make coverage`.
- [x] No unauthorized changes introduced. No schema, `EMBEDDING_DIMS`, vector DDL, or `sqlite::memory:` behavior changed; no setup wizard/config writer added.
- [x] Existing behavior remains intact. Explicit `--db` and `--backend` still win; `sqlite::memory:` is still volatile; `db_url.rs` and the deployment/retention config paths are untouched. The only test edits are hermetic fixtures (explicit `--db sqlite::memory:` on the stdio-EOF and HTTP-bind tests).
- [x] Security checks pass. Malformed `AM_DATA_DIR` fails closed naming the path; help masks URL userinfo; env values are trimmed and empty/whitespace/NUL values fall through.
- [x] Documentation updated. README quick start and `.env.example`.
- [x] Evidence collected and verification completed. See "Completion Evidence" below.
- [x] Required approval obtained. No decision-boundary approval was needed (precedence order, last-resort fallback, and Phase 100330 assumptions are unchanged).
- [x] Required approval is obtained (downstream pipeline step).

### Completion Evidence

**Implementation summary.** Added `crates/clio-config/src/db_path.rs`: one pure, injectable resolver that returns `ResolvedDatabase { url, backend }`. Precedence is `--db` (passes through untouched, including `sqlite::memory:`) > `DATABASE_URL` / `AM_DATABASE_URL` > `AM_DATA_DIR` > `XDG_DATA_HOME` > `HOME` > relative `clio.db`; the backend is explicit when given, else inferred (`postgres://` / `postgresql://` → `postgres`, everything else → `sqlite`). Path joins use `PathBuf::join`, so trailing separators never produce double slashes. Empty, whitespace, and NUL-bearing values are skipped. The resolver performs no filesystem I/O.

**Changed components.**
- `crates/clio-config/src/db_path.rs` (new) + `db_path_tests.rs` (new, 17 tests) + re-exports in `lib.rs`.
- `crates/clio-config/src/config/merge.rs`: `system_defaults(get)` now derives `store.database_url` and `store.sqlite_path` from the resolver instead of the hardcoded `./data/clio.db`.
- `crates/clio-config/src/config/mod.rs`: `Runtime::with_env` plus a shared `boot_with`/`finish_boot(get)`; removed `Runtime::reload_env_overlay` so one injectable lookup drives defaults and the env overlay. New `config/db_agreement_tests.rs`.
- `crates/clio-lib/src/main.rs`: `mcp_options_with` routes both MCP transports through the resolver; per-subcommand `--help` for `mcp stdio` / `mcp http` plus a shared `database_help_block` that masks credentials; `mcp_stdio_serve` and `http_config` split out as testable seams. Inline tests moved to `src/main_tests.rs`.
- `crates/clio-lib/src/ops_cli.rs`: every `am ops` command opens its store through the resolver; `am ops --help` added. Inline tests moved to `src/ops_cli_tests.rs`.
- `crates/clio-store/src/sqlite_path.rs`: the parent-directory failure now names the offending path.
- `crates/clio-lib/tests/default_db_path_test.rs` (new): end-to-end process tests.
- `README.md`, `.env.example`: zero-config quick start, default location, precedence, `AM_DATA_DIR`.

**Test execution output.** `cargo test --locked -p clio-config -p clio-store -p clio` with `DATABASE_URL=postgres://clio:clio@127.0.0.1:34310/clio`: all suites `ok` (clio-config 136, clio-store 235, clio-lib binary 48 + `default_db_path_test` 9, plus the other clio-lib harnesses), 0 failed. `default_db_path_test`: `test result: ok. 9 passed; 0 failed`. `cargo clippy --workspace --all-targets --all-features --locked -- -D warnings` clean.

**Help transcript** (`am mcp stdio --help`, `HOME=/tmp/…`, no DB file created):

```
am mcp stdio [--db PATH] [--backend sqlite|postgres] [--bank BANK]

Database (no flags or config file needed):
  default:    /tmp/…/.local/share/am/clio.db  (backend: sqlite)
  precedence: --db > DATABASE_URL / AM_DATABASE_URL > AM_DATA_DIR > XDG_DATA_HOME > HOME > ./clio.db
  env:        AM_DATA_DIR names the directory; the resolver appends clio.db
```

With `DATABASE_URL=postgres://user:s3cret@127.0.0.1:5432/am` the default line prints `postgres://***@127.0.0.1:5432/am` (asserted by `database_help_block_masks_credentials`).

**Masked config sample.** `config_get("store.sqlite_path")` returns the unmodified resolved path (not a secret key); with no relevant env and `HOME=/tmp/am-t31-10-home` it equals `/tmp/am-t31-10-home/.local/share/am/clio.db`, identical to the CLI resolver output. `store.database_url` is masked by the existing secret masker in `config_get` output (it matches the `database_url` secret marker).

**Verification report.** Final `make coverage` (workspace, `--locked`, `--fail-under-lines 90 --fail-under-functions 90`) — TOTAL **lines 97.92%** (36821 covered / 765 missed) and **functions 98.95%** (3132 / 33 missed); all **262** reported per-file rows are at or above 90% on both metrics, and the gate exited 0. Baseline for comparison was 97.89% lines / 98.92% functions. The intermediate full-gate diagnostic exposed `clio-lib/src/main.rs` at 88.27% lines after the inline test module was extracted; testable seams (`mcp_stdio_serve`, `http_config`) plus new failure-path tests raised it to 97.09% lines / 100% functions (scoped `cargo llvm-cov --package clio` re-read).

**Round 1 remediation.** The adversary found the effective config still reported `backend: sqlite` when `DATABASE_URL` was a Postgres URL, because `system_defaults` hardcoded the backend while the URL came from the shared resolver. Fixed by deriving `backend` from the same `resolve_database` result in `crates/clio-config/src/config/merge.rs`; an explicit `AM_BACKEND` still wins through the env overlay. Two `config/db_agreement_tests` assertions now pin the agreement. Also fixed in r1: 60 stray `crates/clio-lib/*.profraw` coverage dumps (deleted; `*.profraw` added to `.gitignore`; the integration test helper now forwards the inherited `LLVM_PROFILE_FILE` so instrumented child processes dump into the gitignored `target/` directory) and the missing AGENTS.md header on `crates/clio-config/src/db_path_tests.rs`.

**Known limitations.** See §12: the CLI resolver does not read the config file (Phase 100330 owns wiring it in); relative last-resort fallback; Windows `HOME`-only; `DATABASE_URL` over `AM_DATA_DIR`; dense retrieval unwired (Phase 100350).

---

## 10. Failure Handling and Recovery

### Expected Failure Modes
| Failure | Detection | Recovery |
|---------|-----------|----------|
| Data dir not writable | Store-open error | Clear message naming the path; no fallback to a different location |
| `AM_DATA_DIR` is a file | Resolver/open check | Fail closed with guidance |
| Env value empty/whitespace | Resolver | Ignore and fall through to the next tier |
| Config and CLI disagree | Test T100310-10 | Resolution derives from one shared function |

### Rollback Strategy
Pass an explicit `--db` or `DATABASE_URL` to bypass the default; reverting the resolver restores the previous `sqlite::memory:` fallback. No stored data is modified by this phase.

### Partial Completion Policy
Do not claim completion if only the CLI fallback is changed without config agreement, or vice versa. Record completed and incomplete work separately and document remaining work.

---

## 11. Traceability

| Parent Requirement | Implementation Task | Verification | Acceptance Criterion |
|--------------------|---------------------|--------------|-----------------------|
| §4.9.5.E / FR-32 (effective config consistency) | Task 2 | T100310-10 | AC-100310-06 |
| P2 “new memories are queryable/durable” usability prerequisite | Task 1 | T100310-01 | AC-100310-01 |
| `gap/default-sqlite.md` items 1, 2, 4, 5 | Tasks 1–3 | T100310-01…T100310-10 | AC-100310-01…AC-100310-08 |
| NFR-6 / secret hygiene | Task 3 | Help inspection | AC-100310-08 |

Required chain:

```text
Requirement → Capability → Implementation → Test → Evidence
```

---

## 12. Phase Exit Contract

### Outputs Produced
- One shared database-path/precedence resolver with backend inference.
- CLI commands and config defaults that agree on the default path.
- Subcommand help and docs stating the default and the precedence.

### Guarantees Provided to Downstream Phases
- Phase 100330 (`am setup`) can assume `am mcp stdio` works with no flags against a real file database.
- Phase 100330 config writes are honored by config consumers (`config_get`, `StoreOpenOptions::from_effective`) and by the default the CLI reports for this machine. They remain lower precedence than the CLI flag and every environment tier the CLI resolver reads (see the first known limitation).

### Known Limitations
- The CLI resolver reads `--db` and the process environment only; it does not read the effective config file. A `store.database_url` written only to config changes what `config_get` reports, but not which database `am mcp stdio` / `am ops` open; an environment variable or `--db` still overrides it. Wiring config values into the CLI open path is Phase 100330's responsibility.
- Last-resort fallback when neither `HOME`, `XDG_DATA_HOME`, nor `AM_DATA_DIR` is available is a relative `clio.db` (documented, not promoted).
- Windows uses the `HOME` fallback only; no `%APPDATA%` handling ships.
- The precedence places `DATABASE_URL` above `AM_DATA_DIR`; a user who sets both gets Postgres. This is intentional and documented.
- Dense retrieval remains unwired into the MCP write path (Phase 100350 known limitation), so a persisted database still relies on lexical retrieval unless the ops reindex path is used.

### Downstream Prerequisites
- Phase 100330 relies on the precedence order to decide where it writes configuration and which values it reports as already configured.

### Final Status
PASS WITH DOCUMENTED LIMITATIONS

### Verification Sign-Off
- Implementer: OpenCode CLI (Go . Deepseek V4.1 Flash High)
- Verifier: [Adversary r1]
- Human Approver: [none required]
- Date: 2026-09-21

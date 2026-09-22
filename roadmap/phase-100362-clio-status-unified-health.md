# Phase 100362: Unified Read-Only `clio status` Health Command

### Attribution
Rounds below record plan authorship; implementation sign-off is in §12.
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | OpenCode CLI (Go . Deepseek V4.1 Flash High) | done |
| Adversary | r1 | Antigravity CLI (Gemini 3.8 Flash) | done |
| Remediator | r1 | OpenCode CLI (Go . Deepseek V4.1 Flash High) | done |
| Remedy Approver | r1 | Antigravity CLI (Gemini 3.8 Flash) | approved |
| Finalize | r1 | OpenCode CLI (Together . GLM-5.3 Flash High) | done |

**Follow-up phase 100362 · **Effort:** ~1 day · **Gap:** `gaps/am-status.md` (unified health surface)

## 1. Objective

### Goal
Add one read-only `clio status` command that answers "is my stack alive" in a single shot: setup type and deployment-config path, the resolved DB backend plus a redacted URL, HTTP listeners found in the `34300-34309` range, Compose service state, and a `diagnose ok/no` summary.

### Expected Outcome
- `clio status` exits 0 on a healthy stack and 1 on a degraded one, and prints one structured report.
- Every secret-bearing field (DB URL userinfo, config secrets) is masked; the report never echoes credentials.
- No `clio mcp stdio status` exists; `stdio` stays a client-owned child.
- The command never writes: no repair, no migration, no config change.

### Parent Requirement
`gaps/am-status.md`; `requirement.md` FR-30 (operator surface, exit-code contract), FR-32 (masked config views), NFR-6 (no plaintext secrets). CLI dispatch entry is `crates/clio-lib/src/main.rs:43`.

### Design References
- `clio_ops::diagnose` returns `DiagnoseReport` (`crates/clio-ops/src/diagnose.rs:47`, entry at `:86`) with `ok`, `backend_reachable`, `schema_version`, `banks`, index counts, and `findings`.
- `clio_config::db_path::resolve_database` is the single precedence resolver (`crates/clio-config/src/db_path.rs`): `--db` > `DATABASE_URL`/`CLIO_DATABASE_URL` > `CLIO_DATA_DIR` > `XDG_DATA_HOME` > `HOME`.
- `clio_ops::redact_credentials` strips URL userinfo (`crates/clio-ops/src/finding.rs:177`); `clio_config::secret::{masked_clone, mask_secret}` mask secret trees (`crates/clio-config/src/secret.rs`).
- `clio-lib::compose_docker::probe` and `DockerRunner` (`crates/clio-lib/src/compose_docker.rs:65,99`) are the existing Docker invocation seam; `capture` returns `(exit_code, text)`.
- `clio_config::Runtime` exposes deployment-overlay accessors (`deployment_field`, `set_deployment_path`; see `crates/clio-lib/src/setup_config.rs:68,123`) — confirm the path getter used for display.

---

## 2. Scope Boundaries

### In Scope
- A new top-level `clio status` subcommand and its dispatch branch.
- Aggregation of: install/setup type + deployment-config path; resolved DB backend + redacted URL; `34300-34309` listener scan; Compose service state via `docker compose ps`; `diagnose ok/no`.
- A bounded TCP port-scan helper over `127.0.0.1:34300-34309`.
- `--output json|text` consistent with the CLI output contract introduced in Phase 100366, and the documented exit codes (0 healthy, 1 degraded, 2 usage).

### Explicitly Out of Scope
- `clio mcp stdio status`: stdio is a client-owned child with no port or pid registry; it stays out.
- Any mutating action; `doctor`/`repair` remain the only repair path.
- Changing the `34310-34313` Compose sidecar ports or the `34300-34309` range Phase 100364 selects.
- A new Docker SDK or any new dependency; the scan uses `std::net`.

### Must Not Change
- `doctor` never mutates; `stdio` framing purity (stdout carries only protocol data).
- The DB precedence chain and backend inference (`db_path`).
- Compose port assignments and service allowlist.

### Scope Expansion Rule
If work outside this scope appears necessary: stop, document the reason, request clarification or approval, and do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- Phases 100310 (DB resolver), 100320 (compose lifecycle), 100230 (ops diagnose) landed.
- The CLI output/exit-code contract exists or is introduced by Phase 100366; if 100366 is not yet done, `status` uses its own minimal `--output` rendering and is reconciled when 100366 lands.

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| `clio_ops::diagnose` | Callable against an open store | `crates/clio-ops/src/diagnose.rs` |
| DB resolver | Shared precedence + redaction | `clio_config::db_path::resolve_database` |
| Compose runner seam | `capture` available for `ps` | `crates/clio-lib/src/compose_docker.rs` |
| Deployment config | A readable path getter on `Runtime` | `crates/clio-config/src/config/` |

---

## 4. Existing-System Discovery

The agent MUST re-verify the following; the facts below were confirmed at plan time.

### Required Discovery
- Confirm `main.rs` dispatch has no `status` branch and where it attaches.
- Confirm the `DiagnoseReport` shape and how `ops diagnose` maps to exit codes (`crates/clio-lib/src/ops_cli.rs:36`).
- Confirm the deployment-config path getter on `Runtime` and how "setup type" is represented in the overlay.
- Confirm whether `compose_docker` already has a `ps`/state call or only `probe`.
- Confirm there is no existing port-scan helper to reuse.
- Confirm masking/redaction entry points to reuse rather than re-implement.

### Discovery Output
- **No `status` today.** `crates/clio-lib/src/main.rs:43` dispatches only `version|health|help|mcp|ops|retention|compose|setup`; `print_help` (`:266`) has no status row.
- **Diagnose is the health source.** `DiagnoseReport.ok` and `.backend_reachable` drive a binary healthy/degraded verdict; `ops_cli.rs:165` shows the exit mapping to reuse.
- **One resolver.** `db_path::resolve_database` owns precedence; do not add a second copy.
- **Compose has only a probe.** `compose_docker::probe` (`:99`) checks CLI + daemon; there is no `docker compose ps` capture, so service state is a new (small) call on the existing `DockerRunner` seam.
- **No port scanner.** Repository search finds no `TcpStream` connect loop over a port range; the scan is new and stdlib-only.
- **Masking exists.** `redact_credentials` and `masked_clone`/`mask_secret` are the only masking primitives to reuse.

### Repository Adaptation Rule
The agent must determine concrete implementation locations from the actual repository. The plan does not prescribe file or module names unless they are an externally required contract.

---

## 5. Implementation Specification

### Task 1: Port-Scan Helper

#### Intent
Report which `127.0.0.1:34300-34309` ports have a listener, without assuming ownership.

#### Required Capability or Behavior
- Attempt a short-timeout TCP connect to each port in `34300..=34309`; report the ports that accept.
- Bounded total time; never block indefinitely on a closed host.
- Pure/observable result: a sorted list of listening ports.

#### Architectural Responsibility
CLI support layer inside `clio-lib` (or a small read helper in `clio-ops` if reuse is later needed). No memory semantics.

#### Required Changes
1. Add the scan helper using `std::net::{TcpStream, SocketAddr}` with a short `connect_timeout`.
2. Keep the range a named constant so Phase 100364 shares one definition.

#### Implementation Constraints
- Stdlib only; no new dependency.
- Must not treat a refused connection as an error; "no listener" is a normal result.

#### Expected Result
`status` lists the occupied ports in the range, or an empty list.

### Task 2: Aggregate Report and DB/Config Fields

#### Intent
Assemble the single health view.

#### Required Capability or Behavior
- Resolve the DB target through `db_path::resolve_database`, then present backend + URL with userinfo redacted.
- Present setup/install type and the deployment-config path (or "none").
- Embed the `diagnose` verdict and its findings summary.
- Run the Compose service-state probe tolerantly: absent Docker or a stopped stack degrades to a reported status, never a crash.

#### Architectural Responsibility
`clio-lib` owns assembly and rendering; `clio-ops` owns diagnose; `clio-lib::compose_docker` owns Docker; `clio-config` owns config/DB resolution.

#### Required Changes
1. Add a `status` dispatch branch and a `status` module.
2. Compose the report struct and render `--output json|text`.
3. Map exit codes: 0 healthy, 1 degraded (diagnose not ok or backend unreachable), 2 usage error.
4. Route every error string through the shared redactor and every config view through the masker.

#### Implementation Constraints
- Never write; only read and probe.
- Never print raw credentials; redact before formatting.
- Handle no-deployment-config and no-Docker as first-class states.

#### Expected Result
One command answers the "is my stack alive" question with a masked, structured report.

### Implementation Freedom
The agent may choose module placement, the text-table format, and the service-state call shape, provided the behavior, masking, and non-mutation boundaries are respected.

---

## 6. Agent Execution Rules

### Allowed Actions
- Add the `status` subcommand, helper modules, and tests.
- Extend `DockerRunner` usage with a `ps` capture; update help text.

### Forbidden Actions
- Add a `clio mcp stdio status`; mutate any state; change the DB precedence chain or Compose ports.
- Add dependencies; bypass masking/redaction.

### Agent Decision Boundary
The agent may decide report field names and text layout. The agent must request approval for any change to the exit-code contract or the port range.

### Mandatory Stop Conditions
Stop and report if the deployment-config path accessor is unavailable, if the Compose `ps` call cannot be added without touching unrelated Docker behavior, or if the scan cannot be bounded.

---

## 7. Security Constraints

### Required Controls
- Redact DB URL userinfo via `redact_credentials`; mask any config secret via `masked_clone`/`mask_secret`.
- Read-only: no repair, migration, or config write.
- Bound the port scan in time.

### Sensitive Data Rules
- Never log or print plaintext credentials, tokens, or DEK material.
- Reuse existing masking; do not hand-roll a second rule.

### Security Acceptance Conditions
- A planted secret in config/DB URL is masked in every `status` view (test).
- `status` performs no writes (test asserts store/config unchanged).

---

## 8. Test and Verification Strategy

### Required Tests
- [ ] Unit tests (port scan result, redaction, masking, exit mapping)
- [ ] Integration tests (`status` against an in-memory SQLite store; against no config)
- [ ] Contract tests (exit codes 0/1/2)
- [ ] Failure-mode tests (Docker absent, DB unreachable, all ports free)
- [ ] Regression tests (existing dispatch/help unchanged for other commands)

### Required Test Scenarios

| Test ID | Scenario | Expected Result |
|---------|----------|-----------------|
| T100362-01 | Healthy in-memory store, no Docker | Exit 0; report shows diagnose ok and empty port list |
| T100362-02 | Unreachable Postgres | Exit 1; degraded verdict |
| T100362-03 | A listener bound on 34300 | Port 34300 appears in the list |
| T100362-04 | DB URL with userinfo | Userinfo redacted in output |
| T100362-05 | No deployment config | Report says "none"; exit depends on DB/diagnose only |
| T100362-06 | Docker CLI missing | Service state reported unavailable; no crash |

### Negative Testing
Verify no writes occur, secrets never appear, and a degraded stack still returns a structured report rather than a panic.

### Verification Rule
Implementation claims must be supported by actual command output, not inspection alone.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-100362-01 | One read-only command reports setup, DB, ports, Compose, diagnose | T100362-01…T100362-06 | Command output |
| AC-100362-02 | Secrets masked everywhere | T100362-04 | Output diff |
| AC-100362-03 | Exit codes 0/1/2 | T100362-01, T100362-02 | Command output |
| AC-100362-04 | No writes | T100362-01 inspection | Store/config unchanged check |
| AC-100362-05 | No `stdio status` added | Inspection | Help/dispatch diff |

#### Evidence (actual, 2026-09-22)

| AC ID | Result | Evidence |
|-------|--------|----------|
| AC-100362-01 | PASS | `clio status --backend sqlite --db sqlite::memory:` prints setup/database/ports/compose/diagnose and exits 0; run from the repo root it reports the live stack (`embed=running, extract=running, postgres=running, rerank=running`). Integration test `real_status_against_memory_store_exits_0` exits 0 over the real wiring. |
| AC-100362-02 | PASS | A planted `credentials.embed_api_key=sk-planted-secret-1234567890` renders as `secrets: credentials.embed_api_key=****7890`; grep for the raw secret in the JSON output returns 0 matches. DB URL `postgres://alice:sup3rs3cret@127.0.0.1:1/none` renders `postgres://***@127.0.0.1:1/none`, and its connect failure shows no credentials. |
| AC-100362-03 | PASS | exit 0 (healthy in-memory store), exit 1 (`--backend postgres --db postgres://…@127.0.0.1:1/none`), exit 2 (`--output xml`). Contract tests `healthy_memory_no_docker_exits_0`, `unreachable_postgres_exits_1`, `unknown_output_is_a_usage_error`. |
| AC-100362-04 | PASS | `status_does_not_write_config_or_store` asserts the deployment config bytes and the directory listing are identical before/after a run. `status` opens the store without `reconcile_space` and never writes config. |
| AC-100362-05 | PASS | `clio mcp status` → `unknown mcp command … exit 2`; no `mcp stdio status` dispatch exists. `clio help` shows the new `clio status` row only. |

New source files: `crates/clio-lib/src/status_cli.rs`, `status_report.rs`, `port_scan.rs` (plus three `*_tests.rs` modules) and the `main.rs` dispatch/help rows.

Test scenarios: T100362-01 (`healthy_memory_no_docker_exits_0`), T100362-02 (`unreachable_postgres_exits_1`), T100362-03 (`occupied_port_is_reported`), T100362-04 (`build_setup_masks_secret_and_reports_config`, `ports_and_db_userinfo_are_reported_redacted`), T100362-05 (`build_setup_absent_config_is_none`), T100362-06 (`probe_compose_states_and_failures`).

### Definition of Done
- [x] All in-scope behavior implemented.
- [x] All acceptance criteria pass.
- [x] Required tests pass.
- [x] No unauthorized changes introduced.
- [x] Existing behavior remains intact.
- [x] Security checks pass.
- [x] Documentation updated (CLI help row; phase evidence).
- [x] Evidence collected and verification completed.
- [x] Required approval is obtained (downstream pipeline step).

### Completion Evidence
- Implementation summary: a new top-level `clio status` dispatches to `status_cli::status`. `build` resolves the DB target through `clio_config::db_path::resolve_database` and reports backend + `redact_credentials`-masked URL; reads the deployment-overlay provider shape and masks secret fields with `clio_config::secret::mask_secret`; scans `127.0.0.1:34300-34309` via `port_scan` (stdlib, 150 ms per port); reads Compose state through the existing `DockerRunner::capture` seam using the same `compose_args` shape as `clio compose up|ps`; and embeds `clio_ops::diagnose`. `--output json|text` selects rendering; exit codes are 0 healthy, 1 degraded, 2 usage. `status` opens the store WITHOUT `reconcile_space` and never writes config or repairs.
- Discovered/affected components: `crates/clio-lib/src/main.rs` (module decls, dispatch, help); new `status_cli.rs`, `status_report.rs`, `port_scan.rs`; reused `clio_ops::diagnose` / `redact_credentials`, `clio_config::db_path::resolve_database` / `secret::{mask_secret, path_is_secret}` / `Runtime::deployment_field`, `compose_docker::{compose_args, DockerRunner, ComposeTarget, Stack}` and `compose_env::read_marker`. No `clio-store`, `clio-ops`, or Compose-file changes.
- Test execution output: `cargo test --package clio --bin clio` → 177 passed / 0 failed. `make coverage` → 279 files checked, TOTAL lines 97.91% functions 98.90%, all files meet the 90% per-file floor. New files: `port_scan.rs` 100% / 100%, `main.rs` 100% / 97.75%, `status_cli.rs` 93.33% / 97.69%, `status_report.rs` 92.86% / 98.37% (functions / lines).
- Masking evidence: planted `credentials.embed_api_key=sk-planted-secret-1234567890` → `****7890`; raw-secret grep count 0; `postgres://alice:sup3rs3cret@127.0.0.1:1/none` → `postgres://***@127.0.0.1:1/none`. A store-connect failure produced no credential text.
- Known limitations: see §12. `clio setup` does not persist an install type, so `setup.install_type` is reported as `unrecorded`; Compose state requires Docker + a materialized `compose.yml`.

---

## 10. Failure Handling and Recovery

### Expected Failure Modes
| Failure | Detection | Recovery |
|---------|-----------|----------|
| Store cannot be opened | `resolve_database`/open error | Report degraded; exit 1 |
| Docker absent | Probe error | Report unavailable; continue |
| All ports free | Scan result | Report empty list; not an error |
| Secret leak | Masking test | Fix before claiming completion |

### Rollback Strategy
Remove the `status` branch and module; help text reverts. No data or config is affected.

### Partial Completion Policy
Do not claim completion if the command runs but leaves masking, exit codes, or non-mutation unimplemented. Record each separately.

---

## 11. Traceability

| Parent Requirement | Implementation Task | Verification | Acceptance Criterion |
|--------------------|---------------------|--------------|-----------------------|
| `gaps/am-status.md` | Tasks 1–2 | T100362-01…T100362-06 | AC-100362-01, AC-100362-05 |
| FR-30 (operator surface, exit codes) | Task 2 | T100362-01, T100362-02 | AC-100362-03 |
| FR-32 / NFR-6 (masking) | Task 2 | T100362-04 | AC-100362-02 |
| Non-mutation contract | Task 2 | Inspection | AC-100362-04 |

Required chain:

```text
Gap → Status capability → Aggregation + probe → Command tests → Evidence
```

---

## 12. Phase Exit Contract

### Outputs Produced
- `clio status` unified read-only health command.
- A shared `34300-34309` port-scan helper.

### Guarantees Provided to Downstream Phases
After this phase is accepted:
- A single command reports stack health without mutating anything.
- Phase 100364's auto-bind default range matches the scanned range.

### Known Limitations
- Compose service state depends on Docker being installed and on a materialized `compose.yml` in the compose root (`--dir`/cwd). With no project the report says `not materialized`; absent Docker says `unavailable`.
- "Setup type" display depends on the deployment overlay being readable. `clio setup` writes only provider/credential fields, never the chosen install type, so `status` cannot recover `zero-dependency|airgapped|custom`; it reports `install_type: unrecorded` and shows the knowable provider shape (embed/rerank) plus the deployment-config path. Persisting an install type requires a `clio setup` change and is owed by a future setup/status phase, not this one.
- `status` never creates a database: a nonexistent SQLite path is rejected before the store opener runs, so the command reports degraded (exit 1) and leaves no file on disk. On an existing store it opens through the shared bootstrap path but performs no repair, no `reconcile_space`, and no config write. A genuinely read-only open seam (`SQLITE_OPEN_READONLY`, no bootstrap) is owed by a future store/status phase.
- Phase 100366 has not landed, so `status` uses its own minimal `--output json|text` rendering; reconcile rather than duplicate when the shared output contract arrives.

### Remedy Round r1 (2026-09-22)
Adversary findings F-01…F-04 fixed; all four are closed in the findings report.
- F-01: `open_chosen` now rejects a missing SQLite file (`Path::exists`) before `SqliteStore::open`. Repro after fix: `clio status --backend sqlite --db /tmp/nonexistent-remed-test.db` exits 1 and creates no file.
- F-02: `cargo fmt --all` applied; `cargo fmt --all -- --check` and `make check` exit 0.
- F-03: added `clio_config::Runtime::deployment_keys()`; `build_setup` masks every secret-bearing overlay key discovered from the overlay (planted `extract.token`/`custom.secret` -> `****mnop`/`****7890`, raw-value grep count 0).
- F-04: added `listener_on_contract_port_is_reported` binding the contract port `34300`.
- Deferred: a read-only `Store` open seam in `clio-store` (uses `SQLITE_OPEN_READONLY`, skips bootstrap) — a larger cross-crate change owed by a future store/status phase.
- Verification: `make check` exit 0; `make coverage` exit 0 (279 files, TOTAL lines 97.91% functions 98.87%, all per-file floors met).

### Downstream Prerequisites
- Phase 100366's output contract may supersede the interim rendering; reconcile rather than duplicate.

### Final Status
PASS WITH DOCUMENTED LIMITATIONS

### Verification Sign-Off
- Implementer: OpenCode CLI (Go . Deepseek V4.1 Flash High)
- Verifier: [TBD]
- Human Approver: not required
- Date: 2026-09-22

# Phase 100230: Ops Doctor and Repair

### Attribution
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | OpenCode CLI (Together . GLM-5.3 Flash High) | done |
| Adversary | r1 | OpenCode CLI (OpenRouter . Deepseek V4.1 Flash Max) | done |
| Remediator | r1 | OpenCode CLI (Together . GLM-5.3 Flash High) | done |
| Remedy Approver | r1 | OpenCode CLI (Together . GLM-5.3 Flash Max) | approved |
| Finalize | r1 | OpenCode CLI (Go . Deepseek V4.1 Flash High) | done |

**Index slice 100230 · **Effort:** `1×` · **Scope:** `roadmap/index.md` slice 100230 (authoritative)

### Vocabulary (read first) — zero shared moniker

| Term | Enum / form | Where it lives | Must not |
|------|-------------|----------------|----------|
| **`ops_diagnose`** | Read-only install/DB health snapshot (`diagnose`) | §4.9.5.C | Be confused with **`inspect`** (item listing) or **`hygiene_audit`** |
| **`ops_verify`** | Deeper consistency pass/fail findings (`verify`) | §4.9.5.C | Be confused with **`peer_validate`** (`validate` tool) or **`span_verification`** (Phase 100050) |
| **`doctor_repair_plan`** | Ordered plan composed by `doctor` | Ops planner | Be confused with MemTree **`consolidate`** or hygiene clean plans |
| **`ops_repair`** | Confirmed application of known plan actions (`repair`) | §4.9.5.C | Run unknown actions; alias compliance erase |
| **`ops_reindex`** | Rebuild dense/lexical (and optional MemTree materializations) | Public UX over Phase 100110 rebuild API | Be confused with dirty-path **partial** refresh alone |
| **`ops_finding`** | Structured `{code, severity, scope, message}` | diagnose/verify/doctor output | Include memory plaintext, DEKs, or API keys |

---

## 1. Objective

### Goal
Ship PII-safe operator health surfaces **`diagnose`**, **`verify`**, **`doctor`**, **`repair`**, and **`reindex`** (FR-30, NFR-8, §4.9.5.C): read-only health and consistency checks, an ordered repair plan, confirmation-gated mutation, and non-zero process exit status for failed non-interactive runs.

### Expected Outcome
- `diagnose()` reports backend reachability, schema version, vector index presence, embedding pipeline readiness, bank list, and obvious corruption signals—without memory content.
- `verify()` returns pass/fail `ops_finding`s: referential integrity of snapshot/gist/triple refs, orphan edges, manifest-vs-store drift (when manifests exist), vector coverage vs episodic leaves.
- `doctor(dry_run?)` composes an ordered `doctor_repair_plan` from diagnose+verify; default `dry_run=true` prints plan only.
- `repair(plan_id_or_actions, confirm)` applies only known actions; `confirm=true` required to mutate; refuses unknown actions.
- `reindex(target?, dry_run?)` rebuilds dense and/or lexical indexes (optional MemTree ancestor materializations); dry-run reports scope/cost only.
- CLI/non-interactive: failed `verify`, refused `repair`, or aborted `reindex` exits **non-zero** (NFR-8). Tool bindings return `{ok:false, code, findings}` instead of silent success.
- MCP schemas registered on **stdio and Streamable HTTP** with identical semantics (pinned MCP revision).
- `doctor` never mutates (including `dry_run=false`); only `repair` / `reindex` mutate.

### Parent Requirement
`requirement.md` (v1.9+) — §4.9.5.C, §4.9.7, FR-30, NFR-8; rebuild seam from Phase 100110.

### Design References (non-normative)
- **Separate lint vs repair postures:** [OpenClaw doctor CLI](https://docs.openclaw.ai/cli/doctor) — read-only structured findings for CI; explicit repair/fix mode; threshold-aware non-zero exits; never treat advisory JSON as a silent green gate.
- **Re-verify after repair:** OpenClaw pattern of re-running detect scoped to repaired findings so “fixed” is evidenced, not assumed.
- **Stop writers during destructive maintenance:** compact/migrate/reindex guidance—document when operators must quiesce writers.

---

## 2. Scope Boundaries

### In Scope
- PII-safe `diagnose` / `verify` finding emitters.
- `doctor` planner producing versioned `doctor_repair_plan` ids.
- Confirmation-gated `repair` allowlist of actions (e.g. drop orphan edge, rebuild missing vector row, fix null gist ref policy within documented bounds).
- Public `reindex` UX calling Phase 100110 rebuild APIs with dry-run costing.
- CLI exit-code contract + MCP structured failure objects on **stdio and Streamable HTTP**.
- Post-repair re-verify of targeted findings.

### Explicitly Out of Scope
- Implementing new index algorithms (owned by Phase 100110).
- Hygiene noise cleanup (Phase 100210), export/import (Phase 100220), sync serve (Phase 100240).
- Compliance erase (Phase 100190).
- Interactive TUI beyond minimal confirm flags (unless already present).
- Automatic repair on process start without operator intent.
- Any mutation inside `doctor` (including `dry_run=false`).

### Must Not Change
- Phase 100110 rebuild semantics and backend contracts.
- Admission, supersession, and erase rules.
- PII-safe ops I/O: no memory plaintext in findings.

### Scope Expansion Rule
If work outside this scope appears necessary:
1. Stop.
2. Document the reason.
3. Request clarification or approval.
4. Do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- Phase 100020: dual backends + schema versioning hooks.
- Phase 100110: internal rebuild/reindex API for dense+lexical.
- Phase 100070: MemTree materialization hooks if reindex targets ancestors.
- Phase 100010: CLI/process exit plumbing and structured errors.
- Phase 100220 recommended: manifest counts available for drift checks (if export landed; otherwise skip manifest findings with code `MANIFEST_UNAVAILABLE`).

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| Rebuild API | Dense/lexical rebuild + dry-run counts | Phase 100110 tests |
| Schema version registry | Readable current vs expected | Diagnose field |
| Embedding sidecar health | Optional probe | diagnose embedding_ready |
| Confirm flag plumbing | Shared with discard/hygiene | Reject without confirm |

---

## 4. Existing-System Discovery

### Required Discovery
- Locate Phase 100110 rebuild entrypoints and lag metrics.
- Find CLI command framework and exit-code helpers.
- Inventory integrity constraints already checked in tests.
- Identify secret-masking for any path that might echo config.
- Check whether writers can be detected/quiesced safely.

### Discovery Output
- **Rebuild API.** Phase 100110's derived-index rebuild now lives in `clio-index::rebuild::rebuild(store, index, embedder: Option<&dyn Embedder>, bank, targets, dry_run, confirm) -> RebuildReport`. `IndexCoordinator::rebuild_indexes` delegates to it; the optional embedder lets a lexical-only rebuild run without a sidecar while a dense live run fails closed with `ConfigCorrupt`.
- **Finding code catalog.** `clio-ops::finding::codes`: `BACKEND_UNREACHABLE`, `SCHEMA_VERSION_MISSING`, `SCHEMA_VERSION_MISMATCH`, `VECTOR_INDEX_MISSING`, `EMBEDDING_UNREACHABLE`, `SYSTEM_TABLES_UNREADABLE`, `ORPHAN_ASSOC_EDGE`, `DANGLING_TRIPLE_REF`, `DANGLING_SNAPSHOT_REF`, `DANGLING_GIST_REF`, `ORPHAN_MEMTREE_LEAF`, `DENSE_COVERAGE_GAP`, `LEXICAL_COVERAGE_GAP`, `MANIFEST_UNAVAILABLE`, `UNKNOWN_REPAIR_ACTION`, `CONFIRM_REQUIRED`, `PLAN_NOT_FOUND`, `EMBEDDER_UNAVAILABLE`, `ACTION_FAILED`, `REINDEX_ABORTED`.
- **Repair allowlist.** `drop_orphan_assoc_edge`, `rebuild_dense_index`, `rebuild_lexical_index`.
- **CLI wiring points.** `clio-lib` `main.rs` dispatches `ops` to `ops_cli`; the ops store/index/embedder come from a concrete backend open (`SqliteStore`/`PostgresStore`) plus `clio_mcp::runtime::build_ops_embedder`. Exit codes are documented on `ops_cli::ops`.
- **MCP wiring points.** `clio-mcp` binds the five tools through `ops_tools::dispatch_ops`, routed first in `write_tools::dispatch`; schemas are published by `schema_ops_defs::ops_defs` and registered via `lib::bound_read_tools`/`bound_write_tools` (both transports share these lists).
- **Backend probes.** New `clio_store::OpsStore` (impl for both backends) adds ping, schema version, bank inventory, content-free integrity signal counts, and orphan edge cleanup; `clio_store::SCHEMA_VERSION` is the single expected-version constant.

### Repository Adaptation Rule
Concrete modules come from the repository.

---

## 5. Implementation Specification

### Task 1: `diagnose` Health Snapshot

#### Intent
Fast read-only install/DB snapshot for operators and agents.

#### Required Capability or Behavior
- Probe: backend ping, schema version, vector extension/index presence, embedding endpoint health, bank list, basic corruption signals (e.g. unreadable system tables).
- Output structured JSON safe for logs (no item bodies, no DEKs, masked secrets).

#### Architectural Responsibility
Ops diagnose service.

#### Required Changes
1. Probe adapters per backend.
2. MCP + CLI bindings.
3. Stable field names for automation.

#### Expected Result
Unreachable DB yields `ok:false` finding without stack-trace secret leakage.

---

### Task 2: `verify` Consistency Findings

#### Intent
Deeper pass/fail integrity checks.

#### Required Capability or Behavior
- Checks include: dangling snapshot/gist/triple refs; orphan `assoc_edge` endpoints; vector row coverage vs indexable leaves; optional export-manifest count drift when manifests exist.
- Each `ops_finding` has code, severity (`info|warning|error`), scope, message.
- Aggregate `ok` false if any error-severity finding exists (document warning policy for CLI).

#### Architectural Responsibility
Ops verify engine.

#### Required Changes
1. Checker registry (extensible).
2. Dual-backend SQL/query implementations.
3. CLI non-zero exit when verify fails (NFR-8).

#### Implementation Constraints
- Findings MUST NOT include memory plaintext.
- Name remains `verify` in the tool catalog; internal type `ops_verify` avoids clash with `peer_validate` / span verification in code.

#### Expected Result
Planted orphan edge produces a deterministic finding code.

---

### Task 3: `doctor` Plan Composition

#### Intent
Turn findings into an ordered, reviewable repair plan.

#### Required Capability or Behavior
- Default `dry_run=true`: emit `doctor_repair_plan` only.
- **`doctor` never mutates** under any `dry_run` value. `dry_run=false` only persists/returns a concrete `doctor_repair_plan` id for subsequent `repair`; it MUST NOT apply fixes.
- Plan includes ordered actions with ids, rationale (finding codes), risk notes, and whether downtime/quiesce is recommended.
- Persist plan id for subsequent `repair` OR accept inline action list that must match allowlist.
- Mutations remain exclusively in `repair` / `reindex` with confirmation.

#### Architectural Responsibility
Doctor planner (read-only composer).

#### Expected Result
Operators can review plan before any mutation; `doctor(dry_run=false)` still writes zero store repairs.

---

### Task 4: `repair` Confirmed Execution

#### Intent
Apply only known fixes with confirmation and re-verify.

#### Required Capability or Behavior
- `confirm=true` required to mutate; else refuse or dry-run equivalent.
- Refuse unknown action ids.
- Per-action result: `repaired` | `skipped` | `failed` with reason.
- After successful repairs, re-run targeted `verify` checks; residual findings reported (do not claim silent success).

#### Architectural Responsibility
Repair executor.

#### Implementation Constraints
- No path to `erase_request` or DEK destroy.
- No arbitrary SQL from user input.

#### Expected Result
Unknown action → structured refusal; confirmed known action mutates and re-verifies.

---

### Task 5: `reindex` Public UX

#### Intent
Expose Phase 100110 rebuild as operator tool with dry-run costing.

#### Required Capability or Behavior
- Targets: dense, lexical, both; optional MemTree ancestor materializations; bank or whole store.
- `dry_run=true`: scope + estimated row counts/cost; no writes.
- Mutating reindex requires confirmation equivalent (`confirm` or CLI `--yes` mapped to confirm).
- Aborted/failed non-interactive reindex → non-zero exit.

#### Architectural Responsibility
Reindex facade over rebuild API.

#### Expected Result
Dry-run reports counts; live rebuild restores coverage finding to pass.

---

### Task 6: CLI Exit Contract + Conformance

#### Intent
Satisfy NFR-8 and FR-30 tool failure shapes.

#### Required Capability or Behavior
- Non-interactive failures exit non-zero.
- MCP tools return `{ok:false, code, findings}` on failure.
- Document mapping: verify errors ⇒ exit 1; repair refused ⇒ exit 2 (or single non-zero—document one scheme and test it).

#### Expected Result
CI can gate on `verify` exit status.

---

### Implementation Freedom
Finding code strings, plan persistence medium, and exact exit code map may be chosen if documented and tested.

---

## 6. Agent Execution Rules

### Allowed Actions
- Implement ops diagnose/verify/doctor/repair/reindex facades.
- Extend Phase 100110 rebuild callers.
- Add CLI exit handling and tests.

### Forbidden Actions
- Return memory content in findings.
- Apply unknown repair actions.
- Auto-repair on startup without approval.
- Bypass confirm on mutating repair/reindex.
- Upgrade dependencies without approval.

### Agent Decision Boundary
May decide checker ordering and plan storage.

Must request approval for:
- Destructive repairs that delete large classes of rows beyond orphan cleanup.
- Changing NFR-8 exit semantics after publication.

### Mandatory Stop Conditions
Stop if rebuild API missing, if PII cannot be excluded from findings, or if CLI cannot signal non-zero failure.

---

## 7. Security Constraints

### Required Controls
- PII-safe outputs (§4.9.5.C).
- Confirmation on mutating repair/reindex.
- Allowlisted repair actions only.

### Sensitive Data Rules
- Never log DEKs, API keys, sync secrets, or item snapshots in ops output.

### Security Acceptance Conditions
- Fixture with secrets in memory content never appears in diagnose/verify/doctor output.
- Unauthorized actors cannot repair foreign banks.

---

## 8. Test and Verification Strategy

### Required Tests
- [x] Unit: finding aggregation / ok bit (`clio-ops/src/finding_tests.rs`)
- [x] Integration: planted integrity faults (`clio-ops/src/verify_tests.rs`, `clio-store/src/ops_store_tests.rs`, `clio-store/src/pg_ops_tests.rs`)
- [x] Integration: doctor plan dry-run (`clio-ops/src/doctor_tests.rs`, `clio-mcp/src/ops_tools_tests.rs`)
- [x] Integration: repair confirm gate + re-verify (`clio-ops/src/repair_tests.rs`, `clio-mcp/src/ops_tools_tests.rs`)
- [x] Integration: reindex dry-run vs live (`clio-ops/src/reindex_tests.rs`, `clio-index/src/rebuild_embed_tests.rs`)
- [x] CLI: non-zero exits (NFR-8) (`clio-lib/src/ops_cli.rs` tests)
- [x] Security: PII absence in findings (`clio-mcp/src/ops_tools_tests.rs::ops_output_never_contains_item_content_or_secrets`)

### Required Test Scenarios

| Test ID | Scenario | Expected Result |
|---------|----------|-----------------|
| T100230-01 | DB down | diagnose `ok:false`; no panic secrets |
| T100230-02 | Orphan assoc_edge | verify error finding with stable code |
| T100230-03 | doctor default | Plan only; zero mutations |
| T100230-03b | doctor `dry_run=false` | Plan id persisted/returned; **zero** repair mutations |
| T100230-04 | repair without confirm | Refused; exit non-zero in CLI |
| T100230-05 | repair known action | Finding cleared on re-verify |
| T100230-06 | repair unknown action | Refused |
| T100230-07 | reindex dry-run | Cost report; indexes unchanged |
| T100230-08 | Failed verify in CI mode | Process exit ≠ 0 |

### Negative Testing
Partial repair failure reports failed actions; does not mark plan fully complete.

### Verification Rule
Exit-code and finding claims need captured command output.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-100230-01 | PII-safe diagnose/verify | T100230-01/02 + secret fixture | `ops_output_never_contains_item_content_or_secrets` passes with a `sk-live-…` gist/snapshot item through `diagnose`/`verify`/`doctor`; findings carry codes/counts only. |
| AC-100230-02 | doctor plan dry-run default; never mutates | T100230-03 / T100230-03b | `am ops doctor` emits `dry_run:true`, `plan_id:"plan-1"`, zero registered plans; `doctor_tests` asserts registry length 0 on default and 1 on `dry_run=false` with zero item-row change. |
| AC-100230-03 | Confirmed repair allowlist | T100230-04–06 | `am ops repair --actions drop_orphan_assoc_edge` (no `--confirm`) prints an outcome with `ok:false` and a `CONFIRM_REQUIRED` finding, exit 2; unknown action refused with `UNKNOWN_REPAIR_ACTION`; confirmed orphan drop then a clean `verify`. |
| AC-100230-04 | reindex dry-run + live | T100230-07 + coverage | `am ops reindex` dry-run prints counts with `dense_applied:0`; `clio-ops/src/reindex_tests.rs` + `clio-index/src/rebuild_embed_tests.rs` cover live dense (FakeEmbedder) restoring coverage and live lexical without an embedder. |
| AC-100230-05 | Non-zero CLI on failure | T100230-08 | Captured exit codes: verify failure 1 (`ops_cli_fault_tests::verify_with_planted_fault_exits_1` over a fault-seeded temp SQLite store, plus the live transcript below), repair refused/failed 2, reindex failed 3, success 0 (`ops_cli` tests + manual transcripts). |
| AC-100230-06 | MCP structured failure | Tool test | `verify`/`repair` return `{ok:false, …findings…}` with the finding code; hard errors return `{ok:false, code, message, findings}`; `ops_tools_tests` asserts `forbidden`, `CONFIRM_REQUIRED`, and `config_corrupt` failures. |

### Definition of Done
- [x] All five surfaces shipped.
- [x] NFR-8 verified.
- [x] Files ≤ 450 lines; tests green.
- [x] Required approval is obtained (downstream pipeline step).

### Completion Evidence

**Surfaces.**
- `clio-ops` crate: `diagnose` (health snapshot, never Err), `verify` (integrity + coverage findings with `ok` on error severity), `doctor` (ordered plan + `PlanRegistry`, never mutates the store), `repair` (confirmation gate, allowlist refusal, targeted re-verify), `reindex` (dry-run costing + confirmed live rebuild over `clio-index::rebuild`).
- `clio-store::OpsStore` (SQLite + Postgres): `ping`, `schema_version`, `bank_ids`, `integrity_signals`, `drop_orphan_assoc_edges`; `SCHEMA_VERSION = "8"`.
- `clio-mcp`: five tools bound on the shared read/write lists (both stdio and Streamable HTTP), schema-published, returning `{ok:true,…}` / `{ok:false, code, findings}`.
- `clio-lib`: `am ops diagnose|verify|doctor|repair|reindex` with the documented exit scheme.

**CLI transcripts** (`./target/debug/am`, empty SQLite store):
```
$ am ops diagnose --backend sqlite --db sqlite::memory:            # exit 0
{"ok":true,"backend_reachable":true,"schema_version":"8","expected_schema_version":"8",
 "banks":[],"vector_index_present":true,"indexable_items":0,...,"embedding_ready":null,"findings":[]}

$ am ops verify --backend sqlite --db sqlite::memory:              # exit 0
{"ok":true,"scope":"store","integrity":{...all 0...},"indexable_items":0,...,
 "findings":[{"code":"MANIFEST_UNAVAILABLE","severity":"info","scope":"store",...}]}

$ am ops doctor --backend sqlite --db sqlite::memory:              # exit 0
{"plan_id":"plan-1","dry_run":true,"ok":true,"actions":[],"findings":[...],"notes":["MANIFEST_UNAVAILABLE: ..."]}

$ am ops repair --backend sqlite --db sqlite::memory: --actions drop_orphan_assoc_edge   # exit 2
{"ok":false,"confirmed":false,"results":[],
 "findings":[{"code":"CONFIRM_REQUIRED","severity":"error","scope":"store","message":"repair requires confirm=true to mutate"}]}

$ am ops reindex --backend sqlite --db sqlite::memory: --target bogus                     # exit 3
{"code":"invalid_argument","message":"rebuild targets must be dense|lexical|all, got `bogus`","ok":false}

$ am ops reindex --backend sqlite --db sqlite::memory:             # exit 0
{"ok":true,"target":"all","dry_run":true,"indexable_items":0,"dense_applied":0,"lexical_applied":0,...}
```

**Failing-verify transcript** (orphan `assoc_edges` row planted in a temp-file SQLite store after a clean schema bootstrap):
```
$ am ops verify --backend sqlite --db /tmp/am-fault-verify.sqlite          # exit 1
{"ok":false,"timestamp":"2026-09-20T11:17:36Z","scope":"store",
 "integrity":{"orphan_assoc_edges":1,...},
 "findings":[{"code":"ORPHAN_ASSOC_EDGE","severity":"error","scope":"store",
              "message":"1 association edge(s) reference a missing item"},...]}
```

**MCP structured failure.** `repair` on the disabled shared bank returns `{"ok":false,"code":"forbidden"}`; `verify` with a planted orphan edge returns `{"ok":false,"findings":[{"code":"ORPHAN_ASSOC_EDGE",...}]}`; `reindex --target dense` live without an embedder returns `{"ok":false,"code":"config_corrupt"}` (all in `ops_tools_tests.rs`).

**Coverage (final workspace gate, after r1 remediation).** `cargo llvm-cov --workspace --locked --json --fail-under-lines 90 --fail-under-functions 90` exited 0; TOTAL functions 98.72%, lines 97.86%; **220 reported files, 0 below 90%** on either metric. Touched-file highlights: `clio-ops/src/{finding,repair}.rs` 100/98.51% fn, `clio-index/src/{rebuild,worker}.rs` 100/90.91% fn, `clio-store/src/{sqlite,postgres}_index.rs` 100% fn, `clio-mcp/src/ops_tools.rs` 100% fn, `clio-lib/src/ops_cli.rs` 97.14% fn.

**Commands.** `cargo clippy --workspace --all-targets --all-features --locked -- -D warnings` clean; `cargo test --locked --workspace` green (41 `test result: ok` suites, 0 failures); `cargo fmt --all -- --check` clean.

**Remediation (r1).** Adversary findings addressed: the failed-verify exit-1 path is now tested end-to-end (`ops_cli_fault_tests`) with a captured transcript; one shared credential redactor (`clio_ops::redact_credentials`) is applied at the repair `failed()` choke point, the MCP error envelope, and the CLI error path; orphan cleanup is bank-scoped (`IndexStore::cleanup_orphans(Option<&str>)`) and runs once per reindex call; MCP `reindex` rejects a bank-less scope while the shared bank surface is disabled; rebuild sweeps record embed latency/error through an observing embedder wrapper; the MCP Postgres-open test now takes `clio_store::lock_pg_test()`; the MCP schema bank descriptions match actual behavior (diagnose takes no bank scope).

---

## 10. Failure Handling and Recovery

### Expected Failure Modes

| Failure | Detection | Recovery |
|---------|-----------|----------|
| Rebuild worker crash | reindex error | Non-zero exit; leave prior index; report aborted |
| Plan expired/missing | repair lookup | Refuse; ask to re-run doctor |
| Writer contention | lock/timeout | Fail closed; recommend quiesce |

### Rollback Strategy
Prefer additive fixes. If a repair is unsafe to auto-rollback, document manual recovery steps in the finding.

### Partial Completion Policy
Record which actions repaired vs failed; do not claim full PASS.

---

## 11. Traceability

| Parent Requirement | Implementation Task | Verification | Acceptance Criterion |
|--------------------|---------------------|--------------|-----------------------|
| FR-30 / §4.9.5.C | Tasks 1–5 | T100230-01–07 | AC-100230-01–04 |
| NFR-8 | Task 6 | T100230-08 | AC-100230-05 |
| §4.9.7 | Tasks 1–2 | Secret fixture | AC-100230-01 |

---

## 12. Phase Exit Contract

### Outputs Produced
- `diagnose` / `verify` / `doctor` / `repair` / `reindex`
- Finding code catalog + CLI exit contract
- Confirmed repair allowlist

### Guarantees Provided to Downstream Phases
- Operators can detect and repair index/integrity drift before enabling multi-host sync.
- CI can fail on `verify`.

### Known Limitations
- Not all findings are auto-repairable: dangling triple/snapshot/gist refs and orphan MemTree leaves emit findings plus a manual-repair note and produce no plan action. Why: safely deleting rows that are still referenced needs a data-owner policy this phase does not define. Owner: this phase documents the gap; a later ops phase may add allowlisted cleanup.
- Manifest-vs-store drift is never compared: `verify` emits `MANIFEST_UNAVAILABLE` (info) because the runtime persists no export manifest to compare against. Why: manifests are written by the export bundle (Phase 100220) but not stored where the ops layer can read them. Owner: a later phase that persists export manifests.
- Doctor plan ids are process-local: `am ops doctor` and `am ops repair` are separate processes, so `--plan` does not resolve across invocations; cross-invocation repair uses the inline `--actions` allowlist. Why: the plan persistence medium was left to implementation freedom and no durable plan store exists yet. Owner: this phase (documented and tested as `PLAN_NOT_FOUND`); a later phase may persist plans.
- Optional MemTree ancestor materializations are not implemented: `RebuildTargets` is `dense|lexical|all` only and no ancestor target exists. Why: the phase marked ancestor materialization optional and no surface consumes it yet. Owner: this phase documents the omission; a later phase that consumes MemTree materializations from the ops surface owns the debt.
- Bank-scoped reindex skips no cleanup but scopes it: `cleanup_orphans(Some(bank))` only removes derived rows belonging to that bank, so orphans in other banks are left to a whole-store reindex. Why: a scoped operator action must never mutate data outside its scope. Owner: this phase (covered by `index_store_tests`).

### Downstream Prerequisites
- Phase 100240 may require verify-clean banks before first sync serve in production profiles.

### Final Status
PASS WITH DOCUMENTED LIMITATIONS

### Verification Sign-Off
- Implementer: OpenCode CLI (Together . GLM-5.3 Flash High)
- Remediator: OpenCode CLI (Together . GLM-5.3 Flash High)
- Verifier: [Adversary r1]
- Human Approver: [Name, if required]
- Date: 2026-09-20

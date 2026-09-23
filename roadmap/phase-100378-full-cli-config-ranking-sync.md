# Phase 100378: Full CLI Configuration, Ranking, and Sync Surface

### Attribution
Rounds below record plan authorship; implementation sign-off is in §12.
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | OpenCode CLI (Go . Deepseek V4.1 Flash High) | done |
| Adversary | r1 | Antigravity CLI (Gemini 3.8 Flash) | done |
| Remediator | r1 | OpenCode CLI (Together . GLM-5.3 Flash High) | done |
| Remedy Approver | r1 | OpenCode CLI (OpenRouter . Deepseek V4.1 Flash Max) | approved |
| Finalize | r1 | OpenCode CLI (Together . GLM-5.3 Flash High) | done |

**Follow-up phase 100378 · **Effort:** ~2 days · **Gaps:** `gaps/full-cli.md` §6 (config/ranking and sync have zero CLI surface today)

## 1. Objective

### Goal
Close the last CLI gaps: expose `config_get`/`config_set`/`config_profiles`/`config_profile_apply`, `ranking_env_get`/`ranking_env_set`, and the sync tools (`sync status|push|pull|serve`) on the CLI, with secret masking on every config view and an honest single-host sync story.

### Expected Outcome
- `clio config get [PATH]`, `clio config set PATH VALUE [--scope session|profile|deployment]`, `clio config profiles`, `clio config use NAME`, `clio ranking get`, `clio ranking set ...` run standalone.
- Config views are masked; a planted secret never appears.
- `clio sync status` explains on a single-host deployment that sync is omitted, rather than failing obscurely; multi-host uses the same flags as the tool schema.
- `ranking set` supports `--dry-run` and validates/renormalizes weights.

### Parent Requirement
`gaps/full-cli.md` §6, §8; `requirement.md` FR-32 (effective-config/profile/ranking tools; masked views; no gate bypass), FR-31/§4.9.5.D (sync protocol and single-host exception), §4.9.2 item 2 (identical semantics).

### Design References
- Phase 100366 contract; Phase 100368 read pattern.
- FR-32 tools already have server-side logic in `clio-config` (`Runtime` methods; dispatch at `crates/clio-config/src/config/dispatch.rs:34-52`); Phase 100380 binds them over MCP — this phase reuses that shared dispatch rather than a second copy.
- Masking: `clio_config::secret::{masked_clone, mask_secret}` (`crates/clio-config/src/secret.rs`); redaction: `clio_ops::redact_credentials`.
- Sync: Phase 100240 (`phase-100240-multi-host-sync-protocol.md`) and its appendix.
- DB/config precedence: `clio_config::db_path`, `clio_config::Runtime`.

---

## 2. Scope Boundaries

### In Scope
- `clio config get|set|profiles|use` mapping to `config_get`, `config_set`, `config_profiles`, `config_profile_apply`.
- `clio ranking get|set` mapping to `ranking_env_get`, `ranking_env_set`.
- `clio sync status|push|pull|serve` mapping to the sync tools.
- Masking of all config/ranking views; `--dry-run` for `ranking set`; profile-change non-bypass of gates.

### Explicitly Out of Scope
- New config keys, ranking knobs, or precedence changes.
- Changing the sync protocol, conflict rule, or auth.
- Any memory read/write command (earlier phases).
- Provider ingest.

### Must Not Change
- Config merge order and masking policy.
- Ranking weight semantics (sum-to-1.0) and admission/category gates (profile/ranking changes must not bypass them).
- The single-host sync exception (FR-31/§4.9.5.D) and sync auth in non-dev mode.

### Scope Expansion Rule
If work outside this scope appears necessary: stop, document the reason, request clarification or approval, and do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- Phase 100366 contract accepted; Phase 100368 read pattern accepted.
- Phase 100380 binds the six FR-32 tools over MCP and provides the shared dispatch; this phase routes the CLI through the same path.
- The sync tools exist (Phase 100240) with a documented single-host exception.

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| `clio-config` Runtime methods | Serve config/ranking | `crates/clio-config/src/config/dispatch.rs` |
| Phase 100380 shared dispatch | Callable from CLI | Phase exit contract |
| Sync tools | Present with single-host handling | `sync_status` etc. |
| Masking | Available | `clio_config::secret` |
| Coverage guard | Per-file floor | `make coverage` |

---

## 4. Existing-System Discovery

The agent MUST re-verify the following; the facts below were confirmed at plan time.

### Required Discovery
- Confirm the six FR-32 tools' schemas and the shared dispatch Phase 100380 introduces; route the CLI through it (no second implementation).
- Confirm which config views can carry secrets and that masking is applied to each.
- Confirm `config_set` scope handling (`session|profile|deployment`) and validation-before-apply.
- Confirm `ranking_env_set` weight validation/renormalization and dry-run.
- Confirm the sync tool flags and the single-host "omitted" explanation path.

### Discovery Output
- **Config/ranking logic already exists in `clio-config`** (`Runtime` methods; dispatch at `config/dispatch.rs:34-52`), so the CLI adds only a binding.
- **Secrets can appear in config/ranking views**; masking is mandatory (FR-32).
- **`config_set` must validate types/ranges before apply** and honor scope.
- **`ranking_env_set` weights sum to 1.0**; reject or renormalize with a clear error.
- **Sync is optional on single-host** (FR-31): `sync status` explains rather than failing.

### Repository Adaptation Rule
The agent must determine concrete implementation locations from the actual repository.

---

## 5. Implementation Specification

### Task 1: Config and Ranking Commands

#### Intent
Expose effective-config and ranking knobs with masking.

#### Required Capability or Behavior
- `clio config get [PATH]`, `clio config set PATH VALUE --scope session|profile|deployment`, `clio config profiles`, `clio config use NAME` run standalone.
- `clio ranking get` and `clio ranking set ... [--dry-run]` run standalone; weights validated/renormalized.
- Every view masks secrets; profile/ranking changes never bypass admission or category gates.
- Flags mirror the tool schemas 1:1.

#### Architectural Responsibility
`clio-lib` renders; `clio-config` remains the single source of truth; masking stays in its secret module.

#### Required Changes
1. Add config/ranking modules; delegate to the shared dispatch (Phase 100380).
2. Masking on all views; tests planting a secret.

#### Implementation Constraints
- Do not reimplement config or ranking logic.
- Never log plaintext secrets.
- No new dependency.

#### Expected Result
Config/ranking are CLI-reachable and masked.

### Task 2: Sync Commands

#### Intent
Expose sync honestly on both single-host and multi-host deployments.

#### Required Capability or Behavior
- `clio sync status|push|pull|serve` run standalone; flags mirror the tool schema.
- On a single-host deployment, `sync status` explains that sync is omitted by design (FR-31 exception) and exits 0.
- Multi-host paths keep the documented conflict rule and auth.

#### Architectural Responsibility
`clio-lib` renders; `clio-sync` owns protocol and auth.

#### Required Changes
1. Add a sync module; tests for the single-host explanation and a mocked multi-host status.

#### Implementation Constraints
- Do not weaken sync auth in non-dev mode.
- No new dependency.

#### Expected Result
Sync is CLI-reachable; single-host users get a clear explanation.

### Implementation Freedom
The agent may choose module layout and help wording, provided masking, weight validation, and sync semantics are unchanged.

---

## 6. Agent Execution Rules

### Allowed Actions
- Add config/ranking/sync modules, tests, and help.
- Reuse the Phase 100380 shared dispatch and the masker.

### Forbidden Actions
- Add config keys or ranking knobs; change precedence or masking policy.
- Bypass admission/category gates via profile/ranking changes; weaken sync auth; add dependencies.

### Agent Decision Boundary
The agent may decide rendering and command spelling (keeping names/semantics identical to the schema). The agent must request approval for a config/ranking semantic change.

### Mandatory Stop Conditions
Stop and report if a config/ranking view cannot be masked, if the shared dispatch is unavailable, or if sync semantics cannot be preserved.

---

## 7. Security Constraints

### Required Controls
- Mask secrets in `config get`, `config profiles`, `ranking get`, and any other view.
- Validate before side effects; fail closed on invalid values.
- Preserve sync auth and the non-bypass rule for gates.

### Sensitive Data Rules
- Never log or return plaintext secrets, keys, or vectors.
- Reuse the existing masker; do not hand-roll a second rule.

### Security Acceptance Conditions
- A planted secret is masked in every config/ranking view (test).
- Profile/ranking changes do not bypass gates (test).

---

## 8. Test and Verification Strategy

### Required Tests
- [x] Unit tests (scope handling, weight validation, mask)
- [x] Integration tests (config get/set/profiles/use; ranking get/set; sync status single-host)
- [x] Contract tests (semantics identical to MCP; exit codes)
- [x] End-to-end tests (golden output)
- [x] Regression tests (prior phases unchanged)
- [x] Security/failure-mode tests (masking; gate non-bypass; invalid weight/scope rejected)

### Required Test Scenarios

| Test ID | Scenario | Expected Result |
|---------|----------|-----------------|
| T100378-01 | `config get` with planted secret | Secret masked |
| T100378-02 | `config set` invalid type/range | Rejected before apply |
| T100378-03 | `config profiles` / `config use` | Effective diff; no gate bypass |
| T100378-04 | `ranking set --dry-run` non-normalized weights | Normalized or rejected clearly |
| T100378-05 | `sync status` single-host | Explanation; exit 0 |
| T100378-06 | `sync status` multi-host (mocked) | Status as MCP |
| T100378-07 | Regression + coverage | Workspace green; per-file ≥90% |

### Negative Testing
Verify invalid values are rejected, secrets never leak, and gates are not bypassed.

### Verification Rule
Implementation claims must be supported by actual command output and `make coverage`.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-100378-01 | Config/ranking commands bound with identical semantics | T100378-01…T100378-04 | PASS. New `runtime_cli.rs` engine plus `config_cli.rs` / `ranking_cli.rs` bind `clio config get/set/profiles/use` and `clio ranking get/set` to `config_get`/`config_set`/`config_profiles`/`config_profile_apply`/`ranking_env_get`/`ranking_env_set` through the existing shared dispatch `clio_config::Runtime::call_tool` (no second implementation; `clio-config` remains the single source of truth). Live transcripts: `clio config get` (full + path), `clio config set … --scope deployment`, `clio config profiles`, `clio config use coding_local`, `clio ranking get`, `clio ranking set --patch '{…}' --dry-run` (weights renormalized to 0.25 each). Tests: 11 config + 9 ranking + 7 engine + 11 sync; `cargo test -p clio --bin clio` 520 passed. |
| AC-100378-02 | Every config/ranking view masked | T100378-01 | PASS. Planted secret `sk-live-ABCDEFGHIJKLMNOP` set via `clio config set credentials.api_key … --scope deployment`; `clio config get credentials.api_key` prints `****MNOP` and the full `clio config get` view contains zero occurrences of the plaintext (`grep -c` = 0). Test `config_get_masks_a_planted_secret_in_path_and_full_views` asserts the plaintext is absent from both JSON and text output. `config_profiles` and `ranking get`/`set` carry no secret material. |
| AC-100378-03 | Profile/ranking changes do not bypass gates | T100378-03 | PASS. `clio config use coding_local` returns the effective diff and the tool note "Profile apply changes tunable knobs only; it does not bypass §4.1–§4.2 gates." `clio config set ranking.theta_admit 0.5` is rejected `forbidden` (ranking knobs are not tunable via config_set); `ranking set` only patches the ranking env after validation/renormalization. Tests `config_set_rejects_forbidden_and_unknown_paths` and `config_use_applies_a_profile_and_reports_no_gate_bypass`. |
| AC-100378-04 | Sync exposed; single-host explained | T100378-05, T100378-06 | PASS. `clio sync status` on a single-host deployment (effective `sync.omit` = true, the default) prints the FR-31 single-host explanation and exits 0 (transcript collected). With `sync.omit=false` the same command returns the masked MCP status report (`device_id`, per-bank cursors/pending/conflicts/dead letters) and exits 0. `clio sync push/pull` mirror the tool schema (`--remote`, `--mode`, `--banks`, `--token`, `--sync-key`) and require `--remote` (exit 2 without it); `clio sync serve` binds and holds the process for the resolved TTL. Tests: 11 sync + live transcripts. |
| AC-100378-05 | No regression; coverage green | T100378-07 | PASS. `make check` exit 0 (fmt + clippy `-D warnings` workspace + `cargo test --workspace --locked` incl. doctests). `make coverage` final gate: 311 files checked, TOTAL lines 97.98% / functions 98.82%, per-file guard all ≥90%. New files: `runtime_cli.rs` 100%/100%, `config_cli.rs` 99.30%/93.75%, `ranking_cli.rs` 98.84%/90.91%, `sync_cli.rs` 99.39%/93.55%. |

### Definition of Done
- [x] All in-scope behavior implemented.
- [x] All acceptance criteria pass.
- [x] Required tests pass.
- [x] No unauthorized changes introduced.
- [x] Existing behavior remains intact.
- [x] Security checks pass.
- [x] Documentation updated (help catalog, per-command usage lines, `clio help` catalog).
- [x] Evidence collected and verification completed.
- [x] Required approval is obtained (downstream pipeline step). — Remedy Approver r1 verdict APPROVE (all findings F-01…F-03 resolved; size, roadmap-isolation, and coverage constraints hold)

### Completion Evidence
- **Implementation summary**: New modules in `crates/clio-lib/src`: `runtime_cli.rs` (shared engine that resolves a two-token runtime-backed group, parses flags, and bridges to `clio_config::Runtime::call_tool`), `config_cli.rs` (`config get|set|profiles|use` → the four `config_*` tools), `ranking_cli.rs` (`ranking get|set` → `ranking_env_get`/`ranking_env_set`), and `sync_cli.rs` (`sync status|push|pull|serve` → the four §4.9.5.D sync tools through the in-process MCP dispatcher). Config/ranking route through the existing shared dispatch in `clio-config` (Phase 100380 owns MCP publication); sync routes through the same in-process `tools/call` bridge the read/write engines use, so CLI and MCP semantics cannot drift. Shared wiring: dispatch arms in `main.rs`, group subcommands/bindings in `cli_help.rs`, usage lines in `cli_help_usage.rs`, and top-level help lines in `main.rs`.
- **Module diffs**: four new production files + four new `*_tests.rs` files (all ≤450 lines; `sync_cli.rs` is the largest at 434). Edited shared files: `main.rs`, `cli_help.rs`, `cli_help_usage.rs`.
- **Masking evidence**: `clio config set credentials.api_key 'sk-live-ABCDEFGHIJKLMNOP' --scope deployment` then `clio config get credentials.api_key` → `config credentials.api_key = ****MNOP`; full `clio config get` contains zero plaintext occurrences. Test `config_get_masks_a_planted_secret_in_path_and_full_views`.
- **Single-host sync transcript**: `clio sync status` (default `sync.omit=true`) → "sync is omitted on this single-host deployment by design (the FR-31 single-host exception); the local store is authoritative …", exit 0. With `sync.omit=false` → `sync status (device …, remote (none), auth none, encryption false)` with per-bank cursors, exit 0.
- **Coverage report**: pre-change baseline (before edits) `307 files, TOTAL lines 97.96% / functions 98.91%` (guard green). Final `make coverage` → `target/coverage/coverage.json` (`311 files, TOTAL lines 97.98% / functions 98.82%`, per-file guard all ≥90%).
- **Known limitations**:
  1. `config set --scope profile` requires an active profile, which a one-shot CLI process does not have; it fails closed with the tool's clear error, identical to the MCP path. `config use` activation is in-memory for the current process; only `--scope deployment` persists (to the deployment config file). The profile-scope precondition is a `clio-config` tool semantic and is intentionally unchanged.
  2. `ranking set` without `--dry-run` patches only the current process's in-memory ranking env (the tool's "current profile/session" semantics), so a one-shot CLI cannot retain it; the text view states this and `--dry-run` is the useful CLI mode. Persisting ranking is a semantic change and remains out of scope.
  3. `sync serve` runs in the foreground for the resolved TTL (default 1800s); it does not daemonize. `sync_ack_skip` (a documented non-normative extension beyond §4.9.5.D, owned by Phase 100380's extension note) has no CLI binding; this phase binds the four §4.9.5.D sync commands. Debt owner: no phase is assigned a CLI binding for the extension.
  4. Single-host sync detection reads the effective `sync.omit` flag (default true), not a separate host-count probe.

---

## 10. Failure Handling and Recovery

### Expected Failure Modes
| Failure | Detection | Recovery |
|---------|-----------|----------|
| Secret leaks in a view | Masking test | Fix before claiming completion |
| Gate bypass via profile | Test | Fix before claiming completion |
| Sync single-host fails obscurely | Test | Add the explanation path |
| Coverage below floor | `make coverage` | Add tests |

### Rollback Strategy
Remove the config/ranking/sync modules; prior phases remain. No config is mutated by removal.

### Partial Completion Policy
Do not claim completion if config/ranking landed but sync did not, or vice versa. Record each separately.

---

## 11. Traceability

| Parent Requirement | Implementation Task | Verification | Acceptance Criterion |
|--------------------|---------------------|--------------|-----------------------|
| `gaps/full-cli.md` §6 | Tasks 1–2 | T100378-01…T100378-06 | AC-100378-01, AC-100378-04 |
| FR-32 (config/ranking; masked views; no gate bypass) | Task 1 | T100378-01…T100378-04 | AC-100378-02, AC-100378-03 |
| FR-31 / §4.9.5.D (sync; single-host exception) | Task 2 | T100378-05, T100378-06 | AC-100378-04 |
| Phase 100380 (shared config dispatch) | Task 1 | T100378-01 | AC-100378-01 |
| Coverage gate | Both | T100378-07 | AC-100378-05 |

Required chain:

```text
Gap → Config/ranking/sync bindings → CLI modules → Tests → Evidence
```

---

## 12. Phase Exit Contract

### Outputs Produced
- CLI `config`, `ranking`, and `sync` commands.

### Guarantees Provided to Downstream Phases
After this phase is accepted:
- Every MCP tool in the catalog has a CLI equivalent with identical semantics.
- Config/ranking views are masked and sync is honestly exposed.

### Known Limitations
- Sync on a single-host deployment is a reported no-op by design.
- Provider ingest remains out of scope.
- `config set --scope profile` requires an active profile, which a one-shot CLI process does not have; it fails closed with the tool's error. `config use` activation is in-memory only; `--scope deployment` is the persistent scope.
- `ranking set` without `--dry-run` affects only the current process (the tool's session semantics); `--dry-run` is the useful CLI mode.
- `sync serve` runs in the foreground for the resolved TTL; `sync_ack_skip` (a non-normative extension) has no CLI binding.

### Downstream Prerequisites
- None; this phase completes the CLI surface.

### Final Status
PASS WITH DOCUMENTED LIMITATIONS

### Verification Sign-Off
- Implementer: Developer r1 (OpenCode CLI, Go . Deepseek V4.1 Flash High)
- Verifier: Developer r1 — `make check` exit 0; `make coverage` final gate green (311 files, TOTAL lines 97.98% / functions 98.82%, per-file guard all ≥90%); live CLI transcripts collected for config/ranking/sync
- Human Approver: not required
- Date: 2026-09-24

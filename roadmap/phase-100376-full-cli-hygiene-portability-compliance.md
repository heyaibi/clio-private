# Phase 100376: Full CLI Hygiene and Portability/Compliance Surface

### Attribution
Rounds below record plan authorship; implementation sign-off is in §12.
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | OpenCode CLI (Together . GLM-5.3 Flash High) | done |
| Adversary | r1 | OpenCode CLI (OpenRouter . Deepseek V4.1 Flash Max) | done |
| Remediator | r1 | OpenCode CLI (Go . Deepseek V4.1 Flash High) | done |
| Remedy Approver | r1 | Antigravity CLI (Gemini 3.8 Flash) | approved |
| Finalize | r1 | OpenCode CLI (Go . Deepseek V4.1 Flash High) | done |

**Follow-up phase 100376 · **Effort:** ~3 days · **Gaps:** `gaps/full-cli.md` §6, §7 step 3 (hygiene, export/import, erase)

## 1. Objective

### Goal
Expose the hygiene, portability, and compliance tools on the CLI: `hygiene_audit`/`hygiene_clean`/`hygiene_log_list`, `export`, `import`, and `erase_request` — with secret masking, dry-run previews, and a confirm gate on every destructive path, keeping the crypto-shredding (`erase_request`) versus `discard` distinction loud in help and behavior.

### Expected Outcome
- `clio hygiene audit [--min-score N] [--limit N]`, `clio hygiene clean --file candidates.json --action flag|archive|discard|keep --confirm`, `clio hygiene log` run standalone. The whole hygiene family (`audit`, `clean`, `log`) is owned by this phase; it supersedes the earlier `hygiene log` mention in Phase 100368.
- `clio hygiene clean` without `--confirm` is dry-run only.
- `clio export --out FILE [--filter ...]`, `clio import --source FILE [--dry-run] [--force]` work with manifests and idempotent import.
- `clio erase --subject S --basis B --request R --confirm` runs the compliance path and states irreversibility; hygiene never aliases erasure.

### Parent Requirement
`gaps/full-cli.md` §6, §7 step 3, §8; `requirement.md` FR-33 (hygiene audit/clean/log, masking, not compliance erasure), FR-29 (export manifest, idempotent import, dry-run), §7.4 (compliance erase via DEK destruction), NFR-6 (no plaintext secrets).

### Design References
- Phase 100366 contract; Phase 100374 confirm-gate helper (reused here).
- Hygiene semantics: Phase 100210 (`phase-100210-hygiene-audit-confirmed-cleanup.md`).
- Export/import: Phase 100220 (`phase-100220-json-export-import.md`).
- Erase: Phase 100190 (`phase-100190-compliance-erase-path.md`) — DEK destruction + content-free tombstones.
- Masking: `clio_config::secret`; redaction: `clio_ops::redact_credentials`.

---

## 2. Scope Boundaries

### In Scope
- `clio hygiene audit|clean|log` with `--min-score`, `--limit`, candidate-file input, and `--confirm` gating.
- `clio export --out FILE` (manifest-backed) and `clio import --source FILE [--dry-run] [--force]`.
- `clio erase --subject S --basis B --request R --confirm` (compliance erasure).
- Masking on every view and report; irreversibility notes in help and dry-run.

### Explicitly Out of Scope
- `update`/`invalidate`/`discard`/`correct` (Phase 100374).
- Config/ranking/sync (Phase 100378).
- Provider ingest (`import_provider` beyond an existing stub).
- Changing hygiene scoring, export format, or erase mechanism.

### Must Not Change
- Hygiene must not perform compliance erasure (FR-33).
- Export completeness manifest fields; import idempotency; erase via DEK destruction.
- No plaintext secrets in any report or log.

### Scope Expansion Rule
If work outside this scope appears necessary: stop, document the reason, request clarification or approval, and do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- Phase 100366 contract and Phase 100374 confirm gate accepted.
- The hygiene/export/import/erase tools exist and are gated over MCP (Phases 100210/100220/100190).

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| In-process dispatch | Hygiene/portability/erase callable | `crates/clio-mcp/src/lib.rs` |
| Hygiene log | Durable, callable | Phase 100210 |
| Export manifest | Present | Phase 100220 |
| Confirm gate | Available | Phase 100374 |
| Coverage guard | Per-file floor | `make coverage` |

---

## 4. Existing-System Discovery

The agent MUST re-verify the following; the facts below were confirmed at plan time.

### Required Discovery
- Confirm hygiene tool schemas and the candidate-file format `hygiene_clean` expects.
- Confirm export manifest fields and import idempotency/`--force` semantics.
- Confirm the erase request inputs (`subject`, `basis`, `request`) and that erase is DEK destruction, not row deletion.
- Confirm masking entry points for audit/report output.
- Confirm which operations require `--confirm` off-TTY.

### Discovery Output
- **Hygiene clean is confirmed-only.** Without `--confirm` it is dry-run only (Phase 100210).
- **Hygiene ≠ erasure.** `hygiene_clean` removes noise; `erase_request` destroys the subject DEK and writes content-free tombstones (§7.4). The CLI must keep this distinction explicit.
- **Export is manifest-backed.** `complete`, counts, checksums, `content_mode` are required (FR-29).
- **Import is idempotent by default** and supports a zero-write dry-run report.
- **Confirm gate exists** (Phase 100374) for reuse.

### Repository Adaptation Rule
The agent must determine concrete implementation locations from the actual repository.

---

## 5. Implementation Specification

### Task 1: Hygiene Commands

#### Intent
Make ranked noise cleanup reviewable and confirmed.

#### Required Capability or Behavior
- `clio hygiene audit [--min-score N] [--limit N]` lists ranked candidates with masking.
- `clio hygiene clean --file candidates.json --action flag|archive|discard|keep [--confirm]` applies confirmed cleanup; without `--confirm` it is dry-run only and exits 0.
- `clio hygiene log` lists the durable cleanup log.

#### Architectural Responsibility
`clio-lib` renders; hygiene semantics stay in Phase 100210's crates.

#### Required Changes
1. Add a hygiene module and tests (confirmed vs dry-run; masking).

#### Implementation Constraints
- Never mutate without `--confirm`.
- Never alias hygiene to erase.
- Mirror hygiene tool flags 1:1.

#### Expected Result
Hygiene audit, confirmed cleanup, and log are CLI-reachable with correct gating.

### Task 2: Export, Import, and Erase

#### Intent
Bind portability and compliance.

#### Required Capability or Behavior
- `clio export --out FILE [--filter ...]` writes a manifest-backed bundle.
- `clio import --source FILE [--dry-run] [--force]` imports idempotently; dry-run writes nothing.
- `clio erase --subject S --basis B --request R --confirm` runs compliance erasure; the help and dry-run state that it is irreversible and distinct from `discard`/hygiene.
- No plaintext secrets in any output.

#### Architectural Responsibility
`clio-lib` renders; trust-boundary and DEK logic stay in the existing crates.

#### Required Changes
1. Add a portability/compliance module and tests.
2. Reuse the confirm gate for erase; force false preconditions and fail closed without `--confirm`.

#### Implementation Constraints
- Erase requires `--confirm` off-TTY.
- Import dry-run zero-write.
- No new dependency.

#### Expected Result
Portability and compliance operate from the CLI with masks and gates intact.

### Implementation Freedom
The agent may choose module layout and help wording, provided masking, manifests, idempotency, and the erase/clean distinction hold.

---

## 6. Agent Execution Rules

### Allowed Actions
- Add hygiene/portability/compliance modules, tests, and help.
- Reuse the confirm gate and masker.

### Forbidden Actions
- Alias hygiene to erasure; mutate without `--confirm`; emit plaintext secrets.
- Change export format or hygiene scoring; add dependencies.

### Agent Decision Boundary
The agent may decide rendering. The agent must request approval for any change to erase or export contracts.

### Mandatory Stop Conditions
Stop and report if erase cannot be kept distinct from hygiene, if import cannot be idempotent, or if a report cannot be masked.

---

## 7. Security Constraints

### Required Controls
- `--confirm` required for `hygiene clean` mutations and `erase`; dry-run otherwise.
- Mask secrets in every audit/export/report view (`clio_config::secret`).
- Erase operates on the DEK path; no plaintext content in tombstones.

### Sensitive Data Rules
- Never log plaintext credentials, tokens, keys, or memory content in reports.
- Do not emit DEKs under `ciphertext_backup`.

### Security Acceptance Conditions
- Unconfirmed `hygiene clean` writes nothing (test).
- `erase` without `--confirm` exits 2 and writes nothing (test).
- Planted secret is masked in audit/export output (test).

---

## 8. Test and Verification Strategy

### Required Tests
- [ ] Unit tests (candidate-file parse, mask, gate decision)
- [ ] Integration tests (hygiene audit/clean/log; export→import round trip)
- [ ] Contract tests (manifest fields; idempotent import; exit codes)
- [ ] End-to-end tests (golden output; erase dry-run)
- [ ] Regression tests (prior phases unchanged)
- [ ] Security/failure-mode tests (unconfirmed no-op; erase gate; masking)

### Required Test Scenarios

| Test ID | Scenario | Expected Result |
|---------|----------|-----------------|
| T100376-01 | `hygiene audit --limit 1` | Ranked candidate; masked |
| T100376-02 | `hygiene clean` without `--confirm` | Dry-run; zero writes; exit 0 |
| T100376-03 | `hygiene clean --confirm` | Candidates actioned |
| T100376-04 | `hygiene log` | Durable cleanup entries |
| T100376-05 | `export` then `import` | Round trip; manifest complete |
| T100376-06 | `import --dry-run` | Zero writes; report only |
| T100376-07 | `erase` without `--confirm` | Exit 2; zero writes |
| T100376-08 | `erase --confirm` | DEK destroyed; tombstones content-free |
| T100376-09 | Regression + coverage | Workspace green; per-file ≥90% |

### Negative Testing
Verify unconfirmed mutations are no-ops, erase is gated and irreversible-aware, and no secret leaks.

### Verification Rule
Implementation claims must be supported by actual command output and `make coverage`.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-100376-01 | Hygiene audit/clean/log bound with confirmed gating | T100376-01…T100376-04 | PASS (with documented cross-process KMS caveat). `clio hygiene audit|clean|log` bound to `hygiene_audit`/`hygiene_clean`/`hygiene_log_list` (`cli_read_hygiene.rs`, `cli_write_hygiene.rs`). 25 hygiene CLI tests pass (15 clean + 10 audit/log) plus 12 `clio-mcp` hygiene tool tests; full `cargo test -p clio --bin clio` 480 passed. Live CLI transcript: `hygiene clean --file cands.json --action discard` without `--confirm` (or with `--dry-run`) → exit 0, "would flag 0, archive 0, discard 1 (zero writes)", `stats` unchanged; with `--confirm --reason` → item discarded (`items_active` 1→0), `hygiene log` shows the durable row. A confirmed batch abort now exits 1 and the text view names the failing target and the pending remainder (`hygiene clean: applied 1 item(s); failed itm-ghost (…); aborted, 1 pending`), while the JSON payload still carries `applied`/`failed`/`pending`. Cross-process dry-run→confirm is collision-free: the clean batch id mixes process id, a nanosecond clock, and the in-process counter, so durable dry-run rows no longer collide with the confirmed insert (regression test `hygiene_clean_dry_run_then_confirm_across_fresh_runtime_instances`). Caveat (limitation 1): `hygiene audit` over content written by another process still fails `forbidden`/`no DEK for subject` because the only key provider is process-local; the CLI now adds an actionable hint naming the durable KMS need. |
| AC-100376-02 | Export manifest + idempotent import | T100376-05, T100376-06 | PASS (with documented cross-process KMS caveat). Export/import round-trip test: export of 2 seeded items (`--actor harness`) writes a bundle whose manifest reports `complete==true`; import applies (`would_create ≥ 2`); re-importing the same bundle skips everything (`would_create == 0`, `would_skip ≥ 2`); `import --dry-run` reports counts with stats proving zero writes. 11 portability CLI tests pass. Caveat (limitation 1): `export` defaults to `dsar_plaintext`, which decrypts content, so a cross-process export of content written by another process fails `forbidden`/`no DEK for subject` (the in-process `LocalDevKms` is process-local); the round trip is proven in-process, the repo's established test model. |
| AC-100376-03 | Erase gated, distinct from hygiene/discard | T100376-07, T100376-08 | PASS. Live CLI transcript: `clio erase --subject S --basis B --request R` without `--confirm` → exit 2, error names `--confirm`, zero writes; `--dry-run` → exit 0 preview stating IRREVERSIBILITY and the discard/hygiene distinction; with `--confirm --actor harness` → `status COMPLETED`, `item_count 1`, `tombstones_written 1`, one-way `subject_hash`. |
| AC-100376-04 | Masking on every report | T100376-01 | PASS. Test: item seeded with a planted `api_key=sk-…` secret; `hygiene audit` output (stdout and stderr) contains no plaintext secret; audit text view never renders the preview field. Export render/mask test: planted secret absent from CLI stdout/stderr. |
| AC-100376-05 | No regression; coverage green | T100376-09 | PASS. `make check` green (fmt + clippy `-D warnings` workspace + `cargo test --workspace --locked` incl. doctests). `make coverage` final gate after remediation: 307 files checked, TOTAL lines 97.96% / functions 98.91%, per-file guard: all files ≥90% both metrics. New/remediated files: `cli_read_hygiene.rs` 99.19%/100%, `cli_write_hygiene.rs` 96.47%/95.24%, `cli_write_portability.rs` 97.09%/100%, `cli_help_usage.rs` 100%/100%, `cli_help.rs` 100%/100%, `cli_error.rs` 100%/100%, `clio-mcp/hygiene_tools.rs` 99.22%/100%, `clio-mcp/runtime_context.rs` 100%/100%. |

### Definition of Done
- [x] All in-scope behavior implemented.
- [x] All acceptance criteria pass.
- [x] Required tests pass.
- [x] No unauthorized changes introduced.
- [x] Existing behavior remains intact.
- [x] Security checks pass.
- [x] Documentation updated (help catalog, per-command usage lines, `clio help` catalog).
- [x] Evidence collected and verification completed.
- [x] Required approval is obtained (downstream pipeline step). — Remedy Approver r1 verdict APPROVE (all findings F-01…F-07 resolved; size, roadmap-isolation, and coverage constraints hold)

### Completion Evidence
- **Implementation summary**: New CLI surfaces in `crates/clio-lib/src`: `cli_read_hygiene.rs` (`HygieneReadGroup`: `hygiene audit` → `hygiene_audit` with `--min-score/--limit/--offset` + in-band `truncated` marker; `hygiene log` → `hygiene_log_list`), `cli_write_hygiene.rs` (`HygieneWriteGroup`: `hygiene clean --file candidates.json|- --action flag|archive|discard|delete|keep [--confirm] [--dry-run] [--reason] [--note]`; unconfirmed (or `--dry-run`) = tool dry-run, exit 0; fail-closed candidate-file parsing before any dispatcher call), `cli_write_portability.rs` (`PortabilityWriteGroup`: `export --out FILE …` → `export`; `import --source FILE [--dry-run] [--force]`; `erase --subject S --basis B --request R [--reason-code C]` with the shared confirm gate, `--dry-run` irreversibility preview). Shared wiring: help catalog bindings + usage lines (`cli_help.rs`), dispatch (`main.rs`), group registration (`cli_read.rs`, `cli_write.rs`). Hygiene/export/import/erase semantics, masking, manifests, and DEK logic stay in the existing crates (`clio-hygiene`, `clio-compliance`, `clio-mcp`) — CLI and MCP cannot drift because the CLI calls the in-process dispatcher.
- **Module diffs**: six new files from r1 (3 modules: `cli_read_hygiene.rs`, `cli_write_hygiene.rs`, `cli_write_portability.rs`; plus their 3 `*_tests.rs`) and `cli_help_usage.rs` extracted from `cli_help.rs` during remediation (7 new files total, all ≤450 lines); five edited shared files in r1 (`cli_help.rs`, `cli_help_tests.rs`, `main.rs`, `cli_read.rs`, `cli_write.rs`). Remediation additionally edited `cli_write_group.rs`, `cli_error.rs`, `cli_read_tests.rs`, `cli_error_tests.rs`, `cli_write_hygiene.rs`/`cli_write_hygiene_tests.rs`, `cli_read_hygiene.rs`/`cli_read_hygiene_tests.rs`, and `clio-mcp` (`hygiene_tools.rs`, `runtime_context.rs`, `hygiene_tools_tests.rs`).
- **Export/import round-trip evidence**: test suite (in-process, real test output; cross-process CLI transcript not possible today — see limitation 1).
- **Erase-gate and masking transcripts**: live CLI transcripts quoted in the AC table (exit 2 refusal naming `--confirm`; exit 0 dry-run preview with IRREVERSIBLE + hygiene/discard distinctness; confirmed erase `COMPLETED` with tombstones).
- **Coverage report**: pre-change baseline JSON (`303 files, TOTAL 97.95% lines / 98.92% functions, guard green` — the earlier "301 files / 98.91% functions" figures were a transcription error); final gate `make coverage` after remediation → `target/coverage/coverage.json` (`307 files, TOTAL 97.96% / 98.91%, guard green`).
- **Remediation r1 (findings F-01…F-07)**: split the per-command usage table out of `cli_help.rs` into `cli_help_usage.rs` (F-01, keeping every file ≤450 lines); made the hygiene clean batch id collision-free with a cross-process regression test (F-02); added the cross-process KMS caveat to AC-01/02 and a CLI hint at the `no DEK for subject` failure point (F-03); surfaced the confirmed-clean failing target and pending count in the text view and made a batch abort exit 1 while keeping the JSON payload (F-04); surfaced the audit scan-budget `incomplete` flag in the audit text view (F-05); corrected the baseline/count figures here (F-06); accepted `--dry-run` on `hygiene clean` as an explicit zero-write preview that overrides `--confirm` (F-07).
- **Known limitations**:
  1. Cross-process CLI flows over encrypted content fail by design today: the only DEK provider is the documented in-process `LocalDevKms` ("keys never enter the item database"), so content written by one one-shot CLI process cannot be decrypted by the next (e.g. `clio hygiene audit` against another process's `remember` output errors `no DEK for subject`). This phase binds commands; a durable DEK provider is owned by the DEK/KMS persistence track outside this phase's scope (this phase must not change the DEK/erase mechanism). All acceptance tests run in-process (single process), which is the repo's established test model. Debt owner: the DEK/KMS persistence track — no phase in the current roadmap is assigned to it; it is the pre-existing unassigned debt first recorded in the Phase 100370 CLI phase. The CLI now adds an actionable hint at the failure point (`the default key provider is process-local; content written by another process needs a durable KMS provider`).
  2. (Resolved in remediation r1) Cross-process `hygiene clean` dry-run→confirm previously failed the log write: the batch id came from the per-process `next_item_id()` counter (`itm-mcp-<n>`), so a fresh process regenerated the same id and the confirmed insert hit a `hygiene_audit_logs` UNIQUE-constraint abort. `McpState::next_clean_batch_id` now mixes the process id, a nanosecond clock, and the in-process counter, and the regression test `hygiene_clean_dry_run_then_confirm_across_fresh_runtime_instances` runs dry-run then confirm over two fresh runtimes on one durable file DB.
  3. Hygiene candidate files are inputs; interactive candidate review is not added (as scoped in the phase exit contract).

---

## 10. Failure Handling and Recovery

### Expected Failure Modes
| Failure | Detection | Recovery |
|---------|-----------|----------|
| Unconfirmed cleanup mutates | Gate test | Fix before claiming completion |
| Import writes on dry-run | Test | Fix before claiming completion |
| Erase aliases hygiene | Review | Clarify and separate |
| Coverage below floor | `make coverage` | Add tests |

### Rollback Strategy
Remove the modules; prior phases remain. Test artifacts live in temp dirs.

### Partial Completion Policy
Do not claim completion if hygiene landed but compliance did not, or vice versa. Record each separately.

---

## 11. Traceability

| Parent Requirement | Implementation Task | Verification | Acceptance Criterion |
|--------------------|---------------------|--------------|-----------------------|
| `gaps/full-cli.md` §7 step 3 | Tasks 1–2 | T100376-01…T100376-08 | AC-100376-01…AC-100376-03 |
| FR-33 (hygiene audit/clean/log; not erasure) | Task 1 | T100376-01…T100376-04 | AC-100376-01 |
| FR-29 (manifest export; idempotent import; dry-run) | Task 2 | T100376-05, T100376-06 | AC-100376-02 |
| §7.4 (compliance erase via DEK) | Task 2 | T100376-07, T100376-08 | AC-100376-03 |
| NFR-6 (masking) | Both | T100376-01 | AC-100376-04 |
| Coverage gate | Both | T100376-09 | AC-100376-05 |

Required chain:

```text
Gap → Hygiene/portability/compliance bindings → CLI modules + gates → Tests → Evidence
```

---

## 12. Phase Exit Contract

### Outputs Produced
- CLI hygiene audit/clean/log, export/import, and erase commands.

### Guarantees Provided to Downstream Phases
After this phase is accepted:
- Noise cleanup, portability, and compliance are all CLI-reachable with masks and gates.
- Erase is distinct and gated.

### Known Limitations
- Cross-process reads of encrypted content fail today: the only key provider is the process-local `LocalDevKms`, so a durable DEK/KMS provider is still owed. Debt owner: the DEK/KMS persistence track — no phase in the current roadmap is assigned to it (pre-existing unassigned debt first recorded in the Phase 100370 CLI phase).
- Hygiene candidate files are inputs; interactive candidate review is not added.
- Export/import scope is JSON bundles, not provider ingest.

### Downstream Prerequisites
- Phase 100378's config/ranking/sync surface completes the CLI catalog.

### Final Status
PASS WITH DOCUMENTED LIMITATIONS

### Verification Sign-Off
- Implementer: Developer r1 (OpenCode CLI, Together . GLM-5.3 Flash High)
- Verifier: Developer r1 — `make check` green; `make coverage` final gate green with per-file guard (306 files, all ≥90% lines and functions); live CLI gate/dry-run/confirm transcripts collected
- Remediator: Remediator r1 (OpenCode CLI, Go . Deepseek V4.1 Flash High) — addressed findings F-01…F-07; `make check` green (fmt + clippy `-D warnings` workspace + `cargo test --workspace --locked`); `make coverage` final gate green (307 files, TOTAL lines 97.96% / functions 98.91%, all files ≥90% both metrics)
- Human Approver: not required (erase contract unchanged)
- Date: 2026-09-23

# Phase 100376: Full CLI Hygiene and Portability/Compliance Surface

### Attribution
Rounds below record plan authorship; implementation sign-off is in §12.
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | [TBD] | [TBD] |
| Adversary | r1 | [TBD] | [TBD] |
| Remediator | r1 | [TBD] | [TBD] |
| Remedy Approver | r1 | [TBD] | [TBD] |
| Finalize | r1 | [TBD] | [TBD] |

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
| AC-100376-01 | Hygiene audit/clean/log bound with confirmed gating | T100376-01…T100376-04 | Command output |
| AC-100376-02 | Export manifest + idempotent import | T100376-05, T100376-06 | Bundle + output |
| AC-100376-03 | Erase gated, distinct from hygiene/discard | T100376-07, T100376-08 | Output + help |
| AC-100376-04 | Masking on every report | T100376-01 | Output diff |
| AC-100376-05 | No regression; coverage green | T100376-09 | `make check`, `make coverage` |

### Definition of Done
- [ ] All in-scope behavior implemented.
- [ ] All acceptance criteria pass.
- [ ] Required tests pass.
- [ ] No unauthorized changes introduced.
- [ ] Existing behavior remains intact.
- [ ] Security checks pass.
- [ ] Documentation updated.
- [ ] Evidence collected and verification completed.

### Completion Evidence
- Implementation summary
- Module diffs
- Export/import round-trip evidence
- Erase-gate and masking transcripts
- Coverage report
- Known limitations

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
- Hygiene candidate files are inputs; interactive candidate review is not added.
- Export/import scope is JSON bundles, not provider ingest.

### Downstream Prerequisites
- Phase 100378's config/ranking/sync surface completes the CLI catalog.

### Final Status
PASS | PASS WITH DOCUMENTED LIMITATIONS | BLOCKED | FAILED

### Verification Sign-Off
- Implementer: [TBD]
- Verifier: [TBD]
- Human Approver: not required (unless erase contract changes)
- Date: [TBD]

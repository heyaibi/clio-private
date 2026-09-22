# Phase 100220: JSON Export and Import

### Attribution
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | OpenCode CLI (Together . GLM-5.3 Flash High) | done |
| Adversary | r1 | Antigravity CLI (Gemini 3.8 Flash) | done |
| Remediator | r1 | OpenCode CLI (Go . Deepseek V4.1 Flash High) | done |
| Remedy Approver | r1 | Antigravity CLI (Gemini 3.8 Flash) | approved |
| Finalize | r1 | OpenCode CLI (Together . GLM-5.3 Flash High) | done |

**Index slice 100220 · **Effort:** `1×` · **Scope:** `roadmap/index.md` slice 100220 (authoritative)

### Vocabulary (read first) — zero shared moniker

| Term | Enum / form | Where it lives | Must not |
|------|-------------|----------------|----------|
| **`memory_export_bundle`** | JSON payload + sidecar inventory for selected memories | `export` (§4.9.5.B) | Be confused with **`sync_payload`** (§4.9.5.D) or MCP `tool_schema` packs |
| **`completeness_manifest`** | Versioned inventory: counts, checksums, filter, `complete` flag | Required sibling of every export (FR-29) | Be confused with doctor repair plans or sync cursors |
| **`gated_json_import`** | Idempotent import through §4.1–§4.2 gates | `import` tool | Bypass admission or alias **`import_provider`** |
| **`import_dry_run_report`** | would-create / would-skip / would-reject / would-overwrite | `import(dry_run=true)` | Perform writes |
| **`import_force`** | Auditable overwrite mode (`force=true`) | `import` only | Be confused with doctor `--force` / repair aggression |
| **`export_content_mode`** | `dsar_plaintext` \| `ciphertext_backup` | Export bundle (§3 appendix) | Sync wire `client_ciphertext` |
| **`import_provider_stub`** | Seam returning “not implemented” / empty adapter registry | First-release carve-out (FR-29 / index Explicit later) | Expand into multi-provider ingest in this phase |

Bundle format + modes: [phase-100220-appendix-bundle-format.md](phase-100220-appendix-bundle-format.md).

---

## 1. Objective

### Goal
Ship manifest-backed **`export`** and idempotent gated **`import`** for JSON memory bundles (FR-29, NFR-6, §4.9.5.B): completeness inventory, no plaintext secrets, dry-run reports with zero writes, and admission enforcement on every imported candidate. Provider ingest stays a **stub seam only**.

### Expected Outcome
- `export(destination, filter?, content_mode?)` writes a `memory_export_bundle` including items (snapshot/gist refs), triples, persona, task/failure/temporal records, graph edges including **`assoc_edge`**, plus confidence/admission/telemetry fields (NFR-6).
- Default **`export_content_mode=dsar_plaintext`**: authorized export decrypts in-process and writes readable content (still omits DEKs/API/sync secrets). Optional **`ciphertext_backup`**: opaque payloads + key/subject ids without DEKs for like-to-like restore.
- Every export includes a `completeness_manifest` with schema/export format version, `content_mode`, bank ids, counts by type/category, content checksums, filter, `generated_at`, and `complete: true|false` (false if filtered/truncated, with omission notes).
- DEKs, API keys, and sync credentials NEVER appear in plaintext in the export file.
- `import(source, dry_run?, force?)` is idempotent by default (same identities/content hashes ⇒ no duplicate rows); `force=true` may overwrite with an auditable reason.
- Every import candidate for `dsar_plaintext` passes §4.1–§4.2 before commit; `dry_run=true` returns `import_dry_run_report` with zero writes.
- **`import_provider` is first-release stub only.** FR-29 provider SHALL clauses are deferred per index Explicit later / requirement.md v1.9; stub still masks credential params and never writes.

### Parent Requirement
`requirement.md` (v1.9+) — P12, PR-3, PR-5, PR-8, §4.1, §4.2, §4.5 (`assoc_edge`), §4.9.5.B, §4.9.7, FR-29, NFR-6; index “Explicit later” provider ingest (governs first-release stub).

### Design References (non-normative)
- **Manifest + checksums before write:** [OpenViking OVPack](https://docs.openviking.ai/en/guides/09-ovpack) — reject packages that fail manifest/checksum validation even under skip/overwrite policies.
- **Idempotent merge-by-id:** [portable-memory](https://pypi.org/project/portable-memory/) — re-import is a no-op; prefer supersession over silent clobber for bi-temporal facts.
- **Gate reuse on import:** Flexitype-style schema import — run the same create validators as live writes; orchestration only.
- **Canonical bytes:** appendix [phase-100220-appendix-bundle-format.md](phase-100220-appendix-bundle-format.md).

---

## 2. Scope Boundaries

### In Scope
- JSON `export` writer with filters (bank, category, time range, include-archived?) and `export_content_mode`.
- `completeness_manifest` generation and validation on import per [phase-100220-appendix-bundle-format.md](phase-100220-appendix-bundle-format.md).
- Idempotent `import` with dry-run report and optional `import_force`.
- Inclusion of `assoc_edge` graph metadata in bundles.
- Secret stripping/redaction on export; masked diagnostics on import errors.
- Respect for compliance tombstones / erased subjects (do not export recoverable shredded content as valid plaintext).
- Stub `import_provider` seam with stable error code (first-release FR-29 carve-out).
- MCP schemas on **stdio and Streamable HTTP** with identical semantics (pinned MCP revision).

### Explicitly Out of Scope
- Multi-provider `import_provider` adapters (external memory-system matrices — Hindsight/Mem0/Mnemosyne/Honcho/Supermemory, not LLM/chat vendors) — deferred; FR-29 provider SHALLs apply when adapters ship.
- Multi-host sync protocol (Phase 100240)—export is offline portability, not live replication.
- Doctor repair/reindex (Phase 100230), though import MAY enqueue index rebuild hints.
- Changing admission formulas or category whitelist contents.
- Encrypted-at-rest key export (DEKs stay out of bundles).

### Must Not Change
- §4.1–§4.2 gate enforcement on long-term writes.
- Phase 100190 erase semantics; export MUST NOT resurrect shredded plaintext.
- Tool catalog names `export` / `import` / `import_provider`.

### Scope Expansion Rule
If work outside this scope appears necessary:
1. Stop.
2. Document the reason.
3. Request clarification or approval.
4. Do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- Phases 003–015: durable item/triple/persona/task/failure/belief/`assoc_edge` stores exist.
- Phase 100040: admission gates callable for candidates.
- Phase 100180: telemetry fields available for NFR-6 export.
- Phase 100190: tombstone/erased-subject behavior known.
- Phase 100200: `batch` available for atomic multi-row import commits (recommended).

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| Admission + category gates | Invokable per candidate | Dry-run reject below θ |
| Graph metadata store | `assoc_edge` readable | Export contains edges |
| Checksum utility | Stable SHA-256 (or documented hash) | Round-trip verify |
| Batch/transaction | Optional but preferred for import | Rollback on mid-fail |

---

## 4. Existing-System Discovery

### Required Discovery
- Inventory all durable entity kinds required in §4.9.5.B payload list.
- Locate serialization formats already used by MCP/inspect.
- Find secret-masking helpers shared with hygiene/diagnose.
- Confirm how erased subjects and tombstones appear in reads.
- Identify whether embeddings are exported or recomputed on import (prefer recompute; if exported, tag model id).

### Discovery Output
Report entity coverage matrix, manifest field map, embedding policy choice, and any missing serializers.

### Repository Adaptation Rule
Paths and module names come from the repository.

---

## 5. Implementation Specification

### Task 1: Export Bundle + Completeness Manifest (FR-29, NFR-6)

#### Intent
Write portable JSON bundles with integrity inventory.

#### Required Capability or Behavior
- Serialize selected memories + graph edges (`assoc_edge` included) per appendix layout.
- Include confidence, admission, and telemetry fields.
- Emit `completeness_manifest` alongside payload (same file object or sibling file per appendix).
- Support `content_mode`:
  - **`dsar_plaintext` (default):** decrypt under caller authorization; write plaintext snapshots/gists; fail closed without authz.
  - **`ciphertext_backup`:** opaque content blobs + subject/key ids; no DEKs; not a DSAR substitute.
- If filter/truncation applied: `complete=false` and explicit omission notes.
- Strip DEKs, API keys, sync credentials; fail closed if a field is classified secret and cannot be omitted safely.
- Erased/shredded content: export tombstone metadata only, never fake plaintext.
- Checksums over canonical JSON bytes (appendix §4).

#### Architectural Responsibility
Export serializer + manifest builder.

#### Required Changes
1. Bundle schema version constant + content_mode enum.
2. Per-entity serializers for both content modes.
3. Count + checksum aggregation (canonical JSON).
4. MCP/CLI `export` binding on stdio and Streamable HTTP.

#### Implementation Constraints
- Format version MUST be validated on import; unsupported versions reject.
- Checksums cover canonicalized payload bytes (appendix).
- Authz failure produces no destination file.

#### Expected Result
Filtered export produces `complete=false` with honest omission notes; full bank export can be `complete=true`; DSAR mode yields readable content without DEKs.

---

### Task 2: Idempotent Gated Import + Dry-Run (FR-29)

#### Intent
Import bundles safely without duplicates or gate bypass.

#### Required Capability or Behavior
- Validate manifest presence, version, and checksums **before** any write (corrupt bundles fail even with skip/force).
- Default idempotency: matching item identity / content hash ⇒ skip (would-skip).
- `force=true`: overwrite/supersede with auditable reason (prefer bi-temporal invalidate+insert for discrete facts rather than silent row clobber).
- Every would-create candidate runs §4.1–§4.2; rejects recorded in dry-run and live modes.
- `dry_run=true`: full report, zero writes.
- Live import SHOULD use transactional batches; on failure, no partial silent success.

#### Architectural Responsibility
Import orchestrator reusing store/triple/assoc write paths.

#### Required Changes
1. Manifest validator.
2. Candidate planner (create/skip/reject/overwrite).
3. Gate invocation + `batch` commit.
4. `import_dry_run_report` schema.

#### Implementation Constraints
- Do not call `import_provider` adapters here.
- Do not treat import as sync cursor advancement.

#### Expected Result
Re-import of the same complete bundle is a no-op success with would-skip == prior creates.

---

### Task 3: `import_provider` Stub Seam (FR-29 first-release carve-out)

#### Intent
Reserve the tool name without shipping provider matrix; make governance explicit.

#### Required Capability or Behavior
- **Governance:** Index “Explicit later” and requirement.md v1.9 defer FR-29’s provider-adapter SHALLs until a provider phase ships. First release MUST expose `import_provider` as a stub only.
- Tool exists; returns structured `{ok:false, code:"PROVIDER_IMPORT_UNSUPPORTED"}` (or equivalent).
- Docs state first-release omission.
- Credentials parameters accepted only to validate masking in error paths—never logged plaintext; never written.

#### Architectural Responsibility
Stub adapter registry.

#### Expected Result
Callers get a clear unsupported signal; no writes; credential masking still verified.

---

### Task 4: Conformance and Round-Trip Tests

#### Intent
Prove FR-29 with executable evidence.

#### Required Capability or Behavior
- Export → import dry-run → import live → re-import idempotent.
- Gate rejection fixture.
- Secret field absence in serialized file.
- `assoc_edge` round-trip.
- Tombstone/erased subject handling.
- Unsupported version rejection.

#### Expected Result
CI suite green on Postgres and SQLite where storage differs.

---

### Implementation Freedom
Bundle packaging (single JSON vs directory), embedding inclusion policy, and overwrite mechanics may vary if vocabulary and gates hold.

---

## 6. Agent Execution Rules

### Allowed Actions
- Implement export/import modules, schemas, tests.
- Reuse store/triple/assoc/persona writers and admission gates.
- Add stub provider tool.

### Forbidden Actions
- Bypass admission on import.
- Export plaintext DEKs/sync secrets.
- Implement real provider adapters in this phase.
- Use sync protocol as a substitute for export/import.
- Unrelated broad refactors.

### Agent Decision Boundary
May choose canonical JSON encoding and whether vectors are omitted (recompute) vs model-tagged optional.

Must request approval for:
- Breaking bundle format without version bump.
- Auto-running `reindex` without operator opt-in after import.

### Mandatory Stop Conditions
Stop if entity coverage cannot meet §4.9.5.B list, if gates cannot run in dry-run, or if erased content cannot be kept non-exportable as plaintext.

---

## 7. Security Constraints

### Required Controls
- Manifest/checksum validation before write.
- Secret omission on export; masked import diagnostics (§4.9.7).
- Authorization: export/import respect bank and actor scope.

### Sensitive Data Rules
- Never commit export fixtures containing live secrets.
- Never log provider credentials.

### Security Acceptance Conditions
- Grep/scan of export file finds no DEK/API key patterns from fixtures.
- Corrupt manifest never partially applies.

---

## 8. Test and Verification Strategy

### Required Tests
- [ ] Unit: manifest checksum canonicalization
- [ ] Integration: round-trip idempotency
- [ ] Integration: dry-run zero writes
- [ ] Integration: admission reject on import
- [ ] Security: secret stripping
- [ ] Contract: stub provider error shape

### Required Test Scenarios

| Test ID | Scenario | Expected Result |
|---------|----------|-----------------|
| T100220-01 | Full-bank export | Manifest `complete=true`; counts match store |
| T100220-02 | Filtered export | `complete=false` + omission notes |
| T100220-03 | Import dry-run | Report counts; DB unchanged |
| T100220-04 | Import then re-import | Second run all skips; no dup rows |
| T100220-05 | Below-threshold candidate | Rejected; logged reason |
| T100220-06 | Bundle with injected fake API key field | Export omits/redacts; test asserts absence |
| T100220-07 | `import_provider` call | Unsupported stub error; no write; creds masked |
| T100220-08 | `dsar_plaintext` export without authz | No file written; structured denial |
| T100220-09 | `ciphertext_backup` round-trip | Opaque bodies restored; no DEKs in file |

### Negative Testing
Missing manifest rejected; checksum mismatch rejected; `force` without reason/audit fields rejected if reason required by implementation.

### Verification Rule
Evidence required for completeness and idempotency claims.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence | Status |
|-------|----------------------|---------------------|-------------------|--------|
| AC-100220-01 | Manifest-backed export | T100220-01/02 | Bundle + manifest files | PASS — `t22_01_full_bank_export_is_complete_and_parses` / `t22_02_filtered_export_reports_incomplete` (clio-compliance `export_tests`): single-file bundle with embedded `completeness_manifest`, `complete=true` only for the full-bank default filter |
| AC-100220-02 | Idempotent gated import | T100220-04/05 | DB counts + reject log | PASS — `re_import_is_fully_idempotent` (second run all skips, row counts unchanged) and `admission_rejects_below_threshold_without_writes` (would_reject ≥ 1, nothing written); also MCP-level `import_dry_run_then_live_then_reimport_idempotent` (clio-mcp `portability_tools_tests`) |
| AC-100220-03 | Dry-run zero writes | T100220-03 | Transaction/row diff | PASS — `dry_run_reports_and_leaves_store_unchanged` compares `count_items` before/after; belief create path scores without writing in dry runs |
| AC-100220-04 | No plaintext secrets | T100220-06 | Scan output | PASS — `t22_06_secrets_never_reach_the_file` asserts the injected `sk-test-1234567890` value and `"dek"` keys never appear in the written file; export masks snapshot objects (`masked_clone`) and prose (`scrub_inline_secrets`) |
| AC-100220-05 | Provider stub only (FR-29 carve-out) | T100220-07 | Tool transcript + masked creds | PASS — `t22_07_import_provider_stub_unsupported_with_masked_credentials`: `{ok:false, code:"PROVIDER_IMPORT_UNSUPPORTED"}`, `writes_performed: 0`, credential params echoed last-4-masked, plaintext key absent from the response |
| AC-100220-06 | `assoc_edge` included | Graph diff | Edge ids round-trip | PASS — export `list_assoc_edges` includes edges (manifest count asserted); import restores edges by id (skip on re-import; upsert overwrite under force) |
| AC-100220-07 | DSAR plaintext vs ciphertext modes | T100220-08/09 | Mode samples + authz denial | PASS — `t22_09_ciphertext_backup_exports_opaque_items` (opaque bodies equal `inspect_content_ciphertext`, no snapshot fields, no DEKs); `t22_08_agent_actor_is_rejected_without_writing` (structured `Forbidden`, no destination file) |

### Definition of Done
- [x] `export` / `import` complete per FR-29.
- [x] Stub `import_provider` only.
- [x] Tests pass; files ≤ 450 lines (verified: max file 450 lines; gate per-file floors all >=90%).
- [x] Docs state provider matrix is later.
- [x] Required approval is obtained (downstream pipeline step).

### Completion Evidence
Round-trip artifacts, dry-run report sample, secret scan, stub transcript. — All four shipped as executable tests: round-trip/idempotency (`t22_01`, `re_import_is_fully_idempotent`), dry-run report sample (`dry_run_reports_and_leaves_store_unchanged`, report shape in `ImportReport`), secret scan (`t22_06`, `t22_07` masked-credential assertions), stub transcript (`t22_07_import_provider_stub_unsupported_with_masked_credentials` returns the structured unsupported code with masked credentials). Full-bank export → dry-run import → live import → re-import verified end to end at the MCP dispatcher level (`import_dry_run_then_live_then_reimport_idempotent`).

---

## 10. Failure Handling and Recovery

### Expected Failure Modes

| Failure | Detection | Recovery |
|---------|-----------|----------|
| Checksum mismatch | Pre-write validate | Reject bundle; no writes |
| Mid-import gate/SQL failure | Batch error | Rollback; report progress cursor for retry |
| Unsupported version | Version gate | Clear error naming supported versions |

### Rollback Strategy
Transactional import rollback. Export is write-to-destination only; failed export deletes partial destination if documented.

### Partial Completion Policy
Do not claim done if manifest or gate enforcement is missing.

---

## 11. Traceability

| Parent Requirement | Implementation Task | Verification | Acceptance Criterion |
|--------------------|---------------------|--------------|-----------------------|
| FR-29 / §4.9.5.B | Tasks 1–2 | T100220-01–05 | AC-100220-01–03 |
| NFR-6 / §4.9.7 | Task 1 | T100220-06 | AC-100220-04 |
| Index provider later | Task 3 | T100220-07 | AC-100220-05 |
| §4.5 assoc_edge | Task 1–2 | Graph tests | AC-100220-06 |

---

## 12. Phase Exit Contract

### Outputs Produced
- `memory_export_bundle` + `completeness_manifest`
- Gated idempotent `import` + dry-run report
- `import_provider_stub`

### Guarantees Provided to Downstream Phases
- Offline portability without sync.
- Import never weakens admission.

### Known Limitations
- Provider adapters not shipped (`import_provider` is a non-writing stub returning `PROVIDER_IMPORT_UNSUPPORTED`; masking of accepted credential params is still verified). A later provider phase owns the adapters.
- `ciphertext_backup` import writes the exporting node's ciphertext bytes verbatim into `content_ciphertext` (no re-encryption) and restores every metadata column, so a like-to-like restore is exact; the row is only readable when the importing node shares the exporting node's key custody. Decrypted-content restore on a node without that key custody is deferred to the node-restore phase. Export-side metadata inventory is complete in both modes.
- `import` with `force=true` overwrites items, opaque envelopes, assoc edges, and persona rows with an audited `import_force` event; it never clobbers triples/facts (bi-temporal identity — supersession stays with `correct`/`triple_end`), and it never restores tombstone rows (they are export provenance of the erasing node). Both are reported honestly in the import report notes.
- Import planning performs no store writes: every effect (item/triple/assoc/persona/task/failure/belief create, forced overwrite, opaque restore, preference upsert, confidence append) is staged and committed through the atomic batch, so a planning failure or a failed chunk leaves no row written by that chunk's transaction. Batch commit is chunked in sequential transactions of ≤50 ops (`MAX_BATCH_OPS`): each chunk is atomic, and earlier chunks persist if a later chunk fails; the import report carries a note when chunking occurred.
- Task and failure history export is capped at 10,000 rows because both listings are read into memory in one bounded query; rows beyond the cap are not exported, so reaching it sets `complete=false` with an omission note instead of silently certifying a truncated bundle as complete. Streaming those reads to lift the cap is deferred; no phase owns it yet.

- Stores containing derived-purged rows (hub-distilled rows whose ciphertext an erase transaction nulled) fail export closed with a structured `Internal` error until those rows are reconciled; compliance-shredded rows (destroyed DEK) are skipped with the tombstone attesting the erasure.
- Large banks may need filtered export (`complete=false` with omission notes).

### Downstream Prerequisites
- Phase 100230 may verify post-import index coverage.
- Phase 100240 must not treat export files as sync cursors.

### Final Status
PASS WITH DOCUMENTED LIMITATIONS

### Verification Sign-Off
- Implementer: Developer r1 (OpenCode CLI, GLM-5.3 Flash High)
- Verifier: pending (Adversary/Remediator rounds)
- Human Approver: pending
- Date: 2026-09-20

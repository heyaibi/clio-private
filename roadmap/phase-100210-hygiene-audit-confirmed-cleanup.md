# Phase 100210: Hygiene Audit and Confirmed Cleanup

### Attribution
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | OpenCode CLI (Together . GLM-5.3 Flash High) | done |
| Adversary | r1 | Antigravity CLI (Gemini 3.8 Flash) | done |
| Remediator | r1 | OpenCode CLI (Together . GLM-5.3 Flash High) | done |
| Remedy Approver | r1 | OpenCode CLI (Together . GLM-5.3 Flash Max) | approved |
| Finalize | r1 | OpenCode CLI (Go . Deepseek V4.1 Flash High) | done |

**Index slice 100210 · **Effort:** `1×` · **Scope:** `roadmap/index.md` slice 100210 (authoritative)

### Vocabulary (read first) — zero shared moniker

| Term | Enum / form | Where it lives | Must not |
|------|-------------|----------------|----------|
| **`hygiene_noise_score`** | `0.0`–`1.0` deterministic noise rank | `hygiene_audit` result (§4.9.5.A) | Share meaning with **`admission_score`** (§4.2) |
| **`hygiene_audit`** | Read-only ranked noise scan | Ops additive tools | Mutate memory or alias `inspect` / `diagnose` |
| **`hygiene_clean`** | Confirmed `flag` / `archive` / `discard` / `keep` | Ops additive tools | Invoke **`compliance_erase`** / `erase_request` or crypto-shred |
| **`hygiene_archive`** | Reversible exclusion from active retrieval | Hygiene action `archive` | Be treated as compliance erasure or bi-temporal `invalidate` |
| **`hygiene_audit_log`** | Durable cleanup log rows | Ops store (FR-33) | Be conflated with **`item_audit_trail`** (`audit_trail`) or **`compliance_tombstone`** |
| **`hygiene_log_list`** | Callable masked list of hygiene log rows | Ops additive tool / inspect filter | Be conflated with `hygiene_audit` (noise scan) |
| **`ops_discard`** | Operations removal from active use | Core `discard` and hygiene action `discard`/`delete` | Satisfy GDPR Art. 17 / `erase_request` |
| **`delete` (hygiene alias)** | Documented alias of hygiene `discard` | `hygiene_clean` only | Imply physical wipe or DEK destruction |

Noise formulas: [phase-100210-appendix-noise-scoring.md](phase-100210-appendix-noise-scoring.md).

---

## 1. Objective

### Goal
Ship ranked **`hygiene_audit`** and confirmed **`hygiene_clean`** for operational anti-bloat (P1, FR-33, §4.9.5.A): candidates ranked by descending `hygiene_noise_score`, secret masking on all hygiene I/O, and a durable `hygiene_audit_log`. Cleanup is **operations removal only**—not supersession and not compliance erasure (PR-6, §7.4, FR-23).

### Expected Outcome
- `hygiene_audit(bank?, min_score?, limit?, offset?)` returns candidates `{item_id, noise_score, noise_reasons[], suggested_action, preview?}` ranked by descending noise score; read-only; deterministic under fixed config.
- `hygiene_clean(candidates|item_ids, action?, confirm?)` supports `flag`, `archive`, `discard` (`delete` alias), and `keep`; mutations require `confirm=true`; otherwise dry-run counts only.
- Secret-class hits force redacted previews; DEKs, API keys, tokens, and sync secrets appear only masked (last-4 / redacted).
- Every mutating clean (and dry-run SHOULD) appends a durable `hygiene_audit_log` entry; item-level `discard`/`archive` also emit FR-15 telemetry.
- Calling hygiene NEVER destroys `subject_dek` or writes `compliance_tombstone`.
- Machine-readable MCP schemas published and registered on **stdio and Streamable HTTP** (identical semantics; pinned MCP revision) for hygiene tools.
- `hygiene_log_list(limit?, offset?)` (or equivalent inspect filter) returns masked durable log rows so operators can review cleanups.

### Parent Requirement
`requirement.md` (v1.9+) — P1, P12, PR-5, PR-6, PR-8, §4.9.5.A Hygiene, §4.9.7, §7.4, FR-15, FR-23, FR-33.

### Design References (non-normative)
- **Archive-before-discard:** [Engrava memory hygiene](https://github.com/sovantica/engrava/blob/main/docs/memory-hygiene.md) — default reversible archive; hard removal is a separate confirmed step.
- **Secret-safe audit I/O:** [Memstem secrets guidance](https://github.com/Memstem/memstem/blob/main/docs/secrets.md) — never log secret values; redact previews; address by id.
- **Explainable noise ranking:** Mnemosyne-style noise audit + AWS AgentCore lifecycle scoring — multi-factor scores with auditability, not silent GC.

---

## 2. Scope Boundaries

### In Scope
- Read-only `hygiene_audit` scanner with pagination, bank scope, and `min_score`.
- Deterministic noise scoring per [phase-100210-appendix-noise-scoring.md](phase-100210-appendix-noise-scoring.md).
- Confirmed `hygiene_clean` with dry-run default when `confirm` is absent/false.
- Actions: `flag` (metadata only), `archive` (exclude from default retrieve; reversible), `discard`/`delete` (ops removal via existing discard path), `keep` (apply suggested actions).
- Secret detection + masking on responses, dry-run reports, and hygiene logs.
- Durable `hygiene_audit_log` **and** callable `hygiene_log_list` (masked).
- MCP + CLI/tool bindings on **stdio and Streamable HTTP** with identical semantics.

### Explicitly Out of Scope
- Compliance crypto-shredding (`erase_request` — Phase 100190).
- Bi-temporal supersession / `invalidate` authorship (Phase 100080).
- Co-activation weight prune policy changes (Phase 100130 owns formulas; hygiene may discard items that then orphan edges via existing prune hooks).
- JSON export/import (Phase 100220), doctor/reindex (Phase 100230), sync (Phase 100240).
- Automatic background GC loops that mutate without an explicit `hygiene_clean` call.

### Must Not Change
- PR-6 / §7.4 three-way separation: invalidate ≠ ops discard/hygiene ≠ compliance erase.
- Admission gates on any path that *writes new* long-term content (hygiene itself does not admit new items).
- Existing `discard` confirmation rules for harness invocation (§4.9.2).
- Phase 100180 `item_audit_trail` schema ownership.

### Scope Expansion Rule
If work outside this scope appears necessary:
1. Stop.
2. Document the reason.
3. Request clarification or approval.
4. Do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- Phase 100160/100170: MCP tool surfaces available.
- Phase 100180: telemetry + `audit_trail` for item-level history.
- Phase 100190: `erase_request` boundary exists so hygiene can explicitly refuse DEK destruction.
- Phase 100040/100120: item metadata sufficient for utility/staleness proxies; retrieve exclusion hooks for archive.
- Phase 100200 recommended: `batch` available for atomic multi-item confirmed cleans.

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| Ops `discard` path | Logged active-use removal without DEK destroy | Call discard; KMS key still present |
| Retrieve eligibility filter | Can exclude archived items from default search | Archived id absent from retrieve |
| Telemetry emitter | Accepts hygiene operation events (FR-15) | Event row present |
| Secret masker | Shared redaction helper (config/hygiene/diagnose) | Preview shows no raw key |

---

## 4. Existing-System Discovery

### Required Discovery
- Locate existing `discard` implementation and confirmation gating.
- Identify retrieve/compose filters to attach `hygiene_archive` exclusion.
- Find shared secret-masking utilities from config/sync foreshadow paths.
- Confirm Phase 100190 guards that block DEK destruction outside `erase_request`.
- Check whether `batch` can wrap multiple hygiene discards atomically.

### Discovery Output
Before implementation, the agent must report:
- Relevant subsystems for discard, retrieve filters, telemetry.
- Existing secret detectors/maskers reusable here.
- Archive representation choice (flag column vs status enum).
- Assumptions confirmed/contradicted.
- Questions requiring clarification.

### Repository Adaptation Rule
Concrete paths and type names come from the repository. This plan names logical responsibilities only.

---

## 5. Implementation Specification

### Task 1: Noise Scoring Engine (FR-33, appendix)

#### Intent
Compute deterministic `hygiene_noise_score` and `noise_reasons[]` for candidate items.

#### Required Capability or Behavior
- Implement scoring per [phase-100210-appendix-noise-scoring.md](phase-100210-appendix-noise-scoring.md).
- Weights tunable via deployment config / ranking-adjacent knobs; fixed config ⇒ stable order.
- Secret hits force high score floor and secret-class reason.

#### Architectural Responsibility
Hygiene scoring module (ops layer).

#### Required Changes
1. Pattern packs for terminal/stack/heartbeat/command/secret classes.
2. Near-duplicate and staleness/utility proxies from existing metadata.
3. Unit fixtures proving deterministic ordering.

#### Implementation Constraints
- Do not reuse the name `admission_score` for noise.
- Scoring MUST NOT mutate stores.

#### Expected Result
Identical fixtures + config yield identical ranked id lists.

---

### Task 2: `hygiene_audit` Read Path

#### Intent
Expose read-only ranked audit without writes.

#### Required Capability or Behavior
- Parameters: bank scope, `min_score`, `limit`/`offset` (or equivalent).
- Return ranked candidates with optional truncated/redacted `preview`.
- MUST NOT mutate memory (including flags).

#### Architectural Responsibility
Hygiene audit service + MCP/CLI binding.

#### Required Changes
1. Scanner over selected banks.
2. Pagination and stable secondary sort (score desc, then `item_id`).
3. Schema publication for `hygiene_audit`.

#### Expected Result
Operators see ranked noise without state change.

---

### Task 3: `hygiene_clean` Confirmed Mutator

#### Intent
Apply flagged cleanup actions only with confirmation; otherwise dry-run.

#### Required Capability or Behavior
- Inputs: candidate list or ids; optional explicit `action`; `confirm`.
- Actions:
  - `flag` — mark for review; remain in retrieve.
  - `archive` — reversible exclusion from default retrieve (`hygiene_archive`).
  - `discard` / `delete` — call ops discard path; document `delete` as non-compliance alias.
  - `keep` — apply each candidate’s `suggested_action`.
- Without `confirm=true`: zero writes; return would-flag / would-archive / would-discard counts.
- With `confirm=true`: mutate; emit FR-15 events; append `hygiene_audit_log`.
- Refuse any option that would call `erase_request` or destroy DEKs.

#### Architectural Responsibility
Hygiene clean controller; reuses ops discard; never compliance erase.

#### Required Changes
1. Dry-run reporter.
2. Action executors with explicit boundary asserts against erase.
3. Optional `batch` wrapping for multi-id confirmed discard/archive.

#### Implementation Constraints
- Harness destructive confirmation rules still apply (§4.9.2).
- `archive` MUST be reversible via a documented restore/unarchive path or inverse metadata clear (minimal: clear archive flag).

#### Expected Result
Confirmed cleans mutate; unconfirmed calls only report.

---

### Task 4: Secret Masking and Hygiene Audit Log

#### Intent
Keep hygiene I/O and logs secret-safe and reviewable.

#### Required Capability or Behavior
- Mask credentials, DEKs, API keys, tokens, sync secrets in audit responses, clean reports, and log rows.
- Durable log entry shape: `{timestamp, actor, bank, action, item_ids[], noise_scores?, confirm, dry_run, result}`.
- Expose **`hygiene_log_list(limit?, offset?)`** (or equivalent inspect filter) returning masked log rows — required, not docs-only.
- Operators can also see item `audit_trail` effects for archive/discard.

#### Architectural Responsibility
Hygiene log store + shared masker + list tool binding (stdio + Streamable HTTP).

#### Required Changes
1. Persist `hygiene_audit_log` (dedicated table/collection).
2. Implement `hygiene_log_list` (or inspect filter) with pagination; all fields masked.
3. Ensure secret-class previews never include raw secrets.
4. Register schemas on both MCP transports.

#### Expected Result
Every cleanup is reconstructible via callable list + item audit without secret leakage.

---

### Task 5: Conformance Tests

#### Intent
Lock FR-33 / PR-6 boundaries with executable checks.

#### Required Capability or Behavior
- Deterministic ranking fixture.
- Dry-run writes nothing.
- Archive hides from retrieve; unarchive restores.
- Discard does not destroy DEK.
- `delete` alias maps to discard.
- Masking on secret-class preview.

#### Architectural Responsibility
Test harness.

#### Expected Result
CI-green suite on both backends where applicable.

---

### Implementation Freedom
The agent may choose archive storage representation, scanner batching, and log list UX, provided behavior and vocabulary locks hold.

---

## 6. Agent Execution Rules

### Allowed Actions
- Add hygiene scoring, audit, clean, log modules.
- Reuse discard and retrieve filters.
- Add MCP schemas and tests.
- Local refactors needed to share secret masking.

### Forbidden Actions
- Alias hygiene to `erase_request` or DEK destroy.
- Auto-clean without explicit `hygiene_clean`.
- Log unmasked secrets.
- Change admission or supersession semantics.
- Broad unrelated refactors; dependency upgrades without approval.

### Agent Decision Boundary
May decide module layout (≤450 lines/file), archive flag representation, and restore UX details.

Must request approval for:
- Automatic scheduled hygiene mutation loops.
- Changing discard semantics.
- Exporting hygiene logs with payload previews by default.

### Mandatory Stop Conditions
Stop if discard cannot be invoked without erase, if retrieve cannot exclude archived items, or if secret masking cannot be shared safely.

---

## 7. Security Constraints

### Required Controls
- Confirmation gate on mutating clean.
- Secret masking on all hygiene I/O and logs.
- Authorization: hygiene respects bank/actor scope of the caller.

### Sensitive Data Rules
- Never log raw DEKs, API keys, tokens, or sync secrets.
- Secret-class `preview` always redacted.

### Security Acceptance Conditions
- Hygiene cannot shred keys.
- Secret fixtures never appear plaintext in tool output or hygiene log.

---

## 8. Test and Verification Strategy

### Required Tests
- [x] Unit: noise score determinism + secret floor (`clio-hygiene` `scoring_tests`: identical inputs yield identical scores; `secret_hit_floors_score_at_ninety`)
- [x] Integration: audit read-only (`t21_01_*`, `audit_is_read_only_and_min_score_filters`: inspect rows byte-identical before/after audit, no log rows)
- [x] Integration: clean dry-run vs confirm (`t21_02_dry_run_counts_only_and_writes_nothing`, `t21_03_confirmed_archive_hides_from_default_retrieve`)
- [x] Integration: archive retrieve exclusion (lexical visibility probe empty while archived; `unarchive_restores_retrieve_eligibility` restores it)
- [x] Security: masking + no DEK destroy (`t21_05` redacted preview; `t21_04_discard_and_delete_alias_keep_dek_alive` asserts `subject_dek_destroyed == false` and no tombstones)
- [x] Regression: invalidate/erase paths unchanged (workspace suite green; `pg_hygiene_tests` parity; erase/erase_request tests untouched and passing)

### Required Test Scenarios

| Test ID | Scenario | Expected Result |
|---------|----------|-----------------|
| T100210-01 | Audit with fixed fixtures | Stable descending rank by `hygiene_noise_score` |
| T100210-02 | Clean without `confirm` | Counts only; zero mutations |
| T100210-03 | Clean `archive` with confirm | Item excluded from default retrieve; still readable via inspect/id |
| T100210-04 | Clean `discard`/`delete` | Ops removal; DEK still present |
| T100210-05 | Secret-class candidate | Preview redacted; score ≥ 0.90 |
| T100210-06 | Attempt erase via hygiene | Rejected; no tombstone/DEK destroy |
| T100210-07 | `hygiene_log_list` after confirmed clean | Masked log row present and listable |

### Negative Testing
Invalid actions rejected; unauthorized bank scope blocked; partial failure does not leave half-applied confirmed batch without error.

### Verification Rule
Claims need test output or inspection evidence.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-100210-01 | Ranked read-only `hygiene_audit` | T100210-01 | PASS — `t21_01_ranking_is_deterministic_and_descending` + `t21_01_secret_candidate_ranks_top_with_redacted_preview`: identical fixtures/config yield identical descending rank, secret floor 0.90, `min_score` filter verified |
| AC-100210-02 | Confirmed clean + dry-run | T100210-02/03 | PASS — dry-run: counts only, zero writes, `dry_run=1` log row; confirmed: `applied` ids, archive marker set, inspect row shows `archived` |
| AC-100210-03 | Secret masking | T100210-05 | PASS — secret-class candidate preview is exactly `[REDACTED]`; log detail rows carry ids/scores/labels only (asserted no `api_key`/`gist` substrings) |
| AC-100210-04 | Durable `hygiene_audit_log` + `hygiene_log_list` | Log query / T100210-07 | PASS — one masked row per item per action (SQLite + Postgres parity in `pg_hygiene_tests`); listable bank-scoped and paginated |
| AC-100210-05 | Not compliance erasure | T100210-04/06 | PASS — discard via ops path leaves subject DEK alive (`subject_dek_destroyed == false`), zero tombstone rows; `erase_request` action label rejected (`InvalidArgument`) |
| AC-100210-06 | FR-15 telemetry on discard/archive | Telemetry query | PASS — `audit_trail` shows `archive` / `discard` / `hygiene_flag` events recorded in the same transaction as each mutation |
| AC-100210-07 | Dual MCP transports | Schema/conformance | PASS — all three tools in `bound_tools()` (both transports share `write_tools::dispatch` + `tools/list` from `catalog_defs`); `hygiene_tools_are_schema_published` validates inputSchemas; `hygiene_tools_tests` (11 tests) exercise MCP dispatch |

### Definition of Done
- [x] In-scope tools implemented and schema-published (`hygiene_audit`, `hygiene_clean`, `hygiene_log_list` — schemas in `schema_hygiene_defs.rs`, bound on stdio + Streamable HTTP).
- [x] Appendix scoring defaults implemented (`HygieneWeights` 0.35/0.25/0.15/0.15/0.10 + 90-day stale half-life in `clio-config::hygiene_knobs`, tunable via `ranking_env_set` with renormalize-or-reject).
- [x] All AC pass with evidence (see table above; workspace test suite green).
- [x] No unauthorized contract changes (discard/erase/invalidate paths untouched; `Store` gained only `item_is_archived`; `ItemInspectRow` gained `archived`).
- [x] Rust files ≤ 450 lines (largest touched: `clio-retrieve/src/hybrid.rs` 450, `clio-config/src/ranking.rs` 434).
- [x] Required approval is obtained (downstream pipeline step).

### Completion Evidence
- **Implementation:** new crate `clio-hygiene` (slice 100210): `detect.rs` (pattern packs + secret-class detection reusing `clio-config::secret::scrub_inline_secrets` as detector), `scoring.rs` (deterministic `hygiene_noise_score`, secret floor 0.90, appendix action bands), `audit.rs` (bank-scoped ranked scan, near-duplicate pairing, fail-soft staleness via ISO day math, masked previews, pagination), `clean.rs` (dry-run counts / confirmed flag-archive-discard-keep with per-item durable log rows, batch abort with applied-vs-pending, `delete` alias). Store contract: `clio-store::HygieneStore` trait (flag set/clear, archive/unarchive, hygiene log insert/list) implemented on SQLite and Postgres with FR-15 `audit_events` rows in the same transaction; `items.archived_at` column (schema v8, schema files edited directly, no migrations); `Store::item_is_archived` probe; dense/lexical visibility SQL excludes archived items on both backends; retrieve's `fetch_items` also filters archived ids (graph-expansion path). Ranking-env knobs: `hygiene` weights + `hygiene_stale_half_life_days` with renormalize-or-reject patch validation. MCP: `hygiene_tools.rs` dispatch + schemas, tools bound in `bound_write_tools`/`bound_read_tools` (shared by stdio and Streamable HTTP).
- **Test output:** 31+3+34 unit/integration tests in `clio-hygiene`; 11 MCP hygiene tests; SQLite+Postgres parity (`pg_hygiene_tests`); full workspace `make check` (fmt + clippy -D warnings + tests) green. Final gate: `cargo llvm-cov --workspace --locked --summary-only --fail-under-lines 90 --fail-under-functions 90` exit 0 — TOTAL lines 94.68%, functions 98.69%, and 0 of 192 reported files below 90% on either metric (per-file scan of the report).
- **Sample transcript (fixture bank):** secret candidate `itm-c` ranks first with `noise_score ≥ 0.90`, `noise_reasons: ["secret_credential"]`, `suggested_action: "discard"`, `preview: "[REDACTED]"`; `hygiene_clean(candidates, action=keep, confirm=false)` reports `would_discard: N` with zero writes; confirmed run returns `applied: [...]` and `hygiene_log_list` returns masked rows `{action, actor, confirmed, dry_run, item_id, noise_score, detail:{result, batch_id}}`.
- **Known limitations:** (a) pattern packs are best-effort — novel secret formats can evade detection, owned by this phase's scoring module (upgrade path: richer detectors/entropy sources); (b) no automatic scheduled cleaner — every mutation requires an explicit `hygiene_clean` call (per phase scope); (c) staleness uses `created_at` as the last-touch proxy because retrieval/reinforce telemetry is not yet a scannable column (same crate owns the upgrade); (d) near-duplicate pairing is O(n²) over scanned rows with a 64-token sketch (`ponytail:` ceiling in `audit.rs` — upgrade to an index when banks grow past ~5k).

---

## 10. Failure Handling and Recovery

### Expected Failure Modes

| Failure | Detection | Recovery |
|---------|-----------|----------|
| Scorer timeout on huge bank | Deadline / pagination | Return partial page + `incomplete` signal; do not mutate |
| Discard fails mid-batch | Per-id error | Abort batch; report applied vs pending |
| Masker miss | Secret detector test | Fail closed: omit preview |

### Rollback Strategy
`flag`/`archive` are reversible metadata. `discard` follows existing ops discard recovery (not erase). Log rows remain for audit.

### Partial Completion Policy
Do not claim phase complete if log or masking is missing.

---

## 11. Traceability

| Parent Requirement | Implementation Task | Verification | Acceptance Criterion |
|--------------------|---------------------|--------------|-----------------------|
| FR-33 / §4.9.5.A | Tasks 1–4 | T100210-01–05 | AC-100210-01–04 |
| FR-15 | Task 4 | Telemetry | AC-100210-06 |
| FR-23 / PR-6 / §7.4 | Task 3 | T100210-04/06 | AC-100210-05 |

```text
Requirement → Capability → Implementation → Test → Evidence
```

---

## 12. Phase Exit Contract

### Outputs Produced
- `hygiene_audit` / `hygiene_clean` tools
- `hygiene_audit_log` store + masking
- Noise scoring module + appendix defaults

### Guarantees Provided to Downstream Phases
- Ops cleanup exists without compromising erase semantics.
- Archived items are filterable for export/doctor scopes.

### Known Limitations
- Pattern packs are best-effort; not a guarantee against novel secret formats.
- No automatic scheduled cleaner in first release.

### Downstream Prerequisites
- Phase 100220 may exclude archived/discarded per filter.
- Phase 100230 must not treat hygiene log as DB corruption.

### Final Status
PASS | PASS WITH DOCUMENTED LIMITATIONS | BLOCKED | FAILED

### Verification Sign-Off
- Implementer: [Name/Agent]
- Verifier: [Name/Agent]
- Human Approver: [Name, if required]
- Date: [YYYY-MM-DD]

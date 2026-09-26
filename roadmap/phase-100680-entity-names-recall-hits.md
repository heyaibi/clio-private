# Phase 100680: Entity Names on Recall Hits (`entities[]`)

### Attribution
Rounds below record plan authorship; implementation sign-off is in §12.
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r2 | OpenCode CLI (Go . Space Bunny Free Max) | done |
| Adversary | r1 | OpenCode CLI (Go . Space Bunny Free Max) | done |
| Remediator | r1 | OpenCode CLI (Together . GLM-5.3 Flash High) | done |
| Remediator | r2 | OpenCode CLI (Together . GLM-5.3 Flash High) | done |
| Remedy Approver | r2 | OpenCode CLI (Go . Space Bunny Free Max) | approved |
| Finalize | r1 | OpenCode CLI (Go . Space Bunny Free Max) | done |

Round numbers count invocations, so they match the run log files. Developer
r1 was the interrupted attempt that only reached the pre-change baseline gate
and left no row; the implementation is developer r2 (`ledger.json` names
`developer-task-r2.md` as the authoritative developer task file). Remedy
approver r1 sent the work back (`REMEDY_REJECTED`) and, per the table contract,
leaves no row; the ledger transcript holds that round.

**Capability phase 100680** · **Effort:** ~2–3 days · **Status:** Plan ready · **Parent:** gap analysis `gaps/recall-result-fidelity-gap-analysis.md` §4.1, §6, §7, §8 decision 3+5, §10.2; requirement FR-4 / §4.4, PR-4, FR-20 / §4.9.2 item 2, §4.9.5.C (health surfaces), §4.12 and §7.4 (content boundary)

### Vocabulary (read first) — zero shared moniker

| Term | Meaning in this phase | Must not be confused with |
|------|------------------------|----------------------------|
| **entity name** | The span-verified `entity` string already stored in an item's snapshot | A named-entity table, an NER system, or SPO triple subject/object |
| **`entities[]`** | A per-hit array of entity-name strings on `ScoredHit` | A ranking signal; a truth claim; the export bundle's `entities` payload |
| **snapshot `entity`** | The default extractive field (`entity`, required string) verified as a contiguous NFC source substring | The `snapshot` field generally, which is arbitrary JSON |
| **coverage limit** | The documented set of hit kinds that legitimately return an empty `entities[]` | A bug or a partial result |

This phase exposes an already-verified snapshot value. It does not infer, link, or rank by entities.

---

## 1. Objective

### Goal
Expose a per-hit `entities[]` array sourced only from the item's span-verified snapshot `entity` value, with documented coverage limits and minimal trim-only canonicalization, while keeping entity names out of PII-safe surfaces (`warnings`, the `explanation` trace, telemetry, and health surfaces). The field is added to `ScoredHit`, not the frozen `RetrieveHit`, and is exposed identically on MCP, in-process, and CLI reads.

### Expected Outcome
- `ScoredHit` carries `entities: []` (an array of strings), empty when the item has no verified snapshot `entity`.
- The value is the span-verified snapshot `entity`, trimmed only; no inferred or linked entities are added.
- Coverage limits are documented: triple carriers, hub-distill, beliefs, snapshot-less items, and non-default field lists return empty.
- Entity names never appear in `warnings`, the `explanation`/`explain` trace, telemetry, or health surfaces.
- MCP, in-process, and CLI expose the same `entities` names and semantics.

### Parent Requirement
`requirement.md` — FR-4 / §4.4 (snapshot entities are span-verified); PR-4 / §4.4 (only the snapshot is authoritative; a retrieval-side link would be inferred and non-authoritative); FR-20 / §4.9.2 item 2 (binding identity); §4.9.5.C (health-surface PII) and §4.12/§7.4 (content boundary and redaction). Gap source: `gaps/recall-result-fidelity-gap-analysis.md` §4.1.

### Design References (source-verified at plan time)
- There is no named-entity table, index, link, or matching in the repository. `sql/001_core.sql:640-666` `entity_id`/`entity_kind` are sync-journal columns, not named entities.
- The `triples` table (`sql/001_core.sql:231-250`) has no `item_id` index; `crates/clio-store/src/store.rs:272,278,397` offers `get_triple`/`query_triples`/`list_triples` but no by-item query.
- The default snapshot fields are `entity` (required string), `amount`, `date` (`crates/clio-write/src/schema.rs:59-65`); `match_entity` verifies a contiguous NFC source substring (`crates/clio-write/src/verify_entity.rs:28`).
- `snapshot` is `Option<Value>` (`crates/clio-types/src/item.rs:266`); `MemoryItem` is `crates/clio-types/src/item.rs:242-281` and has no `context` field (relevant to the Phase 100601 track).
- Triple carriers store `{subject, predicate, object}` with no `entity` (`crates/clio-write/src/triple.rs:189-193`); SPO subject/object are `crates/clio-types/src/triple.rs:128,132`.
- The decrypted snapshot is in hand where hits are built: `finalize` iterates the fetched `MemoryItem` (`crates/clio-retrieve/src/finalize.rs:83-113`, item loop at `:94-112`), loaded at `crates/clio-retrieve/src/hybrid.rs:382-415`.
- Cross-binding propagation is automatic for the JSON payload: MCP/in-process/CLI serialize `RetrieveOutcome` wholesale (`read_retrieve.rs:90`, `surface.rs:207`, CLI dispatch `cli_read_core.rs:90-107`), so a new `ScoredHit.entities` field reaches all three by serde. The deliberate work is the boundary exclusion (below) and keeping entities out of the `explain` trace (`read_retrieve.rs:119-132`; Phase 100740).
- `ExportEntities` in `crates/clio-compliance/src/bundle.rs:131-163` is unrelated (bundle payload arrays).
- `crates/clio-types/src/item.rs` is 370 lines.

---

## 2. Scope Boundaries

### In Scope
- Adding `entities: Vec<String>` to `ScoredHit`.
- Populating it from the item's span-verified snapshot `entity` value with trim-only canonicalization.
- Documenting empty-coverage hit kinds.
- Excluding entity names from PII-safe/telemetry surfaces.
- Cross-binding exposure and parity tests.

### Explicitly Out of Scope
- Any named-entity store, index, NER, or entity linking.
- Triple-based enrichment (no by-item query and no `item_id` index exist).
- Entity-overlap matching or reason (Phase 100700).
- Entity-based ranking (any future ranking leg must fuse by rank and needs separate approval).
- Adding `entities` to the frozen `RetrieveHit`.
- Persisting a new entity field or changing extraction.
- Score floors / entity-inclusion controls (Phase 100780).

### Must Not Change
- The frozen `RetrieveHit` contract.
- Snapshot authority: `entities[]` is derived from the snapshot, never from the gist, and never a truth claim.
- Span-verification rules (FR-4): no entity value is exposed unless it was already verified at write time. This phase did not change those rules; the write-time span check runs on the default `store`/`batch` admission path, while a bundle import and an operator `correct`/`update` store the caller's snapshot as supplied, so a name written through those paths is republished without a span check (see §12 Known Limitations).
- The PII/content boundary: `entities[]` are content-derived names and MUST NOT enter `warnings`, `explanation`, telemetry, or health surfaces (health-surface PII rule §4.9.5.C; transparency/content boundary §4.12 and §7.4).
- Ranking, ordering, fusion, and budgets.
- Existing MCP tool names/schemas beyond the added `entities` array.

### Scope Expansion Rule
If work outside this scope appears necessary:
1. Stop.
2. Document the reason.
3. Request clarification or approval.
4. Do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- Phase 100620 accepted: `ScoredHit` carries the new display fields and the consolidated structure.
- The snapshot `entity` value is already span-verified at write time (FR-4).
- The PII/content boundary decision for entities is recorded (gap analysis §8 decision 5).
- Phases 100366/100368 (complete) own the CLI read path through which this field's JSON propagates (`command-ownership.md`).

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| `ScoredHit` | Carries display fields | Phase 100620 acceptance |
| Snapshot `entity` | Verified and stored for default-field writes | `schema.rs`/`verify_entity.rs` inspection |
| Fetched item at finalize | `MemoryItem` with decrypted snapshot available | `finalize.rs:94-112` inspection |
| Bound surfaces | A defined boundary list (`warnings`, trace, telemetry, health) | Requirement §4.9.5.C (health PII), §4.12/§7.4 (content); code inspection |
| Bindings | MCP/in-process/CLI projections | Conformance/CLI tests |

---

## 4. Existing-System Discovery

The agent MUST re-verify the following before editing; the facts below were confirmed at plan time.

### Required Discovery
- Confirm where the fetched `MemoryItem` snapshot is available during hit construction.
- Confirm the exact default-field and snapshot shapes across write paths (default fields, triples, hub-distill, beliefs, non-default field lists).
- Confirm `match_entity` verification and that no unverified `entity` can be stored.
- Enumerate every surface that must not receive entity names (`warnings`, `explanation`/`explain`, telemetry, health) and confirm none derives from `ScoredHit` wholesale.
- Confirm the three binding projections and their tests.
- Confirm `item.rs` size against the 450-line limit.

### Discovery Output
Before implementation, the agent must report:

- Relevant subsystems identified
- Existing implementation approach
- Relevant contracts/interfaces
- Existing test coverage
- Architectural constraints discovered
- Assumptions confirmed
- Assumptions contradicted
- Questions requiring clarification

### Current Repository Findings at Plan Time
- The snapshot is in hand in `finalize`; no new storage or fetch is required.
- Triple carriers and several other write paths have no `entity`, so empty `entities[]` is expected for them and must be documented.
- There is no by-item triple query and no `item_id` index, so triple enrichment is genuinely deferred.
- The `explain` trace is a separate hand-written projection (`crates/clio-mcp/src/read_retrieve.rs:118-150`), which is why entities must be deliberately excluded there and why Phase 100740 de-drifts it.
- `item.rs` is 370 lines.

### Repository Adaptation Rule
The agent must determine concrete implementation locations from the actual repository. The plan does not prescribe file paths or module names unless they are an externally required contract. The `entities` field name and its snapshot-only source are the contract for this phase.

---

## 5. Implementation Specification

### Task 1: Extract the Verified Entity from the Snapshot

#### Intent
Derive `entities[]` from the span-verified snapshot value without inventing new entity data.

#### Required Capability or Behavior
- When the item's snapshot has a string `entity` field, `entities` contains that value after trim-only canonicalization.
- When there is no snapshot, no `entity`, or a non-string `entity`, `entities` is empty.
- The value is never taken from the gist, never inferred, and never linked from triples.
- Only values already verified at write time are exposed.

#### Architectural Responsibility
`clio-retrieve` owns extraction of the snapshot value into the hit field. `clio-write` continues to own verification; this phase does not re-verify.

#### Required Changes
1. Add `entities` to the hit structure and populate it during hit construction.
2. Implement trim-only canonicalization and document the choice.
3. Define and document the empty-coverage cases.
4. Add unit tests for each write shape (default fields, triple carrier, hub-distill, belief, snapshot-less, non-default fields).

#### Implementation Constraints
- No new storage, index, or query.
- No NER or linking.
- Do not treat the entity as authoritative content beyond its existing verified snapshot status.
- Keep files ≤450 lines.

#### Expected Result
A hit whose snapshot has an `entity` exposes it in `entities[]`; every other hit exposes an empty array.

### Task 2: Expose `entities[]` Without Leaking Into PII-Safe Surfaces

#### Intent
Serialize the entity names only on the intended read surfaces, keeping them out of diagnostics and telemetry.

#### Required Capability or Behavior
- `entities[]` appears identically on MCP, in-process, and CLI JSON reads.
- Entity names do not appear in `warnings`, the `explanation`/`explain` trace, telemetry events, or health surfaces.
- Empty arrays serialize as `[]`, not omitted inconsistently across bindings.

#### Architectural Responsibility
`clio-retrieve` owns the value; each binding owns its projection and must not add the value to any disallowed surface.

#### Required Changes
1. Update MCP, in-process, and CLI hit projections together.
2. Audit and, if needed, explicitly exclude entities from `warnings`, the explain trace, telemetry, and health.
3. Add parity tests and a boundary test asserting entities are absent from the disallowed surfaces.
4. Update any conformance volatile mask or fixture.

#### Implementation Constraints
- Do not add entity names to any log, warning, or trace.
- Do not change the frozen contract.
- Keep files ≤450 lines.

#### Expected Result
All three bindings expose the same `entities`; no PII-safe surface contains an entity name.

### Implementation Freedom
The agent may choose the internal representation (for example a helper returning `Vec<String>`), the exact trim semantics, and test placement, provided the snapshot-only source, empty-coverage documentation, and boundary exclusion hold.

---

## 6. Agent Execution Rules

### Allowed Actions
- Modify `clio-retrieve` hit construction, the three binding projections, and tests.
- Add documented empty-coverage handling and boundary assertions.

### Forbidden Actions
- Add an entity store/index, NER, triple enrichment, or a by-item triple query.
- Add entity ranking or matching (Phase 100700).
- Put entities on `RetrieveHit` or into `warnings`/trace/telemetry/health.
- Add dependencies, delete tests, or claim completion without evidence.

### Agent Decision Boundary
The agent may decide canonicalization details and test organization. The agent must request approval for: adding triple enrichment, adding an entity index, placing entities on the frozen contract, or any ranking use.

### Mandatory Stop Conditions
Stop and report if: the snapshot is unavailable at hit construction; an unverified entity could be exposed; entities would have to enter a disallowed surface to satisfy a test; or correctness cannot be verified.

---

## 7. Security Constraints

### Required Controls
- Entity names are content-derived; they are subject to the same read authorization as the item content.
- Entity names MUST NOT enter `warnings`, the `explanation`/`explain` trace, telemetry, or health surfaces (health PII rule §4.9.5.C; content boundary §4.12/§7.4). Scoped to the new read-side `entities[]` projection: the write path's pre-existing verify-telemetry snapshot preview carries the snapshot's own `entity` value, which this phase neither introduced nor changed, and whether that preview may carry a name stays a requirement-owner decision (§12 Known Limitations).
- Entities follow existing subject-erasure behavior because they are derived from the item snapshot; this phase adds no durable entity store that could survive erasure.
- Bank isolation unchanged.

### Sensitive Data Rules
- Never log entity names outside the authorized read payload; scoped like the Required Controls bullet above to the new read-side `entities[]` projection. The write path's pre-existing verify-telemetry snapshot preview carries the snapshot's own `entity` value; whether that preview may carry a name is the requirement-owner decision recorded in §12 Known Limitations, not a log site this phase introduced.
- Never commit secrets.
- Reuse existing authorization and redaction.

### Security Acceptance Conditions
- A boundary test proves the read-side `entities[]` projection is absent from `warnings`, the explain trace, telemetry, and health. For telemetry the test additionally asserts the probe name reaches no field except the write path's pre-existing snapshot preview (see Required Controls above and §12).
- An erased/snapshot-less item yields an empty `entities[]`.

---

## 8. Test and Verification Strategy

### Required Tests
- [x] Unit tests (snapshot with `entity`, empty string, non-string, no snapshot, triple carrier)
- [x] Integration tests (entity reaches the finalized hit)
- [x] Contract tests (binding parity; frozen contract unchanged; empty = `[]`)
- [x] End-to-end tests (real CLI/MCP `recall` shows `entities`)
- [x] Regression tests (existing suites; no entity in disallowed surfaces)
- [x] Security tests (the read-side `entities[]` projection is absent from warnings/trace/telemetry/health; in telemetry the probe name reaches no field except the pre-existing snapshot preview)
- [x] Failure-mode tests (snapshot-less item; erased item)

Evidence per test class is in §9 "Evidence (actual, 2026-09-26)". The failure-mode
row is split in two: a snapshot-less item is a real test
(`empty_coverage_shapes_survive_the_pipeline_as_empty_arrays`), while a
content-erased item cannot be returned as a hit at all — its payload no longer
decrypts, so the read never reaches hit assembly. That half is covered by source
inspection plus the existing erasure suites, not by a new test; see §9
"Verification limits".

### Required Test Scenarios

| Test ID | Scenario | Expected Result |
|---------|----------|-----------------|
| T100680-01 | Default-field write with snapshot `entity` | `entities: ["<verified value>"]` |
| T100680-02 | Empty-string or non-string `entity` | `entities: []` |
| T100680-03 | Triple carrier | `entities: []` |
| T100680-04 | Hub-distill / belief / snapshot-less / non-default fields | `entities: []` |
| T100680-05 | `entity` with surrounding whitespace | Trimmed value |
| T100680-06 | MCP, in-process, CLI for same store | Identical `entities` |
| T100680-07 | Warnings, explain trace, telemetry, health | No entity name present |
| T100680-08 | Erased/snapshot-less item | `entities: []`; no failure |
| T100680-09 | Workspace suite, coverage, clippy, fmt, size | Green; per-file ≥90%; files ≤450 lines |

### Negative Testing
Verify an unverified entity is never exposed, no entity leaks into a disallowed surface, and empty coverage is `[]` consistently.

### Verification Rule
Implementation claims must be supported by actual test output, inspection results, or other concrete evidence.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-100680-01 | `entities[]` sourced only from the verified snapshot `entity` | T100680-01, T100680-05 | Test output; source inspection |
| AC-100680-02 | Empty coverage documented and returns `[]` | T100680-02…T100680-04 | Test output; docs |
| AC-100680-03 | Identical `entities` across bindings | T100680-06 | Parity test output |
| AC-100680-04 | No entity in warnings/trace/telemetry/health | T100680-07 | Boundary test output |
| AC-100680-05 | Frozen contract and ranking unchanged | Regression tests | Test output |
| AC-100680-06 | No regression; size/coverage gates pass | T100680-09 | Workspace suite; coverage report; size check |

#### Evidence (actual, 2026-09-26)

| AC ID | Result | Evidence |
|-------|--------|----------|
| AC-100680-01 | PASS | `entities[]` is projected from one place only: `finalize` calls the crate-internal `entities::snapshot_entities(item)` on the already-decrypted `MemoryItem` (`crates/clio-retrieve/src/entities.rs`, wired at `finalize.rs:127`). The helper reads `snapshot.entity` and nothing else — no gist, no triple, no inference. Scope note (remediation round 1): the write-time span check runs on the default `store`/`batch` admission path; a bundle import stages a restored item as supplied and an operator correction (`correct`/`update`) stores the caller's snapshot whole, so an `entity` written through those paths is republished without having been span-verified (disclosed in §12 Known Limitations and in `docs/recall-entities.md`). Tests: `default_field_write_exposes_the_verified_snapshot_entity`, `verified_snapshot_entity_reaches_the_finalized_hit`, `mcp_payload_exposes_the_verified_snapshot_entity` (T100680-01), `entity_is_trimmed_and_nothing_else_is_rewritten` and `surrounding_whitespace_is_trimmed_on_the_finalized_hit` (T100680-05: the value is trimmed, and inner spacing, case, and punctuation survive). Real binary: MCP stdio `store` of a span-verified snapshot, then MCP `retrieve`, returned `"entities":["Ada Lovelace"]` (`developer-e2e-entities.out.txt`). Canonicalization is trim-only, using the same `str::trim` the write-side `match_entity` applied; documented in the `entities.rs` module header and in `docs/recall-entities.md`. One consequence is stated rather than hidden: the write-side matcher compared the NFC form of the stored string, so a name stored in a decomposed Unicode form is exposed as stored (trimmed, not re-normalized) because re-normalizing would need a new dependency in this crate. `a_decomposed_entity_is_exposed_as_stored_not_re_normalized` pins that choice so a later change to it is deliberate. |
| AC-100680-02 | PASS | The empty-coverage table is in the `entities.rs` module docs, the `ScoredHit.entities` field docs, and `docs/recall-entities.md`; it is also executable, not only prose: `every_documented_empty_coverage_shape_stays_empty` walks the triple carrier, hub-distill, belief, snapshot-less, non-default-field, and non-object-snapshot shapes and asserts `[]` for each. Per-shape tests: `triple_carrier_is_empty` (T100680-03), `hub_distilled_item_is_empty`, `belief_item_is_empty`, `snapshot_less_item_is_empty`, `non_default_field_list_is_empty` (T100680-04), `empty_and_whitespace_only_entities_are_empty`, `non_string_entity_values_are_empty`, `non_object_snapshots_are_empty` (T100680-02). The same shapes survive the whole pipeline as `[]` in `empty_coverage_shapes_survive_the_pipeline_as_empty_arrays` and `documented_empty_coverage_shapes_serialize_as_empty_arrays`. `the_gist_never_contributes_an_entity` pins that the prose half is never mined. |
| AC-100680-03 | PASS | `entities` is always serialized (no `skip_serializing_if`), so all three bindings emit the same key by serde: `every_recall_hit_carries_the_entities_key` and `every_hit_serializes_the_entities_key_even_when_empty` pin the key's presence, empty included. Parity: `mcp_and_in_process_surfaces_expose_identical_entities` (MCP payload vs `retrieve_from_json`, same store and args) and `recall_json_entities_match_the_mcp_retrieve_payload` (CLI `recall --output json` vs MCP `retrieve`, per hit id). Real binary: the MCP stdio payload and the CLI `recall --output json` payload for the same store both carry `"entities":["Ada Lovelace"]`, and the snapshot-less item carries `"entities":[]` on both. |
| AC-100680-04 | PASS | `entity_names_never_reach_warnings_or_the_explanation_trace` calls `retrieve` with `explain=true`, removes the `entities` key from every hit, and then asserts the distinctive probe name appears nowhere in the rest of the payload — one sweep covering `warnings`, `explanation` (including `explanation.hits[]`), `metrics`, `dedup`, the counts, and the frozen hit fields. `entity_names_never_reach_the_health_surfaces` asserts the same for the `diagnose` and `verify` reports. `verify_telemetry_carries_no_read_side_entity_projection` drives the real `gated_store_verified` write path for both the `verify_ok` and `verify_fail` branches and makes two assertions per branch: no read-side `entities` key anywhere in the rendered `VerifyEvent`, and the probe name nowhere in the event except inside the pre-existing masked snapshot preview (`preview.snapshot`), which the write path has always carried and which this boundary does not own — so a name leaking through `failure_fields`, the gist, the diagnostic, or any future field would fail. The phase §7 telemetry rule is scoped to the read-side `entities[]` projection (remediation round 1); the pre-existing preview behavior is disclosed under "Known limitations" and was deliberately not changed. `the_recall_text_view_never_prints_entity_names` pins the deliberate text-view omission. Real binary: `clio ops diagnose` and `clio ops verify` on the store holding the entity printed no name (exit 1 from `ops verify` is a pre-existing `DENSE_COVERAGE_GAP`/`LEXICAL_COVERAGE_GAP` finding: no embedder configured and the triple carrier has no lexical doc). The pre-existing write-path snapshot preview is disclosed under "Known limitations" and was deliberately not changed. |
| AC-100680-05 | PASS | The frozen contract is untouched: `the_frozen_retrieve_hit_contract_is_unchanged` asserts `item_id`, `bank_id`, `kind`, `category`, `epistemic_kind`, `requires_confidence_check`, and the fact-side absence of `source_type`/`confidence` are unchanged, with `entities` added beside them on `ScoredHit` only. Ranking is untouched: `entities_do_not_affect_hit_order_or_scores` runs the same query and frozen clock over two stores that differ only in whether the snapshots carry an `entity`, and gets bit-identical fused scores (`{:.17}`) and identical hit order. `entity_names_never_enter_the_compose_pack` proves the pack text is still gist-only, so the PR-1 budget contract is unchanged. The full workspace suite is green (see AC-100680-06), and the MCP transport conformance volatile mask needed no change: the new field is deterministic, so stdio and direct payloads still match. |
| AC-100680-06 | PASS | `cargo fmt --all --check` clean; `cargo clippy --workspace --all-targets --all-features --locked -- -D warnings` clean; `cargo test --workspace --locked` → 2500 passed / 0 failed (Postgres reachable on `127.0.0.1:34310`, so the pg suites really ran; count updated in remediation round 1 for the one added dense-leg test); `make coverage` exit 0 → `coverage-guard: 351 file(s) checked against 90.0% floors`, `TOTAL lines 97.89% functions 98.71%`, `all reported files meet the per-file floor` (raw 48506/49554 = 97.8851% lines, 4276/4332 = 98.7073% functions; zero files below 90% on either metric; the gate was re-run in remediation rounds 1 and 2 with the same result). Per-file rows for the files this phase touched: `entities.rs` 100.00/100.00, `types.rs` 100.00/100.00, `finalize.rs` 97.89/100.00, `read_retrieve.rs` 98.88/100.00, `telemetry.rs` 100.00/100.00 (`clio-retrieve/src/lib.rs` has no report row: module declarations and re-exports only). Report count went 350 → 351 files, exactly the one new production file. Size check: every created or modified Rust file is at or below 450 lines — largest are `cli_read_tests.rs` 411, `read_retrieve.rs` 280, `read_entities_tests.rs` 278, `cli_read_entities_tests.rs` 210, `types.rs` 212, `hit_entities_tests.rs` 299, `entities_tests.rs` 191, `finalize.rs` 168, `telemetry_entity_tests.rs` 148, `lib.rs` 133, `telemetry.rs` 106, `entities.rs` 109. (Sizes updated in remediation round 1 for the files edited there, and `entities.rs` 107 → 109 in finalize r1 close-out after the round-2 doc-comment edit.) |

### Definition of Done
- [x] All in-scope behavior is implemented.
- [x] All acceptance criteria pass.
- [x] Required tests pass.
- [x] No unauthorized changes were introduced.
- [x] Existing behavior remains intact.
- [x] Security checks pass.
- [x] Documentation is updated where required.
- [x] Evidence is collected.
- [x] Verification is completed.
- [x] Required approval is obtained (downstream pipeline step: adversary, remediator, remedy approver, finalize). Not self-certified by the implementer; ticked by Finalize r1 close-out on the recorded pipeline verdicts: Adversary r1 filed six findings, Remediator rounds 1 and 2 fixed them, and Remedy Approver r2 returned `REMEDY_APPROVED fa1e37f8` after re-running the gates and re-measuring every finding itself. Approver round 1 rejected (`REMEDY_REJECTED`, finding F-01) and sent the work back to the remediator. No human approval was needed: no approval-gated item (disclaimer wording, JSON shape, `recall_reason` semantics, the frozen `RetrieveHit` contract) was changed.

### Completion Evidence
- **Implementation summary:** `ScoredHit` carries a new `entities: Vec<String>`, populated in `finalize` from the fetched item's snapshot `entity` value with trim-only canonicalization (span-verified on the default `store`/`batch` write paths; bundle-imported and operator-corrected items carry the snapshot as supplied — see Known limitations). The projection lives alone in the new `crates/clio-retrieve/src/entities.rs` (`snapshot_entities`, plus the `SNAPSHOT_ENTITY_FIELD` constant); `finalize` calls it and nothing else changed in the hit contract. The array holds at most one name, is empty for every documented hit kind that carries no `entity`, and is always serialized so a consumer sees `[]` rather than a missing key. MCP, the in-process JSON surface, and the CLI all serialize the same value by serde, so the field reaches all three bindings with no per-binding projection code. The `entities[]` projection is deliberately absent from warnings, the explanation trace, verify telemetry events, the health surfaces, and the `compose_context` pack; the pre-existing write-path snapshot preview carries the snapshot's own `entity` value and is disclosed under Known limitations. The `clio recall` text view was left unchanged: the phase scopes `entities[]` to JSON reads, and the renderer's reserved entity-reason slot belongs to the later entity-match phase.
- **Discovered/affected architectural components:** `clio-retrieve` (`entities` new, `types`, `finalize`, `lib`), the MCP read binding (`read_retrieve.rs` doc + test registration only — no handler change was needed because the payload is serialized wholesale), `clio-write` (`telemetry.rs` doc + test registration only), `clio-lib` (`cli_read_tests.rs` test registration only), and `docs/`. `RetrieveHit` (the frozen fact/belief contract), fusion, ordering, budgets, the item snapshot schema, and the write-side verifier are all unchanged.
- **Changed-component summary:** production — new `crates/clio-retrieve/src/entities.rs` (109 lines; crate-internal since remediation round 1); modified `clio-retrieve/src/types.rs` (212, the field + doc), `finalize.rs` (168, one call + docs), `lib.rs` (133, module + test registration; the re-export was dropped in remediation round 1 because no downstream crate consumed it), `clio-mcp/src/read_retrieve.rs` (280, doc + test registration), `clio-write/src/telemetry.rs` (106, doc + test registration). Tests — new `clio-retrieve/src/entities_tests.rs` (191), `clio-retrieve/src/hit_entities_tests.rs` (299, includes the dense-leg test added in remediation round 1), `clio-mcp/src/read_entities_tests.rs` (278), `clio-write/src/telemetry_entity_tests.rs` (148, strengthened in remediation round 1), `clio-lib/src/cli_read_entities_tests.rs` (210), plus 6 registration lines in `cli_read_tests.rs` (411). Docs — new `docs/recall-entities.md`; `docs/recall-scores.md` and `docs/recall-scope-and-dedup.md` updated so their "always-present per-hit field" sentences name both `scores` and `entities`.
- **Test execution output:** 30 new tests (29 from the developer round plus one dense-leg test added in remediation round 1). `cargo test -p clio-retrieve --locked` → 192 passed / 0 failed (crate total; 21 of them new here). `cargo test -p clio-mcp --locked read_entities` → 5 passed. `cargo test -p clio-write --locked telemetry` → 4 passed. `cargo test -p clio --locked entities` → 3 passed. `cargo test --workspace --locked` → 2500 passed / 0 failed. (Remediation round 1 corrected the earlier count line, which said 26 new tests and 17 in `clio-retrieve`; the filter runs and a `#[test]` count over the five new test files gave 29, and the dense-leg test makes 30.) Per-test-class map: unit (T100680-01…05) in `entities_tests.rs`; integration and frozen-contract (T100680-01, 04, 05, 08) in `hit_entities_tests.rs`; contract/parity and security (T100680-02…04, 06, 07) in `read_entities_tests.rs` and `cli_read_entities_tests.rs`; telemetry security (T100680-07) in `telemetry_entity_tests.rs`; end-to-end (T100680-01, 06, 07) in the real-binary run.
- **Real-binary end-to-end evidence:** `make compile`, then `developer-e2e-entities.py` drives the built `clio` binary over the real MCP stdio transport and the real CLI: MCP `store` with a span-verified snapshot entity, `clio ops reindex --target lexical --confirm`, then MCP `retrieve(explain=true)` / `diagnose` / `verify`, then `clio recall --output json`, `clio recall --output text`, `clio ops diagnose`, `clio ops verify`. Output saved as `developer-e2e-entities.out.txt`; the script exits 0 and prints `ALL REAL-BINARY CHECKS PASSED`. Observed: MCP payload `"entities":["Ada Lovelace"]`; `explanation.hits[]` carries no `entities` key and no name; CLI `recall --output json` `"entities":["Ada Lovelace"]`; CLI text view has no name; `ops diagnose`/`ops verify` have no name.
- **API/schema evidence for the field:** per hit `"entities": ["<verified value>"]`, or `"entities": []`. Key presence on every hit is pinned by `every_recall_hit_carries_the_entities_key` and `every_hit_serializes_the_entities_key_even_when_empty`; the value source by `mcp_payload_exposes_the_verified_snapshot_entity`; the empty set by the shape tests listed under AC-100680-02. The published MCP `inputSchema` is unchanged (this is an output field, and the tools publish no `outputSchema`).
- **Verification report:** pre-change baseline (workspace JSON left by the interrupted attempt at `/tmp/cov-baseline.json`, guard-printed) 350 files, TOTAL lines 97.88% / functions 98.71%, no file below the floor. The developer's final gate: `make coverage` → exit 0, 351 files, `TOTAL lines 97.89% functions 98.71%`, `all reported files meet the per-file floor` (raw 48506/49554 = 97.8851% lines, 4276/4332 = 98.7073% functions). Remediation round 1 re-ran the full gate after its comment-only and test-only edits: exit 0, same totals and guard verdict. Remediation round 2 re-ran it again after its phase-text and doc-wording edits (the only Rust-side edit there is doc comments in `entities.rs`): exit 0, same totals, and the per-file rows read from the fresh `target/coverage/coverage.json` are unchanged. Per-file rows for every touched file are listed under AC-100680-06. The full gate therefore ran four times in this phase: baseline, developer final, remediation round 1, remediation round 2; the in-between checks were scoped (`cargo llvm-cov --package clio-retrieve --locked --no-clean --summary-only`; a scoped report counts more lines for `entities.rs` than the workspace report because the test module is declared inside that file; both measurements are 100%). An earlier revision of this paragraph said the gate ran exactly twice and was not re-run after the round-1 edits; that was accurate only up to remediation round 1 and is corrected here.
- **Verification limits:** three gaps. (1) The failure-mode row T100680-08 has two halves; only the snapshot-less half is a test (`snapshot_less_item_is_empty`, plus the pipeline variant). The erased half is not directly tested here: a content-erased item cannot be returned as a hit at all, because its payload no longer decrypts, so no read reaches hit assembly. That claim rests on source inspection of the read path plus the existing erasure suites, not on a new test written for this phase. (2) The MCP boundary sweep proves no entity name appears in the `retrieve` payload outside `hits[].entities`; it does not cover surfaces outside the `retrieve` response other than the health reports and verify telemetry that have tests (`diagnose`, `verify`, `VerifyEvent`). A wider sweep over every ops/telemetry surface was not attempted. (3) The real-binary run used no embedding sidecar, so the dense arm was off and the retrieved hit came from the lexical leg only. The dense-populated variant is now exercised in-process: `dense_populated_hit_carries_the_same_entities` attaches a fixed fake embedder, gets the hit ranked on the dense leg (`dense_rank` set, `scores.semantic` present), and asserts the same snapshot entity (added in remediation round 1). Before that, no new test ran a dense-populated retrieve, and the earlier wording here claimed otherwise; the real-binary run itself remains lexical-only.
- **Known limitations:** see §12.

---

## 10. Failure Handling and Recovery

### Expected Failure Modes

| Failure | Detection | Recovery |
|---------|-----------|----------|
| Unverified entity exposed | Unit test with bad snapshot | Stop; expose only verified values |
| Entity leaks into a diagnostic surface | Boundary test | Remove it; treat as a security failure |
| Binding divergence | Parity test | Fix the projection; do not ship partial |
| Snapshot unavailable at hit build | Integration test | Stop; report |
| File approaches 450 lines | Size check | Decompose |

### Rollback Strategy
Remove the `entities` field and projections; no storage changed, so rollback is behavior-preserving. Entity names remain only where they already were (the item snapshot).

### Partial Completion Policy
If only some bindings expose entities, or a boundary surface still contains them, do not claim completion.

---

## 11. Traceability

| Parent Requirement | Implementation Task | Verification | Acceptance Criterion |
|--------------------|---------------------|--------------|-----------------------|
| FR-4 / §4.4 (span-verified entities) | Task 1 | T100680-01, T100680-05 | AC-100680-01 |
| PR-4 / §4.4 (non-authoritative link) | Task 1, Task 2 | T100680-03, T100680-04 | AC-100680-02 |
| FR-20 / §4.9.2 item 2 (binding identity) | Task 2 | T100680-06 | AC-100680-03 |
| §4.9.5.C (health PII) / §4.12 + §7.4 (content boundary) | Task 2 | T100680-07 | AC-100680-04 |
| Regression / quality contract | All | T100680-09 | AC-100680-06 |

Required chain:

```text
Requirement → Capability → Implementation → Test → Evidence
```

---

## 12. Phase Exit Contract

### Outputs Produced
- A per-hit `entities[]` array sourced from the verified snapshot `entity`.
- Documented coverage limits and a PII-boundary test.

### Guarantees Provided to Downstream Phases
After this phase is accepted:
- Phase 100700 can match query text against the hit's entity names.
- Phase 100780 can add an entity-inclusion toggle if desired.
- No durable entity store exists that could complicate erasure.

### Known Limitations
Each entry states what is missing, why, and which phase owns the debt.
- `entities[]` is empty for triple carriers, hub-distill, beliefs, snapshot-less items, and non-default field lists. **Why:** those write paths store no `entity` field, so there is no verified value to expose. **Debt owner:** none; this is the documented coverage limit, not missing work.
- No entity linking, canonical resolution, or deduplication beyond trim. **Why:** a retrieval-side link would be inferred rather than span-verified, so it could not be authoritative (PR-4). **Debt owner:** none; entity matching is the next phase's job.
- Triple-linked enrichment is deferred. **Why:** there is no by-item triple query and no `item_id` index on the `triples` table, so the lookup does not exist and adding it is out of scope here. **Debt owner:** none assigned.
- `entities` is on `ScoredHit`, not the frozen `RetrieveHit`. **Why:** the placement decision keeps the fact/belief contract unchanged; adding a field to a frozen contract needs its own approval. **Debt owner:** none; if a later decision moves it, this phase must be re-sequenced after the `RetrieveHit` context track (gap analysis §10.1).
- The `clio recall` text view does not print entity names. **Why:** the phase scopes the field to the three JSON read projections, and the renderer already holds a reserved entity-reason slot for the separate entity-match phase. **Debt owner:** the entity-match phase, if it wants a text line.
- **Pre-existing, not introduced here:** the write path's verify telemetry carries a secret-masked preview of the candidate snapshot, and that preview includes the snapshot's own `entity` value (`clio-write/src/telemetry.rs` `redact_preview`; asserted by the pre-existing test `redact_masks_api_key_in_gist_and_json`). **Why it is still there:** that preview is a write-path diagnostic owned by the verify telemetry module, whose documented job is secret masking; the phase rule binds the new read-side `entities[]` projection, which provably never reaches that surface. Changing the preview would alter an earlier phase's contract and break its passing test, which is out of scope here. **Debt owner:** unassigned; the requirement owner should decide whether a masked snapshot preview may carry an entity name. **No new test asserts the preview is entity-free, and this phase does not claim it is.** (Remediation round 1: the boundary test now also asserts the probe name appears nowhere in a recorded `VerifyEvent` outside that preview, and the §7 telemetry rule is scoped to the read-side `entities[]` projection.)
- **Pre-existing, not introduced here:** the write-time span check (FR-4) runs on the default `store`/`batch` admission path only, so `entities[]` can republish a name that was never span-verified. A bundle import stages the restored item as supplied (`clio-compliance` import apply), and operator corrections (`correct`/`update`) store the caller's snapshot whole (`clio-store` `correct_item`/`update_memory_item`); `verify_snapshot` has exactly three call sites, all in the gated store path. **Why it is still there:** wiring the check into import and correct is a write-path behavior change outside this phase's scope, and this adds no new exposure class — a caller authorized to read the item can read its whole snapshot through `get_snapshot` either way. **Debt owner:** unassigned; needs either upstream verification on the import/correct paths or an explicit provenance marker the read side can distinguish. The claims in `entities.rs`, the `ScoredHit.entities` field doc, and `docs/recall-entities.md` are qualified accordingly.

### Downstream Prerequisites
- Phase 100700 may rely on `entities[]` being present (possibly empty) on every hit.

### Final Status
PASS WITH DOCUMENTED LIMITATIONS — all six acceptance criteria pass on real test and real-binary output; the qualifier covers the three verification limits in §9, the unassigned telemetry-preview decision in Known Limitations, and the import/correct span-check gap added in remediation round 1.

### Verification Sign-Off
- Implementer: Developer r2 and Remediator rounds 1–2 — OpenCode CLI (Go . Space Bunny Free Max) and OpenCode CLI (Together . GLM-5.3 Flash High), 2026-09-26
- Verifier: Adversary r1 and Remedy Approver r2 — OpenCode CLI (Go . Space Bunny Free Max): all six findings re-measured against the code and re-run gates by the approver (`REMEDY_APPROVED fa1e37f8`)
- Human Approver: not required — no approval-gated item (disclaimer wording, JSON shape, `recall_reason` semantics, the frozen `RetrieveHit` contract) was changed
- Date: 2026-09-26

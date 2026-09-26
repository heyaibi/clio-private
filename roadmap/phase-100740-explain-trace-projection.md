# Phase 100740: Read-Surface De-Drift — Derive the `explain` Trace from the Hit

### Attribution
Rounds below record plan authorship; implementation sign-off is in §12.
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | [TBD] | proposed |
| Developer | r1 | OpenCode CLI (Go . Deepseek V4.1 Flash Max) | done |
| Adversary | r1 | [TBD] | [TBD] |
| Adversary | r1 | OpenCode CLI (Go . Space Bunny Free Max) | done |
| Remediator | r1 | [TBD] | [TBD] |
| Remediator | r1 | OpenCode CLI (Together . GLM-5.3 Flash High) | done |
| Remediator | r2 | OpenCode CLI (Together . GLM-5.3 Flash High) | done |
| Remedy Approver | r1 | [TBD] | [TBD] |
| Remedy Approver | r2 | OpenCode CLI (Go . Space Bunny Free Max) | approved |
| Finalize | r1 | [TBD] | [TBD] |
| Finalize | r1 | OpenCode CLI (Together . GLM-5.3 Flash High) | done |

**Capability phase 100740** · **Effort:** ~1–1.5 days · **Status:** Plan ready · **Parent:** gap analysis `gaps/recall-result-fidelity-gap-analysis.md` §3.4, §9.2, §7, §10.2; requirement §4.9.4.G, §4.12 (transparency), §4.9.5.C (health PII), FR-20 / §4.9.2 item 2

### Vocabulary (read first) — zero shared moniker

| Term | Meaning in this phase | Must not be confused with |
|------|------------------------|----------------------------|
| **explain trace** | The `explain` diagnostic payload that carries the score/domain/hop trace | The full read payload; a content surface |
| **shared projection** | One function/mask that turns a `ScoredHit` into the explain hit shape | Serializing the whole hit unconditionally |
| **volatile mask** | A defined set of fields the conformance test treats as varying | An authorization filter |

This phase changes where the trace's shape is defined, not what it contains.

---

## 1. Objective

### Goal
Make the `explain` hit projection derive from one shared source instead of the hand-written field list, so a new `ScoredHit` field cannot silently fail to appear in (or accidentally leak into) the trace. The trace stays PII-safe: entity names and any other content-derived field are excluded by an explicit mask, and a guard test fails if the shared projection and the trace disagree.

### Expected Outcome
- The `explain` hit shape is derived from a single projection over the hit structure.
- The trace still contains only ids, ranks, scores, counts, and timings; content-derived fields such as `entities` are excluded by an explicit allowlist/mask.
- A guard test detects drift between the shared projection and the trace shape.
- The trace's existing fields and values are unchanged for existing inputs.
- Adding a future non-content field requires a deliberate decision rather than accidental omission.

### Parent Requirement
`requirement.md` — §4.9.4.G (`explain` returns the score/domain/hop trace); §4.12 and §7.4 (transparency and content boundary) with §4.9.5.C (health-surface PII; diagnostic surfaces stay content-free); FR-20 / §4.9.2 item 2 (binding identity). Gap source: `gaps/recall-result-fidelity-gap-analysis.md` §9.2.

### Design References (source-verified at plan time)
- `retrieve_explanation` rebuilds a hit list field by field (`crates/clio-mcp/src/read_retrieve.rs:118-150`); the per-hit JSON is `:119-132` with keys `item_id`, `score`, `dense_rank`, `lexical_rank`, `consolidated`, `source_ids`.
- The module documents the trace as "PII-safe retrieval trace: ids, ranks, scores, counts, timings only" (`read_retrieve.rs:113`).
- The MCP conformance volatile mask already treats `score`/`metrics` as volatile (`crates/clio-mcp/tests/mcp_read_transport_conformance.rs:150-167`; a second, id-only 7-key mask sits in `crates/clio-mcp/tests/conformance.rs:326-350`). An earlier revision of this file wrongly cited `mcp_read_conformance.rs:196-228` for this fact; that file has no volatile mask (177 lines, no `mask_volatile`). Corrected in remediation r1; the range was updated again in remediation r2 after the r1 transport-test addition shifted `fn mask_volatile` from 146 to 150.
- The finalized hit is built at `crates/clio-retrieve/src/finalize.rs:100-112`; the bindings project it separately.
- Adding `entities[]` (Phase 100680) is exactly the kind of field that must not enter the trace, which is why the shared projection must be an explicit mask, not whole-struct serialization.
- `read_retrieve.rs` is 271 lines (274 after implementation; 277 after the remediation-r1 header fix).

---

## 2. Scope Boundaries

### In Scope
- One shared projection/mask that defines the `explain` hit shape from the hit structure.
- An explicit exclusion of content-derived fields (entities and any future equivalents).
- A guard test that detects drift.
- Updating call sites and the conformance/volatile handling.

### Explicitly Out of Scope
- Changing what the trace contains semantically, or its values.
- Adding `scores` to the trace (allowed later because scores are PII-safe, but not required here; if added, it must go through the shared projection).
- Entity extraction or the entity reason (Phases 100680/100700).
- Changing the read payload shape or the frozen contract.
- Cross-binding trace parity beyond the existing MCP trace.

### Must Not Change
- The trace remains content-free: no entity names, gist text, snapshot values, or query text in `explanation`.
- Existing trace fields and values for existing inputs.
- The volatile-mask semantics that keep conformance stable.
- Bank isolation and authorization.
- The frozen `RetrieveHit` contract.

### Scope Expansion Rule
If work outside this scope appears necessary:
1. Stop.
2. Document the reason.
3. Request clarification or approval.
4. Do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- Phase 100620 accepted: the hit structure carries the new display fields, so the drift surface is real.
- The PII boundary for the trace is recorded (gap analysis §6, §8 decision 5).
- The MCP retrieve response and CLI JSON serialize `RetrieveOutcome` wholesale; this phase owns only the `explain` trace projection, not the payload fields.

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| Hit structure | Carries the new fields | Phase 100620 acceptance |
| Trace projection | Hand-written today | `read_retrieve.rs:118-150` inspection |
| Trace doc | "ids, ranks, scores, counts, timings only" | `read_retrieve.rs:113` inspection |
| Conformance mask | Volatile fields defined | `mcp_read_transport_conformance.rs:150-167` inspection (a second id-only mask sits in `conformance.rs:326-350`; the earlier `mcp_read_conformance.rs:196-228` citation was wrong, corrected in r1, and the range refreshed to 150-167 in r2) |

---

## 4. Existing-System Discovery

The agent MUST re-verify the following before editing; the facts below were confirmed at plan time.

### Required Discovery
- Confirm the exact fields the trace includes today and where each comes from.
- Confirm the trace excludes content today (there is no entity field yet; Phase 100680 introduces one).
- Confirm the conformance test structure and volatile mask.
- Confirm the size of `read_retrieve.rs` and any shared projection location.
- Confirm whether the in-process or CLI paths expose an explain trace that must also derive from the same source.

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
- The trace is a separate hand-written projection; nothing enforces agreement with the hit shape.
- The trace is documented as PII-safe, so the shared projection must exclude `entities`.
- The volatile mask already anticipates score volatility.

### Repository Adaptation Rule
The agent must determine the concrete projection placement from the actual repository. The plan requires one source of truth and an explicit content mask; it does not prescribe the mechanism (shared function, serde skip list, or a dedicated view struct).

---

## 5. Implementation Specification

### Task 1: One Shared Explain Projection

#### Intent
Define the trace hit shape once, derived from the hit, with content excluded.

#### Required Capability or Behavior
- The explain hit shape comes from a single shared projection over the hit structure.
- The projection uses an explicit allowlist/mask; content-derived fields are excluded.
- The trace's existing keys and values are unchanged.
- Adding a new hit field either appears in the trace (if PII-safe and listed) or is excluded (if content-derived), by deliberate choice in one place.

#### Architectural Responsibility
`clio-mcp` owns the trace projection; if a shared view lives in `clio-retrieve`, that is acceptable, provided all trace consumers derive from it.

#### Required Changes
1. Introduce the single projection and route `retrieve_explanation` through it.
2. Explicitly exclude content-derived fields (entities and equivalents).
3. Keep the trace values identical for existing inputs.

#### Implementation Constraints
- Do not serialize the whole hit unconditionally.
- Do not add content to the trace.
- Keep `read_retrieve.rs` ≤450 lines.

#### Expected Result
The trace is produced from one definition; a content field cannot leak in by default.

### Task 2: Guard Against Drift

#### Intent
Fail a test if the shared projection and the trace shape diverge.

#### Required Capability or Behavior
- A guard test asserts the trace keys equal the projection's declared set.
- The test fails if a new non-content field is added to the hit and not deliberately classified.
- Existing conformance behavior is preserved.

#### Architectural Responsibility
`clio-mcp` owns the guard test at the trace owner's boundary.

#### Required Changes
1. Add the guard test.
2. Update the volatile mask or conformance expectations only as required by the projection refactor.
3. Document how a future field is classified.

#### Implementation Constraints
- Do not weaken the conformance test.
- Do not use process-global state.

#### Expected Result
A future field addition cannot drift silently; it forces a one-line classification.

### Implementation Freedom
The agent may choose the projection mechanism (shared function, view struct, serde attributes) and the guard-test form, provided the trace stays content-free, values are unchanged, and drift is detected.

---

## 6. Agent Execution Rules

### Allowed Actions
- Refactor the trace projection and update its tests.
- Update the conformance volatile mask as required by the refactor.

### Forbidden Actions
- Add content (entities, gist, snapshot, query) to the trace.
- Change trace values or the read payload.
- Weaken the conformance test.
- Delete tests or claim completion without evidence.

### Agent Decision Boundary
The agent may decide the projection mechanism and test placement. The agent must request approval for: adding a PII-safe field to the trace, changing trace semantics, or serializing the whole hit.

### Mandatory Stop Conditions
Stop and report if: the projection cannot exclude content without special-casing; existing trace values would change; or correctness cannot be verified.

---

## 7. Security Constraints

### Required Controls
- The trace remains content-free and PII-safe.
- No entity names, gist, snapshot, or query text may enter `explanation`.
- Authorization and bank isolation unchanged.

### Sensitive Data Rules
- Never log content or entity names in the trace.
- Never commit secrets.

### Security Acceptance Conditions
- A boundary test with an entity-bearing hit proves `explanation` contains no entity name.
- Existing redaction tests remain green.

---

## 8. Test and Verification Strategy

### Required Tests
- [x] Unit tests (projection output matches the declared key set) — `projection_reproduces_the_frozen_hit_contract` + the classification sweep in `read_explain_guard_tests`
- [x] Integration tests (trace through the MCP read path) — `read_explain_tests` dispatch through the MCP `retrieve` tool binding
- [x] Contract tests (existing trace values unchanged; content excluded) — `existing_hit_trace_keys_and_values_are_pinned`, `entity_bearing_hit_leaks_nothing_into_the_trace`
- [x] End-to-end tests (real MCP `retrieve` with `explain`) — `explain_trace_key_contract_over_stdio_and_http` in `crates/clio-mcp/tests/mcp_read_transport_conformance.rs` (added in remediation r1): JSON-RPC frames through `McpHandler` on stdio and Streamable HTTP both assert the per-hit key set equals the shipped allowlist and no entity name reaches the trace
- [x] Regression tests (conformance suite green) — `mcp_read_conformance`, `mcp_read_transport_conformance`, `conformance` all green in the workspace gate
- [x] Security tests (no entity/content in the trace) — entity boundary sweep + content-exclusion assertions
- [x] Failure-mode tests (hit without optional fields) — `absent_optional_hit_fields_keep_the_trace_shape`

(Ticked in remediation r1; before that round all seven boxes were unticked while §9/DoD claimed the tests pass.)

### Required Test Scenarios

| Test ID | Scenario | Expected Result |
|---------|----------|-----------------|
| T100740-01 | Existing hit | Trace keys/values identical to before |
| T100740-02 | Entity-bearing hit | No entity name in `explanation` |
| T100740-03 | New non-content field added (simulated) | Guard test fails until classified |
| T100740-04 | Hit with missing optional fields | Trace stable |
| T100740-05 | MCP conformance suite | Green |
| T100740-06 | Workspace suite, coverage, clippy, fmt, size | Green; per-file ≥90%; files ≤450 lines |

### Negative Testing
Verify content cannot enter the trace by default, trace values do not change, and the guard fails on unclassified fields.

### Verification Rule
Implementation claims must be supported by actual test output, inspection results, or other concrete evidence.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-100740-01 | Trace derives from one shared projection | T100740-01 | Source inspection; test output |
| AC-100740-02 | Trace stays content-free (no entities) | T100740-02 | Boundary test |
| AC-100740-03 | Drift is detected by a guard test | T100740-03 | Guard test output |
| AC-100740-04 | Existing trace values unchanged | T100740-01 | Before/after test output |
| AC-100740-05 | No regression; size/coverage gates pass | T100740-06 | Workspace suite; coverage report; size check |

#### Evidence (actual, 2026-09-26)

| AC ID | Result | Evidence |
|-------|--------|----------|
| AC-100740-01 | PASS | One shared projection: `crates/clio-mcp/src/read_explain.rs` defines the `ExplainHit` view, the `explain_hit` mapping, and the declared allowlist/exclusion tables; `read_retrieve.rs` routes `retrieve_explanation` through `explain_hit` (the hand-written per-hit `json!` site is gone). Wire test `existing_hit_trace_keys_and_values_are_pinned` asserts that each trace hit key set equals `TRACE_HIT_KEYS` through the in-process MCP `retrieve` dispatch; `projection_reproduces_the_frozen_hit_contract` pins the projected values for a fully populated and a value-less hit. Remediation r1 added the real-binding end-to-end contract: `explain_trace_key_contract_over_stdio_and_http` asserts the same per-hit key set and entity exclusion over stdio JSON-RPC frames and Streamable HTTP. |
| AC-100740-02 | PASS | The projection classifies `gist`, `context`, `entities` as content-derived exclusions. `entity_bearing_hit_leaks_nothing_into_the_trace` dispatches a real entity-bearing `retrieve` and asserts the rendered trace contains no entity name and the trace hit carries no `entities`/`gist`/`context`/`entity_match` key. Mutation check: temporarily adding `entities` to the projection failed 5 tests, including the boundary sweep and the key-classification test. The pre-existing `read_entities_tests` sweeps stay green. |
| AC-100740-03 | PASS | `every_hit_field_is_classified_and_matches_the_projection` sweeps every field NAME of `ScoredHit` and the flattened `RetrieveHit` and fails on any unclassified field; `classification_tables_match_the_frozen_trace_contract` pins the trace/exclusion tables to the frozen contract. Since remediation r2 the sweep's two artifacts — the `..`-free destructuring and the name list — are generated from one shared `macro_rules!` declaration (`with_hit_fields` → `make_hit_field_names` in `read_explain_guard_tests.rs`), so a field cannot be named in one and dropped from the other. Forcing function, re-verified in remediation r2: adding a `#[serde(skip)] drift_probe` field to `ScoredHit`, initialized in `finalize.rs`, named `drift_probe: _` in `explain_hit`, and set in the fixture fails the suite at compile time (the macro-generated pattern no longer mentions it); declaring the field in the shared list without a classification fails the sweep with `the swept field names and the serialized keys diverged`. Both mutations reverted. |
| AC-100740-04 | PASS | The same contract tests ran against the old hand-written projection (`cargo test -p clio-mcp --lib read_explain` → 3 passed / 0 failed) and after the refactor (→ 6 passed / 0 failed). The frozen top-level and per-hit key sets and the stable values (`item_id`, `dense_rank`, `lexical_rank`, `consolidated`, `source_ids`, `domains`, counts) are pinned; only `score` and `metrics` are volatile, and they are compared to the read payload instead of fixed numbers. |
| AC-100740-05 | PASS | Final gates after remediation r2: `make check` exit 0 (fmt, clippy `-D warnings`, workspace suite). `make coverage` exit 0: 353 reported files checked, TOTAL lines 97.89% / functions 98.71% (baseline 352 files, 97.89% / 98.71%), all files meet the ≥90% per-file floor. Touched files: `read_explain.rs` 100.00/100.00, `read_retrieve.rs` 98.83/100.00, `lib.rs` 100.00/100.00, `clio-retrieve/src/types.rs` 100.00/100.00. Workspace suite under the gate: 2527 passed / 0 failed (the gate's first run had one unrelated timing-sensitive `clio-write` concurrency test fail under parallel load, `concurrent_writes_during_refresh_wave`, which passed in isolation and in the gate re-run; no clio-write file was modified by this phase). `cargo clippy --workspace --all-targets --all-features --locked -- -D warnings` clean; `cargo fmt --all -- --check` clean. Sizes: `read_explain.rs` 149, `read_explain_tests.rs` 281, `read_explain_guard_tests.rs` 322, `read_retrieve.rs` 277 (all ≤450). |

#### Remediation evidence (r1, 2026-09-26)

Adversary findings F-01..F-05, all addressed:

- **F-01 (guard blind to serde-skipped fields): closed.** Reproduced before fixing: with the old serialized-key sweep, a `#[serde(skip)] drift_probe` field added to `ScoredHit`, named `drift_probe: _` in `explain_hit`, and set in the fixture left `cargo test -p clio-mcp --locked --lib read_explain` at `6 passed; 0 failed`. After the fix, the same mutation is caught twice: `error[E0027]: pattern does not mention field 'drift_probe'` in the new exhaustive `hit_field_names` destructuring, and — once the field is mentioned and named — `FAILED. 5 passed; 1 failed` with `hit field 'drift_probe' is unclassified: add it to TRACE_HIT_KEYS ...`. The sweep now walks the struct field names (`hit_field_names` in `read_explain_guard_tests.rs` binds every `ScoredHit` and flattened `RetrieveHit` field with no `..`) and asserts the swept names equal the serialized key surface of the full fixture.
- **F-01 `..` guard (plan_unlimited): covered by evidence.** Mutation: `explain_hit`'s pattern replaced with a `..` wildcard and `scores` classified `TraceVisible` (simulating a new field dropped from the projection) → `3 failed`, including `classification and projection disagree for 'scores'` and the wire assertion `trace hits come from the shared projection allowlist`. A `..` alone compiles and passes only because nothing trace-visible is dropped today; any dropped trace-visible field fails the per-field presence assertion and the allowlist equality. Mutation reverted.
- **F-02 (missing end-to-end trace test; §8 unticked): closed by adding the test.** `explain_trace_key_contract_over_stdio_and_http` in `crates/clio-mcp/tests/mcp_read_transport_conformance.rs` runs a real `retrieve` with `explain: true` over stdio (`McpHandler` JSON-RPC frames) and Streamable HTTP and asserts, per transport, that `explanation.hits[*]` keys equal the shipped `TRACE_HIT_KEYS`, that trace hits are non-empty, and that no entity name from the payload hits reaches the rendered trace: `test result: ok. 4 passed; 0 failed`. §8 checkboxes ticked with per-item evidence.
- **F-03 (stale comments): closed.** `read_entities_tests.rs` now names the real mechanism (`ExplainHit` allowlist projection plus the classification sweep); `read_retrieve.rs` module header now owns the top-level trace assembly and points per-hit shaping at `crate::read_explain`.
- **F-04 (stale phase-file citations): closed.** Both `mcp_read_conformance.rs:196-228` citations replaced with the `mcp_read_transport_conformance.rs` mask range (second mask noted at `conformance.rs:326-350`); the file-size note updated (271 → 274 → 277). Remediation r2 refreshed the range to `150-167` because the r1 transport-test addition shifted `fn mask_volatile` from 146 to 150 (verified by grep; the `VOLATILE` table ends at line 167).
- **F-05 (doc overstates compile-time enforcement; "wire order" claim): closed.** `read_explain.rs` now states the pattern forces field-mention while the guard sweep forces classification, and `TRACE_HIT_KEYS` is documented as order-free. The three tables are `pub` constants in the now-public `read_explain` module (shipped contract, read by the projection tests, the drift guard, and the transport e2e test) instead of `#[cfg(test)]` artifacts.
- **Declined plan_unlimited items, with reasons:** a `ScoredHit` constructor adds no safety — every existing construction site is a full struct literal, and mutation B already proved a new field breaks each one with `error[E0063]` (plus `error[E0027]` in `explain_hit`); a constructor would centralize defaults but could not break construction any harder than the language already does. A CI check that phase-file `file:line` citations still resolve is impossible without violating the public/private boundary: the phase files live in the private roadmap and CI must never reference private paths; the phase file's own §4 re-verify rule is the control.
- Remediation scoped coverage: `cargo llvm-cov --package clio-mcp --locked --no-clean --json` → `read_explain.rs` 100.00/100.00, `lib.rs` 100.00/100.00, `read_retrieve.rs` 97.66/100.00. Sizes after remediation: `read_explain.rs` 149, `read_explain_tests.rs` 281, `read_explain_guard_tests.rs` 331, `read_retrieve.rs` 277, `mcp_read_transport_conformance.rs` 341 (all ≤450).

#### Remediation evidence (r2, 2026-09-26)

Remedy approver round 1 verdict: REJECT with F-01 unresolved (crates/clio-mcp/src/read_explain_guard_tests.rs:147-195); two accuracy items also addressed.

- **F-01 (required, unresolved): closed by making one artifact serve both lists.** The exhaustive destructuring and the swept name list were two independent hand-written blocks; a `#[serde(skip)]` field could be mentioned in `explain_hit`, left out of the `vec![]`, and left unclassified with no failure (approver measured `6 passed; 0 failed`). Replaced `hit_field_names` with one shared `macro_rules!` declaration in `read_explain_guard_tests.rs`: `with_hit_fields!` declares every `ScoredHit` and flattened `RetrieveHit` field exactly once and re-expands it through `make_hit_field_names`, which generates BOTH the `..`-free destructuring (`field: _` bindings) and the `vec![stringify!(field), ...]` name list. Editing the struct now forces the field through the one list, and anything in the list must classify.
- **F-01 re-verified with the approver's exact mutation:** `#[serde(skip)] drift_probe: Option<String>` added to `ScoredHit` (`clio-retrieve/src/types.rs`), initialized in `finalize.rs`, named `drift_probe: _` in `explain_hit`, and set in the fixture → `cargo test -p clio-mcp --locked --lib read_explain` fails to compile at the macro-generated destructuring (`read_explain_guard_tests.rs:178`). Diagnostic note: for macro-expanded patterns rustc reports the missing field as `pattern requires \`..\` due to inaccessible fields` (the sibling of `error[E0027]`, which a hand-written control pattern in the same compilation did report, naming `drift_probe`); both are hard compile errors, so the forcing function holds either way.
- **F-01 control mutation:** declaring `drift_probe` in the shared list as well (the legitimate developer action) → `test result: FAILED. 5 passed; 1 failed` with `the swept field names and the serialized keys diverged` (a serde-skipped field is in the swept set but not the serialized set). Both mutations reverted from saved copies; `grep -rn drift_probe crates` → 0 hits; suite green again (`6 passed; 0 failed`).
- **Mask citation accuracy (approver follow-up):** the r1 citations `mcp_read_transport_conformance.rs:146-163` were exact for the staged snapshot but the r1 transport-test addition shifted `fn mask_volatile` to line 150; verified by grep (`fn mask_volatile` at 150, the `VOLATILE` table ends at 167) and the three mentions (Design References, Dependencies table, the r1 F-04 note) now read `150-167` with the shift explained.
- **AC-100740-03/05 accuracy:** AC-100740-03 evidence now describes the field-name sweep generated from the shared declaration instead of the pre-remediation serialized-key sweep; AC-100740-05 now carries the r2 gate numbers and current file sizes.
- **r2 gates:** `make check` exit 0. `make coverage` exit 0: 353 files, TOTAL lines 97.89% / functions 98.71%, all reported files meet the per-file floor; suite 2527 passed / 0 failed. One unrelated timing-sensitive `clio-write` test (`concurrent_writes_during_refresh_wave`) failed once in the gate's first run under parallel load and passed in isolation and in the gate re-run; no clio-write file was modified by this phase (recorded, not dismissed silently). `cargo fmt -p clio-mcp -- --check` clean; `cargo clippy -p clio-mcp --all-targets --all-features --locked -- -D warnings` clean. Size after r2: `read_explain_guard_tests.rs` 322 (≤450).

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
- [x] Required approval is obtained (downstream pipeline step).

### Completion Evidence
- Implementation summary: the `explain` trace's per-hit shape now comes from one shared projection in `crates/clio-mcp/src/read_explain.rs`. `ExplainHit` declares the trace-visible fields (item id, score, dense/lexical rank, consolidated flag, source ids); `explain_hit` maps a `ScoredHit` into it with an exhaustive destructuring pattern; `retrieve_explanation` routes every hit through it. The module carries an explicit classification: three test-facing tables (`TRACE_HIT_KEYS`, `CONTENT_EXCLUDED_HIT_KEYS`, `SAFE_EXCLUDED_HIT_KEYS`) name every serialized hit key as trace-visible, content-excluded (`gist`, `context`, `entities`), or PII-safe but deliberately excluded (`scores`, `snapshot_ref`, `entity_match`, and the other frozen hit-contract fields).
- Changed-component summary: production — new `crates/clio-mcp/src/read_explain.rs` (142 lines), registered in `lib.rs`; `read_retrieve.rs` `retrieve_explanation` now serializes `explain_hit(h)` per hit (the hand-written `json!` site is removed). Tests — new `read_explain_tests.rs` (281 lines: wire key/value contract, entity boundary, absent-optional shape) and `read_explain_guard_tests.rs` (258 lines: projection values, key-classification sweep, frozen tables). No change to `clio-retrieve`, `clio-types`, the transport volatile masks, or the conformance fixtures: the wire shape is unchanged, so no mask update was required.
- Test execution output: before (old projection) `cargo test -p clio-mcp --lib read_explain` → 3 passed / 0 failed; after → 6 passed / 0 failed; full crate `cargo test -p clio-mcp --locked` → 325 lib tests plus every integration binary green (including `mcp_read_conformance` and `mcp_read_transport_conformance`); final workspace gate 2526 passed / 0 failed. Mutation A (leak `entities` into the projection) → 5 failures including `classification and projection disagree for entities` and `no entity name in the explain trace`; mutation B (new `ScoredHit` field) → `error[E0027]: pattern does not mention field` at `read_explain.rs`.
- Verification report: baseline gate (pre-change) 352 files, TOTAL lines 97.89% / functions 98.71%; final `make coverage` 353 files, TOTAL lines 97.89% / functions 98.71%, guard green, per-file floor met on every reported file. Scoped `cargo llvm-cov --package clio-mcp --locked --no-clean` gave `read_explain.rs` 100.00/100.00 and `read_retrieve.rs` 97.71/100.00 before the workspace pass. `make lint` (workspace clippy `-D warnings`) clean; `cargo fmt --all -- --check` clean.
- Incidental bugs: none confirmed; no report filed.
- Known limitations: see §12.
- Remediation r1 (2026-09-26): all five adversary findings addressed — the drift guard now sweeps `ScoredHit`/`RetrieveHit` field names bound exhaustively (serde-skipped fields covered; mutation-verified before and after), the classification tables are shipped `pub` constants read by every assertion, a real-transport end-to-end trace contract test (`explain_trace_key_contract_over_stdio_and_http`) was added over stdio and HTTP, stale comments and the stale phase-file citations were corrected, and the module docs now state what each mechanism actually enforces. Final gates after remediation: `make check` exit 0 (fmt + clippy `-D warnings` + workspace tests, 2527 passed / 0 failed — the `unknown command \`recal\`` lines in the log are expected stderr from a passing CLI typo-suggestion test); `make coverage` exit 0, 353 files, TOTAL lines 97.89% / functions 98.71%, per-file floor met on every reported file, touched files `read_explain.rs` 100.00/100.00, `lib.rs` 100.00/100.00, `read_retrieve.rs` 98.83/100.00. Two plan_unlimited items declined with recorded reasons (see §9 remediation evidence).

---

## 10. Failure Handling and Recovery

### Expected Failure Modes

| Failure | Detection | Recovery |
|---------|-----------|----------|
| Content leaks into the trace | Boundary test | Stop; add exclusion; treat as a security failure |
| Existing trace changed | Before/after test | Restore values; refactor only the shape's source |
| Guard test too weak | Review/test mutation | Strengthen the assertion |
| File approaches 450 lines | Size check | Decompose |

### Rollback Strategy
Revert the projection refactor; the previously hand-written projection is behavior-identical for existing inputs, so rollback is safe.

### Partial Completion Policy
If the projection is shared but the content exclusion or guard is missing, do not claim completion.

---

## 11. Traceability

| Parent Requirement | Implementation Task | Verification | Acceptance Criterion |
|--------------------|---------------------|--------------|-----------------------|
| §4.9.4.G (`explain` score/domain/hop trace) | Task 1 | T100740-01 | AC-100740-01 |
| §4.9.5.C (health PII) / §4.12 + §7.4 (content-free diagnostics) | Task 1, Task 2 | T100740-02 | AC-100740-02 |
| FR-20 / §4.9.2 item 2 (binding identity) | Task 1 | T100740-05 | AC-100740-01 |
| Gap §9.2 (projection drift) | Task 2 | T100740-03 | AC-100740-03 |
| Regression / quality contract | All | T100740-06 | AC-100740-05 |

Required chain:

```text
Requirement → Capability → Implementation → Test → Evidence
```

---

## 12. Phase Exit Contract

### Outputs Produced
- A single shared `explain` hit projection with explicit content exclusion.
- A drift guard test.

### Guarantees Provided to Downstream Phases
After this phase is accepted:
- Any future hit field is deliberately classified as trace-visible or content-excluded.
- The trace remains PII-safe as the result contract grows.

### Known Limitations
- `scores` is not required to appear in the trace by this phase; if added later, it must go through the shared projection.
- Only the MCP trace is in scope; other diagnostic surfaces are protected by their own tests.

### Downstream Prerequisites
- Phase 100780, if it touches diagnostic surfaces, must respect the shared projection's content exclusion.

### Final Status
PASS WITH DOCUMENTED LIMITATIONS — all five acceptance criteria pass on real wire-trace, mutation, and coverage output; the qualifier covers the two planned scope limits in §12 (no `scores` in the trace yet; only the MCP trace is in scope).

### Verification Sign-Off
- Implementer: OpenCode CLI (Go . Deepseek V4.1 Flash Max)
- Verifier: [TBD]
- Human Approver: not required
- Date: 2026-09-26

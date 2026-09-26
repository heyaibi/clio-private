# Phase 100700: Entity-Overlap Match Reason (Display-Only)

### Attribution
Rounds below record plan authorship; implementation sign-off is in §12.
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | [TBD] | proposed |
| Adversary | r1 | [TBD] | [TBD] |
| Remediator | r1 | [TBD] | [TBD] |
| Remedy Approver | r1 | [TBD] | [TBD] |
| Finalize | r1 | [TBD] | [TBD] |
| Developer | r1 | OpenCode CLI (Go . Deepseek V4.1 Flash Max) | blocked |
| Developer | r1 | OpenCode CLI (Go . Deepseek V4.1 Flash Max) | done |
| Adversary | r1 | OpenCode CLI (Go . Space Bunny Free Max) | done |
| Remediator | r1 | OpenCode CLI (Together . GLM-5.3 Flash High) | done |
| Remedy Approver | r1 | OpenCode CLI (Go . Space Bunny Free Max) | approved |
| Finalize | r1 | OpenCode CLI (Together . GLM-5.3 Flash High) | done |

**Capability phase 100700** · **Effort:** ~2–3 days · **Status:** Plan ready · **Parent:** gap analysis `gaps/recall-result-fidelity-gap-analysis.md` §4.2, §7, §8 decision 4, §10.2; requirement FR-4 / §4.4, PR-4, §4.5, FR-20 / §4.9.2 item 2

### Vocabulary (read first) — zero shared moniker

| Term | Meaning in this phase | Must not be confused with |
|------|------------------------|----------------------------|
| **entity overlap** | The query text contains one of the hit's entity names under a documented, deterministic match rule | An entity-based ranking signal or a boost |
| **match reason** | A displayed, clearly labelled *derived* note ("entity match") | A span-verified fact or a retrieval-provenance reason |
| **derived** | Computed at retrieval/display time, not verified against a source span | The verified snapshot `entity` value itself |

This phase adds an explanation, not a ranking input. The hit set and order are unchanged.

---

## 1. Objective

### Goal
Add a deterministic, display-only entity-overlap reason: when the query text contains one of a hit's entity names under a documented match rule, mark that hit with a derived, non-authoritative `[entity match]` reason. The match never affects ordering, scoring, or filtering, and the reason is labelled derived everywhere it appears.

### Expected Outcome
- A hit whose `entities[]` contains a name present in the query text is marked with a derived entity-match reason.
- The match rule is deterministic (documented normalization; no fuzzy matching) and case handling is documented and tested.
- The reason is labelled derived and non-authoritative; it is not present in `warnings`, telemetry, or health surfaces (only the authorized read payload and the reserved text slot).
- Ordering, `scores`, and the hit set are unchanged by the presence of a match.
- The display-only vs rank-based decision is recorded; a ranking leg is explicitly not delivered here.
- The reason appears in the recall text view via the Phase 100660 slot, consistently across bindings.

### Parent Requirement
`requirement.md` — FR-4 / §4.4 (snapshot entities are span-verified; an inferred overlap is not); PR-4 / §4.4 (a derived reason must not be presented as a verified fact); §4.5 (an entity ranking leg would have to fuse by rank and is out of scope); FR-20 / §4.9.2 item 2 (binding identity). Gap source: `gaps/recall-result-fidelity-gap-analysis.md` §4.2.

### Design References (source-verified at plan time)
- No entity matching, overlap, or boost exists today in `crates/clio-retrieve`; boosts present are importance/temporal, and "overlap" in dedup is token overlap, not entity overlap.
- `recall_reason` (`crates/clio-lib/src/cli_read_render.rs:78-85`) maps `dense_rank`/`lexical_rank` to provenance text; the entity reason should follow the same display shape and be visually distinguishable as derived.
- The reserved slot is delivered by Phase 100660 (`crates/clio-lib/src/cli_read_render.rs:36-67`).
- Query text is available at retrieval time (`crates/clio-retrieve/src/hybrid.rs:179-282`, the `retrieve` request carries the query).
- Entity names are on the hit after Phase 100680.
- Determinism requirement: identical input/config MUST produce identical ordering and reason (risk §9 ranking-drift).

---

## 2. Scope Boundaries

### In Scope
- A deterministic entity-overlap match between query text and the hit's `entities[]`.
- A per-hit derived reason exposed on the authorized read surface and rendered in the text slot.
- Documented normalization and case handling.
- Tests for determinism and case sensitivity.
- A recorded decision: display-only (recommended) vs a future rank-based leg.

### Explicitly Out of Scope
- Any entity-based boost, ranking leg, or fusion change.
- Entity linking, canonicalization, or resolution beyond Phase 100680.
- Adding entity names to `warnings`, the `explanation`/`explain` trace, telemetry, or health.
- Query-time entity recognition beyond matching against the hit's names.
- Changing `recall_reason` provenance semantics.
- Entity-inclusion toggles (Phase 100780).

### Must Not Change
- Ordering, `scores`, candidate set, or budgets.
- The verified snapshot `entity` (the reason is derived, the value is not).
- The PII/content boundary and read authorization.
- The frozen `RetrieveHit` contract.
- Existing provenance reasons.

### Scope Expansion Rule
If work outside this scope appears necessary:
1. Stop.
2. Document the reason.
3. Request clarification or approval.
4. Do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- Phase 100680 accepted: hits carry `entities[]`.
- Phase 100660 accepted: the text view has the reserved entity-reason slot.
- The display-only decision is recorded (gap analysis §8 decision 4).
- Phases 100366/100368 (complete) own the CLI read path and the `recall_reason` rendering this phase extends (`command-ownership.md`).

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| `entities[]` | Present on hits | Phase 100680 acceptance |
| Text slot | Reserved in recall text | Phase 100660 acceptance |
| Query text | Available to the reason computation | `hybrid.rs` retrieve request inspection |
| Bindings | MCP/in-process/CLI projections | Parity tests |
| Match rule | Documented and deterministic | This phase's design record |

---

## 4. Existing-System Discovery

The agent MUST re-verify the following before editing; the facts below were confirmed at plan time.

### Required Discovery
- Confirm where the query text is available and whether the reason is computed in retrieval (shared) or only in the text renderer.
- Confirm the Phase 100660 slot and the `recall_reason` shape.
- Confirm how a derived reason can be exposed without leaking entity names into disallowed surfaces.
- Confirm the determinism test approach (identical input/config twice).
- Confirm which crates' files are near the 450-line limit.

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
- No entity matching exists; the reason is new.
- The query is available during retrieval, which is the natural shared place for cross-binding identity; a renderer-only computed reason would diverge JSON from text.
- `recall_reason` gives the display precedent.
- Determinism is already a requirement of the ranking contract (identical input/config), so the reason must be a pure function of the query and the hit's entities.

### Repository Adaptation Rule
The agent must determine the concrete computation location (shared retrieval vs binding) from the actual repository, provided the chosen placement yields identical names and semantics across bindings (FR-20).

---

## 5. Implementation Specification

### Task 1: Deterministic Entity-Overlap Match

#### Intent
Decide, deterministically, whether the query text contains one of the hit's entity names.

#### Required Capability or Behavior
- The match is a documented, deterministic function of the query text and the hit's `entities[]`.
- Normalization (for example Unicode case folding and trim) is documented; no fuzzy, stemmed, or approximate matching.
- Empty `entities[]` yields no match.
- Identical input/config yields identical match results.
- The match does not read or alter `scores`, ranks, or ordering.

#### Architectural Responsibility
`clio-retrieve` owns retrieval and MUST compute the derived flag once there; every binding (MCP, in-process, CLI text, and CLI JSON) projects that same flag. A renderer-only computation is not permitted because it would let JSON and text diverge (FR-20).

#### Required Changes
1. Implement the match function and document the normalization/case rule.
2. Attach a per-hit derived reason when a match occurs.
3. Ensure the function is pure and deterministic.
4. Add unit tests for case handling, whitespace, substrings, and multi-entity hits.
5. Compute the derived flag once in `clio-retrieve` and project it identically in every binding; add a parity test that CLI JSON and CLI text agree.

#### Implementation Constraints
- No ranking effect.
- No entity value in disallowed surfaces.
- No new dependency.
- Keep files ≤450 lines; `hybrid.rs` is 416.

#### Expected Result
A hit whose entity name appears in the query carries a derived entity-match flag; all others do not.

### Task 2: Display the Derived Reason and Record the Decision

#### Intent
Render the reason in the reserved slot, clearly labelled derived, and record the display-only decision.

#### Required Capability or Behavior
- The recall text shows the entity-match reason in the reserved slot, distinguishable from provenance reasons and labelled derived.
- The reason is identical across bindings on the authorized read surface.
- The reason does not appear in `warnings`, the `explanation`/`explain` trace, telemetry, or health.
- A short decision record states display-only was chosen and why a rank-based leg is deferred.

#### Architectural Responsibility
`clio-retrieve` owns the flag; `clio-lib` renders it; all bindings project it consistently.

#### Required Changes
1. Render the reason in the text slot; add a derived label.
2. Consume the single `clio-retrieve` flag in every binding (MCP, in-process, CLI text and JSON) and add a JSON/text parity test.
3. Add the boundary test for disallowed surfaces.
4. Record the display-only decision and the rank-based prerequisites.

#### Implementation Constraints
- Do not change provenance reasons or the disclaimer.
- Do not present the reason as verified.
- Keep test files ≤450 lines.

#### Expected Result
Text and JSON show the same derived reason; no disallowed surface contains entity names; the decision is recorded.

### Implementation Freedom
The agent may choose the match representation (boolean flag vs reason enum), the exact normalization, and where the reason is computed, provided determinism, cross-binding identity, derived labelling, and the no-ranking effect hold.

---

## 6. Agent Execution Rules

### Allowed Actions
- Add the match function, the derived reason, rendering, and tests.
- Record the display-only decision in the phase evidence.

### Forbidden Actions
- Add entity ranking, boosting, or fusion changes.
- Put entity names into `warnings`, trace, telemetry, or health.
- Change ordering, `scores`, budgets, provenance reasons, or the disclaimer.
- Add dependencies, delete tests, or claim completion without evidence.

### Agent Decision Boundary
The agent may decide the match representation and computation placement. The agent must request approval for: any ranking effect, any fuzzy matching, or adding entity data to a diagnostic surface.

A rank-based entity leg is **not** approved by this phase; if the agent believes it is needed, it must stop and request a separate phase (it would require rank-based fusion and benchmark validation).

### Mandatory Stop Conditions
Stop and report if: the match cannot be made deterministic; the reason cannot be exposed without leaking entity names into a disallowed surface; a ranking effect would be required; or correctness cannot be verified.

---

## 7. Security Constraints

### Required Controls
- The reason is computed against the query the caller already supplied; no new data access.
- Entity names remain content; the reason stays on the authorized read surface only.
- No entity name in `warnings`, trace, telemetry, or health.
- Bank isolation and read authorization unchanged.

### Sensitive Data Rules
- Never log the query text or entity names.
- Never commit secrets.

### Security Acceptance Conditions
- A boundary test proves the reason/entities are absent from `warnings`, the explain trace, telemetry, and health.
- No query text is echoed into any error or log by this phase.

---

## 8. Test and Verification Strategy

### Required Tests
- [ ] Unit tests (exact match, case difference, substring, whitespace, multiple entities, empty entities)
- [ ] Integration tests (flag reaches the hit and the text slot)
- [ ] Contract tests (binding parity; ordering/scores unchanged)
- [ ] End-to-end tests (real CLI/MCP `recall` shows the derived reason)
- [ ] Regression tests (provenance reasons and disclaimer unchanged)
- [ ] Security tests (no entity/query in disallowed surfaces)
- [ ] Failure-mode tests (empty entities; query absent)

### Required Test Scenarios

| Test ID | Scenario | Expected Result |
|---------|----------|-----------------|
| T100700-01 | Query contains an entity name (same case) | Derived entity-match reason shown |
| T100700-02 | Case differs | Match per documented case rule (deterministic) |
| T100700-03 | Query does not contain any entity name | No reason |
| T100700-04 | Hit has empty `entities[]` | No reason |
| T100700-05 | Identical input/config run twice | Identical reason and ordering |
| T100700-06 | Ordering and `scores` before/after | Unchanged |
| T100700-07 | MCP/in-process/CLI for same store | Identical reason |
| T100700-08 | Warnings/trace/telemetry/health | No entity name or reason |
| T100700-09 | Workspace suite, coverage, clippy, fmt, size | Green; per-file ≥90%; files ≤450 lines |

### Negative Testing
Verify the reason never changes ranking, is never presented as verified, and never leaks into a diagnostic surface.

### Verification Rule
Implementation claims must be supported by actual test output, inspection results, or other concrete evidence.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-100700-01 | Deterministic entity-overlap match with documented normalization | T100700-01, T100700-02, T100700-05 | Test output; design record |
| AC-100700-02 | Reason is shown labelled derived and non-authoritative | T100700-01 | Golden/test output |
| AC-100700-03 | Ordering, `scores`, and hit set unchanged | T100700-06 | Before/after test output |
| AC-100700-04 | Identical reason across bindings; absent from disallowed surfaces | T100700-07, T100700-08 | Parity/boundary tests |
| AC-100700-05 | Display-only decision recorded; no ranking leg delivered | Inspection | Decision record |
| AC-100700-06 | No regression; size/coverage gates pass | T100700-09 | Workspace suite; coverage report; size check |

#### Evidence (actual, 2026-09-26)

| AC ID | Result | Evidence |
|-------|--------|----------|
| AC-100700-01 | PASS | The rule lives alone in the new `crates/clio-retrieve/src/entity_match.rs`: Unicode lowercase mapping (`str::to_lowercase`, stable since 1.2.0 and locale-independent) on both sides, then contiguous substring containment. The normalization and its limits are documented in that module's header and in `docs/recall-entity-match.md`. Unit tests: `exact_name_in_query_matches`, `case_difference_follows_the_lowercase_rule`, `a_name_inside_a_longer_token_matches`, `whitespace_and_punctuation_are_compared_as_given`, `any_one_of_several_names_matches`, `empty_inputs_never_match`, `the_lowercase_mapping_is_unicode_aware_and_not_full_case_folding`, `the_rule_is_deterministic_for_identical_input`. Research recorded at implementation time: full Unicode case folding (`str::to_casefold`) is unstable (rust-lang/rust#157000, feature `casefold`), so the documented limit is that a few case pairs do not match (`ß` vs `SS`); no dependency was added. Inputs are the names `entities[]` already exposes, so the projection's trim applies and there is no NFC/NFD normalization, whitespace collapsing, or punctuation stripping here. |
| AC-100700-02 | PASS | `clio-retrieve` computes the flag once in `finalize` (`crates/clio-retrieve/src/finalize.rs`, from `args.req.query` and the same `entities` vector the hit carries) and `ScoredHit.entity_match` serializes as `entity_match: true` only (`#[serde(default, skip_serializing_if = "is_false")]`). The `clio recall` text view prints exactly `     [derived] entity match (display-only; not a ranking signal)` directly under the score breakdown (`crates/clio-lib/src/cli_read_render.rs`, `ENTITY_REASON_LINE`); the line is labelled derived and display-only and names no entity. Tests: `a_matched_hit_prints_the_derived_entity_reason`, `the_derived_reason_never_prints_an_entity_name`, `recall_marks_and_renders_the_derived_entity_reason`. Real binary: `developer-e2e-entity-match.out.txt` shows `"entity_match":true` in the CLI JSON and the derived line in the text output for the same store. |
| AC-100700-03 | PASS | The flag is computed after fusion, dedup, and page selection, and no ranking code reads it. `matching_never_changes_order_or_scores` runs one query and frozen clock over two stores that differ only in whether their snapshots carry an `entity`: hit order is identical and fused scores are bit-identical (`{:.17}`), with the flag true only in the entity store. `identical_input_yields_identical_reason_and_order` repeats one request and gets the same order, scores, and flags. A non-matching hit omits the key entirely, so its payload is the pre-existing shape (`a_query_without_the_name_leaves_the_flag_off`). The whole ranking suite runs unchanged in the final gate. |
| AC-100700-04 | PASS | One boolean is projected identically by every binding: serde serializes the same `ScoredHit` for MCP, the in-process JSON surface, and CLI JSON, and the text view formats that same value. Parity tests: `mcp_and_in_process_surfaces_expose_identical_entity_match` (MCP dispatch vs `retrieve_from_json`), `recall_marks_and_renders_the_derived_entity_reason` (CLI JSON and CLI text for one store). Disallowed surfaces: `entity_match_never_reaches_the_explanation_trace` removes the key from every hit and then asserts the rest of the payload — including `explanation.hits[]` and `warnings` — contains no `entity_match`; the pre-existing name sweeps (`entity_names_never_reach_warnings_or_the_explanation_trace`, `entity_names_never_reach_the_health_surfaces`) stay green; the derived text line carries no name (`the_derived_reason_never_prints_an_entity_name`, plus the line-by-line sweep in the CLI test and the real-binary run, which allows the name only in the echoed query line the caller supplied). |
| AC-100700-05 | PASS | Decision record in `docs/recall-entity-match.md` ("Why display-only (decision record)"): display-only was chosen because the reason never enters the fused score, needs no benchmark validation, and keeps results reproducible and comparable with results recorded before this field existed. The rank-based prerequisites are recorded there: a ranking-leg design, a fusion weight validated against the benchmark harness, and an explicit boost/filter decision. No ranking leg is delivered: no fusion, weight, boost, or budget code was touched. |
| AC-100700-06 | PASS | `cargo fmt --all` clean; `cargo clippy --workspace --all-targets --all-features --locked -- -D warnings` clean; workspace suite green. `make coverage` exit 0: `coverage-guard: 352 file(s) checked against 90.0% floors`, TOTAL lines 97.89% functions 98.73%, all reported files meet the per-file floor. Per-file rows: `entity_match.rs` 100.00/100.00, `types.rs` 100.00/100.00, `finalize.rs` 97.96/100.00, `cli_read_render.rs` 98.87/100.00 (the three uncovered lines in `cli_read_render.rs` are pre-existing `recall_reason` arms). Size check: every created or modified Rust file is at or below 450 lines — largest are `read_entities_tests.rs` 437, `schema_read_defs.rs` 368, `cli_read_render_scores_tests.rs` 367, `entity_match_tests.rs` 329, `cli_read_entities_tests.rs` 268, `types.rs` 224, `finalize.rs` 172, `entity_match.rs` 96 (the three test-only unblock files are `read_dedup_tests.rs` 450, `read_scores_tests.rs` 445, `ops_tools_tests.rs` 415; remediator r1 grew `entity_match_tests.rs`, `read_entities_tests.rs`, and `schema_read_defs.rs` by its own additions and re-measured every count above). Pre-change baseline note: the suite was red on the pre-existing issue #31 flake (the clio-mcp dense-arm test double mis-answers partial requests); three test-only hardening edits present in the tree at resume (hermetic `McpState::open_with_effective` for two tests, `fake_tei_server` reading complete request lines on blocking streams) restore the suite, and with them the baseline gate passed (351 files, TOTAL lines 97.89% functions 98.73%). Those three test-file edits are disclosed here because they are outside this phase's behavior but were required to obtain a green baseline and a green final gate; the defect itself stays recorded as issue #31. |

### Definition of Done
- [x] All in-scope behavior is implemented.
- [x] All acceptance criteria pass.
- [x] Required tests pass.
- [x] No unauthorized changes were introduced. (The three clio-mcp test-file hardening edits noted under AC-100700-06 are the requested unblock from the blocked developer attempt for issue #31; no production file outside this phase's scope was edited.)
- [x] Existing behavior remains intact.
- [x] Security checks pass.
- [x] Documentation is updated where required.
- [x] Evidence is collected.
- [x] Verification is completed.
- [x] Required approval is obtained. (Downstream pipeline steps — adversary, remediator, remedy approver, finalize — own this; the developer does not self-certify.)

### Completion Evidence
- **Implementation summary:** A hit whose query text mentions one of its `entities[]` names now carries a derived, display-only `entity_match` flag. The rule is Unicode-lowercase mapping on both sides plus contiguous substring containment, implemented as a pure function in the new `crates/clio-retrieve/src/entity_match.rs`. `finalize` computes it once from the request query and the same `entities` vector the hit already carries, so MCP, the in-process JSON surface, and both CLI outputs project the same boolean by serde, and the `clio recall` text view renders the reserved slot as one line: `[derived] entity match (display-only; not a ranking signal)`. The flag is omitted when false, so non-matching payloads keep their pre-existing shape. It is computed after fusion and read by no ranking code; ordering, scores, filters, and budgets are unchanged.
- **Display-only decision record:** in `docs/recall-entity-match.md` ("Why display-only"), with the rank-based prerequisites. Display-only wins because it explains a result without changing it, needs no benchmark validation, and keeps results reproducible; a future rank-based entity leg needs its own fusion weight, benchmark validation, and boost/filter decision.
- **Changed-component summary:** production — new `crates/clio-retrieve/src/entity_match.rs` (96 lines); modified `crates/clio-retrieve/src/finalize.rs` (172, compute the flag from the query and names), `crates/clio-retrieve/src/types.rs` (224, the field + docs), `crates/clio-retrieve/src/lib.rs` (module declaration only), `crates/clio-lib/src/cli_read_render.rs` (262, the derived line; the slot was reserved by an earlier phase). Tests — new `crates/clio-retrieve/src/entity_match_tests.rs` (329, 13 tests), extended `crates/clio-mcp/src/read_entities_tests.rs` (437), `crates/clio-lib/src/cli_read_entities_tests.rs` (268), `crates/clio-lib/src/cli_read_render_scores_tests.rs` (367). Remediation (r1) — `crates/clio-mcp/src/schema_read_defs.rs` (368, the `retrieve` description now states the flag's derived status). Docs — new `docs/recall-entity-match.md`; cross-links added in `docs/recall-entities.md` and `docs/recall-scores.md`. Unblock — `crates/clio-mcp/src/{ops_tools_tests,read_dedup_tests,read_scores_tests}.rs`, test-only hardening for issue #31.
- **Test execution output:** `cargo test -p clio-retrieve --lib` -> 204 passed / 0 failed (12 new); `cargo test -p clio-mcp --lib` -> 318 passed / 0 failed; `cargo test -p clio` -> 602 passed / 0 failed in the main test binary plus all other binaries green (3 new CLI tests). Real-binary end-to-end (`developer-e2e-entity-match.py` -> `developer-e2e-entity-match.out.txt`, exit 0, `ALL REAL-BINARY CHECKS PASSED`): MCP `store` + MCP `reindex --target lexical`, then MCP `retrieve` with `explain=true` returned `"entity_match":true` on the named hit and no `entity_match` anywhere else in the payload (including `explanation.hits[]`); the non-matching query omitted the key; CLI `recall --output json` carried `"entity_match":true` and `"entities":["Ada Lovelace"]`; CLI `recall --output text` printed the derived line and no entity name outside the echoed query; `clio ops diagnose` and `clio ops verify` carried no name.
- **Verification report:** pre-change baseline: `/tmp/cov-baseline.json`, 351 files, TOTAL lines 97.89% / functions 98.73%, guard clean (log `coverage-baseline-r4-run.log`). Final gate: `make coverage` exit 0, `coverage-guard: 352 file(s) checked against 90.0% floors`, TOTAL lines 97.89% / functions 98.73%, all per-file floors met (log `coverage-final-r4-run.log`). Scoped checks between the gates reused the warm instrumented build: `cargo llvm-cov --package clio-retrieve --locked --no-clean --json` showed `entity_match.rs` 100.00/100.00 with only pre-existing uncovered arms in `finalize.rs`/`types.rs` beyond this phase's edit; `cargo llvm-cov --package clio --locked --no-clean --json` showed `cli_read_render.rs` functions 100.00% and lines 98.87% with the same three pre-existing uncovered `recall_reason` arms.
- **Verification limits:** two gaps. (1) The dense-leg variant of the flag is not directly exercised end to end in a committed real-binary run: the real-binary runs (developer and adversary) have a reranker and, in the adversary run, an embedder, so the adversary's dense-leg evidence (`dense_rank=1` with `entity_match=true`) lives in its run artifact, not in the repo. In-repo, the flag is now pinned on a dense leg too: remediator r1 added `dense_populated_hit_carries_the_derived_flag` (embedder attached, `dense_rank` set, semantic score present). (2) The Unicode tests pin the practical meaning of the lowercase mapping on two examples (`İ`/`i̇` match, `ß`/`SS` no match); the rule inherits the standard library's full Unicode lowercase table, which is not enumerated here.
- **Remediator r1 evidence:** all five adversary findings closed. `make check` exit 0 (fmt clean, workspace clippy `-D warnings` clean, 53 test suites ok, 0 FAILED; log `remediator-check-r1.log`). Final `make coverage` exit 0: `coverage-guard: 352 file(s) checked against 90.0% floors`, TOTAL lines 97.89% / functions 98.73%, all per-file floors met; per-file rows re-read from `target/coverage/coverage.json`: `entity_match.rs` 100.00/100.00, `schema_read_defs.rs` 100.00/100.00, `types.rs` 100.00/100.00, `finalize.rs` 97.96/100.00, `cli_read_render.rs` 98.87/100.00 (log `remediator-coverage-r1.log`). Scoped: `cargo test -p clio-retrieve --lib entity_match` -> 13 passed / 0 failed (12 + the new dense-leg test); `cargo test -p clio-mcp --lib read_entities` -> 9 passed / 0 failed (8 + the new description-pin test).
- **Known limitations:** see §12.

---

## 10. Failure Handling and Recovery

### Expected Failure Modes

| Failure | Detection | Recovery |
|---------|-----------|----------|
| Match is nondeterministic | Repeat-run test | Restrict normalization; remove nondeterministic input |
| Reason changes ranking | Before/after ordering test | Remove any ranking use |
| Entity leaks into a diagnostic surface | Boundary test | Remove it; treat as a security failure |
| Binding divergence | Parity test | Fix the projection |
| Reason presented as verified | Read/review | Add the derived label |

### Rollback Strategy
Remove the reason and its rendering; entity names remain only in `entities[]`, and ranking was never affected, so rollback is behavior-preserving.

### Partial Completion Policy
If the match works but the label/boundary is incomplete, do not claim completion. A derived reason without a derived label is a defect.

---

## 11. Traceability

| Parent Requirement | Implementation Task | Verification | Acceptance Criterion |
|--------------------|---------------------|--------------|-----------------------|
| FR-4 / §4.4 (verified vs inferred) | Task 1, Task 2 | T100700-01, T100700-02 | AC-100700-01, AC-100700-02 |
| PR-4 / §4.4 (non-authoritative) | Task 2 | T100700-01 | AC-100700-02 |
| §4.5 (ranking is rank-fused) | Task 1 | T100700-06 | AC-100700-03 |
| FR-20 / §4.9.2 item 2 (binding identity) | Task 2 | T100700-07 | AC-100700-04 |
| §4.12 + §7.4 (content boundary) / §4.9.5.C (health PII) | Task 2 | T100700-08 | AC-100700-04 |
| Regression / quality contract | All | T100700-09 | AC-100700-06 |

Required chain:

```text
Requirement → Capability → Implementation → Test → Evidence
```

---

## 12. Phase Exit Contract

### Outputs Produced
- A deterministic, derived, display-only entity-overlap reason.
- A recorded display-only decision and rank-based prerequisites.

### Guarantees Provided to Downstream Phases
After this phase is accepted:
- A consumer can see why an entity-bearing hit appeared, without any ranking change.
- Phase 100780 may build an entity-inclusion toggle on the stable `entities[]`/reason shape.

### Known Limitations
- Display-only; entity overlap confers no ranking advantage.
- Deterministic exact/substring-style matching only; no fuzzy or semantic entity match.
- The rule uses Unicode lowercase mapping, not full case folding (the standard library's case-folding API is unstable), so a few case pairs do not match, for example `ß` against `SS`.
- No Unicode normalization on the read side: a name stored in a decomposed form matches only a decomposed query, the same trim-only stance as `entities[]`.
- Substring containment matches a name inside a longer token (`art` in `restart`); word-boundary matching is not implemented.
- Coverage is bounded by the Phase 100680 snapshot coverage.
- A rank-based entity leg remains a separate, unapproved capability requiring rank fusion and benchmark validation.

### Downstream Prerequisites
- Phase 100780 may rely on the derived reason shape and `entities[]`.
- Any future rank-based entity leg must reference this decision record and not retrofit ranking into this reason.

### Final Status
PASS | PASS WITH DOCUMENTED LIMITATIONS | BLOCKED | FAILED

### Verification Sign-Off
- Implementer: [TBD]
- Verifier: [TBD]
- Human Approver: [TBD, if required]
- Date: [TBD]

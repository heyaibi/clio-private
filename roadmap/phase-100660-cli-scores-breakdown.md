# Phase 100660: CLI Scores Breakdown in the Recall Text View

### Attribution
Rounds below record plan authorship; implementation sign-off is in §12.
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | OpenCode CLI (Go . Space Bunny Free Max) | done |
| Adversary | r1 | OpenCode CLI (Go . Deepseek V4.1 Flash Max) | done |
| Remediator | r1 | OpenCode CLI (Go . Space Bunny Free Max) | done |
| Remedy Approver | r1 | Command Code (Space Bunny Alpha High) | approved |
| Finalize | r1 | Command Code (DeepSeek V4 Flash (latest) Max) | done |

**Capability phase 100660** · **Effort:** ~1–1.5 days · **Status:** Plan ready · **Parent:** gap analysis `gaps/recall-result-fidelity-gap-analysis.md` §5.1, §7, §10.2; requirement §4.5, §4.9.4.G

### Vocabulary (read first) — zero shared moniker

| Term | Meaning in this phase | Must not be confused with |
|------|------------------------|----------------------------|
| **text breakdown** | A human-readable per-stage line under each recall hit showing `final`/`semantic`/`keyword`/`reranker` | The JSON `scores` object (Phase 100620); a ranking change |
| **entity reason slot** | A reserved place in the per-hit text for the entity-match reason added in Phase 100700 | The entity names themselves |
| **relative disclaimer** | The existing "score is relative (rank fusion), not calibrated relevance" note | A new calibration claim |

This phase changes presentation only. It does not compute or alter any score.

---

## 1. Objective

### Goal
Render the per-stage `scores` values in the `clio recall` text view, under the existing "relative, not calibrated" disclaimer, and leave a clearly-scoped place for the entity-match reason that Phase 100700 adds. JSON output and empty-recall output are unchanged except for the already-added `scores` object.

### Expected Outcome
- Text recall shows a per-stage breakdown for each hit (for example `final`, `semantic`, `keyword`, and `reranker` when present).
- The "score is relative (rank fusion), not calibrated relevance" disclaimer is retained.
- A `null` stage value is shown as absent/placeholder rather than `0`.
- The per-hit text has a defined slot for an entity reason, unused until Phase 100700.
- The empty-recall text is unchanged.
- CLI fixture/golden tests are updated for the new text.

### Parent Requirement
`requirement.md` — §4.5 step 3 (adaptive retrieval combines dense similarity, lexical/BM25, bounded graph traversal, and reranking, which is where the four stage values come from); §4.9.4.G `explain` (on reads: return a score trace, P12), which is the diagnostic-visibility reason a human-readable per-stage breakdown may exist. Gap source: `gaps/recall-result-fidelity-gap-analysis.md` §5.1.

Corrected in remediation round 1. The original line cited `PR-4 / §4.5 (never present a fused/derived score as calibrated)`. That citation was wrong on both halves: `requirement.md:128` defines PR-4 as "Snapshot for truth, gist for flow", and `grep -i calibrat baseline/requirement.md` returns no match, so no requirement states a score-calibration rule. The "score is relative (rank fusion), not calibrated relevance" line is an existing product disclaimer in the renderer, not a cited requirement, so this phase retains it as pre-existing wording rather than as a requirement trace. The requirement trace is §4.5 plus §4.9.4.G.

### Design References (source-verified at plan time)
- `render_recall` spans `crates/clio-lib/src/cli_read_render.rs:36-67`; it prints the disclaimer at `:50` and one `score {score:.4}` per hit at `:53-65`.
- `recall_reason` (`cli_read_render.rs:78-85`) maps `dense_rank`/`lexical_rank` to `semantic + lexical` / `semantic` / `lexical`; it already prints a provenance reason line, and the entity reason should follow the same shape.
- Text/JSON selection is `resolve_output`/`stdout_is_tty` (`crates/clio-lib/src/cli_output.rs:41-64`), out of scope here.
- CLI text fixtures are `crates/clio-lib/src/cli_read_tests.rs:127-154` (`recall_tty_text_and_explicit_output_override`). That file is 454 lines at plan time (pre-existing over-cap); if it is edited, decompose rather than grow it.
- `cli_read_render.rs` is 163 lines.

---

## 2. Scope Boundaries

### In Scope
- Per-stage score rendering in the recall text view.
- Retaining the relative disclaimer.
- A defined per-hit slot for the entity reason.
- Updating CLI text fixtures/golden tests.
- Keeping empty-recall output unchanged.

### Explicitly Out of Scope
- Computing any score, adding floors, or changing JSON.
- Entity extraction or the entity reason itself (Phase 100700).
- The `-o` alias and help text (Phase 100720).
- Changing the JSON `scores` object (Phase 100620/100640).
- Other read verbs' text rendering.
- Changing the text/JSON selection rule.

### Must Not Change
- The JSON payload shape and values.
- The fused ordering and the "relative, not calibrated" wording's meaning.
- Empty-recall output.
- The existing `recall_reason` provenance semantics.
- The `scores` object's meaning.

### Scope Expansion Rule
If work outside this scope appears necessary:
1. Stop.
2. Document the reason.
3. Request clarification or approval.
4. Do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- Phase 100620 accepted: `scores {final, reranker, semantic, keyword}` exists on hits.
- Phase 100640 accepted: `scores.reranker` is populated when rerank ran.
- Phase 100366 (complete) owns the CLI read path and `render_recall`; this phase edits that renderer under its ownership (`command-ownership.md`).

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| `scores` object | Present in the hit JSON | Phase 100620 acceptance |
| Normalized `reranker` | Numeric or `null` | Phase 100640 acceptance |
| Text renderer | `render_recall` prints one score line | `cli_read_render.rs` inspection |
| CLI tests | Text fixture asserts current output | `cli_read_tests.rs` inspection |

---

## 4. Existing-System Discovery

The agent MUST re-verify the following before editing; the facts below were confirmed at plan time.

### Required Discovery
- Confirm `render_recall`'s exact output lines and how it reads the hit JSON.
- Confirm `recall_reason`'s output shape, so the entity slot matches it.
- Confirm which tests assert the recall text and how they are structured.
- Confirm `cli_read_tests.rs` size and whether it must be decomposed.
- Confirm the empty-recall text path.

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
- `render_recall` prints one `score {score:.4}` per hit plus the disclaimer and a `recall_reason` provenance line.
- `cli_read_tests.rs` is 454 lines (pre-existing over-cap) and holds the text fixture.
- The `scores` object is available on the hit JSON after Phase 100620.

### Repository Adaptation Rule
The agent must determine concrete implementation locations from the actual repository. The plan does not prescribe the exact text format; the required behavior is a per-stage breakdown plus a reserved entity slot, under the existing disclaimer.

---

## 5. Implementation Specification

### Task 1: Render the Per-Stage Breakdown

#### Intent
Show each computed stage value in the text view without changing meaning or order.

#### Required Capability or Behavior
- Each recall hit's text shows the `final` score and any present `semantic`/`keyword`/`reranker` values.
- A `null` stage is omitted or shown as a placeholder, never as `0`.
- The disclaimer "score is relative (rank fusion), not calibrated relevance" remains.
- The provenance reason from `recall_reason` remains.
- Empty recall output is unchanged.

#### Architectural Responsibility
`clio-lib` owns text rendering; it reads the `scores` object and formats it. It does not recompute values.

#### Required Changes
1. Extend `render_recall` to format the per-stage values.
2. Reserve and document a slot for the entity reason; do not emit one yet.
3. Keep `render_recall` and the touched test file within their size budgets.
4. Update text fixtures/golden tests for the new lines.

#### Implementation Constraints
- Do not change JSON output.
- Do not show a missing stage as `0`.
- Do not imply calibration.
- Keep files ≤450 lines; decompose `cli_read_tests.rs` if needed.

#### Expected Result
Text recall shows the per-stage breakdown with the disclaimer; JSON and empty-recall are unchanged.

### Implementation Freedom
The agent may choose the exact line format (inline vs multi-line), the placeholder for absent values, and test structure, provided the required behavior holds and the empty-recall output is unchanged.

---

## 6. Agent Execution Rules

### Allowed Actions
- Modify `render_recall` and its tests; decompose a file if it exceeds 450 lines.
- Add fixture/golden updates for the new text.

### Forbidden Actions
- Change JSON, scores, ordering, or the disclaimer's meaning.
- Compute or fabricate scores.
- Emit an entity reason (Phase 100700) or change help/aliases (100720).
- Delete tests or claim completion without evidence.

### Agent Decision Boundary
The agent may decide the exact text layout and test organization. The agent must request approval for changing the disclaimer wording, the JSON shape, or the `recall_reason` semantics.

### Mandatory Stop Conditions
Stop and report if: the `scores` object is absent (Phase 100620 not landed), the text fixture cannot be updated without weakening coverage, or correctness cannot be verified.

---

## 7. Security Constraints

### Required Controls
- The text view shows only numeric scores and existing metadata; no content or entity names.
- No new logging of query or content.
- Bank isolation and authorization unchanged.

### Sensitive Data Rules
- Never print decrypted content beyond what is already rendered.
- Never commit secrets.

### Security Acceptance Conditions
- The breakdown contains no content or entity names.
- Existing redaction tests remain green.

---

## 8. Test and Verification Strategy

### Required Tests
- [x] Unit tests (formatting with all stages present, some present, all null) — `every_stage_is_shown_with_its_own_value`, `an_absent_stage_renders_the_placeholder_and_never_zero`, `an_all_null_score_object_never_shows_a_zero` in `cli_read_render_scores_tests.rs`.
- [x] Integration tests (recall text through the CLI path) — `recall_text_shows_the_per_stage_breakdown` in `cli_read_output_tests.rs` and `recall_text_shows_every_populated_stage` in `cli_read_scores_tests.rs`.
- [x] Contract tests (JSON unchanged; disclaimer retained) — `recall_json_scores_match_mcp_retrieve`, `recall_json_semantic_is_populated_with_live_embedder`, `recall_json_reranker_is_populated_with_configured_reranker`, and `recall_tty_text_and_explicit_output_override` (JSON carries no text-view line and no disclaimer).
- [x] End-to-end tests (real CLI `recall` text and `--output json`) — `recall_text_shows_the_stage_breakdown_end_to_end` in `tests/recall_text_scores_harness.rs`, which spawns the built `clio` binary for both modes. Added in remediation round 1; this box was the reason for that finding.
- [x] Regression tests (empty recall unchanged; provenance reason unchanged) — `the_empty_recall_text_is_unchanged`, `recall_empty_prints_no_results`, and the `[lexical match]` / `semantic + lexical` reason assertions.
- [x] Security tests (no content in the breakdown) — `the_breakdown_carries_no_content_or_entity_names`.
- [x] Failure-mode tests (missing `scores` handled gracefully) — `a_missing_score_object_falls_back_to_the_top_level_score`, `a_hit_without_any_score_prints_no_score_fragment`, `the_score_object_wins_when_only_it_carries_the_fused_value`.

### Required Test Scenarios

| Test ID | Scenario | Expected Result |
|---------|----------|-----------------|
| T100660-01 | All stages present | Breakdown shows each value; disclaimer present |
| T100660-02 | Only `semantic` present | Absent `keyword`/`reranker` omitted or placeholder, not `0` |
| T100660-03 | Empty recall | Output unchanged |
| T100660-04 | `--output json` | JSON payload unchanged by this phase |
| T100660-05 | Provenance reason | `recall_reason` line unchanged |
| T100660-06 | Workspace suite, coverage, clippy, fmt, size | Green; per-file ≥90%; files ≤450 lines |

### Negative Testing
Verify missing stages never render as `0`, JSON never changes, and no content leaks into the breakdown.

### Verification Rule
Implementation claims must be supported by actual test output, inspection results, or other concrete evidence.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-100660-01 | Text recall shows the per-stage breakdown | T100660-01, T100660-02 | **Met.** 12 unit tests in `cli_read_render_scores_tests.rs` plus `recall_text_shows_the_per_stage_breakdown` and the real-CLI run below. |
| AC-100660-02 | Disclaimer and provenance reason retained | T100660-05 | **Met.** The disclaimer string is asserted byte-for-byte and located above the hits; `[lexical match]` asserted. |
| AC-100660-03 | Empty recall and JSON unchanged | T100660-03, T100660-04 | **Met.** `no results` asserted in both unit and CLI tests; the JSON payload is asserted free of any text-view line. |
| AC-100660-04 | Entity reason slot reserved, not emitted | Inspection | **Met.** `recall_entity_reason_lines` at `crates/clio-lib/src/cli_read_render.rs:142`, called at `:82`; returns no line, and a test pins the per-hit block at three lines. |
| AC-100660-05 | No regression; size/coverage gates pass | T100660-06 | **Met.** Workspace tests pass; `make coverage` exit 0; every touched file ≤ 450 lines. Per-file counts in the Quality Gates table. |

### Test Results (real output)

`cargo test --locked --workspace` → **2470 passed, 0 failed** (2468 after round 1 of implementation; the two additions in remediation round 1 are listed at the end of the table below).

New tests, all passing:

| Test | Scenario |
|------|----------|
| `every_stage_is_shown_with_its_own_value` | All four stages present (T100660-01) |
| `an_absent_stage_renders_the_placeholder_and_never_zero` | `semantic`/`reranker` null, `keyword` present (T100660-02) |
| `a_present_zero_prints_zero_and_an_absent_stage_prints_the_placeholder` | A real `0` reads differently from a missing stage |
| `a_tiny_stage_value_is_not_rounded_into_a_zero` | `keyword: 1e-6` must not print as `0.0000` |
| `an_all_null_score_object_never_shows_a_zero` | Every stage null |
| `a_missing_score_object_falls_back_to_the_top_level_score` | Failure mode: no `scores` object |
| `the_score_object_wins_when_only_it_carries_the_fused_value` | `scores.final` present, top-level `score` absent |
| `a_hit_without_any_score_prints_no_score_fragment` | No score at all: no headline `score`, `final -` |
| `the_entity_reason_slot_is_reserved_but_emits_nothing` | AC-100660-04 |
| `the_breakdown_carries_no_content_or_entity_names` | Security: no content, snapshot, or source text in the line |
| `the_empty_recall_text_is_unchanged` | T100660-03 |
| `every_hit_gets_its_own_breakdown_in_order` | Multi-hit ordering |
| `recall_text_shows_the_per_stage_breakdown` | Real CLI path through `run_state` (T100660-01/02/05) |
| `recall_tty_text_and_explicit_output_override` | Extended: JSON output carries no text-view line (T100660-04) |
| `recall_empty_prints_no_results` | Unchanged, still green (T100660-03) |
| `recall_text_shows_every_populated_stage` | **Added in remediation r1.** All four arms live on the same hit, checked in the JSON and the text view (T100660-01) |
| `recall_text_shows_the_stage_breakdown_end_to_end` | **Added in remediation r1.** The same line through the spawned `clio` binary, in text and JSON mode (T100660-01/03/04) |

### Real CLI run (end to end, not a unit test)

`clio remember ... --db sqlite://… ` then `clio recall terse --output text`:

```text
Results for: terse

score is relative (rank fusion), not calibrated relevance

  1. The user prefers terse answers over verbose replies (2 notes since 2024-01-01).   [lexical match]   score 0.0120
     id: itm-cli-800621446-2223972  category: tool_config  epistemic_kind: fact  kind: semantic
     scores: final 0.0120  semantic -  keyword 0.000001  reranker -
```

The same call with `--output json` still emits only the JSON payload, unchanged. `clio recall zzz-nothing --output text` still prints exactly `no results`.

This run is what caught the number-format defect: the JSON value is `"keyword": 1e-6`, and a four-decimal format printed it as `keyword 0.0000` — indistinguishable from the `0` the phase forbids. The arms are now printed at full precision while `final` keeps the headline's four decimals.

### End-to-end check committed as a test (remediation r1)

The run above used to be a manual step recorded only in this file. It is now
`recall_text_shows_the_stage_breakdown_end_to_end` in
`crates/clio-lib/tests/recall_text_scores_harness.rs`, which spawns the built
`clio` binary: `remember` to seed a scratch database, then `recall terse
--output text` and `recall terse --output json`, plus an empty query.

Its assertions, all of which fail when the binary stops behaving:

| Assertion | Breaks when |
|-----------|-------------|
| the disclaimer and `[lexical match]` are present | the text view loses the note or the provenance reason |
| `semantic -` and `reranker -` appear, and no `<arm> 0` appears | an absent arm is rendered as a number |
| the `keyword` arm parses, is `> 0`, and is not a four-decimal rendering | the arms go back to `{:.4}`, which shows `0.0000` |
| the headline `score` and the breakdown `final` agree | the two stop sharing one formatter |
| JSON carries the four score keys, `semantic`/`reranker` null, and no `scores: final` or disclaimer line | JSON drifts or leaks a text-view line |
| an empty query prints exactly `no results` | the empty path changes |

Mutation evidence, run and then reverted:

| Mutation | Result |
|----------|--------|
| `STAGE_ABSENT` from `-` to `0.0000` | harness fails: "semantic shown as a number" |
| remove the breakdown line from `render_recall` | harness fails: "no breakdown line in the recall text" |
| `semantic_from_distance` in `clio-retrieve/src/stage_score.rs` always returns `0.0` | 595 tests still pass; **only** `recall_text_shows_every_populated_stage` fails, which is what proves the all-stages case is checked through the real retrieval path and not only over synthetic payloads |

The last row matters most: the twelve renderer tests feed the renderer a
hand-written payload, so a real retrieval bug cannot be seen by them.

### Quality Gates

| Gate | Command | Result |
|------|---------|--------|
| Format | `cargo fmt --all -- --check` | clean |
| Lint | `make check` → `cargo clippy --workspace --all-targets --all-features --locked -- -D warnings` | clean |
| Tests | `cargo test --locked --workspace` | 2470 passed, 0 failed |
| Coverage | `make coverage` | exit 0 |
| Coverage aggregate | llvm-cov | lines 97.88%, functions 98.71% |
| Coverage per file | `scripts/coverage_guard.py` | 350 files, every one ≥ 90% lines and functions |
| Renderer per file | `cli_read_render.rs` | lines 98.86% (175), functions 100.00% (31) |
| Entry point per file | `main.rs` | lines 99.05% (105), functions 100.00% (10) |
| Size | touched files | 247 / 295 / 184 / 387 / 424 / 265 / 405 / 207 lines, all ≤ 450 |

The size row lists, in order: `cli_read_render.rs` 247, `cli_read_render_scores_tests.rs` 295, `cli_read_output_tests.rs` 184, `main.rs` 387, `cli_read_scores_tests.rs` 424, `cli_read_tei_doubles_tests.rs` 265, `cli_read_tests.rs` 405, `tests/recall_text_scores_harness.rs` 207.

The `*_tests.rs` and `tests/*.rs` files are excluded from the llvm-cov report by path, which is why the report still shows 350 files. They are test code, and the guard has never scored them.

Baseline before the change was lines 97.73% (132) and functions 100.00% (18) on `cli_read_render.rs`; the new code raised the line figure.

### Definition of Done
- [x] All in-scope behavior is implemented.
- [x] All acceptance criteria pass.
- [x] Required tests pass. All seven §8 boxes are ticked, and each names the tests that satisfy it.
- [x] No unauthorized changes were introduced. JSON shape, values, ordering, disclaimer wording, and `recall_reason` semantics are untouched. Remediation round 1 changed no production code: its unstaged diff is `cli_read_scores_tests.rs` and `cli_read_tests.rs` plus two new test-only files, and `cli_read_render.rs` is byte-identical to the blob staged by round 1.
- [x] Existing behavior remains intact. Every pre-existing workspace test still passes; the count moved from 2468 to 2470 because two tests were added, none removed or weakened.
- [x] Security checks pass. The breakdown is built from the score object alone; a test proves a snapshot, entity name, and source text cannot reach the line.
- [x] Documentation is updated where required. `docs/recall-scores.md` no longer says the text view has no breakdown, and now documents the line. The Parent Requirement citation was corrected in remediation round 1; it had pointed at a requirement that does not say what the phase claimed.
- [x] Evidence is collected, including mutation evidence for the two tests added in remediation round 1.
- [x] Verification is completed: `make check` and `make coverage` both exit 0.
- [x] Required approval is obtained (downstream pipeline step). Remedy Approver r1 verdict `REMEDY_APPROVED 86a9ffef`: all three findings resolved and independently re-measured, both new tests proven by mutations the approver ran and reverted. No human approval was needed: no approval-gated item (disclaimer wording, JSON shape, `recall_reason` semantics) was changed.

### Completion Evidence

**Implementation summary**

`render_recall` in `crates/clio-lib/src/cli_read_render.rs` now prints a
`scores:` line under every hit, after the existing metadata line and before the
reserved entity-reason slot:

```text
     scores: final 0.0120  semantic -  keyword 0.000001  reranker -
```

Four supporting functions carry the behavior:

| Function | Responsibility |
|----------|----------------|
| `recall_final_score` | Resolve the fused value from `scores.final`, else the top-level `score`, else `None` |
| `format_fused` | The one formatter shared by the headline `score` and the breakdown's `final`, so they cannot disagree |
| `recall_score_breakdown` | Format the four stages; placeholder for absent, full precision for present |
| `recall_entity_reason_lines` | The reserved slot: called on every hit, returns no line today |

**Changed components**

| File | Change |
|------|--------|
| `crates/clio-lib/src/cli_read_render.rs` | Breakdown, placeholder, exact arm precision, reserved entity slot, shared fused formatter. 170 → 247 lines. |
| `crates/clio-lib/src/cli_read_render_scores_tests.rs` | **New.** 12 renderer tests over synthetic payloads. 295 lines. |
| `crates/clio-lib/src/cli_read_output_tests.rs` | One new CLI-path test; the existing TTY test now also proves JSON carries no text-view line. 116 → 184 lines. |
| `crates/clio-lib/src/main.rs` | Module declaration for the new test file (+4 lines). |
| `docs/recall-scores.md` | Removed the stale "the CLI text view does not show a score breakdown yet"; added a text-view section. |
| `crates/clio-lib/tests/recall_text_scores_harness.rs` | **New, remediation r1.** 1 test that spawns the real `clio` binary and checks the breakdown in text and JSON mode. 207 lines. |
| `crates/clio-lib/src/cli_read_tei_doubles_tests.rs` | **New, remediation r1.** The local `/embed` and `/rerank` doubles and the state factories, moved out of the assertion file. 265 lines. |
| `crates/clio-lib/src/cli_read_scores_tests.rs` | **Modified, remediation r1.** Doubles removed; added `recall_text_shows_every_populated_stage`, which checks the all-arms case through the CLI in both views. 311 → 424 lines. |
| `crates/clio-lib/src/cli_read_tests.rs` | **Modified, remediation r1.** Declares the new sibling doubles module. 398 → 405 lines. |

**Discovery output (re-verified before editing)**

- Subsystems: `clio-lib` CLI read engine and its text renderer only. `clio-retrieve` (score computation) and `clio-mcp` (payload shape) were read but not modified.
- Existing approach: `render_recall` printed one `score {score:.4}` per hit with `unwrap_or(0.0)`, plus the disclaimer and a `recall_reason` provenance bracket.
- Contracts: the hit JSON carries `scores {final, reranker, semantic, keyword}`; `final` mirrors the top-level `score`; `HitScores` types `final` as a non-optional `f64` and the arms as `Option<f64>`.
- Test coverage that had to change: the plan pointed at `cli_read_tests.rs:127-154`, but that fixture had already moved to `cli_read_output_tests.rs` and `cli_read_tests.rs` had already been decomposed. Both plan-time line references were stale; the behavior was not.
- Architectural constraints found: `render_text` is reached from two places — `cli_read_core.rs:72` for `recall` and `cli_write_shared.rs:78` for `shared retrieve`. Both share the renderer, so the breakdown appears in both text views. That is one renderer, not a second call site to change.
- **Assumption contradicted:** the plan assumed the top-level `score` is always present. It is, from `retrieve` — but the old `unwrap_or(0.0)` would have printed `score 0.0000` for a hit carrying no score, which is exactly the failure mode §10 lists. The renderer now omits the fragment instead.
- No question required escalation: the plan grants layout freedom, and no approval-gated item was touched.

**Known limitations**

1. **Resolved in remediation round 1: the all-stages-populated case is now proven through the CLI, not only at the renderer level.** The first round recorded this as a limitation because the TEI doubles were locked inside `cli_read_scores_tests.rs`, a file already at 447 of the 450-line cap. They now live in their own module, `cli_read_tei_doubles_tests.rs`, and `state_with_embedder_and_reranker` attaches a fake embedder and a fake reranker to the same state. `recall_text_shows_every_populated_stage` then checks one hit with all four arms populated, in the JSON view and in the text view, with the `semantic` and `reranker` values compared bit for bit. The two views cannot disagree about a number now, and the mutation table above shows the test fails when the real dense transform is broken.
2. **The reserved entity-reason slot emits nothing.** It is a real call site and a real function, both exercised on every hit, so the line and function coverage gates are honest. It deliberately reads no payload key: reading one would let arbitrary item content into the text view, which §7 forbids. The follow-up phase fills the function body.
3. `shared retrieve` text output also gains the breakdown, because it shares `render_recall`. That follows from the shared renderer rather than from a scope decision, and no other verb's text view changed.
4. **The `keyword` arm is compared on presence and precision, not on exact digits, in the two new tests.** `serde_json`'s float parser is not always correctly rounded: re-parsing the payload text `"keyword":1.4080000000000001e-6` lands one unit in the last place away from the value the renderer was handed. Comparing exact digits would either fail spuriously or need a tolerance wide enough to hide a real rounding defect, so the tests instead require the arm to be present, positive, and different from its own four-decimal rendering, which is exactly the property that failed in the first place. `semantic` and `reranker` are short decimals, so those are compared bit for bit.

---

## 10. Failure Handling and Recovery

### Expected Failure Modes

| Failure | Detection | Recovery |
|---------|-----------|----------|
| Missing stage shown as `0` | Fixture test | Emit omitted/placeholder |
| JSON drift | JSON test | Fix the renderer; JSON must be untouched |
| Empty recall changed | Regression test | Restore the empty path |
| Test file exceeds 450 lines | Size check | Decompose the test module |

### Rollback Strategy
Revert the renderer and fixture changes; the JSON path is untouched, so rollback only affects text presentation.

### Partial Completion Policy
If only some stages render, do not claim completion. Record what is covered and keep the tree green.

---

## 11. Traceability

| Parent Requirement | Implementation Task | Verification | Acceptance Criterion |
|--------------------|---------------------|--------------|-----------------------|
| §4.5 step 3 (dense + lexical + graph + rerank stages) | Task 1 | T100660-01 | AC-100660-01, AC-100660-02 |
| §4.9.4.G `explain` (score trace on reads) | Task 1 | T100660-01 | AC-100660-01 |
| Phase 100620/100640 outputs | Task 1 | T100660-02 | AC-100660-01 |
| Phase 100700 entity reason (slot only) | Task 1 | Inspection | AC-100660-04 |
| Regression / quality contract | All | T100660-06 | AC-100660-05 |

Required chain:

```text
Requirement → Capability → Implementation → Test → Evidence
```

---

## 12. Phase Exit Contract

### Outputs Produced
- A per-stage score breakdown in recall text output.
- A reserved, unused entity-reason slot.

### Guarantees Provided to Downstream Phases
After this phase is accepted:
- Phase 100700 can append an entity reason into the reserved slot without redesigning the renderer.
- JSON consumers are unaffected.

### Known Limitations
- The breakdown is presentational; it does not change ranking or calibration.
- Absent stages are shown as omitted/placeholder, so the exact absolute values may not always appear.

### Downstream Prerequisites
- Phase 100700 may rely on the reserved slot and the existing `recall_reason` line shape.

### Final Status
PASS WITH DOCUMENTED LIMITATIONS — Remedy Approver r1 approved (`REMEDY_APPROVED 86a9ffef`) with all three findings resolved and independently reproduced, and `make check` passes. The qualifier names the known limitations that stay open: the reserved entity-reason slot emits nothing until Phase 100700 fills it, `shared retrieve` gains the same breakdown because it shares the renderer, and the two new tests compare the `keyword` arm by presence and precision rather than exact digits.

### Verification Sign-Off
- Implementer: OpenCode CLI (Go · Space Bunny Free Max) — Developer r1 and remediation r1, 2026-09-26
- Verifier: Remedy Approver r1 — Command Code (Space Bunny Alpha High): every finding re-measured, both new tests proven by mutations it ran and reverted
- Human Approver: not required — no approval-gated item (disclaimer wording, JSON shape, `recall_reason` semantics) was changed
- Date: 2026-09-26

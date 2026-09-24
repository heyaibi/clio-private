# Phase 100660: CLI Scores Breakdown in the Recall Text View

### Attribution
Rounds below record plan authorship; implementation sign-off is in §12.
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | [TBD] | proposed |
| Adversary | r1 | [TBD] | [TBD] |
| Remediator | r1 | [TBD] | [TBD] |
| Remedy Approver | r1 | [TBD] | [TBD] |
| Finalize | r1 | [TBD] | [TBD] |

**Capability phase 100660** · **Effort:** ~1–1.5 days · **Status:** Plan ready · **Parent:** gap analysis `gaps/recall-result-fidelity-gap-analysis.md` §5.1, §7, §10.2; requirement §4.5, PR-4, §4.9.4.G

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
`requirement.md` — §4.5 (retrieval scores are relative); PR-4 / §4.5 (never present a fused/derived score as calibrated); §4.9.4.G (diagnostic visibility). Gap source: `gaps/recall-result-fidelity-gap-analysis.md` §5.1.

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
- [ ] Unit tests (formatting with all stages present, some present, all null)
- [ ] Integration tests (recall text through the CLI path)
- [ ] Contract tests (JSON unchanged; disclaimer retained)
- [ ] End-to-end tests (real CLI `recall` text and `--output json`)
- [ ] Regression tests (empty recall unchanged; provenance reason unchanged)
- [ ] Security tests (no content in the breakdown)
- [ ] Failure-mode tests (missing `scores` handled gracefully)

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
| AC-100660-01 | Text recall shows the per-stage breakdown | T100660-01, T100660-02 | Golden/test output |
| AC-100660-02 | Disclaimer and provenance reason retained | T100660-05 | Test output |
| AC-100660-03 | Empty recall and JSON unchanged | T100660-03, T100660-04 | Test output |
| AC-100660-04 | Entity reason slot reserved, not emitted | Inspection | Renderer inspection; Phase 100700 prerequisite |
| AC-100660-05 | No regression; size/coverage gates pass | T100660-06 | Workspace suite; coverage report; size check |

### Definition of Done
- [ ] All in-scope behavior is implemented.
- [ ] All acceptance criteria pass.
- [ ] Required tests pass.
- [ ] No unauthorized changes were introduced.
- [ ] Existing behavior remains intact.
- [ ] Security checks pass.
- [ ] Documentation is updated where required.
- [ ] Evidence is collected.
- [ ] Verification is completed.
- [ ] Required approval is obtained.

### Completion Evidence
- Implementation summary
- Changed-component summary
- Test execution output (text and JSON)
- Verification report
- Known limitations

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
| §4.5 / PR-4 (relative score) | Task 1 | T100660-01 | AC-100660-01, AC-100660-02 |
| §4.9.4.G (diagnostic visibility) | Task 1 | T100660-01 | AC-100660-01 |
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
PASS | PASS WITH DOCUMENTED LIMITATIONS | BLOCKED | FAILED

### Verification Sign-Off
- Implementer: [TBD]
- Verifier: [TBD]
- Human Approver: [TBD, if required]
- Date: [TBD]

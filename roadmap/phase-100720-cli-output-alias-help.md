# Phase 100720: CLI `-o` Alias and Output-Mode Help

### Attribution
Rounds below record plan authorship; implementation sign-off is in §12.
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | [TBD] | proposed |
| Adversary | r1 | [TBD] | [TBD] |
| Remediator | r1 | [TBD] | [TBD] |
| Remedy Approver | r1 | [TBD] | [TBD] |
| Finalize | r1 | [TBD] | [TBD] |

**Capability phase 100720** · **Effort:** ~1–2 days · **Status:** Plan ready · **Parent:** gap analysis `gaps/recall-result-fidelity-gap-analysis.md` §5.2, §5.3, §7, §8 decision 6, §10.2; requirement §4.9.2 item 2 (binding syntax may differ; semantics must not)

### Vocabulary (read first) — zero shared moniker

| Term | Meaning in this phase | Must not be confused with |
|------|------------------------|----------------------------|
| **`-o` alias** | A short spelling of the existing global `--output` value flag | A new output mode or a per-verb-only flag |
| **output-mode rule** | Explicit `--output`/`-o` wins, else text on a TTY and JSON when piped | A new default |
| **help body** | The `COMMAND_CATALOG` text printed by `clio help` | Per-verb usage strings |

This phase adds a spelling and documentation. It does not change output behavior.

---

## 1. Objective

### Goal
Add `-o` as an alias for the global `--output` value flag in the hand-rolled CLI parser and document the output-mode rule (explicit flag wins, otherwise text on a TTY and JSON when piped) in `clio help`. Output behavior and defaults are unchanged; only the accepted spelling and the help text change.

### Expected Outcome
- `-o json` and `-o=json` (and the joined/space forms the parser supports) behave exactly like `--output json`.
- `-o` is accepted before or after the verb consistently with `--output`'s current handling.
- `clio help` explains the output-mode rule and lists `-o` alongside `--output`.
- Unsupported short tokens still fail closed as before.
- Parser, output, and help tests are updated.

### Parent Requirement
`requirement.md` — §4.9.2 item 2 (binding syntax may differ; names and semantics must not). This is a CLI usability follow-up, consistent with the follow-up CLI phases 100362–100378. Gap source: `gaps/recall-result-fidelity-gap-analysis.md` §5.2–§5.3.

### Design References (source-verified at plan time)
- The parser rejects every single-dash token except `-h` (`crates/clio-lib/src/cli_args.rs:118-128`); `output` is a long-only global value flag in `GLOBAL_VALUE_FLAGS` (`cli_args.rs:30`).
- `explicit_output` recognizes only `--output`/`--output=` (`crates/clio-lib/src/cli_output.rs:89-105`).
- `split_leading_globals` strips only `--`-prefixed globals (`cli_args.rs:170-205`).
- No short-flag infrastructure exists beyond `-h` and top-level `-V`; there is no general alias mechanism.
- The help body is `COMMAND_CATALOG` (`crates/clio-lib/src/main.rs:187-317`); the global-flags line is `main.rs:314`.
- `resolve_output`/`stdout_is_tty` implement the rule (`crates/clio-lib/src/cli_output.rs:41-64`).
- Per-verb usage lines are `crates/clio-lib/src/cli_help_usage.rs:24-273`; **62 entries** at plan time, and 8 do not end in `[--output json|text]` (they end in trailing prose), so a blanket find/replace is not safe.
- Tests: `crates/clio-lib/src/cli_args_tests.rs:83-87` (`unknown_single_dash_flag_fails_closed`); `crates/clio-lib/src/cli_output_tests.rs:52-93`.
- Sizes: `cli_args.rs` 267, `cli_output.rs` 170, `main.rs` 358, `cli_help_usage.rs` 281.

---

## 2. Scope Boundaries

### In Scope
- `-o` as an alias for `--output` in parsing, global stripping, and explicit-output detection.
- Help text describing the output-mode rule and `-o`.
- Parser/output/help tests.
- A decision on whether to update the 62 per-verb usage strings (and, if so, doing it correctly).

### Explicitly Out of Scope
- Any new short flags other than `-o`.
- Changing the output-mode rule, defaults, or TTY detection.
- Per-verb-only `-o` semantics.
- Changing JSON/text payloads (Phases 100620–100700).
- The reserved top-level verbs and command ownership.

### Must Not Change
- The output-mode rule: explicit flag wins; otherwise text on a TTY and JSON when piped.
- Existing long-flag behavior.
- Fail-closed rejection of unknown single-dash tokens.
- Reserved top-level verbs; no new command.
- Existing help structure beyond the added output-mode explanation.

### Scope Expansion Rule
If work outside this scope appears necessary:
1. Stop.
2. Document the reason.
3. Request clarification or approval.
4. Do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- The CLI parser and output resolver are intact.
- The `-o` scope decision (global, allowed before the verb like `--output`, and whether to update per-verb usage strings) is recorded (gap analysis §8 decision 6).
- Phase 100366 (complete) owns the CLI parser/output/help plumbing this phase extends (`command-ownership.md`).

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| Global value flags | `output` present | `cli_args.rs:30` inspection |
| Single-dash rejection | Present | `cli_args.rs:118-128` inspection |
| Explicit-output detection | Present | `cli_output.rs:89-105` inspection |
| Help body | Present | `main.rs:187-317` inspection |
| Per-verb usage | Present | `cli_help_usage.rs:24-273` inspection |

---

## 4. Existing-System Discovery

The agent MUST re-verify the following before editing; the facts below were confirmed at plan time.

### Required Discovery
- Confirm every place `--output` is recognized (parser, global stripping, explicit-output detection) so `-o` is honored everywhere.
- Confirm the accepted forms (`--output json`, `--output=json`, and whether space/joined variants exist) and mirror them.
- Confirm `-h` handling so `-o` does not collide.
- Confirm the `COMMAND_CATALOG` global-flags line and where the output rule belongs.
- Confirm the exact per-verb usage entries and which do not end in the output suffix.
- Confirm sizes against the 450-line limit.

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
- No alias mechanism exists; `-o` needs explicit handling at each recognition point.
- 62 usage entries exist; 8 do not end in the output suffix, so per-verb updates require a careful, reviewed pass if undertaken.
- `main.rs` is 358 lines; `cli_help_usage.rs` 281.

### Repository Adaptation Rule
The agent must determine the concrete recognition points from the actual repository. The plan does not prescribe an alias infrastructure; a minimal, consistent handling of `-o` at every existing `--output` site is sufficient.

---

## 5. Implementation Specification

### Task 1: Add `-o` as a `--output` Alias

#### Intent
Accept `-o` wherever `--output` is accepted, with identical semantics.

#### Required Capability or Behavior
- `-o <mode>` and any joined form the parser supports behave exactly like `--output`.
- `-o` before the verb is handled the same way `--output` is handled by `split_leading_globals`.
- `explicit_output` recognizes `-o` so the mode is treated as explicit (it is not overridden by TTY detection).
- Unknown single-dash tokens still fail closed.
- `-o` without a value fails with the established usage error.

#### Architectural Responsibility
`clio-lib` owns the hand-rolled parser and output resolution.

#### Required Changes
1. Recognize `-o` in global flag handling and value-flag parsing.
2. Extend `explicit_output` to accept `-o` forms.
3. Ensure leading-global stripping handles `-o`.
4. Add parser and output tests for the new spelling and the fail-closed cases.

#### Implementation Constraints
- Do not add a general alias framework unless needed; keep the change minimal and consistent.
- Do not change defaults or TTY behavior.
- Keep files ≤450 lines.

#### Expected Result
`clio -o json recall "q"`, `clio recall "q" -o json`, and `clio recall "q" --output json` produce identical behavior.

### Task 2: Document the Output-Mode Rule

#### Intent
Explain the rule in help so the TTY/piped behavior is discoverable.

#### Required Capability or Behavior
- `clio help` describes: explicit `--output`/`-o` wins; otherwise text on a TTY and JSON when piped.
- The global-flags line mentions `-o` alongside `--output`.
- The help remains accurate if per-verb usage strings are updated.

#### Architectural Responsibility
`clio-lib` owns the help body and usage strings.

#### Required Changes
1. Add the output-mode explanation to `COMMAND_CATALOG`.
2. Add `-o` to the global-flags line.
3. Decide and execute the per-verb usage update (see Task 3).
4. Add/update help tests.

#### Implementation Constraints
- Do not restructure the help catalog.
- Keep wording consistent with the implemented rule.

#### Expected Result
A user can discover `-o` and understand when output is text vs JSON.

### Task 3: Decide Per-Verb Usage-String Updates

#### Intent
Resolve decision 6 explicitly rather than leaving a half-updated help surface.

#### Required Capability or Behavior
- Either all applicable usage entries mention `-o` consistently, or the decision to leave them as `[--output json|text]` is recorded with a reason.
- No entry is left inconsistent by an incomplete find/replace.

#### Architectural Responsibility
`clio-lib` owns the usage strings.

#### Required Changes
1. Identify the 62 entries and the 8 that do not end in the output suffix.
2. Apply the chosen option (update all applicable, or leave and document).
3. Add a test that pins the chosen form for a representative sample.

#### Implementation Constraints
- Do not blindly replace; the 8 non-suffixed entries must be reviewed individually.
- Keep `cli_help_usage.rs` ≤450 lines (it is 281).

#### Expected Result
The help surface is internally consistent and the decision is recorded.

### Implementation Freedom
The agent may choose the minimal recognition approach and the exact help wording, and may choose the per-verb update scope, provided `-o` is honored everywhere `--output` is, the rule is documented, and fail-closed behavior is preserved.

---

## 6. Agent Execution Rules

### Allowed Actions
- Modify the parser, output resolver, help body, usage strings, and tests.
- Record the `-o` scope and per-verb decision.

### Forbidden Actions
- Change output defaults, TTY behavior, or payloads.
- Add other short flags or a new command.
- Break fail-closed rejection of unknown single-dash tokens.
- Delete tests or claim completion without evidence.

### Agent Decision Boundary
The agent may decide the minimal parser handling and help wording, and whether per-verb strings are updated (with a recorded reason). The agent must request approval for: changing the output-mode rule, adding another short flag, or changing a command's ownership.

### Mandatory Stop Conditions
Stop and report if: `-o` cannot be honored at every `--output` site consistently; the change would alter defaults; or correctness cannot be verified.

---

## 7. Security Constraints

### Required Controls
- No new data access; help and parsing only.
- No secret or path leakage in help or errors.
- Bank isolation unchanged.

### Sensitive Data Rules
- Never log flags or values that could contain secrets.
- Never commit secrets.

### Security Acceptance Conditions
- Unknown single-dash tokens still fail closed with a usage error.
- No new output or logging path is introduced.

---

## 8. Test and Verification Strategy

### Required Tests
- [ ] Unit tests (parser accepts `-o` in each form; unknown `-x` fails closed; `-o` without value fails)
- [ ] Integration tests (`-o` before/after the verb; explicit output overrides TTY)
- [ ] Contract tests (output-mode rule unchanged)
- [ ] End-to-end tests (real CLI `recall` with `-o json` and `-o text`)
- [ ] Regression tests (existing `--output` and `-h` behavior)
- [ ] Security tests (no secret leakage in help/errors)
- [ ] Failure-mode tests (missing value, unknown short token)

### Required Test Scenarios

| Test ID | Scenario | Expected Result |
|---------|----------|-----------------|
| T100720-01 | `-o json` after the verb | JSON output, same as `--output json` |
| T100720-02 | `-o json` before the verb | Same as before-verb `--output json` |
| T100720-03 | `-o` joined/short form the parser supports | Matches `--output` equivalent |
| T100720-04 | `-o` without a value | Usage error |
| T100720-05 | `-x` unknown short token | Still fails closed |
| T100720-06 | TTY with no flag | Text; with `-o json` → JSON |
| T100720-07 | `clio help` | Documents the rule; lists `-o` |
| T100720-08 | Per-verb usage decision applied | Consistent entries |
| T100720-09 | Workspace suite, coverage, clippy, fmt, size | Green; per-file ≥90%; files ≤450 lines |

### Negative Testing
Verify unknown short tokens still fail closed, `-o` cannot silently change the default, and no payload changes.

### Verification Rule
Implementation claims must be supported by actual test output, inspection results, or other concrete evidence.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-100720-01 | `-o` behaves identically to `--output` at every recognition site | T100720-01…T100720-04 | Test output |
| AC-100720-02 | Unknown single-dash tokens still fail closed | T100720-05 | Test output |
| AC-100720-03 | Output-mode rule documented in help | T100720-07 | Help output |
| AC-100720-04 | Per-verb usage decision made and applied consistently | T100720-08 | Test output; decision record |
| AC-100720-05 | No payload or default change | Regression tests | Test output |
| AC-100720-06 | No regression; size/coverage gates pass | T100720-09 | Workspace suite; coverage report; size check |

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
- `-o` scope and per-verb decision record
- Changed-component summary
- Test execution output
- Help output
- Verification report
- Known limitations

---

## 10. Failure Handling and Recovery

### Expected Failure Modes

| Failure | Detection | Recovery |
|---------|-----------|----------|
| `-o` honored in one site but not another | Matrix test | Fix all recognition sites |
| Unknown short token accepted | Fail-closed test | Restore rejection |
| Default changed | TTY/regression test | Revert; do not change defaults |
| Incomplete per-verb find/replace | Help review/test | Finish or revert; never leave inconsistent |
| File approaches 450 lines | Size check | Decompose |

### Rollback Strategy
Revert the parser/help changes; `--output` and the output-mode rule are untouched, so rollback is behavior-preserving.

### Partial Completion Policy
If `-o` works but help is undocumented (or vice versa), do not claim completion. Record the gap and keep the tree green.

---

## 11. Traceability

| Parent Requirement | Implementation Task | Verification | Acceptance Criterion |
|--------------------|---------------------|--------------|-----------------------|
| §4.9.2 item 2 (binding syntax may differ; semantics must not) | Task 1 | T100720-01…T100720-04 | AC-100720-01 |
| §4.9.2 (fail-closed usage) | Task 1 | T100720-05 | AC-100720-02 |
| Usability / discoverability (follow-up CLI set) | Task 2 | T100720-07 | AC-100720-03 |
| Gap §8 decision 6 (`-o` scope) | Task 3 | T100720-08 | AC-100720-04 |
| Regression / quality contract | All | T100720-09 | AC-100720-06 |

Required chain:

```text
Requirement → Capability → Implementation → Test → Evidence
```

---

## 12. Phase Exit Contract

### Outputs Produced
- A working `-o` alias for `--output`.
- Documented output-mode help.
- A recorded per-verb usage-string decision.

### Guarantees Provided to Downstream Phases
After this phase is accepted:
- CLI documentation examples may use `-o` uniformly.
- The output-mode rule is discoverable and unambiguous.

### Known Limitations
- Only `-o` is added; there is no general short-flag framework.
- Per-verb usage strings may remain `[--output json|text]` if the recorded decision chose that.
- No payload or behavior change.

### Downstream Prerequisites
- No new capability depends on this phase; it is independent.

### Final Status
PASS | PASS WITH DOCUMENTED LIMITATIONS | BLOCKED | FAILED

### Verification Sign-Off
- Implementer: [TBD]
- Verifier: [TBD]
- Human Approver: [TBD, if required]
- Date: [TBD]

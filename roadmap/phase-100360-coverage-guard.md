# Phase 100360: Per-File Coverage Guard for the Lines/Functions Floor

### Attribution
Rounds below record plan authorship; implementation sign-off is in §12.
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | OpenCode CLI (Together . GLM-5.3 Flash High) | done |
| Adversary | r1 | Antigravity CLI (Gemini 3.8 Flash) | done |
| Remediator | r1 | OpenCode CLI (Go . Deepseek V4.1 Flash High) | done |
| Remedy Approver | r1 | OpenCode CLI (OpenRouter . Deepseek V4.1 Flash Max) | approved |
| Finalize | r1 | OpenCode CLI (Together . GLM-5.3 Flash High) | done |

**Remediation phase 100360 · **Effort:** ~0.5 day · **Gap:** G-04 · **Source:** `gap/requirement-gaps.md` §2, §3

## 1. Objective

### Goal
Enforce the per-file ≥90% lines/functions floor that `coverage.md` §2 already states but no automated check verifies, and document which llvm-cov summary column is which so agents stop confusing regions with lines.

### Expected Outcome
- `make coverage` exits non-zero when any reported file is below 90% lines or below 90% functions, not only when the aggregate TOTAL is below 90%.
- CI enforces the same per-file guard on the same single instrumented run.
- `coverage.md` documents the region/line/function column mapping and the guard command, and its §6 checklist references the guard.

### Parent Requirement
`coverage.md` §2 ("Per-file floor"), §6 (checklist), §9 (non-negotiables); `AGENTS.md` "Coverage Gate". This phase is a quality-gate fix; it does not change any `requirement.md` behavior.

### Design References
- `Makefile` `coverage` target runs `cargo llvm-cov --workspace --locked --summary-only --fail-under-lines 90 --fail-under-functions 90`; `--fail-under-*` only gates the TOTAL row.
- `.github/workflows/ci.yml` mirrors those two flags.
- `cargo llvm-cov --json` emits `data[].files[].summary.{lines,functions,regions}.percent`, which is what a per-file guard reads.

---

## 2. Scope Boundaries

### In Scope
- A guard script that reads one llvm-cov JSON run and fails if any reported file is under 90% lines or 90% functions.
- Wiring so `make coverage` and CI both invoke the guard on the same instrumented run (the test suite must not run twice for one gate).
- A `coverage.md` subsection documenting the three columns and the guard.

### Explicitly Out of Scope
- Changing the 90% threshold, the gate metrics (lines + functions), or the llvm-cov test-path exclusions.
- Gating regions; reintroducing `--fail-under-regions`.
- Fixing any file that is currently below 90% (the tree is green today; if the guard finds a violation, stop and raise — see `coverage.md` §9.1).
- Any Rust behavior change.

### Must Not Change
- The aggregate `--fail-under-lines 90 --fail-under-functions 90` gate.
- Region metrics remain informational and ungated (`coverage.md` §2).
- The existing path-based exclusion of `tests/` directories and `*_tests.rs` / `*-tests.rs` / `tests.rs` files.

### Scope Expansion Rule
If work outside this scope appears necessary: stop, document the reason, request clarification or approval, and do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- `cargo llvm-cov` and `llvm-tools-preview` are installed (already required by `make coverage`).
- The tree is green at ≥90% per file (verified 2026-09-22: 276 files, minimum 91.26% lines, 90.00% functions).

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| `cargo llvm-cov` | Emits JSON with per-file summaries | `cargo llvm-cov --workspace --locked --json --output-path /tmp/cov.json` |
| `Makefile` coverage target | Aggregate gate present | `make coverage` |
| CI workflow | Mirrors the Makefile gate | `.github/workflows/ci.yml` |
| `scripts/` conventions | Existing Python 3 scripts run without extra deps | `scripts/extract_quality.py` |

---

## 4. Existing-System Discovery

The agent MUST re-verify the following; the facts below were confirmed at plan time.

### Required Discovery
- Confirm the current `make coverage` command and that it gates only the aggregate TOTAL.
- Confirm CI runs the same two flags and where a guard step would attach.
- Confirm the exact JSON shape of the per-file summary (key names for lines/functions percentages).
- Confirm `coverage.md` §2 wording and §6 checklist so the new note slots in without contradiction.
- Identify how to obtain the JSON and the aggregate check from a single instrumented run.

### Discovery Output
- **Aggregate-only today.** `Makefile` `coverage` uses `--summary-only --fail-under-lines 90 --fail-under-functions 90`. `coverage.md` §2 explicitly requires agents to scan per-file rows by hand, which is the gap G-04 names.
- **CI mirrors the aggregate.** `.github/workflows/ci.yml` runs `cargo llvm-cov --workspace --locked --fail-under-lines 90 --fail-under-functions 90`; no per-file step.
- **JSON per-file shape.** `data[].files[].summary.lines.percent` and `data[].files[].summary.functions.percent`; regions are also present and MUST be ignored by the guard.
- **Docs already say the rule.** `coverage.md` §2 states the per-file floor; §6 has a checklist item; §9.1 forbids starting a phase when a file is below 90%. The missing piece is enforcement plus an explicit column-mapping note.

### Repository Adaptation Rule
The agent must determine concrete implementation locations from the actual repository. The plan does not prescribe file paths or script names unless they are an externally required contract.

---

## 5. Implementation Specification

### Task 1: Per-File Guard Script

#### Intent
Turn the hand-scan rule into an executable check.

#### Required Capability or Behavior
- Read one llvm-cov JSON report and, for every reported file, compare `summary.lines.percent` and `summary.functions.percent` against 90.0.
- Exit 0 when every file meets both floors; exit non-zero with a readable list of offending files (path, lines %, functions %) otherwise.
- Never read or report `summary.regions` as a pass/fail input.
- Handle missing/unreadable/malformed JSON with a clear non-zero error.

#### Architectural Responsibility
Tooling layer (`scripts/` plus `Makefile`/CI wiring). No Rust crate owns this.

#### Required Changes
1. Add the guard script using only the standard library (Python 3 is already used by `scripts/`).
2. Add a Make target (for example `coverage-guard`) and wire it so `make coverage` produces the JSON once, runs the aggregate gate, and runs the per-file guard on the same report.
3. Preserve operator ergonomics: the current target prints an llvm-cov summary, and switching the run to JSON must not silently drop it. Either re-derive the summary from the same report without re-running the suite (for example `cargo llvm-cov report`), or have the guard print a totals line plus the per-file offenders. Record which approach was taken.
4. Add the matching CI step.

#### Implementation Constraints
- The instrumented test suite MUST run once per gate, not twice. If a single run cannot both feed the guard and print a useful summary, the summary is re-derived from the same report — not obtained by a second instrumented run.
- The guard MUST fail closed on any parse error.
- No new dependency.

#### Expected Result
`make coverage` fails if any file is under 90% lines or functions, and prints the offenders.

### Task 2: Document the Column Mapping and Guard

#### Intent
Remove the hand-reading ambiguity the gap calls out.

#### Required Capability or Behavior
- `coverage.md` explains that llvm-cov reports regions, lines, and functions, that only lines and functions are gated, and that the guard enforces the per-file floor.
- The §6 checklist includes the guard result.

#### Architectural Responsibility
`coverage.md` only.

#### Required Changes
1. Add a short subsection under §2 (or a new subsection) with the column mapping and the guard command.
2. Update the §6 checklist item to reference the guard.
3. Do not contradict §9's non-negotiables (regions stay ungated).

#### Expected Result
A reader can tell regions from lines/functions and knows the guard exists.

### Implementation Freedom
The agent may choose the script language, file name, and Make/CI wiring provided the behavior, single-run constraint, and boundaries are respected.

---

## 6. Agent Execution Rules

### Allowed Actions
- Add the guard script, Make target, CI step, and docs note.
- Refactor the `coverage` recipe locally to avoid a double run.

### Forbidden Actions
- Gate regions; raise or lower the 90% threshold; change test-path exclusions.
- Change Rust source or tests.
- Claim completion without running the guard on the current tree.

### Agent Decision Boundary
The agent may decide script structure, target names, and JSON-vs-summary parsing. The agent must request approval for changing the gate metrics or thresholds.

### Mandatory Stop Conditions
Stop and report if the guard finds a reported file below 90% on the current tree, or if a single-run wiring cannot be achieved without changing the gate semantics.

---

## 7. Security Constraints

### Required Controls
- The guard reads only coverage metadata (file paths and percentages); it must not read source content or environment secrets.
- CI step must not print secret-bearing environment.

### Sensitive Data Rules
- Never commit secrets; the guard writes no files outside the coverage output directory.

### Security Acceptance Conditions
- Guard output contains file paths and percentages only.

---

## 8. Test and Verification Strategy

### Required Tests
- [ ] Unit tests for the guard's parse/compare logic against synthetic JSON fixtures
- [ ] Integration test: guard exits 0 on the current tree
- [ ] Contract test: aggregate gate still enforced on the same run
- [ ] Failure-mode tests: missing JSON, malformed JSON, a file at exactly 90.0%

### Required Test Scenarios

| Test ID | Scenario | Expected Result |
|---------|----------|-----------------|
| T100360-01 | Synthetic JSON with one file at 89.0% lines | Guard exits non-zero, names the file |
| T100360-02 | Synthetic JSON with one file at 89.0% functions, lines fine | Guard exits non-zero, names the file |
| T100360-03 | Synthetic JSON with a file at exactly 90.0% lines and functions | Guard exits 0 |
| T100360-04 | Synthetic JSON with regions below 90% but lines/functions at 95% | Guard exits 0 (regions ignored) |
| T100360-05 | Missing or malformed JSON path | Guard exits non-zero with a clear error |
| T100360-06 | Real `make coverage` on the current tree | Exit 0; guard reports no offenders |

### Negative Testing
Verify invalid/missing input fails closed, regions never affect the verdict, and the aggregate floor still fails independently.

### Verification Rule
Implementation claims must be supported by actual command output, not inspection alone.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-100360-01 | Guard fails when any file is under 90% lines or functions | T100360-01, T100360-02 | Self-test: `coverage_guard.py --self-test` → T100360-01 exits 1 naming `a.rs` (lines 89.00%); T100360-02 exits 1 naming `b.rs` (functions 89.00%) |
| AC-100360-02 | Guard passes on the current green tree | T100360-06 | `make coverage` exit 0: guard printed "276 file(s) checked … TOTAL lines 97.90% functions 98.94% … all reported files meet the per-file floor" |
| AC-100360-03 | Regions never gate | T100360-04 | Self-test T100360-04: lines/functions 95.0% with regions 50.0% exits 0 |
| AC-100360-04 | Aggregate gate unchanged and still enforced | T100360-06 | `make coverage` exit 0 keeps `--fail-under-lines 90 --fail-under-functions 90` on the same run; scoped contract run with `--fail-under-lines 99.5` on `clio-types` exited 1 |
| AC-100360-05 | One instrumented run per gate | Inspection | Makefile `coverage` recipe: one `cargo llvm-cov --json --summary-only --output-path` invocation, then `python3 scripts/coverage_guard.py $(COV_JSON)` on the same report; CI has the same two steps |
| AC-100360-06 | `coverage.md` documents column mapping and guard | Inspection | `coverage.md` §2 "Column mapping and the per-file guard" (JSON paths, gating table, guard command) and §6 first checklist item references the guard |

### Definition of Done
- [x] All in-scope behavior implemented.
- [x] All acceptance criteria pass.
- [x] Required tests pass.
- [x] No unauthorized changes introduced.
- [x] Existing gate behavior remains intact.
- [x] Security checks pass.
- [x] Documentation updated.
- [x] Evidence collected and verification completed.
- [x] Required approval obtained (none expected).
- [x] Required approval is obtained (downstream pipeline step).

### Completion Evidence
- Implementation summary: added `scripts/coverage_guard.py` (stdlib-only Python 3 guard that reads one llvm-cov JSON report, prints a TOTAL line plus per-file offenders, and exits 0/1/2/3 for pass/below-floor/usage/parse-error). Rewired the `make coverage` recipe to produce the JSON once (`--json --summary-only --output-path target/coverage/coverage.json`) with the unchanged aggregate `--fail-under-lines 90 --fail-under-functions 90` flags, then run the guard on that same report — one instrumented test run per gate. Added a standalone `coverage-guard` target that re-checks the floor on an existing report without re-running the suite. Added matching CI steps in `.github/workflows/ci.yml`. Operator ergonomics: the run no longer prints the full per-file table (JSON replaces it); the summary is re-derived from the same report by the guard (TOTAL line + offenders) — no second instrumented run.
- Guard script path and Make/CI diff: `scripts/coverage_guard.py`; `Makefile` (`coverage`/`coverage-guard` targets, `COV_JSON` variable, help line); `.github/workflows/ci.yml` ("Coverage (≥90% aggregate lines and functions)" + "Per-file coverage guard" steps).
- Synthetic-fixture test output: `python3 scripts/coverage_guard.py --self-test` → T100360-01 exit 1 (lines 89.0% named), T100360-02 exit 1 (functions 89.0% named), T100360-03 exit 0 (exactly 90.0%), T100360-04 exit 0 (regions 50% ignored), T100360-05 exit 3 (missing report); additional fail-closed fixtures (malformed JSON, file entry without summary, zero-file report) all exit 3. Result: "self-test: all passed".
- Real `make coverage` output: exit 0; "coverage-guard: 276 file(s) checked against 90.0% floors / TOTAL lines 97.90% functions 98.94% / all reported files meet the per-file floor".
- Known limitations: (a) regions remain ungated — intentional per `coverage.md` §2/§9, owned by no phase (not debt); (b) the guard inspects an existing report and never runs the suite itself — intentional, so the suite runs exactly once per gate; (c) on machines with a durable deployment config at `~/.config/am/deployment.json`, the hermetic gate needs `AM_DEPLOYMENT_CONFIG` pointed at an empty/absent file (two host tests assert on a deployment-free effective config); CI is unaffected because it has no such file. This is an environment note, not repo debt.

---

## 10. Failure Handling and Recovery

### Expected Failure Modes
| Failure | Detection | Recovery |
|---------|-----------|----------|
| `cargo llvm-cov` missing | Command not found | Print install hint, exit non-zero |
| JSON missing/malformed | Parse error | Fail closed with the path and reason |
| A file below 90% on current tree | Guard report | Stop, raise per `coverage.md` §9.1; do not fix silently |
| Double test run | Makefile inspection | Rework to a single JSON run |

### Rollback Strategy
Remove the guard wiring; the aggregate gate and docs revert to the prior state. No data or Rust behavior is affected.

### Partial Completion Policy
Do not claim completion if only the script or only the docs landed. Record both separately.

---

## 11. Traceability

| Parent Requirement | Implementation Task | Verification | Acceptance Criterion |
|--------------------|---------------------|--------------|-----------------------|
| G-04 (`gap/requirement-gaps.md`) | Task 1 | T100360-01…T100360-06 | AC-100360-01…AC-100360-05 |
| `coverage.md` §2 per-file floor | Task 1 | T100360-06 | AC-100360-02 |
| `coverage.md` §6 checklist | Task 2 | Inspection | AC-100360-06 |

Required chain:

```text
Gap → Guard capability → Script + wiring → Guard tests → Evidence
```

---

## 12. Phase Exit Contract

### Outputs Produced
- A per-file lines/functions guard executable by `make` and CI.
- Updated `coverage.md` column-mapping note and checklist.

### Guarantees Provided to Downstream Phases
After this phase is accepted:
- Any later phase that lowers a file below 90% lines or functions fails the gate automatically.
- `make coverage` is the single authoritative local gate for aggregate and per-file floors.

### Known Limitations
- The guard enforces lines and functions only; regions remain ungated by design.
- The guard reads llvm-cov output; it does not itself run the instrumented suite.

### Downstream Prerequisites
- Phases 038–052 assume `make coverage` enforces the per-file floor.

### Final Status
PASS | PASS WITH DOCUMENTED LIMITATIONS | BLOCKED | FAILED

### Verification Sign-Off
- Implementer: Developer r1 (OpenCode CLI — Together, GLM-5.3 Flash High); all acceptance criteria verified 2026-09-22, see §9 evidence
- Verifier: [TBD]
- Human Approver: not required
- Date: [TBD]

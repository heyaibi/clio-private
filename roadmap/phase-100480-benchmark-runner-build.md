# Phase 100480: Benchmark Runner Build — LongMemEval-style and LoCoMo-style

### Attribution
Rounds below record plan authorship; implementation sign-off is in §12.
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | [TBD] | [TBD] |
| Adversary | r1 | [TBD] | [TBD] |
| Remediator | r1 | [TBD] | [TBD] |
| Remedy Approver | r1 | [TBD] | [TBD] |
| Finalize | r1 | [TBD] | [TBD] |

**Remediation phase 100480 · **Effort:** locked by Phase 100460 at 60 h core (range 48–66 h, assumptions in `benchmark.md` §10.2) · **Gap:** G-10 (build) · **Source:** `gap/requirement-gaps.md` §2, §3

## 1. Objective

### Goal
Build a thin `am-bench` runner that scores the two first suites with one command and pinned snapshots, so retrieval quality gains an external anchor.

### Expected Outcome
- Adapters for the LongMemEval-style and LoCoMo-style suites exist.
- A one-command run scores both suites reproducibly against pinned snapshots.
- Judge integration produces first baseline scores.
- BEAM, MemoryAgentBench, and AMA-Bench remain documented stubs.

### Parent Requirement
`requirement.md` §8 (retrieval-quality benchmark expectation). Gap G-10 (build half). `benchmark.md` §5 (harness architecture, adapter interface, judge protocol), §6 (step plan).

### Design References
- Phase 100460 locked the datasets, judge, and estimate.
- `benchmark.md` §5.1 (harness architecture), §5.2 (unified system adapter interface), §5.3 (judge protocol), §5.4 (data partitioning), §5.6 (latency protocol), §5.7 (reference tokenizer).
- Keep the harness thin: the first two suites green before touching the other three.

---

## 2. Scope Boundaries

### In Scope
- Two suite adapters (LongMemEval-style, LoCoMo-style).
- A runner harness: one command, pinned snapshots, docs.
- Judge integration and first baseline scores.

### Explicitly Out of Scope
- BEAM, MemoryAgentBench, AMA-Bench implementations (documented stubs only).
- CI continuous benchmarking (`benchmark.md` step 12) — later.
- Tuning product retrieval/admission to improve scores.
- New rival-system adapters beyond the two first suites.

### Must Not Change
- Product retrieval, extraction, or admission behavior.
- `requirement.md` §8's SHOULD-level expectation.
- Phase 100460's dataset and judge decisions (a change requires a recorded reason).

### Scope Expansion Rule
If work outside this scope appears necessary: stop, document the reason, request clarification or approval, and do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- Phase 100460 accepted (pinned datasets, selected judge, locked estimate).

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| Dataset pins | Resolvable, license-checked | Phase 100460 record |
| Judge | Selected and calibratable | Phase 100460 record |
| Agent Memoir adapter target | Public library or MCP surface | Existing crates |
| Host resources | Bounded per the Phase 100460 estimate | Estimate assumptions |

### Locked decisions inherited from Phase 100460

- **Datasets:** LoCoMo (`snap-research/locomo` @ `3eb6f2c…`, blob `d95b8724…`) and LongMemEval (`xiaowu0162/LongMemEval` @ `9e0b455f…`, HF `longmemeval-cleaned`, oracle sha256 `821a2034…`), license-checked per `benchmark.md` §3.6. Do not re-decide without a recorded reason.
- **Judge:** calibrated two-tier LLM-as-a-judge per `benchmark.md` §5.3.1 — Tier 1 local `Qwen2.5-1.5B-Instruct` (temp 0, structured JSON) for trial loops; Tier 2 `gpt-4o-2024-08-06` for official scores. Token F1 is a cross-check only.
- **Estimate:** 60 h core (range 48–66 h) per `benchmark.md` §10.2, covering steps 1, 2, 3, 4, and 6 of `benchmark.md` §6.1 plus partitioning/stubs/docs margin. Scope itself is unchanged: two suite adapters, one-command runner, judge integration, three stubs.

---

## 4. Existing-System Discovery

The agent MUST re-verify the following; the facts below were confirmed at plan time.

### Required Discovery
- Confirm no runner/adapter/judge code exists.
- Read `benchmark.md` §5.2 for the adapter interface the two suites must implement.
- Confirm the product entry point the adapter drives (library API vs MCP).
- Confirm the latency and tokenizer protocols from `benchmark.md` §§5.6–5.7.
- Confirm the judge integration point from Phase 100460's decision.

### Discovery Output
- **No harness exists.** `benchmark.md` is a plan; nothing in `crates/`, `scripts/`, or `benchmarks/`.
- **Adapter contract is specified.** `benchmark.md` §5.2 gives a unified adapter interface; both suite adapters implement it.
- **Judge is decided.** Phase 100460 fixed the judge and its calibration; Phase 100480 integrates it.
- **Thin-first rule.** The gap explicitly says keep the harness thin and get the two suites green before the other three.

### Repository Adaptation Rule
The agent must determine concrete crate/module/test locations from the actual repository. The plan does not prescribe file paths or module names unless they are an externally required contract.

---

## 5. Implementation Specification

### Task 1: Suite Adapters

#### Intent
Turn each pinned suite into the unified adapter shape.

#### Required Capability or Behavior
- A LongMemEval-style adapter and a LoCoMo-style adapter each load their pinned snapshot, produce the ingestion stream and question set, and expose the unified adapter interface from `benchmark.md` §5.2.
- Single-hop, multi-hop, and temporal-reasoning categories are preserved.
- The anti-overfitting partition from `benchmark.md` §5.4 is honored.

#### Architectural Responsibility
Benchmark harness; product crates are consumers only.

#### Required Changes
1. Implement both adapters against the pinned snapshots.
2. Preserve category metadata needed for per-category scoring.

#### Implementation Constraints
- No product-behavior changes to fit a suite.
- Do not commit datasets; load from pinned sources.

#### Expected Result
Both suites ingest and question correctly.

### Task 2: Runner Harness

#### Intent
Make the suites runnable reproducibly in one command.

#### Required Capability or Behavior
- One command runs a suite end to end against pinned snapshots and emits scores.
- The run is reproducible (same inputs → same scores, modulo judge nondeterminism).
- Docs describe the command, inputs, and outputs.

#### Architectural Responsibility
Benchmark harness.

#### Required Changes
1. Add the runner entry point and configuration.
2. Add per-suite and overall score output.
3. Document usage.

#### Expected Result
One-command reproducible scoring.

### Task 3: Judge Integration and First Baselines

#### Intent
Produce the external anchor.

#### Required Capability or Behavior
- The Phase 100460 judge is integrated; positional-bias mitigation from `benchmark.md` §5.8 applies.
- First baseline scores for both suites are recorded.

#### Architectural Responsibility
Benchmark harness; judge credentials via the standard secret mechanism.

#### Required Changes
1. Integrate the judge and record scores.
2. Record the baseline with the exact dataset pins and judge settings.

#### Expected Result
First baseline scores for both suites.

### Task 4: Stubs for the Remaining Suites

#### Intent
Bound the scope explicitly.

#### Required Capability or Behavior
- BEAM, MemoryAgentBench, and AMA-Bench are documented stubs that clearly state they are not implemented.

#### Required Changes
1. Add stub documentation/placeholders.

#### Expected Result
Three stubs recorded; the two first suites green.

### Implementation Freedom
The agent may choose harness language, layout, and scoring output provided the adapter interface, reproducibility, and boundaries are respected.

---

## 6. Agent Execution Rules

### Allowed Actions
- Build adapters, the runner, and judge integration; add docs and stubs.
- Add benchmark-scoped tests and fixtures metadata.

### Forbidden Actions
- Change product behavior or tune it to a suite.
- Commit datasets or secrets.
- Implement the three stub suites.
- Claim scores without a reproducible run.

### Agent Decision Boundary
The agent may decide harness structure and output format. The agent must request approval for changing a Phase 100460 dataset/judge decision or for adding a new dependency.

### Mandatory Stop Conditions
Stop and report if a pinned dataset cannot be loaded, the judge cannot be integrated within the locked estimate, or reproducibility cannot be achieved.

---

## 7. Security Constraints

### Required Controls
- Judge credentials via the approved secret mechanism; never logged.
- No dataset redistribution beyond its license.

### Sensitive Data Rules
- Never commit secrets or downloaded datasets.
- Benchmark outputs contain scores, not user content.

### Security Acceptance Conditions
- No secret or licensed dataset in the repo.

---

## 8. Test and Verification Strategy

### Required Tests
- [ ] Unit tests (adapter parsing, partition logic, score aggregation)
- [ ] Integration tests (one-command run per suite)
- [ ] Contract tests (adapter interface honored)
- [ ] End-to-end tests (full suite run emits scores)
- [ ] Regression tests (product workspace green; no behavior change)
- [ ] Security tests (no secret in output/logs)
- [ ] Failure-mode tests (missing snapshot, judge unavailable)

### Required Test Scenarios

| Test ID | Scenario | Expected Result |
|---------|----------|-----------------|
| T100480-01 | LongMemEval-style adapter load + ingest | Correct stream and questions |
| T100480-02 | LoCoMo-style adapter load + ingest | Correct stream and questions |
| T100480-03 | One-command run, pinned snapshot | Reproducible scores |
| T100480-04 | Judge integration | Scores produced; bias mitigation applied |
| T100480-05 | Missing snapshot | Clear failure, no partial score |
| T100480-06 | Judge unavailable | Clear failure; no fabricated score |
| T100480-07 | Three stub suites | Documented, not implemented |
| T100480-08 | Product regression | Workspace green |
| T100480-09 | Per-category scores | Single-hop/multi-hop/temporal present |

### Negative Testing
Verify missing inputs fail clearly, no score is fabricated, and no product behavior changed.

### Verification Rule
Scores must come from an actual run with pinned inputs, not estimates.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-100480-01 | Both suite adapters work | T100480-01, T100480-02 | Test output |
| AC-100480-02 | One-command reproducible scoring | T100480-03 | Run output |
| AC-100480-03 | Judge integrated with bias mitigation | T100480-04 | Run output |
| AC-100480-04 | First baselines recorded with pins | T100480-04 | Baseline report |
| AC-100480-05 | Three suites remain stubs | T100480-07 | Stub docs |
| AC-100480-06 | No product regression | T100480-08 | Workspace test output |

### Definition of Done
- [ ] All in-scope behavior implemented.
- [ ] All acceptance criteria pass.
- [ ] Required tests pass.
- [ ] No unauthorized changes introduced.
- [ ] Existing behavior remains intact.
- [ ] Security checks pass.
- [ ] Documentation updated.
- [ ] Evidence collected and verification completed.
- [ ] Required approval obtained (if a Phase 100460 decision changes).

### Completion Evidence
- Implementation summary
- Adapter and runner code
- One-command run output
- Baseline scores with dataset pins and judge settings
- Known limitations

---

## 10. Failure Handling and Recovery

### Expected Failure Modes
| Failure | Detection | Recovery |
|---------|-----------|----------|
| Snapshot missing/mismatched | Adapter load | Fail clearly; do not score |
| Judge unavailable | Integration | Fail clearly; do not fabricate |
| Non-reproducible run | Repeat run | Fix nondeterminism sources |
| Estimate overrun | Progress check | Stop and re-estimate with the operator |

### Rollback Strategy
Remove the benchmark harness; product code is untouched, so rollback is additive-only.

### Partial Completion Policy
Do not claim completion if only one suite runs, or if scores are produced without pinned inputs. Record stubs and incomplete suites separately.

---

## 11. Traceability

| Parent Requirement | Implementation Task | Verification | Acceptance Criterion |
|--------------------|---------------------|--------------|-----------------------|
| §8 benchmark SHOULD | Tasks 1–3 | T100480-01…T100480-04 | AC-100480-01…AC-100480-04 |
| G-10 (build) | Tasks 1–4 | T100480-01…T100480-07 | AC-100480-01…AC-100480-05 |
| `benchmark.md` §5.2 (adapter), §5.4 (partition), §5.8 (bias) | Tasks 1, 3 | T100480-01, T100480-04 | AC-100480-01, AC-100480-03 |
| Regression (workspace green) | Tasks 1–4 | T100480-08 | AC-100480-06 |

Required chain:

```text
Requirement → Capability → Implementation → Test → Evidence
```

---

## 12. Phase Exit Contract

### Outputs Produced
- Two working suite adapters.
- A thin one-command runner with pinned snapshots.
- Judge integration and first baseline scores.
- Three documented stub suites.

### Guarantees Provided to Downstream Phases
After this phase is accepted:
- Retrieval quality has an external, reproducible anchor.
- The adapter interface is stable for adding later suites.

### Known Limitations
- Only two suites are implemented; the other three are stubs.
- Scores depend on the Phase 100460 judge; judge drift affects comparability.
- Continuous CI benchmarking is not yet wired.

### Downstream Prerequisites
- A later phase may extend to the remaining suites using the same adapter interface; it must not re-decide datasets or judge without a recorded reason.

### Final Status
PASS | PASS WITH DOCUMENTED LIMITATIONS | BLOCKED | FAILED

### Verification Sign-Off
- Implementer: [TBD]
- Verifier: [TBD]
- Human Approver: required only if a Phase 100460 decision changes
- Date: [TBD]

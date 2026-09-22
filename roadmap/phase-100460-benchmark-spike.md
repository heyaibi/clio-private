# Phase 100460: Benchmark Spike — Dataset and Judge Selection

### Attribution
Rounds below record plan authorship; implementation sign-off is in §12.
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | [TBD] | [TBD] |
| Adversary | r1 | [TBD] | [TBD] |
| Remediator | r1 | [TBD] | [TBD] |
| Remedy Approver | r1 | [TBD] | [TBD] |
| Finalize | r1 | [TBD] | [TBD] |

**Remediation phase 100460 · **Effort:** ~2–3 days · **Gap:** G-10 (spike) · **Source:** `gap/requirement-gaps.md` §2, §3

## 1. Objective

### Goal
Decide, with evidence, which benchmark datasets and which judge the first `am-bench` build will use, and lock the Phase 100480 build estimate before any runner code is written.

### Expected Outcome
- Dataset snapshots for the LongMemEval-style and LoCoMo-style suites are pinned with their licensing checked and recorded.
- A judge is selected (calibrated LLM-as-a-judge vs token F1) with a calibration check on a sample.
- A go/no-go decision and a locked Phase 100480 build estimate are recorded.

### Parent Requirement
`requirement.md` §8: "Retrieval quality SHOULD be benchmarked against established long-term conversational memory benchmarks (e.g., multi-session QA benchmarks such as LongMemEval-style and LoCoMo-style evaluations) covering single-hop, multi-hop, and temporal-reasoning question categories." Gap G-10 (spike half). `benchmark.md` §§3.1–3.2 (suites), §5.3 (judge protocol), §5.8 (positional bias).

### Design References
- `benchmark.md` is a plan only today; no runner, adapter, or judge code exists in `crates/`, `scripts/`, or a `benchmarks/` directory.
- `benchmark.md` §5.3 proposes a unified LLM-as-a-judge protocol; §5.8 covers positional-bias mitigation; §5.4 covers data partitioning.
- The two suites to build first are LongMemEval-style and LoCoMo-style; BEAM, MemoryAgentBench, and AMA-Bench stay documented stubs (Phase 100480).

---

## 2. Scope Boundaries

### In Scope
- Dataset selection, snapshot pinning, and licensing review for the two first suites.
- Judge selection and one calibration sample.
- A go/no-go decision and a locked Phase 100480 estimate.

### Explicitly Out of Scope
- Writing the runner, adapters, or judge integration (Phase 100480).
- Implementing BEAM, MemoryAgentBench, or AMA-Bench.
- Changing retrieval, extraction, or admission behavior to improve scores.
- CI wiring for continuous benchmarking (`benchmark.md` step 12 is later).

### Must Not Change
- `requirement.md` §8's SHOULD-level benchmark expectation.
- Extraction, admission, and retrieval semantics.
- No benchmark-driven tuning of product behavior in this phase.

### Scope Expansion Rule
If work outside this scope appears necessary: stop, document the reason, request clarification or approval, and do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- Phase 100440 accepted (fidelity and latency measured).
- Network access for dataset/judge research and licensing checks.

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| `benchmark.md` | Suite and judge specs present | Document review |
| Dataset availability | Public download reachable | Fetch attempt |
| Licensing terms | Known and compatible | License text review |
| Judge option | Calibratable | Sample run |

---

## 4. Existing-System Discovery

The agent MUST re-verify the following; the facts below were confirmed at plan time.

### Required Discovery
- Confirm no benchmark runner/adapter/judge code exists anywhere.
- Read `benchmark.md` §§3.1–3.2 for suite definitions and §5.3/§5.8 for the judge.
- Identify each suite's license, size, download method, and metric.
- Identify candidate judge options and their cost/latency/bias properties.
- Confirm the local model/host constraints that bound the Phase 100480 estimate.

### Discovery Output
- **Plan only.** `benchmark.md` describes a 12-step `am-bench` plan but no code exists in `crates/`, `scripts/`, or `benchmarks/`.
- **Two first suites.** LongMemEval-style (ReMe/AgentScope) and LoCoMo-style (Snap Research) are named; the other three stay stubs.
- **Judge undecided.** `benchmark.md` §5.3 proposes LLM-as-a-judge but does not lock a judge or calibration method.
- **Overfitting risk.** `benchmark.md` §5.4 already names an anti-overfitting data-partitioning protocol that the spike must respect.

### Repository Adaptation Rule
The agent must determine concrete decisions and estimate components from actual evidence. The plan does not prescribe dataset versions or judge vendors.

---

## 5. Implementation Specification

### Task 1: Pin Dataset Snapshots and Licensing

#### Intent
Make the suites reproducible and legally usable.

#### Required Capability or Behavior
- For each of the LongMemEval-style and LoCoMo-style suites: a pinned snapshot (version/hash), a download method, an expected size, and a recorded license with redistribution/use notes.
- The anti-overfitting partition rule from `benchmark.md` §5.4 is reflected in the pin.

#### Architectural Responsibility
Benchmark planning docs; no product code.

#### Required Changes
1. Record dataset identity, snapshot pin, and license per suite.
2. Note any licensing constraint that affects distribution.

#### Expected Result
A pinned, license-checked dataset decision for both suites.

### Task 2: Select the Judge and Calibrate

#### Intent
Choose the scoring mechanism before building around it.

#### Required Capability or Behavior
- A judge decision: calibrated LLM-as-a-judge or token F1, with the rationale and the trade-off recorded.
- A calibration check on a sample measures agreement/consistency and cost.

#### Architectural Responsibility
Benchmark planning docs.

#### Required Changes
1. Compare the judge options (accuracy, cost, latency, bias, reproducibility).
2. Run a calibration sample.
3. Record the choice and any positional-bias mitigation to carry into Phase 100480.

#### Expected Result
A selected judge with calibration evidence.

### Task 3: Go/No-Go and Locked Phase 100480 Estimate

#### Intent
Set the build scope and budget.

#### Required Capability or Behavior
- A go/no-go decision for Phase 100480.
- A locked build estimate (effort and cost) with the assumptions stated.

#### Architectural Responsibility
Phase 100460 documentation.

#### Required Changes
1. Record the decision and the estimate.
2. Update Phase 100480's scope if needed.

#### Expected Result
Phase 100480 has a locked estimate.

### Implementation Freedom
The agent may choose dataset sources and judge options provided the decisions are evidence-backed and boundaries respected.

---

## 6. Agent Execution Rules

### Allowed Actions
- Research datasets and judges; run calibration samples; write planning docs.
- Add pinned dataset metadata files if useful.

### Forbidden Actions
- Write runner/adapter/judge code (Phase 100480).
- Tune product behavior to a benchmark.
- Commit large datasets or secrets.

### Agent Decision Boundary
The agent may decide dataset versions, judge, and sampling method. The agent must request approval for any licensing arrangement that restricts redistribution, or for a scope change to Phase 100480 beyond the estimate.

### Mandatory Stop Conditions
Stop and report if a dataset's license forbids the intended use, if no judge can be calibrated within budget, or if the estimate cannot be bounded.

---

## 7. Security Constraints

### Required Controls
- Do not commit downloaded datasets; reference pinned sources.
- Judge credentials, if any, come from the standard secret mechanism and are never logged.

### Sensitive Data Rules
- Never commit secrets or API keys.
- Record license terms, not copyrighted content.

### Security Acceptance Conditions
- No secret in the repo; no unlicensed data committed.

---

## 8. Test and Verification Strategy

### Required Tests
- [ ] Verification: dataset pin resolves and hash/version matches
- [ ] Verification: license accepted and recorded
- [ ] Verification: judge calibration sample run and result recorded
- [ ] Verification: Phase 100480 estimate is numeric and assumption-backed
- [ ] Failure-mode: missing/unreachable dataset or uncalibratable judge is reported, not guessed

### Required Test Scenarios

| Test ID | Scenario | Expected Result |
|---------|----------|-----------------|
| T100460-01 | Resolve each dataset pin | Version/hash matches |
| T100460-02 | License review | Constraint recorded |
| T100460-03 | Judge calibration sample | Consistency/agreement number recorded |
| T100460-04 | Phase 100480 estimate | Locked numeric estimate with assumptions |
| T100460-05 | No-go path | Recorded with the blocking reason |

### Negative Testing
Verify a blocked license or uncalibratable judge ends in a recorded no-go rather than proceeding.

### Verification Rule
Decisions must cite the evidence (pin, license text, calibration number), not assertions.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-100460-01 | Both datasets pinned and license-checked | T100460-01, T100460-02 | Pin + license record |
| AC-100460-02 | Judge selected with calibration evidence | T100460-03 | Calibration output |
| AC-100460-03 | Go/no-go recorded | T100460-04, T100460-05 | Decision note |
| AC-100460-04 | Phase 100480 estimate locked | T100460-04 | Estimate with assumptions |

### Definition of Done
- [ ] All in-scope behavior implemented.
- [ ] All acceptance criteria pass.
- [ ] Required verifications pass.
- [ ] No unauthorized changes introduced.
- [ ] Existing behavior remains intact.
- [ ] Security checks pass.
- [ ] Documentation updated.
- [ ] Evidence collected and verification completed.
- [ ] Required approval obtained (if licensing restricts use).

### Completion Evidence
- Dataset pin and license record
- Judge selection and calibration output
- Go/no-go decision
- Locked Phase 100480 estimate
- Known limitations

---

## 10. Failure Handling and Recovery

### Expected Failure Modes
| Failure | Detection | Recovery |
|---------|-----------|----------|
| Dataset unreachable | Fetch failure | Record and choose an alternative or no-go |
| License forbids use | License review | No-go or alternative dataset |
| Judge cannot calibrate | Calibration sample | Fall back to token F1 or no-go |
| Estimate unbounded | Host constraints | Record the blocking factor in a no-go |

### Rollback Strategy
Planning-only phase; revert the docs and pins. No product behavior changes.

### Partial Completion Policy
Do not proceed to Phase 100480 without a dataset pin and a judge decision. If either is blocked, record a no-go.

---

## 11. Traceability

| Parent Requirement | Implementation Task | Verification | Acceptance Criterion |
|--------------------|---------------------|--------------|-----------------------|
| §8 benchmark SHOULD (retrieval quality) | Tasks 1–2 | T100460-01…T100460-03 | AC-100460-01, AC-100460-02 |
| G-10 (spike) | Task 3 | T100460-04 | AC-100460-03, AC-100460-04 |
| `benchmark.md` §§3.1–3.2, 5.3–5.4, 5.8 | Tasks 1–2 | T100460-01…T100460-03 | AC-100460-01, AC-100460-02 |

Required chain:

```text
Requirement → Capability → Implementation → Test → Evidence
```

---

## 12. Phase Exit Contract

### Outputs Produced
- Pinned, license-checked dataset decisions for the two suites.
- A selected judge with calibration evidence.
- A locked Phase 100480 estimate and go/no-go.

### Guarantees Provided to Downstream Phases
After this phase is accepted:
- Phase 100480 has fixed datasets, a fixed judge, and a bounded build scope.

### Known Limitations
- Only the two first suites are in scope; BEAM, MemoryAgentBench, and AMA-Bench remain stubs.
- Judge calibration is a sample, not a full validation.

### Downstream Prerequisites
- Phase 100480 must not re-decide datasets or judge without a recorded reason.

### Final Status
PASS | PASS WITH DOCUMENTED LIMITATIONS | BLOCKED | FAILED

### Verification Sign-Off
- Implementer: [TBD]
- Verifier: [TBD]
- Human Approver: required only if licensing restricts use
- Date: [TBD]

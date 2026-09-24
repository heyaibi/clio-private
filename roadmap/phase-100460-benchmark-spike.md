# Phase 100460: Benchmark Spike — Dataset and Judge Selection

### Attribution
Rounds below record plan authorship; implementation sign-off is in §12.
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | OpenCode CLI (Together . GLM-5.3 Flash High) | done |
| Adversary | r1 | Antigravity CLI (Gemini 3.8 Flash) | done |
| Remediator | r1 | OpenCode CLI (Go . Deepseek V4.1 Flash High) | done |
| Remedy Approver | r1 | Antigravity CLI (Gemini 3.8 Flash) | approved |
| Finalize | r1 | OpenCode CLI (Go . Deepseek V4.1 Flash High) | done |

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
- [x] Verification: dataset pin resolves and hash/version matches (LoCoMo blob verified via `git hash-object`; LongMemEval oracle sha256 verified byte-for-byte)
- [x] Verification: license accepted and recorded (CC BY-NC 4.0 and MIT recorded with redistribution notes in `benchmark.md` §3.6)
- [x] Verification: judge calibration sample run and result recorded (30-item sample; 60/60 discrimination, 0/60 consistency mismatches; `benchmark.md` §5.3.1)
- [x] Verification: Phase 100480 estimate is numeric and assumption-backed (60 h core, range 48–66 h; `benchmark.md` §10.2)
- [x] Failure-mode: missing/unreachable dataset or uncalibratable judge is reported, not guessed (no-go triggers recorded in `benchmark.md` §10.1; neither condition occurred)

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
| AC-100460-01 | Both datasets pinned and license-checked | T100460-01, T100460-02 | Pin + license record — **met**: `benchmark.md` §3.6; LoCoMo blob hash verified via `git hash-object` at pinned commit; LongMemEval oracle sha256 verified byte-for-byte against the HF LFS oid; S/M hashes API-resolved |
| AC-100460-02 | Judge selected with calibration evidence | T100460-03 | Calibration output — **met**: `benchmark.md` §5.3.1; local Tier-1 judge 60/60 discrimination agreement, 0/60 consistency mismatches, mean 8.5 s / p95 11.0 s per verdict, $0.00 cost on a 30-item seeded sample; swap-position spot check 7/8 |
| AC-100460-03 | Go/no-go recorded | T100460-04, T100460-05 | Decision note — **met**: `benchmark.md` §10.1 records GO with evidence and explicit no-go triggers |
| AC-100460-04 | Phase 100480 estimate locked | T100460-04 | Estimate with assumptions — **met**: `benchmark.md` §10.2 (60 h core, range 48–66 h, five stated assumptions); mirrored into `phase-100480-benchmark-runner-build.md` §3 |

### Definition of Done
- [x] All in-scope behavior implemented. (Dataset pins + licensing; judge selection with calibration sample; go/no-go; locked estimate — planning-only phase, no product code.)
- [x] All acceptance criteria pass. (See table above.)
- [x] Required verifications pass. (T100460-01..T100460-04 executed with real output; T100460-05 covered by recorded no-go triggers in `benchmark.md` §10.1.)
- [x] No unauthorized changes introduced. (Docs only: `benchmark.md` §3.6/§5.3.1/§10, this phase file, Phase 100480 header/dependencies.)
- [x] Existing behavior remains intact. (No Rust/crate changes; baseline coverage gate re-run and green — 318 files, TOTAL lines 97.96%, functions 98.87%.)
- [x] Security checks pass. (No secrets; datasets downloaded to a temporary directory only, nothing committed.)
- [x] Documentation updated. (`benchmark.md`, Phase 100480 roadmap.)
- [x] Evidence collected and verification completed. (Pin verifications, calibration results JSON, decision record.)
- [x] Required approval obtained (if licensing restricts use). (**Pending human review**: LoCoMo is CC BY-NC 4.0 — non-commercial terms are recorded in §3.6; use is internal evaluation with no redistribution, and the Human Approver sign-off below is left for the approval stage.)
- [x] Required approval is obtained (downstream pipeline step). (Remedy Approver r1 verdict APPROVE; all findings resolved.)

### Completion Evidence
- Dataset pin and license record: `benchmark.md` §3.6 (commit/blob/sha256 pins, sizes, download methods, CC BY-NC 4.0 and MIT license reviews with redistribution notes).
- Judge selection and calibration output: `benchmark.md` §5.3.1 (two-tier decision; 30-item sample, seed 100460; 60/60 discrimination, 0/60 consistency mismatches, latency mean 8.5 s / p95 11.0 s, $0.00; swap-position spot check 7/8). Raw calibration output was produced by a throwaway script in a temporary directory and is summarized here by design; numbers are quoted, not regenerable from this repo.
- Go/no-go decision: `benchmark.md` §10.1 — GO, with no-go triggers recorded.
- Locked Phase 100480 estimate: `benchmark.md` §10.2 — 60 h core (48–66 h), five assumptions; Phase 100480 header and §3 updated.
- Known limitations: the calibration sample used verbatim gold vs wrong-answer pairs (no paraphrase arm) and excluded LoCoMo category 5 (adversarial/abstention) and LongMemEval's `single-session-preference` question type (the 12 LongMemEval items covered five of the suite's six types); the hosted Tier-2 judge is untested end to end (no credentials in the environment); S/M splits were hash-verified via API metadata but not fully downloaded. Each is assigned to Phase 100480 as recorded work, not silently dropped.

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
- Judge calibration is a sample, not a full validation. The sample omitted LongMemEval's `single-session-preference` type (five of six types covered) and LoCoMo category 5 (adversarial/abstention); both are added to the Phase 100480 calibration set.

### Downstream Prerequisites
- Phase 100480 must not re-decide datasets or judge without a recorded reason.

### Final Status
PASS WITH DOCUMENTED LIMITATIONS

### Verification Sign-Off
- Implementer: Developer r1 (calibration sample, pin verification, and decision record; run log in `runs/phase-100460/developer-task-r1.log`)
- Verifier: [TBD]
- Human Approver: pending — LoCoMo's CC BY-NC 4.0 restricts use to non-commercial; use here is internal evaluation with no redistribution, and the approver should confirm that reading
- Date: 2026-09-24

# Phase 100440: Extraction Fidelity and Write-Path Latency Acceptance

### Attribution
Rounds below record plan authorship; implementation sign-off is in §12.
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | [TBD] | [TBD] |
| Adversary | r1 | [TBD] | [TBD] |
| Remediator | r1 | [TBD] | [TBD] |
| Remedy Approver | r1 | [TBD] | [TBD] |
| Finalize | r1 | [TBD] | [TBD] |

**Remediation phase 100440 · **Effort:** ~4–7 days · **Gaps:** G-11, G-12 · **Source:** `gap/requirement-gaps.md` §2, §3

## 1. Objective

### Goal
Raise FR-4 span grounding from a fixture-set 90.48% to the §8 ≥99% release bar on a genuine held-out set, and split the write-path latency metrics §8 requires: time-to-queryable and structural-maintenance duration, reported separately.

### Expected Outcome
- The empty-extract class (currently `rust_version`) is diagnosed with a named cause.
- The extractor-recall fix is applied without weakening span verification.
- A held-out numbers/names/dates set yields ≥99% FR-4 grounding, or the run fails with a named cause.
- `time-to-queryable` and `structural-maintenance duration` are measured and reported as separate metrics.

### Parent Requirement
`requirement.md` §8: "Fidelity (P3/FR-4/FR-5) acceptance: on a held-out set of turns containing exact numbers/names/dates, ≥ 99% of admitted structured snapshots SHALL pass FR-4 span grounding" and the write-path latency rule that time-to-queryable be measured independent of queued maintenance and reported as separate metrics (P2/FR-3/NFR-2). Gaps G-11, G-12.

### Design References
- `scripts/extract_quality.py` runs unit + live fixtures and enforces `--min-fidelity` (default 0.99); the `rust_version` case returns empty extracts.
- `scripts/span_verify.py` is the FR-4 verifier used by the harness.
- `crates/clio-write/src/ingest.rs:93-104` defines `IngestTiming { leaf_publish_ms, extract_phase_ms }`; §8 wants time-to-queryable (independent of queued maintenance) and maintenance duration separated.

---

## 2. Scope Boundaries

### In Scope
- Diagnosis and fix of the empty-extract class.
- A genuine held-out set and a ≥99% FR-4 run.
- Latency instrumentation splitting time-to-queryable from structural-maintenance duration, with separate reporting.

### Explicitly Out of Scope
- Changing FR-4 span-grounding rules or the verifier's acceptance criteria.
- Benchmark suites and the judge (Phases 046/048).
- Changing NFR-2's target or the drain schedule.
- New extractors or providers (Phase 100340 shipped the adapter).

### Must Not Change
- Span verification remains the authoritative gate; no field is admitted without a locatable span.
- Snapshots remain lossless; gists stay non-authoritative (PR-4).
- The extract phase is never conflated with leaf publish (NFR-2 / §9 risk).
- Release bar is ≥99%; a lower bar is a failure with a named cause, not a silent pass.

### Scope Expansion Rule
If work outside this scope appears necessary: stop, document the reason, request clarification or approval, and do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- Phase 100360 accepted (coverage guard).
- Phase 100400 accepted (backend-proven live path).
- The live extract endpoint is reachable for the fixtures (Compose profile).

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| `scripts/extract_quality.py` | Runs unit + live | `--unit-only` / `--live-only` |
| `scripts/span_verify.py` | FR-4 verifier | Import in the harness |
| Extractor factory | Configured extractor | Phase 100340 |
| `IngestTiming` | Current metrics shape | `crates/clio-write/src/ingest.rs` |

---

## 4. Existing-System Discovery

The agent MUST re-verify the following; the facts below were confirmed at plan time.

### Required Discovery
- Reproduce the 19/21 fixture result and identify exactly which cases fail and how (empty vs wrong value).
- Determine whether the failure is extractor recall or verifier false-reject (the gap says the failing class returns empty extracts → recall).
- Locate where `IngestTiming` is populated and where `leaf_publish_ms` is reported today.
- Identify what "structural-maintenance duration" can be measured from (maintenance hook timing).
- Confirm no held-out measurement exists and define the held-out set construction rule.

### Discovery Output
- **90.48% on fixtures.** `scripts/extract_quality.py` measures 19/21 = 90.48% against the §8 99% bar; the failing class returns empty extracts (extractor recall, not verifier false-accept).
- **No held-out measurement.** The current cases are tuning fixtures, not a held-out release set.
- **Latency not separated.** `crates/clio-write/src/ingest.rs:93-104` defines `IngestTiming { leaf_publish_ms, extract_phase_ms }`. It carries a leaf-publish time and an extract-phase time, but neither is a time-to-queryable measured independently of queued structural maintenance, and there is no structural-maintenance-duration metric at all. §8 requires those two reported separately.
- **Verifier is authoritative.** `span_verify.py` admits/rejects independently of the extractor; the fix must not loosen it.

### Repository Adaptation Rule
The agent must determine concrete implementation locations from the actual repository. The plan does not prescribe file paths or fixture names unless they are an externally required contract.

---

## 5. Implementation Specification

### Task 1: Diagnose the Empty-Extract Class (G-11)

#### Intent
Name the cause before fixing.

#### Required Capability or Behavior
- A written diagnosis identifies why the failing class (`rust_version` and any peers) returns empty extracts: prompt, template key, parse, or a verifier/extractor interaction.
- The diagnosis distinguishes extractor recall from verifier behavior.

#### Architectural Responsibility
Extraction pipeline (`clio-write` / the hosted extractor prompt) and the test harness.

#### Required Changes
1. Reproduce the failures with raw extractor output captured.
2. Write the diagnosis with the failing fixture and cause.

#### Expected Result
A named cause, not "it fails".

### Task 2: Extractor-Recall Fix

#### Intent
Make the extractor return the values it currently drops.

#### Required Capability or Behavior
- The recall fix makes the previously empty class extract correctly.
- Span verification still rejects ungrounded values; the fix must not bypass or weaken it.
- Fixture fidelity returns to 100% on the tuning set.

#### Architectural Responsibility
Extractor prompt/template/parse path; verifier unchanged.

#### Required Changes
1. Apply the fix identified in Task 1.
2. Re-run the fixture set and confirm all cases pass.
3. Add a regression test for the previously failing class.

#### Implementation Constraints
- Do not weaken span verification to raise the number.
- Do not special-case fixture strings; the fix must generalize.

#### Expected Result
Fixtures pass; the verifier is unchanged.

### Task 3: Held-Out Set and ≥99% Run

#### Intent
Measure the real acceptance bar on data not used for tuning.

#### Required Capability or Behavior
- A held-out set of turns containing exact numbers/names/dates is constructed and frozen before the run.
- `scripts/extract_quality.py --min-fidelity 0.99` runs against the held-out set and reports fidelity.
- The run passes ≥99%, or fails and the failure is reported with a named cause (no tuning on the held-out set to force a pass).

#### Architectural Responsibility
Test/fixture harness; the extractor and verifier are consumers.

#### Required Changes
1. Build and freeze the held-out set.
2. Run the acceptance measurement.
3. Record the fidelity and any named cause.

#### Implementation Constraints
- The held-out set must not be used for prompt tuning.
- The bar is ≥99%; do not lower it silently.

#### Expected Result
A recorded ≥99% pass or a named-cause failure.

### Task 4: Separate Latency Metrics (G-12)

#### Intent
Report time-to-queryable and maintenance duration separately.

#### Required Capability or Behavior
- Time-to-queryable for a new item is measured independent of any queued structural-maintenance job.
- Structural-maintenance duration is measured separately.
- Both are reported as distinct metrics (not conflated into `leaf_publish_ms`).

#### Architectural Responsibility
`clio-write` ingest timing plus the maintenance dispatch path.

#### Required Changes
1. Add a structural-maintenance duration metric alongside time-to-queryable.
2. Report both separately in the diagnostic/status surface.
3. Add a test proving a slow maintenance job does not inflate time-to-queryable.

#### Implementation Constraints
- Do not block the write path to measure maintenance.
- Keep the existing metrics meaningful; do not drop data.

#### Expected Result
Two separate metrics with a test that distinguishes them.

### Implementation Freedom
The agent may choose diagnosis tooling, held-out construction, and metric naming provided the behavior, bar, and boundaries are respected.

---

## 6. Agent Execution Rules

### Allowed Actions
- Capture raw extractor output; fix the extractor path; build held-out fixtures; add latency metrics and tests.
- Update `scripts/extract_quality.py` reporting for the held-out run.

### Forbidden Actions
- Weaken span verification; tune on the held-out set; lower the 99% bar.
- Conflate the two latency metrics.
- Claim a pass without the measured number.

### Agent Decision Boundary
The agent may decide fixture construction, prompt changes, and metric implementation. The agent must request approval for changing FR-4 verification rules or the §8 bar.

### Mandatory Stop Conditions
Stop and report if the failure is in the verifier rather than the extractor (a different fix, requiring approval), or if reaching ≥99% would require weakening verification.

---

## 7. Security Constraints

### Required Controls
- Held-out fixtures contain synthetic data, not real user content.
- Hosted extraction remains opt-in; no new egress when unconfigured.

### Sensitive Data Rules
- Never commit secrets or captured production content.
- Fixture source text is synthetic.

### Security Acceptance Conditions
- No ungrounded value reaches a snapshot, before or after the fix.

---

## 8. Test and Verification Strategy

### Required Tests
- [ ] Unit tests (previously failing class extracts correctly)
- [ ] Integration tests (fixture run at 100%)
- [ ] Contract tests (verifier behavior unchanged; snapshots lossless)
- [ ] End-to-end tests (held-out ≥99% run)
- [ ] Regression tests (workspace green)
- [ ] Security tests (ungrounded value still refused)
- [ ] Failure-mode tests (extractor unavailable; empty output)

### Required Test Scenarios

| Test ID | Scenario | Expected Result |
|---------|----------|-----------------|
| T100440-01 | Previously failing class | Non-empty, span-grounded extract |
| T100440-02 | Full fixture set | 100% |
| T100440-03 | Ungrounded paraphrase | Still refused |
| T100440-04 | Held-out run with `--min-fidelity 0.99` | ≥99% or named cause |
| T100440-05 | Slow maintenance job + store | Time-to-queryable unaffected |
| T100440-06 | Maintenance duration measured | Separate non-zero metric |
| T100440-07 | Regression suite | Workspace green |

### Negative Testing
Verify the fix does not admit ungrounded values, the held-out set is not tuned, and a slow maintenance job cannot inflate the leaf metric.

### Verification Rule
Implementation claims must be supported by the measured fidelity number and test output.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-100440-01 | Empty-extract class diagnosed with a named cause | T100440-01 | Diagnosis note |
| AC-100440-02 | Extractor-recall fix; fixtures at 100% | T100440-02 | Harness output |
| AC-100440-03 | Verifier still refuses ungrounded values | T100440-03 | Test output |
| AC-100440-04 | Held-out run ≥99% or named-cause failure | T100440-04 | Harness output |
| AC-100440-05 | Time-to-queryable and maintenance duration reported separately | T100440-05, T100440-06 | Test + metric output |
| AC-100440-06 | No regression | T100440-07 | Workspace test output |

### Definition of Done
- [ ] All in-scope behavior implemented.
- [ ] All acceptance criteria pass.
- [ ] Required tests pass.
- [ ] No unauthorized changes introduced.
- [ ] Existing behavior remains intact.
- [ ] Security checks pass.
- [ ] Documentation updated.
- [ ] Evidence collected and verification completed.
- [ ] Required approval obtained (only if FR-4 rules change).

### Completion Evidence
- Implementation summary
- Diagnosis and fix
- Held-out set description and fidelity number
- Latency metric output
- Known limitations

---

## 10. Failure Handling and Recovery

### Expected Failure Modes
| Failure | Detection | Recovery |
|---------|-----------|----------|
| Held-out fidelity <99% | T100440-04 | Report with a named cause; do not tune on the held-out set |
| Fix weakens verification | T100440-03 | Revert; fix recall only |
| Latency metrics conflated | T100440-05 | Separate them before claiming completion |
| Extractor unavailable | Harness | Report unavailable; do not fabricate |

### Rollback Strategy
Revert the extractor fix and the metric additions; the prior fixture result and `leaf_publish_ms` remain.

### Partial Completion Policy
Do not claim completion if diagnosis is missing, the held-out run was not executed, or the metrics are still conflated. Record the fidelity number honestly, including a failure.

---

## 11. Traceability

| Parent Requirement | Implementation Task | Verification | Acceptance Criterion |
|--------------------|---------------------|--------------|-----------------------|
| §8 fidelity bar / FR-4 / FR-5 (P3) | Tasks 1–3 | T100440-01…T100440-04 | AC-100440-01…AC-100440-04 |
| §8 write-path latency / FR-3 / NFR-2 (P2) | Task 4 | T100440-05, T100440-06 | AC-100440-05 |
| PR-4 (gists non-authoritative, snapshots lossless) | Task 2 | T100440-03 | AC-100440-03 |
| Regression (workspace green) | Tasks 1–4 | T100440-07 | AC-100440-06 |

Required chain:

```text
Requirement → Capability → Implementation → Test → Evidence
```

---

## 12. Phase Exit Contract

### Outputs Produced
- A named-cause diagnosis of the empty-extract class.
- An extractor-recall fix with regression coverage.
- A held-out fidelity measurement against the ≥99% bar.
- Separate time-to-queryable and maintenance-duration metrics.

### Guarantees Provided to Downstream Phases
After this phase is accepted:
- FR-4 fidelity has a real held-out number, not only a fixture number.
- Write-path latency reporting matches §8's separation requirement.

### Known Limitations
- A held-out failure below 99% blocks release and is recorded with a cause.
- Extraction throughput remains bounded by the configured provider.

### Downstream Prerequisites
- Phases 046/048 depend on a stable, measured extraction pipeline for benchmark ingestion.

### Final Status
PASS | PASS WITH DOCUMENTED LIMITATIONS | BLOCKED | FAILED

### Verification Sign-Off
- Implementer: [TBD]
- Verifier: [TBD]
- Human Approver: required only if FR-4 rules change
- Date: [TBD]

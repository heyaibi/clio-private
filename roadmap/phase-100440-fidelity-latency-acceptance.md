# Phase 100440: Extraction Fidelity and Write-Path Latency Acceptance

### Attribution
Rounds below record plan authorship; implementation sign-off is in §12.
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | OpenCode CLI (Go . Space Bunny Free Max) | done |
| Adversary | r1 | OpenCode CLI (OpenRouter . Deepseek V4.1 Flash Max) | done |
| Remediator | r1 | OpenCode CLI (Go . Space Bunny Free Max) | done |
| Remedy Approver | r1 | OpenCode CLI (OpenRouter . Deepseek V4.1 Flash Max) | approved |
| Finalize | r1 | OpenCode CLI (Go . Space Bunny Free Max) | blocked |
| Finalize | r2 | OpenCode CLI (Together . GLM-5.3 Flash High) | done |

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
| AC-100440-01 | Empty-extract class diagnosed with a named cause | T100440-01 | `docs/extraction-fidelity.md`; historical fixture replay reports `rust_version:empty_extract` and 19/21; this is replay evidence, not a provider measurement |
| AC-100440-02 | Extractor-recall fix; fixtures at 100% | T100440-02 | Mock `ChatExtractor` response flows through span verification and `extract_verify_store` into an admitted, grounded snapshot; tuning numbers are explicitly `fixture_contract_fidelity=21/21`; real extractor recall remains unverified with `endpoint_unavailable` |
| AC-100440-03 | Verifier still refuses ungrounded values | T100440-03 | Python/Rust shared parity table passes 14/14; self-tests cover paraphrase, missing, ambiguous/invalid dates, NFC/entity, numbers, and fail-closed unlisted leaves |
| AC-100440-04 | Held-out run ≥99% or named-cause failure | T100440-04 | Re-frozen 10-case held-out contract is 27/27 offline only; live attempt is 10/10 `endpoint_unavailable`, `live_fidelity=0.0000`; no live ≥99% claim |
| AC-100440-05 | Time-to-queryable and maintenance duration reported separately | T100440-05, T100440-06 | `IngestTiming`/`MaintenanceStatusData` expose both metrics; `render_maintenance` prints both; blocking-maintenance, completed-wave, and CLI text tests pass |
| AC-100440-06 | No regression | T100440-07 | Final serial `make check` passed; final `make coverage` passed 318 files at 97.9608% lines / 98.8955% functions with zero per-file offenders |

### Definition of Done
- [x] In-scope code and harness behavior implemented: the hosted prompt, fixture-contract/replay separation, verifier parity suite, fail-closed snapshot scope, redaction, mock recall path, and separated latency metrics.
- [x] The deterministic mock-provider path proves the previously empty `rust_version`/`os` response becomes a non-empty, span-grounded admitted snapshot; the real extractor-recall result remains explicitly unverified rather than inferred from fixture replay.
- [x] AC-100440-04 is handled through the explicit named-cause failure path: the live held-out request failed closed as `endpoint_unavailable`, with no fabricated ≥99% result.
- [x] Focused tests, the final serial `make check`, and the final coverage gate pass; the one initial clippy failure was fixed by extracting a test helper and the rerun was clean.
- [x] No unauthorized production verifier/admission rule changes were made; the harness rejects unlisted leaves and the Rust admission path remains authoritative.
- [x] Existing workspace regression tests remain green; the final serial run avoids the previously observed load-sensitive MemTree timeout.
- [x] Security checks pass: synthetic fixtures, bounded/redacted live handling, credential-pattern self-tests, no ungrounded admission, and no new egress path.
- [x] Documentation and public harness evidence distinguish fixture-contract replay, mock-provider verification, and live-provider evidence.
- [x] Evidence is recorded below, including the unavailable live extractor and the final coverage report.
- [x] Required approval is obtained (downstream pipeline step).

### Completion Evidence
- **Implementation summary:** The stdlib-only harness now labels fixed responses as `fixture_contract_replay` and historical responses as `historical_fixture_replay`, rejects non-empty unlisted snapshot leaves, reports `structural_candidates` separately from authoritative admission, redacts AWS/GitHub/JWT/Slack credential forms, and exposes `--parity`. The shared `scripts/verifier_parity.json` table is executed by both Python and the Rust test. A deterministic `ChatExtractor` transport test drives the previously empty `rust_version`/`os` response through response parsing, span verification, `extract_verify_store`, admission, and the write callback. The CLI maintenance text view now prints `time_to_queryable_ms` and `structural_maintenance_ms` separately.
- **Diagnosis and evidence classes:** `python3 -B scripts/extract_quality.py --unit-only --historical` intentionally fails with `fixture_replay_fidelity=0.9048`, `gold=19/21`, and `rust_version:empty_extract`; the fixed command passes with `fixture_contract_fidelity=1.0000`, `gold=21/21`. These are explicitly fixture replay/contract results, not extractor recall. The mock-provider test proves the fixed response is consumable and grounded, but a real provider capture remains unavailable.
- **Verifier and held-out set:** `python3 -B scripts/extract_quality.py --parity` passes 14/14 cases, and the Rust test executes the same table and passes. The re-frozen `scripts/extract_heldout.json` has 10 synthetic cases and passes its offline contract at 27/27 gold fields; it is not live evidence. The final live command against `http://127.0.0.1:34313` failed closed with 10/10 `endpoint_unavailable`, `live_fidelity=0.0000`, and a mode-0600 redacted raw record containing no sampled credential markers. No live ≥99% result is claimed.
- **Latency metric output:** `IngestTiming` preserves `leaf_publish_ms` and `extract_phase_ms`, records `time_to_queryable_ms` at the leaf-publish boundary, and keeps structural maintenance timing separate. `LeafIndex`, `MemTreeMaint`, `MaintenanceStatusData`, and `render_maintenance` expose the two values independently. `t05_t06_leaf_readable_before_slow_maintenance`, `consolidate_wait_reports_structural_duration`, and the CLI graph tests pass.
- **Regression and coverage:** Focused `cargo test -p clio-write --lib` passed 149 tests; the CLI graph tests passed 7 tests. The final serial `make check` passed formatting, workspace clippy with `-D warnings`, all workspace tests, and doc tests. The final full coverage gate used the canonical database URL, `RUST_TEST_THREADS=1`, and the installed `cargo-llvm-cov` path: 318 files, 97.9608% lines / 98.8955% functions, zero per-file offenders. Touched production rows include `cli_read_graph.rs` 100/100, `extract_chat.rs` 94.27/100, `ingest.rs` 99.49/100, `maintenance.rs` 100/100, `memtree_maint.rs` 96.58/100, and `memtree_tools.rs` 96.03/100 (lines/functions). The report is `target/coverage/coverage.json`.
- **Known limitations:** A live held-out fidelity number and a real extractor-recall measurement are unavailable because the configured local extraction endpoint reports `endpoint_unavailable` (the deployment/runtime prerequisite owns provisioning the model). The historical 19/21 result and fixed 21/21 result are offline fixture replay/contract evidence only. No unrelated bug was confirmed or fixed.

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
- A named-cause diagnosis of the empty-extract class, including the historical 19/21 fixture replay.
- A deterministic mock-provider regression through the hosted extraction, span verification, admission, and write path; the fixed 21/21 result is labeled fixture-contract evidence, not a provider score.
- A re-frozen held-out set, a 14/14 Python/Rust verifier parity table, and an honest live-run report; the live run is a named-cause failure because the configured endpoint is unavailable.
- Separate time-to-queryable and maintenance-duration metrics in ingest, status JSON, and human status text.

### Guarantees Provided to Downstream Phases
After this phase is accepted:
- The extraction harness can distinguish historical recall failure from span-verifier rejection and will not fabricate unavailable live results.
- Write-path latency reporting exposes queryability and structural maintenance separately.

### Known Limitations
- The live held-out ≥99% number and a real extractor-recall measurement are unavailable because the configured local endpoint reports `endpoint_unavailable`; the extraction deployment/runtime prerequisite owns provisioning that asset. This phase owns the frozen harness, mock-provider verification, and named-cause report.
- The historical 19/21 result and fixed 21/21 result are offline fixture replay/contract evidence, not live provider measurements.
- Extraction throughput remains bounded by the configured provider.

### Downstream Prerequisites
- Phases 046/048 require a healthy extractor and a fresh live held-out run before treating the release bar as measured.

### Final Status
PASS WITH DOCUMENTED LIMITATIONS

### Verification Sign-Off
- Implementer: OpenCode CLI (Go . Space Bunny Free Max), Developer r1
- Remediator: OpenCode CLI (Go . Space Bunny Free Max), Remediator r1
- Verifier: [pending — Adversary r1]
- Human Approver: not required; FR-4 rules were not changed
- Date: 2026-09-24

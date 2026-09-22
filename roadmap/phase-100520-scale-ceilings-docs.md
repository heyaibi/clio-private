# Phase 100520: Scale Ceilings, Transport Pooling, and Deployment Docs

### Attribution
Rounds below record plan authorship; implementation sign-off is in §12.
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | [TBD] | [TBD] |
| Adversary | r1 | [TBD] | [TBD] |
| Remediator | r1 | [TBD] | [TBD] |
| Remedy Approver | r1 | [TBD] | [TBD] |
| Finalize | r1 | [TBD] | [TBD] |

**Remediation phase 100520 · **Effort:** ~4–5 days · **Gaps:** G-13, G-14, G-15, G-16 · **Source:** `gap/requirement-gaps.md` §2, §3

## 1. Objective

### Goal
Raise or explicitly document each known scale ceiling: hygiene near-dedup and staleness, retention-mission matching, TLS transport pooling and verification, and the missing single-host sync-omission note in user-facing deployment docs.

### Expected Outcome
- Hygiene has either an index/ceiling upgrade, a last-relevance field, and a scheduled-cleaner decision, or a documented upgrade path for each.
- Retention matching has a semantic-matching spike result and a learning decision.
- TLS transport has a pooling/HTTP-2 decision and a verified-TLS mock test.
- A user-facing deployment doc states that single-host deployments may omit sync.

### Parent Requirement
Diagnostic/ops behavior around §4.9.5.A (hygiene), §4.9.5.E / retention mission (clause near `Retention profile` in the glossary and `retention_mission`), the HTTP transport used for embed/rerank/extract providers, and §4.9.5.D / §4.9.6 (single-host sync omission must be stated plainly). Gaps G-13–G-16.

### Design References
- `crates/clio-hygiene/src/audit.rs`: `DEFAULT_MAX_SCAN = 5000`; a `ponytail:` comment marks the O(n²) near-duplicate pairing with a ~5k upgrade threshold; staleness uses `created_at` as the last-relevance proxy.
- `clio-config` retention mission uses literal substring matching (`mission_match.rs`) and one mission per bank.
- `crates/clio-index/src/http.rs`: a per-call `ureq` agent (verified TLS for `https://`), no pooling, no HTTP/2; `crates/clio-index/src/http_tests.rs:173` notes a dead `https://` endpoint exercises TLS but no verified-TLS mock test exists.
- `crates.md:271` carries the only single-host sync-omission note.

---

## 2. Scope Boundaries

### In Scope
- Hygiene: index upgrade or raised ceiling, a last-relevance field, and a scheduled-cleaner decision.
- Retention: a semantic-matching spike and a learning decision.
- Transport: a pooling/HTTP-2 decision plus a verified-TLS mock test.
- Deployment docs: the single-host sync-omission sentence outside `crates.md`.

### Explicitly Out of Scope
- Rewriting hygiene scoring or retention admission policy.
- Changing the DEK/encryption model or the transport security contract.
- Adding a scheduled job runner infrastructure.
- Changing sync semantics.

### Must Not Change
- Hygiene, retention, and transport safety invariants (masking, fail-closed on bad scheme, no content in logs).
- The verified-TLS requirement for `https://` endpoints.
- Single-host deployments must still work without sync.

### Scope Expansion Rule
If work outside this scope appears necessary: stop, document the reason, request clarification or approval, and do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- Phase 100360 accepted (coverage guard).

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| Hygiene audit | Scan ceiling + O(n²) pairing | `crates/clio-hygiene/src/audit.rs` |
| Retention mission | Literal matching, one per bank | `clio-config` `mission_match` |
| Transport | Per-call ureq agent | `crates/clio-index/src/http.rs` |
| Deployment docs | User-facing docs exist | `README.md` / deployment docs |

---

## 4. Existing-System Discovery

The agent MUST re-verify the following; the facts below were confirmed at plan time.

### Required Discovery
- Confirm the hygiene scan ceiling, the O(n²) pairing, and how staleness is derived.
- Confirm retention mission matching is syntactic and one-per-bank, and whether any learning exists.
- Confirm the transport creates a per-call agent with no pooling/HTTP-2, and that no verified-TLS mock test exists.
- Locate all user-facing deployment docs and confirm the sync-omission note is only in `crates.md`.
- Identify query/index options for a scalable near-duplicate lookup on both backends.

### Discovery Output
- **Hygiene ceiling.** `DEFAULT_MAX_SCAN = 5000` with a `ponytail:` comment naming the O(n²) near-duplicate pairing and a ~5k upgrade threshold; staleness uses `created_at`, not a last-relevance field; no scheduled cleaner.
- **Retention is syntactic.** Mission matching is literal substring; one mission per bank; no auto-learning; it misfires on differently phrased repos.
- **Transport is unpooled.** `http.rs` builds a one-shot `ureq` agent per call; verified TLS works but there is no pooling/HTTP-2 and no verified-TLS mock test.
- **Docs note is buried.** Only `crates.md:271` states that a single-host deployment may omit sync.

### Repository Adaptation Rule
The agent must determine concrete implementation locations from the actual repository. The plan does not prescribe file paths or module names unless they are an externally required contract.

---

## 5. Implementation Specification

### Task 1: Hygiene Scale (G-13)

#### Intent
Make hygiene scale or document the ceiling honestly.

#### Required Capability or Behavior
- Near-duplicate pairing either uses an index/scalable lookup or the ceiling is raised with a documented upgrade path and cost.
- Staleness uses a real last-relevance signal, or the proxy is documented with its upgrade path.
- A scheduled-cleaner decision is recorded (implemented or explicitly deferred).

#### Architectural Responsibility
`clio-hygiene` owns scoring/audit; storage index support comes from `clio-store`.

#### Required Changes
1. Upgrade the near-duplicate lookup or raise the ceiling with docs.
2. Add or specify a last-relevance field. If this adds or changes a column or index in `sql/001_core.sql`, follow the Pre-existing-Data Compatibility Policy in §12 (new names, existing-row validation, version pins moved together, upgrade test).
3. Record the scheduled-cleaner decision.

#### Implementation Constraints
- Do not change the noise-scoring policy or masking.
- Keep the partial-page + `incomplete` behavior for huge banks.
- Any schema-affecting part of this task follows the same policy as Phase 100420 (see §12).

#### Expected Result
A raised ceiling or a documented upgrade path; a last-relevance decision; a cleaner decision.

### Task 2: Retention Semantic Matching (G-14)

#### Intent
Decide whether matching gets semantic and whether it learns.

#### Required Capability or Behavior
- A spike measures whether semantic matching on the mission's keep/drop examples improves hit rate over literal substring matching.
- A learning decision is recorded (implement or defer with a reason).

#### Architectural Responsibility
`clio-config` retention mission / `clio-admission` policy.

#### Required Changes
1. Run the spike on representative differently-phrased examples.
2. Record the result and the decision.

#### Expected Result
A recorded semantic-matching result and learning decision.

### Task 3: TLS Pooling and Verified-TLS Mock (G-15)

#### Intent
Decide pooling and close the TLS mock-test gap.

#### Required Capability or Behavior
- A pooling/HTTP-2 decision is recorded with its trade-off.
- A verified-TLS mock test exercises the `https://` path against a test certificate, proving the verified-TLS behavior (not just a dead endpoint).

#### Architectural Responsibility
`clio-index` transport.

#### Required Changes
1. Record the pooling decision.
2. Add the verified-TLS mock test.

#### Implementation Constraints
- Do not weaken TLS verification.
- Fail-closed on non-http/https schemes stays.

#### Expected Result
A pooling decision plus a passing verified-TLS mock test.

### Task 4: Deployment Docs Single-Host Note (G-16)

#### Intent
Put the omission rule where deployers will see it.

#### Required Capability or Behavior
- A user-facing deployment doc states plainly that single-host deployments may omit the sync runtime.

#### Architectural Responsibility
Deployment docs (`README.md` and/or a deployment guide).

#### Required Changes
1. Add the sentence outside `crates.md`.

#### Expected Result
The note exists in user-facing docs.

### Implementation Freedom
The agent may choose the index strategy, last-relevance representation, pooling approach, and doc location provided invariants and boundaries are respected.

---

## 6. Agent Execution Rules

### Allowed Actions
- Upgrade hygiene indexing/ceiling; add a last-relevance field; run the retention spike; add the TLS mock test; write docs.
- Refactor locally as needed.

### Forbidden Actions
- Change hygiene/retention scoring policy or masking.
- Weaken TLS verification; add a scheduled-job framework.
- Claim a semantic improvement without a measured spike.

### Agent Decision Boundary
The agent may decide index strategy and doc placement. The agent must request approval for changing the scanning contract, adding a scheduler dependency, or changing transport security.

### Mandatory Stop Conditions
Stop and report if a ceiling cannot be raised without a schema change with downstream impact, or if the TLS mock test cannot be built without a new dependency.

---

## 7. Security Constraints

### Required Controls
- Hygiene masking unchanged; no content in logs.
- TLS verification remains enforced for `https://`; fail closed on bad schemes.
- Retention matching must not weaken admission gates.

### Sensitive Data Rules
- Never log secrets or content; test certificates are test-only and not committed as secrets.

### Security Acceptance Conditions
- Verified-TLS mock test passes and rejects an invalid certificate.
- Hygiene/retention masking tests still pass.

---

## 8. Test and Verification Strategy

### Required Tests
- [ ] Unit tests (index lookup/ceiling, last-relevance, semantic matcher)
- [ ] Integration tests (hygiene audit at scale; retention mission matching)
- [ ] Contract tests (masking unchanged; scoring policy unchanged)
- [ ] End-to-end tests (hygiene audit on a large bank)
- [ ] Regression tests (workspace green)
- [ ] Security tests (verified TLS; masking)
- [ ] Failure-mode tests (invalid cert; huge bank partial page; differently-phrased mission)

### Required Test Scenarios

| Test ID | Scenario | Expected Result |
|---------|----------|-----------------|
| T100520-01 | Hygiene audit above the old ceiling | Completes or documents the raised ceiling |
| T100520-02 | Near-duplicate lookup at scale | Correct pairs; bounded cost |
| T100520-03 | Staleness with last-relevance | Uses the new signal (or documented proxy) |
| T100520-04 | Retention mission, differently phrased | Recorded spike outcome |
| T100520-05 | Verified TLS with a valid test cert | Succeeds |
| T100520-06 | Verified TLS with an invalid cert | Fails closed |
| T100520-07 | Deployment docs | Single-host sync note present outside `crates.md` |
| T100520-08 | Regression suite | Workspace green |

### Negative Testing
Verify invalid certs fail closed, masking still holds, huge banks still page with `incomplete`, and no scoring policy changed.

### Verification Rule
Implementation claims must be supported by measured spike results and test output.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-100520-01 | Hygiene ceiling raised or upgrade path documented | T100520-01, T100520-02 | Test output + docs |
| AC-100520-02 | Last-relevance signal added or documented | T100520-03 | Test output / note |
| AC-100520-03 | Scheduled-cleaner decision recorded | Inspection | Decision note |
| AC-100520-04 | Retention semantic spike + learning decision | T100520-04 | Spike result + decision |
| AC-100520-05 | Pooling/HTTP-2 decision + verified-TLS mock test | T100520-05, T100520-06 | Test output + decision |
| AC-100520-06 | Single-host sync note outside `crates.md` | T100520-07 | Docs diff |
| AC-100520-07 | No regression | T100520-08 | Workspace test output |

### Definition of Done
- [ ] All in-scope behavior implemented.
- [ ] All acceptance criteria pass.
- [ ] Required tests pass.
- [ ] No unauthorized changes introduced.
- [ ] Existing behavior remains intact.
- [ ] Security checks pass.
- [ ] Documentation updated.
- [ ] Evidence collected and verification completed.
- [ ] Required approval obtained (scheduler or transport-security change, if any).

### Completion Evidence
- Implementation summary
- Hygiene scale change/docs
- Retention spike result and decision
- TLS mock test output and pooling decision
- Deployment docs diff
- Known limitations

---

## 10. Failure Handling and Recovery

### Expected Failure Modes
| Failure | Detection | Recovery |
|---------|-----------|----------|
| Index upgrade too costly | Cost measurement | Raise ceiling with a documented upgrade path |
| Semantic spike inconclusive | Spike result | Defer learning with the reason recorded |
| TLS mock needs a dependency | Build | Record the decision and use the closest available test |
| Large-bank regression | T100520-01 | Keep the partial-page `incomplete` behavior |

### Rollback Strategy
Revert each ceiling change independently; docs revert is trivial. No data migration is involved.

### Partial Completion Policy
Do not claim completion if a ceiling was silently left undocumented. Each ceiling must be either raised or documented with an upgrade path; record each separately.

---

## 11. Traceability

| Parent Requirement | Implementation Task | Verification | Acceptance Criterion |
|--------------------|---------------------|--------------|-----------------------|
| §4.9.5.A hygiene (G-13) | Task 1 | T100520-01…T100520-03 | AC-100520-01…AC-100520-03 |
| §4.9.5.E / retention mission (G-14) | Task 2 | T100520-04 | AC-100520-04 |
| Provider transport TLS (G-15) | Task 3 | T100520-05, T100520-06 | AC-100520-05 |
| §4.9.5.D / §4.9.6 single-host (G-16) | Task 4 | T100520-07 | AC-100520-06 |
| Last-relevance / regression | Tasks 1, 3 | T100520-03, T100520-08 | AC-100520-02, AC-100520-07 |

Required chain:

```text
Requirement → Capability → Implementation → Test → Evidence
```

---

## 12. Phase Exit Contract

### Outputs Produced
- Hygiene scale decision/upgrade, last-relevance signal, and cleaner decision.
- Retention semantic spike result and learning decision.
- Pooling decision and verified-TLS mock test.
- Deployment-doc single-host sync note.

### Guarantees Provided to Downstream Phases
After this phase is accepted:
- Every known scale ceiling is either raised or documented with an upgrade path.
- TLS behavior has a verified mock test, not only a dead-endpoint check.

### Known Limitations
- A raised hygiene ceiling still bounds a very large bank; the upgrade path is documented.
- Semantic retention matching may remain deferred if the spike is inconclusive.

### Pre-existing-Data Compatibility Policy
Any schema-affecting change in this phase (for example a hygiene last-relevance column or index) MUST follow the four rules stated in `roadmap/phase-100420-history-temporal-invariant.md` §12: new names for new objects, existing-row validation with a named diagnostic, version pins (`crates/clio-store/src/migrate.rs:8,111` and the `sql/001_core.sql:30` seed) moved together, and an upgrade test from the previous schema.

### Downstream Prerequisites
- Any later phase touching hygiene scale, retention matching, or transport must account for these decisions.

### Final Status
PASS | PASS WITH DOCUMENTED LIMITATIONS | BLOCKED | FAILED

### Verification Sign-Off
- Implementer: [TBD]
- Verifier: [TBD]
- Human Approver: required only for a scheduler or transport-security change
- Date: [TBD]

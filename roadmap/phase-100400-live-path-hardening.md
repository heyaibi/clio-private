# Phase 100400: Live-Path Hardening — Postgres Drain, Stdio Proof, and Flake Closure

### Attribution
Rounds below record plan authorship; implementation sign-off is in §12.
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | [TBD] | [TBD] |
| Adversary | r1 | [TBD] | [TBD] |
| Remediator | r1 | [TBD] | [TBD] |
| Remedy Approver | r1 | [TBD] | [TBD] |
| Finalize | r1 | [TBD] | [TBD] |

**Remediation phase 100400 · **Effort:** ~4–5 days · **Gaps:** G-06a–G-06f · **Source:** `gap/requirement-gaps.md` §2, §3

## 1. Objective

### Goal
Close the six evidence and hardening gaps Phase 100350 left open: prove the runtime index drain on Postgres end to end, decide and execute the raw-ingest MCP wrapper, add a literal stdio store-to-retrieve test, assert the over-window backlog is surfaced rather than hidden, assert drain-failure logs carry no memory content, and fix the nanosecond-collision test flake.

### Expected Outcome
- The runtime drain and retrieve path is exercised end to end on Postgres through the dispatcher, matching the existing SQLite coverage.
- The raw-ingest MCP wrapper is either added with `tool_schema` approval or explicitly recorded as not added.
- One test drives the literal stdio transport through store → retrieve.
- A test asserts that a backlog exceeding the NFR-2 window is surfaced in coverage, not hidden.
- A test asserts drain-failure log text contains no memory content.
- The `clio-compliance` stats flake is fixed and stable across repeated runs.

### Parent Requirement
`requirement.md` — FR-3 / PR-9 (leaf queryable before maintenance), FR-17 (durable handoff), NFR-2 (bounded retrievability), FR-28 (`maintenance_status` inspectable), FR-29 / §4.9.5 (tool publishing rule). Phase 100350 known limitations (G-06a–G-06f).

### Design References
- Phase 100350 known limitations record the exact shortfalls at `roadmap/phase-100350-live-index-extraction-wiring.md:363` and §12.
- The outbox contract is backend-shared and covered by `clio-store`; the runtime drain is what lacks a Postgres run.
- `scripts/` and `clio-mcp/tests/` show the existing test harness patterns.

---

## 2. Scope Boundaries

### In Scope
- A Postgres end-to-end runtime drain run.
- The raw-ingest MCP wrapper decision and, if approved, its implementation.
- A literal stdio store-to-retrieve test.
- Backlog-surfacing assertion, drain-log content assertion, and the flake fix.

### Explicitly Out of Scope
- Changing drain scheduling, fusion, or retrieval semantics (Phase 100350).
- New providers or adapters (Phases 034/050).
- Changing NFR-2's target or the coverage report shape beyond surfacing backlog.
- Rewriting the transport or the protocol handler.

### Must Not Change
- The write response must not block on network I/O (NFR-2).
- Span verification and admission gates stay between extraction and any write.
- Existing tool semantics and schemas except the explicitly approved raw-ingest wrapper.
- Drain failures must never mark an item indexed when it is not.

### Scope Expansion Rule
If work outside this scope appears necessary: stop, document the reason, request clarification or approval, and do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- Phase 100350 accepted (runtime drain, rerank attach, raw-ingest library API).
- Phase 100360 accepted (coverage guard).
- Phase 100380 accepted (binding closure; pack-approval pattern).
- Docker Compose Postgres reachable for the Postgres run.

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| Runtime drain | Constructed and drained off the write path | `clio-mcp` `index_drain_tests` |
| Raw-ingest library API | Runs extract → verify → gated store | `clio-write` `raw_ingest_tests` |
| Stdio transport | Starts the sweeper and dispatches | `clio-mcp` `main.rs` / `protocol` |
| Postgres | Compose service up | `make compose up mac` |
| `tool_schema` approval | Recorded as an `Approval requested` subsection in the phase file; decided by the Remedy Approver step | `roadmap/phase-100170-mcp-read-retrieve-compose-surface.md` §9 precedent; `README.md:358` |

---

## 4. Existing-System Discovery

The agent MUST re-verify the following; the facts below were confirmed at plan time.

### Required Discovery
- Confirm the runtime drain is exercised only on SQLite today.
- Confirm the raw-ingest library API exists and the MCP wrapper does not.
- Confirm no test drives the literal stdio transport through store → retrieve.
- Confirm the backlog path reports over-window state (and find where to assert it).
- Confirm drain failure logging emits counts/errors and no content.
- Reproduce the `clio-compliance/src/stats_tests.rs` `unique()` collision.

### Discovery Output
- **Postgres drain unproven.** Phase 100350 known limitation (1): the drain ran end to end on SQLite only; the outbox SQL is backend-shared and covered by `clio-store`.
- **Raw-ingest wrapper deferred.** The library API shipped (`clio-write/src/raw_ingest.rs`); `README.md:358` states plainly that an MCP wrapper needs a published `tool_schema` entry and explicit approval, so it was not added. The approval mechanism is established: an `Approval requested` subsection in the phase file decided by the Remedy Approver (Phase 100170 §9 precedent, also used by Phases 100250/100260; Phase 100270's adversary enforced recording it).
- **No literal stdio test.** Phase 100350 known limitation (3): the transport test only asserts the sweeper starts; the shared dispatcher is covered directly.
- **Backlog surfaced, not prevented.** Phase 100350 known limitation (4): a sustained backlog can exceed the 2 s window and is surfaced in coverage.
- **Log content unasserted.** Phase 100350 known limitation (5): drain failures log counts/errors only, but no test scans log text for content.
- **Flake reproduced.** `crates/clio-compliance/src/stats_tests.rs:25-26` builds `unique()` from `SystemTime::now()` nanoseconds; two adjacent calls can share a nanosecond, making `bank == other`.

### Repository Adaptation Rule
The agent must determine concrete implementation locations from the actual repository. The plan does not prescribe file paths or test names unless they are an externally required contract.

---

## 5. Implementation Specification

### Task 1: Postgres End-to-End Runtime Drain (G-06a)

#### Intent
Prove the live path on the second backend.

#### Required Capability or Behavior
- With Postgres configured, a store → drain → retrieve flow through the runtime dispatcher succeeds: the item is retrievable after the drain without manual seeding.
- The run covers lexical and dense behavior consistent with the SQLite run.

#### Architectural Responsibility
`clio-mcp` runtime and tests; the outbox SQL remains owned by `clio-store`.

#### Required Changes
1. Add a Postgres-gated end-to-end drain test (skip cleanly when Postgres is unavailable, but run in the gate environment).
2. Document the run in the phase evidence.

#### Implementation Constraints
- Serialize Postgres test access per `coverage.md` §4.4.
- Do not change the outbox contract or the drain logic to make the test pass.

#### Expected Result
The runtime drain is green on Postgres and SQLite.

### Task 2: Raw-Ingest MCP Wrapper Decision (G-06b)

#### Intent
Resolve the deferred wrapper explicitly.

#### Required Capability or Behavior
- Either the wrapper is added (schema + dispatch + bound list + tests) with `tool_schema` approval, or a recorded decision not to add it explains why the library API suffices.

#### Architectural Responsibility
`clio-mcp` binding; the library API stays in `clio-write`/`clio-lib`.

#### Required Changes
1. If approved: add the schema, dispatch, bound-list entry, and tests; keep span verification and admission gates in the path.
2. If not approved: record the decision and the reason in the phase file and docs.

#### Implementation Constraints
- No gate bypass; no new egress when unconfigured.
- Do not add the tool without approval.

#### Expected Result
The wrapper exists with approval, or the no-add decision is recorded.

### Task 3: Literal Stdio Store-to-Retrieve Test (G-06c)

#### Intent
Exercise the transport a harness actually uses.

#### Required Capability or Behavior
- A test drives the literal stdio transport through a store call and a retrieve call, asserting the stored item is returned.

#### Architectural Responsibility
`clio-mcp` transport tests. `crates/clio-mcp/src/stdio.rs` exposes `serve(handler, input, output)` over `BufRead`/`Write` (newline-delimited JSON-RPC, stdout purity); `crates/clio-mcp/src/stdio_tests.rs` already covers framing.

#### Required Changes
1. Add the stdio end-to-end test. The cheapest faithful form drives `crate::stdio::serve` with an in-memory `BufRead` (for example a `Cursor` over the request lines) and a `Vec<u8>` writer, sending `store` then `retrieve` frames and asserting the retrieved item. That exercises the real framing loop and stdout purity, not the direct dispatcher. A subprocess test (`am mcp stdio`) is an acceptable stronger form if the harness supports it.
2. Assert the response lines are compact single-line JSON and that nothing but responses reaches stdout.

#### Expected Result
One passing test proves stdio store → retrieve through `serve`.

### Task 4: Backlog-Beyond-2 s Surfacing Assertion (G-06d)

#### Intent
Prove the over-window case is visible.

#### Required Capability or Behavior
- A test constructs a backlog that exceeds the NFR-2 window and asserts `maintenance_status` / coverage reports the backlog (pending/retry counts and last error), rather than hiding it.

#### Architectural Responsibility
`clio-mcp` coverage reporting and tests.

#### Required Changes
1. Add the surfacing assertion test.
2. Document the expected behavior when the outbox outpaces the drain.

#### Expected Result
The over-window case is asserted visible.

### Task 5: Drain-Failure Log-Content Assertion (G-06e)

#### Intent
Prove failures never leak memory content.

#### Required Capability or Behavior
- A test forces a drain failure with known item content and asserts the emitted log text contains counts/ids/errors but not the item content.

#### Architectural Responsibility
`clio-mcp` / `clio-index` logging and tests.

#### Required Changes
1. Add the log-content assertion test.

#### Expected Result
The assertion passes; content never appears in drain logs.

### Task 6: Nanosecond-Collision Flake Fix (G-06f)

#### Intent
Remove the pre-existing flake so the gate is trustworthy.

#### Required Capability or Behavior
- `unique()` in `clio-compliance/src/stats_tests.rs` produces distinct values across adjacent calls (monotonic counter or process-unique suffix).
- The affected test passes across many repeated runs.

#### Architectural Responsibility
`clio-compliance` test helper only.

#### Required Changes
1. Replace the time-based uniqueness with a monotonic counter or a unique suffix.
2. Run the test repeatedly to confirm stability.

#### Implementation Constraints
- Do not change production code; the fix is test-only.
- Keep the test in a path-excluded `*_tests.rs` file.

#### Expected Result
The flake is closed with repeated-run evidence.

### Implementation Freedom
The agent may choose test placement, gating mechanism, and the uniqueness strategy provided the behavior and boundaries are respected.

---

## 6. Agent Execution Rules

### Allowed Actions
- Add Postgres-gated tests, the stdio test, the surfacing and log assertions, and the flake fix.
- Add the raw-ingest wrapper with approval.

### Forbidden Actions
- Block the write path; bypass gates; add dependencies.
- Publish a new tool without approval.
- Weaken or delete existing tests; claim completion without evidence.

### Agent Decision Boundary
The agent may decide test structure and the uniqueness strategy. The agent must request approval for publishing the raw-ingest tool in the versioned `tool_schema` pack.

### Mandatory Stop Conditions
Stop and report if: Postgres cannot be reached in the gate environment; the stdio test cannot run without a real subprocess and no harness exists; or the flake cannot be closed without touching production code.

---

## 7. Security Constraints

### Required Controls
- Drain and failure logs never contain item content or secrets.
- Raw-ingest (if added) preserves span verification, admission gates, and bank scoping.
- Postgres test credentials come from the standard Compose/Makefile environment, never committed.

### Sensitive Data Rules
- Never log plaintext secrets, vectors, or source text.
- Never commit secrets.

### Security Acceptance Conditions
- Log-content assertion passes.
- An ungrounded extraction still cannot reach the store.

---

## 8. Test and Verification Strategy

### Required Tests
- [ ] Unit tests (uniqueness helper; backlog counting)
- [ ] Integration tests (Postgres drain; stdio store → retrieve)
- [ ] Contract tests (no tool semantics change; pack names unchanged unless approved)
- [ ] End-to-end tests (runtime drain on both backends)
- [ ] Regression tests (workspace green)
- [ ] Security tests (log content; gate non-bypass)
- [ ] Failure-mode tests (drain failure, backlog, embedder down)

### Required Test Scenarios

| Test ID | Scenario | Expected Result |
|---------|----------|-----------------|
| T100400-01 | Postgres: store → drain → retrieve | Item retrievable without seeding |
| T100400-02 | SQLite: store → drain → retrieve (regression) | Item retrievable |
| T100400-03 | Raw-ingest wrapper (if approved) | Grounded stored; paraphrase refused |
| T100400-04 | Literal stdio store → retrieve | Item returned over stdio |
| T100400-05 | Backlog exceeds NFR-2 window | Coverage reports backlog; not hidden |
| T100400-06 | Forced drain failure with known content | Log text has counts/errors, no content |
| T100400-07 | `unique()` repeated calls | All values distinct |
| T100400-08 | Affected stats test, many repeats | Stable pass |
| T100400-09 | Regression suite | Workspace green |

### Negative Testing
Verify the wrapper (if added) cannot bypass gates, the backlog is reported rather than swallowed, and the flake fix does not mask a real failure.

### Verification Rule
Implementation claims must be supported by actual test output, not inspection alone.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-100400-01 | Runtime drain green on Postgres | T100400-01 | Test output |
| AC-100400-02 | Raw-ingest wrapper added with approval, or no-add decision recorded | T100400-03 / decision note | Test output / decision record |
| AC-100400-03 | Literal stdio store → retrieve passes | T100400-04 | Test output |
| AC-100400-04 | Over-window backlog surfaced | T100400-05 | Test output |
| AC-100400-05 | Drain logs carry no content | T100400-06 | Test output |
| AC-100400-06 | Stats flake closed | T100400-07, T100400-08 | Repeated-run output |
| AC-100400-07 | No regression | T100400-09 | Workspace test output |

### Definition of Done
- [ ] All in-scope behavior implemented.
- [ ] All acceptance criteria pass.
- [ ] Required tests pass.
- [ ] No unauthorized changes introduced.
- [ ] Existing behavior remains intact.
- [ ] Security checks pass.
- [ ] Documentation updated.
- [ ] Evidence collected and verification completed.
- [ ] Required approval obtained (only if the wrapper is added).

### Completion Evidence
- Implementation summary
- Postgres run output
- Stdio test output
- Backlog and log-content test output
- Repeated-run flake evidence
- Known limitations

---

## 10. Failure Handling and Recovery

### Expected Failure Modes
| Failure | Detection | Recovery |
|---------|-----------|----------|
| Postgres unavailable | Test skip / connect error | Record the skip; rerun in the gate environment |
| Wrapper approval denied | Approval record | Record the no-add decision |
| Backlog hidden | T100400-05 | Fix reporting before claiming completion |
| Log content leaks | T100400-06 | Fix logging before claiming completion |
| Flake persists | T100400-08 | Revisit the uniqueness strategy |

### Rollback Strategy
Remove the new tests and revert the test helper. No production behavior changes; data is unaffected.

### Partial Completion Policy
Do not claim completion if only some of the six items are closed. Record each item's state separately; never leave a state where the live path appears proven but a backend was untested.

---

## 11. Traceability

| Parent Requirement | Implementation Task | Verification | Acceptance Criterion |
|--------------------|---------------------|--------------|-----------------------|
| FR-3 / PR-9, NFR-2 (live path) | Tasks 1, 3 | T100400-01, T100400-02, T100400-04 | AC-100400-01, AC-100400-03 |
| FR-29 / §4.9.5 (publishing rule) | Task 2 | T100400-03 | AC-100400-02 |
| FR-28 (`maintenance_status`) | Task 4 | T100400-05 | AC-100400-04 |
| Security (no content in logs) | Task 5 | T100400-06 | AC-100400-05 |
| Gate trustworthiness (G-06f) | Task 6 | T100400-07, T100400-08 | AC-100400-06 |
| Regression (workspace green) | Tasks 1–6 | T100400-09 | AC-100400-07 |

Required chain:

```text
Requirement → Capability → Implementation → Test → Evidence
```

---

## 12. Phase Exit Contract

### Outputs Produced
- Postgres end-to-end runtime drain proof.
- Raw-ingest wrapper or recorded no-add decision.
- Literal stdio store-to-retrieve test.
- Backlog-surfacing and log-content assertions.
- Closed stats flake.

### Guarantees Provided to Downstream Phases
After this phase is accepted:
- The live path is proven on both backends through the dispatcher.
- Drain observability and logging are asserted, not assumed.

### Known Limitations
- A sustained backlog can still exceed the NFR-2 window; it is surfaced, not prevented.
- The raw-ingest wrapper remains optional if approval is denied.

### Downstream Prerequisites
- Phase 100440's latency work relies on the backend-proven drain.

### Final Status
PASS | PASS WITH DOCUMENTED LIMITATIONS | BLOCKED | FAILED

### Verification Sign-Off
- Implementer: [TBD]
- Verifier: [TBD]
- Human Approver: required only if the wrapper is added
- Date: [TBD]

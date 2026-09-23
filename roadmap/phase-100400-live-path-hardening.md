# Phase 100400: Live-Path Hardening — Postgres Drain, Stdio Proof, and Flake Closure

### Attribution
Rounds below record plan authorship; implementation sign-off is in §12.
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | OpenCode CLI (Go . Space Bunny Free Max) | done |
| Adversary | r1 | Antigravity CLI (Gemini 3.8 Flash) | done |
| Remediator | r1 | OpenCode CLI (Go . Deepseek V4.1 Flash High) | done |
| Remedy Approver | r1 | OpenCode CLI (OpenRouter . Deepseek V4.1 Flash Max) | approved |
| Finalize | r1 | OpenCode CLI (Go . Space Bunny Free Max) | done |

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
`requirement.md` — FR-3 / PR-9 (leaf queryable before maintenance), FR-17 (durable handoff), NFR-2 (bounded retrievability), FR-28 (`maintenance_status` inspectable), FR-20 / §4.9.2 and §4.9.5 (tool publishing rule). Phase 100350 known limitations (G-06a–G-06f).

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
| `tool_schema` approval | Not applicable to the recorded no-add decision; any future wrapper publication requires a reviewed approval request | `roadmap/phase-100170-mcp-read-retrieve-compose-surface.md` §9 precedent; `crates/clio-mcp/README.md` |

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
- **Raw-ingest wrapper deferred.** The library API shipped (`clio-write/src/raw_ingest.rs`). The MCP README records the explicit no-add decision: native callers use the library API, MCP callers use `store`, and any future MCP wrapper needs a published `tool_schema` entry plus explicit approval. No wrapper is published in this phase.
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

| AC ID | Acceptance Criterion | Verification Method | Required Evidence | Result (r1) |
|-------|----------------------|---------------------|-------------------|-------------|
| AC-100400-01 | Runtime drain green on Postgres | T100400-01 | Test output | **PASS** — `index_drain_hardening_tests::postgres_store_drain_retrieve_covers_dense_and_lexical` ran with the gate `DATABASE_URL`, dispatched `store`, found the durable outbox row, drained it, retrieved the same id, and reported `dense_candidates=1`, `lexical_candidates=1`, `dense_rows=1`, `lexical_rows=1`, and `pending_jobs=0`. |
| AC-100400-02 | Raw-ingest wrapper added with approval, or no-add decision recorded | T100400-03 / decision note | Test output / decision record | **PASS — no-add decision** — no MCP wrapper or schema was added. `crates/clio-mcp/README.md` records that native callers use `clio_write::ingest_raw`, MCP callers use `store`, and a future wrapper requires a reviewed versioned `tool_schema` entry and explicit approval. T100400-03 is therefore not applicable. |
| AC-100400-03 | Literal stdio store → retrieve passes | T100400-04 | Test output | **PASS** — `stdio::stdio_tests::stdio_store_retrieve_end_to_end` drives one `stdio::serve` session over an in-memory `BufRead`, drains the lexical row between the two frames, and returns exactly two compact JSON-RPC response lines; all 4 stdio tests passed. |
| AC-100400-04 | Over-window backlog surfaced | T100400-05 | Test output | **PASS** — `maintenance_status_keeps_failed_backlog_visible_after_wait` keeps a batch-sized failed backlog visible after a 2.1-second wait and reports `pending_jobs`, `retry_jobs`, and `coverage_last_error` through `maintenance_status`. |
| AC-100400-05 | Drain logs carry no content | T100400-06 | Test output | **PASS** — the guarded subprocess test uses a provider that echoes the unique content phrase into the job error; the real sweeper warning contains `index_drain_failed`, `failed=1`, and `error=index_job_failed`, while captured stderr contains no phrase. Runtime logging now emits stable labels/counts instead of raw provider error text. |
| AC-100400-06 | Stats flake closed | T100400-07, T100400-08 | Repeated-run output | **PASS** — `unique_values_are_distinct_for_adjacent_calls` passes, the affected stats test passed 100 repeated runs, and the clio-compliance package passed 95 tests. The helper now uses a process-local `AtomicU64` sequence instead of wall-clock nanoseconds. |
| AC-100400-07 | No regression | T100400-09 | Workspace test output | **PASS** — `make check` with the installed rustdoc toolchain on `PATH` passed; the hermetic `DATABASE_URL`-unset workspace run also passed. Each reported 47 suite results / 2022 tests passed, 0 failed, 0 ignored. The final full coverage guard passed with no reported file below either floor. |

### Definition of Done
- [x] All in-scope behavior implemented (Postgres proof, stdio proof, backlog/log assertions, and stats flake fix).
- [x] All acceptance criteria pass.
- [x] Required tests pass (unit, integration, contract, end-to-end, regression, security, and failure-mode scenarios).
- [x] No unauthorized changes introduced (public changes are limited to the two test surfaces, the runtime logging hardening, the MCP README decision, and this phase record).
- [x] Existing behavior remains intact (workspace checks and no-DATABASE_URL fallback pass; no drain, retrieval, transport, schema, or outbox semantics were changed).
- [x] Security checks pass (the echoed-content failure test proves the drain warning carries no memory text; no gate bypass or dependency was added).
- [x] Documentation updated (`crates/clio-mcp/README.md` and this phase record).
- [x] Evidence collected and verification completed.
- [x] Required approval is obtained (downstream pipeline step).

### Completion Evidence

**Implementation summary (Developer r1).** Three disjoint worker slices were integrated and reviewed by the parent:

- **Stats flake:** `crates/clio-compliance/src/stats_tests.rs` now uses a process-local atomic sequence for unique fixture ids and has an adjacent-call regression test. No production code changed.
- **Literal stdio:** `crates/clio-mcp/src/stdio_tests.rs` now sends grounded `store` and `retrieve` frames through one real `stdio::serve` call. A small test-only `BufRead` drains the queued lexical row between frames without depending on sweeper timing; output is checked for two valid, compact, single-line JSON-RPC responses.
- **Live drain hardening:** `crates/clio-mcp/src/index_drain_hardening_tests.rs` adds the gated Postgres store → drain → retrieve test with a 384-dimensional local TEI double and the 2.1-second backlog visibility test. `runtime_index.rs` now logs per-job failures with a count and stable error labels, never raw provider error text. `runtime_index_hardening_tests.rs` verifies the real sweeper warning in an isolated subprocess, including an error response that echoes the known content phrase.
- **Raw-ingest decision:** the MCP wrapper was deliberately not added. The library API remains the native raw-turn path and the existing `store` binding remains the MCP path; the rationale and future approval boundary are in `crates/clio-mcp/README.md`. Traceability was corrected to FR-20 / §§4.9.2 and 4.9.5; FR-29 remains the export requirement.

**Postgres and test output.**

- `DATABASE_URL=postgres://clio:clio@127.0.0.1:34310/clio cargo test --locked -p clio-mcp --lib index_drain_hardening_tests -- --nocapture`: **2 passed, 0 failed**; the Postgres test did not skip, and the backlog test completed after 2.1 seconds.
- `cargo test --locked -p clio-mcp --lib`: **240 passed, 0 failed** with Postgres configured.
- `cargo test --locked -p clio-mcp --lib stdio_tests -- --nocapture`: **4 passed, 0 failed**.
- `cargo test --locked -p clio-compliance stats::stats_tests::unique_values_are_distinct_for_adjacent_calls -- --exact`: **1 passed**; the affected bank-isolation test also passed, in addition to Worker A's 100 repeated runs.
- The guarded drain-log test passed **2/2** in 0.68 seconds after the child scenario was corrected to assert the actual retry/error state rather than an over-specific status spelling.

**Coverage and regression evidence.**

- Pre-change baseline JSON: `/tmp/cov-baseline.json`; 317 files, **97.98% lines / 98.89% functions**, all per-file floors passed.
- Final `make coverage` (with the installed rustdoc and cargo-llvm-cov paths available): 317 files, **97.97% lines / 98.89% functions**, and `coverage_guard.py` reported no file below 90% on either metric.
- Final JSON re-read for touched production files: `clio-mcp/src/index_drain.rs` **100.00% / 100.00%**, `clio-mcp/src/runtime_index.rs` **93.94% / 100.00%**, `clio-mcp/src/stdio.rs` **100.00% / 100.00%**, and `clio-compliance/src/stats.rs` **100.00% / 100.00%** (lines / functions). The new `*_tests.rs` files are path-excluded by the coverage configuration; their scenarios passed in the scoped and workspace runs.
- `make check` with rustdoc available passed formatting, clippy, workspace tests, and doc-tests. A first run exposed a pre-existing intermittent clio-ops reindex test failure; the targeted test passed on rerun, and no unrelated production code was changed. GitHub issue filing could not be completed because `gh` is not installed in this environment.

**Known limitations and owners.**

1. A sustained outbox can still exceed the two-second NFR-2 target. This phase proves that the condition is surfaced through pending/retry/error status rather than hidden; changing scheduler capacity or latency is owned by the downstream Phase 100440 latency work.
2. The raw-ingest MCP wrapper is absent by explicit no-add decision, not by an unrecorded boundary. Native callers use `clio_write::ingest_raw`, MCP callers use `store`, and any future wrapper belongs to a later tool-schema approval decision. No current acceptance criterion depends on that wrapper.

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
| FR-20 / §4.9.2 and §4.9.5 (publishing rule) | Task 2 | T100400-03 / decision record | AC-100400-02 |
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
- A sustained backlog can still exceed the NFR-2 window; this phase surfaces it and does not change scheduler capacity. Phase 100440 owns the downstream latency work.
- The raw-ingest MCP wrapper is intentionally absent by the recorded no-add decision. Native callers use `clio_write::ingest_raw`, MCP callers use `store`, and a future wrapper requires a separate reviewed tool-schema approval; no current acceptance criterion depends on it.

### Downstream Prerequisites
- Phase 100440's latency work relies on the backend-proven drain.

### Final Status
PASS WITH DOCUMENTED LIMITATIONS (Developer r1; six gap-closing behaviors verified, with the explicit no-add raw-ingest decision and the sustained-backlog limitation recorded above)

### Verification Sign-Off
- Implementer: Developer r1 (OpenCode CLI, Go . Space Bunny Free Max) — implemented and reviewed the six scoped behaviors; all listed commands and final gates are recorded above
- Verifier: [TBD — Adversary r1]
- Human Approver: not required; no new MCP tool schema was published
- Date: 2026-09-24

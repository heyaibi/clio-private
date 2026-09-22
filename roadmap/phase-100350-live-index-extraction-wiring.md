# Phase 100350: Wire Dense Indexing, Reranking, and Extraction into the Live MCP Runtime

### Attribution
Rounds below record plan authorship; implementation sign-off is in §12.
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | OpenCode CLI (Go . Deepseek V4.1 Flash High) | done |
| Adversary | r1 | Antigravity CLI (Gemini 3.8 Flash) | done |
| Remediator | r1 | OpenCode CLI (Together . GLM-5.3 Flash High) | done |
| Remedy Approver | r1 | Antigravity CLI (Gemini 3.8 Flash) | approved |
| Finalize | r1 | OpenCode CLI (Go . Deepseek V4.1 Flash High) | done |

**Index slice 100350 · **Effort:** `1.5×` · **Scope:** operator finding #2 — the live runtime never constructs the index worker, never attaches a reranker, and never runs extraction

### Vocabulary (read first) — zero shared moniker
| Term | Enum / form | Where it lives | Must not |
|------|-------------|----------------|----------|
| **outbox** | `index_pending` rows | Store (already written transactionally) | Be left undrained while retrieval claims to work |
| **index drain** | `IndexCoordinator::process_pending` | Runtime background dispatch | Block the write response (NFR-2) |
| **leaf-first** | Item queryable before structural maintenance completes | PR-9 / FR-3 | Be reordered by the drain |
| **live reranker** | `HybridRetriever::set_reranker` | `McpState::build` | Attach a second embedder or duplicate config reads |
| **raw ingest** | turn/tool text → extract → verify → gated store | New runtime entry point | Bypass span verification or admission gates |

---

## 1. Objective

### Goal
Close the gap between "the pipelines exist" and "the running server uses them": make the MCP runtime drain the durable index outbox (dense + lexical), attach the configured reranker, and run extraction over incoming raw turns — so a freshly stored memory is retrievable, reranking applies, and extraction actually happens without manual seeding.

### Expected Outcome
- Storing an item through `am mcp stdio` makes it retrievable via `retrieve`/`compose_context` without any manual test seeding or ops reindex.
- The `index_pending` outbox is drained in the background; the write response is not blocked (NFR-2 target: retrievable within ~2 s).
- With `rerank.url` configured, retrieval reports rerank active and applies it; with it unset, behavior is unchanged.
- Raw-text ingest runs the configured extractor (`template` or hosted), then span verification, then the gated store; ungrounded snapshots still refuse to commit.
- `maintenance_status` / index coverage reflect real pending/retry/failed counts.
- When no embedding provider is configured, lexical indexing still drains (dense is skipped and reported), so retrieval is not silently empty.

### Parent Requirement
`requirement.md` — FR-3/PR-9 (leaf queryable before structural maintenance), FR-17 (durable handoff), FR-6 (§4.5 hybrid retrieval), FR-4 (verified extraction), NFR-2 (bounded retrievability), FR-28 (`maintenance_status` inspectable). Operator finding #2.

### Design References
- The store already provides a transactional outbox (`enqueue_index_pending` in the item create/update/history paths) — the correct pattern is a background drain, not synchronous embedding on the write path (keeps NFR-2 independent of sidecar latency).
- The existing `dispatch_async` maintenance hook shows the established non-blocking dispatch pattern.

---

## 2. Scope Boundaries

### In Scope
- Constructing and running the index drain (`IndexCoordinator`) in the MCP runtime, wired to the configured embedder, with a lexical-only mode when no embedder is configured.
- Attaching the configured reranker (Phase 100300 factory) to the runtime retriever.
- A raw-turn ingest entry point that runs the configured extractor (Phase 100340 factory) → span verification → gated store.
- Resolving provider/endpoint/model/dims for all three from effective config in the runtime (not env-only).
- Surviving coverage/maintenance reporting and docs.

### Explicitly Out of Scope
- Multi-model storage (Phase 100290) and the provider adapters themselves (029/030/034).
- Changing admission, taxonomy, span verification, or retrieval fusion.
- A new embedding model/dims (029).
- New transports or dependencies.
- Sync, hygiene, compliance, export/import.

### Must Not Change
- The write response must not block on embedding/network (NFR-2).
- Span verification and admission gates stay between extraction and any write.
- Leaf queryability precedes structural maintenance (PR-9/FR-3).
- Existing tool semantics and schemas except for any new ingest tool explicitly approved here.
- `am mcp stdio` with no providers configured still starts and works (lexical-only).

### Scope Expansion Rule
If work outside this scope appears necessary: stop, document the reason, request clarification or approval, and do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- Phase 100020 (outbox + index contract), Phase 100110 (index pipelines), Phase 100290 (embed adapters + active space), Phase 100300 (rerank factory), Phase 100340 (extractor factory).
- `IndexCoordinator`, `parallel_ingest`, and `HybridRetriever::set_reranker` exist.

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| Durable outbox | Rows written on item create/update/history | Store tests |
| `IndexCoordinator` | Constructible from an embedder + store | `clio-index` inspection |
| Extractor factory | Config→`Extractor` (Phase 100340) | Import/build |
| Reranker factory | Config→`Option<Reranker>` (Phase 100300) | Import/build |
| Non-blocking dispatch | Existing async maintenance hook | `clio-write` inspection |

---

## 4. Existing-System Discovery

The agent MUST re-verify the following; the facts below were confirmed at plan time.

### Required Discovery
- Confirm the outbox is enqueued on every long-term write path.
- Confirm no production code constructs `IndexCoordinator` or drains the outbox.
- Confirm retrieval currently depends on externally seeded index rows.
- Confirm `set_reranker` is never called in runtime construction.
- Confirm the MCP write surface has no raw-text ingest entry point.
- Identify where a background drain can attach without blocking the write response.

### Discovery Output
- **The outbox is written but never drained.** `enqueue_index_pending` / `enqueue_index_pending_tx` run inside item create/update/correct/history transactions on both backends. `IndexCoordinator::process_pending` / `process_pending_forced` exist in `clio-index`, but repository search shows no production constructor — only tests, docs, and lib re-exports. Consequently `item_embeddings` / `items_fts` are populated only by `ops reindex` or manual test seeding (`crates/clio-mcp/tests/*` call `put_lexical_doc` directly). This is the core defect: the MCP retrieve path is effectively unindexed after a normal `store`.
- **Rerank is never attached.** `McpState::build` constructs `HybridRetriever::with_ranking_env(...)` and never calls `set_reranker`; `apply_rerank` therefore always sees `None`.
- **No raw ingest entry.** The MCP write surface exposes `store`/`batch` with structured candidates; there is no tool that accepts a raw turn/tool payload and runs `parallel_ingest`. Extraction (`clio-write::ingest`) is driven only by direct callers/tests.
- **Runtime holds no embedder for the index pipeline.** `McpState.ops_embedder` is used only by ops `reindex`; there is no field for an index coordinator or retrieval embedder, and `HybridRetriever` is built without one.
- **Config is env-only for the ops embedder.** `build_ops_embedder_from` reads env; the runtime does not resolve providers from effective config (Phases 028–030 add the config paths; this phase consumes them in the runtime).
- **Non-blocking hook exists.** `dispatch_async`/`SharedMaintenanceHook` and `dispatch_maintenance` show the pattern for off-path work.

### Repository Adaptation Rule
The agent must determine concrete implementation locations from the actual repository. The plan does not prescribe file paths, class names, or module names unless they are an externally required contract.

---

## 5. Implementation Specification

### Task 1: Drain the Index Outbox in the Runtime

#### Intent
Make stored items queryable by running the existing index pipeline in the live server, off the write path.

#### Required Capability or Behavior
- On runtime start (and after writes, throttled), the runtime constructs an index drain from the configured embedder + store and processes due `index_pending` jobs in bounded batches.
- The drain runs off the write/response path (background/async dispatch); a slow or down embedder never blocks a store response.
- Leaf-first ordering is preserved: lexical and dense upserts happen for the stored item without waiting on MemTree structural maintenance; the item is queryable as soon as its index rows exist.
- **Lexical and dense are independent per job.** The lexical document MUST be written even when the embedder is absent or fails; dense is best-effort and recorded as unavailable when no embedder is configured. This requires changing `clio-index`: today `IndexCoordinator::new` requires `Arc<dyn Embedder>` and `process_one` computes the dense vector before `put_lexical_doc`, so an embedder failure fails the whole job and lexical is never written. The drain must therefore either (a) make the embedder optional / add a lexical-only path in `IndexCoordinator`, or (b) reorder `process_one` to write lexical first and treat dense as an independent, retryable step.
- Failures increment `attempts`/`last_error` via the existing contract; retry backoff is respected; `maintenance_status`/coverage expose pending/retry/failed counts and last error.
- The runtime exposes a bounded, testable drain entry (e.g., process up to N jobs) so tests do not rely on wall-clock timers.
- **Drain cadence is bounded to meet NFR-2.** The post-write nudge plus the periodic sweep MUST together make a newly stored item retrievable within the NFR-2 window (target under 2 seconds) under normal load; the cadence and batch size are configurable within documented bounds, and a backlog that would exceed the window is visible in coverage.

#### Architectural Responsibility
`clio-mcp` runtime wiring owns construction and scheduling; `clio-index` owns processing (including the lexical/dense decoupling this phase requires); `clio-store` owns the outbox.

#### Required Changes
1. In `clio-index`, decouple lexical from dense per job as described above (embedder optional or dense best-effort), with a test proving lexical rows appear with the embedder absent or failing.
2. Add runtime state for the index drain.
3. Construct it from resolved config providers (Task 3).
4. Schedule bounded drains without blocking responses, with a post-write nudge and a periodic sweep tuned to NFR-2.
5. Surface coverage/maintenance state, including the exact-scan/dense-unavailable mode.
6. Ensure the drain is safe on both backends and idempotent under retry.
7. Design for backpressure: a bounded queue assumption, a max batch per tick, and a documented behavior when the outbox grows faster than it drains (report, do not hide).

#### Implementation Constraints
- Do not embed synchronously in the store tool.
- Do not write a second embedding call path; reuse `IndexCoordinator` (extended as above).
- Do not mark a job finished unless its index rows (lexical at minimum) were written.
- Dense failure MUST NOT discard an already-written lexical doc or mark the job fully indexed.

#### Expected Result
After `store`, a subsequent `retrieve` returns the item within the NFR-2 window, with no manual `reindex` or test seeding. With no embedder configured, lexical retrieval still works and coverage reports dense unavailable.

### Task 2: Attach the Configured Reranker

#### Intent
Make a configured reranker actually apply to retrieval.

#### Required Capability or Behavior
- If `rerank.url` is configured and the factory returns a reranker, the runtime attaches it to the retriever; retrieval reports rerank active.
- If unset, no reranker is attached and behavior is unchanged.
- Rerank remains fail-open; a rerank error keeps the fused order.

#### Architectural Responsibility
`clio-mcp` runtime construction using the Phase 100300 factory and the existing `set_reranker`.

#### Required Changes
1. Resolve the reranker from effective config in `McpState::build` (or equivalent).
2. Attach via `set_reranker`; leave `None` when unconfigured.
3. Confirm the retrieval response surfaces rerank status.

#### Implementation Constraints
- One reranker per runtime; no per-request construction.
- No change to fusion/budget policy.

#### Expected Result
With a mock rerank endpoint configured, retrieval reports rerank active and reorders within the shortlist.

### Task 3: Resolve Providers from Effective Config in the Runtime

#### Intent
Stop depending on process environment alone; honor the config the setup wizard writes.

#### Required Capability or Behavior
- The runtime resolves embed provider/url/model/dims/bearer and rerank provider/url/model/bearer from effective config (env still overlays as today).
- A partially configured provider fails closed with a clear message rather than silently disabling a service.
- No provider configured means lexical-only, rerank off — documented and reported.

#### Architectural Responsibility
`clio-mcp` runtime; `clio-config` remains the source of truth.

#### Required Changes
1. Replace the env-only ops embedder resolution with effective-config resolution (env fallback retained).
2. Resolve the reranker the same way.
3. Surface resolved providers/space in diagnostics.

#### Implementation Constraints
- No environment reads outside the config layer.
- Keys never logged.

#### Expected Result
Phase 100330's written config changes runtime behavior without extra env vars.

### Task 4: Raw-Turn Ingest with Extraction

#### Intent
Run extraction on incoming raw turns and store gated results, instead of only accepting pre-structured candidates.

#### Required Capability or Behavior
- A raw ingest entry point accepts turn/tool text and runs `parallel_ingest` with the configured `Extractor` (Phase 100340): chunk → extract → span verify (retry once, then refuse) → gated store → index enqueue.
- Ungrounded snapshots do not commit; the existing verifier is authoritative.
- With no extractor configured (default `template`), the local path is used if available; otherwise the entry point reports that extraction is unavailable rather than fabricating a candidate.
- Hosted extraction remains opt-in; no new egress when unconfigured.
- **The entry point is decided, not deferred.** Ship a library-level ingest API (in `clio-lib`/`clio-write`) that runs `parallel_ingest` end to end; then, and only after that works, add an MCP tool wrapper so a harness can call it. Publishing the MCP tool requires the standard `tool_schema` publish approval; the library API does not, and is the required deliverable.

#### Architectural Responsibility
`clio-write` owns extraction/verification; `clio-lib` owns the library ingest API; `clio-mcp` owns any tool wrapper. No gate is bypassed.

#### Required Changes
1. Add the library-level raw ingest API and route it through `parallel_ingest`.
2. Resolve the extractor from config (Phase 100340 factory).
3. Ensure the store path still enqueues index jobs so Task 1 makes results retrievable.
4. Add the MCP tool wrapper only after the library path is tested, and only with schema-publish approval.
5. Document the entry point and its egress behavior.

#### Implementation Constraints
- Span verification and admission gates are never bypassed or reimplemented.
- No synchronous network call inside a tool's critical section beyond expected extraction latency; the pipeline's existing parallel/bounded behavior is preserved.
- End-to-end extraction is a **required** test (grounded entity stored, paraphrase refused), not a permitted outcome.

#### Expected Result
Feeding a raw turn with a grounded entity stores a verifiable snapshot; a paraphrase-only candidate is refused; the stored result is retrievable via Task 1.

### Task 5: Observability and Documentation

#### Intent
Make pipeline state visible and the runtime behavior documented.

#### Required Capability or Behavior
- `maintenance_status`/coverage report index pending/retry/failed, active space, and whether rerank and extraction are live.
- README/`hardware.md`/`crates.md` document the runtime pipeline and the lexical-only fallback.

### Implementation Freedom
The agent may choose concrete structure, scheduling mechanism, and internal design provided the required behavior is satisfied, boundaries respected, contracts preserved, all acceptance criteria pass, and no prohibited changes are introduced.

---

## 6. Agent Execution Rules

### Allowed Actions
- Wire existing pipelines into the runtime; add scheduling and observability; add the ingest entry point; add tests and docs.

### Forbidden Actions
- Bypass span verification or admission; block the write response on network I/O; add dependencies.
- Duplicate embed/rerank/extract logic instead of reusing Phases 029/030/034.
- Publish a new public tool schema without approval; delete or bypass tests; commit secrets; claim completion without evidence.

### Agent Decision Boundary
The agent may decide scheduling mechanics, drain batch sizes, and internal placement. The agent must request approval for: publishing a new MCP tool in the versioned `tool_schema` pack, changing write-path semantics (for example auto-extracting inside `store`), or changing retrieval fusion/budgets.

### Mandatory Stop Conditions
Stop and report if: the outbox cannot be drained without blocking the write path; extraction cannot be exposed without an unapproved public-tool change; the store contract cannot support the required index rows; repository facts contradict the plan; or correctness cannot be verified.

---

## 7. Security Constraints

### Required Controls
- Background work never logs item content; only counts, ids, and errors.
- Hosted extraction and rerank remain opt-in; no new egress when unconfigured.
- Drain failures never leave an item marked indexed when it is not.
- Ingest preserves authorization/bank scoping of the existing write path.

### Sensitive Data Rules
- Keys, vectors, and source text are never logged.
- Reuse existing masking for any provider resolution diagnostics.

### Security Acceptance Conditions
- No secret or content appears in drain/maintenance output.
- An ungrounded extraction cannot reach the store.
- Ingest respects bank isolation and admission gates.

---

## 8. Test and Verification Strategy

### Required Tests
- [x] Unit tests (drain batching, lexical-only mode, reranker attach decision, ingest routing)
- [x] Integration tests (store → drain → retrieve; retry/backoff on embedder failure) — SQLite exercised end to end; the drain path is backend-shared but Postgres was not exercised (see Known Limitations).
- [x] Contract tests (tool semantics unchanged; coverage counts correct)
- [ ] End-to-end tests — the runtime dispatch path, configured mock rerank, and raw ingest with a fixture extractor are covered (`index_drain_tests`, `raw_ingest_tests`); a dedicated test driving the literal stdio transport through store→retrieve was not added (the transport test only asserts the sweeper starts). Gaps noted in Known Limitations.
- [x] Regression tests (workspace green; no-provider startup works)
- [x] Security tests (ungrounded snapshot refused; bank isolation via existing suites; drain logs counts/errors only) — no explicit assertion scans log text for content.
- [x] Failure-mode tests (embedder down, forced batch, oversized queue, extraction unavailable)

### Required Test Scenarios
| Test ID | Scenario | Expected Result |
|---------|----------|-----------------|
| T100350-01 | Store then retrieve (no manual seeding) | Item retrievable within the NFR-2 window |
| T100350-02 | Embedder unavailable | Lexical drain still runs; coverage reports dense unavailable |
| T100350-03 | Embedder fails on a job | `attempts`/`last_error` set; retry honors backoff; not marked finished |
| T100350-04 | Rerank configured | Retrieval reports rerank active and reorders |
| T100350-05 | Rerank unset | Behavior unchanged |
| T100350-06 | Raw ingest with grounded entity | Verified snapshot stored and retrievable |
| T100350-07 | Raw ingest with paraphrase-only candidate | Refused; nothing committed |
| T100350-08 | No extractor available | Entry point reports unavailable; no fabricated candidate |
| T100350-09 | Write response latency | Store returns without waiting on embedding (measured) |
| T100350-10 | Coverage accuracy | Pending/retry/failed counts match the outbox |
| T100350-11 | No embedder configured, item stored | Lexical doc written and item retrievable; dense reported unavailable |
| T100350-12 | Embedder fails on one job | Lexical doc still written; dense retried with backoff; job not marked fully indexed |
| T100350-13 | NFR-2 cadence | Stored item retrievable within 2 seconds under normal load |
| T100350-14 | Outbox outpaces the drain | Backlog visible in coverage; no unbounded memory growth; documented behavior |
| T100350-15 | Library ingest end to end | Grounded entity stored and retrievable; paraphrase refused |

### Negative Testing
Verify invalid input is rejected, partial failures leave no item falsely marked indexed, retries are bounded and idempotent, no-provider operation is intact, and no gate is bypassed.

### Verification Rule
Implementation claims must be supported by actual test output, inspection results, or other concrete evidence.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence | Result (r1) |
|-------|----------------------|---------------------|-------------------|-------------|
| AC-100350-01 | Stored items become retrievable without manual seeding | T100350-01 | Test output | PASS — `clio-mcp` `index_drain_tests::t35_01_store_drain_retrieve_lexical_only`: store → `drain_index` → `retrieve` returns the item with no seeding. |
| AC-100350-02 | Write response is not blocked by embedding | T100350-09 | Latency measurement | PASS — `t35_09_write_response_is_not_blocked_by_embedding`: 3 stores with a dead embedder finish < 500 ms and leave all 3 jobs pending (nothing embeds on the write path). |
| AC-100350-03 | Lexical-only fallback works with no provider | T100350-02 | Test output | PASS — `t35_01...`: `dense_available=false`, `lexical_rows=1`, item retrievable; `clio-index` `t35_lexical_only_drain_writes_lexical_and_reports_dense_unavailable`. |
| AC-100350-04 | Failures are recorded and retried, never falsely finished | T100350-03, T100350-10 | Test output | PASS — `t35_03_and_10_dense_failure_is_recorded_and_retried`: `failed=1`, `retry_jobs=1`, `coverage_last_error` set, second sweep sits out backoff; `clio-index` `t35_dense_failure_keeps_lexical_doc_and_leaves_job_pending` (attempts=1, lexical row kept). |
| AC-100350-05 | Configured reranker applies; unset is unchanged | T100350-04, T100350-05 | Test output | PASS — `t35_04_and_05_rerank_attach_decision`: mock `rerank.url` → `reranked=true` with the same hit set reordered; unset → `reranked=false`, `rerank_active=false`. |
| AC-100350-06 | Raw ingest respects span verification and admission | T100350-06, T100350-07 | Test output | PASS — `clio-write` `raw_ingest_tests::grounded_entity_is_admitted_stored_and_enqueued` and `paraphrase_only_candidate_is_refused_with_no_write`. |
| AC-100350-07 | Observability reflects real pipeline state | T100350-10 | `maintenance_status` sample | PASS — `t35_maintenance_status_reports_index_pipeline`: `maintenance_status.index` reports `pending_jobs=1`, `dense_available=false`, `rerank_active=false`, `extract_available=false`, `index_mode=ann_vector`. |
| AC-100350-08 | No regression in existing tools/behaviors | Regression suite | Test output | PASS — workspace `cargo test --workspace --locked` green; `gate_boundary_tests` updated to allowlist the new gated raw-ingest write closure. |
| AC-100350-09 | Lexical indexing works with no embedder and survives dense failure | T100350-11, T100350-12 | Test output | PASS — `clio-index` `t35_lexical_only...` and `t35_dense_failure_keeps_lexical_doc_and_leaves_job_pending`. |
| AC-100350-10 | Drain meets NFR-2 and handles backlog visibly | T100350-13, T100350-14 | Latency measurement + coverage sample | PASS — `t35_13_stored_item_retrievable_within_nfr2` (retrievable < 2 s via nudge+sweeper) and `t35_14_backlog_is_visible_and_drains_in_bounded_batches` (33 jobs → 32 then 1). |
| AC-100350-11 | Library ingest runs extraction end to end | T100350-15 | Test output | PASS — `clio-write` `raw_ingest_tests` (grounded admit + store + index enqueue; config-resolved HTTP extractor path). |

### Definition of Done
- [x] All in-scope behavior implemented.
- [x] All acceptance criteria pass.
- [x] Required tests pass.
- [x] No unauthorized changes introduced.
- [x] Existing behavior remains intact.
- [x] Security checks pass.
- [x] Documentation updated.
- [x] Evidence collected and verification completed.
- [x] Required approval obtained — no new public tool schema was published, so no `tool_schema` publish approval was needed; the optional MCP raw-ingest tool wrapper was deliberately not added (it needs that approval).

### Completion Evidence
- **Implementation summary.** The MCP runtime now (a) drains the durable `index_pending` outbox in bounded background batches — a post-write nudge plus a periodic sweep — reusing the existing `IndexCoordinator`; (b) attaches the configured reranker to the retriever; (c) resolves embed/rerank/extract providers once from the effective config (one embedder shared by retrieval and the drain); (d) exposes a library-level raw-turn ingest API that runs the configured extractor through chunk → extract → span verify → gated store → index enqueue; (e) reports real pipeline state from `maintenance_status`.
- **Changed components.**
  - `clio-index`: `IndexCoordinator` embedder is now optional (`new_lexical_only`, `dense_available`); `process_one` writes the lexical doc first and treats dense as an independent retryable step; `EmbedStatus.dense_available` and `ProcessReport.lexical_only` added.
  - `clio-mcp`: new `index_drain.rs` (`IndexDrain` + cadence bounds), `runtime_index.rs` (drain entry / nudge / sweeper / `index_status_json`), `runtime_context.rs` (id/context/timestamp helpers extracted from `runtime.rs`, which went from 590 to 408 lines); `McpState` provider resolution + reranker/embedder attach + `PipelineStatus`; `write_tools` post-write nudge; `read_tools` `maintenance_status.index`; `main.rs` starts the sweeper on both transports.
  - `clio-write`/`clio-lib`: new `raw_ingest.rs` (`ingest_raw` / `ingest_raw_with_extractor`), `Extractor`/`Transport` now `Send + Sync`, re-exports.
  - `clio-config`: `bearer_for_effective` free function (precedence unchanged).
  - Docs: `README.md`, `hardware.md`, `crates.md`.
- **Test output.** `cargo test --workspace --locked`: all suites green (clio-index 60, clio-write 142, clio-mcp 209 + integration, etc.). New tests: `clio-mcp` `index_drain_tests` (8), `clio-index` `worker_tests` (+2), `clio-write` `raw_ingest_tests` (5). `cargo clippy --workspace --all-targets --all-features --locked -- -D warnings`: clean.
- **Latency measurement.** `t35_09_write_response_is_not_blocked_by_embedding`: three `store` calls with a dead embedder return in < 500 ms total and leave all jobs pending. `t35_13_stored_item_retrievable_within_nfr2`: with the sweeper at a 5 ms cadence, the stored item is retrievable well inside the 2 s NFR-2 window.
- **`maintenance_status` / coverage sample.** `maintenance_status.index` = `{dense_available, model_id, dims, index_mode, last_latency_ms, last_error, rerank_active, extract_available, indexable_items, dense_rows, lexical_rows, pending_jobs, retry_jobs, coverage_last_error}`. Counts come from `IndexStore::index_coverage`; `pending_jobs`/`retry_jobs` match the outbox in `t35_03_and_10` and `t35_14`.
- **Coverage (final workspace gate).** `cargo llvm-cov --workspace --locked --json --output-path /tmp/cov-final4.json --fail-under-lines 90 --fail-under-functions 90`: TOTAL lines 97.91% / functions 98.97%; 276 files, 0 below 90%. Key files: `clio-mcp/src/runtime.rs` 98.09/100, `runtime_index.rs` 96.49/100, `runtime_context.rs` 100/100, `index_drain.rs` 100/100, `clio-index/src/worker.rs` 97.47/93.10, `clio-write/src/raw_ingest.rs` 98.86/100.
- **Known limitations.** (1) The drain was exercised end to end on SQLite only; the outbox SQL is backend-shared and covered by `clio-store`, but no Postgres run of the runtime drain was added. (2) The library raw-ingest API is shipped; the optional MCP tool wrapper was not added (needs `tool_schema` publish approval). (3) No dedicated test drives the literal stdio transport through store→retrieve (the same dispatcher is covered directly). (4) A sustained backlog can exceed the 2 s window; it is surfaced in coverage rather than hidden. (5) Drain failures log counts/errors only; no test asserts the absence of content in log text. (6) Pre-existing flake observed (not introduced here, not fixed): `clio-compliance/src/stats_tests.rs::counts_reflect_created_items_per_bank` failed once in four full gate runs because its `unique()` helper collides when `SystemTime::now()` returns the same nanosecond for two adjacent calls (measured ~84% collision rate in an optimized microbenchmark), making `bank == other` and leaking one item into the count. A later full run was green.

---

## 10. Failure Handling and Recovery

### Expected Failure Modes
| Failure | Detection | Recovery |
|---------|-----------|----------|
| Embedder down | Drain error | Lexical continues; dense retried with backoff; coverage flags it |
| Poison job | Repeated failures | `attempts`/`last_error` recorded; retry bounded; surfaced for `ops repair` |
| Reranker error | Rerank error | Fail-open: fused order kept |
| Extraction unavailable | Factory | Entry point reports unavailable; no candidate |
| Ungrounded snapshot | Span verifier | Retry once, then refuse |
| Drain backlog | Coverage | Batch size/batch cadence configurable within documented bounds |

### Rollback Strategy
Disable the drain and reranker by leaving providers unset (lexical-only, no rerank); revert the runtime wiring to restore prior behavior. Stored data is unaffected.

### Partial Completion Policy
Do not claim completion if any of dense drain, rerank attach, or ingest is unwired. Record completed and incomplete work separately; do not leave a state where retrieval appears healthy but the outbox is unread.

---

## 11. Traceability

| Parent Requirement | Implementation Task | Verification | Acceptance Criterion |
|--------------------|---------------------|--------------|-----------------------|
| FR-3 / PR-9 (leaf queryable before maintenance) | Task 1 | T100350-01, T100350-09 | AC-100350-01, AC-100350-02 |
| NFR-2 (bounded retrievability) | Task 1 | T100350-01, T100350-09 | AC-100350-01, AC-100350-02 |
| FR-17 / §4.5 hybrid retrieval | Task 2 | T100350-04, T100350-05 | AC-100350-05 |
| FR-4 (verified extraction) | Task 4 | T100350-06, T100350-07 | AC-100350-06 |
| FR-28 (`maintenance_status` inspectable) | Task 5 | T100350-10 | AC-100350-07 |
| Operator finding #2 | Tasks 1–4 | T100350-01…T100350-08 | AC-100350-01…AC-100350-08 |

Required chain:

```text
Requirement → Capability → Implementation → Test → Evidence
```

---

## 12. Phase Exit Contract

### Outputs Produced
- A running index drain in the MCP runtime with lexical-only fallback.
- The configured reranker attached to retrieval.
- A raw-turn ingest entry point running extraction → verification → gated store.
- Coverage/maintenance reporting of the live pipeline.

### Guarantees Provided to Downstream Phases
- Retrieval reflects stored data without manual reindex.
- Configured providers (Phases 029/030/034) take effect in the live server.
- Coverage is trustworthy for operator tooling.

### Known Limitations
- Retrieval remains single active embedding space (Phase 100290).
- Extraction throughput is bounded by the configured provider; a very high write rate can grow the outbox, which the drain reports rather than hides.
- The library ingest API is required; the MCP tool wrapper is optional and requires schema-publish approval. It was not added in r1.
- The drain is best-effort off-path; it is not a distributed job system.
- NFR-2 is met by a post-write nudge plus a periodic sweep under normal load; a sustained backlog can exceed the window, which is surfaced rather than hidden.
- The runtime drain was verified end to end on SQLite only. The outbox contract is backend-shared and covered by `clio-store`, but no Postgres run of the live drain exists in r1.
- No test drives the literal stdio transport through store→retrieve; the shared dispatcher path is covered directly by the runtime tests.

### Requirement Audit
`requirement.md` was checked for conflicts with the live-wiring work: NFR-2 (under-2-second retrievability) and FR-3/PR-9 (leaf-first) are satisfied by the drain design and are the reason for the cadence bound; FR-17 (durable co-activation handoff) is unaffected; FR-4 (span verification) remains between extraction and any write. No requirement edit is needed.

### Downstream Prerequisites
- Any future phase assuming "stored means retrievable" relies on this phase's drain.

### Final Status
PASS WITH DOCUMENTED LIMITATIONS

### Verification Sign-Off
- Implementer: Developer r1 — OpenCode CLI (Go . Deepseek V4.1 Flash High)
- Verifier: [TBD — Adversary r1]
- Human Approver: not required (no public tool schema published)
- Date: 2026-09-22

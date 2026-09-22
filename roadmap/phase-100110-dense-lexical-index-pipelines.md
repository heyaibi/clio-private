# Phase 100110: Dense and Lexical Index Pipelines

### Attribution
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | OpenCode CLI (Together . GLM-5.3 Flash High) | done |
| Adversary | r1 | Antigravity CLI (Gemini 3.8 Flash) | done |
| Remediator | r1 | OpenCode CLI (Go . Deepseek V4.1 Flash High) | done |
| Remedy Approver | r1 | OpenCode CLI (Together . GLM-5.3 Flash Max) | approved |
| Finalize | r1 | OpenCode CLI (Together . GLM-5.3 Flash High) | done |

**Index slice 100110 · **Effort:** `1×` · **Scope:** `roadmap/index.md` slice 100110 (authoritative)

## 1. Objective

### Goal
Wire **embedding generation** and **lexical/BM25-style indexing** for both backends (Postgres via pgvector + FTS; SQLite via the Phase 100020 vector extension + FTS5), including **rebuild hooks**. Keep index maintenance **separable from leaf write success** (PR-9 / FR-3). Early-complete any SQLite vector integration left unfinished in slice 100020. Revisit ANN only per `roadmap/phase-100020-appendix-vector-parity.md`.

### Expected Outcome
- Every admitted leaf (and other configured indexable units) can obtain a dense embedding and a lexical index posting without blocking the write ACK beyond a bounded enqueue.
- Dual-backend behavioral contract: same item ids are searchable via dense KNN and lexical rank; product rules do not fork by backend.
- Rebuild / reindex seam usable by later ops (`reindex` in slice 100230)—this phase ships the **pipeline + internal rebuild API**, not necessarily the full doctor UX.
- Index lag is observable (dirty/pending flags or queue depth) without making leaves unreadable.
- Embedding and rerank **model inference runs as configured sidecars** (Docker Compose / remote HTTP)—not as ad-hoc host-process model loads—consistent with the project’s Profile C packaging constraint.

### Parent Requirement
`requirement.md` (current) — §0 dual backends, §4.5 adaptive retrieval prerequisites (dense + lexical), PR-9 / FR-3 write vs maintenance, NFR-2 retrievability window, FR-32 ranking_env weights foreshadow, §4.9.5.C `reindex` foreshadow. Vector ceilings: `roadmap/phase-100020-appendix-vector-parity.md`.

### Design references (non-normative)
- Hybrid search needs **both** legs before fusion; lexical catches exact IDs/codes dense misses: [Hybrid Search BM25 + Vector reference](https://www.digitalapplied.com/blog/hybrid-search-bm25-vector-reranking-reference-2026).
- Postgres: `tsvector` + pgvector is a valid first lexical leg; native `ts_rank*` is **not** classic BM25—acceptable under rank fusion; escalate to true BM25 extensions only if required: [Postgres hybrid search guide](https://learnbackend.com/guides/hybrid-search-postgres-bm25-pgvector/), [Supabase hybrid search](https://supabase.com/docs/guides/ai/hybrid-search).
- SQLite: FTS5 provides built-in `bm25()`; external-content tables need triggers; rebuild via FTS rebuild command when drift occurs.
- Keep ANN optional on SQLite per Phase 100020 appendix (exact KNN OK for first release scale).

---

## 2. Scope Boundaries

### In Scope
- Embedding provider client (HTTP to sidecar / configured endpoint) with dimension + model id recorded on vectors.
- Dense vector upsert/delete/rebuild for Postgres pgvector and SQLite vector extension.
- Lexical index: Postgres FTS (`tsvector` / GIN) and SQLite FTS5; document whether Postgres uses `ts_rank_cd` or a BM25 extension—**must be consistent in ranking_env docs**.
- Async or deferred index workers: leaf write success MUST NOT wait on embedding HTTP p95 beyond a documented bound; prefer enqueue + background apply.
- Rebuild hooks: rebuild dense, lexical, or both for bank/scope; dry-run count support desirable.
- Coverage metrics: vector row count vs indexable leaves; lexical row coverage.
- Failure isolation: embedding outage marks pending/dirty; does not roll back admitted leaf.

### Explicitly Out of Scope
- Intent gate, hybrid fusion, rerank orchestration, `compose_context` (slice 100120)—this phase may expose **primitive** `dense_search` / `lexical_search` test hooks.
- Co-activation graph updates (slice 100130).
- Full `diagnose` / `doctor` / public `reindex` CLI UX (slice 100230)—internal rebuild API is enough.
- Changing admission, taxonomy, EMA, or belief rules.
- Host-local loading of large embedding/rerank weights outside approved sidecar packaging.
- Requiring ANN parity on SQLite (see Phase 100020 appendix).

### Must Not Change
- Phase 100020 DEK encryption: embed **plaintext after decrypt in-process** or embed over approved plaintext views—never write raw DEKs into the embedding service logs.
- Leaf-first queryability (FR-3): missing vector MUST NOT hide the leaf from id fetch / MemTree leaf reads.
- Backend choice MUST NOT fork admission or encryption rules.

### Scope Expansion Rule
If work outside this scope appears necessary:
1. Stop.
2. Document the reason.
3. Request clarification or approval.
4. Do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- Phase 100020 accepted: vector storage hooks + SQLite extension loadable; exact KNN acceptable.
- Phase 100060–007 accepted recommended: leaves and MemTree summaries exist as embeddable text sources.
- Phase 100010 accepted: config for embedding endpoint, model id, dimensions; `ranking_env_*` weight knobs exist (consumed fully in slice 100120).

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| Vector tables / extension | Insert/KNN works | Phase 100020 tests + appendix |
| Item plaintext access | Decrypt for embed | Phase 100020 DEK |
| Embed HTTP sidecar | Reachable in Profile C | Health check / compose |
| Lexical extensions | FTS available both backends | Smoke SQL |

---

## 4. Existing-System Discovery

The agent MUST inspect the existing system before deciding
where or how to implement the changes.

### Required Discovery
- Phase 100020 vector API gaps (especially SQLite).
- Which text fields are indexable (snapshot JSON, gist, MemTree summaries)—define the embed/lexical corpus.
- Existing queue/worker patterns for dirty-path (Phase 100070) to reuse for index jobs.
- Compose/profile docs for embed service URL and model.
- Current `reindex` stubs if any.

### Discovery Output
Before implementation, the agent must report:

- Relevant subsystems identified
- Existing implementation approach
- Relevant contracts/interfaces
- Existing test coverage
- Architectural constraints discovered
- Assumptions confirmed
- Assumptions contradicted
- Questions requiring clarification

### Repository Adaptation Rule
The agent must determine the concrete implementation locations
from the actual repository. The plan does not prescribe file paths,
class names, module names, or directory structures unless they
are explicitly part of an externally required contract.

---

## 5. Implementation Specification

### Task 1: Embedding Generation Pipeline

#### Intent
Produce dense vectors for indexable memory units via configured sidecar.

#### Required Capability or Behavior
- Given item id / text payload → embedding vector of configured dimension.
- Record `model_id`, `dim`, `updated_at` with the vector row.
- Timeouts, retries (bounded), and structured errors when sidecar down.
- Batch embed API for rebuild efficiency.
- **No host-process model load** for Profile C; HTTP (or equivalent IPC to container) only.

#### Architectural Responsibility
Embedding client + indexing worker.

#### Required Changes
1. Provider client with config from Phase 100010.
2. Map item → embed text (document field priority: prefer gist for semantic recall; include snapshot tokens needed for exactish lexical—lexical handles exactness separately).
3. Tests with fake embed server returning deterministic vectors.

#### Implementation Constraints
- Never send DEKs to the embed service.
- Redact obvious secrets from embed text when detectable (best-effort; full hygiene is slice 100210).
- Dimension mismatch → fail closed; do not silently truncate.

#### Expected Result
Admitted leaf gets a vector row after worker runs; fake-server tests are deterministic.

### Task 2: Dense Index Upsert and Search Primitive

#### Intent
Complete dual-backend dense KNN path for retrieval’s dense leg.

#### Required Capability or Behavior
- Upsert/delete vectors on item create/update/discard paths (async OK).
- `dense_search(query_vector, domains?, limit?, bank?)` primitive for slice 100120.
- Postgres: pgvector query; HNSW/IVF optional—document index choice.
- SQLite: extension KNN; exact KNN acceptable per Phase 100020 appendix.
- Bank filters applied in-query.

#### Architectural Responsibility
Vector repository (Phase 100020) + search facade.

#### Required Changes
1. Finish any incomplete SQLite vector integration.
2. Search primitive with parity tests.
3. Coverage check helper (leaves missing vectors).

#### Implementation Constraints
- Do not block leaf write ACK on KNN index build.
- ANN revisit only if appendix upgrade path triggered.

#### Expected Result
Same fixture corpus returns overlapping top-k ids on both backends (allow documented score differences).

### Task 3: Lexical / BM25-Style Index Pipeline

#### Intent
Provide the sparse leg required by §4.5 hybrid retrieval.

#### Required Capability or Behavior
- Maintain lexical documents for indexable units.
- Postgres: `tsvector` + GIN (or approved BM25 extension); query via `tsquery` / `websearch_to_tsquery` (or extension API).
- SQLite: FTS5 with `bm25()` ranking; external-content triggers if used.
- `lexical_search(query_text, domains?, limit?, bank?)` primitive.
- Keep lexical text in sync on write/update; rebuild recovers drift.

#### Architectural Responsibility
Lexical index subsystem per backend behind one behavioral facade.

#### Required Changes
1. Schema + triggers/generated columns as appropriate.
2. Search primitive.
3. Document honesty: Postgres native FTS ≠ BM25; fusion in slice 100120 uses **ranks**.

#### Implementation Constraints
- Lexical index must include identifier-heavy fields (names, versions, error codes) that dense search misses—prefer indexing snapshot string fields / gist.
- Do not require Elasticsearch or a second datastore.

#### Expected Result
Exact-token queries hit the correct leaf when the token exists in indexed text.

### Task 4: Separable Maintenance and Rebuild Hooks

#### Intent
Index work must not block leaf readability (PR-9); rebuild must be operable.

#### Required Capability or Behavior
- On leaf write: mark index pending / enqueue job; return success when leaf durable.
- Worker applies dense + lexical updates; exposes status (pending count, last error).
- `rebuild_indexes(scope, targets=[dense|lexical|all], dry_run?)` internal API.
- Dry-run reports counts without writing.
- NFR-2: newly written leaf retrievable by id immediately; searchable via hybrid within bounded window once indexes catch up—document the target and test with fake immediate worker.

#### Architectural Responsibility
Index maintenance coordinator (may share dirty-path patterns with Phase 100070).

#### Required Changes
1. Queue or dirty flags + worker.
2. Rebuild API + tests.
3. Failure: sidecar down → pending remains; leaf still get-able.

#### Implementation Constraints
- Do not couple MemTree ancestor refresh success to vector success (independent dirty flags OK).
- Mutating rebuild confirmation UX can wait for slice 100230; internal API may require an explicit `confirm` flag already.

#### Expected Result
Kill embed sidecar mid-write → leaf exists; status shows pending; restore sidecar → rebuild clears backlog.

### Task 5: Ranking Env + Ops Seams

#### Intent
Connect Phase 100010 knobs and foreshadow slice 100120/100230.

#### Required Capability or Behavior
- Read dense/lexical-related config (model, dim, endpoint) via effective config.
- Ensure `ranking_env_get` still exposes dense/lexical **weights** (fusion used in slice 100120).
- Emit metrics/logs: embed latency, queue depth, coverage ratio (PII-safe).

#### Architectural Responsibility
Config integration + observability.

#### Required Changes
1. Wire config keys.
2. Coverage/status report structure for diagnose later.
3. Tests that misconfigured dim/endpoint fail clearly.

#### Implementation Constraints
- Secrets for embed API keys masked in config views.
- Do not implement full hybrid RRF here.

#### Expected Result
Operator can see index pipeline health without reading memory content.

### Implementation Freedom
The agent may choose the concrete implementation structure,
file locations, naming, and internal design provided that:
- The required behavior is satisfied.
- Architectural boundaries are respected.
- Existing contracts are preserved.
- All acceptance criteria pass.
- No prohibited changes are introduced.
- Rust sources stay ≤450 lines per file.

---

## 6. Agent Execution Rules

### Allowed Actions
- Inspect and modify the repository as required to implement
  the in-scope capabilities.
- Add or update implementation components where appropriate.
- Add or update tests required to verify the behavior.
- Refactor locally when necessary to implement the specified
  capability without changing unrelated behavior.
- Complete unfinished Phase 100020 SQLite vector integration in scope.

### Forbidden Actions
- Change public contracts without approval.
- Delete or bypass tests.
- Disable security controls.
- Introduce unrelated features.
- Perform unrelated broad refactoring.
- Upgrade dependencies without approval (embed client libs need approval if new).
- Commit secrets.
- Claim completion without evidence.
- Load production embedding models on the app host when Profile C requires sidecars.
- Block leaf durability on embedding success.

### Agent Decision Boundary
The agent may decide:
- Queue technology (in-process worker vs table-as-queue).
- Exact embed text assembly.
- Postgres FTS vs BM25 extension (document).
- Test organization.
- Non-breaking implementation details.

The agent must request approval for:
- Architecture changes beyond the stated scope.
- Breaking API or data-contract changes.
- Making ANN mandatory on SQLite contrary to Phase 100020 appendix.
- Security-sensitive policy decisions.
- Destructive rebuild that wipes vectors without recovery plan.
- New heavy ML dependencies on the host binary.

### Mandatory Stop Conditions
Stop and report if:
- Requirements are ambiguous.
- Repository facts contradict the plan.
- Required dependencies are missing (extension won’t load).
- Scope expansion is required.
- A destructive migration is necessary but unspecified.
- Existing architecture cannot support async index without breaking FR-3.
- Correctness cannot be verified.
- Embed sidecar contract is undefined and cannot be stubbed for tests.

---

## 7. Security Constraints

### Required Controls
- Bank filters on all search primitives.
- Embed endpoint auth via secrets config; masked in `config_get`.
- Do not log plaintext memory bodies at info level in workers—ids + hashes OK.

### Sensitive Data Rules
- Never send DEKs to embedding/rerank services.
- Never commit API keys.
- Best-effort secret redaction before embed.

### Security Acceptance Conditions
- Cross-bank dense/lexical search fails closed.
- Worker crash does not leave plaintext secrets in crash dumps beyond existing platform behavior—avoid writing secrets to vector metadata.

---

## 8. Test and Verification Strategy

### Required Tests
- [x] Unit tests (embed/http/worker/search unit modules; `SearchDomain` contract tests)
- [x] Integration tests (worker + store pipeline on SQLite; parity suites on SQLite + Postgres)
- [x] Contract tests (`clio_store::IndexStore` parity suite per backend; `RetrieveHit`/config golden tests)
- [x] End-to-end tests (leaf write → transactional enqueue → worker → dense/lexical search, T100110-01/T100110-10)
- [x] Regression tests (full pre-existing workspace suite passes unchanged: 409 tests green)
- [x] Security tests (cross-bank fail closed, embed API key masked, only scrubbed text leaves the process)
- [x] Failure-mode tests (sidecar down + backoff, dim mismatch, slow sidecar, exhausted retries, orphan cleanup)

### Required Test Scenarios

| Test ID | Scenario | Expected Result |
|---------|----------|-----------------|
| T100110-01 | Leaf write with worker | PASS — `worker_tests::t01`: transactional enqueue on `create_memory_item`; `process_pending` produces the vector row + lexical row; leaf `get_memory_item` works immediately |
| T100110-02 | Embed sidecar down | PASS — `worker_tests::t02`: leaf write succeeds, job stays pending with structured `last_error`, 30 s backoff blocks crash-looping, rebuild after restore clears the backlog |
| T100110-03 | Dense search fixture | PASS — expected id first in top-k on both backends (`index_store_tests`, `worker_tests::t01`) |
| T100110-04 | Lexical exact token | PASS — `ECONNRESET` ranks the carrying leaf first on both backends |
| T100110-05 | Dual-backend parity sample | PASS — `sqlite_index_contract` + `postgres_index_contract` run the identical suite with overlapping results |
| T100110-06 | Rebuild dry_run | PASS — counts only; dense/lexical rows unchanged (verified via coverage before/after) |
| T100110-07 | Rebuild apply | PASS — coverage restored after intentional wipe of derived rows |
| T100110-08 | Dimension mismatch | PASS — coordinator construction rejects non-384 dims; response dim drift fails the job with a clear message; no vector rows written |
| T100110-09 | Discard/invalidate item | PASS — invalidated items drop out of search (current-belief filter); `delete_item` removes vector/lexical/outbox rows |
| T100110-10 | Bank isolation | PASS — cross-bank dense/lexical searches empty; empty bank → `MissingBank` |
| T100110-11 | Write ACK not blocked by slow embed | PASS — `worker_tests::t11`: create with a 700 ms-delay sidecar returns <500 ms; worker eats the timeout |
| T100110-12 | SQLite extension path | PASS — vec0 exact KNN via widening fetch; asserted in `sqlite_index_contract` |

### Negative Testing
Verify that:
- Invalid queries handled.
- Unauthorized bank access blocked.
- Partial worker failures retry safely / idempotent upsert.
- Duplicate rebuild is safe.
- Existing MemTree/admission behavior intact.
- Failure does not delete admitted leaves.

### Verification Rule
Implementation claims must be supported by actual test output,
inspection results, or other concrete evidence.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-100110-01 | Embedding pipeline via sidecar/stub | T100110-01, T100110-02, T100110-08 | PASS — `TeiEmbedder` (TEI-compatible `POST /embed`, `GET /health`) over a minimal std-only HTTP/1.1 client (`clio-index/src/http.rs`); `embed.url` / `embed.model` / `embed.dims` config keys + `EMBED_URL` / `EMBED_MODEL` env wiring; bearer auth via `credentials.embed_api_key` (masked in config views). Tests: `worker_tests::t01/t02/t08/t11`, fake deterministic TEI server, dim-mismatch fail-closed at coordinator construction and per response. |
| AC-100110-02 | Dense search both backends | T100110-03, T100110-05, T100110-12 | PASS — `IndexStore::dense_search` parity suite passes on SQLite (`sqlite_index_contract`) and Postgres/pgvector (`postgres_index_contract`); bank + domain + current-belief filters in-query; widening fetch keeps top-k correct under filters. |
| AC-100110-03 | Lexical search both backends | T100110-04, T100110-05 | PASS — `IndexStore::lexical_search`: SQLite FTS5 `bm25()` (rank negated so higher=better), Postgres `websearch_to_tsquery('simple', …)` + `ts_rank_cd` (higher=better). Exact-token fixture (`ECONNRESET`) ranks the right leaf first on both backends. |
| AC-100110-04 | Index separable from leaf write success | T100110-01, T100110-02, T100110-11 | PASS — leaf writes durably enqueue a job row inside the item's transaction (`index_pending` outbox; PR-9). Write ACK measured <1000 ms with a 700 ms-delay embed sidecar (T100110-11); sidecar outage leaves the leaf readable and the job pending with 30 s backoff (T100110-02). |
| AC-100110-05 | Rebuild hooks | T100110-06, T100110-07 | PASS — `IndexCoordinator::rebuild_indexes(bank?, targets, dry_run, confirm)`: dry-run reports counts with zero writes (T100110-06); confirmed apply sweeps visible indexable items (idempotent upsert) and restores coverage after an intentional wipe (T100110-07); orphans (derived rows for vanished items) removed. Mutating runs without `confirm=true` fail closed. |
| AC-100110-06 | Bank isolation | T100110-10 | PASS — all search primitives require a bank and fail closed on empty (`MissingBank`); cross-bank dense + lexical searches return nothing (`postgres_index_contract` / `sqlite_index_contract`, plus end-to-end `t10_bank_isolation_end_to_end`). |
| AC-100110-07 | Phase 100020 appendix ceilings respected | Inspection | Statement: SQLite dense search stays **exact KNN** over sqlite-vec `vec0` with a widening in-bank fetch; no ANN was added and no ANN is mandatory on SQLite. Vector/lexical rows are derived state and safe to wipe + rebuild. |

### Definition of Done
- [x] All in-scope behavior is implemented.
- [x] All acceptance criteria pass.
- [x] Required tests pass (workspace: 409 tests, 0 failures; parity suites run per backend).
- [x] No unauthorized changes were introduced (no new dependencies; new crate `clio-index` + `clio-store::IndexStore` contract are in-scope additions).
- [x] Existing behavior remains intact (all pre-existing suites pass unchanged).
- [x] Security checks pass (bank filters on both legs; secrets masked in config views; only scrubbed text leaves the process; DEKs never sent to the sidecar; no plaintext at info level in workers — ids/errors only).
- [x] Documentation is updated where required (`crates.md` clio-index row; phase evidence below; lexical-honesty notes in module docs).
- [x] Evidence is collected.
- [x] Verification is completed (`make coverage` exit 0: aggregate 98.50% lines / 98.77% functions, every reported file ≥90% on both gated metrics).
- [x] Required approval is obtained (no approval-gated actions were taken: no new dependencies, no contract removals, no destructive migrations — schema change is an additive `CREATE TABLE IF NOT EXISTS index_pending`).

### Completion Evidence
- Implementation summary: new crate `clio-index` (`embed.rs` Embedder trait + TEI adapter + text assembly + redaction + dim gate; `http.rs` std-only HTTP/1.1 JSON client with bounded timeouts + chunked decode; `worker.rs` IndexCoordinator outbox worker + rebuild sweeps + status; `report.rs` report shapes; `search.rs` primitive facades). `clio-store` gains the `IndexStore` trait (queue + lexical + scoped search + coverage + orphan cleanup) implemented by both backends, plus a transactional outbox (`index_pending`, schema v6) wired into `create_memory_item`, `update_memory_item`, and `commit_triple_add`; `delete_item` removes vector/lexical/outbox rows. `clio-types::SearchDomain` maps the §4.9.4 domain vocabulary to SQL predicates. `clio-config` gains `embed.url` / `embed.model` / `embed.dims` / `credentials.embed_api_key` (allowlisted, masked; `EMBED_URL` / `EMBED_MODEL` env wiring).
- Embed model id + dim + endpoint config keys: `embed.model` default `BAAI/bge-small-en-v1.5`, `embed.dims` default `384` (schema-pinned via `EMBEDDING_DIMS`; mismatches fail closed), `embed.url` default empty (TEI-compatible sidecar base URL, e.g. `http://127.0.0.1:34311`), env `EMBED_URL` / `EMBED_MODEL`, bearer secret `credentials.embed_api_key` (masked in `config_get`).
- Lexical strategy per backend: **Postgres** — native FTS: `items.content_tsv = to_tsvector('simple', text)` + GIN, queried with `websearch_to_tsquery('simple', …)` and ranked by `ts_rank_cd`. This is **not** BM25; documented honesty note in `postgres_index.rs` — downstream fusion (slice 100120) must combine legs by **rank** (RRF or equivalent), never by raw score mixing. **SQLite** — FTS5 `items_fts` (standalone table, `porter` tokenizer, `item_id`/`bank_id` UNINDEXED) queried with escaped quoted tokens joined by OR, ranked by built-in `bm25()` (negated so higher = better). No external datastore, no Elasticsearch.
- SQLite vector extension name/version: `sqlite-vec` crate 0.1 (`vec0` virtual tables); version asserted live via `vec_version()` at open; exact KNN via `knn_in_bank` widening fetch (phase-100020 appendix ceiling accepted).
- Test execution output: `cargo test --workspace --locked` → 409 passed, 0 failed (includes new suites: `clio-store::index_store_tests` SQLite + Postgres parity; `clio-index` 38 tests: T100110-01, T100110-02, T100110-06, T100110-07, T100110-08, T100110-10, T100110-11 scenarios, fake deterministic TEI server, HTTP client error paths). `make coverage` exit 0 → TOTAL 98.50% lines / 98.77% functions; **no reported file below 90% on either gated metric**.
- Known scale ceiling statement (link appendix): per `roadmap/phase-100020-appendix-vector-parity.md`, SQLite dense retrieval remains **exact KNN** (vec0 brute force with widening in-bank fetch — comfortable for tens to low hundreds of thousands of vectors); Postgres uses pgvector HNSW cosine index (schema v2, unchanged). Re-embedding on `update` rides the outbox; stale-model vectors are refreshed by rebuild sweeps (idempotent upsert).
- Verification report: `make check` (fmt + clippy `-D warnings` + tests with `--workspace`) clean; `make coverage` (aggregate + per-file ≥90% lines/functions) exit 0; baseline was verified green before any change (96.00% lines / 99.10% functions, no per-file violations).

---

## 10. Failure Handling and Recovery

### Expected Failure Modes

| Failure | Detection | Recovery |
|---------|-----------|----------|
| Embed timeout | Client error | Retry with backoff; leave pending |
| Extension missing | Startup check | Fail fast with doctor-friendly message |
| Lexical drift | Coverage verify | `rebuild_indexes` |
| Dim change | Model config change | Full dense rebuild required; detect mismatch |

### Rollback Strategy
Revert code; rebuild indexes from source items. Vector/lexical tables are derived—safe to wipe and rebuild. Do not wipe item store.

### Partial Completion Policy
If only part of the phase is complete:
- Do not claim full completion.
- Record completed and incomplete work separately.
- Document remaining work.
- Do not leave undocumented broken state.

---

## 11. Traceability

| Parent Requirement | Implementation Task | Verification | Acceptance Criterion |
|--------------------|---------------------|--------------|-----------------------|
| §0 / §4.5 dense+lexical legs | Tasks 1–3 | T100110-03–T100110-05 | AC-100110-02, AC-100110-03 |
| PR-9 / FR-3 separable maintenance | Task 4 | T100110-01, T100110-02, T100110-11 | AC-100110-04 |
| Phase 100020 vector parity | Tasks 2, 5 | T100110-12 | AC-100110-07 |
| §4.9.5.C reindex foreshadow | Task 4 | T100110-06, T100110-07 | AC-100110-05 |
| Bank isolation | Task 2–3 | T100110-10 | AC-100110-06 |
| Sidecar packaging | Task 1 | T100110-01, T100110-02 | AC-100110-01 |

Required chain:

```text
Requirement → Capability → Implementation → Test → Evidence
```

Every acceptance criterion must be traceable.

---

## 12. Phase Exit Contract

### Outputs Produced
- Embedding generation pipeline (sidecar client).
- Dense + lexical indexes on both backends.
- Search primitives for slice 100120 fusion.
- Async maintenance + rebuild hooks.
- Coverage/status signals for later ops.

### Guarantees Provided to Downstream Phases
After this phase is accepted:
- Slice 100120 can assume dense and lexical candidate lists exist.
- Slice 100230 can wrap rebuild in `reindex` UX.
- Leaf writes remain fast when index workers lag.

### Known Limitations
- Hybrid RRF + rerank + intent gate not implemented.
- ANN on SQLite may remain exact KNN.
- Public doctor/reindex CLI may be incomplete.

### Downstream Prerequisites
- Slice 100120 MUST fuse by **rank** (RRF or documented equivalent), not naïve score averaging across dense cosine and BM25/`ts_rank`.
- Slice 100120 MUST honor domain filters and bi-temporal args without requiring index rebuild.

### Final Status
PASS WITH DOCUMENTED LIMITATIONS
(limitations are scope boundaries, not defects: no hybrid RRF/rerank/intent gate — slice 100120;
Postgres lexical leg is `ts_rank_cd`, not BM25 — fusion must use ranks; SQLite stays exact KNN;
no public `reindex` CLI yet — internal rebuild API shipped)

### Verification Sign-Off
- Implementer: Developer r1 — OpenCode CLI (Together . GLM-5.3 Flash High)
- Verifier: [pending — Adversary r1]
- Human Approver: [pending]
- Date: 2026-09-18

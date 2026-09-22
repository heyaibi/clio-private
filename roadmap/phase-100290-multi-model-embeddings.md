# Phase 100290: Multi-Model Embedding Storage and Embed Provider Adapters

### Attribution
Rounds below record plan authorship; implementation sign-off is in §12.
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | OpenCode CLI (Go . Deepseek V4.1 Flash High) | done |
| Adversary | r1 | OpenCode CLI (OpenRouter . Deepseek V4.1 Flash Max) | done |
| Remediator | r1 | OpenCode CLI (Go . Deepseek V4.1 Flash High) | done |
| Remedy Approver | r1 | OpenCode CLI (OpenRouter . Deepseek V4.1 Flash Max) | approved |
| Finalize | r1 | OpenCode CLI (Go . Deepseek V4.1 Flash High) | done |

**Index slice 100290 · **Effort:** `1.5×` · **Scope:** operator finding #1 (multiple embedding models/providers) plus the embed half of `gap/zero-deps.md`

### Vocabulary (read first) — zero shared moniker
| Term | Enum / form | Where it lives | Must not |
|------|-------------|----------------|----------|
| **active embedding space** | `(model_id, dims)` | `schema_settings` + effective config | Be a per-row free choice; exactly one space is active per deployment |
| **space switch** | Replacing the active space | Store bootstrap | Silently mix two models' vectors in one index |
| **derived dense vectors** | `item_embeddings` rows | Store | Be treated as source of truth; they are rebuildable from item content |
| **`embed.dims`** | Configured output width | Effective config | Be inferred silently; required for non-default models |
| **timeout/degrade policy** | Index vs exact scan above 2000 dims | Store | Pretend an HNSW index exists above the pgvector index limit |

---

## 1. Objective

### Goal
Remove the hardcoded 384-dimension embedding assumption so the deployment can be configured to use a different embedding model or provider, with the current `BAAI/bge-small-en-v1.5` / 384 default unchanged, and ship the TEI + OpenAI-compatible embed adapters on the Phase 100280 transport. Supported widths are bounded by the storage engine: Postgres/pgvector stores up to 16000 dimensions and can serve an ANN index up to 2000 (`vector`) or 4000 (`halfvec`); wider vectors use exact search. Exactly one embedding space is active at a time; switching model or dimensions rebuilds the derived dense index.

### Expected Outcome
- Configuring a different `embed.model` / `embed.dims` (for example OpenAI `text-embedding-3-small` at 1536, or a local 768-dim model) no longer fails with a dimension mismatch: the store adopts the configured width.
- `embed.provider = "tei"` and `"openai"` both produce vectors; count and dimension mismatches fail closed.
- Switching the active space purges and rebuilds only derived dense vectors; item content, triples, beliefs, persona, and history are untouched.
- Dense retrieval, ops reindex, and `diagnose`/coverage report the active model and dimensions.
- An existing 384-dim database opens unchanged with no rebuild required.

### Parent Requirement
`requirement.md` — §4.9.5.E/FR-32 (config), FR-26/PR-4 (no silent truncation), NFR-5 (determinism), §2 (storage independence). Operator finding: multiple embedding models/providers must be supported. Gap source: `gap/zero-deps.md` embed portion.

### Design References (validated)
- **pgvector dimension rules:** a `vector(n)` column enforces its width at the type level and cannot be altered in place; an unconstrained `vector` column **cannot be indexed**; the HNSW/IVFFlat index ceiling is 2000 dimensions for `vector` and 4000 for `halfvec`, while storage holds up to 16000 (`docs.rs/pgvector`, Supabase HNSW docs, pgvector PR #849, and a 2026 pgvector source analysis). For widths above 2000, the working pattern is an **expression index** on a `vector(N)` column, `USING hnsw ((embedding::halfvec(N)) halfvec_cosine_ops)`, with the **same cast repeated in every query** or the planner silently falls back to a sequential scan; `halfvec` requires pgvector ≥ 0.7.0.
- **Never mix models in one index:** vectors from different embedding models are not comparable, so the model identity must be part of the space and queries must run only in the active space.
- **sqlite-vec `vec0`** requires `float[N]` at table creation, so the same resolved-width approach applies to SQLite (exact KNN there regardless).

---

## 2. Scope Boundaries

### In Scope
- An active embedding space `(model_id, dims)` resolved from effective config and recorded in `schema_settings`.
- Dimension-agnostic vector storage: parameterized DDL for the vector table and its index, a purge-and-rebuild on space change, and an index-availability policy by width.
- Updating the dimension gate (`IndexCoordinator`, `rebuild`, coverage/diagnose) to compare against the active space instead of the constant.
- TEI + OpenAI-compatible embedding adapters selected by `embed.provider`, with dims from config.
- Ops embedder factory resolving provider/model/dims/bearer from effective config.
- Docs: how to switch models, what gets rebuilt, and the default remaining 384.

### Explicitly Out of Scope
- Multiple **coexisting** spaces (one active space only; operator decision).
- Rerank adapters (Phase 100300) and runtime write-path wiring (Phase 100350).
- Hosted extraction (Phase 100340).
- Changing chunking, retrieval fusion, or admission.
- Automatic discovery of a model's output dimension by probing the endpoint (dims are configured; a probe may be an implementation convenience but must not be the source of truth).

### Must Not Change
- Default `embed.model = "BAAI/bge-small-en-v1.5"`, `embed.dims = 384`; behavior with no provider configured.
- No silent truncation or padding of vectors (FR-26/PR-4): a width mismatch is an error.
- Item content and all non-vector tables are never touched by a space switch.
- The `IndexStore`/`Store` public signatures unless the plan explicitly says so; prefer validating query length against the active space over changing every caller.

### Scope Expansion Rule
If work outside this scope appears necessary: stop, document the reason, request clarification or approval, and do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- Phase 100280 accepted: HTTPS transport and provider config/credentials/env plumbing.
- Phase 100020 accepted: both backends and the vector tables exist.
- Phase 100110 accepted: dense/lexical index pipelines and rebuild hooks exist.

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| Active-space record | `schema_settings` keys `embedding_model`/`embedding_dim` usable | Existing rows present |
| Parameterized DDL | Store can build vector DDL for resolved dims | Migration test on both backends |
| `IndexCoordinator` gate | Compares embedder dims to a runtime value | Unit test |
| Phase 100280 transport | `post_json` reachable | Import/build |

---

## 4. Existing-System Discovery

The agent MUST re-verify the following; the facts below were confirmed at plan time.

### Required Discovery
- Confirm every use of `EMBEDDING_DIMS` and `EmbeddingDims` and classify each as default-only or hard pin.
- Inspect the vector DDL and any settings rows that record the dimension.
- Inspect `IndexCoordinator::new` (dims gate), `rebuild.rs`, coverage, and `diagnose`.
- Inspect `IndexStore::knn` / `Store::knn` and how the query vector length is validated.
- Confirm how `schema_version` is bumped and how existing databases converge.

### Discovery Output
- **Constant is a pin, not just a default.** `clio-store/src/model.rs` defines `pub const EMBEDDING_DIMS: usize = 384` and `EmbeddingDims`; `IndexCoordinator::new` (`clio-index/src/worker.rs`) fails closed when `embedder.dims() != EMBEDDING_DIMS`. `clio-mcp/src/runtime.rs::build_ops_embedder_from` constructs `TeiEmbedder::new(url, model, EMBEDDING_DIMS, None)`. Many tests use `EMBEDDING_DIMS` as a fixture width.
- **Storage pins 384 in three places.** `sql/002_vectors_postgres.sql`: `vector(384)` and `CHECK (dims = 384)` plus an HNSW index on the column. `sql/002_vectors_sqlite.sql`: `vec0` with `float[384]`. `sql/001_core.sql`: `schema_settings` rows `embedding_dim='384'` and `embedding_model='BAAI/bge-small-en-v1.5'` (the model row uses `DO NOTHING`; the dim row too).
- **DDL is static and embedded.** `clio-store/src/migrate.rs` includes the SQL files via `include_str!` and asserts `SQL_VECTORS_POSTGRES.contains("vector")` / `SQL_VECTORS_SQLITE.contains("vec0")`. Parameterizing the vector width therefore requires generating the vector-table DDL in Rust (or a second, width-specific creation step) while keeping the non-vector portions static.
- **Vector rows carry `model_id` and `dims`.** `VectorSlot { item_id, bank_id, model_id, embedding }` and `item_embeddings` has `model_id` and `dims` columns. These are the hooks for space identity, but nothing currently filters by them in `knn`.
- **`knn` is bank-scoped only.** `Store::knn(&self, bank_id, query, k)` validates nothing about model or width; the query length is implied by the caller. With one active space, the store can validate `query.len() == active_dims` and treat a mismatch as fail-closed.
- **`EMBEDDING_DIMS` is used as a fixture width in tests.** Changing the constant's meaning would ripple; the plan instead keeps it as the *default* and introduces a runtime active width.
- **Existing database compatibility.** A database at 384 with the configured default must open with no purge and no rebuild; the settings rows already say 384.

### Repository Adaptation Rule
The agent must determine concrete implementation locations from the actual repository. The plan does not prescribe file paths, class names, or module names unless they are an externally required contract (the SQL dialect behavior and `vec0`/pgvector constraints are external).

---

## 5. Implementation Specification

### Task 1: Active Embedding Space Resolution

#### Intent
Make the embedding width and model a runtime value owned by the store and config, not a compile-time constant.

#### Required Capability or Behavior
- Effective config supplies the desired `(model_id, dims)` from `embed.model` and `embed.dims`; both must be non-empty/positive or the store fails closed with a clear message.
- On open, the store compares the configured space to the recorded `schema_settings` space:
  - equal → open normally, no change;
  - different → perform a space switch (Task 2);
  - absent (fresh database) → record the configured space.
- The resolved space is exposed to the index layer so the dimension gate compares against it rather than a constant.

#### Architectural Responsibility
`clio-store` owns the space record and switch; `clio-config` supplies the configured values; `clio-index` consumes the resolved space. No index layer reads the process environment.

#### Required Changes
1. Add a resolved-space type/accessor (model id + dims) available from the store/config.
2. Read and write the `schema_settings` rows for model and dimension; treat them as the recorded active space.
3. Replace the constant comparison in the index gate with the resolved space.
4. Keep `EMBEDDING_DIMS` as the documented default for tests and as the value matching the default config.

#### Implementation Constraints
- No silent width coercion; a mismatch between configured and stored space is an explicit switch, never a partial mix.
- No environment reads outside the config layer.

#### Expected Result
Opening a 384 database with the default config is a no-op; opening with a 1536 config triggers a switch and records the new space.

### Task 2: Dimension-Agnostic Vector Storage and Space Switch

#### Intent
Let the storage layer adopt any embedding width, rebuilding derived vectors only when the active space changes.

#### Required Capability or Behavior
- The vector table is created for the resolved width:
  - Postgres: `embedding vector(N)` with an HNSW cosine index when `N ≤ 2000`. For `2000 < N ≤ 4000`, keep the `vector(N)` column and create an **expression index** `USING hnsw ((embedding::halfvec(N)) halfvec_cosine_ops)`; the KNN SQL MUST repeat the identical cast (`ORDER BY embedding::halfvec(N) <=> $1::halfvec(N)`) or the index is not used and the query becomes a sequential scan. `halfvec` requires pgvector ≥ 0.7.0, asserted at bootstrap.
  - Above 4000 dimensions (up to the 16000 storage ceiling), store `vector(N)` and serve exact KNN with no ANN index; report this mode in `diagnose`.
  - Never create an index that exceeds the engine limit; never store above 16000 dimensions (fail closed with a clear message).
  - SQLite: `vec0` with `float[N]` (exact KNN as today).
- On a space switch: require an explicit confirmation (or an opt-in flag) before dropping the old space, unless the new space is built first or the database has no derived rows yet; then purge/rebuild the derived dense vectors (drop and recreate the vector table with the new width), record the new space, and leave the dense-coverage gap (`dense_rows` below `indexable_items`) plus the `embedding_space_switch` log as the rebuild signal. Log the switch (old → new) as an operational event with no content.
- The per-row `dims`/`model_id` columns are retained but must equal the active space; a row that does not match is an error, not silently kept.
- Existing 384 data requires no purge when the configured space is 384.

#### Architectural Responsibility
`clio-store` migration/bootstrap and vector CRUD; `clio-index` rebuild performs the re-embedding and owns the query-side cast.

#### Required Changes
1. Generate the vector-table DDL for the resolved width at bootstrap (parameterized in code) while keeping FTS/triggers/lineage DDL static; update the `migrate.rs` assertions accordingly.
2. Remove `CHECK (dims = 384)`; keep `dims` and `model_id` and validate against the active space on write/read.
3. Implement the switch (confirmation gate, drop/recreate vector table, record settings, surface the cleared dense coverage as the rebuild signal) with a clear log and a documented consequence.
4. Implement the index-availability policy by width, including the halfvec expression index and the matching query cast, with a clear `diagnose` message for each mode (ANN vector / ANN halfvec / exact scan).
5. Assert the pgvector extension version at bootstrap when halfvec is required; fail closed with guidance if the installed version is older.
6. Bump `schema_version` and converge existing databases (no-op at 384).

#### Implementation Constraints
- A space switch MUST NOT touch item content, triples, beliefs, persona, history, hygiene, audit, or sync tables. Only `item_embeddings` (and its index) is affected.
- A space switch is destructive to derived data. Because the trigger is a config edit (`embed.dims`/`embed.model`) and vectors are only regenerable if a rebuild then runs, the switch MUST require an explicit confirmation or an opt-in flag, and MUST be logged and surfaced by `diagnose`/coverage. "Regenerable" is not sufficient justification for silently wiping the active index.
- A query whose length does not equal the active width fails closed.

#### Expected Result
After configuring 1536 dims and confirming, then running reindex, KNN returns hits from the 1536 space (plain `vector` index). After configuring 3072 dims, the halfvec expression index is used and the query plan shows an index scan, not a sequential scan; configuring 384 again switches back with another rebuild.

### Task 3: Embed Provider Adapters

#### Intent
Produce vectors from TEI or an OpenAI-compatible endpoint, at the configured width.

#### Required Capability or Behavior
- `embed.provider = "tei"`: `POST {url}/embed` with `{"inputs":[...]}`; response is a bare array of width-length arrays, 1:1 with input order.
- `embed.provider = "openai"`: `POST {url}/v1/embeddings` with `{"input":[...], "model":<embed.model>, "dimensions":<embed.dims>}`; response parsed from `data[]` ordered by `index`, each `embedding` a width-length array.
- Unknown provider fails closed with the allowed values.
- Reuse the existing retry classification, redaction, and fail-closed count/dimension checks; no truncation or padding.

#### Architectural Responsibility
`clio-index` owns embed adapters; they reuse the Phase 100280 transport and the resolved active width.

#### Required Changes
1. Add the OpenAI-compatible adapter and select it by `embed.provider`.
2. Keep TEI behavior byte-shape compatible.
3. Parse by provider order, not arrival order.
4. Validate count and width against the resolved space.

#### Implementation Constraints
- No second HTTP client; no async.
- A wrong-width or wrong-count response is an error.

#### Expected Result
A mocked OpenAI response yields vectors identical in order and width to the TEI path for the same input at the same width.

### Task 4: Ops Embedder Factory and Reporting

#### Intent
Make the configured embedder actually constructible and its space visible in operator output.

#### Required Capability or Behavior
- The ops embedder factory resolves provider, url, model, dims, and bearer from effective config (env fallback retained) instead of reading only `EMBED_URL`/`EMBED_MODEL` and passing `None`.
- `diagnose`/coverage report the active model, dims, and whether an ANN index is in effect.
- A missing url/model/dims for a configured provider fails closed.

#### Architectural Responsibility
`clio-mcp` runtime ops wiring and `clio-ops`/`clio-index` reporting.

#### Required Changes
1. Refactor the factory to take resolved config values with the injectable seam preserved.
2. Surface the active space in diagnostics/coverage.
3. Preserve behavior when no provider is configured.

#### Implementation Constraints
- One embedder per runtime; no per-request construction.
- No dense write-path wiring here (Phase 100350).

#### Expected Result
`am ops reindex --target dense` embeds at the configured width through the configured provider, and `diagnose` shows the active space.

### Task 5: Documentation

#### Intent
Document model switching clearly, including the rebuild consequence.

#### Required Capability or Behavior
- README/`hardware.md` explain supported providers, how to set `embed.provider`/`embed.model`/`embed.dims`, that switching rebuilds dense vectors, and that the default is unchanged at `BAAI/bge-small-en-v1.5`/384.
- Document the width/index policy (ANN up to the pgvector limit; exact scan above) and the model/provider examples with correct dimensions.

### Task 6: Pre-Implementation Multi-Width Calibration

#### Intent
Prove the width/index mechanics on the real engines before committing to the DDL, because the halfvec path and the >1536-dimension recall behaviour are not otherwise validated.

#### Required Capability or Behavior
- Against a real Postgres/pgvector instance (the pinned Compose image) and a real SQLite/sqlite-vec store:
  - create and search at 384, 768, 1536, 3072, and 4096 dimensions;
  - confirm `EXPLAIN` shows an index scan for 384/768/1536 (`vector`) and 3072 (halfvec expression index) and a sequential scan for 4096;
  - confirm `SELECT extversion FROM pg_extension WHERE extname='vector'` meets the minimum for halfvec;
  - measure recall against exact search at 3072 (halfvec) to confirm the precision cost is acceptable on this corpus.
- Record the results in the completion evidence; adjust the width/index thresholds if the measurements disagree with the plan.

#### Architectural Responsibility
Implementer-owned calibration; feeds Task 2's DDL and thresholds.

#### Required Changes
1. Run the width/index/recall matrix and record it.
2. If halfvec recall is materially worse than documented elsewhere, document the measured value and prefer exact scan or a narrower model.
3. Confirm the pgvector image tag is pinned and the version assertion is correct.

#### Implementation Constraints
- The calibration MUST NOT be skipped in favour of assuming the published limits (which were measured at ≤1536 dims).
- No dependency changes.

#### Expected Result
The width/index policy is backed by measured `EXPLAIN` plans and recall numbers on this project's own engines.

### Implementation Freedom
The agent may choose concrete structure, naming, and internal design provided the required behavior is satisfied, boundaries respected, contracts preserved, all acceptance criteria pass, and no prohibited changes are introduced.

---

## 6. Agent Execution Rules

### Allowed Actions
- Modify vector DDL generation, space resolution, the dimension gate, embed adapters, factory, reporting, and docs; add tests.
- Change the `IndexStore` query-width validation if needed (in-scope contract adjustment).

### Forbidden Actions
- Coexisting spaces; rerank/extraction; dense write-path wiring.
- Add dependencies; silently truncate/pad vectors; leave old-space rows mixed with new-space rows.
- Delete or bypass tests; disable security controls; commit secrets; claim completion without evidence.

### Agent Decision Boundary
The agent may decide parameterized-DDL structure, space-switch mechanics, and test organization. The agent must request approval for: changing the default model/dims; changing the `model_id`/`dims` column contract; supporting widths above the pgvector index limit with a non-exact path; or any change affecting Phase 100300/100330/100340 assumptions.

### Mandatory Stop Conditions
Stop and report if repository facts contradict the plan, a space switch cannot be restricted to derived data, existing 384 databases cannot open without a rebuild, dependency approval is absent, scope expansion is required, or correctness cannot be verified.

---

## 7. Security Constraints

### Required Controls
- A space switch never decrypts or rewrites item content; it touches derived vector rows only.
- Provider endpoints validated; keys sent only as an `Authorization` header over HTTPS.
- Rebuild/index operations keep their existing confirmation requirements (Phase 100230).
- Wrong-width responses are rejected (no memory-safety or silent-corruption path).

### Sensitive Data Rules
- Never log vectors, source text, or keys; log only counts, widths, model ids, and durations.
- Space-switch logging carries no item content.

### Security Acceptance Conditions
- A space switch cannot alter or erase non-vector data (test asserts item counts unchanged).
- No secret appears in rebuild/diagnose output.

---

## 8. Test and Verification Strategy

### Required Tests
- [ ] Unit tests (space resolution, width comparison, provider parse, dims gate)
- [ ] Integration tests (switch 384→1536→384 on both backends; reindex after switch)
- [ ] Contract tests (default 384 database opens unchanged; KNN query width validated)
- [ ] End-to-end tests (ops reindex against a mock OpenAI and mock TEI endpoint at two widths)
- [ ] Regression tests (whole workspace green; default behavior unchanged)
- [ ] Security tests (switch preserves non-vector tables; no secret in output)
- [ ] Failure-mode tests (wrong count/width, unknown provider, width above index limit, unconfigured provider)

### Required Test Scenarios
| Test ID | Scenario | Expected Result |
|---------|----------|-----------------|
| T100290-01 | Existing 384 DB, default config | Opens with no purge/rebuild; settings unchanged |
| T100290-02 | Config 1536, reindex | Vector table recreated at 1536; new vectors stored; KNN works |
| T100290-03 | Switch back to 384 | Another rebuild; KNN works; no mixed rows |
| T100290-04 | Space switch | Non-vector tables byte-for-byte unchanged (counts + a sampled row) |
| T100290-05 | OpenAI embed mock, correct width | Vectors in input order; width gate passes |
| T100290-06 | Provider returns wrong width/count | `OutOfRange`; no partial write |
| T100290-07 | Unknown `embed.provider` | `ConfigCorrupt` listing allowed values |
| T100290-08 | Configured width > index limit | Exact scan in effect; `diagnose` says so |
| T100290-09 | KNN query with wrong width | Fail closed |
| T100290-10 | No provider configured | Dense/ops reindex unavailable; no behavior change |
| T100290-11 | 3072-dim space on Postgres | Halfvec expression index created; `EXPLAIN` shows index scan for the cast query |
| T100290-12 | 4096-dim space | No ANN index; exact scan; `diagnose` reports exact mode |
| T100290-13 | pgvector older than halfvec support | Bootstrap fails closed with version guidance |
| T100290-14 | Space switch without confirmation | Refused; no vectors dropped |

### Negative Testing
Verify invalid input is rejected, partial failures leave no invalid state, retries remain correct, existing behavior is intact, and a failed switch leaves the store usable at the prior space.

### Verification Rule
Implementation claims must be supported by actual test output, inspection results, or other concrete evidence.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-100290-01 | Any configured width is adopted; no hardcoded 384 pin remains in storage | T100290-02, T100290-03 | Test output; DDL inspection |
| AC-100290-02 | Existing 384 DB opens unchanged; default preserved | T100290-01, T100290-10 | Test output |
| AC-100290-03 | Space switch rebuilds derived vectors only | T100290-04 | Counts + sampled non-vector row diff |
| AC-100290-04 | TEI + OpenAI adapters produce correctly ordered vectors, fail closed on mismatch | T100290-05, T100290-06 | Test output |
| AC-100290-05 | Provider selection and index-availability policy are explicit and reported | T100290-07, T100290-08 | Test output + `diagnose` sample |
| AC-100290-06 | Wrong-width queries and responses fail closed | T100290-06, T100290-09 | Test output |
| AC-100290-07 | No regression on taxonomy/retrieval/admission | Regression suite | Test output |
| AC-100290-08 | Wide-dimension index behaviour is measured, not assumed | T100290-11, T100290-12, T100290-13 | `EXPLAIN` plans + recall numbers recorded (Task 6) |
| AC-100290-09 | Space switching is explicit and cannot silently wipe the index | T100290-14 | Test output |

### Evidence (recorded from the implementation round)

**Coverage gate.** Baseline (pre-change workspace JSON): aggregate lines 97.89% / functions 98.98%, 254 reported files, 0 below 90%. Final `make coverage`: aggregate lines **97.88%** / functions **98.91%**, 261 reported files, **0 below 90%** on either metric. Per-file for everything created or modified this round (lines% / functions%): `embedding_space` 100/100, `vector_ddl` 99.32/100, `space_reconcile` 94.12/100, `postgres_coverage` 100/100, `sqlite` 100/100, `postgres` 99.30/100, `sqlite_store` 100/100, `postgres_store` 100/100, `postgres_index` 96.52/100, `sqlite_index` 98.36/100, `sqlite_ops` 95.83/100, `postgres_ops` 92.79/92.86, `bootstrap` 100/100, `model` 100/100, `migrate` 100/100, `store`/`ops_store` 100/100, `openai` 93.10/92.31, `provider` 100/100, `embed` 100/100, `worker` 97.00/90.91, `report` 100/100, `diagnose` 100/100, `runtime` 99.44/100, `ops_embedder` 100/100, `validate` 98.22/100, `merge` 100/100, `ops_cli` 95.47/97.22.

**AC-100290-01 / T100290-02, T100290-03 — any configured width is adopted; no 384 pin in storage.** The vector table and its index are generated in Rust from the resolved `(model_id, dims)` (`vector_ddl`); neither static SQL asset contains `item_embeddings` any more (`migrate.rs` asserts this). SQLite round trip: switch 384→768 recreated the vec0 table as `float[768]`, purged 1 derived row, recorded `embedding_dim='768'`, then 1536→384 switched back with `purged_rows=1` and no mixed rows. Postgres round trip: after a confirmed switch the column type read back from `pg_attribute` was `vector(768)`, a 768-wide upsert + KNN worked, and a 384-wide query failed closed with `OutOfRange`.

**AC-100290-02 / T100290-01, T100290-10 — existing 384 DB opens unchanged; default preserved.** `fresh_store_records_the_default_space` opens a store and asserts `EmbeddingSpace::default_space()`, `embedding_dim='384'`, `embedding_model='BAAI/bge-small-en-v1.5'`, and a `float[384]` table, then writes and KNN-queries at 384. `equal_space_reconcile_is_a_noop` asserts `switched=false, purged_rows=0`. With no `embed.url` the ops factory returns `None` and a live dense reindex still exits 3 (`reindex_dense_confirmed_without_embedder_exits_3`).

**AC-100290-03 / T100290-04 — a switch rebuilds derived vectors only.** `switch_preserves_every_non_vector_table` compares the decrypted item before/after (`assert_eq!(before_item, after_item)`), item counts, and lexical row counts across a confirmed switch; only `dense_rows` drops to 0. The Postgres round trip asserts `get_memory_item` still resolves after two switches.

**AC-100290-04 / T100290-05, T100290-06 — TEI + OpenAI adapters, ordered, fail closed.** `batch_is_reconstructed_in_input_order` serves a response with `index` 1 then 0 and asserts the returned vectors match input order; `wrong_width_and_count_fail_closed` asserts `OutOfRange` for a 7-dim reply and for a count mismatch; `response_shape_failures_are_rejected` covers missing `data`, an out-of-range `index`, a duplicate `index`, a non-numeric `embedding`, and a missing slot. `empty_provider_keeps_the_tei_default` and `openai_provider_selects_the_data_array_dialect` prove provider dispatch, and `unknown_provider_fails_closed_listing_the_allowed_values` asserts `ConfigCorrupt` naming `tei|openai`.

**AC-100290-05 / T100290-07, T100290-08 — provider selection and index policy are explicit and reported.** `unknown_provider_fails_closed_listing_the_allowed_values` (T100290-07). `am ops diagnose` on a memory store printed: `{"ok":true,...,"embedding_model":"BAAI/bge-small-en-v1.5","embedding_dims":384,"index_mode":"ann_vector",...}`. The width→mode matrix test asserts `ann_vector`/`ann_halfvec`/`exact_scan` per width and that a 4096 table carries no ANN index (T100290-08).

**AC-100290-06 / T100290-06, T100290-09 — wrong-width queries and responses fail closed.** `require_dims` unit tests; `confirmed_switch_recreates_the_table_at_the_new_width` asserts a 384 query and a 384 upsert both fail with `OutOfRange` while the active space is 768; the OpenAI adapter rejects a wrong-width reply without writing anything.

**AC-100290-07 — no regression on taxonomy/retrieval/admission.** `cargo test --locked --workspace` (with `DATABASE_URL` set) is green across every crate, including `clio-store` 230 tests, `clio-mcp` 202, `clio-config` 115, `clio-index` 58, `clio-ops` 47. `cargo clippy --workspace --all-targets --all-features --locked -- -D warnings` is clean.

**AC-100290-08 / T100290-11, T100290-12, T100290-13 — wide-dimension behaviour measured, not assumed.** See "Task 6 calibration" below; pgvector 0.8.6 satisfies the 0.7.0 `halfvec` floor, 3072 creates and uses the `halfvec` expression index, 4096 has no ANN index and stays a sequential scan even with `enable_seqscan=off`, and `halfvec` recall@10 at 3072 measured **0.9800 (98/100)** against exact search on 200 rows, with the indexed run forced through the HNSW index (`SET enable_seqscan = off`) and guarded by an `EXPLAIN` assertion so the number measures the ANN path rather than a second exact scan. `pgvector_below_halfvec_floor_fails_closed_with_guidance` asserts the refusal text names `0.7.0` and `upgrade`; `old_pgvector_bootstrap_refuses_halfvec_before_ddl` drives the same bootstrap gate (`apply_vector_ddl_with`) with an injected `0.6.2` version and asserts the refusal, so the T100290-13 refusal path is exercised without an old extension installed.

**AC-100290-09 / T100290-14 — switching is explicit and cannot silently wipe the index.** `unconfirmed_switch_is_refused_and_keeps_rows` asserts `ConfigCorrupt`, the message naming `embed.switch_space=true`, and that the old table and rows are still intact; both the MCP runtime and `am ops` refuse a mismatched space without the opt-in.

### Task 6 calibration (real engines)

Postgres (`pgvector/pgvector:pg16` in Compose, private schema per case, 200 rows per width; captured with `cargo test -p clio-store pg_space_tests -- --nocapture`):

```text
calibration: pgvector extversion = 0.8.6
calibration: width=384  mode=ann_vector  hnsw=true  seqscan_off=[Index Scan using item_embeddings_embedding_hnsw_inx on item_embeddings]
calibration: width=768  mode=ann_vector  hnsw=true  seqscan_off=[Index Scan using item_embeddings_embedding_hnsw_inx on item_embeddings]
calibration: width=1536 mode=ann_vector  hnsw=true  seqscan_off=[Index Scan using item_embeddings_embedding_hnsw_inx on item_embeddings]
calibration: width=3072 mode=ann_halfvec hnsw=true  seqscan_off=[Index Scan using item_embeddings_embedding_hnsw_inx on item_embeddings]
calibration: width=4096 mode=exact_scan  hnsw=false seqscan_off=[Seq Scan on item_embeddings]
calibration: halfvec recall@10 at 3072 dims = 0.9800 (98/100)
```

Measured nuance (recorded honestly): with only 200 rows the plain plan chooses `Seq Scan` + `Sort` at 768/1536/3072 (seq cost ≈ 15 versus an HNSW startup cost ≈ 400–790); 384 chose the index scan outright. Index applicability is therefore asserted with `enable_seqscan=off`, which shows the HNSW index serving the exact cast query at every width ≤ 4000 and no matching index at 4096. The recall comparison forces the indexed run through that same index (and asserts the plan used it), so it measures halfvec ANN precision rather than a second exact scan; the measured cost on this corpus is 0.98, above the 0.9 floor, so the planned thresholds were kept.

Live DDL, both widths (index definitions read back from Postgres after applying the generated DDL):

```text
WIDTH384  CREATE INDEX item_embeddings_embedding_hnsw_inx ON item_embeddings USING hnsw (embedding vector_cosine_ops)
WIDTH3072 CREATE INDEX item_embeddings_embedding_hnsw_inx ON item_embeddings USING hnsw (((embedding)::halfvec(3072)) halfvec_cosine_ops)
```

SQLite DDL for a width is `CREATE VIRTUAL TABLE item_embeddings USING vec0 (… embedding float[N] distance_metric = cosine, +bank_id text, +model_id text, +created_at text, +updated_at text)` (`sqlite_ddl_carries_width_and_aux_columns` asserts `float[1536]`).

**Masked config.** Secrets are masked by the config layer (`Runtime::effective_masked`); `embed_config_keys_defaults_allowlist_and_masking` passes and asserts the masked view contains neither the embed nor the rerank token while `effective_raw` carries them. The operator-facing space view above (`am ops diagnose`) contains no secret. `config_get`/`config_set` are config-layer tools; this build does not register them on the MCP tool surface, so the masked sample is cited from the config-layer test rather than a captured MCP response.

### Definition of Done
- [x] All in-scope behavior implemented.
- [x] All acceptance criteria pass.
- [x] Required tests pass.
- [x] No unauthorized changes introduced.
- [x] Existing behavior remains intact.
- [x] Security checks pass.
- [x] Documentation updated.
- [x] Evidence collected and verification completed.
- [x] Required approval is obtained (downstream pipeline step).

### Completion Evidence

**Implementation summary.** The 384-dimension pin is gone from storage. `clio-store` now owns an `EmbeddingSpace { model_id, dims }` resolved from `embed.model`/`embed.dims` (validated to `1..=16000`), records it in `schema_settings` (`embedding_model`/`embedding_dim`), and generates the `item_embeddings` table and its index for that width (`clio-store/src/vector_ddl.rs`). Widths ≤ 2000 get a plain `vector` HNSW index, 2001–4000 a `halfvec` expression index (pgvector ≥ 0.7.0 asserted at open), 4001–16000 no index (exact scan), above 16000 a config error. SQLite builds `vec0` with `float[N]`. A configured space that differs from the recorded one is refused unless `embed.switch_space = true`, except on a genuinely fresh database (no recorded space and no derived rows), which records the configured space directly; a confirmed switch drops and recreates only the vector table, records the new space, and logs one PII-free `embedding_space_switch` event. `clio-index` gained the OpenAI-compatible adapter (`/v1/embeddings`, index-ordered parsing) and a provider factory (`tei`/`openai`, empty = TEI) that fails closed on unknown providers; the coordinator's dimension gate now compares the embedder against the store's active space. `clio-mcp` builds the ops embedder from the effective config (provider, url, model, dims, bearer) and reconciles the space at open; an unknown `embed.provider` (including one supplied only via `EMBED_PROVIDER`) now surfaces the allowed-values error instead of silently disabling dense work. `clio-ops::diagnose` reports `embedding_model`, `embedding_dims`, and `index_mode`. `schema_version` moved 9 → 10 and converges on open (a no-op at 384).

**Remediation (r1).** The Adversary round found that per-row `model_id` was not validated on write; both backends now reject a foreign model id (`EmbeddingSpace::require_model`) with `InvalidArgument`, and the store's test fixtures/fakes were aligned to the default model. The `halfvec` recall measurement was corrected to force the ANN path (it previously compared two exact scans) and now measures 0.98 with an `EXPLAIN` guard. A fresh-database path was added so a first-time non-default width is adopted without the destructive-switch opt-in, while a database with derived rows still requires it. The pgvector version gate gained an injected-version seam and an end-to-end refusal test. The ops embedder surfaces unknown-provider errors. README phase-number leakage, the `openai_tests.rs` copyright header, and the stale `VectorSlot` doc comment were corrected.

**Changed components.** New: `clio-store` `embedding_space.rs`, `vector_ddl.rs`, `space_reconcile.rs`, `postgres_coverage.rs`; `clio-index` `openai.rs`, `provider.rs`; `clio-mcp` `ops_embedder.rs`; test modules `sqlite_space_tests.rs`, `pg_space_tests.rs`, `openai_tests.rs`, `provider_tests.rs`, `reindex_space_tests.rs`. Modified: `clio-store` `sqlite.rs`, `postgres.rs`, `sqlite_store.rs`, `postgres_store.rs`, `postgres_index.rs`, `sqlite_index.rs`, `sqlite_ops.rs`, `postgres_ops.rs`, `bootstrap.rs`, `migrate.rs`, `store.rs`, `ops_store.rs`, `lib.rs`; `clio-index` `embed.rs`, `worker.rs`, `report.rs`, `lib.rs`; `clio-ops` `diagnose.rs`; `clio-config` `config/merge.rs`, `config/validate.rs`; `clio-mcp` `runtime.rs`; `clio-lib` `ops_cli.rs`; `sql/001_core.sql`, `sql/002_vectors_postgres.sql`, `sql/002_vectors_sqlite.sql`; docs `README.md`, `hardware.md`, `.env.example`.

**Test output.** `cargo test --locked --workspace` green (clio-store 230, clio-mcp 202, clio-config 115, clio-index 58, clio-ops 47, clio-write 123, clio-belief/clio-history/clio-retrieve/clio-sync/clio-types/clio-admission/clio-persona/clio-hygiene/clio-compliance all green). `make coverage` → lines 97.88% / functions 98.91%, 0 files below 90%. `cargo clippy --workspace --all-targets --all-features --locked -- -D warnings` clean.

**DDL excerpts, masked config sample, calibration.** See the "Evidence" and "Task 6 calibration" sections above.

**Verification report.** Verified by real output: the two-engine space switch (SQLite + Postgres), the width→index matrix with `EXPLAIN`, `halfvec` recall at 3072 through the forced ANN index, the provider adapters against in-process mock TEI/OpenAI endpoints at two widths through `am ops reindex`, the fail-closed paths (unknown provider, wrong count/width, unconfirmed switch, wrong-width query, foreign model id), the non-vector-table preservation check, and the full coverage/clippy gates. Not verified: no hosted OpenAI endpoint was contacted (only a local mock); a real pgvector older than 0.7.0 was unavailable, so the T100290-13 refusal is exercised with an injected version through the same bootstrap gate rather than against an installed old extension; the `config_get`/`config_set` MCP tools are not registered in this build, so masking is cited from the config-layer test.

**Known limitations.**
- Exactly one embedding space is active. Vectors for a previous model are discarded on switch and must be re-embedded; coexistence is out of scope by operator decision.
- Widths are bounded by the storage engine: ≤ 2000 indexed as `vector`; 2001–4000 via a `halfvec` expression index (pgvector ≥ 0.7.0); 4001–16000 exact scan only; above 16000 rejected at configuration time.
- The per-row `model_id` is written by the caller (worker/rebuild stamp the embedder's model) and is validated against the active space on every `upsert_vector` (both backends): a foreign model id fails closed with `InvalidArgument` rather than being stored. Combined with the purge-on-switch and the refused unconfirmed switch, one active space can never mix models.
- A space switch purges every derived row, so the operator's rebuild signal is the dense-coverage gap (`dense_rows` below `indexable_items`) reported by `diagnose`/coverage plus the `embedding_space_switch` log; no separate persisted rebuild-required flag is set. Durable rebuild-required state is owned by the dense write-path wiring in Phase 100350.
- Dense index maintenance is still not wired into the MCP write path until Phase 100350, so a switched space needs an explicit `reindex`.
- No automatic probing of a model's output width; `embed.dims` is operator-supplied and validated against the response.
- A running MCP server reconciles the embedding space only when it opens; a config change made while the server runs is picked up on the next restart. Runtime config-change detection without a restart is not implemented.
- The plain (cost-based) `EXPLAIN` plan at 768/1536/3072 on a 200-row table is a sequential scan; the ANN index is proven applicable with `enable_seqscan=off`. Larger corpora are expected to select the index, but that was not measured here.

---

## 10. Failure Handling and Recovery

### Expected Failure Modes
| Failure | Detection | Recovery |
|---------|-----------|----------|
| Configured dims missing/zero | Resolution | Fail closed with guidance |
| Switch interrupted mid-way | Bootstrap guard | Next open detects mismatch and re-runs the switch; vectors rebuilt |
| Provider returns wrong width | Width gate | Error; no partial write |
| Width above index limit | Index policy | Exact scan; reported by `diagnose` |
| Rebuild fails | Rebuild report | Dense index left marked dirty; retry reindex |

### Rollback Strategy
Set `embed.dims`/`embed.model` back to the previous space and run reindex; only derived vectors change. Reverting the phase restores the 384 pin for unmodified databases.

### Partial Completion Policy
Do not claim completion if storage is generalized but adapters are absent, or vice versa. Record completed and incomplete work separately; never leave a half-switched space.

---

## 11. Traceability

| Parent Requirement | Implementation Task | Verification | Acceptance Criterion |
|--------------------|---------------------|--------------|-----------------------|
| Operator finding #1 (multi-model/providers) | Tasks 1–3 | T100290-01…T100290-05 | AC-100290-01, AC-100290-02, AC-100290-03 |
| FR-26 / PR-4 (no silent truncation) | Tasks 2, 3 | T100290-06, T100290-09 | AC-100290-06 |
| §4.9.5.E / FR-32 | Task 4 | T100290-08, T100290-10 | AC-100290-05 |
| `gap/zero-deps.md` embed portion | Tasks 3, 4 | T100290-05, T100290-10 | AC-100290-04, AC-100290-07 |

Required chain:

```text
Requirement → Capability → Implementation → Test → Evidence
```

---

## 12. Phase Exit Contract

### Outputs Produced
- Active embedding space resolution and dimension-agnostic vector storage.
- Space-switch rebuild semantics restricted to derived vectors.
- TEI + OpenAI-compatible embed adapters and an ops embedder factory from config.
- Diagnostics reporting the active space and index mode.

### Guarantees Provided to Downstream Phases
- Phase 100300 (rerank) can build on the same transport/config.
- Phase 100350 can construct the dense index pipeline knowing the store accepts the configured width.
- Any supported provider/model becomes selectable without a schema fork.

### Known Limitations
- Exactly one embedding space is active; vectors for a previous model are discarded on switch (re-embed needed). Coexistence is out of scope by operator decision.
- Widths are bounded by the storage engine: ≤ 2000 index as `vector`; 2001–4000 index via a `halfvec` expression index (requires pgvector ≥ 0.7.0); 4001–16000 exact scan only; above 16000 is rejected at configuration time. A 4096-dimension model (for example Qwen3-Embedding-8B) falls into the exact-scan band.
- Dense index maintenance is still not wired into the MCP write path until Phase 100350, so a switched space needs an explicit `reindex`.
- No automatic probing of a model's output width; `embed.dims` is operator-supplied and validated against the response.
- A running MCP server reconciles the embedding space only when it opens; a config change made while the server runs is picked up on the next restart. Runtime config-change detection without a restart is not implemented.

### Requirement Audit
`requirement.md` was checked for any FR/NFR that fixes a single embedding dimension or forbids multiple models: none exists. The storage section names both backends but no width; multi-model support is additive under §4.9.5.E (effective configuration) and NFR-5 (determinism is preserved because a space is fixed per configuration). No requirement edit is needed.

### Downstream Prerequisites
- Phase 100350 assumes the store resolves and validates the active width.
- Phase 100300 does not depend on this phase's space change.

### Final Status
PASS

### Verification Sign-Off
- Implementer: OpenCode CLI (Go . Deepseek V4.1 Flash High)
- Verifier: pending (Adversary r1)
- Human Approver: [Name, if required]
- Date: 2026-09-21

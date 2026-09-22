# Agent Memoir — 35 build slices + 9 remediation + 9 follow-up phases (53 total)

Each numbered slice is one staffing unit of roughly **equal engineering effort** (~1×). Relative weights are marked on each heading (`1×` or `1.5×`); the max/min ratio is kept ≤ 1.5. Order is primary build dependency, not priority; independent slices (for example 100310 and 100320, and the extraction adapter 100340) share no dependency with their neighbours and are placed for narrative grouping. No links outside this folder.

The **remediation phases 100360–100520** added 2026-09-22 use a different sizing basis: bottom-up ideal days for one senior Rust dev (0.5–9 days), not the ~1× slice unit, because they are gap-closure work of very uneven size rather than equal staffing units. The ≤1.5 ratio rule applies to the original slices only and does not bind the remediation table.

## Effort model

Target unit is about **one focused engineer-week** of implementation (design + code + a small self-check), not calendar elapsed time. Weights below are a lightweight WBS: most slices are `1×`; the larger-fan-out slices are `1.5×` (dual-backend storage 2, hybrid retrieve 12, MCP write binding 16, sync 24, multi-model embeddings 29, setup wizard 33, hosted extraction 34, live wiring 35). A former `2×` setup+compose slice was split into 32 (`1×`) and 33 (`1.5×`) to keep the ratio at ≤ 1.5. Re-estimate after a spike if a `1.5×` still overruns.

## Plan status

Status values: **Plan ready** (spec only) · **Complete — PASS WITH DOCUMENTED LIMITATIONS** (implementation accepted; see phase exit contract).

| Slice | Effort | Implementation plan | Status |
|------:|--------|---------------------|--------|
| 100010 | `1×` | [phase-100010-runtime-profiles-packaging.md](phase-100010-runtime-profiles-packaging.md) | Complete — PASS WITH DOCUMENTED LIMITATIONS |
| 100020 | `1.5×` | [phase-100020-dual-backend-persistence.md](phase-100020-dual-backend-persistence.md) | Complete — PASS WITH DOCUMENTED LIMITATIONS |
| 100030 | `1×` | [phase-100030-memory-item-core.md](phase-100030-memory-item-core.md) | Complete — PASS WITH DOCUMENTED LIMITATIONS |
| 100040 | `1×` | [phase-100040-taxonomy-admission.md](phase-100040-taxonomy-admission.md) | Complete — PASS WITH DOCUMENTED LIMITATIONS |
| 100050 | `1×` | [phase-100050-online-extraction-span-verification.md](phase-100050-online-extraction-span-verification.md) | Complete — PASS WITH DOCUMENTED LIMITATIONS |
| 100060 | `1×` | [phase-100060-parallel-write-canonical-consolidation.md](phase-100060-parallel-write-canonical-consolidation.md) | Plan ready |
| 100070 | `1×` | [phase-100070-memtree-dirty-path-maintenance.md](phase-100070-memtree-dirty-path-maintenance.md) | Complete — PASS WITH DOCUMENTED LIMITATIONS |
| 100080 | `1×` | [phase-100080-bitemporal-triples-supersession.md](phase-100080-bitemporal-triples-supersession.md) | Plan ready |
| 100090 | `1×` | [phase-100090-shared-continuous-ema-update-engine.md](phase-100090-shared-continuous-ema-update-engine.md) | Plan ready |
| 100100 | `1×` | [phase-100100-fact-belief-epistemic-kind-confidence-trajectories.md](phase-100100-fact-belief-epistemic-kind-confidence-trajectories.md) | Plan ready |
| 100110 | `1×` | [phase-100110-dense-lexical-index-pipelines.md](phase-100110-dense-lexical-index-pipelines.md) | Plan ready |
| 100120 | `1.5×` | [phase-100120-intent-gate-hybrid-retrieve-compose.md](phase-100120-intent-gate-hybrid-retrieve-compose.md) | Plan ready |
| 100130 | `1×` | [phase-100130-coactivation-associations-hub-distillation.md](phase-100130-coactivation-associations-hub-distillation.md) | Plan ready |
| 100140 | `1×` | [phase-100140-persona-companion-object.md](phase-100140-persona-companion-object.md) | Plan ready |
| 100150 | `1×` | [phase-100150-task-failure-temporal-history.md](phase-100150-task-failure-temporal-history.md) | Plan ready |
| 100160 | `1.5×` | [phase-100160-mcp-schemas-write-surface.md](phase-100160-mcp-schemas-write-surface.md) | Plan ready |
| 100170 | `1×` | [phase-100170-mcp-read-retrieve-compose-surface.md](phase-100170-mcp-read-retrieve-compose-surface.md) | Plan ready |
| 100180 | `1×` | [phase-100180-audit-trail-inspect-correction.md](phase-100180-audit-trail-inspect-correction.md) | Plan ready |
| 100190 | `1×` | [phase-100190-compliance-erase-path.md](phase-100190-compliance-erase-path.md) | Plan ready |
| 100200 | `1×` | [phase-100200-additive-harness-workspace-tools.md](phase-100200-additive-harness-workspace-tools.md) | Plan ready |
| 100210 | `1×` | [phase-100210-hygiene-audit-confirmed-cleanup.md](phase-100210-hygiene-audit-confirmed-cleanup.md) | Plan ready |
| 100220 | `1×` | [phase-100220-json-export-import.md](phase-100220-json-export-import.md) | Plan ready |
| 100230 | `1×` | [phase-100230-ops-doctor-repair.md](phase-100230-ops-doctor-repair.md) | Plan ready |
| 100240 | `1.5×` | [phase-100240-multi-host-sync-protocol.md](phase-100240-multi-host-sync-protocol.md) | Plan ready |
| 100250 | `1×` | [phase-100250-per-bank-retention-profiles.md](phase-100250-per-bank-retention-profiles.md) | Plan ready |
| 100260 | `1×` | [phase-100260-retention-mission-coding-defaults.md](phase-100260-retention-mission-coding-defaults.md) | Plan ready |
| 100270 | `1×` | [phase-100270-consolidated-recall-dedup.md](phase-100270-consolidated-recall-dedup.md) | Plan ready |
| 100280 | `1×` | [phase-100280-https-transport-config.md](phase-100280-https-transport-config.md) | Plan ready |
| 100290 | `1.5×` | [phase-100290-multi-model-embeddings.md](phase-100290-multi-model-embeddings.md) | Plan ready |
| 100300 | `1×` | [phase-100300-rerank-providers.md](phase-100300-rerank-providers.md) | Plan ready |
| 100310 | `1×` | [phase-100310-default-database-path.md](phase-100310-default-database-path.md) | Plan ready |
| 100320 | `1×` | [phase-100320-compose-lifecycle.md](phase-100320-compose-lifecycle.md) | Plan ready |
| 100330 | `1.5×` | [phase-100330-am-setup-wizard.md](phase-100330-am-setup-wizard.md) | Plan ready |
| 100340 | `1.5×` | [phase-100340-hosted-extraction-adapter.md](phase-100340-hosted-extraction-adapter.md) | Plan ready |
| 100350 | `1.5×` | [phase-100350-live-index-extraction-wiring.md](phase-100350-live-index-extraction-wiring.md) | Plan ready |

Phase-scoped appendices (same folder): [phase-100020-appendix-vector-parity.md](phase-100020-appendix-vector-parity.md) · [phase-100040-appendix-admission-factors.md](phase-100040-appendix-admission-factors.md) · [phase-100050-appendix-span-verification.md](phase-100050-appendix-span-verification.md) · [phase-100080-appendix-bitemporal-intervals.md](phase-100080-appendix-bitemporal-intervals.md) · [phase-100090-appendix-ema-formulas.md](phase-100090-appendix-ema-formulas.md) · [phase-100120-appendix-hybrid-fusion-and-budgets.md](phase-100120-appendix-hybrid-fusion-and-budgets.md) · [phase-100130-appendix-association-weight-policy.md](phase-100130-appendix-association-weight-policy.md) · [phase-100210-appendix-noise-scoring.md](phase-100210-appendix-noise-scoring.md) · [phase-100220-appendix-bundle-format.md](phase-100220-appendix-bundle-format.md) · [phase-100240-appendix-sync-cursors-conflict.md](phase-100240-appendix-sync-cursors-conflict.md)

## Explicit later (not in these 35)

- **Provider ingest** (`import_provider` matrix beyond a stub): **out of first release**. First release ships JSON export/import with manifests; provider adapters follow later in a dedicated provider-ingest phase (not 029/030/034). First-wave memory systems: `hindsight`, `mem0`, `mnemosyne`, `honcho`, `supermemory`; LLM/chat vendors are not ingest providers.

---

## 100010. Runtime, profiles, ranking env, and coding-agent packaging · `1×` · **Complete** · [phase-100010-runtime-profiles-packaging.md](phase-100010-runtime-profiles-packaging.md)

Build the process/library shell (entrypoints, logging, error shapes, `bank` / `actor`), effective configuration with secret masking, named profiles (`config_*`), `ranking_env_*` knobs, and a coding-agent profile that exposes the full tool surface with per-repo bank defaults. This is the chassis and packaging milestone every later slice plugs into.

## 100020. Dual-backend persistence with encryption hooks · `1.5×` · **Complete** · [phase-100020-dual-backend-persistence.md](phase-100020-dual-backend-persistence.md)

Implement selectable Postgres+pgvector and SQLite backends behind one behavioral contract for items, graph/structure metadata (SQL `assoc_edges` / `assoc_kind`), and vectors. For SQLite vectors, use a loadable vector-search extension (e.g. sqlite-vec or equivalent)—not a pretend native pgvector. Phase 100020 requires storage hooks and exact/brute-force KNN where the extension provides it; ANN performance parity is not required (see [phase-100020-appendix-vector-parity.md](phase-100020-appendix-vector-parity.md)). Store content payloads as ciphertext under a per-subject DEK interface from day one so later erase does not retrofit every table. Backend choice must not fork product rules.

## 100030. Memory item core and dual representations · `1×` · **Complete** · [phase-100030-memory-item-core.md](phase-100030-memory-item-core.md)

Ship repository create/read/update for semantic and episodic items with provenance, confidence, admission fields, and separate snapshot vs gist storage. Exact-value consumers always read snapshots; gists stay non-authoritative. These are **repository primitives only**—no public harness write may bypass the admission gates in slice 100040.

## 100040. Taxonomy and admission scoring · `1×` · **Complete** · [phase-100040-taxonomy-admission.md](phase-100040-taxonomy-admission.md)

Implement both write gates end to end: closed category whitelist for semantic types, episodic type-tag admission path, then five-factor admission scoring with thresholds, deterministic decisions, logged rejects, and `admit_preview` without write. Factor formulas: [phase-100040-appendix-admission-factors.md](phase-100040-appendix-admission-factors.md). All long-term public writes (including later MCP tools) must pass these gates.

## 100050. Online extraction and span verification · `1×` · [phase-100050-online-extraction-span-verification.md](phase-100050-online-extraction-span-verification.md)

Build turn/tool extraction into schema-typed snapshots with span-copy verification for entities, numbers, and dates (retry once, then refuse commit). Online path stays a cheap verifier.

## 100060. Parallel write path and canonical consolidation · `1×` · [phase-100060-parallel-write-canonical-consolidation.md](phase-100060-parallel-write-canonical-consolidation.md)

Make new memory queryable fast: parallel chunk extraction, merge near-duplicates into a canonical unit, and expose the leaf immediately. Structural maintenance must not block leaf readability.

## 100070. MemTree and dirty-path maintenance · `1×` · **Complete** · [phase-100070-memtree-dirty-path-maintenance.md](phase-100070-memtree-dirty-path-maintenance.md)

Organize episodic memory as time-ordered trees and refresh only dirty ancestor paths, with parallel same-depth updates. Expose `maintenance_status` and `consolidate` so agents can see and trigger non-blocking structure work.

## 100080. Bi-temporal triples and supersession · `1×` · [phase-100080-bitemporal-triples-supersession.md](phase-100080-bitemporal-triples-supersession.md)

Implement subject–predicate–object edges with valid-time and transaction-time, supersession via invalidation (not delete), and point-in-time query (`as_of`, `time_axis`). Reject continuous/scalar updates on this path.

## 100090. Shared continuous EMA update engine · `1×` · [phase-100090-shared-continuous-ema-update-engine.md](phase-100090-shared-continuous-ema-update-engine.md)

Implement the continuous/scalar update model (EMA plus slower trend) and enforce `update_rule` declarations so discrete invalidation and continuous smoothing never mix. This slice owns the **shared update engine** and generic `update` rule splitting; persona (slice 100140) calls into it and does not reimplement EMA. Formulas: [phase-100090-appendix-ema-formulas.md](phase-100090-appendix-ema-formulas.md).

## 100100. Fact/belief epistemic kind and confidence trajectories · `1×` · [phase-100100-fact-belief-epistemic-kind-confidence-trajectories.md](phase-100100-fact-belief-epistemic-kind-confidence-trajectories.md)

Tag every item with `epistemic_kind` fact or belief; give beliefs append-only confidence history with `source_type`; expose `belief_observe` / `belief_history`; surface `epistemic_kind` and belief confidence on retrieval responses.

## 100110. Dense and lexical index pipelines · `1×` · [phase-100110-dense-lexical-index-pipelines.md](phase-100110-dense-lexical-index-pipelines.md)

Wire embedding generation and lexical/BM25 indexing for both backends (Postgres via pgvector; SQLite via the extension chosen in slice 100020), including rebuild hooks. Keep index maintenance separable from leaf write success. Early spike of the SQLite vector path happens here if slice 100020 left integration unfinished. Revisit ANN only per [phase-100020-appendix-vector-parity.md](phase-100020-appendix-vector-parity.md).

## 100120. Intent gate, hybrid retrieve, and compose · `1.5×` · [phase-100120-intent-gate-hybrid-retrieve-compose.md](phase-100120-intent-gate-hybrid-retrieve-compose.md)

Combine the per-turn intent gate (skip unneeded search; never gate persona), hybrid dense+lexical+optional graph retrieval with reranking, and `compose_context` under fixed token budgets. Honor domain filters and bi-temporal query args. Storage size stays independent of injection size. Fusion/budgets: [phase-100120-appendix-hybrid-fusion-and-budgets.md](phase-100120-appendix-hybrid-fusion-and-budgets.md).

## 100130. Co-activation associations and hub distillation · `1×` · [phase-100130-coactivation-associations-hub-distillation.md](phase-100130-coactivation-associations-hub-distillation.md)

On co-retrieved sets, update edge weights with saturating growth, lazy decay, pruning below threshold, and hub consolidation into gated semantic items. Expose `associations`, `graph_link`, and `graph_query`. Formulas: [phase-100130-appendix-association-weight-policy.md](phase-100130-appendix-association-weight-policy.md).

## 100140. Persona companion object · `1×` · [phase-100140-persona-companion-object.md](phase-100140-persona-companion-object.md)

Build the bounded persona document and always-on injection under its own token budget with ranked truncation. Discrete stables use invalidation-style puts; continuous preferences call the shared EMA engine from slice 100090 (`persona_observe_preference` is a thin adapter, not a second EMA implementation).

## 100150. Task, failure, and temporal history · `1×` · [phase-100150-task-failure-temporal-history.md](phase-100150-task-failure-temporal-history.md)

Implement selective history records and tools for tasks, length-capped failure lessons, and temporal trajectories—without full-log replay. Surface prior failures when retrying the same or similar task.

## 100155. Operations `discard` tool (gap remediation) · `1×` · [phase-100155-ops-discard-tool.md](phase-100155-ops-discard-tool.md)

Remediation insert added 2026-09-19: implement the in-process ops `discard` tool (`discard(item_id, reason)`, §4.9.4.A) writing the existing `discarded_at`/`discard_reason` columns on both backends, with FR-15 telemetry and §4.9.2 confirmation. Closes the phase-100080 scope ambiguity ("`discard` full ops tool if not already present" was skipped) that left slice 100160's minimum write set unbindable. Slice 100160 depends on this being accepted first.

## 100160. MCP schemas and write surface · `1.5×` · [phase-100160-mcp-schemas-write-surface.md](phase-100160-mcp-schemas-write-surface.md)

Publish machine-readable schemas for the normative catalog and expose gated write/mutate tools over **stdio and Streamable HTTP** (legacy HTTP+SSE only if a harness still requires it). Cover `store`, triples, invalidate/discard, persona writes, failures, beliefs, and related mutators. Tool semantics must match across transports; gates stay enforced inside tools.

## 100170. MCP read, retrieve, and compose surface · `1×` · [phase-100170-mcp-read-retrieve-compose-surface.md](phase-100170-mcp-read-retrieve-compose-surface.md)

Complete the same MCP transports for reads and orchestration: intent diagnostics, retrieve/compose, snapshot/gist getters, MemTree queries, temporal/belief history, and day-to-day inspect listing. Semantics stay identical to the write surface.

## 100180. Audit trail, inspect, and correction · `1×` · [phase-100180-audit-trail-inspect-correction.md](phase-100180-audit-trail-inspect-correction.md)

Emit attributable telemetry on mutating operations and expose `audit_trail`, `inspect`, and `correct` as a read/correct path over the same history structures the write path already stores—not a second logging system.

## 100190. Compliance erase path · `1×` · [phase-100190-compliance-erase-path.md](phase-100190-compliance-erase-path.md)

Ship verified `erase_request`: destroy the subject DEK (keys introduced in slice 100020), regenerate derived structures via dirty-path, and write content-free tombstones. Hygiene and discard must not alias this path. This slice is erase UX and propagation, not first-time encryption plumbing.

## 100200. Additive harness workspace tools · `1×` · [phase-100200-additive-harness-workspace-tools.md](phase-100200-additive-harness-workspace-tools.md)

Deliver coding-agent operability tools: atomic `batch`, ephemeral scratchpad, `canonical_*`, `shared_*`, and `validate`, without bypassing long-term admission rules or treating scratchpad as durable memory.

## 100210. Hygiene audit and confirmed cleanup · `1×` · [phase-100210-hygiene-audit-confirmed-cleanup.md](phase-100210-hygiene-audit-confirmed-cleanup.md)

Ship ranked `hygiene_audit` and confirmed `hygiene_clean` (`flag` / `archive` / `discard`) with secret masking, a durable hygiene log, and callable `hygiene_log_list`. Operations removal only—not supersession and not compliance erasure. Noise defaults: [phase-100210-appendix-noise-scoring.md](phase-100210-appendix-noise-scoring.md).

## 100220. JSON export and import · `1×` · [phase-100220-json-export-import.md](phase-100220-json-export-import.md)

Ship manifest-backed `export` and idempotent gated `import` with dry-run reports and no plaintext secrets. Default `dsar_plaintext` content mode; optional `ciphertext_backup`. Provider ingest is explicitly later; this slice may leave a stub seam but must not expand into a multi-provider matrix. Bundle format: [phase-100220-appendix-bundle-format.md](phase-100220-appendix-bundle-format.md).

## 100230. Ops doctor and repair · `1×` · [phase-100230-ops-doctor-repair.md](phase-100230-ops-doctor-repair.md)

Ship PII-safe `diagnose`, `verify`, `doctor`, `repair`, and `reindex` with confirmation on mutating repair/reindex and non-zero exit status for failed non-interactive runs. `doctor` never mutates.

## 100240. Multi-host sync protocol · `1.5×` · [phase-100240-multi-host-sync-protocol.md](phase-100240-multi-host-sync-protocol.md)

Implement client/server incremental sync alone: `sync_serve`, `sync_push`, `sync_pull`, `sync_status`, cursors, idempotent apply, auth outside dev mode, optional client-side encryption compatible with slice 100020 DEKs, bank scope, and a documented deterministic conflict rule. Trusted peer-admitted creates must not be rejected by local admission θ. Single-host deployments may omit this slice’s runtime, but the protocol remains a full effort unit when multi-host is claimed. Cursors/apply/DLQ/conflict: [phase-100240-appendix-sync-cursors-conflict.md](phase-100240-appendix-sync-cursors-conflict.md).

## 100250. Per-bank retention profiles with verbosity and batch dry-run · `1×` · [phase-100250-per-bank-retention-profiles.md](phase-100250-per-bank-retention-profiles.md)

Ship per-bank `retention_profile` objects with a `selective`/`balanced`/`permissive` verbosity knob, per-category threshold offsets, split write/read duplicate-tolerance knobs, and a read-only batch `admit_preview` dry-run. Gap remediation for Hindsight-style noise overcapture at the write gate.

## 100260. Retention mission policy and coding-agent first-run defaults · `1×` · [phase-100260-retention-mission-coding-defaults.md](phase-100260-retention-mission-coding-defaults.md)

Ship upgrade-safe per-bank retention missions with keep/drop examples that deterministically steer admission utility, plus a quiet-by-default coding-agent profile that drops routine status chatter. Deterministic policy, not an LLM prompt.

## 100270. Consolidated-only recall preset and prefer-consolidated dedup · `1×` · [phase-100270-consolidated-recall-dedup.md](phase-100270-consolidated-recall-dedup.md)

Ship `consolidated_only` recall scope, `prefer_consolidated` supersede-plus-backfill, and a page-local near-duplicate cap with per-request counters. Depends on canonical/hub provenance links (slices 100060/100130) with a documented no-links fallback.

## 100280. HTTPS transport and provider configuration plumbing · `1×` · [phase-100280-https-transport-config.md](phase-100280-https-transport-config.md)

Replace the `http://`-only hand-rolled transport with one TLS-capable JSON client (ureq, operator-approved) behind the existing `post_json`/`get_ok` contract, and add the config/credential/env plumbing for providers: `embed.provider`, `rerank.provider`, `rerank.url`, `rerank.model`, `credentials.rerank_api_key`, plus `EMBED_*`/`RERANK_*` env knobs and masking. No adapters yet. Gap `gap/zero-deps.md` Phase 100010 + Phase 100030/100040 plumbing. Split from the former single zero-dependency phase.

## 100290. Multi-model embedding storage and embed providers · `1.5×` · [phase-100290-multi-model-embeddings.md](phase-100290-multi-model-embeddings.md)

Remove the hardcoded 384-dimension pin so any embedding model/provider can be configured (default stays `bge-small-en-v1.5`/384): an active embedding space `(model_id, dims)` in `schema_settings`, dimension-agnostic vector DDL with a purge-and-rebuild on space switch restricted to derived vectors, an index-availability policy by width (HNSW ≤ 2000 dims), and TEI + OpenAI-compatible embed adapters. One active space at a time (operator decision). Operator finding #1 + gap embed portion.

## 100300. Rerank provider adapters · `1×` · [phase-100300-rerank-providers.md](phase-100300-rerank-providers.md)

Add the Cohere-compatible rerank adapter (`POST /v1/rerank`, `results[].index`) alongside the existing TEI `POST /rerank`, selected by `rerank.provider`, plus a reranker factory resolving url/model/bearer from effective config. Reuses the Phase 100280 transport; keeps the full-permutation and fail-open contracts. Live attachment is Phase 100340. Split from the former single zero-dependency phase.

## 100310. Zero-config default database path with full precedence · `1×` · [phase-100310-default-database-path.md](phase-100310-default-database-path.md)

Ship one shared database-path/precedence resolver so `am mcp stdio` persists to `$XDG_DATA_HOME/am/clio.db` (fallback `~/.local/share/am/clio.db`) with no flags, honoring `--db` > `DATABASE_URL`/`AM_DATABASE_URL` > `AM_DATA_DIR` > XDG default, with backend inferred from the URL scheme. Config and CLI agree; help shows the default. Gap `gap/default-sqlite.md`, extended by operator decision.

## 100320. Embedded Docker lifecycle (`am compose up|down`) · `1×` · [phase-100320-compose-lifecycle.md](phase-100320-compose-lifecycle.md)

Move Docker management into the binary: `am compose up`/`down` with OS/arch detection, embedded compose material materialized at the project root, secure `.env` generation, service selection mapped to Compose profiles, and `docker` CLI invocation. Gap `gap/am-setup.md` Docker portion. Split from the former single `am setup` + compose phase.

## 100330. `am setup` first-run wizard · `1.5×` · [phase-100330-am-setup-wizard.md](phase-100330-am-setup-wizard.md)

Move first-run configuration into the binary: `am setup` with three install types (zero-dependency, airgapped, custom) writing a backed-up deployment JSON overlay, detecting existing values, orchestrating Phase 100320 for local services, and a default deployment-config path the binary loads without an env var. Gap `gap/am-setup.md` setup portion. Split from the former single `am setup` + compose phase.

## 100340. Hosted extraction adapter · `1.5×` · [phase-100340-hosted-extraction-adapter.md](phase-100340-hosted-extraction-adapter.md)

Add an OpenAI-compatible chat-completions `Extractor` that reproduces the local NuExtract `{snapshot, gist}` contract with a deterministic prompt and fail-closed output validation, reusing the Phase 100280 transport. Wire `extract.provider`, `credentials.extract_api_key`, and `EXTRACT_*` env vars; keep FR-4 span verification and PR-4 gist rules unchanged. Ships the adapter and factory; live wiring is Phase 100350. Deferred from the zero-dependency provider phases by operator decision.

## 100350. Live index, rerank, and extraction wiring · `1.5×` · [phase-100350-live-index-extraction-wiring.md](phase-100350-live-index-extraction-wiring.md)

Close the gap between "the pipelines exist" and "the running server uses them": drain the durable `index_pending` outbox (dense + lexical, with a lexical-only fallback when no embedder is configured) off the write path, attach the configured reranker to the retriever, resolve providers from effective config, and run extraction over raw turns through span verification and the gated store. Operator finding #2. Without this, a normally stored item is not retrievable and configured providers have no runtime effect.

---

## Remediation phases 100360–100520

Added 2026-09-22 from the gap register in `gap/requirement-gaps.md` (build plan, not a second requirements document). These phases close the remaining requirement gaps after the first 35 slices: two P0 binding breaks, the live-path evidence gaps, historical and temporal-invariant gaps, and the deferred acceptance, benchmark, provider, and scale work. This block uses even numbers only, except that **slots 100362–100378 are reserved for the follow-up CLI phases below**; future remediation phases continue above 100520 or use the remaining odd range. Order is primary build dependency: 100360 → 100380 → 100400 → 100440 → 100460 → 100480, with 100420 parallel to 100380–100400 and 100500/100520 parallel to 100440–100500.

| Phase | Scope | Effort | Implementation plan | Gaps |
|------:|-------|--------|---------------------|------|
| 100360 | Coverage guard for the per-file lines/functions floor | ~0.5 day | [phase-100360-coverage-guard.md](phase-100360-coverage-guard.md) | G-04 |
| 100380 | Bind `summarize` and the six FR-32 config/ranking tools; NFR-7 test | ~4–5 days | [phase-100380-binding-closure.md](phase-100380-binding-closure.md) | G-01, G-02, G-17, G-18 |
| 100400 | Postgres drain, stdio proof, backlog/log assertions, flake closure | ~4–5 days | [phase-100400-live-path-hardening.md](phase-100400-live-path-hardening.md) | G-06a–G-06f |
| 100420 | Phase 100060 close-out, 100030/100050 adversary pass, open-edge constraint, MemTree decision | ~3–5 days | [phase-100420-history-temporal-invariant.md](phase-100420-history-temporal-invariant.md) | G-05, G-07, G-08, G-09 |
| 100440 | Extraction fidelity ≥99% held-out; separate latency metrics | ~4–7 days | [phase-100440-fidelity-latency-acceptance.md](phase-100440-fidelity-latency-acceptance.md) | G-11, G-12 |
| 100460 | Benchmark spike: dataset and judge selection | ~2–3 days | [phase-100460-benchmark-spike.md](phase-100460-benchmark-spike.md) | G-10 (spike) |
| 100480 | Benchmark runner build: LongMemEval-style and LoCoMo-style | ~6–9 days | [phase-100480-benchmark-runner-build.md](phase-100480-benchmark-runner-build.md) | G-10 (build) |
| 100500 | First real provider ingest adapter (spike-gated) | ~5–7 days | [phase-100500-first-provider-adapter.md](phase-100500-first-provider-adapter.md) | G-03 |
| 100520 | Scale ceilings, TLS pooling, deployment docs | ~4–5 days | [phase-100520-scale-ceilings-docs.md](phase-100520-scale-ceilings-docs.md) | G-13, G-14, G-15, G-16 |

Critical path: 100360 → 100380 → 100400 → 100440 → 100460 → 100480. Total 33–47 ideal days plus review latency (see `gap/requirement-gaps.md` §4). The `batch` widening stays in the backlog as an enhancement.

---

## Follow-up phases 100362–100378

Added 2026-09-22 from the human-facing CLI/UX gap set in `gaps/` (`am-status.md`, `http-bind-auto.md`, `full-cli.md`). These close CLI usability gaps rather than `requirement.md` behavior gaps, and are sized to **≤3 ideal days** each. Even numbers are used per operator instruction; the reserved 100362–100378 slots are documented in the remediation intro above. Order is primary dependency: 100362 and 100364 are parallel (100362 uses interim rendering until 100366 lands); full-cli follows 100366 → 100368 → 100370 → 100372, then 100374/100376 reuse the confirm gate, and 100378 completes the catalog. Two cross-cutting decisions are recorded in the phases: CLI verbs are **binding syntax** (aliases such as `recall`→`retrieve`, `remember`→`store`) with each verb's tool name printed in `help`/`help --json`, and new verbs MUST NOT collide with the reserved top-level verbs (`compose` included — `compose_context` is bound as `compose-context`). Per-command ownership lives in [command-ownership.md](command-ownership.md).

| Phase | Scope | Effort | Implementation plan | Gaps |
|------:|-------|--------|---------------------|------|
| 100362 | `clio status` unified read-only health command | ~1 day | [phase-100362-clio-status-unified-health.md](phase-100362-clio-status-unified-health.md) | `gaps/am-status.md` |
| 100364 | `clio mcp http` auto-bind + `34300-34309` port scan | ~1 day | [phase-100364-mcp-http-auto-bind-port-scan.md](phase-100364-mcp-http-auto-bind-port-scan.md) | `gaps/http-bind-auto.md` |
| 100366 | CLI core plumbing (parser/output/exit/errors, `help --json`) + retrieval reads | ~3 days | [phase-100366-full-cli-core-and-retrieval-reads.md](phase-100366-full-cli-core-and-retrieval-reads.md) | `gaps/full-cli.md` §5, §7 step 1 |
| 100368 | CLI history/graph/workspace read surface | ~3 days | [phase-100368-full-cli-history-graph-reads.md](phase-100368-full-cli-history-graph-reads.md) | `gaps/full-cli.md` §6, §7 step 1 |
| 100370 | CLI safe core writes (`remember`, `admit`/`admit --file`, triples, beliefs, graph, summarize, consolidate) | ~3 days | [phase-100370-full-cli-safe-core-writes.md](phase-100370-full-cli-safe-core-writes.md) | `gaps/full-cli.md` §7 step 2 |
| 100372 | CLI safe workspace/harness writes (persona, task, scratchpad, canonical, shared, batch) | ~3 days | [phase-100372-full-cli-safe-workspace-writes.md](phase-100372-full-cli-safe-workspace-writes.md) | `gaps/full-cli.md` §7 step 2 |
| 100374 | CLI confirmed memory mutations (`update`, `invalidate`, `discard`, `correct`) | ~2 days | [phase-100374-full-cli-confirmed-memory-mutations.md](phase-100374-full-cli-confirmed-memory-mutations.md) | `gaps/full-cli.md` §7 step 3 |
| 100376 | CLI hygiene + portability/compliance (`hygiene_*`, `export`, `import`, `erase`) | ~3 days | [phase-100376-full-cli-hygiene-portability-compliance.md](phase-100376-full-cli-hygiene-portability-compliance.md) | `gaps/full-cli.md` §6, §7 step 3 |
| 100378 | CLI configuration/ranking + sync (`config_*`, `ranking_*`, `sync_*`) | ~2 days | [phase-100378-full-cli-config-ranking-sync.md](phase-100378-full-cli-config-ranking-sync.md) | `gaps/full-cli.md` §6 |

Critical path: 100366 → 100368 → 100370 → 100372. 100364 is independent; 100362 is parallel but uses interim rendering until 100366 lands, then reconciles to the shared output contract. 100378 depends on Phase 100380 (shared config dispatch) and Phase 100240 (sync tools). Per-command ownership (one command, one phase) is tracked in [command-ownership.md](command-ownership.md).

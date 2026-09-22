# Crates Workspace Structure

## Workspace Structure

```
clio/                               # workspace root
├── Cargo.toml                       # [workspace] members = ["crates/*"]
│
└── crates/                          # all sub-crates live here
    ├── clio-types/                    # Pure types, enums, traits, error shapes
    │   └── src/                     #   Zero I/O deps. Everything depends on this.
    │                                #   MemoryItem, EpisodicTriple, FailureRecord,
    │                                #   BeliefObject, PersonaDocument, Category,
    │                                #   EpistemicKind, UpdateRule, Interval types,
    │                                #   AdmissionFactors, BankId, ActorId,
    │                                #   AmError, ErrorCode, ToolResult, Bank, Actor,
    │                                #   OpContext, BankDefaultPolicy
    │
    ├── clio-config/                   # Config loading, profiles, ranking env
    │   └── src/                     #   Effective config resolution (Runtime),
    │                                #   secret masking, named profiles,
    │                                #   ranking_env_* knobs, weight normalization,
    │                                #   tool inventory packaging
    │                                #   Depends on: clio-types
    │
    ├── clio-store/                    # Dual-backend persistence
    │   └── src/                     #   Postgres+pgvector backend
    │                                #   SQLite backend (sqlite-vec extension)
    │                                #   DEK interface, content encryption hooks
    │                                #   CRUD for items, triples, assoc_edges
    │                                #   Depends on: clio-types, clio-config
    │                                #   Slices 100020, 3, 8 (triple persistence)
    │                                #   Modules: postgres.rs, sqlite.rs, dek.rs, bootstrap.rs
    │                                #   Graph shelf: assoc_edges / assoc_kind (≠ edges / edge_kind)
    ├── clio-admission/                # Category gate + five-factor scoring
    │   └── src/                     #   Category whitelist, five-factor formula,
    │                                #   threshold management, admit_preview
    │                                #   Pure logic, no I/O. Testable in isolation.
    │                                #   Depends on: clio-types, clio-config
    │                                #   Slices 100040
    │
    ├── clio-write/                    # Write path orchestration (includes extraction)
    │   └── src/                     #   Online extraction + span verification
    │                                #   Parallel chunk extraction coordination,
    │                                #   canonical fact consolidation,
    │                                #   MemTree (hierarchical temporal index),
    │                                #   dirty-path refresh, parallel summary refresh,
    │                                #   EMA update engine (shared, continuous)
    │                                #   Depends on: clio-store, clio-admission, clio-types
    │                                #   Slices 100050, 6, 7, 9
    │                                #   Modules: extraction.rs, consolidation.rs, memtree.rs, ema.rs
    │
    ├── clio-index/                    # Dense + lexical index pipelines
    │   └── src/                     #   Embedding sidecar client (TEI /embed),
    │                                #   item → embed/lexical text assembly,
    │                                #   BM25/lexical indexing via IndexStore,
    │                                #   pgvector / sqlite-vec vector index,
    │                                #   index outbox worker + rebuild hooks,
    │                                #   optional embedder (lexical-first job;
    │                                #   lexical-only when no embedder configured),
    │                                #   search primitives (dense/lexical)
    │                                #   Depends on: clio-store, clio-types, clio-config
    │                                #   Slices 100110
    │                                #   Modules: embed.rs, http.rs, worker.rs,
    │                                #            report.rs, search.rs
    │
    ├── clio-retrieve/                 # Retrieval, intent gate, co-activation, compose
    │   └── src/                     #   Intent gate classifier,
    │                                #   hybrid dense+lexical+graph retrieval,
    │                                #   co-activation reinforcement + decay + pruning,
    │                                #   hub distillation,
    │                                #   compose_context under token budget
    │                                #   Depends on: clio-store, clio-index, clio-types, clio-config
    │                                #   Slices 100120, 13
    │                                #   Modules: intent.rs, hybrid.rs, fusion.rs,
    │                                #            rerank.rs, filter.rs, finalize.rs,
    │                                #            compose.rs, surface.rs, types.rs, token.rs
    │
    ├── clio-persona/                  # Persona companion object (§4.7)
    │   └── src/                     #   Persona document storage + management,
    │                                #   stable entries (bi-temporal invalidation),
    │                                #   preference entries (EMA via clio-write),
    │                                #   token budget + ranked truncation,
    │                                #   always-on injection (not gated by intent gate)
    │                                #   Depends on: clio-store, clio-admission, clio-write, clio-types
    │                                #   Slices 100140
    │
    ├── clio-history/                  # Task, failure, temporal history
    │   └── src/                     #   FailureRecord CRUD,
    │                                #   task history, MemTree queries,
    │                                #   temporal_history
    │                                #   Depends on: clio-store, clio-types
    │                                #   Slices 100150
    │
    ├── clio-belief/                   # Belief evolution + confidence tracking
    │   └── src/                     #   Belief object storage (§4.10),
    │                                #   append-only confidence_history,
    │                                #   belief_observe / belief_history tools,
    │                                #   admission on create (five-factor),
    │                                #   append validation (no re-admission)
    │                                #   Depends on: clio-store, clio-admission, clio-types
    │                                #   Slices 100100
    │
    ├── clio-mcp/                      # MCP tool schemas + transport bindings
    │   └── src/                     #   JSON Schema tool definitions,
    │                                #   stdio transport,
    │                                #   Streamable HTTP transport,
    │                                #   tool dispatch/router,
    │                                #   runtime wiring: effective-config provider
    │                                #   resolution, outbox drain scheduler
    │                                #   (post-write nudge + periodic sweep),
    │                                #   retriever embedder/reranker attach,
    │                                #   MCP protocol revision pin (2025-11-25)
    │                                #   Depends on: all domain crates above
    │                                #   Slices 100160, 17
    │                                #   Modules: write_tools.rs, read_tools.rs, schema.rs, transport.rs
    │
    ├── clio-ops/                      # Doctor, repair, reindex
    │   └── src/                     #   diagnose / verify / doctor / repair / reindex
    │                                #   PII-safe health surfaces
    │                                #   Depends on: clio-store, clio-index, clio-types, clio-config
    │                                #   Slices 100230
    │
    ├── clio-hygiene/                  # Noise scoring, audit/cleanup, hygiene log
    │   └── src/                     #   hygiene_audit / hygiene_clean,
    │                                #   ranked noise candidates,
    │                                #   confirmed flag/archive/discard,
    │                                #   secret masking on all I/O,
    │                                #   durable hygiene audit log
    │                                #   Depends on: clio-store, clio-types, clio-config
    │                                #   Slices 100210
    │
    ├── clio-compliance/               # Erase path, export/import, audit trail
    │   └── src/                     #   erase_request (crypto-shredding),
    │                                #   export / import (JSON, manifest-backed),
    │                                #   audit_trail, inspect, correct
    │                                #   batch, scratchpad, canonical_*, shared_*, validate
    │                                #   Depends on: clio-store, clio-types, clio-config
    │                                #   Slices 100180, 19, 20, 22
    │                                #   Modules: audit.rs, erase.rs, workspace.rs, export.rs
    │
    ├── clio-sync/                     # Multi-host sync protocol
    │   └── src/                     #   sync_serve / sync_push / sync_pull / sync_status,
    │                                #   sync_ack_skip (operator DLQ ack),
    │                                #   cursors, idempotent apply, LWW conflict rule,
    │                                #   auth, client-side encryption, dead letters,
    │                                #   Depends on: clio-store, clio-config, clio-types
    │                                #   Modules: apply.rs, client.rs, clock.rs,
    │                                #            crypto.rs, http.rs, protocol.rs, server.rs
    │
    └── clio-lib/                      # Top-level facade + binary entrypoints
        └── src/                     #   Re-exports from sub-crates,
                                      #   process entrypoints (clio CLI),
                                     #   logging setup,
                                     #   bank/actor abstractions
                                     #   Depends on: all crates
```

## Dependency Graph

Arrow convention: `A → B` means "A depends on B" (A imports from B).

```
clio-types
  ↑
clio-config
  ↑
clio-store ←──────────────────────────────────────────────────────┐
  ↑                    ↑                    ↑                    ↑
clio-admission        clio-index            clio-history           clio-sync
  ↑                    ↑                                       ↑
clio-write ←───────── clio-retrieve                               │
  ↑                    ↑                                       │
clio-persona          clio-mcp ←── clio-ops ←── clio-hygiene ←── clio-compliance
                        ↑
                      clio-lib
```

### Per-crate dependency list

| Crate | Depends on | Notes |
|-------|-----------|-------|
| clio-types | _(none)_ | Zero external I/O deps. Pure types, enums, traits. |
| clio-config | clio-types | Config resolution, profiles, ranking env, secret masking. |
| clio-store | clio-types, clio-config | Dual-backend persistence, DEK interface, CRUD. |
| clio-admission | clio-types, clio-config | Category gate + five-factor scoring. Pure logic. |
| clio-index | clio-store, clio-types, clio-config | Embedding sidecar client, BM25/lexical + dense index, outbox worker, rebuild. |
| clio-write | clio-store, clio-admission, clio-types | Write orchestration, extraction, MemTree, EMA engine. |
| clio-retrieve | clio-store, clio-index, clio-types, clio-config | Intent gate, hybrid retrieval, co-activation, compose. |
| clio-persona | clio-store, clio-admission, clio-write, clio-types | Persona document, stable/preference storage, injection. |
| clio-history | clio-store, clio-types, clio-admission | Task, failure, temporal history records. |
| clio-belief | clio-store, clio-admission, clio-types | Belief objects, confidence history, admission on create. |
| clio-mcp | clio-store, clio-write, clio-retrieve, clio-persona, clio-history, clio-belief, clio-ops, clio-hygiene, clio-compliance, clio-sync, clio-types, clio-config | MCP tool schemas + transport bindings. |
| clio-ops | clio-store, clio-index, clio-types, clio-config | Doctor, repair, reindex. |
| clio-hygiene | clio-store, clio-types, clio-config | Noise scoring, audit/cleanup, hygiene log; reuses the shared secret masker. |
| clio-compliance | clio-store, clio-types, clio-config | Erase, export/import, audit trail, batch, workspace tools. |
| clio-sync | clio-store, clio-config, clio-types | Multi-host sync protocol. |
| clio-lib | all crates | Top-level facade, CLI entrypoint, logging. |

## Slice → Crate Mapping

| Slice | Effort | Target crate(s) | Notes |
|------:|--------|-----------------|-------|
| 1 | `1×` | clio-lib, clio-config, clio-types | Runtime shell, profiles, packaging |
| 2 | `1.5×` | clio-store | Dual-backend persistence, DEK interface |
| 3 | `1×` | clio-store | Memory item CRUD |
| 4 | `1×` | clio-admission | Category gate + five-factor scoring |
| 5 | `1×` | clio-write | Online extraction + span verification |
| 6 | `1×` | clio-write | Parallel write + canonical consolidation |
| 7 | `1×` | clio-write | MemTree + dirty-path maintenance |
| 8 | `1×` | clio-store, clio-write | Bi-temporal triples + supersession |
| 9 | `1×` | clio-write | Shared continuous EMA update engine |
| 10 | `1×` | clio-belief | Belief objects + confidence trajectories |
| 11 | `1×` | clio-index | Dense + lexical index pipelines |
| 12 | `1.5×` | clio-retrieve | Intent gate + hybrid retrieve + compose |
| 13 | `1×` | clio-retrieve | Co-activation associations + hub distillation |
| 14 | `1×` | clio-persona | Persona companion object (full: storage + injection) |
| 15 | `1×` | clio-history | Task, failure, temporal history |
| 16 | `1.5×` | clio-mcp | MCP schemas + write surface |
| 17 | `1×` | clio-mcp | MCP read + retrieve + compose surface |
| 18 | `1×` | clio-compliance | Audit trail + inspect + correction |
| 19 | `1×` | clio-compliance | Compliance erase path |
| 20 | `1×` | clio-compliance | Additive harness workspace tools |
| 21 | `1×` | clio-hygiene | Hygiene audit + confirmed cleanup |
| 22 | `1×` | clio-compliance | JSON export + import |
| 23 | `1×` | clio-ops | Ops doctor + repair |
| 24 | `1.5×` | clio-sync | Multi-host sync protocol |

## Current Code Mapping

How the existing `src/` files map to the target workspace crates:

| Current file | Target path | Notes |
|-------------|-------------|-------|
| `src/lib.rs` | `crates/clio-lib/src/lib.rs` | Crate root, re-exports, package identity |
| `src/main.rs` | `crates/clio-lib/src/main.rs` | `clio` binary CLI entrypoint |
| `src/log.rs` | `crates/clio-lib/src/log.rs` | Process log level, secret-safe emission |
| `src/error.rs` | `crates/clio-types/src/error.rs` | `AmError`, `ErrorCode`, `ToolResult` — pure types |
| `src/context.rs` | `crates/clio-types/src/context.rs` | `Bank`, `Actor`, `OpContext`, `BankDefaultPolicy` — pure types |
| `src/config/mod.rs` | `crates/clio-config/src/config/mod.rs` | `Runtime`, config/ranking tool handlers |
| `src/config/dispatch.rs` | `crates/clio-config/src/config/dispatch.rs` | Tool-name JSON dispatch |
| `src/config/merge.rs` | `crates/clio-config/src/config/merge.rs` | Overlay flatten/set primitives |
| `src/config/persist.rs` | `crates/clio-config/src/config/persist.rs` | File load/save |
| `src/config/validate.rs` | `crates/clio-config/src/config/validate.rs` | Path/value validation rules |
| `src/config/types.rs` | `crates/clio-config/src/config/types.rs` | Tool data types (`ConfigGetData`, etc.) |
| `src/config/tests.rs` | `crates/clio-config/src/config/tests.rs` | Config integration tests |
| `src/ranking.rs` | `crates/clio-config/src/ranking.rs` | `RankingEnv`, weight types, normalization |
| `src/secret.rs` | `crates/clio-config/src/secret.rs` | Secret path detection, masking logic |
| `src/profile.rs` | `crates/clio-config/src/profile.rs` | `Profile`, `ToolInventoryEntry`, coding inventory |

**Migration order:**
1. Create `crates/clio-types/` with `error.rs` + `context.rs` (zero deps, compiles instantly)
2. Create `crates/clio-config/` with `config/*` + `ranking.rs` + `secret.rs` + `profile.rs`
3. Create `crates/clio-lib/` with `lib.rs` + `main.rs` + `log.rs`, depending on clio-types + clio-config
4. All later crates build on this foundation

## Rationale

### Why these seams

- **clio-types** is its own crate because every other crate depends on it. Splitting it keeps compile times honest — changing a config struct doesn't recompile the store. Currently: `error.rs` + `context.rs`.
- **clio-store** absorbs slices 100020+3+8 because the DEK interface, backend abstraction, and triple persistence are one contract. Keeping persistence together avoids a trait-vs-impl split across crates for no benefit.
- **clio-write** absorbs extraction (slice 100050) because extraction is only called during the write path — it's too thin for a dedicated crate and has no independent callers. The shared EMA engine (slice 100090) lives here because it's a write-path concern; persona (slice 100140) calls into it, not reimplements it (per requirement §4.9.4.C).
- **clio-persona** owns the full persona companion object (slice 100140): storage of stable entries with bi-temporal invalidation, storage of preference entries with EMA, admission scoring on writes, token budget management with ranked truncation, and always-on injection. This is a distinct domain with its own data model and tool surface (persona_get, persona_put_stable, persona_observe_preference).
- **clio-belief** owns belief objects (slice 100100) because beliefs are a first-class domain concept: distinct from semantic categories and episodic types (§4.10), with their own admission rules (category gate N/A, five-factor on create only), their own data model (append-only confidence_history with source_type), and their own tool surface (belief_observe, belief_history).
- **clio-retrieve** owns intent gate, hybrid retrieval, co-activation, and compose (slices 100120+13). The persona always-on injection is NOT here — it lives in clio-persona, which is called by clio-mcp alongside clio-retrieve.
- **clio-history** is task, failure, and temporal history only (slice 100150). Beliefs are separated into clio-belief.
- **clio-hygiene** owns noise scoring, ranked audit, and confirmed cleanup (slice 100210) because it has its own data model (noise scores, hygiene audit log) and its own failure modes (secret masking on all I/O).
- **clio-compliance** owns the data lifecycle: crypto-shredding (slice 100190), export/import with manifests (slice 100220), audit trail (slice 100180), and workspace tools (slice 100200). These share "data governance" semantics.
- **clio-ops** is slimmed to doctor/repair/reindex only (slice 100230) — diagnostic and repair operations that read the store and produce findings.
- **clio-sync** is isolated because single-host deployments omit it entirely. Single-host note (§4.9.5.D / §4.9.6): if sync runtime is omitted, the deployment docs must say so plainly; the coding-agent profile skips the five sync tools (`sync_serve`, `sync_push`, `sync_pull`, `sync_status`, `sync_ack_skip`) via the profile's sync omission flag, and nothing in the single-host path depends on this crate.
- **clio-mcp** is the binding layer that wires all domain crates to MCP tool schemas and transports.

### Migration path

1. Create `crates/clio-types/` with `error.rs` + `context.rs` (zero deps, compiles instantly).
2. Create `crates/clio-config/` with `config/*` + `ranking.rs` + `secret.rs` + `profile.rs`.
3. Create `crates/clio-lib/` with `lib.rs` + `main.rs` + `log.rs`.
4. As each slice ships, extract into its target crate under `crates/`.
5. Workspace `Cargo.toml` uses `members = ["crates/*"]`; adding a new crate is automatic.

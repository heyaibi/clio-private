# Phase 100020: Dual-Backend Persistence with Encryption Hooks

### Attribution
| Role | Agent |
|------|-------|
| Developer | Cursor (Auto) |
| Adversary | Cursor (Auto) |

**Index slice 100020 · **Effort:** `1.5×` · **Scope:** `roadmap/index.md` slice 100020 (authoritative)

## 1. Objective

### Goal
Implement selectable **PostgreSQL + pgvector** and **SQLite** backends behind one behavioral persistence contract for memory items, graph/structure metadata, and vector slots. For SQLite vectors, use a real loadable **vector search** extension (e.g. sqlite-vec or equivalent)—not a pretend native pgvector. Phase 100020 acceptance is **storage hooks + exact/brute-force KNN capability** where the extension provides it; approximate ANN index performance is **not** required here (see `roadmap/phase-100020-appendix-vector-parity.md`). Store content payloads as ciphertext under a per-subject DEK interface from day one so compliance erase (later) does not retrofit every table. Backend choice MUST NOT fork product rules (`requirement.md` §0).

### Expected Outcome
- One storage abstraction with two selectable backends; same item/metadata/vector behavioral contract.
- Content fields written as ciphertext via a per-subject DEK interface (KMS separate from item store — §7.4).
- Schema/migrations exist for items, graph/structure metadata (SQL table `assoc_edges` with column `assoc_kind` ∈ {`coactivation`, `explicit`}; hub distillation is a write-path item, **not** an `assoc_kind`), and vector storage hooks.
- Switching backend via config (from Phase 100010) does not change API semantics.
- Documented vector parity ceilings recorded in this phase’s exit contract (exact KNN OK; ANN deferred).

### Parent Requirement
`requirement.md` (current) — §0 Supported storage backends; §7.4 field-level encryption / crypto-shredding prerequisites; FR-19 (DEK destruction path foreshadowed); vector ceilings in `roadmap/phase-100020-appendix-vector-parity.md`.

---

## 2. Scope Boundaries

### In Scope
- Dual-backend persistence driver selection (Postgres+pgvector, SQLite+vector extension).
- Unified repository contract for: item rows, graph/structure metadata, vector index hooks.
- Per-subject DEK interface: encrypt/decrypt content payloads; destroy-key hook stubbed for later erase slice.
- Migrations / schema bootstrap for both backends.
- Backend-agnostic error mapping into Phase 100010 error shapes.

### Explicitly Out of Scope
- Public write admission gates (Phase 100040) and full `store` tool (later).
- Online extraction / span verification (slice 100050).
- Hybrid retrieve, embeddings generation pipeline beyond storage hooks (slice 100110–12).
- Full `erase_request` UX and dirty-path regeneration (slice 100190) — only DEK *hooks* here.
- MemTree maintenance, triples supersession logic, MCP.

### Must Not Change
- Phase 100010 config/profile/`bank`/`actor` contracts.
- Requirement that backend choice does not weaken behavioral rules (§0).
- Separation of invalidation / discard / crypto-shred (§7.4) — do not conflate in schema design.

### Scope Expansion Rule
If work outside this scope appears necessary:
1. Stop.
2. Document the reason.
3. Request clarification or approval.
4. Do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- Phase 100010 accepted (or equivalent): effective config, backend hint, secret masking, `bank` context.
- Development environments can reach Postgres (for that backend’s tests) and local disk (SQLite).

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| Phase 100010 | Config + profiles available | Apply profile; read backend hint |
| PostgreSQL + pgvector | Available in CI/dev for Postgres suite | Extension present check |
| SQLite vector extension | Chosen and loadable | Load extension in test |
| DEK/KMS interface | Design approved for local/dev provider | Interface compiles; destroy hook exists |

---

## 4. Existing-System Discovery

The agent MUST inspect the existing system before deciding
where or how to implement the changes.

### Required Discovery
- Identify the subsystem(s) responsible for the relevant behavior.
- Locate the existing implementation of related capabilities.
- Identify existing interfaces, contracts, schemas, and boundaries.
- Identify relevant tests and verification mechanisms.
- Identify architectural conventions that must be followed.
- Confirm that the current system supports the proposed change.

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

### Task 1: Unified Persistence Contract

#### Intent
Define one behavioral repository API both backends implement.

#### Required Capability or Behavior
- Create/read/update/delete (or soft-state) primitives for memory item envelopes and metadata, scoped by `bank`.
- Graph/structure metadata includes durable SQL table `assoc_edges` (logical record: `assoc_edge`) even if co-activation algorithms come later (Phase 100130). Column `assoc_kind` is `coactivation` | `explicit` only — do not revive `edges` / `edge_kind` / `distilled`.
- Vector storage hooks exist (insert/delete/rebuild seam) without requiring a full embedding pipeline.

#### Architectural Responsibility
Persistence layer / storage ports.

#### Required Changes
1. Define backend-agnostic repository traits/interfaces.
2. Document invariants: bank isolation, id stability, ciphertext-at-rest for content.
3. Map storage errors to shared error codes.

#### Implementation Constraints
- No product-logic fork by backend (`if postgres { different admission }`).
- Do not expose plaintext content APIs that skip the DEK boundary.

#### Expected Result
Contract tests compile against both backends (even if one suite is feature-gated).

### Task 2: PostgreSQL + pgvector Backend

#### Intent
Ship the Postgres persistence path with pgvector for dense vectors.

#### Required Capability or Behavior
- Migrations create required tables including vector column/index hooks.
- Item content columns store ciphertext blobs (or equivalent), not plaintext prose/snapshots.
- Metadata allowed in plaintext per §7.4 (structure/timestamps/relationships).

#### Architectural Responsibility
Postgres adapter.

#### Required Changes
1. Schema + migrations (`sql/001_core.sql` portable DDL includes `assoc_edges` / `assoc_kind`; dialect vector SQL under `sql/002_vectors_*.sql`).
2. Repository implementation.
3. pgvector extension dependency documented for operators.

#### Implementation Constraints
- Use parameterized queries; no string-concat SQL.
- Follow project SQL guidelines when writing SQL.

#### Expected Result
Integration tests against Postgres pass for CRUD + vector row insert/delete.

### Task 3: SQLite + Vector Extension Backend

#### Intent
Ship SQLite path with a real loadable vector-search extension.

#### Required Capability or Behavior
- Same behavioral contract as Postgres.
- Vector extension is actually loaded and used for vector slots (not a float-blob pretend index claimed as pgvector-equivalent).
- Exact/brute-force KNN (or equivalent query API the extension documents) is sufficient for Phase 100020 hooks.
- Do **not** require alpha ANN indexes (e.g. experimental DiskANN/IVF builds) for phase exit.

#### Architectural Responsibility
SQLite adapter.

#### Required Changes
1. Schema + migrations appropriate to SQLite.
2. Extension load path configurable via Phase 100010 config.
3. Repository implementation matching the shared contract.
4. Record chosen extension name/version and ceilings from `roadmap/phase-100020-appendix-vector-parity.md` in completion evidence.

#### Implementation Constraints
- If extension load fails, fail loudly with operator guidance — do not silently degrade to “no vectors” while claiming parity.
- Early query-scale ceilings may be incomplete vs Postgres+pgvector ANN indexes; storage hooks MUST exist (slice 100110 may deepen indexing).

#### Expected Result
Integration tests on SQLite with extension loaded pass parity suite for **hooks + exact KNN**, not ANN throughput parity.

### Task 4: Per-Subject DEK Interface

#### Intent
Install encryption-at-rest hooks required by §7.4 so later erase is crypto-shred, not table rewrites.

#### Required Capability or Behavior
- Each data subject maps to a DEK held outside the item store (interface may use a local/dev KMS).
- Encrypt content on write; decrypt on authorized read.
- `destroy_dek(subject_id)` (or equivalent) exists and renders ciphertext unreadable; Phase 100190 will orchestrate legal erase around it.
- Config/diagnostics NEVER print DEK material (masking from Phase 100010).

#### Architectural Responsibility
Crypto / KMS boundary separate from persistence adapters.

#### Required Changes
1. DEK provider interface + at least one dev implementation.
2. Envelope format for ciphertext (subject id, key version, nonce, ciphertext).
3. Wire repository writes/reads through encrypt/decrypt.
4. Destroy-key API with tests proving unreadability after destroy.

#### Implementation Constraints
- Do not implement full `erase_request` tombstones/dirty-path regen here.
- Bi-temporal *structure* MAY remain plaintext; *content* MUST NOT.

#### Expected Result
Round-trip encrypt/decrypt tests; post-destroy decrypt fails; store never persists plaintext content fields.

### Task 5: Backend Selection and Parity Harness

#### Intent
Make backend choice a deployment config switch with automated parity checks.

#### Required Capability or Behavior
- Config selects backend; process opens the matching driver.
- A shared behavioral test suite runs against both backends (CI may matrix).

#### Architectural Responsibility
Wiring between Phase 100010 config and persistence bootstrap.

#### Required Changes
1. Bootstrap from effective config.
2. Parity tests for bank isolation, ciphertext round-trip, metadata vs content split.
3. Operator notes for extension/pgvector prerequisites (keep minimal; no drive-by docs sprawl unless required for phase exit).

#### Implementation Constraints
- Do not fork FR/admission behavior by backend.
- Dependency additions require approval if beyond what is needed for drivers/extensions.

#### Expected Result
Documented command(s) to run Postgres suite and SQLite suite; both green on AC.

### Implementation Freedom
The agent may choose the concrete implementation structure,
file locations, naming, and internal design provided that:
- The required behavior is satisfied.
- Architectural boundaries are respected.
- Existing contracts are preserved.
- All acceptance criteria pass.
- No prohibited changes are introduced.

---

## 6. Agent Execution Rules

### Allowed Actions
- Inspect and modify the repository as required to implement
  the in-scope capabilities.
- Add or update implementation components where appropriate.
- Add or update tests required to verify the behavior.
- Refactor locally when necessary to implement the specified
  capability without changing unrelated behavior.

### Forbidden Actions
- Change public contracts without approval.
- Delete or bypass tests.
- Disable security controls.
- Introduce unrelated features.
- Perform unrelated broad refactoring.
- Upgrade dependencies without approval.
- Commit secrets.
- Claim completion without evidence.

### Agent Decision Boundary
The agent may decide:
- Concrete file/module/class placement.
- Internal implementation structure.
- Local refactoring required for the phase.
- Test organization.
- Non-breaking implementation details.
- Which SQLite vector extension to use, if not already fixed by an approved spike — document the choice in completion evidence.

The agent must request approval for:
- Architecture changes beyond the stated scope.
- Breaking API or data-contract changes.
- Security-sensitive policy decisions (e.g. storing DEKs beside ciphertext).
- Destructive data operations.
- Changes affecting downstream phase assumptions.

### Mandatory Stop Conditions
Stop and report if:
- Requirements are ambiguous.
- Repository facts contradict the plan.
- Required dependencies are missing.
- Scope expansion is required.
- A destructive migration is necessary but unspecified.
- Existing architecture cannot support the intended behavior
  without an unapproved structural change.
- Correctness cannot be verified.
- No viable SQLite vector extension can be loaded in target environments.

---

## 7. Security Constraints

### Required Controls
- Content encryption under per-subject DEK; KMS separate from item DB.
- Parameterized queries; least-privilege DB roles in documented defaults where applicable.
- Secret/DEK masking in all diagnostics.

### Sensitive Data Rules
- Never log DEKs, plaintext snapshots/gists, or raw credentials.
- Never commit real DEKs or production connection strings.
- Use approved secret/configuration mechanism for DB URLs and KMS material.

### Security Acceptance Conditions
- After DEK destroy, content reads fail closed.
- Plaintext content absent from on-disk DB inspection in tests.
- Backend switch cannot disable encryption.

---

## 8. Test and Verification Strategy

### Required Tests
- [x] Unit tests
- [x] Integration tests
- [x] Contract tests
- [x] End-to-end tests
- [x] Regression tests
- [x] Security tests
- [x] Failure-mode tests

### Required Test Scenarios

| Test ID | Scenario | Expected Result |
|---------|----------|-----------------|
| T100020-01 | CRUD item envelope on Postgres | Success; bank-scoped |
| T100020-02 | CRUD item envelope on SQLite | Success; bank-scoped |
| T100020-03 | Content written then read | Decrypt equals plaintext input |
| T100020-04 | DEK destroyed then read | Decrypt fails; no plaintext recovery |
| T100020-05 | Cross-bank read | Isolated / not found |
| T100020-06 | Vector hook insert/delete both backends | Succeeds with real extension/pgvector (exact KNN OK) |
| T100020-07 | Wrong/missing vector extension (SQLite) | Loud failure, not silent pretend mode |
| T100020-08 | Config backend switch | Opens matching driver; same contract tests apply |

### Negative Testing
Verify that:
- Invalid input is rejected.
- Unauthorized cross-bank access is blocked.
- Partial failures are handled safely (transaction boundaries).
- Duplicate id / retry behavior is correct.
- Phase 100010 tests remain intact.
- Failure does not leave mixed plaintext/ciphertext rows undocumented.

### Verification Rule
Implementation claims must be supported by actual test output,
inspection results, or other concrete evidence.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-100020-01 | Shared contract implemented on both backends | Contract/integration tests | Dual-suite pass logs |
| AC-100020-02 | Postgres+pgvector path works | Integration tests | Test output |
| AC-100020-03 | SQLite + real vector-search extension works (exact KNN OK; ANN not required) | Integration tests | Extension load + test output |
| AC-100020-04 | Content stored encrypted under DEK interface | Security/unit tests | Ciphertext inspection + round-trip |
| AC-100020-05 | DEK destroy renders content unreadable | Security test | Post-destroy failure assertion |
| AC-100020-06 | Backend choice does not fork behavior | Parity suite | Same assertions both backends |
| AC-100020-07 | Secrets/DEKs masked in diagnostics | Security test | Mask assertion |

### Definition of Done
- [x] All in-scope behavior is implemented.
- [x] All acceptance criteria pass.
- [x] Required tests pass.
- [x] No unauthorized changes were introduced.
- [x] Existing behavior remains intact.
- [x] Security checks pass.
- [x] Documentation is updated where required.
- [x] Evidence is collected.
- [x] Verification is completed.
- [x] Required approval is obtained.

### Completion Evidence
- **Implementation summary:** New `clio-store` crate — `Store` trait, `SqliteStore` (sqlite-vec exact KNN), `PostgresStore` (pgvector), `LocalDevKms` DEK provider, `BlockingAsyncStore` async bridge (`spawn_blocking`), config bootstrap via `StoreOpenOptions` / `open_store`.
- **Discovered/affected:** `sql/001_core.sql` graph shelf renamed to `assoc_edges`/`assoc_kind`; compose mounts `./sql/`; CI Postgres service; Makefile `DATABASE_URL` default matches Compose `clio`.
- **Changed-component summary:** `clio-store`, `clio-config` store keys, `clio-lib` re-export, compose/CI/Makefile/`.env.example`, roadmap vocab sync, `./coverage.md`, `AGENTS.md` coverage pointer.
- **Test execution:** `cargo test -p clio-store` / workspace `make check` (fmt + clippy `-D warnings` + test). Coverage gate: `make coverage` (lines + functions ≥90% per `./coverage.md`; regions not gated).
- **Chosen SQLite vector extension:** [`sqlite-vec`](https://github.com/asg017/sqlite-vec) Rust crate `0.1` (workspace), loaded via `sqlite3_auto_extension` / `vec0` virtual table; `vec_version()` probed at open.
- **Migration/schema evidence:** portable `sql/001_core.sql` + `sql/002_vectors_{postgres,sqlite}.sql` applied on open; Compose init mounts the same files.
- **Verification report:** AC-100020-01–AC-100020-07 covered by `parity_tests` + edge modules; T100020-07 fails closed via `sqlite_vec_missing` / registration `Result`.
- **Known limitations:** see §12; async API is a blocking-pool bridge (not native `sqlx`/`deadpool` drivers yet).

---

## 10. Failure Handling and Recovery

### Expected Failure Modes

| Failure | Detection | Recovery |
|---------|-----------|----------|
| Migration failure | Migrate error | Abort boot; do not half-apply without record |
| Extension missing | Load error | Fail boot/tests with operator message |
| KMS unavailable | Encrypt/decrypt error | Fail closed on content ops |
| Backend misconfigured | Bootstrap error | Refuse start; keep prior data untouched |

### Rollback Strategy
Roll back migrations with documented down scripts where safe; otherwise restore DB from backup taken before migrate. Application code reverts via git. Destroyed DEKs are not recoverable by design — only use destroy in tests or with disposable subjects during this phase.

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
| §0 dual backends | Tasks 1–3, 5 | T100020-01, T100020-02, T100020-08 | AC-100020-01–AC-100020-03, AC-100020-06 |
| §7.4 DEK / crypto-shred prep | Task 4 | T100020-03, T100020-04 | AC-100020-04, AC-100020-05 |
| FR-19 (prerequisite hooks) | Task 4 | T100020-04 | AC-100020-05 |
| FR-32 backend hints | Task 5 | T100020-08 | AC-100020-06 |

Required chain:

```text
Requirement → Capability → Implementation → Test → Evidence
```

Every acceptance criterion must be traceable.

---

## 12. Phase Exit Contract

### Outputs Produced
- Dual-backend persistence with shared contract.
- Ciphertext content storage via per-subject DEK interface.
- Graph shelf: SQL `assoc_edges` + `assoc_kind` ∈ {`coactivation`, `explicit`} (not SPO triples; not hub-`distilled` as a kind).
- Vector storage hooks on both backends (sqlite-vec exact KNN; pgvector hooks).

### Guarantees Provided to Downstream Phases
After this phase is accepted:
- Phase 100030 can implement item repository semantics on the shared contract without choosing a backend.
- Later erase can call DEK destroy without redesigning tables.
- Index/retrieve slices can attach to existing vector hooks.

### Known Limitations
- Embedding generation / hybrid search not implemented (slice 100110–12).
- `erase_request` orchestration and tombstones not implemented.
- Graph algorithms and MemTree not implemented (`assoc_edges` shelf only; co-activation write loop is Phase 100130).
- **Sync drivers + async bridge:** `Store` remains synchronous (`rusqlite` / `postgres`). Tokio callers use `BlockingAsyncStore` (`spawn_blocking`). Native async pools (`deadpool` / `tokio-postgres` / `sqlx`) are the upgrade when multiplexed concurrent DB I/O is required.
- **SQLite bank-scoped KNN:** sqlite-vec cannot put `bank_id` in the MATCH WHERE clause; `knn_in_bank` widens the global fetch until the in-bank top-k is filled or the neighbor set is exhausted (not a fixed over-fetch heuristic).
- **Vector parity ceilings** (see `roadmap/phase-100020-appendix-vector-parity.md`):
  - SQLite path: stable sqlite-vec exact/brute-force KNN is acceptable; do not block on ANN alpha features.
  - Postgres path: pgvector indexes MAY offer ANN; Phase 100020 only requires behavioral hook parity, not equal p95 at million-vector scale.
  - Scale expectation for SQLite exact KNN in first release: comfortable for tens–low hundreds of thousands of vectors; multi-million ANN is out of Phase 100020 scope.
  - Upgrade path: slice 100110 may adopt ANN when an extension build is production-stable; document the choice then.

### Downstream Prerequisites
- Phase 100030 MUST write snapshots/gists through ciphertext content fields.
- Phase 100040 MUST NOT open a plaintext side channel around the store.

### Final Status
**PASS WITH DOCUMENTED LIMITATIONS** (2026-09-17)

### Verification Sign-Off

- Implementer: Cursor (Auto) — Phase 100020 + adversarial-review remediation
- Verifier: pending human
- Human Approver: approved (2026-09-17)
- Date: 2026-09-17

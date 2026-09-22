# Phase 100070: MemTree and Dirty-Path Maintenance

### Attribution
| Role | Agent |
|------|-------|
| Developer | Cursor Agent CLI (auto) |
| Adversary | Antigravity CLI (Gemini 3.8 Flash) |
| Remediator | OpenCode CLI (GLM-5.3 Flash High) |
| Remedy Approver | Antigravity CLI (Gemini 3.8 Flash) |

**Index slice 100070 · **Effort:** `1×` · **Scope:** `roadmap/index.md` slice 100070 (authoritative)

## 1. Objective

### Goal
Organize episodic memory as **time-ordered trees (MemTree)** and refresh only **dirty ancestor paths**, with **parallel same-depth updates** (§4.3 steps 3–5). Expose `maintenance_status` and `consolidate` so agents can inspect and trigger non-blocking structure work (FR-28 / §4.9.4.A). Leaf readability from Phase 100060 MUST remain intact (FR-3 / PR-9).

### Expected Outcome
- Episodic leaves attach into a hierarchical temporal index: leaves = granular units; internal nodes = interval aggregates; root = coarsest view.
- On leaf insert/update, only the leaf→root ancestor chain is marked dirty (not a global rewrite).
- Dirty marks coalesce; refresh proceeds bottom-up by tree level; same-depth dirty nodes refresh concurrently.
- `maintenance_status(item_id?)` reports whether the leaf is queryable and which ancestors are dirty/refreshing.
- `consolidate(scope?, force?)` triggers dirty-path / parallel ancestor refresh (and MAY enqueue eligible hub distillation later—hub logic itself is slice 100130); MUST NOT block new leaf writes.
- `memtree_query` / `memtree_get` provide selective hierarchical access (§4.9.4.D) sufficient for structure inspection (full hybrid retrieve remains later).

### Parent Requirement
`requirement.md` (current) — P2, PR-9, §4.3 steps 3–5, §4.8 episodic retrieval pattern, §4.9.4.A `maintenance_status` / `consolidate`, §4.9.4.D `memtree_query` / `memtree_get`, FR-3, FR-27 (memtree tools), FR-28, NFR-2.

### Design references (non-normative)
- MemTree dirty-path refresh, level-parallel bottom-up recompute, coalesced dirty marks: [MemForest](https://arxiv.org/html/2605.23986v2); implementation sketch in [Concyclics/MemForest `tree_builder`](https://github.com/Concyclics/MemForest).
- Persistent state vs derived artifacts: tree structure + leaf facts are durable; interval summaries (and later embeddings) are regenerable derived artifacts—refresh only affected paths.
- Algorithmic note: for balanced k-ary trees, a single insertion dirties O(log N) ancestors; total work scales with distinct dirty nodes, not full corpus rewrite. End-to-end latency is not claimed logarithmic once extraction/IO dominate.

---

## 2. Scope Boundaries

### In Scope
- MemTree data model: nodes, parent links, time-ordered leaf placement, ancestor path computation.
- Structural insert of Phase 100060 canonical leaves into the tree (eager structure, lazy summary refresh).
- Dirty-path marking, coalescing, bottom-up level-parallel summary refresh.
- Tools (in-process OK until MCP): `maintenance_status`, `consolidate`, `memtree_query`, `memtree_get`.
- `summarize(scope)` MAY regenerate gists for dirty internal nodes without altering snapshots (PR-4 / §4.9.4.A)—if implemented, keep snapshot-safe.
- Preserve FR-3: leaf queryable even while ancestors dirty.

### Explicitly Out of Scope
- Parallel chunk extraction / canonical merge design (owned by slice 100060; consume its handoff).
- Bi-temporal triples / supersession (slice 100080).
- Co-activation edges and hub distillation execution (slice 100130)—`consolidate` MAY expose a hook/flag but MUST NOT claim full Hebbian distillation done.
- Dense NodeIndex / RootIndex ANN performance (slice 100110+); summaries text-first is enough here.
- Intent gate, hybrid retrieve, compose (slice 100120).
- Multi-scope forest (session/entity/scene) as three mandatory product trees—MAY start with one primary episodic/session tree; additional scopes only if cheap and non-blocking. Do not expand into a research port of all MemForest views without approval.

### Must Not Change
- Phase 100060 leaf-first readability and gated admit path.
- Phase 100050 span verify / Phase 100040 gates.
- Snapshot vs gist authority (ancestor summaries are non-authoritative for exact values).
- PR-9: `consolidate` must not block new leaf writes.

### Scope Expansion Rule
If work outside this scope appears necessary:
1. Stop.
2. Document the reason.
3. Request clarification or approval.
4. Do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- Phase 100060 accepted: canonical leaves + maintenance handoff + leaf queryability.
- Phase 100030–005 accepted for item content and fidelity.

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| Canonical leaf writes | Produce leaf ids + dirty signals | Phase 100060 tests |
| Item get_snapshot/get_gist | Available for leaf evidence | Phase 100030 tests |
| Background task runner | Can run refresh without blocking requests | Smoke |
| Tool surface registry | Can bind new tool handlers | Phase 100010 inventory |

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
- Inspect Phase 100060 maintenance handoff event shape and leaf flags.

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

### Task 1: MemTree Structure and Leaf Attachment

#### Intent
Implement §4.3 step 3: hierarchical temporal index over episodic leaves.

#### Required Capability or Behavior
- Persist tree nodes: leaf nodes reference canonical item ids; internal nodes hold aggregated summary text (gist-class), time interval coverage, child pointers, dirty flag.
- **Locked defaults (MemForest-aligned):** max fan-out `k = 8` children per internal node (config override allowed); on overflow, split so each node stays ≤ `k`. Leaves are level 0; levels increase toward the root.
- Insert leaf in time order; rebalance/split only as needed to preserve fan-out bound.
- Placement map: item_id → leaf node_id for later maintenance and erase foreshadow (FR-19 dirty-path regeneration later).
- Root per bank (single primary episodic/session tree for this phase).

#### Architectural Responsibility
MemTree storage + structural editor.

#### Required Changes
1. Schema/migration for nodes and edges/paths.
2. Attach-leaf algorithm on Phase 100060 handoff with `k=8` split policy.
3. Tests for ordering, parent linkage, and fan-out splits.

#### Implementation Constraints
- Structural insert is eager; summary text refresh is lazy (dirty).
- Do not rewrite unrelated branches.
- Dual-backend parity: behavior identical on Postgres and SQLite (Phase 100020 contract).

#### Expected Result
After leaf write, a leaf node exists and is findable via `memtree_get` / path from root.

### Task 2: Dirty-Path Marking and Coalescing

#### Intent
Implement §4.3 step 4 without global invalidation.

#### Required Capability or Behavior
- On leaf attach/update, mark each ancestor to root dirty.
- **Coalesce:** maintain a set keyed by `node_id`; repeated marks before the next refresh wave count once. A refresh wave drains the set (or a snapshot of it) so overlapping writes share ancestor work.
- Leaves remain queryable while dirty=true on ancestors (FR-3).

#### Architectural Responsibility
Maintenance state machine on MemTree nodes.

#### Required Changes
1. Dirty bit + optional generation counter.
2. Coalesce set/queue keyed by node_id (MUST, not optional).
3. Instrumentation for dirty counts and coalesce hits.

#### Implementation Constraints
- Marking MUST be cheap and synchronous with structural insert; refresh is async.
- Never clear dirty before refresh successfully regenerates derived summary (or explicit empty children policy).

#### Expected Result
Two rapid inserts under same parent → parent dirty once in the coalesced set before refresh.

### Task 3: Parallel Same-Depth Ancestor Refresh

#### Intent
Implement §4.3 step 5: recompute dirty ancestors concurrently at the same depth.

#### Required Capability or Behavior
- Group dirty nodes by depth; refresh bottom-up (leaves depth 0 → root).
- Within a depth, refresh distinct dirty nodes in parallel (bounded concurrency).
- Refresh regenerates internal-node aggregate gist/summary from children; MUST NOT mutate child snapshots.
- After success, clear dirty for that node; failures leave dirty set and report via `maintenance_status`.

#### Architectural Responsibility
Maintenance worker / consolidator engine.

#### Required Changes
1. Level-parallel scheduler.
2. Summary regeneration function (deterministic template or LLM-backed gist—if LLM, document cost; provide deterministic fixture mode for CI).
3. Failure isolation per node.

#### Implementation Constraints
- MUST NOT block Phase 100060 leaf ingest on this scheduler.
- Ancestor summaries are non-authoritative for exact entities/numbers/dates (PR-4).
- Derived embeddings optional; text summary sufficient for this phase exit.

#### Expected Result
Fixture forest with multiple dirty branches refreshes same-depth nodes concurrently; root becomes clean after bottom-up pass.

### Task 4: `maintenance_status` and `consolidate` Tools

#### Intent
Make PR-9 inspectable and triggerable (FR-28 / §4.9.4.A).

#### Required Capability or Behavior
- `maintenance_status(item_id?)` → `{leaf_queryable, dirty_ancestors[], refreshing[], last_error?}`.
- `consolidate(scope?, force?)` → enqueues/triggers dirty-path refresh for scope (bank/tree/item path); returns job/accept status without waiting for full completion unless a documented `wait` debug flag exists (default non-blocking).
- `force` MAY re-dirty and refresh even if currently clean (test/repair aid).
- New leaf writes succeed while consolidate runs.

#### Architectural Responsibility
Tool/handler layer over maintenance engine.

#### Required Changes
1. Tool handlers + schemas for inventory.
2. Concurrency test: store/ingest during consolidate.
3. Status accuracy tests.

#### Implementation Constraints
- Derived long-term writes from consolidate (if any) re-enter gates (§4.9.3 matrix row for `consolidate`).
- Do not implement full hub distillation here; if `force` mentions hubs, return `not_implemented` for hub portion or no-op with explicit field.

#### Expected Result
Agent-visible status + non-blocking trigger with tests.

### Task 5: `memtree_query` / `memtree_get`

#### Intent
Expose hierarchical episodic access without full-log replay (FR-27 / §4.9.4.D).

#### Required Capability or Behavior
- `memtree_get(node_id)` returns one node (leaf or aggregate) with type, interval, dirty flag, child ids / item ref.
- `memtree_query(time_range?, task_id?, depth?, limit?)` returns nodes matching filters.
- Exact values for leaves still via `get_snapshot` when needed.

#### Architectural Responsibility
Read API over MemTree store.

#### Required Changes
1. Query filters + pagination/limit.
2. Bank scoping.
3. Tests for time range and depth.

#### Implementation Constraints
- Do not auto-inject full MemTree into model context (PR-1).
- Coarse-to-fine retrieve orchestration is slice 100120; this phase only exposes structure reads.

#### Expected Result
Query returns expected subtree fixtures; get returns single node.

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
- Block leaf writes on ancestor refresh.

### Agent Decision Boundary
The agent may decide:
- Concrete file/module/class placement.
- Summary text format (deterministic template vs LLM) for CI vs prod.
- Worker pool sizing (default bound concurrency to `min(P, num_dirty_at_level)`).
- Test organization.
- Non-breaking implementation details.

The agent must request approval for:
- Architecture changes beyond the stated scope.
- Breaking API or data-contract changes.
- Security-sensitive policy decisions.
- Destructive data operations.
- Changes affecting downstream phase assumptions.
- Changing default fan-out `k` away from 8 without a measured reason.
- Mandatory multi-view forest (session+entity+scene) as exit criteria.

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
- Leaf reads regress to requiring clean ancestors.

---

## 7. Security Constraints

### Required Controls
- MemTree nodes bank-scoped; no cross-bank parent pointers.
- Aggregate summaries MUST NOT decrypt or log foreign-bank content.
- Tool calls require actor attribution.

### Sensitive Data Rules
- Never log full leaf snapshots in maintenance traces by default.
- Never commit secrets.
- Summary prompts redact credentials when LLM summarization is enabled.

### Security Acceptance Conditions
- Cross-bank `memtree_get` fails closed.
- Consolidate cannot escalate bank scope via `scope` parameter tricks.

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
| T100070-01 | Attach leaf after Phase 100060 write | Leaf node linked; leaf still get-by-id readable |
| T100070-02 | Insert dirties only ancestor path | Unrelated branch remains clean |
| T100070-03 | Two inserts coalesce parent dirty | Single refresh of shared ancestor |
| T100070-04 | Same-depth dirty nodes | Parallel refresh; both clear |
| T100070-05 | `maintenance_status` during dirty | Reports dirty ancestors; `leaf_queryable=true` |
| T100070-06 | `consolidate` while new leaf writes | Writes succeed; no blocking |
| T100070-07 | Refresh failure on one node | Node stays dirty; status surfaces error; others may succeed |
| T100070-08 | `memtree_query` time_range | Only overlapping nodes |
| T100070-09 | `memtree_get` missing id | Structured not-found |
| T100070-10 | Ancestor summary vs leaf snapshot | Summary change does not alter snapshot bytes |
| T100070-11 | Cross-bank memtree read | Denied / not found |

### Negative Testing
Verify that:
- Invalid node ids are rejected.
- Unauthorized bank actions are blocked.
- Partial refresh failures leave safe dirty state.
- Duplicate consolidate calls coalesce work.
- Phase 100060 leaf freshness remains intact.
- Failure does not delete leaves.

### Verification Rule
Implementation claims must be supported by actual test output,
inspection results, or other concrete evidence.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-100070-01 | Time-ordered MemTree with leaf attachment | T100070-01, T100070-08 | `cargo test -p clio-write memtree`: `t01_attach_leaf_linked_and_readable`, `t08_memtree_query_time_range` PASS |
| AC-100070-02 | Dirty-path only (no global rewrite) | T100070-02 | `t02_dirty_path_only` PASS |
| AC-100070-03 | Coalesce + level-parallel refresh | T100070-03, T100070-04 | `t03_coalesce_parent_dirty`, `t04_same_depth_parallel_refresh` PASS |
| AC-100070-04 | FR-3 preserved under dirty ancestors | T100070-01, T100070-05 | `t01_*`, `t05_maintenance_status_while_dirty` (`leaf_queryable=true`) PASS |
| AC-100070-05 | `maintenance_status` / `consolidate` non-blocking | T100070-05, T100070-06 | `t05_*`, `t06_consolidate_nonblocking_with_writes` PASS |
| AC-100070-06 | `memtree_query` / `memtree_get` | T100070-08, T100070-09 | `t08_*`, `t09_memtree_get_missing` (`UnknownPath`) PASS |
| AC-100070-07 | Summaries do not mutate snapshots | T100070-10 | `t10_summary_does_not_mutate_leaf_snapshot` PASS (MemoryItem structured snapshot bytes verified through `LeafIndex` across ancestor refresh) |
| AC-100070-08 | Bank isolation | T100070-11 | `t11_cross_bank_denied` PASS; store dual-backend get wrong-bank → `None` |

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
- **Implementation summary:** In-process MemTree forest (`clio-write`: `memtree`, `memtree_attach`, `memtree_maint`, `memtree_tools`) with default fan-out `k=8`, time-ordered leaf attach, k-ary split, coalesced dirty set, level-parallel bottom-up deterministic summary refresh with bounded workers and generation-guarded refresh, and tools `maintenance_status` / `consolidate` / `memtree_query` / `memtree_get`. Maintenance hook attaches leaves without blocking ingest. Durable `memtree_nodes` DDL expanded (schema_version `3`) with dual-backend CRUD in `clio-store` (SQLite + Postgres parity tests). Remediation round 1: dirty-set race fixed (wave drain + generation guard + requeue of superseded/failed nodes), worker pool bounded to CPU budget, refresh locks narrowed to snapshot/commit phases, sibling split interval recomputed from all children, MemTree reshape validated before schema-version stamp, and test/header/isolation compliance restored.
- **Discovered/affected architectural components:** `clio-write` maintenance handoff; `clio-store` Store trait + async adapter; `sql/001_core.sql` MemTree table; `schema_reshape` version bump + MemTree reshape helper.
- **Changed-component summary:** New MemTree engine/tools (`memtree_maint`, `memtree_tools`, `memtree_attach`); store memtree persist modules; SQL interval/child/dirty columns; profile inventory names already present.
- **Test execution output:** `make check` PASS; `cargo test -p clio-write` memtree suite 17 PASS (T100070-01..T100070-11 + coverage, split-interval regression, concurrent-write-during-wave regression); `cargo test -p clio-store` 82 PASS + 1 doc (incl. Postgres parity); `make coverage` PASS — TOTAL lines **98.82%** functions **99.72%**; per-file scan: every reported file ≥90% lines and functions.
- **Tree fan-out default `k=8` and dirty-coalesce set semantics:** Locked in `DEFAULT_FANOUT` and `MemTreeMaint::enqueue_dirty` (coalesce hit counter); verified by `fanout_default_is_eight` and `t03_coalesce_parent_dirty`.
- **Verification report:** Dual-backend memtree upsert/get/query parity exercised; cross-bank reads fail closed; hub distillation returns `not_implemented` on consolidate accept.
- **Known limitations:** Summaries are deterministic templates (no LLM); single primary episodic tree per bank; hub distillation not executed; hybrid retrieve / ANN indexes deferred; in-process forest is authoritative for tool semantics (store rows available for durable hosts).

---

## 10. Failure Handling and Recovery

### Expected Failure Modes

| Failure | Detection | Recovery |
|---------|-----------|----------|
| Summary LLM timeout | Worker error | Leave dirty; retry on next consolidate; leaf remains readable |
| Tree imbalance / fan-out overflow | Structural check | Split/rebalance; if unsafe, stop and report |
| Orphan leaf without node | Status/doctor foreshadow | Repair path MAY be slice 100230; this phase logs inconsistency |
| Refresh writes wrong bank | Guard | Abort node refresh; fail closed |

### Rollback Strategy
Stop maintenance workers; leaves and item rows remain queryable via Phase 100060 paths. Tree tables may be rebuilt from placement map + leaves in a later repair. Prefer additive migrations.

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
| §4.3 step 3 MemTree | Task 1 | T100070-01 | AC-100070-01 |
| §4.3 step 4 dirty-path | Task 2 | T100070-02, T100070-03 | AC-100070-02, AC-100070-03 |
| §4.3 step 5 parallel refresh | Task 3 | T100070-04 | AC-100070-03 |
| FR-3 / PR-9 / NFR-2 | Tasks 1–4 | T100070-01, T100070-05, T100070-06 | AC-100070-04, AC-100070-05 |
| FR-28 maintenance_status | Task 4 | T100070-05 | AC-100070-05 |
| §4.9.4.A consolidate | Task 4 | T100070-06 | AC-100070-05 |
| FR-27 memtree_* | Task 5 | T100070-08, T100070-09 | AC-100070-06 |
| PR-4 snapshot safety | Task 3 | T100070-10 | AC-100070-07 |

Required chain:

```text
Requirement → Capability → Implementation → Test → Evidence
```

Every acceptance criterion must be traceable.

---

## 12. Phase Exit Contract

### Outputs Produced
- MemTree hierarchical temporal index over episodic leaves.
- Dirty-path, coalesced, level-parallel maintenance.
- `maintenance_status`, `consolidate`, `memtree_query`, `memtree_get`.

### Guarantees Provided to Downstream Phases
After this phase is accepted:
- Slice 100120 can browse coarse→fine structure without inventing a tree.
- Slice 100130 can reuse consolidate hooks for hub distillation.
- Slice 100190 erase can target dirty-path regeneration of derived ancestors.
- Agents can observe non-blocking maintenance explicitly.

### Known Limitations
- Hybrid dense+lexical retrieve not included.
- Hub distillation not fully implemented.
- Multi-scope MemForest views optional/minimal.
- ANN node indexes deferred.

### Downstream Prerequisites
- Slice 100080 triples are a separate graph plane—do not overload MemTree nodes as SPO edges.
- Slice 100110 MAY attach embeddings to node summaries as derived artifacts refreshed on dirty paths.

### Final Status
**PASS WITH DOCUMENTED LIMITATIONS** (2026-09-18)

### Verification Sign-Off
- Implementer: Cursor Agent CLI (auto)
- Verifier / Adversary: Antigravity CLI (Gemini 3.8 Flash)
- Remediator: OpenCode CLI (GLM-5.3 Flash High)
- Remedy Approver: Antigravity CLI (Gemini 3.8 Flash) — ACCEPTED (all 9 findings verified fixed; `make check` / `make coverage` green)
- Human Approver: [pending]
- Date: 2026-09-18

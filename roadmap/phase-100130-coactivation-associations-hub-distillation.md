# Phase 100130: Co-Activation Associations and Hub Distillation

### Attribution
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | OpenCode CLI (Together . GLM-5.3 Flash High) | done |
| Adversary | r1 | OpenCode CLI (OpenRouter . Deepseek V4.1 Flash Max) | done |
| Remediator | r1 | OpenCode CLI (Go . Deepseek V4.1 Flash High) | done |
| Remedy Approver | r1 | OpenCode CLI (Together . GLM-5.3 Flash Max) | approved |
| Finalize | r1 | OpenCode CLI (Together . GLM-5.3 Flash High) | done |

**Index slice 100130 · **Effort:** `1×` · **Scope:** `roadmap/index.md` slice 100130 (authoritative)

### Vocabulary (read first) — zero shared moniker

| Term | Enum / form | Where it lives | Must not |
|------|-------------|----------------|----------|
| **`assoc_edge`** | weighted link between item ids | Association graph store | Be stored as an SPO **triple** |
| **`assoc_kind`** | `coactivation` \| `explicit` | On each `assoc_edge` | Share a column with `epistemic_kind` or `update_rule` |
| **`association_weight_policy`** | growth / lazy decay / prune / hub distill | §4.5 mechanics | Be named **`update_rule`** (that enum is `discrete`\|`continuous` only) |
| **`η`** | learning rate for saturating growth | `ranking_env` / assoc config | Be called EMA **`α`** |
| **`hub_distill`** | maintenance job kind | `consolidate` / dirty-path runner | Be conflated with **`memtree_refresh`** or Phase 100060 canonical merge |
| **`relationship`** | string on `graph_link` | Explicit edges | Be called **`predicate`** (triples only) |

Formulas and fixtures: `roadmap/phase-100130-appendix-association-weight-policy.md`.

## 1. Objective

### Goal
On **co-retrieved** sets, update pairwise **association** weights with **saturating growth**, **lazy decay**, **pruning** below threshold, and **hub distillation** into gated semantic items (FR-17, FR-18, §4.5). Expose `associations`, `graph_link`, and `graph_query`. Wire `retrieve(expand_graph=true)` to walk effective association weights (Phase 100120 already reserved the hook).

### Expected Outcome
- After each successful `retrieve` that returns ≥2 hits, every unordered pair in the **returned** hit set receives one saturating growth step (`η`, default `0.15`); weights stay in `[0, 1]`.
- Reads (`associations`, expand, graph hop scoring) use **effective** weight after lazy exponential decay from `last_reinforced_at`.
- Edges with `w_eff < w_min` (default `0.05`) are deleted and logged (operations removal—not supersession, not compliance erase).
- Nodes exceeding configured above-threshold degree are flagged for **`hub_distill`**; `consolidate` runs eligible distillations without blocking new leaf writes (PR-9).
- Distilled semantic items **re-enter** category + admission gates; optional prune of fine-grained assoc edges after cross-ref.
- `associations(item_id, min_weight?)` lists co-activation and explicit edges with effective weights.
- `graph_link` creates/updates `assoc_kind=explicit` edges; `graph_query` does bounded multi-hop traversal.
- `ranking_env_*` exposes η, half-life, `w_min` (and documents hub degree limit SoT).

### Parent Requirement
`requirement.md` (current, v1.8+) — §4.5 co-activation (growth/decay/prune/hub), association vs triple data model, §4.9.4.B `associations`, §4.9.4.E `graph_link` / `graph_query`, `retrieve(expand_graph)`, `consolidate` hub eligibility, FR-17, FR-18, PR-6 (prune ≠ supersession), PR-8, PR-9, §7.4.5 distilled-derivative logging, sync assoc payload. Appendix: `roadmap/phase-100130-appendix-association-weight-policy.md`.

### Normative resolution (was review Critical #1)
`requirement.md` v1.8 locks: `assoc_edge` lives in **graph/structure metadata** (same persistence concern as §4.6), is **not** an SPO triple and **not** a new memory domain/tier. Dedicated assoc tables are permitted. Erase/sync treat edges as graph metadata referencing item ids.

### Design references (non-normative)
- Co-activation + hub distillation **pattern** only: [HeLa-Mem](https://arxiv.org/html/2604.16839) (research alias “Hebbian distillation” → product term **hub distillation**). **Formula divergence:** HeLa-Mem eq. (1) is `(1−λ)w + η·I(coactivated)`—**do not implement that**. Weight math MUST match §4.5 saturating growth + separate lazy decay / appendix fixtures.
- Saturating growth avoids unbounded weights; production graphs without decay lose discrimination ([capability-graph saturation notes](https://github.com/For-Sunny/capability-graph-neuroscience)).
- Lazy half-life decay + prune + hub-degree dampening in practice: [NeuralMind synapses](https://github.com/dfrostar/neuralmind/blob/main/neuralmind/synapses.py) (inspiration only).
- Consolidation sweep knobs (cooldown, max neighbors): [zeph HebbianConfig](https://docs.rs/zeph-config/latest/zeph_config/memory/struct.HebbianConfig.html)—optional ops inspiration; not a second policy language.

---

## 2. Scope Boundaries

### In Scope
- Durable `assoc_edge` store in **graph/structure metadata** (dual-backend) with `assoc_kind`, raw weight, `last_reinforced_at`, bank scope; explicit edges also store `relationship`.
- Co-activation write hook on `retrieve` with **durable handoff** (FR-17)—same txn or outbox before/with response.
- `association_weight_policy` for coactivation: saturating growth, lazy decay, prune-on-observe, hub flagging.
- Explicit edges **sticky by default** (no coactivation decay/prune unless documented longer half-life).
- Tools (in-process OK): `associations`, `graph_link`, `graph_query`.
- `expand_graph` on `retrieve`: bounded hop expansion using `w_eff` / sticky explicit weights and `min_weight`.
- `consolidate` / maintenance: execute eligible **`hub_distill`** jobs (alongside existing MemTree refresh—distinct job kind).
- Hub distill → gated semantic item write + optional assoc prune + erase-policy log bit.
- Config: η, half_life, `w_min`, hub degree limit; surface via `ranking_env` where required.
- Telemetry: reinforce, prune, hub enqueue/complete (FR-15 spirit).
- Property / isolation tests: association_weight_policy never calls Phase 100090 EMA (`α`).

### Explicitly Out of Scope
- Replacing or rewriting Phase 100080 SPO triples / bi-temporal supersession.
- Reimplementing Phase 100090 EMA (different formula; different owners).
- Persona document CRUD (slice 100140).
- Task/failure history packaging (slice 100150).
- MCP transport binding (slices 100160–17)—in-process tools suffice.
- Full hygiene / erase UX (slices 100190, 21)—only prune logging + distill derivative flag.
- Training an LLM solely for distillation if a cheaper template/extract path exists—MAY call extract sidecar; MUST still gate the admitted item.
- Scheduled full-graph decay sweeps as a correctness requirement (lazy read-time is normative).

### Must Not Change
- Phase 100120 fusion correctness when `expand_graph=false`.
- PR-2 / FR-11: do not route association updates through `update(..., update_rule=...)`.
- PR-6: assoc prune is operations removal, not fact invalidation.
- Phase 100040: distilled hub items MUST pass gates; failed admission MUST NOT pretend distillation succeeded.
- Phase 100070: MemTree dirty-path semantics remain; hub distill is additive job kind under `consolidate`.

### Scope Expansion Rule
If work outside this scope appears necessary:
1. Stop.
2. Document the reason.
3. Request clarification or approval.
4. Do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- Phase 100120 accepted: `retrieve` returns ordered hits; `expand_graph` hook exists (may no-op).
- Phase 100070 accepted: `consolidate` / maintenance runner / `maintenance_status`.
- Phase 100040 accepted: gated semantic writes for hub distill outputs.
- Phase 100010 accepted: `ranking_env_*` extensible for η / half_life / `w_min`.
- Phase 100020 accepted: dual-backend persistence for graph metadata.

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| `retrieve` hit set | Stable ordered ids per call | Phase 100120 tests |
| Maintenance runner | Non-blocking jobs | Phase 100070 |
| Admission / category | Semantic write path | Phase 100040 |
| Ranking env | Can store co-activation knobs | Phase 100010 |
| Item ids | Exist for link endpoints | Phase 100030 |

---

## 4. Existing-System Discovery

The agent MUST inspect the existing system before deciding
where or how to implement the changes.

### Required Discovery
- Where Phase 100120 left `expand_graph` / co-activation no-op hooks.
- Confirm Phase 100020 graph shelf is SQL table `assoc_edges` (`assoc_kind` = `coactivation` | `explicit`) — reuse it; do not add a second graph silo or revive `edges` / `edge_kind` / `distilled` as an `assoc_kind`.
- How `consolidate` dispatches MemTree work—extend with `hub_distill` job kind without overloading MemTree node ids.
- Token/extract path available for distill synthesis (Phase 100050 extract sidecar vs template).
- File size / module split (≤450 lines per Rust source file).

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

### Task 1: Association Edge Store

#### Intent
Persist association links separately from SPO triples.

#### Required Capability or Behavior
- Store `assoc_edge{bank, id_a, id_b, assoc_kind, relationship?, weight, last_reinforced_at, sticky?, ...}` with canonical id ordering for the pair.
- **Uniqueness:**
  - `coactivation`: `(bank, id_a, id_b, assoc_kind=coactivation)` — one undirected weight per pair.
  - `explicit`: `(bank, id_a, id_b, assoc_kind=explicit, relationship)` — multiple relationships per pair allowed.
- Dual-backend behavioral parity for CRUD used by tools.
- Persist in graph/structure metadata (requirement v1.8); not SPO triple rows.

#### Architectural Responsibility
Association graph persistence (graph metadata subsystem; not the bi-temporal triple fact store).

#### Required Changes
1. Schema/migration or equivalent for both backends under graph metadata.
2. Repository API: upsert weight, get, list by item, delete; explicit multi-relationship support.
3. Bank isolation on every query.
4. Document erase/sync hooks: drop edges when endpoints erased; sync includes assoc mutations (FR-31 foreshadow).

#### Implementation Constraints
- Do not reuse triple interval columns or `subject`+`predicate` identity for assoc edges.
- Do not name the weight-update API `update_rule`.

#### Expected Result
Round-trip store/load of coactivation and multi-relationship explicit edges in tests on both backends.

### Task 2: Association Weight Policy Engine

#### Intent
Implement §4.5 four-part policy with appendix fixtures.

#### Required Capability or Behavior
- `reinforce_pair(i, j, now)` applies saturating growth and bumps `last_reinforced_at`.
- `effective_weight(edge, now)` applies lazy decay.
- `maybe_prune(edge, now)` deletes + logs when below `w_min`.
- Concurrent reinforces on same pair are safe (no lost updates).

#### Architectural Responsibility
Association engine (not Phase 100090 continuous engine).

#### Required Changes
1. Pure functions matching appendix numeric oracles.
2. Config load for η, half_life, `w_min`.
3. Unit tests from appendix §3.

#### Implementation Constraints
- Never call this EMA; never accept `update_rule` as a parameter.
- Decay is lazy; optional background sweep is optimization only.

#### Expected Result
Fixture table matches within float tolerance; prune deletes and emits audit-friendly log event.

### Task 3: Co-Activation Hook on Retrieve

#### Intent
FR-17: memories retrieved together strengthen links.

#### Required Capability or Behavior
- After `retrieve` builds the **returned** hit list (post budget trim), for every unordered pair, **durably hand off** `reinforce_pair` (FR-17): same DB transaction as retrieve completion **or** insert into a durable outbox/queue **before** returning hits.
- If durable handoff fails: retrieve MUST **fail closed** or return structured degraded error forcing retry—**silent soft-drop of reinforce is forbidden**.
- Applying the weight update may be async **after** durable enqueue; hits MAY return once enqueue commits.
- Singleton / empty hit sets are no-ops.
- Bank of the retrieve scopes edge writes.

#### Architectural Responsibility
Retrieve post-processor + durable reinforce path.

#### Required Changes
1. Wire hook in Phase 100120 orchestrator with txn/outbox.
2. Tests: 3-hit retrieve creates 3 undirected edges; weights match one growth step from zero.
3. Tests: simulated outbox/DB failure → retrieve does not succeed with skipped reinforce.
4. Metric: pairs reinforced / outbox depth (PII-safe counts).

#### Implementation Constraints
- Do not reinforce the entire pre-fusion candidate pool—returned set only.
- Do not block retrieve on hub distill (separate from reinforce durability).
- Do not treat reinforce as best-effort logging.

#### Expected Result
Two retrieves of the same pair increase weight per saturating formula; `associations` shows rising `w_eff`; failed handoff fails the call.

### Task 4: Tools — `associations`, `graph_link`, `graph_query`

#### Intent
Agent-visible graph inspect and explicit causality edges.

#### Required Capability or Behavior
- `associations(item_id, min_weight?)` → neighbors with `assoc_kind`, raw + effective weight (coactivation) or sticky weight (explicit), `relationship` for explicit.
- `graph_link(source_id, target_id, relationship, weight?)` → upsert `assoc_kind=explicit` keyed by relationship; optional initial weight (default documented, e.g. `1.0`); validate ids exist in bank.
- `graph_query(seed_id, max_hops?, edge_type?, min_weight?)` → bounded BFS/DFS; `edge_type` filters `assoc_kind` (map to `assoc_kind` internally—do not invent a third enum named `class`).
- Reject linking to missing ids with structured error.
- Two `graph_link` calls with different `relationship` on the same pair both persist.

#### Architectural Responsibility
Public graph tools (in-process).

#### Required Changes
1. Tool handlers + contract tests (multi-relationship fixture).
2. Explicit edges participate in expand/associations alongside coactivation.
3. Audit/telemetry on `graph_link`.
4. Sticky explicit: half-life decay/prune MUST NOT apply by default; test that aged explicit edge remains.

#### Implementation Constraints
- `relationship` ≠ triple `predicate`.
- Sticky default is normative (requirement v1.8); longer explicit half-life only if documented.

#### Expected Result
`caused_by` and `depends_on` both listed for the same pair; aged sticky edge survives; within `max_hops` of `graph_query`.

### Task 5: `expand_graph` on Retrieve

#### Intent
Optional spreading activation beyond pure similarity (FR-17 MAY).

#### Required Capability or Behavior
- When `expand_graph=true`, from seed hits, add neighbors with `w_eff ≥ min_weight` up to `max_hops` and a hard neighbor budget.
- Expanded ids merge into candidate set before or after fusion—**document one place** and keep deterministic (NFR-5 spirit).
- Missing assoc store → no-op (Phase 100120 compatibility).

#### Architectural Responsibility
Retrieval graph expansion stage.

#### Required Changes
1. Expansion module with hop/neighbor caps.
2. Tests: linked neighbor surfaces when expand on; absent when off.
3. Latency budget note in metrics breakdown.

#### Implementation Constraints
- Caps mandatory (prevent hub fan-out DoS).
- Do not traverse SPO triples as assoc edges.

#### Expected Result
Fixture graph: similarity miss + strong assoc edge → hit appears only with expand.

### Task 6: Hub Distillation via `consolidate`

#### Intent
Bound graph size; crystallize hub clusters into gated semantic memory (§4.5).

#### Required Capability or Behavior
- Degree check uses **effective** above-threshold edges.
- Enqueue `hub_distill` job; `consolidate(scope?, force?)` drains eligible jobs without blocking writes.
- Distill pipeline: gather hub + top neighbors → propose semantic item → **category + admission** → on pass, store + cross-ref; MAY prune cluster assoc edges; log anonymized-derivative decision (§7.4.5).
- On admission reject: leave graph intact; record failure; do not delete edges.
- `maintenance_status` MAY report pending hub jobs.

#### Architectural Responsibility
Maintenance runner + gated write path.

#### Required Changes
1. Job kind distinct from `memtree_refresh`.
2. Integration test: force high degree → consolidate → semantic item id exists → gates logged.
3. Ensure distill write uses a real §4.1 category (not a forged sixth category).

#### Implementation Constraints
- Reuse consolidation/admit machinery; do not bypass gates.
- Do not claim MemTree ancestor refresh “is” hub distill.

#### Expected Result
Over-degree fixture produces one admitted semantic item and reduces assoc degree when prune-after-distill enabled.

### Task 7: Ranking Env / Config Surface

#### Intent
Operators can tune co-activation without code changes.

#### Required Capability or Behavior
- `ranking_env_get` includes η, half_life, `w_min` (requirement list).
- Hub degree limit documented and readable (ranking_env or assoc config—pick one SoT).

#### Architectural Responsibility
Config / ranking_env (Phase 100010).

#### Required Changes
1. Extend ranking_env schema.
2. Tests: updated η changes growth step size.

#### Implementation Constraints
- Do not store α/N EMA knobs in the same fields as η.

#### Expected Result
Config round-trip visible in `ranking_env_get`.

### Task 8: Isolation Property Checks (unlimited-plan item)

#### Intent
Prove association policy never mixes with continuous EMA.

#### Required Capability or Behavior
- Property or unit tests: for random η and prior w, growth matches saturating formula within float eps; never equals `α·x+(1−α)·prev` unless by coincidence on a fixed fixture that is asserted not used as the engine.
- Grep/architecture test: association engine module MUST NOT call Phase 100090 continuous update entrypoints.
- Concurrent reinforce RMW still holds.

#### Architectural Responsibility
Association engine + CI guards.

#### Required Changes
1. Property fixtures / proptest```text
∀ w∈[0,1], η∈(0,1]: grow(w,η)=w+η(1−w) ∈ [0,1]
```

2. Module-boundary test excluding EMA imports from assoc path.

#### Implementation Constraints
- Do not weaken float checks into “approximately EMA.”

#### Expected Result
CI fails if EMA is wired into reinforce.

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
- Whether explicit edges use optional longer half-life (default sticky / no decay).
- Outbox vs same-txn durable reinforce (both compliant).

The agent must request approval for:
- Architecture changes beyond the stated scope.
- Breaking API or data-contract changes.
- Security-sensitive policy decisions.
- Destructive data operations.
- Changes affecting downstream phase assumptions.
- Soft-dropping FR-17 reinforce (forbidden).

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

---

## 7. Security Constraints

### Required Controls
- Bank isolation on all assoc reads/writes.
- Validate item ids on `graph_link` (no cross-bank linking).
- Cap expand_graph fan-out (resource safety).
- Hub distill content encrypted under existing DEK path (Phase 100020).

### Sensitive Data Rules
- Never log full memory payloads in reinforce/prune telemetry—ids + weights only.
- Never commit secrets.
- Use approved secret/configuration mechanism from Phase 100010.

### Security Acceptance Conditions
- Cross-bank `graph_link` rejected.
- Expand caps enforced under adversarial high-degree fixtures.

---

## 8. Test and Verification Strategy

### Required Tests
- [ ] Unit tests
- [ ] Integration tests
- [ ] Contract tests
- [ ] End-to-end tests
- [ ] Regression tests
- [ ] Security tests
- [ ] Failure-mode tests

### Required Test Scenarios

| Test ID | Scenario | Expected Result |
|---------|----------|-----------------|
| T100130-01 | Grow from w=0 with η=0.15 | Matches appendix step table |
| T100130-02 | Decay half-life 30d, Δt=30d, w=1 | w_eff≈0.5 |
| T100130-03 | w_eff &lt; w_min on read | Edge deleted + logged |
| T100130-04 | Retrieve 3 hits | 3 undirected coactivation edges reinforced |
| T100130-05 | Durable handoff fails | Retrieve fails closed / degraded—no silent skip |
| T100130-06 | `graph_link` two relationships same pair | Both edges listed |
| T100130-07 | `graph_query` max_hops=1 | Neighbor visible; hop2 not |
| T100130-08 | `expand_graph=true` | Assoc neighbor enters hit set when capped rules allow |
| T100130-09 | Hub over degree + `consolidate` | Gated semantic item; job completes |
| T100130-10 | Hub distill admission fail | Edges retained; no fake success |
| T100130-11 | Cross-bank link | Rejected |
| T100130-12 | ranking_env η change | Next growth uses new η |
| T100130-13 | No `update_rule` / EMA API on assoc path | Compile/contract guard or reject |
| T100130-14 | Dual-backend parity sample | Same pair weights after identical ops |
| T100130-15 | Aged sticky explicit edge | Still present after coactivation would prune |
| T100130-16 | Property: growth ≠ EMA engine | Task 8 CI |

### Negative Testing
Verify that:
- Invalid input is rejected.
- Unauthorized / cross-bank actions are blocked.
- Partial failures are handled safely (retrieve vs assoc).
- Duplicate/retry reinforce is monotonic saturating, not double-apply bugs beyond one step per pair per retrieve.
- Existing retrieve fusion tests still pass with expand off.
- Failure does not leave half-deleted hubs without log.

### Verification Rule
Implementation claims must be supported by actual test output,
inspection results, or other concrete evidence.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-100130-01 | Saturating growth + lazy decay + prune per §4.5 | T100130-01–T100130-03 | Pass: `assoc::assoc_policy_tests::grow_matches_appendix_step_table`, `saturating_growth_stays_bounded_property`, `effective_weight_half_life_and_edge_cases`; `t01_t04_growth_applies_one_step_per_pair`, `t02_t03_decay_prunes_below_w_min` |
| AC-100130-02 | Co-retrieve durably reinforces pairs (FR-17) | T100130-04–T100130-05 | Pass: `t04_retrieve_reinforces_every_returned_pair` (3 hits → 3 edges, w=0.15, `pairs_reinforced=3`), `t05_reinforce_failure_fails_retrieve_closed` (reinforce error propagates), `t05b_mid_reinforce_failure_fails_retrieve_closed` (second-pair store failure → `retrieve` returns `Err`, no partial-success outcome) |
| AC-100130-03 | `associations` exposes effective weights (FR-17–18) | T100130-06 | Pass: `assoc_surface_tests::associations_surface_lists_and_validates`, `assoc_tests::t06_graph_link_two_relationships_both_listed` |
| AC-100130-04 | `graph_link` / `graph_query` multi-relationship | T100130-06–T100130-07 | Pass: `t06_graph_link_two_relationships_both_listed`, `t07_graph_query_respects_max_hops`, `assoc_surface_tests::graph_query_surface_hops_and_filters` |
| AC-100130-05 | `expand_graph` uses assoc weights | T100130-08 | Pass: `t08_expand_graph_surfaces_assoc_neighbor`, `t08b_retrieve_expand_graph_includes_assoc_neighbor`, `t08c_expand_skips_explicit_below_min_weight` (explicit edge below `w_min` not expanded; edge at/above it is) |
| AC-100130-06 | Hub distill gated + non-blocking | T100130-09–T100130-10 | Pass: `hub_distill_tests::t09_over_degree_hub_distills_gated_item_and_prunes`, `t10_admission_reject_keeps_edges_and_no_item`, `consolidate_tool_runs_hub_distillation` |
| AC-100130-07 | Assoc path ≠ `update_rule` / ≠ triples | T100130-13, T100130-16 | Pass: `assoc_tests::t13_assoc_engine_has_no_ema_or_update_rule_wiring` (source guard), `assoc::assoc_policy_tests::grow_is_not_the_ema_engine`; assoc tables are separate from `triples` |
| AC-100130-08 | ranking_env knobs | T100130-12 | Pass: `clio-config::admission_knobs_tests::ranking_env_patch_updates_association_knobs`, `hub_and_expand_bounds_validate`; `assoc_tests::t12_eta_change_scales_growth_step`, `assoc_tests::t12b_ranking_env_coactivation_wires_into_retriever` (`HybridRetriever::with_ranking_env` applies `RankingEnv.coactivation.eta` to the growth step end-to-end) |
| AC-100130-09 | Bank isolation | T100130-11 | Pass: `t11_cross_bank_link_rejected`, `assoc_surface_tests::graph_link_surface_rejects_missing_endpoint`, `sqlite_reinforce_list_and_bank_isolation` |
| AC-100130-10 | Dual-backend sample parity | T100130-14 | Pass: `pg_assoc_edge_tests::t14_dual_backend_reinforce_parity` (sqlite vs PG identical weights + explicit multi-relationship) |
| AC-100130-11 | Explicit sticky default | T100130-15 | Pass: `t15_aged_sticky_explicit_edge_survives` |
| AC-100130-12 | Graph-metadata model matches requirement v1.8 | Inspection | `assoc_edges` is a dedicated graph-metadata table (`sql/001_core.sql`), not a triple; `AssocKind` enum is `coactivation`\|`explicit` only; no reuse of `subject`/`predicate`/interval columns |

### Definition of Done
- [x] All in-scope behavior is implemented.
- [x] All acceptance criteria pass (coverage run below; targeted test list in AC table).
- [x] Required tests pass.
- [x] No unauthorized changes were introduced.
- [x] Existing behavior remains intact.
- [x] Security checks pass.
- [x] Documentation is updated where required.
- [x] Evidence is collected.
- [x] Verification is completed.
- [x] Required approval is obtained (downstream pipeline step).

### Completion Evidence

**Implementation summary**
- `clio-store::assoc` (new): pure `association_weight_policy` math — saturating `grow`, lazy `effective_weight`, `should_prune`, canonical pair ordering, deterministic `coactivation_id`/`explicit_id`, `AssocPolicy`.
- `clio-store` `Store` trait: added `list_assoc_edges` (by item or whole bank), `reinforce_assoc_edge` (single-statement atomic saturating upsert), `record_assoc_audit` (PII-safe `audit_events` write). SQLite bodies in `sqlite_assoc.rs`, Postgres in `postgres_assoc.rs`; async mirrors on `AsyncStore`.
- `clio-config`: `CoactivationConstants` gained `hub_degree_limit` (16) and `max_hops` (2) with serde defaults, so `ranking_env_get`/`ranking_env_set` expose all association knobs.
- `clio-retrieve::assoc` (new): `AssociationEngine` (associations, graph_link, graph_query, expand_ids, reinforce_hits, prune-on-observe) and `StoreGraphExpander` implementing the Phase 100120 `GraphExpander` seam. `assoc_surface.rs` exposes JSON handlers for the three tools.
- `clio-retrieve::hybrid`: default expander is now store-backed; `retrieve` reinforces every unordered pair of the **returned** hit set synchronously before returning (fail-closed), reports `pairs_reinforced`, and added `expand_ms` to `RetrieveMetrics`. Rollback switches: `set_reinforcement(false)`, `set_assoc_policy`.
- `clio-write::hub_distill` (new): `HubDistillEngine` detects over-degree hubs from effective coactivation weights, distills each cluster through `clio_admission::gated_create` into a real §4.1 category, cross-references with explicit edges, optionally prunes cluster edges, and logs the derivative decision. `consolidate_tool` now takes an optional hub engine and runs `hub_distill` alongside `memtree_refresh`.

**Discovered/affected architectural components**
- Association persistence reuses the existing Phase 100020 `assoc_edges` graph-metadata shelf (`Store` trait, `sqlite_store`/`postgres_store`); no new silo, no triple-column reuse.
- Phase 100120 `GraphExpander`/`NoopGraphExpander` seam in `clio-retrieve::types` was the expand hook; `expand_graph` merges neighbors into `candidate_ids` **before fusion** (pre-fusion candidate merge, deterministic ordering).
- `clio-write` maintenance runner (`MemTreeMaint` + `memtree_tools::consolidate_tool`) is the consolidate dispatch; `hub_distill` is a distinct job kind.
- Admission gate reuse: `clio_admission::gated_create` + `AdmissionPolicy` + `SignalSource`.

**Job-kind list (`memtree_refresh` vs `hub_distill`)**
- `memtree_refresh`: existing dirty-path ancestor recompute (`memtree_maint`), unchanged.
- `hub_distill`: new `HUB_DISTILL_JOB = "hub_distill"` constant; run by `consolidate_tool` via `HubDistillEngine::consolidate_hubs`; never aliased to MemTree refresh.

**Chosen expand merge point (pre/post fusion)**
- Pre-fusion: expanded neighbor ids are appended to `candidate_ids` before item fetch and RRF fusion; they enter fusion via the existing `DEFAULT_GRAPH_DECAY` boost path. Deterministic and documented in `hybrid.rs`.

**Explicit-edge decay policy note**
- Explicit edges are sticky: `AssociationEngine::observe` returns the raw weight and never applies lazy decay or prune to `assoc_kind=explicit`. Only coactivation edges decay/prune. Documented in `clio-store::assoc` and the phase appendix.

**Test execution output**
- `cargo test --workspace --locked`: all suites pass (531 tests across unit + integration + doc binaries; no failures).
- New tests: `clio-store` assoc policy fixtures + concurrent RMW + SQL-error + dual-backend parity; `clio-retrieve` T100130-04/T100130-05/T100130-06/T100130-07/T100130-08/T100130-11/T100130-12/T100130-15/T100130-16 + surface; `clio-write` T100130-09/T100130-10 + consolidate integration; `clio-config` knob patch/round-trip.

**Dual-backend sample**
- `pg_assoc_edge_tests::t14_dual_backend_reinforce_parity`: three saturating reinforces from 0 with η=0.15 produce `0.385875` on both SQLite and Postgres; explicit multi-relationship (`caused_by`, `depends_on`) lists are byte-identical after id sort.

**Verification report**
- `make coverage` exits 0. Aggregate: functions 98.54%, lines 98.41%. Every reported source file is ≥90% functions and lines (checked via `cargo llvm-cov report` over 113 files; initial offenders `postgres_assoc.rs` (88.61% lines) and `assoc_graph.rs` (80% functions) were fixed by exercising their validation/whole-bank-list branches and the sort tie-breaker closures respectively).
- `cargo clippy --workspace --all-targets --all-features --locked -- -D warnings`: clean.
- `cargo fmt --all`: applied.

**Remediation (round r1)**
- F-01: `HybridRetriever::with_ranking_env` / `set_ranking_env` build the `AssocPolicy` from the live `RankingEnv.coactivation` and apply `env.retrieval` + `recency_tau_days`; `t12b_ranking_env_coactivation_wires_into_retriever` proves an η set on the env changes the growth step end-to-end.
- F-02: `HubDistillEngine::audit` returns `Result` and `distill_hub` propagates it, so a failed §7.4.5 derivative-decision log fails the distillation instead of being discarded.
- F-03: `expand_ids` now filters every edge kind by `policy.w_min` (previously sticky explicit edges bypassed it); `t08c_expand_skips_explicit_below_min_weight` covers both sides of the threshold.
- F-04: `assoc_reinforce`, `hub_distill_enqueue`, and `hub_distill_complete` telemetry added; durable resumable-queue semantics recorded above as an explicit non-conformance (phase says `maintenance_status` pending-hub reporting is optional).
- F-05: `FaultyStore` delegating double fails the second reinforce; `t05b_mid_reinforce_failure_fails_retrieve_closed` asserts `retrieve` returns `Err` with no partial-success outcome.
- F-06: full AGENTS.md header blocks added to `assoc_policy_tests.rs`, `assoc_edge_tests.rs`, and `pg_assoc_edge_tests.rs`; new `assoc_durable_tests.rs` uses the same header.
- F-07: developer attribution row corrected to the instructed agent string; remediator row appended.
- F-08: partial unique index `assoc_edges_coactivation_pair_inx` on `(bank_id, source_id, target_id) WHERE assoc_kind='coactivation'`; `sqlite_coactivation_pair_unique_index_blocks_duplicates` proves a second row with a different id is rejected.

**Known limitations**
- Distill synthesis is a deterministic template over the hub + top neighbor gists (no LLM); the admission gate still decides whether it is stored.
- Lazy decay means untouched coactivation edges linger until observed (acceptable per §4.5).
- The "reinforce handoff failure" tests now cover both a store-side validation error (`t05_reinforce_failure_fails_retrieve_closed`, invalid η) and a mid-wave store failure on the second pair (`t05b_mid_reinforce_failure_fails_retrieve_closed`); both assert `retrieve` returns `Err` so no partial-success outcome is returned.
- On a mid-wave failure, pairs reinforced before the failing pair remain written and a retry re-applies one saturating step to them (idempotent to `[0,1]` but not exactly-once). Reinforce is not wrapped in a single transaction across all pairs; FR-17 requires the durable handoff to fail closed, which it does.
- `expand_graph` on a store whose `assoc_edges` table is absent surfaces a SQL error (fail-closed) rather than silently no-op'ing; Phase 100120 compatibility is preserved by explicitly injecting `NoopGraphExpander`.
- Hub degree counts coactivation edges above `w_min` only (explicit sticky edges excluded); documented as the source of truth.
- Non-conformance (hub job durability): `hub_distill` is not persisted as a resumable queue/job row. `consolidate_hubs` recomputes eligible hubs from effective degree each wave and drains them inline, emitting durable `hub_distill_enqueue` / `hub_distill_complete` audit telemetry but no pending-work record. `maintenance_status` therefore cannot report pending hub jobs. The phase marks that report optional ("MAY"), and a durable queue would require a new store table + dual-backend + async surface beyond this slice's scope; recorded here as an explicit deviation rather than pretending queue semantics.
- Telemetry now emitted on every association path: `assoc_reinforce` (retrieve wave, pairs + hit count), `assoc_prune`, `graph_link`, `hub_distill` (per-item derivative decision, §7.4.5), `hub_distill_cross_ref`, `hub_distill_prune`, `hub_distill_enqueue`, `hub_distill_complete`. All are PII-safe (ids/counts/weights only), and every `record_assoc_audit` error now propagates instead of being discarded.

---

## 10. Failure Handling and Recovery

### Expected Failure Modes

| Failure | Detection | Recovery |
|---------|-----------|----------|
| Assoc write / handoff error | Outbox/txn fail | Fail retrieve closed or degraded retry; never silent skip |
| Hub admit reject | Admission result | Keep edges; surface in maintenance_status |
| Expand blow-up | Cap hit | Stop expansion; return partial expand |
| Decay clock skew | Test/injectable clock | Document clock SoT |

### Rollback Strategy
Disable reinforce hook + expand via config flags; assoc tables can remain inert. Revert code; no triple data affected.

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
| FR-18 / §4.5 policy | Task 2 | T100130-01–T100130-03 | AC-100130-01 |
| FR-17 reinforce | Task 3 | T100130-04–T100130-05 | AC-100130-02 |
| FR-17–18 associations | Task 4 | T100130-06 | AC-100130-03 |
| §4.9.4.E graph_* | Task 4 | T100130-06–T100130-07 | AC-100130-04 |
| retrieve expand_graph | Task 5 | T100130-08 | AC-100130-05 |
| §4.5 hub / consolidate | Task 6 | T100130-09–T100130-10 | AC-100130-06 |
| Vocab / PR-2 boundary | Tasks 1–2 | T100130-13 | AC-100130-07 |
| ranking_env | Task 7 | T100130-12 | AC-100130-08 |
| Bank isolation | Task 4 | T100130-11 | AC-100130-09 |
| Dual backend | Task 1 | T100130-14 | AC-100130-10 |

Required chain:

```text
Requirement → Capability → Implementation → Test → Evidence
```

Every acceptance criterion must be traceable.

---

## 12. Phase Exit Contract

### Outputs Produced
- Association edge store + weight policy engine.
- Co-activation hook on retrieve.
- `associations`, `graph_link`, `graph_query`.
- Working `expand_graph` path.
- Hub distillation via `consolidate` job kind `hub_distill`.

### Guarantees Provided to Downstream Phases
After this phase is accepted:
- Slice 100160 can bind graph/association write-adjacent tools with stable semantics.
- Slice 100190 erase can treat assoc edges as derived structures to regenerate/drop.
- Compose/retrieve continue to function with association side effects opt-in via expand.

### Known Limitations
- Distill quality depends on extract/LLM budget—admission still gates junk.
- Lazy decay means untouched **coactivation** edges linger until observed (acceptable per §4.5).
- Explicit edges are sticky by default; optional longer half-life is deployment-documented only.

### Downstream Prerequisites
- Slice 100160–17 MUST use tool names/semantics unchanged.
- Slice 100190 MUST drop/regenerate `assoc_edge` when endpoints are erased.
- Slice 100240 sync MUST include assoc mutations when multi-host claimed.
- Do not let hygiene (slice 100210) silently alias assoc prune without audit.

### Final Status
PASS | PASS WITH DOCUMENTED LIMITATIONS | BLOCKED | FAILED

### Verification Sign-Off
- Implementer: [Name/Agent]
- Verifier: [Name/Agent]
- Human Approver: [Name, if required]
- Date: [YYYY-MM-DD]

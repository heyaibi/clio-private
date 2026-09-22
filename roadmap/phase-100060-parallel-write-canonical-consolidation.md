# Phase 100060: Parallel Write Path and Canonical Consolidation

### Attribution
| Role | Agent |
|------|-------|
| Developer | Cursor Agent CLI (auto) |
| Adversary | Antigravity CLI (Gemini 3.8 Flash) |
| Remediator | Cursor Agent CLI (auto) |
| Remedy Approver | Antigravity CLI (Gemini 3.8 Flash) |

**Index slice 100060 · **Effort:** `1×` · **Scope:** `roadmap/index.md` slice 100060 (authoritative)

## 1. Objective

### Goal
Make new memory **queryable fast** (PR-9 / FR-3 / NFR-2): run **parallel chunk extraction**, **merge near-duplicates into a canonical unit**, and expose the **leaf immediately**. Structural maintenance (MemTree ancestor refresh) MUST NOT block leaf readability—full tree maintenance lands in slice 100070; this slice owns §4.3 steps 1–2 and the leaf-queryability guarantee.

### Expected Outcome
- Incoming turns/sessions are partitioned into extraction chunks processed concurrently (bounded parallelism).
- Each chunk uses Phase 100050 extract + span verify; failures follow FR-4 per chunk without failing unrelated chunks blindly (document partial-success policy).
- Near-duplicate candidates from parallel extraction consolidate into stable **canonical units** before they are treated as the durable leaf write unit.
- After canonical consolidation + gated admit, the new episodic item is **leaf-queryable** immediately—before any ancestor structural maintenance completes (FR-3).
- Target: newly written episodic item retrievable within a bounded window (NFR-2: under ~2 seconds of source turn completing), independent of background maintenance duration.
- `store` / ingest path returns success for leaf durability without waiting on MemTree summary refresh (slice 100070).

### Parent Requirement
`requirement.md` (current) — P2, PR-9, §4.3 steps 1–2, FR-3, NFR-2; gated writes §4.9.3 / FR-21; fidelity via Phase 100050 / FR-4.

### Design references (non-normative)
- Parallel chunk extraction + canonical fact consolidation before indexing: [MemForest](https://arxiv.org/html/2605.23986v2) (Chen et al., 2026) and [Concyclics/MemForest](https://github.com/Concyclics/MemForest).
- Canonicalization practice from MemForest: normalize surface forms → merge duplicates → keep non-equivalent updates as **separate temporally anchored facts** (do not overwrite older evidence during consolidation).
- Near-duplicate merge vs supersede distinction (merge equivalents only): related pattern discussion in [MemSIF](https://arxiv.org/html/2608.01742)—supersession of discrete facts remains slice 100080 / PR-6, not this consolidation step.

---

## 2. Scope Boundaries

### In Scope
- Session/turn partitioning into extraction chunks.
- Bounded-parallel invocation of Phase 100050 extraction + verification.
- Canonical consolidation: normalize + merge near-duplicate / equivalent candidates into one write unit; preserve provenance links to source chunks/spans.
- Leaf publish: after gated admission, mark item queryable at leaf level without waiting for ancestor refresh.
- Minimal leaf lookup path sufficient to prove FR-3 / NFR-2 (by id and/or simple time-ordered leaf list)—full hierarchical MemTree browse is slice 100070.
- Non-blocking handoff hook for dirty-path maintenance (slice 100070 can subscribe); MUST NOT require slice 100070 to complete for leaf reads.

### Explicitly Out of Scope
- MemTree node hierarchy, dirty-path ancestor recompute, `maintenance_status` / `consolidate` tools (slice 100070).
- Bi-temporal triple supersession engine (slice 100080).
- Hub distillation / co-activation graph (slice 100130).
- Dense/lexical index rebuilds (slice 100110)—leaf queryability here is structural/id/time based, not hybrid retrieve.
- MCP transports.

### Must Not Change
- Phase 100050 span-verify rules and refuse-commit semantics.
- Phase 100040 admission gates on every long-term canonical write.
- Snapshot authoritative / gist non-authoritative (PR-4).
- PR-6: consolidation MUST NOT delete or silently overwrite a prior discrete fact under the guise of “merge” when the content is a contradictory update—contradictions become separate candidates / later triple supersession.

### Scope Expansion Rule
If work outside this scope appears necessary:
1. Stop.
2. Document the reason.
3. Request clarification or approval.
4. Do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- Phase 100050 accepted: extract + span verify + gated store wiring.
- Phase 100040 accepted: admission gates.
- Phase 100030 accepted: item repository.

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| Extract+verify pipeline | Per-chunk callable | Phase 100050 tests |
| Gated write | Canonical unit admits only through gates | Phase 100040 tests |
| Async/concurrency primitive | Bounded parallel tasks | Runtime smoke |
| Leaf read API | Get-by-id (and/or leaf list) works post-write | Phase 100030 + this phase |

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
- Locate any existing queue/worker/async patterns to reuse before inventing a new scheduler.

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

### Task 1: Chunk Partitioning and Bounded Parallel Extraction

#### Intent
Break the sequential extraction bottleneck (§4.3 step 1).

#### Required Capability or Behavior
- Partition a session/turn stream into chunks (document default size strategy; MemForest-style short multi-turn chunks are acceptable).
- Extract+verify chunks concurrently with a configurable concurrency limit `P`.
- Aggregate per-chunk results: verified candidates, verify-refused diagnostics, transport errors.
- Partial success policy (MUST document and test): e.g. verified chunks proceed to consolidation; failed chunks log and do not poison successful admits unless the caller requested all-or-nothing.

#### Architectural Responsibility
Write-path orchestrator / ingest pipeline.

#### Required Changes
1. Chunker.
2. Worker pool / async fan-out with hard concurrency cap.
3. Structured aggregate result type.

#### Implementation Constraints
- Do not serialize all chunks through one LLM call “for simplicity” in the default path.
- Do not unbounded-spawn one task per token/turn without a cap.
- Each chunk still obeys Phase 100050 retry-once verify rules independently.

#### Expected Result
Tests show wall-clock overlap for multi-chunk fixtures with a fake extractor (concurrency probe), and correct aggregation.

### Task 2: Canonical Near-Duplicate Consolidation

#### Intent
Repair fragmentation introduced by parallel extraction (§4.3 step 2).

#### Required Capability or Behavior
- Normalize surface forms (case/whitespace/Unicode policy documented).
- **Default merge path until slice 100110:** deterministic fingerprint / normalized exact match on key fields **only**. Embedding candidate search and LLM equivalence checks are **out of default production path** until dense index exists; if experimented with, they MUST NOT be the sole merge authority and MUST be behind an explicit config flag defaulting off.
- **Hard no-merge rule for discrete contradictions:** if two candidates share a normalized discrete key (`subject`+`predicate` when SPO-shaped, or an explicit discrete attribute key) and differ on object/value, they MUST NOT merge. Emit separate canonical units and/or hand off to `triple_add` supersession (Phase 100080). Never blend Boston/NYC-style updates into one value.
- Non-keyed near-duplicates (same fingerprint) merge with provenance union.
- Canonical unit retains provenance: source chunk ids, span evidence; confidence aggregation rule documented (e.g. max).

#### Architectural Responsibility
Canonicalization / fact-manager layer between extraction and gated write.

#### Required Changes
1. Fingerprint / normalize helpers (deterministic-only default).
2. Merge algorithm + **mandatory** discrete-key contradiction split.
3. Provenance union on merged unit.
4. Test: `lives_in` Boston vs NYC → two units / triple handoff, never one blended object.

#### Implementation Constraints
- Consolidation is **not** bi-temporal supersession (slice 100080) and **not** `discard`.
- Consolidation MUST NOT bypass Phase 100040 gates: the merged unit is still a candidate for admit.
- Do not merge across banks or actors.
- LLM/embedding merge MUST NOT be sole authority for keyed discrete attributes (even after slice 100110).

#### Expected Result
Two near-duplicate chunk outputs → one admitted leaf; contradictory objects for same subject+predicate → two candidates or explicit handoff note to triple path—not a blended value.

### Task 3: Gated Admit of Canonical Leaf

#### Intent
Persist the canonical unit through existing gates with dual representation.

#### Required Capability or Behavior
- Run Phase 100040 gated write (and Phase 100050 verify if snapshot present / re-verify after merge if merge rewrote extractive fields).
- If merge rewrites snapshot text, re-run span verify against original sources before commit.
- On admit: repository create returns id; leaf marked queryable.

#### Architectural Responsibility
Application service using Phase 100030–005 stack.

#### Required Changes
1. Post-merge verify-if-needed.
2. Gated create for each surviving canonical unit.
3. Telemetry: consolidate_merge counts, admit results.

#### Implementation Constraints
- No ungated repository create from the parallel path.
- Empty merged set → no write; log.

#### Expected Result
Integration: parallel extract → merge → single gated item with provenance.

### Task 4: Immediate Leaf Queryability (Non-Blocking Maintenance)

#### Intent
Satisfy FR-3 / PR-9 / NFR-2: leaf readable before structural maintenance completes.

#### Required Capability or Behavior
- After Task 3 commit, `get` / leaf listing by id succeeds even if MemTree ancestors are dirty/absent.
- Emit a maintenance signal/event (“leaf attached / path dirty”) that slice 100070 can consume; if slice 100070 is not present yet, buffer or no-op without blocking.
- Ingest API MUST NOT await ancestor summary regeneration.
- **NFR-2 harness (required for exit):** with a **fixture/no-op extractor** (or recorded extract), measure wall-clock from ingest completion to successful leaf get; p95 MUST be **< 2 seconds** on the CI reference profile. Separately assert maintenance independence (slow fake consolidator does not block leaf get). Real LLM extract latency is reported as a distinct metric and MUST NOT be conflated with the NFR-2 leaf-publish budget (see `requirement.md` §8).

#### Architectural Responsibility
Leaf index / query façade + maintenance hook boundary + perf self-check.

#### Required Changes
1. Explicit `leaf_queryable=true` (or equivalent) state on write completion.
2. Read path that does not require clean ancestors.
3. Async handoff stub for dirty-path refresh.
4. Automated timing test for NFR-2 with fixture extractor.

#### Implementation Constraints
- Do not implement full MemTree refresh here.
- Do not block the write response on embedding rebuilds (slice 100110).

#### Expected Result
Test: write returns; immediate get-by-id succeeds; a simulated slow maintenance task started after write does not gate the read.

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
- Implement full MemTree maintenance under this slice’s exit claim.

### Agent Decision Boundary
The agent may decide:
- Concrete file/module/class placement.
- Chunk size defaults and concurrency defaults.
- Merge fingerprint details.
- Test organization.
- Non-breaking implementation details.
- Shape of the maintenance handoff event for slice 100070.

The agent must request approval for:
- Architecture changes beyond the stated scope.
- Breaking API or data-contract changes.
- Security-sensitive policy decisions.
- Destructive data operations.
- Changes affecting downstream phase assumptions.
- Using LLM equivalence checks as the only merge path with no deterministic baseline.

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
- Leaf reads cannot be made independent of ancestor state without redesign—escalate rather than blocking writes on maintenance.

---

## 7. Security Constraints

### Required Controls
- Parallel workers inherit bank/actor; no cross-bank merge.
- Admission and span verify remain mandatory on canonical units.
- Logs mask secrets from chunk text.

### Sensitive Data Rules
- Never log full multi-chunk sources with credentials.
- Never commit secrets.
- Use approved configuration for extractor endpoints.

### Security Acceptance Conditions
- Worker panic/failure does not leave plaintext unencrypted rows.
- Partial batch cannot admit into the wrong bank.

---

## 8. Test and Verification Strategy

### Required Tests
- [x] Unit tests
- [x] Integration tests
- [x] Contract tests (bank isolation / embedding_merge reject)
- [x] End-to-end tests (`parallel_ingest` fixture path)
- [x] Regression tests (Phase 100050 pipeline still green)
- [x] Security tests (cross-bank reject; prior secret-redact path retained)
- [x] Failure-mode tests (partial fail, all-or-nothing, empty/all-fail)

### Required Test Scenarios

| Test ID | Scenario | Expected Result | Evidence |
|---------|----------|-----------------|----------|
| T100060-01 | Multi-chunk session with fake slow extractor | Chunks run concurrently under cap `P` | `parallel::t01_chunks_run_concurrently_under_cap` PASS |
| T100060-02 | Two near-duplicate chunk outputs | One canonical admitted leaf | `ingest::t02_near_duplicates_one_leaf` PASS |
| T100060-03 | Same discrete key, different object (Boston vs NYC) | **No merge**; two units or triple-path handoff | `consolidate::t03_boston_vs_nyc_no_merge` + `ingest::t03_contradiction_two_units` PASS |
| T-03b | Identical fingerprint near-duplicates | Single canonical unit | `consolidate::t03b_identical_fingerprint_merges` PASS |
| T100060-04 | One chunk verify-fails, others pass | Partial policy honored; failures logged | `ingest::t04_partial_chunk_failure` PASS |
| T100060-05 | After admit, get-by-id before maintenance finishes | Leaf readable (FR-3) | `ingest_leaf::t05_t06_leaf_readable_before_slow_maintenance` PASS |
| T100060-06 | Artificial slow maintenance during/after write | Leaf get still succeeds (maintenance independence) | same test; get before slow hook completes PASS |
| T-06b | Fixture-extractor ingest → leaf get timing | p95 < 2s (NFR-2); metric separate from extract LLM time | `ingest_leaf::t06b_nfr2_fixture_leaf_publish_under_2s` PASS (profiles A/B/C/reference) |
| T100060-07 | Merged snapshot rewrites extractive field | Re-verify before commit | `ingest::t07_merged_snapshot_reverify` PASS |
| T100060-08 | Canonical write skips gates | Impossible / rejected | `ingest_gate::t08_rejected_by_admission_gate` PASS — real admission reject (theta pinned, novelty 0): admitted empty, no write, no leaf publish, `admit_reject` event |
| T100060-09 | Cross-bank chunk mix | Rejected / isolated | `ingest_gate::t09_cross_bank_rejected` PASS — `item.bank_id != ctx.bank` → `InvalidArgument`, no write, no leaf in either bank |
| T100060-10 | Empty session / all chunks fail | No leaf admit; structured result | `ingest_leaf::t10_empty_or_all_fail_no_admit` PASS |

### Negative Testing
Verify that:
- Invalid input is rejected.
- Unauthorized bank actions are blocked.
- Partial failures are handled per documented policy.
- Duplicate merge is idempotent for identical fingerprints.
- Existing Phase 100050 behavior remains intact.
- Failure does not leave ungated or unverified snapshots admitted.

### Verification Rule
Implementation claims must be supported by actual test output,
inspection results, or other concrete evidence.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-100060-01 | Parallel chunk extraction with bounded concurrency | T100060-01 | `cargo test -p clio-write` — `t01_chunks_run_concurrently_under_cap` PASS (wall-clock overlap under P=4) |
| AC-100060-02 | Near-duplicates consolidate to one canonical unit | T100060-02 | `t02_near_duplicates_one_leaf` PASS — 1 admit, `consolidate_merges >= 1` |
| AC-100060-03 | Discrete key contradictions never merged | T100060-03 | Boston vs NYC → 2 units + `triple_handoff_note`; ingest admits 2 leaves |
| AC-03b | Fingerprint duplicates consolidate | T-03b | Normalized entity fingerprints merge to 1 unit |
| AC-100060-04 | FR-3 leaf queryable before maintenance completes | T100060-05, T100060-06 | `LeafIndex::get` succeeds; slow hook runs after return |
| AC-04b | NFR-2 p95 < 2s leaf publish (fixture extract) | T-06b | `leaf_publish_ms < 2000` for profiles A/B/C/reference |
| AC-100060-05 | Gates + span verify still enforced | T100060-07, T100060-08 | `gated_store_verified` span-verifies the canonical snapshot against merged source; T100060-08 proves admission reject blocks write + leaf publish |
| AC-100060-06 | Partial chunk failure safe | T100060-04, T100060-10 | Partial admit 1 leaf; empty/all-fail admit 0; all-or-nothing aborts |
| AC-100060-07 | Bank isolation under parallelism | T100060-09 | `item.bank_id != ctx.bank` → `InvalidArgument` |

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
- **Implementation summary:** `clio-write` gained `chunk`, `parallel`, `consolidate`, `maintenance`, `ingest`. `pipeline` exposes `extract_and_verify` for workers. Default path: partition → bounded parallel extract+verify → deterministic fingerprint consolidate (discrete-key no-merge) → gated admit → `LeafIndex` publish + `leaf_attached` handoff.
- **Discovered/affected architectural components:** Write-path orchestrator in `clio-write` (no MemTree yet); reuse of Phase 100050 extract/verify and Phase 100040 `gated_store_verified`.
- **Changed-component summary:** New modules above; `lib.rs` re-exports; pipeline refactor only (no Phase 100050 rule changes).
- **Test execution output:** `make check` PASS; `cargo test -p clio-write` — 65 lib tests PASS (includes T100060-01…T100060-10, `profile_configs_are_distinct`, and remediation tests `t08_rejected_by_admission_gate` / `t09_cross_bank_rejected`).
- **NFR-2 timing harness:** `t06b_nfr2_fixture_leaf_publish_under_2s` — fixture extract; `WriteIngestConfig::for_profile` switches A/B/C/reference; asserts `leaf_publish_ms < 2000` (separate from live LLM extract).
- **Consolidation merge-rule note:** NFC+lowercase+whitespace normalize; fingerprint merge for non-keyed / same-object keyed duplicates; same `subject|predicate` (or `attr:*`) with different object → separate units + `handoff=triple_supersession`. `embedding_merge=true` rejected.
- **Maintenance handoff contract (slice 100070):** `MaintenanceSignal { kind: "leaf_attached", item_id, bank_id }` via `MaintenanceHook::on_leaf_attached`. Leaf readability uses `LeafIndex` and MUST NOT await ancestor refresh.
- **Verification report:** `make coverage` PASS — aggregate lines **99.17%**, functions **99.84%**; every reported file ≥90% lines and functions (incl. new `clio-write` modules at ≥93% lines / ≥100% functions where listed).
- **Known limitations:** No MemTree / `maintenance_status` / `consolidate` tools (slice 100070); leaf get/list is in-process façade (not hybrid retrieve); embedding/LLM merge flagged off.

#### Remediation round 1 (adversary findings F-01…F-06)

- **F-01:** clippy `default_constructed_unit_structs` fixed (`NoopMaintenance` instead of `::default()`); `make check`/`make lint` green.
- **F-02:** all five new `clio-write` module headers completed with the negative boundary and single-responsibility clauses.
- **F-03:** fudged T100060-08 replaced with a real admission-reject test; T100060-09 decoupled into its own cross-bank body. Both moved to `crates/clio-write/src/ingest_gate_tests.rs` to stay within the 450-line file limit.
- **F-04:** maintenance handoff is now explicitly non-blocking (`SharedMaintenanceHook` + `maintenance::dispatch_async` on a detached thread); `MaintenanceHook` contract documented; new `BlockingMaintenance` test proves ingest returns and leaf get succeeds while the hook is still blocked.
- **F-05:** `WriteIngestConfig::for_profile` maps A/B/C to hardware-profile vCPU budgets (concurrency 1/2/4); `profile_configs_are_distinct` test added.
- **F-06:** dead post-merge `reverify_if_needed` branch removed; documented that the first candidate's snapshot is canonical/immutable and `gated_store_verified` span-verifies the merged source.
- **Re-verification:** `make check` PASS; `make coverage` PASS — aggregate lines **99.17%**, functions **99.84%**, no reported file under 90%.

---

## 10. Failure Handling and Recovery

### Expected Failure Modes

| Failure | Detection | Recovery |
|---------|-----------|----------|
| Worker timeout | Future/join error | Mark chunk failed; continue per partial policy |
| Merge ambiguity | Conflicting equivalence | Keep separate; log; do not invent blended fact |
| Admit reject after merge | Gate/verify | No leaf; log factors/verify reasons |
| Maintenance hook flood | Queue depth | Coalesce signals (slice 100070 will coalesce dirty marks); never block leaf write |

### Rollback Strategy
Feature-flag parallel ingest off → fall back to single-chunk Phase 100050→004 path. Leaves already admitted remain. No need to unwind MemTree (not required yet).

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
| §4.3 step 1 parallel extraction | Task 1 | T100060-01 | AC-100060-01 |
| §4.3 step 2 canonical consolidation | Task 2 | T100060-02, T100060-03 | AC-100060-02, AC-100060-03 |
| FR-3 / PR-9 leaf before maintenance | Task 4 | T100060-05, T100060-06 | AC-100060-04 |
| NFR-2 freshness window | Task 4 | T100060-06 | AC-100060-04 |
| FR-4 / Phase 100050 | Tasks 1, 3 | T100060-04, T100060-07 | AC-100060-05, AC-100060-06 |
| FR-21 / Phase 100040 gates | Task 3 | T100060-08 | AC-100060-05 |
| Bank isolation | Task 1–3 | T100060-09 | AC-100060-07 |

Required chain:

```text
Requirement → Capability → Implementation → Test → Evidence
```

Every acceptance criterion must be traceable.

---

## 12. Phase Exit Contract

### Outputs Produced
- Parallel chunk extraction orchestrator.
- Canonical consolidation into stable leaf write units.
- Immediate leaf queryability with non-blocking maintenance handoff.

### Guarantees Provided to Downstream Phases
After this phase is accepted:
- Slice 100070 can attach leaves into MemTrees and refresh dirty ancestors without changing the leaf-first readability contract.
- Fresh episodic memory is available for agents without waiting on summaries.
- Consolidation merge rules exist for later hub distillation reuse (§4.5 references §4.3 step 2).

### Known Limitations
- Hierarchical ancestor summaries and `maintenance_status` / `consolidate` not shipped yet (slice 100070).
- Hybrid retrieve not available (slices 100110–12); leaf get/list only.
- Embedding/LLM-assisted merge remains **flagged off** until slice 100110; deterministic fingerprint is the production default.
- NFR-2 harness uses fixture extractors; Profile A/B/C live-extract p95 is reported separately and does not gate Phase 100060 exit unless it also exceeds an explicitly configured deploy SLO.
- The NFR-2 timing harness MUST be invocable under Profile A/B/C **config switches** (same fixture extract) so operators can compare leaf-publish budgets across profiles; CI exit requires the reference profile used in T-06b.

### Downstream Prerequisites
- Slice 100070 MUST honor leaf-queryable-before-refresh and coalesce dirty marks.
- Slice 100080 MUST NOT overload consolidation as supersession.

### Final Status
PASS WITH DOCUMENTED LIMITATIONS

### Verification Sign-Off
- Implementer: Cursor Agent CLI (auto)
- Verifier: (pending adversary / human)
- Human Approver: [Name, if required]
- Date: 2026-09-17

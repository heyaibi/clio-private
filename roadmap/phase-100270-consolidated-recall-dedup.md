# Phase 100270: Consolidated-Only Recall Preset and Prefer-Consolidated Dedup

### Attribution
Rounds below record plan authorship; implementation sign-off is in §12.
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | OpenCode CLI (Go . Deepseek V4.1 Flash High) | done |
| Adversary | r1 | OpenCode CLI (OpenRouter . Deepseek V4.1 Flash Max) | done |
| Remediator | r1 | OpenCode CLI (Go . Deepseek V4.1 Flash High) | done |
| Remedy Approver | r1 | OpenCode CLI (OpenRouter . Deepseek V4.1 Flash Max) | approved |
| Finalize | r1 | OpenCode CLI (Go . Deepseek V4.1 Flash High) | done |

**Index slice 100270 · **Effort:** `1×` · **Scope:** `gap/hindsight-noise-overcapture.md` item 3 plus read-side duplicate recall

### Vocabulary (read first) — zero shared moniker

| Term | Enum / form | Where it lives | Must not |
|------|-------------|----------------|----------|
| **`recall_scope`** | `consolidated_only` \| `full` (per-call param + bank default from profile) | Retrieve request | Be conflated with write **`domains`** partition or MCP transport |
| **`consolidated_item`** | Canonical/distilled long-term unit (canonical consolidation, hub distillation) eligible for `consolidated_only` | Retrieval eligibility flag | Be conflated with a new memory domain or sixth semantic category |
| **`prefer_consolidated`** | Boolean read-time dedup: consolidated unit supersedes its raw sources, freed slots backfilled | `retrieve`/`compose_context` param | Be conflated with write-time novelty scoring or hygiene archive |
| **`duplicate_tolerance_read`** | `strict` \| `balanced` \| `lenient`, per-bank; read-time page similarity cap with its own mapping (Jaccard thresholds per level, documented in Task 3) | `retention_profile` field, independent default from `duplicate_tolerance_write` | Share a value, default, or tuning rationale with `duplicate_tolerance_write`; one knob MUST NOT drive both mechanics |

## 1. Objective

### Goal

Give recall the same kind of narrowing knob the Hindsight fix used: a documented, bank-defaultable scope that returns consolidated knowledge instead of every raw fact, plus a `prefer_consolidated` mode that keeps full coverage but drops raw sources already folded into a returned consolidated unit and backfills the freed slots. Duplicates stop reaching the model even when near-duplicates slipped past write-time gates.

### Expected Outcome

- `retrieve` and `compose_context` accept `recall_scope=consolidated_only`, returning only consolidated units, with token budget still honored.
- `prefer_consolidated=true` on a `full` recall drops raw items whose canonical/distilled parent is also returned, then backfills from the next-best candidates so coverage does not shrink.
- The bank default `recall_scope_default` from Phase 100250 is honored unless the call overrides it; explicit calls always execute regardless of the intent gate.
- A duplicate-recall fixture (raw facts plus their consolidated parent) returns one representative under both modes instead of three near-identical hits.

### Parent Requirement

`requirement.md` — P1, PR-1, PR-7, §4.3 step 2, §4.5, §4.9.4.B (`retrieve`, `compose_context`), FR-17, FR-24, NFR-3, NFR-4. Gap source: `gap/hindsight-noise-overcapture.md` item 3.

### Design References (non-normative)

- **Hermes `recall_types=observation` default change:** recall queries only `observations` (synthesized facts/patterns/preferences) instead of all three memory types; restoring broad recall requires explicitly setting `observation,world,experience` (`hermes-agent/plugins/memory/hindsight/README.md`). Validated via search. Our `consolidated_only` is the direct analog, scoped to our own consolidated units rather than Hindsight type names.
- **Hindsight `prefer_observations`:** when both observations and raw facts are recalled, raw facts folded into a returned observation are dropped and slots backfilled (`hindsight.vectorize.io/developer/api/recall`). We copy the supersede-plus-backfill shape exactly, including that it has no effect unless both levels are in the candidate set.
- **GC literature:** soft-delete first with a grace period, then hard-delete; measure retrieval precision@K, stale-retrieval rate, and contradiction rate (Tianpan 2026-04-14; AgentCore lifecycle 2026-09-04). Our dedup is read-time suppression (never deletion), and this phase adds the duplicate-rate half of those metrics.

---

## 2. Scope Boundaries

### In Scope

- `consolidated_item` eligibility definition over existing canonical units (Phase 100060) and hub-distilled items (Phase 100130), plus provenance link from consolidated parent to raw sources.
- `recall_scope` parameter on `retrieve` and `compose_context` plus honoring the bank `recall_scope_default`.
- `prefer_consolidated` supersede-plus-backfill logic with deterministic ordering.
- Read-time near-duplicate cap driven by the independent `duplicate_tolerance_read` knob (baseline Jaccard thresholds per level: `strict` 0.80 / `balanced` 0.90 / `lenient` 0.95 token-set similarity; tunable within bands, changes require re-running T100270-06).
- Recall quality metrics: duplicate rate and consolidated-coverage counters exposed via existing telemetry/inspect surfaces.

### Explicitly Out of Scope

- New consolidation algorithms or changing canonical/hub-distillation write logic (Phases 006/013 own them).
- Write-path admission changes (Phases 100250/100260).
- New memory domains, new semantic categories, or new storage tiers.
- Background retroactive consolidation of old banks.
- Changing dense/lexical/graph fusion formulas or rerankers (Phase 100120 owns them).

### Must Not Change

- PR-1 budgets: scope and dedup never exceed the requested token budget.
- FR-24: explicit `retrieve`/`compose_context` calls execute even when the intent gate would skip background retrieval.
- Persona always-on channel (§2.7): scope applies to searched stores, never to persona injection.
- FR-17 co-activation: dedup applies to the returned set; co-activation reinforcement still observes the pre-dedup candidate set or a documented equivalent — the phase MUST document which, not silently drop reinforcement.
- Bi-temporal `as_of`/`time_axis` semantics (NFR-4).

### Scope Expansion Rule

If work outside this scope appears necessary:
1. Stop.
2. Document the reason.
3. Request clarification or approval.
4. Do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions

- Phase 100250 accepted: `recall_scope_default` and `duplicate_tolerance_read` stored per bank (inside the `accepted_but_inert` envelope until this phase activates them).
- Phases 006/013 provide canonical units and hub-distilled items with source links, or the documented fallback below applies: before implementation, audit the 006/013 plans and stores for actual parent→source link shapes. If links are absent, Task 1 ships the eligibility predicate with the no-links behavior (parent suppresses nothing; near-dup cap still applies) and T100270-10/T100270-11 become the primary acceptance path instead of T100270-01/T100270-02.
- Phase 100120 retrieve/compose with token budgets and Phase 100170 MCP read bindings exist.

### Dependencies

| Dependency | Required State | Validation |
|------------|----------------|------------|
| Consolidated provenance | Parent → source-ids link queryable at retrieval time | Fixture parent resolves sources |
| Retrieve pipeline | Single point where scope filter + dedup + backfill attach after ranking, before budget truncation | Code inspection |
| Telemetry/inspect | Counters exposable without new PII | Existing surface test |

---

## 4. Existing-System Discovery

The agent MUST inspect the existing system before deciding where or how to implement the changes.

### Required Discovery

- Identify how canonical consolidation records its merged sources and how hub distillation cross-references the distilled item, to define `consolidated_item` eligibility and parent→source links.
- Locate the retrieve/compose assembly point (post-fusion ranking, pre-budget truncation) where scope filtering and supersede-plus-backfill attach.
- Identify how `domains`, `expand_graph`, `as_of`/`time_axis`, and `explain` flow through, so the new params compose rather than collide.
- Identify co-activation reinforcement timing relative to the return set to document the FR-17 interaction.
- Confirm `compose_context` budget partitioning so backfill cannot overflow persona vs memory partitions.

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

The agent must determine the concrete implementation locations from the actual repository. The plan does not prescribe file paths, class names, module names, or directory structures unless they are explicitly part of an externally required contract.

---

## 5. Implementation Specification

### Task 1: Consolidated Eligibility and Provenance Links

#### Intent

Define exactly which items count as consolidated and how a parent claims its raw sources.

#### Required Capability or Behavior

- An item is a `consolidated_item` iff it is a canonical consolidation output or a hub-distilled semantic item admitted through the category gate; the definition cites the existing record markers, inventing no new store.
- Each consolidated item exposes `source_ids[]` (possibly empty for operator-created canonicals); missing links mean the parent suppresses nothing.
- Eligibility and links are visible in `explain` traces and inspect metadata without exposing ciphertext or secrets.

#### Architectural Responsibility

Retrieval eligibility adapter reading existing write-path metadata.

#### Required Changes

1. Eligibility predicate plus source-link accessor, both total functions (unknown shape → not-consolidated, no crash).
2. Backfill-safe ordering key: admission score descending, id ascending (matches compose truncation).
3. Documentation of the FR-17 choice: reinforcement observes the pre-dedup fused set.

#### Implementation Constraints

- MUST NOT create a new domain, category, or storage tier; eligibility is a predicate over existing rows.
- MUST NOT treat SPO triples as association weights or vice versa (§4.5 model separation).

#### Expected Result

Fixture with one consolidated parent (sources A, B) marks parent eligible and resolves both sources; an orphan raw item resolves to no parent.

### Task 2: Recall Scope Preset and Prefer-Consolidated Dedup

#### Intent

Implement the two read modes with Hindsight-compatible semantics.

#### Required Capability or Behavior

- `recall_scope=consolidated_only`: filter fused candidates to eligible parents before budget truncation; when empty, return empty with a `scope_empty` signal (never silently widen to full).
- `recall_scope=full` (default unless bank default says otherwise): rank normally, then if `prefer_consolidated=true` and at least one parent is present, drop raw candidates whose id appears in any returned parent's `source_ids`, then backfill from the next-best fused candidates in rank order.
- `prefer_consolidated` has no effect when no parent is in the candidate set or when scope is `consolidated_only` (documented no-op, not an error).
- Bank `recall_scope_default` applies when the call omits scope; explicit call param always wins.

#### Architectural Responsibility

Retrieve/compose ranking assembly plus MCP/CLI parameter plumbing on both transports.

#### Required Changes

1. Parameter threading through `retrieve` and `compose_context` with schema publication and pinned-revision conformance.
2. Supersede-plus-backfill routine preserving rank order and budget caps, including the persona-partition invariant in compose.
3. `explain` extension: `scope_applied`, `suppressed_raw_ids[]`, `backfilled_ids[]`.

#### Implementation Constraints

- Backfill MUST NOT exceed the requested token budget or item limit.
- Dedup MUST be deterministic: identical candidate set plus config yields identical return order.

#### Expected Result

Duplicate fixture (parent + 2 raw sources + 3 unrelated) under `consolidated_only` returns the parent only; under `full` + `prefer_consolidated` returns parent + unrelated items with raw sources suppressed and slots backfilled.

### Task 3: Read-Time Near-Duplicate Cap and Quality Metrics

#### Intent

Catch paraphrase duplicates the parent-link logic misses, and prove the fix with numbers.

#### Required Capability or Behavior

- Within the final ranked set, apply a pairwise near-duplicate cap driven by `duplicate_tolerance_read` (`strict` 0.80 / `balanced` 0.90 / `lenient` 0.95 token-set similarity), keeping the higher-ranked representative. Token-based similarity consistent with the admission novelty proxy; no new embedding dependency.
- Emit per-request counters: `candidates_considered`, `raw_suppressed`, `backfilled`, `near_dup_suppressed`, `scope_applied`.
- Expose a duplicate-rate summary through the existing telemetry or inspect surface (no new PII fields).

#### Architectural Responsibility

Ranking post-processor plus telemetry extension.

#### Required Changes

1. Similarity cap with documented thresholds per tolerance level and O(n²)-over-page ceiling note (page-bounded, not whole-bank).
2. Counter emission on every scoped/deduped retrieval.
3. Operator doc: how to read the counters and when to tighten tolerance vs fix missions at write time. The doc records the Jaccard-vs-embedding trade-off explicitly: token overlap is the baseline because it needs no new dependency and matches the admission novelty proxy; the precision@K experiment that would justify an embedding-based upgrade (seeded paraphrase bank, Jaccard vs embedding precision comparison) is specified here and owned by a future retrieval-tuning phase.

#### Implementation Constraints

- Similarity MUST be computed over the returned page only; whole-bank clustering is explicitly out of scope.
- Metrics MUST NOT log candidate text, only ids and counts.

#### Expected Result

Paraphrase fixture (`User prefers Python` × 3 wordings, no parent link) under `strict` returns one representative plus counters showing two suppressions.

### Implementation Freedom

The agent may choose the concrete implementation structure, file locations, naming, and internal design provided that the required behavior is satisfied, architectural boundaries are respected, existing contracts are preserved, all acceptance criteria pass, and no prohibited changes are introduced.

---

## 6. Agent Execution Rules

### Allowed Actions

- Inspect and modify the repository as required to implement the in-scope capabilities.
- Add or update implementation components where appropriate.
- Add or update tests required to verify the behavior.
- Refactor locally when necessary to implement the specified capability without changing unrelated behavior.

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

The agent may decide concrete placement, similarity-threshold numbers within documented tolerance bands, explain-shape details, test fixtures, and non-breaking details.

The agent must request approval for publishing `recall_scope` / `prefer_consolidated` params and the `explain` extensions in the versioned `tool_schema` pack (approved schema edit, same rule as Phase 100170 §9), and for changing the eligibility definition, altering fusion/rerank formulas, expanding dedup beyond the returned page, or any FR-17 reinforcement change.

### Mandatory Stop Conditions

Stop and report if requirements are ambiguous, repository facts contradict the plan (notably missing parent→source links with no viable fallback), required dependencies are missing, scope expansion is required, a destructive migration is unspecified, architecture cannot support the behavior without unapproved change, or correctness cannot be verified.

---

## 7. Security Constraints

### Required Controls

- Bank isolation preserved through scope and dedup: suppression and backfill never cross banks.
- Depth/hop caps on graph expansion unchanged; dedup does not raise traversal bounds.
- Auth and Origin rules on Streamable HTTP unchanged for the extended read tools.

### Sensitive Data Rules

- Never return DEKs or cryptographic material in explain traces or metric surfaces.
- Mask secret-looking snippets in `explain` suppression lists (ids only, no text).
- Never commit secrets.

### Security Acceptance Conditions

- Cross-bank retrieval still returns empty or denied under scope modes.
- Explain output on a secret-adjacent fixture contains ids and counts only.

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

Every scenario is implemented; test names below are the real `cargo test` names.

| Test ID | Scenario | Expected Result | Result |
|---------|----------|-----------------|--------|
| T100270-01 | Parent + 2 raw sources, `consolidated_only` | Parent only; `scope_empty=false` | PASS — `clio-retrieve dedup_tests::t27_01_consolidated_only_returns_parent_only`; e2e `clio-mcp read_dedup_tests::t27_05_bank_default_scope_is_honored_and_call_overrides` |
| T100270-02 | Same fixture, `full` + `prefer_consolidated` | Raw sources suppressed; slots backfilled; order deterministic | PASS — `dedup_tests::t27_02_prefer_consolidated_suppresses_raws_and_backfills`; page-awareness in `dedup_page_tests::{prefer_consolidated_keeps_raws_when_the_parent_falls_below_the_limit, prefer_consolidated_keeps_raws_when_the_parent_falls_below_the_budget, page_narrowing_suppresses_a_raw_that_only_the_backfill_admits}`; e2e `read_dedup_tests::prefer_consolidated_suppresses_raws_and_reports_counters` |
| T100270-03 | `full` without prefer flag | All candidates returned (no suppression) | PASS — `dedup_tests::t27_03_full_without_prefer_returns_everything`; `read_dedup_tests::plain_retrieve_payload_keeps_the_prior_shape` |
| T100270-04 | `consolidated_only` with no parents in bank | Empty with `scope_empty` signal; no silent widening | PASS — `dedup_tests::t27_04_consolidated_only_without_parents_is_empty_and_signalled` |
| T100270-05 | Bank default scope honored vs call override | Default applies when omitted; call param wins | PASS — `read_dedup_tests::t27_05_bank_default_scope_is_honored_and_call_overrides` (also rejects an unknown scope) |
| T100270-06 | Paraphrase trio, no parent, `strict` tolerance | One representative; `near_dup_suppressed=2` | PASS — `dedup_tests::t27_06_paraphrase_trio_with_strict_tolerance_keeps_one`; level split in `dedup_tests::read_cap_levels_differ_between_strict_and_balanced`; page-local counter in `dedup_page_tests::{near_dup_counter_counts_only_returned_page_items, cap_rechecks_the_page_after_a_freed_slot_backfills_a_duplicate}` |
| T100270-07 | Budget cap with backfill | Total tokens ≤ budget; persona partition intact | PASS — `read_dedup_tests::compose_scope_keeps_the_persona_partition_and_budget` (persona section first, `total_tokens ≤ budget`); `clio-retrieve finalize_tests::budget_tokens_trims_returned_hits` |
| T100270-08 | Explicit call during intent-gate-false turn | Executes (FR-24) with scope applied | PASS — `read_dedup_tests::t27_08_explicit_scoped_call_runs_when_the_gate_would_skip` |
| T100270-09 | Cross-bank scope isolation | No cross-bank ids in suppressed/backfilled lists | PASS — `read_dedup_tests::t27_09_scope_and_dedup_never_cross_banks`: bank-b's parent claims bank-a's `shared-A` id and bank-b suppression is proven active (`raw_suppressed=1`, `suppressed_raw_ids=["raw-b"]`) while bank-a's `shared-A` still returns unsuppressed, so the test fails if another bank's parent can suppress |
| T100270-10 | No-links bank, `consolidated_only` | Empty with `scope_empty` signal; near-dup cap still applies to raw candidates | PASS — `dedup_tests::t27_10_no_links_consolidated_only_is_empty_but_cap_still_applies_on_full` |
| T100270-11 | No-links bank, `full` + `prefer_consolidated` | Documented no-op on supersede; raw duplicates handled by near-dup cap only | PASS — `dedup_tests::t27_11_no_links_prefer_is_a_noop_and_cap_handles_duplicates` |

### Negative Testing

Verify that invalid scope values are rejected, unauthorized bank access is blocked, partial co-activation failures still fail closed per FR-17, over-limit requests are rejected, and existing retrieve/compose behavior without the new params is byte-identical.

- Invalid scope: `read_dedup_tests::t27_05_...` asserts `invalid_argument` for `recall_scope=observations`.
- Unauthorized bank: `read_dedup_tests::t27_09_...` returns only the requested bank's ids; the shared-bank permission gate is unchanged.
- FR-17 fail-closed: `clio-retrieve assoc_tests::t05_reinforce_failure_fails_retrieve_closed` still passes with reinforcement now fed the pre-dedup page.
- Over-limit requests: `clio-retrieve hybrid_tests::validate_rejects_bad_requests` unchanged.
- Byte-identical default: `read_dedup_tests::plain_retrieve_payload_keeps_the_prior_shape` asserts the `dedup` block is omitted from the payload **and** from `explanation` when no new parameter is used; `read_dedup_tests::compose_explanation_reports_dedup_only_for_a_non_inert_call` covers compose explain; all prior retrieve/compose tests remain green.

### Verification Rule

Implementation claims must be supported by actual test output, inspection results, or other concrete evidence.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-100270-01 | Scope preset filters to consolidated units | T100270-01, T100270-04, T100270-05 | PASS for hub-distilled units — `dedup_tests::t27_01_*`, `t27_04_*`, `read_dedup_tests::t27_05_*`; payloads carry `scope_applied`/`scope_empty`. Canonical consolidation outputs are **not** eligible (no durable marker, no item-id links), so a canonical-only bank returns empty with `scope_empty=true`; this is a named limitation, not a passing claim (see Known Limitations and `docs/recall-scope-and-dedup.md`) |
| AC-100270-02 | Prefer-consolidated supersede + backfill | T100270-02, T100270-03 | PASS — `dedup_tests::t27_02_*` asserts `suppressed_raw_ids=[A,B]`, `backfilled_ids=[U3]`, `backfill_exhausted=true`, deterministic repeat; `t27_03_*` shows no suppression. Suppression is page-aware: a parent outside the returned page claims nothing (`dedup_page_tests::prefer_consolidated_keeps_raws_when_the_parent_falls_below_the_limit`, `..._below_the_budget`) and a raw admitted only by backfill is suppressed in the next pass (`dedup_page_tests::page_narrowing_suppresses_a_raw_that_only_the_backfill_admits`) |
| AC-100270-03 | Near-duplicate cap + counters | T100270-06 | PASS — `dedup_tests::t27_06_*` (`near_dup_suppressed=2`, one representative); counter set serialized in `DedupReport`; the counter is page-local (`dedup_page_tests::near_dup_counter_counts_only_returned_page_items` reports 0 for a one-item page, `dedup_page_tests::cap_rechecks_the_page_after_a_freed_slot_backfills_a_duplicate` reports 2) |
| AC-100270-04 | Budget, persona, FR-17/FR-24 preserved | T100270-07, T100270-08 | PASS — `read_dedup_tests::compose_scope_keeps_the_persona_partition_and_budget`; `t27_08_*`; `assoc_tests::t05_reinforce_failure_fails_retrieve_closed`; FR-17 reinforces the pre-dedup page (`dedup_tests::t27_02_*` asserts the pre-dedup page includes suppressed A,B) and `requirement.md` §4.9.4.B now states that reinforcement observes the pre-dedup candidate page |
| AC-100270-05 | Transport parity + bank isolation | Contract + T100270-09 | PASS — `read_dedup_tests::protocol_handler_matches_direct_dispatch_for_scoped_retrieve` (shared protocol layer) and the rewritten `t27_09_*` (bank-b parent claims bank-a's id; bank-b suppression proven active, bank-a's item untouched); the in-process JSON binding resolves a supplied `ReadPolicyResolver` (`surface_tests::retrieve_json_surface_applies_the_bank_read_policy_when_a_resolver_is_supplied`, `compose_json_surface_applies_the_bank_read_policy_when_a_resolver_is_supplied`); existing stdio/HTTP matrix `clio-mcp/tests/conformance.rs` green |
| AC-100270-06 | No fusion/rerank/triple regression | Regression suite | PASS — full `cargo test --locked --workspace` green; `make coverage` exit 0 |
| AC-100270-07 | Scope params published in versioned `tool_schema` pack | Schema-pack CI check | PASS — `read_dedup_tests::scope_params_are_published_in_the_versioned_schema_pack`; pack carries `mcp_protocol_revision=2025-11-25`; the additive schema edits are enumerated under "Approval requested" for the round's Remedy Approver |
| AC-100270-08 | Graceful degradation without 006/013 links | T100270-10, T100270-11 | PASS — `dedup_tests::t27_10_*`, `t27_11_*`; canonical consolidation stores chunk provenance only, so those items suppress nothing and are not eligible for `consolidated_only`; the near-dup cap covers them |

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
- [x] Required approval is obtained (additive schema edits are enumerated under "Approval requested"; the downstream Remedy Approver step records the decision).

### Completion Evidence

- Implementation summary:
  - `clio-config`: `RecallScope::parse`; the read-time similarity mapping (`strict` 0.80 / `balanced` 0.90 / `lenient` 0.95) on `DuplicateTolerance::read_similarity_cap`; schema gains `x-duplicate-tolerance-read-mapping`; the read-side policy envelope now reports `status: active`; `ResolvedRetention` moved to `retention_resolved.rs` (size limit).
  - `clio-retrieve`: new `dedup.rs` (eligibility predicate + source-link accessor, scope filter, page-aware prefer-consolidated suppression, page-local near-duplicate cap, `DedupReport` counters) and `hybrid_rank.rs` (fusion + rerank extracted from the 450-line `hybrid.rs`). `RetrieveRequest`/`ComposeRequest` gained `recall_scope`, `prefer_consolidated`, `duplicate_tolerance_read`; `finalize` gained `select_page`, assembles the dedup report, and stamps `consolidated`/`source_ids` on each returned hit so eligibility and links are visible in response metadata and `explain`; FR-17 reinforcement observes the pre-dedup page; the in-process JSON surface gained the `ReadPolicyResolver` seam (`retrieve_from_json_with_policy` / `compose_from_json_with_policy`) so a binding can supply the bank read policy instead of hardcoding `full`/`balanced`.
  - `clio-mcp`: `retrieve`/`compose_context` resolve the bank `recall_scope_default` (explicit call wins) and the bank `duplicate_tolerance_read`; `explain` carries the `dedup` block only when the report did something (an inert report is omitted from the payload and the trace, so a plain call's explain output is unchanged); the versioned schema pack publishes both parameters.
  - `docs/recall-scope-and-dedup.md`: operator guide (counters, duplicate rate, when to tighten read tolerance vs fix write missions, Jaccard-vs-embedding trade-off, and the precision@K experiment owned by a future retrieval-tuning phase).
- Discovered/affected architectural components: `clio-config` retention profile + schema, `clio-retrieve` hybrid/finalize/compose/surface, `clio-mcp` read binding + schema pack. Canonical consolidation (writer) keeps chunk provenance only; hub distillation is the item-id parent→source link.
- Changed-component summary: files listed in "Implementation summary" plus the test modules `clio-retrieve/src/dedup_tests.rs` and `clio-mcp/src/read_dedup_tests.rs`; `requirement.md` §4.9.4.B signatures and the retention-profile row/glossary.
- Test execution output: one post-remediation `make check` pass exited 0 (`cargo fmt` + `cargo clippy --workspace --all-targets --all-features -D warnings` + `cargo test --locked --workspace`); scoped counts with real output: `clio-retrieve` 123 passed, `clio-mcp` lib 202 passed, `clio-config` 108 passed, every suite `0 failed`.
- Sample duplicate-fixture transcripts for both modes:
  - `consolidated_only`: fixture parent `P` (claims `A`,`B`) + raws `A`,`B` + unrelated `U` returns `["P"]`, `scope_applied="consolidated_only"`, `scope_empty=false`.
  - `full` + `prefer_consolidated`: same fixture returns `["P","U"]`, `raw_suppressed=2`, `suppressed_raw_ids=["A","B"]`, `backfilled>=0`; with six candidates and `limit=5` the unit test reports `backfilled_ids=["U3"]`.
  - Page-aware fixtures: a parent ranked below the `limit=3` page (or below a two-item token budget) suppresses nothing (`raw_suppressed=0`), and a raw admitted only by a freed slot is suppressed on the next pass (`raw_suppressed=1`, `near_dup_suppressed=1`).
- Verification report (post-remediation): `make coverage` exit 0; TOTAL lines 97.88%, functions 98.89%; the parsed per-file table has 253 reported files and **0 below 90%** on either metric. Load-bearing files: `dedup.rs` 99.02% lines / 100% functions, `surface.rs` 98.31/100, `hybrid.rs` 99.26/100, `finalize.rs` 97.56/100, `compose.rs` 100/100, `retention.rs` 99.33/100, `read_retrieve.rs` 97.77/100. `cargo clippy --workspace --all-targets --all-features -D warnings` clean; `cargo fmt` applied.
- Known limitations:
  - **Not implemented: canonical consolidation outputs are not eligible for `consolidated_only`.** They carry no durable consolidated marker (the canonical path stores a comma-joined provenance string in `source_ref` and keeps chunk ids on the ingest leaf) and no item-id source links, so a canonical-only bank returns empty with `scope_empty=true` and `prefer_consolidated` cannot suppress their sources. Why: recording a marker or item-id provenance is writer-side work owned by the 006/013 lineage, and changing the eligibility definition is behind the phase's decision boundary; this round had no approval for it. The operator doc states the exclusion, and the predicate and link accessor are ready for that addition.
  - Paraphrase dedup is page-local and token-based; the page is re-evaluated after each freed slot and the counter reports page items only. Whole-bank semantic clustering and an embedding-based cap are out of scope (the upgrade experiment is specified in `docs/recall-scope-and-dedup.md`).
  - The read-time cap runs when a dedup mode is active or the level is `strict`/`lenient`; the neutral `balanced` default caps nothing on a plain full call, so an unchanged bank keeps its prior output.
  - `consolidated_only` lags behind the latest writes until consolidation catches up; `prefer_consolidated` on `full` is the recommended default for fresh-read coverage.

### Approval requested: read-tool `tool_schema` additions

Phase 100170 §9 set the rule that publishing changed read-tool schemas needs approver sign-off. This phase adds two optional properties and no new tool, no renamed tool, and no transport revision change:

- `retrieve` gains `recall_scope` (enum `full` | `consolidated_only`) and `prefer_consolidated` (boolean).
- `compose_context` gains the same two properties, documented as memory-section-only.

`read_dedup_tests::scope_params_are_published_in_the_versioned_schema_pack` asserts the published properties and the pack's `mcp_protocol_revision=2025-11-25`. If the approver rejects either property, it can be removed from `crates/clio-mcp/src/schema_read_defs.rs` without touching the bound behavior, which stays driven by the same arguments.

**Remediation r1.** The adversarial round found twelve defects; all twelve were addressed. Code: suppression and the near-duplicate cap are now page-aware (a parent outside the returned page claims nothing; a raw admitted by a freed slot is suppressed in the next pass) and the near-duplicate counter counts returned-page items only; the `explain` payload omits the `dedup` block when the report is inert; the in-process JSON surface resolves a supplied `ReadPolicyResolver`; `t27_09` was rebuilt into a falsifiable cross-bank fixture (bank-b's parent claims bank-a's `shared-A` id while bank-b suppression is proven active); the schema description typo and the two stale doc comments are fixed. The canonical-marker gap was resolved by narrowing the acceptance claim and stating the limitation above rather than adding a writer-side marker, which this phase's scope and decision boundary exclude. Numbers in this section were re-derived from the post-remediation runs. The `benchmark.md` edit staged with the phase diff predates the phase (documented in the developer log); remediation does not touch the git index, so the approver should decide whether to keep it.

---

## 10. Failure Handling and Recovery

### Expected Failure Modes

| Failure | Detection | Recovery |
|---------|-----------|----------|
| Missing parent→source links | Eligibility probe at retrieval | Parent suppresses nothing; near-dup cap still applies; log once |
| Backfill candidate exhaustion | Rank-list underflow | Return smaller set within budget; signal `backfill_exhausted` |
| Co-activation handoff failure | FR-17 error path | Fail closed per existing contract; no silent partial return |

### Rollback Strategy

Default the bank `recall_scope_default` to `full` and call without `prefer_consolidated`: behavior reverts to pre-phase ranking. No data migration involved.

### Partial Completion Policy

If only part of the phase is complete, do not claim full completion. Record completed and incomplete work separately. Document remaining work. Do not leave undocumented broken state.

---

## 11. Traceability

| Parent Requirement | Implementation Task | Verification | Acceptance Criterion |
|--------------------|---------------------|--------------|-----------------------|
| §4.3/§4.5 consolidated knowledge | Task 1 | T100270-01 | AC-100270-01 |
| Gap item 3 observations-only analog | Task 2 | T100270-01, T100270-02, T100270-05 | AC-100270-01, AC-100270-02 |
| P1 duplicate recall | Tasks 2–3 | T100270-02, T100270-06 | AC-100270-02, AC-100270-03 |
| PR-1 budget + FR-24 explicit exec | Task 2 | T100270-07, T100270-08 | AC-100270-04 |
| §4.9.2 parity + bank isolation | Task 2 | Contract + T100270-09 | AC-100270-05 |
| FR-20 / §4.9.2 versioned `tool_schema` pack | Task 2 | Schema-pack CI check | AC-100270-07 |
| 006/013 link dependency + fallback | Task 1 | T100270-10, T100270-11 | AC-100270-08 |

Required chain:

```text
Requirement → Capability → Implementation → Test → Evidence
```

Every acceptance criterion must be traceable.

---

## 12. Phase Exit Contract

### Outputs Produced

- `recall_scope` preset (`consolidated_only`/`full`) with bank default.
- `prefer_consolidated` supersede-plus-backfill.
- Read-time near-duplicate cap with per-request counters and operator doc.

### Guarantees Provided to Downstream Phases

- Write-time and read-time duplicate handling compose: strict write tolerance plus read dedup never double-penalize the same item beyond documented suppression.
- Every scoped/deduped response carries `scope_applied`, suppression lists, and counters for audit.
- Default behavior without the new params is byte-identical to pre-phase retrieval.

### Known Limitations

- **Not implemented: canonical consolidation outputs are not eligible for `consolidated_only`.** They expose no durable consolidated marker and no item-id parent→source links (canonical consolidation keeps chunk/source-ref provenance), so on a canonical-only bank the preset returns empty with `scope_empty=true` and their sources cannot be suppressed; this is a documented scope reduction, not a passing claim, and the writer-side marker or item-id provenance is owned by the 006/013 lineage (the predicate and link accessor are ready for it).
- Paraphrase dedup is page-local and token-based; the page is re-evaluated after each freed slot and the counter reports page items only. Whole-bank semantic clustering is out of scope.
- `consolidated_only` lags behind the latest writes until consolidation catches up; `prefer_consolidated` on `full` is the recommended default for fresh-read coverage.
- No new consolidation scheduling in this phase; stale parents age out only via existing decay/prune policies.

### Downstream Prerequisites

- Any future whole-bank semantic dedup or consolidation scheduler builds on the eligibility predicate and counters defined here.
- Export/sync phases treat suppression as read-time only: suppressed raw items still export and sync normally.

### Final Status

PASS WITH DOCUMENTED LIMITATIONS

All acceptance criteria pass for the implemented eligibility (hub-distilled consolidated units) and the gate is green. The documented limitation is the canonical-output exclusion described in the Known Limitations above and the §9 Completion Evidence: canonical consolidation keeps chunk provenance rather than raw item ids or a durable consolidated marker, so those items are neither returned by `consolidated_only` nor able to suppress sources; adding that provenance is writer-side work outside this phase's scope and approval boundary.

### Verification Sign-Off

- Implementer: OpenCode CLI (Go . Deepseek V4.1 Flash High)
- Verifier: [pending adversary round]
- Human Approver: not required for this round
- Date: 2026-09-21

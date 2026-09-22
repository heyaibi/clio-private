# Phase 100250: Per-Bank Retention Profiles with Verbosity and Batch Dry-Run

### Attribution
Rounds below record plan authorship; implementation sign-off is in §12.
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | OpenCode CLI (Together . GLM-5.3 Flash High) | done |
| Adversary | r1 | OpenCode CLI (OpenRouter . Deepseek V4.1 Flash Max) | done |
| Remediator | r1 | OpenCode CLI (Together . GLM-5.3 Flash High) | blocked |
| Remediator | r2 | OpenCode CLI (Go . Deepseek V4.1 Flash High) | done |
| Remedy Approver | r1 | Antigravity CLI (Gemini 3.8 Flash) | approved |
| Finalize | r1 | OpenCode CLI (Go . Deepseek V4.1 Flash High) | done |

**Index slice 100250 · **Effort:** `1×` · **Scope:** `gap/hindsight-noise-overcapture.md` items 1 and 4 (partial)

### Vocabulary (read first) — zero shared moniker

| Term | Enum / form | Where it lives | Must not |
|------|-------------|----------------|----------|
| **`retention_profile`** | Per-bank named policy object (`verbosity`, thresholds, `duplicate_tolerance_write`, `duplicate_tolerance_read`, `recall_scope_default`) | Config layer, bank-scoped | Be conflated with deployment **`ranking_env`** weights or named process **`profile`** (`coding_local`) |
| **`verbosity`** | `selective` \| `balanced` \| `permissive` | `retention_profile` field only | Be conflated with process log verbosity, an LLM extraction prompt mode, or Hindsight `verbatim` chunk preservation (our `permissive` was named `verbatim` in draft and renamed for exactly this collision) |
| **`duplicate_tolerance_write`** | `strict` \| `balanced` \| `lenient`, per-bank; admission-time novelty cutoff only | `retention_profile` field only | Be conflated with **`novelty`** factor score, hygiene `hygiene_noise_score`, or the read-side cap `duplicate_tolerance_read` |
| **`duplicate_tolerance_read`** | `strict` \| `balanced` \| `lenient`, per-bank; read-time page similarity cap only (mapping defined in Phase 100270) | `retention_profile` field, honored by the recall-side dedup capability (Phase 100270) | Be conflated with `duplicate_tolerance_write`; the two knobs share level names but have independent defaults and mappings |
| **`admit_preview_batch`** | Dry-run scoring of N candidates without write | Admission service | Mutate stores or bypass the category gate |

## 1. Objective

### Goal

Give every bank a user-tunable retention profile that controls how strict admission is at write time, without editing code or touching global scoring weights. The profile carries a three-level verbosity knob, per-category threshold offsets, and a duplicate tolerance setting. Operators can dry-run a batch of candidates through `admit_preview` to see what would be stored before turning the profile on.

### Expected Outcome

- Each bank resolves to exactly one effective `retention_profile` with documented defaults.
- Setting `verbosity=selective` admits measurably fewer routine status candidates than `balanced` on the same fixture.
- `admit_preview` accepts a batch of candidates and returns per-item pass/fail with factor breakdown, writing nothing.
- Changing a profile never alters global `ranking_env` weights, category taxonomy, or other banks.

### Parent Requirement

`requirement.md` — P1, PR-3, PR-5, §4.1, §4.2, §4.9.4.A (`admit_preview`), FR-10. Gap source: `gap/hindsight-noise-overcapture.md` items 1 and 4.

### Design References (non-normative)

- **Hindsight extraction modes:** `concise` (default selective) vs `verbose` (detailed) vs `custom` — validated via web search (`hindsight.vectorize.io/llms-full.txt`, commit `3172e99`). Our `verbosity` is the deterministic analog: it shifts admission strictness, not an LLM prompt, because first release has no LLM extractor in the write path.
- **AWS AgentCore lifecycle:** TTL differentiated by memory class plus a single intuitive tuning parameter (`pruneDays`) rather than raw decay constants. We copy the shape: one intuitive `verbosity` knob over documented threshold mechanics.
- **FintekCafe production guide:** write facts in a form that can be contradicted and log everything to cold storage but index a curated subset. Our profile controls the curated-subset gate; it does not delete cold history.

---

## 2. Scope Boundaries

### In Scope

- `retention_profile` schema, per-bank storage, and effective-resolution order (bank override → deployment default → builtin default).
- `verbosity` three-level mapping to per-category threshold offsets and novelty-floor adjustments, fully documented.
- `duplicate_tolerance_write` three-level mapping to the novelty-factor duplicate cutoff used at admission time.
- `duplicate_tolerance_read` field reserved with an independent default; mapping and honoring belong to Phase 100270 (the recall-side dedup capability).
- Batch form of `admit_preview` (`items[]` in, per-item decisions out), read-only.
- Config/MCP/CLI surface to get, set, and validate a bank profile, with secret-safe errors.

### Explicitly Out of Scope

- Mission/keep-drop example lists (Phase 100260).
- Recall-side scope presets and read-time dedup (Phase 100270).
- Changes to five-factor formulas, category taxonomy, or global `ranking_env` defaults.
- Automatic background re-scoring of already-stored items under a new profile.
- LLM-based extraction prompts or offline training of the extractor.

### Must Not Change

- Closed taxonomy in §4.1: no sixth semantic category.
- Gate enforcement inside tools (PR-5); transport cannot bypass admission.
- `epistemic_kind` vs `update_rule` vocabulary split.
- PR-6 three-way separation: profile strictness never deletes, invalidates, or shreds anything.

### Scope Expansion Rule

If work outside this scope appears necessary:
1. Stop.
2. Document the reason.
3. Request clarification or approval.
4. Do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions

- Phase 100040 admission gates and `admit_preview` single-item path exist.
- Phase 100010 config profiles and `ranking_env` patch validation exist.
- Phase 100160/100170 MCP dispatcher can register extended config tools with identical stdio/Streamable HTTP semantics.

### Dependencies

| Dependency | Required State | Validation |
|------------|----------------|------------|
| Admission scorer | Five-factor scoring with per-key thresholds | Phase 100040 tests green |
| Config store | Bank-scoped overlay persistence that survives upgrades | Set profile, restart, re-read |
| MCP dispatcher | Shared handler for stdio + Streamable HTTP | Parity test on new tools |

---

## 4. Existing-System Discovery

The agent MUST inspect the existing system before deciding where or how to implement the changes.

### Required Discovery

- Identify where `ranking_env` weights, `theta_admit`, and per-key overrides live and how patches are validated.
- Locate the single-item `admit_preview` handler and the novelty-factor neighbor lookup it uses.
- Identify the bank-resolution path (`bank` arg → connection default → profile default) to attach profile resolution.
- Identify existing config get/set tools to reuse validation and masking conventions.
- Confirm no existing per-bank retention object already exists under another name.

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

### Discovery Output

Recorded by the r1 developer before implementation:

- **Relevant subsystems identified.** Config layer = `clio-config` (`config::Runtime` tool handlers, `ranking.rs` for `RankingEnv`, `admission_knobs.rs` for `theta_admit`/`theta_overrides`/`type_prior_overrides`, `profile.rs` for the named-process-profile inventory). Admission layer = `clio-admission` (pure logic: `policy.rs`, `decision.rs`, `factors.rs`, `gated.rs`). Binding layer = `clio-mcp` (schema pack + one shared `McpHandler` used by both stdio and Streamable HTTP). CLI = `clio-lib` (`am` binary: `mcp`, `ops` subcommands).
- **Existing implementation approach.** `theta_admit` is a global in `RankingEnv` with per-key `theta_overrides`; `AdmissionPolicy::new(&RankingEnv)` resolved thresholds at score time. The single-item `admit_preview` is `clio-mcp::write_tools::store_path(allow_write=false)`, which runs the same `clio_write::gated_store_verified` path as `store` (span verify, category gate, five factors, threshold) and returns the §4.9.4.A decision shape. The novelty signal comes from an injected `SignalSource`; the MCP runtime supplies `NoSignals` (empty neighbors).
- **Relevant contracts/interfaces.** `Decision { pass, admission_score, factors, rejection_reason? }`; `AdmissionPolicy`; `ToolResult<T>` (`{ok, …}` with flattened payload); `RetentionStore` did not exist. Config tools (`config_get`/`config_set`/`ranking_env_*`) exist in-process in `Runtime` but were **not** MCP-bound, and were absent from the published `tool_schema` pack.
- **Existing test coverage.** Admission, gated writes, config/ranking, schema pack, transports, and the `gate_boundary_tests` guard (which fails if a direct `create_memory_item(` caller appears outside an allowlist).
- **Architectural constraints discovered.** (a) `clio-admission` must stay I/O-free, so profile storage lives in `clio-config` and only a resolved `Copy` snapshot crosses into admission. (b) `make coverage` scans the whole workspace, so no test may create a direct ungated item write. (c) The MCP store path uses `NoSignals`, so novelty is always `1.0` there — profiles still change admission via thresholds, but the novelty floor is only observable through an injected `SignalSource` (unit level).
- **Assumptions confirmed.** Per-bank storage had no existing name; `ranking_env` weights and category taxonomy are separate from retention policy; one shared `McpHandler` gives transport parity for free once a tool is in the bound set.
- **Assumptions contradicted.** The plan implies the profile get/set tools are "extended config tools" already registered over MCP. In the actual repository the `config_*` family is in-process only; this phase therefore had to add the MCP binding and the pack publication for the new tools (the plan's AC-100250-04/AC-100250-06 require exactly that).
- **Questions requiring clarification.** None that blocked work. Two documented decisions: (1) `duplicate_tolerance_write` levels `balanced` and `lenient` both resolve to a `0.0` write-side novelty floor, because the existing regression suite requires a novelty-`0` candidate to be admitted under the default profile (`user_stated_source_lifts_confidence`); only `strict` adds a duplicate-rejection floor. (2) The `tool_schema` pack publication follows the Phase 100170 §9 approved-schema-edit rule; the phase's own AC-100250-06 mandates it.

### Repository Adaptation Rule

The agent must determine the concrete implementation locations from the actual repository. The plan does not prescribe file paths, class names, module names, or directory structures unless they are explicitly part of an externally required contract.

**Chosen locations.** Profile object + mapping + schema publication: `clio-config/src/retention.rs`. Bank-scoped store + resolution order + durable load/save: `clio-config/src/retention_store.rs`. Runtime handlers: `clio-config/src/config/retention_ops.rs`. Admission consumption: `clio-admission/src/policy.rs` + `decision.rs`. MCP tools: `clio-mcp/src/retention_tools.rs`, `runtime_retention.rs`, `schema_retention_defs.rs`, and `store_write.rs` (store-path core extracted from `write_tools.rs` to stay under the 450-line cap). CLI: `clio-lib/src/retention_cli.rs`.

---

## 5. Implementation Specification

### Task 1: Retention Profile Schema and Resolution

#### Intent

Define the profile object and make every admission decision resolve exactly one effective profile.

#### Required Capability or Behavior

- Profile shape: `{ verbosity, theta_offsets{category: delta}, duplicate_tolerance_write, duplicate_tolerance_read, recall_scope_default, version }`. `recall_scope_default` and `duplicate_tolerance_read` are stored here but only honored by the later recall-side scope and dedup capability; until then profile-get responses carry them inside an `accepted_but_inert` envelope with `honored_by: "recall_scope_and_dedup"` so operators never mistake a stored value for an active one. The envelope names the capability, never a roadmap phase: code and the published schema must stand alone after `roadmap/` is deleted.
- Resolution order: bank override → deployment default → builtin default (`balanced` verbosity / `balanced` write tolerance / `balanced` read tolerance / zero offsets / `full` recall default).
- Unknown fields and out-of-range offsets are rejected with structured errors; defaults are documented in one place.

#### Architectural Responsibility

Config layer owning bank-scoped policy; admission layer consuming a resolved snapshot.

#### Required Changes

1. Schema with JSON-Schema publication and version stamp.
2. Resolution function called on every gated write and every preview.
3. Upgrade rule: missing profile reads as builtin default; never fails open or closed on upgrade.

#### Implementation Constraints

- Profile storage MUST be bank-scoped; no cross-bank leakage.
- Offsets MUST be bounded deltas (e.g. ±0.20), not replacement thresholds, so global tuning stays meaningful.

#### Expected Result

Same candidate scored under `selective` vs `balanced` on the same bank fixture yields a strictly smaller or equal admit set for `selective`.

### Task 2: Verbosity-to-Strictness Mapping

#### Intent

Make `verbosity` a single intuitive knob with predictable admission effects.

#### Required Capability or Behavior

- `selective`: raises per-category theta by a documented positive delta and raises the novelty floor (near-duplicates rejected more aggressively).
- `balanced`: zero delta; current behavior unchanged.
- `permissive`: lowers theta by a documented negative delta within bounds; intended for ingest-debug banks, never the coding default. Migration note: drafts named this level `verbatim`; it was renamed because Hindsight `verbatim` means preserving original chunk text, while this level means permissive admission — no chunk text is ever stored.
- Mapping table is published in the schema docs with exact numbers.

#### Architectural Responsibility

Admission policy adapter consuming the resolved profile.

#### Required Changes

1. Threshold computation: `theta_effective = theta_base + verbosity_delta + theta_offset[category]`.
2. Novelty-floor computation from `duplicate_tolerance_write` (Task 1 field, mapping defined here; the read-side cap uses the separate `duplicate_tolerance_read` mapping owned by Phase 100270).
3. Unit fixtures proving monotonicity: `selective ⊆ balanced ⊆ permissive` admit sets on identical inputs.

#### Implementation Constraints

- Do not alter five-factor formula weights; only thresholds and novelty cutoffs move.
- Do not rename `verbosity` values after publication without a migration note.

#### Expected Result

Fixture with 20 routine status candidates admits fewest under `selective`, all-or-most under `permissive`, with per-item reasons logged.

### Task 3: Batch Admit Preview Dry-Run

#### Intent

Let operators see what a profile would store before enabling it.

#### Required Capability or Behavior

- `admit_preview_batch(bank, items[], profile_override?)` returns per-item `{pass, admission_score, factors, rejection_reason?}` plus summary counts `{would_admit, would_reject, by_reason}`.
- Pure read-only: zero writes, zero telemetry mutations, zero side effects on stores or indexes.
- Optional `profile_override` previews a candidate profile without persisting it.

#### Architectural Responsibility

Admission service read path plus MCP/CLI binding.

#### Required Changes

1. Batch handler reusing the single-item scoring path item-by-item with the resolved (or override) profile.
2. Summary aggregation with stable ordering (input order preserved; ties unbroken by reorder).
3. Schema publication for the batch tool on both MCP transports.

#### Implementation Constraints

- Batch size MUST be capped with a documented limit and a clean oversize error.
- Preview MUST run category gate first per item, exactly as real writes do.

#### Expected Result

Operator pastes 10 transcript lines, runs preview under two profiles, and sees which lines each profile would admit, with reasons.

### Implementation Freedom

The agent may choose the concrete implementation structure, file locations, naming, and internal design provided that the required behavior is satisfied, architectural boundaries are respected, existing contracts are preserved, all acceptance criteria pass, and no prohibited changes are introduced.

---

## 6. Agent Execution Rules

### Allowed Actions

- Inspect and modify the repository as required to implement the in-scope capabilities.
- Add or update implementation components where appropriate.
- Add or update tests required to verify the behavior.
- Refactor locally when necessary without changing unrelated behavior.

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

The agent may decide concrete file/module placement, internal structure, local refactoring, test organization, and non-breaking details.

The agent must request approval for:
- Publishing `admit_preview_batch` and the profile get/set tools in the versioned `tool_schema` pack (approved schema edit, same rule as Phase 100170 §9).
- Architecture changes beyond the stated scope, breaking API changes, security-sensitive policy decisions, destructive data operations, and changes affecting downstream phase assumptions (notably the Phase 100260 mission fields and Phase 100270 recall-scope semantics).

### Mandatory Stop Conditions

Stop and report if requirements are ambiguous, repository facts contradict the plan, required dependencies are missing, scope expansion is required, a destructive migration is unspecified, architecture cannot support the behavior without unapproved change, or correctness cannot be verified.

---

## 7. Security Constraints

### Required Controls

- Bank isolation: profile read/write scoped to caller `bank`/`actor`; no cross-bank profile application.
- Confirmation for persisting a profile change when invoked from an agent harness (same destructive-adjacent caution as other mutators).
- Secret-safe errors: profile validation messages never echo secret material.

### Sensitive Data Rules

- Never log candidate content beyond truncated, masked previews in preview responses.
- Never commit secrets.
- Use the approved secret/configuration mechanism.

### Security Acceptance Conditions

- Cross-bank profile read returns not-found or permission-denied, never another bank's profile.
- Unauthenticated Streamable HTTP profile mutation is rejected outside dev mode.

---

## 8. Test and Verification Strategy

### Required Tests

- [x] Unit tests — `clio-config` (retention object/mapping/store/runtime handlers), `clio-admission` (policy + decision + monotonicity + novelty floor), `clio-mcp` (retention tools, runtime accessors, schema defs, transport parity)
- [x] Integration tests — `crates/clio-lib/tests/retention_profile_harness.rs` (T100250-01 … T100250-08 + CLI smoke)
- [x] Contract tests — `crates/clio-lib/tests/inventory_contract.rs` (§4.9.4 Core name set now includes `admit_preview_batch`) and `clio-mcp` schema-pack tests (`catalog_defs` == bound set + `summarize`)
- [x] End-to-end tests — `am retention set|get|schema` through the real `am` binary; stdio vs Streamable HTTP `tools/call` parity test
- [x] Regression tests — full workspace suite green; `clio-store` `gate_boundary_tests::only_gated_path_creates_items` updated for the `store_write.rs` move and green
- [x] Security tests — bank isolation (T100250-06), confirmation requirement on `retention_profile_set`, cross-bank read never returns another bank's profile
- [x] Failure-mode tests — invalid profile / unknown offset key / oversize offset / oversize batch / per-item scoring error / corrupt stored profile / unwritable store path

### Required Test Scenarios

| Test ID | Scenario | Expected Result | Where |
|---------|----------|-----------------|-------|
| T100250-01 | Same 20-item fixture under selective/balanced/permissive | Monotonic admit sets; selective smallest | `retention_profile_harness::t25_01_verbosity_admit_sets_are_monotone` |
| T100250-02 | Batch preview with 10 mixed candidates | Per-item decisions + summary counts; zero writes verified by store diff | `t25_02_batch_preview_reports_decisions_and_writes_nothing` |
| T100250-03 | Preview with profile_override | Override affects only the response, persisted profile unchanged | `t25_03_profile_override_does_not_persist` |
| T100250-04 | Invalid profile (bad verbosity, oversize offset) | Structured rejection; stored profile unchanged | `t25_04_invalid_profiles_are_rejected_and_stored_profile_is_unchanged` |
| T100250-05 | Oversize batch | Clean limit error; nothing scored | `t25_05_oversize_batch_is_a_clean_limit_error` |
| T100250-06 | Cross-bank profile isolation | Bank A profile invisible from Bank B | `t25_06_cross_bank_profile_isolation` |
| T100250-07 | Upgrade with no stored profile | Resolves to builtin default; writes still gate correctly | `t25_07_fresh_runtime_resolves_builtin_default_and_still_gates` |

### Negative Testing

Verify that invalid input is rejected, unauthorized actions are blocked, partial failures are handled safely, duplicate/retry behavior is correct, existing behavior remains intact, and failure does not leave invalid state.

### Verification Rule

Implementation claims must be supported by actual test output, inspection results, or other concrete evidence.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-100250-01 | Per-bank profile persists and resolves deterministically | T100250-04, T100250-06, T100250-07 | Config round-trip + isolation tests |
| AC-100250-02 | Verbosity monotonicity on shared fixture | T100250-01 | Admit-count comparison output |
| AC-100250-03 | Batch dry-run writes nothing and reports reasons | T100250-02, T100250-03 | Store diff + preview payload |
| AC-100250-04 | Transports parity for new tools | Contract test | stdio vs HTTP matrix |
| AC-100250-05 | No taxonomy/weight/formula regression | Regression suite | Prior admission tests green |
| AC-100250-06 | New tools published in versioned `tool_schema` pack | Schema-pack CI check | Pack contains `admit_preview_batch` + profile tools with pinned revision stamp |

### Acceptance Evidence (r1)

| AC ID | Result | Evidence |
|-------|--------|----------|
| AC-100250-01 | PASS | `clio-config` `retention_store_tests::resolution_order_is_bank_then_deployment_then_builtin`, `save_round_trips_and_reports_io_errors`; `config::retention_tests::retention_profile_round_trips_across_a_restart` (set → restart → re-read, plus deployment default); `t25_06_cross_bank_profile_isolation`; `t25_07_fresh_runtime_resolves_builtin_default_and_still_gates` |
| AC-100250-02 | PASS | `clio-admission` `decision_tests::verbosity_admit_sets_are_monotone_on_a_shared_fixture` (selective ⊆ balanced ⊆ permissive, selective strictly smaller); `t25_01_verbosity_admit_sets_are_monotone` (selective 10 < balanced 20 ≤ permissive 20 on the 20-item fixture) |
| AC-100250-03 | PASS | `t25_02_batch_preview_reports_decisions_and_writes_nothing` (per-item decisions + summary, store item count unchanged, item ids absent from the store); `t25_03_profile_override_does_not_persist`; `retention_tools_tests::batch_preview_reports_per_item_decisions_and_writes_nothing` |
| AC-100250-04 | PASS | `http_tests::retention_tools_parity_stdio_vs_http` — identical `structuredContent` for `admit_preview_batch` and `retention_profile_get` over stdio and Streamable HTTP, and identical `tools/list` name sets |
| AC-100250-05 | PASS | Full workspace suite exit 0 with no changes to five-factor weights, category taxonomy, or `ranking_env` defaults; `clio-admission`/`clio-mcp`/`clio-store` prior admission tests green; `gate_boundary_tests::only_gated_path_creates_items` green |
| AC-100250-06 | PASS | `schema_retention_defs_tests::retention_tools_are_in_the_published_pack_with_the_pinned_revision`; `schema_tests::t01_...` asserts the published set equals the bound set + `summarize`; `inventory_contract::coding_inventory_core_matches_requirement_4_9_4` covers the new Core name |

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

**Implementation summary.** Each bank resolves to exactly one effective `retention_profile` via bank override → deployment default → builtin default (`balanced` verbosity, zero offsets, `balanced` write tolerance, `balanced` read tolerance, `full` recall scope). `verbosity` maps to `theta_delta` (`selective +0.08`, `balanced 0.00`, `permissive -0.08`) and a novelty floor (`selective 0.15`, others `0.00`); `duplicate_tolerance_write=strict` adds a `0.25` novelty floor. `theta_effective = clamp01(theta_base + verbosity_delta + theta_offsets[key])`, with offsets bounded to `±0.20`. `admit_preview_batch` runs the single-item scoring path once per item in input order, capped at 50, and writes nothing. `retention_profile_get`/`retention_profile_set` are bound over both MCP transports and published in the `tool_schema` pack; `am retention get|set|schema` provides the CLI surface. `recall_scope_default` and `duplicate_tolerance_read` are stored but returned only inside an `accepted_but_inert` envelope with `honored_by: "recall_scope_and_dedup"` (a capability token, not a phase number).

**Remediation r1.** The r1 remediator resolved findings F-02..F-10 (schema-pack evidence corrected to real output; `retention. verbosity=permissive` now rejected as a deployment default at the store level and on load; failed persists roll back the in-memory store before the error returns; hub distill now scores under the bank's resolved profile; span-verify refusals stamp the policy's resolved `profile_version`; header/attribution/test-count fixes) and left F-01 (`honored_from_phase: "027"` vs the no-phase-numbers hard rule) blocked pending an operator decision.

**Remediation r2.** The operator approved the capability-token option. `INERT_FIELDS_HONORED_FROM = "027"` is replaced by `INERT_FIELDS_HONORED_BY = "recall_scope_and_dedup"`; the `accepted_but_inert` envelope now carries `honored_by`, the profile schema carries `x-inert-fields-honored-by`, and the two field descriptions no longer name a phase (`crates/clio-config/src/retention.rs`). No phase number remains in production code or the published pack; a guard test (`published_profile_schema_carries_no_phase_number`) fails if one returns. `requirement.md` now says the envelope names the capability that will honor the inert fields. Phase 100270's own document is unaffected: it reads `recall_scope_default` and `duplicate_tolerance_read` from the stored profile and never named the envelope key.

**Discovered/affected architectural components.** `clio-config` (config layer owning bank-scoped policy + durable store), `clio-admission` (consumes a resolved `Copy` snapshot; stays I/O-free), `clio-mcp` (tool binding, schema pack, runtime store), `clio-write` (span-verify rejections now stamp `profile_version`), `clio-lib` (CLI). No taxonomy, five-factor formula, or global `ranking_env` default changed.

**Changed-component summary.**

| File | Change |
|------|--------|
| `crates/clio-config/src/retention.rs` | New: profile object, enums, validation, mapping tables, `ResolvedRetention`, `profile_json_schema()` |
| `crates/clio-config/src/retention_store.rs` | New: `RetentionStore`, `ProfileSource`, resolution order, durable load/save, lossy load |
| `crates/clio-config/src/config/retention_ops.rs` | New: `Runtime` get/set/set_deployment + store-path override |
| `crates/clio-config/src/config/{mod,types,dispatch,validate}.rs` | Runtime fields/init, payload types, tool dispatch, `retention.` forbidden for generic `config_set` |
| `crates/clio-config/src/{lib,profile}.rs` | Module exports; inventory gains `admit_preview_batch` (core) and the two retention tools (implemented) |
| `crates/clio-admission/src/{policy,decision,gated}.rs` | `with_retention`, novelty floor, `profile_version`, duplicate-gate rejection |
| `crates/clio-mcp/src/{retention_tools,runtime_retention,schema_retention_defs,store_write}.rs` | New: profile tools, batch preview, runtime accessors (with persist-failure rollback), schema defs, extracted store-path core |
| `crates/clio-mcp/src/{lib,runtime,schema,read_tools,additive_tools,write_tools}.rs` | Bound lists, retention store field/loader, pack assembly, routing, retention-aware policy resolution |
| `crates/clio-mcp/src/mutator_tools.rs` | `consolidate` resolves the bank profile and threads it into hub distill |
| `crates/clio-write/src/{hub_distill,memtree_tools}.rs` | `distill_hub`/`consolidate_hubs`/`consolidate_tool` take the resolved retention snapshot and gate distilled items under it |
| `crates/clio-write/src/{pipeline,store_path}.rs` | Verify-refusal decisions stamp the policy's resolved `profile_version` |
| `crates/clio-lib/src/{retention_cli,main,lib}.rs` | New CLI surface + dispatch/help + facade re-exports |
| `crates/clio-store/src/gate_boundary_tests.rs` | Allowlist tracks the moved gated write closure (`write_tools.rs` → `store_write.rs`) |
| `crates/clio-config/src/retention_tests.rs`, `crates/clio-mcp/src/schema_tests.rs` | Guard tests: the profile schema and the published pack carry no roadmap phase number |

**Test execution output.**

```
make check (fmt + clippy -D warnings + workspace tests)   exit 0, 44 suites green, 0 failed
cargo test -p clio-config                                   90 passed
cargo test -p clio-admission                                33 passed
cargo test -p clio-mcp --lib                               187 passed
cargo test -p clio (am bin unittests)              40 passed
cargo test -p clio --test retention_profile_harness  11 passed (T100250-01..08 + CLI smoke + restart strictness)
```

**API/schema evidence for profile and batch preview tools.** `am mcp schema-export` publishes 67 tools including `admit_preview_batch`, `retention_profile_get`, `retention_profile_set`, with `mcp_protocol_revision: "2025-11-25"` (verified against the real binary output). The profile JSON Schema with the exact mapping tables (`x-retention-profile-version: 1`, `x-verbosity-mapping`, `x-duplicate-tolerance-write-mapping`, `x-theta-offset-bound: 0.20`) is published via `am retention schema` (all five `x-*` keys verified present in its output), not inside the MCP pack, whose retention tool defs embed the profile `properties` only. The schema-pack test asserts the published name set equals the bound set plus the one reserved unbound def (`summarize`), so both a missing and an extra tool fail. `tools/list` over stdio and Streamable HTTP returns the same names (parity test). After remediation r2 the pack contains no phase-number token: the `accepted_but_inert` envelope carries `honored_by: "recall_scope_and_dedup"` and the embedded profile properties describe the recall-side capability instead of a roadmap phase.

**Verification report.** Remediation r1 re-verified with one workspace coverage run (`cargo llvm-cov --workspace --locked --json`, `DATABASE_URL` from `coverage.md`): **244 reported source files, 0 below 90% on functions or lines; aggregate lines 97.88% (34102/34840), functions 98.86% (2956/2990)**, plus one `make check` pass (exit 0). No new/modified Rust file exceeds 450 lines. Remediation r2 (capability-token rename plus two guard tests) re-verified with one `make check` pass (exit 0, 44 suites green) and one `make coverage` pass (exit 0; 244 reported files, 0 below 90%; aggregate lines 97.88% (34102/34840), functions 98.86% (2956/2990)).

**Known limitations.** See §12.

**Security evidence.** Bank isolation: profile storage is keyed by the caller's resolved bank, and `t25_06_cross_bank_profile_isolation` shows bank B resolves `builtin` after bank A stores a profile, and a bank-B preview is unaffected. Confirmation: `retention_profile_set` returns a no-write preview unless `confirm=true`; `retention_tools_tests::profile_set_requires_confirmation_and_is_bank_scoped` asserts nothing is stored without it. Cross-bank read: a `retention_profile_get` response only ever contains the requested bank's effective profile plus its source, never another bank's override. Streamable HTTP mutation: the transport refuses to bind a non-loopback address without a configured auth token (`main.rs` `mcp_http_non_loopback_without_token_fails_closed`), so an unauthenticated remote profile mutation cannot reach the handler. Secret-safe errors: profile fields are enums and bounded numbers, and offset keys are restricted to the known admission keys, so validation messages never echo caller-supplied free text.

**Attribution note.** The `tool_schema` pack publication of `admit_preview_batch` and the profile tools follows the Phase 100170 §9 approved-schema-edit rule; AC-100250-06 mandates it.

---

## 10. Failure Handling and Recovery

### Expected Failure Modes

| Failure | Detection | Recovery |
|---------|-----------|----------|
| Corrupt stored profile | Validation on load | Fall back to deployment default + log warning; never fail writes open |
| Batch scorer neighbor-store outage | Per-item error signal | Return per-item `factor_unavailable` errors; no partial writes (there are none) |
| Oversize batch | Request validation | Reject with limit + retry guidance |

### Rollback Strategy

Delete or reset the bank override to restore deployment-default behavior. No data migration is involved; stored memories are untouched by profile changes.

### Partial Completion Policy

If only part of the phase is complete, do not claim full completion. Record completed and incomplete work separately. Document remaining work. Do not leave undocumented broken state.

---

## 11. Traceability

| Parent Requirement | Implementation Task | Verification | Acceptance Criterion |
|--------------------|---------------------|--------------|-----------------------|
| P1 / §4.2 strictness knob | Task 2 | T100250-01 | AC-100250-02 |
| PR-5 explicit decision + dry-run | Task 3 | T100250-02, T100250-03 | AC-100250-03 |
| FR-22 per-repository bank isolation (+ FR-10 catalog conformance for the new tools) | Task 1 | T100250-06, T100250-07 | AC-100250-01 |
| §4.9.2 transport parity | Task 3 | Contract test | AC-100250-04 |
| FR-20 / §4.9.2 versioned `tool_schema` pack | Task 3 | Schema-pack CI check | AC-100250-06 |

Required chain:

```text
Requirement → Capability → Implementation → Test → Evidence
```

Every acceptance criterion must be traceable.

---

## 12. Phase Exit Contract

### Outputs Produced

- `retention_profile` schema, storage, and resolution.
- Verbosity and duplicate-tolerance mappings.
- Batch `admit_preview` dry-run tool on both MCP transports.

### Guarantees Provided to Downstream Phases

- Phase 100260 may add mission keep/drop fields to the profile without changing resolution or verbosity semantics.
- Phase 100270 may honor `recall_scope_default` without changing write-path behavior.
- Admission decisions always carry the resolved `profile_version` for audit.

### Known Limitations

- Profiles tune strictness only; they do not re-score already-stored items.
- `recall_scope_default` and `duplicate_tolerance_read` are stored inside an `accepted_but_inert` envelope (with `honored_by: "recall_scope_and_dedup"`) until the recall-side scope and dedup capability lands.
- `permissive` is intentionally loose and MUST NOT become a default. Enforced: `RetentionStore::set_deployment` rejects `verbosity=permissive`, the lossy loader prunes a stored permissive deployment default back to builtin, and bank-scope `permissive` stays legal (tested at store, Runtime, and MCP-tool level).
- `duplicate_tolerance_write` exposes three level names, but on the write path `balanced` (the default) and `lenient` both resolve to a `0.0` novelty floor; only `strict` adds a duplicate-rejection floor. Why: the existing admission regression suite requires a novelty-`0` candidate to be admitted under the default profile, so the default cannot reject near-duplicates without changing prior behavior. The level names are shared with `duplicate_tolerance_read`, whose Phase 100270 mapping gives all three levels distinct values. Owner: the phase that first needs three distinct write-side levels.
- The MCP `admit_preview_batch` and `store` paths score with an empty (`NoSignals`) neighbor source, so novelty is always `1.0` there and the duplicate-tolerance floor is not observable through MCP. Why: no embed/age `SignalSource` is wired into the MCP runtime (pre-existing limitation of the MCP store path). Owner: the phase that binds the index-backed signal source to the MCP runtime.
- The MCP profile store is process-scoped; it persists only when `AM_RETENTION_PROFILES` (or `McpState::set_retention_path`) names a file. Why: no new `McpOpenOptions` field was added, to keep the public open-options struct unchanged. Owner: the phase that adds operator-facing MCP configuration for the retention store path.

### Downstream Prerequisites

- Phase 100260 relies on the profile version stamp and override-preview mechanism.
- Phase 100270 relies on bank-scoped profile resolution for recall defaults.

### Final Status

PASS

### Verification Sign-Off

- Implementer: OpenCode CLI (Together . GLM-5.3 Flash High)
- Verifier: [pending adversary round]
- Human Approver: [pending, if required]
- Date: 2026-09-21

# Phase 100090: Shared Continuous EMA Update Engine

### Attribution
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | OpenCode CLI (Together . GLM-5.3 Flash High) | done |
| Adversary | r1 | Antigravity CLI (Gemini 3.8 Flash) | done |
| Remediator | r1 | OpenCode CLI (Go . Deepseek V4.1 Flash High) | done |
| Remedy Approver | r1 | Antigravity CLI (Gemini 3.8 Flash) | approved |
| Finalize | r1 | OpenCode CLI (Together . GLM-5.3 Flash High) | done |

**Index slice 100090 · **Effort:** `1×` · **Scope:** `roadmap/index.md` slice 100090 (authoritative)

### Vocabulary (read first) — zero shared moniker

| Term | Enum | Where it lives | Must not |
|------|------|----------------|----------|
| **`epistemic_kind`** | `fact` \| `belief` | Item/triple/belief field (FR-14) | Be passed to `update` |
| **`update_rule`** | `discrete` \| `continuous` | Attribute schema + `update(..., update_rule)` (FR-11) | Be stored in the `epistemic_kind` column |

Reject `update(..., update_rule=belief)` / `=fact` with structured `wrong_update_rule`. Do not name either field `class`. Normative defs: `requirement.md` §10.

## 1. Objective

### Goal
Implement the **continuous/scalar update model** (fast EMA plus slower trend) and enforce **`update_rule` declarations** so discrete invalidation and continuous smoothing never mix (PR-2 / FR-11 / §4.6). This slice owns the **shared update engine** and generic `update` rule splitting. Persona (slice 100140) MUST call into this engine and MUST NOT reimplement EMA.

### Expected Outcome
- Attribute schemas declare `update_rule` ∈ {`discrete`, `continuous`} at definition time; the declaration is durable and readable.
- `update(item_id, new_value, update_rule)` routes: `discrete` → Phase 100080 invalidation path; `continuous` → this EMA engine. Wrong rule MUST fail closed with a structured error (`wrong_update_rule`).
- Continuous observe applies:
  - `new_state = α · observed_value + (1 − α) · previous_state` (fast EMA)
  - `trend =` long-window average over the **N most recent states** (slower baseline)
- Per-attribute tunable `α` and trend window `N` (defaults documented; **source of truth is attribute schema / continuous-engine config**—not `ranking_env_*`. `ranking_env` MAY expose global default α/N only as defaults that schemas can override).
- Continuous state history is retained enough to recompute trend and support §4.8 temporal preference trajectories (full `temporal_history` tool wiring may complete in later slices; series storage starts here).
- Concurrent observes on the same attribute key are serialized (compare-and-swap or equivalent transactional RMW); no lost updates.
- Symmetric rejection: continuous path rejects discrete/categorical payloads; discrete path already rejects continuous (Phase 100080).

### Parent Requirement
`requirement.md` (current) — P9, PR-2, §2.2, §4.6 continuous rule, §4.7 preferences foreshadow, §4.9.4.A `update`, §4.9.7, FR-11, FR-15 spirit, FR-25 foreshadow (persona adapter later). Numeric edge cases: `roadmap/phase-100090-appendix-ema-formulas.md`.

### Design references (non-normative)
- Requirement-native dual estimator (EMA + slower trend) matches preference-drift literature that separates short-term fluctuation from long-term tendency; see PAMU (sliding window + EMA fusion and divergence detection) as **optional diagnostic inspiration only**, not a replacement for the §4.6 formulas: [Preference-Aware Memory Update (PAMU)](https://arxiv.org/html/2510.09720).
- Bounded EMA score updates in production memory systems (α as learning rate; stay in declared numeric bounds): [Engram memory scoring EMA](https://deepwiki.com/bit2swaz/engram/6.1-memory-scoring-and-ema-updates).

---

## 2. Scope Boundaries

### In Scope
- Attribute `update_rule` registry / schema declaration (`discrete` | `continuous`) at definition time (FR-11).
- Shared continuous update engine: EMA state, trend over last N states, configurable α and N on the attribute/engine config.
- Generic `update(item_id, new_value, update_rule)` splitter implementing the rule split end to end.
- Persistence of continuous scalar state + enough recent states for trend (dual-backend).
- Structured rejection when `update_rule` does not match attribute declaration or payload shape (numeric required for continuous); reject `epistemic_kind` values passed as `update_rule`.
- Concurrent-safe RMW for observes on the same key.
- Telemetry on continuous updates (FR-15 spirit).
- Documented adapter contract for slice 100140 `persona_observe_preference` (thin wrapper; not implemented here unless a minimal internal hook already exists—prefer stub interface + tests of the shared engine).

### Explicitly Out of Scope
- Full persona object, token budget, and `persona_*` public tools (slice 100140).
- Belief confidence trajectories (slice 100100)—beliefs are not EMA-smoothed facts.
- Hybrid retrieve / intent gate / compose (slice 100120).
- Co-activation edge weight EMA-style growth (slice 100130)—different formula (§4.5 saturating growth); do not overload this engine.
- Changing Phase 100080 supersession identity or interval algebra.
- MCP binding of `update` (slice 100160)—in-process / library surface is enough for exit.
- Compliance erase of continuous series (slice 100190).

### Must Not Change
- PR-2: no attribute handled by both discrete invalidation and continuous EMA.
- Phase 100080: discrete supersession remains invalidation-not-delete.
- Phase 100040 gates on long-term *writes*; mutators follow §4.9.3 (N/A category/admission) but still enforce FR-11 + audit.
- Phase 100020 DEK encryption for any continuous value payloads stored as content.

### Scope Expansion Rule
If work outside this scope appears necessary:
1. Stop.
2. Document the reason.
3. Request clarification or approval.
4. Do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- Phase 100080 accepted: discrete path + `wrong_update_rule` rejection foreshadow; this phase completes the continuous half.
- Phase 100030 accepted: item repository that can hold scalar preference-like values or continuous attribute rows.
- Phase 100010 accepted: effective config exists; α/N defaults live on attribute/engine config (not as ranking_env source of truth).

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| Discrete update / invalidate | Phase 100080 path works | Call `update(..., update_rule=discrete)` or invalidate in tests |
| Persistence | Can store scalar + history window | Phase 100020 dual-backend |
| Attribute metadata | Place to declare `update_rule` | Schema/migration or registry table |
| Clock | Deterministic `as_of` on observations | Injectable clock in tests |

---

## 4. Existing-System Discovery

The agent MUST inspect the existing system before deciding
where or how to implement the changes.

### Required Discovery
- Locate Phase 100080 `update_rule` guard and any stub `update` entrypoint.
- Identify where item/attribute schemas live and how categories relate to continuous keys.
- Confirm whether continuous values are stored as items, persona preference rows, or a dedicated continuous-attribute table—choose one coherent model.
- Find existing telemetry hooks for mutators.
- Confirm DEK encrypt path for content-bearing continuous payloads.
- Confirm file size / module split conventions (≤450 lines per Rust source file).

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

### Task 1: Attribute `update_rule` Declaration

#### Intent
Make `discrete` vs `continuous` a first-class, definition-time **`update_rule`** property (FR-11)—separate from `epistemic_kind`.

#### Required Capability or Behavior
- Every updatable attribute schema records exactly one `update_rule`: `discrete` | `continuous`.
- Declaration is immutable for a given attribute key without an explicit schema-change path (document how keys are versioned if change is allowed).
- Reads can answer “what update_rule is attribute X?” without applying an update.
- Storage MUST NOT reuse the item `epistemic_kind` (`fact`|`belief`) column for `update_rule`.

#### Architectural Responsibility
Schema / attribute registry owned by write-path governance (alongside taxonomy, not inside retrieval).

#### Required Changes
1. Persist `update_rule` with the attribute definition (dedicated field/table).
2. Validation on schema registration: reject missing/unknown update_rule.
3. Tests for declaration round-trip, immutability, and column separation from `epistemic_kind`.

#### Implementation Constraints
- Do not infer update_rule from value shape alone at update time as the *sole* authority—declaration wins; shape checks are additional guards.
- Do not allow dual update_rule attributes.
- Do not store update_rule in `epistemic_kind`.

#### Expected Result
Registered continuous and discrete attributes are distinguishable; updates consult the declaration.

### Task 2: Shared EMA + Trend Engine

#### Intent
Implement the normative continuous update formulas (§4.6) in one shared module.

#### Required Capability or Behavior
- Input: attribute key, observed numeric value, optional confidence/evidence_ref, prior state.
- Output: updated `state`, updated `trend`, observation timestamp.
- Formulas and edge cases per appendix (cold start, bounds, empty window).
- `α` and `N` resolvable per attribute from **attribute schema / continuous-engine config** with documented defaults (global defaults MAY be mirrored in config for convenience; `ranking_env_*` is not the source of truth).
- Engine is pure/deterministic given identical inputs and config (NFR-5 spirit for this path).
- Concurrent observes on the same attribute key: transactional compare-and-swap (or equivalent) so each observation is applied exactly once to a consistent prior state; final state matches some serial permutation of the observes.

#### Architectural Responsibility
Shared continuous-update domain service—**the only** EMA implementation persona may call later.

#### Required Changes
1. Implement EMA + trend window in one place.
2. Persist current state, trend, and last N states (or equivalent sufficient store).
3. Unit tests for formula correctness from appendix fixtures.

#### Implementation Constraints
- Observed value MUST be numeric; reject strings/categoricals.
- Do not blend discrete facts (e.g. city names) via EMA.
- Do not implement saturating co-activation weights here (§4.5).
- Optional PAMU-style `|short − long|` divergence MAY be exposed as a diagnostic metric; MUST NOT change the stored `state`/`trend` formulas away from §4.6 without approval.

#### Expected Result
Repeated observations converge toward recent values while `trend` moves more slowly; tests match appendix expected numbers.

### Task 3: Generic `update` Rule Splitter

#### Intent
Expose `update(item_id, new_value, update_rule)` that enforces FR-11 routing.

#### Required Capability or Behavior
- Resolve target attribute/item and its declared `update_rule`.
- If caller `update_rule` ≠ declared rule → structured error (`wrong_update_rule`).
- If caller passes `fact`/`belief` (or any non discrete|continuous value) → `wrong_update_rule` (epistemic kind is not an update_rule).
- If `update_rule=discrete` → invalidate/supersede path (Phase 100080); never EMA.
- If `update_rule=continuous` → shared EMA engine; never invalidation blending.
- Emit telemetry on successful mutates.

#### Architectural Responsibility
Mutator facade above discrete and continuous engines.

#### Required Changes
1. Public/in-process `update` API matching §4.9.4.A semantics (`update_rule` parameter).
2. Wire both backends of the split.
3. Contract tests for both success paths, both mismatch failures, and epistemic_kind-as-update_rule rejection.

#### Implementation Constraints
- Mutators: category/admission gates N/A (§4.9.3); FR-11 + audit still required.
- Do not silently coerce types.
- Bank/actor scoping preserved.

#### Expected Result
One entrypoint; two legal paths; mismatches and enum collisions fail closed.

### Task 4: Continuous Series Read Seam for Temporal History

#### Intent
Ensure continuous updates leave a queryable series so NFR-4 / §4.8 temporal trajectories are possible.

#### Required Capability or Behavior
- After observations, a reader can obtain ordered `(as_of, state, trend?)` points for a continuous attribute.
- Full `temporal_history` tool MAY remain thin/stub if slice 100150 owns packaging—but the **data** MUST exist and be covered by tests.
- Point-in-time “state as of T” uses observation timestamps (document semantics).

#### Architectural Responsibility
Continuous store read API used later by history tools.

#### Required Changes
1. Persist observation points (or reconstructible window).
2. Read helper with as-of filter.
3. Tests for append-only observation growth (no overwrite of prior points).

#### Implementation Constraints
- Continuous history is not bi-temporal SPO invalidation; do not force valid/transaction axes onto EMA states unless already present—document the chosen time model.
- Content ciphertext rules apply to stored values.

#### Expected Result
Tests can reconstruct how a scalar preference drifted over a fixture timeline.

### Task 5: Persona Adapter Contract (Stub)

#### Intent
Lock the slice-14 integration surface so persona cannot fork EMA.

#### Required Capability or Behavior
- Documented function/trait: `observe_continuous(key, observed_value, …) -> ContinuousState` calling Task 2.
- Explicit MUST NOT: second EMA copy in persona module.
- Optional compile-time or test-only assertion that persona preference updates (when added later) import this engine.

#### Architectural Responsibility
Boundary between companion persona and shared continuous engine.

#### Required Changes
1. Stable internal API + short contract comment / ADR note in-repo (not under `roadmap/` as a long-lived dependency—keep the note in code or design docs outside roadmap if needed).
2. Unit test that the shared engine is invoked from a thin adapter stub.

#### Implementation Constraints
- Do not ship full `persona_observe_preference` MCP/tool surface here.
- Do not enforce persona token budget here.

#### Expected Result
Downstream persona work has a single call target; plan exit evidence names the adapter hook.

### Implementation Freedom
The agent may choose the concrete implementation structure,
file locations, naming, and internal design provided that:
- The required behavior is satisfied.
- Architectural boundaries are respected.
- Existing contracts are preserved.
- All acceptance criteria pass.
- No prohibited changes are introduced.
- Rust sources stay ≤450 lines per file (split modules if needed).

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
- Implement a second EMA inside a persona prototype.
- Apply EMA to discrete/categorical attributes.
- Use DELETE to “reset” continuous history when an observe fails.

### Agent Decision Boundary
The agent may decide:
- Concrete file/module/class placement.
- Whether continuous rows are items vs dedicated tables.
- Default α / N values (on attribute/engine config—not ranking_env as SoT).
- Test organization.
- Non-breaking implementation details.

The agent must request approval for:
- Architecture changes beyond the stated scope.
- Breaking API or data-contract changes.
- Replacing §4.6 formulas with PAMU fused SW+EMA as the stored state.
- Security-sensitive policy decisions.
- Destructive data operations.
- Changes affecting downstream phase assumptions (especially slice 100140).

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
- Discrete and continuous paths cannot share a single `update` facade without breaking Phase 100080.

---

## 7. Security Constraints

### Required Controls
- Bank-scoped continuous attributes; actor on telemetry.
- Numeric validation and range checks at the trust boundary.
- Continuous values encrypted when stored as content payloads (Phase 100020 DEK).

### Sensitive Data Rules
- Never log DEKs or raw secrets that appear in evidence_ref payloads.
- Never commit secrets.
- Mask credential-like strings in error messages.

### Security Acceptance Conditions
- Cross-bank continuous update fails closed.
- Wrong-`update_rule` updates never mutate state.

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
| T100090-01 | Register continuous attribute | `update_rule` declaration persisted; not in `epistemic_kind` column |
| T100090-02 | EMA update sequence (appendix fixture) | State matches expected floats within epsilon |
| T100090-03 | Trend over N states | Trend equals mean of last N states |
| T100090-04 | Cold start (no prior state) | Documented init: state=observation; trend=observation |
| T100090-05 | `update(..., update_rule=continuous)` on continuous attr | EMA applied; no invalidation |
| T100090-06 | `update(..., update_rule=discrete)` on continuous attr | `wrong_update_rule`; no mutation |
| T100090-07 | `update(..., update_rule=continuous)` on discrete attr | `wrong_update_rule`; no mutation |
| T100090-08 | Categorical string as continuous observation | Rejected |
| T100090-09 | Dual-backend parity sample | Same state/trend on Postgres and SQLite |
| T100090-10 | Continuous series as-of read | Prior points retained; as-of returns correct state |
| T100090-11 | Telemetry on continuous update | Event observable |
| T100090-12 | Thin adapter stub calls shared engine | Single engine invocation path |
| T100090-13 | `update(..., update_rule=belief)` or `=fact` | `wrong_update_rule`; no mutation |
| T100090-14 | Concurrent observes same key | Both applied; final state = some serial permutation; no lost update |

### Negative Testing
Verify that:
- Invalid α / N config is rejected or clamped per documented rule.
- Unauthorized bank actions are blocked.
- Partial failures do not corrupt the trend window.
- Duplicate/retry observe is deterministic for identical inputs.
- Phase 100080 discrete supersession still works.
- Failure does not DELETE history points.

### Verification Rule
Implementation claims must be supported by actual test output,
inspection results, or other concrete evidence.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-100090-01 | Attribute `update_rule` declaration at definition time | T100090-01, T100090-13 | PASS — `clio-types::AttributeSchema` + `attribute_schemas.attr_class` (separate column from `items.epistemic_kind`); `clio-store::attribute_tests::t01_declaration_roundtrip_not_epistemic_column` and `clio-types::attribute_tests::t13_epistemic_kind_is_not_update_rule` |
| AC-100090-02 | §4.6 EMA + trend formulas correct | T100090-02, T100090-03, T100090-04 | PASS — `clio-types::attribute_tests::t02_t03_appendix_fixture` (α=0.5, N=3, obs 1.0/0.0/1.0 → states 1.0/0.5/0.75, trends 1.0/0.75/0.75, epsilon 1e-9) and `t04_cold_start`; store-level fixture in `clio-store::attribute_tests::t02_t04_appendix_fixture_through_store` |
| AC-100090-03 | FR-11 `update` rule split both directions | T100090-05–T100090-08, T100090-13 | PASS — `clio-write::update_tests` (t05 continuous applies EMA + no invalidation; t06/t07 wrong_update_rule both directions with no mutation; t08 categorical payload `InvalidType`, NaN `OutOfRange`; t13 `fact`/`belief` rejected via `UpdateRule::parse` with `wrong_update_rule`) |
| AC-100090-04 | Continuous series retained for trajectories | T100090-10 | PASS — `clio-store::attribute_tests::t10_series_retention_and_as_of`: append-only growth, as-of filter, failed observe does not delete history |
| AC-100090-05 | Dual-backend behavioral parity | T100090-09 | PASS — `clio-store::pg_attribute_tests::t09_parity_with_sqlite`: same appendix fixture numbers on Postgres (compose DB 127.0.0.1:34310) and SQLite |
| AC-100090-06 | Shared engine + persona adapter contract | T100090-12 | PASS — `clio-write::persona_tests::t12_adapter_calls_shared_engine`: thin adapter produces identical state/trend/window to the direct store path; single EMA implementation in `clio-types::apply_observation`; contract documented in `clio-write/src/persona.rs` |
| AC-100090-07 | Telemetry on continuous mutator | T100090-11 | PASS — `ContinuousEvent`/`ContinuousSink` emitted on every successful observe (`persona_tests`, `update_tests::t05`); audit row `continuous_observe` written by both backends |
| AC-100090-08 | Concurrent observes are serializable | T100090-14 | PASS — SQLite: `attribute_tests::t14_concurrent_observes_serialized` (8 threads; series reconstruction proves a valid EMA chain over a serial permutation, no lost updates). Postgres: `pg_attribute_tests::t14_pg_concurrent_observes_serialized` (4 independent clients, per-key advisory lock) |

### Definition of Done
- [x] All in-scope behavior is implemented.
- [x] All acceptance criteria pass.
- [x] Required tests pass.
- [x] No unauthorized changes were introduced.
- [x] Existing behavior remains intact (`make check` green: fmt + clippy `-D warnings` + all 16 workspace test suites).
- [x] Security checks pass (cross-bank observes fail closed — `observe_fails_closed` on SQLite and `t09_parity_with_sqlite` on Postgres; wrong-rule updates never mutate; numeric validation at the trust boundary).
- [x] Documentation is updated where required (module headers, SQL comments, defaults documented in code).
- [x] Evidence is collected.
- [x] Verification is completed (`make coverage` exit 0).
- [x] Required approval is obtained (pipeline sign-off pending).

### Completion Evidence
- Implementation summary: `update_rule` declarations live in `attribute_schemas.attr_class` (α/N/bounds/clamp knobs on the same table; never in `items.epistemic_kind`). The shared §4.6 engine (`apply_observation`, EMA + mean-of-last-N-states trend, cold start, bounds reject/clamp) lives in `crates/clio-types/src/attribute.rs` and is the only EMA implementation. Both backends implement a new `ContinuousStore` trait (declaration registry + transactional observe RMW + append-only series + as-of read): SQLite via immediate transactions over the single connection, Postgres via per-key advisory lock + `FOR UPDATE`. The `update(item_id, new_value, update_rule)` facade lives in `crates/clio-write/src/update.rs` (one entrypoint, two legal paths, all mismatches fail closed with `wrong_update_rule`); the persona adapter contract is `crates/clio-write/src/persona.rs::observe_continuous`.
- Discovered/affected architectural components: Phase-100080 `update_rule` guard (`ensure_discrete_update_rule`) and continuous rejection in `sqlite_triple`/`postgres_triple` left intact; the discrete path already rejected continuous attributes via `attribute_schemas` — the declaration is now first-class with a registry API. Triple `Store` impl files were at their 450-line ceiling after adding four more trait methods, so the continuous surface is a separate `ContinuousStore` trait implemented in the attribute modules (main `Store` impls unchanged in behavior).
- Changed-component summary: `sql/001_core.sql` (attribute_schemas columns + `continuous_state` + `continuous_observations`, additive); `crates/clio-types/src/attribute.rs` (engine + types); `crates/clio-store/src/{attribute_map,sqlite_attribute,postgres_attribute}.rs` + `store.rs` (`ContinuousStore` trait) + `attribute_tests.rs` + `pg_attribute_tests.rs`; `crates/clio-types/src/triple.rs` (`UpdateRule::parse` now fails closed with `wrong_update_rule` for `fact`/`belief`); `crates/clio-write/src/{update,persona}.rs` (+ tests); re-exports in crate roots.
- Default α / N values documented: `DEFAULT_ALPHA = 0.3`, `DEFAULT_TREND_WINDOW = 10` (`crates/clio-types/src/attribute.rs`); per-attribute overrides live on `attribute_schemas` (source of truth); `ranking_env_*` is not consulted.
- Test execution output: `make check` → fmt + `clippy -D warnings` + 16 suites all `test result: ok` (28 clio-types, 94 clio-write, 91 clio-store incl. Postgres parity/concurrency against compose DB). `make coverage` exit 0 — aggregate 96.14% lines / 99.22% functions; every reported file ≥90% on both gated metrics (lowest new file: `postgres_attribute.rs` 95.83% functions / 98.40% lines; regions informational per coverage.md).
- Verification report: T100090-01–T100090-14 all pass (see AC table); negative tests pass (invalid α/N rejected at registration, cross-bank fails closed, corrupt window rebuilds from the series without deleting, duplicate observes deterministic, Phase-100080 discrete supersession untouched, failure never DELETEs history).
- Known limitations: (1) `temporal_history` tool packaging is not wired in this slice — the data seam (`continuous_series`) is tested; (2) additive schema only — a pre-existing database does not gain the new columns/tables (project treats schemas as undeployed; re-init or explicit migration required before deploy); (3) observation `as_of` ordering assumes sortable ISO-8601 text timestamps; (4) the persona adapter is a thin in-process stub — the full `persona_*` tool surface is later scope.
- Remediation r1 (adversary findings): all 5 findings addressed. F-02/F-04/F-05 fixed in code — boundary focus lines added to the 6 new module headers; `parse_window` now rejects an empty array so a corrupt `[]` window rebuilds from `continuous_observations`; SQLite `LIMIT ?4` parameterized to match Postgres. F-03 resolved by documenting the §4.2–4.4 gated-write contract that forbids admitting `new_value` on the discrete path. F-01 resolved by documenting the `update` facade addressability model as intentional and deterministic (attribute lookup wins; discrete is item-addressed; both structural alternatives rejected with reasons), pinned by `clio-write::update_tests::t_addressability_precedence_and_discrete_key_rejection`. Re-verified after remediation: `make check` PASS (clio-write 95 passed; all suites ok) and `make coverage` exit 0 — aggregate 96.14% lines / 99.22% functions, no file below 90% on either gated metric. Finding-by-finding detail in `.workflows/phase-100090/findings.json`.

---

## 10. Failure Handling and Recovery

### Expected Failure Modes

| Failure | Detection | Recovery |
|---------|-----------|----------|
| Wrong `update_rule` | Validation | Reject; no write |
| Non-numeric observation | Validation | Reject |
| Corrupt / short history window | Integrity check | Recompute trend from available points; log |
| Config α outside (0,1] | Config validation | Reject or documented clamp |

### Rollback Strategy
Revert code; continuous history rows are additive and safe to keep. Prefer additive migrations. Do not DELETE observation history to “undo” a bad deploy without an explicit ops decision.

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
| FR-11 / PR-2 `update_rule` declaration | Task 1 | T100090-01, T100090-13 | AC-100090-01 |
| §4.6 EMA + trend | Task 2 | T100090-02–T100090-04 | AC-100090-02 |
| §4.9.4.A `update` split | Task 3 | T100090-05–T100090-08, T100090-13 | AC-100090-03 |
| §4.8 temporal / NFR-4 seam | Task 4 | T100090-10 | AC-100090-04 |
| Dual-backend | Tasks 2–4 | T100090-09 | AC-100090-05 |
| Slice 100140 adapter contract | Task 5 | T100090-12 | AC-100090-06 |
| FR-15 spirit | Task 3 | T100090-11 | AC-100090-07 |
| Concurrent RMW | Task 2 | T100090-14 | AC-100090-08 |

Required chain:

```text
Requirement → Capability → Implementation → Test → Evidence
```

Every acceptance criterion must be traceable.

---

## 12. Phase Exit Contract

### Outputs Produced
- Attribute `update_rule` declarations.
- Shared continuous EMA + trend engine (concurrent-safe).
- `update` rule splitter enforcing FR-11.
- Continuous observation series storage + read seam.
- Documented thin adapter hook for persona (slice 100140).

### Guarantees Provided to Downstream Phases
After this phase is accepted:
- Slice 100140 MAY implement `persona_observe_preference` as a thin adapter only.
- Discrete and continuous paths remain mutually exclusive.
- Continuous preference trajectories have durable data for later `temporal_history`.

### Known Limitations
- Full persona object and token budget not implemented.
- `temporal_history` tool packaging may be incomplete until history slices.
- Co-activation weight updates are not this engine (slice 100130).

### Downstream Prerequisites
- Slice 100100 MUST NOT use EMA to overwrite belief confidence (append-only history instead).
- Slice 100140 MUST call the shared engine for scalar preferences.
- Slice 100120 compose MAY later inject persona preferences that include `trend` fields once persona exists.

### Final Status
PASS | PASS WITH DOCUMENTED LIMITATIONS | BLOCKED | FAILED

### Verification Sign-Off
- Implementer: [Name/Agent]
- Verifier: [Name/Agent]
- Human Approver: [Name, if required]
- Date: [YYYY-MM-DD]

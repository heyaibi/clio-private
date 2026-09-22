# Phase 100140: Persona Companion Object

### Attribution
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | OpenCode CLI (Together . GLM-5.3 Flash High) | done |
| Adversary | r1 | Antigravity CLI (Gemini 3.8 Flash) | done |
| Remediator | r1 | OpenCode CLI (Together . GLM-5.3 Flash High) | done |
| Remedy Approver | r1 | OpenCode CLI (OpenRouter . Deepseek V4.1 Flash Max) | approved |
| Finalize | r1 | OpenCode CLI (Go . Deepseek V4.1 Flash High) | done |

**Index slice 100140 · **Effort:** `1×` · **Scope:** `roadmap/index.md` slice 100140 (authoritative)

### Vocabulary (read first) — zero shared moniker

| Term | Enum / form | Where it lives | Must not |
|------|-------------|----------------|----------|
| **`persona_document`** | bounded `{stable[], preferences[]}` | Companion always-on channel (§4.7) | Be confused with semantic **category** `persona` on `store` |
| **`stable` entry** | discrete/categorical key→value | `persona_put_stable` | Hold scalar intensities or use EMA |
| **`preferences` entry** | continuous/scalar + `trend` | `persona_observe_preference` → Phase 100090 engine | Hold categorical strings |
| **`update_rule`** | `discrete` \| `continuous` | Attribute / engine routing | Be stored as `epistemic_kind` |
| **`epistemic_kind`** | `fact` \| `belief` | Items/triples/beliefs | Route persona puts |
| **`source` (persona)** | e.g. `explicit` \| `inferred` on persona entries | Persona document fields | Be named **`source_type`** (belief provenance enum) |
| **Persona token budget** | fixed injection budget (default ≤400 tokens) | Compose channel (Phase 100120) | Be the same knob as memory `budget_tokens` |

## 1. Objective

### Goal
Build the **bounded persona companion document** and **always-on injection** under its own token budget with ranked truncation (§4.7, FR-7, NFR-3). Discrete stables use **invalidation-style** puts; continuous preferences call the **shared EMA engine from Phase 100090**—`persona_observe_preference` is a **thin adapter**, not a second EMA implementation (FR-25, PR-2).

### Expected Outcome
- `persona_get()` returns current `persona_document`: `stable` + `preferences` (with `trend`) and per-entry **`admission_score`**.
- `persona_put_stable(key, value, ...)` upserts categorical/durable attributes with invalidation semantics; runs §4.2 admission; **stamps `admission_score`**; rejects numeric-intensity payloads meant for EMA.
- `persona_observe_preference(key, observed_value, ...)` requires **numeric** `observed_value`; rejects categorical strings; delegates to Phase 100090 continuous engine; updates `trend`; retains create-time admission score or documented synthetic score.
- Document stays within configured persona token budget (default target ≤ 400); overflow ranked by stored `admission_score` desc, tie-break `key` asc, then **truncated**—never silently unbounded.
- Semantic category `persona` on `store` MUST NOT bypass companion budget; document non-overlapping boundary (requirement v1.8).
- Phase 100120 `compose_context` persona channel is **filled** and remains **ungated** by intent gate (§2.7).
- Telemetry on persona mutators (FR-15 spirit).

### Parent Requirement
`requirement.md` (current, v1.8+) — P5, P9, PR-2, §2.7, §4.7 (`persona_document`, admission_score truncation), §4.9.4.C, FR-7, FR-11, FR-25, NFR-3; continuous engine Phase 100090; compose channel Phase 100120; discrete invalidation Phase 100080 spirit.

### Design references (non-normative)
- Always-on small profile vs retrieval-gated episodic memory: requirement §2.7 (product-native).
- Preference drift via dual estimators: Phase 100090 / [PAMU](https://arxiv.org/html/2510.09720) as diagnostic inspiration only—formulas remain §4.6 EMA + trend.
- Keep persona **separate** from task-failure lessons (slice 100150) to avoid contaminating the always-on channel with Reflexion-style critiques ([Honest Lying](https://arxiv.org/html/2605.29463v2) risk class).

---

## 2. Scope Boundaries

### In Scope
- `persona_document` persistence (dual-backend) scoped by bank / subject as discovered.
- Tools: `persona_get`, `persona_put_stable`, `persona_observe_preference`.
- Discrete path: invalidation-style history for stable keys (align with Phase 100080 item/attribute invalidation patterns).
- Continuous path: thin adapter → Phase 100090 shared engine only.
- Token budget enforcement on put/observe and on compose packing.
- Ranked truncation when over budget using **stored per-entry `admission_score`** (requirement v1.8)—not an ad-hoc undocumented priority.
- Fill Phase 100120 persona channel section with real content.
- Structured rejection when stable↔preference paths are crossed (PR-2).
- Document and enforce: `store(category=persona)` cannot substitute for `persona_*` companion budget rules (non-overlapping boundary).

### Explicitly Out of Scope
- MCP binding (slice 100160)—in-process OK.
- Belief trajectories (Phase 100100)—persona preferences are not beliefs.
- Co-activation (Phase 100130)—persona channel is not graph-expanded for always-on inject.
- Task/failure history (slice 100150).
- Compliance erase UX (slice 100190)—but payloads MUST use DEK encryption hooks already present.
- Auto-inferring persona from every turn without explicit tool/extract path (MAY add optional extract later; not required for exit).
- Reimplementing EMA math in this slice.

### Must Not Change
- Intent gate MUST NOT gate persona injection (§2.7 / FR-7).
- Phase 100090 owns EMA α/N and trend; this slice only adapts.
- Phase 100120 dual-budget compose structure.
- PR-2: no attribute on both discrete and continuous paths.
- Vocabulary: do not name persona provenance `source_type`.

### Scope Expansion Rule
If work outside this scope appears necessary:
1. Stop.
2. Document the reason.
3. Request clarification or approval.
4. Do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- Phase 100090 accepted: shared continuous EMA engine + `wrong_update_rule` behavior.
- Phase 100120 accepted: compose persona channel + persona token budget seam.
- Phase 100080 accepted: discrete invalidation patterns reusable for stable keys.
- Phase 100040 accepted: admission scores available for truncation ranking.
- Phase 100010 accepted: config for persona budget default.

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| Continuous engine | `update`/`observe` continuous works | Phase 100090 tests |
| Compose channel | Budget section exists | Phase 100120 tests |
| Discrete invalidate | Close prior stable version | Phase 100080 patterns |
| Token estimator | Same as compose | Phase 100120 choice |
| DEK hooks | Content encrypted | Phase 100020 |

---

## 4. Existing-System Discovery

The agent MUST inspect the existing system before deciding
where or how to implement the changes.

### Required Discovery
- Phase 100090 adapter stub for `persona_observe_preference`.
- How Phase 100120 represents empty persona pack sections.
- Whether stable entries are rows, items with category `persona`, or a dedicated document table—pick one coherent model and document it.
- Existing token counter.
- Conflict: semantic `store(..., category=persona)` vs companion document—define non-overlapping responsibilities.

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

### Task 1: Persona Document Model

#### Intent
Durable bounded companion object matching §4.7 shape.

#### Required Capability or Behavior
- Persist `stable[]` and `preferences[]` with fields aligned to requirement example (`key`, `value`, `confidence`, `source`, `as_of`, `admission_score`, and `trend` on preferences).
- Bank (and subject if applicable) isolation.
- Read API returns assembled `persona_document`.

#### Architectural Responsibility
Persona store / repository.

#### Required Changes
1. Storage schema both backends including `admission_score` column/field per entry.
2. Assembly for `persona_get`.
3. Encryption for values via DEK path.
4. Written boundary note: category=`persona` store items vs `persona_document`.

#### Implementation Constraints
- Field name for provenance is `source`, not `source_type`.
- Preferences values are numeric only at rest.
- Every entry MUST have `admission_score` ∈ [0,1].

#### Expected Result
Round-trip document equals fixture JSON modulo timestamps; scores present.

### Task 2: `persona_put_stable` (Discrete)

#### Intent
Categorical/durable attributes with invalidation semantics (FR-25).

#### Required Capability or Behavior
- Upsert by `key`; prior open value invalidated (not silent overwrite without history).
- MUST reject payloads that are clearly scalar-intensity updates (numeric-only affinity)—structured error pointing to `persona_observe_preference`.
- MUST run category + admission (§4.9.3); **persist returned `admission_score` on the entry**.
- Enforces persona token budget after mutation via truncation-by-rank (requirement: truncate, not reject-on-exceed).

#### Architectural Responsibility
Persona discrete write path.

#### Required Changes
1. Tool handler with gated admit + score stamp.
2. Invalidation history retention sufficient for later `temporal_history` (slice 100150).
3. Contract tests for reject-numeric-on-stable and score persistence.

#### Implementation Constraints
- Do not call Phase 100090 engine.
- Do not use belief `belief_observe`.

#### Expected Result
Put `communication_style=concise` stores score; second put supersedes with history; compose shows latest.

### Task 3: `persona_observe_preference` (Continuous Adapter)

#### Intent
Thin EMA adapter only (slice 100090 ownership).

#### Required Capability or Behavior
- `observed_value` MUST be numeric; categorical string → structured reject → use `persona_put_stable`.
- Delegates to shared continuous engine with declared `update_rule=continuous` attribute for that preference key.
- Updates `trend` from engine.
- On first create of a preference key: run admission and stamp `admission_score`; on later observes: retain existing score (or documented synthetic).
- Budget enforcement after observe.
- Concurrent observes on same key serialized (engine guarantee).

#### Architectural Responsibility
Persona continuous adapter (no local EMA formulas).

#### Required Changes
1. Adapter wiring + attribute registration for preference keys + score stamp rules.
2. Tests: two observes move EMA toward observations; trend defined; score present.
3. Prove no duplicated α math in persona module (review/grep evidence).

#### Implementation Constraints
- MUST NOT reimplement `new_state = α·x + (1−α)·prev` locally.
- MUST NOT accept `epistemic_kind` as routing input.

#### Expected Result
Adapter tests pass against Phase 100090 engine fakes and real engine; scores survive observes.

### Task 4: Budget + Ranked Truncation

#### Intent
NFR-3 / §4.7 bounded object.

#### Required Capability or Behavior
- Configurable persona budget (default ≤400 tokens).
- When over budget, sort by `admission_score` descending, `key` ascending; drop lowest until within budget.
- Fixture MUST prove deterministic drop order for known scores.
- Never grow injection unboundedly.
- `persona_get` and compose see the same truncated document (single SoT).

#### Architectural Responsibility
Persona budgeter + compose integration.

#### Required Changes
1. Truncation algorithm + deterministic fixture test.
2. Wire compose channel to real `persona_get` assembly.
3. Intent-gate skip fixture still includes persona section (Phase 100120 regression).

#### Implementation Constraints
- Persona budget ≠ memory budget.
- Truncation is not compliance erase.
- Do not invent undocumented priority lists.

#### Expected Result
Oversize stable list truncates deterministically by score then key; NFR-3 holds on compose.

### Task 5: Tool Surface + Telemetry

#### Intent
FR-25 callable API + audit spirit.

#### Required Capability or Behavior
- All three `persona_*` tools registered in catalog.
- Mutators emit attributable telemetry (actor, bank, key, path discrete|continuous).

#### Architectural Responsibility
Tool registry + telemetry hooks.

#### Required Changes
1. Catalog entries.
2. Telemetry assertions in tests.

#### Implementation Constraints
- Do not log raw secret-bearing values.

#### Expected Result
Catalog lists tools; telemetry events present for put/observe.

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
- Fork a second EMA implementation for persona.

### Agent Decision Boundary
The agent may decide:
- Concrete file/module/class placement.
- Whether companion document is a dedicated table vs item-backed—must document.
- Local refactoring required for the phase.
- Test organization.
- Non-breaking implementation details.

The agent must request approval for:
- Architecture changes beyond the stated scope.
- Breaking API or data-contract changes.
- Security-sensitive policy decisions.
- Destructive data operations.
- Changes affecting downstream phase assumptions.
- Merging persona channel into intent-gated retrieve.

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
- Phase 100090 engine missing or persona would need a local EMA copy.

---

## 7. Security Constraints

### Required Controls
- Bank isolation on all persona reads/writes.
- DEK encryption for persona values.
- Input validation: path split stable vs preference.
- Admission/category gates where §4.9.3 requires them for `persona_put_stable`.

### Sensitive Data Rules
- Never log raw persona PII in telemetry (keys + redacted meta only).
- Never commit secrets.
- Use approved configuration mechanism.

### Security Acceptance Conditions
- Cross-bank persona read/write blocked.
- Compose cannot dump unbounded persona text past budget.

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
| T100140-01 | `persona_put_stable` then `persona_get` | Stable entry present |
| T100140-02 | Second put same key | Prior invalidated; latest visible |
| T100140-03 | Put numeric intensity on stable | Rejected → preference path |
| T100140-04 | `persona_observe_preference` numeric | EMA state + trend update via Phase 100090 |
| T100140-05 | Observe categorical string | Rejected → stable path |
| T100140-06 | Over-budget puts with known scores | Truncation order = score desc, key asc; token count ≤ budget |
| T100140-07 | Compose after intent skip | Persona section non-empty when document set |
| T100140-08 | Grep/architecture check | No local EMA formula in persona module |
| T100140-09 | Cross-bank access | Rejected |
| T100140-10 | Concurrent preference observes | No lost updates |
| T100140-11 | `source` field not `source_type` | Contract schema |
| T100140-12 | Dual-backend parity sample | Same get after puts |

### Negative Testing
Verify that:
- Invalid input is rejected.
- Unauthorized actions are blocked.
- Partial failures are handled safely.
- Duplicate/retry put behavior is invalidation-correct.
- Existing compose/retrieve tests remain intact.
- Failure does not leave budget-violating documents without repair path.

### Verification Rule
Implementation claims must be supported by actual test output,
inspection results, or other concrete evidence.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-100140-01 | `persona_get` / put / observe exist (FR-25) | T100140-01, T100140-04 | clio-persona handler tests: `t01_put_then_get_returns_stable_with_score` and `t04_observe_moves_ema_and_trend` pass; three tools exported from `clio_persona` and re-exported via `clio-lib::persona`. Catalog: `clio-config::profile` coding inventory already lists `persona_get` / `persona_put_stable` / `persona_observe_preference`. |
| AC-100140-02 | Discrete vs continuous split (PR-2) | T100140-03, T100140-05 | `t03_numeric_intensity_rejected_on_stable_path` (numeric value and continuous-declared key → `WrongUpdateRule` naming `persona_observe_preference`); `t05_discrete_declared_key_rejected` (discrete-declared key → `WrongUpdateRule` naming `persona_put_stable`). Categorical strings cannot reach the EMA path (typed `f64` surface). |
| AC-100140-03 | Adapter uses Phase 100090 only | T100140-04, T100140-08 | `clio-persona/src/observe.rs` delegates to `clio_write::persona::observe_continuous` (single call site, line 140); no EMA formula in clio-persona (grep evidence: no `apply_observation`/α math in crate, only schema registration). Shared-engine equivalence already pinned by `clio-write::persona_tests::t12_adapter_calls_shared_engine`. |
| AC-100140-04 | Token budget + score-ranked truncation (NFR-3 / §4.7) | T100140-06 | `budget_tests::over_budget_truncates_by_score_then_key` fixture: scores (0.9, 0.9, 0.5, 0.1) → kept `["alpha","beta"]`, dropped `["gamma","delta"]`; tie-break proof in `equal_scores_tie_break_by_key_ascending`; used tokens ≤ budget asserted. Same estimator (`clio-types::tokens::estimate_tokens`) backs compose packing. |
| AC-100140-05 | Always-on vs intent gate (§2.7 / FR-7) | T100140-07 | `compose_wire_tests::compose_after_intent_skip_includes_persona_section`: with a skip gate, persona section non-empty (≤ persona budget) and memory empty. Phase 100120 regression `compose_tests::t05_auto_path_skips_memory_but_keeps_persona` still green. |
| AC-100140-06 | Invalidation semantics for stable | T100140-02 | `t02_second_put_invalidates_prior`: prior version closed on both axes (`valid_until` set), latest visible via `persona_get`, both versions retained in `stable_history` (slice-15 feed). Partial UNIQUE open-row index in DDL enforces one open row per (bank, key). |
| AC-100140-07 | Vocab: `source` ≠ `source_type` | T100140-11 | `clio-types/src/persona_tests.rs::vocab_contract_source_not_source_type` (serde emits `source`, never `source_type`); `pg_persona_tests::persona_schema_uses_source_column` inspects `information_schema.columns`: both persona tables have `source`, no `source_type`, plus `admission_score`. |
| AC-100140-08 | Bank isolation | T100140-09 | `run_persona_suite` (both backends): cross-bank `get_persona_document` / `stable_history` / ciphertext inspect return empty; clio-persona `t09_cross_bank_access_isolated` same. |
| AC-100140-09 | Dual-backend sample | T100140-12 | `pg_persona_tests::persona_document_parity_sqlite_vs_postgres`: same puts on both backends → same document keys/values/scores. SQLite+Postgres contract suites (`run_persona_suite`) both pass. |

### Definition of Done
- [x] All in-scope behavior is implemented.
- [x] All acceptance criteria pass.
- [x] Required tests pass (`cargo test --workspace --locked`: all suites green, 0 failures).
- [x] No unauthorized changes were introduced (changes limited to clio-types, clio-store, clio-persona, clio-lib, clio-retrieve token re-export, `sql/001_core.sql`, workspace manifests).
- [x] Existing behavior remains intact (`make check` green: fmt + clippy -D warnings + full workspace tests).
- [x] Security checks pass (cross-bank reads fail closed — T100140-09; values DEK-encrypted at rest — ciphertext inspection asserts; no raw persona values in telemetry — `PersonaEvent` carries keys + redacted meta only).
- [x] Documentation is updated where required (module headers, non-overlap boundary note in `clio-persona/src/lib.rs`).
- [x] Evidence is collected (below).
- [x] Verification is completed (`make coverage` exit 0; per-file scan: no file below 90% functions or lines).
- [x] Required approval is obtained (downstream pipeline step).

### Completion Evidence
- Implementation summary: new crate `crates/clio-persona` (`persona_get`, `persona_put_stable`, `persona_observe_preference`, `PersonaEvent` telemetry, budget truncation in `budget.rs`); new `clio-types::persona` document shapes + `clio-types::tokens` shared estimator; new `clio-store::PersonaStore` trait with SQLite + Postgres implementations over dedicated persona tables (added `admission_score` + `source` columns and the open-row UNIQUE index in `sql/001_core.sql`, edited directly); stable values encrypted under the bank DEK (subject id = bank id); continuous path is a thin adapter over the shared §4.6 engine.
- Persona vs category=`persona` boundary note: the companion document is assembled only from `persona_stable_entries` + `persona_preferences` under the persona token budget. Semantic `store(..., category=persona)` items are a separate generic-store subsystem surfaced through retrieval; they never feed `persona_get`, so category-`persona` items cannot bypass the companion budget. The two paths share no identity space.
- Truncation ranking rule: stored per-entry `admission_score` descending, tie-break `key` ascending; drop lowest until within budget; token cost per entry = `estimate_tokens(key) + estimate_tokens(text)` — the same estimator and rule compose uses, so `persona_get` and compose see the same truncated view.
- Proof of Phase 100090 reuse (no second EMA): `clio-persona/src/observe.rs:140` calls `clio_write::persona::observe_continuous`; grep of `crates/clio-persona` finds no `apply_observation`/α arithmetic; the single EMA implementation remains `clio-types::apply_observation` behind the store's transactional RMW (serialized per key — T100140-10 thread test: 16 concurrent observes land all 17 series points, final state exact).
- Test execution output: `make check` green (fmt, clippy `-D warnings`, full workspace tests, 0 failures); `make coverage` green — aggregate functions 98.50%, lines 98.40%; per-file scan shows every reported file ≥90% on both metrics (new files: persona_store 100/100, sqlite_persona 96.0/99.2, postgres_persona 95.8/97.6, clio-persona modules 100–100/97.2–100).
- Compose before/after pack sample: before (empty stub) persona section text empty; after `persona_put_stable(name=Ada)` + `persona_put_stable(communication_style=concise)`, the pack's persona section text is non-empty (`name: Ada\ncommunication_style: concise`), tokens ≤ 400, and the memory section stays empty under the intent-skip gate.
- Verification report: T100140-01–T100140-12 mapped to tests in `clio-types/src/persona_tests.rs`, `clio-store/src/persona_tests.rs` + `pg_persona_tests.rs` + `sqlite_persona_tests.rs`, `clio-persona/src/{budget,stable,observe,compose_wire}_tests.rs`; T100140-08 covered by the grep report above; T100140-12 by the parity sample and both backend suites.
- Known limitations: no automatic persona inference from dialogue (explicit tools only, per scope); concurrent first-observes on a brand-new key rely on declaration-registration retry (engine RMW serializes the value path); observed preference state is a projection of the shared engine state — a crash between engine observe and row upsert self-heals on the next observe; truncation may drop low-ranked stables (operators tune budgets); MCP binding deferred to its own phase (in-process surface complete).

### Final Status
PASS WITH DOCUMENTED LIMITATIONS

---

## 10. Failure Handling and Recovery

### Expected Failure Modes

| Failure | Detection | Recovery |
|---------|-----------|----------|
| EMA engine unavailable | Error | Fail closed on observe; do not invent local EMA |
| Budget overflow | Token count | Truncate per policy |
| Gate reject on stable | Admission | Structured rejection; no write |
| Compose missing persona | Pack inspect | Fail test; fix wiring |

### Rollback Strategy
Revert code; compose falls back to empty persona section. Data tables may remain.

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
| FR-25 / §4.9.4.C | Tasks 2–3, 5 | T100140-01, T100140-04 | AC-100140-01 |
| PR-2 / FR-11 | Tasks 2–3 | T100140-03, T100140-05 | AC-100140-02 |
| P9 / Phase 100090 | Task 3 | T100140-04, T100140-08 | AC-100140-03 |
| NFR-3 / §4.7 | Task 4 | T100140-06 | AC-100140-04 |
| FR-7 / §2.7 | Task 4 | T100140-07 | AC-100140-05 |
| §4.6 discrete | Task 2 | T100140-02 | AC-100140-06 |
| Vocab | Task 1 | T100140-11 | AC-100140-07 |
| Bank | Task 1 | T100140-09 | AC-100140-08 |
| Dual backend | Task 1 | T100140-12 | AC-100140-09 |

Required chain:

```text
Requirement → Capability → Implementation → Test → Evidence
```

Every acceptance criterion must be traceable.

---

## 12. Phase Exit Contract

### Outputs Produced
- `persona_document` store + three `persona_*` tools.
- Always-on compose channel filled under budget.
- Thin continuous adapter over Phase 100090.

### Guarantees Provided to Downstream Phases
After this phase is accepted:
- Slice 100150 `temporal_history` can read preference series / stable invalidation history.
- Slice 100160 can bind `persona_*` write tools over MCP with identical semantics.
- Intent gate remains irrelevant to persona injection.

### Known Limitations
- Automatic persona inference from dialogue may be absent (explicit tools required).
- Truncation may drop low-ranked stables—operators must tune budgets.

### Downstream Prerequisites
- Slice 100150 MUST NOT dump full persona into task failure lessons.
- Slice 100160 MUST keep path split in tool_schemas.

### Final Status
PASS | PASS WITH DOCUMENTED LIMITATIONS | BLOCKED | FAILED

### Verification Sign-Off
- Implementer: Developer r1 (OpenCode CLI, GLM-5.3 Flash High)
- Verifier: [Name/Agent]
- Human Approver: [Name, if required]
- Date: 2026-09-19

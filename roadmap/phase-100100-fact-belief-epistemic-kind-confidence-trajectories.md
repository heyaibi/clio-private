# Phase 100100: Fact/Belief Epistemic Kind and Confidence Trajectories

### Attribution
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | OpenCode CLI (Go . Deepseek V4.1 Flash High) | done |
| Adversary | r1 | OpenCode CLI (OpenRouter . Deepseek V4.1 Flash Max) | done |
| Remediator | r1 | OpenCode CLI (Together . GLM-5.3 Flash High) | done |
| Remedy Approver | r1 | OpenCode CLI (OpenRouter . Deepseek V4.1 Flash Max) | approved |
| Finalize | r1 | OpenCode CLI (Go . Deepseek V4.1 Flash High) | done |

**Index slice 100100 · **Effort:** `1×` · **Scope:** `roadmap/index.md` slice 100100 (authoritative)

### Vocabulary (read first) — zero shared moniker

| Term | Enum | Where it lives | Must not |
|------|------|----------------|----------|
| **`epistemic_kind`** | `fact` \| `belief` | Item/triple/belief field (FR-14)—**this phase** | Be used as `update`'s routing parameter |
| **`update_rule`** | `discrete` \| `continuous` | Attribute schema + `update` (FR-11 / Phase 100090) | Be stored in `epistemic_kind` |

Belief confidence is **append-only history**, never EMA (`update_rule=continuous`). Do not name either field `class`. Normative defs: `requirement.md` §10.

## 1. Objective

### Goal
Tag every memory item as **`fact` or `belief`** via `epistemic_kind`; give beliefs an **append-only confidence history** with per-entry `source_type`; expose `belief_observe` / `belief_history`; and ensure retrieval/read responses surface `epistemic_kind` and, for beliefs, current confidence + `source_type` (P11, P13, §4.10–§4.11, FR-13, FR-14, PR-8).

### Expected Outcome
- Every stored item carries mandatory `epistemic_kind ∈ {fact, belief}` (FR-14).
- Beliefs always carry `source_type`-tagged confidence history; facts MUST NOT carry a confidence trajectory and are not gradually EMA-smoothed (PR-2 / §4.11).
- `belief_observe(proposition, confidence, evidence_ref, source_type)` appends (creates belief if needed); never overwrites prior history entries.
- **Admission (locked Option B):** Beliefs are §4.10 **belief objects**—not a sixth semantic category and not an episodic type tag. Category gate = **N/A**. Five-factor admission = **MUST on create**; **append** validates without re-scoring novelty/utility (§4.9.3 belief-writes row / FR-13).
- `belief_history(belief_id_or_proposition)` returns the full trajectory.
- Read/retrieve response shapes include `epistemic_kind` and, when `epistemic_kind=belief`, current `source_type` and confidence.
- Reject treating belief updates as EMA continuous updates or as silent fact overwrite.
- Point-in-time belief confidence via history `as_of` (NFR-4).

### Parent Requirement
`requirement.md` (current) — P11, P13, PR-8, §4.10 (incl. admission), §4.11, §4.9.3 belief-writes row, §4.9.4.E `belief_*`, §7.1/§7.2 epistemic_kind fields, FR-13, FR-14, NFR-4, NFR-5, NFR-6 foreshadow.

### Design references (non-normative)
- Separate verifiability (fact vs belief) from provenance (`source_type`)—requirement §4.11 rationale; avoid three-way fact/opinion/belief peer classes.
- Transparency via inspectable trajectories rather than a parallel logging system (§4.12)—history is write-path data.

---

## 2. Scope Boundaries

### In Scope
- Enforce and backfill-safe rules for `epistemic_kind` on items (and triples already storing epistemic_kind from Phase 100080).
- Belief record model: proposition, `confidence_history[]` with `{as_of, confidence, evidence_ref, source_type}` as §4.10 objects (Option B).
- Tools (in-process OK): `belief_observe`, `belief_history`.
- Create vs append admission split (create = full five-factor; append = validate + audit only).
- Current confidence = latest history entry; trajectory fully readable.
- `source_type ∈ {user_stated, agent_inferred, third_party}` required on each belief history entry.
- Surface `epistemic_kind` / belief confidence / `source_type` on get and on whatever retrieve response stub exists (full hybrid retrieve is slice 100120—define the **response field contract** now so slice 100120 cannot omit it).
- Reject treating belief updates as EMA continuous updates or as silent fact overwrite.
- Point-in-time belief confidence via history `as_of` (NFR-4).

### Explicitly Out of Scope
- Hybrid retrieve orchestration, intent gate, compose (slice 100120)—only response field contract + any existing get paths.
- Persona tools (slice 100140).
- Full `audit_trail` / `inspect` / `correct` UX (slice 100180)—but belief history data must be reusable by those later.
- MCP schema publication (slice 100160–17).
- Changing fact supersession to append confidence (facts stay bi-temporal invalidation).
- Auto-promoting high-confidence `user_stated` beliefs to `fact` (explicitly forbidden by §4.11).
- Inventing a sixth semantic category or new episodic type for beliefs (forbidden; Option B locked).

### Must Not Change
- FR-14 two-kind taxonomy (no third peer epistemic kind).
- Phase 100080 discrete supersession for facts.
- Phase 100090 EMA engine—beliefs do not use it for confidence.
- Phase 100040 five-factor scoring formulas (used on belief **create** only).
- Phase 100020 encryption for proposition / evidence-linked content.

### Scope Expansion Rule
If work outside this scope appears necessary:
1. Stop.
2. Document the reason.
3. Request clarification or approval.
4. Do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- Phase 100030 accepted: items already have `epistemic_kind` / `source_type` fields (enforce end-to-end here).
- Phase 100040 accepted: gated long-term writes for `belief_observe`.
- Phase 100080 accepted: triples may already carry `epistemic_kind`; belief trajectory API completes the belief story.
- Phase 100090 accepted recommended so agents do not confuse continuous EMA with belief confidence (orthogonal mechanisms).

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| Item repository | Can store epistemic_kind + history | Phase 100030 |
| Admission gates | Long-term write gating works | Phase 100040 tests |
| Clock | Deterministic as_of | Injectable clock |
| Encryption | Proposition content under DEK | Phase 100020 |

---

## 4. Existing-System Discovery

The agent MUST inspect the existing system before deciding
where or how to implement the changes.

### Required Discovery
- Where `epistemic_kind` / `source_type` are already validated on `store` and `triple_add`.
- Whether beliefs are separate rows vs items with `epistemic_kind=belief`.
- Confirm Option B belief store hooks (not semantic category / episodic type).
- How propositions are normalized for identity (exact string vs canonical key)—document the chosen identity rule.
- Existing get/retrieve response builders that must gain belief fields.
- Admission scoring entry points reusable for belief **create** only.

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

### Task 1: Class Enforcement Completeness

#### Intent
Make FR-14 mandatory everywhere items are written or read.

#### Required Capability or Behavior
- Create/update paths require `epistemic_kind`.
- `epistemic_kind=belief` requires `source_type` on the *current* evidence (history entry); `epistemic_kind=fact` MUST NOT require `source_type` and SHOULD omit it.
- Facts MUST NOT allocate a `confidence_history` array; single confidence field allowed as static metadata but MUST NOT be treated as a trajectory.
- Attempts to attach confidence_history to facts → reject.

#### Architectural Responsibility
Item/triple write validation shared across store paths.

#### Required Changes
1. Harden validators on all write entrypoints that create durable items.
2. Migration/backfill policy for any pre-epistemic_kind rows (fail closed or default with audit—document; prefer explicit backfill script if needed).
3. Tests for both epistemic kinds.

#### Implementation Constraints
- Do not invent `opinion` as a third epistemic kind.
- Do not auto-upgrade belief → fact on high confidence.

#### Expected Result
Illegal epistemic_kind/source_type combinations cannot commit.

### Task 2: Belief Record + Append-Only History

#### Intent
Implement §4.10 versioned belief objects (FR-13).

#### Required Capability or Behavior
- Belief identity: stable id and/or normalized proposition key (document).
- `confidence_history` is append-only; updates never rewrite prior entries.
- Current confidence = last entry’s confidence; current `source_type` = last entry’s `source_type`.
- Each entry: `as_of`, `confidence` ∈ [0,1], `evidence_ref`, `source_type`.
- Dual-backend parity.

#### Architectural Responsibility
Belief repository on Phase 100020 storage.

#### Required Changes
1. Schema for beliefs + history (table or JSON list with integrity constraints—prefer queryable rows if as-of filters are first-class).
2. Append API used by `belief_observe`.
3. Integrity: no UPDATE of historical confidence rows.

#### Implementation Constraints
- Content (proposition text) encrypted per DEK rules.
- History entries are not EMA-smoothed.
- Bank scoping required.

#### Expected Result
Multiple observes produce a growing trajectory; prior points unchanged.

### Task 3: `belief_observe` (Create vs Append)

#### Intent
Agent-callable append of evidence (FR-13 / §4.9.4.E) with locked Option B gating.

#### Required Capability or Behavior
- `belief_observe(proposition, confidence, evidence_ref, source_type)`.
- Creates belief if none exists for the identity key; otherwise appends.
- **Create path:** MUST pass five-factor admission (§4.2); category gate N/A; structured rejection on fail; no sixth category / no forged episodic type.
- **Append path:** MUST validate `confidence` ∈ [0,1], `source_type` enum, bank/auth; MUST emit audit; MUST NOT re-run novelty/utility admission as a new candidate.
- MUST NOT overwrite history.
- Emit telemetry (FR-15 spirit).

#### Architectural Responsibility
Belief write service (Option B store).

#### Required Changes
1. Tool/handler with explicit create vs append branches.
2. Validation of source_type enum and confidence range on both paths.
3. Tests: create, append-after-create, create gate reject, append always succeeds when validation passes even if a fresh admit would fail novelty, invalid source_type.

#### Implementation Constraints
- Do not route through Phase 100090 EMA.
- Do not call discrete invalidation to “replace” a belief confidence.
- Do not invent semantic category or episodic type for beliefs.

#### Expected Result
Create is gated by admission score; append grows history without re-admission.

### Task 4: `belief_history` + Point-in-Time

#### Intent
Inspectable trajectories (P12 / NFR-4).

#### Required Capability or Behavior
- `belief_history(belief_id_or_proposition)` returns full ordered trajectory + source_types.
- Support as-of filtering: confidence that was current at time T = latest entry with `as_of ≤ T` (document).
- Empty/unknown proposition → structured not-found.

#### Architectural Responsibility
Belief read API.

#### Required Changes
1. History query API.
2. As-of helper shared with future `temporal_history`.
3. Tests for full trajectory and mid-timeline as-of.

#### Implementation Constraints
- Explicit history reads run even if a future intent gate would skip background retrieve (FR-24 spirit).
- Do not return gist-only substitutes for proposition text when exact proposition is requested.

#### Expected Result
Fixture timeline answers “what confidence did we hold then?”

### Task 5: Surface Class on Reads / Retrieve Contract

#### Intent
Consumers always see epistemic_kind (FR-14 / PR-8).

#### Required Capability or Behavior
- `get` / list / any retrieve response builder includes `epistemic_kind`.
- When `epistemic_kind=belief`, include current `source_type` and current `confidence`.
- Document that treating belief as fact without a caller confidence-threshold check is a consumer bug (§4.11)—optionally return a `requires_confidence_check: true` hint field (non-normative nicety; do not require agents to honor it for phase exit).

#### Architectural Responsibility
Read DTO / response mapping layer.

#### Required Changes
1. Update response serializers.
2. Contract tests for fact vs belief payloads.
3. Freeze a retrieve-hit schema fragment for slice 100120 to implement against.

#### Implementation Constraints
- Do not strip epistemic_kind fields for “compact” responses by default.
- Facts must not pretend to have belief trajectories.

#### Expected Result
Golden JSON fixtures for fact hit vs belief hit.

### Implementation Freedom
The agent may choose the concrete implementation structure,
file locations, naming, and internal design provided that:
- The required behavior is satisfied.
- Architectural boundaries are respected.
- Existing contracts are preserved.
- All acceptance criteria pass.
- No prohibited changes are introduced.
- Rust sources stay ≤450 lines per file.

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
- Promote belief → fact automatically.
- Overwrite confidence history entries.
- Route belief confidence through the EMA engine.

### Agent Decision Boundary
The agent may decide:
- Concrete file/module placement.
- Proposition identity normalization rules (document them).
- History storage shape (rows vs document)—prefer as-of-friendly.
- Test organization.

The agent must request approval for:
- Architecture changes beyond the stated scope.
- Breaking API or data-contract changes.
- Adding a third epistemic peer kind.
- Reopening Option B (dedicated belief objects) without amending `requirement.md`.
- Security-sensitive policy decisions.
- Destructive data operations.
- Changes affecting downstream retrieve/compose assumptions.

### Mandatory Stop Conditions
Stop and report if:
- Requirements are ambiguous.
- Repository facts contradict the plan.
- Required dependencies are missing.
- Scope expansion is required.
- A destructive migration is necessary but unspecified.
- Existing architecture cannot support append-only history
  without an unapproved structural change.
- Correctness cannot be verified.
- Gate path for `belief_observe` attempts to invent a sixth semantic category or episodic type (Option B forbids this; stop and use §4.10 belief objects).

---

## 7. Security Constraints

### Required Controls
- Gated `belief_observe`; bank-scoped beliefs; actor attribution.
- Validate `source_type` enum; reject free-form provenance labels.
- Encrypt proposition / sensitive evidence-linked content.

### Sensitive Data Rules
- Never log DEKs.
- Never commit secrets.
- Mask credentials that appear in evidence_ref or proposition text in logs.

### Security Acceptance Conditions
- Cross-bank belief_history fails closed.
- Ungated belief_observe cannot commit.

---

## 8. Test and Verification Strategy

### Required Tests
- [x] Unit tests — `clio-types` belief/read, `clio-store` belief_store helpers, `clio-belief` observe/history/read.
- [x] Integration tests — `clio-belief` tool suite over `SqliteStore`; `clio-store` `belief_tests` dual-backend parity.
- [x] Contract tests — `clio-types/src/read_tests.rs` golden fact vs belief JSON; `clio-belief/src/read_tests.rs` stored-item mapping.
- [x] End-to-end tests — `clio-belief` observe→append→history→retrieve-hit over a real store.
- [x] Regression tests — full `cargo test --workspace --locked` (95 pre-existing `clio-write` tests, `clio-store` triple/supersession/EMA suites, `clio-admission` scoring) remain green.
- [x] Security tests — proposition ciphertext hides plaintext; cross-bank history empty; append wrong bank rejected; destroyed DEK renders belief unreadable (`clio-store/src/belief_tests.rs`).
- [x] Failure-mode tests — create below threshold rejected with no write; unavailable signal backend fails closed; invalid confidence/source_type rejected; append unknown belief rejected.

### Required Test Scenarios

| Test ID | Scenario | Expected Result |
|---------|----------|-----------------|
| T100100-01 | Store/get fact | `epistemic_kind=fact`; no confidence_history |
| T100100-02 | `belief_observe` create (passes admission) | Belief created; history length 1 |
| T100100-03 | Second `belief_observe` same proposition | History length 2; first entry unchanged |
| T-03b | Append when a fresh create would fail novelty | Append succeeds; history grows (no re-admission) |
| T100100-04 | `belief_history` full | Returns ordered entries with source_types |
| T100100-05 | Belief as-of mid timeline | Returns confidence current at T |
| T100100-06 | Belief without source_type | Rejected |
| T100100-07 | Fact with confidence_history attach | Rejected |
| T100100-08 | Auto-promote high-confidence user_stated → fact | Does not occur |
| T100100-09 | `belief_observe` create below admission threshold | Structured rejection; no write |
| T-09b | Forged sixth semantic category / episodic type for belief | Rejected / not used |
| T100100-10 | Get/retrieve DTO for belief | Surfaces epistemic_kind, source_type, confidence |
| T100100-11 | Dual-backend parity | Same trajectories on both backends |
| T100100-12 | Telemetry on observe | Event observable |
| T100100-13 | `update(..., update_rule=belief)` | Rejected at Phase 100090 boundary (cross-check) |

### Negative Testing
Verify that:
- Invalid confidence / source_type rejected.
- Unauthorized bank access blocked.
- Partial failures do not orphan half-written history.
- Duplicate observe with same evidence is documented (append vs idempotent)—pick one; test it.
- Existing fact supersession and EMA paths remain intact.
- Failure does not DELETE prior history.

### Verification Rule
Implementation claims must be supported by actual test output,
inspection results, or other concrete evidence.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Evidence (r1) |
|-------|----------------------|---------------------|-------------------|
| AC-100100-01 | FR-14 epistemic_kind enforcement | T100100-01, T100100-06, T100100-07 | `clio-types` `item.validate`/`MemoryItem` tests; `clio-types/src/belief_tests.rs::fact_items_never_carry_a_trajectory` (T100100-07's rejection is **structural**: `MemoryItem` has no `confidence_history` field, so a fact cannot carry a trajectory by type, and `item.validate` rejects `source_type` on facts; the test asserts a fact with scalar confidence validates — no runtime rejection path exists to call); `clio-store/src/belief_tests.rs` (invalid confidence/source_type rejected). All green under `cargo test --workspace --locked`. |
| AC-100100-02 | FR-13 append-only belief history | T100100-02, T100100-03 | `clio-belief/src/observe_tests.rs::t02...`, `t03...`; `clio-store/src/belief_tests.rs::run_belief_suite` asserts prior entry byte-identical after append and that SQLite/Postgres history rows only INSERT. |
| AC-100100-03 | `belief_history` + NFR-4 as-of | T100100-04, T100100-05 | `clio-belief/src/history_tests.rs::t04_full_trajectory_by_id_and_proposition`, `t05_as_of_returns_confidence_current_then`; `clio-types/src/belief_tests.rs::as_of_confidence_picks_latest_at_or_before`. |
| AC-100100-04 | Create gated; append not re-admitted | T100100-09, T-03b, T-09b | `clio-belief/src/observe_tests.rs::t09_create_below_threshold_is_rejected_without_write`, `t03b_append_succeeds_even_when_fresh_create_would_fail`, `t09b_no_sixth_category_or_forged_episodic_type`. Concurrent first observes serialize as append: the create-race loser retries the append branch (`observe_flow_tests.rs::create_race_loser_appends_instead_of_erroring`, `::create_race_loser_propagates_error_when_identity_is_gone`, `::concurrent_first_observes_serialize_as_append`). |
| AC-100100-05 | Reads surface epistemic_kind/belief fields | T100100-10 | Golden JSON fixtures `clio-types/src/read_tests.rs`; stored-item mapping `clio-belief/src/read_tests.rs`. Fact hits omit `source_type`/`confidence`; belief hits include them plus `requires_confidence_check`. |
| AC-100100-06 | No belief→fact auto-promotion | T100100-08 | `clio-belief/src/observe_tests.rs::t08_high_confidence_user_stated_stays_a_belief` (0.99 `user_stated` stays `belief`; no item/fact row created). |
| AC-100100-07 | Dual-backend parity | T100100-11 | `clio-store/src/belief_tests.rs::postgres_belief_parity` runs the identical `run_belief_suite` on `SqliteStore` and `PostgresStore`; both green. |
| AC-100100-08 | Telemetry | T100100-12 | `clio-belief/src/observe_tests.rs::t12_telemetry_emits_created_appended_and_rejected`; durable `audit_events` rows in `sqlite_belief`/`postgres_belief` carry the `confidence` column plus `detail_json` `{created|appended, confidence, source_type, entry_count}` sufficient to reconstruct each observe (asserted by `clio-store/src/belief_tests.rs::sqlite|postgres_belief_audit_rows_carry_reconstruction_fields` on both backends). |
| AC-100100-09 | Option B taxonomy (no sixth category) | T-09b | Beliefs are separate `beliefs` rows with no `items` carrier (asserted in `t08`); `EpisodicType::parse("belief")` and `UpdateRule::parse("belief")` rejected. |

### Definition of Done
- [x] All in-scope behavior is implemented. — `clio-types` belief/read shapes, `clio-store` belief repository on both backends, `clio-belief` `belief_observe` / `belief_history`, and the frozen `RetrieveHit` contract.
- [x] All acceptance criteria pass. — AC-100100-01…AC-100100-09 evidenced above.
- [x] Required tests pass. — `make check` (fmt + `clippy -D warnings` + `cargo test --locked --workspace`) green; `make coverage` green.
- [x] No unauthorized changes were introduced. — Only phase-scoped additive changes plus the authorized beliefs-table reshape.
- [x] Existing behavior remains intact. — Pre-existing triple/supersession/EMA/admission suites unchanged and green.
- [x] Security checks pass. — Proposition encrypted under DEK; cross-bank reads fail closed; destroyed DEK fails closed.
- [x] Documentation is updated where required. — Module headers and this phase file updated; identity rule documented in `clio-types::belief::proposition_key`.
- [x] Evidence is collected. — Command output below and test names above.
- [x] Verification is completed. — Coverage: aggregate 96.04% lines / 99.30% functions, every reported file ≥90% lines and functions.
- [x] Required approval is obtained. — N/A beyond the pipeline's own review chain.

### Completion Evidence

**Implementation summary (r1).** Added the `clio-belief` crate and wired belief objects end to end.
- `clio-types`: `BeliefObject`, `ConfidenceEntry`, `check_confidence`, `proposition_key`, and the frozen `RetrieveHit` response contract with `from_item` / `from_belief` mappers.
- `clio-admission`: `decide_ungated(key, …)` extracts the gate-free five-factor path reused by belief create; `decide` now delegates to it (formulas unchanged).
- `clio-store`: `BeliefStore` trait plus SQLite and Postgres implementations (`sqlite_belief`, `postgres_belief`). Create inserts the belief and its first entry atomically; append only INSERTs history rows and never rewrites prior entries. Proposition text is sealed under the subject DEK; only the normalized key is plaintext. Create/append also write durable `audit_events` rows.
- `clio-belief`: `belief_observe` (create gated by five-factor admission, append validates without re-admission), `belief_history` (by id or proposition, with `as_of` point-in-time), `BeliefSignalSource`, and `BeliefEvent` telemetry.
- Schema: `sql/001_core.sql` beliefs tables reshaped to `subject_id` + `proposition_key` + `proposition_ciphertext` (legacy plaintext `proposition`/`item_id` removed); `belief_reshape` drops an empty stale table on either backend; `schema_version` bumped 4→5.

**Proposition identity rule.** `bank_id` + `proposition_key`, where `proposition_key = (proposition split on whitespace, collapsed to single spaces, lowercased)`. Documented on `clio_types::belief::proposition_key`; `belief_history` and `belief_observe` resolve the same identity without a scan.

**Retrieve-hit schema fragment for slice 100120** (`clio_types::RetrieveHit`, JSON field order): `item_id, bank_id, kind, category?, episodic_type?, epistemic_kind, source_type?, confidence?, gist?, requires_confidence_check`. Facts omit `source_type`/`confidence`; beliefs include current values and set `requires_confidence_check=true`. Golden fixtures: `clio-types/src/read_tests.rs`.

**Test execution output.**
- `make check` → fmt clean, `clippy --workspace --all-targets --all-features --locked -- -D warnings` clean, `cargo test --locked --workspace` green (all suites pass, 0 failed).
- `make coverage` → TOTAL lines 96.04%, functions 99.30%; all 85 reported files ≥90% lines and ≥90% functions. New files: `clio-types/belief.rs` 82/82 lines, `clio-store/belief_reshape.rs` 149/149, `clio-store/belief_store.rs` 100% lines, `clio-belief/{observe,history,signals}.rs` 100% lines.
- Adversarial checks included: `t09b` (no forged category/episodic type), dead closures replaced with `expect` invariants after the first coverage run reported `sqlite_belief.rs` functions at 88.89%.

**Verification report.** AC-100100-01…AC-100100-09 each map to a named test (table above); dual-backend parity runs the same `run_belief_suite` on SQLite and Postgres; security assertions cover ciphertext-at-rest, cross-bank fail-closed, and crypto-shredding.

**Known limitations.** Full hybrid retrieve/compose is not implemented — only the frozen response contract. Out-of-order `as_of` appends are allowed and ordered by `as_of`; `belief_history`'s not-found uses `ErrorCode::NotFound`. `as_of` values order and filter as ISO-8601 text (lexicographic): use one canonical form per trajectory (date-only or full timestamp), never mix the two. Belief audit rows carry confidence/source_type/entry_count; `admission_score` is not persisted on the belief create row (the decision lives in the in-process `BeliefEvent`). No cross-crate Postgres test in `clio-belief` (only `clio-store` owns the PG test lock), so the tool-level PG path is exercised indirectly through the store suite.

**Remediation (r1).** Adversarial findings addressed: concurrent first observes now serialize as append (retry-on-duplicate in `clio-belief/src/observe.rs`, covered by a two-thread test); `belief` is a tunable admission key (`clio-config` KNOWN_ADMISSION_KEYS + default prior 0.50, behavior-preserving); durable audit rows carry confidence/source_type/entry_count (both backends); `beliefs.updated_at` is maintained on append as `MAX(as_of)` matching the derived read; `ErrorCode::NotFound` added for `belief_history` not-found; reshape guard also counts orphaned `belief_confidence_entries`; §4.10 implicit-kind and `as_of` format contract documented; AGENTS.md closing header line added to the nine new files. Re-verified: `make check` PASS (fmt, clippy -D warnings, 18 suites, 365 tests, 0 failed), `make coverage` PASS (TOTAL 99.10% functions / 98.74% lines, every reported file ≥90% on both gated metrics).

---

## 10. Failure Handling and Recovery

### Expected Failure Modes

| Failure | Detection | Recovery |
|---------|-----------|----------|
| Gate reject | Admission result | No history append |
| Unknown belief id | Not found | Structured error |
| Concurrent observes | Txn / append race | Serializable append; order by as_of/id |
| Missing source_type | Validation | Reject |

### Rollback Strategy
Revert code; history rows are append-only and safe. Do not DELETE trajectories to roll back. Additive migrations preferred.

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
| FR-14 / §4.11 | Tasks 1, 5 | T100100-01, T100100-06, T100100-07, T100100-10 | AC-100100-01, AC-100100-05 |
| FR-13 / §4.10 | Tasks 2–3 | T100100-02, T100100-03, T-03b | AC-100100-02, AC-100100-04 |
| NFR-4 belief as-of | Task 4 | T100100-04, T100100-05 | AC-100100-03 |
| §4.9.3 belief-writes / Option B | Task 3 | T100100-09, T-09b | AC-100100-04, AC-100100-09 |
| PR-8 / §4.11 no auto-fact | Task 1 | T100100-08 | AC-100100-06 |
| Dual-backend | Task 2 | T100100-11 | AC-100100-07 |
| FR-15 spirit | Task 3 | T100100-12 | AC-100100-08 |

Required chain:

```text
Requirement → Capability → Implementation → Test → Evidence
```

Every acceptance criterion must be traceable.

---

## 12. Phase Exit Contract

### Outputs Produced
- Enforced fact/belief epistemic_kind.
- Append-only belief confidence trajectories.
- `belief_observe` / `belief_history`.
- Read/retrieve response field contract including epistemic_kind + belief metadata.

### Guarantees Provided to Downstream Phases
After this phase is accepted:
- Slice 100120 retrieve/compose MUST populate the frozen belief/fact fields.
- Slice 100180 audit/inspect can read belief trajectories without a second log store.
- Facts remain supersession-based; beliefs remain append-only.

### Known Limitations
- Full hybrid retrieve not implemented.
- `temporal_history` unified tool packaging may still be incomplete.
- MCP schemas come later.

### Downstream Prerequisites
- Slice 100120 MUST NOT drop `epistemic_kind` from hits to save tokens without an explicit alternate exact-read path.
- Slice 100140 persona stables remain discrete facts/labels; scalar prefs remain EMA—not belief trajectories unless classified as beliefs intentionally.

### Final Status
PASS

### Verification Sign-Off
- Implementer: OpenCode CLI (Go . Deepseek V4.1 Flash High) — r1
- Verifier: [pending adversary review]
- Human Approver: N/A
- Date: 2026-09-18

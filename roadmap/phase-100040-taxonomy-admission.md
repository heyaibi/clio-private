# Phase 100040: Taxonomy and Admission Scoring

### Attribution
| Role | Agent |
|------|-------|
| Developer | Open Code (Muse Spark 1.3 Contributor) |
| Adversary | Open Code (Muse Spark 1.3 Contributor) |

**Index slice 100040 · **Effort:** `1×` · **Scope:** `roadmap/index.md` slice 100040 (authoritative)

## 1. Objective

### Goal
Implement both write gates end to end: (1) closed category whitelist for semantic types (§4.1 / FR-1), then (2) five-factor admission scoring with thresholds, deterministic decisions, logged rejects, and `admit_preview` without write (§4.2 / FR-2 / FR-21). Implement a parallel **episodic admission path** for episodic type tags (§4.9.3)—not a forged sixth semantic category. All long-term public writes (including later MCP tools) MUST pass these gates (PR-5, §4.9.3).

### Expected Outcome
- Semantic writes reject non-whitelist categories.
- Episodic long-term writes use an explicit type-tag allowlist + five-factor scoring with per-type `θ_admit` (see Task 1b and `roadmap/phase-100040-appendix-admission-factors.md`).
- Category- or type-eligible candidates receive a five-factor score; below `θ_admit` are discarded with a log/telemetry event (not silent).
- `admit_preview` returns `{pass, admission_score, factors, rejection_reason?}` without writing (semantic **or** episodic candidates).
- Public/gated write path uses Phase 100030 repository only after both gates pass.
- Scoring consumes ranking-env weights from Phase 100010 (`w1…w5`, thresholds) and is deterministic given identical inputs/config (NFR-5).
- If a required factor backend is unavailable, the gated path returns a **structured error** (no admission decision, no write)—never a silent pass and never a logged “reject” that implies scoring completed.

### Parent Requirement
`requirement.md` (current) — §2.3–§2.4, PR-3, PR-5, §4.1, §4.2, §4.9.3 gating matrix, `admit_preview` / gated `store` semantics in §4.9.4.A, FR-1, FR-2, FR-21, NFR-5; risk note in §9 on weight drift (deployment-tunable, not hard-coded forever). Factor signal definitions: `roadmap/phase-100040-appendix-admission-factors.md`.

---

## 2. Scope Boundaries

### In Scope
- Closed semantic category whitelist: `task_spec` | `schema` | `tool_config` | `output_constraint` | `persona`.
- Episodic admission path: type-tag allowlist `triple` | `gist` | `task` | `failure` | `temporal`, then five-factor scoring with per-type `θ_admit` (not a forged semantic category).
- Five-factor scoring: future utility, factual confidence, semantic novelty, temporal recency, content-type prior (formulas in `roadmap/phase-100040-appendix-admission-factors.md`).
- Configurable weights and per-category / per-episodic-type `θ_admit` via ranking-env/config.
- Deterministic admit/reject with structured rejection; structured **error** when a factor backend is unavailable.
- Logged rejects (telemetry event sufficient for PR-5/PR-8 spirit).
- `admit_preview` tool semantics for both semantic and episodic candidates (in-process binding acceptable until MCP).
- Gated write wrapper used by any public long-term write entrypoint.

### Explicitly Out of Scope
- Span verification / extraction (slice 100050).
- Canonical consolidation, MemTree, parallel write orchestration (slices 100060–7).
- Novelty embedding pipeline maturity beyond what is needed for a defined novelty signal (MAY use a simple distance stub only if documented; MUST NOT fake pass/fail randomly — NFR-5).
- MCP transport packaging (slices 100160–17) beyond in-process tool handlers.
- Hygiene, erase, import gates (reuse this gate later; do not build those tools now).

### Must Not Change
- Phase 100030 snapshot/gist separation and repository primitives.
- Phase 100020 encryption and dual-backend behavior.
- Phase 100010 ranking-env as the source of weight vectors.
- Closed taxonomy: no ad hoc sixth semantic category.

### Scope Expansion Rule
If work outside this scope appears necessary:
1. Stop.
2. Document the reason.
3. Request clarification or approval.
4. Do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- Phase 100030 accepted: item repository + dual representations + ungated primitive boundary.
- Phase 100010 accepted: `ranking_env_*` supplies `w1…w5` and related knobs.
- Phase 100020 accepted: durable writes available.

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| Item repository | Create works when called | Phase 100030 tests |
| Ranking env | Weights readable | `ranking_env_get` |
| Telemetry/log sink | Can record reject events | Emit + assert in tests |
| Novelty signal | Defined deterministic function | Documented; tested |

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

### Task 1: Category Whitelist Gate (semantic)

#### Intent
Enforce FR-1 / PR-3 closed taxonomy at write time for semantic candidates.

#### Required Capability or Behavior
- Semantic candidates whose category ∉ five whitelist values are rejected regardless of score (§2.4).
- Semantic candidates MUST NOT be admitted by rewriting them as episodic types to dodge the whitelist.
- Rejection is structured and logged.

#### Architectural Responsibility
Admission / governance layer (first gate for semantic).

#### Required Changes
1. Category enum + gate function.
2. Integration with gated write wrapper.
3. Tests for each illegal category / missing category.

#### Implementation Constraints
- Adding categories requires schema-change review — not a config toggle (§4.1).
- Gate runs before scoring.

#### Expected Result
Illegal semantic categories never touch repository create.

### Task 1b: Episodic Admission Path

#### Intent
Satisfy §4.9.3: episodic long-term writes use an episodic admission path, not a forged semantic category.

#### Required Capability or Behavior
- Episodic type-tag allowlist: `triple` | `gist` | `task` | `failure` | `temporal`. Any other tag is rejected at the type gate (logged).
- After the type gate, run the **same five-factor scoring engine** as semantic (Task 2), with:
  - `type_prior` keyed by episodic type (see appendix),
  - `θ_admit` configurable **per episodic type** (defaults in appendix / ranking-env),
  - other factors (utility, confidence, novelty, recency) as in the appendix.
- Gated `store` for episodic MUST accept an episodic type tag (e.g. `episodic_type` or `category` discriminated union)—MUST NOT require a semantic category enum value.
- `admit_preview` MUST accept the same discriminator: semantic category **or** episodic type; return the same decision shape.
- Passing episodic admission still writes via Phase 100030 repository only after score ≥ θ.

#### Architectural Responsibility
Admission / governance layer (first gate for episodic + shared scorer).

#### Required Changes
1. Episodic type enum + type gate.
2. Per-type threshold map in ranking-env/config.
3. Preview and gated-write signatures that distinguish semantic vs episodic candidates.
4. Tests: illegal type rejected; legal type scored; no silent map onto `persona`/`task_spec`/etc.

#### Implementation Constraints
- Do not invent a sixth semantic category for episodic content.
- Do not skip five-factor scoring for episodic “because it is operational.”
- Span verification for snapshots remains slice 100050 (structural store OK after gates).

#### Expected Result
Episodic long-term writes are gated end-to-end with explicit rules and tests.

### Task 2: Five-Factor Admission Scoring

#### Intent
Implement §4.2 second gate with deployment-tunable weights for both semantic and episodic candidates.

#### Required Capability or Behavior
- Compute `admission_score = w1·utility + w2·confidence + w3·novelty + w4·recency + w5·type_prior` per `roadmap/phase-100040-appendix-admission-factors.md`.
- Compare to `θ_admit` (per semantic category or per episodic type).
- Below threshold → discard (no write) + log (FR-2).
- Deterministic given identical inputs and config (NFR-5).
- If a factor signal cannot be computed because a required backend is down, return **structured error** `{ok: false, code: factor_unavailable, …}`—**no write**, and **do not** emit an admission reject event that claims scoring finished.

#### Architectural Responsibility
Admission scoring engine.

#### Required Changes
1. Factor computation interfaces implementing the appendix formulas (Phase 100040 novelty MAY use the deterministic non-embedding proxy until slice 100110).
2. Weight load from ranking-env.
3. Threshold comparison + structured factor breakdown for previews.
4. Persist `admission_score` on accepted items (Phase 100030 field).

#### Implementation Constraints
- No randomness on the online path (NFR-5).
- Novelty embedding distance is the long-term signal; until dense index exists, use the appendix’s deterministic proxy and flag it in Known Limitations.
- Do not bypass gate for “system” actors unless requirements explicitly allow (they do not for long-term writes).

#### Expected Result
Unit tests with fixed weights/inputs produce stable scores and decisions for semantic and episodic fixtures.

### Task 3: `admit_preview` Without Write

#### Intent
Expose the same decision as gated write without mutation (FR-21 / §4.9.4.A).

#### Required Capability or Behavior
- `admit_preview(candidate)` where candidate is discriminated as semantic (`category` ∈ whitelist) or episodic (`episodic_type` ∈ type allowlist) → `{pass, admission_score, factors, rejection_reason?}` or structured `factor_unavailable` error.
- No durable write on preview (including on error).
- Preview decision matches what gated write would decide for the same inputs/config when scoring completes.

#### Architectural Responsibility
Tool/handler layer over admission engine.

#### Required Changes
1. Preview API/tool handler.
2. Parity tests: preview pass iff gated write would admit (for same frozen config/state).
3. Ensure preview does not create side effects in novelty stores (or document and test any read-only measurement carefully).

#### Implementation Constraints
- Preview MUST NOT commit snapshots/gists.
- Same category gate applies.

#### Expected Result
Parity tests green; DB row count unchanged on preview.

### Task 4: Gated Public Write Wrapper

#### Intent
Make repository create reachable from public long-term writes only after both gates.

#### Required Capability or Behavior
- Gated write runs category gate → score → on pass, Phase 100030 create with score fields; on fail, structured rejection + log.
- Align with §4.9.3 matrix for long-term writes.
- Wire coding-agent inventory so `store` (when exposed) uses this wrapper, not raw repository create.
- `admit_preview` shares the same engine.

#### Architectural Responsibility
Application service boundary between tools and repository.

#### Required Changes
1. `store`-shaped gated API (in-process).
2. Replace/guard any prior stub.
3. Tests: reject paths; accept path writes once; raw repository remains available only to gated path + tests.

#### Implementation Constraints
- Mutators like `invalidate` are N/A for this phase’s matrix row — do not build them here.
- Scratchpad must remain non-long-term if present as stub.

#### Expected Result
End-to-end gated write tests on a backend; rejects never persist items.

### Task 5: Reject Logging and Attribution

#### Intent
Satisfy PR-5 / PR-8 “nothing admitted without a decision” and attributable rejects.

#### Required Capability or Behavior
- Every reject emits a telemetry/log event including operation, category, scores/factors or gate reason, actor, timestamp (FR-15 spirit for store attempts).
- Accepted writes store admission_score on the item.

#### Architectural Responsibility
Telemetry alongside admission layer.

#### Required Changes
1. Event shape for admit/reject.
2. Assertions in tests that rejects are observable.
3. Ensure secrets in item previews are masked if logged.

#### Implementation Constraints
- Do not build full `audit_trail` tool (slice 100180); durable enough logging for rejects is enough.
- Do not log plaintext secrets from item content.

#### Expected Result
Reject fixtures produce inspectable log/events in tests.

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
- Concrete factor signal implementations, provided they are deterministic and documented.

The agent must request approval for:
- Architecture changes beyond the stated scope.
- Breaking API or data-contract changes.
- Security-sensitive policy decisions.
- Destructive data operations.
- Changes affecting downstream phase assumptions.
- Adding a sixth semantic category.

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
- Novelty or another factor cannot be made deterministic without unapproved infra.

---

## 7. Security Constraints

### Required Controls
- Gates cannot be disabled by profile/ranking patches (FR-32).
- Reject/accept logging masks secrets.
- Bank/actor required on gated writes.

### Sensitive Data Rules
- Never log raw credentials or DEKs in admission events.
- Never commit secrets.
- Use masked previews if item content appears in reject diagnostics.

### Security Acceptance Conditions
- Ranking_env_set cannot introduce `admission_bypass=true` (or equivalent) that skips gates.
- Rejected content is not persisted in long-term item tables.

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
| T100040-01 | Semantic category not in whitelist | Reject; no write; logged |
| T100040-02 | Whitelisted category, score ≥ θ | Admit; item persisted with admission_score |
| T100040-03 | Whitelisted category, score < θ | Reject; no write; logged |
| T100040-04 | `admit_preview` on T100040-02 inputs | `pass=true`; no write |
| T100040-05 | `admit_preview` on T100040-03 inputs | `pass=false` with factors; no write |
| T100040-06 | Preview vs gated write parity | Same decision for frozen config/state |
| T100040-07 | Identical inputs/config twice | Identical score and decision (NFR-5) |
| T100040-08 | Episodic type not in allowlist | Reject; no write; logged |
| T100040-09 | Episodic type legal, score ≥ θ | Admit via episodic path; no forged semantic category |
| T100040-10 | `admit_preview` episodic candidate | Same decision as gated episodic write; no write |
| T100040-11 | Novelty/factor backend unavailable | Structured `factor_unavailable` error; no write; no admit-reject event claiming a finished score |
| T100040-12 | Public `store` uses gated wrapper | Raw ungated create not exposed |
| T100040-13 | ranking_env weight change | Scores change deterministically; still gated |

### Negative Testing
Verify that:
- Invalid input is rejected.
- Unauthorized bank actions are blocked.
- Partial failures are handled safely.
- Duplicate/retry: double admit of same preview does not bypass scoring.
- Existing behavior remains intact.
- Failure does not leave orphan plaintext rows.

### Verification Rule
Implementation claims must be supported by actual test output,
inspection results, or other concrete evidence.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-100040-01 | FR-1 category gate enforced | T100040-01 | Test output |
| AC-100040-02 | FR-2 scoring + threshold + logged discard | T100040-02, T100040-03 | Test + log evidence |
| AC-100040-03 | `admit_preview` has no write side effects | T100040-04, T100040-05, T100040-10 | Row-count assertions |
| AC-100040-04 | Preview matches gated write decision | T100040-06, T100040-10 | Parity test |
| AC-100040-05 | Deterministic online admission (NFR-5) | T100040-07 | Repeated-run test |
| AC-100040-06 | Public long-term write path gated | T100040-12 | Wiring/guard test |
| AC-100040-07 | Weights read from ranking-env | T100040-13 | Config integration test |
| AC-100040-08 | Episodic admission path end to end (§4.9.3) | T100040-08–T100040-10 | Test output |
| AC-100040-09 | Factor backend down → structured error, not fake reject | T100040-11 | Test output |

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
- **Implementation summary:** `clio-admission` crate — category/type gates, five-factor scoring (`factors.rs` + appendix Jaccard/recency proxies), `admit_preview`, `gated_create` / `gated_create_raw`, `VecSink` reject/accept events with secret-masked previews; weights/`θ_admit` from `RankingEnv` (`clio-config` admission knobs).
- **Discovered/affected:** `clio-admission`, `clio-config` knobs, `clio-store` gated integration tests + `gate_boundary_tests`, coding inventory keeps Core `store`/`admit_preview` as stubs until MCP.
- **Changed-component summary:** Pure admission engine + in-process gated write wrapper; inventory stubs guarded (not replaced) per Phase 100010 FR-10 deferral.
- **Test execution:** `cargo test -p clio-admission` (31) + `clio-store` gated suites + `inventory_contract` (store remains Stub). Coverage: `make coverage` lines/functions gate.
- **Factor-signal documentation:** `roadmap/phase-100040-appendix-admission-factors.md`; novelty = Jaccard proxy; hosts inject `SignalSource` (no default store adapter in this crate).
- **Verification report:** AC-100040-01–AC-100040-09 covered by decision/gated/store tests (see §8 T100040-01–T100040-13). Adversarial doc review 2026-09-17; exit filled after remediation (split oversized `gated_tests`, Known Limitations honesty).
- **Known limitations:** see §12.

---

## 10. Failure Handling and Recovery

### Expected Failure Modes

| Failure | Detection | Recovery |
|---------|-----------|----------|
| Ranking-env missing weights | Validation error | Refuse admit with clear error; no write |
| Novelty/factor signal backend down | Factor error | Structured `factor_unavailable` error; no write; no finished-score reject event |
| Partial write after admit | Transaction failure | Roll back item; log failure |
| Taxonomy drift attempt | Review/stop | Require requirements change |

### Rollback Strategy
Revert gated-write wiring to stubs if needed; items already admitted remain unless explicitly discarded by later ops tools. Prefer feature-flag only if already present — do not invent a bypass flag that skips gates in production profiles.

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
| FR-1 / §4.1 / PR-3 | Task 1 | T100040-01 | AC-100040-01 |
| FR-2 / §4.2 / PR-5 | Task 2, 5 | T100040-02, T100040-03 | AC-100040-02 |
| §4.9.3 episodic path | Task 1b | T100040-08–T100040-10 | AC-100040-08 |
| FR-21 / admit_preview | Task 3 | T100040-04–T100040-06, T100040-10 | AC-100040-03, AC-100040-04 |
| NFR-5 | Task 2 | T100040-07, T100040-11 | AC-100040-05, AC-100040-09 |
| §4.9.3 gating matrix | Task 4 | T100040-12 | AC-100040-06 |
| FR-32 ranking weights | Task 2, 4 | T100040-13 | AC-100040-07 |
| §2.4 both gates | Tasks 1–4 | T100040-01–T100040-03 | AC-100040-01, AC-100040-02 |

Required chain:

```text
Requirement → Capability → Implementation → Test → Evidence
```

Every acceptance criterion must be traceable.

---

## 12. Phase Exit Contract

### Outputs Produced
- Category whitelist gate.
- Five-factor admission scoring with logging.
- `admit_preview` and gated public write wrapper.

### Guarantees Provided to Downstream Phases
After this phase is accepted:
- Every later long-term write tool can (and MUST) call the same gates.
- Import/hygiene/shared/canonical paths can reuse admission without forking policy.
- Extraction (slice 100050) feeds candidates into an existing admit decision.

### Known Limitations
- Novelty uses the appendix’s deterministic non-embedding proxy (Jaccard over neighbor texts) until dense index (slice 100110) supplies embedding distance; upgrade path is documented in the appendix.
- **No default store-backed `SignalSource`:** `clio-admission` is pure logic; callers (tests today; `clio-write` / MCP later) MUST inject neighbor/prior lookups. Empty neighbor lists are correct only when the bank sample is empty — otherwise novelty scores `1.0` and can inflate admission. `Store` still has no list/sample API for `neighbors_in_bank`; that adapter lands with write orchestration or index work, not as a silent empty stub.
- Reject telemetry uses injectable `EventSink` (`VecSink` for tests / single-process hosts). Full durable `audit_trail` is slice 100180.
- Coding-profile inventory still marks Core `store` / `admit_preview` as stubs (`not_implemented`); in-process `gated_create` / `admit_preview` are the Phase 100040 public write seam. MCP transports bind inventory in slices 100160–17 (**FR-10 / FR-20 not claimed here**).
- Span verification still required before snapshot truth claims (slice 100050).

### Downstream Prerequisites
- Slices 100050+ MUST NOT add ungated long-term write entrypoints.
- Slice 100050 locks write order: schema → span verify (if snapshot) → taxonomy/type → admission score. This phase’s gated wrapper MUST call span verify before scoring once slice 100050 lands (do not score unverifiable snapshots).
- Slice 100160 MCP `store` MUST call this gated wrapper.
- Downstream facades that call `gated_create` MUST supply a honest `SignalSource` (bank sample or explicit empty-bank), never an accidental always-empty source against a non-empty bank.

### Final Status
**PASS WITH DOCUMENTED LIMITATIONS** (2026-09-17)

### Verification Sign-Off

- Implementer: Open Code (Muse Spark 1.3 Contributor); exit remediation Cursor (Auto) (2026-09-17)
- Verifier: bug-review pipeline + `cargo test -p clio-admission` / store gated suites / `make coverage`
- Human Approver: approved (2026-09-17)
- Date: 2026-09-17

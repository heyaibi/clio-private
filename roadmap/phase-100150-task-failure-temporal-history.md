# Phase 100150: Task, Failure, and Temporal History

### Attribution
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | OpenCode CLI (Go . Deepseek V4.1 Flash High) | done |
| Adversary | r1 | OpenCode CLI (OpenRouter . Deepseek V4.1 Flash Max) | done |
| Remediator | r1 | OpenCode CLI (Go . Deepseek V4.1 Flash High) | done |
| Remedy Approver | r1 | OpenCode CLI (Together . GLM-5.3 Flash Max) | approved |
| Finalize | r1 | OpenCode CLI (Together . GLM-5.3 Flash High) | done |

**Index slice 100150 · **Effort:** `1×` · **Scope:** `roadmap/index.md` slice 100150 (authoritative)

### Vocabulary (read first) — zero shared moniker

| Term | Enum / form | Where it lives | Must not |
|------|-------------|----------------|----------|
| **`FailureRecord`** | `{task_id, attempt_n, what_failed, lesson, evidence_ref?}` | Episodic failure history (§4.8 / §7.3) | Be an ungated free-text log |
| **`lesson`** | length-capped natural language | Inside `FailureRecord` | Be stored as persona preference or belief confidence |
| **`task` history** | task definition / steps / status | `task_*` tools | Full chat-log replay |
| **`temporal_history` target** | discrete fact \| preference series \| belief trajectory | Read aggregator | Invent a fourth parallel logging DB |
| **Episodic type tag `failure` / `task` / `temporal`** | admission path | Phase 100040 episodic | Forge a sixth **semantic category** |
| **Verbal reinforcement** | store lesson, inject on retry | P7 / Reflexion-style | Weight fine-tuning / gradient RL |

## 1. Objective

### Goal
Implement **selective history** records and tools for **tasks**, **length-capped failure lessons**, and **temporal trajectories**—without full-log replay (P6, FR-8, FR-27). Surface prior failures when retrying the same or similar task (P7, FR-9).

### Expected Outcome
- `task_upsert` / `task_get` / `task_history` manage task records (gated episodic writes where required).
- `failure_record` stores structured `FailureRecord` with **capped** `lesson`; gated admission (§2.8).
- `failures_for_task` returns prior failures for same **or similar** task (FR-9)—similar is **required**, not optional.
- On retry of same/similar task, system **surfaces** prior failures via a **system path** (retrieve/compose domain `failure` and/or prepare-retry helper)—not docs-only.
- `temporal_history(target, as_of?, time_axis?)` returns trajectories from existing write-path data.
- `memtree_query` / `memtree_get` remain available (Phase 100070); this slice verifies FR-27 composition with history tools.
- Default retrieval path is **selective**, never full-log replay (FR-8).
- Evaluation fixture set for similar-task retitles (coding-agent rename patterns).

### Parent Requirement
`requirement.md` (current, v1.8+) — P6, P7, §2.1, §2.8, §4.8, §4.9.4.D, §7.3 FailureRecord shape, FR-8, FR-9 (same **and** similar), FR-27; MemTree Phase 100070; triples Phase 100080; EMA Phase 100090; beliefs Phase 100100; persona series Phase 100140.

### Design references (non-normative)
- Verbal reinforcement via episodic lessons: [Reflexion](https://arxiv.org/abs/2303.11366).
- Failure mode: confabulated / harmful reflections—mitigate with **admission**, **length caps**, **task tagging**, and **bounded retrieve** ([Honest Lying](https://arxiv.org/html/2605.29463v2)); do not treat lessons as exempt from gates (§2.8).
- Prefer structured `what_failed` + short `lesson` over unbounded critique buffers (token-cost / contradiction risks in production Reflexion deployments).

---

## 2. Scope Boundaries

### In Scope
- Task record model + `task_upsert`, `task_get`, `task_history`.
- `FailureRecord` model + `failure_record`, `failures_for_task`.
- Lesson max length config (tokens or chars—document; enforce hard cap).
- Similarity rule for “same or similar task”: exact `task_id` **and** definition similarity (lexical and/or embedding threshold—defaults documented). **Exact-only is not an exit waiver** (requirement v1.8 / FR-9).
- Retry surfacing path for FR-9 as a **system** mechanism (retrieve/compose and/or prepare-retry helper) with automated tests.
- Similar-task **evaluation fixture set**: ≥5 coding-agent retitle pairs (same definition, different `task_id`) that MUST surface prior failures.
- `temporal_history` aggregator over existing stores.
- Domain filters already on retrieve (`task`, `failure`, `temporal`) return these records correctly.
- Gates: `failure_record` and `task_upsert` per §4.9.3 long-term writes (episodic admission path).

### Explicitly Out of Scope
- Full conversation transcript warehouse / replay API.
- MCP transports (slice 100160–17).
- Hygiene cleanup UX (slice 100210).
- Offline RL / weight updates.
- Replacing MemTree (owned by Phase 100070)—only consume it.
- Reimplementing bi-temporal or EMA or belief history storage.
- Persona document tools (Phase 100140)—only read preference series via `temporal_history`.

### Must Not Change
- FR-8: no default full-log replay.
- §2.8: failures are gated episodic memories, not exempt logs.
- Phase 100100: belief history remains append-only; temporal_history is a reader.
- Phase 100140: do not inject failure lessons into always-on persona channel.
- Snapshot vs gist authority (PR-4).

### Scope Expansion Rule
If work outside this scope appears necessary:
1. Stop.
2. Document the reason.
3. Request clarification or approval.
4. Do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- Phase 100070 accepted: MemTree query/get; episodic structure.
- Phase 100040 accepted: episodic admission for `task` / `failure` / `temporal` tags.
- Phase 100080 accepted: triple history for discrete temporal_history.
- Phase 100090/100140 accepted: preference series readable.
- Phase 100100 accepted: `belief_history` data available.
- Phase 100120 accepted: domains include `task` / `failure` / `temporal`.

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| Episodic admit | task/failure writes gated | Phase 100040 |
| MemTree | Query by time/task | Phase 100070 |
| Triple as_of | Discrete trajectories | Phase 100080 |
| Continuous series | Preference trends | Phase 100090/100140 |
| Belief history | Confidence trajectory | Phase 100100 |
| Retrieve domains | Filters exist | Phase 100120 |

---

## 4. Existing-System Discovery

The agent MUST inspect the existing system before deciding
where or how to implement the changes.

### Required Discovery
- Existing stubs for `task_*` / `failure_*` / `temporal_history` in tool catalog.
- How episodic type tags map to storage.
- Whether task records are MemTree leaves or separate keyed rows—prefer one clear model.
- Lesson cap config location.
- How compose/retrieve can surface failures on retry without forcing full replay.

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

### Task 1: Task History Records

#### Intent
Selective task memory without transcript replay (FR-8 / FR-27).

#### Required Capability or Behavior
- `task_upsert(task_id, definition?, steps?, status?, evidence_ref?)` gated episodic write.
- `task_get(task_id)` returns record + optional summarized ancestor when MemTree linked.
- `task_history(task_id, limit?)` prior attempts/steps, newest-first, hard `limit`.
- No API returns “entire bank chat log.”

#### Architectural Responsibility
Task history repository + tools.

#### Required Changes
1. Storage model both backends.
2. Tool handlers + contract tests.
3. Link to MemTree when task_id indexing exists (Phase 100070).

#### Implementation Constraints
- Episodic type `task`, not semantic category invention.
- Bank isolation.

#### Expected Result
Upsert → get → history limit=1 returns latest step only.

### Task 2: Failure Records + Caps

#### Intent
P7 structured lessons with governance (§2.8).

#### Required Capability or Behavior
- `failure_record(...)` writes `FailureRecord`; **reject or truncate** `lesson` over cap (prefer reject with structured error if over hard max; MAY truncate with warning—pick one, test it).
- Must pass episodic admission; logged rejects on fail.
- Persist `attempt_n`, `what_failed`, `evidence_ref`.
- Encrypt content payloads via DEK path.

#### Architectural Responsibility
Failure store + gated write.

#### Required Changes
1. Schema + cap config.
2. Admission integration.
3. Tests: oversize lesson handled; admit reject path.

#### Implementation Constraints
- Not persona; not belief_observe.
- Not compliance erase.

#### Expected Result
Fixture failure readable by id/task; oversize lesson does not store unbounded text.

### Task 3: `failures_for_task` + Retry Surfacing (FR-9)

#### Intent
Surface prior failures on repeated attempts.

#### Required Capability or Behavior
- `failures_for_task(task_id_or_query, limit?)` returns ranked/recent failures.
- Exact `task_id` match required for primary path.
- **Similar path required for exit:** when `task_id_or_query` is a new id or free-text query, match prior tasks whose `definition` meets configured lexical **and/or** embedding similarity threshold; return their failures.
- Surfacing: retrieve/compose when domain includes `failure` **and/or** a `prepare_retry(task_id)`-style helper—**must** have automated tests proving failures appear on second attempt **including retitled task_id**.
- Ship evaluation fixtures (≥5 retitle pairs) as regression assets.

#### Architectural Responsibility
Failure query + retrieve/compose integration.

#### Required Changes
1. Query API with exact + similar matching.
2. End-to-end retry fixture (same id) + retitle fixture (similar).
3. Document default thresholds in config.
4. Metrics: failures returned count (PII-safe).

#### Implementation Constraints
- Do not dump all bank failures.
- Do not inject into persona channel.
- Do not claim PASS WITH LIMITATIONS for missing similar path.

#### Expected Result
Attempt 2 with renamed `task_id` but same definition still surfaces attempt 1 lesson.

### Task 4: `temporal_history` Aggregator

#### Intent
One read tool for trajectories across existing stores (§4.8 temporal).

#### Required Capability or Behavior
- `temporal_history(target, as_of?, time_axis?)` resolves `target` to:
  - discrete fact / triple identity → Phase 100080 history
  - preference key → Phase 100090/100140 series
  - belief id/proposition → Phase 100100 history
- Structured error if target type unknown.
- Does not copy data into a new “temporal log” table as SoT (MAY materialize cache with invalidate-on-write later—not required).

#### Architectural Responsibility
History read façade.

#### Required Changes
1. Dispatcher by target kind.
2. Contract tests per source.
3. NFR-4 point-in-time where axes apply.

#### Implementation Constraints
- Read-only regarding belief append semantics.
- Do not name this `audit_trail` (slice 100180).

#### Expected Result
Three fixtures (triple, preference, belief) each return non-empty trajectories.

### Task 5: Retrieve Domain Wiring + No-Replay Guard

#### Intent
Domains `task` / `failure` / `temporal` return selective slices (FR-8).

#### Required Capability or Behavior
- Hybrid retrieve with those domains returns history records, not entire episode dumps.
- Default limits applied.
- Regression: compose budget still holds when failures included.

#### Architectural Responsibility
Retrieve domain adapters.

#### Required Changes
1. Index or filter hooks for task/failure items.
2. Tests for domain isolation.
3. Explicit assertion that “list all messages” API does not exist.

#### Implementation Constraints
- Storage growth ≠ injection growth (PR-1).

#### Expected Result
Domain=`failure` retrieve returns only failure-typed hits.

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
- Add an ungated failure log bypassing admission.

### Agent Decision Boundary
The agent may decide:
- Concrete file/module/class placement.
- Exact vs similar matching algorithm details (must meet FR-9 thresholds).
- Lesson over-cap: reject vs truncate (document).
- Test organization.
- Non-breaking implementation details.

The agent must request approval for:
- Architecture changes beyond the stated scope.
- Breaking API or data-contract changes.
- Security-sensitive policy decisions.
- Destructive data operations.
- Changes affecting downstream phase assumptions.
- Building a full transcript warehouse.
- Waiving similar-task matching (forbidden without amending FR-9).

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
- Bank isolation on task/failure reads/writes.
- Admission gates on long-term history writes.
- Lesson length cap (abuse / token bomb).
- DEK encryption for lesson / what_failed / definitions.

### Sensitive Data Rules
- Never log full lessons in telemetry—ids + lengths.
- Never commit secrets.
- Mask secrets if lesson accidentally contains credentials (best-effort redaction on write optional; do not claim perfect).

### Security Acceptance Conditions
- Ungated failure write path does not exist.
- Cross-bank task history access rejected.

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
| T100150-01 | task_upsert → task_get | Record matches |
| T100150-02 | task_history limit | Caps returned steps |
| T100150-03 | failure_record admit pass | Stored FailureRecord |
| T100150-04 | lesson over cap | Reject or truncate per policy |
| T100150-05 | failure admit reject | No durable record |
| T100150-06 | failures_for_task | Returns prior for task_id |
| T100150-07 | Retry same task_id FR-9 | Prior lesson surfaced |
| T-07b | Retry retitled task_id (similar def) | Prior lesson surfaced |
| T100150-08 | temporal_history triple | Point-in-time trajectory |
| T100150-09 | temporal_history preference | EMA series / trend points |
| T100150-10 | temporal_history belief | Confidence trajectory |
| T100150-11 | retrieve domain=failure | Only failure hits |
| T100150-12 | No full-log API | Absent / rejected |
| T100150-13 | Failures not in persona channel | Compose persona unchanged |
| T100150-14 | Dual-backend sample | Parity on task_id |

### Negative Testing
Verify that:
- Invalid input is rejected.
- Unauthorized actions are blocked.
- Partial failures are handled safely.
- Duplicate failure attempts with same attempt_n behavior is defined (reject or idempotent—document).
- Existing MemTree/retrieve tests remain intact.
- Failure does not leave uncapped lessons stored.

### Verification Rule
Implementation claims must be supported by actual test output,
inspection results, or other concrete evidence.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence | Result |
|-------|----------------------|---------------------|-------------------|--------|
| AC-100150-01 | Task tools work (FR-27) | T100150-01–T100150-02 | Contract tests | PASS — `task_tests.rs` t01/t02 + `sqlite_history_tests`/`pg_history_tests` |
| AC-100150-02 | FailureRecord gated + capped (§2.8) | T100150-03–T100150-05 | Tests | PASS — `failure_tests.rs` t03/t04/t05 + duplicate/carrier guards |
| AC-100150-03 | failures_for_task same+similar (FR-9) | T100150-06–T-07b | E2E + fixture set | PASS — exact + similar, 6 retitle fixtures in `retry_tests.rs` |
| AC-100150-04 | temporal_history façade | T100150-08–T100150-10 | Contract tests | PASS — `temporal_tests.rs` triple/preference/belief + malformed targets; point-in-time predicate runs before LIMIT (`t08b`; `triple_history_at` in both backends) |
| AC-100150-05 | Selective retrieve (FR-8) | T100150-11–T100150-12 | Tests | PASS — `domain_tests.rs` t11/t12 plus `retrieve_isolation_tests.rs` t11 (hybrid retrieve `domain=failure` returns only failure hits) and t12 (source guard: no unbounded/full-log read API) |
| AC-100150-06 | Failures ≠ persona channel | T100150-13 | Regression | PASS — `domain_tests.rs` t13 plus `retrieve_isolation_tests.rs` t13 (compose persona section byte-identical with a failure present; failure only in the memory section) |
| AC-100150-07 | Dual-backend sample | T100150-14 | Test output | PASS — `postgres_parity_tests.rs` with `AM_PG_HISTORY_PARITY=1`; plus `pg_history_tests.rs` |

### Definition of Done
- [x] All in-scope behavior is implemented.
- [x] All acceptance criteria pass.
- [x] Required tests pass (`cargo test --locked --workspace` with `DATABASE_URL` set: all suites green).
- [x] No unauthorized changes were introduced (only new history code; no existing contracts changed).
- [x] Existing behavior remains intact (full workspace suite green, clippy `-D warnings` clean).
- [x] Security checks pass (bank-scoped reads/writes; DEK-sealed content; gated writes; capped lesson).
- [x] Documentation is updated where required (these sections; in-code module docs).
- [x] Evidence is collected (`make coverage` exit 0; per-file functions/lines ≥90%).
- [x] Verification is completed (`make check` exit 0).
- [x] Required approval is obtained (downstream pipeline step).

### Completion Evidence

**Implementation summary**
- New `clio-types` module `history.rs`: `TaskRecord`, `FailureRecord` (§7.3 shape), and `HistoryPolicy` (lesson cap + similarity threshold + bounded read limits).
- New `clio-store` contract `HistoryStore` (`history_store.rs`) with SQLite (`sqlite_history_read`/`sqlite_history_write`) and Postgres (`postgres_history_read`/`postgres_history_write`) implementations. Writes atomically insert a gated carrier `task`/`failure` episodic item plus one structured row, seal all content under the subject DEK, emit an audit event, and enqueue the carrier for indexing (mirrors `commit_triple_add`).
- New `sql/001_core.sql` tables `task_records` and `failure_records` (direct schema edit, no migration).
- New crate `clio-history` with tools: `task_upsert`/`task_get`/`task_history`, `failure_record`/`failures_for_task`, `prepare_retry`, and `temporal_history`. Wired into the workspace and re-exported from `clio-lib` (`clio_history as history`).
- Carrier items use `episodic_type = task|failure`, so the existing `SearchDomain::Task`/`Failure` filters select them without a new index table.

**Lesson cap policy**
- `HistoryPolicy::lesson_max_tokens` default `120` estimated tokens (characters/4). Over-cap lessons are **rejected** with a structured `out_of_range` error before any gate or write; nothing is stored. Enforced at the `failure_record` boundary; covered by T100150-04.

**FR-9 surfacing mechanism description**
- System path: `prepare_retry(task_id, limit?)` returns the latest task record plus prior failures. Exact `task_id` failures win; when none exist the task's own `definition` (or the raw argument for an unknown id) drives lexical similar-task matching. `failures_for_task(task_id_or_query, limit?)` does the same and is additionally reachable through the `failure` retrieve domain because carriers are indexed episodic `failure` items.
- Returns a `matched_task_ids` list and a PII-safe `HistoryEvent` with the returned count.

**Similar-task support level**
- Lexical Jaccard over lowercased alphanumeric tokens, default threshold `0.5` (`HistoryPolicy::similarity_threshold`), bounded by `list_tasks`/`list_failures` windows. Embedding similarity is **not** implemented (the requirement allows "lexical and/or embedding"). Thresholds are defined in `similar.rs` and `clio-types::history`, and surfaced/tunable through `clio-config::HistoryKnobs` (config paths `history.lesson_max_tokens`, `history.similarity_threshold`, `history.default_limit`, `history.max_limit`; `Runtime::history_policy()` builds the validated `HistoryPolicy`).

**Test execution output**
- `make check` exit `0` (fmt + clippy `-D warnings` + `cargo test --locked --workspace`).
- `cargo llvm-cov --workspace --locked` report (`--fail-under-lines 90 --fail-under-functions 90`) exit `0`: TOTAL lines `98.38%`, functions `98.72%`; all 137 reported files ≥90% functions and lines.
- Per-file (functions / lines): `clio-history/src/temporal.rs` `100.0%` / `97.62%`; `clio-store/src/history_store.rs` `100%` / `100%`; `clio-store/src/sqlite_history_read.rs` `100%` / `98.44%`; `clio-store/src/sqlite_history_triple.rs` `100%` / `97.2%`; `clio-store/src/sqlite_history_write.rs` `100%` / `97.9%`; `clio-store/src/postgres_history_read.rs` `100%` / `98.36%`; `clio-store/src/postgres_history_write.rs` `100%` / `96.3%`; `clio-config/src/history_knobs.rs` `100%` / `100%`; `clio-types/src/history.rs` `100%` / `96.97%`.

**Verification report**
- `cargo test --locked --workspace` (DATABASE_URL set): all test binaries pass, including the opt-in Postgres parity test with `AM_PG_HISTORY_PARITY=1`.
- Clippy `--workspace --all-targets --all-features -D warnings`: clean.

**Remediation (round r1)**
- F-01: point-in-time triple reads now filter on the chosen axis **inside** the store query before `LIMIT` (`HistoryStore::triple_history_at`, implemented for SQLite and Postgres), and select the newest `limit` versions at/under `as_of`; the client-side post-filter was removed. Regression `temporal_tests.rs::t08b` uses 3 versions with `limit=2` and `as_of` beyond the limit and asserts the version current at `as_of` survives.
- F-02: the mandated Responsibility/Owns/Does-not-own/Boundary header was added to all 12 previously bare test/support modules.
- F-03/F-04: `retrieve_isolation_tests.rs` adds an end-to-end hybrid-retrieve `domain=failure` test (only failure-typed hits), a compose test asserting the persona section is byte-identical when a failure exists (T100150-13), and a source guard that no unbounded/full-log read API exists (T100150-12).
- F-05: `sqlite_history_tests.rs::history_reads_are_bank_isolated` writes in bank A and asserts every read against bank B is empty/`None`.
- F-06: this section now reports the machine-measured per-file numbers (temporal.rs is `100.0%` functions / `97.62%` lines after covering `TemporalHistoryOutcome::is_empty`).
- F-07: `clio-config::HistoryKnobs` + config paths + `Runtime::history_policy()` expose the lesson cap, similarity threshold, and read limits.
- F-08: `failure_record` validates `attempt_n >= 1` before the admission gate, so no accept event is emitted for a never-written record.
- F-09: `what_failed` is deliberately uncapped and documented as such; a test proves it round-trips while the lesson cap still rejects over-cap lessons.

**Known limitations**
- Similar matching is lexical only (no embedding leg); defaults pass the retitle fixtures but may need deployment tuning for low-overlap rewordings.
- `prepare_retry` is the implemented system surfacing path (the phase permits "retrieve/compose domain failure **and/or** a prepare-retry helper"); `compose_context` itself was not modified, so the injected-pack budget is unchanged by construction.
- Lesson-cap and similarity defaults are defined in `clio-types::HistoryPolicy` and exposed through `clio-config::HistoryKnobs` (the `history.*` config paths) with `Runtime::history_policy()`; hosts still pass the resulting policy into the tools, so tuning takes effect where the tool args are constructed.
- Over-cap lessons are rejected, never truncated; duplicate `(bank, task_id, attempt_n)` and duplicate task version writes are rejected by unique constraints.
- No full-log/transcript replay API exists; all reads resolve a hard limit (`default 20`, `max 200`).

---

## 10. Failure Handling and Recovery

### Expected Failure Modes

| Failure | Detection | Recovery |
|---------|-----------|----------|
| Admit reject | Structured error | Agent revises lesson / content |
| Lesson over cap | Validation | Reject/truncate per policy |
| Unknown temporal target | Error | Caller fixes target |
| Similar-task false miss | Metric | Exact-id still works; tune later |

### Rollback Strategy
Revert code; history tables inert. No change to triple/belief SoT.

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
| FR-27 task_* | Task 1 | T100150-01–T100150-02 | AC-100150-01 |
| P7 / §2.8 / FR-27 | Task 2 | T100150-03–T100150-05 | AC-100150-02 |
| FR-9 | Task 3 | T100150-06–T100150-07 | AC-100150-03 |
| §4.8 temporal / FR-27 | Task 4 | T100150-08–T100150-10 | AC-100150-04 |
| FR-8 | Task 5 | T100150-11–T100150-12 | AC-100150-05 |
| §2.7 persona split | Task 3/5 | T100150-13 | AC-100150-06 |
| Dual backend | Tasks 1–2 | T100150-14 | AC-100150-07 |

Required chain:

```text
Requirement → Capability → Implementation → Test → Evidence
```

Every acceptance criterion must be traceable.

---

## 12. Phase Exit Contract

### Outputs Produced
- Task + failure history tools and stores.
- FR-9 retry surfacing path.
- `temporal_history` read façade.

### Guarantees Provided to Downstream Phases
After this phase is accepted:
- Slice 100160 can expose gated `failure_record` / `task_upsert` / related mutators over MCP.
- Slice 100170 can bind history reads with the same semantics.
- Slice 100180 audit can reuse write-path history (not a parallel log).

### Known Limitations
- Lesson quality not guaranteed—admission + caps only.
- Similarity thresholds need deployment tuning; defaults must still pass retitle fixtures.

### Downstream Prerequisites
- Slice 100160 MUST enforce gates inside MCP tools (no transport bypass).
- Slice 100180 MUST NOT duplicate FailureRecord into a second log SoT.

### Final Status
PASS WITH DOCUMENTED LIMITATIONS

### Verification Sign-Off
- Implementer: OpenCode CLI (Go . Deepseek V4.1 Flash High), r1
- Verifier: [pipeline Adversary/Remediator]
- Human Approver: [if required]
- Date: 2026-09-19

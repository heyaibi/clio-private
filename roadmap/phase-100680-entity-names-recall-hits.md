# Phase 100680: Entity Names on Recall Hits (`entities[]`)

### Attribution
Rounds below record plan authorship; implementation sign-off is in §12.
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | [TBD] | proposed |
| Adversary | r1 | [TBD] | [TBD] |
| Remediator | r1 | [TBD] | [TBD] |
| Remedy Approver | r1 | [TBD] | [TBD] |
| Finalize | r1 | [TBD] | [TBD] |

**Capability phase 100680** · **Effort:** ~2–3 days · **Status:** Plan ready · **Parent:** gap analysis `gaps/recall-result-fidelity-gap-analysis.md` §4.1, §6, §7, §8 decision 3+5, §10.2; requirement FR-4 / §4.4, PR-4, FR-20 / §4.9.2 item 2, §4.9.5.C (health surfaces), §4.12 and §7.4 (content boundary)

### Vocabulary (read first) — zero shared moniker

| Term | Meaning in this phase | Must not be confused with |
|------|------------------------|----------------------------|
| **entity name** | The span-verified `entity` string already stored in an item's snapshot | A named-entity table, an NER system, or SPO triple subject/object |
| **`entities[]`** | A per-hit array of entity-name strings on `ScoredHit` | A ranking signal; a truth claim; the export bundle's `entities` payload |
| **snapshot `entity`** | The default extractive field (`entity`, required string) verified as a contiguous NFC source substring | The `snapshot` field generally, which is arbitrary JSON |
| **coverage limit** | The documented set of hit kinds that legitimately return an empty `entities[]` | A bug or a partial result |

This phase exposes an already-verified snapshot value. It does not infer, link, or rank by entities.

---

## 1. Objective

### Goal
Expose a per-hit `entities[]` array sourced only from the item's span-verified snapshot `entity` value, with documented coverage limits and minimal trim-only canonicalization, while keeping entity names out of PII-safe surfaces (`warnings`, the `explanation` trace, telemetry, and health surfaces). The field is added to `ScoredHit`, not the frozen `RetrieveHit`, and is exposed identically on MCP, in-process, and CLI reads.

### Expected Outcome
- `ScoredHit` carries `entities: []` (an array of strings), empty when the item has no verified snapshot `entity`.
- The value is the span-verified snapshot `entity`, trimmed only; no inferred or linked entities are added.
- Coverage limits are documented: triple carriers, hub-distill, beliefs, snapshot-less items, and non-default field lists return empty.
- Entity names never appear in `warnings`, the `explanation`/`explain` trace, telemetry, or health surfaces.
- MCP, in-process, and CLI expose the same `entities` names and semantics.

### Parent Requirement
`requirement.md` — FR-4 / §4.4 (snapshot entities are span-verified); PR-4 / §4.4 (only the snapshot is authoritative; a retrieval-side link would be inferred and non-authoritative); FR-20 / §4.9.2 item 2 (binding identity); §4.9.5.C (health-surface PII) and §4.12/§7.4 (content boundary and redaction). Gap source: `gaps/recall-result-fidelity-gap-analysis.md` §4.1.

### Design References (source-verified at plan time)
- There is no named-entity table, index, link, or matching in the repository. `sql/001_core.sql:640-666` `entity_id`/`entity_kind` are sync-journal columns, not named entities.
- The `triples` table (`sql/001_core.sql:231-250`) has no `item_id` index; `crates/clio-store/src/store.rs:272,278,397` offers `get_triple`/`query_triples`/`list_triples` but no by-item query.
- The default snapshot fields are `entity` (required string), `amount`, `date` (`crates/clio-write/src/schema.rs:59-65`); `match_entity` verifies a contiguous NFC source substring (`crates/clio-write/src/verify_entity.rs:28`).
- `snapshot` is `Option<Value>` (`crates/clio-types/src/item.rs:266`); `MemoryItem` is `crates/clio-types/src/item.rs:242-281` and has no `context` field (relevant to the Phase 100601 track).
- Triple carriers store `{subject, predicate, object}` with no `entity` (`crates/clio-write/src/triple.rs:189-193`); SPO subject/object are `crates/clio-types/src/triple.rs:128,132`.
- The decrypted snapshot is in hand where hits are built: `finalize` iterates the fetched `MemoryItem` (`crates/clio-retrieve/src/finalize.rs:83-113`, item loop at `:94-112`), loaded at `crates/clio-retrieve/src/hybrid.rs:382-415`.
- Cross-binding propagation is automatic for the JSON payload: MCP/in-process/CLI serialize `RetrieveOutcome` wholesale (`read_retrieve.rs:90`, `surface.rs:207`, CLI dispatch `cli_read_core.rs:90-107`), so a new `ScoredHit.entities` field reaches all three by serde. The deliberate work is the boundary exclusion (below) and keeping entities out of the `explain` trace (`read_retrieve.rs:119-132`; Phase 100740).
- `ExportEntities` in `crates/clio-compliance/src/bundle.rs:131-163` is unrelated (bundle payload arrays).
- `crates/clio-types/src/item.rs` is 370 lines.

---

## 2. Scope Boundaries

### In Scope
- Adding `entities: Vec<String>` to `ScoredHit`.
- Populating it from the item's span-verified snapshot `entity` value with trim-only canonicalization.
- Documenting empty-coverage hit kinds.
- Excluding entity names from PII-safe/telemetry surfaces.
- Cross-binding exposure and parity tests.

### Explicitly Out of Scope
- Any named-entity store, index, NER, or entity linking.
- Triple-based enrichment (no by-item query and no `item_id` index exist).
- Entity-overlap matching or reason (Phase 100700).
- Entity-based ranking (any future ranking leg must fuse by rank and needs separate approval).
- Adding `entities` to the frozen `RetrieveHit`.
- Persisting a new entity field or changing extraction.
- Score floors / entity-inclusion controls (Phase 100780).

### Must Not Change
- The frozen `RetrieveHit` contract.
- Snapshot authority: `entities[]` is derived from the snapshot, never from the gist, and never a truth claim.
- Span-verification rules (FR-4): no entity value is exposed unless it was already verified at write time.
- The PII/content boundary: `entities[]` are content-derived names and MUST NOT enter `warnings`, `explanation`, telemetry, or health surfaces (health-surface PII rule §4.9.5.C; transparency/content boundary §4.12 and §7.4).
- Ranking, ordering, fusion, and budgets.
- Existing MCP tool names/schemas beyond the added `entities` array.

### Scope Expansion Rule
If work outside this scope appears necessary:
1. Stop.
2. Document the reason.
3. Request clarification or approval.
4. Do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- Phase 100620 accepted: `ScoredHit` carries the new display fields and the consolidated structure.
- The snapshot `entity` value is already span-verified at write time (FR-4).
- The PII/content boundary decision for entities is recorded (gap analysis §8 decision 5).
- Phases 100366/100368 (complete) own the CLI read path through which this field's JSON propagates (`command-ownership.md`).

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| `ScoredHit` | Carries display fields | Phase 100620 acceptance |
| Snapshot `entity` | Verified and stored for default-field writes | `schema.rs`/`verify_entity.rs` inspection |
| Fetched item at finalize | `MemoryItem` with decrypted snapshot available | `finalize.rs:94-112` inspection |
| Bound surfaces | A defined boundary list (`warnings`, trace, telemetry, health) | Requirement §4.9.5.C (health PII), §4.12/§7.4 (content); code inspection |
| Bindings | MCP/in-process/CLI projections | Conformance/CLI tests |

---

## 4. Existing-System Discovery

The agent MUST re-verify the following before editing; the facts below were confirmed at plan time.

### Required Discovery
- Confirm where the fetched `MemoryItem` snapshot is available during hit construction.
- Confirm the exact default-field and snapshot shapes across write paths (default fields, triples, hub-distill, beliefs, non-default field lists).
- Confirm `match_entity` verification and that no unverified `entity` can be stored.
- Enumerate every surface that must not receive entity names (`warnings`, `explanation`/`explain`, telemetry, health) and confirm none derives from `ScoredHit` wholesale.
- Confirm the three binding projections and their tests.
- Confirm `item.rs` size against the 450-line limit.

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

### Current Repository Findings at Plan Time
- The snapshot is in hand in `finalize`; no new storage or fetch is required.
- Triple carriers and several other write paths have no `entity`, so empty `entities[]` is expected for them and must be documented.
- There is no by-item triple query and no `item_id` index, so triple enrichment is genuinely deferred.
- The `explain` trace is a separate hand-written projection (`crates/clio-mcp/src/read_retrieve.rs:118-150`), which is why entities must be deliberately excluded there and why Phase 100740 de-drifts it.
- `item.rs` is 370 lines.

### Repository Adaptation Rule
The agent must determine concrete implementation locations from the actual repository. The plan does not prescribe file paths or module names unless they are an externally required contract. The `entities` field name and its snapshot-only source are the contract for this phase.

---

## 5. Implementation Specification

### Task 1: Extract the Verified Entity from the Snapshot

#### Intent
Derive `entities[]` from the span-verified snapshot value without inventing new entity data.

#### Required Capability or Behavior
- When the item's snapshot has a string `entity` field, `entities` contains that value after trim-only canonicalization.
- When there is no snapshot, no `entity`, or a non-string `entity`, `entities` is empty.
- The value is never taken from the gist, never inferred, and never linked from triples.
- Only values already verified at write time are exposed.

#### Architectural Responsibility
`clio-retrieve` owns extraction of the snapshot value into the hit field. `clio-write` continues to own verification; this phase does not re-verify.

#### Required Changes
1. Add `entities` to the hit structure and populate it during hit construction.
2. Implement trim-only canonicalization and document the choice.
3. Define and document the empty-coverage cases.
4. Add unit tests for each write shape (default fields, triple carrier, hub-distill, belief, snapshot-less, non-default fields).

#### Implementation Constraints
- No new storage, index, or query.
- No NER or linking.
- Do not treat the entity as authoritative content beyond its existing verified snapshot status.
- Keep files ≤450 lines.

#### Expected Result
A hit whose snapshot has an `entity` exposes it in `entities[]`; every other hit exposes an empty array.

### Task 2: Expose `entities[]` Without Leaking Into PII-Safe Surfaces

#### Intent
Serialize the entity names only on the intended read surfaces, keeping them out of diagnostics and telemetry.

#### Required Capability or Behavior
- `entities[]` appears identically on MCP, in-process, and CLI JSON reads.
- Entity names do not appear in `warnings`, the `explanation`/`explain` trace, telemetry events, or health surfaces.
- Empty arrays serialize as `[]`, not omitted inconsistently across bindings.

#### Architectural Responsibility
`clio-retrieve` owns the value; each binding owns its projection and must not add the value to any disallowed surface.

#### Required Changes
1. Update MCP, in-process, and CLI hit projections together.
2. Audit and, if needed, explicitly exclude entities from `warnings`, the explain trace, telemetry, and health.
3. Add parity tests and a boundary test asserting entities are absent from the disallowed surfaces.
4. Update any conformance volatile mask or fixture.

#### Implementation Constraints
- Do not add entity names to any log, warning, or trace.
- Do not change the frozen contract.
- Keep files ≤450 lines.

#### Expected Result
All three bindings expose the same `entities`; no PII-safe surface contains an entity name.

### Implementation Freedom
The agent may choose the internal representation (for example a helper returning `Vec<String>`), the exact trim semantics, and test placement, provided the snapshot-only source, empty-coverage documentation, and boundary exclusion hold.

---

## 6. Agent Execution Rules

### Allowed Actions
- Modify `clio-retrieve` hit construction, the three binding projections, and tests.
- Add documented empty-coverage handling and boundary assertions.

### Forbidden Actions
- Add an entity store/index, NER, triple enrichment, or a by-item triple query.
- Add entity ranking or matching (Phase 100700).
- Put entities on `RetrieveHit` or into `warnings`/trace/telemetry/health.
- Add dependencies, delete tests, or claim completion without evidence.

### Agent Decision Boundary
The agent may decide canonicalization details and test organization. The agent must request approval for: adding triple enrichment, adding an entity index, placing entities on the frozen contract, or any ranking use.

### Mandatory Stop Conditions
Stop and report if: the snapshot is unavailable at hit construction; an unverified entity could be exposed; entities would have to enter a disallowed surface to satisfy a test; or correctness cannot be verified.

---

## 7. Security Constraints

### Required Controls
- Entity names are content-derived; they are subject to the same read authorization as the item content.
- Entity names MUST NOT enter `warnings`, the `explanation`/`explain` trace, telemetry, or health surfaces (health PII rule §4.9.5.C; content boundary §4.12/§7.4).
- Entities follow existing subject-erasure behavior because they are derived from the item snapshot; this phase adds no durable entity store that could survive erasure.
- Bank isolation unchanged.

### Sensitive Data Rules
- Never log entity names outside the authorized read payload.
- Never commit secrets.
- Reuse existing authorization and redaction.

### Security Acceptance Conditions
- A boundary test proves entities are absent from `warnings`, the explain trace, telemetry, and health.
- An erased/snapshot-less item yields an empty `entities[]`.

---

## 8. Test and Verification Strategy

### Required Tests
- [ ] Unit tests (snapshot with `entity`, empty string, non-string, no snapshot, triple carrier)
- [ ] Integration tests (entity reaches the finalized hit)
- [ ] Contract tests (binding parity; frozen contract unchanged; empty = `[]`)
- [ ] End-to-end tests (real CLI/MCP `recall` shows `entities`)
- [ ] Regression tests (existing suites; no entity in disallowed surfaces)
- [ ] Security tests (no entity name in warnings/trace/telemetry/health)
- [ ] Failure-mode tests (snapshot-less item; erased item)

### Required Test Scenarios

| Test ID | Scenario | Expected Result |
|---------|----------|-----------------|
| T100680-01 | Default-field write with snapshot `entity` | `entities: ["<verified value>"]` |
| T100680-02 | Empty-string or non-string `entity` | `entities: []` |
| T100680-03 | Triple carrier | `entities: []` |
| T100680-04 | Hub-distill / belief / snapshot-less / non-default fields | `entities: []` |
| T100680-05 | `entity` with surrounding whitespace | Trimmed value |
| T100680-06 | MCP, in-process, CLI for same store | Identical `entities` |
| T100680-07 | Warnings, explain trace, telemetry, health | No entity name present |
| T100680-08 | Erased/snapshot-less item | `entities: []`; no failure |
| T100680-09 | Workspace suite, coverage, clippy, fmt, size | Green; per-file ≥90%; files ≤450 lines |

### Negative Testing
Verify an unverified entity is never exposed, no entity leaks into a disallowed surface, and empty coverage is `[]` consistently.

### Verification Rule
Implementation claims must be supported by actual test output, inspection results, or other concrete evidence.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-100680-01 | `entities[]` sourced only from the verified snapshot `entity` | T100680-01, T100680-05 | Test output; source inspection |
| AC-100680-02 | Empty coverage documented and returns `[]` | T100680-02…T100680-04 | Test output; docs |
| AC-100680-03 | Identical `entities` across bindings | T100680-06 | Parity test output |
| AC-100680-04 | No entity in warnings/trace/telemetry/health | T100680-07 | Boundary test output |
| AC-100680-05 | Frozen contract and ranking unchanged | Regression tests | Test output |
| AC-100680-06 | No regression; size/coverage gates pass | T100680-09 | Workspace suite; coverage report; size check |

### Definition of Done
- [ ] All in-scope behavior is implemented.
- [ ] All acceptance criteria pass.
- [ ] Required tests pass.
- [ ] No unauthorized changes were introduced.
- [ ] Existing behavior remains intact.
- [ ] Security checks pass.
- [ ] Documentation is updated where required.
- [ ] Evidence is collected.
- [ ] Verification is completed.
- [ ] Required approval is obtained.

### Completion Evidence
- Implementation summary
- Changed-component summary
- Test execution output (all shapes and boundary surfaces)
- Coverage-field documentation
- Verification report
- Known limitations

---

## 10. Failure Handling and Recovery

### Expected Failure Modes

| Failure | Detection | Recovery |
|---------|-----------|----------|
| Unverified entity exposed | Unit test with bad snapshot | Stop; expose only verified values |
| Entity leaks into a diagnostic surface | Boundary test | Remove it; treat as a security failure |
| Binding divergence | Parity test | Fix the projection; do not ship partial |
| Snapshot unavailable at hit build | Integration test | Stop; report |
| File approaches 450 lines | Size check | Decompose |

### Rollback Strategy
Remove the `entities` field and projections; no storage changed, so rollback is behavior-preserving. Entity names remain only where they already were (the item snapshot).

### Partial Completion Policy
If only some bindings expose entities, or a boundary surface still contains them, do not claim completion.

---

## 11. Traceability

| Parent Requirement | Implementation Task | Verification | Acceptance Criterion |
|--------------------|---------------------|--------------|-----------------------|
| FR-4 / §4.4 (span-verified entities) | Task 1 | T100680-01, T100680-05 | AC-100680-01 |
| PR-4 / §4.4 (non-authoritative link) | Task 1, Task 2 | T100680-03, T100680-04 | AC-100680-02 |
| FR-20 / §4.9.2 item 2 (binding identity) | Task 2 | T100680-06 | AC-100680-03 |
| §4.9.5.C (health PII) / §4.12 + §7.4 (content boundary) | Task 2 | T100680-07 | AC-100680-04 |
| Regression / quality contract | All | T100680-09 | AC-100680-06 |

Required chain:

```text
Requirement → Capability → Implementation → Test → Evidence
```

---

## 12. Phase Exit Contract

### Outputs Produced
- A per-hit `entities[]` array sourced from the verified snapshot `entity`.
- Documented coverage limits and a PII-boundary test.

### Guarantees Provided to Downstream Phases
After this phase is accepted:
- Phase 100700 can match query text against the hit's entity names.
- Phase 100780 can add an entity-inclusion toggle if desired.
- No durable entity store exists that could complicate erasure.

### Known Limitations
- `entities[]` is empty for triple carriers, hub-distill, beliefs, snapshot-less items, and non-default field lists.
- No entity linking, canonical resolution, or deduplication beyond trim.
- Triple-linked enrichment is deferred (no by-item query and no `item_id` index).
- `entities` is on `ScoredHit`, not the frozen `RetrieveHit`.

### Downstream Prerequisites
- Phase 100700 may rely on `entities[]` being present (possibly empty) on every hit.

### Final Status
PASS | PASS WITH DOCUMENTED LIMITATIONS | BLOCKED | FAILED

### Verification Sign-Off
- Implementer: [TBD]
- Verifier: [TBD]
- Human Approver: [TBD, if required]
- Date: [TBD]

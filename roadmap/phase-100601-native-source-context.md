# Phase 100601: Native Source Context and Evidence Identity

### Attribution
Rounds below record plan authorship; implementation sign-off is in §12.
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | OpenCode (Space Bunny Free) | proposed |
| Adversary | r1 | [TBD] | [TBD] |
| Remediator | r1 | [TBD] | [TBD] |
| Remedy Approver | r1 | [TBD] | [TBD] |
| Finalize | r1 | [TBD] | [TBD] |

**Remediation/follow-up phase 100601** · **Effort:** ~5–7 days · **Status:** Plan ready · **Parent:** requirement.md v1.10 native context contract and provenance identity

### Vocabulary (read first) — zero shared moniker

| Term | Meaning in this phase | Must not be confused with |
|------|------------------------|----------------------------|
| **`context`** | Optional, bounded descriptive information about the source or situation surrounding a memory item | `compose_context`, a prompt window, a semantic category, or evidence for a factual claim |
| **`evidence_ref`** | Caller-facing stable provenance reference; aliases to the durable `source_ref` field | A free-form citation, a source-span haystack, or a truth-confidence score |
| **`source_ref`** | Durable provenance identifier stored on a memory item | `source_text`, which is the text searched by span verification |
| **`source_text`** | Evidence text used to verify structured snapshot spans | Descriptive `context` |
| **`compose_context`** | Bounded retrieval/injection pack assembled for a model turn | The per-item `context` field |

The native public field is named `context` for direct conceptual and migration compatibility. Its meaning is always source context. The existing `compose_context` tool keeps its current meaning and budget contract.

---

## 1. Objective

### Goal
Add a provider-neutral, first-class `context` field to Clio's long-term memory contract and establish `evidence_ref` as the general stable source-identity field. A caller must be able to retain both the human-meaningful setting of a memory and the external reference that identifies its source, without weakening the existing taxonomy, admission, fidelity, or privacy rules. Document-container (`doc_id`) semantics are out of scope and deferred to a later phase (see requirement §9).

### Expected Outcome
- The normative requirements define `context`, its limits, its lifecycle, and its distinction from category, provenance, source text, and retrieval composition.
- Core memory items can carry an optional context value through the store path and both persistence backends.
- `clio remember ... --context ...` and the equivalent MCP/tool inputs accept the same semantics; existing calls without context remain valid.
- `evidence_ref` can identify a memory item, conversation turn, tool call, or other external source, and is durably represented by `source_ref` per the precedence rule.
- Reads, inspection, audit, export/import, erasure, and schema validation do not silently discard the new field.
- Existing items and old bundles remain readable without a destructive migration.

### Product Rationale
A memory statement is often incomplete without the setting that gives it meaning. The same person, project, date, or decision can mean different things in a team chat, a support ticket, a career update, or a tool result. Native context preserves that setting at the point of capture instead of requiring every caller to rewrite the fact or remember it later.

The feature also gives Clio one provider-neutral vocabulary for external sources. `evidence_ref` can identify a memory item, a conversation turn, a tool call, or another source record. Keeping context and evidence reference separate gives Clio both human meaning and machine identity:

```text
content:       "Alice works at Google"
context:       "team chat"
evidence_ref:  "conversation:turn:turn-456"
```

Neither field changes the truth value of the statement. The snapshot remains authoritative, context remains descriptive, and the evidence reference remains provenance.

### Parent Requirement
Requirement v1.10: P1, P5, P12, P13; PR-1, PR-3, PR-5, PR-8, PR-9, PR-10; FR-1, FR-2, FR-4, FR-5, FR-14, FR-20, FR-21, FR-34, FR-35; NFR-5, NFR-6, NFR-7, NFR-9; §4.1, §4.4, §4.9.2, §4.9.4, §7.1, §7.2, §7.3, §7.4, and the glossary.

Requirement v1.10 now defines the native `context` and generalized `evidence_ref` contract. This phase implements and verifies that contract; implementation MUST NOT silently add a different public contract.

---

## 2. Scope Boundaries

### In Scope
- A normative definition of optional source `context`, including validation, size, preservation, and lifecycle behavior.
- A normative clarification that `evidence_ref` is the general provenance/source-identity field for turns, tool calls, and source records. Document-container (`doc_id`) semantics are explicitly out of scope; external document identifiers may be carried opaquely with no parity claim.
- Core `MemoryItem` and persistence support on SQLite and PostgreSQL, with backward-compatible nullable storage.
- Encryption and erasure treatment for context values that may contain personal data.
- `store`/`remember`/`admit`/batch input propagation, machine-readable schemas, CLI help, and direct read/inspect output.
- Round-trip serialization for the core item contract and compatibility with existing bundles and sync payloads.
- Tests for validation, encryption, provenance mapping, backward compatibility, and binding parity.

### Explicitly Out of Scope
- A Hindsight API client, provider adapter, remote pull, or Hindsight-specific migration job.
- Automatic Hindsight document upsert behavior.
- A new semantic category, episodic type, belief type, or update rule.
- Tags, arbitrary key/value metadata, or context-based filtering and ranking policy.
- Changing admission scoring, confidence semantics, span verification, or `compose_context` budgets.
- Live dual-write, remote observation consolidation, or provider-side asynchronous retention.
- Rewriting existing memories to invent context or provenance that was not supplied.

### Must Not Change
- The five semantic categories and episodic type whitelist.
- The fact/belief distinction and the rule that `source_type` is present only for beliefs.
- `source_text` as the only span-verification haystack; context must not satisfy FR-4 by itself.
- The meaning of `compose_context` as a bounded retrieval/injection operation.
- The non-authoritative status of gist text and the authority of structured snapshots.
- Existing source references, validity intervals, admission decisions, or item identities unless the caller explicitly supplies a new stable reference.
- Secret masking and per-subject encryption guarantees.

### Scope Expansion Rule
If work outside this scope appears necessary:
1. Stop.
2. Document the reason.
3. Request clarification or approval.
4. Do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- The core memory-item, store-path, schema, and persistence contracts have been accepted by their owning phases.
- The requirement v1.10 context/evidence contract is the parent contract for public schema changes.
- The existing CLI binding owner for `clio remember` has been consulted; this phase adds a flag to the existing command and does not create a new command.
- Existing encryption, source-reference, audit, and export/import behavior has been inspected on both supported backends.

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| Core memory item | Snapshot/gist, `source_ref`, epistemic fields, and DEK-backed content storage exist | Inspect item model and backend serializers |
| Store path | `store` and `admit_preview` share the same item construction and gate path | Existing store-path tests |
| Binding schemas | MCP tool schemas and CLI help derive from one contract | Schema/catalog inspection |
| Encryption/erase | Subject-scoped content encryption and dirty-path regeneration exist | Existing encryption/erase tests |
| Portability | JSON bundle validation and idempotent import contracts exist | Existing export/import tests |
| Backward compatibility | Old rows and old bundle versions are readable | Fixture round-trip test |

---

## 4. Existing-System Discovery

The agent MUST inspect the existing system before deciding where or how to implement the changes.

### Required Discovery
- Locate the canonical `MemoryItem` model and both backend serializers.
- Trace `store` input decoding, `source_ref`/`evidence_ref` mapping, admission, and direct reads.
- Inspect MCP schema definitions and the hand-written CLI parser/help for `remember`, `admit`, and `batch`.
- Identify where source text is used for span verification and prove that context cannot enter that path accidentally.
- Locate encryption boundaries, audit events, export/import serializers, sync payloads, and erase propagation.
- Identify tests that pin current fact/belief validation, category validation, and source-reference behavior.
- Confirm that no existing field already has the native `context` meaning.

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
- The core item model contains `source_ref` but no `context` field.
- The store tool exposes `evidence_ref` as a provenance alias and `source_text` as the snapshot span haystack.
- The current `store` schema has no `context` parameter; the CLI `remember` path has no context flag.
- `evidence_ref` currently maps into `source_ref`; it is not a document-upsert identity by itself.
- `source_type` is constrained to belief provenance values and must not be repurposed for context.
- The current CLI `remember` binding creates a gist-oriented item; this phase defines storage and contract behavior, while extraction and retrieval policy belong to Phase 100606.
- The existing provider-import seam is non-writing; no provider behavior is assumed by this phase.

### Assumptions Confirmed
- A nullable field is backward-compatible with existing rows and callers.
- A bounded string is sufficient for the first native context contract; arbitrary structured metadata is not required.
- Context must not be interpreted as a category or as authoritative evidence.
- `evidence_ref` is the correct general place to carry a stable external source identity.

### Assumptions Requiring Approval
- Requirement v1.10 sets a 4 KiB UTF-8 reference maximum with rejection rather than silent truncation; implementation may lower but not raise it without a reviewed revision.
- Whether context is included in lexical retrieval input in Phase 100606; the core phase must not decide dense embedding or automatic injection behavior accidentally.
- Exact namespaced syntax for provider evidence references; the phase must preserve an opaque stable value even if syntax is provider-specific.

### Repository Adaptation Rule
The agent must determine concrete implementation locations from the actual repository. The plan does not prescribe file paths, class names, module names, or directory structures unless they are explicitly part of the externally required contract.

---

## 5. Implementation Specification

### Task 1: Implement and Verify the Normative Context and Evidence Contract

#### Intent
Make the v1.10 context/evidence contract concrete in the implementation and verify that every public surface follows it.

#### Required Capability or Behavior
- Define `context` as optional, bounded, descriptive source context.
- State that context is not truth, category, epistemic kind, source type, source span, prompt budget, or retrieval filter.
- Define preservation, validation, encryption, export, audit, erasure, and compatibility behavior.
- Define `evidence_ref` as a stable provenance/source identifier that populates `source_ref` per the precedence rule and may identify an external item, turn, or tool call.
- State that document-container (`doc_id`) semantics are out of scope: no upsert, bulk-delete, or original-text contract is defined, and `evidence_ref` MUST NOT be presented as delivering them.
- Update the tool catalog, data-model schemas, glossary, and affected cross-references together.

#### Architectural Responsibility
Requirements and contract ownership. No runtime component may introduce a field that contradicts requirement v1.10.

#### Required Changes
1. Verify the v1.10 context definition across taxonomy/provenance sections without creating a new category.
2. Extend the store/item and related item schemas with the optional field.
3. Verify FR-20/NFR-7 binding parity for context and evidence references.
4. Verify P12/NFR-6 and §7.4 behavior for context in audit/export/erase.
5. Verify the glossary distinctions among context, evidence reference, source reference, source text, and compose context.
6. Record the maximum-size decision and the backward-compatibility rule.

#### Implementation Constraints
- Do not silently reinterpret existing “contextual memory” prose as a new field; define the new term explicitly.
- Do not weaken the closed category whitelist.
- Do not make context an admission factor until a separate reviewed requirement defines that behavior.
- Do not change the meaning of `source_type` or `epistemic_kind`.

#### Expected Result
A verified v1.10 contract that makes the public context/evidence behavior unambiguous and traceable to the implementation and tests in this phase.

### Task 2: Add Context to the Core Item and Persistence Contract

#### Intent
Persist context without losing existing data or weakening encryption and backend parity.

#### Required Capability or Behavior
- Add an optional context value to the canonical item representation.
- Store it in the subject-protected content boundary because arbitrary context can contain personal data.
- Keep old items valid with an absent/null context value.
- Preserve context through create, read, update/correction, and history paths according to the approved lifecycle.
- Ensure both SQLite and PostgreSQL expose identical behavior.

#### Architectural Responsibility
The domain item model and storage/encryption layer own durable representation; repository adapters own backend parity.

#### Required Changes
1. Add the field to the canonical item and read/serialization types.
2. Add nullable migration/schema handling with no destructive rewrite.
3. Extend encryption and decryption coverage for the new content field.
4. Extend update/correct/history behavior so context is not silently discarded.
5. Add round-trip and old-row compatibility fixtures.

#### Implementation Constraints
- No silent truncation.
- No plaintext persistence for arbitrary context.
- No change to snapshot/gist authority rules.
- No new category or metadata map.
- Backend behavior must not fork based on SQLite versus PostgreSQL.

#### Expected Result
A context-bearing item round-trips on both backends, while an old item without context remains readable and unchanged.

### Task 3: Expose Context and Evidence Reference Through Core Write Contracts

#### Intent
Allow callers to supply context and a stable evidence reference using the existing write surface.

#### Required Capability or Behavior
- `store` accepts optional `context` and retains the existing `evidence_ref` behavior.
- `clio remember` accepts `--context` and passes it unchanged to the core store call.
- `admit` and batch item parameters accept the same field where they wrap the generic store candidate.
- MCP schemas, CLI help, parser validation, and text/JSON output describe the same behavior.
- Context is not silently injected into the gist or snapshot.

#### Architectural Responsibility
The binding layer maps syntax to the core contract; the write engine and admission layer retain ownership of validation and writes.

#### Required Changes
1. Add the field to the machine-readable store/admit/batch schemas.
2. Add the CLI flag and usage text to the existing `remember`/`admit` binding owned by the CLI phases.
3. Validate type, UTF-8, emptiness, and the approved maximum before dispatch.
4. Preserve `evidence_ref` as the caller-facing alias for `source_ref`.
5. Add schema/CLI parity tests.

#### Implementation Constraints
- Do not add a `--doc-id` flag or any document-container behavior in this phase; `doc_id` is deferred to a later research phase (see requirement §9).
- Do not add a new top-level command or change command ownership.
- Do not make `--context` change category, confidence, or epistemic classification.
- Unknown or malformed context fails with the established usage/error shape.

#### Expected Result
A caller can write context through MCP and CLI, and the same serialized request produces the same stored context on both bindings.

### Task 4: Preserve Context in Direct Reads and Core Audit Views

#### Intent
Ensure a stored context is observable and attributable without treating it as authoritative content.

#### Required Capability or Behavior
- Direct item reads expose context as optional metadata.
- `inspect` and core audit views expose enough information to identify the context and its source reference according to the approved redaction policy.
- Context is not included in exact-value verification or fact/belief classification.
- Context changes are attributable through the existing audit path.

#### Architectural Responsibility
Read/audit projections own visibility; storage and admission remain unchanged.

#### Required Changes
1. Add context to direct read and inspect projections.
2. Add audit handling for create/update/correct operations that carry context.
3. Define masking/redaction for context in human-readable diagnostics.
4. Add regression tests proving gist-only truth rules remain intact.

#### Implementation Constraints
- Do not inject context into model-facing composition in this task.
- Do not expose secrets or raw sensitive context in errors or logs.
- Do not create a second audit system.

#### Expected Result
An operator can inspect where context came from and what changed without using context as proof of a fact.

### Task 5: Conformance and Regression Coverage

#### Intent
Prove that the new field is backward-compatible and consistent across supported bindings and backends.

#### Required Capability or Behavior
- Contract tests cover the exact context and evidence-reference shapes.
- Unit tests cover validation, null/empty behavior, preservation, and source-reference mapping.
- Integration tests cover SQLite/PostgreSQL round trips and encrypted reads.
- Regression tests cover existing calls with no context and all fact/belief validation rules.
- Compatibility tests cover old serialized items and old import bundles.

#### Architectural Responsibility
The owning crates’ test modules verify their own contracts; this task collects the cross-boundary evidence.

#### Required Changes
1. Add unit and contract tests at the appropriate ownership boundaries.
2. Add backend parity tests.
3. Add CLI/MCP schema parity tests.
4. Record test output and known compatibility limits in the phase evidence.

#### Implementation Constraints
- Do not delete or weaken existing tests.
- Do not use a process-global database or hidden state to make tests pass.
- Do not claim backend parity from SQLite-only evidence.

#### Expected Result
All acceptance tests pass, including old-data and no-context regression cases.

### Implementation Freedom
The agent may choose concrete file locations, internal field layout, migration mechanics, and test organization provided that:
- The public context/evidence contract is unchanged.
- Context remains separate from category, truth, source text, and compose context.
- Existing data remains readable.
- Encryption, audit, export, and erase obligations are met.
- All acceptance criteria pass.

---

## 6. Agent Execution Rules

### Allowed Actions
- Inspect the existing model, store path, schemas, CLI, encryption, audit, portability, and tests.
- Implement the v1.10 context/evidence contract and keep requirement references synchronized.
- Add the context field, evidence-reference clarification, schemas, bindings, persistence, and focused tests.
- Perform local refactoring required to keep the field within the owning domain boundary.

### Forbidden Actions
- Add a Hindsight client or provider adapter.
- Add a new category, tag system, or arbitrary metadata map.
- Change admission formulas, source-span verification, or retrieval composition budgets.
- Store arbitrary context as unprotected plaintext.
- Add a `doc_id` field or document-container behavior, or silently change existing source references.
- Delete tests, weaken security controls, or claim compatibility without old-data evidence.

### Agent Decision Boundary
The agent may decide:
- Internal storage layout and migration mechanics.
- Whether the public wire name is implemented through a compatibility alias internally.
- Test placement and local helper structure.

The agent must request approval for:
- A different context data type or maximum size.
- Any new category, tag/filter semantics, or retrieval behavior.
- A breaking schema/version change.
- Changes to encryption, erasure, or audit guarantees.
- Any provider-specific code.

### Mandatory Stop Conditions
Stop and report if:
- The requirement v1.10 contract is internally inconsistent with the implementation boundary.
- Existing item/schema versions cannot be made backward-compatible.
- Context would need to be stored outside the protected content boundary.
- A proposed change would make context authoritative or automatically injected.
- Correctness cannot be demonstrated on both supported backends.

---

## 7. Security Constraints

### Required Controls
- Authorization and bank isolation remain unchanged.
- Context is validated at every trust boundary and rejected when oversized or malformed.
- Arbitrary context is encrypted with the subject content boundary.
- Context is redacted or masked in logs, errors, dry-run samples, and audit human output according to the approved policy.
- Evidence references must not be treated as authorization tokens or secret credentials.

### Sensitive Data Rules
- Never log plaintext credentials.
- Never log raw context merely because it was supplied.
- Never use context as an instruction to an extractor, model, or tool.
- Never place secrets in evidence references.
- Use the repository's approved secret/configuration mechanisms for any operational credentials.

### Security Acceptance Conditions
- A context value containing a planted secret does not appear in diagnostics or plaintext metadata.
- An oversized or malformed context is rejected before persistence.
- Context is removed or made unreadable through the existing subject-erasure path.
- A context value cannot change authorization, category admission, or fact/belief validation.

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
| T100601-01 | Store a valid context and evidence reference | Item persists and both values round-trip |
| T100601-02 | Omit context | Existing behavior remains valid; context is absent |
| T100601-03 | Empty, invalid UTF-8, or oversized context | Request is rejected before write |
| T100601-04 | Store a fact with context | Fact remains fact; context does not add `source_type` |
| T100601-05 | Store a belief with context | Existing source-type and confidence rules remain enforced |
| T100601-06 | Snapshot with source text and context | Span verification uses source text, not context |
| T100601-07 | Old item/bundle without context | Read/import succeeds without data loss |
| T100601-08 | Context update/correction | New context is attributable and old behavior remains bounded |
| T100601-09 | Context containing secret-like text | Logs, errors, and samples redact or omit it |
| T100601-10 | SQLite/PostgreSQL parity | Both backends produce the same logical item contract |
| T100601-11 | MCP and CLI parity | Equivalent requests produce equivalent stored fields |
| T100601-12 | Subject erasure | Context follows existing protected-content erasure behavior |

### Negative Testing
Verify that:
- Invalid input is rejected.
- Unauthorized bank access is blocked.
- Context cannot bypass category, admission, or fact/belief rules.
- Duplicate evidence references do not silently rewrite unrelated items.
- Existing behavior remains intact for calls without context.
- Failure does not leave partially written context or audit state.

### Verification Rule
Implementation claims must be supported by actual test output, schema inspection, backend inspection, or other concrete evidence.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-100601-01 | Requirement v1.10 defines context separately from category, source text, evidence reference, and compose context | Requirement review | v1.10 review evidence |
| AC-100601-02 | Core store accepts optional bounded context and preserves it on read | T100601-01, T100601-03 | Test output and schema evidence |
| AC-100601-03 | Evidence reference remains a stable provenance alias and can identify an external document/item | T100601-01, contract inspection | Schema and mapping evidence |
| AC-100601-04 | Existing fact/belief and source-type rules are unchanged | T100601-04, T100601-05 | Regression output |
| AC-100601-05 | Old items and bundles remain readable | T100601-07 | Compatibility test output |
| AC-100601-06 | Context is protected from plaintext logging and unauthorized access | T100601-09, security inspection | Security test output |
| AC-100601-07 | SQLite and PostgreSQL expose the same logical context contract | T100601-10 | Backend parity output |
| AC-100601-08 | MCP and CLI bindings expose identical context/evidence semantics | T100601-11 | Contract/parity output |

### Definition of Done
- [ ] Requirement v1.10 contract verified.
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
- Requirement v1.10 context/evidence contract and consistency review.
- Domain/storage/binding change summary.
- Schema and CLI/MCP parity evidence.
- Backend round-trip and old-data compatibility output.
- Security/redaction and erasure evidence.
- Known limitations and deferred retrieval/provider behavior.

---

## 10. Failure Handling and Recovery

### Expected Failure Modes

| Failure | Detection | Recovery |
|---------|-----------|----------|
| Context exceeds the approved limit | Validation error before write | Reject with a bounded usage/domain error; do not truncate |
| Context contains invalid data | Schema/encoding validation | Reject before persistence; preserve existing item |
| Encryption or serialization misses context | Round-trip test or read mismatch | Fail the phase; do not mark migration complete |
| Evidence reference conflicts with existing identity | Identity/idempotency validation | Stop or require explicit overwrite policy; never silently merge |
| Backend behavior diverges | Parity test | Block acceptance until both backends satisfy one contract |
| Context leaks in diagnostics | Security test or inspection | Redact, remove unsafe output, rotate any exposed credential, and rerun |
| Existing data cannot be read | Compatibility test | Preserve old schema; roll back migration and revise plan |

### Rollback Strategy
Keep the new field nullable and avoid destructive backfills. If the phase fails, remove the new binding/schema exposure, leave old rows readable, and retain any encrypted data only under the existing erase/recovery rules. Do not attempt to reconstruct context that was never supplied.

### Partial Completion Policy
If only the schema or one backend is complete, do not claim phase completion. Record completed and incomplete work separately, identify the unsupported binding/backend, and do not expose a partial public contract as native support.

---

## 11. Traceability

| Parent Requirement | Implementation Task | Verification | Acceptance Criterion |
|--------------------|---------------------|--------------|-----------------------|
| P1 / PR-1 / PR-9 | Tasks 2–3 | T100601-01, T100601-10 | AC-100601-02, AC-100601-07 |
| P12 / PR-8 / NFR-6 | Tasks 2, 4 | T100601-08, T100601-09 | AC-100601-03, AC-100601-06 |
| P13 / FR-14 | Task 3 | T100601-04, T100601-05 | AC-100601-04 |
| §4.1 / PR-3 | Task 1 | Requirement review | AC-100601-01 |
| §4.4 / FR-4 | Task 2 and Task 3 | T100601-06 | AC-100601-02 |
| FR-20 / NFR-7 | Task 3 | T100601-11 | AC-100601-08 |
| §7.4 | Tasks 2 and 4 | T100601-09, T100601-12 | AC-100601-06 |
| Requirement v1.10 context/evidence contract | Task 1 | Requirement review | AC-100601-01 |

Required chain:

```text
Requirement → Capability → Implementation → Test → Evidence
```

Every acceptance criterion must be traceable.

---

## 12. Phase Exit Contract

### Outputs Produced
- Approved context and evidence-reference contract.
- Native optional context support in the core item/store path.
- Backward-compatible backend and binding behavior.
- Direct-read, audit, and portability integration points ready for Phase 100606.

### Guarantees Provided to Downstream Phases
After this phase is accepted:
- A context value can be supplied, validated, stored, read, and audited without becoming a category or truth source.
- `evidence_ref` is the canonical stable provenance field and can carry an external document reference.
- Existing items remain compatible and all bindings share one contract.
- Phase 100606 can propagate context through extraction, retrieval, and portability without inventing a new data model.

### Known Limitations
- No provider adapter or Hindsight API behavior.
- No context-based filtering, ranking, or automatic model injection.
- Exact dense retrieval treatment is deferred to Phase 100606.
- Exact namespaced-reference syntax remains an implementation decision; the stable identity semantics are fixed by v1.10.

### Downstream Prerequisites
- Phase 100606 may rely on the approved context field, evidence-reference mapping, encryption behavior, and backward-compatible item contract.
- Migration tooling may carry external document identifiers opaquely in `evidence_ref` with no container-parity claim; a dedicated later phase owns `doc_id` research and design.

### Final Status
PASS | PASS WITH DOCUMENTED LIMITATIONS | BLOCKED | FAILED

### Verification Sign-Off
- Implementer: [TBD]
- Verifier: [TBD]
- Human Approver: required for the public requirement/schema change
- Date: [TBD]

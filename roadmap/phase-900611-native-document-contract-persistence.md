# Phase 900611: Native Document Contract and Persistence

### Attribution
Rounds below record plan authorship; implementation sign-off is in §12.
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | OpenCode (Space Bunny Free) | proposed |
| Adversary | r1 | [TBD] | [TBD] |
| Remediator | r1 | [TBD] | [TBD] |
| Remedy Approver | r1 | [TBD] | [TBD] |
| Finalize | r1 | [TBD] | [TBD] |

**Conditional follow-up phase 900611** · **Effort:** ~3–4 days · **Status:** Conditional — approval required · **Parent:** requirement.md §9 document-container gate and an approved native-preservation contract

### Approval Gate

This phase is planning-only until an approval record satisfies all conditions:

1. Requirement §9 is satisfied by a completed migration rehearsal or an explicit owner amendment that authorizes a Clio-native document track.
2. The owner selects **native preservation** and approves the document contract decisions that are not fixed by requirement v1.10.
3. The owner records the §9 “bulk operations” interpretation: one-document cascade deletion either satisfies the phrase, or a separate multi-document contract and phase are required.
4. The owner approves the event-time, document-level context propagation, and metadata split decisions in §3.

A destructive provider-parity track does not satisfy this gate. It requires a separate requirement amendment and separate phase.

The §9 phrase “bulk operations” is ambiguous. The Hindsight evidence establishes one-document cascade deletion, which Hindsight calls “delete in bulk,” and does not establish a multi-document delete request. This plan implements one-document lifecycle only; it does not expose a multi-document API. The approval record must state the interpretation rather than leaving it implicit.

### Vocabulary (read first) — zero shared moniker

| Term | Meaning in this phase | Must not be confused with |
|------|------------------------|----------------------------|
| **`doc_id`** | Caller-supplied, non-empty UTF-8 document-container key, unique within one bank | `evidence_ref`, `source_ref`, `context`, or a memory-item ID |
| **document container** | Bank-scoped lifecycle aggregate for retained source, revisions, chunks, metadata, and derivation links | A sixth semantic category, episodic type, persona document, or truth claim |
| **source revision** | Immutable retained version of one document's supplied source text | A mutable “current text” field or a memory-item correction |
| **document chunk** | Persisted source span used for extraction and later context expansion | The transient extraction-only `chunk_id` values that exist today |
| **derivation link** | Auditable relationship from a derived record to a source revision/chunk or existing source-record lineage | Proof that every consolidated record has a direct document reference |
| **repository deletion** | Document-container removal under an explicitly approved, non-compliance lifecycle policy | `discard`, invalidation, subject erasure, or destructive replacement |
| **native replacement** | Create a new immutable source revision, preserve old revisions and derived records, and retire stale active projections under existing temporal rules | Hindsight's destructive delete-then-reextract behavior |

`doc_id` is not an authorization token. The effective identity key is `(bank_id, doc_id)`. Two banks may contain the same `doc_id` without referring to the same document.

### Hindsight Feature Mapping for the Native Track

| Hindsight behavior | Clio treatment in these phases | Phase home |
|--------------------|--------------------------------|------------|
| Document get/list with ID substring, time filters, pagination, and metadata | Include and adapt to Clio bank/subject authorization; do not add unapproved tag filters. Hindsight tag visibility scoping is not equivalent to Clio authorization and is not claimed. | 900611, 900620 |
| Retain-time document metadata | Include as bounded document metadata. Split it from item-level metadata. Define whether it is retained/returned only or also passed to extraction; if passed, treat it as untrusted data under the same rules as `context`. | 900611, 900615, 900625 |
| Retain-time item metadata returned with memories | Defer unless separately approved; do not claim Hindsight item-metadata parity in native version one. | Deferred |
| Retain-time event `timestamp` | Include an event-time field with explicit default and “unset” behavior, mapped to extraction temporal anchoring and Clio valid/transaction time. | 900611, 900615 |
| Retain-time `context` | Clio `context` remains bounded descriptive metadata and MUST NOT be a model instruction. Define document-level context propagation to derived items without copying Hindsight's direct prompt-injection behavior. | 900611, 900615 |
| Document tags and retagging effects | Defer unless Clio adopts a separate generic tag contract; no Hindsight re-consolidation side effects are copied. Tag-based visibility scoping remains a future contract; bank/subject authorization is the native boundary. | Deferred |
| `entities` / `resolve_entities` | Defer; existing extraction behavior remains authoritative. | Deferred |
| Batch ingestion and async `operation_id` | Use existing `batch` and durable document attempt/idempotency identity; add no new async provider API. | 900615, 900620 |
| Document response fact-type counts (`world`, `experience`, `observation`) | Do not expose provider fact-type names; map to Clio taxonomy or defer counts with no parity claim. | 900611, 900620 |
| Observation scopes | Preserve direct/indirect lineage through Clio consolidation; do not reproduce custom Hindsight scope modes | 900611, 900615 |
| Stored-document reprocess/recovery | Include with durable attempts, mission/policy versioning, and curation preservation | 900615, 900620 |
| File upload and one-document-per-file ingestion | Out of scope; Clio does not own upload/parsing/OCR/transcription/remote file storage | Out of scope |
| Inline attachments and attachment URLs | Out of scope; native documents carry caller-supplied text and chunk references only | Out of scope |
| Delta append / unchanged-chunk reuse | Optional implementation optimization with identical observable semantics | 900615 |
| Source-retention-disabled append | Reject the configuration/operation; native source retention is mandatory | 900611, 900615 |
| Lost append race | Return a retryable conflict; never overwrite unseen source | 900611, 900615, 900620 |
| Destructive replacement | Exclude from native phases; separate requirement and phase only if approved | Deferred optional track |
| Hindsight provider adapter/remote ingestion | Exclude from native phases | Deferred separate provider work |

---

## 1. Objective

### Goal
After the approval gate, define and implement Clio's first-class native document aggregate and dual-backend repository contract. The phase must persist immutable source revisions, source chunks, bounded document metadata, and auditable links to independently identified derived records while preserving Clio's history and compliance boundaries.

### Expected Outcome
- The normative requirements define the approved native document identity, update, source-retention, zero-memory, and repository-deletion behavior before public runtime exposure.
- SQLite and PostgreSQL share one logical contract for creating, getting, listing, appending, replacing, inspecting chunks, and repository-removing document containers.
- Source revisions and chunks are encrypted under the applicable subject boundary and are never stored as plaintext content.
- Replace creates a new revision and preserves prior revisions and derivation links; it never implements Hindsight's destructive replacement.
- Append and replace use optimistic revision checks so a concurrent writer receives a retryable conflict instead of losing unseen content.
- Existing items and `evidence_ref` values remain unchanged; the migration does not invent document ownership for historical data.
- A downstream write/retrieval phase receives a stable repository contract without requiring a public tool name yet.

### Parent Requirement
Conditional parent contract: requirement.md §0 dual-backend support; PR-3, PR-5, PR-6, PR-8, PR-10; §4.1–§4.4; §4.9.2; §7.4; FR-4, FR-15, FR-19, FR-23, FR-34, FR-35; NFR-6, NFR-7; §9 document-container open issue; §10 glossary.

The current requirement v1.10 does not normatively define a document container or document tools. The implementation cannot start until the approval gate produces a reviewed requirement amendment or another owner-approved normative contract.

---

## 2. Scope Boundaries

### In Scope
- A reviewed native document contract covering identity, revisioning, source retention, chunking, document and item metadata, event time, document-level context propagation, derivation links, zero-derived-record behavior, concurrency, and repository deletion.
- Additive portable schema and migration support for documents, immutable source revisions, persisted chunks, event time, and derivation references.
- A backend-agnostic repository contract implemented by SQLite and PostgreSQL.
- Internal create/get/list/append/replace/chunk-list/repository-delete primitives.
- Subject-bound encryption for source text, chunks, event time, and sensitive document or item metadata.
- Stable operation identity, expected-revision checks, and recoverable processing state for later extraction/public-tool use.
- Legacy-database compatibility without assigning documents to existing items.
- Focused unit, contract, integration, migration, concurrency, security, and failure-recovery tests.

### Explicitly Out of Scope
- Public MCP tools, CLI commands, schemas, help text, or command-ownership entries.
- Extraction, admission, publication, recall projection, or stale-index retirement; these belong to Phase 900615.
- Audit/inspect UX, export/import, compliance-erasure orchestration, or sync; these belong to Phase 900625.
- Provider-faithful destructive replacement.
- A Hindsight client or `import_provider` adapter.
- File upload, parsing, conversion, OCR, transcription, remote file storage, attachment binaries, or attachment URLs.
- A configurable source-retention-disabled mode.
- Document tag filtering, tag-based visibility scoping, Hindsight observation-scope modes, or tag-triggered re-consolidation.
- Hindsight `entities` / `resolve_entities` controls or provider fact-type names (`world`, `experience`, `observation`).
- Item-level arbitrary metadata unless the approved split contract explicitly includes it.
- A document semantic category or new episodic type.
- Backfilling existing memories into documents from `source_ref` or `evidence_ref` text.

### Must Not Change
- `evidence_ref` remains provenance only and must not become the document key.
- `context` remains descriptive metadata and is not a document identifier.
- PR-6: ordinary document replacement does not delete prior source revisions or derived-record history.
- PR-5: a document container must not let extracted records bypass category or admission controls.
- PR-8: every later public mutation must remain attributable to bank, actor, operation, and revision.
- §7.4: document source and chunks use the subject encryption boundary; repository deletion is not compliance erasure.
- Existing item, triple, belief, persona, task, failure, graph, and MemTree identities remain stable.
- Backend choice must not fork logical behavior.

### Scope Expansion Rule
If work outside this scope appears necessary:
1. Stop.
2. Document the reason.
3. Request clarification or approval.
4. Do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- A written §9 approval basis exists: migration-rehearsal evidence or an explicit owner amendment.
- The owner has recorded whether one-document cascade deletion satisfies §9's “bulk operations” wording; this track covers one-document repository deletion unless a separate multi-document contract is approved.
- The selected policy is native preservation, not provider-faithful destructive replacement.
- The owner has resolved the contract questions listed under Dependencies before schema implementation, including event time, document-level context propagation, metadata split, subject ownership, and sync conflict semantics.
- Phase 100601's accepted context/evidence boundary is available; Phase 100601 may still be in plan status, but its contract must be approved before schema work begins.
- The existing dual-backend, encryption, audit-event, migration, and item/provenance contracts have been inspected.

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| §9 approval | Rehearsal evidence or owner amendment is recorded | Review the signed approval record |
| §9 bulk-operation interpretation | Owner records whether one-document cascade deletion satisfies “bulk operations,” or a separate multi-document phase is approved | Requirement consistency review |
| Native policy | Preservation is selected; destructive parity is excluded | Requirement/ADR review |
| Identity contract | Non-empty UTF-8 `doc_id`; published maximum if one is required; exact `(bank_id, doc_id)` uniqueness | Contract tests and schema constraints |
| Event time | Document revision event-time default, explicit unset, and mapping to extraction and valid/transaction time are approved | Contract review and temporal tests |
| Context propagation | Document-level context is bounded, non-instructional, and reaches derived records under the approved PR-10 policy | Contract/security review |
| Metadata split | Document metadata and item-level metadata are separated; prompt exposure and return behavior are approved or deferred | Contract/security review |
| Source ownership | The subject/key ownership of each document revision is unambiguous for encryption and later erasure | Security design review |
| Source retention | Native version retains encrypted source and chunks; no non-retention mode | Requirement review |
| Zero-result policy | Whether a document with zero admitted records persists, appears in inspection, and is portable is explicitly chosen | Requirement review and fixture |
| Repository deletion | Hard removal, invalidation, or archival semantics and its history effects are explicitly chosen; it is not compliance erase | Requirement/security review |
| Phase 100601 | `context`, `evidence_ref`, and `source_ref` remain distinct | Contract review |
| Phase 100020 | Shared store trait plus SQLite/PostgreSQL behavior and subject DEK hooks exist | Existing backend tests |
| Phase 100030 | Items have stable IDs, bank/subject ownership, and provenance | Item/schema inspection |
| Migration framework | Additive schema convergence works for existing SQLite and PostgreSQL databases | Old-schema fixture migration |
| Audit event seam | A content-free event sink can later record document operations | Existing audit tests/interface |

### Contract Decisions That Must Be Approved Before Coding
- Maximum `doc_id` size and whether identifiers are compared exactly or normalized.
- Allowed document metadata shape, size, prompt exposure, return behavior, and whether caller tags are opaque metadata only.
- Whether item-level arbitrary metadata is deferred or gets a bounded native contract.
- Subject ownership when source text may mention multiple people.
- Event-time semantics: default, explicit unset, mapping to extraction, and mapping to valid/transaction time.
- Document-level context propagation to derived items under PR-10.
- Processing states and retry/reprocess behavior for an interrupted revision.
- Exact repository-deletion semantics and whether it may remove retained source.
- Whether one-document cascade deletion satisfies §9 “bulk operations.”
- Zero-admission document persistence, visibility, and deletion behavior.
- Whether direct and indirect derivation links use one table or separate typed relations.
- Deterministic document sync conflict resolution when multi-host is claimed.

The implementer must not invent answers to these policy questions.

---

## 4. Existing-System Discovery

The agent MUST inspect the existing system before deciding where or how to implement the changes.

### Required Discovery
- Locate the canonical item, provenance, temporal, belief, persona, history, graph, and MemTree models and identify which durable aggregates may be derived from a document.
- Inspect the shared `Store` contract and both backend drivers for transaction, migration, encryption, and pagination conventions.
- Inventory all current uses of `source_ref`, `evidence_ref`, `context`, and transient `chunk_id` values.
- Identify the current audit-event and operation-identity mechanisms that later phases can reuse.
- Locate the subject-key/KMS boundary and prove which fields are encrypted at rest.
- Locate migration convergence for existing SQLite and PostgreSQL databases.
- Identify backend-parity test harnesses and coverage requirements.
- Confirm that no current `doc_id`, `document_id`, document table, persisted source API, or document cascade already exists.

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
- Approved contract decisions and their approval evidence

### Current Repository Findings at Plan Time
- `MemoryItem` has independent IDs, bank/subject ownership, `source_ref`, temporal fields, and separate snapshot/gist halves; it has no document field.
- The shared store contract covers items, graph metadata, vectors, triples, audit reads, and backend-neutral operations; it has no document aggregate.
- The write path carries transient `chunk_id` and `chunk_ids` values through parallel extraction and consolidation, but those values are not persisted document chunks.
- The portable SQL schema has durable item, triple, history, belief, persona, MemTree, and graph tables but no document/revision/chunk table.
- Repository code search found no `doc_id` or `document_id` implementation in Rust sources.
- Existing source text is suitable as the span-verification haystack; `context` and `evidence_ref` have different meanings.
- Phase 100601/100606 explicitly keep document-container semantics separate from provenance identity.

### Assumptions Confirmed
- The feature is a new aggregate, not exposure of a hidden existing container.
- A bank-scoped `(bank_id, doc_id)` key is compatible with existing isolation rules.
- Source revisions and chunks can use the existing subject encryption boundary.
- Existing item identities can remain independent from document identities.
- A durable revision/processing state is required for safe later extraction and replay.

### Assumptions Contradicted or Unconfirmed
- Existing transient chunk IDs do not provide durable document ownership.
- Existing `source_ref` or `evidence_ref` values do not imply document ownership.
- Existing item deletion/supersession primitives do not by themselves define a document cascade.
- The repository does not yet prove mixed-subject document ownership or zero-admission source governance.

### Repository Adaptation Rule
The agent must determine concrete implementation locations from the actual repository. The plan does not prescribe file paths, type names, table names, or directory structures unless they are part of the approved external contract.

---

## 5. Implementation Specification

### Task 1: Record and Verify the Pre-Approved Native Document Contract

#### Intent
Make the already approved document semantics precise enough that schema, repository, write, tool, portability, and erasure phases cannot invent incompatible behavior. Normative ratification happens before this phase starts; this task records and verifies it.

#### Required Capability or Behavior
- Record `doc_id` identity, validation, uniqueness, and bank isolation.
- Record document, revision, chunk, document metadata, item metadata, and derivation-link vocabulary.
- Record native create/retain, append, and replace behavior without destructive replacement.
- Record expected-revision concurrency and retryable conflict behavior.
- Record zero-derived-record and repository-deletion behavior from the approval record.
- Record event-time semantics and document-level context propagation under PR-10.
- Record source retention as mandatory for this native track and explicitly reject any non-retention configuration.
- Keep `context`, `evidence_ref`, `source_text`, and document identity separate in examples and acceptance language.
- Verify that affected requirement sections, tool-catalog placeholders, data-model examples, risks, and glossary were updated together before this phase started.

#### Architectural Responsibility
Requirements and domain-contract ownership. Runtime code must implement the approved contract rather than define policy during coding.

#### Required Changes
1. Verify and trace the pre-phase §9 approval basis, bulk-operation interpretation, and native-preservation choice.
2. Verify that every contract decision listed in §3 was approved before coding.
3. Record observable repository operations without assigning unapproved public tool names.
4. Record error categories for invalid identity, missing document, revision conflict, unauthorized bank/subject, unavailable source, and unsupported operation.
5. Record backward compatibility: old items and old bundles remain valid and are not backfilled as documents.
6. Stop and report if any pre-phase ratification item is missing rather than creating it inside this phase.

#### Implementation Constraints
- Do not describe Hindsight parity unless the behavior is actually equivalent.
- Do not make `evidence_ref` an alias for `doc_id`.
- Do not create a sixth category or episodic type.
- Do not expose repository deletion publicly in this phase.
- Do not add a non-retention source mode.

#### Expected Result
A reviewed contract and glossary define one unambiguous native document model for downstream phases.

### Task 2: Add the Portable Document Schema and Migration

#### Intent
Persist document containers and immutable source revisions without destructive changes to existing data.

#### Required Capability or Behavior
- Enforce `(bank_id, doc_id)` uniqueness and stable document identity.
- Persist immutable source revisions with monotonic revision identity, content hash, processing state, approved event time, actor/operation metadata, and timestamps.
- Persist ordered chunks tied to one source revision with stable chunk identity and content hash.
- Persist bounded document metadata according to the approved encryption/classification policy.
- Persist or explicitly omit item-level metadata according to the approved split contract; do not silently treat document metadata as item metadata.
- Persist derivation references sufficient to identify direct source provenance and traverse indirect consolidation lineage.
- Support zero derived records without forcing a fake memory item or observation.
- Include processing/idempotency state needed by Phase 900615.
- Converge existing databases additively and preserve all current rows.

#### Architectural Responsibility
Portable schema and backend migration ownership.

#### Required Changes
1. Add the approved tables, keys, foreign keys, uniqueness constraints, and indexes to the portable schema path.
2. Add dialect-specific convergence where required without forking logical semantics.
3. Bump the schema version through the established mechanism.
4. Add old-database migration fixtures for SQLite and PostgreSQL.
5. Add integrity checks for missing revisions, chunks, or derivation targets.

#### Implementation Constraints
- No inferred document ownership for existing `source_ref` or `evidence_ref` values.
- No plaintext source or chunk payload.
- No schema-level product behavior that differs by backend.
- No delete migration that destroys historical rows during upgrade.

#### Expected Result
Fresh and existing databases have the same logical document schema, and old data remains readable.

### Task 3: Implement the Shared Document Repository Contract

#### Intent
Provide one backend-neutral repository for native document lifecycle primitives.

#### Required Capability or Behavior
- Create the first document/revision under an expected-revision precondition.
- Get current metadata and authorized source for a bank-scoped `doc_id`.
- List documents with deterministic pagination and approved filters.
- List chunks for a selected source revision.
- Append only when the caller's expected revision matches; append to an unused `doc_id` creates revision one under the approved contract.
- Replace only when the expected revision matches; create a new immutable revision and retain prior revisions.
- Atomically move the current-revision pointer only after the new revision and required links are durable.
- Return a retryable conflict for a lost append or replace race.
- Apply the approved repository-deletion policy without claiming compliance erasure.
- Return content-free not-found behavior across banks.

#### Architectural Responsibility
Backend-neutral store port plus SQLite and PostgreSQL adapters.

#### Required Changes
1. Add document model types and repository methods to the owning domain/store boundaries.
2. Implement transaction and optimistic-check behavior in both drivers.
3. Reuse existing encryption, error mapping, pagination, and actor conventions.
4. Keep extraction, admission, recall ranking, and public tool dispatch outside the repository.
5. Add a shared backend contract suite.

#### Implementation Constraints
- No backend-specific logical behavior.
- No silent last-write-wins append or replace.
- No public plaintext read that bypasses subject authorization/encryption.
- No physical delete unless the approved repository-deletion policy explicitly requires it.
- No operation may partially commit a revision and its current pointer.

#### Expected Result
The same document repository contract passes on SQLite and PostgreSQL, including conflict and migration cases.

### Task 4: Encrypt Source, Chunks, and Sensitive Metadata

#### Intent
Keep retained document content inside Clio's existing subject-protection boundary.

#### Required Capability or Behavior
- Encrypt source revisions and chunks under the approved subject key owner.
- Encrypt document and item metadata fields classified as personal or sensitive, and keep document metadata separate from item-level metadata.
- Keep only the minimum routing, identity, hash, revision, event-time, and lifecycle metadata needed for repository operation.
- Return `ERASED_SUBJECT` or the established equivalent when key custody is unavailable.
- Ensure later Phase 900625 can identify all rows affected by a subject erasure without scanning plaintext.
- Prove no plaintext source appears in database inspection, errors, or ordinary audit payloads.

#### Architectural Responsibility
Existing KMS/encryption boundary and repository adapters.

#### Required Changes
1. Reuse the subject DEK envelope and error mapping.
2. Add document/chunk encryption round trips to the security test suite.
3. Add ciphertext inspection and post-key-destruction unreadability probes.
4. Record the subject/key owner on each revision according to the approved contract.

#### Implementation Constraints
- No DEK material in rows, fixtures, logs, or diagnostics.
- No plaintext fallback when KMS is unavailable.
- Do not implement the full erase workflow in this phase; provide the hooks and inventory needed later.
- Do not treat `doc_id` or content hash as authorization.

#### Expected Result
Authorized reads recover source exactly; raw database inspection reveals ciphertext only.

### Task 5: Represent Direct and Indirect Derivation Lineage

#### Intent
Trace extracted records to their document source without forcing every consolidated record to claim a direct document reference.

#### Required Capability or Behavior
- Directly derived records reference their document revision and originating chunk.
- Consolidated records preserve links to their source records and can traverse those records to one or more document revisions.
- The model does not infer that every derived record has exactly one document.
- One item may be linked to multiple revisions or chunks when existing consolidation semantics justify it.
- A source revision with zero links is valid according to the approved zero-result policy.
- Deleting or superseding a link follows the approved non-destructive history rules.

#### Architectural Responsibility
Document provenance model plus existing consolidation/lineage conventions.

#### Required Changes
1. Define typed or explicitly constrained derivation relationships.
2. Add integrity tests for missing targets, cross-bank targets, and ambiguous lineage.
3. Expose read primitives needed by Phase 900615 to attach provenance during publication.
4. Keep relation semantics independent of retrieval ranking.

#### Implementation Constraints
- No provider-specific observation-scope model.
- No direct `doc_id` claim when only indirect lineage is known.
- No source-text duplication into item provenance.
- No deletion of source-record lineage as a side effect of creating a document link.

#### Expected Result
A consumer can distinguish direct document provenance from indirect consolidated provenance.

### Task 6: Conformance, Migration, and Recovery Tests

#### Intent
Prove the repository contract, encryption boundary, migration safety, and failure recovery before downstream work depends on it.

#### Required Capability or Behavior
- Unit tests cover validation, exact bank scoping, metadata bounds, revision transitions, and conflict mapping.
- Contract tests run the same repository suite against SQLite and PostgreSQL.
- Migration tests start from representative pre-document schemas.
- Security tests inspect raw storage for plaintext and prove key destruction makes source unreadable.
- Failure tests inject transaction, encryption, uniqueness, and migration errors.
- Regression tests prove existing item/triple/history/erase behavior is unchanged.
- Per-file function and line coverage must each remain at or above 90% for every reported Rust source file.

#### Architectural Responsibility
Each owning crate tests its boundary; phase evidence aggregates the results.

#### Required Changes
1. Add focused unit and backend contract tests.
2. Add old-schema and interrupted-migration fixtures.
3. Add concurrency tests for append and replace.
4. Add source/chunk plaintext scans and post-destruction probes.
5. Run the workspace checks and required coverage procedure.
6. Record uncovered behavior as a blocker, not a pass.

#### Implementation Constraints
- Do not use process-global database state.
- Do not weaken existing tests.
- Do not claim PostgreSQL parity from SQLite-only evidence.
- Do not count region coverage as a substitute for function/line coverage.

#### Expected Result
The phase has executable evidence that the new aggregate is portable, encrypted, backward-compatible, and conflict-safe.

### Implementation Freedom
The agent may choose concrete file locations, internal type names, table decomposition, and test organization provided that:
- The approved external contract is unchanged.
- Existing architectural boundaries are respected.
- Source and chunk encryption remains mandatory.
- Native replacement is non-destructive.
- All acceptance criteria pass.

---

## 6. Agent Execution Rules

### Allowed Actions
- Inspect and modify domain, schema, store, migration, encryption, and test components required for the document aggregate.
- Add the approved document/revision/chunk/lineage model and dual-backend repository contract.
- Perform local refactoring needed to preserve clear ownership and the 450-line Rust file limit.
- Add focused fixtures and conformance tests.

### Forbidden Actions
- Start implementation before the approval gate is recorded.
- Expose public tools or edit command ownership.
- Add destructive Hindsight replacement.
- Reuse `evidence_ref` as the document key.
- Backfill historical items into documents without explicit evidence and approval.
- Store plaintext source/chunks or weaken encryption/KMS separation.
- Add unrelated refactors, dependencies, or provider code.
- Delete or bypass tests.
- Claim completion without evidence.

### Agent Decision Boundary
The agent may decide:
- Internal table decomposition and repository method layout.
- Shared helper placement and test organization.
- Non-breaking serialization details after the approved contract is fixed.

The agent must request approval for:
- Any unresolved contract decision in §3.
- A new semantic category or episodic type.
- Mixed-subject ownership not covered by the approved contract.
- A source-retention-disabled mode.
- Destructive repository deletion or destructive replacement.
- Public operation names or CLI ownership.
- Changes to existing admission, temporal, audit, export, sync, or erase semantics.

### Mandatory Stop Conditions
Stop and report if:
- The §9 approval basis is missing.
- The §9 “bulk operations” interpretation has not been recorded.
- Event time, document-level context propagation, metadata split, subject ownership, or sync conflict decisions are unresolved.
- Native preservation is not selected.
- Any required contract decision remains unresolved.
- Existing data cannot be migrated additively.
- The current architecture cannot encrypt and erase document source without a security-sensitive redesign.
- Cross-bank uniqueness or authorization cannot be guaranteed.
- Correctness cannot be demonstrated on both supported backends.

---

## 7. Security Constraints

### Required Controls
- `(bank_id, doc_id)` is the mandatory lookup and uniqueness boundary.
- Bank and subject authorization are checked independently of `doc_id` possession.
- Source text, chunks, and sensitive metadata are encrypted at rest.
- SQL access uses parameterized statements and the established least-privilege model.
- Audit handoff data is content-free: IDs, revisions, hashes, counts, state, actor, and timestamps only.
- `doc_id`, content hashes, revision IDs, and chunk IDs are identity/integrity metadata, not anonymized data; ordinary diagnostics must not overexpose them.
- Repository deletion has a distinct authorization and confirmation contract from compliance erasure.

### Sensitive Data Rules
- Never log raw source text, chunks, sensitive metadata, DEKs, or decrypted envelopes.
- Never place secrets in `doc_id`, metadata, test fixtures, or error messages.
- Never use a content hash as proof of authorization.
- Never copy source text into plaintext indexes or migration logs.
- Use only the repository's approved secret and key-management mechanisms.

### Security Acceptance Conditions
- The same `doc_id` in two banks remains isolated.
- A caller authorized for one bank cannot read or mutate another bank's document.
- Raw database inspection finds no plaintext source or chunks.
- Destroying the subject key makes document source/chunks unreadable.
- A cross-bank derivation target is rejected.
- Repository deletion cannot be mistaken for or aliased to `erase_request`.

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
| T900611-01 | Create the first document in a bank | Revision 1, chunks, metadata, and current pointer commit together |
| T900611-02 | Reuse the same `doc_id` in another bank | Two independent documents exist |
| T900611-03 | Empty, invalid, or policy-violating `doc_id` | Rejected before persistence |
| T900611-04 | Native replace with matching expected revision | New revision becomes current; prior revision remains readable |
| T900611-05 | Concurrent replace with stale expected revision | Retryable conflict; no partial revision/current-pointer state |
| T900611-06 | Append to an unused `doc_id` | Creates revision 1 under the approved append policy |
| T900611-07 | Concurrent append with stale expected revision | Retryable conflict; unseen content is not overwritten |
| T900611-08 | Create a document with zero derivation links | Valid according to the approved zero-result policy |
| T900611-09 | Link a directly derived item to revision/chunk | Exact provenance round-trips |
| T900611-10 | Link only through consolidated source lineage | No false direct-document claim is emitted |
| T900611-11 | Apply repository-deletion policy | Exact approved lifecycle behavior; audit/compliance boundaries remain distinct |
| T900611-12 | Inspect raw SQLite/PostgreSQL rows | Source/chunks/sensitive metadata are ciphertext only |
| T900611-13 | Destroy the subject key | Source/chunk reads fail closed; structure remains non-authoritative |
| T900611-14 | Migrate a pre-document database | Existing rows remain intact and readable |
| T900611-15 | Inject a mid-migration or transaction failure | Database remains at a valid prior schema/state; recovery path is explicit |
| T900611-16 | Run the same contract suite on both backends | Identical logical outcomes |
| T900611-17 | Persist a revision with an explicit event time and with explicit unset | Event time round-trips exactly; unset remains distinguishable from a default timestamp |
| T900611-18 | Persist document metadata separately from item metadata | The two metadata classes round-trip independently and are not silently merged |
| T900611-19 | Retain a revision with document-level context under the approved policy | Context is bounded, non-instructional, and available to the downstream derivation path |

### Negative Testing
Verify that:
- Invalid identity, metadata, revision, event-time, and cross-bank targets are rejected.
- Unauthorized actions fail without existence leaks.
- Stale writers never silently overwrite content.
- Migration failures do not partially expose the new contract.
- Existing item and provenance behavior remains intact.
- Failure does not leave orphaned source/chunk/lineage rows.
- Document metadata is not silently promoted to item metadata or to extraction instructions.

### Verification Rule
Implementation claims must be supported by actual test output, migration inspection, raw-storage inspection, and backend-parity evidence. A passing aggregate coverage number is insufficient when any reported Rust file is below the per-file floor.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-900611-01 | A reviewed approval and requirement-consistency record covers the §9 basis, native-preservation policy, §9 “bulk operations” wording, and all §3 contract decisions | Requirement/approval review | Approval record and consistency review |
| AC-900611-02 | `(bank_id, doc_id)` identity is enforced and bank-isolated on both backends | T900611-01, T900611-02, T900611-03 | Contract/integration output and schema evidence |
| AC-900611-03 | Native append/replace use expected revisions and return retryable conflicts without lost content | T900611-04–07 | Concurrency test output |
| AC-900611-04 | Source revisions and chunks are immutable, persisted, and directly/indirectly traceable to derived records | T900611-08–10 | Schema and lineage test output |
| AC-900611-05 | Source, chunks, and sensitive metadata are encrypted; key destruction makes them unreadable | T900611-12, T900611-13 | Raw-storage and post-destruction evidence |
| AC-900611-06 | Repository deletion follows the approved non-compliance policy | T900611-11 | Requirement review and deletion test |
| AC-900611-07 | Existing SQLite/PostgreSQL databases migrate without destructive backfill | T900611-14, T900611-15 | Migration transcripts and row-count evidence |
| AC-900611-08 | Existing item/provenance/erase behavior remains intact | Regression suite | Test output |
| AC-900611-09 | SQLite and PostgreSQL satisfy one logical document repository contract | T900611-16 | Shared contract-suite output |
| AC-900611-10 | Every created/refactored Rust file is ≤450 lines and meets per-file function/line coverage floors | Size inspection and `make coverage` | Size list and coverage report |
| AC-900611-11 | Event time and unset are persisted and distinguishably round-tripped | T900611-17 | Temporal field test output |
| AC-900611-12 | Document metadata and item metadata are separated and never silently merged | T900611-18, negative testing | Metadata split evidence |
| AC-900611-13 | Document-level context is bounded and non-instructional on the downstream path | T900611-19 | Context contract test output |

### Definition of Done
- [ ] Approval gate and all contract decisions are recorded.
- [ ] All in-scope behavior is implemented.
- [ ] All acceptance criteria pass.
- [ ] Required tests pass on SQLite and PostgreSQL.
- [ ] No unauthorized changes were introduced.
- [ ] Existing behavior remains intact.
- [ ] Security checks pass.
- [ ] Documentation and normative cross-references are updated where required.
- [ ] Evidence is collected.
- [ ] Verification is completed.
- [ ] Required approval is obtained.

### Completion Evidence
- Approval record and requirement/ADR consistency review.
- Data-model, schema, migration, and repository change summary.
- SQLite/PostgreSQL contract-suite output.
- Concurrency, encryption, lineage, and old-data compatibility output.
- Rust file-size inventory and per-file coverage report.
- Known limitations and unresolved downstream decisions.

---

## 10. Failure Handling and Recovery

### Expected Failure Modes

| Failure | Detection | Recovery |
|---------|-----------|----------|
| §9 gate is missing | Precondition review | Stop before code/schema changes |
| §9 “bulk operations” interpretation is unresolved | Requirement consistency review | Record whether one-document cascade satisfies the phrase, or approve a separate multi-document contract/phase |
| Migration fails midway | Migration/transaction error | Preserve prior valid schema; repair migration and retry from fixture/backup |
| Duplicate `(bank_id, doc_id)` | Unique constraint | Reject with existing error mapping; do not merge implicitly |
| Stale append/replace | Expected-revision mismatch | Return retryable conflict with current revision metadata |
| Encryption/KMS failure | Repository write/read error | Roll back transaction; fail closed; never store plaintext fallback |
| Revision pointer update fails | Transaction error | Roll back new revision/current pointer together |
| Orphan chunk/link | Integrity check | Quarantine/repair through an explicit operation; do not silently ignore |
| Repository-deletion ambiguity | Contract review | Stop; do not guess hard delete versus invalidation/archive |
| Cross-bank target | Authorization/integrity validation | Reject without revealing target existence |

### Rollback Strategy
Use additive schema changes and immutable source revisions. Before public exposure, a failed implementation can be disabled or removed while leaving old item data readable. Never roll back by deleting source revisions or document rows. Any approved destructive repository-deletion operation requires its own recovery/backup policy and cannot be used as a generic rollback.

### Partial Completion Policy
If only one backend, schema without encryption, or create/get without conflict-safe append/replace is complete, do not claim phase completion. Record completed boundaries, keep public tools disabled, and identify the exact missing behavior.

---

## 11. Traceability

| Parent Requirement | Implementation Task | Verification | Acceptance Criterion |
|--------------------|---------------------|--------------|-----------------------|
| §9 document-container gate | Preconditions, Task 1 | Approval review | AC-900611-01 |
| §0 dual-backend support | Tasks 2–3 | T900611-14, T900611-16 | AC-900611-07, AC-900611-09 |
| PR-3 / PR-5 taxonomy and admission boundary | Tasks 1, 5 | Contract review, T900611-08–10 | AC-900611-01, AC-900611-04 |
| PR-6 / FR-12 preservation | Tasks 1, 3 | T900611-04, T900611-11 | AC-900611-03, AC-900611-06 |
| PR-8 / FR-15 attribution | Tasks 2–3 | Schema/audit handoff inspection | AC-900611-01, AC-900611-03 |
| PR-10 / FR-34 / FR-35 identity separation | Tasks 1, 5 | T900611-03, T900611-09, T900611-10 | AC-900611-02, AC-900611-04 |
| §7.4 / FR-19 encryption prerequisite | Task 4 | T900611-12, T900611-13 | AC-900611-05 |
| NFR-6 protected lifecycle data | Tasks 1, 4 | Contract/security review | AC-900611-05 |
| NFR-7 dual-backend contract | Tasks 2–3, 6 | T900611-16 | AC-900611-09 |
| Event time / temporal extraction boundary | Tasks 1–2 | T900611-17 | AC-900611-11 |
| Metadata split / untrusted-data boundary | Tasks 1–2, 4 | T900611-18 | AC-900611-12 |
| Document-level context / PR-10 | Task 1 | T900611-19 | AC-900611-13 |
| Native preservation selected for this track | Tasks 1, 3 | T900611-04 | AC-900611-03 |

Required chain:

```text
Requirement → Capability → Implementation → Test → Evidence
```

Every acceptance criterion must be traceable.

---

## 12. Phase Exit Contract

### Outputs Produced
- Approved native document contract and consistency-reviewed requirement amendment.
- Portable document/revision/chunk/metadata/lineage schema and migration.
- Shared SQLite/PostgreSQL document repository contract.
- Encrypted source/chunk storage hooks and conflict-safe revision handling.
- Verified direct and indirect derivation-lineage model.
- Backend, migration, concurrency, security, and coverage evidence.

### Guarantees Provided to Downstream Phases
After this phase is accepted:
- Phase 900615 can attach extraction and publication to stable revision/chunk identities.
- Phase 900620 can design schemas without inventing persistence semantics.
- Phase 900625 can extend audit, portability, erasure, and sync to a stable aggregate.
- Native replacement is known to preserve source revisions and record history.
- `doc_id` remains bank-scoped and separate from `evidence_ref` and `context`.

### Known Limitations
- No public document tool or CLI command exists yet.
- Extraction, admission, publication, and recall projection are not implemented here.
- Audit UX, export/import, full compliance erasure, and sync are not integrated here.
- Hindsight destructive replacement is not implemented or claimed.
- Hindsight provider ingestion, file/attachment handling, tag filters, tag-based visibility scoping, custom observation scopes, `entities`/`resolve_entities`, provider fact-type names, item-level arbitrary metadata, and source-retention-disabled behavior are excluded or deferred.
- The 3–4 day estimate excludes approval/review latency, rehearsal, and unrelated baseline repair.

### Downstream Prerequisites
- Phase 900615 may rely only on the accepted repository, revision, chunk, event-time, context, metadata, lineage, encryption, and processing-state contracts.
- Phase 900620 is strictly blocked on normative operation-name approval and a `command-ownership.md` update; no schema, parser, or binding work starts before that gate.
- Phase 900625 may rely on direct/indirect lineage and subject ownership being unambiguous.

### Final Status
BLOCKED

The current status is `BLOCKED` until the §9 approval gate and contract decisions are recorded. After approval and implementation, replace this line only with evidence-backed `PASS`, `PASS WITH DOCUMENTED LIMITATIONS`, or `FAILED`.

### Verification Sign-Off
- Implementer: [TBD]
- Verifier: [TBD]
- Human Approver: required for the §9 gate, normative contract, and repository-deletion policy
- Date: [TBD]

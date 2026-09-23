# Phase 900625: Document Portability, Erasure, and Conditional Sync

### Attribution
Rounds below record plan authorship; implementation sign-off is in §12.
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | OpenCode (Space Bunny Free) | proposed |
| Adversary | r1 | [TBD] | [TBD] |
| Remediator | r1 | [TBD] | [TBD] |
| Remedy Approver | r1 | [TBD] | [TBD] |
| Finalize | r1 | [TBD] | [TBD] |

**Conditional follow-up phase 900625** · **Effort:** ~3–4 days single-host; +2–4 days multi-host · **Status:** Conditional — approval and Phases 900611/900615 required · **Parent:** document lifecycle plus existing audit, export/import, compliance-erasure, and multi-host sync contracts

### Approval Gate

This phase may start only after:

1. The document approval gate in Phase 900611 is recorded.
2. Phases 900611 and 900615 are accepted with stable revision, processing, lineage, current-derivation, and source-retention contracts.
3. Phase 900620 is accepted if approved public document tools are required as part of the end-to-end lifecycle.
4. The owner approves document import admission, repository-delete propagation, document sync-conflict semantics, and the Phase 900611 event-time, context, and metadata split contracts.
5. Multi-host document sync is implemented only when the deployment explicitly claims multi-host support; otherwise the phase documents the omission and does not add unused runtime behavior. The multi-host allowance is separate from the single-host estimate.

### Vocabulary (read first) — zero shared moniker

| Term | Meaning in this phase | Must not be confused with |
|------|------------------------|----------------------------|
| **document audit event** | Content-free record of document create/append/replace/reprocess/delete state, actor, IDs, hashes, counts, and outcome | A duplicate copy of source text or full document history |
| **document export section** | Portable document, revision, chunk, metadata, and lineage records in the existing export bundle | A Hindsight provider export or sync payload |
| **document import identity** | Stable revision/operation identity used to make document restoration idempotent | Admission score or provider memory-unit ID |
| **subject-erased document** | Document source/chunks whose subject key is destroyed and whose content is no longer reconstructable | Repository-deleted or operations-discarded document |
| **document sync mutation** | Bank-scoped durable create/append/replace/reprocess/delete or lineage event | A generic item last-write-wins upsert |
| **document sync conflict** | Concurrent source mutations that cannot be applied without losing or silently rewriting source | A normal item metadata conflict |
| **single-host sync omission** | Deployment mode that does not claim multi-host replication | A broken or partially implemented sync runtime |
| **tombstone** | Content-free proof that erasure or approved repository deletion occurred | Recoverable source text or a reversible hash |

---

## 1. Objective

### Goal
Extend Clio's existing audit, export/import, compliance-erasure, and multi-host sync paths so the native document lifecycle remains attributable, portable, erasable, and convergent without weakening PR-6, FR-19, FR-29, FR-31, or bank isolation. Multi-host work is conditional on an explicit deployment claim; single-host deployments document the omission.

### Expected Outcome
- Every native document mutation emits a content-free, attributable audit event with revision and operation identity.
- Export/import preserves document containers, immutable revisions, chunks, metadata, zero-result policy state, and direct/indirect lineage with a complete manifest.
- Import is idempotent and applies the owner-approved source-admission policy without duplicating revisions or derived records.
- Subject erasure renders document source/chunks unreadable, removes active document retrieval/lineage projections, regenerates affected summaries/indexes, and leaves content-free tombstones.
- Repository deletion, operations discard, document replacement, and compliance erasure remain distinct.
- When multi-host is claimed, document mutations and references sync incrementally, idempotently, and without silent source loss.
- When multi-host is not claimed, documentation states that document mutations are local-only and no unused sync path is added.
- Existing item, graph, belief, persona, history, export, erase, and sync behavior remains intact.

### Parent Requirement
Conditional parent contract: requirement.md P1, P2, P12; PR-1, PR-6, PR-8, PR-9; §4.3 dirty-path maintenance, §4.5 graph metadata, §4.9.5.B import/export, §4.9.5.D sync, §4.12 transparency, §7.4 erasure; FR-12, FR-15, FR-16, FR-19, FR-23, FR-29, FR-31, FR-34, FR-35; NFR-3, NFR-6, NFR-7; §9 document-container gate.

Document-specific payload and mutation behavior remains conditional on the approved requirement amendment.

---

## 2. Scope Boundaries

### In Scope
- Audit/inspect integration for document create, append, replace, reprocess, repository delete, conflicts, and subject erasure.
- Versioned export-bundle support for document containers, immutable source revisions, chunks, metadata, and derivation references.
- Idempotent import with manifest/checksum validation, dry-run reporting, and the approved document source-admission policy.
- Compliance-erasure integration for document source, chunks, derived records, indexes, MemTree/summaries, graph links, audit, and sync resurrection prevention.
- Repository-delete propagation to portability/sync/audit under the approved Phase 900611 deletion semantics.
- Multi-host document mutation/reference sync when multi-host support is claimed.
- Document conflict handling that never silently loses concurrent appended or replaced source.
- Single-host documentation of local-only document mutations when sync is omitted.
- Focused unit, integration, contract, end-to-end, two-node, security, and failure tests.

### Explicitly Out of Scope
- Provider-faithful destructive replacement.
- Hindsight provider adapter, provider credentials, polling, or remote migration.
- File upload, parsing, conversion, OCR, transcription, remote file storage, attachments, or attachment URLs.
- A generic tag/filter system, Hindsight tag retagging, custom observation scopes, or tag-triggered re-consolidation.
- A configurable source-retention-disabled mode.
- A document category, new episodic type, or admission bypass.
- Replacing the existing export format, sync protocol, compliance-erasure workflow, or audit system with a second mechanism.
- Full CRDT text merging unless separately approved.
- Bulk multi-document repository deletion.
- Unrelated portability, sync, erase, or audit improvements.

### Must Not Change
- PR-6: document replacement preserves source revisions and derived-record history.
- FR-19: only verified subject erasure destroys the DEK and triggers compliance propagation.
- Repository document deletion is not `discard`, invalidation, or `erase_request`.
- Export never includes DEKs, API keys, or sync credentials.
- Import never bypasses the approved source-admission and derived-item admission gates.
- Sync never carries DEKs or plaintext in server-blind encrypted mode.
- Sync apply never resurrects erased subject content.
- Bank scope remains part of document identity, audit, export/import, and sync.
- Existing single-host sync omission remains honest.
- Existing export, sync, and erase public tool names remain authoritative unless separately amended.

### Scope Expansion Rule
If work outside this scope appears necessary:
1. Stop.
2. Document the reason.
3. Request clarification or approval.
4. Do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- Phases 900611 and 900615 are accepted.
- Phase 900620 is accepted if its public tools are part of the claimed feature set.
- Phase 100606 context/evidence lifecycle decisions are available for coordination where fields overlap.
- Existing audit, export/import, compliance-erasure, and sync implementations have been inspected on both backends.
- The owner has approved import admission, delete propagation, and sync-conflict policies.
- A deployment's multi-host claim is known before sync work begins.

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| Phase 900611 | Document/revision/chunk/lineage/encryption schema | Phase exit evidence |
| Phase 900615 | Stable derivation attempts/current state/reprocess behavior | Phase exit evidence |
| Phase 100180/100601/100606 | Existing audit event and context/evidence lifecycle conventions | Existing audit/contract tests |
| Phase 100220 | Versioned manifest-backed export/import and dry-run behavior | Existing portability tests |
| Phase 100190 | Subject DEK destruction, tombstone, derived purge/regeneration | Existing erase tests |
| Phase 100240 | Sync journal, cursors, idempotency, bank scope, auth, DLQ, conflict status | Existing two-node tests |
| Phase 100070/100110/100120 | MemTree, index, and retrieval cleanup hooks | Existing maintenance tests |
| Import admission policy | Owner-approved treatment of previously admitted document source on restore | Requirement/approval review |
| Sync conflict policy | Approved rule for concurrent append/replace/reprocess/delete | ADR/requirement review |
| Subject ownership | Each source revision's subject/key ownership is unambiguous | Security design review |

---

## 4. Existing-System Discovery

The agent MUST inspect the existing system before deciding where or how to implement the changes.

### Required Discovery
- Inventory the existing audit event schema, redaction rules, inspect projections, and correction/history behavior.
- Inspect export bundle schema/versioning, entity ordering, checksums, content modes, import planner, chunked batch behavior, and dry-run reports.
- Trace compliance erasure from DEK destruction through item ciphertext, vectors, lexical indexes, associations, MemTree, tombstones, and sync resurrection checks.
- Inspect the sync journal/change feed, supported entity kinds, cursors, idempotency keys, LWW rule, dead-letter handling, auth, encryption, and `sync_status` projection.
- Determine which existing sync limitations from Phase 100240 affect document or source-record lineage.
- Locate how bank/subject identity is represented in audit, bundles, tombstones, and sync envelopes.
- Identify existing old-bundle and unsupported-entity compatibility tests.
- Confirm whether a document revision can be assigned unambiguously to one subject DEK owner.

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
- The approved document import/delete/sync policies
- Exact single-host or multi-host deployment claim being tested

### Current Repository Findings at Plan Time
- Audit uses existing durable event rows and content-free detail conventions; document integration should extend this path.
- Export/import already has a versioned bundle, completeness manifest, `dsar_plaintext`/`ciphertext_backup` modes, dry-run, idempotency, and existing entity limitations.
- Compliance erase destroys the subject DEK, purges derived indexes/edges, detaches MemTree leaves, and writes content-free tombstones.
- Sync uses a durable journal, cursors, mutation IDs, deterministic conflict handling, dead-letter quarantine, auth, optional client encryption, and bank scoping.
- Existing Phase 100240 documents unsupported sync entity kinds rather than silently dropping them; document support must follow the same honesty.
- Existing portability/erase/sync behavior is complete enough to extend, but no document payload/mutation exists.
- The current item model has one `subject_id`; document source ownership must be equally unambiguous for encrypted revisions/chunks.

### Assumptions Confirmed
- Existing manifest, erase, audit, and sync frameworks can carry a new first-class entity.
- DEK destruction can render document source/chunks unreadable without rewriting every historical backup.
- Existing sync cursor/dead-letter behavior can expose document conflicts without silent loss.
- Single-host deployments already have a documented sync-omission pattern.

### Assumptions Requiring Approval or Discovery
- Whether a previously admitted document source is re-admitted on import.
- How concurrent append/replace operations resolve across hosts without losing source.
- Whether repository deletion is represented as a tombstone, mutation event, or physical removal in each backend.
- Whether document metadata is exported as plaintext authorized data or ciphertext under each content mode.
- How a multi-source consolidated record syncs when one or more source documents are deleted.

### Repository Adaptation Rule
The agent must determine concrete implementation locations from the actual repository. The plan does not prescribe file paths, table names, or module names unless required by the approved external contract.

---

## 5. Implementation Specification

### Task 1: Extend Audit and Inspection for Document Lifecycle

#### Intent
Make every document mutation attributable without creating a second logging system or duplicating source content.

#### Required Capability or Behavior
- Emit content-free events for create/retain, append, replace, reprocess attempt/state change, repository delete, admission rejection, sync conflict, and subject erase.
- Include bank, actor, `doc_id`, document/revision IDs, operation/derivation-attempt IDs, content hashes, prior/current revision, counts, state, and error/retryability.
- Keep source, chunk text, sensitive metadata, DEKs, and decrypted payloads out of ordinary audit output.
- Allow authorized source retrieval only through the approved document source-read path, not by reconstructing source from audit.
- Expose document lifecycle through the approved inspect/audit surface once Phase 900620 has defined ownership.
- Preserve existing item audit behavior.

#### Architectural Responsibility
Existing audit/inspect subsystem extended with document projections.

#### Required Changes
1. Add document event kinds and PII-safe detail serialization.
2. Wire all Phase 900615 state transitions and approved repository deletion to audit events.
3. Add document-aware inspect/audit lookup without a parallel log.
4. Add redaction and authorization tests.
5. Record source hashes rather than source text.

#### Implementation Constraints
- No raw source/chunk content in audit.
- No new audit database or event protocol.
- No audit write that can make a failed document mutation appear successful.
- No source recovery from audit after compliance erasure.

#### Expected Result
Operators can reconstruct document lifecycle and attribution without storing a second plaintext copy of source.

### Task 2: Add Document Sections to Export and Manifest

#### Intent
Preserve the native document lifecycle through the existing versioned export format.

#### Required Capability or Behavior
- Export document containers, immutable revisions, chunks, approved event time, document-level context, document metadata, item-level metadata where approved, current-derivation state, and direct/indirect lineage.
- Preserve the approved document/item metadata split and never silently merge the two classes on export.
- Include zero-result documents according to the approved zero-result policy.
- Exclude repository-deleted source according to the approved delete semantics; include only permitted content-free deletion evidence.
- Include document counts, revision/chunk/link counts, checksums, filters, and source-availability state in the completeness manifest.
- Under `dsar_plaintext`, decrypt source/chunks only after authorization.
- Under `ciphertext_backup`, export opaque source/chunk envelopes without DEKs.
- Never export DEKs, API keys, sync credentials, or erased plaintext.
- Preserve old bundle readability and mark completeness honestly when limits apply.

#### Architectural Responsibility
Existing export bundle and manifest implementation.

#### Required Changes
1. Version the bundle format compatibly and add document serializers.
2. Add deterministic ordering and canonical checksums for document entities.
3. Add document content modes and source-availability flags.
4. Add complete/filtered/truncated manifest accounting.
5. Add round-trip and secret-scan fixtures.

#### Implementation Constraints
- Do not create a separate Hindsight export format.
- Do not export source from a shredded subject.
- Do not claim completeness when document limits omit data.
- Do not include document links without their required revisions/chunks.

#### Expected Result
A full export contains a complete, integrity-checked native document lifecycle, and a filtered/truncated export states what is missing.

### Task 3: Add Idempotent Document Import

#### Intent
Restore exported document state without duplicate revisions, lineage loss, or admission bypass.

#### Required Capability or Behavior
- Validate format version, manifest, and checksums before any write.
- Plan create/skip/reject/conflict outcomes with zero writes in dry-run mode.
- Use stable document/revision/operation identities for idempotency.
- Apply the owner-approved source-storage admission policy to document source.
- Preserve event time, document-level context, and the document/item metadata split exactly as approved.
- Run existing category/admission rules for imported derived candidates unless the approved trusted-import rule explicitly applies.
- Preserve direct and indirect lineage and current-derivation state.
- Make re-import of the same bundle a no-op.
- Use existing atomic/chunked batch semantics and report partial completion honestly.
- Never restore a repository-deleted document as active unless the approved delete/import policy explicitly permits a distinct restore operation.

#### Architectural Responsibility
Existing import planner/orchestrator extended with document entities.

#### Required Changes
1. Add document import parsing, validation, planning, and apply paths.
2. Add idempotency and conflict checks at document/revision identity boundaries.
3. Add approved source-admission and derived-item admission invocation.
4. Add old-bundle, unsupported-version, partial-failure, and re-import tests.
5. Extend dry-run/import reports with document-specific counts and notes.

#### Implementation Constraints
- No silent overwrite of a newer local revision.
- No duplicate document/chunk/link rows on replay.
- No admission bypass.
- No resurrection of erased subject content.
- No second import protocol.

#### Expected Result
Export → dry-run → import → re-import restores the same logical document state with no duplicate or silent overwrite.

### Task 4: Integrate Repository-Aware Compliance Erasure

#### Intent
Ensure a subject erasure covers document source, chunks, lineage, derived structures, and synchronized copies.

#### Required Capability or Behavior
- Identify all document revisions/chunks/links owned or encrypted under the subject key.
- Destroy the subject DEK through the existing compliance path so source/chunks become unreadable in primary storage, replicas, and encrypted backups.
- Remove document source/chunk retrieval and document provenance that exposes erased content.
- Apply existing item/triple/graph/MemTree/index/association erase propagation to affected derived records.
- Regenerate affected summaries and indexes; do not leave a readable document-derived projection.
- Write content-free tombstones that prove document erasure without preserving source; use the existing approved salted one-way erase-hash mechanism for document/revision identifiers rather than raw content hashes.
- Prevent sync/import from resurrecting erased document content.
- Keep repository document deletion and operations discard distinct from compliance erasure.

#### Architectural Responsibility
Existing compliance-erasure subsystem extended with document inventory and propagation.

#### Required Changes
1. Add document source/chunk/link rows to the erase transaction and derived-purge plan.
2. Add document-specific fail-closed read behavior.
3. Extend tombstones/sync checks with content-free document/revision hashes and counts.
4. Add affected MemTree/index/graph regeneration hooks.
5. Add end-to-end erase tests over both backends and sync/import paths.

#### Implementation Constraints
- No plaintext rewrite requirement for immutable encrypted backups; key destruction is the mechanism.
- No raw source in tombstones or audit.
- No repository delete masquerading as compliance erase.
- No mixed-subject ownership assumption without an approved erasure design.
- No resurrection through export/import/sync.

#### Expected Result
After verified erasure, document source/chunks and affected derived projections are unreadable or removed, and all later portability/sync paths fail closed.

### Task 5: Propagate Approved Repository Deletion

#### Intent
Keep document deletion coherent across audit, export/import, derived state, and sync without confusing it with compliance erasure.

#### Required Capability or Behavior
- Apply the exact Phase 900611 repository-deletion semantics to current revision, historical revisions, source/chunks, links, indexes, and active retrieval.
- Emit the approved audit/deletion event.
- Ensure a deleted document is not exported as active source.
- Ensure a later sync/import cannot silently resurrect it.
- Preserve or remove historical records according to the approved deletion policy; never improvise beyond that policy.
- If deletion is irreversible repository removal, require a distinct recovery/restore mechanism before public exposure.

#### Architectural Responsibility
Document lifecycle owner with integration from audit, portability, retrieval, and sync owners.

#### Required Changes
1. Propagate the approved deletion state through Phase 900615/900620 services.
2. Add export/import/sync deletion handling.
3. Add referential cleanup/regeneration according to the approved policy.
4. Add tests distinguishing delete, discard, invalidation, replacement, and erase.

#### Implementation Constraints
- No bulk delete.
- No key destruction from repository delete.
- No hidden history deletion beyond the approved policy.
- No resurrection.

#### Expected Result
Repository deletion is coherent and distinguishable across every downstream lifecycle surface.

### Task 6: Add Document Sync When Multi-Host Is Claimed

#### Intent
Replicate document mutations and lineage incrementally without silently losing source or crossing banks.

#### Required Capability or Behavior
- Journal document create, append, replace, reprocess state, repository delete, and derivation-reference mutations with stable mutation IDs.
- Include document/revision/chunk/link identity, expected prior revision, content hash, bank/subject routing metadata, and encrypted/opaque content fields as approved.
- Apply duplicate delivery idempotently.
- Reject cross-bank and unauthorized mutations.
- Preserve bank scope and optional client encryption; never send DEKs.
- Surface document pending counts, conflicts, dead letters, and last errors in existing `sync_status` output.
- Freeze pull progress across unresolved document conflicts rather than skipping them.
- Use the approved deterministic conflict rule; concurrent append/replace must not silently discard source.
- Preserve erased-subject and repository-delete protections on pull.
- Document local-only behavior when the deployment is single-host.

#### Architectural Responsibility
Existing sync journal, wire protocol, client/server, apply engine, and status projection.

#### Required Changes
1. Add document mutation packaging and cursor/feed integration.
2. Add document apply/idempotency/bank/auth/encryption handling.
3. Add the approved document conflict/dead-letter behavior.
4. Extend `sync_status` with document counts/conflict details.
5. Add two-process tests and single-host omission documentation.

#### Implementation Constraints
- No generic item LWW that silently loses an append or replacement.
- No plaintext server storage in client-encrypted mode.
- No DEK transfer.
- No cursor advance past unresolved document mutations.
- No unsupported document mutation silently dropped.
- No unused sync runtime in a single-host deployment.

#### Expected Result
Claimed multi-host deployments converge on document state with deterministic, visible conflicts; single-host deployments state the omission clearly.

### Task 7: Cross-Cutting Verification and Evidence

#### Intent
Prove audit, portability, erasure, deletion, and conditional sync as one coherent lifecycle.

#### Required Capability or Behavior
- Unit, integration, contract, end-to-end, regression, security, and failure-mode tests cover every in-scope path.
- Export/import round trips run on SQLite and PostgreSQL.
- Compliance erase runs end to end and is followed by export/import/sync resurrection attempts.
- Multi-host claims use real two-process or equivalent transport evidence.
- Single-host omission is verified by documentation/profile inspection and absence of claimed document replication.
- Required workspace checks and per-file coverage pass.

#### Architectural Responsibility
Owning crates test their own boundaries; the phase exit aggregates the evidence.

#### Required Changes
1. Add a multi-revision document portability fixture.
2. Add erase and non-resurrection tests.
3. Add audit redaction/reconstruction tests.
4. Add two-node document sync/concurrency tests when claimed.
5. Run workspace checks, file-size inspection, and `make coverage`.
6. Record any omitted sync mode and its deployment condition explicitly.

#### Implementation Constraints
- Do not claim sync evidence from SQLite-only or in-process tests.
- Do not claim erase completeness without negative read/export/import/sync probes.
- Do not hide unsupported entity kinds.
- Do not defer required coverage to another phase.

#### Expected Result
The phase has executable evidence that the document lifecycle survives audit, portability, deletion, erasure, and the claimed sync topology safely.

### Implementation Freedom
The agent may choose internal bundle placement, journal representation, conflict record shape, and test organization provided that versioning, idempotency, no silent source loss, security, and acceptance criteria remain fixed.

---

## 6. Agent Execution Rules

### Allowed Actions
- Inspect and modify audit, export/import, compliance, sync, retrieval, index, and test components required for document integration.
- Add document bundle sections, sync mutations, erase inventory, and PII-safe audit projections.
- Perform local refactoring needed to preserve existing framework ownership and Rust file-size limits.
- Reuse existing manifest, tombstone, KMS, cursor, dead-letter, and dirty-path mechanisms.

### Forbidden Actions
- Start before approval and phase dependencies are satisfied.
- Create a second audit, export, import, erase, or sync system.
- Add provider destructive replacement, provider adapter, upload/ETL, attachments, tags, observation scopes, or source-retention-off behavior.
- Silently lose source through sync conflict handling.
- Export DEKs, credentials, or erased plaintext.
- Restore erased/deleted content through import or sync.
- Add unused sync runtime for a single-host deployment.
- Delete/bypass tests or claim completion without evidence.

### Agent Decision Boundary
The agent may decide:
- Internal bundle layout/version migration mechanics.
- Audit event serialization details.
- Sync journal/feed batching and conflict-record layout.
- Test fixture organization.

The agent must request approval for:
- Changing import admission semantics.
- Changing the existing bundle format incompatibly.
- Changing the published sync conflict protocol.
- Adding document behavior to an unsupported topology.
- Any new source-retention or deletion policy.
- Any public tool/catalog change outside approved Phase 900620 ownership.

### Mandatory Stop Conditions
Stop and report if:
- Import admission, delete propagation, or sync conflict policy is unresolved.
- Document subject ownership cannot support unambiguous DEK erasure.
- Existing erase cannot cover document source/chunks without a security-sensitive redesign.
- Export/import cannot preserve direct/indirect lineage without silent loss.
- Sync would require silent source overwrite or plaintext key exposure.
- The deployment's multi-host claim is unclear.
- Correctness cannot be demonstrated on both backends.

---

## 7. Security Constraints

### Required Controls
- Bank/subject authorization gates audit, export, import, source restore, erase, and sync operations.
- Export source is authorized-decrypted only in the approved content mode.
- DEKs, API keys, sync credentials, and raw source never enter ordinary audit or logs.
- Compliance erase uses the existing verified key-destruction path.
- Sync preserves client encryption and bank scope when claimed.
- Conflict/dead-letter records contain IDs, hashes, and state, not source text.
- Import validates integrity and authorization before durable apply.

### Sensitive Data Rules
- Never log raw source/chunks during export, import, sync, delete, or erase.
- Never include source or reversible normalized text in tombstones.
- Never transfer DEKs to export files or sync peers.
- Never let repository delete destroy keys.
- Never use a document ID/hash as authorization.
- Never restore erased subject content from ciphertext backup or sync.

### Security Acceptance Conditions
- Unauthorized export/import/sync/audit access fails without content or existence leaks.
- Export scans find no DEKs, credentials, or erased plaintext.
- After subject erasure, document source/chunk reads fail closed and derived projections are removed/regenerated.
- Import and sync cannot resurrect erased or repository-deleted content.
- A concurrent append/replace conflict preserves both source payloads and does not silently choose a winner.
- Unauthorized or cross-bank sync cannot mutate a document.

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
| T900625-01 | Create/append/replace/reprocess/delete a document | Content-free audit reconstructs the full state transition |
| T900625-02 | Audit output for source containing secrets | No source/chunk/sensitive metadata appears |
| T900625-03 | Full authorized export | Documents/revisions/chunks/links and manifest counts/checksums are complete |
| T900625-04 | Filtered/truncated document export | `complete=false` with explicit omissions |
| T900625-05 | `dsar_plaintext` document export/import | Authorized source round-trips; no DEK/credential appears |
| T900625-06 | `ciphertext_backup` document export/import | Opaque source/chunks round-trip only with key custody; no DEK appears |
| T900625-07 | Re-import the same document bundle | No duplicate document, revision, chunk, link, or item rows |
| T900625-08 | Import a bundle with a newer local document revision | Visible conflict/plan result; no silent overwrite |
| T900625-09 | Import a zero-result document | Restored according to the approved zero-result policy |
| T900625-10 | Subject erase with document source/chunks | Source/chunks unreadable; active provenance/index/summary removed; content-free tombstone remains |
| T900625-11 | Export/import after subject erase | No erased source is exported or restored |
| T900625-12 | Repository-delete a document | Exact approved history/source behavior; no DEK destruction |
| T900625-13 | Import/sync after repository delete | No silent resurrection |
| T900625-14 | Two-node document create/append/reprocess sync | Peer converges; source protected; mutation replay is idempotent |
| T900625-15 | Concurrent append on two nodes | Deterministic visible conflict/dead letter; no source silently lost |
| T900625-16 | Concurrent replace/delete on two nodes | Approved conflict/deletion rule applies; no resurrection or partial state |
| T900625-17 | Cross-bank document sync attempt | Rejected without mutation or existence leak |
| T900625-18 | Erased-subject document sync attempt | Dead-letter/fail-closed; no plaintext resurrection |
| T900625-19 | Single-host deployment | Documentation states local-only document mutations; no unused runtime claim |
| T900625-20 | Run portability/erase tests on SQLite and PostgreSQL | Same logical outcomes |
| T900625-21 | Export/import event time, document context, document metadata, and item metadata | Each field round-trips under the approved split; none is silently merged or dropped |

### Negative Testing
Verify that:
- Missing manifest/checksum/version rejects before write.
- Unauthorized/cross-bank export/import/sync fails safely.
- Partial import/sync/erase reports incomplete state without false success.
- Duplicate and stale operations are idempotent/conflicted as approved.
- Existing non-document portability/sync/erase behavior remains intact.
- Excluded provider/file/attachment features are absent.
- Document metadata is not merged into item metadata on import or export.

### Verification Rule
Implementation claims must be supported by actual bundle artifacts, database/tombstone inspection, negative read probes, and—when multi-host is claimed—real two-node transcripts.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-900625-01 | Document lifecycle is attributable through the existing audit system without raw-source duplication | T900625-01, T900625-02 | Audit transcript and redaction scan |
| AC-900625-02 | Export/import preserves documents, revisions, chunks, metadata, lineage, and manifest completeness | T900625-03–09 | Bundle, manifest, round-trip, and idempotency evidence |
| AC-900625-03 | Subject erasure covers document source/chunks and all affected derived structures | T900625-10, T900625-11 | Erase transcript, negative reads, tombstone/purge evidence |
| AC-900625-04 | Repository deletion follows the approved policy and cannot be confused with compliance erase | T900625-12, T900625-13 | Policy review and lifecycle tests |
| AC-900625-05 | Claimed multi-host sync is incremental, idempotent, bank-scoped, encrypted, and conflict-safe | T900625-14–18 | Two-node sync/dead-letter/security output |
| AC-900625-06 | Single-host omission is explicit and no unused document sync path is claimed | T900625-19 | Documentation/profile inspection |
| AC-900625-07 | SQLite and PostgreSQL satisfy the same logical document portability/erase contract | T900625-20 | Dual-backend output |
| AC-900625-08 | Existing audit, export/import, erase, sync, and document behavior remain intact | Regression suite | Test output |
| AC-900625-09 | No provider destructive parity, upload/ETL, attachment, tag-filter, observation-scope, fact-type, item-metadata, or source-retention-off claim is made | Contract/docs review | Explicit limitation matrix |
| AC-900625-10 | Every created/refactored Rust file is ≤450 lines and meets per-file function/line coverage floors | Size inspection and `make coverage` | Size list and coverage report |
| AC-900625-11 | Event time, document context, and the document/item metadata split survive export/import | T900625-21 | Round-trip metadata evidence |

### Definition of Done
- [ ] Approval and phase dependencies are satisfied.
- [ ] All in-scope audit, portability, erase, delete, and claimed-sync behavior is implemented.
- [ ] All acceptance criteria pass.
- [ ] Required tests pass on SQLite and PostgreSQL.
- [ ] Multi-host claims have two-node evidence; single-host omission is documented.
- [ ] No unauthorized changes were introduced.
- [ ] Existing behavior remains intact.
- [ ] Security checks pass.
- [ ] Documentation is updated.
- [ ] Evidence is collected.
- [ ] Verification is completed.
- [ ] Required approval is obtained.

### Completion Evidence
- Audit/inspect summary and redaction output.
- Export bundle/manifest samples and import/idempotency transcripts.
- Compliance erase, negative-read, purge, tombstone, and non-resurrection evidence.
- Repository-delete propagation output.
- Two-node document sync/conflict/dead-letter/security evidence or single-host omission evidence.
- Dual-backend output, Rust file-size inventory, and per-file coverage report.
- Known limitations and feature-mapping matrix.

---

## 10. Failure Handling and Recovery

### Expected Failure Modes

| Failure | Detection | Recovery |
|---------|-----------|----------|
| Bundle manifest/checksum invalid | Pre-write validation | Reject with zero writes; preserve current store |
| Mid-import failure | Batch/transaction error | Roll back affected batch, retain prior committed batches, report progress honestly |
| Newer local document revision | Expected revision/import conflict | Do not overwrite; return visible conflict/plan result |
| Partial audit failure | Transaction/event sink error | Fail mutation or mark processing; never report unlogged success |
| Subject erase propagation failure | Purge/regeneration status | Source remains unreadable after key destruction; retry/queue repair and report processing |
| Repository delete propagation failure | Integrity/status check | Keep source inaccessible according to approved state; retry cleanup; do not call erase |
| Sync network/auth failure | Client/server error | Do not advance cursor; resume with idempotent mutation IDs |
| Concurrent document mutation | Expected-revision conflict | Preserve payloads, record conflict/dead letter, freeze cursor until resolution |
| Erased/deleted content arrives through sync/import | Tombstone/delete check | Reject/dead-letter; never resurrect |
| Multi-host claim absent | Deployment inspection | Do not implement/claim runtime; document local-only behavior |

### Rollback Strategy
Disable document portability/sync exposure while preserving the existing export/sync/erase frameworks and local document history. Use idempotent retries and dead-letter resolution rather than overwriting data. Compliance key destruction is irreversible by design and is never a rollback mechanism.

### Partial Completion Policy
If audit/export works but erase or claimed multi-host sync is incomplete, do not claim the phase complete. Public feature status must state the exact supported lifecycle and whether sync is omitted.

---

## 11. Traceability

| Parent Requirement | Implementation Task | Verification | Acceptance Criterion |
|--------------------|---------------------|--------------|-----------------------|
| §9 / Phase 900611/900615 gates | Preconditions | Approval/dependency review | AC-900625-01–06 |
| PR-8 / FR-15 | Task 1 | T900625-01, T900625-02 | AC-900625-01 |
| FR-29 / NFR-6 | Tasks 2–3 | T900625-03–09 | AC-900625-02 |
| PR-6 / FR-12 | Tasks 3–5 | History/delete/round-trip tests | AC-900625-02, AC-900625-04 |
| FR-19 / §7.4 | Task 4 | T900625-10, T900625-11, T900625-18 | AC-900625-03 |
| FR-23 deletion separation | Task 5 | T900625-12, T900625-13 | AC-900625-04 |
| FR-31 / §4.9.5.D | Task 6 | T900625-14–18 | AC-900625-05 |
| §4.9.6 single-host omission | Task 6 | T900625-19 | AC-900625-06 |
| NFR-7 dual backend | Tasks 2–7 | T900625-20 | AC-900625-07 |
| Event time / context / metadata split | Tasks 2–3 | T900625-21 | AC-900625-11 |
| Phase 100601/100606 lifecycle coordination | Tasks 1–4 | Cross-phase regression review | AC-900625-01–04, AC-900625-08 |
| Explicit parity exclusions | All tasks | Contract/docs review | AC-900625-09 |

Required chain:

```text
Requirement → Capability → Implementation → Test → Evidence
```

Every acceptance criterion must be traceable.

---

## 12. Phase Exit Contract

### Outputs Produced
- Content-free document audit/inspect integration.
- Versioned manifest-backed document export/import with idempotency.
- Repository-aware compliance erasure and non-resurrection guarantees.
- Approved repository-delete propagation.
- Document sync mutations/conflicts for claimed multi-host deployments, or explicit single-host omission.
- Dual-backend, security, failure, and coverage evidence.

### Guarantees Provided to Downstream Phases
After this phase is accepted:
- Native documents remain attributable, portable, and erasable across their complete lifecycle.
- Import/sync cannot silently overwrite newer source or resurrect erased/deleted content.
- Multi-host document convergence has visible, deterministic conflict handling.
- Single-host deployments make an honest local-only claim.
- Provider-specific destructive behavior remains outside native Clio governance.

### Known Limitations
- Hindsight destructive replacement and provider import are excluded.
- File/attachment ingestion, tag filtering, tag-based visibility scoping, observation scopes, `entities`/`resolve_entities`, provider fact-type names, item-level arbitrary metadata, and source-retention-disabled behavior are excluded or deferred.
- Bulk multi-document deletion is excluded; one-document cascade deletion is the interpretation question recorded in Phase 900611.
- No full CRDT text merge is provided.
- Sync remains conditional on an explicit multi-host claim.
- The 3–4 day estimate covers single-host audit, export/import, delete propagation, and erasure only; multi-host sync adds 2–4 days and excludes approval/review latency, migration surprises, unrelated baseline repair, and provider work.

### Downstream Prerequisites
- Any later provider adapter must translate Hindsight document behavior explicitly, ship provider fixture or contract tests, and not weaken native preservation.
- Any later source-retention-disabled feature must redesign append/reprocess/erase/portability rather than silently dropping source.
- Any later tag or observation-scope feature must define visibility scoping, provenance, and re-consolidation behavior before implementation.

### Final Status
BLOCKED

The current status is `BLOCKED` until the document approval gate and phase dependencies are accepted. After implementation, replace this line only with evidence-backed `PASS`, `PASS WITH DOCUMENTED LIMITATIONS`, or `FAILED`.

### Verification Sign-Off
- Implementer: [TBD]
- Verifier: [TBD]
- Human Approver: required for import admission, repository-delete propagation, and sync-conflict policy
- Date: [TBD]

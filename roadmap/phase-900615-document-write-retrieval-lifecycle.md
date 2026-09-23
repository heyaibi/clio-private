# Phase 900615: Document Write and Retrieval Lifecycle

### Attribution
Rounds below record plan authorship; implementation sign-off is in §12.
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | OpenCode (Space Bunny Free) | proposed |
| Adversary | r1 | [TBD] | [TBD] |
| Remediator | r1 | [TBD] | [TBD] |
| Remedy Approver | r1 | [TBD] | [TBD] |
| Finalize | r1 | [TBD] | [TBD] |

**Conditional follow-up phase 900615** · **Effort:** ~3–4 days · **Status:** Conditional — approval and Phase 900611 required · **Parent:** Phase 900611 native document repository and requirement §4 write/retrieval rules

### Approval Gate

This phase may start only after:

1. The document approval gate in Phase 900611 is recorded.
2. Phase 900611's repository, revision, chunk, lineage, encryption, and zero-result contracts are accepted.
3. The owner has approved how a source-document container itself is admitted without turning it into a new memory category.
4. Any public operation exposed later still requires the separate Phase 900620 tool-catalog gate; this phase implements internal lifecycle behavior only.

All four document phases are parked at or above the runner's 900000 floor, so the selector ignores the whole family. This phase depends on Phase 900611; un-park them together or supply the 900611 contract separately before either runs.

### Vocabulary (read first) — zero shared moniker

| Term | Meaning in this phase | Must not be confused with |
|------|------------------------|----------------------------|
| **document write** | Native source-text ingestion that creates a revision and runs existing extraction/admission/publication | Public MCP/CLI binding or provider ingestion |
| **source-storage admission** | Governance decision that permits retained source text to be stored as a document container | A sixth semantic category or a new episodic type |
| **derivation attempt** | One extraction/admission/publication run over a stored source revision | A new source revision |
| **current derivation** | The successful attempt whose records are eligible for active retrieval for that document revision | Physical deletion of older records |
| **reprocess** | Re-run extraction/admission over already retained source without requiring the caller to resubmit text | Replace, append, or destructive re-extraction |
| **active index retirement** | Removing, disabling, or excluding stale derived rows from active lexical/dense retrieval | Deleting historical item content |
| **direct provenance** | A record's derivation link names a document revision and originating chunk | A claim that every consolidated record has a direct document link |
| **resolved provenance** | A record reaches one or more documents through existing source-record lineage | A fabricated direct `doc_id` field |

---

## 1. Objective

### Goal
Carry a document's bank-scoped identity, immutable source revision, and persisted chunks through Clio's existing extraction, verification, admission, publication, and retrieval paths. Native append and replace must preserve prior revisions and derived records, publish only coherent current derivations, retire stale active index entries, and support recovery/reprocessing without destructive history loss.

### Expected Outcome
- A caller-supplied source text can be processed into the existing typed memory model with document revision/chunk provenance.
- Append and replace use the Phase 900611 expected-revision contract and return retryable conflicts on stale writes.
- Native replace creates new derived records, preserves old records, and makes only the new successful derivation active.
- A document may persist with zero admitted records according to the Phase 900611 policy; that outcome is explicit and auditable.
- Recall results expose `doc_id`, revision, and chunk references only when direct or unambiguous resolved provenance exists.
- Stored-document reprocessing uses retained source, preserves prior curation/history, and cannot silently replace the current derivation after failure.
- Existing category, admission, span verification, snapshot/gist authority, temporal, and PR-9 leaf-first rules remain intact.

### Parent Requirement
Conditional parent contract: requirement.md P1, P2, P3, P5, P9, P10, P12; PR-1, PR-3, PR-4, PR-5, PR-6, PR-8, PR-9, PR-10; §4.1–§4.6; §4.9.3; FR-3, FR-4, FR-5, FR-11, FR-12, FR-14, FR-15, FR-17, FR-20, FR-24, FR-34, FR-35; NFR-2, NFR-3, NFR-4, NFR-5, NFR-6, NFR-7; §9 document-container gate.

The document-specific write/retrieval contract remains conditional on the requirement amendment described in Phase 900611.

---

## 2. Scope Boundaries

### In Scope
- Internal native document retain/create, append, replace, and stored-source reprocess orchestration.
- The approved document source-storage admission gate, including event time, document-level context, and the document/item metadata split.
- Mapping persisted chunks and approved event time into the existing parallel extraction and verification path.
- Carrying direct document revision/chunk provenance through consolidation, admission, item creation, and recall.
- Durable derivation-attempt state, idempotency, failure recovery, and current-derivation publication.
- Native replacement behavior that preserves old revisions/records and retires stale active projections.
- Optional unchanged-chunk/delta append optimization only when observable semantics and conflict behavior remain identical.
- Recall projections for `doc_id`, revision, and chunk references, including resolved provenance through consolidation.
- Active lexical/dense index retirement or exclusion and affected MemTree/summary regeneration.
- Focused unit, integration, contract, end-to-end, regression, security, and failure tests.

### Explicitly Out of Scope
- Public MCP tools, CLI commands, machine-readable public schemas, help text, or command ownership.
- Audit/inspect UX, export/import, full compliance erasure, or sync; these belong to Phase 900625.
- Provider-faithful destructive replacement.
- Hindsight API calls, provider polling, or `import_provider` integration.
- File upload, parsing, conversion, OCR, transcription, remote file storage, attachments, or attachment URLs.
- Hindsight custom observation scopes, tag filtering, tag-based visibility scoping, or tag-triggered re-consolidation.
- Hindsight `entities` / `resolve_entities` controls or provider fact-type names.
- Item-level arbitrary metadata unless the approved split contract explicitly includes it.
- A configurable mode that discards verbatim source.
- A document memory category, new episodic type, or admission bypass.
- Replacing Clio's extraction model, span verifier, retrieval ranking, or general temporal fact model.

### Must Not Change
- `context` remains descriptive metadata, not identity or extraction truth.
- `evidence_ref` remains external provenance and is not replaced by `doc_id`.
- `source_text` remains the span-verification haystack.
- Snapshot remains authoritative; gist remains non-authoritative.
- Category and five-factor admission remain mandatory for every derived long-term record.
- Native replacement preserves prior revisions and records; it never deletes them as a side effect of supersession.
- PR-9: newly published leaves are queryable before ancestor summary maintenance completes.
- Existing retrieval budgets, time filters, bank scope, and explicit-call behavior remain intact.
- Existing `chunk_id` concepts remain distinct unless the approved contract deliberately maps them to persisted document chunks.

### Scope Expansion Rule
If work outside this scope appears necessary:
1. Stop.
2. Document the reason.
3. Request clarification or approval.
4. Do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- Phase 900611 is accepted with a stable document repository contract.
- The approved amendment defines source-storage admission, zero-result behavior, current-derivation semantics, and reprocess behavior.
- Existing extraction, verification, admission, publication, indexing, MemTree, and retrieval owners have been inspected.
- Existing Phase 100601 context/evidence rules are available; Phase 100606 coordination is planned where its contracts overlap.
- A known unrelated baseline failure does not get hidden or silently repaired; it is scheduled outside this phase.

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| Phase 900611 | Create/get/list/append/replace/chunks/lineage/encryption repository contract | Phase exit evidence |
| Source-storage admission policy | Explicit document-container admission decision and bounds | Requirement/approval review |
| Native replacement policy | New revision and derivation become current only after durable success; old history remains | Contract review |
| Phase 100050/100060 | Extraction, span verification, and consolidation seams accept chunk provenance | Existing tests and source inspection |
| Phase 100040 | Category and admission gates remain callable for each derived candidate | Gate tests |
| Phase 100030/100080 | Item and temporal supersession contracts retain history | Existing regression tests |
| Phase 100070/100110/100120 | Dirty-path, lexical/dense indexing, and retrieval can mark stale active rows | Existing tests |
| Phase 100601 | `context`/`evidence_ref`/`doc_id` boundaries are accepted | Contract review |
| Deterministic clock/IDs | Retry and reprocess tests can control ordering | Test fixture inspection |
| Durable processing state | Phase 900611 supports resumable/idempotent derivation attempts | Repository contract tests |

---

## 4. Existing-System Discovery

The agent MUST inspect the existing system before deciding where or how to implement the changes.

### Required Discovery
- Trace the real ingest path from raw source text through chunking, parallel extraction, verification, consolidation, admission, item persistence, leaf publication, and index maintenance.
- Determine which `chunk_id` values are currently transient and which fields survive consolidation.
- Trace item provenance and temporal supersession to identify safe native-replacement behavior.
- Locate the active lexical/dense index and MemTree/summary maintenance paths and their failure/retry semantics.
- Locate retrieval result serialization and determine how optional provenance metadata can cross existing budget and type boundaries.
- Locate operation/audit event seams for later Phase 900625 without exposing raw source.
- Identify existing tests for failed extraction, zero-result writes, retries, stale index rows, and backend parity.
- Confirm whether the runtime can resume an interrupted document operation rather than starting a new one.

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
- The exact write/recovery state machine selected for the approved contract

### Current Repository Findings at Plan Time
- Parallel extraction returns per-chunk `chunk_id`, source text, and verified candidates; these IDs are generated in the transient write path.
- Consolidation carries a union of contributing `chunk_ids`, source references, and source text into canonical units.
- The current item model has one `source_ref` and no document/revision/chunk provenance fields.
- Existing item and triple writes already distinguish historical rows from active retrieval through temporal/discard state.
- Dense/lexical indexing is durable and queue-backed; MemTree maintenance is dirty-path and decoupled from leaf publication.
- Existing retrieval can return item metadata, but no document revision/chunk contract exists.
- There is no current stored-document reprocess operation or document processing journal.

### Assumptions Confirmed
- Existing extraction can be reused by mapping persisted document chunks into its current input.
- Existing admission and supersession can govern derived records without creating a document category.
- Retrieval can expose bounded provenance metadata without returning source text by default.
- Durable processing state is needed to avoid duplicate derivation after retries.

### Assumptions Requiring Approval or Discovery
- Exact source-storage admission policy.
- Whether active retrieval should use a current-derivation filter, vector/index deletion, or both.
- Whether unchanged chunks may be reused after append without changing observable item identity/admission behavior.
- How a consolidated record with multiple document sources is represented in the result schema.

### Repository Adaptation Rule
The agent must determine concrete implementation locations from the actual repository. The plan does not prescribe module names or file paths unless they are part of the approved external contract.

---

## 5. Implementation Specification

### Task 1: Implement the Document Source-Storage Admission Boundary

#### Intent
Allow a document container to be retained only under an explicit governance decision without turning documents into a new semantic memory class.

#### Required Capability or Behavior
- Validate bank/subject authorization, `doc_id`, source bounds, event-time bounds, document metadata bounds, item metadata policy, and configured source-retention policy.
- Apply the owner-approved document source-storage admission rule before persisting or decrypting source for processing.
- Keep document admission separate from category admission for each derived record.
- Emit a content-free accepted/rejected decision for later audit integration.
- Reject unsupported source-retention-disabled configurations rather than silently losing prior text.
- Treat instruction-like source text, document metadata, and context as untrusted data, not system/model instructions.
- Keep document metadata and item-level metadata separate under the approved split contract.

#### Architectural Responsibility
A document-domain admission service adjacent to, but not inside, the existing category/admission engine.

#### Required Changes
1. Implement the approved source-container validation and decision contract.
2. Invoke existing item category/admission checks unchanged for every derived candidate.
3. Define structured errors and retryability for admission rejection versus infrastructure failure.
4. Add tests proving a document cannot bypass PR-3 or PR-5.

#### Implementation Constraints
- No sixth semantic category.
- No new episodic type.
- No arbitrary metadata map without the approved contract.
- No raw source or metadata in rejection logs.

#### Expected Result
A document may be stored only under the approved source policy, while every extracted record still passes existing memory admission.

### Task 2: Carry Persisted Chunks Through Extraction and Publication

#### Intent
Use the existing extraction and verification pipeline while preserving exact document provenance.

#### Required Capability or Behavior
- Select the source revision, approved event time, document-level context, and persisted chunks for the operation.
- Feed chunk text as `source_text` and approved event time as temporal input to extraction and verification.
- Carry document ID, revision ID, chunk ID, event time, and operation/derivation-attempt identity through verified candidates and consolidation.
- Preserve all contributing chunk links when consolidation merges candidates.
- Keep `context` bounded and descriptive, keep document metadata untrusted, and map `evidence_ref` only to the caller's external provenance.
- Persist derived items with independent IDs and direct lineage, applying document-level context under the approved PR-10 policy.
- Make successful leaf records queryable before MemTree/index maintenance completes.

#### Architectural Responsibility
Existing write/extraction/consolidation pipeline plus the document provenance adapter.

#### Required Changes
1. Extend internal candidate/canonical envelopes with document provenance.
2. Map persisted document chunks to extraction inputs without reusing transient IDs ambiguously.
3. Persist links and source references during item publication.
4. Preserve span verification and snapshot/gist rules.
5. Add leaf-first publication and multi-chunk consolidation tests.

#### Implementation Constraints
- Do not copy raw source into plaintext item columns.
- Do not set `source_ref = doc_id`.
- Do not require one direct document link when consolidation has multiple sources.
- Do not pass document metadata or context to an extractor as instructions or trusted system text.
- Do not block leaf publication on ancestor refresh.

#### Expected Result
Each derived record can identify its direct source chunk or resolve lineage through its source records, and normal extraction behavior remains intact.

### Task 3: Implement Native Append and Replace Publication

#### Intent
Apply the approved update semantics without deleting old source or derived history.

#### Required Capability or Behavior
- Append to an unused `doc_id` creates the first document revision under the approved policy.
- Append to an existing document uses the expected revision and creates a new immutable cumulative source revision.
- Preserve submitted append boundaries as chunks/provenance even when extraction reuses unchanged chunks.
- Replace uses the expected revision and creates a new source revision rather than mutating or deleting the old one.
- A new derivation attempt publishes new item IDs; old item IDs and temporal history remain.
- Only a fully successful, coherent derivation becomes the document's current active derivation.
- Stale records remain historical/readable by authorized direct inspection but do not appear in ordinary current recall.
- Record-level supersession uses existing discrete/continuous rules; document replacement does not invent a blanket temporal update rule.
- A failed new attempt leaves the prior current derivation active and records the failure for recovery.

#### Architectural Responsibility
Document write orchestration and existing publication/temporal/index owners.

#### Required Changes
1. Implement state transitions for pending, processing, published, and failed attempts.
2. Use idempotent operation/attempt identities to make retries safe.
3. Atomically switch the current derivation only after required records and links are durable.
4. Retire stale active lexical/dense entries and refresh affected summaries.
5. Add append/replace recovery and regression tests.

#### Implementation Constraints
- No destructive replacement.
- No last-write-wins behavior.
- No mixed current derivation across revisions.
- No deletion of old vectors/records when an eligibility filter is sufficient; if index rows are removed, treat them as derived and rebuildable.
- Do not re-run admission merely because a retry replays the same operation.

#### Expected Result
Successful replace/append exposes only the new derivation as current, while all prior revisions and records remain recoverable and historical.

### Task 4: Implement Stored-Document Reprocess and Recovery

#### Intent
Allow Clio to re-extract retained source without requiring the caller to submit it again.

#### Required Capability or Behavior
- Reprocess reads an authorized stored source revision and chunks.
- Reprocess creates a new derivation attempt, not a new source revision unless the approved contract explicitly says otherwise.
- The new attempt uses the current approved mission/admission policy and records that policy version.
- Prior derivation attempts, decisions, corrections, discards, and temporal history remain bound to their original records/revisions.
- Manual curation decisions are not copied to unrelated new item IDs automatically.
- A failed or interrupted reprocess leaves the last successful current derivation active and is resumable/retryable.
- Replaying the same reprocess idempotency key does not create duplicate attempts or records.

#### Architectural Responsibility
Document recovery orchestration using the Phase 900611 processing state.

#### Required Changes
1. Add an internal reprocess request and durable attempt identity.
2. Resume or retry from stored source/chunks and the last durable step.
3. Publish atomically after a complete successful attempt.
4. Add tests for mission change, failure, retry, duplicate delivery, and curation preservation.

#### Implementation Constraints
- No caller source resubmission requirement for reprocess.
- No source deletion before a replacement attempt succeeds.
- No silent reuse of old admission decisions when policy changed.
- No public tool name in this phase.

#### Expected Result
A stored document can be reprocessed safely, and an unsuccessful attempt cannot replace the last known-good derivation.

### Task 5: Project Document Provenance Through Recall

#### Intent
Let callers use document identity and source-chunk references without exposing source text or inventing provenance.

#### Required Capability or Behavior
- Direct document-derived hits expose `doc_id`, source revision ID, and originating chunk references as bounded metadata.
- Indirect consolidated hits expose only provenance that can be resolved unambiguously under the approved result contract.
- If one record resolves to multiple documents/revisions, return an explicit multi-source shape rather than choosing one silently.
- Recall does not return raw document source text; authorized source fetch belongs to Phase 900620.
- A document with zero admitted records does not become a synthetic recall hit unless the approved zero-result contract explicitly requires it.
- Existing bank, time, domain, budget, rerank, co-activation, and explicit-call semantics remain unchanged.

#### Architectural Responsibility
Retrieval result projection and document provenance resolver.

#### Required Changes
1. Extend result metadata with bounded document provenance.
2. Resolve direct and indirect lineage without decrypting full source for ranking.
3. Ensure optional chunk references count against any configured response budget.
4. Add retrieval, multi-source, zero-result, bank-isolation, and source-non-disclosure tests.

#### Implementation Constraints
- Do not inject raw source or `context` into model composition automatically.
- Do not change ranking because a document link exists.
- Do not claim source verification from `doc_id`.
- Do not cross banks while resolving lineage.

#### Expected Result
Recall returns useful document references while preserving truth, privacy, budget, and provenance boundaries.

### Task 6: Cross-Cutting Verification and Evidence

#### Intent
Prove the full native document write/retrieval lifecycle, including failure and recovery behavior.

#### Required Capability or Behavior
- Unit, contract, integration, end-to-end, regression, security, and failure-mode tests cover the approved lifecycle.
- Tests run against SQLite and PostgreSQL.
- Tests cover direct and consolidated provenance, zero-result documents, append/replace races, reprocess, stale-index retirement, and MemTree refresh.
- Existing workspace checks and the required coverage procedure pass.
- Every created/refactored Rust file remains at or below 450 lines and meets the per-file function/line floors.

#### Architectural Responsibility
Owning crates test their own boundaries; the phase exit aggregates evidence.

#### Required Changes
1. Add tests at extraction, store, publication, retrieval, index, and MemTree boundaries.
2. Add an end-to-end native document fixture with at least two revisions and multiple chunks.
3. Add failure injection around extraction, admission, publication, index retirement, and reprocess.
4. Record known baseline failures separately; do not weaken or misattribute them.
5. Run `make coverage` and verify every reported Rust file.

#### Implementation Constraints
- Do not use a separate validation-only phase; this phase carries its own evidence.
- Do not claim success from unit tests alone.
- Do not hide backend-specific behavior.
- Do not count region coverage as a substitute for the mandated floors.

#### Expected Result
The phase has executable evidence for native preservation, current-derivation coherence, recovery, retrieval provenance, and regression safety.

### Implementation Freedom
The agent may choose internal orchestration structure, durable state representation, index-retirement mechanism, and test placement provided that observable semantics, security, and acceptance criteria remain fixed.

---

## 6. Agent Execution Rules

### Allowed Actions
- Inspect and modify document write, extraction, consolidation, publication, retrieval, index, MemTree, and test components required for the lifecycle.
- Add internal document operations and provenance types.
- Implement local refactoring needed to keep responsibilities focused and Rust files within 450 lines.
- Reuse existing admission, temporal, audit-event, encryption, and retrieval mechanisms.

### Forbidden Actions
- Start before the approval and Phase 900611 gates are satisfied.
- Expose public tools or edit command ownership.
- Implement destructive replacement.
- Reuse `evidence_ref` as a document key.
- Bypass category/admission/span verification.
- Return raw source from ordinary recall.
- Add file/attachment/provider behavior.
- Introduce a new category, episodic type, source-retention mode, or unrelated dependency.
- Delete/bypass tests or claim completion without evidence.

### Agent Decision Boundary
The agent may decide:
- Internal derivation state representation.
- Index retirement by deletion, disabling, or retrieval eligibility projection when behavior is equivalent.
- Delta append optimization details when observable semantics remain unchanged.
- Test organization and helper placement.

The agent must request approval for:
- Any new source-storage admission policy.
- Changing active-derivation or curation semantics.
- Returning source text from recall.
- A public operation name or binding.
- Destructive replacement or source deletion.
- Changes to existing admission, temporal, ranking, or category rules.

### Mandatory Stop Conditions
Stop and report if:
- The source-storage admission policy is unresolved.
- Phase 900611 cannot represent the required source ownership or lineage.
- A successful attempt cannot be published without exposing mixed old/new current state.
- Existing extraction or retrieval architecture requires an unapproved structural rewrite.
- Source text would be logged, returned by recall, or stored outside the encryption boundary.
- Correctness cannot be demonstrated on both backends.

---

## 7. Security Constraints

### Required Controls
- Bank and subject authorization gate every document read, write, reprocess, and source use.
- `doc_id` is never proof of access.
- Source and chunks remain encrypted and are treated as untrusted data.
- Source-storage admission runs before durable retention.
- Derived records pass existing category and admission gates.
- Provenance results expose IDs/hashes/chunk references, not raw source, by default.
- Operation and failure logs contain IDs, state, counts, and error codes only.

### Sensitive Data Rules
- Never log raw document source, chunks, decrypted metadata, or extractor prompts containing source text.
- Never send source to a hosted extractor unless the existing source-egress policy authorizes that data class.
- Never treat document text or metadata as model/system instructions.
- Never use content hashes or revision IDs as authorization tokens.
- Never copy source text into telemetry, sync, or index diagnostics.

### Security Acceptance Conditions
- Cross-bank append/replace/reprocess/retrieval fails without existence leaks.
- Source text containing a secret or instruction cannot alter schema/admission or appear in logs.
- Recall never returns raw source through document provenance fields.
- A failed operation cannot expose an unauthorized partial revision.
- Old and new derivations cannot be mixed under one current revision after a partial failure.

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
| T900615-01 | Create a document and extract from multiple chunks | Items publish with exact direct revision/chunk links |
| T900615-02 | Consolidate candidates from two chunks | Both contributing links survive; no provenance is invented |
| T900615-03 | Snapshot contains an entity/number/date | Verification uses document chunk `source_text` and passes/refuses normally |
| T900615-04 | Derived candidate is below admission threshold | No derived item publishes; document zero-result policy is applied and recorded |
| T900615-05 | Append to an unused `doc_id` | First revision is created under the approved policy |
| T900615-06 | Append to an existing document with current expected revision | New cumulative revision/derivation becomes current |
| T900615-07 | Concurrent append with stale expected revision | Retryable conflict; no unseen text is lost |
| T900615-08 | Native replace with a changed source | New items become current; old revisions/items remain historical |
| T900615-09 | Replace extraction fails after revision creation | Old current derivation stays active; failed attempt is resumable |
| T900615-10 | Delta append reuses unchanged chunks | Observable document/record semantics match full re-extraction |
| T900615-11 | Reprocess the same stored source | New attempt runs without caller resubmission; duplicate idempotency key is a no-op |
| T900615-12 | Reprocess under a changed mission | New decisions use the new policy; old decisions remain attributable |
| T900615-13 | A corrected/discarded old item is reprocessed | Decision stays with the old record; it is not copied to a new ID |
| T900615-14 | Retrieve a direct document-derived item | `doc_id`, revision, and chunk references appear as bounded metadata |
| T900615-15 | Retrieve an indirect/multi-source consolidated item | Explicit resolved lineage; no false single-document claim |
| T900615-16 | Zero-admission persistent document | Visible only through the approved document inspection policy, not synthetic recall |
| T900615-17 | Replace retires stale lexical/dense entries | Ordinary recall returns only the new current derivation |
| T900615-18 | Run the lifecycle on SQLite and PostgreSQL | Same logical outcomes and conflict behavior |
| T900615-19 | Extract relative dates with an explicit event time and with unset | Explicit time anchors relative dates; unset yields unknown temporal output rather than a fabricated date |
| T900615-20 | Document-level context and document metadata contain instruction-like text | Both are treated as untrusted data and cannot override extraction schema, category, or admission |
| T900615-21 | Document metadata and item-level metadata are both present or one is absent | Each follows the approved split; neither is silently copied into the other |

### Negative Testing
Verify that:
- Invalid/stale revision writes are rejected.
- Unauthorized bank/subject actions are blocked.
- Document containers cannot bypass item admission.
- Reprocess cannot publish after a failed attempt.
- Raw source does not appear in logs/errors/recall.
- Document metadata or context cannot act as an instruction or bypass admission.
- Old history is not deleted by replace or stale-index retirement.
- Existing non-document writes and retrieval remain unchanged.

### Verification Rule
Implementation claims must be supported by real test output, runtime transcripts, index/recall inspection, and backend-parity evidence. The phase must include the required coverage gate rather than deferring it to another phase.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-900615-01 | Document source storage is governed separately while every derived record still passes existing admission | T900615-03, T900615-04 | Admission/security test output |
| AC-900615-02 | Extraction/publication preserves exact direct chunk and resolved consolidated provenance | T900615-01, T900615-02, T900615-14, T900615-15 | Lineage and retrieval evidence |
| AC-900615-03 | Append/replace are revision-checked, recoverable, and retryable on conflict | T900615-05–09 | Concurrency/failure output |
| AC-900615-04 | Native replace preserves old revisions/records and exposes only a coherent new current derivation | T900615-08, T900615-09, T900615-17 | History, recall, and index evidence |
| AC-900615-05 | Stored-source reprocess works without resubmission and preserves prior curation/history | T900615-10–13 | Reprocess transcripts and idempotency output |
| AC-900615-06 | Zero-admission behavior follows the approved policy without synthetic memory bypass | T900615-04, T900615-16 | Requirement and zero-result test evidence |
| AC-900615-07 | Recall exposes bounded document provenance but no raw source | T900615-14–16, security inspection | Retrieval/security evidence |
| AC-900615-08 | SQLite and PostgreSQL satisfy the same document lifecycle contract | T900615-18 | Dual-backend output |
| AC-900615-09 | Existing extraction, admission, temporal, PR-9, and retrieval behavior remains intact | Regression suite | Test output |
| AC-900615-10 | Every created/refactored Rust file is ≤450 lines and meets per-file function/line coverage floors | Size inspection and `make coverage` | Size list and coverage report |
| AC-900615-11 | Event time is used for temporal extraction and maps to Clio temporal fields under the approved contract | T900615-19 | Temporal extraction evidence |
| AC-900615-12 | Document-level context and metadata remain untrusted, bounded, and separate from item metadata | T900615-20, T900615-21 | Security and metadata split evidence |

### Definition of Done
- [ ] Approval and Phase 900611 dependencies are satisfied.
- [ ] All in-scope behavior is implemented.
- [ ] All acceptance criteria pass.
- [ ] Required tests pass on SQLite and PostgreSQL.
- [ ] No unauthorized changes were introduced.
- [ ] Existing behavior remains intact.
- [ ] Security checks pass.
- [ ] Documentation is updated where required.
- [ ] Evidence is collected.
- [ ] Verification is completed.
- [ ] Required approval is obtained.

### Completion Evidence
- Approved source-admission and derivation-state decisions.
- Write, extraction, publication, retrieval, index, and MemTree change summary.
- End-to-end two-revision/multi-chunk transcript.
- Concurrency, reprocess, zero-result, provenance, and security output.
- SQLite/PostgreSQL parity output.
- Rust file-size inventory and per-file coverage report.
- Known limitations and deferred portability/erase/sync/tool work.

---

## 10. Failure Handling and Recovery

### Expected Failure Modes

| Failure | Detection | Recovery |
|---------|-----------|----------|
| Source-storage admission rejects input | Structured decision | Do not persist/process source; return content-free reason |
| Extraction or verification refuses | Existing refusal result | Keep prior current derivation; record failed attempt |
| Admission rejects every candidate | Zero-result outcome | Apply approved document persistence policy; do not fabricate memory records |
| Item publication fails midway | Durable attempt state | Resume idempotently or mark failed; never switch current pointer early |
| Index retirement fails | Maintenance/index error | Keep explicit revision eligibility so stale rows are not actively returned; retry cleanup |
| MemTree refresh fails | Dirty-path state | New leaves remain queryable; existing maintenance recovery handles ancestors |
| Reprocess is interrupted | Pending/processing attempt | Resume from stored source and durable step; no duplicate attempt |
| Concurrent append/replace | Expected-revision conflict | Return retryable conflict; caller refreshes and retries |
| Provenance is ambiguous | Resolver validation | Omit/return explicit multi-source shape; never choose a document silently |

### Rollback Strategy
Disable new document write exposure while preserving the Phase 900611 schema and immutable revisions. Failed attempts remain non-current and can be retried or explicitly discarded under an approved operations policy. Never roll back by deleting historical records or source revisions.

### Partial Completion Policy
If extraction works but retrieval provenance, index retirement, reprocess recovery, or one backend is incomplete, do not claim the phase complete. Keep public document tools unavailable and record the exact supported boundary.

---

## 11. Traceability

| Parent Requirement | Implementation Task | Verification | Acceptance Criterion |
|--------------------|---------------------|--------------|-----------------------|
| §9 / Phase 900611 native gate | Preconditions | Approval/dependency review | AC-900615-01 |
| PR-3 / PR-5 / §4.1–§4.2 | Task 1 | T900615-03, T900615-04 | AC-900615-01 |
| PR-4 / FR-4 / FR-5 | Tasks 1–2 | T900615-01–03 | AC-900615-02 |
| PR-6 / FR-12 | Task 3 | T900615-08, T900615-09 | AC-900615-04 |
| PR-8 / FR-15 | Tasks 1, 3, 4 | State/audit-handoff inspection | AC-900615-03, AC-900615-05 |
| PR-9 / FR-3 / NFR-2 | Tasks 2–3 | Leaf-first publication test | AC-900615-04 |
| PR-10 / FR-34 / FR-35 | Tasks 2, 5 | T900615-14, T900615-15 | AC-900615-02, AC-900615-07 |
| §4.5 / FR-17 retrieval | Task 5 | T900615-14–17 | AC-900615-07 |
| NFR-7 dual backend | Tasks 2–6 | T900615-18 | AC-900615-08 |
| Event time / temporal extraction | Tasks 1–2 | T900615-19 | AC-900615-11 |
| Metadata split and untrusted context/metadata | Tasks 1–2 | T900615-20, T900615-21 | AC-900615-12 |
| Native preservation policy | Tasks 3–4 | T900615-08–13 | AC-900615-04, AC-900615-05 |

Required chain:

```text
Requirement → Capability → Implementation → Test → Evidence
```

Every acceptance criterion must be traceable.

---

## 12. Phase Exit Contract

### Outputs Produced
- Governed internal document write lifecycle with native append/replace.
- Durable document revision/chunk provenance through extraction, consolidation, publication, and recall.
- Current-derivation publication, stale-index retirement, and MemTree refresh integration.
- Stored-source reprocess/recovery with curation/history preservation.
- Zero-result and multi-source provenance behavior.
- Dual-backend, security, failure, and coverage evidence.

### Guarantees Provided to Downstream Phases
After this phase is accepted:
- Phase 900620 can bind approved document operations to a coherent native lifecycle.
- Phase 900625 can audit, export, erase, and synchronize stable document mutations and lineage.
- Recall results carry document provenance without exposing source text.
- Native replacement preserves history and never silently mixes old/new current derivations.
- Reprocess can recover from stored source without caller resubmission.

### Known Limitations
- No public document tools or CLI commands yet.
- Audit/inspect UX, export/import, full compliance erasure, and sync are not integrated here.
- Hindsight destructive replacement and provider import are excluded.
- File/attachment ingestion, tag filtering, tag-based visibility scoping, custom observation scopes, `entities`/`resolve_entities`, provider fact-type names, item-level arbitrary metadata, and source-retention-disabled behavior are excluded or deferred.
- The 3–4 day estimate assumes stable Phase 900611 contracts and excludes approval/review latency and unrelated baseline repair.

### Downstream Prerequisites
- Phase 900620 is strictly blocked on normative tool-name and CLI ownership approval; no schema, parser, or binding work starts before that gate.
- Phase 900625 may rely on stable revision, derivation-attempt, current-derivation, event-time, context, metadata, and direct/indirect lineage contracts.
- Any provider adapter must translate destructive provider replacement and provider input semantics explicitly, ship fixture or contract tests, and must not redefine native Clio replacement.

### Final Status
BLOCKED

The current status is `BLOCKED` until the document approval gate and Phase 900611 are accepted. After implementation, replace this line only with evidence-backed `PASS`, `PASS WITH DOCUMENTED LIMITATIONS`, or `FAILED`.

### Verification Sign-Off
- Implementer: [TBD]
- Verifier: [TBD]
- Human Approver: required for source-storage admission and native derivation semantics
- Date: [TBD]

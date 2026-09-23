# Hindsight document identity and conditional Clio-native document proposal

## Executive conclusion

This is a **research and conditional planning note**, not an approved implementation plan. It uses **Clio-native document lifecycle** to mean a preservation-oriented Clio design and **Hindsight provider parity** to mean reproducing Hindsight's destructive replacement behavior. Those are separate approval tracks.

Hindsight calls this field `document_id`; `doc_id` is primarily the command-line spelling, `--doc-id`. It is a caller-supplied identity for a document container within a memory bank, not the identity of an extracted memory record.

The effective Hindsight key is `(bank_id, document_id)`. Reusing that key with the default `update_mode="replace"` removes the previous document and its extracted memories before ingesting the replacement. `update_mode="append"` requires a document ID, combines the new text with the existing text, and reprocesses the resulting document.

A future Clio `doc_id` should therefore model a document lifecycle, not provenance alone. It must define the source container, update semantics, derived-memory ownership, source and chunk retention, retrieval, and deletion. Clio's existing `evidence_ref` cannot silently acquire those semantics because Clio requires non-destructive supersession and compliance-grade erasure through separate paths.

### Approval gate

No implementation phase below may start until one of the following is recorded:

1. Migration rehearsal demonstrates that document-container parity is required, satisfying the trigger in requirement section 9.
2. An owner explicitly amends requirement section 9 to authorize a Clio-native document track without that rehearsal result.

The approval must also select either native preservation or provider-faithful destructive replacement. Native preservation is the default planning assumption in this note; destructive replacement requires a separate requirement amendment and phase. All proposed operation names are provisional until the normative tool catalog is amended. The headline implementation effort is a **12-day aggressive lower bound**; the recommended planning range is **15–24 days** for single-host document scope, plus **2–4 days** when document multi-host sync is claimed, excluding baseline repair, migration rehearsal, and roadmap review latency.

Requirement §9 uses the phrase “bulk operations” without defining its scope. The evidence below establishes one-document cascade deletion, which Hindsight calls “delete in bulk,” and does not establish a multi-document delete request. Before implementation, the owner must record whether one-document cascade deletion satisfies §9 “bulk operations,” or whether a separate multi-document contract and phase are required. The conditional native plans implement one-document lifecycle only and do not expose a multi-document API.

Current Hindsight 0.10 public documentation adds input semantics that were not in the original snapshot: an event `timestamp` that anchors relative temporal extraction, a `context` value injected into the extraction prompt, `metadata` injected into the prompt and returned with recalled memories, explicit `entities` and `resolve_entities` controls, batch ingestion, and async `operation_id` idempotency. Any provider-informed native contract must map or explicitly defer these behaviors rather than silently omit them.

## Terminology and boundaries

| Term | Meaning |
|---|---|
| Hindsight `document_id` | Caller-supplied, bank-scoped document-container key. |
| Hindsight `--doc-id` | CLI spelling of the same concept. |
| Hindsight memory unit ID | Separate identity for one extracted world, experience, or observation record. |
| Clio `evidence_ref` / `source_ref` | Stable source or provenance identity for a memory item. It does not own or replace source content. |
| Proposed Clio `doc_id` | A future source-document lifecycle key with explicitly defined update, retrieval, and deletion behavior. This note assumes native preservation unless destructive parity is separately approved. |
| Proposed `document_*` operation names | Provisional handles for planning discussion only, not approved additions to Clio's normative tool catalog. |

A `doc_id` is not a `context` value. It is also not the source-span verification text (`source_text`). It may accompany a document and its derived records, but it does not determine category, epistemic truth, confidence, or source span.

## Hindsight document lifecycle

### 1. Creation and scope

A caller supplies `document_id` on retained content:

```python
client.retain(
    bank_id="my-bank",
    content="Alice presented the Q4 roadmap...",
    document_id="meeting-2024-03-15",
)
```

The official client model makes the field optional at line 37 of the generated model. When omitted, Hindsight generates a random UUID, so the same source is not naturally idempotent across repeated requests. [Retain API](https://hindsight.vectorize.io/developer/api/retain#document_id), [`MemoryItem` model, L37](https://github.com/vectorize-io/hindsight/blob/f00ad1fe993a86779682067b8a0e9883aba580d2/hindsight-clients/python/hindsight_client_api/models/memory_item.py#L37)

Hindsight's tests describe the ID as unique only within a bank and use `(document_id, bank_id)` as the document key at lines 125-126. The same text may therefore identify unrelated documents in separate banks. All document lookup and mutation must remain bank-scoped. [Document delete test, L5](https://github.com/vectorize-io/hindsight/blob/f00ad1fe993a86779682067b8a0e9883aba580d2/hindsight-system-tests/tests/test_13_delete_document.py#L5), [document key and bank-scoped deletion, L125-L157](https://github.com/vectorize-io/hindsight/blob/f00ad1fe993a86779682067b8a0e9883aba580d2/hindsight-api-slim/tests/test_document_tracking.py#L125-L157)

### 2. Replace is the default

Calling retain again with the same bank and document ID under the default `update_mode="replace"` causes Hindsight to:

1. Remove the existing document container.
2. Remove memories associated with that document.
3. Store the replacement source text.
4. Extract a new set of memories.

This makes the document key a replacement and ingestion boundary. It does not preserve the identities of memories derived from the previous document revision. The replacement test verifies at lines 255-286 that old content disappears, while the upsert test verifies at lines 47-84 that old and replacement memory-ID sets are disjoint. [Retain update modes](https://hindsight.vectorize.io/developer/api/retain#update_mode), [replace default, L255-L286](https://github.com/vectorize-io/hindsight/blob/f00ad1fe993a86779682067b8a0e9883aba580d2/hindsight-api-slim/tests/test_retain_append_mode.py#L255-L286), [upsert and disjoint IDs, L47-L84](https://github.com/vectorize-io/hindsight/blob/f00ad1fe993a86779682067b8a0e9883aba580d2/hindsight-api-slim/tests/test_document_tracking.py#L47-L84)

### 3. Append requires a document identity

`update_mode="append"` requires `document_id`, as verified at lines 172-176. Hindsight combines the new content with the existing document text and reprocesses the resulting document. This is not an alias for adding an unrelated memory item: the document remains the grouping and reprocessing boundary. Hindsight's delta processing can avoid re-extracting unchanged chunks, and appending to a newly supplied document ID behaves like an ordinary retain when no prior document exists, as verified at lines 137-165. Append is rejected when verbatim source storage is disabled because the prior text cannot be reconstructed safely, as verified at lines 147-153. [Retain update modes](https://hindsight.vectorize.io/developer/api/retain#update_mode), [append requirements and new-document behavior](https://github.com/vectorize-io/hindsight/blob/f00ad1fe993a86779682067b8a0e9883aba580d2/hindsight-api-slim/tests/test_retain_append_mode.py#L137-L176), [append rejection without stored text](https://github.com/vectorize-io/hindsight/blob/f00ad1fe993a86779682067b8a0e9883aba580d2/hindsight-api-slim/tests/test_store_document_text.py#L147-L153)

### 4. Source, chunks, and extracted memories

A Hindsight document can own:

- Original source text.
- A content hash.
- Source chunks.
- Document metadata and timestamps.
- Zero or more extracted memory records.

Each extracted memory has its own memory-unit ID and records the source document and originating chunk. Recall results expose `document_id` as the document a fact belongs to and may return chunks for context expansion. [Documents API](https://hindsight.vectorize.io/developer/api/documents), [Recall API](https://hindsight.vectorize.io/developer/api/recall), [Retain architecture](https://hindsight.vectorize.io/developer/retain)

Consolidated observations can have relationships to source records without carrying a direct document ID. Hindsight reports their count separately from facts that directly carry a document ID at lines 155-158. This distinction matters if Clio copies Hindsight's projections: not every derived record can be assumed to have a direct container reference. [Retain architecture](https://hindsight.vectorize.io/developer/retain), [observation counts, L155-L158](https://github.com/vectorize-io/hindsight/blob/f00ad1fe993a86779682067b8a0e9883aba580d2/hindsight-api-slim/tests/test_document_chunks_and_reprocess.py#L155-L158), [retain input and update-mode types, L120-L134](https://github.com/vectorize-io/hindsight/blob/f00ad1fe993a86779682067b8a0e9883aba580d2/hindsight-api-slim/hindsight_api/engine/retain/types.py#L120-L134)

### 5. Document lookup

Callers can retrieve a document's stored source and metadata through:

```text
GET /v1/default/banks/{bank_id}/documents/{document_id}
```

A document response can include `id`, `bank_id`, `original_text`, `content_hash`, `memory_unit_count`, fact-type counts, and timestamps. Source and chunk listing are separate document operations. [Documents API](https://hindsight.vectorize.io/developer/api/documents)

Raw source and chunk storage is configurable in current Hindsight releases. The storage test defines that behavior at lines 2-7, verifies default retention at lines 118-141, and verifies null source text when storage is disabled at lines 76-104. Therefore, “original text is retained” is a supported Hindsight capability, not an unconditional storage guarantee in every configuration. A Clio contract must choose whether source retention is mandatory, configurable, or disabled for privacy reasons. [storage flag, L2-L7; default retention, L118-L141; disabled storage, L76-L104](https://github.com/vectorize-io/hindsight/blob/f00ad1fe993a86779682067b8a0e9883aba580d2/hindsight-api-slim/tests/test_store_document_text.py#L2-L104)

### 6. Deletion

Callers delete one document through:

```text
DELETE /v1/default/banks/{bank_id}/documents/{document_id}
```

Hindsight removes the document and all memories extracted from it, and reports `memory_units_deleted`. The evidence establishes cascade deletion of all memories belonging to one document. No cited source was found for deleting multiple named documents in one request. [Documents API](https://hindsight.vectorize.io/developer/api/documents), [Document delete test](https://github.com/vectorize-io/hindsight/blob/f00ad1fe993a86779682067b8a0e9883aba580d2/hindsight-system-tests/tests/test_13_delete_document.py)

Clio should therefore describe this as **cascade deletion of one document's derived memories**. It should not use “bulk delete” to imply a documented multi-document operation unless Clio separately specifies one.

### 7. Documents with no extracted memories

A document can remain persisted when extraction produces zero memory records, as verified at lines 335-370. It remains available through the document API, but it cannot be found by recall because recall searches extracted memories rather than documents. [Retain architecture](https://hindsight.vectorize.io/developer/retain#when-a-mission-excludes-everything-in-a-document), [zero-fact persistence, L335-L370](https://github.com/vectorize-io/hindsight/blob/f00ad1fe993a86779682067b8a0e9883aba580d2/hindsight-api-slim/tests/test_document_tracking.py#L335-L370)

Clio must decide whether document admission is a separate governed operation. Under the current requirements, creating a source container that produces no admissible memory must not become an unreviewed long-term storage bypass.

### 8. Additional lifecycle operations relevant to parity

These behaviors should be explicitly included, adapted, or deferred before Clio claims practical parity:

- **Document listing:** Hindsight lists bank-scoped documents with ID-substring search, tag filtering, time-window filtering, pagination, and document metadata. [List documents](https://hindsight.vectorize.io/developer/api/documents#list-documents)
- **Document retagging:** document tags replace the prior tag set rather than merging with it. Retagging can invalidate consolidated observations derived from the document's memories and requeue co-sourced memories for consolidation. [Update document](https://hindsight.vectorize.io/developer/api/documents#update-document)
- **Document metadata:** retain-time metadata is captured in document parameters and surfaced through document get/list operations. Item-level metadata is separately stored and returned with memories. [Retain metadata](https://hindsight.vectorize.io/developer/api/retain#metadata), [document tracking test](https://github.com/vectorize-io/hindsight/blob/f00ad1fe993a86779682067b8a0e9883aba580d2/hindsight-api-slim/tests/test_document_tracking.py)
- **Observation scopes:** Hindsight permits combined, shared, per-tag, all-combination, and custom observation-consolidation scopes. Observations derived under those scopes are reported separately from directly extracted world and experience records. [Observation scopes](https://hindsight.vectorize.io/developer/api/retain#observation_scopes), [document/chunk test](https://github.com/vectorize-io/hindsight/blob/f00ad1fe993a86779682067b8a0e9883aba580d2/hindsight-api-slim/tests/test_document_chunks_and_reprocess.py)
- **Reprocessing:** Hindsight can reprocess an existing stored document without requiring the caller to resubmit the source. This is the documented recovery path for a document whose mission excluded all facts, and the test verifies the asynchronous operation at lines 168-186. [Retain architecture](https://hindsight.vectorize.io/developer/retain#when-a-mission-excludes-everything-in-a-document), [reprocess operation, L168-L186](https://github.com/vectorize-io/hindsight/blob/f00ad1fe993a86779682067b8a0e9883aba580d2/hindsight-api-slim/tests/test_document_chunks_and_reprocess.py#L168-L186)
- **File ingestion:** each uploaded file becomes a separate document with optional per-file context, document ID, and tags. [File ingestion](https://hindsight.vectorize.io/developer/api/retain#files)
- **Attachments:** inline images and file references can be evidence for particular extracted facts and are retrievable through attachment URLs. This is separate from document-level text and chunk storage. [Images and files](https://hindsight.vectorize.io/developer/retain#images-and-files-in-your-content)
- **Append concurrency:** Hindsight's implementation treats a lost append read-modify-write race as a retryable conflict rather than silently overwriting unseen content at lines 578-590. [Retryable append conflict, L578-L590](https://github.com/vectorize-io/hindsight/blob/f00ad1fe993a86779682067b8a0e9883aba580d2/hindsight-api-slim/hindsight_api/engine/retain/types.py#L578-L590)

Clio's current core model has no corresponding document-metadata, tag, observation-scope, attachment, file-ingestion, or document-reprocess contract: the repository search finds only `items` and `triples` as the relevant durable aggregates and only transient write-path `chunk_id` values. The proposed phases therefore need a parity checklist rather than silently assuming those behaviors are unnecessary.

## Comparison with Clio's current concepts

| Concern | Hindsight | Clio today | Required boundary |
|---|---|---|---|
| Source identity | `document_id`, bank-scoped | `evidence_ref` / `source_ref` | Keep provenance identity separate from document ownership. |
| Descriptive setting | Not the document key | Optional bounded `context` | Never use `context` as a container key or instruction. |
| Source evidence | Original text and chunks | Inline `source_text` for span verification | A document may supply `source_text`, but `doc_id` is not verification text. |
| Extraction output | Memory units with separate IDs | Snapshot plus non-authoritative gist | A document owns a set of independently identified records. |
| Update | Replace is default; append is available | Discrete facts use non-destructive invalidation; continuous values use EMA | Native Clio replacement must preserve history under PR-6; destructive provider replacement requires a separate approval track. |
| Delete | Document deletion cascades to extracted memories | `discard`, invalidation, and compliance crypto-shredding are separate | A document cascade is not automatically a compliance erasure mechanism. |
| Zero-result source | Document persists but recall cannot see it | Admission gates and logs govern long-term writes | Define persistence and audit behavior for zero-admission documents. |
| Cross-bank identity | Not globally unique | Banks are isolation boundaries | Define and enforce `(bank_id, doc_id)` uniqueness. |

## Recommended Clio-native contract

A native Clio design should make the following decisions before implementation:

1. **Identity:** `doc_id` is non-empty UTF-8, unique within a bank, and never implicitly crosses banks.
2. **Ownership:** a document references source revisions, chunks, and zero or more extracted memory records; records keep their own identities. Source revisions are a Clio-native extension: Hindsight exposes the current stored source text rather than a complete revision history.
3. **Modes:** define `replace` and `append` explicitly. Reject either mode when no `doc_id` is supplied. Specify that appending to a previously unused `doc_id` creates the document, while appending is unavailable when verbatim source storage is disabled.
4. **History:** native replacement preserves prior document revisions and derived records, closes or supersedes active derived records under existing temporal rules, and regenerates affected summaries. Destructive replacement is a separate approval track.
5. **Provenance:** each derived record stores `doc_id` plus its source chunk or source-revision reference. `evidence_ref` remains available for the external source record.
6. **Admission and taxonomy:** a document container is a storage and governance operation, not a sixth semantic category or a new episodic type. Document creation must be audited and must not let extracted records bypass category or admission controls. Any representation of documents as a memory category requires schema-change review.
7. **Zero-memory documents:** define whether such documents persist, remain visible in document inspection, and appear in export/import.
8. **Source retention:** native documents retain encrypted source and chunks by default. A configurable non-retention mode remains deferred; if later added, append and source recovery must be rejected or redesigned rather than silently losing prior content.
9. **Retrieval:** recall can return `doc_id` and source-chunk references; callers can fetch authorized document metadata and retained source text.
10. **Deletion:** distinguish repository-level document removal, record invalidation, operations discard, and subject-level compliance erasure. Repository deletion is not automatically compliance erasure. A document cascade must update audit and derived structures coherently.
11. **Concurrency:** use optimistic revision checks or locking for replace and append. A lost append race must produce a retryable conflict, not silently overwrite unseen content.
12. **Import/export:** preserve source revisions, chunks, document references, and configuration-dependent source availability; re-import must be idempotent.
13. **Sync:** synchronize document mutations and record references only where multi-host sync is claimed. Single-host deployments must document omission rather than implement an unused sync path. Synchronization must preserve bank boundaries and use deterministic conflict handling.
14. **Authorization:** bank and subject authorization must gate document reads, source-text reads, updates, and deletion. A `doc_id` is never an authorization token.
15. **Reprocessing and recovery:** define whether an existing stored document can be re-extracted without new caller content, including mission changes, asynchronous behavior, and preservation of curation decisions.
16. **Provider-feature mapping:** explicitly include, adapt, or defer document metadata, tags, observation scopes, append optimization, and verbatim-storage-disabled behavior. File ingestion and attachment-binary handling are out of scope and must not be treated as deferred Clio work. Clio must not claim Hindsight parity for features it omits.

## Selected planning track: native preservation

Hindsight replacement is destructive to the old extracted-memory set. Clio's `PR-6` says ordinary discrete-fact supersession retains history and closes temporal intervals. Therefore, this proposal selects **native Clio preservation** as its planning track; it is not a claim of exact Hindsight replacement parity.

The three policy alternatives are:

- **Native Clio preservation, selected for these phases:** retain old document revisions and derived records, supersede active derived records under existing temporal rules, and regenerate affected summaries.
- **Provider-faithful replacement, not selected:** delete the old document-derived set before ingesting the replacement. This requires a separate requirement amendment and phase.
- **Dual mode, possible later:** preserve history natively while a separately approved Hindsight import operation reproduces destructive provider replacement without weakening native Clio governance.

“Destructive replacement” below means the separately gated provider-parity option, not the behavior included in the native estimate.

## Effort estimate for the native Clio document lifecycle

### Scope of the estimate

This estimate covers a native Clio document-container contract informed by Hindsight, not exact Hindsight replacement parity:

- Bank-scoped document identity and source-revision tracking.
- Replace and append ingestion modes.
- Original-source and chunk persistence, subject to one published Clio storage policy.
- Explicit links from documents and chunks to independently identified memory records.
- Replace-time handling of old derived records without silently weakening Clio's history and erasure rules.
- Document get/list/delete surfaces over CLI and MCP.
- Recall projections for `doc_id` and chunk references.
- Index cleanup or replacement for old derived records.
- Audit, export/import, sync, and compliance-erasure integration.
- Schema convergence, both storage backends, tests, and operator documentation.

It does **not** estimate a complete Hindsight provider adapter. Document upload and ETL are also out of scope: Clio does not own file-upload transport, file parsing or conversion, OCR, transcription, remote file storage, or attachment-binary ingestion. Callers supply source text through the native document operation; existing Clio extraction and admission then handle that supplied text. This note also excludes model-quality tuning, new embedding models, a new service, distributed consensus, or a general rewrite of Clio's temporal fact model.

### Current Clio baseline

Clio already has building blocks that reduce the estimate:

- Memory items have independent IDs, bank and subject ownership, provenance, snapshot/gist separation, and temporal fields in `crates/clio-types/src/item.rs` and `sql/001_core.sql`.
- SQLite and PostgreSQL implement a shared storage contract in `crates/clio-store/src/store.rs`, with separate backend drivers.
- The write path already creates transient extraction chunks and associates candidates with chunk IDs in `crates/clio-write/src/parallel.rs` and `crates/clio-write/src/consolidate.rs`; those chunks are not a persisted document lifecycle.
- Export, sync, audit, and compliance-erasure frameworks already exist and can carry a new first-class entity once its contract is defined.
- MCP and CLI binding patterns are established.

Clio currently has no `doc_id`, `document_id`, document table, document-chunk table, persisted document-source API, or document cascade operation. `source_ref` is an optional provenance field, and transient `chunk_id` values are not document-container references. The implementation therefore adds a new aggregate rather than exposing an existing hidden container.

### Proposed roadmap phases — conditional approval draft

These phase titles and boundaries are now recorded as conditional roadmap plans and index entries. All four document phases (900611, 900615, 900620, 900625) are parked at or above the pipeline's 900000 floor, so `next_phase.py` ignores them and `runner.py` rejects them. Phase 900615 depends on 900611; un-park them together or supply the 900611 contract separately before any of them runs. The plans are not approved for implementation, and no phase may start until the approval gate above is satisfied. The provisional `document_*` operation names remain unapproved and have not been added to the normative tool catalog or CLI command-ownership matrix.

The proposal assumes a native Clio document aggregate with bank-scoped `(bank_id, doc_id)` identity. Native replacement preserves prior Clio history. Each phase includes its own implementation, tests, required coverage, and phase-level verification; there is no separate validation or coverage phase. All operation names remain provisional until the normative catalog is amended.

| Proposed phase | Concise scope | Estimate |
|---|---|---:|
| **900611 — Native Document Contract and Persistence** | Define document revisions, chunks, event time, document versus item metadata, and derived-record references; add portable schema, migration, and SQLite/PostgreSQL repository semantics for retain, get, list, append, replace, and repository-level delete. | 3–4 days |
| **900615 — Document Write and Retrieval Lifecycle** | Carry `doc_id`, source-revision, chunk, event-time, context, and metadata references through extraction and publication; return document provenance from recall; preserve old history while retiring stale active index entries on native replacement. | 3–4 days |
| **900620 — Provisional Document Management Tools** | Publish matching CLI and MCP surfaces under pinned revision `2025-11-25`, with approved Core or Additive classification, provisional document retain/replace/append, metadata/source fetch, chunk fetch, and the confirmed user-facing delete workflow. | 3–4 days |
| **900625 — Document Portability, Erasure, and Conditional Sync** | Extend audit, repository-aware compliance-erasure handling, manifest-backed export/import, and multi-host sync where claimed. Single-host deployments document sync omission instead of implementing an unused sync path. | 3–4 days single-host; +2–4 days multi-host |

The aggressive lower bound is **12 person-days**. The recommended planning range is **15–24 person-days** for single-host document scope, plus **2–4 days** when document multi-host sync is claimed, allowing for schema surprises, cross-feature integration, roadmap review, and adversary/remediation cycles. The estimate excludes repair of the unrelated failing baseline test, migration rehearsal, review latency, destructive provider parity, and a Hindsight adapter. Any later Hindsight adapter must ship provider fixture or contract tests before claiming parity.

Phase dependencies:

- Phase 900611 depends on the approval gate and the accepted native `context`/`evidence_ref` contract from phase 100601.
- Phase 900615 follows Phase 900611. Phase 900620 is strictly blocked on the normative catalog and command-ownership approval; no schema, parser, or binding work starts before that gate.
- Phase 900620 also depends on approval of the operation names in the normative tool catalog and CLI command ownership.
- Phase 900625 follows the reference contract from phase 900615 and must coordinate with phase 100606 where context, audit, export, sync, or erasure behavior overlaps.

Not included in these proposed phases:

- Provider-faithful destructive replacement. This would require a separately approved requirement change and phase; a provisional allowance is **3–4 days**.
- A Hindsight `import_provider` adapter. This remains separate provider-ingest work; a provisional allowance is **8–12 days**.
- Document upload and ETL. File intake, parsing, conversion, OCR, transcription, remote file storage, and attachment ingestion are not Clio document-feature responsibilities.
- A configurable source-retention mode. Native documents retain encrypted source and chunks by default.

### Principal risks to the estimate

- **Policy conflict:** Hindsight replacement deletes old derived memories, while Clio `PR-6` preserves superseded discrete facts. This is the largest source of design and test effort.
- **Cross-cutting provenance:** Every extraction, consolidation, retrieval, export, sync, audit, and erase path must agree about which source version and chunk produced a record.
- **Dual-backend migrations:** Existing databases may already contain data that the new aggregate must reference without assigning ambiguous ownership.
- **Atomic replacement:** Replacing source text, derived records, vectors, audit records, and MemTree state requires a recoverable transaction or durable operation journal.
- **Authorization:** `doc_id` must never become an authorization token, and original-source reads may expose more sensitive content than recall results.
- **Current test baseline:** I reproduced one failing workspace CLI test on 2026-09-24: `reindex_dense_confirmed_without_embedder_exits_3` expected exit status 3 but received exit status 0. Repair is outside the document estimate and must be scheduled separately before document-phase validation.
- **Review and approval latency:** roadmap adversary, remediation, approval, migration rehearsal, and requirement-amendment work are outside the implementation-day estimates.

### Estimate confidence

Confidence is **medium** for the Hindsight analysis and **low-medium** for the schedule. The lower bound assumes an experienced implementer, stable repository contracts, prompt approval decisions, and no migration surprises. The recommended 15–24-day range is more appropriate for planning single-host document scope; add 2–4 days when document multi-host sync is claimed.

Before implementation, record both the section-9 approval basis and the selected native-preservation policy. The estimates and dependency order above remain provisional until the migration-rehearsal report and owner decision exist. Destructive Hindsight parity remains a separate approval decision.

## Appendix A — extended parity, investigation, and optional-track checklist

This appendix records the broader investigation requested for unlimited follow-up work. It does not approve additional implementation.

### Parity checklist

| Hindsight behavior | Proposed Clio treatment | Phase home |
|---|---|---|
| Document get/list, including ID search, tags, pagination, and metadata | Include native metadata, listing, and chunk references; Clio-specific tag filtering remains deferred unless a generic tag contract is separately approved. Hindsight tags scope recall visibility; Clio bank/subject authorization remains the native visibility boundary and is not tag-equivalent. | 900611, 900620 |
| Document retagging with observation re-consolidation effects | Include only if Clio adopts document tags; otherwise preserve external tag strings opaquely and do not reproduce Hindsight-specific consolidation behavior. | 900611 |
| Document metadata | Split document metadata from item-level metadata. Define whether document metadata is retained/returned only or also passed to extraction; if passed, treat it as untrusted data with the same encryption and redaction rules as `context`. Item-level arbitrary metadata is deferred unless separately approved. | 900611, 900615, 900625 |
| Retain-time `timestamp` (event time) | Define an event-time field with explicit default and “unset” behavior, map it to extraction temporal anchoring and Clio valid/transaction time, and test relative-date extraction. | 900611, 900615 |
| Retain-time `context` prompt injection | Clio `context` may be supplied as bounded descriptive metadata but MUST NOT be a model instruction. Define how document-level context reaches derived items; do not copy Hindsight's direct prompt-injection behavior without the PR-10 boundary. | 900611, 900615, 100606 |
| `entities` / `resolve_entities` | Defer. Clio does not expose caller-supplied entity resolution controls in native document version one; existing extraction behavior remains authoritative. | Deferred |
| Batch ingestion and async `operation_id` | Clio uses existing `batch` and durable document attempt/idempotency identity. No new async provider API is added. | 900615, 900620 |
| Document response fact-type counts (`world`, `experience`, `observation`) | Do not expose provider fact-type names. Map to Clio taxonomy or defer counts; no Hindsight taxonomy parity claim. | 900611, 900620 |
| Document metadata and observation scopes | Preserve document metadata under the split contract above; adapt observation provenance through Clio's existing consolidation and audit structures; defer custom Hindsight observation-scope modes. | 900611, 900615 |
| Stored-document reprocessing and recovery | Include a native re-extract/recovery operation with explicit handling of mission changes, asynchronous behavior, and prior curation decisions. | 900615 |
| File uploads with one document per file | Out of scope. Clio does not own upload transport, file parsing or conversion, OCR, transcription, or remote file storage. | Out of scope |
| Inline attachments and attachment URLs | Out of scope. Clio does not ingest attachment binaries or serve attachment-specific evidence URLs in native document version one. | Out of scope |
| Delta append and unchanged-chunk optimization | Permit an efficient append implementation, but require identical observable document semantics and conflict behavior. | 900615 |
| Append with verbatim storage disabled | Reject the operation rather than silently discarding prior content. | 900615 |
| Append read-modify-write conflict | Return a retryable conflict rather than overwriting unseen submissions. | 900615 |
| Destructive replacement | Exclude from native phases; handle only through a separately approved provider-parity phase. | Deferred optional track |
| Provider adapter and remote ingestion | Exclude from native phases; handle only through separately approved provider-ingest work. | Deferred optional track |

### Migration-rehearsal protocol, not yet executed

Before invoking section 9 as an implementation trigger, rehearsal should:

1. Use anonymized or synthetic representative Clio databases from both SQLite and PostgreSQL.
2. Import representative Hindsight documents, chunks, metadata, tags, and memory units.
3. Compare native preservation against destructive replacement for history, recall, audit, export, sync, and erasure.
4. Test interrupted replace/append operations, replay behavior, rollback or forward recovery, and duplicate delivery.
5. Record which container behaviors Clio actually needs rather than copying every Hindsight capability.
6. Preserve the rehearsal report as the section-9 evidence or as the reason for deferring implementation further.

### Version and compatibility check

This note uses current Hindsight 0.10 documentation and the pinned `f00ad1f` source snapshot. The 0.10 Retain, Documents, and API-reference pages were rechecked on 2026-09-24. That pass confirmed default replace, append concatenation with delta chunk skipping, one-document cascade deletion, document get/list/chunks/reprocess/tag-update surfaces, and file/attachment behavior. It also surfaced input and response behaviors absent from the original snapshot: event `timestamp`, prompt-injected `context` and `metadata`, `entities` and `resolve_entities`, batch and async `operation_id` retry semantics, tag-based recall visibility scoping, and `world`/`experience`/`observation` fact-type counts. Before implementation, recheck the active Hindsight release again for changes to raw-text configuration, delta append, reprocessing, tag-triggered consolidation, attachments, file ingestion, and observation scopes. Do not assume that a newer release preserves every behavior cited here. Any later Hindsight adapter must ship provider fixture or contract tests before claiming parity.

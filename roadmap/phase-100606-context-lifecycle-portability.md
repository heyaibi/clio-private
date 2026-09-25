# Phase 100606: Context Lifecycle, Retrieval, and Portability

### Attribution
Rounds below record plan authorship; implementation sign-off is in §12.
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | OpenCode (Space Bunny Free) | proposed |
| Developer | r1 | OpenCode CLI (Together . GLM-5.3 Flash High) | done |
| Adversary | r1 | OpenCode CLI (Go . Space Bunny Free Max) | done |
| Adversary | r1 | [TBD] | [TBD] |
| Remediator | r1 | OpenCode CLI (Together . GLM-5.3 Flash High) | done |
| Remedy Approver | r1 | [TBD] | [TBD] |
| Finalize | r1 | [TBD] | [TBD] |
| Remediator | r2 | Command Code (DeepSeek V4 Flash (latest) Max) | done |
| Remediator | r3 | OpenCode CLI (Together . GLM-5.3 Flash High) | done |

**Remediation/follow-up phase 100606** · **Effort:** ~4–6 days · **Status:** Plan ready · **Parent:** requirement.md v1.10 and Phase 100601 native context contract

### Vocabulary (read first) — zero shared moniker

| Term | Meaning in this phase | Must not be confused with |
|------|------------------------|----------------------------|
| **context propagation** | Carrying an already-validated source context through extraction, indexing, retrieval, portability, and audit | Creating a new category or injecting arbitrary text into a model |
| **context-aware lexical match** | Optional retrieval use of bounded context text for matching | Treating a context match as factual proof |
| **retrieval metadata** | Context returned alongside a hit for inspection or downstream policy | Unbudgeted automatic prompt injection |
| **source-span grounding** | Verification of snapshot values against `source_text` | Verification against context |
| **migration-ready bundle** | Portable data that preserves context and evidence references without a provider adapter | A Hindsight-specific export format |

This phase makes context useful after it is stored. It does not create a Hindsight client or provider-specific migration path.

---

## 1. Objective

### Goal
Propagate native source context through extraction, indexing, retrieval, export/import, audit, sync, and erasure while preserving the core distinction between descriptive context, authoritative facts, evidence spans, and model-facing composition. The result must let a migration or ordinary caller preserve context and evidence identity without a provider adapter.

### Expected Outcome
- Raw ingest/extraction can receive bounded context as untrusted descriptive input without weakening span verification.
- Retrieval results expose context and define a safe, bounded way to use it for matching without making it authoritative.
- `compose_context` continues to enforce token budgets and does not automatically inject arbitrary context.
- JSON portability, sync, audit, correction, and erase preserve or remove context according to the Phase 100601 contract.
- CLI and MCP behavior remains identical and migration-oriented examples use only the native contract (no provider client, no container claims).

### Product Rationale
Storing context without carrying it through the rest of the lifecycle would create a misleading feature: a field would appear in one inspector but disappear during extraction, export, synchronization, or deletion. This phase makes context useful wherever the memory is transformed or inspected, while keeping it bounded and subordinate to the snapshot/gist contract.

It also keeps migration provider-neutral. A migration tool or operator can retain the human-readable context and carry external source identifiers opaquely without requiring Clio to know which external system produced the record. Document-container parity is explicitly deferred (see requirement §9).

### Parent Requirement
Requirement v1.10 and Phase 100601's context/evidence contract; current P1, P3, P5, P6, P12; PR-1, PR-3, PR-4, PR-5, PR-8, PR-9, PR-10; FR-4, FR-5, FR-6, FR-15, FR-17, FR-20, FR-24, FR-29, FR-34, FR-35; NFR-2, NFR-3, NFR-5, NFR-6, NFR-7, NFR-9; §4.3–§4.5, §4.9.3, §4.9.5.B, §7.4.

---

## 2. Scope Boundaries

### In Scope
- Context propagation through the existing raw-ingest/extraction contract.
- Safe treatment of context as untrusted input to local and hosted extractors.
- Retrieval result metadata and the explicitly approved lexical matching policy.
- Safe behavior of `compose_context` and context budget accounting.
- JSON export/import round trips, manifests, checksums, and version compatibility.
- Audit, correction, sync, and erasure propagation for context.
- CLI/MCP parity tests, migration examples, and operator documentation.
- A provider-neutral migration mapping guide showing how external source identifiers are carried opaquely in `evidence_ref` with no container-parity claim.

### Explicitly Out of Scope
- Hindsight API calls, provider credentials, provider polling, provider-side document upsert, or a Hindsight adapter.
- Automatic live migration or dual-write.
- A generic tags, labels, or context-based filtering API.
- New context categories or admission factors.
- Changing snapshot/gist authority, confidence semantics, or update rules.
- Unbounded context injection into model prompts.
- New storage engines or unrelated retrieval features.

### Must Not Change
- `compose_context` remains bounded by the existing token budget and persona/memory separation.
- FR-4 span verification continues to use `source_text` as the haystack.
- Context never overrides a structured snapshot or changes fact/belief classification.
- Existing provider stubs remain unchanged; no provider code is added.
- Existing export/import idempotency and manifest guarantees remain intact.
- Existing sync, erase, and audit semantics remain authoritative.

### Scope Expansion Rule
If work outside this scope appears necessary:
1. Stop.
2. Document the reason.
3. Request clarification or approval.
4. Do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- Phase 100601's contract is implemented or explicitly available as the downstream context/evidence contract.
- Existing extraction, retrieval, CLI, portability, audit, sync, and erase owners have been identified.
- The context maximum and redaction policy are documented.

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| Native context field | Store/read contract accepts and returns bounded context | Phase 100601 acceptance |
| Evidence reference | Stable external source IDs survive read/write/portability | Phase 100601 acceptance |
| Extraction contract | Candidate has source text, snapshot, gist, and source reference | Existing extraction inspection/tests |
| Span verification | Context is not accepted as a replacement for source text | Existing FR-4 tests |
| Retrieval | Hybrid results can carry optional metadata without exceeding budgets | Existing retrieve/compose tests |
| Portability | Manifest, checksums, versioned JSON, and idempotent import exist | Phase 100220 tests |
| Audit/erase/sync | Context can be propagated or removed through existing records | Existing phase tests |

---

## 4. Existing-System Discovery

The agent MUST inspect the existing system before deciding where or how to implement the changes.

### Required Discovery
- Locate raw ingest/extraction entry points and determine which path actually runs in the live runtime.
- Confirm how `source_text`, `source_ref`, snapshots, gists, and retry feedback are passed to extractors.
- Locate lexical/dense document construction and result serialization.
- Confirm how `compose_context` selects and budgets persona versus memory content.
- Locate export/import payload versions, manifests, checksums, and idempotency keys.
- Locate sync payload serialization, audit projections, correction, and dirty-path erase propagation.
- Inspect CLI/MCP schema generation and existing migration documentation.

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
- The extraction interface carries source text and candidate output, but the live MCP store path does not currently run raw extraction.
- `source_text` is only needed when a structured snapshot is present and is the correct span-verification haystack.
- Retrieval already has a separate `compose_context` budget and persona channel; context must not bypass that contract.
- JSON portability has a manifest and idempotent import foundation but must be checked for the new field.
- Audit, sync, and erase have established paths; context must be added to those paths rather than creating parallel mechanisms.
- The CLI binding for `remember` is already owned by the CLI write phase; this phase extends behavior and must not create a second command owner.

### Assumptions Confirmed
- Context can be carried as bounded metadata through existing item envelopes.
- The retrieval result type can expose optional metadata without changing the authoritative item.
- Existing manifest/version mechanisms can represent a new optional field compatibly.
- Provider-neutral migration documentation can explain external source identifiers without a provider client.

### Assumptions Requiring Approval
- Whether context participates in lexical matching by default or only under an explicit retrieval option.
- Whether `compose_context` may ever include context automatically; the recommended default is no.
- Whether context is included in dense embedding input; the recommended default is no until separately benchmarked.

### Repository Adaptation Rule
The agent must determine concrete implementation locations from the actual repository. The plan does not prescribe file paths, class names, module names, or directory structures unless they are explicitly part of the externally required contract.

---

## 5. Implementation Specification

### Task 1: Propagate Context Safely Through Ingest and Extraction

#### Intent
Allow source context to help a future extractor understand a memory's setting without allowing it to become evidence or an instruction channel.

#### Required Capability or Behavior
- Raw ingest accepts the same optional context contract as the core store.
- Domain-record writes accept the same optional `context` contract: `persona_put_stable`, `persona_observe_preference`, `task_upsert`, `failure_record`, `triple_add`, and `belief_observe` declare an optional bounded `context` parameter and persist it per record (SQLite and Postgres parity); a record written without context stays unchanged.
- Context is passed to extractors as bounded descriptive metadata.
- The authoritative evidence haystack remains `source_text`.
- Context is not concatenated into a prompt as an instruction and cannot override schema, system, or verifier rules.
- Extracted snapshots, gists, source references, and context remain associated after successful admission.
- A failed or rejected extraction follows the existing retry/refusal behavior.

#### Architectural Responsibility
The ingest/extraction boundary owns propagation and prompt safety; the span verifier remains the sole grounding authority.

#### Required Changes
1. Add context to the extraction request/candidate envelope where raw ingest is supported.
2. Preserve context through extraction, verification, admission, and leaf publication.
3. Add explicit prompt delimiters and untrusted-data treatment for context in hosted extraction.
4. Ensure context is not used as a source span or included in snapshot verification.
5. Add tests for missing, normal, oversized, and instruction-like context.
6. Declare the optional bounded `context` parameter on the domain-record write tools (`persona_put_stable`, `persona_observe_preference`, `task_upsert`, `failure_record`, `triple_add`, `belief_observe`) and persist it per record on both backends, rejecting a supplied context only where the record type has no context carrier (fail closed, never silently drop).

#### Implementation Constraints
- Do not send context to a hosted extractor unless the existing source-egress policy permits the same data class.
- Do not let model output or context change the category, epistemic kind, or source type.
- Do not change FR-4 retry/refusal behavior.
- Do not require live extraction wiring if that wiring is owned by another phase; provide the contract and tests at the existing seam.

#### Expected Result
An extractor can receive context as bounded descriptive input, while only source text can satisfy span verification and the stored item retains the original context.

### Task 2: Define Context-Aware Retrieval Without Breaking Budgets

#### Intent
Make context useful for finding related memories while keeping fact authority and model budgets unchanged.

#### Required Capability or Behavior
- Retrieval hits may return context as optional metadata.
- The approved lexical policy may include context in lexical matching; dense snapshot/gist embeddings remain unchanged unless separately approved.
- A context match never upgrades an item from belief to fact or bypasses category/admission history.
- `compose_context` counts any explicitly included context under the same memory budget and never injects it by default.
- Retrieval remains bank-scoped and subject to existing time, domain, and budget controls.

#### Architectural Responsibility
The retrieval/composition owner controls candidate text, result metadata, and budgets; the context field itself remains storage data.

#### Required Changes
1. Add context to retrieval result metadata and safe rendering.
2. Implement or explicitly reject the proposed lexical matching policy with deterministic tests.
3. Ensure dense/gist behavior is documented and covered by regression tests.
4. Add budget tests showing context cannot expand `compose_context` beyond its budget.
5. Add tests for context-only matches, fact/belief preservation, and bank isolation.
6. Surface the stored context on the FR-34 domain reads (`persona_get`, `task_get`/`task_history`, `temporal_history`, `belief_history`) as optional per-record metadata, omitting the key when the record has none (T100606-13 / AC-100606-09).

#### Implementation Constraints
- No unbounded context concatenation.
- No new context filter syntax in this phase.
- No change to the intent gate or persona channel rules.
- No claim that a context match proves the underlying fact.

#### Expected Result
A caller can retrieve context when present, and any context used for matching or composition is bounded, visible, and separate from authoritative truth.

### Task 3: Extend Portability, Audit, Correction, Sync, and Erasure

#### Intent
Ensure context survives the complete data lifecycle and does not create a hidden backup or orphan field.

#### Required Capability or Behavior
- Export includes context and the evidence reference according to the approved content mode.
- Import validates and round-trips context, including old bundles where it is absent.
- Manifest completeness/checksum calculations include the new field when present.
- Audit and correction show context changes without logging unsafe raw values.
- Sync carries context under the existing encrypted/conflict/idempotency rules.
- Erasure removes or renders context unreadable through the existing subject/derived-structure path.
- A context-only change does not silently rewrite unrelated item content.

#### Architectural Responsibility
Existing portability, audit, sync, and compliance owners add the field to their established projections and lifecycle rules.

#### Required Changes
1. Update versioned export/import schemas and compatibility logic.
2. Update manifest counts/checksums and dry-run samples with safe redaction.
3. Update audit/correction history for context changes.
4. Update sync serialization and idempotency comparison.
5. Update erase/dirty-path propagation and verify no derived copy remains readable.
6. Add round-trip, old-version, redaction, and erasure tests.

#### Implementation Constraints
- Do not add a second export or sync format.
- Do not expose context in plaintext logs or diagnostics.
- Do not let import bypass admission or category gates.
- Do not treat context as a new source of truth.

#### Expected Result
A context-bearing item survives export/import, sync, correction, audit, and erasure according to the same lifecycle guarantees as the rest of its content.

### Task 4: CLI, Documentation, and Migration Mapping

#### Intent
Make the feature usable and migration-ready without adding a provider adapter.

#### Required Capability or Behavior
- Existing `remember` and `admit` CLI help documents `--context` and the evidence-reference semantics.
- The MCP schema and CLI help describe identical constraints and defaults.
- Operator documentation explains context versus category, evidence reference, source text, and compose context.
- A provider-neutral migration example shows how external source identifiers are carried opaquely in `evidence_ref` and how `context` is retained, with no document-container claim.
- No Hindsight network call or credential is required for the example.

#### Architectural Responsibility
CLI/help/docs owners expose the already-defined contract; migration documentation does not implement a provider adapter.

#### Required Changes
1. Add or update CLI usage text and examples.
2. Add a migration mapping example using generic external records.
3. Document that `evidence_ref` confers no document-container semantics and that `doc_id` is deferred to the approval-gated Phase 900611 family (see requirement §9).
4. Document retrieval, redaction, and context-size behavior.

#### Implementation Constraints
- Do not add a new top-level CLI command.
- Do not add provider credentials or a remote migration flow.
- Do not imply that evidence references are automatically idempotent unless the identity contract says so.

#### Expected Result
A user can manually or programmatically migrate records into Clio using the native context and evidence-reference contract without an adapter.

### Task 5: Cross-Cutting Verification and Evidence

#### Intent
Demonstrate that context is safe and useful across the full system, not merely accepted by one parser.

#### Required Capability or Behavior
- Unit, integration, contract, end-to-end, regression, security, and failure-mode tests cover the approved lifecycle.
- Tests prove context is not used for span verification or automatic injection.
- Tests prove export/import, sync, audit, correction, and erase preserve lifecycle guarantees.
- Tests prove MCP and CLI semantics match.

#### Architectural Responsibility
Each owning crate tests its boundary; the phase exit report collects the aggregate evidence.

#### Required Changes
1. Add focused tests at extraction, retrieval, portability, audit, sync, erase, and binding boundaries.
2. Add a migration fixture with context, evidence reference, and no provider dependency.
3. Run the workspace's required checks and coverage procedure.
4. Record any unimplemented downstream policy as a documented limitation, not as a silent pass.

#### Implementation Constraints
- Do not claim retrieval quality improvement without comparative evidence.
- Do not claim provider compatibility without a real contract test against a fixture or documented API shape.
- Do not weaken existing tests to accommodate context.

#### Expected Result
The phase has executable evidence that context remains bounded, attributable, portable, erasable, and separate from truth and model composition.

### Implementation Freedom
The agent may choose internal module placement, retrieval representation, serializer layout, and test organization provided the public contract, security boundaries, and acceptance criteria remain intact.

---

## 6. Agent Execution Rules

### Allowed Actions
- Inspect and modify extraction, retrieval, CLI, portability, audit, sync, erase, schema, and documentation components.
- Add context propagation and safe metadata handling.
- Add provider-neutral migration examples and fixtures.
- Perform local refactoring required to preserve existing ownership boundaries.

### Forbidden Actions
- Add a Hindsight adapter, Hindsight API client, provider polling, or remote migration job.
- Add a new provider or dependency without approval.
- Add a generic tag/filter system or new category.
- Change fact/belief, source-span, admission, or compose-context semantics silently.
- Unbounded prompt injection or plaintext logging.
- Delete tests, weaken security, or claim success without evidence.

### Agent Decision Boundary
The agent may decide:
- Whether context is included in lexical matching under the approved policy.
- Internal metadata and serialization layout.
- Documentation examples and test placement.

The agent must request approval for:
- Dense embedding changes.
- Automatic context injection into `compose_context`.
- New filtering or ranking semantics.
- Provider-specific behavior.
- A change to the context size or encryption policy.

### Mandatory Stop Conditions
Stop and report if:
- Context cannot be kept separate from source text or truth.
- Retrieval budgets cannot account for context safely.
- Export/import or sync would lose or expose context.
- Existing runtime extraction is not actually wired and the phase would require an unapproved rewrite.
- A provider adapter appears necessary to satisfy the approved scope.

---

## 7. Security Constraints

### Required Controls
- Treat context as untrusted, potentially sensitive input.
- Validate and bound context before extraction, indexing, storage, or egress.
- Scrub or omit context from logs, dry-run samples, errors, and audit human output.
- Preserve bank/subject authorization and existing provider stub behavior.
- Keep model instructions and source text authoritative over context.

### Sensitive Data Rules
- Never log raw context by default.
- Never treat context as a credential, authorization token, or executable instruction.
- Never send context to a hosted model without the same explicit egress policy and scrubbing used for source text.
- Never commit secrets or provider credentials.

### Security Acceptance Conditions
- Instruction-like context cannot change extraction schema or admission outcome.
- Secret-like context is absent from plaintext diagnostics and exports unless the authorized content mode explicitly includes it.
- Context is removed through the existing erasure path.
- No provider network call occurs in this phase.

---

## 8. Test and Verification Strategy

### Required Tests
- [x] Unit tests (extraction seam, record persistence, serde omission, validation fail-closed)
- [x] Integration tests (SQLite + Postgres store-level context persistence and reads)
- [x] Contract tests (MCP schema declarations, CLI/MCP parity)
- [x] End-to-end tests (MCP surface: six record writes with context → domain reads surface it)
- [x] Regression tests (lexical/dense exclusion; compose budget; carrier-envelope reads)
- [x] Security tests (egress scrubbing, instruction-like context as data, unreadable/shredded context tolerance)
- [x] Failure-mode tests (oversized/empty context rejected before any write; no partial propagation)

### Required Test Scenarios

| Test ID | Scenario | Expected Result |
|---------|----------|-----------------|
| T100606-01 | Extract with normal context and source text | Snapshot verifies only against source text; context persists |
| T100606-02 | Context contains instruction-like text | Treated as data; schema/admission cannot be overridden |
| T100606-03 | Context is oversized or malformed | Rejected before extraction or persistence |
| T100606-04 | Retrieve an item with context | Context appears as metadata; truth and bank scope remain correct |
| T100606-05 | Compose a budgeted pack containing context candidate | Total budget is enforced; no unbounded injection |
| T100606-06 | Export/import context-bearing item | Context and evidence reference round-trip; manifest remains complete |
| T100606-07 | Import an old bundle without context | Accepted with absent context and no data loss |
| T100606-08 | Correct/sync an item with context | Lifecycle change is attributable and idempotent |
| T100606-09 | Erase a subject with context | Context is unreadable and derived copies are regenerated/removed |
| T100606-10 | Context contains secret-like text | Logs, samples, and errors redact or omit it |
| T100606-11 | CLI and MCP equivalent requests | Same stored context/evidence behavior |
| T100606-12 | No provider/network configured | All local behavior remains available; no provider call occurs |
| T100606-13 | Domain-record write with optional context (persona_put_stable, persona_observe_preference, task_upsert, failure_record, triple_add, belief_observe) followed by its domain read (persona_get, task_get/task_history, temporal_history, belief_history) | The context persists per record on SQLite and Postgres, the domain read surfaces it as metadata, and records written without context omit the key |

### Negative Testing
Verify that:
- Context cannot bypass extraction or admission validation.
- Context cannot expand retrieval or composition budgets.
- Export/import and sync do not drop context silently.
- Erasure does not leave a readable derived copy.
- Existing no-context behavior remains intact.
- A failed operation does not leave partially propagated context.

### Verification Rule
Implementation claims must be supported by actual test output, runtime evidence, schema inspection, or other concrete evidence.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-100606-01 | Context propagates through extraction without becoming evidence or instructions | T100606-01, T100606-02, T100606-03 | PASS — `cargo test -p clio-write`: prompt carries `<source_context>` as delimited, neutralized, scrubbed data; fixture extraction outcome identical with instruction-like context; oversized/empty rejected before extraction; stored item retains original context (`extract_chat_tests`, `raw_ingest_tests`, `ingest_tests`) |
| AC-100606-02 | Retrieval exposes context safely and preserves budgets | T100606-04, T100606-05 | PASS — `RetrieveHit.context` surfaced on item and belief hits; `compose_tests::source_context_is_never_injected_and_never_expands_the_budget` proves context never enters the pack and budgets hold; `embed_tests::source_context_is_excluded_from_dense_and_lexical_text` fixes the lexical/dense default-off policy |
| AC-100606-03 | Portability and sync preserve context and evidence identity | T100606-06, T100606-07, T100606-08 | PASS — item context round-trips export/import (export scrubs inline secrets; import stays idempotent); record context rides the sealed carrier or a dedicated sealed column and now also replicates as structured sync records: task and failure feeds plus apply effects materialize the structured row on the peer through the atomic history commit paths (two-node TCP test `task_and_failure_records_replicate_end_to_end`), persona stable/preference and belief records replicate with parity, and an authorized belief-context correction bumps the record's change stamp so it replicates through the audited correction path |
| AC-100606-04 | Audit, correction, and erasure honor context lifecycle | T100606-08, T100606-09 | PASS — record context travels in the sealed carrier or dedicated sealed ciphers; crypto-shredded subjects read back `context: None` (tested on both backends); belief appends never replace a stored context and the authorized correction commits row + audit atomically; erasure also blanks the persona-bearing sync journal and dead-letter copies, and no audit detail retains a sealed prior context (`sqlite/postgres_erase_destroys_persona_derived_sync_copies`) |
| AC-100606-05 | Context is redacted from unsafe diagnostics and egress | T100606-10 | PASS — chat egress scrubs inline secrets from `<source_context>` (`extract_chat_egress_tests`); audit telemetry records presence/length/hash only; raw context never enters logs or audit detail; `ciphertext_backup` bundles carry no readable record content at all, and the post-scrub length bound is re-checked against `CONTEXT_MAX_BYTES` before any value is written |
| AC-100606-06 | CLI and MCP expose identical semantics | T100606-11 | PASS — `--context` on `triple add`, `belief observe`, `persona stable/observe`, `task upsert`, `failure record` plus existing `remember/admit/correct`; `context_parity_tests::cli_and_mcp_task_upsert_store_the_same_context` proves identical stored context |
| AC-100606-07 | No provider adapter or network dependency is introduced | T100606-12, code inspection | PASS — no provider code added; local extraction seam only; all behavior verified without network |
| AC-100606-08 | Migration documentation carries external source identifiers opaquely with no container-parity claim | Documentation review | PASS — `docs/source-context-and-migration.md` documents `evidence_ref` as identity-only, explicitly defers `doc_id` container semantics, and uses only the native contract |
| AC-100606-09 | Domain-record writes accept optional `context` (persona_put_stable, persona_observe_preference, task_upsert, failure_record, triple_add, belief_observe) and the domain reads (persona_get, task_get/task_history, temporal_history, belief_history) surface the stored context per record | T100606-13 | PASS — SQLite + Postgres parity (`pg_history_tests`, `pg_triple_tests`, `pg_persona_tests`, `belief_context_pg_tests`); MCP surface tests (`context_domain_record_tests`); the MCP/CLI bindings and the batch pre-flight decode `context` fail closed (non-string, empty and oversized rejected); `temporal_history` attaches the context effective at the requested point via `persona_preferences.context_as_of`, so a context introduced later never appears on an earlier point; key omitted when absent; sealed at rest; unreadable context degrades to `None` |

### Definition of Done
- [x] All in-scope behavior is implemented.
- [x] All acceptance criteria pass.
- [x] Required tests pass (`cargo test --workspace --locked` green; 0 failures).
- [x] No unauthorized changes were introduced.
- [x] Existing behavior remains intact (baseline per-file coverage ≥90% before and after; no pre-existing file lost coverage).
- [x] Security checks pass (egress scrubbing, no raw context in telemetry, fail-closed validation).
- [x] Documentation is updated where required (`docs/source-context-and-migration.md`, CLI usage text, MCP schemas).
- [x] Evidence is collected (per-file scoped `cargo llvm-cov` runs plus the final full gate).
- [x] Verification is completed (final `make check` green: fmt, `clippy -D warnings`, workspace tests; final `make coverage` exit 0 — 345 files checked, all reported files meet the 90% per-file floor, TOTAL lines 97.90%, functions 98.71%; re-run on the frozen round-3 tree after the final test-file edit).
- [x] Required approval is obtained — **operator acceptance without a passing checker, recorded 2026-09-26.** The remedy approver rejected three times and a fourth round was aborted; no machine approval signal was ever emitted. This box is ticked as an operator decision, not a machine verdict. What was independently verified at close-out: all seven round-3 grounds addressed; the F-06 import-scrub ground was real and unfixed, and is now fixed (`32d905d`) with four regression tests; `cargo fmt` clean, `clippy -D warnings` clean, 2426 tests pass / 0 fail, `make coverage` exit 0 — 347 files checked, all reported files meet the 90% per-file floor, TOTAL lines 97.88% / functions 98.72%, changed files `import_apply.rs` L95.80/F94.74 and `import_rows.rs` L98.13/F100. **The outstanding human gate is unchanged and still open:** the public lexical/retrieval policy choice (documented default-off, no ranking change made) has not had a Human Approver sign-off, and two defects remain accepted in writing in §12 Known Limitations (F-10 restore context effective time; F-13 part 2 item watermark resume key).

### Completion Evidence
- Context propagation and retrieval policy summary: raw ingest validates and carries context to extractors as a delimited, scrubbed, untrusted `<source_context>` section; every public extraction entry point (raw ingest, pipeline, parallel fan-out, and both HTTP adapters) validates the bound before egress; hits expose context as metadata; compose never injects it and budgets cannot expand; lexical/dense exclusion is the documented deterministic default policy (`docs/source-context-and-migration.md`, Retrieval and composition policy).
- Portability/audit/sync/erase evidence: task/failure/triple context rides the sealed carrier envelope on both backends (no schema change for records with carriers); persona and belief records carry dedicated sealed `context_cipher` columns with guarded SQLite/Postgres convergence; preference context additionally records its effective time (`context_as_of`) so point-in-time reads cannot leak a later value; erasure renders record context unreadable, including the persona-bearing sync journal and dead-letter copies (tests on both backends).
- Structured sync evidence: `cargo test -p clio-sync` green, including the two-node TCP test `client_feed_tests::task_and_failure_records_replicate_end_to_end` (a pushed task and failure are readable on the peer with their context) plus the Postgres feed/apply parity tests.
- CLI/MCP parity output: `cargo test -p clio context_parity` (2 passed) plus `context_domain_record_tests` (4 passed).
- Security and budget test output: `extract_chat_egress_tests`, `context_write_tests`/`context_correct_tests`, `compose_tests::source_context_is_never_injected_and_never_expands_the_budget`.
- Provider-neutral migration example: `docs/source-context-and-migration.md` §Migration mapping (JSON tool-call example, no provider client); the example's snapshot is executed by the documentation smoke test under native span verification.
- Known limitations and deferred dense/provider work: see §12 Known Limitations; additionally, task/failure/triple history reads still fail closed for fully crypto-shredded subjects (pre-existing carrier-cipher behavior); context surfacing on those records degrades to `None` only when the carrier body is unreadable but the record itself stays readable; belief `belief_history` returns the belief-level context with the trajectory.
- Verification sign-off pending: Human Approver required for the public lexical/retrieval policy choice (documented default-off; no ranking change was made).

---

## 10. Failure Handling and Recovery

### Expected Failure Modes

| Failure | Detection | Recovery |
|---------|-----------|----------|
| Context changes extraction output unexpectedly | Golden extraction comparison | Treat context as descriptive only; fix prompt/data boundary before proceeding |
| Context causes budget overflow | Compose test | Exclude or truncate according to the approved budget policy; never inject unbounded text |
| Export/import drops context | Round-trip test | Block acceptance; preserve old version compatibility while fixing serializer |
| Sync omits context | Sync contract test | Fail the sync operation or use the documented compatibility path; do not silently clear it |
| Context leaks in logs | Security test | Redact, remove output, investigate exposure, and rerun |
| Erase leaves derived context | Erase test | Block acceptance and repair dirty-path propagation |
| Existing extraction runtime is absent | Discovery | Limit work to the defined seam and document the live-wiring dependency; do not add an unapproved runtime rewrite |

### Rollback Strategy
Disable context-aware retrieval and new field exposure while retaining nullable stored values. Old bundles and items remain readable. Do not delete context-bearing data without an explicit erase/retention decision.

### Partial Completion Policy
If extraction, retrieval, portability, or erasure is incomplete, do not claim native support end to end. Record the completed boundary and the exact missing lifecycle behavior.

---

## 11. Traceability

| Parent Requirement | Implementation Task | Verification | Acceptance Criterion |
|--------------------|---------------------|--------------|-----------------------|
| PR-1 / NFR-3 | Task 2 | T100606-04, T100606-05 | AC-100606-02 |
| PR-4 / FR-4 / FR-5 | Task 1 | T100606-01, T100606-02 | AC-100606-01 |
| PR-8 / FR-15 / NFR-6 | Task 3 | T100606-08, T100606-09 | AC-100606-03, AC-100606-04 |
| FR-20 / NFR-7 | Task 4 | T100606-11 | AC-100606-06 |
| §4.9.5.B / FR-29 | Task 3 and Task 4 | T100606-06, T100606-07 | AC-100606-03 |
| §7.4 | Task 3 | T100606-09, T100606-10 | AC-100606-04, AC-100606-05 |
| Provider-neutral migration goal | Task 4 | Documentation review | AC-100606-08 |
| No-provider scope boundary | All tasks | T100606-12 | AC-100606-07 |
| FR-34 / §4.4 domain records | Task 1 and Task 2 | T100606-13 | AC-100606-09 |

Required chain:

```text
Requirement → Capability → Implementation → Test → Evidence
```

Every acceptance criterion must be traceable.

---

## 12. Phase Exit Contract

### Outputs Produced
- Safe context propagation through extraction, retrieval, portability, audit, sync, and erase.
- Documented retrieval and composition policy for context.
- Provider-neutral migration documentation using context and `evidence_ref`.
- No Hindsight adapter, provider client, or remote migration flow.

### Guarantees Provided to Downstream Phases
After this phase is accepted:
- Context is a first-class, bounded, protected part of the memory lifecycle.
- `evidence_ref` is the canonical external source identity; document-container semantics are deferred (see requirement §9).
- Retrieval and model composition remain bounded and truth-preserving.
- A later migration tool or operator can map external records without changing the core contract.

### Known Limitations
- No direct Hindsight import or live migration.
- Dense use of context is not enabled by default.
- No generic context filter or tag system.
- Provider-side document upsert semantics are not implemented.
- Context is not part of lexical or dense matching by default; enabling it is a separately approved, benchmarked policy change (documented in the operator guide).
- Task/failure/triple domain reads fail closed for fully crypto-shredded subjects (pre-existing carrier-cipher behavior, unchanged); surfaced record context degrades to `None` only when the carrier body is unreadable while the record stays readable.
- Preference context is stored once per key with its effective time (`persona_preferences.context_as_of`), so a temporal point carries the context effective from its introduction onward; a genuine per-observation context history would need a context column on `continuous_observations` and is not implemented.
- Persona context is sealed under the bank DEK (subject = bank), so erasure purges persona context for the affected bank rather than for an individual subject within that bank; a bank whose persona purge destroyed rows is tombstoned (`persona_erase_tombstones`) and later persona writes into it fail closed with `ErasedSubject`, because persona rows cannot name the erased subject.
- A belief point-in-time read between the original context introduction and a later authorized correction returns no context: the prior value is unrecoverable by design (FR-15 forbids retaining it) and the future-corrected value is never leaked (`beliefs.context_as_of` gates the read).
- The structured-record sync commit and its journal append remain two store writes; a lost journal write no longer freezes relay (every domain-record equal-state apply journals the mutation on the next delivery), but the two writes are not one transaction.
- A hand-crafted (non-shipped) import bundle could stage a secret-shaped task/failure/triple `context` unscrubbed: shipped bundles are already scrubbed on export and over-bound contexts fail closed at record validation, so this is a defense-in-depth gap, recorded and not silently skipped.
- Restoring a bundle re-derives a belief's context effective time from `created_at` instead of carrying the exported `context_as_of`, because the store refuses a caller- or wire-supplied stamp so that sync apply cannot forge it. A restored belief whose context was later changed by an authorized correction therefore exposes the corrected context from creation time, where the source store returned none for a point-in-time read between introduction and correction. The source value is authoritative; the restored value is an upper bound on visibility, never a disclosure of a prior value.
- The item push watermark can step past a row that a concurrent write later inserts with an older business stamp. When a page is not full the cursor advances to the largest packaged close stamp, which is above the rows' ordering stamps; the feed then resumes strictly after it. A row written after that query whose `created_at`/`updated_at` falls inside the gap is never selected. This is reachable because bundle restore preserves an item's original `created_at`/`updated_at`, so a restore issued just after such a push lands below the cursor. Clamping the advance to the last row's own stamp instead makes a post-dated discard re-send its row on every push, so neither bound is sufficient on its own: the real fix is a resume key that is monotone with respect to insertion (the journal sequence the bank-level compound cursor already uses) rather than business time. Recorded, not silently skipped.

### Downstream Prerequisites
- Any later migration tooling may rely on context and evidence-reference round trips.
- Any future provider work must use the native contract; `doc_id` container design belongs to the approval-gated Phase 900611 family and must not be smuggled in as a string alias.

### Final Status
PASS WITH DOCUMENTED LIMITATIONS

### Verification Sign-Off
- Implementer: OpenCode CLI (Together . GLM-5.3 Flash High), Developer r1
- Verifier: [TBD]
- Human Approver: required for public retrieval/portability policy changes (lexical default-off decision documented; no ranking code changed)
- Date: 2026-09-25

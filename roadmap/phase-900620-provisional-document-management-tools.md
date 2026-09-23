# Phase 900620: Provisional Document Management Tools

### Attribution
Rounds below record plan authorship; implementation sign-off is in §12.
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | OpenCode (Space Bunny Free) | proposed |
| Adversary | r1 | [TBD] | [TBD] |
| Remediator | r1 | [TBD] | [TBD] |
| Remedy Approver | r1 | [TBD] | [TBD] |
| Finalize | r1 | [TBD] | [TBD] |

**Conditional follow-up phase 900620** · **Effort:** ~3–4 days · **Status:** Conditional — tool-catalog approval required · **Parent:** Phases 900611/900615 and a reviewed document tool-catalog amendment

### Approval Gate

This phase is planning-only until all of the following are recorded:

1. The document approval gate in Phase 900611 is satisfied.
2. The normative requirement tool catalog, command contract, data examples, risks, and glossary are amended with approved document operation names, semantics, and Core versus Additive classification.
3. `command-ownership.md` assigns each approved CLI command to exactly one phase.
4. Phase 900611 is accepted; Phase 900615 is accepted before end-to-end tool completion. No schema, parser, or binding work starts before this gate.
5. The approved MCP protocol revision is recorded as `2025-11-25`; mixing a later sessionless revision with that pin is forbidden.

The working names below are provisional planning handles. They MUST NOT be implemented, published in schemas, or added to command ownership while still marked provisional.

### Provisional Working Names — Not Yet Normative

| Capability | Working tool handle | Provisional CLI shape | Status |
|------------|--------------------|----------------------|--------|
| Create/retain initial document | `document_retain` | `clio document retain` | Unapproved |
| Create a native replacement revision | `document_replace` | `clio document replace` | Unapproved |
| Append source to a document | `document_append` | `clio document append` | Unapproved |
| Fetch document metadata/state | `document_get` | `clio document get` | Unapproved |
| Fetch authorized retained source | `document_source_get` | `clio document source` | Unapproved |
| List documents | `document_list` | `clio document list` | Unapproved |
| List persisted source chunks | `document_chunks` | `clio document chunks` | Unapproved |
| Reprocess retained source | `document_reprocess` | `clio document reprocess` | Unapproved / catalog decision required |
| Apply approved repository deletion | `document_delete` | `clio document delete` | Unapproved / deletion-policy gate |

The owner may merge, split, or rename these operations. Observable semantics and boundaries matter more than these handles.

### Vocabulary (read first) — zero shared moniker

| Term | Meaning in this phase | Must not be confused with |
|------|------------------------|----------------------------|
| **document metadata** | Authorized lifecycle facts such as bank, `doc_id`, revisions, hashes, timestamps, processing state, and counts | Raw source text or authorization |
| **document source** | Decrypted retained text for a selected source revision after explicit authorization | Ordinary recall output or `source_text` span verification by itself |
| **document chunk** | Persisted source segment for a selected revision | Transient write-path `chunk_id` by assumption |
| **expected revision** | Caller-supplied concurrency precondition for append/replace/reprocess/delete | An authorization token or last-write-wins hint |
| **repository delete** | Approved document-container removal semantics | `discard`, `invalidate`, `erase_request`, or destructive replacement |
| **source unavailable** | A valid state only if the approved contract later allows non-retention; native v1 should reject that configuration | A normal fallback to empty source |
| **provisional operation** | Planning handle awaiting normative catalog and ownership approval | A shipped public API |

---

## 1. Objective

### Goal
After normative approval, expose matching MCP and CLI surfaces for the native document lifecycle implemented by Phases 900611 and 900615. Callers must be able to create/retain, append, replace, inspect, list, fetch authorized source/chunks, reprocess, and apply the approved repository-deletion workflow without weakening bank/subject authorization, confirmation, audit, or source-retention guarantees.

### Expected Outcome
- The normative catalog defines one unambiguous set of document operation names, inputs, outputs, errors, confirmation, and authorization semantics.
- MCP stdio and Streamable HTTP expose identical document tool behavior and machine-readable schemas.
- The CLI provides one owner per approved command, matching JSON behavior, useful human output, and non-zero failures for automation.
- Metadata reads do not automatically reveal raw source; source reads require explicit authorization and an approved source-fetch operation.
- Append/replace/reprocess use expected-revision or idempotency preconditions and return retryable conflicts.
- Repository deletion is explicit, confirmed, audited, and never aliased to compliance erasure.
- No Hindsight parity claim is made for destructive replacement, uploads, attachments, tag filters, observation scopes, or source-retention-disabled behavior.

### Parent Requirement
Conditional parent contract: requirement.md §4.9.2 delivery/binding, §4.9.3 gating, §4.9.4 tool catalog, §4.9.6 coding-agent profile, §4.9.7 prohibited tool behavior; PR-3, PR-5, PR-6, PR-8, PR-10; FR-15, FR-20, FR-23, FR-35; NFR-7; §7.4; §9 document-container gate; §10 glossary.

Requirement v1.10 does not currently list document tools. This phase is `BLOCKED` until the normative catalog and CLI ownership are amended.

---

## 2. Scope Boundaries

### In Scope
- Normative tool-name and command-ownership approval for the native document surface.
- MCP tool schemas and dispatch on stdio and Streamable HTTP.
- CLI parsing, help, human/JSON output, confirmation, and exit/error mapping.
- Initial retain/create, native replace, and append bindings.
- Document metadata/state get and bank-scoped list bindings.
- Explicitly authorized source and chunk fetch bindings.
- Stored-source reprocess binding if the approved catalog assigns a public operation.
- The approved, confirmed repository-deletion workflow.
- Contract, parity, authorization, redaction, confirmation, and failure tests.
- Operator/help documentation for identity, revisions, conflicts, source availability, and deletion boundaries.

### Explicitly Out of Scope
- Any change to the Phase 900611 repository contract or Phase 900615 native lifecycle semantics.
- Provider-faithful destructive replacement.
- Hindsight API/provider adapter or `import_provider` behavior.
- File upload, parsing, conversion, OCR, transcription, remote file storage, binary attachments, or attachment URLs.
- A generic tag/filter system, Hindsight tag retagging, observation-scope modes, or custom re-consolidation controls.
- A configurable source-retention-disabled mode.
- Bulk deletion of multiple named documents unless a separate approved contract explicitly defines it.
- Export/import, sync, or full compliance-erasure changes; these belong to Phase 900625.
- A new memory category, episodic type, retrieval ranking feature, or model change.
- Exposing raw source from ordinary recall.

### Must Not Change
- `doc_id` remains bank-scoped and is not an authorization token.
- `evidence_ref` remains provenance; no document tool may treat it as an alias for `doc_id`.
- `context` remains descriptive metadata.
- Raw source is not returned by metadata/list/chunk summaries unless the approved source operation explicitly includes authorized chunk text.
- Destructive tools require explicit confirmation; repository delete is not compliance erase.
- MCP and CLI semantics are identical even when syntax differs.
- Existing tool names and command owners remain unchanged.
- Single-host sync omission and all existing tool behavior remain intact.

### Scope Expansion Rule
If work outside this scope appears necessary:
1. Stop.
2. Document the reason.
3. Request clarification or approval.
4. Do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- The approval gate is recorded and native preservation remains selected.
- Phase 900611 is accepted.
- Phase 900615 is accepted before this phase claims end-to-end completion. No schema, parser, or binding work starts before the catalog, ownership, and MCP revision gate.
- The owner has approved exact tool names, CLI commands, Core versus Additive classification, input/output schemas, and repository-deletion semantics.
- `command-ownership.md` has been updated through an approved private roadmap change.
- The normative requirement tool catalog, data examples, §9, and glossary have been updated together.
- The MCP protocol revision is pinned to `2025-11-25` for both stdio and Streamable HTTP; no later sessionless revision is mixed in.
- Existing MCP, CLI, auth, error, output, and confirmation conventions have been inspected.

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| Phase 900611 | Stable document/revision/chunk/source/lineage repository contract | Phase exit evidence |
| Phase 900615 | Stable append/replace/reprocess/current-derivation lifecycle | Phase exit evidence |
| Normative catalog | Approved operation names, semantics, and Core versus Additive classification | Requirement consistency review |
| CLI ownership | Exactly one owner per approved command/tool | `command-ownership.md` review |
| MCP revision | First-release revision pinned to `2025-11-25` for tools and transports together | Requirement and transport tests |
| MCP transport | Identical stdio and Streamable HTTP dispatch under the pinned revision | Existing transport contract tests |
| Authorization | Bank/subject checks on every source-sensitive operation | Security tests |
| Confirmation | Destructive repository delete requires explicit confirmation | Existing confirmation mechanism |
| Error model | Stable mapping for invalid/not-found/conflict/forbidden/erased/source-unavailable | Contract tests |
| Source retention | Native encrypted source is mandatory | Requirement/config inspection |
| Existing output contract | Human and JSON output/exit conventions are known | CLI/MCP contract tests |

---

## 4. Existing-System Discovery

The agent MUST inspect the existing system before deciding where or how to implement the changes.

### Required Discovery
- Locate MCP bound read/write tool lists, schema definitions, dispatch, and stdio/Streamable HTTP parity tests.
- Locate the CLI parser, help/`help --json`, output formatting, confirmation, and non-zero error conventions.
- Trace actor/bank/subject authorization used by current sensitive reads and writes.
- Inspect how expected revision, idempotency, conflict, and retryable errors are represented.
- Locate source redaction helpers and how raw content is excluded from logs/errors.
- Locate command ownership and the test that enforces one owner per tool.
- Identify which Phase 900611/900615 internal methods should be exposed and which must remain private.
- Confirm whether document source/chunk reads require a stricter permission than ordinary metadata.

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
- Final approved tool and command mapping

### Current Repository Findings at Plan Time
- MCP publishes separate bound read/write tool lists and machine-readable schemas with transport parity tests.
- CLI binding follows the command-ownership matrix and prints each verb's tool name in help.
- Existing tools already validate bank/actor authorization, use structured errors, and distinguish agent confirmation for destructive operations.
- Existing retrieval and item reads do not expose a document source contract.
- `command-ownership.md` has no document commands; provisional names must not be added before catalog approval.
- Source-bearing tools use stricter handling than metadata-only tools, but document-specific source permission must be explicitly defined.

### Assumptions Confirmed
- Existing MCP and CLI binding patterns can expose the new lifecycle without a new service.
- Existing error, auth, output, and confirmation mechanisms can be reused.
- Document tools can remain thin adapters over Phase 900611/900615 services.
- Source fetch can be separated from metadata fetch for least privilege.

### Assumptions Requiring Approval
- Exact operation split and names.
- Whether reprocess is public, operator-only, or omitted with an approved exception.
- Whether chunk fetch returns metadata only or authorized chunk text.
- Exact permission required for raw source.
- Exact confirmation/reason requirements for repository deletion.
- Whether a `clio document` command group is approved or another syntax is selected.

### Repository Adaptation Rule
The agent must determine concrete implementation locations from the actual repository. The plan does not prescribe file paths or internal type names unless they are part of the approved external contract.

---

## 5. Implementation Specification

### Task 1: Verify the Pre-Approved Public Tool and Command Contract

#### Intent
Record and verify the approved native lifecycle as a normative, internally consistent public contract before code binds it. Normative ratification happens before this phase starts.

#### Required Capability or Behavior
- Approve exact tool names, command syntax, parameter names, defaults, outputs, errors, and confirmation rules.
- Classify each approved operation as Core (§4.9.4) or Additive (§4.9.5) and state the resulting binding, coding-agent-profile, and omission consequences.
- Define the initial retain/create, replace, append, get, list, source, chunks, reprocess, and delete behavior or explicitly omit/redefine an operation.
- Define whether source is returned in a combined get response or a separate source operation; the recommended baseline is a separate operation.
- Define expected-revision/idempotency inputs for mutations.
- Define zero-result, processing, failed-attempt, and repository-deleted response states.
- Define how Clio taxonomy is exposed instead of Hindsight `world`/`experience`/`observation` fact-type names.
- State that Hindsight tag-based visibility scoping is not implemented and bank/subject authorization remains the Clio boundary.
- Update the normative tool catalog, feature coverage, examples, §9, glossary, and command-ownership matrix together.
- State that provider-faithful destructive replacement and excluded Hindsight features are not claimed.

#### Architectural Responsibility
Requirements and binding-contract ownership.

#### Required Changes
1. Verify every approval question in §4 was resolved before the phase.
2. Verify one source-controlled schema contract exists for MCP and CLI.
3. Verify one owner per approved tool/command.
4. Verify the recorded Core versus Additive classification and binding/omission consequences.
5. Verify content-free human/JSON error output and automation exit behavior.
6. Verify examples against PR-2, PR-4, PR-5, PR-6, PR-10, and §7.4.
7. Stop and report if any pre-phase ratification item is missing rather than creating it inside this phase.

#### Implementation Constraints
- Do not publish provisional names.
- Do not add a second schema source for CLI and MCP.
- Do not use `document_*` naming until approved; names are not semantically required by the roadmap.
- Do not expose unapproved bulk delete.

#### Expected Result
The public contract is unambiguous, approved, and traceable to the internal lifecycle.

### Task 2: Implement MCP Document Schemas and Dispatch

#### Intent
Expose the approved document lifecycle consistently over both MCP transports.

#### Required Capability or Behavior
- Pin the document MCP surface to revision `2025-11-25` for tools and transports together; do not mix a later sessionless revision.
- Register each approved read/write tool in the correct bound list.
- Publish machine-readable `tool_schema` artifacts with bounds, defaults, and confirmation requirements.
- Dispatch only to Phase 900611/900615 services; do not duplicate business logic in MCP.
- Enforce bank/subject authorization and expected-revision/idempotency checks in the service layer.
- Return source only from the approved source operation and only to authorized callers.
- Map domain errors to stable structured error codes.
- Make stdio and Streamable HTTP semantics identical under the pinned revision.

#### Architectural Responsibility
MCP binding layer over native document services.

#### Required Changes
1. Add approved tool definitions and dispatch entries.
2. Add transport-parity and `tool_schema` validation tests under revision `2025-11-25`.
3. Add authorization, redaction, and error-shape tests.
4. Add help/catalog listings through the existing schema mechanism.
5. Keep provider or CLI-specific syntax out of the core service.
6. Add a test or check that forbids a later sessionless MCP revision from being mixed with the pinned one.

#### Implementation Constraints
- No tool may bypass the service-layer auth or revision checks.
- No raw source in metadata/list responses.
- No credentials or source in logs.
- No public tool before the catalog amendment is accepted.
- No MCP revision other than `2025-11-25` for this surface.

#### Expected Result
Equivalent approved MCP calls behave identically on stdio and Streamable HTTP.

### Task 3: Implement CLI Commands and Output

#### Intent
Give operators and coding agents a consistent native command surface with automation-safe behavior.

#### Required Capability or Behavior
- Implement only commands assigned to this phase in `command-ownership.md`.
- Print the backing tool name in `help` and `help --json`.
- Support text and JSON output with the same result/error semantics as MCP.
- Reject malformed/ambiguous source input without leaking it in errors.
- Map failed operations to non-zero exit status for non-interactive automation.
- Require explicit confirmation for repository delete; print the selected bank, `doc_id`, revision, and effect before confirmation.
- Do not require a second spelling for the same operation.

#### Architectural Responsibility
CLI binding layer over the same document services and schemas.

#### Required Changes
1. Add the approved parser/dispatch/help entries.
2. Add safe source input handling from approved sources such as argument/stdin or an approved raw-text file input that performs no upload, parsing, conversion, OCR, transcription, or remote storage.
3. Add text/JSON renderers and exit-code mapping.
4. Add command-ownership and parser/help parity tests.
5. Add confirmation and cancellation tests.

#### Implementation Constraints
- No raw source echoed in ordinary diagnostics.
- No command collides with reserved top-level verbs.
- No unapproved alias or second owner.
- No local reimplementation of append/replace/delete semantics.

#### Expected Result
The CLI and MCP surfaces expose one contract with predictable automation behavior.

### Task 4: Expose Metadata, Source, Chunk, and List Reads Safely

#### Intent
Make document inspection useful without overexposing retained source.

#### Required Capability or Behavior
- Metadata get returns approved lifecycle fields, current revision, processing state, Clio taxonomy counts, content hash, timestamps, and availability flags. It never exposes Hindsight `world`/`experience`/`observation` fact-type names as Clio categories.
- List is bank-scoped, deterministic, paginated, and supports only approved filters such as ID substring and time window. Tag-based visibility scoping is not implemented; bank/subject authorization is the boundary.
- Source fetch requires explicit authorization and a selected revision; current and historical revision behavior is explicit.
- Chunk listing returns approved metadata and returns chunk text only when the approved schema explicitly includes it.
- Deleted, failed, pending, zero-result, and erased-subject states are distinguishable without leaking hidden data.
- Cross-bank identifiers behave as not found or forbidden according to the existing no-existence-leak policy.

#### Architectural Responsibility
Document read projections and binding serializers.

#### Required Changes
1. Implement approved read schemas and service calls.
2. Add deterministic ordering and pagination.
3. Add source/chunk permission checks and redaction.
4. Add tests for historical/current revisions, zero-result, deleted, erased, and cross-bank cases.
5. Ensure recall remains a separate path and does not gain raw-source behavior.

#### Implementation Constraints
- No tag filtering or tag-based visibility scoping unless a generic tag contract is separately approved.
- No Hindsight fact-type names in Clio responses.
- No raw source in list/get summaries by default.
- No authorization by possession of `doc_id`.
- No source availability fallback that silently returns empty text.

#### Expected Result
Authorized users can inspect document lifecycle and source deliberately, while unauthorized users receive no protected content.

### Task 5: Bind Mutation Operations and Confirmation

#### Intent
Expose native retain/replace/append/reprocess/delete through the approved public contract.

#### Required Capability or Behavior
- Retain/create validates the approved source-storage policy and creates the first revision.
- Replace requires an expected revision and creates a new revision; it never deletes prior history.
- Append requires `doc_id` and an expected state; appending to an unused ID follows the approved create behavior.
- Reprocess reads stored source and uses an idempotency key; it does not require source resubmission.
- Repository delete uses the approved history semantics, expected revision, explicit reason, and `confirm=true` for agent calls.
- All mutation responses report operation/derivation state, current revision, and retryability without raw source.
- Failed and in-progress operations do not report false success.

#### Architectural Responsibility
Thin write bindings over Phase 900615 orchestration.

#### Required Changes
1. Bind approved mutation inputs and outputs.
2. Map conflict, admission, processing, erased-subject, and deletion errors.
3. Add confirmation and dry-run behavior required by the catalog.
4. Add end-to-end binding tests over MCP and CLI.
5. Add command/tool ownership coverage.

#### Implementation Constraints
- No destructive replacement.
- No bulk delete.
- No `erase_request` alias.
- No false success while extraction/publication is incomplete.
- No source echo in mutation output.

#### Expected Result
Every public mutation invokes the native service exactly once, honors preconditions, and reports truthful state.

### Task 6: Conformance, Security, and Documentation

#### Intent
Prove catalog, schema, transport, CLI, authorization, and safety parity.

#### Required Capability or Behavior
- Unit, contract, integration, end-to-end, regression, security, and failure-mode tests cover every approved tool.
- Tests cover both MCP transports and CLI text/JSON modes.
- Tests prove equivalent requests produce equivalent state/results.
- Tests prove source, secrets, and unauthorized content never appear in logs/errors.
- Documentation explains native preservation, conflicts, zero-result behavior, source retention, and deletion boundaries.
- The required workspace coverage and per-file floors pass.

#### Architectural Responsibility
Binding tests plus phase-wide evidence collection.

#### Required Changes
1. Add a shared document binding conformance fixture.
2. Add schema/catalog/command-ownership assertions.
3. Add transport and CLI parity tests.
4. Add source redaction, auth, confirmation, and error tests.
5. Update operator/help documentation.
6. Run required checks and `make coverage`.

#### Implementation Constraints
- Do not claim public availability from in-process service tests alone.
- Do not claim parity from one transport or one CLI mode.
- Do not add unrelated docs or behavior.
- Do not defer this phase's required coverage to another phase.

#### Expected Result
The public document surface has executable evidence and an honest feature/limitation matrix.

### Implementation Freedom
The agent may choose binding internals, JSON layout, CLI source-input adapter, and test organization after the approved names and semantics are fixed.

---

## 6. Agent Execution Rules

### Allowed Actions
- Inspect and modify MCP schema/dispatch, CLI parser/output/help, and binding tests.
- Add thin adapters over accepted document services.
- Update approved private requirement/roadmap ownership documents before implementation.
- Perform local refactoring needed to preserve binding boundaries and file-size limits.

### Forbidden Actions
- Start binding work while names remain provisional.
- Change repository or write-lifecycle semantics silently.
- Add destructive replacement, provider import, upload/ETL, attachments, tags, observation scopes, or source-retention-off behavior.
- Expose raw source without approved authorization.
- Add bulk delete or compliance-erasure aliasing.
- Modify unrelated tools or command owners.
- Delete/bypass tests or claim completion without evidence.

### Agent Decision Boundary
The agent may decide:
- Internal dispatch organization and output renderer reuse.
- Safe CLI source-input mechanics after the public contract is fixed.
- Test fixture and helper placement.

The agent must request approval for:
- Renaming, merging, splitting, or omitting a provisional operation.
- Source/chunk response permissions.
- Public reprocess or delete availability.
- New confirmation, auth, or error semantics.
- Any change to Phase 900611/900615 assumptions.

### Mandatory Stop Conditions
Stop and report if:
- The normative catalog or command ownership is not approved.
- Phase 900611 is not accepted.
- End-to-end completion requires Phase 900615 behavior that is not accepted.
- Source cannot be separated safely from metadata/logs.
- Repository deletion semantics remain ambiguous.
- MCP/CLI parity or authorization cannot be verified.

---

## 7. Security Constraints

### Required Controls
- Bank and subject authorization on every operation.
- Raw source fetch uses least privilege and explicit operation semantics.
- `doc_id`, source hash, revision ID, and chunk ID are not authorization tokens.
- Source/chunk text is redacted from errors, logs, dry-run samples, and ordinary list/get output.
- Repository delete requires explicit confirmation and a reason under the approved contract.
- Compliance erase remains a separate authorized workflow.
- MCP and CLI apply the same service-layer checks.

### Sensitive Data Rules
- Never log raw source, chunk text, sensitive metadata, or decrypted envelopes.
- Never accept secrets in `doc_id` or metadata.
- Never print source in shell error messages or JSON diagnostics.
- Never use source-retention-disabled fallback.
- Never expose cross-bank existence through list/get/chunk/source behavior.

### Security Acceptance Conditions
- Unauthorized source/chunk reads fail without returning content or existence details.
- Equivalent MCP and CLI calls have identical authorization outcomes.
- A planted secret in source is absent from logs, errors, and non-source outputs.
- Unconfirmed repository delete performs no mutation.
- `document_delete` cannot invoke or masquerade as `erase_request`.

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
| T900620-01 | Validate every approved tool schema | Schema passes catalog validation and published bounds |
| T900620-02 | Equivalent retain call over stdio and Streamable HTTP | Same revision/state/result on both transports |
| T900620-03 | Equivalent CLI text and JSON calls | Same stored state and logical result |
| T900620-04 | Replace with stale expected revision | Stable retryable conflict; no write |
| T900620-05 | Append to a new and existing document | Approved create/append behavior; expected revision honored |
| T900620-06 | Metadata get for a valid document | Returns approved metadata without raw source |
| T900620-07 | Authorized source fetch | Returns only the selected revision's source after authorization |
| T900620-08 | Unauthorized source/chunk fetch | Denied without content or existence leak |
| T900620-09 | List with pagination/ID/time filters | Deterministic bank-scoped page; no raw source |
| T900620-10 | Historical revision fetch | Authorized source/history behavior matches Phase 900611 |
| T900620-11 | Reprocess through the approved public surface | Uses stored source and returns idempotent/processing state |
| T900620-12 | Repository delete without confirmation | Dry-run/no mutation according to approved contract |
| T900620-13 | Confirmed repository delete | Exact approved deletion effect; never key destruction |
| T900620-14 | Cross-bank `doc_id` use | Isolation and no existence leak |
| T900620-15 | Source contains planted secret/instruction text | No leak or instruction override in diagnostics |
| T900620-16 | Command ownership validation | Every approved tool/command has exactly one owner |
| T900620-17 | Excluded Hindsight feature request | Clear unsupported/out-of-scope response; no silent substitute |
| T900620-18 | CLI automation receives a failed operation | Non-zero exit and stable structured error |
| T900620-19 | Run document MCP tools over stdio and Streamable HTTP under the pinned revision | Both transports pass under `2025-11-25`; a later sessionless revision is rejected by the check |
| T900620-20 | Verify catalog classification and binding obligations | Every approved operation is Core or Additive with the correct exposure and omission behavior |
| T900620-21 | Request document counts or tag-filtered reads | Clio taxonomy counts are returned; Hindsight fact-type names and tag visibility scoping are not exposed |

### Negative Testing
Verify that:
- Invalid source/metadata/revision/command input is rejected safely.
- Unauthorized and cross-bank actions are blocked.
- Partial failures do not report success.
- Duplicate delivery is idempotent.
- Unconfirmed delete does not mutate.
- Existing tools and commands remain unchanged.
- A mixed or unpinned MCP revision is rejected.
- A tag-visibility request is not silently treated as bank/subject authorization.

### Verification Rule
Implementation claims must be supported by real MCP, HTTP, and CLI transcripts plus schema/ownership/security output. Internal in-process tests alone are insufficient for a binding phase.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-900620-01 | Normative catalog and command ownership approve every public document operation | Requirement/ownership review | Approval and consistency evidence |
| AC-900620-02 | MCP stdio and Streamable HTTP expose identical approved semantics | T900620-01, T900620-02 | Schema and two-transport transcripts |
| AC-900620-03 | CLI text/JSON behavior matches MCP and maps failures to non-zero exits | T900620-03, T900620-18 | CLI transcripts and exit output |
| AC-900620-04 | Metadata, list, source, and chunk reads enforce bank/subject authorization and source least privilege | T900620-06–10, T900620-14 | Security/read output |
| AC-900620-05 | Retain/replace/append/reprocess honor revision/idempotency preconditions | T900620-04, T900620-05, T900620-11 | Mutation/concurrency output |
| AC-900620-06 | Repository deletion is confirmed, auditable, and distinct from compliance erase | T900620-12, T900620-13 | Confirmation/deletion evidence |
| AC-900620-07 | Secrets/source/instruction-like text do not leak through logs, errors, or non-source output | T900620-15 | Security scan/transcript |
| AC-900620-08 | One owner exists per approved tool/command and existing ownership remains valid | T900620-16 | Ownership validation output |
| AC-900620-09 | Excluded Hindsight features are neither implemented nor claimed | T900620-17, T900620-21 | Contract and documentation review |
| AC-900620-10 | Every created/refactored Rust file is ≤450 lines and meets per-file function/line coverage floors | Size inspection and `make coverage` | Size list and coverage report |
| AC-900620-11 | Document MCP tools are pinned to revision `2025-11-25` and pass both transports without revision mixing | T900620-19 | Pinned-revision and transport evidence |
| AC-900620-12 | Every approved operation is classified Core or Additive with correct binding and omission behavior | T900620-20 | Catalog classification review |
| AC-900620-13 | Clio taxonomy is exposed without Hindsight fact-type or tag-visibility parity claims | T900620-21 | Read-response and documentation evidence |

### Definition of Done
- [ ] Approval, catalog, ownership, and phase dependencies are satisfied.
- [ ] All approved in-scope tools and commands are implemented.
- [ ] All acceptance criteria pass.
- [ ] Required tests pass on both transports and CLI modes.
- [ ] No unauthorized changes were introduced.
- [ ] Existing behavior remains intact.
- [ ] Security checks pass.
- [ ] Documentation is updated.
- [ ] Evidence is collected.
- [ ] Verification is completed.
- [ ] Required approval is obtained.

### Completion Evidence
- Approved catalog/tool/command mapping and requirement consistency review.
- MCP schema/dispatch and CLI implementation summary.
- Two-transport, text/JSON, auth, source, conflict, confirmation, and ownership transcripts.
- Rust file-size inventory and per-file coverage report.
- Explicit feature parity and known-limitations matrix.

---

## 10. Failure Handling and Recovery

### Expected Failure Modes

| Failure | Detection | Recovery |
|---------|-----------|----------|
| Catalog/ownership approval missing | Precondition review | Stop; do not implement provisional names |
| MCP revision mixed or unpinned | Revision check | Block release; restore `2025-11-25` for tools and transports |
| MCP and CLI schemas diverge | Contract test | Block release; restore one shared contract |
| Source permission too broad | Security test | Remove source from metadata/list responses; require source operation |
| Stale revision mutation | Conflict error | Return current revision metadata and retryable code; no write |
| Processing still running | Operation state read | Return processing state, not success/failure |
| Delete confirmation bypass | Mutation/security test | Reject before service call; no state change |
| Source text leaks in error | Security scan | Redact, remove output, investigate, and rerun |
| Cross-bank existence leak | Authorization test | Normalize to established not-found/forbidden behavior |
| One transport/CLI mode fails | Parity test | Block phase; do not ship partial public support |

### Rollback Strategy
Remove public schema/binding exposure while retaining accepted repository/lifecycle code and old non-document tool behavior. Do not delete source revisions or records as a binding rollback. Approved deletion operations require their own recovery policy and are not a rollback mechanism.

### Partial Completion Policy
If only one transport, CLI mode, or approved operation is complete, do not claim native document-tool support. Keep unimplemented names absent from the public catalog and record the exact boundary.

---

## 11. Traceability

| Parent Requirement | Implementation Task | Verification | Acceptance Criterion |
|--------------------|---------------------|--------------|-----------------------|
| §9 / Phase 900611 gate | Preconditions, Task 1 | Approval/dependency review | AC-900620-01 |
| §4.9.2 binding rules / NFR-7 | Tasks 1–3, 6 | T900620-01–03, T900620-18 | AC-900620-02, AC-900620-03 |
| §4.9.3 gating / PR-5 | Task 5 | Service and end-to-end tests | AC-900620-05 |
| PR-6 / FR-23 | Task 5 | T900620-12, T900620-13 | AC-900620-06 |
| PR-8 / FR-15 | Task 5 | Audit handoff/dispatch inspection | AC-900620-05, AC-900620-06 |
| PR-10 / FR-35 | Tasks 1, 4 | T900620-06–10, T900620-14 | AC-900620-04 |
| §7.4 | Tasks 4–5 | T900620-08, T900620-13 | AC-900620-04, AC-900620-06 |
| §4.9.7 prohibited behavior | Tasks 2–5 | T900620-15, T900620-17 | AC-900620-07, AC-900620-09 |
| §4.9.2 MCP revision pin | Tasks 2, 6 | T900620-19 | AC-900620-11 |
| §4.9.4 / §4.9.5 catalog classification | Task 1 | T900620-20 | AC-900620-12 |
| Taxonomy and tag-scoping boundary | Task 4 | T900620-21 | AC-900620-13 |
| Command ownership rule | Task 1, 6 | T900620-16 | AC-900620-08 |
| Phase 900615 lifecycle | Task 5 | T900620-04, T900620-05, T900620-11 | AC-900620-05 |

Required chain:

```text
Requirement → Capability → Implementation → Test → Evidence
```

Every acceptance criterion must be traceable.

---

## 12. Phase Exit Contract

### Outputs Produced
- Approved document tool catalog, Core/Additive classification, and CLI command ownership.
- MCP stdio/Streamable HTTP schemas and dispatch pinned to revision `2025-11-25`.
- CLI parser, help, output, confirmation, and error behavior.
- Authorized metadata/list/source/chunk reads.
- Native retain/replace/append/reprocess/delete bindings.
- Binding parity, security, and coverage evidence.

### Guarantees Provided to Downstream Phases
After this phase is accepted:
- Users can manage native documents through approved, equivalent MCP and CLI surfaces.
- Public operation names and ownership are unambiguous.
- Source access is explicit and authorized separately from metadata.
- Mutation conflicts and processing states are visible and retryable.
- Repository deletion is confirmed and cannot be mistaken for compliance erasure.

### Known Limitations
- Hindsight destructive replacement is not implemented or claimed.
- Hindsight provider import, file/attachment ingestion, tag filtering, tag-based visibility scoping, observation scopes, `entities`/`resolve_entities`, provider fact-type names, item-level arbitrary metadata, and source-retention-disabled behavior are excluded or deferred.
- Bulk multi-document deletion is excluded unless separately approved later; one-document cascade deletion is the approved interpretation question in Phase 900611.
- Public tools do not yet guarantee export/import, sync, or full erase propagation; Phase 900625 owns those integrations.
- The 3–4 day estimate excludes catalog/review latency and unrelated baseline repair.

### Downstream Prerequisites
- Phase 900625 may extend these approved tools and existing portability/erase/sync operations without inventing another public document surface.
- Any provider adapter must preserve native Clio history, ship provider fixture or contract tests, and use separately approved destructive behavior only at the provider boundary.

### Final Status
BLOCKED

The current status is `BLOCKED` until the normative tool catalog, CLI ownership, and phase dependencies are approved. After implementation, replace this line only with evidence-backed `PASS`, `PASS WITH DOCUMENTED LIMITATIONS`, or `FAILED`.

### Verification Sign-Off
- Implementer: [TBD]
- Verifier: [TBD]
- Human Approver: required for operation names, source permissions, and repository-delete exposure
- Date: [TBD]

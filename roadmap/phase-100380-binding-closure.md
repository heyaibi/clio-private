# Phase 100380: Binding Closure — `summarize` and the FR-32 Config/Ranking Tools

### Attribution
Rounds below record plan authorship; implementation sign-off is in §12.
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | [TBD] | [TBD] |
| Adversary | r1 | [TBD] | [TBD] |
| Remediator | r1 | [TBD] | [TBD] |
| Remedy Approver | r1 | [TBD] | [TBD] |
| Finalize | r1 | [TBD] | [TBD] |

**Remediation phase 100380 · **Effort:** ~4–5 days · **Gaps:** G-01, G-02, G-17, G-18 · **Source:** `gap/requirement-gaps.md` §2, §3

## 1. Objective

### Goal
Close the two P0 binding breaks and the two related evidence gaps: bind the one defined-but-unbound Core tool `summarize`; expose the six FR-32 effective-config/ranking tools (`config_get`, `config_set`, `config_profiles`, `config_profile_apply`, `ranking_env_get`, `ranking_env_set`) over MCP with secret masking; mark `sync_ack_skip` as a documented extension; and add the schema-driven NFR-7 test.

### Expected Outcome
- Every Core tool (§4.9.4) and every FR-32 tool is callable over MCP; no published Core tool returns `not_implemented`.
- The published `tool_schema` pack name set equals `bound_tools()` exactly; the `summarize` carve-out in `schema_tests.rs` is removed.
- Every config/ranking view masks secrets; tests prove no plaintext secret appears in any view.
- `sync_ack_skip` is documented as a non-normative extension beyond §4.9.5.D.
- NFR-7 has a schema-driven test that passes, or an explicit recorded exception.

### Parent Requirement
`requirement.md` — FR-5 / FR-26 / §4.9.4 (`summarize`), FR-32 / §4.9.5.E (config/ranking tools), §4.9.5.D (`sync_ack_skip` extension), NFR-7 (language-agnostic schema exercisability). Gaps G-01, G-02, G-17, G-18.

### Design References
- `summarize` is already defined with a schema at `crates/clio-mcp/src/schema_read_defs.rs:73` and is the sole extra name in `crates/clio-mcp/src/schema_tests.rs:26-34`.
- The six config/ranking operations already exist as `Runtime` methods dispatched by `clio-config` (`crates/clio-config/src/config/dispatch.rs:34-52`); only the MCP schema and `clio-mcp` dispatch are missing.
- Secret masking already exists (`clio_config::secret::masked_clone`, used by `crates/clio-mcp/src/portability_tools.rs`).
- Publishing tools in the versioned `tool_schema` pack requires approval, recorded as an `Approval requested` subsection in this phase file and decided by the Remedy Approver step (Phase 100170 §9 precedent; Phases 100250/100260 follow it; Phase 100270's adversary enforced recording it). The pin stays `mcp_protocol_revision=2025-11-25`.

---

## 2. Scope Boundaries

### In Scope
- A `summarize` handler: regenerate gist(s) for a scope, snapshots byte-immutable, structured report.
- Six MCP schemas plus `clio-mcp` dispatch that delegates to the existing `clio-config` `Runtime` methods.
- Secret masking on all config/ranking views plus masking tests.
- The `sync_ack_skip` extension documentation paragraph.
- A schema-driven NFR-7 test over the published pack.

### Explicitly Out of Scope
- Provider adapters (Phase 100500).
- New configuration keys, new ranking knobs, or changes to effective-config precedence.
- Changing the masking policy or the secret mechanism.
- Widening the bound tool set beyond `summarize` + the six FR-32 tools.
- Changing `retention_profile_get` / `retention_profile_set`, which are already bound.

### Must Not Change
- Snapshots are never altered by `summarize` (PR-4 / §4.9.4).
- Admission and category gates are never bypassed by profile or ranking changes (FR-32).
- Existing tool names, semantics, and the pack format revision.
- The `not_implemented` fallback for genuinely unknown tools.

### Scope Expansion Rule
If work outside this scope appears necessary: stop, document the reason, request clarification or approval, and do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- Phase 100360 landed (per-file coverage guard).
- The MCP dispatch surface and schema pack are stable (Phases 016/017/035).

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| `clio-config` `Runtime::call_tool` | Serves the six tools | `crates/clio-config/src/config/dispatch.rs` |
| `clio-mcp` runtime | Holds a `Runtime` (used by retention tools) | `retention_tools.rs` / `mutator_tools.rs` |
| Secret masking | `masked_clone` available | `crates/clio-config/src/secret.rs` |
| Gist machinery | Existing gist generation path reachable | `clio-write` / `clio-index` discovery |
| `tool_schema` approval | Recorded as an `Approval requested` subsection; decided by the Remedy Approver | `roadmap/phase-100170-mcp-read-retrieve-compose-surface.md` §9 precedent |

---

## 4. Existing-System Discovery

The agent MUST re-verify the following; the facts below were confirmed at plan time.

### Required Discovery
- Confirm `summarize` has a schema but no dispatch branch and returns `not_implemented`.
- Confirm the exact published-name assertion in `schema_tests.rs` and where to remove the carve-out.
- Confirm there is (or is not) an existing `clio-mcp` dispatch path that reaches `clio-config` `Runtime::call_tool`; if none exists, locate the pattern used by `retention_profile_get` / `_set` and by the additive tools, and use it as the model for new branches.
- Confirm which config/ranking views can carry secrets and that masking is applied to each.
- Identify the existing gist generation path (what produced stored gists) so `summarize` reuses it rather than inventing a summarizer.
- Confirm the `tool_schema` publish approval rule and where approval is recorded.

### Discovery Output
- **`summarize` is schema-only.** `crates/clio-mcp/src/schema_read_defs.rs:73` defines it; `crates/clio-mcp/src/schema_tests.rs:26-34` asserts `published == bound_tools() + ["summarize"]`; no `clio-mcp` dispatch branch handles it, so the call falls to the `not_implemented` arm.
- **The six FR-32 tools have server-side logic in `clio-config` but are not exposed by `clio-mcp`.** `clio_config::Runtime::call_tool` (`crates/clio-config/src/config/dispatch.rs:34-52`) handles `config_get`, `config_set`, `config_profiles`, `config_profile_apply`, `ranking_env_get`, `ranking_env_set`; `bound_tools()` (`crates/clio-mcp/src/lib.rs:78-162`) omits them.
- **There is no existing `clio-mcp` → `Runtime::call_tool` seam.** A repository search finds no `call_tool` call site in `crates/clio-mcp/src/` outside test files. The `retention_profile_get` / `_set` tools are bound, but they do **not** route through `Runtime::call_tool`: `crates/clio-mcp/src/additive_tools.rs:47` and `crates/clio-mcp/src/read_tools.rs:44` dispatch to `crate::retention_tools` (`profile_set` / `profile_get`), which consume `clio_config` types (`RetentionProfile`, `runtime_retention`) directly. A `Runtime` is constructed in `crates/clio-mcp/src/runtime.rs:228` (and `ops_embedder.rs:81`), but nothing forwards MCP calls through it. The correct model is therefore to add new `clio-mcp` dispatch branches (following the `additive_tools.rs` / `read_tools.rs` pattern) that call the existing `clio_config` `Runtime` methods or `Runtime::call_tool`; treat the exact wiring as a discovery-and-implementation task, not as an existing seam to copy.
- **Masking exists.** `clio_config::secret::masked_clone` is already used for provider credentials; config/ranking views must route through the same masking.
- **`sync_ack_skip` is bound but undocumented.** `crates/clio-mcp/src/lib.rs:113` lists it; §4.9.5.D does not define it.
- **NFR-7 has no test.** Repository search for `NFR-7` returns nothing.

### Repository Adaptation Rule
The agent must determine concrete implementation locations from the actual repository. The plan does not prescribe file paths or module names unless they are an externally required contract.

---

## 5. Implementation Specification

### Task 1: Bind `summarize`

#### Intent
Make the last unbound Core tool callable, without touching snapshots.

#### Required Capability or Behavior
- `summarize(scope)` regenerates gist(s) for the given scope (bank or item) from existing snapshots and returns a structured report (items summarized, skipped, and why).
- Snapshots are byte-identical before and after; only gists change.
- The existing gist generation path is reused; if no gist generator is available/configured, the tool fails closed with a structured error rather than fabricating text.
- No new egress when no hosted provider is configured.

#### Architectural Responsibility
`clio-mcp` owns the binding and scope resolution; the gist generation machinery owns text production; snapshots remain owned by `clio-store` and are read-only here.

#### Required Changes
1. Add the dispatch branch and route it to the gist regeneration path.
2. Add `summarize` to the read bound list.
3. Remove the `summarize` carve-out from `schema_tests.rs` and assert `published == bound_tools()`.
4. Test snapshot immutability and the unavailable-generator failure.

#### Implementation Constraints
- Never write to snapshot columns; assert immutability in a test.
- Reuse the existing gist path; do not add a new summarizer or a new dependency.
- Respect bank scoping and authorization of the read path.

#### Expected Result
A `summarize` MCP call returns a structured report; snapshots are unchanged; no `not_implemented`.

### Task 2: Publish and Dispatch the Six FR-32 Tools

#### Intent
Make effective-config and ranking tools callable over MCP, with masking.

#### Required Capability or Behavior
- `config_get`, `config_set`, `config_profiles`, `config_profile_apply`, `ranking_env_get`, `ranking_env_set` are callable over MCP with the arguments described in §4.9.5.E.
- `config_set` validates types/ranges before apply and honors `session | profile | deployment` scope.
- `ranking_env_set` supports `dry_run` and rejects or renormalizes weights that must sum to 1.0.
- Every view masks secrets; no plaintext secret appears in any response.
- Profile/ranking changes never bypass admission or category gates.

#### Architectural Responsibility
`clio-mcp` owns schemas and dispatch; `clio-config` remains the single source of truth for behavior; masking stays in `clio-config`'s secret module.

#### Required Changes
1. Add the six schemas to the appropriate schema-defs module.
2. Add `clio-mcp` dispatch branches (following the `additive_tools.rs` / `read_tools.rs` pattern) that delegate to the existing `clio_config::Runtime` methods or `Runtime::call_tool`. There is no existing `clio-mcp` → `Runtime::call_tool` path to reuse (see §4); the branch is new wiring, and the exact call shape is a discovery item.
3. Add the six names to the bound lists.
4. Add masking tests that plant a secret and assert it is masked in `config_get`, `config_profiles`, and `ranking_env_get`.
5. Keep the pack assertion exact (`published == bound_tools()`).

#### Implementation Constraints
- Do not reimplement config or ranking logic in `clio-mcp`.
- Never log plaintext secrets or values.
- Do not change the pack format revision; only names are added.

#### Expected Result
All six tools are callable; views are masked; `schema_pack` names equal `bound_tools()`.

### Task 3: Document `sync_ack_skip` as an Extension

#### Intent
Resolve G-17's undocumented bound tool.

#### Required Capability or Behavior
- A paragraph in the user/developer docs states that `sync_ack_skip` is a non-normative extension beyond §4.9.5.D (a dead-letter ack helper with zero behavioral risk).

#### Architectural Responsibility
Documentation (`crates.md` and/or `README.md`). If `requirement.md` is edited, the requirement consistency procedure in `AGENTS.md` applies (cross-references, glossary, IDs).

#### Required Changes
1. Add the extension paragraph.
2. Prefer a docs-only change to avoid a normative revision.

#### Expected Result
The tool is documented as an extension; no normative contradiction remains.

### Task 4: Schema-Driven NFR-7 Test

#### Intent
Prove every published tool is exercisable through its schema without language dependence.

#### Required Capability or Behavior
- A test iterates the published pack, derives a minimal valid argument instance from each tool's JSON schema, and dispatches it over the MCP surface, asserting a structured response (no panic, and not `not_implemented` for a bound tool).
- If a tool cannot be dispatched without a live external provider, the exception is recorded explicitly and the test still asserts schema validity and bound-name equality for it.

#### Architectural Responsibility
`clio-mcp` test surface.

#### Required Changes
1. Add the schema-driven test.
2. Record any exception with the reason.

#### Implementation Constraints
- No network; deterministic; no new tool.
- Do not weaken the existing schema validation tests.

#### Expected Result
NFR-7 test green with an empty (or explicitly recorded) exception list.

### Implementation Freedom
The agent may choose schema module placement, dispatch seam, and test structure provided behavior, boundaries, and the exact pack assertion are respected.

---

## 6. Agent Execution Rules

### Allowed Actions
- Add schemas, dispatch branches, bound-list entries, tests, and docs.
- Reuse existing `clio-config` logic and gist machinery.

### Forbidden Actions
- Change snapshots; bypass admission/category gates; log plaintext secrets.
- Publish new tool names without `tool_schema` approval.
- Delete or bypass tests; claim completion without evidence.

### Agent Decision Boundary
The agent may decide module placement and test organization. The agent must request approval for: publishing the six new tool names in the versioned `tool_schema` pack, and (if chosen) binding `summarize`. If approval is denied, the fallback is the FR-32 narrowing path in Task 2's exception clause, which requires amending `requirement.md` under the consistency procedure.

### Mandatory Stop Conditions
Stop and report if: no gist generator exists and `summarize` cannot be implemented without new egress or a new dependency; the six tools cannot be bound without an unapproved pack change; or a config/ranking view cannot be masked.

---

## 7. Security Constraints

### Required Controls
- Secret masking on `config_get`, `config_profiles`, `ranking_env_get`, and any other view that can carry credentials.
- Authorization and bank scoping preserved for `summarize`.
- Profile/ranking changes must not bypass admission or category gates.

### Sensitive Data Rules
- Never log or return plaintext secrets, keys, or vectors.
- Reuse the existing masking mechanism; do not hand-roll a second one.

### Security Acceptance Conditions
- A planted secret is masked in every config/ranking view (test).
- No plaintext secret appears in test output or logs.

---

## 8. Test and Verification Strategy

### Required Tests
- [ ] Unit tests (scope resolution, masking, schema generation, argument validation)
- [ ] Integration tests (`summarize` over MCP; six tools over MCP; `dry_run` path)
- [ ] Contract tests (pack names equal `bound_tools()`; no `not_implemented` for bound tools)
- [ ] End-to-end tests (a full MCP request/response for each new tool)
- [ ] Regression tests (existing tools unchanged)
- [ ] Security tests (masking; gate non-bypass)
- [ ] Failure-mode tests (unknown tool still `not_implemented`; invalid scope/patch rejected; unavailable gist generator)

### Required Test Scenarios

| Test ID | Scenario | Expected Result |
|---------|----------|-----------------|
| T100380-01 | `summarize` over MCP on a scope with items | Structured report; gists regenerated |
| T100380-02 | Snapshots before/after `summarize` | Byte-identical |
| T100380-03 | `summarize` with no gist generator available | Structured error; no fabricated text |
| T100380-04 | `config_get` with a planted secret | Secret masked |
| T100380-05 | `config_set` with an invalid type/range | Rejected before apply |
| T100380-06 | `ranking_env_set` dry-run with non-normalized weights | Normalized or rejected with a clear error |
| T100380-07 | `config_profile_apply` | Returns effective diff; no gate bypass |
| T100380-08 | Pack names vs `bound_tools()` | Equal; no carve-out |
| T100380-09 | NFR-7 schema-driven dispatch over every published tool | Structured response; no `not_implemented` for bound tools |
| T100380-10 | Unknown tool name | Still `not_implemented` |
| T100380-11 | Regression suite | Workspace green |

### Negative Testing
Verify invalid scope/patch rejection, unknown-tool fallback, masking under planted secrets, and that no gate is bypassed.

### Verification Rule
Implementation claims must be supported by actual test output, not inspection alone.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-100380-01 | `summarize` callable; snapshots immutable | T100380-01, T100380-02 | Test output |
| AC-100380-02 | Six FR-32 tools callable over MCP | T100380-04…T100380-07 | Test output |
| AC-100380-03 | Pack names equal `bound_tools()` | T100380-08 | Test output |
| AC-100380-04 | No bound tool returns `not_implemented` | T100380-09, T100380-10 | Test output |
| AC-100380-05 | Every config/ranking view masks secrets | T100380-04 | Test output |
| AC-100380-06 | `sync_ack_skip` documented as extension | Inspection | Docs diff |
| AC-100380-07 | NFR-7 green or exception recorded | T100380-09 | Test output / exception note |
| AC-100380-08 | No regression | T100380-11 | Workspace test output |

### Definition of Done
- [ ] All in-scope behavior implemented.
- [ ] All acceptance criteria pass.
- [ ] Required tests pass.
- [ ] No unauthorized changes introduced.
- [ ] Existing behavior remains intact.
- [ ] Security checks pass.
- [ ] Documentation updated.
- [ ] Evidence collected and verification completed.
- [ ] Required approval obtained (`tool_schema` publish approval).

### Completion Evidence
- Implementation summary
- Schema/dispatch/bound-list diffs
- Test output for every scenario
- Masking evidence
- Pack-name equality evidence
- Known limitations

---

## 10. Failure Handling and Recovery

### Expected Failure Modes
| Failure | Detection | Recovery |
|---------|-----------|----------|
| `tool_schema` approval denied | Approval record | Fall back to FR-32 narrowing via `requirement.md` amendment |
| No gist generator available | Discovery | Fail closed; record the exception the requirement permits |
| Secret leaks in a view | Masking test | Fix masking before claiming completion |
| A tool cannot be schema-dispatched | NFR-7 test | Record the exception with a reason |

### Rollback Strategy
Remove the six bound names and the `summarize` binding; revert the pack assertion to the prior carve-out. No data is affected.

### Partial Completion Policy
Do not claim completion if only `summarize` or only the six tools landed. Record each separately and do not leave a state where a published tool is unbound.

---

## 11. Traceability

| Parent Requirement | Implementation Task | Verification | Acceptance Criterion |
|--------------------|---------------------|--------------|-----------------------|
| FR-5 / FR-26 / §4.9.4 (`summarize`) | Task 1 | T100380-01…T100380-03 | AC-100380-01 |
| FR-32 / §4.9.5.E (config/ranking) | Task 2 | T100380-04…T100380-07 | AC-100380-02, AC-100380-05 |
| §4.9.5.D (`sync_ack_skip` extension) | Task 3 | Inspection | AC-100380-06 |
| NFR-7 | Task 4 | T100380-09 | AC-100380-07 |
| Pack-name contract | Tasks 1–2 | T100380-08 | AC-100380-03 |
| No-unimplemented / regression contract | Tasks 1–2, 4 | T100380-09, T100380-10, T100380-11 | AC-100380-04, AC-100380-08 |

Required chain:

```text
Requirement → Capability → Implementation → Test → Evidence
```

---

## 12. Phase Exit Contract

### Outputs Produced
- `summarize` bound with a gist-regeneration handler.
- Six FR-32 tools bound with schemas and masking.
- `sync_ack_skip` extension documentation.
- NFR-7 schema-driven test.

### Guarantees Provided to Downstream Phases
After this phase is accepted:
- Every Core and FR-32 tool is callable over MCP.
- The published pack name set is exactly `bound_tools()`.

### Known Limitations
- FR-32 may be narrowed by revision instead of bound if `tool_schema` approval is denied.
- `summarize` depends on an available gist generator; without one it fails closed.

### Downstream Prerequisites
- Phase 100400's raw-ingest MCP wrapper reuses this phase's pack-approval pattern.

### Final Status
PASS | PASS WITH DOCUMENTED LIMITATIONS | BLOCKED | FAILED

### Verification Sign-Off
- Implementer: [TBD]
- Verifier: [TBD]
- Human Approver: required for `tool_schema` publish
- Date: [TBD]

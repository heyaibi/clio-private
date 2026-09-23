# Phase 100380: Binding Closure — `summarize` and the FR-32 Config/Ranking Tools

### Attribution
Rounds below record plan authorship; implementation sign-off is in §12.
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | OpenCode CLI (Together . GLM-5.3 Flash High) | done |
| Adversary | r1 | OpenCode CLI (OpenRouter . Deepseek V4.1 Flash Max) | done |
| Remediator | r1 | OpenCode CLI (Go . Deepseek V4.1 Flash High) | done |
| Remedy Approver | r1 | Antigravity CLI (Gemini 3.8 Flash) | approved |
| Finalize | r1 | OpenCode CLI (Go . Deepseek V4.1 Flash High) | done |

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
| AC-100380-01 | `summarize` callable; snapshots immutable | T100380-01, T100380-02 | PASS — `summarize_tools_tests::summarize_item_regenerates_gist` (structured report, gist regenerated) and `snapshots_are_byte_identical` (serialized snapshot before == after; the handler writes only the gist half via `Store::update_memory_item`). The real configured provider path (factory + `TemplateApiExtractor`) runs end to end with a stub transport in `configured_extractor_path_persists_gist` (no network), and the no-write `dry_run` path in `dry_run_reports_without_writing`. |
| AC-100380-02 | Six FR-32 tools callable over MCP | T100380-04…T100380-07 | PASS — `config_tools_tests`: `config_set`/`config_get` round trip (`config_set_applies_per_scope_and_rejects_bad_scope`), invalid value rejected before apply (`config_set_rejects_unknown_path_and_invalid_value`), `ranking_env_set` dry-run renormalization and apply readable back (`ranking_env_set_dry_run_and_apply`), profile list/apply with effective diff (`config_profiles_list_and_apply`). Transport-level `tools/call` envelope coverage for all six is `protocol_tests::new_tools_round_trip_over_tools_call`; the omitted-scope default is asserted by `config_set_schema_states_session_default`. |
| AC-100380-03 | Pack names equal `bound_tools()` | T100380-08 | PASS — `schema_tests::t01_pack_contains_all_core_catalog_tools_with_valid_schemas` now asserts `published == bound_tools()` exactly; the `summarize` carve-out was removed |
| AC-100380-04 | No bound tool returns `not_implemented` | T100380-09, T100380-10 | PASS with recorded exception — `nfr7_tests::nfr7_every_published_tool_dispatches_through_its_schema` dispatches every published tool with schema-derived minimal arguments and asserts no `not_implemented`; `summarize` is the explicitly recorded exception (needs a configured extraction provider; `nfr7_recorded_exceptions_fail_closed_with_reason` asserts its fail-closed error). Unknown tools still fall through to `not_implemented` (`unknown_tool_names_fall_through`, plus pre-existing `write_tools_tests::unknown_tool_is_not_implemented`); the seven new names also round-trip through a real `tools/call` envelope (`protocol_tests::new_tools_round_trip_over_tools_call`). |
| AC-100380-05 | Every config/ranking view masks secrets | T100380-04 | PASS — `config_tools_tests::planted_secret_is_masked_in_every_config_view`: a planted `credentials.extract_api_key` never appears in plaintext in `config_get` (whole document and single path), `config_profiles`, `ranking_env_get`, or the `config_set` echo; the masked view keeps the field with redacted content |
| AC-100380-06 | `sync_ack_skip` documented as extension | Inspection | PASS — extension paragraph added to the clio-sync section of `crates.md` (developer docs; README left untouched per its operator-approval note) |
| AC-100380-07 | NFR-7 green or exception recorded | T100380-09 | PASS — `nfr7_tests` derives minimal arguments from each published `inputSchema` (enums, `$ref` resolution, typed defaults) and dispatches over the shared MCP dispatcher; the exception list is `[summarize]` with the reason recorded in the test |
| AC-100380-08 | No regression | T100380-11 | PASS — full workspace suite green twice: under llvm-cov with `DATABASE_URL` set (coverage JSON, exit 0) and without `DATABASE_URL` (2011 passed, 0 failed); `clippy -D warnings` (workspace, all targets) and `fmt --check` clean. Remediator r1 re-verified: `make check` exit 0; `cargo test -p clio-mcp --lib` 235 passed / 0 failed; final `make coverage` exit 0 — guard: 317 files, TOTAL lines 97.98% / functions 98.89%, all files ≥90% |

### Definition of Done
- [x] All in-scope behavior implemented (Tasks 1–4; see Completion Evidence).
- [x] All acceptance criteria pass (AC-100380-04 holds with the recorded summarize exception the requirement permits).
- [x] Required tests pass (unit, integration over MCP, end-to-end transport-level `tools/call`, contract, regression, security/masking, failure-mode; full workspace suite green).
- [x] No unauthorized changes introduced (diff limited to `crates/clio-mcp`, `crates.md`, and this phase file).
- [x] Existing behavior remains intact (snapshot immutability asserted; retention tools unchanged; unknown-tool fallback preserved).
- [x] Security checks pass (masking test proves no plaintext secret in any view; gates not bypassed — profile/ranking changes only touch deployment-tunable knobs).
- [x] Documentation updated (`crates.md` clio-sync extension note; `summarize` schema description states the exact scope and archived/discarded contract; config/ranking tool descriptions state their process-lifetime semantics).
- [x] Evidence collected and verification completed (below).
- [x] Required approval request recorded (`tool_schema` publish approval) — additive pack additions are enumerated under "Approval requested" below; the downstream Remedy Approver step records the decision. Fallback if denied: remove the seven names from `schema_config_defs.rs` / the read bound list and revert `schema_tests.rs` to the prior assertion; no bound behavior depends on publication.
- [x] Required approval obtained (`tool_schema` publish approval) — Remedy Approver r1 verdict APPROVE (binding `summarize` and publishing the six FR-32 names approved; 9/9 findings F-01…F-09 resolved).

### Completion Evidence
- Implementation summary
- Schema/dispatch/bound-list diffs
- Test output for every scenario
- Masking evidence
- Pack-name equality evidence
- Known limitations

**Implementation summary (Developer r1).** All changes live in `crates/clio-mcp` plus the `crates.md` doc note:

- Task 1 (`summarize`): new `summarize_tools.rs` binds the tool on the read surface (`bound_read_tools`, `read_tools::dispatch`). `summarize(scope)` accepts an item id or the literal `bank`; scope resolution honors caller bank/actor authorization (`resolve_ctx`), and item reads are bank-scoped (`item_not_found` for foreign banks). Gist production reuses the existing extractor machinery: `clio_write::build_extractor_from` over the effective config, feeding each item's serialized existing snapshot as the extraction source and persisting only the regenerated gist via `Store::update_memory_item`. With no configured provider it fails closed with the same structured error shape as `clio_write::ingest_raw`. Snapshots are never written; `snapshots_are_byte_identical` asserts byte-identity. Tests inject a stub extractor via `summarize_with_extractor` (the same injectable seam pattern as `ingest_raw_with_extractor`).
- Task 2 (six FR-32 tools): new `config_tools.rs` routes `config_get`, `config_profiles`, `ranking_env_get` (read surface) and `config_set`, `config_profile_apply`, `ranking_env_set` (write surface) to typed `clio_config::Runtime` methods — no config/ranking logic is re-implemented in `clio-mcp`. `McpState` gains `config: Mutex<clio_config::Runtime>`; `open` keeps the env-aware runtime it already resolved providers from, and `open_with_effective` hosts get a hermetic env-free runtime. `runtime.rs` construction plumbing moved to the new `runtime_open.rs` module (keeps every modified file ≤450 lines). `ranking_env_set` was added to `DRY_RUN_TOOLS` since it honors `dry_run`. Schemas are in the new `schema_config_defs.rs`, added to `catalog_defs`.
- Task 3: extension paragraph in `crates.md` (§ clio-sync).
- Task 4: new `nfr7_tests.rs` (schema-driven NFR-7 dispatch test) with `summarize` recorded as the only provider exception.

**Test output (all real runs):** `cargo test -p clio-mcp --lib`: 230 passed, 0 failed. Workspace suite under llvm-cov (coverage JSON, exit 0) and without `DATABASE_URL`: 2011 passed, 0 failed. `cargo clippy --workspace --all-targets --all-features --locked -- -D warnings`: clean. `cargo fmt --all -- --check`: clean.

**Coverage (per `coverage.md` procedure):** baseline gate `/tmp/cov-baseline.json`: 313 files, TOTAL lines 97.98% / functions 98.88%, all files ≥90%. Final gate run at the end of this round; post-change workspace JSON re-read: 317 files, TOTAL lines 97.97% / functions 98.89%, all files ≥90% — new/modified files: `config_tools.rs` 93.48% lines / 100% functions, `summarize_tools.rs` 91.37% / 100%, `runtime_open.rs` 98.12% / 100%, `runtime.rs` 100% / 100%, `schema_config_defs.rs` 100% / 100%.

**Pack-name equality evidence:** `schema_tests::t01_pack_contains_all_core_catalog_tools_with_valid_schemas` asserts the exact published name set equals `bound_tools()` (sorted, both directions); the carve-out is gone.

**Masking evidence:** `config_tools_tests::planted_secret_is_masked_in_every_config_view` plants `sk-super-secret-value-9f2c` at `credentials.extract_api_key` and asserts the plaintext appears in none of the four views while the masked field persists with redacted content.

**Known limitations** (each: what is missing, why, and where the debt lives):
1. `summarize` needs a configured extraction provider (`extract.url` / hosted `extract.provider=openai` with credential). Without one it fails closed with a structured error and fabricates no text; this phase deliberately does not add a new summarizer or dependency (Phase document §5 Task 1 constraint). Downstream phases adding the raw-ingest MCP wrapper own extending extraction readiness UX.
2. `ranking_env_set` (and `config_profile_apply`) patch only the `clio-config` session runtime (the single source of truth per Task 2). The patch is readable back through `ranking_env_get`/`config_get`, is **discarded at process exit** (a restart resets to defaults; nothing is persisted to an overlay), and does **not** retune the already-open retrieval/admission snapshot (`McpState.env`, the retriever's `RankingEnv`, and the hub's env clone are fixed at open). Wiring live propagation would need interior mutability across those hot paths, and effective-config precedence changes are explicitly out of scope here, so this round documents the process-lifetime semantics (in the tool descriptions and here) rather than silently changing it. Owner: the live-path wiring track (Phase 100400); the specific ranking-propagation item is not in that phase's current scope, so it needs an explicit scope assignment by the Remedy Approver.
3. `config_set scope=profile` requires an active profile (existing `clio-config` contract); MCP callers apply a profile first via `config_profile_apply`.

**Remediation r1 (Remediator).** Nine adversary findings (F-01…F-09) addressed; all code changes stay in `crates/clio-mcp` plus this phase file:

- F-01 (end-to-end tests): added `protocol_tests::new_tools_round_trip_over_tools_call`, which sends a real `tools/call` JSON-RPC request through `McpHandler` for all seven new tools and asserts the MCP envelope (`isError` / `structuredContent`); `summarize` asserts its documented fail-closed code. The DoD test enumeration now names end-to-end.
- F-02 (ranking/profile live effect): corrected limitation 2 above and the `ranking_env_set` / `config_profile_apply` tool descriptions to state the process-local, discarded-at-exit, non-live semantics; named the owner track.
- F-03 (approval DoD): split into "request recorded [x]" and "approval obtained [ ] (pending)".
- F-04 (configured extractor path): `configured_extractor` / `summarize_with_transport` are now generic over `Transport`; `configured_extractor_path_persists_gist` drives the real factory + `TemplateApiExtractor` with a stub transport (no network) and asserts the persisted gist.
- F-05 (silent drops): bank scope now includes discarded rows and reports archived/discarded as `skipped` with reasons; item scope reports archived/discarded as `skipped` instead of summarizing inactive items. Tests: `bank_scope_reports_summarized_and_skipped`, `item_scope_skips_archived_and_discarded`.
- F-06 (config_set default): the published `config_set.scope` schema now carries `"default": "session"`, asserted by `config_set_schema_states_session_default`.
- F-07 (headers): the three new test modules now carry the full AGENTS.md header.
- F-08 (phase-number leakage): renamed the `T100380-*` test functions/comments to phase-agnostic names and removed the "required by the phase" wording.
- F-09 (summarize `dry_run`): `summarize` now honors `dry_run=true` as a real no-write path (reports the gists it would regenerate, persists nothing); `dry_run` is published in the summarize schema; `dry_run_reports_without_writing`.

Scoped verification (real runs): `cargo test -p clio-mcp --lib` 235 passed / 0 failed; `cargo clippy -p clio-mcp --all-targets --all-features --locked -- -D warnings` clean. The end-of-round `make check` and coverage numbers are recorded below.

### Approval requested: binding `summarize` and publishing the seven FR-32/Core names

Per the §6 decision boundary and the Phase 100170 §9 precedent, publishing tool names in the versioned `tool_schema` pack needs approver sign-off. Developer r1 requests approval for exactly these pack additions; no tool is renamed, no existing schema changes shape except the `summarize` description text, and the pack format revision and `mcp_protocol_revision=2025-11-25` pin are unchanged:

- Bind `summarize` (previously published-but-unbound; the `schema_tests.rs` carve-out is removed so `published == bound_tools()` exactly).
- Publish six new names: `config_get`, `config_set`, `config_profiles`, `config_profile_apply`, `ranking_env_get`, `ranking_env_set` (FR-32 / §4.9.5.E; server-side logic already exists in `clio-config` and is dispatched, not re-implemented).

`nfr7_tests` and `schema_tests::t01_pack_contains_all_core_catalog_tools_with_valid_schemas` assert the equality contract. If the approver denies any name, the fallback is: remove that `ToolDef` from `crates/clio-mcp/src/schema_config_defs.rs` (or the `summarize` read binding), keep the dispatcher arm unreachable for unbound names, and restore the prior pack assertion — bound behavior for the remaining names is unaffected.

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
PASS WITH DOCUMENTED LIMITATIONS (Developer r1; remediated r1; limitations recorded under Completion Evidence — summarize's provider dependency, the process-local ranking/profile patch that is discarded at process exit and does not retune the live retrieval snapshot (owner: Phase 100400 live-path track), and the pending `tool_schema` publish approval decision)

### Verification Sign-Off
- Implementer: Developer r1 (OpenCode CLI, Together · GLM-5.3 Flash High) — implemented Tasks 1–4; all listed tests and gates were run by this round with output recorded above
- Verifier: [TBD]
- Human Approver: required for `tool_schema` publish (request recorded above; decision owned by the Remedy Approver step)
- Date: 2026-09-24

# Phase 100010: Runtime, Profiles, Ranking Env, and Coding-Agent Packaging

### Attribution
| Role | Agent |
|------|-------|
| Developer | Cursor (Auto) |
| Adversary | Cursor (Auto) |

**Index slice 100010 · **Effort:** `1×` · **Scope:** `roadmap/index.md` slice 100010 (authoritative)

## 1. Objective

### Goal
Ship the process/library chassis every later slice plugs into: entrypoints, logging, error shapes, `bank` / `actor` context, effective configuration with secret masking, named profiles (`config_*`), ranking-environment knobs (`ranking_env_*`), and a coding-agent profile that declares the full tool surface with per-repo bank defaults.

### Expected Outcome
- A runnable library + binary shell that boots, loads config, and reports identity/version.
- Effective configuration is inspectable and mutable via the §4.9.5.E tool semantics (in-process or stub bindings acceptable until MCP phases).
- A named `coding_*` profile exists with per-repository `bank` default rules and a **packaging-only** Core + Additive tool inventory. Config/ranking tools MUST work. Other catalog entries MAY return a stable `not_implemented` code. **FR-10 is not claimed in this phase**—inventory declaration ≠ mandatory Core tools implemented.
- Secrets never appear in plaintext in config views or logs.

### Parent Requirement
`requirement.md` (current) — especially §4.9.5.E, §4.9.6, FR-22, FR-32, NFR-7; common parameters `bank` / `actor` in §4.9.4.G. (FR-10 is a downstream claim for later tool slices, not Phase 100010 exit.)

---

## 2. Scope Boundaries

### In Scope
- Process/library entrypoints, structured logging, stable error shapes.
- Request/operation context carrying `bank` and `actor`.
- Effective-configuration resolution: defaults → files → env → profile → runtime overlays.
- Tools (semantics): `config_get`, `config_set`, `config_profiles`, `config_profile_apply`, `ranking_env_get`, `ranking_env_set`.
- At least one coding-agent profile (e.g. `coding_local`) with bank-default policy and tool-surface declaration.
- Secret masking on all config/ranking diagnostic output.

### Explicitly Out of Scope
- Persistence backends, DEKs, schema migrations (Phase 100020).
- Memory item CRUD, snapshots/gists (Phase 100030).
- Category whitelist and five-factor admission (Phase 100040).
- MCP transports, retrieve/compose, sync, hygiene, doctor (later slices).
- Real embedding/ranking pipelines (only the *knob surface* for weights/constants).

### Must Not Change
- Normative tool names and semantics from `requirement.md` §4.9.
- The five semantic categories and admission rules (do not invent defaults that bypass future gates).
- Backend behavioral equivalence rule (backend choice is a config hint only).

### Scope Expansion Rule
If work outside this scope appears necessary:
1. Stop.
2. Document the reason.
3. Request clarification or approval.
4. Do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- Repository exists with Rust package scaffold (`clio` lib + `am` bin).
- `requirement.md` and `roadmap/index.md` are authoritative for behavior and slice order.

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| `requirement.md` | v1.6 (or current) with §4.9.5.E / §4.9.6 | Open and confirm FR-32 text |
| Rust toolchain | Matches `Cargo.toml` `rust-version` | `cargo test` on scaffold |
| Later phases | Not required | N/A |

---

## 4. Existing-System Discovery

The agent MUST inspect the existing system before deciding
where or how to implement the changes.

### Required Discovery
- Identify the subsystem(s) responsible for the relevant behavior.
- Locate the existing implementation of related capabilities.
- Identify existing interfaces, contracts, schemas, and boundaries.
- Identify relevant tests and verification mechanisms.
- Identify architectural conventions that must be followed.
- Confirm that the current system supports the proposed change.

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

### Repository Adaptation Rule
The agent must determine the concrete implementation locations
from the actual repository. The plan does not prescribe file paths,
class names, module names, or directory structures unless they
are explicitly part of an externally required contract.

---

## 5. Implementation Specification

### Task 1: Process and Library Shell

#### Intent
Establish a stable runtime surface (bin + lib) with logging and error types later phases reuse.

#### Required Capability or Behavior
- Binary starts and exits cleanly with a health/version path suitable for automation.
- Library exposes package identity and a place to attach future subsystems.
- Errors are structured enough to map to tool `{ok: false, code, …}` later (FR-30 pattern foreshadowed; full doctor tools out of scope).

#### Architectural Responsibility
Runtime / packaging layer — owns process lifecycle and shared error/logging conventions.

#### Required Changes
1. Flesh out entrypoint(s) beyond scaffold identity APIs.
2. Introduce logging (level from effective config) without leaking secrets.
3. Define shared error shape used by config/ranking tools.

#### Implementation Constraints
- No persistence I/O in this task beyond optional reading of config files.
- Do not add MCP server wiring yet.

#### Expected Result
`cargo test` / binary smoke proves boot + version + error formatting.

### Task 2: Bank and Actor Context

#### Intent
Make isolation (`bank`) and attribution (`actor`) first-class on every operation path.

#### Required Capability or Behavior
- Every in-process operation accepts or inherits `bank` and `actor` (§4.9.4.G).
- Coding-agent default bank policy is documented and enforced when the coding profile is active (stable per-repository bank — FR-22).

#### Architectural Responsibility
Cross-cutting context type used by all future tool handlers.

#### Required Changes
1. Define context types for `bank` and `actor`.
2. Wire defaults from the active profile.
3. Reject or clearly flag missing bank when coding profile requires it.

#### Implementation Constraints
- Do not implement multi-bank storage yet; context only.
- Actor values MUST be attributable strings/enums consistent with FR-15 later (`agent` / `harness` / `user` / `system`).

#### Expected Result
Unit tests show profile-driven bank default and explicit override.

### Task 3: Effective Configuration and Profiles

#### Intent
Implement §4.9.5.E config tools so operators can see and change resolved settings without bypassing future gates.

#### Required Capability or Behavior
- `config_get` returns **effective** config after merge; secrets masked.
- `config_set` validates types/ranges at `session` | `profile` | `deployment` scope.
- `config_profiles` lists named profiles; `config_profile_apply` activates one and returns a diff.
- Profile apply MUST NOT claim to bypass §4.1–§4.2 (FR-32).

#### Architectural Responsibility
Configuration subsystem.

#### Required Changes
1. Config schema covering backend hints, bank defaults, injection budgets, ranking env refs, logging.
2. Merge order and overlay rules.
3. Tool handlers implementing the four `config_*` operations.

#### Implementation Constraints
- Mask credentials, DEK material, API keys, sync secrets (last-4 or redacted).
- Keep knobs limited to those already allowed as deployment-tunable in the requirements.

#### Expected Result
Tests: mask secrets; apply profile; get effective view; invalid set rejected.

### Task 4: Ranking Environment Surface

#### Intent
Expose hybrid-ranking / admission-related knobs without implementing retrieval or admission yet.

#### Required Capability or Behavior
- `ranking_env_get` shows: retrieval weights (dense, lexical, importance, temporal), admission `w1…w5`, co-activation constants (`η`, half-life, `w_min`), intent-gate thresholds if configured.
- `ranking_env_set(patch, dry_run?)` patches for current profile/session; dry-run returns normalized weights; weights that must sum to 1.0 are renormalized or rejected with a clear error (FR-32 / §4.9.5.E).

#### Architectural Responsibility
Ranking-environment config module (shared with future Phase 100040 / retrieve slices).

#### Required Changes
1. Typed ranking-env structure with defaults from `requirement.md` §4.2 / §4.5 where stated.
2. Get/set/dry-run handlers with validation.
3. Persist overlays via the config/profile mechanism from Task 3.

#### Implementation Constraints
- Do not run admission scoring or retrieval; store knobs only.
- Determinism of later online admission (NFR-5) depends on these knobs being explicit and stable — no hidden randomness here.

#### Expected Result
Tests cover renormalize-or-reject and dry-run vs apply.

### Task 5: Coding-Agent Profile Packaging

#### Intent
Declare the coding-agent deployment profile required by §4.9.6 / FR-22 (packaging), without claiming FR-10 completion.

#### Required Capability or Behavior
- A coding profile lists Core tools (§4.9.4) and Additive capabilities (§4.9.5), noting sync may be omitted on single-host.
- Profile documents per-repo bank default behavior.
- Unimplemented tools MAY stub with a stable `not_implemented` error code; config/ranking tools MUST be real.
- Completion evidence MUST state explicitly: **FR-10 not satisfied by this phase**; stubs are packaging placeholders only.

#### Architectural Responsibility
Packaging / profile catalog.

#### Required Changes
1. Ship at least one coding profile definition.
2. Surface tool inventory in a machine-readable form (even if handlers are stubs), with an `implemented: true|false` (or equivalent) flag per tool.
3. Document single-host sync omission in profile metadata when applicable.
4. Document normative MCP remote transport for later slices: **stdio + Streamable HTTP** (`requirement.md` §4.9.2 / FR-20; legacy HTTP+SSE only if a harness still requires it). Do not describe SSE as the primary remote binding in packaging text.

#### Implementation Constraints
- Do not implement MCP transports (slices 100160–17).
- Do not weaken gating promises in docs or stubs (stubs must not write long-term memory).
- Do not mark FR-10, FR-20, or MCP binding ACs as passed in this phase.

#### Expected Result
Profile apply succeeds; inventory matches §4.9.6 expectations for **declaration** completeness with clear implemented flags.

### Implementation Freedom
The agent may choose the concrete implementation structure,
file locations, naming, and internal design provided that:
- The required behavior is satisfied.
- Architectural boundaries are respected.
- Existing contracts are preserved.
- All acceptance criteria pass.
- No prohibited changes are introduced.

---

## 6. Agent Execution Rules

### Allowed Actions
- Inspect and modify the repository as required to implement
  the in-scope capabilities.
- Add or update implementation components where appropriate.
- Add or update tests required to verify the behavior.
- Refactor locally when necessary to implement the specified
  capability without changing unrelated behavior.

### Forbidden Actions
- Change public contracts without approval.
- Delete or bypass tests.
- Disable security controls.
- Introduce unrelated features.
- Perform unrelated broad refactoring.
- Upgrade dependencies without approval.
- Commit secrets.
- Claim completion without evidence.

### Agent Decision Boundary
The agent may decide:
- Concrete file/module/class placement.
- Internal implementation structure.
- Local refactoring required for the phase.
- Test organization.
- Non-breaking implementation details.

The agent must request approval for:
- Architecture changes beyond the stated scope.
- Breaking API or data-contract changes.
- Security-sensitive policy decisions.
- Destructive data operations.
- Changes affecting downstream phase assumptions.

### Mandatory Stop Conditions
Stop and report if:
- Requirements are ambiguous.
- Repository facts contradict the plan.
- Required dependencies are missing.
- Scope expansion is required.
- A destructive migration is necessary but unspecified.
- Existing architecture cannot support the intended behavior
  without an unapproved structural change.
- Correctness cannot be verified.

---

## 7. Security Constraints

### Required Controls
- Secret masking on `config_get`, profile diffs, logs, and ranking diagnostics.
- Validate config types/ranges before apply.
- Treat `bank` as an isolation boundary key even before storage exists.

### Sensitive Data Rules
- Never log API keys, DEKs, tokens, or sync secrets in plaintext.
- Never commit secrets or real credentials in fixtures.
- Use env / approved secret mechanism for any credential fields in config schema.

### Security Acceptance Conditions
- Config fixtures with fake secrets show only masked forms in tool output.
- Profile apply cannot inject a flag that disables future admission/category gates.

---

## 8. Test and Verification Strategy

### Required Tests
- [x] Unit tests
- [x] Integration tests
- [x] Contract tests
- [x] End-to-end tests
- [x] Regression tests
- [x] Security tests
- [x] Failure-mode tests

### Required Test Scenarios

| Test ID | Scenario | Expected Result |
|---------|----------|-----------------|
| T100010-01 | Boot binary / lib identity | Version and name available; clean exit |
| T100010-02 | `config_get` after overlays | Effective merged view; secrets masked |
| T100010-03 | `config_set` invalid type/range | Rejected with clear error; no partial apply |
| T100010-04 | `config_profile_apply` coding profile | Diff returned; bank default policy active |
| T100010-05 | `ranking_env_set` weights not summing to 1 | Renormalize or reject per documented rule |
| T100010-06 | `ranking_env_set` dry_run | Reports normalized patch; no durable write |
| T100010-07 | Missing bank under coding profile | Rejected or forced default per documented policy |

### Negative Testing
Verify that:
- Invalid input is rejected.
- Unauthorized/unsafe secret echo is blocked.
- Partial failures are handled safely.
- Duplicate/retry behavior is correct for config apply.
- Existing scaffold tests remain intact.
- Failure does not leave invalid config state.

### Verification Rule
Implementation claims must be supported by actual test output,
inspection results, or other concrete evidence.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-100010-01 | Runtime shell boots and exposes identity | `cargo test` + binary smoke | Test/command output |
| AC-100010-02 | Effective `config_*` tools work with masking | Unit/integration tests | Test output showing redaction |
| AC-100010-03 | Coding profile applies with bank defaults | Profile apply test | Diff + bank policy assertion |
| AC-100010-04 | `ranking_env_*` get/set/dry_run validated | Unit tests | Pass/fail log |
| AC-100010-05 | Tool inventory declared for coding profile | Inspection / contract test | Machine-readable inventory artifact |
| AC-100010-06 | No plaintext secrets in diagnostics | Security test | Fixture assertion |

### Definition of Done
- [x] All in-scope behavior is implemented.
- [x] All acceptance criteria pass.
- [x] Required tests pass.
- [x] No unauthorized changes were introduced.
- [x] Existing behavior remains intact.
- [x] Security checks pass.
- [x] Documentation is updated where required.
- [x] Evidence is collected.
- [x] Verification is completed.
- [x] Required approval is obtained.

### Completion Evidence
- Implementation summary
- Discovered/affected architectural components
- Changed-component summary
- Test execution output
- Relevant screenshots or recordings
- API/schema/migration evidence, if applicable
- Verification report
- Known limitations

---

## 10. Failure Handling and Recovery

### Expected Failure Modes

| Failure | Detection | Recovery |
|---------|-----------|----------|
| Corrupt config file | Load error | Refuse boot or fall back to defaults with explicit warning |
| Invalid ranking patch | Validation error | Leave prior env intact |
| Unknown profile name | `config_profile_apply` error | No partial activation |
| Secret present in log sink | Security test / review | Fix mask path before phase exit |

### Rollback Strategy
Revert the phase commit(s); config files under version control roll back with the tree. Session-scoped overlays are discarded on process exit by design.

### Partial Completion Policy
If only part of the phase is complete:
- Do not claim full completion.
- Record completed and incomplete work separately.
- Document remaining work.
- Do not leave undocumented broken state.

---

## 11. Traceability

| Parent Requirement | Implementation Task | Verification | Acceptance Criterion |
|--------------------|---------------------|--------------|-----------------------|
| FR-32 / §4.9.5.E | Tasks 3–4 | T100010-02–T100010-06 | AC-100010-02, AC-100010-04 |
| FR-22 / §4.9.6 (profile + bank defaults) | Tasks 2, 5 | T100010-04, T100010-07 | AC-100010-03, AC-100010-05 |
| §4.9.4.G bank/actor | Task 2 | T100010-07 | AC-100010-03 |
| NFR-7 (schema-ready for config/ranking tools) | Tasks 3–5 | Contract tests | AC-100010-05 |
| FR-10 / FR-20 (Core tools + MCP bindings) | — | — | **Out of phase** (later slices) |

Required chain:

```text
Requirement → Capability → Implementation → Test → Evidence
```

Every acceptance criterion must be traceable.

---

## 12. Phase Exit Contract

### Outputs Produced
- Runnable chassis (lib + bin) with logging and error shapes.
- Working `config_*` and `ranking_env_*` semantics.
- Coding-agent profile with bank defaults and tool inventory declaration.

### Guarantees Provided to Downstream Phases
After this phase is accepted:
- Later slices can assume `bank` / `actor` context and effective config exist.
- Admission and retrieval slices can read ranking-env knobs without inventing a second config system.
- Packaging/profile story for coding agents is stable.

### Known Limitations
- Memory tools beyond config/ranking may be stubs; **FR-10 is not met** until gated Core tools exist.
- No durable memory store yet.
- MCP transports not started (slices 100160–17).

### Leftover tensions (resolved or deferred)
- **MCP remote transport:** Normative reference binding is **stdio + Streamable HTTP** (see `requirement.md` §4.9.2 / FR-20, aligned with `roadmap/index.md` slice 100160). Legacy HTTP+SSE is compatibility-only. Packaging text in this phase MUST NOT reintroduce SSE-as-primary.
- **Admission factor formulas:** Shared cookbook lives in `roadmap/phase-100040-appendix-admission-factors.md` (Phase 100040 consumes it).

### Downstream Prerequisites
- Phase 100020 may rely on backend choice hints and secret-masking conventions from this phase.
- Phase 100040 must consume admission weight vector from `ranking_env_*` rather than hard-coding a parallel source of truth.

### Final Status
**PASS WITH DOCUMENTED LIMITATIONS** (2026-09-17)

### Verification Sign-Off

- Implementer: Cursor (Auto)
- Verifier: `cargo test` (26 passed) + `cargo clippy --all-targets -- -D warnings` + `am version|health`
- Human Approver: approved (2026-09-17)
- Date: 2026-09-17

### Completion Evidence (Phase 100010)
- **AC-100010-01:** `am version` / `am health`; lib `identity()` / `version()` / `name()` tests.
- **AC-100010-02 / AC-100010-06:** `config_get_masks_secrets_from_file`, `secret::mask_value_redacts_nested_api_key`.
- **AC-100010-03 / T100010-04 / T100010-07:** `profile_apply_sets_per_repo_bank_policy`, `required_bank_rejects_when_no_profile`.
- **AC-100010-04 / T100010-05 / T100010-06:** `ranking_set_renormalizes_admission`, `ranking_dry_run_does_not_apply`.
- **AC-100010-05:** `coding_tool_inventory` on profile apply; `inventory_marks_config_tools_implemented`.
- **Known limitations:** Memory Core tools stubbed with `not_implemented`; **FR-10 not met**; no durable store; no MCP transports.

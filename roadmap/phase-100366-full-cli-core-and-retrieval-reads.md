# Phase 100366: Full CLI Core Plumbing and Retrieval Read Surface

### Attribution
Rounds below record plan authorship; implementation sign-off is in §12.
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | [TBD] | [TBD] |
| Adversary | r1 | [TBD] | [TBD] |
| Remediator | r1 | [TBD] | [TBD] |
| Remedy Approver | r1 | [TBD] | [TBD] |
| Finalize | r1 | [TBD] | [TBD] |

**Follow-up phase 100366 · **Effort:** ~3 days · **Gaps:** `gaps/full-cli.md` §5, §7 step 1 (CLI output/exit contract + first read commands)

## 1. Objective

### Goal
Give `clio` a real memory read surface without any MCP client: a shared CLI output/exit-code/error contract, an argument-parser contract, a machine-readable help catalog, and the flagship retrieval commands `recall`, `get`/`show`, `inspect`, and `stats`, all routed through the same in-process gating and semantics the MCP tools use.

### Expected Outcome
- `clio recall "q" --bank demo | jq` works blind (JSON default when piped), and the same command on a TTY prints a human table; `--output json|text` overrides both ways.
- `clio remember` is not in this phase, but the read path proves the plumbing end to end.
- Every error prints `code`, `message`, and `hint`; on a TTY the message is human-readable text; the structured envelope is reserved for non-TTY or `--output json`. Unknown commands suggest the closest command and exit 2.
- `clio help --json` emits a machine catalog generated from `clio_mcp::schema::schema_pack()` (`catalog_defs()` names), so CLI and MCP cannot drift; after Phase 100380 those names equal `bound_tools()`.

### Parent Requirement
`gaps/full-cli.md` §5 (UX contract), §7 step 1 (reads first), §9 (constraints), §10 (acceptance); `requirement.md` §4.9.2 item 2 (every Core tool exposed through a harness-consumable binding with identical names/semantics), FR-10/FR-20 (catalog exposure), FR-30 (exit codes).

### Name and Binding-Syntax Note
`requirement.md` §4.9.2 item 2 states "Binding syntax MAY differ; names and semantics MUST NOT." This plan reads CLI verbs as **binding syntax**: `clio recall` invokes the `retrieve` tool, `clio remember` invokes `store`, and `clio show`/`get` invoke `get`. The tool name each verb maps to MUST be printed in `clio help` and in `clio help --json` (as a `tool` field), so names never silently drift. If the operator prefers strict name parity, the fallback is to rename the verbs to the tool names (`retrieve`, `store`); that decision is recorded here rather than left implicit. No `requirement.md` edit is required for this reading, but if one is ever made it follows the AGENTS.md consistency procedure.

### Design References
- Dispatch is `crates/clio-lib/src/main.rs:43`; flags via hand-rolled `parse_flags` (`:89`); help via `print_help` (`:266`).
- The MCP tool catalog: `catalog_defs()`/`schema_pack()` (`crates/clio-mcp/src/schema.rs:41,57`, using `schema_defs::ToolDef` at `:26`) and `bound_tools()` (`crates/clio-mcp/src/lib.rs:158`).
- The in-process dispatch seam: `clio_mcp::protocol::McpHandler::new(state)` plus `handle_message(&Value) -> Option<Value>` (`crates/clio-mcp/src/protocol.rs:53,72`), over `McpState::open` (`crates/clio-mcp/src/runtime.rs:227`). No socket is required.
- Store/runtime seams already used by ops: `clio_config::Runtime::new()` (`crates/clio-lib/src/ops_cli.rs:128`), `clio_mcp::runtime::{now_utc, build_ops_embedder}` (`ops_cli.rs:140-141`).
- Redaction: `clio_ops::redact_credentials` (`crates/clio-ops/src/finding.rs:177`); masking: `clio_config::secret` (`crates/clio-config/src/secret.rs`).
- DB precedence: `clio_config::db_path::resolve_database` (`crates/clio-config/src/db_path.rs`).

---

## 2. Scope Boundaries

### In Scope
- Global flags on every command: `--db`, `--backend`, `--bank`, `--actor`, `--output json|text`, `--no-input`.
- An explicit argument-parser contract (positionals, boolean flags, `--flag value` and `--flag=value`, global flags before or after the verb), implemented without a dependency.
- Output contract: data on stdout, diagnostics on stderr; JSON default when piped; human table on TTY; no ANSI when piped; honor `NO_COLOR`; human-readable error message on a TTY, structured `code`/`message`/`hint` envelope for non-TTY or `--output json`.
- Exit 0 ok, 1 operational failure, 2 usage error (matching the existing ops contract).
- Unknown-command suggestion and `did you mean` for unknown flags.
- `clio help --json` catalog generated from the same source as `schema-export`; each entry carries the tool name it binds.
- Read commands: `recall` (→ `retrieve`), `get`/`show` (→ `get`/`get_snapshot`/`get_gist`), `inspect`, `stats`.

### Explicitly Out of Scope
- Any write or mutation command (Phase 100370/100372); destructive commands (Phase 100374).
- `status` (Phase 100362) and HTTP bind (Phase 100364).
- GUI/TUI, shell completions, plugin system.
- New dependencies (no arg-parsing crate; the phase-100320 constraint stands).

### Must Not Change
- The DB precedence chain (route through `db_path`, never a second copy).
- stdio framing purity and the pinned MCP revision.
- MCP tool semantics, gating, and names — the CLI must produce identical results.
- The ops exit-code contract.
- **Reserved top-level verbs**: `version|health|help|mcp|ops|retention|compose|setup` (main.rs:43-67) are taken. New verbs MUST NOT collide; in particular `compose` is the Docker lifecycle command (`clio compose up|down`) and `compose_context` is therefore bound as `clio compose-context`, never `clio compose`.

### Scope Expansion Rule
If work outside this scope appears necessary: stop, document the reason, request clarification or approval, and do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- Phases 100310 (DB resolver), 100320 (compose/module conventions), 100360 (per-file coverage guard) landed.
- The `clio-mcp` in-process dispatch is callable from `clio-lib` (confirmed: `McpHandler::new` + `handle_message`, protocol.rs:53,72).

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| In-process tool dispatch | Callable without a socket | `crates/clio-mcp/src/protocol.rs:53,72` |
| `tool_schema` pack | Names + schemas available | `clio_mcp::schema::schema_pack()` (schema.rs:57) |
| DB resolver | Shared precedence | `clio_config::db_path` |
| Secret masker / redactor | Available | `clio_config::secret`, `clio_ops::redact_credentials` |

---

## 4. Existing-System Discovery

The agent MUST re-verify the following; the facts below were confirmed at plan time.

### Required Discovery
- Confirm the in-process dispatch entry (`McpHandler::new` + `handle_message`) can run a read tool with structured args from `clio-lib`.
- Confirm the exact `ToolDef`/schema source that `catalog_defs()` and `schema_pack()` share, so `help --json` reuses it.
- Confirm and resolve `parse_flags` limitations (positionals dropped, no boolean flags, `--flag value` only) and decide the grammar.
- List the reserved top-level verbs before introducing any new verb.
- Confirm the existing `ops` exit-code mapping (`crates/clio-lib/src/ops_cli.rs:36`) to keep 0/1/2 consistent.
- Audit existing CLI output/exit behavior (`ops`, `retention`, `compose`) for inconsistencies the shared contract must reconcile rather than duplicate.
- Identify all masking/redaction call sites to reuse.

### Discovery Output
- **No output layer today.** Commands print with `println!`/`eprintln!`; no TTY detection, no `--output`, no `NO_COLOR`.
- **Dispatch is manual.** `main.rs:43` matches top-level commands; there is no shared flag/output framework.
- **The in-process seam exists and needs no socket.** `McpHandler::new(Arc<McpState>)` + `handle_message(&Value) -> Option<Value>` (protocol.rs:53,72) route `tools/call` and return a JSON-RPC response; `McpState::open` (runtime.rs:227) builds the state. The CLI can therefore reuse gating and semantics exactly. This resolves the principal unknown that would otherwise gate phases 100366–100378.
- **`parse_flags` cannot express the required CLI.** `main.rs:89-104` inserts only `--`-prefixed tokens and consumes `it.next()` unconditionally, so positionals are silently dropped and a boolean flag followed by a token mis-captures it. `clio recall QUERY`, `clio get ID --snapshot`, and `--dry-run`/`--confirm` are unusable as-is. This is a required task, not an open question.
- **`help --json` uses `catalog_defs()`.** `schema_pack()` is built from `catalog_defs()` (schema.rs:41,58); after Phase 100380 its names equal `bound_tools()` (lib.rs:158). Before that, `summarize` is the only difference.
- **Existing output is inconsistent.** `ops` prints compact JSON unconditionally (ops_cli.rs:315-319); `retention` prints pretty JSON (retention_cli.rs:56+); both write human error text to stderr. The shared contract keeps stdout as data, keeps stderr human on a TTY, and adds `--output` rather than rewriting the existing commands.
- **Coverage guard is active.** Every new module must ship tests; `make coverage` enforces the per-file floor.

### Repository Adaptation Rule
The agent must determine concrete implementation locations from the actual repository. The plan does not prescribe file or module names.

---

## 5. Implementation Specification

### Task 1: CLI Argument, Output, and Error Contract

#### Intent
Establish one shared behavior every later CLI command inherits.

#### Required Capability or Behavior
- **Parser grammar:** a verb followed by an ordered list of positionals and flags; flags accept `--flag value` and `--flag=value`; documented boolean flags (`--dry-run`, `--confirm`, `--snapshot`, `--yes`, `--no-input`) take no value; global flags (`--db`, `--backend`, `--bank`, `--actor`, `--output`) may appear before or after the verb; an unknown flag fails closed with a `did you mean` suggestion and exit 2.
- **Output contract:** data on stdout, diagnostics on stderr; JSON default when piped, human table on a TTY, no ANSI when piped, honor `NO_COLOR`; an explicit `--output` always wins over TTY detection.
- **Error contract:** on a TTY, a human-readable message on stderr; for non-TTY or `--output json`, a `{ok:false, code, message, hint}` envelope. Exit 0/1/2 unchanged.
- Unknown-command handling suggests the closest command and exits 2.
- `clio help --json` emits the catalog with each entry's tool name.

#### Architectural Responsibility
`clio-lib` owns the contract; it delegates data retrieval to `McpHandler::handle_message` and masking to `clio-config`/`clio-ops`.

#### Required Changes
1. Add CLI support modules (output, errors, parser) under the 450-line cap.
2. Implement the grammar above with unit tests for the ambiguous cases (positional followed by flag, boolean flag before a positional, `--flag=value`, unknown flag).
3. Route the existing `ops`/`retention`/`compose` output through the shared renderer where it does not change their contract; record any behavior intentionally left as-is.
4. Add `clio help --json`, generated from `catalog_defs()`/`schema_pack()`, with a `tool` field per entry.

#### Implementation Constraints
- No new dependencies.
- **Choice and tradeoff (recorded):** default JSON when piped and human table on a TTY follows clispec.dev Principle 1 (`SHOULD` structured output when piped) and agent-CLI practice; clig.dev instead favors human-first output with `--json` opt-in. This plan takes the piped-JSON default but keeps a human error message on a TTY, following clispec.dev v0.3's reversal of the always-JSON error envelope. No ANSI escapes when stdout is not a TTY; respect `NO_COLOR` (clig.dev).
- Keep the existing documented exit codes; do not invent new ones.
- Do not change MCP behavior.

#### Expected Result
Every command emits consistent output and errors; scripts and humans both work; the parser supports positionals and boolean flags.

### Task 2: Retrieval Read Commands

#### Intent
Ship the flagship reads through the same gating as MCP.

#### Required Capability or Behavior
- `clio recall QUERY [--bank B] [--limit N] [--domains LIST] [--as-of TS] [--time-axis valid|transaction] [--output ...]` → `retrieve`.
- `clio get ID` / `clio show ID [--snapshot|--gist]` → `get`/`get_snapshot`/`get_gist`.
- `clio inspect [--filter ...] [--limit N]` → `inspect`, with `truncated` metadata in-band.
- `clio stats` → `stats`.
- Results are byte-identical in meaning to the MCP tools, called through `McpHandler::handle_message` over `McpState::open`.

#### Architectural Responsibility
`clio-lib` renders; `clio-mcp` (in-process) and the underlying crates own semantics and gating.

#### Required Changes
1. Add one module per command group (for example retrieval/id reads), each under 450 lines.
2. Add golden stdout/stderr tests and exit-code tests.
3. Document each command in `print_help` and `help --json`, including the tool name it binds.

#### Implementation Constraints
- Never silently truncate `retrieve`/`inspect`; expose limits and `truncated`.
- Bound output; honor `--limit`.
- Never re-implement retrieval or gating logic.

#### Expected Result
`recall`/`get`/`inspect`/`stats` run by hand with no MCP client.

### Implementation Freedom
The agent may choose module names, table formatting, and help layout, provided semantics match MCP and the constraints hold.

---

## 6. Agent Execution Rules

### Allowed Actions
- Add the support and read-command modules, tests, and help text.
- Refactor the existing top-level dispatch to share the new contract.

### Forbidden Actions
- Add dependencies; change MCP semantics, gating, or names.
- Add write/destructive/config/sync commands (other phases own them).
- Change the DB precedence chain or the ops exit codes.
- Introduce a verb that collides with a reserved top-level verb.

### Agent Decision Boundary
The agent may decide parsing structure, table format, and module layout. The agent must request approval for any change to the exit-code contract or for adding an arg-parsing dependency.

### Mandatory Stop Conditions
Stop and report if the in-process dispatch cannot be invoked without a socket (it can, per §4), if positionals cannot be parsed without a new dependency, or if a read tool's semantics cannot be reproduced identically.

---

## 7. Security Constraints

### Required Controls
- Mask secrets in every view and every error string (`clio_config::secret`, `clio_ops::redact_credentials`).
- Validate flags before side effects; unknown flags fail closed.
- No network or mutation in read commands.

### Sensitive Data Rules
- Never print plaintext credentials, tokens, vectors, or secrets.
- Prefer env over argv for any future secret-bearing flag; document masking.

### Security Acceptance Conditions
- A planted secret never appears in any read-command output or error.
- Read commands perform no writes.

---

## 8. Test and Verification Strategy

### Required Tests
- [ ] Unit tests (parser grammar, output mode selection, error rendering, suggestion)
- [ ] Integration tests (`recall`/`get`/`inspect`/`stats` against in-memory SQLite)
- [ ] Contract tests (JSON default when piped; TTY table; exit codes 0/1/2; explicit `--output` wins)
- [ ] End-to-end tests (golden stdout/stderr)
- [ ] Regression tests (existing ops/retention/compose unchanged)
- [ ] Failure-mode tests (unknown command, unknown flag, missing arg, invalid value)

### Required Test Scenarios

| Test ID | Scenario | Expected Result |
|---------|----------|-----------------|
| T100366-01 | `recall q` piped | JSON on stdout; diagnostics on stderr |
| T100366-02 | `recall q` on TTY | Human table; exit 0 |
| T100366-03 | `--output text` when piped | Text, not JSON (explicit wins) |
| T100366-04 | `clio get <id>` | Item returned; identical to MCP `get` |
| T100366-05 | `clio inspect --limit 1` | Bounded; `truncated` present when applicable |
| T100366-06 | `clio bogus` | Closest-command suggestion; exit 2 |
| T100366-07 | Error path on TTY vs piped | Human message on TTY; envelope when piped; secrets masked |
| T100366-08 | `clio help --json` | Catalog names equal `schema_pack()`/`catalog_defs()`; each entry names its tool |
| T100366-09 | parser edge cases | `recall QUERY --limit 2`, boolean `--dry-run`, `--flag=value`, unknown flag all behave per grammar |
| T100366-10 | Regression suite | Workspace green; per-file coverage ≥90% |

### Negative Testing
Verify unknown flags/commands fail closed, no ANSI when piped, and no secret leaks.

### Verification Rule
Implementation claims must be supported by actual command output and `make coverage`.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-100366-01 | `recall`/`get`/`inspect`/`stats` run with no MCP client | T100366-01…T100366-05 | Command output |
| AC-100366-02 | Piped JSON default; TTY table; `--output` overrides | T100366-01…T100366-03 | Output diff |
| AC-100366-03 | Errors actionable; human on TTY, envelope when piped; unknown command suggests | T100366-06, T100366-07 | Command output |
| AC-100366-04 | `help --json` catalog matches `schema_pack()` and names each tool | T100366-08 | Diff of names |
| AC-100366-05 | Parser supports positionals and boolean flags without a dependency | T100366-09 | Test output |
| AC-100366-06 | No regression; coverage green | T100366-10 | `make check`, `make coverage` |

### Definition of Done
- [ ] All in-scope behavior implemented.
- [ ] All acceptance criteria pass.
- [ ] Required tests pass.
- [ ] No unauthorized changes introduced.
- [ ] Existing behavior remains intact.
- [ ] Security checks pass.
- [ ] Documentation updated.
- [ ] Evidence collected and verification completed.

### Completion Evidence
- Implementation summary
- Diffs of dispatch/support modules
- Golden output fixtures
- Parser grammar tests
- Coverage report
- Known limitations

---

## 10. Failure Handling and Recovery

### Expected Failure Modes
| Failure | Detection | Recovery |
|---------|-----------|----------|
| In-process dispatch needs a socket | Discovery | Stop; raise before building around it |
| Positionals need a dependency | Discovery | Stop; request approval or hand-roll a bounded parser |
| Output drifts from MCP | Contract test | Fix before claiming completion |
| Coverage below floor | `make coverage` | Add tests; do not exclude files |

### Rollback Strategy
Remove the read commands and support module; existing dispatch reverts. No data is affected.

### Partial Completion Policy
Do not claim completion if plumbing landed but reads did not, or vice versa. Record each separately.

---

## 11. Traceability

| Parent Requirement | Implementation Task | Verification | Acceptance Criterion |
|--------------------|---------------------|--------------|-----------------------|
| `gaps/full-cli.md` §5 | Task 1 | T100366-01…T100366-03, T100366-06, T100366-07 | AC-100366-02, AC-100366-03 |
| `gaps/full-cli.md` §7 step 1 / §9 (parser) | Task 1 | T100366-09 | AC-100366-05 |
| `requirement.md` §4.9.2 item 2 (binding syntax vs names) | Task 1 (Name note) | Inspection | AC-100366-04 |
| `requirement.md` §4.9.2 item 2 read bindings | Task 2 | T100366-04, T100366-05 | AC-100366-01 |
| FR-10 / FR-20 (catalog exposure) | Task 1 | T100366-08 | AC-100366-04 |
| FR-30 (exit codes) | Task 1 | T100366-06, T100366-07 | AC-100366-03 |
| Coverage gate | Both | T100366-10 | AC-100366-06 |

Required chain:

```text
Gap → CLI parser/output/exit contract → Read bindings → Command tests → Evidence
```

---

## 12. Phase Exit Contract

### Outputs Produced
- Shared CLI argument-parser, output, error, and exit-code contract.
- `clio help --json` catalog (with tool names).
- `recall`, `get`/`show`, `inspect`, `stats` commands.

### Guarantees Provided to Downstream Phases
After this phase is accepted:
- Every later CLI write command inherits the parser, output, error, and exit-code contract.
- CLI read results are semantically identical to MCP results, invoked in-process.
- Reserved top-level verbs are documented, so later phases do not collide.

### Known Limitations
- Arg parsing stays hand-rolled; complex nested flags may need follow-up.
- Human table formatting is minimal in this phase.
- The catalog names equal `bound_tools()` only after Phase 100380.

### Downstream Prerequisites
- Phases 100370/100372/100374/100376/100378 assume this contract and parser exist.

### Final Status
PASS | PASS WITH DOCUMENTED LIMITATIONS | BLOCKED | FAILED

### Verification Sign-Off
- Implementer: [TBD]
- Verifier: [TBD]
- Human Approver: not required
- Date: [TBD]

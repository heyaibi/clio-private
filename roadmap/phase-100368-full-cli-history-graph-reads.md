# Phase 100368: Full CLI History, Graph, and Workspace Read Surface

### Attribution
Rounds below record plan authorship; implementation sign-off is in §12.
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | OpenCode CLI (Go . Deepseek V4.1 Flash High) | done |
| Adversary | r1 | Antigravity CLI (Gemini 3.8 Flash) | done |
| Remediator | r1 | OpenCode CLI (Together . GLM-5.3 Flash High) | done |
| Remediator | r2 | OpenCode CLI (Go . Deepseek V4.1 Flash High) | done |
| Remedy Approver | r2 | Antigravity CLI (Gemini 3.8 Flash) | approved |
| Finalize | r1 | OpenCode CLI (Go . Deepseek V4.1 Flash High) | done |

**Follow-up phase 100368 · **Effort:** ~3 days · **Gaps:** `gaps/full-cli.md` §6, §7 step 1 (remaining read tools)

## 1. Objective

### Goal
Complete the read half of the CLI: bind the remaining read-only tools so `clio` can answer history, graph, belief, persona, task, temporal, and intent questions by hand, with no MCP client, reusing the output/exit contract from Phase 100366.

### Expected Outcome
- These commands run standalone and return the same structured results as their MCP counterparts: `triple query`, `belief history`, `persona get`, `task get`/`task history`, `failure list` (`failures_for_task`), `memtree query`/`memtree get`, `history temporal`, `graph query`, `intent gate`, `compose-context`, `associations`, `maintenance status`, `audit trail`. (The hygiene family — `hygiene audit|clean|log` — is owned entirely by Phase 100376 and is deliberately not bound here.)
- Each command documents its full flag set mirroring the MCP `inputSchema` 1:1 (no semantic divergence).
- Bounded output: list commands expose `--limit` and in-band `truncated` metadata; none silently truncate.

### Parent Requirement
`gaps/full-cli.md` §5 (UX contract), §6 (command tree), §7 step 1 (read rollout); `requirement.md` §4.9.2 item 2 and FR-10/FR-20 (catalog exposure with identical semantics).

### Design References
- Phase 100366 establishes the output/exit/flag contract and the read-group pattern; this phase follows it.
- The catalog and schemas: `bound_tools()` (`crates/clio-mcp/src/lib.rs:158`) and `clio_mcp::schema::schema_pack()`.
- In-process dispatch: the same callable surface Phase 100366 wires.
- Masking/redaction: `clio_config::secret` and `clio_ops::redact_credentials` (`crates/clio-ops/src/finding.rs:177`).

---

## 2. Scope Boundaries

### In Scope
- Read-only command bindings for history, graph, belief, persona, task/failure, MemTree, temporal, intent, compose-context, associations, maintenance status, and audit-trail tools.
- One module per command group, each mirroring its tool schema.
- Golden tests and exit-code/limit tests per group.

### Explicitly Out of Scope
- Writes and mutations (Phases 100370/100372/100374).
- `recall`/`get`/`inspect`/`stats` (Phase 100366).
- `status` (Phase 100362), config/ranking/sync (Phase 100378), hygiene clean (Phase 100376).
- New dependencies; GUI/TUI.

### Must Not Change
- MCP tool names, arguments, and semantics.
- Gating (intent gate, admission) and bank/actor semantics.
- DB precedence and the output/exit contract.
- Reserved top-level verbs (`version|health|help|mcp|ops|retention|compose|setup`); `compose_context` is bound as `compose-context` and `clio compose` stays the Docker lifecycle command.

### Scope Expansion Rule
If work outside this scope appears necessary: stop, document the reason, request clarification or approval, and do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- Phase 100366 accepted (output/error/flag contract and in-process dispatch seam).
- The read tools exist over MCP (Phases 100170/100180 and related).

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| Phase 100366 contract | Accepted | Phase exit contract |
| In-process dispatch | Callable read tools | `crates/clio-mcp/src/lib.rs` |
| Tool schemas | Available for flag mirroring | `schema_pack()` |
| Coverage guard | Enforcing per-file floor | `make coverage` |

---

## 4. Existing-System Discovery

The agent MUST re-verify the following; the facts below were confirmed at plan time.

### Required Discovery
- Enumerate the read-only tools not yet bound by Phase 100366 and map each to a command group.
- Confirm each tool's `inputSchema` so flags mirror it exactly.
- Confirm which reads paginate (need `--limit`/cursor + `truncated`).
- Confirm masking needs for audit/history views.
- Confirm the 450-line cap forces one module per group.

### Discovery Output
- **The remaining reads are the history/graph family**, per `gaps/full-cli.md` §2: `triple_query`, `belief_history`, `persona_get`, `task_get`, `task_history`, `failures_for_task`, `memtree_query`, `memtree_get`, `temporal_history`, `graph_query`, `intent_gate`, `compose_context`, `associations`, `maintenance_status`, `hygiene_log_list`, `audit_trail`.
- **Schema mirroring is required**, not optional: the gap's non-goal states names and semantics MUST NOT differ from §4.9.
- **Bounded output is normative** for `inspect`/retrieve; list reads follow the same rule.
- **Grouping is forced by the 450-line cap**: one file per group (for example triple/belief, task/failure/memtree/temporal, graph/associations, intent/compose-context).
- **Verb collision resolved.** `compose_context` is bound as `clio compose-context`; `clio compose` is the existing Docker lifecycle command (main.rs:66) and is reserved. The reserved verbs are `version|health|help|mcp|ops|retention|compose|setup`.

### Repository Adaptation Rule
The agent must determine concrete implementation locations from the actual repository. The plan does not prescribe file or module names.

---

## 5. Implementation Specification

### Task 1: History and Task Read Commands

#### Intent
Make task, failure, MemTree, and temporal history readable by hand.

#### Required Capability or Behavior
- `clio task get` / `clio task history`, `clio failure list`, `clio memtree query` / `clio memtree get`, `clio history temporal`, `clio belief history`, `clio triple query` run standalone.
- Arguments and defaults mirror the MCP `inputSchema` 1:1.
- List results honor `--limit` and expose `truncated`.

#### Architectural Responsibility
`clio-lib` renders; in-process dispatch and the underlying crates own semantics.

#### Required Changes
1. Add one module per group with thin wrappers over the dispatch.
2. Golden stdout/stderr tests; limit/truncation tests.

#### Implementation Constraints
- No re-implementation of history or gating logic.
- No new dependency.

#### Expected Result
History and task reads work with no MCP client.

### Task 2: Graph, Intent, Persona, and Workspace Reads

#### Intent
Complete the read-only surface.

#### Required Capability or Behavior
- `clio graph query`, `clio associations`, `clio intent gate`, `clio compose-context`, `clio persona get`, `clio maintenance status`, `clio audit trail` run standalone with mirrored flags.
- Masking applied to any view that could carry secrets.
- Bounded output everywhere.

#### Architectural Responsibility
`clio-lib` renders; semantics stay in the existing crates.

#### Required Changes
1. Add the group modules.
2. Tests: masking, limits, exit codes, golden output.

#### Expected Result
All read-only catalog tools are reachable from the CLI.

### Implementation Freedom
The agent may choose module names and grouping, provided semantics mirror MCP and the coverage/file-size constraints hold.

---

## 6. Agent Execution Rules

### Allowed Actions
- Add read-command modules, tests, and help.
- Reuse the Phase 100366 contract.

### Forbidden Actions
- Add writes/mutations; change MCP semantics or names.
- Add dependencies; bypass masking; silently truncate output.

### Agent Decision Boundary
The agent may decide grouping and flag spellings (keeping names/semantics identical to the schema). The agent must request approval for a semantic divergence.

### Mandatory Stop Conditions
Stop and report if a read tool cannot be reached in-process, if a schema cannot be mirrored without a new dependency, or if a view cannot be masked.

---

## 7. Security Constraints

### Required Controls
- Mask secrets in audit/history views via `clio_config::secret`.
- Read-only: no writes, no network side effects.
- Fail closed on invalid flags.

### Sensitive Data Rules
- Never print plaintext credentials, tokens, or secrets in history or audit output.

### Security Acceptance Conditions
- Planted secret is masked in `audit trail` output.
- No read command writes.

---

## 8. Test and Verification Strategy

### Required Tests
- [x] Unit tests (flag→schema mapping, limit handling)
- [x] Integration tests (each read group against in-memory SQLite)
- [x] Contract tests (piped JSON; TTY table; exit codes)
- [x] End-to-end tests (golden output per command)
- [x] Regression tests (Phase 100366 commands unchanged)
- [x] Failure-mode tests (unknown flag, missing arg, masking)

### Required Test Scenarios

| Test ID | Scenario | Expected Result |
|---------|----------|-----------------|
| T100368-01 | `clio task history --limit 2` | Two records; `truncated` when more |
| T100368-02 | `clio triple query S P` | Matching edges; identical to MCP |
| T100368-03 | `clio belief history <id>` | Confidence history; identical to MCP |
| T100368-04 | `clio graph query <seed>` | Neighbors; identical to MCP |
| T100368-05 | `clio intent gate "q"` | Gate decision; identical to MCP |
| T100368-06 | `clio audit trail` with planted secret | Secret masked |
| T100368-07 | Unknown flag | Exit 2; hint |
| T100368-08 | Regression + coverage | Workspace green; per-file ≥90% |

### Negative Testing
Verify reads never write, secrets never leak, and output is bounded.

### Verification Rule
Implementation claims must be supported by actual command output and `make coverage`.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence | Result |
|-------|----------------------|---------------------|-------------------|--------|
| AC-100368-01 | All remaining read tools have CLI access | T100368-01…T100368-05 | Command output | PASS — the real binary ran `task get`, `task history`, `failure list`, `memtree query`, `memtree get`, `history temporal`, `triple query`, `belief history`, `graph query`, `associations`, `persona get`, `maintenance status`, `intent gate`, `compose-context`, and `audit trail` against a SQLite file seeded over `clio mcp stdio`; `help --json` binds 20 commands. (Hygiene family deliberately not bound.) |
| AC-100368-02 | Flags/semantics mirror MCP 1:1 | T100368-02, T100368-03, T100368-04 | Output diff vs MCP | PASS — every command decodes into the same in-process MCP tool call (`McpHandler::handle_message` → `tools/call`) with the schema's exact argument names and defaults; `command_bindings()` maps each command to its tool and `help --json` is generated from `schema_pack()`. No MCP name/argument/semantic was changed. |
| AC-100368-03 | Bounded, non-silent truncation | T100368-01 | Output with `truncated` | PASS — `task history` and `failure list` emit in-band `truncated` when the returned page fills the resolved limit (`--limit 1` of 2 → `true`; default → `false`); `memtree query` sets `truncated` when an explicit `--limit` is filled. |
| AC-100368-04 | Masking on audit/history views | T100368-06 | Output diff | PASS — the CLI applies `clio_config::secret::mask_value` over the `audit trail` payload; a synthetic secret-keyed field is masked (`sk-live-supersecret` → `****cret`), and real audit output never contains the planted secret. |
| AC-100368-05 | No regression; coverage green | T100368-08 | `make check`, `make coverage` | PASS — `make check` EXIT=0 (workspace fmt + clippy `-D warnings` + tests); final `make coverage` EXIT=0 with every reported file ≥90% lines and functions (see Completion Evidence). |

### Definition of Done
- [x] All in-scope behavior implemented. (task/failure/MemTree/temporal, triple/belief, graph/associations/persona/maintenance, intent/compose-context/audit)
- [x] All acceptance criteria pass. (AC-100368-01…05)
- [x] Required tests pass. (`make check` EXIT=0; 291 clio-lib unit tests; per-group in-process integration tests)
- [x] No unauthorized changes introduced. (new `cli_read_*` group modules in `clio-lib` only; MCP names/arguments/semantics untouched)
- [x] Existing behavior remains intact. (Phase 100366 `recall`/`get`/`show`/`inspect`/`stats` and their tests unchanged and green; ops/retention/compose untouched)
- [x] Security checks pass. (audit-trail payload masked; unknown flags/commands fail closed; no writes or network from any read command)
- [x] Documentation updated. (`print_help` lists every new command; `help --json` catalog now binds 20 commands; per-command `--help` usage lines)
- [x] Evidence collected and verification completed. (see Completion Evidence)
- [x] Required approval is obtained (downstream pipeline step).

### Completion Evidence
- Implementation summary: the `clio-lib` read surface gained a `ReadGroup` contract (`cli_read_group`) and a group-based engine (`cli_read`) that resolves two-token groups (`task get`, `history temporal`, …), parses per-command flags, and routes every call through the same in-process MCP `tools/call` bridge as Phase 100366. New group modules: `cli_read_core` (recall/get/show/inspect/stats moved behind the contract), `cli_read_history` (task get/history, failure list, memtree query/get, history temporal), `cli_read_belief` (triple query, belief history), `cli_read_graph` (graph query, associations, persona get, maintenance status), and `cli_read_workspace` (intent gate, compose-context, audit trail). `cli_help` gained the full command→tool binding table, group subcommand resolution, group help, and per-command usage.
- Group-module diffs: `crates/clio-lib/src/{cli_read,cli_read_group,cli_read_core,cli_read_history,cli_read_belief,cli_read_graph,cli_read_workspace,cli_help}.rs`, their `*_tests.rs` suites, and `main.rs`/`main_read_tests.rs` dispatch wiring. Every file ≤450 lines.
- Golden output fixtures (real binary; `--db /tmp/clio-e2e.db --bank bank-a` seeded over `clio mcp stdio`):
  - `clio triple query rust used_by` → `{"ok":true,"triples":[{...,"object":"agent","predicate":"used_by","subject":"rust",...}]}` exit 0; text → `triples: 1` + `rust used_by agent`.
  - `clio history temporal triple:rust:used_by` → `{"target_kind":"triple","entries":[...],"subject":"rust","predicate":"used_by",...}` exit 0; text → `target_kind: triple` / `entries: 1`.
  - `clio graph query itm-1` → `{"nodes":[],"ok":true}`; `clio associations itm-1` → `{"associations":[],"ok":true}`.
  - `clio maintenance status` → `{"leaf_queryable":true,"dirty_ancestors":[],"refreshing":[],"index":{...},"ok":true}`.
  - `clio memtree query` → `{"nodes":[],"ok":true,"truncated":false}`.
  - `clio audit trail itm-1` → masked lifecycle `{item_id, lineage_ids, revisions, events, belief_confidence, timeline, ok:true}` exit 0; text → `item_id: itm-1` / `lineage_ids: 1` / `revisions: 1` / `events: 1` / `timeline: 2`.
  - `clio intent gate "hello there" --db sqlite::memory:` → `{"retrieval_needed":true,"domains":["semantic","episodic"],"confidence":0.5,"reason":"default-retrieve","ok":true}` exit 0.
  - `clio task get ghost --db sqlite::memory: --bank bank-a` → `{"ancestor_gist":null,"ok":true,"record":null}` exit 0.
  - `clio task` → `{"code":"usage","hint":"try `clio task get`","message":"`task` requires a subcommand"}` exit 2; `clio task gett` → `{"hint":"did you mean `clio task get`?"}` exit 2.
  - `clio graph query itm-1 --max-hops 9` → `{"code":"out_of_range","message":"graph_query max_hops must be <= 3"}` exit 1; `clio task history t1 --limt 2` → usage exit 2; `clio compose-context` (no budget) → usage exit 2.
  - `clio help --json` → 20 `commands`, each `{command, tool}` (recall→retrieve … audit trail→audit_trail), tool list equal to `schema_pack()`.
- Bounded-output tests: `cli_read_history_tests::task_history_limit_and_truncation` (`--limit 2` of 3 → `truncated:true`; default → `false`), `failure_list_exact_truncation_and_none`, `memtree_query_get_and_truncation`.
- Masking tests: `cli_read_workspace_tests::audit_trail_masks_planted_secret` (planted `api_key` never appears in real output; the CLI mask pass turns a synthetic `sk-live-supersecret` into `****cret`).
- Coverage report: final workspace `make coverage` EXIT=0 — `coverage-guard: 292 file(s) checked against 90.0% floors`, `TOTAL lines 97.96% functions 98.95%`, all reported files meet the per-file floor. New/changed `clio-lib` files: `cli_read.rs` 96.39% lines / 97.37% functions; `cli_read_core.rs` 100/100; `cli_read_history.rs` 98.23/100; `cli_read_belief.rs` 98.86/100; `cli_read_graph.rs` 100/100; `cli_read_workspace.rs` 100/100; `cli_read_group.rs` 100/100; `cli_help.rs` 99.25/100; `main.rs` 93.69/100. The `cli_read_support_tests.rs` fixture file is path-excluded by llvm-cov (matches `*_tests.rs`).
- Known limitations: see below.
- Verification note: reads that decrypt item content (`task get`/`task history`, `failure list`, `belief history`, `persona get`, `compose-context`) return the store's `forbidden`/`no DEK for subject` error when the data was written by a *different* process, because `LocalDevKms` is process-local (pre-existing behavior recorded in Phase 100366). Their success paths are proven by the in-process integration tests; metadata-only reads (triple/temporal/graph/associations/maintenance/MemTree/audit) run cross-process end to end.

---

## 10. Failure Handling and Recovery

### Expected Failure Modes
| Failure | Detection | Recovery |
|---------|-----------|----------|
| A read tool is unreachable in-process | Discovery | Stop; raise |
| Schema cannot be mirrored | Discovery | Stop; request approval |
| Output drifts from MCP | Contract test | Fix before claiming completion |
| Coverage below floor | `make coverage` | Add tests |

### Rollback Strategy
Remove the read modules; Phase 100366 commands remain. No data affected.

### Partial Completion Policy
Do not claim completion if only some read groups landed. Record completed and incomplete groups separately.

---

## 11. Traceability

| Parent Requirement | Implementation Task | Verification | Acceptance Criterion |
|--------------------|---------------------|--------------|-----------------------|
| `gaps/full-cli.md` §6, §7 step 1 | Tasks 1–2 | T100368-01…T100368-07 | AC-100368-01…AC-100368-03 |
| `requirement.md` §4.9.2 item 2 | Tasks 1–2 | T100368-02…T100368-04 | AC-100368-02 |
| FR-10 / FR-20 (catalog exposure) | Tasks 1–2 | T100368-01 | AC-100368-01 |
| NFR-6 (masking) | Task 2 | T100368-06 | AC-100368-04 |
| Coverage gate | Both | T100368-08 | AC-100368-05 |

Required chain:

```text
Gap → Read bindings → Group modules → Command tests → Evidence
```

---

## 12. Phase Exit Contract

### Outputs Produced
- CLI read bindings for history, graph, belief, persona, task, temporal, intent, and workspace reads.

### Guarantees Provided to Downstream Phases
After this phase is accepted:
- The entire read-only catalog is reachable from the CLI.
- All remaining CLI work (writes, destructive, config, sync) starts from a stable read contract.

### Known Limitations
- Long list results depend on tool-side pagination; cursor-style reads may be added later.
- Human table formatting remains minimal.
- `memtree query` emits in-band `truncated` only when `--limit` is explicit; the tool's internal default cap is owned by `clio-write` and is not surfaced.
- Reads that decrypt item content (task get/history, failure list, belief history, persona get, compose-context) cannot read data written by a different process because `LocalDevKms` is process-local; this is pre-existing store behavior, not a CLI defect (see Completion Evidence).
- `triple query` also accepts positional `SUBJECT PREDICATE OBJECT` as sugar over the schema's named `subject`/`predicate`/`object` arguments; explicit flags override positionals.
- The final `make coverage` run hit a pre-existing flaky `clio-write` concurrency test (`memtree_cov_tests::concurrent_writes_during_refresh_wave`, "refresh did not converge") once under instrumentation; it passes in isolation and the gate passed on re-run. This phase did not touch `clio-write`.

### Downstream Prerequisites
- Phases 100370/100372/100374/100376/100378 assume the read groups and contract exist.

### Final Status
PASS

### Verification Sign-Off
- Implementer: Developer r1 (OpenCode CLI)
- Verifier: [TBD]
- Human Approver: not required
- Date: 2026-09-23

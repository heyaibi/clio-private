# Phase 100368: Full CLI History, Graph, and Workspace Read Surface

### Attribution
Rounds below record plan authorship; implementation sign-off is in §12.
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | [TBD] | [TBD] |
| Adversary | r1 | [TBD] | [TBD] |
| Remediator | r1 | [TBD] | [TBD] |
| Remedy Approver | r1 | [TBD] | [TBD] |
| Finalize | r1 | [TBD] | [TBD] |

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
- [ ] Unit tests (flag→schema mapping, limit handling)
- [ ] Integration tests (each read group against in-memory SQLite)
- [ ] Contract tests (piped JSON; TTY table; exit codes)
- [ ] End-to-end tests (golden output per command)
- [ ] Regression tests (Phase 100366 commands unchanged)
- [ ] Failure-mode tests (unknown flag, missing arg, masking)

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

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-100368-01 | All remaining read tools have CLI access | T100368-01…T100368-05 | Command output |
| AC-100368-02 | Flags/semantics mirror MCP 1:1 | T100368-02, T100368-03, T100368-04 | Output diff vs MCP |
| AC-100368-03 | Bounded, non-silent truncation | T100368-01 | Output with `truncated` |
| AC-100368-04 | Masking on audit/history views | T100368-06 | Output diff |
| AC-100368-05 | No regression; coverage green | T100368-08 | `make check`, `make coverage` |

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
- Group-module diffs
- Golden output fixtures
- Coverage report
- Known limitations

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

### Downstream Prerequisites
- Phases 100370/100372/100374/100376/100378 assume the read groups and contract exist.

### Final Status
PASS | PASS WITH DOCUMENTED LIMITATIONS | BLOCKED | FAILED

### Verification Sign-Off
- Implementer: [TBD]
- Verifier: [TBD]
- Human Approver: not required
- Date: [TBD]

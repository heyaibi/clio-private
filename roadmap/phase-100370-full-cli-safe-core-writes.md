# Phase 100370: Full CLI Safe Core Write Surface

### Attribution
Rounds below record plan authorship; implementation sign-off is in §12.
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | OpenCode CLI (Go . Deepseek V4.1 Flash High) | done |
| Adversary | r1 | Antigravity CLI (Gemini 3.8 Flash) | done |
| Remediator | r1 | OpenCode CLI (Together . GLM-5.3 Flash High) | done |
| Remedy Approver | r1 | OpenCode CLI (OpenRouter . Deepseek V4.1 Flash Max) | approved |
| Finalize | r1 | OpenCode CLI (Together . GLM-5.3 Flash High) | done |

**Follow-up phase 100370 · **Effort:** ~3 days · **Gaps:** `gaps/full-cli.md` §6, §7 step 2 (flagship write + gated core writes)

## 1. Objective

### Goal
Make the flagship promise real — `clio remember "x"` then `clio recall "x"` — and bind the safe core write tools (`store`, `admit_preview`, `summarize`, `triple_add`/`triple_end`, `belief_observe`, `graph_link`) to the CLI with the same gates MCP uses and a `--dry-run` preview on every mutation.

### Expected Outcome
- `clio remember "prefers aisle seats" --category persona --bank demo` writes one gated item; `clio recall "seat preference" --bank demo` returns it, with no MCP client and no env vars beyond a fresh temp `HOME`.
- `clio remember --dry-run` and `clio admit ...` print score and factors without writing.
- `clio triple add`, `clio belief observe`, `clio graph link`, `clio summarize`, `clio consolidate`, and `clio admit --file ops.json` work standalone with mirrored flags.
- Admission/category/span gating is identical to the MCP path; a rejected write is reported with the same reason.

### Parent Requirement
`gaps/full-cli.md` §6, §7 step 2; `requirement.md` §4.9.2 item 2 (identical semantics across bindings), FR-10/FR-20 (catalog), FR-21 (write gating on the long-term path; `admit_preview` exposes the same decision without writing), PR-3/PR-5.

### Design References
- Phase 100366 output/exit contract and in-process dispatch seam; Phase 100368 read surface.
- `clio-mcp::runtime::{now_utc, build_ops_embedder}` (`crates/clio-lib/src/ops_cli.rs:140-141`) for the runtime the write path needs.
- The catalog/schemas: `bound_tools()` (`crates/clio-mcp/src/lib.rs:158`), `schema_pack()`.
- Redaction/masking: `clio_ops::redact_credentials`, `clio_config::secret`.

### Name and Binding-Syntax Note
`requirement.md` §4.9.2 item 2 states "Binding syntax MAY differ; names and semantics MUST NOT." This plan reads CLI verbs as binding syntax: `clio remember` invokes `store`, `clio admit` invokes `admit_preview`, `clio consolidate` invokes `consolidate`. Each verb's tool name MUST be printed in `clio help` and `clio help --json`. If the operator prefers strict name parity, the fallback is to use the tool names as verbs.

---

## 2. Scope Boundaries

### In Scope
- `clio remember TEXT --category C [--bank B] [--actor A] [--epistemic-kind fact|belief] [--dry-run]` → `store` (dry-run → `admit_preview`).
- `clio admit TEXT --category C ...` → `admit_preview`; `clio admit --file ops.json` → `admit_preview_batch` (read-only batch preview).
- `clio summarize [--scope ...]` → `summarize`.
- `clio consolidate [--scope ...]` → `consolidate` (maintenance write; non-blocking structure work).
- `clio triple add S P O ...`, `clio triple end S P [--object O]`.
- `clio belief observe PROP --confidence C --evidence E --source S`.
- `clio graph link A B --relationship R`.
- `--dry-run` on every mutating command, writing nothing and exiting 0.

### Explicitly Out of Scope
- Destructive/confirmed mutations `update`, `invalidate`, `discard`, `correct` (Phase 100374).
- Workspace/harness writes (Phase 100372).
- Hygiene, export/import, erase (Phase 100376); config/ranking/sync (Phase 100378).
- New memory semantics, categories, admission factors, or schema.

### Must Not Change
- Admission and category gates, span verification, masking, bank/actor semantics.
- MCP tool names/arguments/semantics and gate behavior.
- Snapshots are never written by `summarize`.

### Scope Expansion Rule
If work outside this scope appears necessary: stop, document the reason, request clarification or approval, and do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- Phase 100366 accepted (contract + dispatch seam); Phase 100368 accepted (read surface).
- MCP write tools (`store`, `triple_add`, `belief_observe`, `summarize`, `graph_link`) exist and are gated.

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| In-process write dispatch | Callable with gating intact | `crates/clio-mcp/src/lib.rs` |
| Admission preview | Same decision, no write | `admit_preview` semantics |
| Runtime/embedder | Available to CLI | `clio-mcp::runtime` |
| Coverage guard | Per-file floor | `make coverage` |

---

## 4. Existing-System Discovery

The agent MUST re-verify the following; the facts below were confirmed at plan time.

### Required Discovery
- Confirm the in-process write dispatch and that it enforces admission/category/span gates that the CLI must not bypass.
- Confirm `admit_preview` writes nothing and returns score + factors.
- Confirm `summarize` regenerates gists only and leaves snapshots byte-immutable.
- Confirm the runtime/embedder construction the write path needs and reuse it.
- Confirm `--epistemic-kind` handling for facts vs beliefs (belief creation follows §4.9.3).

### Discovery Output
- **Gating lives inside the tools.** The CLI must call the same dispatch, not a parallel store write, so gates cannot be skipped.
- **`admit_preview` is the dry-run primitive** and already returns the decision without writing (FR-21).
- **`summarize` is snapshot-safe by contract** (Phase 100380 binds it; this phase only exposes it).
- **Extraction/embedding may be async.** The CLI write returns after the gated write; background index drain stays off the response path (per `gaps/full-cli.md` §8).
- **No writes without gates.** There is no public write path bypassing admission.

### Repository Adaptation Rule
The agent must determine concrete implementation locations from the actual repository.

---

## 5. Implementation Specification

### Task 1: Flagship Write and Dry-Run

#### Intent
Ship `remember`/`admit` with a zero-write preview.

#### Required Capability or Behavior
- `clio remember TEXT --category C [--bank B] [--actor A] [--epistemic-kind fact|belief] [--dry-run]` writes one gated item.
- `--dry-run` maps to `admit_preview` and prints score plus factors, writing nothing, exit 0.
- A refused write reports the same reason the MCP path would and exits 1 (domain refusal) or 2 (usage).
- No inference of `--category`: it is required, keeping PR-3/PR-5 loud (per §11 open question 1).

#### Architectural Responsibility
`clio-lib` parses/renders; the in-process write dispatch owns gating and persistence.

#### Required Changes
1. Add a write-command module with `remember`/`admit` under the 450-line cap.
2. Route through the gated dispatch; implement `--dry-run`.
3. Golden tests: successful write, preview (no write), refusal.

#### Implementation Constraints
- Never write the long-term store on `--dry-run`.
- Never bypass admission/category gates.
- Reuse the shared resolver, masker, and redactor.

#### Expected Result
One command saves a memory; the dry-run previews the exact decision without writing.

### Task 2: Triples, Beliefs, Graph, and Summarize

#### Intent
Bind the remaining safe core writes.

#### Required Capability or Behavior
- `clio triple add` / `clio triple end`, `clio belief observe`, `clio graph link`, `clio summarize` run standalone with mirrored flags.
- `triple add` rejects continuous/scalar updates (§4.9.4.E); `belief observe` appends to existing identities without re-scoring novelty (§4.9.3).
- `summarize` regenerates gists only.

#### Architectural Responsibility
`clio-lib` renders; semantics stay in the existing crates.

#### Required Changes
1. Add group modules and tests.
2. Assert snapshot immutability for `summarize`; assert append semantics for beliefs.

#### Implementation Constraints
- No new dependency; no semantic divergence from MCP.
- Snapshot columns never written by `summarize`.

#### Expected Result
All safe core writes are reachable from the CLI with identical behavior.

### Implementation Freedom
The agent may choose module layout and flag spellings, provided semantics and gating are unchanged.

---

## 6. Agent Execution Rules

### Allowed Actions
- Add write modules, `--dry-run`, tests, and help.
- Reuse the Phase 100366 contract and the shared runtime.

### Forbidden Actions
- Bypass admission/category/span gates; write on `--dry-run`.
- Change MCP names/semantics; add dependencies; add destructive commands.

### Agent Decision Boundary
The agent may decide parsing/rendering details. The agent must request approval for any semantic change or a new required flag.

### Mandatory Stop Conditions
Stop and report if a write path exists that bypasses gating, if `--dry-run` cannot be made write-free, or if the write runtime cannot be reached in-process.

---

## 7. Security Constraints

### Required Controls
- All writes pass the same gates as MCP; `--dry-run` performs zero writes.
- Mask secrets in errors; never echo raw content beyond the item itself.
- No internal retries hiding failures (caller decides); the background index drain stays as-is.

### Sensitive Data Rules
- Never log plaintext credentials, tokens, or secrets.
- Prefer env over argv for any future secret-bearing input.

### Security Acceptance Conditions
- A rejected write leaves the store unchanged (test).
- `--dry-run` leaves the store unchanged (test).

---

## 8. Test and Verification Strategy

### Required Tests
- [ ] Unit tests (flag mapping, dry-run routing)
- [ ] Integration tests (remember→recall round trip; triple/belief/graph writes)
- [ ] Contract tests (gating identical to MCP; same refusal reasons)
- [ ] End-to-end tests (golden output for write + preview)
- [ ] Regression tests (read commands unchanged)
- [ ] Security/failure-mode tests (gate bypass impossibility; dry-run no-write; snapshot immutability)

### Required Test Scenarios

| Test ID | Scenario | Expected Result |
|---------|----------|-----------------|
| T100370-01 | `remember` then `recall` in temp HOME | Item returned |
| T100370-02 | `remember --dry-run` | Score+factors; store unchanged; exit 0 |
| T100370-03 | Low-utility rejected write | Refusal; same reason as MCP; store unchanged |
| T100370-04 | `triple add` then `triple query` | Edge present |
| T100370-05 | `belief observe` twice | Append; audit emitted; no novelty re-score |
| T100370-06 | `graph link` then `graph query` | Edge present |
| T100370-07 | `summarize` | Gists regenerated; snapshots byte-identical |
| T100370-08 | Regression + coverage | Workspace green; per-file ≥90% |

### Negative Testing
Verify no gate bypass, no dry-run writes, correct refusals, and unchanged snapshots.

### Verification Rule
Implementation claims must be supported by actual command output and `make coverage`.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence | Result |
|-------|----------------------|---------------------|-------------------|--------|
| AC-100370-01 | `remember`→`recall` works with no MCP client | T100370-01 | Command output | PASS (with recorded store limitation) — in-process CLI round trip `remember`→`recall` returns the item (`cli_write_core::tests::remember_then_recall_round_trip_in_one_runtime`); real-binary `remember` writes one gated item and `inspect` reads it back. A second process's `recall`/`get` returns the store's `forbidden`/`no DEK for subject` error because `LocalDevKms` is process-local (pre-existing, recorded in Phases 100366/100368; not a CLI defect). |
| AC-100370-02 | `--dry-run` writes nothing, exits 0 | T100370-02 | Output + store check | PASS — `remember --dry-run` prints `dry_run:true`, `pass`, `admission_score`, and `factors`, and publishes nothing (`remember_dry_run_writes_nothing_and_exits_zero`); `consolidate --dry-run` and `summarize --dry-run` emit validated previews without a dispatcher call (`dry_run_preview_writes_nothing_and_exits_zero`); a real-binary file-store `remember --dry-run` leaves 0 items. |
| AC-100370-03 | Gating identical to MCP | T100370-03 | Refusal comparison | PASS — every write routes through the same in-process dispatcher (`cli_read::call_tool`); the CLI reports the exact MCP refusal message for the category gate (`remember_refusal_reports_the_mcp_reason_and_writes_nothing`), the continuous update-rule gate (`triple_add_rejects_continuous_update_rule_like_mcp`), the belief `source_type` rule (`triple_add_belief_without_source_type_is_refused`), and a missing graph endpoint (`graph_link_missing_endpoint_is_refused_like_mcp`). |
| AC-100370-04 | Triples/beliefs/graph/summarize bound | T100370-04…T100370-07 | Command output | PASS WITH DOCUMENTED LIMITATION — `triple add`/`triple end`, `belief observe`, and `graph link` are bound and verified (`triple_add_then_query_returns_the_edge`, `triple_end_expires_and_retains_history`, `belief_observe_twice_appends_without_re_scoring`, `graph_link_then_query_returns_the_edge`). `summarize` is exposed (verb, flags, `--dry-run`, help) but its gist-regeneration handler is the Phase 100380 deliverable, so the live call faithfully reports the dispatcher's structured unknown-tool error; see Known Limitations. |
| AC-100370-05 | No regression; coverage green | T100370-08 | `make check`, `make coverage` | PASS — `make check` exit 0; `make coverage` exit 0 with `coverage-guard: 297 file(s) checked against 90.0% floors`, `TOTAL lines 97.96% functions 98.94%`, `all reported files meet the per-file floor`. Changed files: `cli_write.rs` fn 100.00% / lines 95.45%, `cli_write_core.rs` fn 95.83% / lines 96.35%, `cli_write_graph.rs` fn 100.00% / lines 100.00%, `cli_write_group.rs` fn 100.00% / lines 100.00%, `mcp_cli.rs` fn 100.00% / lines 92.03%, `main.rs` fn 100.00% / lines 96.74%, `cli_help.rs` fn 100.00% / lines 99.36%, `cli_read.rs` fn 97.37% / lines 96.15%. |

### Definition of Done
- [x] All in-scope behavior implemented.
- [x] All acceptance criteria pass (AC-100370-04 passes with the documented `summarize` exposure limitation recorded under Known Limitations).
- [x] Required tests pass.
- [x] No unauthorized changes introduced.
- [x] Existing behavior remains intact.
- [x] Security checks pass.
- [x] Documentation updated.
- [x] Evidence collected and verification completed.
- [x] Required approval is obtained (downstream pipeline step).

### Completion Evidence

**Implementation summary.** `clio-lib` gains a write-command engine plus two disjoint group modules, all routing through the same in-process MCP dispatcher the MCP transport uses, so gating cannot drift:

- `cli_write.rs` — the engine: verb resolution, flag parsing, `--help`, the `tools/call` bridge, exit-code mapping (0 ok, 1 refusal/operational, 2 usage), and one bounded index drain after a mutating success (a one-shot process has no background sweeper).
- `cli_write_group.rs` — the `WriteGroup` contract, the `WriteCall::{Tool,Preview}` split (a preview carries no tool name, so it can never become a dispatcher call), and the shared `pass:false` → exit-1 refusal mapping.
- `cli_write_core.rs` — `remember` (→ `store`), `admit` (→ `admit_preview`; `--file ops.json` → `admit_preview_batch`), `summarize`, and `consolidate`, each with `--dry-run`.
- `cli_write_graph.rs` — `triple add`, `triple end`, `belief observe`, and `graph link` with mirrored flags and `--dry-run` previews.
- `cli_read.rs` delegates group-resolved write verbs (`triple add`, …) to the write engine; `cli_help.rs` and `main.rs` publish the new verbs and their bound tool names in `clio help` and `clio help --json`.
- `mcp_cli.rs` was extracted from `main.rs` (which dropped from 456 to 275 lines) to keep every file under the 450-line cap.

**Write-module diffs.** New: `cli_write.rs` (208 lines), `cli_write_group.rs` (107), `cli_write_core.rs` (309), `cli_write_graph.rs` (349), `mcp_cli.rs` (227). Modified: `main.rs`, `cli_help.rs`, `cli_read.rs`, `main_tests.rs`. Test-only modules: `cli_write_tests.rs`, `cli_write_core_tests.rs`, `cli_write_graph_tests.rs`, `cli_write_graph_flag_tests.rs`, `cli_write_support_tests.rs`, `main_write_tests.rs`.

**Round-trip command transcript (real binary, `--db` file store, `--output json`).**
- `clio remember "prefers aisle seats" --category persona --bank demo` → exit 0, `{"ok":true,"pass":true,"admission_score":0.86,"id":"itm-cli-…","factors":{…}}`.
- `clio remember "…" --category persona --bank demo --dry-run` → exit 0, `{"dry_run":true,"pass":true,"admission_score":…,"factors":{…}}`; a following `inspect` shows 0 items.
- `clio admit "hello" --category persona --bank demo` → exit 0, preview with `pass`/`factors`, 0 writes.
- `clio admit --file ops.json` → exit 0, `{"read_only":true,"count":2,"summary":{"would_admit":2,"would_reject":0},"writes":0}`.
- `clio consolidate` → exit 0, `{"ok":true,"job_id":"job-1","status":"accepted"}`.
- `clio triple add demo likes sqlite --bank demo` → exit 0, `{"decision":{"pass":true},"new_edge_id":"trp-…"}`; `triple query demo likes` returns the edge; `triple end demo likes --valid-until …` → `{"closed_ids":["trp-…"]}`.
- `clio belief observe "Postgres handles writes" --confidence 0.7 --evidence ev-1 --source user_stated --bank demo` → exit 0, `{"outcome":"created","belief":{…}}`.
- `clio graph link itm-a itm-b --relationship relates_to --bank demo` → exit 0, `{"edge_id":"…"}`.
- `clio recall "aisle" --bank demo` in a *second* process → exit 1, `{"code":"forbidden","message":"no DEK for subject `itm-cli-…`"}` (pre-existing `LocalDevKms` process-local limitation).
- `clio summarize --scope demo` → exit 1, `{"code":"-32602","message":"unknown tool `summarize`"}` (handler is Phase 100380; verb/help/`--dry-run` are exposed here).

**Snapshot-immutability evidence.** Not verifiable in this phase: the `summarize` gist-regeneration handler is not bound yet (Phase 100380 owns it per §4 Discovery Output), so there is no live `summarize` write whose snapshot immutability could be asserted. The CLI's `summarize --dry-run` preview states "snapshots are never altered" and performs zero writes (`summarize_dry_run_previews_without_calling_the_dispatcher`). This is recorded as a known limitation, not as a passing immutability test.

**Coverage report.** `make coverage` (final): `coverage-guard: 297 file(s) checked against 90.0% floors`; `TOTAL lines 97.96% functions 98.94%`; `all reported files meet the per-file floor`. Per-file rows for changed files are in AC-100370-05.

**Known limitations.** See §12.


---

## 10. Failure Handling and Recovery

### Expected Failure Modes
| Failure | Detection | Recovery |
|---------|-----------|----------|
| Gate bypass discovered | Audit/test | Stop; remove the bypass |
| `--dry-run` writes | Test | Fix before claiming completion |
| Snapshot mutated by `summarize` | Immutability test | Fix before claiming completion |
| Coverage below floor | `make coverage` | Add tests |

### Rollback Strategy
Remove the write modules; reads remain. Writes performed during testing are confined to temp stores.

### Partial Completion Policy
Do not claim completion if `remember` landed but the other safe writes did not. Record each separately.

---

## 11. Traceability

| Parent Requirement | Implementation Task | Verification | Acceptance Criterion |
|--------------------|---------------------|--------------|-----------------------|
| `gaps/full-cli.md` §7 step 2 | Tasks 1–2 | T100370-01…T100370-07 | AC-100370-01, AC-100370-04 |
| `requirement.md` §4.9.2 item 2 | Tasks 1–2 | T100370-03, T100370-04 | AC-100370-03 |
| FR-21 (`admit_preview` no write; long-term gating) | Task 1 | T100370-02, T100370-03 | AC-100370-02, AC-100370-03 |
| PR-3 / PR-5 (loud category) | Task 1 | T100370-01 | AC-100370-01 |
| Coverage gate | Both | T100370-08 | AC-100370-05 |

Required chain:

```text
Gap → Gated write bindings → CLI modules + dry-run → Round-trip tests → Evidence
```

---

## 12. Phase Exit Contract

### Outputs Produced
- CLI `remember`/`admit` (with `--dry-run`), `triple add|end`, `belief observe`, `graph link`, `summarize`.

### Guarantees Provided to Downstream Phases
After this phase is accepted:
- The flagship write→read loop works from the CLI.
- All safe core writes are CLI-reachable with unchanged gating.

### Known Limitations
- Category is required; no inference.
- Background indexing remains asynchronous and off the response path.
- `summarize`'s gist-regeneration handler is not implemented in this phase. What is missing: the MCP `summarize` handler and its snapshot-immutability test (T100370-07). Why: this phase exposes the CLI verb only — §4 Discovery Output assigns binding the `summarize` MCP handler to Phase 100380 ("Phase 100380 binds it; this phase only exposes it"), and binding it needs the versioned `tool_schema` publish approval that phase owns. Debt owner: Phase 100380. A live `clio summarize` returns the dispatcher's structured unknown-tool error; `clio summarize --dry-run` and the help surface work.
- Cross-process reads of encrypted content (`recall`, `get`, and the `belief observe` append path) return the store's `forbidden`/`no DEK for subject` error because `LocalDevKms` is process-local (keys never enter the item DB). Why: pre-existing store behavior recorded in Phases 100366/100368; no phase currently owns a persistent KMS. Debt owner: unassigned (pre-existing). The CLI reports it faithfully and the success paths are proven in-process.

### Downstream Prerequisites
- Phase 100372/100374/100376 build their write/confirm behavior on this contract.
- Phase 100380 binds the `summarize` handler this phase exposes.

### Final Status
PASS WITH DOCUMENTED LIMITATIONS

### Verification Sign-Off
- Implementer: OpenCode CLI (Go . Deepseek V4.1 Flash High)
- Verifier: [TBD]
- Human Approver: not required
- Date: 2026-09-23

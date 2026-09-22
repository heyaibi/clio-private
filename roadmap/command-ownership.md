# CLI Command Ownership Matrix

Purpose: bind every published tool to exactly one owning phase, so no command is built twice or left unbuilt. This is the check that caught the duplicate `persona get` / `hygiene log` assignments and the unassigned `consolidate` / `admit_preview_batch` tools.

## Rules

- One tool → one owning phase. The phase named here is the only phase that binds the CLI command.
- CLI verbs are **binding syntax** (`requirement.md` §4.9.2 item 2): `clio recall` invokes `retrieve`, `clio remember` invokes `store`. Each verb's tool name is printed in `clio help` and `clio help --json`.
- Reserved top-level verbs (never reused by new commands): `version`, `health`, `help`, `mcp`, `ops`, `retention`, `compose`, `setup`. `compose_context` is therefore `clio compose-context`, not `clio compose`.
- Tools already served by an existing phase stay with it; the follow-up phases add only the missing surface.

## Ownership by phase

| Owning phase | Tool | CLI command |
|--------------|------|-------------|
| 100230 (existing) | `diagnose` | `clio ops diagnose` |
| 100230 (existing) | `verify` | `clio ops verify` |
| 100230 (existing) | `doctor` | `clio ops doctor` |
| 100230 (existing) | `repair` | `clio ops repair` |
| 100230 (existing) | `reindex` | `clio ops reindex` |
| 100250 (existing) | `retention_profile_get` | `clio retention get` |
| 100250 (existing) | `retention_profile_set` | `clio retention set` |
| 100362 | — (composite, no tool) | `clio status` |
| 100364 | — (transport) | `clio mcp http` |
| 100366 | `retrieve` | `clio recall` |
| 100366 | `get` | `clio get` / `clio show` |
| 100366 | `get_snapshot` | `clio get --snapshot` |
| 100366 | `get_gist` | `clio get --gist` |
| 100366 | `inspect` | `clio inspect` |
| 100366 | `stats` | `clio stats` |
| 100368 | `intent_gate` | `clio intent gate` |
| 100368 | `compose_context` | `clio compose-context` |
| 100368 | `associations` | `clio associations` |
| 100368 | `maintenance_status` | `clio maintenance status` |
| 100368 | `persona_get` | `clio persona get` |
| 100368 | `task_get` | `clio task get` |
| 100368 | `task_history` | `clio task history` |
| 100368 | `failures_for_task` | `clio failure list` |
| 100368 | `memtree_query` | `clio memtree query` |
| 100368 | `memtree_get` | `clio memtree get` |
| 100368 | `temporal_history` | `clio history temporal` |
| 100368 | `triple_query` | `clio triple query` |
| 100368 | `belief_history` | `clio belief history` |
| 100368 | `graph_query` | `clio graph query` |
| 100368 | `audit_trail` | `clio audit trail` |
| 100368 | `canonical_get` | `clio canonical get` |
| 100368 | `shared_retrieve` | `clio shared retrieve` |
| 100370 | `store` | `clio remember` |
| 100370 | `admit_preview` | `clio admit` |
| 100370 | `admit_preview_batch` | `clio admit --file` |
| 100370 | `summarize` | `clio summarize` |
| 100370 | `consolidate` | `clio consolidate` |
| 100370 | `triple_add` | `clio triple add` |
| 100370 | `triple_end` | `clio triple end` |
| 100370 | `belief_observe` | `clio belief observe` |
| 100370 | `graph_link` | `clio graph link` |
| 100372 | `persona_put_stable` | `clio persona stable` |
| 100372 | `persona_observe_preference` | `clio persona observe` |
| 100372 | `task_upsert` | `clio task upsert` |
| 100372 | `failure_record` | `clio failure record` |
| 100372 | `scratchpad_write` | `clio scratchpad write` |
| 100372 | `scratchpad_read` | `clio scratchpad read` |
| 100372 | `scratchpad_clear` | `clio scratchpad clear` |
| 100372 | `canonical_put` | `clio canonical put` |
| 100372 | `shared_store` | `clio shared store` |
| 100372 | `shared_discard` | `clio shared discard` |
| 100372 | `validate` | `clio validate` |
| 100372 | `batch` | `clio batch` |
| 100374 | `update` | `clio update` |
| 100374 | `invalidate` | `clio invalidate` |
| 100374 | `discard` | `clio discard` |
| 100374 | `correct` | `clio correct` |
| 100376 | `hygiene_audit` | `clio hygiene audit` |
| 100376 | `hygiene_clean` | `clio hygiene clean` |
| 100376 | `hygiene_log_list` | `clio hygiene log` |
| 100376 | `export` | `clio export` |
| 100376 | `import` | `clio import` |
| 100376 | `erase_request` | `clio erase` |
| 100378 | `sync_status` | `clio sync status` |
| 100378 | `sync_push` | `clio sync push` |
| 100378 | `sync_pull` | `clio sync pull` |
| 100378 | `sync_serve` | `clio sync serve` |
| 100378 | `sync_ack_skip` | `clio sync ack-skip` (extension; CLI optional) |
| 100378 | `config_get` | `clio config get` |
| 100378 | `config_set` | `clio config set` |
| 100378 | `config_profiles` | `clio config profiles` |
| 100378 | `config_profile_apply` | `clio config use` |
| 100378 | `ranking_env_get` | `clio ranking get` |
| 100378 | `ranking_env_set` | `clio ranking set` |
| Deferred | `import_provider` | out of first release (`gaps/full-cli.md` non-goal; provider ingest is explicit later) |

## Coverage

- `bound_write_tools()` (`crates/clio-mcp/src/lib.rs:78`) and `bound_read_tools()` (`:120`) are fully assigned above, except `import_provider` (deferred) and the existing-phase tools.
- Phase 100380 adds `summarize` and the six FR-32 config/ranking tools to the MCP binding; their CLI ownership is fixed here (100370 and 100378 respectively).
- Validation: every tool name in the two bound lists appears exactly once in the table above. Re-run this check whenever either bound list changes or a new phase adds a command.

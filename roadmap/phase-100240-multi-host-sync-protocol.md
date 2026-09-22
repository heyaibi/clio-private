# Phase 100240: Multi-Host Sync Protocol

### Attribution
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | OpenCode CLI (Together . GLM-5.3 Flash High) | done |
| Adversary | r1 | Antigravity CLI (Gemini 3.8 Flash) | done |
| Remediator | r1 | OpenCode CLI (Go . Deepseek V4.1 Flash High) | done |
| Remedy Approver | r1 | OpenCode CLI (OpenRouter . Deepseek V4.1 Flash Max) | approved |
| Finalize | r1 | OpenCode CLI (Together . GLM-5.3 Flash High) | done |

**Index slice 100240 · **Effort:** `1.5×` · **Scope:** `roadmap/index.md` slice 100240 (authoritative)

### Vocabulary (read first) — zero shared moniker

| Term | Enum / form | Where it lives | Must not |
|------|-------------|----------------|----------|
| **`sync_serve`** | Authenticated sync **server** accepting push/pull | §4.9.5.D | Require every client to also serve |
| **`sync_push` / `sync_pull`** | Client incremental send / fetch-apply | §4.9.5.D | Be confused with **`batch_transaction`** (Phase 100200) or JSON **`memory_export_bundle`** (Phase 100220) |
| **`sync_status`** | Device id, cursors, pending counts, endpoint, auth/enc state, last error | §4.9.5.D | Return unmasked sync secrets or DEKs |
| **`sync_cursor`** | Opaque resume token per `(device_id, bank)` | Appendix | Be confused with MemTree dirty watermarks or doctor plan ids |
| **`sync_payload`** | Incremental mutation envelope batch | Wire protocol | Be an export file format or MCP schema pack |
| **`sync_lww_rule`** | Deterministic conflict resolution | Appendix | Replace §4.6 bi-temporal **`invalidate`** authorship |
| **`client_ciphertext`** | Optional client-encrypted content opaque to server | Wire + store | Ship or require **`subject_dek`** on the sync server |
| **`sync_mutation_id`** | Stable idempotency key for a mutation event | Envelope | Duplicate durable rows on retry |
| **`remote_admission_trust`** | Pull-apply trusts peer-admitted creates | Appendix apply matrix | Re-run local §4.2 θ (that is Phase 100220 import only) |
| **`sync_dead_letter`** | Quarantine for permanent apply failures | Appendix §7 | Hygiene discard or compliance erase |

Cursors, apply matrix, DLQ, state machine: [phase-100240-appendix-sync-cursors-conflict.md](phase-100240-appendix-sync-cursors-conflict.md).

---

## 1. Objective

### Goal
Implement the client/server **incremental sync protocol** alone (FR-31, §4.9.5.D): `sync_serve`, `sync_push`, `sync_pull`, `sync_status`, opaque cursors, idempotent apply, authentication outside dev mode, optional client-side encryption compatible with Phase 100020 DEK separation, bank scope, modes (push/pull/bidirectional), inclusion of durable **`assoc_edge`** mutations, and one documented deterministic conflict rule. Single-host deployments MAY omit runtime enablement, but claiming multi-host requires this full effort unit.

### Expected Outcome
- A process can `sync_serve(bind, auth?)` for one or more banks; clients `sync_push` / `sync_pull` against a remote.
- Incremental sync via persisted `sync_cursor`s; duplicate delivery does not duplicate memories.
- Non-dev mode rejects unauthenticated server access.
- Optional `client_ciphertext`: server stores opaque bytes without DEKs; local decrypt uses subject DEKs / KMS as today.
- Conflicts resolve via `sync_lww_rule`, are logged, and surface on `sync_status`.
- Pull apply uses `remote_admission_trust` (appendix matrix): already-admitted peer creates are **not** re-scored against local `θ_admit`.
- Permanent apply failures enter `sync_dead_letter` and **block** `pull_cursor` until operator `ack_skip`.
- Push does not require a local serve on the client host.
- Docs state single-host omission clearly when sync runtime is disabled.
- Property tests cover cursor crash-safety, idempotency, no-readmit divergence, DLQ blocking, and LWW.

### Parent Requirement
`requirement.md` (v1.9+) — §4.9.5.D, §4.9.6, §4.9.7, §7.4 KMS/store separation, FR-31, §4.5.9 assoc sync note.

### Design References (non-normative)
- **Opaque server + client encryption:** [secsync](https://github.com/nikgraf/secsync) / [Loro E2EE protocol notes](https://github.com/loro-dev/protocol/blob/main/protocol-e2ee.md) — relay stores ciphertext; keys stay with clients.
- **Cursor after durable apply:** [Client-side sync notes](https://andrewaltimit.github.io/Documentation/docs/distributed-systems/client-side-consistency.html) — advance cursor only post-apply; retries stay idempotent.
- **LWW vs CRDT:** same reference — LWW is acceptable for independent records when losing concurrent writes is documented; this project chooses documented LWW (not full CRDT text merge) per §4.9.5.D.4.
- **Operational exposure:** ephemeral high ports, default auto-stop TTL for interactive serve, dismissible firewall warning, and push-without-local-serve (local-first ops hygiene; appendix §10).

---

## 2. Scope Boundaries

### In Scope
- Sync server accepting authenticated push/pull for selected banks.
- Client push/pull/bidirectional modes and `sync_status`.
- Mutation journal or equivalent change feed producing `sync_payload` batches.
- Idempotent apply keyed by `sync_mutation_id`.
- Default `sync_lww_rule` per appendix; conflict journal visibility.
- Optional client encryption of content fields; server-blind storage.
- Bank-scoped sync; default all banks on device when unspecified.
- `assoc_edge` reinforce / `graph_link` / prune in the payload set.
- `remote_admission_trust` apply matrix, `sync_dead_letter`, and appendix state-machine property tests.
- Packaging/docs for enabling vs omitting sync on single-host profiles (including serve exposure hygiene).

### Explicitly Out of Scope
- Full CRDT collaborative text editing.
- Replacing bi-temporal supersession tools with sync merges.
- Provider import matrix (Phase 100220 stub remains separate).
- Redesigning DEK/KMS (Phase 100020/100190); only compatibility.
- P2P gossip without a server role (server role is required by catalog).
- Re-running local §4.2 admission θ on trusted peer-admitted creates (that would break convergence; see appendix §4). Phase 100220 JSON import remains fully gated.

### Must Not Change
- Phase 100020 separation of KMS and item store.
- Phase 100200 `batch` semantics (local atomic tool batches ≠ sync).
- Phase 100220 export format (offline portability ≠ live sync).
- Compliance erase path.

### Scope Expansion Rule
If work outside this scope appears necessary:
1. Stop.
2. Document the reason.
3. Request clarification or approval.
4. Do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- Phases 002–015: durable entities + `assoc_edge` exist.
- Phase 100160/100170: MCP tool binding patterns.
- Phase 100010: profiles can declare sync remotes / enable flags.
- Phase 100190: erased subjects fail closed on decrypt; sync must not rehydrate shredded plaintext.
- Phase 100230 recommended: `verify` clean before production sync serve.

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| Mutation journal / CDC | Can list mutations since cursor | Fixture push size |
| Auth material | Non-dev token/mTLS/config secret | Unauth request rejected |
| DEK interface | Local decrypt only | Server never receives DEK |
| Apply matrix | `remote_admission_trust` vs import gating distinguished | Peer create applies under high local θ |

---

## 4. Existing-System Discovery

### Required Discovery
- Whether a write-ahead mutation log already exists; if not, design minimal journal.
- Network stack available (HTTP) consistent with MCP Streamable HTTP choices.
- Profile flags for sync enablement and remotes.
- Secret masking for sync status.
- How discard/archive/erase appear as syncable ops.

### Discovery Output
Report journal approach, auth mechanism candidate, encryption envelope choice, and bank scoping strategy.

### Repository Adaptation Rule
Paths come from the repository; appendix defines logical envelopes.

---

## 5. Implementation Specification

### Task 1: Mutation Journal and Cursors

#### Intent
Support incremental sync with crash-safe resume.

#### Required Capability or Behavior
- Record durable mutations with `sync_mutation_id`, bank, entity fields per appendix.
- Persist `push_cursor` / `pull_cursor` per device/bank.
- Advance cursors only after durable ack/apply.

#### Architectural Responsibility
Sync journal + cursor store.

#### Required Changes
1. Journal schema/migration.
2. Cursor persistence API.
3. Include `assoc_edge` mutations.

#### Expected Result
Interrupted pull resumes without dup rows.

---

### Task 2: `sync_serve` + Auth

#### Intent
Run an authenticated sync server.

#### Required Capability or Behavior
- Bind address configurable; default local/dev serve uses an **ephemeral high port**.
- Non-dev: require auth (token, mTLS, or equivalent)—reject anonymous.
- Dev mode MAY relax auth only when profile explicitly marks `dev`; never default-open in production profiles.
- Interactive `sync_serve` SHOULD default to a **30-minute auto-stop TTL** unless opted into a long-running service unit.
- Accept push/pull for authorized banks only.
- Store optional `client_ciphertext` without needing DEKs.
- Operator docs: dismissible firewall/OS permission warning; state clearly that **push does not need local serve**.

#### Architectural Responsibility
Sync server runtime.

#### Implementation Constraints
- Do not log auth secrets.
- Follow appendix §10 serve exposure rules.

#### Expected Result
Unauthenticated non-dev request returns 401/equivalent; no mutation applied.

---

### Task 3: Client `sync_push` / `sync_pull` / Bidirectional

#### Intent
Ship client modes and status.

#### Required Capability or Behavior
- `sync_push(remote?, mode?)`: send mutations since push cursor; update cursor on ack.
- `sync_pull(remote?, mode?)`: fetch since pull cursor; idempotent apply; update cursor post-durable apply.
- Bidirectional: documented order (pull-then-push recommended).
- Push MUST work without local `sync_serve`.
- `sync_status()`: device id, cursors, pending counts, endpoint, auth/encryption state (masked), last error, conflict counts.

#### Architectural Responsibility
Sync client.

#### Expected Result
Two devices converge under LWW for conflicting upserts; status shows conflicts when they occur.

---

### Task 4: Idempotent Apply + Trust Matrix + Conflict + DLQ

#### Intent
Apply remote mutations safely, convergently, and with a single cursor/reject policy.

#### Required Capability or Behavior
- Dedupe on `sync_mutation_id` (appendix).
- Apply appendix §4 matrix: trusted remote creates use `remote_admission_trust` (schema/category/authz/erasure checks only—**no** local θ re-score). Metadata ops skip admission. Malformed/unauthorized → `sync_dead_letter`.
- Apply `sync_lww_rule` on concurrent entity conflicts; journal conflicts; surface via status.
- Erased subjects: do not resurrect plaintext; honor tombstones/fail-closed decrypt.
- Cursor policy: never advance `pull_cursor` past unapplied retryable or open dead-letter mutations; `ack_skip` required to skip poison ids (appendix §1 / §7).
- Implement appendix §9 state machine; ship property tests P-cursor-crash, P-idempotent, P-no-readmit-divergence, P-dlq-blocks, P-lww.

#### Architectural Responsibility
Sync apply engine.

#### Expected Result
Replayed batch is no-op; conflicting pair leaves one winner + conflict log entry; high local θ cannot drop a peer-admitted create; poison items freeze cursor until ack-skip.

---

### Task 5: Optional Client Encryption Envelope

#### Intent
Allow content to leave the node as ciphertext.

#### Required Capability or Behavior
- When enabled, encrypt content fields before push; server persists opaque bytes + routing metadata.
- Pull decrypts locally with subject DEKs / KMS.
- Status reports encryption enabled/disabled without secrets.

#### Architectural Responsibility
Client crypto adapter compatible with Phase 100020.

#### Expected Result
Server DB inspection shows ciphertext only for protected fields when mode on.

---

### Task 6: MCP/CLI Bindings + Conformance (1.5× fan-out)

#### Intent
Expose catalog tools and prove protocol requirements.

#### Required Capability or Behavior
- Bind `sync_serve`, `sync_push`, `sync_pull`, `sync_status`.
- Tests: incremental cursor, idempotent replay, auth reject, LWW conflict, assoc_edge sync, bank scope, push-without-local-serve, encryption opaque server (if enabled in test profile).
- Single-host profile docs: how to disable/omit sync runtime.

#### Expected Result
Conformance suite green; docs match FR-31.

---

### Implementation Freedom
Transport (HTTP JSON vs framed messages), journal storage, and auth plugin may vary if appendix semantics hold.

---

## 6. Agent Execution Rules

### Allowed Actions
- Implement journal, server, client, apply, crypto adapter, tests, docs.
- Reuse admission and discard/invalidate paths.

### Forbidden Actions
- Put DEKs on the server.
- Use export files as the live sync protocol.
- Skip auth in non-dev defaults.
- Silent data loss without conflict logging.
- Broad unrelated refactors; unapproved dependency upgrades.

### Agent Decision Boundary
May choose HTTP framework and journal batching sizes.

Must request approval for:
- Changing the published conflict rule or apply matrix.
- Peer-to-peer topology replacing server role.
- Re-introducing local θ re-admission on trusted peer creates.

### Mandatory Stop Conditions
Stop if mutation journal cannot be made complete for required entity kinds, if auth cannot be enforced in non-dev, or if DEK separation cannot be preserved.

---

## 7. Security Constraints

### Required Controls
- Auth required outside dev mode.
- Bank authorization on serve/push/pull.
- Secret masking on `sync_status` and logs (§4.9.7).
- Optional client encryption; server blind to plaintext content.

### Sensitive Data Rules
- Never commit sync tokens.
- Never transmit `subject_dek` to sync peers.

### Security Acceptance Conditions
- Unauth non-dev push/pull fails closed.
- Server storage of encrypted mode lacks plaintext snapshots.

---

## 8. Test and Verification Strategy

### Required Tests
- [ ] Unit: cursor advance / idempotent dedupe
- [ ] Integration: two-node push/pull converge
- [ ] Integration: conflict LWW + status
- [ ] Integration: assoc_edge sync
- [ ] Security: auth reject; secret masking
- [ ] Security: server-blind ciphertext mode
- [ ] Failure: crash mid-pull resume

### Required Test Scenarios

| Test ID | Scenario | Expected Result |
|---------|----------|-----------------|
| T100240-01 | Push then pull on second device | Item readable on B |
| T100240-02 | Replay same payload | No duplicate rows |
| T100240-03 | Concurrent upserts | Winner per `sync_lww_rule`; conflict logged |
| T100240-04 | Non-dev unauth serve | Rejected |
| T100240-05 | Push without local serve | Succeeds against remote only |
| T100240-06 | `assoc_edge` reinforce syncs | Edge present on peer |
| T100240-07 | Encrypted mode | Server lacks plaintext; client decrypts |
| T100240-08 | Peer-admitted create pulled into higher-θ node | Applied via `remote_admission_trust`; no θ reject |
| T100240-09 | Permanent malformed mutation | Dead-letter open; pull_cursor frozen until ack_skip |
| T100240-10 | Property suite (appendix §9) | P-cursor-crash, P-idempotent, P-no-readmit-divergence, P-dlq-blocks, P-lww pass |

### Negative Testing
Unknown bank scope rejected; erased subject content not resurrected; malformed envelope refused.

### Verification Rule
Multi-host claims need two-process (or equivalent) test evidence.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-100240-01 | Incremental cursors + idempotent apply | T100240-01/02 | PASS — `t24_01_push_then_pull_replicates_item_content`, `t24_02_same_mutation_id_applies_once_then_duplicates`, `t24_02_replay_push_and_pull_create_no_duplicates`: one durable row, cursors persist in `sync_cursors` and only advance after durable apply/ack |
| AC-100240-02 | Auth outside dev | T100240-04 | PASS — `t24_04_refuses_anonymous_bind_outside_dev_mode`, `t24_04_token_enforced_and_routes_scoped`, `dev_mode_accepts_anonymous_requests` without token refuses bind (`Forbidden`); wrong/missing bearer → 401, zero mutations applied; dev-mode relaxation only when `dev=true` |
| AC-100240-03 | Documented LWW conflicts | T100240-03 | PASS — `t24_03_lww_later_stamp_wins_loser_conflict_recorded` + `t24_03_equal_stamp_tie_broken_by_score_then_device`: later `transaction_time` wins, ties on admission score then `device_id`; loser retained + `sync_conflicts` row; conflicts surface in `sync_status` (`conflicts` count + `conflict_sample`) |
| AC-100240-04 | Optional client ciphertext | T100240-07 | PASS — `t24_07_client_encryption_server_blind_keyless_dead_letters`: server journal `content_sealed` holds client ciphertext only (no plaintext snapshot/gist), pull decrypts locally with `SyncCipherKey`; server holds no DEKs |
| AC-100240-05 | Bank scope + modes | Push/pull/bidi tests | PASS — `sync_push`/`sync_pull`/`bidirectional` client functions + MCP bindings; unauthorized bank → 403 on server, feed is per-bank with independent cursors |
| AC-100240-06 | `assoc_edge` included | T100240-06 | PASS — `t24_06_assoc_edge_syncs_and_lists_on_peer`: coactivation edge pushed and readable on peer via `list_assoc_edges`; reinforce/prune ops applied |
| AC-100240-07 | `remote_admission_trust` preserves convergence | T100240-08 / P-no-readmit-divergence | PASS — apply engine never re-scores (ungated store primitive is allow-listed in `gate_boundary_tests` with the convergence rationale); peer-admitted create with score 0.05 applies on any node |
| AC-100240-08 | Single-host omission documented | Doc inspection | PASS — `crates.md` clio-sync rationale + `crates/clio-sync/src/lib.rs` "Single-host omission" section: five sync tools gated by the profile sync-omission flag; single-host path has zero dependency on the crate |
| AC-100240-09 | DLQ blocks cursor until ack_skip | T100240-09 | PASS — `t24_09_erased_subject_resurrection_dead_letters` + `p_dlq_blocks_pull_cursor_until_key_or_ack_context`: poisoned mutation quarantines (`dead_letter_open ≥ 1`), `pull_cursor` frozen (re-pull does not advance), `ack_skip` marks `acked_skip` and the next pull advances past it without re-opening the row |
| AC-100240-10 | State-machine property tests | T100240-10 | PASS — `p_no_readmit_divergence_low_score_peer_create_applies`, `p_dlq_blocks_pull_cursor_until_key_or_ack_context`, `t24_08_crash_between_page_and_cursor_is_idempotent`, `t24_03_*` LWW pair, `t24_02_*` idempotence (41 clio-sync tests, 0 failed) |

### Definition of Done
- [x] All FR-31 surfaces implemented when multi-host claimed (`sync_serve`, `sync_push`, `sync_pull`, `sync_status` + operator `sync_ack_skip`).
- [x] Appendix rules implemented and tested (cursor model §1, envelope §2, idempotent apply §3, apply matrix §4, `sync_lww_rule` §5, DLQ §7, modes §8, state machine §9, serve exposure §10).
- [x] Files ≤ 450 lines (verified per file); suite green. Final gate `make coverage` exit 0: aggregate lines 97.87% / functions 98.86%. **Every reported file is ≥90% on both functions and lines** (remediation round r1: alongside the genuine dual per-`cfg` instantiation records there were real gaps — never-run error-mapper closures and untested functions — fixed by removing the unreachable closures, replacing them with shared unit-tested mappers, and adding the missing tests; stale `target/llvm-cov-target` artifacts that had inflated the misses are cleared with `cargo llvm-cov clean --workspace` before the gate).
- [x] Docs cover enable vs omit (`crates.md`, `clio-sync/src/lib.rs` crate docs, profile `omit_sync` gating).
- [x] Required approval is obtained (downstream pipeline step).

### Completion Evidence
- Two-node transcripts: `crates/clio-sync/src/client_tests.rs` runs real TCP two-node converge (device A push → server → device B pull; item readable on B), including `push` with no local serve (T100240-05) and bank scoping.
- Conflict sample: LWW pair recorded in `sync_conflicts` and surfaced via `sync_status` `conflict_sample` (`entity_id / loser_mutation_id`).
- Auth failure: non-dev serve without token refuses bind; wrong bearer token → HTTP 401 with zero applied mutations (T100240-04).
- Encryption inspection: server journal `content_sealed` carries client ciphertext in encrypted mode; decrypted only on the pulling client (T100240-07).
- DLQ freeze transcript: quarantine → frozen `pull_cursor` → `ack_skip` → cursor advances, row stays skipped, no content resurrection (T100240-09 / P-dlq-blocks).
- Conformance suites (post-remediation): `cargo test -p clio-sync --locked --lib` 64 passed / 0 failed; `cargo test -p clio-mcp --locked --lib sync` 9 passed / 0 failed; `cargo test -p clio-store --locked --lib sync` 17 passed / 0 failed.

### Remediation Evidence (round r1)

Adversary findings fixed and re-verified; `make check` exit 0 (1185 tests, 0 failed) and `make coverage` exit 0 (aggregate lines 97.87% / functions 98.86%; **no reported file below 90% on functions or lines**).

- **Clean build/lint (F-01):** removed the unused `ErrorCode` import from `journal_row.rs`; `make lint` (clippy `-D warnings`) is clean.
- **Per-file function coverage (F-02):** the dual per-`cfg` instantiation is real, but it had masked genuine gaps. Removed unreachable error-mapper closures (`content_for`, `crypto::seal`, `server::write_json`, `journal_row_to_mutation` error arms), introduced shared unit-tested mapper functions in `http.rs`, split push-side packaging into `client_feed.rs`, and added the missing tests. Final per-file functions/lines: `clio-sync/src` protocol.rs 100/100, client.rs 100/92.97, client_feed.rs 100/96.39, http.rs 100/99.15, server.rs 100/95.51, crypto.rs 100/94.74, apply.rs 100/97.29, clock.rs/journal_row.rs 100/100; `clio-store/src` postgres_sync.rs 100/100, sqlite_sync.rs 100/100, postgres_sync_rows.rs 100/96.97.
- **Rapid-update audit collision (F-03):** `update_audit_id` appends a process-wide atomic sequence to the millisecond stamp (`item_update.rs`), so two updates of one item in the same millisecond no longer collide. Regression test `memory_item_tests::sqlite_memory_item_suite` / `postgres_memory_item_suite` (`suite_rapid_updates_unique_audit`, 25 back-to-back updates).
- **Triples omitted from push (F-04):** `client_feed::push_bank` now packages closed triples from `feed_triples` as `invalidate` mutations, and `sync_status.pending_push` counts them. End-to-end test `triple_close_packages_as_invalidate_and_replicates` closes a triple on A, pushes, and the peer's matching triple closes; `triple_packaging_skips_open_and_missing_triples` covers the skip paths.
- **DLQ quarantine on unopenable ciphertext (F-05):** `decrypt_for_apply` quarantines a wrong-key/tampered/non-JSON payload as `malformed` and returns `Ok(None)` so `pull_cursor` freezes and `ack_skip` can unfreeze it. Test `wrong_cipher_key_quarantines_then_ack_skip_unfreezes`.
- **Pull 500 on unsealed journal rows (F-06):** `server::journal_row_to_mutation` serves empty plain content for a KMS-less (no sealed content) row instead of deserializing an empty string into a `CiphertextEnvelope`. Test `pull_survives_unsealed_journal_row_without_http_500`.
- **Roadmap isolation (F-07):** removed the `Phase 100020` reference from `crypto.rs`.
- **LWW device tie-break (F-08):** `apply::lww_loser` now compares against this node's device id instead of the empty string, removing the "any remote device wins a full tie" asymmetry. Covered by `t24_03_equal_stamp_tie_broken_by_score_then_device` (higher device id `peer-z` wins the tie).

---

## 10. Failure Handling and Recovery

### Expected Failure Modes

| Failure | Detection | Recovery |
|---------|-----------|----------|
| Network drop mid-batch | Client error / incomplete ack | Resume from last cursor; idempotent replay |
| Auth failure | 401 | Surface on status; do not advance cursor |
| Permanent apply reject | `sync_dead_letter` open | Freeze `pull_cursor`; operator `ack_skip` to advance |
| Transient apply reject | Retry budget | Retry without cursor advance; escalate to DLQ if exhausted |
| Conflict | LWW compare | Journal + status; winner applied |

**Cursor policy (normative):** never advance past unapplied retryable mutations; poison mutations require DLQ + `ack_skip` (appendix §1 / §7).

### Rollback Strategy
Disable sync profile flag; journals remain for audit. Do not delete peer data automatically.

### Partial Completion Policy
If serve works but conflict journaling is missing, phase is not complete.

---

## 11. Traceability

| Parent Requirement | Implementation Task | Verification | Acceptance Criterion |
|--------------------|---------------------|--------------|-----------------------|
| FR-31 / §4.9.5.D | Tasks 1–4, 6 | T100240-01–06, 08–10 | AC-100240-01–03, 05–07, 09–10 |
| §7.4 / §4.9.7 | Tasks 2, 5 | T100240-04/07 | AC-100240-02, AC-100240-04 |
| Convergence / appendix §4 | Task 4 | T100240-08 | AC-100240-07 |
| §4.9.6 omission | Task 6 docs | Inspection | AC-100240-08 |

---

## 12. Phase Exit Contract

### Outputs Produced
- Sync server + client tools
- Journal/cursors + conflict journal
- Optional client encryption path
- Appendix-normative LWW rule implementation

### Guarantees Provided to Downstream Phases
- Multi-host deployments have a complete, testable protocol.
- Single-host may omit runtime with documented honesty.

### Known Limitations
- LWW can drop concurrent loser values (logged, not CRDT-merged) — per the appendix §5 default, retained in `sync_conflicts`; owned by this phase's docs (no phase debt).
- Not a substitute for offline `export`/`import` portability (Phase 100220 remains the offline path).
- Journal/apply coverage by kind (what is missing, why, debt owner): this release journals and applies `item`, `assoc_edge`, `triple` (invalidate), and tombstone/discard metadata — the entity kinds the change feed produces and the apply matrix defines for this slice. Envelopes for `persona`/`task`/`failure`/`belief` are accepted on the wire (schema-complete) but arriving ones are quarantined as `unsupported_op` (never silently dropped), because those domains (PersonaStore EMA observe, HistoryStore records, BeliefStore append validation) lack plain cross-node upsert semantics that would be honest to sync; debt owner: post-roadmap sync hardening, which must add per-domain upsert semantics before those kinds sync. No downstream phase in the roadmap depends on them.
- Client-side push change feed uses wall-clock watermark stamps from the durable rows (millisecond ISO text); commit ordering for PULL is the per-bank journal `seq`, and a truncated push page re-sends trailing rows with idempotent dedupe absorbing them. Owned by this slice; upgrade path = a write-path journal hook (Phase 100020 index-pending pattern) if wall-clock skew ever matters.
- HTTP transport is plaintext JSON over std TCP with bearer-token auth; mTLS/TLS is not implemented (the requirement allows "token, mTLS, or equivalent"). Debt owner: post-roadmap deployment hardening for TLS-terminated deployments.
- LWW tie-break uses the receiving node's device id as the existing row's side because items do not persist their originating device id (`apply::lww_loser`). This removes the old empty-string asymmetry (any remote device won a full tie) and is deterministic per node, but a row that originated on a peer is compared under this node's id rather than its true origin. What is missing and why: true cross-node symmetric tie-break needs the origin device persisted per item or a sync-origin table, which this slice does not add. Debt owner: post-roadmap sync hardening (schema plus both backends) before device-id ordering can be called globally symmetric. No downstream phase depends on it.
- llvm-cov note: `cargo llvm-cov` counts every per-`cfg`/per-crate-hash instantiation and every closure as a separate function record (`instantiations` column). Running `cargo llvm-cov` on a dirty `target/llvm-cov-target` merges stale pre-refactor instantiations and can over-report misses, so the workspace gate is run after `cargo llvm-cov clean --workspace`. After round r1 all reported files pass ≥90% on both functions and lines in the clean workspace run; no coverage limitation remains.

### Downstream Prerequisites
- None inside the 24-slice set; post-roadmap work may add provider ingest or CRDT modes only with new requirements.

### Final Status
PASS WITH DOCUMENTED LIMITATIONS

### Verification Sign-Off
- Implementer: OpenCode CLI (Together . GLM-5.3 Flash High), developer round r1
- Verifier: pending (Adversary round r1)
- Human Approver: [Name, if required]
- Date: 2026-09-20

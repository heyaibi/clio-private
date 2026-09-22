# Phase 100240 Appendix: Sync Cursors, Apply Matrix, Conflict Rule, and State Machine

**Consumers:** Phase 100240 multi-host sync. Normative default for first release; deployments MAY document a stricter conflict rule only by replacing this default entirely (never mix rules mid-bank).

### Vocabulary (zero shared moniker)

| Term | Meaning | Must not confuse with |
|------|---------|------------------------|
| **`sync_cursor`** | Opaque, monotonically advancing resume token per `(device_id, bank)` | MemTree dirty watermark or index rebuild cursor |
| **`sync_mutation_id`** | Stable id for a durable mutation event | Memory `item_id` (related but not identical) |
| **`sync_lww_rule`** | Deterministic last-writer conflict resolution | Bi-temporal **`invalidate`** supersession (§4.6) |
| **`client_ciphertext`** | Optional client-encrypted payload opaque to sync server | Server-held **`subject_dek`** (MUST remain local/KMS) |
| **`sync_dead_letter`** | Quarantined unapplied mutation awaiting operator ack | Hygiene discard or compliance erase |
| **`remote_admission_trust`** | Apply path that trusts a peer's already-admitted create | Phase 100220 **`gated_json_import`** (re-admits) |

**Convergence invariant:** For authenticated peers syncing the same bank under this protocol, every successfully applied `sync_mutation_id` eventually appears on all peers (modulo documented LWW loser retention as history, not as silent drop without journal). Local `ranking_env` MUST NOT reject an already-admitted remote create solely because local `θ_admit` would have scored it differently.

---

## 1. Cursor model

1. Each device persists `sync_cursor` values: `push_cursor` (last mutation successfully accepted by remote) and `pull_cursor` (last remote mutation durably applied **or** durably quarantined with operator-ack skip — see §7).
2. Cursors are **opaque strings** to clients (implementation MAY encode sequence + checksum). Clients MUST NOT invent cursors; only the peer that issued them may advance them.
3. Advance a cursor **only after** durable local apply (pull) **or** durable dead-letter quarantine with recorded ack-skip (pull) **or** durable remote ack (push). Crash mid-batch resumes from the last persisted cursor; duplicate delivery is safe via idempotent apply.
4. Bank-scoped sync uses independent cursors per bank. Default “all banks” mode iterates banks and reports per-bank status in `sync_status`.

**Normative reject policy:** Do **not** advance `pull_cursor` past an unapplied mutation that is still retryable. Poison / permanently rejected mutations enter `sync_dead_letter` and block cursor advance until an operator ack-skip is recorded for that `sync_mutation_id`.

---

## 2. Mutation envelope (logical)

Every synced record MUST carry at least:

```text
{
  sync_mutation_id,   // stable, globally unique
  bank,
  entity_kind,        // item | triple | assoc_edge | persona | task | failure | belief | tombstone_meta
  entity_id,          // stable business id
  op,                 // upsert | invalidate | discard | archive | reinforce | prune | ...
  transaction_time,   // writer’s transaction_time.start (or close stamp for invalidate)
  device_id,
  content_or_ciphertext,
  content_hash,       // hash of plaintext logical content (even when wire form is ciphertext)
  admission_receipt?  // optional: { admitted: true, score?, category?, epistemic_kind? } from origin device
}
```

`assoc_edge` mutations (coactivation reinforce, explicit `graph_link`, prune) MUST be included when multi-host sync is claimed (§4.9.5.D.9).

---

## 3. Idempotent apply

1. Primary key for dedupe: `sync_mutation_id`. Re-delivery → no-op success (counts as applied for cursor purposes).
2. Secondary guard: same `(entity_kind, entity_id, content_hash, op)` already applied → no-op.
3. Never create a second durable row for the same `sync_mutation_id`.

---

## 4. Apply matrix (`remote_admission_trust`)

| Op class | Examples | Local gates on pull | Notes |
|----------|----------|---------------------|-------|
| **Trusted remote create/upsert** | `upsert` item/triple/persona/task/failure/belief with stable `entity_id` + origin `admission_receipt.admitted=true` (or equivalent already-durable peer evidence) | Validate schema, category whitelist membership, authz/bank scope, erased-subject fail-closed | **Do not** re-run §4.2 scoring against local `θ_admit`. Optional local re-score MAY be logged as advisory telemetry only. |
| **Metadata / lifecycle** | `invalidate`, `discard`, `archive`, `flag`, reinforce/prune `assoc_edge` | Validate referential targets + authz | No admission scoring |
| **Malformed / unauthorized** | bad schema, wrong bank, auth failure, DEK-erased subject content resurrect attempt | Reject → `sync_dead_letter` | Cursor does not advance until ack-skip |
| **Offline JSON import** (Phase 100220) | `import` tool | Full §4.1–§4.2 | Different trust boundary; not this matrix |

This matrix is the FR-31 convergence rule. Phase 100220 import remains gated because export files are not authenticated peer journals.

---

## 5. Default conflict rule (`sync_lww_rule`)

When two **concurrent** mutations target the same logical entity and both are otherwise valid:

1. Compare `transaction_time` (later wins).
2. If equal, compare `admission_score` / importance if present on both; higher wins.
3. If still tied, compare `device_id` lexicographically; higher wins.
4. Loser is **not deleted**. Record a conflict journal entry and, for discrete facts, prefer closing the loser via ordinary invalidation semantics when applicable—do not invent a third deletion path.
5. Conflicts MUST appear in `sync_status` (counts + last conflict summary). Full detail MUST be queryable via ops/audit surfaces without leaking secrets.

**Explicit non-goals:** this is not a text CRDT merge and not a substitute for §4.6 supersession authorship. Authors still invalidate via normal tools; sync only converges replicas.

---

## 6. Encryption posture

- Optional: client encrypts `content_or_ciphertext` before leave-node; server stores opaque bytes and routing metadata only.
- Server MUST NOT require `subject_dek` material. DEKs stay in local/KMS per §7.4.
- `sync_status` and logs mask sync auth secrets (last-4 / redacted).

---

## 7. Dead-letter and operator ack-skip

1. Permanent apply failures (schema, authz, erased-subject resurrection, unsupported op) write a `sync_dead_letter` row: `{sync_mutation_id, bank, reason_code, first_seen, last_error, status: open|acked_skip}`.
2. Open dead-letters appear in `sync_status` (`dead_letter_count`, sample ids).
3. Operator `ack_skip(sync_mutation_id)` (CLI/tool) sets `acked_skip`, after which `pull_cursor` MAY advance past that id.
4. Transient failures (network, DB lock) MUST retry without dead-letter until a documented retry budget is exhausted, then dead-letter.

---

## 8. Modes

| Mode | Behavior |
|------|----------|
| `push` | Send local mutations since `push_cursor` |
| `pull` | Fetch/apply remote mutations since `pull_cursor` |
| `bidirectional` | Pull then push (or documented equivalent) in one operator action |

Push MUST NOT require a local `sync_serve` on the client host.

---

## 9. Formal state machine (per bank)

States for the **pull pipeline** (client):

```text
IDLE
  -- sync_pull --> FETCHING
FETCHING
  -- batch received --> APPLYING
  -- network error --> IDLE (cursor unchanged; surface last_error)
APPLYING (for each mutation in order)
  -- idempotent hit --> next
  -- apply ok (matrix) --> next; persist apply receipt
  -- LWW resolve --> next; append conflict journal
  -- transient fail --> RETRYING
  -- permanent fail --> DEAD_LETTER_OPEN (cursor frozen at prior id)
RETRYING
  -- success --> APPLYING/next
  -- budget exceeded --> DEAD_LETTER_OPEN
DEAD_LETTER_OPEN
  -- operator ack_skip --> CURSOR_ADVANCE then IDLE/APPLYING
CURSOR_ADVANCE
  -- durable cursor write --> IDLE or FETCHING more
```

States for the **push pipeline**:

```text
IDLE -- sync_push --> SENDING -- remote ack --> CURSOR_ADVANCE --> IDLE
                 \-- error --> IDLE (push_cursor unchanged)
```

**Property tests (required in Phase 100240 conformance):**

| Property | Check |
|----------|-------|
| P-cursor-crash | Kill mid-APPLYING; restart pull; no dup rows; cursor ≤ last durable apply |
| P-idempotent | Deliver same `sync_mutation_id` thrice → one durable effect |
| P-no-readmit-divergence | Peer A admits low-score item; B with higher θ still applies via `remote_admission_trust` |
| P-dlq-blocks | Permanent fail freezes cursor until ack_skip |
| P-lww | Concurrent upserts → one winner + conflict journal row |

---

## 10. Serve exposure (ops hygiene)

When documenting/implementing `sync_serve`:

1. Prefer **ephemeral high ports** for local/dev serve; do not default to a well-known privileged port.
2. Non-dev profiles MUST require auth; refuse anonymous bind.
3. Prefer a **default auto-stop TTL** (e.g. 30 minutes) for interactive local serve unless the operator opts into a long-running service unit.
4. Operator docs MUST warn that opening `sync_serve` may require an explicit firewall/OS permission and that **push does not require a local serve** on the pushing host.

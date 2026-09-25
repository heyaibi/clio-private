# Clio Security Audit — Findings

**Target:** `/Users/aiuser/Documents/projects/agentmemoir/clio` (16-crate Rust workspace)
**Date:** 2026-09-25
**Mode:** Read-only. No repository file was modified. All reproductions ran from a scratch crate outside the repo (`/private/var/.../opencode/audit`) linked against the real crates by path.

**Method:** Source review of the store, sync, MCP, compliance, and index crates. Every finding below was executed against the real production code path (real `McpState`, real `SqliteStore`, real `sync_serve`, real `SyncCipherKey::seal`) and then independently challenged by a second agent before inclusion.

---

## Summary

| # | Finding | Severity | Reproduced | Issue |
|---|---------|----------|-----------|-------|
| 1 | Plaintext triple SPO survives compliance erasure | **High** | Yes, end-to-end via MCP `triple_add` | heyaibi/clio#20 |
| 2 | Deterministic AEAD nonce in sync encryption | **Medium** | Yes, keystream reuse + plaintext recovery | heyaibi/clio#21 |
| 3 | Sync server buffers unboundedly before authenticating | **Medium** | Yes, against real `sync_serve` | heyaibi/clio#22 |
| 4 | MCP HTTP spawns unbounded threads with no read timeout | **Low** | Yes, against real HTTP transport | heyaibi/clio#23 |
| 5 | Provider API key and memory payload sent over cleartext `http://` | **Low** | Yes, bytes captured off the socket | heyaibi/clio#24 |

---

## 1. Plaintext triple content survives compliance erasure — **High**

### What

A knowledge triple's subject, predicate, and object are stored as plaintext text in the `triples` table, even though the same content is correctly sealed inside the carrier item's `content_ciphertext`. The compliance erasure path never touches the `triples` table, so a verified erasure request destroys the DEK and renders the carrier item unreadable — while the identical content sits in the clear in a neighbouring table and remains fully readable with no key.

### Where

- Schema: `sql/001_core.sql:236-238` — `subject`, `predicate`, `object` are plain `text NOT NULL` columns.
- Write: `crates/clio-store/src/sqlite_triple.rs:158-186` inserts them verbatim. Postgres equivalent: `crates/clio-store/src/postgres_triple.rs`.
- The content is *also* written correctly sealed: `crates/clio-write/src/triple.rs:246-276` builds a carrier item whose `snapshot`/`gist` contain the same SPO, and that item is DEK-sealed.
- Erase: `crates/clio-store/src/sqlite_erase_purge.rs` issues deletes against `item_embeddings`, `index_pending`, `items_fts`, `assoc_edges`, and `memtree_nodes`. There is **no** statement against `triples`. Postgres: `crates/clio-store/src/postgres_erase.rs`, same omission.
- The only `DELETE FROM triples` in the entire workspace is test fixture code: `crates/clio-store/src/pg_ops_tests.rs:90`.

### Why it matters

This is the storage design for the `beliefs` table done correctly, one table over. The `beliefs` DDL at `sql/001_core.sql:335-337` states the intended rule explicitly:

> The proposition CONTENT is sealed under the subject DEK; only the normalized identity key and structure are plaintext (§7.4 field-level encryption).

The `triples` table applies the opposite treatment to the same kind of content.

The normative requirement is not ambiguous. `private/clio-private/baseline/requirement.md:707` (§7.4.1):

> Every memory item's content payload — the structured snapshot (§7.2), the gist text, the belief proposition text, and source `context` when present — is stored encrypted under a per-data-subject data encryption key (DEK) … The bi-temporal *structure* … is treated as metadata and MAY remain in plaintext; the *content* is unreadable without the DEK.

A triple's SPO is proposition content, not bi-temporal structure. And §7.4.3 (`:709`) requires propagation to derived structures so that "no derived summary or readable context projection continues to describe content that is no longer legible." The `triples` row is precisely such a projection, and it is not reached.

### Reproduction

Driven through the real MCP tool handler, then the real erasure API:

```
[mcp] triple_add over the real MCP handler -> ok=true
[mcp] triples rows now: 1
[mcp]   service:hunter2Correct | runs_on | host:db-hunter2Correct.internal:5432

[erase] erase_subject ok: 1 tombstone(s) written
[erase] carrier item now: unreadable (ErasedSubject)   <- DEK destroyed, as designed
[erase] triples rows surviving erase: 1
[erase]   subject = service:hunter2Correct
[erase]   object  = host:db-hunter2Correct.internal:5432
[erase]   contains the secret: true
```

A separate run confirmed the plaintext is present in the raw `.db` bytes on disk, and that `list_triples` returns the SPO with no DEK present at all.

### Impact

- **Confidentiality.** Anyone with read access to the database file (backup, snapshot, stolen disk, misconfigured volume) reads every triple in cleartext. The per-subject DEK provides no protection for this content.
- **Compliance.** A data-subject erasure request is recorded as successful — tombstone written, DEK destroyed, verification probe passes — while the subject's content remains readable. That is a false attestation of erasure. The system's own audit trail says the erasure worked.

The subject of a triple is attacker- and user-supplied free text via the `triple_add` MCP tool, so real deployments will contain whatever people put there.

### Fix

Decide the storage shape explicitly, then implement it. Either seal the SPO under the subject DEK and keep only a normalized identity key in plaintext (matching the `beliefs` design and its DDL comment), or add `triples` to the erasure purge in both `sqlite_erase_purge.rs` and `postgres_erase.rs`. The first is the one consistent with §7.4.1 as written. Either way, add a regression test asserting that a `triple_add` followed by `erase_subject` leaves no readable copy.

---

## 2. Deterministic AEAD nonce in sync client encryption — **Medium**

### What

`sync_push` optionally encrypts outgoing content with XChaCha20-Poly1305. The nonce is derived from the wall clock and the plaintext length. It contains no random input.

`crates/clio-sync/src/crypto.rs:79-88`:

```rust
let nanos = std::time::SystemTime::now()...as_nanos();
let digest = clio_store::sha256_hex(
    format!("{nanos}|{}", plaintext.len()).as_bytes(),
    "am-sync-nonce",
);
let nonce_bytes: [u8; 24] = digest.as_bytes()[..24].try_into()...
```

A source comment at `crypto.rs:77-78` acknowledges the shortcut: *"switch to OsRng at the first cryptanalytic or throughput concern."*

### Reproduction

Calling the real `SyncCipherKey::seal` 240,000 times across 8 threads under one key:

```
[seal] 240000 seals across 8 threads -> 43932 distinct nonces
[seal] nonce values reused = 42793, worst single-nonce reuse = 8
[leak] msg ct#13836 XOR msg ct#43800 == pt#13836 XOR pt#43800 : true
[leak] recovered pt#13836 with NO key                 : {"w":0,"i":0013836}
[leak] recovery matches the true plaintext         : true
```

Separately, the nonce of a live ciphertext was reproduced offline from (clock, length) in 200/200 trials with no key material.

### Impact, stated precisely

XChaCha20-Poly1305's security requires that a (key, nonce) pair is never reused. When it is, the keystream repeats, so `ct1 XOR ct2 == pt1 XOR pt2`. An observer who also knows one plaintext — a plausible guess, a low-entropy field, or anything confirmed via the `content_hash` the protocol already sends in the clear at `crates/clio-sync/src/client_feed.rs:236-240` — recovers the other.

### Corrections to my initial assessment

I initially overstated this. Three things are wrong in a first reading:

- The 24-byte nonce is 24 **ASCII hex characters**, not 24 digest bytes (`sha256_hex` returns hex text). That is 96 bits of hash output, not 192.
- The XOR identity holds for the ciphertext **body**, not the full `ciphertext_b64` value, which appends the 16-byte Poly1305 tag.
- My 8-thread demonstration is not the single-CLI-push shape. `push()` is sequential for one process. Reuse arises from the concurrency that *is* real: MCP HTTP handles each connection on its own thread (`crates/clio-mcp/src/http.rs:99-106`), multiple client processes and multiple devices share one `sync_key`, and concurrent `sync_push` calls overlap.

Poly1305 key reuse also opens a forgery path, but only with further known/chosen message-tag pairs. A passive observer holding two opaque ciphertexts does not automatically gain arbitrary forgery. I am not claiming that.

Nonce **predictability alone is not a vulnerability** — nonces are public values. The defect is reuse.

**Severity: Medium.** It becomes High against a malicious sync peer or on-path observer that holds one known plaintext, since the server stores client ciphertext verbatim.

### Fix

Draw 24 raw bytes from `OsRng` per seal, or use a persisted per-key counter. Add a test that asserts uniqueness under concurrency — the existing `crypto_tests.rs:58-65` only checks two sequential seals differ, which passes purely because the clock ticked.

---

## 3. Sync server buffers unboundedly before authenticating — **Medium**

### What

`read_request` grows its buffer until it sees the header terminator and the declared `Content-Length` bytes, with no cap on either. It has no equivalent of the MCP transport's 10 MiB `MAX_BODY` (`crates/clio-mcp/src/http.rs:37-38`). Critically, `handle_connection` calls it **before** checking authorization:

`crates/clio-sync/src/server.rs:173` calls `read_request`; `crates/clio-sync/src/server.rs:181` calls `authorized`. `serve_loop` (`server.rs:151-170`) then handles each connection **serially in the accept loop**, with no thread spawn.

### Reproduction

Against a real `sync_serve` with a token configured:

```
[baseline] authorized empty push -> HTTP/1.1 200 OK
[flood] one connection buffered ~11 MiB in 5.117s with no header terminator
[hol]   legitimate request during one stalled connection: HTTP/1.1 200 OK
[hol]   legitimate request waited 11.130s
[after] server recovered -> HTTP/1.1 200 OK in 55.172ms
```

An unauthenticated client occupies the single accept slot for the full read window while never presenting a token.

### Corrections to my initial assessment

- The 5-second `set_read_timeout` (`server.rs:160-162`) is a **per-read** timeout, not a total request deadline. A client dribbling a byte every few seconds holds the connection indefinitely. I previously described it as a hard bound.
- The result of `set_read_timeout` is discarded.
- The default bind is loopback, so exposure requires an operator binding to a LAN or `0.0.0.0` with a token.

**Severity: Medium** when network-exposed, **Low** for the loopback default. This is a pre-authentication availability issue, not an authorization bypass.

### Fix

Cap the header block and declared body length, add a total request deadline, and replace the serial accept loop with a bounded worker pool.

---

## 4. MCP HTTP spawns unbounded threads with no read timeout — **Low–Medium**

### What

`serve_with_listener` spawns one `std::thread::spawn` per accepted connection with no cap and no pool (`crates/clio-mcp/src/http.rs:99-106`). `handle_conn` blocks in `read_request` (`:111-124`, `:151-209`) and no read timeout is ever set on the stream. The `MAX_BODY` checks at `:165-189` bound completed data but do nothing for a connection that sends no bytes.

### Reproduction

```
[idle]    200 idle connections held open, none authenticated
[idle]    live threads on this host: 202
[serve]   after 200 idle conns, authorized request -> HTTP/1.1 200 in 3.4ms
[exhaust] connect() started failing after 14727 extra idle connections
[exhaust] authorized request now -> connect failed: Can't assign requested address
```

### Corrections to my initial assessment

- Request bodies **are** capped at 10 MiB. The missing protection is the count and lifetime of threads, not body size.
- A non-loopback bind cannot start without a token (`http.rs:90-96`), but the token is not needed to occupy a thread — allocation happens before any auth decision.
- A valid-token holder doing this to themselves is not a privilege escalation. The realistic adversaries are an untrusted local process, or a container/reverse-proxy setup that publishes the loopback port.

**Severity: Low** for the documented loopback default, **Medium** if the listener is exposed.

### Fix

Set read/write deadlines before parsing, and replace one-thread-per-connection with a bounded worker pool or semaphore.

---

## 5. Provider API key and memory payload sent over cleartext `http://` — **Low–Medium**

### What

`HttpEndpoint::parse` accepts `http://` for any host, not just loopback (`crates/clio-index/src/http.rs:71-80`). `post_json` then attaches the provider key as a bearer token (`:252`, `:285`). Config validation for `embed.url` / `rerank.url` / `extract.url` only requires the value be a string (`crates/clio-config/src/config/validate.rs:254-266`) — there is no scheme or host restriction, and no warning for a non-loopback plaintext endpoint.

### Reproduction

Bytes captured off a socket by the real client:

```
[parse] accepted remote http:// -> host=api.vendor.example.com port=80 path=/v1/embed

[wire]   POST /v1/embed HTTP/1.1
[wire]   authorization: Bearer sk-live-VENDORKEY-abc123
[wire]   {"input":"confidential memory text","model":"m"}
[wire] provider API key appeared in cleartext on the wire: true
[wire] confidential request payload in cleartext           : true
```

### Impact

An operator who points `extract.url` (or embed/rerank) at a remote `http://` endpoint sends a long-lived provider API key and memory content — the actual text being embedded or extracted — in cleartext. The request also traverses DNS and routing unencrypted, so a network attacker can read and modify both. Nothing in the product warns or blocks this.

**Severity: Low–Medium.** It requires a configuration choice, but the default posture for a "local sidecar" feature is being applied to arbitrary remote hosts without a guard.

### Fix

Require `https://` for any non-loopback host and warn (or refuse) on `http://` to a remote address, matching the loopback-only rule the MCP HTTP bind already enforces.

---

## Examined and not reported

I want to be explicit about hypotheses I tested and dropped, so they are not re-litigated.

- **Caller-controlled `bank` in MCP tools.** `resolve_ctx` (`crates/clio-mcp/src/runtime_context.rs:69-93`) lets the caller name any bank, with a single gate on the reserved `shared` bank. This is by design: banks are per-agent namespaces within one deployment, not a tenant boundary. The sync server, which *is* a multi-party boundary, does enforce an allowlist (`server.rs:230-232`). Not a finding.
- **Plaintext MemTree `summary_gist`.** `sql/001_core.sql:465` is a plaintext column and `memtree_attach.rs:54` copies the plaintext gist into it — I proved the row lands in cleartext on disk. But `upsert_memtree_node` has **no production caller**: the only call sites are test fixtures (`memtree_persist_tests.rs`, `erase_test_support.rs`, `task_tests.rs`). The live MCP runtime keeps the tree in memory (`runtime_open.rs`). Latent defect in a persistence primitive, not a reachable vulnerability. Worth a guard test before anyone wires it up.
- **`postgres::NoTls` (`crates/clio-store/src/postgres.rs:54`).** The connection never uses TLS, so a non-loopback Postgres would carry credentials and all content in cleartext. The shipped default is `127.0.0.1` (`.env.example:16`) and the compose service is local. Conditional on deployment; no `sslmode` handling exists to make it worse.
- **Prompt injection through stored gists into `compose_context`.** The retrieval pack is token-budgeted and section-structured but does not mark memory content as untrusted data. This is an architectural property of any memory system rather than a code defect, and I found no concrete injection path to demonstrate.
- **Erase completeness of `summary_gist`.** Erase does null ancestor summaries and deletes the leaf (`sqlite_erase_purge.rs:113-161`), though the ancestor walk caps at 64 hops. Not reported separately; the triples gap in Finding 1 is the material one.

---

## Verification notes and limitations

**What I ran.** The four reproductions above execute real production code — real `McpState` and `McpHandler`, real `SqliteStore` with the real `LocalDevKms`, real `sync_serve` over real TCP, real `SyncCipherKey::seal`. The verification subagent additionally ran `cargo test -p clio-sync` (65 passed), `cargo test -p clio-mcp http_tests` (12), `cargo test -p clio-store erase_tests` (11), `memtree_persist_tests` (2), `cargo test -p clio-write memtree` (18), and `cargo test -p clio --test mcp_http_bind_harness` (4).

**Limitations, stated plainly.**

- No dependency advisory scan. `cargo-audit`, `cargo-deny`, `osv-scanner`, `semgrep`, and `trivy` are not installed on this machine. `Cargo.lock` is present and `gitleaks` is available, but the vulnerability surface of third-party crates is **unreviewed**. This is a real gap in coverage.
- PostgreSQL was not exercised. No server was available, so the Postgres paths in Findings 1 and 3 are confirmed by code reading and schema inspection only, not by execution. Both backends use parallel SQL in `postgres_triple.rs` / `postgres_erase.rs` with the same omission.
- The 5-second sync read timeout and the ~11 MiB buffering figure are specific to this host's speed. The unbounded-growth property is structural; the exact numbers are not portable.
- The codebase-memory graph index was unavailable for this session, so discovery was by `grep`/`glob` and direct reading rather than call-graph analysis. I may have missed paths that a call graph would have surfaced.
- I did not audit the Docker Compose deployment, CI workflows, or the model-provider response-handling paths in depth.

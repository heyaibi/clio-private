# Phase 100220 Appendix: Export Bundle Format and Content Modes

**Consumers:** Phase 100220 JSON export/import. Normative for first-release bundle shape and content modes.

### Vocabulary (zero shared moniker)

| Term | Meaning | Must not confuse with |
|------|---------|------------------------|
| **`memory_export_bundle`** | Versioned JSON (or directory) package of memories + manifest | **`sync_payload`** live journal |
| **`completeness_manifest`** | Inventory with counts, checksums, `complete` flag | Doctor repair plan |
| **`export_content_mode`** | `dsar_plaintext` \| `ciphertext_backup` | Sync `client_ciphertext` wire mode |
| **`canonical_json`** | Deterministic UTF-8 JSON used for checksums | Pretty-printed operator views |

---

## 1. Bundle layout (choose one; document in code)

**Single-file (default):**

```text
{
  "format": "clio.memory_export",
  "format_version": 1,
  "content_mode": "dsar_plaintext" | "ciphertext_backup",
  "manifest": { ... completeness_manifest ... },
  "entities": { "items": [...], "triples": [...], "assoc_edges": [...], ... }
}
```

**Directory alternative:** `manifest.json` + `entities/*.jsonl` with the same logical fields; manifest lists relative paths + per-file sha256.

Unsupported `format_version` → import reject before any write.

---

## 2. Completeness manifest fields

| Field | Required | Notes |
|-------|----------|-------|
| `format_version` | yes | Integer; match bundle |
| `content_mode` | yes | See §3 |
| `bank_ids` | yes | Array |
| `counts_by_type` | yes | items/triples/assoc_edges/persona/task/failure/belief/… |
| `counts_by_category` | yes | Semantic categories + episodic tags as applicable |
| `content_sha256` | yes | Hash of canonical payload bytes (see §4) |
| `filter` | yes | Object describing selection; empty means full |
| `generated_at` | yes | RFC 3339 UTC |
| `complete` | yes | `false` if filtered/truncated; MUST list `omissions[]` when false |
| `omissions` | when incomplete | Human/machine notes of what was left out |

---

## 3. Content modes (`export_content_mode`)

| Mode | When | Content bytes | Authz |
|------|------|---------------|-------|
| **`dsar_plaintext`** (default) | Audit / data-subject access / operator migration needing readable JSON | Decrypt in-process under caller authorization; write **plaintext** snapshots/gists/propositions | Fail closed if caller lacks export authz; **never** write DEKs, API keys, or sync credentials |
| **`ciphertext_backup`** | Like-to-like restore between nodes that share key custody out-of-band | Emit opaque payload blobs + key/subject ids **without** DEK material | Same authz bar; importer must be able to attach local KMS; not a DSAR substitute |

Erased/shredded subjects: both modes export **tombstone metadata only**, never recoverable personal content.

NFR-6 fields (confidence, admission, telemetry) MUST appear in both modes' metadata; in `ciphertext_backup`, content bodies remain opaque but metadata inventory remains complete.

---

## 4. Canonicalization and checksums

1. Build a **canonical JSON** encoding of the payload entities object:
   - UTF-8
   - Object keys sorted lexicographically at every level
   - No insignificant whitespace
   - Arrays preserve documented entity order (sort by `entity_id` ascending unless a type defines otherwise)
2. `content_sha256` = hex SHA-256 over those canonical bytes.
3. Import MUST recompute and compare before any write. Mismatch → reject entire bundle (even with `force`).

---

## 5. Import interaction

| Situation | Behavior |
|-----------|----------|
| `dsar_plaintext` import | Full §4.1–§4.2 gates on would-create candidates |
| `ciphertext_backup` import | Restore opaque bytes + metadata; do not invent plaintext; index rebuild may be deferred until decryptable |
| Re-import same identities/hashes | Idempotent skip |
| `force=true` | Auditable overwrite/supersede; prefer invalidate+insert for discrete facts |

Provider adapters are out of first release (see FR-29 / index Explicit later); this appendix covers JSON bundles only.

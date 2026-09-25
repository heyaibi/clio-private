## Summary

When any existing item row in a bank has a sealed body that fails AEAD authentication (for example one flipped character inside `items.content_ciphertext`), every new `remember`/`store` write to that bank fails with `factor_unavailable: content decryption failed`, even though the new write does not touch the unreadable row. The admission novelty factor appears to decrypt neighbor rows and propagates the decrypt error instead of skipping the unreadable row.

Found incidentally while verifying a separate read-listing fix; not fixed in that change.

## Reproduction

1. Create a data dir and store one item:

   ```
   CLIO_DATA_DIR=/tmp/repro clio remember "tamper probe note" --category task_spec --bank demo --actor agent --output json
   # ok
   ```

2. Copy the data dir. In the copy, open `clio.db` and flip one character inside the `ciphertext_b64` value of the stored `items.content_ciphertext` envelope (keeping base64 validity so the envelope still parses; this breaks AEAD authentication).

3. On the tampered copy:

   ```
   CLIO_DATA_DIR=/tmp/repro-copy target/debug/clio remember "write probe after corruption" \
     --category task_spec --bank demo --actor agent --output json
   {"code":"factor_unavailable","message":"factor_unavailable: content decryption failed","ok":false}  # exit 1
   ```

4. Control: the same `remember` command against the untouched copy succeeds (`ok: true`, exit 0).

Also reproduced in-process: with a file-backed database opened under a fresh key store, `store` for a new item fails with `factor_unavailable: no DEK for subject `<another subject>`' while an old sealed row is unreadable.

## Expected result

A write whose own inputs are valid should succeed (or report a targeted, self-explanatory failure). An unreadable neighbor row should at most degrade that item's novelty contribution (or skip it with a warning), not fail every write in the bank. Direct reads of the unreadable item (`clio get <id>`) correctly still report `forbidden: content decryption failed`; the listing tool (`clio inspect`) already skips unreadable rows.

## Actual result

Any create against the bank exits 1 with `{"code":"factor_unavailable","message":"factor_unavailable: content decryption failed","ok":false}`. A data dir with a single corrupted (or key-mismatched) row becomes write-hostile for the whole bank.

## Impact

One damaged or key-orphaned row blocks all ingestion into the affected bank, which is worse than the read side (listing still works, single reads still report the row's own error). No data loss occurs, but recovery requires repairing or removing the unreadable row first.

## Notes

- Error surfaced from the store decrypt layer (`clio-store` KMS decrypt maps AEAD authentication failure to `ErrorCode::Forbidden`, message `content decryption failed`), wrapped as `factor_unavailable` by the admission factor path (see `clio-admission` novelty scoring / `clio-mcp` write tools).
- The behavior is present on the current master build (`make compile`, `cargo test --workspace` green apart from this scenario).
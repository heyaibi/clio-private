## Summary

`masked_clone` masks a JSON value when the key that holds it looks like a secret, but it leaves that key in the output unchanged. A JSON object whose key is itself secret-shaped is therefore republished verbatim, even though the routine recognized it as secret and masked the value next to it.

## Observed

Masking a document like

```json
{"entity": "Ada", "sk-live-LEAKEDKEY99": "x"}
```

produces a preview that still contains the key:

```json
{"entity": "Ada", "sk-live-LEAKEDKEY99": "****UE88"}
```

The value is masked; the key is not.

## Expected

A key the masker has already decided is secret should not be echoed verbatim. Either the key should be replaced with a masked placeholder as well, or the entry dropped.

## Evidence

- `crates/clio-config/src/secret.rs:71-95` — `mask_value` computes `secret` from `path_is_secret(&child_path) || path_is_secret(key)`, and when true replaces only `*child`. The map key is never touched.
- `crates/clio-config/src/secret.rs:107-111` — `masked_clone` delegates to `mask_value`.
- `crates/clio-write/src/telemetry.rs:77-92` — `redact_preview` builds the diagnostic `snapshot` and `diagnostic` previews with `masked_clone`, so this reaches the `VerifyEvent` and `AdmissionEvent` payloads written to stderr.

Reproduction (public entry point, the JSON masking helper directly):

```rust
let document = serde_json::json!({"entity": "Ada", "sk-live-LEAKEDKEY99": "x"});
let rendered = serde_json::to_string(&masked_clone(&document)).unwrap();
assert!(!rendered.contains("sk-live-LEAKEDKEY99"));
```

This assertion fails today: the rendered string still contains the key. The same shape was observed in a `verify_fail` event's `preview.snapshot` during a rejected-store test.

## Impact

Any diagnostic preview of a JSON object whose key is secret-shaped leaks the key. This is the write-path telemetry and diagnostic surface, so a caller who stores a secret in a key name — rather than a value — gets it written to stderr logs in clear.

Severity depends on how callers populate keys; most store secrets in values, where masking works today. The exposure is a leak of the key, not of the value.

## Cause

`mask_value` replaces the value under a secret-looking key but never rewrites the key itself.

## Proposed fix

In `mask_value`, when `secret` is true, also replace the map key with a masked placeholder, or drop the entry entirely. This needs an owner decision because `masked_clone` is shared: the audit and history read views use it and must keep their structured result intact, so dropping entries there could change a view contract.

Found incidentally while adding an unrelated regression test, and not fixed here: the shared masker is outside that task's scope and the fix touches every consumer of `masked_clone`.

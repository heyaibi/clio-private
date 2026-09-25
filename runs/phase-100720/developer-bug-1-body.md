## Summary

The reserved top-level CLI surfaces that parse flags with the lenient `parse_flags` extractor ignore unknown flags. `clio status --bogus`, `clio ops diagnose --bogus`, and `clio mcp schema-export --bogus` all run normally and exit 0. The shared hand-rolled parser (`crates/clio-lib/src/cli_args.rs`) rejects unknown flags with a usage error (exit 2), and `clio status` itself documents exit 2 for usage errors, so behavior differs by surface.

## Reproduction

```
cargo build --locked --bin clio
./target/debug/clio status --backend sqlite --db sqlite::memory: --bogus; echo $?
./target/debug/clio status --backend sqlite --db sqlite::memory: -x; echo $?
./target/debug/clio ops diagnose --backend sqlite --db sqlite::memory: --bogus; echo $?
./target/debug/clio mcp schema-export --bogus; echo $?
```

Actual (sanitized):

```
clio status: healthy
...
0
clio status: healthy
...
0
0
{"catalog_hash":"fnv1a64:...","format":"am_tool_schema_pack",...}
0
```

## Expected

Each invocation should fail closed with a usage error and exit code 2, the same as `clio recall q --bogus` does (`unknown flag `--bogus``), or at minimum reject the unknown flag instead of ignoring it.

## Actual

Unknown flags are silently stored or skipped and the command proceeds with defaults. Relevant code: `crates/clio-lib/src/main.rs:148-160` (`parse_flags` accepts any `--name` and skips tokens that do not start with `--`); `crates/clio-lib/src/status_cli.rs:113-121` (only known keys are read); the same extractor is used at `crates/clio-lib/src/ops_cli.rs:57`, `crates/clio-lib/src/mcp_cli.rs:47`, `crates/clio-lib/src/compose_cli.rs:49`, and `crates/clio-lib/src/retention_cli.rs:39`.

## Impact

A typo or unsupported flag on a health, ops, compose, mcp, or retention command is silently accepted and the command runs with defaults. Scripts and agents cannot tell a malformed invocation from a valid one, which is the opposite of the shared parser's fail-closed contract and contradicts `clio status`'s documented "2 usage" exit code.

## Notes

Found incidentally while working on CLI output flag handling; not fixed because it is outside that task's scope. A fix needs a per-surface known-flag list (or routing these surfaces through `cli_args::parse`), which is a design change beyond the incidental report.

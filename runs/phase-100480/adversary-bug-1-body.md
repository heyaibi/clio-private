### Summary
The CLI argument parser in `crates/clio-lib/src/cli_args.rs` does not recognize the standard POSIX `--` end-of-options delimiter and treats any token starting with `-` (or `--`) as a flag. As a result, attempting to use `--` to delimit options from positional arguments fails with `unknown flag '--'`, and positional arguments starting with a hyphen (such as markdown lists, bullet points, or negative numbers) cannot be supplied.

Found incidentally during benchmark adapter review; was not fixed as it is outside the current task scope.

### Steps to Reproduce
1. Attempt to pass `--` before a positional argument:
   ```bash
   cargo run -q -- remember --category output_constraint --bank test --actor user --output json -- "- note"
   ```
2. Or attempt to pass a string starting with `-` directly:
   ```bash
   cargo run -q -- remember "- note" --category output_constraint --bank test --actor user --output json
   ```
3. Or attempt to recall a string starting with `-`:
   ```bash
   cargo run -q -- recall "- query" --output json
   ```

### Expected Behavior
- When `--` is encountered, flag parsing should terminate and all subsequent tokens should be appended to `positionals`.
- Tokens following `--` (even if starting with `-`) should be treated as positional arguments.

### Actual Behavior
- Passing `--` produces:
  ```json
  {"code":"usage","message":"unknown flag `--`","ok":false}
  ```
- Passing a hyphen-prefixed positional directly produces:
  ```json
  {"code":"usage","message":"unknown flag `- note`","ok":false}
  ```

### Evidence
In `crates/clio-lib/src/cli_args.rs`:
```rust
        let Some(body) = token.strip_prefix("--") else {
            if token.starts_with('-') && token != "-" {
                return Err(unknown_flag(&token, spec));
            }
            parsed.positionals.push(token);
            continue;
        };
```
When `token == "--"`, `token.strip_prefix("--")` yields `""`. The name lookup fails against `spec.bool_flags()` and `spec.value_flags()`, and the parser invokes `unknown_flag("--", spec)`, returning exit code 2.
Furthermore, line 123 rejects any token where `token.starts_with('-') && token != "-"` as an unknown flag, providing no mechanism to pass hyphenated text.

### Impact
CLI users, scripts, and adapters cannot store or recall propositions or queries beginning with `-` (such as markdown bullet lists or diff excerpts) through the CLI.

### Proposed Fix
In `crates/clio-lib/src/cli_args.rs`:
1. Check if `token == "--"`. If so, append `tokens[index..]` directly to `parsed.positionals` and break out of the parsing loop.
2. In `split_leading_globals`, also stop splitting when `--` is encountered.

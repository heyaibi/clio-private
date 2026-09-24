# Proposal: support Command Code as a pipeline harness

Status: draft. Date: 2026-09-24. Scope: harness only. No stage or pipeline changes.

Note: on implementation, move this file to implemented/ with its implementation record.

## Problem

The runner invokes four harnesses: `opencode`, `agy`, `cursor`, and `hermes`. Command Code (https://commandcode.ai/) is installed and authenticated on this host, but no stage can select it. The operator wants it as an option, with custom providers staying exclusive to Opencode.

## Proposal

Accept a fifth harness CLI for Command Code, invoked under its own binary, using its native model catalog only. Opencode provider and model aliases keep applying to the opencode CLI only. Improve or replace this proposal if your local and external validation finds a safer or more reliable fix.

## Example

Entries use native Command Code ids:

- `cmd:deepseek/deepseek-v4-flash@high`
- `cmd:z-ai/glm-5.3-flash@high`
- `cmd:gpt-5.5@high`

Stage frontmatter:

```yaml
harness: ['opencode:go/deepseek-v4.1-flash@max', 'cmd:deepseek/deepseek-v4-flash@high', 'agy:gemini-3.8-flash-high']
harness_names:
  'opencode:go/deepseek-v4.1-flash@max': "OpenCode CLI (Go . Deepseek V4.1 Flash Max)"
  'cmd:deepseek/deepseek-v4-flash@high': "Command Code (Deepseek V4 Flash High)"
  'agy:gemini-3.8-flash-high': "Antigravity CLI (Gemini 3.8 Flash High)"
```

Resulting command:

```bash
cmd --trust --yolo -m deepseek/deepseek-v4-flash --effort high "<2-line task pointer>"
```

## Hypothesis (non-binding)

Treat Command Code like the existing interactive harnesses: one new CLI id, one command mapping, one static catalog check, and the same signal, rotation, and ledger contract unchanged.

This document states the problem and the safety properties only. It deliberately prescribes no implementation. The implementer owns the design after validation below.

## What the implementer must validate locally

Do not trust this proposal on where things live. Read the code first and confirm or correct each point.

- Find every place that enumerates harness CLIs, including the known-CLI set, the invoke mapping, the self-test binary and catalog checks, the live-probe shapes, and the idle-reminder eligibility set. Confirm what a fifth CLI must touch so validation stays strict.
- Find the Command Code binary name. Confirm the harness id matches the installed `cmd` binary and lookup resolves to it.
- Find how the runner passes the task pointer, polls the run log for the nonce-bearing signal, and closes the session. Confirm whether Command Code stages should use the interactive form (`cmd "message"` with trust and permission flags) rather than headless `-p`, which exits on its own.
- Find how Opencode provider aliases (`go`, `together`) and model aliases resolve. Confirm they stay scoped to `cli == "opencode"` so a `cmd` entry can never inherit them.
- Find how effort levels are validated. Confirm which `@effort` values Command Code accepts, since current stages use `@high` and `@max` and the docs describe effort as model-dependent.
- Find how the idle reminder decides eligibility. Confirm Command Code only qualifies when invoked with permissions auto-approved, and stays excluded otherwise like `cursor` and `hermes`.
- Read `runner.md`, `instruction.md`, the pipeline harness comment, and one stage frontmatter (`harness` plus `harness_names`) before changing anything. Confirm `preference.md` is operator-owned and must not be edited.

## What the implementer must validate externally

Search first. Do not invent CLI behavior.

- Search Command Code docs for the CLI reference, headless mode, BYOK providers, and available models. Confirm the interactive start shape, `-m/--model`, `--effort`, `--yolo`, `--trust`, `--skip-onboarding`, `-p/--print`, `--list-models`, and exit codes.
- Search for how unknown model ids behave. Confirm they are rejected before the run rather than failing later.
- Search for how BYOK custom providers are declared and named. Confirm native catalog ids versus custom `provider/model` ids, and why stages should carry native ids only when custom providers are Opencode-only.

## Safety properties

- The harness id is `cmd` and invokes the `cmd` binary.
- Opencode provider and model aliases never apply to `cmd` entries.
- Stages using `cmd` name native Command Code catalog models only. No BYOK custom provider ids appear in stage files.
- An unknown `cmd` model or an unsupported `--effort` fails as a config error before any harness starts.
- The per-invocation nonce, signal scan, rotation-slot consumption, ledger task pointer, and `ATTEMPT AUTHORITY` rules apply to `cmd` exactly as they do today.
- The agent-facing idle reminder is sent to `cmd` only when its invocation auto-approves permissions. It is never typed into an approval dialog.
- Static checks use `cmd --list-models` with no inference spend. Any live probe uses headless `-p` with a one-word reply and never opens an interactive session.

## Acceptance

- Add an automated check that a `cmd` harness id validates, resolves its binary, and rejects an unknown model and an unsupported effort without spend.
- Add a manual check with a stubbed `cmd`: a finished-but-unsignalled attempt advances only via `--mark-done`, and a failed attempt retries the same harness without consuming rotation.
- Run the existing gates unchanged: `--self-test`, `--dry-run`, and the worker check. State what was verified locally and externally, and list anything that could not be verified.

## Open questions

- Which stages should list `cmd` first: one rotation slot on developer, or every stage at once?
- Does `cmd` accept `@max`, or should `cmd` stage entries stay at `@high` and below?
- Should live stages use interactive `cmd` with `--trust --yolo`, or headless `-p --yolo` with `--max-turns`?

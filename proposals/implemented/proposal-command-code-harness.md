# Proposal: support Command Code as a pipeline harness

Status: implemented (2026-09-24). Scope: harness only. No stage or pipeline changes.

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

---

# Implementation record

## Local validation and reproduction

Places that enumerate harness CLIs (all confirmed by reading the code, not assumed
from the proposal):

- `KNOWN_CLIS` gates stage frontmatter in `load_stage`; a fifth id is required there
  before any pipeline can name it.
- `Run.invoke` holds the per-CLI command mapping (a `raise Fail("no command mapping")`
  else-branch).
- `self_test` holds three per-CLI enumerations: the binary map, the model-catalog
  branches (`agy models`, `opencode models`, hermes skipped), and the live-probe
  command shapes.
- `REMINDER_CLIS` decides idle-reminder eligibility, and the reminder is only ever
  typed when the CLI runs with permissions auto-approved.
- `parse_harness` (grammar), the nonce, signal scan, rotation, ledger, and
  `ATTEMPT AUTHORITY` paths are CLI-agnostic and needed no change.

Confirmed against the running CLI on this host (darwin, `cmd` 1.65.0):

- The binary is `cmd`, on PATH at `/Users/aiuser/.volta/bin/cmd`; `shutil.which("cmd")`
  resolves it. The id `cmd` therefore names the installed binary. (On Windows the
  alias is `cmdc`; this harness is Unix-only.)
- `cmd "message"` starts an interactive session seeded with the pointer, which matches
  the runner's contract (the runner polls the run log and closes the session). Headless
  `-p` ends when the turn ends, so it would drop the signal mid-stage; the interactive
  form is the correct mapping.
- Provider and model aliases were already gated on `cli == "opencode"`, so a `cmd`
  entry cannot inherit `go`/`together` or the registry-specific model spellings.
- Effort is model-dependent: the CLI accepts `low`, `medium`, `high`, `xhigh`, `max`,
  and rejects `none`, `minimal`, and `ultra` outright (`Unknown effort "ultra".
  Supported: high, max.`). A level the catalog does not give a model is refused too
  (`gpt-5.5 --effort max` -> `Unknown effort "max". Supported: low, medium, high, xhigh.`).
- Model ids are matched case-insensitively: `zai-org/GLM-5.3` and `zai-org/glm-5.3`
  both resolve, while `cmd --list-models` prints the lowercase spelling.
- An unknown model and an unsupported effort are both refused before any inference,
  with exit 1 and no output, in the interactive form as well as with `-p` (measured
  0.66-0.69 s, no session, no spend).

Reproduction before the change (the unmodified runner from `HEAD`, temp fixture with a
`cmd` stage, `--dry-run`):

```
{"state": "config_error",
 "error": ".../stage.md: unknown harness cli in 'cmd:deepseek/deepseek-v4-flash@high'"}
```

After the change the same fixture renders: `dry-run ok: pipeline validates, all steps
render`. The new validation gate was reproduced on a fixture naming
`cmd:bogus/not-a-real-model@high`: `--self-test` reports
`[False] cmd:bogus/not-a-real-model@high model listed: Error: unknown model
"bogus/not-a-real-model".`, and a direct `Run.invoke` on the real CLI returns
`cmd rejected model 'bogus/not-a-real-model' with effort 'high': Error: unknown model
"bogus/not-a-real-model".` with no run log and no session written.

## Design

- **One new CLI id, one command mapping.** `cmd` joins `KNOWN_CLIS`;
  `cmd_launch()` builds `cmd --trust --yolo --skip-onboarding -m <model>
  [--effort <effort>] <pointer>`. The pointer stays last: it is the positional initial
  message (`-i`-style flags swallow following tokens, as with agy).
- **Interactive, not headless.** The runner's contract is one attached session per
  step, closed by the runner after the signal; `-p` exits on its own and would drop the
  signal whenever an agent pauses. `--trust` skips the project trust prompt, `--yolo`
  auto-approves permissions (the stages mandate unattended tool use), and
  `--skip-onboarding` is for automated runs.
- **Idle reminder enabled.** `cmd` joins `REMINDER_CLIS` because `--yolo` auto-approves
  permissions, so the reminder can never be typed into an approval dialog. The
  prompt-tail skip and the never-a-signal text are unchanged.
- **Two spend-free catalog checks, no hardcoded catalog.** `cmd_catalog_ids()` parses
  `cmd --list-models` (model rows only; the header, the `Docs:` footer, and the
  "(headless only)" decision models are excluded) and matches case-insensitively.
  `cmd_probe_problem()` resolves one `(model, effort)` pair with `cmd -p --no-session`
  and `CMD_LOCAL_ONLY=1` forced: a resolved pair is then refused at the transport, so
  the probe sends nothing, starts no session, and costs nothing, while a rejected pair
  prints the CLI's own rejection. Both are cached per pair.
- **Config error before the harness starts.** `--self-test` checks each declared cmd
  model and effort with those two mechanisms, and `Run.invoke` repeats the pair probe
  before launching, so an unknown model or an unsupported effort fails as `Fail`
  (exit 2, `config_error`) with the CLI's own reason instead of surfacing later as a
  missing run log. The pre-invocation probe fails open on unrecognisable output (a
  reworded refusal, a timeout): the step proceeds and the CLI's own pre-inference
  rejection remains the backstop, so no spend and no partial run is possible either
  way.
- **Native catalog ids only.** Stage entries carry native ids (`cmd:deepseek/deepseek-v4-flash@high`);
  `cmd:auto` is not accepted (it would make model identity host-dependent), BYOK custom
  provider ids stay out of stage files, and opencode's aliases never apply. Catalog ids
  containing a colon cannot be expressed by the harness-id grammar and are unusable.
- **Nothing else changed.** Nonce, signal scan (including the console mirror), rotation
  slots, ledger task pointers, and `ATTEMPT AUTHORITY` apply to `cmd` unchanged.

## External validation

- CLI reference (flags, `cmd "message"`, `-m/--model`, `--effort`, `--yolo`, `--trust`,
  `--skip-onboarding`, `--max-turns` semantics): https://commandcode.ai/docs/reference/cli
- Headless mode (`-p` exits on its own, exit codes 0/1/3-10/130, `--no-session`,
  `--output-format`, one-word probes never open a TUI):
  https://commandcode.ai/docs/headless
- Model catalog, exact ids, and per-model efforts:
  https://commandcode.ai/docs/reference/cli/models
- BYOK custom providers and their `provider/model` ids (`providers.json`, `reasoningEfforts`,
  local-only mode refusing gateway models):
  https://commandcode.ai/docs/byok
- The same documents ship with the installed CLI as its bundled knowledge reference
  (`command-code/dist/bundled/command-code-knowledge/reference/`); the local probes
  above were treated as the behavioural source of truth where the two could differ.

## Resolved choices

- **Interactive form.** Headless `-p --yolo --max-turns` is not used for live stages:
  it exits when the turn ends, which would drop the signal, and it leaves no session for
  the operator to watch or nudge.
- **Effort.** `@max` is valid only for models that declare it; `cmd` stage entries must
  use a level the model lists. The runner does not carry an effort table: it asks the
  installed CLI, so the check tracks catalog changes.
- **Which stages list `cmd`.** Left to the operator at implementation time: that change
  touched no stage or pipeline file. The operator then had the stage harness lists
  synced to `preference.md` (their source of truth): `cmd:deepseek/deepseek-v4-flash@max`
  joins remediator and finalize, `cmd:deepseek/deepseek-v4.1-flash@max` joins the
  approver, and developer and adversary are unchanged. That sync's gates are recorded
  under Verification below.
- **Reminder on, never typed into a dialog.** `--yolo` is the reason; the existing
  prompt-tail guard still applies.
- **`auto` model rejected.** Unlike opencode and cursor, a `cmd` entry must name a
  catalog model, so rotation and the ledger keep naming one real model per attempt.

## Verification

- `python3 -m py_compile private/clio-private/harness/runner.py private/clio-private/harness/check-cmd-harness.py` — passed (clean under `-W error::SyntaxWarning`).
- `runner.py --self-test --pipeline .../default.yaml` — passed, 125 checks. The cmd block reports the binary at `/Users/aiuser/.volta/bin/cmd`, `cmd catalog: model list readable: 81 ids`, the parser fixture, the launch shape, the opencode-only alias scoping, the reminder rule, the live rejection of an unknown model, of an unknown level, and of an effort a model does not support, and the successful resolution of a supported pair. The pre-existing opencode catalog checks still report "catalog unavailable" on this host and remain skipped, as before.
- `runner.py --dry-run --pipeline .../default.yaml --input phase_number=100060 --input phase_file=...` — passed. The full `--dry-run --show-prompts` output is byte-identical to the unmodified `HEAD` runner (833 lines, 80,546 bytes), so the existing pipeline is unchanged.
- `runner.py --dry-run` on a temp fixture whose stage declares `cmd:deepseek/deepseek-v4-flash@high` — passed; the unmodified runner from `HEAD` fails the same fixture with `unknown harness cli`.
- `runner.py --self-test --live` on a temp fixture declaring `cmd:stealth/space-bunny-alpha@high` (a free catalog model) — passed, including `live probe: SELFTEST_OK`, which exercises the headless `-p` probe shape end to end at no cost.
- `runner.py --fuzz 100` — passed.
- `runner.py --autoexit-test` — passed, all 6 cases.
- `check-workers.py` — passed (4 workers).
- `check-retry-authority.py` — passed (hermetic missing-signal and interrupt scenarios).
- `check-cmd-harness.py` (new) — passed: pre-session rejection with no session argv, missing-signal retry on the same slot with rotation {developer: 1} unchanged after the failure and exactly one slot consumed on success, nonce round-trip into the ledger signal, pointer naming the task file, and a finished-but-unsignalled attempt advancing only via `--mark-done`.
- `gitsync.py --self-test` and `github_issues.py --self-test` — passed.
- Live CLI checks (spend-free): `cmd --list-models`; local-only pair probes for a valid pair, an unknown model, an unknown level, and a level the model does not support; an interactive `cmd --trust --yolo --skip-onboarding -m stealth/space-bunny-alpha --effort high "<message>"` session under a pty, which confirmed the launch shape, the seeded initial message, the applied effort, and `permission bypass on`.
- Live end-to-end run through `Run.invoke` with a real `cmd` session (free catalog model, temp fixture, runner under a pty): the runner attached in `pty` mode, the agent appended its signal with the instruction's log path, and the runner read `S0_DONE b08f898b` from the run log with the matching per-invocation nonce (`log_done: true`), then closed the session. This is the production path for one step: launch mapping, pointer handoff, console capture, log signal, and session close.
- After the `preference.md` stage sync: `runner.py --dry-run` renders all five steps with the new lists; `runner.py --self-test` passes 129 checks (up from 125 — each new cmd id adds a binary and a catalog check), including `cmd:deepseek/deepseek-v4-flash@max` and `cmd:deepseek/deepseek-v4.1-flash@max` resolving against the live catalog with no spend; `check-workers.py` passes. Rendered prompt sizes are unchanged (developer 11982 B, adversary 24349 B, remediator 21900 B, approver 10055 B, finalize 10921 B), because `{{harness}}` resolves to the first slot, which no step changed. The durable rotation counters are unaffected by the sync: this checkout has no counter file for its pipeline path, so it starts a fresh cycle at slot 0, while any checkout that owns one resumes mid-cycle with the new list lengths (remediator 17 -> cmd, approver 16 -> bunny, finalize 15 -> cmd).

Not verified: a full pipeline routing loop driven by real `cmd` models (the loop itself is CLI-agnostic and pinned by `check-cmd-harness.py` and `--fuzz`), a live `cmd` stage under the driver's tmux session, non-macOS hosts, and behaviour on a Windows host, where the CLI binary is `cmdc` and this harness is not built to run. The interactive form requires a terminal: the CLI refuses `Interactive mode requires a TTY terminal` when stdio is a pipe, which is the same constraint the other TUI harnesses have and is why every step runs attached in the operator's terminal.

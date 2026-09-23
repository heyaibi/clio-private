# Pipeline runner (`runner.py`)

The runner executes a stage pipeline: it renders each step's stage file by binding its placeholders, invokes the step's harness CLI attached in the operator's terminal, reads the step's final-line signal from its run log, and routes to the next step. Start with `instruction.md` for the operator workflow; this file is the reference for the runner itself.

## Commands

```bash
python3 private/clio-private/harness/runner.py --pipeline private/clio-private/harness/pipelines/default.yaml --input phase_number=100060 --input phase_file=private/clio-private/roadmap/phase-100060.md --dry-run
python3 private/clio-private/harness/runner.py --pipeline private/clio-private/harness/pipelines/default.yaml --input phase_number=100060 --input phase_file=private/clio-private/roadmap/phase-100060.md
python3 private/clio-private/harness/runner.py --pipeline private/clio-private/harness/pipelines/default.yaml --input phase_number=100060 --input phase_file=private/clio-private/roadmap/phase-100060.md --self-test
python3 private/clio-private/harness/runner.py --pipeline private/clio-private/harness/pipelines/default.yaml --input phase_number=100060 --input phase_file=private/clio-private/roadmap/phase-100060.md --resume
python3 private/clio-private/harness/runner.py --pipeline private/clio-private/harness/pipelines/default.yaml --input phase_number=100060 --input phase_file=private/clio-private/roadmap/phase-100060.md --from-step remediator
python3 private/clio-private/harness/runner.py --pipeline private/clio-private/harness/pipelines/default.yaml --input phase_number=100060 --input phase_file=private/clio-private/roadmap/phase-100060.md --mark-done remediator REMEDIATOR_DONE
python3 private/clio-private/harness/runner.py --pipeline private/clio-private/harness/pipelines/default.yaml --input phase_number=100060 --input phase_file=private/clio-private/roadmap/phase-100060.md --fresh
python3 private/clio-private/harness/runner.py --pipeline private/clio-private/harness/pipelines/default.yaml --reset-rotation
python3 private/clio-private/harness/runner.py --fuzz 50
python3 private/clio-private/harness/runner.py --autoexit-test
```

`--dry-run` validates everything and prints rendered-prompt sizes without invoking any harness (`--show-prompts` also prints full prompts). `--self-test` runs static harness checks with no inference spend (`--live` adds one-word inference probes, which spend). `--mark-done STEP SIGNAL` records STEP as finished with SIGNAL (for work that is done but whose run log never got the bare signal line) and advances `resume.json` to the routed target without invoking any harness; verify the work first, then `--resume` continues. `--fuzz N` runs N randomized router property trials in temp dirs. `--autoexit-test` runs scripted fake-harness checks of the auto-exit logic. `--fresh` archives the existing run dir to `<run_dir>.prev-<timestamp>` and starts over. `--reset-rotation` deletes the pipeline's rotation file and exits. `--pipeline` is always required. Run from the repo root: the repo root is the process working directory and `run_dir` resolves against it.

Exit codes: 0 completed, 1 terminal non-complete (rejected/blocked), 2 config error (machine-readable JSON on stdout in all cases), 130 operator Ctrl-C.

## Harness identifiers

Each stage file declares `harness:` as one identifier or a list of them. Format: `<CLI>:<Provider>/<Model>[@<Effort>]`, where provider and effort are optional. Examples: `opencode:together/glm-5.3-flash@high`, `opencode:go/deepseek-v4.1-flash@high`, `agy:gemini-3.8-flash-high`, `opencode:openrouter/deepseek-v4.1-flash@max`.

Known CLIs: `opencode`, `agy`, `cursor`, `hermes`. A present but unknown `@effort` is a config error; known efforts are none, minimal, low, medium, high, xhigh, max, ultra. Full (unaliased) identifiers work identically: anything not in the alias tables resolves to itself, so both styles can be mixed.

Provider aliases (opencode CLI only): `go` always means the installed `opencode-go` provider, `together` always means `togetherai`. Model aliases are keyed by resolved provider, because each registry names the same model its own way: on `togetherai`, `glm-5.3-flash` expands to `zai-org/GLM-5.3-Flash` and `deepseek-v4.1-flash` expands to `deepseek-ai/DeepSeek-V4.1-Flash`; on `openrouter`, `deepseek-v4.1-flash` expands to `deepseek/deepseek-v4.1-flash`; on `opencode-go` the bare slugs are already full. Unmapped models pass through untouched, and aliases apply to the opencode CLI only.

How each CLI is invoked (all attached in the foreground with inherited stdio; the harness receives a 2-line pointer to its task file, never prompt text): `agy --dangerously-skip-permissions --model <model> [--effort <effort>] -i <pointer>`; `opencode run --auto [-m <provider/model[#variant]>] <pointer>` (v2 headless; output streams to the pane, which the driver pipe-panes into the session log); `agent [--model <model>] <pointer>` for cursor; `hermes [--usage-file <file>] chat --query-file <taskfile> [--provider <p> -m <m>] [--reasoning <effort>]` for hermes (usage files only for hermes). The runner polls the step's run log and closes the session about 15 s after the final signal lands. A nonzero harness exit fails the step only when the run log carries no valid final signal; a missing or empty log always fails.

A list of identifiers means round-robin: each invocation of that step uses the next entry, wrapping around. Counters persist across runs in `private/clio-private/runs/.harness-rotation-<pipeline>-<hash>.json` (one file per pipeline file, keyed by pipeline path), so consecutive runs keep alternating. Rotation slots are consumed only after a successful invoke, so a crash between render and invoke retries the same harness. `--fresh` does not reset rotation.

Current steps and harnesses: developer (implement) rotates `opencode:together/glm-5.3-flash@high` and `opencode:go/deepseek-v4.1-flash@high`; adversary rotates `agy:gemini-3.8-flash-high` and `opencode:openrouter/deepseek-v4.1-flash@max`; remediator rotates `opencode:go/deepseek-v4.1-flash@high` and `opencode:together/glm-5.3-flash@high`; approver rotates `opencode:together/glm-5.3-flash@max` and `opencode:openrouter/deepseek-v4.1-flash@max`; finalize rotates `opencode:together/glm-5.3-flash@high` and `opencode:go/deepseek-v4.1-flash@high`.

Each stage file also declares `harness_names:` mapping every harness id to its display name, which is what `{{harness}}` renders to in prompts and what lands in Attribution rows and the ledger. Anything unmapped falls back to the raw id.

## Pipeline files

`pipelines/default.yaml` holds the whole workflow: `version` (must be 1), `run_dir` (a format template, currently `private/clio-private/runs/phase-{phase:06d}`), `inputs` (defaults or `{required: true}` markers; `--input k=v` overrides, `phase_number` and `max_remedy_rounds` parse as ints), `start`, `ends`, and `steps`. Each step names a `stage` file, a `record_as` label, `bindings`, and exactly one of `when` (signal-to-target routing map) or `end` (a terminal state from `ends`). Optional keys: `require_file`, `skip_when_empty`, `snapshot` (exactly `from`/`to`), `max_rounds` with `on_exhausted`.

Binding values are format strings over inputs plus run builtins (`phase`, `run_id`, `run_dir`, `agent`, `round`, `rounds`), `{output: <step>}` (that step's last output text), `{task: <step>}` (that step's rendered stage text), `{join: [...]}` with optional `sep`, or `{prev_output: true}` (the output of whatever step routed here). `{{harness}}` is runner-provided per invocation and must be neither declared in the stage's `placeholders` nor bound in the pipeline.

Validation is strict: unknown keys; start, edge targets, `skip_when_empty`/`on_exhausted`, and binding source steps that resolve nowhere; non-positive `max_rounds`; a step with neither or both of `when`/`end`; end states outside `ends`; unbound or over-bound placeholders; body tokens outside placeholders plus `{{harness}}`; missing stage files; unknown harness CLIs or malformed harness ids.

## Signals and routing

Signal matching is a prefix match scanned bottom-up over the last 10 non-empty run-log lines: the line equals a `when` key or starts with the key plus a space or colon. One leading ISO-8601 timestamp plus any `| ... |` journal prefixes are stripped before matching, and a `{"signal": ..., "nonce": ...}` JSON line counts the same as its bare form. Every invocation carries a fresh random nonce (appended to the task file); non-`*_BLOCKED*` signal lines must carry it as a separate token, so a mid-run echo of the bare signal word neither closes the session nor routes the pipeline. A signal printed only in chat never counts toward the log match, but under a terminal the runner also captures the harness console to `<step>-task-r<N>.tui.log` and a console-only signal still routes (marked `signal_via: mirror`). If the log stops growing with no signal for 5 minutes the runner prints the exact `printf ... >> <log>` recovery line to stderr and keeps waiting. Any signal whose first token ends in `BLOCKED` ends the run as blocked from any step. End steps (no `when`) accept a `*_DONE` / `*_APPROVED` / `*_REJECTED`-style first token the same way. A matched edge into an already-visited target caps at the current step's `max_rounds` and then ends with `on_exhausted`.

After the signal, `require_file` is verified before routing: for the findings report the runner parses the JSON and checks its `findings` key, otherwise it checks the file is non-empty. With `skip_when_empty`, an empty artifact routes to the skip target instead. `snapshot` copies run-dir `from` to `to` before the step unless the target already exists. Conventions that must not change silently: `agent` is the step id, and finalize is attributed Developer but logs to `finalize.log`.

## Run state

Each run dir holds `<step>-task-r<N>.md` prompts with matching `<step>-task-r<N>.log` run logs, `<step>-resume-r<N>.md` resume prompts, `resume.json`, `ledger.json`, `run.json`, and the step artifacts (`findings.json`, `findings.original.json`). `resume.json` (outputs, visits, harness use, transcript, events, current step) is saved before every invocation and after every routing decision; it is deleted on a clean finish but kept after Ctrl-C, step failure, or a blocked ending so the same command resumes. A finished non-blocked run refuses to rerun (use `--fresh`); a blocked run drops its stale `run.json` marker and resumes. `--from-step S` resumes at S after proving every dominator predecessor of S has a ledger entry, and inherits the previous step from the last event that routed into S.

`ledger.json` records per-step completion proofs (signal, harness, visits, output hash, artifact hashes, git HEAD). On resume every entry is re-proven: outputs and artifacts must hash identically (files a later step intentionally rewrites via a snapshot `from` are exempt), and later steps moving git HEAD fail the check. The resumed current step is exempt from the output pin since its saved output is the interrupted attempt.

## Verify

`--dry-run`, `--self-test`, and `--fuzz` create nothing in the repo. `--self-test` checks harness binaries and model slugs statically (plus signal parsing, the opencode TUI command shape, harness display-name coverage, alias expansion, and rotation persistence with a stub harness in a temp dir). `--fuzz` asserts router properties over random graphs: terminal states are terminal, every routed edge matches the taken signal, exhaustion respects `max_rounds`, and consecutive events chain step-to-step.

## Worker contract (birth-die)

Stage files stay lean orchestrators; execution detail lives in `harness/workers/*.md`, which the runner never loads. Rules: stages reference workers by exact relative path; every referenced file must exist; every worker defines its per-spawn slots under `## You own` and ends with `## Report back`; workers never signal, touch the index, run full gates, or spawn subworkers (depth cap is main -> worker). Static check (dry-run does not cover workers/): `python3 private/clio-private/harness/check-workers.py`. Run it after any stage/worker edit.

Baseline 2026-09-21 (dry-run, phase 100060): developer 6649 B, adversary 12542 B, remediator 12023 B, approver 4390 B, finalize 3559 B. Re-capture after stage edits when claiming context savings.

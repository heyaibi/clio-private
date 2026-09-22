# Foreground harnesses

One harness at a time, attached in the operator's terminal. No tmux, no pipes.

Proposal: drop `--attach` entirely. It joins a detached session the operator
never wanted — with the harness in the foreground from the start, there is
nothing to attach to. The flag, `attach()`, session fields, and tune-in docs go.

Pass the 2-line file pointer (`TASK_POINTER`), never prompt text.

- agy: `agy --dangerously-skip-permissions --model <model> -i <pointer>`
- cursor: `agent [--model <model>] <pointer>` (never `-p`)
- hermes: `hermes chat --query-file <taskfile> --provider <p> -m <m>`
- opencode: `opencode --auto --prompt <pointer> [-m <provider/model>]` (full TUI, not `run`)

## opencode variant gap

The root `opencode` TUI command has no `--variant` flag (upstream anomalyco/opencode
#7354 / #37925, still open as of Sep 2026), so a stage's reasoning effort
(`...@high` in the harness spec) cannot be passed on the TUI command line.
Workaround in the runner: when the opencode harness carries an effort, it
injects a temporary agent (`am_pipeline_stage`) with the model and variant via
the `OPENCODE_CONFIG_CONTENT` env var and launches with `--agent am_pipeline_stage`
(spike-proven on opencode 1.18.31: the session runs at the injected variant).
Simplify back to a plain `--variant <effort>` flag once opencode ships root
`--variant`. Docs here must be updated again when that happens.

Sessions close themselves ~15 s after the final signal lands in the run log
(`autoexit.md`); quitting earlier is always fine; Ctrl-C kills the step and
rerunning the same command resumes.

## Note

- Display a big decorated artistic ascii banner announcing start of new harness.

## Runner changes

1. `invoke()`: spawn attached with inherited stdio (`Popen`); poll the run log and close the session ~15 s after the final signal lands (`autoexit.md`).
2. Signal: read it back from the step's `LOG_PATH` file (`script -qec` fallback only if a log proves unreliable).
3. Nonzero exit fails the step only when the run log carries no valid final signal; missing or empty log always fails. Keep signal/exit contract, ledger, resume.

## Docs

`instruction.md`: run the command, watch it work, Ctrl-C kills the step, same command resumes.

## Verify

`--self-test`, `--fuzz`, one `--dry-run`, one live two-step run.

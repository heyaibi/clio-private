---
name: am_finalize
description: Clio finalize stage - close-out duty after remedy approval
role: developer
harness: ['opencode:together/glm-5.3-flash@high', 'opencode:go/deepseek-v4.1-flash@high']
harness_names:
  'opencode:together/glm-5.3-flash@high': "OpenCode CLI (Together . GLM-5.3 Flash High)"
  'opencode:go/deepseek-v4.1-flash@high': "OpenCode CLI (Go . Deepseek V4.1 Flash High)"
placeholders:
  REMEDY_APPROVER_AGENT_OUTPUT: Final approver verdict and message.
  LOG_PATH: Absolute path of this invocation's run log (beside the task file).
---

You are the Developer agent for the Clio project, on finalize duty.
The remedy approver approved all findings, as recorded below. You did not
re-open the work; you confirm and close out. The same hard rules from your
Developer role apply (no drive-by refactors, 450-line limit, AGENTS.md
headers, coverage gates, roadmap isolation, no migrations), except you must
stage, commit, and push as ordered below. Do everything yourself; spawn no
workers - commit/push must stay single-owner to avoid split-brain.

## Task

Your remedy was approved. Stage all files in both repos (main + nested
`private/clio-private`), including `private/clio-private/runs/` folder
contents, write a commit message per repo, create the commits, and push both
to GitHub. Here's the message from Remedy Approver agent.

=====

{{REMEDY_APPROVER_AGENT_OUTPUT}}

## Sync before publishing (mandatory)

The phase began on a synced base, but a remote can move while you work. After
you have committed both repos and immediately before you push, run this from
the repo root:

    python3 private/clio-private/harness/gitsync.py --root . --mode push

It fetches `clio` and `private/clio-private`, fast-forwards or merges any new
remote commits (never rebasing, force-pushing, resetting, or discarding
work), and confirms each push will fast-forward. If it merges remote commits
into your work, run `make check` again before pushing, since the base changed.

- Exit 0: safe to push both repos.
- Exit 1: a real conflict remains. Resolve it yourself: open the conflicted
  files the JSON names, edit them to the correct combined result, `git add`
  them, and complete the merge with `git commit --no-edit`. Then run the
  sync check again. Never `git rebase`, `git reset --hard`, or push with
  `--force`. If you cannot resolve it confidently, leave the merge state,
  quote the printed evidence, and end with
  `FINALIZE_BLOCKED: <one-line reason>`.

If a push is still rejected after the check (a remote moved in the last
instant), stop and signal `FINALIZE_BLOCKED`; never retry with `--force`.

## Close-out

- Confirm every Attribution row the earlier stages recorded is present and
  well-formed; add yourself with {{harness}} if your row is missing.
  Table contract, stated once here: Status is pending (not run), done,
  blocked, rejected (sent back for another round), or approved; Round
  counts invocations and matches `<step>-task-r<N>.log`; harness order
  lives only in the stage frontmatter `harness:` lists. Rejected approver
  rounds leave no row (the approver touches nothing on REJECT); the run
  transcript is the full record.
- Run `make check` once and confirm it passes.
- In the active `private/clio-private/roadmap/phase-*.md` file, change `- [ ] Required approval is obtained (downstream pipeline step).` to `- [x] Required approval is obtained (downstream pipeline step).` Include that change in the same commit.
- This stage order is the authorization. Do not ask the operator for separate per-command git approvals. Automatically select commit-all with a fixed accurate message (the previously chosen option): if the staged scope is broader than one file, write the broader message covering all staged work.
- Stage all files in both repos, including `private/clio-private/runs/` folder contents (e.g. `git add -A` in the main repo, then `cd private/clio-private && git add -A` in the nested private repo); do not exclude pipeline-internal `runs/` paths.
- Confirm `git status` in both repos shows only intended working-tree changes, including the staged `runs/` changes.
- Write a clear commit message describing the change.
- Create the commit.
- Run the sync check above; only if it exits 0, push both repos to GitHub
  and confirm each push succeeds.

## Run log

Log timestamped entries to {{LOG_PATH}} as you work (fresh file for this
invocation, beside your task file): attribution check, final `make check` result, file
list of the change. Never write secrets or tokens.

## Finish

Summarize the close-out and quote the final `make check` result. The FINAL
line of your reply must be exactly one of:

- `FINALIZE_DONE`
- `FINALIZE_BLOCKED: <one-line reason>`

Write that same signal as the very last line of your run log ({{LOG_PATH}}),
on its own line, with no timestamp prefix and nothing after it; the pipeline
matches that final log line against the exact signals above. Do it with a
tool call as your final action: `printf '%s %s\n' 'FINALIZE_DONE' '<nonce
from the Signal nonce section at the end of your task file>' >>
{{LOG_PATH}}` (or your full `FINALIZE_BLOCKED: ...` line instead, which
needs no nonce). A chat
summary alone never counts. The "timestamped
entries" rule applies to every other log line. The pipeline parses that log
line, and nothing after the signal is read.

**This is mandatory.** A run that ends without that signal line halts the pipeline with `missing expected signal`. Never end your turn, stop early, or leave a background worker running before the signal is written. If you delegated to a worker, wait for it to finish, then write the signal as your final action.

# Proposal: split the harness engine from Clio's private operation and open-source the engine

Status: draft. Date: 2026-09-24. Scope: `harness/` only. No stage, worker, or roadmap
changes. No behavior change to a running phase.

Note: on implementation, move this file to `implemented/` with its implementation record.

This file lives in the private repo on purpose. A root `proposals/` would put private
paths, phase numbers, and requirement text into the public checkout, which AGENTS.md
forbids. The engine that ships publicly is the only artifact that crosses the line.

## Problem

The `harness/` directory mixes two things with different audiences:

- A **reusable pipeline engine** — a deterministic runner that renders stage files,
  launches coding-agent CLIs attached, reads their final-line signals, routes between
  stages, rotates harnesses, and keeps an auditable ledger. This is generic: nothing in
  it is specific to Clio, phases, or memory.
- **Clio's private operation** — the stages, workers, preference list, phase selection,
  shared reservation board, roadmap, and run state. This is Clio's process, not a product.

Because the two live in one tree, the engine cannot be published, reused, or reviewed on
its own, and every Clio path is baked into code that would otherwise be generic.

## Goal

Separate the generic engine (open source) from Clio's private configuration and policy
(stays private), with a small, documented seam between them. Clio keeps running exactly
as today; the engine becomes a standalone project others can adopt.

## Current inventory

Evidence: `wc -l` and keyword counts over `harness/` (2026-09-24).

| Artifact | Lines | Clio-coupled? | Target layer |
|---|---|---|---|
| `runner.py` | 5006 | Yes — phase/reservation/gitsync references throughout | Engine + hooks |
| `check-workers.py`, `check-retry-authority.py`, `check-cmd-harness.py`, `check-harness-availability.py` | 48/128/315/268 | Only in fixtures | Engine |
| `github_issues.py` | 753 | Yes — Clio's issue tracker | Clio private |
| `gitsync.py` | 1124 | Yes — Clio's dual-checkout publication | Clio private (v1) |
| `phase_reservations.py` | 1334 | Yes — shared phase board | Clio private |
| `next_phase.py` | 614 | Yes — roadmap selection | Clio private |
| `phase_policy.py` | 16 | Yes — parked-phase floor | Clio private |
| `phase-driver.sh` | — | Yes — cron/tmux/notify unattended mode | Clio private |
| `pipelines/default.yaml` | 142 | Yes — Clio phase workflow | Clio private (ship generic example instead) |
| `stages/01..05*.md` | 637 | Yes — Clio roles, `make check`, 450-line Rust rule, roadmap isolation | Clio private |
| `workers/*.md` | 99 | Yes — same | Clio private |
| `preference.md`, `instruction.md`, `dev-note.md`, `runner.md` | 571 | Yes — operator-owned Clio docs | Clio private |
| `roadmap/`, `baseline/`, `coordination/`, `runs/`, `case-studies/`, `gaps/`, `issue-tracker/`, `docs/adr/`, `scripts/`, `proposals/` | — | Yes | Clio private |

The one hard number that drives the work: `runner.py` has ~89 `reservation` references,
~40 `phase_number`, ~30 `phase_file`, ~13 `roadmap`, and ~12 `gitsync`, and it imports
`gitsync`, `phase_policy`, and `phase_reservations` at module load. The engine cannot be
extracted until those imports are inverted.

## Product name

Company **agentmemoir**; products **clio** (advanced agentic memory) and **jotter**
(markdown memory, Obsidian vaults). The engine's product name is decided: **`glide`**.

The runner's job is to move a phase from stage to stage smoothly and hands-off: it
launches each harness, waits for the signal, and routes to the next step with no operator
friction. "Glide" names that continuous, unattended motion.

- CLI: `glide run --pipeline …`
- Public repo: https://github.com/agentmemoir/glide

Note: `glide` is a common word already used by unrelated software (Glide apps, Glide.js,
the Android Glide image loader). The engine is namespaced under `agentmemoir/`; if a
package-registry name is taken at publish time, ship under the org's scope rather than
rename.

## Proposal

Three layers, three repos.

1. **Engine (public).** The pipeline runtime, harness CLI adapters, and the pipeline/
   stage/worker *formats*, plus a minimal set of example pipelines. It knows nothing about
   phases, roadmaps, reservations, publication, GitHub, or Clio.
2. **Hooks (public, small and documented).** The engine's only seams for host policy: a
   closed set of named lifecycle points, declared in versioned config and run as commands.
   Fail-closed: a declared hook that is missing or errors stops the run at the point it
   gates, never proceeds silently. See Hook model.
3. **Clio layer (private).** Clio's stages, workers, `default.yaml`, `preference.md`,
   `instruction.md`, `dev-note.md`, `runner.md`, the phase/reservation/sync/GitHub helpers,
   its hook declarations, and the hook scripts themselves.

Target public layout (`glide`):

```
glide/
  LICENSE                     # Apache-2.0, to match clio
  README.md
  pyproject.toml              # console_scripts: glide = glide.cli:main
  src/glide/
    __main__.py               # python -m glide
    cli.py                    # arg parsing / main
    pipeline.py               # yaml load + strict validation
    stage.py                  # frontmatter + placeholder binding
    signals.py                # signal parse/match
    router.py                 # drive() loop
    attach.py                 # pty/plain attach + idle reminder
    ledger.py                 # ledger, resume, crash journal
    rotation.py               # round-robin counters
    hooks.py                  # lifecycle points + hook runner + recording
    harness/
      base.py
      opencode.py  agy.py  cursor.py  hermes.py  cmd.py
      aliases.py              # provider/model/effort tables
    checks.py                 # self-test, fuzz, autoexit-test
  examples/
    hello-pipeline.yaml
    stages/…  workers/…
  docs/
    pipeline-format.md  stage-format.md  worker-contract.md
    harnesses.md  hooks.md
  tests/                      # the four hermetic checks, genericized
```

Clio's private side is thin: hook commands at the lifecycle points carry the host policy —
sync + claim before the run, the canonical `phase_file` check, the per-step
reservation/publication gate, and `github_issues.py` exposed as a helper. `default.yaml`,
stages, and workers stay where they are; only their `harness/` sibling code changes.

### Local layout (nested repos)

The engine is a nested (sub-sub) repo, cloned in place so it is editable from a checkout of
`clio` without hopping folders:

```
clio/                             # public repo (github.com/heyaibi/clio)
  private/                        # git-ignored in clio (global excludes file)
    clio-private/                 # private repo; ignores /glide
      glide/                      # github.com/agentmemoir/glide  <- this engine
```

- `glide` is a plain nested clone, not a submodule: its own repo, remote, and history.
- Two ignore rules keep the tree safe: clio ignores `private/` (global excludes), and
  clio-private ignores `/glide` (committed `.gitignore`). Neither parent can stage glide
  or leak its contents.
- Goal met: one editor root (`clio/`) reaches the engine at
  `private/clio-private/glide/`, with the same view on the Mac and the server.
- Consequence and its fix: a plain clone is not pinned by git, so the engine is pinned by
  `harness/glide.lock` and converged by the three-repo sync (see Dependency pinning and
  three-repo sync below).

### Rejected alternatives

- **B. Split by directory, single repo, mixed license.** No real separation; the engine
  still carries Clio paths and cannot be adopted cleanly.
- **C. Fork the runner into a second copy.** Two engines diverge; every fix lands twice.

## Packaging: standalone CLI and importable module

`glide` must run two ways from one codebase:

- **Installed executable** — `pipx install` / `pip install` gives a `glide` command through
  a `console_scripts` entry point, for anyone using it standalone.
- **Module / script** — `python3 -m glide …`, or the file directly, for embedding and for
  callers that want no install step.

Both are one `pyproject.toml` plus `__main__.py`; there is no second code path.

Clio consumes the **module form from the pinned clone**, not an installed copy:

```bash
PYTHONPATH=private/clio-private/glide/src \
  python3 -m glide --pipeline private/clio-private/harness/pipelines/default.yaml …
```

- A pip-installed glide lives in `site-packages`, where git cannot see it, so the version
  that runs would no longer be the commit `glide.lock` names — the exact drift the pin
  exists to prevent.
- A separate process keeps a glide crash or hang from taking down the cron driver, and
  matches today's `python3 …/runner.py` call shape.

Standalone users still get `glide` on `PATH`; that path is deliberately not the one Clio's
pipelines use.

## Hook model

The engine has no knowledge of Clio. Everything host-specific enters through hooks. The
rules below keep hooks from making a run non-reproducible or unsafe.

### Lifecycle points (closed set)

| point | when | failure effect |
|---|---|---|
| `pre_run` | once, before the first step | config error, run does not start |
| `pre_step` | before each step invocation | config error, that step does not run |
| `post_step` | after a step's accepted signal, before routing | blocks that step's completion |
| `post_run` | once, after the terminal state | recorded; never changes the outcome |
| `on_blocked` | on a blocked/rejected terminal state | recorded; never changes the outcome |
| `on_interrupt` | on Ctrl-C / signal | best-effort; can never change the exit code or the journal |

There is deliberately no open-ended set ("pre, post, interruption, blah"): adding a point is
an engine change, not config. `on_interrupt` carries the heaviest constraints — bounded
time, no writes to the run log, cannot swallow the signal or block exit — because the crash
journal and `--mark-done` already own recovery.

### Hooks are commands

Each hook is an external command, invoked with context passed through environment variables
(`GLIDE_RUN_DIR`, `GLIDE_STEP`, `GLIDE_PHASE`, `GLIDE_SIGNAL`, `GLIDE_TOOL`, …) and reading
nothing else. The exit code is the contract: `0` proceeds, nonzero fails at that point per
the table above. Hooks receive the run dir and may write evidence there; they never receive
the pipeline's secret values.

### Declared in git, overridable per host

Hook declarations live in the **versioned pipeline (or a versioned clio-private config)**,
so they are reviewed, diffed, and move with the pin — the same discipline as the stages.

A host may still need its own hooks without editing git (a server-only notify/claim step,
say). That is supported as an **override, not a source of truth**:

- an optional host-local file (XDG: `~/.config/agentmemoir/glide/hooks.toml`) may *select or
  replace* the hook for a point;
- the runner **records the effective hook set** — point, command, a hash of the command
  string, and its exit — into `run.json`/the ledger for every run;
- so a Mac/server difference is never silent: it shows up in the run's record.

The engine keeps no persisted state of its own. Any state a hook needs lives with its owner
— for Clio that is the versioned `coordination/state.json`, not a glide home-dir registry.

### Why not a global registry in the home dir

A host-local registry as the only declaration would make the same pinned commit behave
differently on two machines with no diff and no ledger entry — reintroducing in behavior the
drift we just removed in code. Declaring hooks in git keeps them reviewable; the override
exists for genuine per-host needs and is recorded so it stays visible.

## Dependency pinning and three-repo sync

Hard constraint: **no glue in the public repos.** `clio` and `glide` stay generic and
public-facing; every part of the machinery below lives in `clio-private`. This is what
makes the sync safe to own privately — the public repos never learn about each other.

### The pin

`private/clio-private/harness/glide.lock` (committed) is the single source of truth for
which engine version the pipeline runs:

```json
{
  "version": 1,
  "repo": "https://github.com/agentmemoir/glide",
  "commit": "<40-hex sha>",
  "tag": "v0.1.0"
}
```

The engine is the only artifact the current sync gate does not cover — it is ignored by
both parents, so git never sees it. This file closes that gap: the Mac and the server both
converge on `commit`, so the engine cannot drift silently. `commit` is authoritative; `tag`
is human context and is not used to resolve.

### Sync grows from two repos to three

`gitsync.sync_all(root, mode)` today syncs exactly `root` (clio) and
`private/clio-private` (`gitsync.py:310-316`), and the runner calls it in `preflight_sync`
before every fresh start (`runner.py:2710`). Add a third repo,
`private/clio-private/glide`, with **different semantics per repo**:

| repo | path | tracks | start-mode rule |
|---|---|---|---|
| clio | `.` | its own upstream | fast-forward or clean merge (unchanged) |
| clio-private | `private/clio-private` | its own upstream | fast-forward or clean merge (unchanged) |
| glide | `private/clio-private/glide` | **the pin** | fetch; must be clean; fast-forward to the pin when behind; fail when ahead, diverged, or missing |

Glide is never pushed from clio-private and never merged: it only moves forward to a commit
clio-private already names. The existing destination-overlap check (`gitsync.py:320-331`)
extends to glide, so private content still cannot reach a public remote.

### Modes

- `--mode start` — the pre-run sync gate. Enforces the pin: glide clean and at `commit`, or
  fast-forwardable to it. Any other state is a fail-closed config error naming the exact
  repair — no force, no reset, no discard, same discipline as today.
- `--mode check` (new, read-only) — report all three repos: local vs remote vs pin, and
  what would move. The doctor to run on a new machine.
- `--mode pin` (new) — re-pin: record glide's current HEAD into `glide.lock`, refusing when
  glide is dirty or its HEAD is not yet pushed to its own upstream. This is the one explicit
  action after working on the engine.
- `--mode push` / `--mode publish` — unchanged; clio + clio-private only. Glide publishes
  itself from its own repo.

### Bootstrap

Because `glide.lock` records both the URL and the commit, clio-private can **materialize**
glide when it is absent: if `private/clio-private/glide` is missing, `--mode start` clones
the recorded URL and checks out the pinned commit. That collapses the routine to your first
two steps, and is idempotent with a manual clone for anyone who prefers it.

```
git clone https://github.com/heyaibi/clio && cd clio
mkdir private && cd private && git clone https://github.com/heyaibi/clio-private
cd ..
python3 private/clio-private/harness/gitsync.py --root . --mode check   # doctor, all 3
python3 private/clio-private/harness/gitsync.py --root . --mode start   # converge all 3
```

### Why not a git submodule

A submodule would pin glide for free (the committed gitlink), but it conflicts with the
chosen layout: clio-private ignores `/glide`, and the routine is a plain clone. It also adds
detached-HEAD and update ceremony for no gain, since `glide.lock` plus the sync gate give
the same guarantee on top of the clone you already do.

## What the implementer must verify locally

Do not trust this inventory. Read the code and confirm or correct each point.

- Confirm the engine's true coupling surface by tracing every `phase_*`, `gitsync`,
  `reservation`, `roadmap`, and `github_issues` reference in `runner.py` and listing which
  are engine-generic (e.g. `run_dir` templating, input parsing) versus host policy.
- Confirm `run_dir`, docstrings, model aliases, and self-test fixtures contain no baked
  `private/clio-private` paths after genericization. Today `run_dir` defaults to a Clio
  path and the four checks mention `private/clio-private` in fixtures.
- Confirm the hook set is sufficient and minimal: which behaviors currently hardcoded in
  `runner.py` (sync gate, phase_file check, reservation heartbeat, completion evidence,
  publication receipt) can move behind the lifecycle points with no loss of fail-closed
  behavior, and that every hook that runs is recorded in the run state.
- Confirm both invocation forms work from the pinned clone — `python3 -m glide …` and the
  installed `glide` entry point — and that clio-private drives the clone, not a
  pip-installed copy.
- Confirm `--dry-run`, `--self-test`, `--fuzz`, `--autoexit-test`, and the four hermetic
  checks run against the **example** pipeline in the public repo with no repo state and no
  Clio files.
- Confirm a real Clio phase still completes end to end via the engine plus Clio's hooks:
  same routing, same ledger contents, same resume behavior, same exit codes.

## What the implementer must validate externally

Search first. Do not invent conventions.

- How comparable tools structure a host-policy seam as commands (git hooks, pre-commit,
  Claude Code hooks): which lifecycle set and recording convention keeps fail-closed
  semantics simplest, and how interrupt hooks are bounded so they cannot swallow a signal.
- Python packaging for a dual CLI/module tool: `pyproject.toml` layout, `console_scripts`
  entry point, `__main__.py`, and invoking a pinned clone without installing it.
- Precedent license and naming checks for a company-prefixed OSS release under
  agentmemoir; whether Apache-2.0 (clio's license) is the right default.

## Migration plan (staged, non-breaking)

1. **Engine in place, private.** Move the generic runtime into a package (e.g.
   `private/clio-private/harness/engine/`), invert the three imports into hooks, and write
   Clio's hook commands. Keep paths and behavior identical. Prove with `--self-test`,
   `--fuzz`, the four hermetic checks, and one real phase.
2. **Genericize and scrub.** Remove baked Clio paths from code, docstrings, and fixtures;
   add `examples/`; write the public `docs/`; run a leak scan (no `private/`, no roadmap
   text, no credentials, no phase numbers) in CI.
3. **Publish.** Stand up https://github.com/agentmemoir/glide (Apache-2.0) with the engine,
   examples, and docs.
4. **Clio runs the published engine** from the pinned clone at
   `private/clio-private/glide/` (module form or subprocess), never an installed copy.
   Clio's config and hook scripts stay private. One source of truth from here on.

`gitsync.py` stays private in v1. If a second adopter wants the dual-checkout publish
model, generalize it as an optional engine plugin later — do not force it now.

## Safety properties

- A running Clio phase behaves identically before and after each step; exit codes and
  ledger contents are unchanged.
- The public repo never contains a `private/` path, roadmap or requirement text, phase
  numbers, credentials, or run state. The leak scan is fail-closed.
- Hooks stay fail-closed: a missing or erroring hook stops the run at the point it gates,
  as a config error, never proceeds silently. An interrupt hook can never swallow the
  signal, block exit, or touch the crash journal.
- The engine that runs is the pinned clone, not an installed copy, so the code version is
  always the one `glide.lock` names.
- Every hook that actually ran is recorded in the run state, so a run stays reconstructible
  even when a host-local override changed the hooks.
- The private repo's secret boundary is unchanged: only engine code crosses, never data.

## Acceptance

- Public engine repo passes `self-test`, `fuzz`, `autoexit-test`, and the four hermetic
  checks against the example pipeline, with no Clio files present.
- A real Clio phase runs to completion through the engine + Clio's hooks, and a `--dry-run`
  matches today's output for the same inputs.
- Leak scan over the public repo finds no private paths, phase numbers, roadmap/requirement
  text, or credentials.
- Product name `glide` recorded; `pyproject`, console entry point, and README use it
  consistently.
- `glide run …` (entry point) and `python -m glide …` both work; clio-private drives the
  pinned clone.
- A run records its effective hook set (points + command hash + exit) in `run.json`/the
  ledger, so a host-local override is visible.

## Open questions

- Should `--mode start` auto-clone a missing `glide/` from the lock, or require the manual
  clone and only converge?
- Should the unattended `phase-driver.sh` mode ever be generalized and published, or is
  cron/tmux/notify too host-specific to ship?
- Where do the private hook scripts live — beside `harness/`, or under `harness/hooks/`?

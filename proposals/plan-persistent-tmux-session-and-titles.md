# Plan: persistent tmux session and phase/stage titles

Status: plan, not started. Date: 2026-09-26. Branch: `master`.
Scope: `private/clio-private/scripts/phase-driver.sh`, one new host script, one new tmux helper, one host pipeline `hooks:` block. **No change to glide.**

## Goal

1. The tmux session `development` stays alive across the whole line, so a television attached to it always has something to show.
2. The terminal titlebar shows what the line is doing, updated at phase level by the driver and at stage level by a glide hook.

## What I verified before writing this

Read the code and probed real tmux 3.7c on this machine. Facts, not assumptions:

- `new-window` has **no** `-x`/`-y` flags. Confirmed in the man page (`[-abdEkPS] [-c] [-e] [-F] [-n] [-t]`) and by running it: `command new-window: unknown flag -x`. The existing `new-session -x -y` trick cannot be reused for the phase window.
- A new window in an existing session **inherits the session's geometry** (100x30 session -> 100x30 window).
- `resize-window -t <session>:<window> -x W -y H` **works on a non-active window** and sets the size. This is the geometry mechanism.
- `window-size manual` + `default-size 164x48` did **not** give a new window 164x48 in my probe; it stayed at the session size. Do not rely on it. Use `resize-window`. (Probed at 164x48; the size is irrelevant to the result, which is that `default-size` was ignored.)
- **`window-size manual` does protect geometry.** I pinned the session to manual, then attached an 80x24 client, and both windows stayed at their size. This is a second, independent defence against the TV resizing the agent's pane.
- **A persistent session must be reconciled, not just created.** Found during implementation: because the session now outlives every phase, `ensure` returning early on an existing session left a stale window size in place forever. A session born at the old default kept it. Fixed with `tmux_session_reconcile`, which re-asserts the options and resizes the idle window on every tick.
- `set-titles` (default off) + `set-titles-string` set the client terminal title. `set-titles-string` expands formats.
- **The title reaches an attached client on its own.** I attached a real pty client, changed only `set-titles-string` while the pane was idle and silent, and the new title arrived in **0.6s**. No `refresh-client` needed.
- A literal title string works independently of which window is current. `#{window_name}` also works but follows the current window, so a literal is safer here.
- `automatic-rename` is turned **off for that window** when a name is given at creation with `-n`, or later with `rename-window`. Confirmed in the man page and by probe. So our names stick.
- `attach -r` is an alias for `-f read-only,ignore-size`. `ignore-size` means the TV's own dimensions do not resize the session's windows.
- A window whose command exits **closes the window**. With a persistent session, that is the phase-completion signal (today the whole session dies).
- `pipe-pane`, `send-keys`, `list-panes`, and `display-message` all take a target. Given only a session name they resolve to that session's **current** window, which becomes ambiguous the moment a second window exists. This is the main correctness trap in the whole change.

Two facts about the existing code that constrain the options below:

- `prune()` deletes only `session-*.log`. **`driver.log` is never pruned or rotated.** A `tail -F` on it is cheap, but the file grows forever.
- `check()` starts two Python self-tests and calls `hermes ... send --list` on every run. A repeating `--check` loop is **not** free: it spawns Python twice and hits the Hermes profile each cycle.

## Design

**Session `development` is permanent. Only the phase window comes and goes.**

- `idle` window, created once, shows a status view (see Q1).
- `phase` window, created per launch, runs `phase-driver.sh --session <N> <file>`. It closes by itself when that command exits, which is how completion is detected.
- The driver never calls `kill-session` on `development`. Only the operator does.

**Busy means "the phase window exists", not "the session exists".** An idle session must not block the line.

**Titles.**

- Driver sets phase-level titles: launch, completion, halt, and idle ticks.
- Stage-level titles come from a glide `pre_step` hook, which **already exists** and already passes the step name. No glide code change.

## Why no glide change

`glide/src/glide/router.py:121` already calls `run.hook("pre_step", step=current, attempt=..., harness=...)`; line 158 calls `post_step` with `step`, `signal`, `routed_to`.

`glide/src/glide/hookrun.py:105` maps context keys to environment variables as `GLIDE_<KEY>`, so the hook already receives `GLIDE_STEP`, `GLIDE_ATTEMPT`, `GLIDE_HARNESS`, `GLIDE_SIGNAL`, `GLIDE_ROUTED_TO`, `GLIDE_RUN_DIR`.

`glide/src/glide/hooks.py:47` defines the point set. `pre_step` is already there.

So stage titles are a **host pipeline `hooks:` block plus a host shell script**. glide stays byte-identical, which is what `glide/AGENTS.md` requires. This is better than the glide change I proposed earlier; I withdraw that.

## Work items

### 1. New file `scripts/phase-tmux.sh`, sourced by the driver

Holds every tmux call, so the driver grows by a few lines instead of ~80 and the tmux logic is readable in one place.

- `tmux_session_ensure` — create `development` with the `idle` window if `has-session` fails. Set `set-titles on`. Never kill it.
- `tmux_phase_window_open <n> <launch>` — `new-window -d -n phase`, then `resize-window` to `$TMUX_WIDTH`x`$TMUX_HEIGHT`, then `pipe-pane -o` **targeted at `development:phase`**.
- `tmux_phase_window_alive` — true when `development:phase` exists and its pane is not dead.
- `tmux_phase_window_close` — reclaim a dead-but-retained phase window. Never touches the session.
- `tmux_set_title <string>` — `set-option -t development set-titles-string <string>`, session-scoped, literal.

### 2. `phase-driver.sh` — retarget every session-scoped tmux call

| Line | Today | Change |
|---|---|---|
| 270-279 | `tmux_busy` checks `has-session`, reclaims a dead session | check `development:phase`; reclaim only the phase window |
| 344-347 | dry-run `has-session` | check the phase window |
| 401-405 | `if tmux_busy` | same retarget |
| 410-420 | orphan = live PID, **no session** | orphan = live PID, **no phase window** |
| 525-529 | `new-session -d -s ... -x -y` | `ensure` session, then open the phase window; `pipe-pane` retargeted |
| 555-564 | `stop()` sends `C-c` to the session | send to `development:phase` |
| 566-573 | `wait_session_gone` | `wait_phase_window_gone` |
| 732 | `check()` geometry line | report phase window size, note the session is persistent |

Also add `CLIO_TMUX_SESSION` to the launch environment (line 502-514 block) so the glide hook can find the session, and list it in the header comment at lines 30-34.

### 3. `run_session` — set the terminal titles

`phase <N> running` at the top; `phase <N> done` on rc 0; `HALTED phase <N>` in the `*)` branch that writes the halt marker. Both before `exit`, so the title outlives the window closing.

### 4. Idle title on each cron tick

In `_drive`, when there is no phase window and nothing is launching, set `idle - waiting`. This is what a TV shows between phases.

### 5. New file `scripts/pipeline/tmux_title.sh` — the stage-title hook

Reads `GLIDE_STEP`, `GLIDE_ROUTED_TO`, `CLIO_TMUX_SESSION`. Maps the step id (`developer`, `adversary`, `remediator`, `approver`, `finalize`) to a readable label. Renames the phase window and sets the title string.

**Always exits 0.** `pre_step` and `post_step` are `GATING` (`glide/src/glide/hooks.py:47`). A nonzero exit **stops the run**. A failed `tmux rename-window` must never halt a phase. This is the single most important safety property in the change.

### 6. `workflow/pipelines/default.yaml` — add a `hooks:` block

```yaml
hooks:
  pre_step: ["bash", "private/clio-private/scripts/pipeline/tmux_title.sh"]
```

Host file, private repo. glide untouched.

## Risks

1. **Gating hook.** Covered above: exit 0 unconditionally.
2. **Missed target.** Any `tmux` call left pointing at the bare session name acts on whichever window the TV is viewing. Grep every `tmux` call at the end; each needs an explicit window target.
3. **Geometry.** `window-size` defaults to `latest`, so an attached client can resize the phase window, and glide copies the pane size into each harness pty. Mitigations in Q3.

   **Known limitation, found after implementation and deliberately not acted on.** The
   `window-size manual` set in `tmux_session_reconcile` also stops a *deliberate* operator
   resize from reaching the pane: with it on, resizing an attached terminal does not
   resize the windows, so a CLI in the phase window will not re-lay-out. This is the
   intended trade for Q3 (a display must not change the agent's geometry), but it also
   removes the resize behaviour an interactive user would expect.

   Two facts recorded for whoever picks this up later, both measured and neither
   acted on: `window-size` can be set **per window**, not only per session
   (`tmux set-option -w -t <session>:<window> window-size manual` sticks to that window
   alone, and other windows keep inheriting the global value), and `attach -r` implies
   `ignore-size`, which may be enough on its own to stop a display resizing the session.
   If so, the per-window form would give both: the phase window pinned, everything else
   still following the client. **Not implemented, not tested as a pair.**
4. **Idle window death.** If the idle command exits and it is the last window, the session dies. Whatever Q1 picks must not exit on a missing file.
5. **Self-test rewrite.** `wait_session_gone` and the orphan test both assume the session dies with the phase. Expected, but it is the bulk of the test work.
6. **Driver file size.** 751 lines now. The 450-line ceiling in the host `AGENTS.md` is written for Rust files, so bash is not covered. The `phase-tmux.sh` split is for readability, not to satisfy a limit.

---

# Open decisions

Each question below lists avenues with two pros and two cons each. **My recommendation is on each one, but every avenue is viable.**

## Q1. What does the idle window show?

### Avenue A — `tail -F` the driver log

- Pro: shows the real reason for the last result; the log already records every decision, reservation, and halt.
- Pro: costs one `tail` process; no extra load on a machine that is running agents.
- Con: `driver.log` is **never pruned or rotated** (verified above), so a months-old tail target is a file nobody has bounded.
- Con: timestamps and log noise are hard to read from across a room, which is the actual TV use case.

### Avenue B — loop `phase-driver.sh --check` every 10s

- Pro: the output is already written for humans and answers "is the environment ready" directly.
- Pro: no new content to design; it is the same text an operator gets today.
- Con: **not free.** `check()` starts two Python self-tests and calls `hermes ... send --list` every cycle. Ten-second polling is real, repeated load.
- Con: `--check` reports environment readiness, not line progress. It would not tell a TV viewer that phase 100700 just finished.

### Avenue C — a dedicated idle status script

A small host script that prints a fixed block: last phase, last result, halted or not, time since last activity, next phase if known. Refreshes on a timer.

- Pro: built for distance reading, large type, no log noise.
- Pro: can show "next: phase 100701" so the TV answers "what happens next", which neither A nor B does.
- Con: a second source of truth. It reads the same marker files the driver writes, so it can disagree with the log if a marker is stale.
- Con: more code to write and keep correct than either tailing or looping an existing command.

**Recommendation: Avenue C**, with a `tail -F` of the last few log lines underneath it. It is the only option that shows progress, and progress is the point of a TV. If you want the smallest change, take A and accept the readability cost.

## Q2. How should a halt appear on screen?

### Avenue A — title carries `HALTED`, idle window stays a log tail

- Pro: one small change, entirely inside the title-setting code.
- Pro: the log stays readable, so you can still read *why* it halted right after the banner appears.
- Con: a terminal title is easy to miss on a TV. Many terminals and TV output modes hide the titlebar entirely, which would make the halt invisible.
- Con: the halt *reason* lives only in the log. The title can say `HALTED` but not `orphaned run pid 1234`.

### Avenue B — idle window switches to a large `HALTED` banner

- Pro: impossible to miss. It works even where the titlebar is hidden, which is the failure mode of A.
- Pro: can show the halt reason inline, read from the halt marker.
- Con: the idle window's content is now conditional, so the session has two modes and every reader of `tmux_title.sh` and the idle script has to know about both.
- Con: the log tail is gone exactly when you are most likely to want it. You get the banner, then you have to attach elsewhere to read the cause.

### Avenue C — both

- Pro: the banner guarantees visibility; the title guarantees it for anyone on a terminal that shows titles.
- Pro: keeps the log tail available below the banner, so the cause is one glance away.
- Con: two mechanisms to keep consistent. A bug that sets one and not the other produces a contradictory screen.
- Con: slightly more code than either alone, and the acceptance list grows to match.

**Recommendation: Avenue C.** A is cheapest and B is the only one that survives a hidden titlebar; a TV is exactly the place where you cannot assume the titlebar is visible. The consistency risk is small because both read the same halt marker.

## Q3. How is the agent's pane geometry protected from the TV?

This is the risk with real consequences: `runner.py` copies the pane size into each harness pty, so a TV that resizes the pane changes the agent's working environment mid-phase.

### Avenue A — document `tmux attach -t development -r` only

- Pro: zero code. `-r` already means `read-only,ignore-size`, so the TV cannot resize or type.
- Pro: read-only also stops accidental keystrokes reaching a live agent, which is a second benefit.
- Con: purely conventional. If anyone attaches without `-r`, nothing stops the resize.
- Con: does not protect the geometry on its own. It relies on every future attach remembering the flag.

### Avenue B — `set -w window-size manual` on the session at creation

- Pro: **verified working.** I pinned manual, attached an 80x24 client, and both windows held at 164x56.
- Pro: protects the geometry even against a plain attach, so it does not depend on operator discipline.
- Con: `manual` is session-wide, so a human who wants to resize their own terminal cannot. They must resize the window explicitly.
- Con: it is a session option, so it must be set at `ensure` time and survives only as long as the session does. A session created outside the driver will not have it.

### Avenue C — both A and B

- Pro: belt and braces. `-r` stops the TV doing damage; `manual` stops the resize even if the flag is forgotten.
- Pro: each covers the other's failure. Forget `-r` and geometry holds; override `manual` and `-r` still ignores size.
- Con: two things to document and two things to test, for a risk that one of them already covers.
- Con: `manual` makes interactive reattaching mildly annoying, which is the cost you pay for unattended safety.

### Avenue D — `default-size` on the session

- Pro: one option, and it is the documented way to set new-window size under `manual`.
- Pro: would apply to any window created later, not just the ones the driver opens.
- Con: **does not work as expected.** I tested `default-size 164x56` with `window-size manual` and the new window still came up at the session size. This avenue is refuted by my own probe.
- Con: even if it worked, it sets a default for new windows and says nothing about protecting the window that already exists.

**Recommendation: Avenue C (A + B).** B is the one that actually holds, and A costs nothing to keep. **Do not take D** — I would have proposed it if I had not tested it.

## Q4. Should the driver keep the tmux calls inline, or extract them?

### Avenue A — extract to `scripts/phase-tmux.sh`, sourced by the driver

- Pro: the driver grows by a few lines instead of ~80, and every retargeting decision sits in one readable block. Given that missing one target is the main correctness risk, one block is easier to audit.
- Pro: the tmux helpers become testable on their own, without running a whole phase.
- Con: two files to read to understand one behaviour, and the sourced file must be found by anyone who does not know it is there.
- Con: shell sourcing has no static checking. A typo in the helper fails at runtime, not at read time.

### Avenue B — keep everything inline in `phase-driver.sh`

- Pro: one file, one place to look. The driver is already the single home of this logic.
- Pro: no sourcing, no path resolution, no risk of a stale copy if the helper is ever copied instead of sourced.
- Con: the file reaches roughly 830 lines and mixes session lifecycle with coordination, notifications, and halting.
- Con: the retargeting audit (Risk 2) has to be done across a longer file, which is the most likely place for this change to go wrong.

**Recommendation: Avenue A.** The single-block audit argument is the deciding factor: the highest risk in this change is missing one window target, and one 80-line file is much easier to check than a 751-line one.

## Q5. How are stage titles derived from step ids?

### Avenue A — a `case` statement in the hook script mapping step id to label

- Pro: five ids, five labels. Trivial to read and to test exhaustively.
- Pro: no config file, no extra process, nothing to keep in sync.
- Con: adding a step to `default.yaml` means editing the script, and a new id would silently fall through to a default label.
- Con: the mapping is duplicated knowledge. The pipeline knows the step names; the script now repeats them.

### Avenue B — read labels from the stage files' `name:` frontmatter

The stages already declare `name: am_implement`, `am_adversarial_analysis`, and so on.

- Pro: no duplication. Rename a stage and the title follows with no script change.
- Pro: the label is the stage's own declared identity, so it cannot drift from the stage.
- Con: the frontmatter names are prefixed (`am_`), so titles would read `am_adversarial_analysis` unless the script strips the prefix, which is a rule of its own.
- Con: it couples the title to file parsing. A malformed or missing frontmatter degrades the title, where a `case` statement cannot.

### Avenue C — use the raw step id, untranslated

- Pro: zero mapping code and zero drift risk. The id is exactly what `router.py` passed.
- Pro: `adversary` and `remediator` are already readable, so translation buys little.
- Con: ids and stage names differ (`developer` vs `am_implement`), so the title vocabulary will not match the stage files.
- Con: if the pipeline is ever renamed to ids that are not plain words, the TV shows ids instead of meaning.

**Recommendation: Avenue A.** Five fixed ids in a versioned pipeline, and an exhaustive test for all five is worth more than removing five lines of duplication. Choose B only if you expect to rename steps often.

---

# Acceptance

Extend `driver_self_test` (`phase-driver.sh:575`) with:

- After a phase completes, the session **still exists** and the `idle` window is present.
- `idle` window is present before, during, and after a phase.
- The phase window exists while running and is gone after.
- A second `drive` while the phase window exists logs `running; skip`.
- A second `drive` with no phase window does **not** log `running; skip`.
- Title is `phase <N> running` during, `phase <N> done` after rc 0, `HALTED phase <N>` after failure.
- Phase window geometry is `$TMUX_WIDTH`x`$TMUX_HEIGHT`.
- Orphan detection fires when the **phase window** is killed with a live PID.
- `stop()` reaches the phase window.
- A halted line still refuses to launch.
- `tmux_title.sh` exits 0 when `tmux` is missing or the session does not exist.
- `tmux_title.sh` sets the expected title for each of the five step ids.

Manual check, real entry point, real state:

1. `bash private/clio-private/scripts/phase-driver.sh --self-test` passes.
2. Launch a real phase, attach from a second terminal with `tmux attach -t development -r`, and watch the title change at each stage without detaching.
3. Kill the phase window mid-phase; confirm the driver halts and says orphaned.
4. Confirm the session survives between phases and the idle window shows the status block.

# What I have not verified

- I have not tested `--dry-run` output, which prints a literal `tmux new-window` line and needs rewording.
- I have not tested whether the TV's terminal shows the titlebar at all. Q2 Avenue C exists precisely because I cannot assume it does.
- I have not measured the real cost of a 10s `--check` loop; I only established that it is non-zero.

## Resolved during implementation: does the CLI adapt to the pane?

Yes, and this closes the one assumption Risk 3 and Q3 rested on. The old comment
claimed `runner.py` copies the pane size into each harness pty. The code that
actually does it is glide's, not the old runner's:

- `glide/src/glide/ptysession.py:56` `set_winsize` reads `TIOCGWINSZ` from the
  operator's **stdin** and applies it to the freshly opened pty master.
- `glide/src/glide/ptysession.py:102` calls it at spawn.
- `glide/src/glide/ptysession.py:218` `install_winch` re-applies it on `SIGWINCH`,
  so a later resize is tracked too.
- `glide/src/glide/ptypump.py:112` re-applies it when the pump sees a resize.

So the chain is: tmux pane size -> the driver's stdin (the pane) -> the pty the
harness runs in. I verified it end to end by replaying that exact sequence inside
a real 164x56 pane:

```
  stdin (the tmux pane) reports : 164x56
  child pty gave the CLI         : 56 164 | TERM=tmux-256color | 164 | 56 |
```

`stty size` inside the child reports 56 rows by 164 columns, which is what a TUI
queries to lay itself out. A CLI in the phase window therefore adapts to 164x56.

**The corollary, and the reason the idle screen would have looked wrong.** If stdin
is not a terminal, `TIOCGWINSZ` raises `OSError` and `set_winsize` returns without
setting anything, so the pty keeps its default 24x80. I confirmed a pipe raises
`Errno 25 Inappropriate ioctl for device`. That is what happens when a phase runs
detached from any tty, and the CLI would silently render at 80x24 while the window
is 164x56. The persistent-session design removes this risk rather than leaving it
to chance: the phase always runs in a real pane.

# Decisions I need from you

1. **Q1** — idle status script (recommended) or plain log tail?
2. **Q2** — halt banner plus title (recommended), or title only?
3. **Q3** — accept A+B, or title-only simplicity with A alone?
4. **Q4** — extract `phase-tmux.sh` (recommended) or keep it inline?
5. **Q5** — `case` statement (recommended) or read stage frontmatter?

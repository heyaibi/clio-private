# Proposal: make remedy failure cheap, and make the loop legible

Status: draft. Date: 2026-09-26. Scope: pipeline, driver, `next_phase.py`, `runner.py`, stage files, plus one new read-only report. No change to the approver's standard. No change to product code.

Note: on implementation, move this file to `implemented/` with its implementation record.

This proposal is the umbrella for the phase-100606 postmortem. It supersedes
nothing and depends on nothing. One earlier proposal covers a single item in
detail and is referenced rather than duplicated: `proposal-remedy-round-memory.md`
(carry a remedy round's own evidence into the next round). That item is listed
here only so the set is complete.

## Problem

Phase 100606 took roughly twelve hours, needed manual intervention, failed at
least twice, and left a reservation that blocked a second machine. The work
itself was not unusually large. Comparing 51 completed phases on this machine,
the median phase is 1.47h, p90 is 2.11h, and the slowest phase ever recorded
is 3.91h. At roughly twelve hours, 100606 was about 8x the median and 3x the
worst phase in the project's history. Phase 100601 ran the same three-round
remedy shape in 1.97h total, with 0.57h of remediator time across its rounds.

Three separate defects stacked, and the incident needed all three.

**The cap is a cliff, not a limit.** When the approver exhausts `max_rounds`,
the pipeline ends in the `rejected` state. The driver treats any nonzero exit
that is not 3 as a stop and writes a halt marker, so the whole line stops. The
phase's reservation is retained, and per `dev-note.md` there is no automatic
expiry on a claim, so a second machine cannot take the phase over. Per the same
document a rejected phase is terminal and cannot resume automatically. A
converging run therefore converts into a halted line, a contested reservation,
and an operator session. On 100606 the cap was reached with rejections falling
14 to 7 to 4, which is convergence, and the mechanism responded by stopping
everything.

**The loop has no feedback.** The approver's verdict signal already carries the
unresolved finding ids: `REMEDY_REJECTED: F-02,F-06` in 100601,
`F-04, F-06` in 100080, `F-01` in 100320 and 100368. The finding totals sit in
`findings.original.json`, which the pipeline already snapshots as the remediator
step's `require_file` backup. Every input needed to compute per-round
convergence has been on disk for the life of the project. No report reads it.
This is why diagnosing 100606 required an operator to reconstruct a moved-aside
run directory by hand.

**The cost model is the wrong shape.** `run.json` records `duration_s` per
agent step. It does not record cron wait, halt dwell, or operator time. The
local driver log shows phase 100060 halting at 02:09:38 and the line refusing
to advance until 02:32:21, about 22 minutes of wall clock that appears nowhere
in any `run.json`. With a 10-minute cron interval, every manual fix costs up to
10 minutes of pure waiting before anything restarts. So the two numbers people
were comparing, "twelve hours" and "5.75h of remediator", are different
quantities, and the run evidence cannot be reconciled against the wall clock.

A fourth issue is smaller but corrupts analysis: the remediator stage declares
only two harnesses, and per-round model rotation was in effect until a recent
change. In all five multi-round phases in the local history the remediator used
a different model each round, and in two of them the approver also changed
mid-run. The recent change pins one harness per stage per run, which removes
the rotation, but the rotation file is namespaced by pipeline path and the
namespace changed with that commit, so the per-stage offsets restart. Model
assignment is therefore not comparable across the change boundary, and any
comparison of one model against another is currently unanswerable.

## Proposal

Six items, ordered by how much incident they would have prevented. The first
two are the ones that matter; the rest are cheap and remove a recurring class of
confusion.

### 1. A non-terminal cap exhaustion state

Add a distinct end state, `remedy_exhausted`, reached when the approver hits
`max_rounds` with findings still unresolved. It means "the approver's budget ran
out", which is a fact about the budget, not a verdict on the work, and should
not be recorded as `rejected`.

On reaching it, in order:

1. Write the remaining unresolved findings and their grounds to a durable file
   in the run directory. The approver already produces this verbatim in its
   verdict, including `file:line`.
2. Release the phase reservation, so another machine is not blocked by a claim
   no one is working on.
3. Do not write the halt marker. The line continues to the next phase. The cost
   of one phase needing more rounds should be that phase's cost, not a stopped
   line.
4. File an issue naming the phase and the unresolved findings, so the work is
   tracked instead of lost.

Raise the approver `max_rounds` from 3 to 5. This is the smaller half of the fix
and is worth doing, but it only moves the cliff; item 1 removes it.

**A trap in this design that the implementer must handle explicitly.** Phase
selection treats only six markers as done, and `state == "completed"` is one of
them; a brand-new end state is not on that list. If `remedy_exhausted` neither
halts the line nor counts as done, the driver will select the same phase again
on the very next 10-minute tick and re-run it in a loop, which is worse than
today's halt. The new state needs an explicit exclusion from automatic
selection, and the natural place is the selection path itself: a phase whose
`run.json` records `remedy_exhausted` is skipped until an operator acts. Decide
and record whether the operator action is a marker file, a
`--resume-exhausted` flag, or an explicit takeover. Whichever it is, a skipped
phase must be visible in `--dry-run` and in the audit output, never silently
passed over.

Then make exhaustion resumable on request: one command re-enters the approver
loop with the remaining findings as its input. This turns "rejected, deal with
it" into "paused, continue when you can", the same class of operation the runner
already has for `--mark-done`.

### 2. One read-only convergence and cost report

A script, not a pipeline change, that reads what is already on disk and prints
per phase: finding total, rejected count per round, whether the rejected set is
shrinking, the round count, and the wall-clock cost split into agent time versus
halt and wait time where the driver can supply it.

Every input already exists. `run.json` carries each step's signal and
`duration_s`; `findings.original.json` carries the totals; the driver log
carries launch, halt, and resume timestamps. This is the twenty lines whose
absence cost the 100606 investigation, and it is the item that would let an
operator see convergence from a notification instead of from a shell.

Two supporting changes, both small:

- Have the approver include the unresolved count in its verdict, for example
  `REMEDY_REJECTED: 4 (was 7) of 16: F-04,F-11`. It already knows this; it is
  deciding on those findings. This makes the report's answer arrive without
  anyone remembering to run it.
- Have the driver write a per-phase cost breakdown next to its existing finish
  notification: agent seconds by step, remedy rounds, and elapsed wall clock
  from launch to finish.

### 3. Record the wall clock, not only the agent time

Extend the run record so a phase's elapsed time is answerable without
reconstructing it from log timestamps: launch and finish timestamps, halt
dwell time, and the number of times the line was halted for that phase. This is
the difference between "the remediator took 5.75h" and "the phase took twelve
hours, of which two were the line waiting for a person". Both numbers are
useful; today only one is recorded and it is the one that does not explain the
incident.

### 4. Close the silent harness-swap hole left by pinning

The recent pinning change guarantees one harness per stage per run by reading
the saved plan at invocation time. One documented exception remains: the
recorded entry is re-decided from the rotation offset when the binary is no
longer available, and the rotation-offset fallback is a different model. On a
server where a provider credential can lapse, a step can therefore still change
model mid-run, which is the exact failure pinning exists to prevent. The strict
behavior is to refuse to start the step and report the missing CLI, rather than
silently substitute a different model. Decide and record which, but do not
leave the substitution silent.

### 5. Reuse a gate receipt when the code has not changed

Each approver round currently re-runs formatting, clippy, the full test suite,
and the Postgres path from scratch, even when the previous round was green and
the diff is unchanged. Carry the receipt forward when the recorded commit and
the gate inputs are identical, so a later round can cite it rather than spend
minutes reproducing it. The saving here is minutes, not hours, and it is listed
low deliberately.

### 6. Record why two plausible-looking changes were rejected

Two recommendations that arrived from the 100606 review must not be adopted, and
the reason should be written down so the question does not reopen every time a
phase repeats.

- Do not price remedy rounds as a function of unresolved finding count, for
  example `max(1h, 0.15h x findings)`. Measured over the 49 local phases with
  both fields present, the correlation between adversary finding count and
  remedy rounds is 0.09. Phase 100120 had 13 findings and one round; 100170 had
  2 findings and one round; 100601 had 6 findings and 3 rounds. The formula was
  fitted to a single outlier and contradicts every other observation.
- Do not re-split phases by surface area on the theory that smaller phases
  converge better. The correlation between phase file size and remedy rounds is
  0.07, and between phase file size and total hours it is 0.05. Phase 100606's
  phase file is 30KB, the 76th percentile, which is smaller than 100601 at 49KB
  and 100290 at 45KB, both of which finished in about two hours.

The durable conclusion from these two measurements is the one that matters: no
feature of a phase file predicts remedy rounds. The only reliable predictor
available is that a phase already repeated. That is an argument for item 1,
which makes a repeat survivable, and against guessing at phase size, which
addresses a cause that is not present in the data.

## Out of scope for this proposal

**Phase 100760 needs a decision from the operator, not a code change.** Its
goal is to resolve a disagreement between `docs/extraction-fidelity.md` and
production `verify_snapshot`, choose one rule deliberately, and align docs,
tests, and the trust assumption to it. The hard part is choosing the rule. That
is a judgement about trust semantics, and the four-stage pipeline is built for
implementing a stated specification and then checking it, not for making the
specification. The adversary role in particular has no clear target when the
deliverable is the decision itself. It is also small: one crate, seven Rust file
references, an estimated one to two days. The recommended handling is an
attended session with an operator and an agent, with the phase file retained and
marked complete rather than deleted, since the file is the record of the
decision and other phases refer back to it. That is an operator decision and
this proposal only records the reasoning.

**Do not change the approver's standard.** Rejecting a resolution whose prose
misstates the code is the system working correctly. Every item here makes
failure cheaper or evidence easier to reach. None of them makes the check more
lenient, and any implementation that reduces a rejection rate by relaxing
verification has missed the point.

## Hypothesis (non-binding)

Cap exhaustion is rare, so the cliff costs little in the common case and a great
deal in the rare one. A loop that cannot be seen from outside also costs little
until someone needs to explain it, at which point the only available method is
manual reconstruction from partially moved run state. Both costs fall on the
operator, and both are paid in the same incident.

## What the implementer must validate locally

Do not trust this proposal on where things live. Read the code first and confirm
or correct each point.

- Find every consumer of a run's terminal state: the pipeline `ends:` list, the
  driver's exit-code case, `next_phase.py`'s done test, the reservation
  completion path, and the audit and verbose output. Confirm the full set
  before adding a state, and confirm which of them would misbehave on an
  unrecognised value.
- Confirm the re-selection loop described in item 1 against the real selection
  path, and confirm the chosen skip mechanism cannot itself strand a phase
  permanently with no notification.
- Confirm what the approver's verdict actually contains on a rejection, and
  whether the unresolved count is available to it without a new computation.
- Confirm the totals in `findings.original.json` are the right denominator, and
  that they are written for every phase including ones with no adversary run.
- Confirm the driver's log has launch, halt, and resume timestamps sufficient to
  compute wall clock, and that they are not cleared or rotated within a phase's
  lifetime. Note the local log-retention setting before relying on this.
- Confirm whether a gate receipt can be keyed on something durable. The ledger
  already records `git_head` per step; establish whether that plus the gate
  inputs are enough to prove the receipt still applies, rather than assuming a
  commit hash is sufficient.
- Re-measure the correlations in item 6 on whatever data exists at implementation
  time, including any phases completed since this proposal was written. If a
  real predictor has appeared, record it rather than preserving these numbers
  uncritically.

## What the implementer must validate externally

Search first. Do not invent a pattern.

- Search for established handling of a bounded retry budget that runs out, and
  compare a non-terminal quarantine against a terminal stop for unattended
  pipelines. The question to answer is what the run should do next, not how to
  report exhaustion.
- Search for how unattended job runners resume or quarantine a job that hit a
  retry ceiling, and specifically whether an operator-visible skip marker is the
  normal answer.
- Search for guidance on whether a review loop should be able to re-verify a
  prior round's conclusion or must treat it as settled, since item 1 makes
  resumption routine.
- Search for established practice on reusing a verification receipt keyed on
  content identity, and what invalidates one. Do not design a cache from memory
  of similar systems.

## Safety properties

- The approver's bar does not move. No item may reduce a rejection by relaxing
  verification.
- Exhaustion never silently passes. A phase skipped by automatic selection must
  appear in the dry-run preview and the audit output.
- No exhausted phase is ever re-run automatically. Resumption is always an
  explicit operator action.
- A reservation is released only after the leftover findings are durably
  written, so a released claim never loses the only record of the open work.
- Releasing a reservation must not let a second machine pick up the same phase
  concurrently with the first. Confirm the reservation lifecycle still fences
  this after exhaustion, and that the skip mechanism and the reservation agree
  about who owns the phase.
- The report is read-only. It must not mutate run state, and it must be safe to
  run against a run in progress.
- No report output, notification, or issue body may contain a private path, a
  private phase number, private requirement text, or a run-log excerpt. The
  existing redaction rules in the stage files stay in force and are not weakened
  by anything here.
- Adding a verdict field must not break signal parsing. The runner matches the
  signal as a prefix and carries the remainder as context; confirm the new form
  parses and that existing recorded signals still read correctly.

## Acceptance

- Automated: a stubbed pipeline that exhausts an approver cap ends in the new
  state, writes the leftover findings, releases the reservation, does not write
  the halt marker, and is skipped by the next selection tick rather than
  re-launched.
- Automated: a phase skipped after exhaustion appears in `--dry-run` and in the
  audit output, and is not selected for launch.
- Automated: an explicit resume action re-enters the approver with the leftover
  findings, and the cap is not reset silently in a way that permits an unbounded
  loop.
- Automated: the new verdict form parses, and a recorded old-form signal still
  reads correctly.
- Automated: the report runs read-only against a synthetic run directory and
  against a run in progress, and produces the same numbers twice.
- Manual: exhaust a cap on a real phase, confirm the line continues to the next
  phase unprompted, confirm the leftover findings file exists and is readable,
  and confirm the finish notification carries the cost breakdown.
- Record, in the implementation record, the next real repeat phase's remedy
  rounds and wall clock next to the 100601 and 100606 numbers, so the effect is
  measured rather than asserted.

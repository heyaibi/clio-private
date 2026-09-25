# Proposal: escalate instead of loop — cheap failure and legible evidence

Status: draft. Date: 2026-09-26. Scope: pipeline, driver, `next_phase.py`, `runner.py`, one new read-only report, one new pre-flight check. No change to the approver's standard. No change to product code.

Note: on implementation, move this file to `implemented/` with its implementation record.

This is the umbrella proposal from the phase-100606 postmortem, revised after
the phase's own run records were read. Three earlier conclusions were wrong and
are corrected in the "Corrections" section below; an implementer should read
that section before designing anything.

A second proposal covers carrying a remedy round's own evidence into the next
round: `proposal-remedy-round-memory.md`. That item is listed here only so the
set is complete, and its priority is lower than it was when first written.

## Problem

Phase 100606 took roughly twelve hours, needed manual intervention, failed at
least twice, and left a reservation that blocked a second machine. Comparing 51
completed phases on this machine, the median is 1.47h, p90 is 2.11h, and the
slowest phase ever recorded is 3.91h. At roughly twelve hours, 100606 was about
8x the median and 3x the worst phase in the project's history.

### What the run records show

From `runs/phase-100606/run.json.rejected-round3`, the agent-time total is
7.84h. The approver's signals record the open set shrinking:

| Round | Open findings | Cleared | Remaining |
|---|---|---|---|
| 1 | 14 | — | F-02..F-08, F-10, F-11, F-13, F-15, F-16, NEW-01, NEW-02 |
| 2 | 7 | F-02, F-07, F-08, F-11, F-15, NEW-01, NEW-02 | F-03, F-04, F-05, F-06, F-10, F-13, F-16 |
| 3 | 4 | F-04, F-05, F-16 | F-03, F-06, F-10, F-13 |

The round-3 approver's own log states: "All seven previously rejected findings
are functionally resolved and I reproduced the decisive behaviors myself", and
rejects anyway. Its seven grounds classify as four prose or comment defects and
two functional defects, plus the F-06 report claim. The two functional grounds
are F-06 (`token: [REDACTED]` re-imports as `token: ****TED]`, a reproduced
non-idempotent masking bug) and F-13 (a reproduced push-cursor freeze). Both are
among the defects the operator handoff deliberately leaves open as requiring
design work rather than a surgical fix.

The finding that a third remedy round cleared — F-04, F-05, F-16 — was
doc-comment and lock-ordering work. The finding set that survived all three
rounds is the set requiring real design judgement.

### The three defects that actually stacked

**The surface was an order of magnitude larger than a normal phase, and nothing
checked.** The developer produced 120 modified plus 51 untracked files, 171 in
total, before the adversary ran. Phase 100601, which also took three rounds,
touched 8. The remediator then spent 1.88h, 1.70h and 2.17h re-deriving its
reasoning across that surface. Across 43 phases with both fields present,
developer time and remediator time correlate at r = 0.46. The size of the
change the developer made is the best available predictor of how expensive the
remedy loop becomes, and no gate in the pipeline looks at it.

**The cap is a cliff, and it converted a decision into a halt.** When the
approver exhausts `max_rounds` the run ends in `rejected`. The driver treats
any nonzero exit other than 3 as a stop and writes a halt marker, so the whole
line stops. The reservation is retained and, per `dev-note.md`, claims have no
automatic expiry, so a second machine cannot take over. A rejected phase is
terminal and cannot resume automatically. What the loop actually needed at
round 3 was a human decision about two hard defects; the mechanism instead
produced a stopped line, a contested claim, and a run that had to be
reconstructed by hand into a handoff document.

**The evidence needed to make that decision was never surfaced.** The verdict
signals already carry the open finding ids. `findings.original.json` already
carries the totals. The approver's log already contains `file:line` for every
defect, 25 distinct sites in round 3 alone. All of it was on disk. Assembling
it into a decision took an operator an evening and produced a document the
pipeline should have been able to write itself.

## Corrections to the first version of this proposal

Three conclusions in the earlier draft were wrong. They are recorded here so
they are not reintroduced.

**Do not raise the approver cap to 5.** The earlier draft proposed it on the
theory that the loop was converging and needed one more round. The run records
show the opposite: the loop converged on everything tractable and stopped at
two findings that the handoff itself classifies as redesigns. A fourth round
would have ground against an anti-forgery boundary decision and a cursor
redesign. More rounds do not help when the remaining work needs a judgement
call. If a cap change is ever revisited, the question to ask is why the hard
findings were not escalated when they were recognised, not whether there were
more rounds available.

**Do not split phases on phase-file size; do check the produced diff size.**
The earlier draft rejected resplitting on a correlation of 0.05 between
phase-file size and hours, which was correct but answered the wrong question.
Phase-file size is not the variable. The developer produced 171 files in
100606 against 8 in 100601, and developer time predicts remediator time at
r = 0.46 across 43 phases. The actionable form of this is item 2 below, not a
sizing rule about the plan document.

**Round-to-round memory is a smaller win than first assessed.** Carrying a
round's own evidence forward would have made rounds 2 and 3 write truer prose,
which is four of the seven round-3 grounds. It would not have touched F-06 or
F-13, the two functional grounds. It is worth doing and is worth doing
cheaply, but it reduces prose defects; it does not fix convergence.

## Proposal

Five items, ordered by how much incident each would have prevented.

### 1. Escalate with evidence instead of exhausting into a halt

When the approver hits `max_rounds` with findings still open, the run currently
ends in `rejected`. That state conflates two different facts: the checker
disagreed with the work, and the checker's budget ran out. Only the second is
true at exhaustion.

Add a distinct end state, `remedy_escalated`. On reaching it:

1. **Write a handoff document into the run directory**, generated by the
   pipeline, not by an operator. It must carry: the finding table with severity
   and status; the per-round open set and what cleared each round; every
   `file:line` site the approver cited, grouped by finding; the gate results
   the approver recorded; and the open findings split into those whose grounds
   are prose or comments and those with a reproduced functional defect. The
   approver's log already contains all of this; the work is assembly, not new
   analysis.
2. **Split the residue by ground type in that same document.** A prose ground
   is a thing a further round can plausibly fix. A reproduced functional defect
   is a thing that may need a design decision, a scope change, or acceptance
   with documentation. An operator reading only the split can tell in one
   glance whether another round would help. This distinction is the single most
   useful thing the pipeline can produce here, and it is invisible today.
3. **Release the reservation**, so no other machine is blocked by a claim no one
   is working on. Release only after the handoff is durably written.
4. **Do not write the halt marker.** The line continues to the next phase. The
   cost of one phase needing a decision should be that phase's cost.
5. **File an issue** naming the phase, the handoff path, and the open findings,
   so the work is tracked rather than lost.

**A trap in this design that the implementer must handle explicitly.** Phase
selection treats only six markers as done, and `state == "completed"` is one of
them; a new end state is not on that list. If `remedy_escalated` neither halts
the line nor counts as done, the driver will select the same phase again on the
next 10-minute tick and re-run it in a loop, which is worse than today's halt.
The new state needs an explicit exclusion from automatic selection. Decide and
record the operator action that clears it: a marker file, an explicit takeover,
or an explicit resume flag. Whichever it is, a phase skipped after escalation
must appear in `--dry-run` and in the audit output, never silently passed over.

Resumption should then be routine: one command re-enters the approver with the
remaining findings, and an operator who decided to accept the phase without a
passing checker records that as an operator decision through the existing
roadmap markers, which `next_phase.py` already honours.

### 2. A diff-size check before the adversary runs

The single highest-value gate in this proposal, because it is the one that would
have fired before any of the cost was incurred. After the developer signals and
before the adversary starts, record the size of the produced change: modified
plus untracked file count, and total diff lines. Compare it against the
distribution of the last N completed phases and report where this phase sits.

Report only, at first. Do not block on it: an unusually large phase is
legitimate often enough that a hard stop trains the operator to bypass the
check. But a notification saying "this phase's change is 4x the median" is the
difference between deciding to split the phase deliberately and discovering
three remedy rounds later that the surface was the problem.

Establish the threshold from the recorded history rather than picking one. The
local data supports a clear separation: developer time and remediator time
correlate at r = 0.46, and 100606's 171 files against 100601's 8 is far outside
anything else in the record.

Record the per-phase measurement in the run directory whether or not it
exceeds anything, so the distribution grows rather than being recomputed from
scratch each time.

### 3. One read-only convergence and cost report

A script, not a pipeline change, that prints per phase: finding total, open set
per round, what cleared each round, whether the residue is shrinking or stable,
the round count, and agent time by step.

Every input already exists: `run.json` carries each step's signal and
`duration_s`; `findings.original.json` carries the totals; the approver's log
carries the cited sites. This is the twenty lines whose absence cost the 100606
investigation, and it is the item that would let convergence be read from a
notification instead of reconstructed from a shell.

Two supporting changes, both small:

- Have the approver include the open count in its verdict, for example
  `REMEDY_REJECTED: 4 (was 7) of 16: F-03,F-06,F-10,F-13`. It already knows
  this; it is deciding on those findings. This makes the report's answer arrive
  without anyone remembering to run it.
- Have the driver write a per-phase cost breakdown next to its existing finish
  notification: agent seconds by step, remedy rounds, and elapsed wall clock
  from launch to finish.

### 4. Record the wall clock, not only the agent time

100606's run records total 7.84h of agent time against roughly twelve hours of
wall clock. The difference is cron wait, halt dwell, and operator time, and none
of it is recorded anywhere. The local driver log shows the same pattern at
small scale: phase 100060 halted at 02:09:38 and the line refused to advance
until 02:32:21, about 22 minutes that appear in no `run.json`. With a
10-minute cron interval every manual fix costs up to 10 minutes of pure waiting.

Extend the run record so a phase's elapsed time is answerable without
reconstructing it: launch and finish timestamps, halt dwell, and the number of
times the line was halted for that phase. This is the difference between "the
remediator took 5.75h" and "the phase took twelve hours, and we cannot say
where the rest went". Both numbers matter; today only the one that does not
explain the incident is recorded.

### 5. Reuse a gate receipt when the tree has not changed

Each approver round re-runs formatting, clippy, the full suite and the Postgres
path from scratch. In 100606's round 3 the approver re-ran all of it and
recorded every result, which is good practice and also roughly six minutes
repeated per round. Carry the receipt forward when the recorded tree identity
and the gate inputs are unchanged, so a later round can cite it rather than
reproduce it.

Establish what a valid identity key is before building this. The ledger records
`git_head` per step, and a commit hash is not sufficient on its own, because
the working tree during these phases is unstaged and uncommitted by design. The
approver validates the unstaged diff, so the receipt key must cover the diff
content and not only the commit.

Listed last deliberately. This saves minutes, not hours, and the 100606 evidence
shows the approver's gate re-runs were the cheapest part of a very expensive
run.

## Out of scope for this proposal

**The driver never passes `--takeover`.** The operator handoff names this as
the single most useful harness fix available, and it is a real gap: any phase
whose reservation is stale or terminal fails instead of recovering, which is
what forced a manual bypass on 100606. It is left out here only because it
belongs to the driver's recovery path rather than to the remedy loop, and
because it deserves its own proposal with its own fencing analysis. It should
not wait long.

**The ledger's `git_head` repin is hand-maintained.** In `100606`'s ledger,
`head_repin` records a move from one HEAD to another with a reason, and all
four steps now carry the later value. The runner does not read `head_repin`; the
check at `verify_ledger` is a plain string comparison of each step's `git_head`
against the current HEAD. So the repin is documentation, not mechanism, and
merging the recovery pull request will move HEAD again and require a manual
repin of four values before the resume will pass. A supported repin path, with
an audit record the runner writes rather than a human, belongs with the
`--takeover` work.

**Do not change the approver's standard.** Rejecting a resolution whose prose
misstates the code is the system working. Every item here makes failure cheaper
or evidence easier to reach. Any implementation that reduces a rejection rate
by relaxing verification has missed the point.

## Hypothesis (non-binding)

The loop did converge on 100606. It reached the two findings that needed a
person and then had no way to say so, so it produced a halt instead of a
decision. A pipeline that recognised a stable residue, split it by ground type,
and wrote the evidence up would have converted a twelve-hour incident into an
afternoon of review and a clear choice.

## What the implementer must validate locally

Do not trust this proposal on where things live. Read the code first and confirm
or correct each point.

- Find every consumer of a run's terminal state: the pipeline `ends:` list, the
  driver's exit-code case, `next_phase.py`'s done test, the reservation
  completion path, and the audit and verbose output. Confirm the full set
  before adding a state, and confirm which would misbehave on an unrecognised
  value.
- Confirm the re-selection loop described in item 1 against the real selection
  path, and confirm the chosen skip mechanism cannot strand a phase permanently
  and silently.
- Confirm where the diff size can be measured without disturbing the working
  tree. These phases run with changes unstaged and uncommitted by design, so
  any measurement must read the same diff semantics the approver validates and
  must not stage, commit, or clean anything.
- Confirm what the approver's log actually contains at verdict time, and
  whether the cited `file:line` sites are parseable without re-deriving them
  from prose. If they are only in prose, the assembly in item 1 becomes an
  extraction problem and that changes its cost.
- Confirm the totals in `findings.original.json` are the right denominator, and
  that they exist for every phase including ones with no adversary run.
- Confirm the driver's log has launch, halt and resume timestamps sufficient to
  compute wall clock, and that they survive for the life of a phase. Note the
  log-retention setting before relying on this.
- Re-measure the developer-time and remediator-time correlation on whatever
  data exists at implementation time, including 100606 itself, and establish
  the item 2 threshold from the recorded distribution rather than from the
  numbers quoted here.

## What the implementer must validate externally

Search first. Do not invent a pattern.

- Search for how unattended pipelines escalate a job that exhausted a retry or
  review budget, and compare a generated handoff plus continued line against a
  terminal stop. The question is what the system should do next, not how to
  report exhaustion.
- Search for established practice on splitting a failed review's residue into
  actionable classes, particularly separating documentation defects from
  reproduced functional defects, and for any known failure mode in doing so.
- Search for guidance on change-size thresholds for review or CI gating, and on
  why a large change is expensive to review repeatedly rather than once. This
  is the closest analogue to item 2 and may have established numbers.
- Search for guidance on caching verification results keyed on content
  identity. Do not design a cache from memory of similar systems.

## Safety properties

- The approver's bar does not move. No item may reduce a rejection by relaxing
  verification.
- Escalation never silently passes. A phase skipped after escalation appears in
  the dry-run preview and in the audit output.
- No escalated phase is re-run automatically. Resumption is always an explicit
  operator action.
- The reservation is released only after the handoff is durably written, so a
  released claim never loses the only record of the open work.
- Releasing a reservation must not let a second machine start the same phase
  concurrently with the first. Confirm the reservation lifecycle still fences
  this after escalation, and that the skip mechanism and the reservation agree
  about ownership.
- The handoff document is private. It may contain private paths, phase numbers,
  requirement text and run-log excerpts, and must never be copied into a public
  file, an issue body, a pull request, or CI output. Any issue filed on
  escalation carries only the public-safe summary and a pointer.
- The diff-size check reads the working tree and never mutates it. These phases
  run uncommitted by design; the check must not stage, commit, stash or clean.
- The report is read-only and must be safe to run against a run in progress.
- Adding a verdict field must not break signal parsing. The runner matches the
  signal as a prefix and carries the remainder as context; confirm the new form
  parses and that already-recorded signals still read correctly.

## Acceptance

- Automated: a stubbed pipeline that exhausts an approver cap ends in
  `remedy_escalated`, writes a handoff containing the per-round open sets and
  the cited sites, splits the residue into prose and functional groups, releases
  the reservation, writes no halt marker, and is skipped by the next selection
  tick rather than re-launched.
- Automated: the handoff for a stubbed run with mixed grounds lists the prose
  and functional findings in separate groups, with no finding in both.
- Automated: a phase skipped after escalation appears in `--dry-run` and in the
  audit output, and is not selected for launch.
- Automated: an explicit resume action re-enters the approver with the leftover
  findings, and cannot loop unboundedly.
- Automated: the diff-size check reports the modified and untracked counts and
  diff line total for a stubbed tree, and leaves the tree byte-identical.
- Automated: the new verdict form parses, and a recorded old-form signal still
  reads correctly.
- Automated: the report runs read-only against a synthetic run directory and
  against a run in progress, and produces the same numbers twice.
- Manual: exhaust a cap on a real phase, confirm the line continues unprompted,
  confirm the handoff is readable and correctly splits the residue, and confirm
  the finish notification carries the cost breakdown.
- Record, in the implementation record, the next real escalated phase's remedy
  rounds and wall clock next to the 100601 and 100606 numbers, so the effect is
  measured rather than asserted.

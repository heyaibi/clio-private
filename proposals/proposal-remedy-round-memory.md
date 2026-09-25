# Proposal: carry a remedy round's own evidence into the next round

Status: draft. Date: 2026-09-25. Scope: pipeline bindings, one stage file, possibly the runner. No stage-role changes, no cap changes.

Note: on implementation, move this file to `implemented/` with its implementation record.

## Problem

A remedy round cannot see what it already proved. Round N writes its verified
evidence into its own run log (`remediator-task-r<N>.log`) and into the
`resolution` fields of `findings.json`. Round N+1 receives the approver's
verdict and nothing else. It does not receive the path to its own previous
log, and it is not told that its previous evidence exists.

Measured on `runs/phase-100601`, the run with the most remedy rounds available
locally:

- `remediator-task-r1.log` is 5825 bytes of per-finding evidence with
  `file:line`, named tests, and real command output — for example
  `crates/clio-compliance/src/correct.rs:129-143` with
  `cargo test -p clio-compliance` output, and a before/after binary
  comparison at `target/debug/clio`.
- `remediator-task-r2.md` is 34124 bytes. The string `remediator-task-r1`
  appears exactly once in it, and that single occurrence is a negative example
  inside the GitHub redaction rules ("do not write
  `private/clio-private/runs/phase-100060/remediator-task-r1.log`"). It is not
  a pointer to read.
- The remediator's declared prior-context placeholder is
  `PREVIOUS_VERDICT: Approver verdict from the previous round`, bound in
  `pipelines/default.yaml` to `{output: approver}`. That is the only
  round-to-round channel the stage has.

So round 2 re-derives what round 1 already established. The cost is not only
time. When the approver rejects on a claim round 2 cannot substantiate,
round 2 either re-derives the evidence correctly or restates the claim from
its own reading. The second case is what the server-side review of phase
100606 described as "the remediator writes claims it hasn't verified", and it
consumed the most expensive round in the run's history.

This is a distinct problem from harness pinning. Pinning keeps the same model
across rounds. It does not hand that model what it already knew. A pinned
model with no memory of its own prior round still re-reads and re-derives.

## Proposal

Give the next round of a loop step a way to reach the previous round's own
recorded evidence, and tell the stage in its own text that this is expected.

Three parts, in increasing order of invasiveness. The implementer should
choose the smallest part that closes the loop, and should say in the
implementation record which part was needed and why.

1. Bind the previous round's log path into the stage. The runner already knows
   the run directory, the step id, and the round number, so a binding of the
   form `{run_dir}/{agent}-task-r{round-1}.log` is derivable for any round
   above 1. Add a placeholder to the stage's frontmatter, bind it in the
   pipeline, and reference it in the stage body. This is a pipeline and stage
   change only; it needs no runner change if the previous round number can be
   computed in the binding. Confirm whether `{round}` is an integer in the
   binding context before assuming arithmetic works in the format string —
   `Run.ctx` builds it as an int, and format strings do not evaluate
   arithmetic, so this likely needs either a new context key (for example
   `prev_round`) or a new binding source.

2. Alternatively, bind the previous round's *output text* rather than its
   path. The runner keeps per-step output in `run.outputs` and overwrites it
   per step id, not per round, so the prior round's text is not currently
   retained. Retaining a per-round output history is a runner change with real
   cost: it grows the resume state and the committed record. Only take this
   path if part 1 proves insufficient, and if you do, say why a path was not
   enough.

3. Add a stage-text rule that the prior round's log is the first thing to read
   on any round above 1, and that a finding the previous round marked resolved
   with cited evidence is not to be re-litigated without new contradicting
   evidence. This is the part that changes behavior. The binding alone only
   makes the evidence reachable.

## Hypothesis (non-binding)

The previous round's log already contains the evidence an approver later
demands. Making it reachable, and requiring it be read first, should reduce
the number of findings rejected for unsupported claims without raising the
approver's standard. Convergence should arrive sooner, and the claims a
remediator makes should be ones it can point at.

## What the implementer must validate locally

Do not trust this proposal on where things live. Read the code first and
confirm or correct each point.

- Confirm the exact binding set the remediator stage receives, and that
  `PREVIOUS_VERDICT` is the only cross-round channel. `stages/03-remedy.md`
  frontmatter and the `remediator:` block in `pipelines/default.yaml` are the
  two places to read.
- Confirm `Run.ctx` (search `def ctx`) and record what `round` and `rounds`
  are, and whether any existing binding performs arithmetic on them. The
  format-string binding path is a `str.format` over the context dict, so
  assume no arithmetic until proven otherwise.
- Confirm whether per-round output text is retained anywhere after the step
  re-runs. `run.outputs` is keyed by step id; check whether a re-visit
  overwrites or whether anything keeps a per-round copy.
- Confirm the run log filename convention is derivable, not incidental. The
  remediator's `LOG_PATH` binding is `"{run_dir}/{agent}-task-r{round}.log"`;
  confirm the runner uses that same convention to locate logs when it reads
  or displays them, so a new binding cannot drift from it.
- Confirm round 1 gets an empty or absent prior-log binding rather than a
  path to a file that does not exist, and decide what a round-1 agent should
  be told when the path is empty.
- Check what a bound path looks like in the rendered prompt when the run
  directory is on a different machine than the one running the stage. The
  local `runs/` copy and the server copy have different absolute prefixes, so
  a hardcoded or copied path is a live risk, not a theoretical one.
- Confirm the stage body has a natural place for the new instruction that does
  not crowd the existing triage and orchestration rules. `stages/03-remedy.md`
  already has a rounds-after-round-1 line in its execution rules; check
  whether the new rule belongs next to it.

## What the implementer must validate externally

Search first. Do not invent a memory pattern.

- Search for established practice on carrying an agent's own prior-turn
  scratch work into a later turn of the same task, especially where the prior
  work is an append-only log with tool output. Compare binding the log path
  against inlining the log text, for both token cost and for whether the
  agent actually reads a path it is merely told about.
- Search for failure modes where an agent is given a pointer to its own prior
  evidence and does not read it, and what makes an instruction to read it
  effective. This determines whether part 1 alone is worth doing.
- Search for guidance on whether re-verifying a prior conclusion is a feature
  or a bug in review loops. If re-derivation catches real regressions, a rule
  against re-litigating a resolved finding needs a stated exception for new
  contradicting evidence.

## Safety properties

- The approver's standard does not change. A remediator that reuses its own
  evidence must still substantiate every claim; reuse is not acceptance.
- No finding can be closed on the strength of a previous round alone. The
  stage must still verify against the current diff, because the diff can
  change between rounds for reasons outside the remediator's control.
- The original findings backup stays authoritative and unmodified. Passing a
  log path forward must not become a path by which the backup can be edited.
- A missing, unreadable, or empty prior log degrades to today's behavior
  rather than failing the round. A missing log must never block a remedy.
- Nothing in this proposal may put a private path, phase number, or run-log
  excerpt into a public file, an issue body, or CI output. The stage already
  carries redaction rules; the new instruction must not undermine them.
- A round-2 prompt must not grow without bound. If the evidence grows, prefer
  the path over the inlined text, and keep the task file within the size the
  pipeline already assumes.

## Acceptance

- Add an automated check with a stubbed stage that runs two rounds of a
  two-step loop, and assert the second round's rendered prompt carries the
  first round's log path, and that round 1's does not.
- Add a check that the binding is empty rather than dangling on round 1, and
  that a stubbed stage given a nonexistent prior-log path still completes.
- Add a manual check on a real repeat phase: after round 2 starts, confirm its
  first run-log entries cite the round-1 evidence rather than re-deriving it
  from scratch, and that the round-1 log was actually opened.
- Record, in the implementation record, how many remedy rounds and how much
  wall-clock the next real repeat phase takes, next to the 100601 and 100606
  numbers, so the effect is measurable rather than asserted.

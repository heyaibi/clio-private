# Proposal: carry a remedy round's own evidence into the next round

Status: draft. Date: 2026-09-26. Scope: pipeline bindings, one stage file, possibly the runner. No stage-role changes, no cap changes.

Note: on implementation, move this file to `implemented/` with its implementation record.

**Priority note, revised after the 100606 run records were read.** This was
first written as a convergence fix. It is not one. In 100606's round 3, four of
the seven rejection grounds were prose or comment defects, and carrying a
round's own evidence forward would have reduced that number. The other grounds
were reproduced functional defects — a non-idempotent secret mask, a push-cursor
freeze — which no amount of carried-forward evidence would have fixed. So this
proposal reduces a documentation defect class. It does not fix the loop. It is
still worth doing, it is cheap, and it is listed in the umbrella proposal
`proposal-remedy-loop-escalation-and-evidence.md` at lower priority for that
reason.

## Problem

A remedy round cannot see what it already proved. Round N writes its verified
evidence into its own run log (`remediator-task-r<N>.log`) and into the
`resolution` fields of `findings.json`. Round N+1 receives the approver's verdict
and nothing else. It is not given the path to its own previous log, and it is
not told that its previous evidence exists.

Measured on `runs/phase-100601`, which has the most remedy rounds in the local
history:

- `remediator-task-r1.log` is 5825 bytes of per-finding evidence with `file:line`,
  named tests, and real command output — for example
  `crates/clio-compliance/src/correct.rs:129-143` with
  `cargo test -p clio-compliance` output, and a before/after binary comparison.
- `remediator-task-r2.md` is 34124 bytes. The string `remediator-task-r1` appears
  exactly once in it, and that occurrence is a negative example inside the
  GitHub redaction rules ("do not write `private/clio-private/runs/.../
  remediator-task-r1.log`"). It is not a pointer to read.
- The remediator's only cross-round channel is `PREVIOUS_VERDICT: Approver
  verdict from the previous round`, bound to `{output: approver}`.

The same pattern appears in 100606. The round-3 approver's grounds 1, 2, 5 and 7
are all places where a remediator assertion about the code did not match the
code — `correct.rs:296-300` still claiming a prior sealed context is
reconstructable, `docs/source-context-and-migration.md:28-30` making the same
claim, `findings.json` `recommendations[0]` asserting two wire kinds are
dead-lettered when `apply.rs:142-147` routes them, and stale test comments at
`apply_records_tests.rs:100-106` denying coverage the same round had added. Each
is a claim made without re-reading the site it was about.

So the cost is not only time. When the approver rejects on a claim the next round
cannot substantiate, that round either re-derives the evidence correctly or
restates the claim from its own reading. The second is what the 100606 review
described as "the remediator writes claims it hasn't verified", and it
contributed four of the seven grounds in the most expensive round on record.

This is a distinct problem from harness pinning. Pinning keeps one model across
rounds. It does not hand that model what it already knew. A pinned model with no
memory of its own prior round still re-reads and re-derives.

## Proposal

Give the next round of a loop step a way to reach the previous round's own
recorded evidence, and say in the stage text that this is expected.

Three parts, in increasing order of invasiveness. Choose the smallest that
closes the loop, and record in the implementation note which was needed and why.

1. **Bind the previous round's log path into the stage.** The runner already
   knows the run directory, the step id and the round number, so a path of the
   form `{run_dir}/{agent}-task-r{round-1}.log` is derivable for any round above
   1. Add a placeholder to the stage frontmatter, bind it in the pipeline, and
   reference it in the stage body. This is a pipeline and stage change; it needs
   no runner change only if the previous round number is computable in the
   binding. Confirm whether `{round}` supports arithmetic before assuming it —
   `Run.ctx` builds it as an int and format strings do not evaluate arithmetic,
   so this likely needs a new context key such as `prev_round`, or a new binding
   source.

2. **Alternatively, bind the previous round's output text** rather than its path.
   The runner keeps per-step output in `run.outputs`, keyed by step id, so the
   prior round's text is not currently retained. Retaining a per-round history is
   a runner change with real cost: it grows the resume state and the committed
   record. Take this path only if part 1 proves insufficient, and say why a path
   was not enough.

3. **Add a stage-text rule** that the prior round's log is the first thing to
   read on any round above 1, and that a finding the previous round marked
   resolved with cited evidence is not re-litigated without new contradicting
   evidence. This is the part that changes behavior; the binding alone only
   makes the evidence reachable.

   Scope the rule narrowly. In 100606 the approver's functional grounds were
   *correct*: the mask really was non-idempotent, and the cursor freeze was
   real. A rule that made the remediator trust its own prior conclusions more
   confidently would have made that worse. The rule should be about re-reading
   before re-asserting, not about treating prior conclusions as settled.

## Hypothesis (non-binding)

The previous round's log contains most of the evidence an approver later demands
for a prose ground. Making it reachable, and requiring it be read first, should
reduce rejections whose grounds are unsupported claims, without moving the
rejection rate for reproduced functional defects, and without any change to the
approver's standard.

## What the implementer must validate locally

Do not trust this proposal on where things live. Read the code first and confirm
or correct each point.

- Confirm the exact binding set the remediator stage receives, and that
  `PREVIOUS_VERDICT` is the only cross-round channel. `stages/03-remedy.md`
  frontmatter and the `remediator:` block in `pipelines/default.yaml` are the
  two places to read.
- Confirm `Run.ctx` (search `def ctx`) and record what `round` and `rounds` are,
  and whether any existing binding performs arithmetic on them.
- Confirm whether per-round output text is retained anywhere after a step
  re-runs. `run.outputs` is keyed by step id; check whether a re-visit overwrites
  or whether anything keeps a per-round copy.
- Confirm the run log filename convention is derivable rather than incidental.
  The remediator's `LOG_PATH` binding is `"{run_dir}/{agent}-task-r{round}.log"`;
  confirm the runner uses that same convention when it reads or displays logs,
  so a new binding cannot drift from it.
- Confirm round 1 gets an empty or absent prior-log binding rather than a path
  to a file that does not exist, and decide what a round-1 agent is told when
  the path is empty.
- Check what a bound path looks like in the rendered prompt when the run
  directory is on a different machine from the one running the stage. The local
  and server copies of `runs/` have different absolute prefixes, so a
  hardcoded or copied path is a live risk, not a theoretical one.
- Confirm the stage body has room for the new instruction without crowding the
  existing triage and orchestration rules. `stages/03-remedy.md` already has a
  rounds-after-round-1 line in its execution rules; check whether the new rule
  belongs beside it.
- Re-read the 100606 round-3 grounds against whatever rule you write, and confirm
  the rule would not have suppressed grounds 3, 4 or 6, which were real
  reproduced defects rather than unsupported claims.

## What the implementer must validate externally

Search first. Do not invent a memory pattern.

- Search for established practice on carrying an agent's own prior-turn scratch
  work into a later turn of the same task, especially where the prior work is an
  append-only log with tool output. Compare binding the log path against
  inlining the log text, for token cost and for whether the agent actually reads
  a path it is merely told about.
- Search for failure modes where an agent is given a pointer to its own prior
  evidence and does not read it, and what makes an instruction to read it
  effective. This determines whether part 1 alone is worth doing.
- Search for guidance on whether re-verifying a prior conclusion is a feature or
  a bug in review loops. If re-derivation catches real regressions, any rule
  against re-litigating a resolved finding needs a stated exception for new
  contradicting evidence.

## Safety properties

- The approver's standard does not change. A remediator that reuses its own
  evidence must still substantiate every claim; reuse is not acceptance.
- No finding can be closed on the strength of a previous round alone. The stage
  must still verify against the current diff, because the diff can change
  between rounds for reasons outside the remediator's control.
- A prior round's conclusion that the approver contradicted must not be treated
  as settled. In 100606 the approver's functional grounds overrode remediator
  claims; that ordering must survive this change.
- The original findings backup stays authoritative and unmodified. Passing a log
  path forward must not become a route by which the backup can be edited.
- A missing, unreadable, or empty prior log degrades to today's behavior rather
  than failing the round. A missing log must never block a remedy.
- Nothing here may put a private path, phase number, or run-log excerpt into a
  public file, an issue body, or CI output. The stage already carries redaction
  rules; the new instruction must not undermine them. In particular the carried
  log is full of absolute private paths, so the stage must tell the agent it is
  reading private run evidence and must not quote it outward.
- A round-2 prompt must not grow without bound. If the evidence grows, prefer the
  path over the inlined text, and keep the task file within the size the pipeline
  already assumes.

## Acceptance

- Automated: a stubbed two-step loop runs two rounds and the second round's
  rendered prompt carries the first round's log path, while round 1's does not.
- Automated: the binding is empty rather than dangling on round 1, and a stubbed
  stage given a nonexistent prior-log path still completes.
- Automated: the stage text does not instruct the agent to treat a contradicted
  prior conclusion as settled. Assert on the rendered text, since this is the
  safety property most likely to be reintroduced by a well-meaning edit.
- Manual: on a real repeat phase, confirm the round-2 run log's first entries
  cite the round-1 evidence rather than re-deriving from scratch, and that the
  round-1 log was actually opened.
- Record, in the implementation note, how many rejections on the next real
  repeat phase had prose grounds, next to the 100606 baseline of four of seven
  in round 3, so the effect is measured rather than asserted.

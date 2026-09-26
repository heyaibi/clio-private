# Proposal: [short outcome, not the mechanism]

<!--
HOW TO USE THIS FILE
  1. Copy it to proposals/proposal-<short-kebab-name>.md. Drop this comment block.
  2. Replace every [bracketed] placeholder. Delete any section that does not apply
     rather than leaving it empty — an empty section reads as an oversight.
  3. Delete the italic guidance under each heading once you have answered it.
  4. On implementation, move the file to proposals/implemented/ and append the
     Implementation record from the bottom of this template.

A proposal is not a plan. A plan says what to build and how. A proposal states a
problem, the properties an answer must have, and the evidence the implementer must
gather before designing. The implementer owns the design. If you find yourself
writing step 1, step 2, you have written a plan — put it in roadmap/ instead.

The recurring mistake this template exists to prevent: asserting how the code works
without reading it. Every claim about current behaviour belongs in "What the
implementer must validate locally", backed by a file:line, a command you ran, or a
number you measured. A claim you did not verify is a guess wearing a citation.
-->

Status: draft. Date: [YYYY-MM-DD]. Scope: [exact files, directories, or components this touches]. [State what this does NOT change — name the specific behaviour, not "nothing".]

Note: on implementation, move this file to implemented/ with its implementation record.

<!-- Optional. One short paragraph: where this came from, what prompted it, and any
     correction to an earlier version of this same document. If this proposal revises
     an earlier one, say so here, and keep the "Corrections" section near the end. -->

## Problem

[What is wrong or missing today, in plain words. Describe the behaviour, not your
feelings about it: "the driver notifies once and is then silent", not "notifications
are bad".]

[Where you can, show it. A log excerpt, a table of measured numbers, a before/after
diff, the exact command and its exact error. Evidence is what separates a problem
from a hunch.]

[If the problem was found by a postmortem or an audit, name the source. If earlier
conclusions were wrong, say so here and correct them below — do not quietly write the
first version as though it were right.]

## Goal

[One or two sentences. What must be true when this is done, stated so that "done" is
checkable. If you cannot write a checkable sentence, the problem is not yet defined.]

## Proposal

[What is being proposed, at the level of behaviour and properties. Be explicit about
what you are choosing NOT to prescribe, and why. A proposal that prescribes no
implementation is deliberate: it forces the implementer to find a design, and lets a
better one win without rewriting the proposal.]

[This document states the problem and the safety properties only. It deliberately
prescribes no implementation. The implementer owns the design after the validation
below.]

## Hypothesis (non-binding)

[Your best current guess at why this works, stated so it can be proved wrong. If the
hypothesis is wrong, the proposal should survive on its safety properties alone — if
it does not, the proposal is over-fitted to one design and should be rewritten.]

## What the implementer must validate locally

Do not trust this proposal on where things live. Read the code first and confirm or
correct each point.

- [Claim from this document, with its file:line, and what to check.]
- [The path that must be exercised end to end, not just a helper in one process.]
- [What state must exist for the problem to occur. A fix that only works on a fresh
  install is not a fix.]
- [What must NOT change, and how to prove it did not.]

## What the implementer must validate externally

Search first. Do not invent behaviour, and do not assume a library works the way its
name suggests.

- [The established approach, with a source.]
- [The failure mode this design is chosen to avoid, and how others handle it.]
- [Any option you rejected, and the reason, so nobody re-derives it.]

## Design decisions

[Every choice a reader might reasonably have made differently. One subsection per
question, at least two avenues each, and for each avenue exactly two pros and two
cons. State a recommendation. A question with one avenue is not a decision, it is a
decision you made without noticing.]

### [Decision question, phrased as the choice]

#### Avenue A — [name]

- Pro: [real advantage]
- Pro: [second real advantage]
- Con: [real cost or risk]
- Con: [second real cost or risk]

#### Avenue B — [name]

- Pro: [real advantage]
- Pro: [second real advantage]
- Con: [real cost or risk]
- Con: [second real cost or risk]

Recommendation: [Avenue X, and the one sentence that decides it.]

## Safety properties

[Each property must be checkable and must hold in the failure cases, not just the
happy path. Write them so a reviewer can disagree with one.]

- [Property that must never be violated, and what it protects.]
- [What happens when a dependency is missing, times out, or returns nonsense.]
- [What happens if this is run twice, or run concurrently with itself.]
- [The blast radius if this is wrong. What breaks, and what is merely ugly.]

## Acceptance

- [Automated check. Name the file and the assertion, not "add tests".]
- [Manual check on the real entry point, with realistic state, and the exact commands.]
- [State what was verified locally and externally, and list anything that could not
  be verified. An unverified claim must appear here, not be quietly dropped.]

## What could not be verified

[Anything you asserted but did not confirm by running or reading. If this section is
empty, say so explicitly — an empty list usually means the check was skipped, not
that nothing was uncertain.]

- [Claim, and why it stayed unverified.]

## Out of scope for this proposal

[What a reader might reasonably expect this to also fix, and why it is not here. This
section prevents scope creep and prevents a deferred bug from being silently tied to
this work.]

- [Adjacent problem, and where it should go instead.]

## Corrections to the first version of this proposal

[Delete this section on a first draft. Keep it on every revision: list what the
earlier version claimed, what is actually true, and what the correction changes. A
proposal that quietly rewrites itself loses the record of why it was believed, which
is usually the most useful part. State plainly that an earlier conclusion was wrong.]

## Open questions

[For the operator, not the implementer. Anything needing a decision before work starts.]

- [Question, and what it blocks.]

<!--
===========================================================================
IMPLEMENTATION RECORD
Delete everything above this line when moving the file to implemented/, then
replace the status line with: Status: implemented (YYYY-MM-DD). Scope: ...
===========================================================================

# Implementation record

## Local validation and reproduction

[The reproduction as it was actually run, before any edit: exact command, exact
output, exact state. Then the same commands after, from the same starting state.
If you never reproduced it end to end, say so here plainly and do not call it fixed.]

## Design

[The design actually built, and why it is this one. If it differs from the
recommendation in the proposal, say which avenue was chosen over which, and why.]

## External validation

[What you searched, what you found, and whether it changed the design.]

## Resolved choices

[Each open question, the decision, and who made it. One line each.]

## Verification

[What was checked and passed. What was not checked. Anything still outstanding,
including deployment acceptance that could not run in this environment.]
-->

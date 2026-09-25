# Resuming phase 100606 locally — pre-flight

Private. Read `local_docs/phase-100606-handoff.md` end to end first; this is
the short list of things that will stop you if you do not know about them.

## Four things that will bite

**1. The claim is held by `devserver`, not by you.** Generation 4. Any local run
needs `--takeover` or the runner refuses with a reservation conflict.

**2. Enter at the `remediator`, not the approver.** `resume.json` already points
there. Resuming directly at the approver returns instantly without invoking
anything, because the ledger already proves that step completed with a terminal
routing. That is a silent no-op, not an error — easy to misread as success.

**3. Merging the recovery PR will break the resume until you re-pin.** The
ledger's `git_head` is compared as a plain string against the current HEAD. All
four steps currently carry `6169cfa8d577`. Merge PR #28, HEAD moves, and the
resume fails. The `head_repin` key in the ledger is documentation only — the
runner does not read it.

To re-pin, set each step's `git_head` in `runs/phase-100606/ledger.json` to the
current HEAD, and update the `head_repin` record to say why. Do this after the
merge and before the run, not during.

**4. The run state is deliberately incomplete, and that is correct.**
`run.json` is intentionally absent — round 4 was aborted before any verdict. Do
not reconstruct one by hand. The historical record is
`run.json.rejected-round3` and `.rejected-round3.takeover2`. Leave both.

## Order of work

1. Sync both repos. `git fetch --all --prune` in the public root, then
   `git pull --rebase` in `private/clio-private`.
2. Review and merge PR #28. Run the full gate set locally first: `make fmt`,
   `make lint`, `make test`, `make coverage`, and check the per-file 90% floors.
   Spend your attention on review priority 1 in the handoff — the F-13 part 1
   change to sync delivery semantics.
3. Re-derive the four findings' resolutions against the merged tree. Verify F-06
   and F-13 part 1 yourself. Assume more untrue claims remain in
   `findings.json`; the handoff found two by hand.
4. Re-pin the ledger if HEAD moved (see above).
5. Take over and run:
   ```bash
   CLIO_MACHINE_ID=<your-id> python3 private/clio-private/harness/runner.py \
     --pipeline private/clio-private/harness/pipelines/default.yaml \
     --input phase_number=100606 \
     --input phase_file=private/clio-private/roadmap/phase-100606-context-lifecycle-portability.md \
     --takeover
   ```
6. Let the remediator and approver run for real. If the remediator produces a
   new round, check its prose claims before the approver sees them.

## If it rejects again

Do not raise the round cap to force it through. Read the grounds, fix the real
cause. Round 4 is capped out; a further attempt is a fresh decision.

Expect the residue to be the two hard findings. F-10 is an anti-forgery
tradeoff, F-13 part 2 is a cursor redesign. Neither is a round of work.

## If you decide to accept without a passing checker

Legitimate, but it must be recorded as an operator decision, not a machine
verdict. Tick the approval box in the phase file, or mark it Complete in
`roadmap/index.md`. `next_phase.py` accepts either.

Never hand-write `run.json`, a `FINALIZE_DONE` ledger entry, a finalize log, or
a completion receipt. A fabricated receipt carries commit SHAs that are false,
and it permanently buries F-13 part 2 and F-10.

## Two open defects — decide each on purpose

Both are in the phase file's Known Limitations. Neither may disappear behind a
completion marker.

- **F-13 part 2** — the item watermark can skip a row. Neither clamping nor the
  current bound is sufficient; the real fix is a resume key monotone with
  respect to insertion. A redesign.
- **F-10** — restore re-derives the context effective time. Carrying the
  exported stamp would reopen the anti-forgery boundary across both backends.

Fix, or accept in writing. Do not let it pass silently.

## Good news about the environment

- Cron entries on the devserver are all commented out. Nothing will launch a
  phase behind you.
- `runs/.driver.env` does not exist, so Discord notifications go nowhere. You
  will get no messages; that is expected, not a fault.
- No `halted`, `current`, `pid` or `stalled` marker exists, and no
  `phase-driver.sh` or `runner.py` is running. The driver is not refusing to
  advance.
- `runs/.driver/driver.lock` was removed. It was harmless anyway — `flock` is
  advisory and released when the holder dies.

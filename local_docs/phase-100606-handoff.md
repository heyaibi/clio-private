# Phase 100606 — operator handoff for off-host completion

> **The code for this phase is in pull request
> [#28](https://github.com/heyaibi/clio/pull/28)** (`phase-100606-recovery` →
> `master`, 217 files, +22,544/−2,761). That PR is the deliverable to review
> and merge. This document is the run history, the two defects that PR
> deliberately leaves open, and the ordered steps to finish the phase without
> fabricating a verdict.

**Status: NOT complete.** The approver rejected the remedy three times and a
fourth round was aborted by the operator before it produced a verdict. No
approval signal was ever emitted for round 4, and no terminal `run.json` was
written for it. Nothing in this repository asserts that phase 100606 passed.

Read this end to end before touching anything. It exists so that the work can
be finished honestly on another machine, one real step at a time.

---

## 0. The pull request

**[#28 — Phase 100606: context lifecycle portability (rounds 1-3 fixes) + F-06/F-13 corrections](https://github.com/heyaibi/clio/pull/28)**

| | |
|---|---|
| Branch | `phase-100606-recovery` → `master` |
| Size | 217 files, +22,544 / −2,761 |
| State | open, rebased onto `master` (`4ed5141`), gates green |

Four commits, and the distinction matters when reviewing:

| Commit | What it is |
|---|---|
| `936c0a2` | **Verbatim preservation** of 215 files of rounds 1–3 work that existed only as uncommitted changes on `master`. Not new authorship — this is prior work captured before it could be lost. |
| `cfb96b4` | F-06 fix — import re-scrubbed an already-scrubbed value (real bug, reproduced end to end) |
| `96b470c` | F-13 part 1 fix — one dead-letter froze all eight push cursors (real bug), plus the F-10 / F-13-part-2 Known Limitations |
| `b0b20cc` | Correct stale sync test comments that denied existing regression coverage |

Verified on the rebased tree: `cargo fmt` clean, `clippy -D warnings` clean,
**2422 tests pass / 0 fail**. Every touched file within the 450-line cap.
Coverage was last measured on a different host before the abort; re-run
`make coverage` if you want it fresh.

**Review priorities on that PR**, hardest first:

1. **F-13 part 1 changes sync delivery semantics.** The case that matters: a
   kind that holds its cursor because one of *its own* mutations was rejected
   must not be able to skip a row the peer never stored.
2. **F-06** is the one change with a real before/after reproduction. Verify it
   yourself rather than trusting the account.
3. The 215-file bulk is prior work; skim for correctness, do not re-review
   from scratch.

Two defects are **deliberately not fixed** in that PR — see section 4. They
are the reason this phase must not be marked complete before someone decides
their fate on purpose.

---

## 1. What happened

| Step | Round | Harness | Outcome |
|---|---|---|---|
| developer | 2 | `opencode:together/glm-5.3-flash@high` | `DEVELOPER_DONE` |
| adversary | 1 | `opencode:go/space-bunny-free@max` | `ADVERSARY_DONE`, 16 findings |
| remediator | 1 | `opencode:together/glm-5.3-flash@high` | `REMEDIATOR_DONE` |
| approver | 1 | `opencode:go/space-bunny-free@max` | `REMEDY_REJECTED` (14 open) |
| remediator | 2 | `cmd:deepseek/deepseek-v4-flash@max` | `REMEDIATOR_DONE` |
| approver | 2 | `opencode:go/space-bunny-free@max` | `REMEDY_REJECTED` (7 open) |
| remediator | 3 | `opencode:together/glm-5.3-flash@high` | `REMEDIATOR_DONE` |
| approver | 3 | `cmd:deepseek/deepseek-v4.1-flash@max` | `REMEDY_REJECTED` (4 open) → `max_rounds` exhausted → `rejected` |
| approver | 4 | `opencode:go/space-bunny-free@max` | **aborted by operator, no verdict** |

Round 3's rejection is the informative one. The approver reproduced all seven
previously-open findings as functionally resolved, with `fmt`, `clippy -D
warnings`, the full test suite and the coverage gate all green — and still
rejected, because five of its seven grounds were prose asserting things the
code did not do. That pattern, not missing functionality, is what consumed the
three rounds.

**Do not trust `findings.json` resolutions without re-verifying them.** The
`recommendations[0]` entry and two test comments in this repo were factually
wrong and were corrected by hand during the handoff. Assume more remain.

## 2. Where the state lives

- `runs/phase-100606/run.json.rejected-round3` — the round-3 terminal result,
  verbatim. Also `.takeover2`. These are the historical record.
- `runs/phase-100606/run.json` — **intentionally absent.** No terminal state
  was produced for the aborted round 4. Do not reconstruct one by hand.
- `runs/phase-100606/resume.json` — **present.** Lets round 4 resume where it
  stopped, at the `remediator` step.
- `runs/phase-100606/ledger.json` — step proofs pinned by sha256. Carries a
  `head_repin` key recording that `git_head` was moved from `09679d68` to the
  post-rebase HEAD, with the reason. Re-pin it if you move HEAD again, or
  `verify_ledger` will refuse the resume.
- `coordination/state.json` — phase 100606 is `blocked`, generation 4, owned by
  `machine_id: devserver`. **`devserver` is not the local machine.** Any local
  run must pass `--takeover` or the runner refuses with a reservation conflict.
- `roadmap/phase-100606-context-lifecycle-portability.md` — carries two Known
  Limitations added during the handoff. See section 4.

## 3. Product fixes — see PR #28

All four fixes are in **[#28](https://github.com/heyaibi/clio/pull/28)**.
Review and merge that PR; do not re-implement any of it. The summary below is
so you can verify rather than trust.

- **F-06 — real bug, reproduced end to end.** `scrub_inline_secrets` was not
  idempotent. `mask_secret` returns the literal `[REDACTED]` only for values of
  four characters or fewer, so an exported `token: ab` became
  `token: [REDACTED]`, and re-scrubbing that ten-character value produced
  `token: ****TED]`. Before/after was reproduced through the real binary
  (store a persona with a short secret, export `dsar_plaintext`, import into a
  fresh store, read back). Fixed in `crates/clio-config/src/secret.rs` by
  treating a value already exactly `[REDACTED]` as masked. Longer masks were
  already fixed points, so the guard closes the only non-idempotent case and
  does not weaken masking of hand-crafted bundles.
- **F-13 part 1 — real bug.** Every per-kind push watermark advance sat inside
  `if response.rejected.is_empty()`. The bank-level compound cursor is one
  ordered position and must hold on any rejection, but gating all eight kind
  cursors on it meant a single dead-lettered mutation froze every kind, the
  whole backlog re-sent on each retry, and `pending_push` never drained.
  `KindBatch` now records the `mutations` range it packaged and a kind
  advances unless one of **its own** mutations was rejected.
  `crates/clio-sync/src/client_feed.rs`.
- **F-03 — documentation only.** Four sites claimed the prior sealed context
  stayed reconstructable through `audit_trail`; the code stores only
  presence/length/hash. The code was correct, so the prose was corrected.
- **Corrected false claims**: `findings.json` `recommendations[0]` (claimed the
  `task`/`failure` wire kinds are dead-lettered and ride the item feed — both
  false) and two stale comments in `crates/clio-sync/src/apply_records_tests.rs`
  (claimed persona-erase regression coverage was removed or blocked; it exists
  at `apply_records_edge_tests::persona_preference_erased_bank_dead_letters`).

**Do not trust `findings.json` resolutions without re-verifying them.** Those
two false claims were found by hand during the handoff, which means the
remediator wrote them. Assume more remain.

## 4. Two defects that are known-open — do not lose these

- **F-13 part 2 — item watermark can skip a row.** When a push page is not
  full, the cursor advances to the largest packaged close stamp, which sits
  above the rows' ordering stamps; the feed then resumes strictly after it. A
  row written after that query whose `created_at`/`updated_at` falls in the gap
  is never selected. This is reachable because bundle restore preserves an
  item's original timestamps, so a restore issued just after such a push lands
  below the cursor. Clamping the advance instead makes a post-dated discard
  re-send on every push, so neither bound is sufficient — the real fix is a
  resume key monotone with respect to insertion (the journal sequence the
  bank-level compound cursor already uses) instead of business time. That is a
  redesign, not a surgical change.
- **F-10 — restore re-derives the context effective time.** The store refuses a
  caller- or wire-supplied `context_as_of` so that sync apply cannot forge the
  stamp. Import therefore re-derives it from `created_at`, so a restored belief
  whose context was later corrected exposes the corrected context from creation
  time, where the source store returned none. Carrying the exported stamp
  instead would reopen the anti-forgery boundary across both backends.

Both are recorded in the phase file's Known Limitations. Decide each one
explicitly: fix it, or accept it in writing. Do not let it disappear behind a
completion marker.

## 5. Completing the phase honestly, step by step

Do this on the local machine, in this order. Each step is a real action with a
real artifact — no hand-written signals, no hand-written `run.json`, no
hand-edited ledger, no fabricated publication receipt.

1. **Sync and reconcile.**
   ```bash
   cd <public-repo-root>
   git fetch --all --prune && git status
   cd private/clio-private && git pull --rebase
   ```
2. **Review and merge [#28](https://github.com/heyaibi/clio/pull/28)** into
   `master`. Run the full gate set locally first: `make fmt`, `make lint`,
   `make test`, `make coverage`, and check the per-file 90% floors in the
   coverage output. Pay attention to review priority 1 in section 0 — the
   F-13 part 1 delivery-semantics change.
3. **Investigate on your own.** Re-derive the four findings' resolutions
   against the merged tree. Verify F-06 and F-13 part 1 yourself rather than
   trusting the account above. Confirm whether more untrue claims remain in
   `findings.json`.
4. **Take over the phase claim.** The reservation is held by `devserver` at
   generation 4, so a local run needs `--takeover`:
   ```bash
   cd <public-repo-root>
   CLIO_MACHINE_ID=<your-id> python3 private/clio-private/harness/runner.py \
     --pipeline private/clio-private/harness/pipelines/default.yaml \
     --input phase_number=100606 \
     --input phase_file=private/clio-private/roadmap/phase-100606-context-lifecycle-portability.md \
     --takeover
   ```
   Enter at the **`remediator`** step, not the approver. `resume.json` already
   points there, and the ledger's idempotency fallback will advance it to the
   approver. Resuming directly at the approver returns instantly without
   invoking anything, because the ledger already proves that step completed
   with a terminal routing.
5. **Let the remediator and approver run for real.** If the remediator produces
   a new round, re-check its prose claims before the approver sees them. If the
   approver approves, `finalize` runs automatically in the same process and
   publishes; that is the phase completing legitimately.
6. **If the approver rejects again**, do not raise the round cap to force it
   through. Read the grounds, fix the real cause, and re-run. Round 4 of 100606
   is capped out; a further attempt is a fresh operator decision.
7. **If the operator decides to accept the phase without a passing checker** —
   a legitimate choice, but it must be recorded as an operator decision, not as
   a machine verdict. Use the operator-owned roadmap artifacts:
   - tick `- [x] ... Required approval is obtained` in
     `roadmap/phase-100606-context-lifecycle-portability.md`, or
   - mark the phase `Complete` in `roadmap/index.md`.

   `next_phase.py` accepts either and prints a warning to stderr when a phase
   is indexed Complete without a machine marker. Never hand-write `run.json`,
   a `FINALIZE_DONE` ledger entry, a finalize log, or a completion receipt in
   `coordination/state.json` — a fabricated receipt carries commit SHAs that
   are false, and it permanently buries the two open defects in section 4.

## 6. Workflow state and the cron entry

The devserver driver state was left clean on purpose, so a cron tick or a
manual run is not blocked by a stale lock:

- `runs/.driver/driver.lock` — removed. `flock` is advisory and released when
  the holder dies, so the leftover file was harmless, but it is gone.
- No `halted`, `current`, `pid`, or `stalled` marker exists, so the driver is
  not refusing to advance.
- No `phase-driver.sh` or `runner.py` process is running.
- The cron entries on the devserver host are all commented out. Editing the
  crontab is not blocked by anything in this repository; cron keeps its own
  `/tmp/cron.<user>` lock only for the duration of a crontab write.

Before enabling a cron entry that can actually launch a phase, be aware of two
gaps found during the handoff:

- **The driver never passes `--takeover`.** It calls `runner.py` with only
  `--pipeline` and two `--input` pairs. Any phase whose reservation is stale
  or terminal therefore fails instead of recovering, which is what forced a
  manual bypass. Plumbing `--takeover` through the driver is the single most
  useful harness fix here.
- **`runs/.driver.env` does not exist**, so the driver uses built-in defaults
  and Discord notifications go nowhere. Start, halt and stall notices are
  therefore invisible.

## 7. Housekeeping already done upstream — do not redo

- `harness: retire the agy (Antigravity CLI) rotation entries` — no stage
  selects `agy` any more. (Relevant because the account was flagged for VPS
  use.)
- `harness: decide every stage's harness before the run starts`
- Phase 100720 completed upstream, so the pipeline is not wholly stalled on
  100606.

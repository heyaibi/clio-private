# Proposal: shared phase reservations for server and local work

Status: implemented; code-complete with deployment acceptance pending (2026-09-24). Date: 2026-09-24. Scope: phase ownership and selection. No product-code behavior changes.

## Problem

The server and a local operator can choose the same phase at the same time. The server's lock, terminal-session state, and process marker protect only that server. They do not protect against a second machine.

The phase selector already returns the lowest incomplete phase. Completing a future phase should not move the server past unfinished earlier phases. The missing control is shared ownership of each phase.

There is a second concurrency risk: different phases can still publish each other's partial run records or conflict in Git. A phase reservation prevents duplicate execution; it does not make arbitrary overlapping code changes safe.

## Proposal

Use the existing private repository's selected `master` branch as the shared
reservation board. The state path and transaction worktree are isolated from
phase working directories even though the branch is shared with private code:

```text
coordination/state.json
```

The state is never placed in the public repository. The selected answer for
this repository is `master` on the existing private repository; do not silently
switch to a different branch during deployment.

Each host has a stable machine ID:

```text
server-01
local-01
```

The machine ID identifies the owner in the reservation record. It is configuration, not a secret and not a special Unix command. The server entry point always selects the next phase; the local entry point always runs the exact phase named by the operator. No separate server/manual mode field is required.

Each individual reservation also receives a random `reservation_id`.

## State shape

A phase with no record is available. Records remain in the state after completion for audit history.

```json
{
  "version": 1,
  "phases": {
    "100440": {
      "status": "running",
      "machine_id": "server-01",
      "reservation_id": "rsv-abc123",
      "generation": 3,
      "claimed_at": "2026-09-24T10:00:00Z",
      "heartbeat_at": "2026-09-24T10:20:00Z",
      "expires_at": null,
      "run_id": "phase-100440",
      "base_revisions": {
        "public": "abc123",
        "private": "def456"
      }
    },
    "100601": {
      "status": "claimed",
      "machine_id": "local-01",
      "reservation_id": "rsv-def456",
      "generation": 1,
      "claimed_at": "2026-09-24T10:05:00Z",
      "heartbeat_at": "2026-09-24T10:05:00Z",
      "expires_at": null,
      "run_id": "phase-100601",
      "base_revisions": {
        "public": "abc123",
        "private": "def456"
      }
    }
  }
}
```

`expires_at` is retained as `null` for schema compatibility. The selected
policy has no automatic expiry; an operator must explicitly take over a
stopped claim.

Supported statuses are:

```text
claimed
running
paused
blocked
completed
rejected
```

A reservation is not completion evidence. Completion still requires the existing run, ledger, approval, or equivalent evidence. An active reservation takes precedence over a manually edited completion marker until the two sources are reconciled.

## Reservation protocol

To reserve a phase, a host:

1. Fetches the latest coordination branch.
2. Reads the current state.
3. Checks that the phase is available or already belongs to that same reservation.
4. Updates the record with its machine ID, random reservation ID, generation, and `expires_at: null`.
5. Commits the state.
6. Pushes the commit normally, without force.
7. Starts work only after the push succeeds.

If two hosts read the same old state, only one normal fast-forward push can win. The rejected host fetches the new state and retries. It must not overwrite the other reservation.

The coordination state path must not be used as a phase working file. State
updates use an isolated detached coordination checkout or an equivalent
temporary Git worktree, even though the selected branch is the shared private
`master` branch.

A separate small private coordination repository remains an acceptable alternative if branch permissions or history volume make the selected shared branch unsuitable. A GitHub Issue, a normal local file, and the server's local lock are not sufficient shared reservation mechanisms.

## Server behavior

The server must update its checkout and fetch the coordination state before selecting work.

The server then:

1. Finds the lowest incomplete phase using the existing ordering.
2. Attempts to reserve that exact phase.
3. Starts the run only if the reservation succeeds.
4. If the phase already has a live reservation, returns a distinct `WAIT_FOR_CLAIM` result and does not start it.

A future local reservation does not stop lower server work. If the local machine reserves `100601` while the server is working on `100440`, the server continues with `100460` and later phases.

When the server reaches `100601`:

- If it is completed, the server records that it was already completed and continues.
- If it is actively reserved, the server waits.
- If it is blocked or paused, the server does not silently take it over.

There is no global highest-completed-phase pointer and no server cursor derived from future local work.

## Recovery and fencing

An active process renews its reservation while it works. Under the selected
policy there is no automatic expiry: a crashed process leaves its claim in
place until an operator explicitly takes it over.

Each takeover increments `generation`. Every renewal, resume, completion, release, and publication operation must check:

```text
machine_id
reservation_id
generation
```

An older process that wakes up after its reservation was taken over must be rejected. A lease without this generation check is not sufficient.

Interrupted, blocked, and rejected work keeps its reservation. It is not silently released. An explicit operator takeover is required when an old owner may still be alive.

A phase becomes `completed` only after its work and completion evidence are safely published. The reservation must not be released before that point.

## Run-state and publication safety

Phase reservations solve same-phase duplication, not arbitrary multi-phase Git safety.

To keep different phases from publishing each other's work:

- Scope run-state cleanup and final publication to the current phase.
- Use a short publication lock around the final sync-and-push operation.
- Keep the existing fail-closed Git behavior: conflicts stop work and are never hidden by force-pushing, resetting, or discarding changes.
- Use separate worktrees or branches when concurrent phases may edit the same files.

A Git push by itself does not update files already checked out on the server. The first deployment of this proposal therefore needs a deliberate server update while the line is idle. After that, the server should refresh its checkout and coordination state before each idle selection. If refresh fails, it must not launch unclaimed work.

## Safety properties

- Two machines cannot hold the same live phase reservation.
- A future local completion never changes the server's lower-phase ordering.
- A stale owner cannot renew, resume, complete, or publish after takeover.
- A blocked or interrupted phase is not silently repeated by another machine.
- The server never falls back to unclaimed execution when coordination is unavailable.
- Private coordination state stays in the private repository.
- A reservation is never treated as proof that the phase completed.
- Different phases may still stop on Git conflicts; the system must fail clearly rather than publish ambiguous work.

## Acceptance

- Start two temporary clients from the same coordination state and prove that only one can reserve `100601`.
- Prove that the server can reserve `100440` while the local machine reserves `100601`.
- Complete `100601` locally and prove that the server still selects `100460` next.
- Prove that the server waits when it reaches an actively reserved phase.
- Treat a stopped reservation as stale, explicitly take it over, and prove that the old reservation ID and generation are rejected.
- Prove that an update or coordination-state push failure prevents an unclaimed launch.
- Prove that publication and run-state cleanup affect only the current phase.
- Run the existing selector, runner, driver, and synchronization self-tests.
- Verify the private `master` branch is not shallow and is protected from force-push, rewrite, and deletion.
- Perform a manual two-machine check with synthetic phases before enabling real manual reservations.

## Open questions

Q: Should the coordination state live on a dedicated branch in the existing private repository or in a separate private coordination repository?
A: master branch on the existing private repository

Q: How long should a machine's claim last before another machine may take it over, and how often should the active machine renew it while it works?
A: No automatic expiry

Q: Should the server ever defer a manually claimed phase, or should waiting remain the only safe default?
A: A server should ignore a phase claimed by other machine(s). 


Q: When two different phases finish at the same time, should they publish one after the other using a short shared lock, or should each finalizer use a claim-checking publish command that verifies ownership before pushing?
A: Each finalizer checks its own claim before publishing

Q: If a phase was already running before this reservation system was enabled, how should we mark it as belonging to the server and prevent anyone else from resuming it until the server finishes?
A: Register it as a server-owned claim

## Implementation record

Code-complete and automated checks verified on 2026-09-24; real two-machine deployment acceptance remains pending.

- `harness/phase_reservations.py` stores `coordination/state.json` on the private `master` branch through a detached temporary worktree. Claims use normal fast-forward pushes, random reservation IDs, machine/reservation/generation fencing, strict six-digit keys, and state-history continuity checks that reject deletion or shallow history.
- `next_phase.py --server` selects the lowest incomplete phase, ignores future claims until they become lowest, returns `WAIT_FOR_CLAIM` for an active owner, and fails closed when coordination is unavailable.
- The driver syncs both checkouts, reserves before launching tmux, and passes the claim to the runner. Direct local runs claim their exact phase. Interrupted, blocked, and rejected work keeps its claim; takeover is explicit because the selected policy has no automatic expiry.
- `runner.py` persists the phase-local reservation token, renews it while active, resumes only with the same fence, and requires the published `publication.json` receipt before changing the shared record to `completed`. Failed publication leaves a resumable blocked marker.
- `gitsync.py --mode publish --phase N` rechecks the claim, takes the short publication lock, scopes cleanup to `runs/phase-N`, verifies effective public/private push destinations, writes and pushes the completion receipt, syncs fail-closed, and pushes without force. The finalize stage uses this command instead of an unclaimed manual push.
- Automated checks cover two-client claim races, independent phase claims, real Git-backed lower-phase ordering, waiting, explicit takeover fencing and retry fencing, deleted/noncanonical state, shallow-history refusal, public pushurl boundaries, unavailable coordination, valid publication-lock contention, phase-scoped cleanup, phase-file binding, publication receipts, failed-publication recovery, portable driver locking, and the driver's real fail-closed coordination path. Temporary local-runner and publication smokes also passed with synthetic phases. The existing selector, driver, worker, and synchronization checks pass; the runner self-test passes with model-catalog checks marked unavailable because the host's OpenCode catalog command is broken, so deployment must resolve that environment exception separately.
- A real two-machine manual check with synthetic phases remains an operator acceptance action. The local two-client check uses temporary Git remotes only. Do not enable real manual reservations until that check and the first deliberate idle server checkout update are complete.


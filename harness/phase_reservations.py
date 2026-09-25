#!/usr/bin/env python3
# Copyright 2026 Agent Memoir Developers (https://agentmemoir.com/)
# SPDX-License-Identifier: Apache-2.0
"""Shared, fenced phase reservations backed by a private Git branch.

The coordination file is ``coordination/state.json`` in the nested private
repository.  The selected answer for this repository is the private
repository's ``master`` branch.  The branch is never checked out as a phase
working branch: every write uses a short-lived detached Git worktree and a
normal, non-forced push.  A rejected push is retried from a fresh fetch, so
one of two clients can win a claim without overwriting the other.

A reservation is an ownership record, not completion evidence. The pipeline
must publish the current phase and a matching ``publication.json`` receipt
before the record can change to ``completed``.

The module is intentionally usable both as a library and as a small CLI.
The CLI is useful for registering a phase that was already running before
coordination was enabled, and for explicit operator takeover when a process
has stopped without releasing its claim.
"""

import argparse
import contextlib
import datetime as _datetime
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
from pathlib import Path


PRIVATE_REL = Path("private") / "clio-private"
STATE_REL = Path("coordination") / "state.json"
DEFAULT_BRANCH = "master"
DEFAULT_REMOTE = "origin"
COORDINATION_VERSION = 1
STATUSES = frozenset({
    "claimed", "running", "paused", "blocked", "completed", "rejected",
    "accepted",
})
ACTIVE_STATUSES = frozenset({"claimed", "running", "paused", "blocked"})
# "completed" means the pipeline's finalize step published the phase.
# "accepted" means an operator closed it deliberately, without a passing
# checker, and recorded that decision in the phase file. It is terminal for
# the same reason, but it must never require a publication receipt: finalize
# did not run, so no receipt with real commit SHAs exists to point at.
TERMINAL_STATUSES = frozenset({"completed", "rejected", "accepted"})
MAX_TRANSACTION_ATTEMPTS = 4
GIT_TIMEOUT_S = 60
FETCH_TIMEOUT_S = 180
MACHINE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
BRANCH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,127}$")
REMOTE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
RESERVATION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
PHASE_KEY_RE = re.compile(r"^[0-9]{6}$")
PUBLICATION_NAME = "publication.json"


class CoordinationError(Exception):
    """Base class for errors that must prevent unclaimed work."""


class CoordinationUnavailable(CoordinationError):
    """The coordination branch could not be fetched, read, or pushed."""


class ReservationConflict(CoordinationError):
    """Another owner, or another reservation, already owns the phase."""

    def __init__(self, phase, record=None, reason="phase is already reserved"):
        self.phase = phase
        self.record = record or {}
        self.reason = reason
        owner = self.record.get("machine_id", "unknown")
        status = self.record.get("status", "unknown")
        super().__init__(
            f"phase {phase} is unavailable ({self.reason}; "
            f"owner={owner}, status={status})")


class ReservationFenced(CoordinationError):
    """The caller's machine, reservation, or generation is stale."""


class PublicationBusy(CoordinationError):
    """Another phase currently owns the short publication lock."""


class _Mutation:
    def __init__(self, changed, value):
        self.changed = changed
        self.value = value


def _now():
    return _datetime.datetime.now(_datetime.timezone.utc).isoformat(
        timespec="milliseconds").replace("+00:00", "Z")


def _phase_key(phase):
    try:
        if isinstance(phase, bool):
            raise ValueError
        number = int(phase)
    except (TypeError, ValueError):
        raise CoordinationError(f"invalid phase number: {phase!r}") from None
    if number < 0 or number > 999999:
        raise CoordinationError(f"phase number out of range: {number}")
    return f"{number:06d}", number


def _validate_machine_id(machine_id):
    if not isinstance(machine_id, str) or not MACHINE_ID_RE.fullmatch(machine_id):
        raise CoordinationError(
            "machine_id must contain only letters, numbers, '.', '_' or '-' "
            "and be at most 128 characters")
    return machine_id


def _validate_branch(branch):
    if (not isinstance(branch, str) or not BRANCH_RE.fullmatch(branch)
            or ".." in branch or "//" in branch or branch.endswith("/")):
        raise CoordinationError(f"invalid coordination branch: {branch!r}")
    return branch


def _validate_remote(remote):
    if not isinstance(remote, str) or not REMOTE_RE.fullmatch(remote):
        raise CoordinationError(f"invalid Git remote: {remote!r}")
    return remote


def _validate_reservation_id(reservation_id):
    if not isinstance(reservation_id, str) \
            or not RESERVATION_ID_RE.fullmatch(reservation_id):
        raise CoordinationError(
            "reservation_id must contain only letters, numbers, '.', '_' or "
            "'-' and be at most 128 characters")
    return reservation_id


def _validate_generation(generation):
    if isinstance(generation, bool) or not isinstance(generation, int) \
            or generation < 1:
        raise CoordinationError("generation must be a positive integer")
    return generation


def _validate_status(status):
    if status not in STATUSES:
        raise CoordinationError(f"invalid reservation status: {status!r}")
    return status


def _safe_detail(text, limit=500):
    """Keep diagnostics useful without echoing a credential-bearing URL."""
    text = (text or "").replace("\n", " ").strip()
    text = re.sub(r"(https?://)[^/@\s]+@", r"\1<redacted>@", text)
    return text[:limit]


def _git(repo, *args, timeout=GIT_TIMEOUT_S):
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True, text=True, timeout=timeout, env=env,
        )
    except FileNotFoundError as exc:
        raise CoordinationUnavailable("git is not on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise CoordinationUnavailable(
            f"git {' '.join(args)} timed out after {timeout}s") from exc
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def _is_git_repo(path):
    rc, out, _ = _git(path, "rev-parse", "--is-inside-work-tree")
    return rc == 0 and out == "true"


def _remote_urls(repo, remote, *, push=False):
    args = ["remote", "get-url"]
    if push:
        args.append("--push")
    args.extend(["--all", remote])
    rc, out, err = _git(repo, *args)
    if rc != 0:
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def _canonical_remote_url(value):
    value = (value or "").strip()
    if not value:
        return ""
    if "://" not in value and not re.match(r"^[^/]+@[^:]+:", value):
        return str(Path(value).expanduser().resolve())
    parsed = urllib.parse.urlsplit(value)
    if not parsed.scheme:
        return value
    return urllib.parse.urlunsplit((
        parsed.scheme.lower(),
        parsed.netloc.lower(),
        parsed.path.rstrip("/") or "/",
        parsed.query,
        parsed.fragment,
    ))


def _remote_url_sets(root, private, remote):
    public_fetch = {
        _canonical_remote_url(url)
        for url in _remote_urls(root, remote)
    }
    public_push = {
        _canonical_remote_url(url)
        for url in _remote_urls(root, remote, push=True)
    }
    private_fetch = {
        _canonical_remote_url(url)
        for url in _remote_urls(private, remote)
    }
    private_push = {
        _canonical_remote_url(url)
        for url in _remote_urls(private, remote, push=True)
    }
    return public_fetch, public_push, private_fetch, private_push


def _assert_private_boundary(root, private, remote):
    public_is_repo = _is_git_repo(root)
    if not public_is_repo:
        return
    public_fetch, public_push, private_fetch, private_push = _remote_url_sets(
        root, private, remote)
    if not public_fetch or not public_push or not private_fetch or not private_push:
        raise CoordinationUnavailable(
            "cannot prove separate public/private Git destinations")
    if public_push & private_push or public_push & private_fetch \
            or public_fetch & private_push:
        raise CoordinationUnavailable(
            "public and private repositories share a Git push/fetch destination")


def _head(repo):
    rc, out, _ = _git(repo, "rev-parse", "HEAD")
    return out if rc == 0 and out else None


def _empty_state():
    return {"version": COORDINATION_VERSION, "phases": {}}


def _validate_state(state):
    if not isinstance(state, dict):
        raise CoordinationUnavailable("coordination state is not an object")
    if state.get("version") != COORDINATION_VERSION:
        raise CoordinationUnavailable(
            f"unsupported coordination state version: {state.get('version')!r}")
    phases = state.get("phases")
    if not isinstance(phases, dict):
        raise CoordinationUnavailable("coordination state.phases is not an object")
    for key, record in phases.items():
        if not isinstance(key, str) or not PHASE_KEY_RE.fullmatch(key):
            raise CoordinationUnavailable(f"invalid phase key in state: {key!r}")
        if not isinstance(record, dict):
            raise CoordinationUnavailable(f"phase {key} record is not an object")
        for field in ("status", "machine_id", "reservation_id"):
            if not isinstance(record.get(field), str) or not record[field]:
                raise CoordinationUnavailable(
                    f"phase {key} has an invalid {field}")
        _validate_machine_id(record["machine_id"])
        _validate_reservation_id(record["reservation_id"])
        _validate_status(record["status"])
        _validate_generation(record.get("generation"))
        for field in ("claimed_at", "heartbeat_at", "expires_at", "run_id"):
            if field in record and record[field] is not None \
                    and not isinstance(record[field], str):
                raise CoordinationUnavailable(
                    f"phase {key} has an invalid {field}")
        if "base_revisions" in record and not isinstance(
                record["base_revisions"], dict):
            raise CoordinationUnavailable(
                f"phase {key} has invalid base_revisions")
    publication = state.get("publication")
    if publication is not None:
        if not isinstance(publication, dict):
            raise CoordinationUnavailable("publication lock is not an object")
        for field in ("machine_id", "reservation_id", "phase", "generation"):
            if field not in publication:
                raise CoordinationUnavailable(
                    f"publication lock is missing {field}")
        _validate_machine_id(publication["machine_id"])
        _validate_reservation_id(publication["reservation_id"])
        _phase_key(publication["phase"])
        _validate_generation(publication["generation"])
    return state


def _read_state_file(path, *, allow_missing=True):
    try:
        raw = path.read_text()
    except FileNotFoundError:
        if allow_missing:
            return _empty_state()
        raise CoordinationUnavailable("coordination state file is missing")
    except OSError as exc:
        raise CoordinationUnavailable(
            f"cannot read coordination state: {exc}") from exc
    try:
        state = json.loads(raw)
    except ValueError as exc:
        raise CoordinationUnavailable(
            f"coordination state does not parse: {exc}") from exc
    return _validate_state(state)


def _write_state_file(path, state):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def _owner_matches(record, machine_id, reservation_id, generation):
    return (record.get("machine_id") == machine_id
            and record.get("reservation_id") == reservation_id
            and record.get("generation") == generation)


def _reservation_from_record(record):
    return {
        "phase": str(record.get("_phase", "")),
        "status": record.get("status"),
        "machine_id": record.get("machine_id"),
        "reservation_id": record.get("reservation_id"),
        "generation": record.get("generation"),
        "run_id": record.get("run_id"),
        "base_revisions": record.get("base_revisions"),
    }


def _branch_from_env(branch):
    return _validate_branch(branch or os.environ.get(
        "CLIO_PHASE_COORDINATION_BRANCH", DEFAULT_BRANCH))


def _remote_from_env(remote):
    return _validate_remote(remote or os.environ.get(
        "CLIO_PHASE_COORDINATION_REMOTE", DEFAULT_REMOTE))


def _resolve_private_repo(repo_root, private_repo=None):
    root = Path(repo_root).resolve()
    private = Path(private_repo).resolve() if private_repo else root / PRIVATE_REL
    if not private.is_dir() or not _is_git_repo(private):
        raise CoordinationUnavailable(
            f"private coordination repository is unavailable: {private}")
    return root, private


def _fetch_ref(private, remote, branch):
    remote_ref = f"refs/remotes/{remote}/{branch}"
    refspec = f"+refs/heads/{branch}:{remote_ref}"
    rc, out, err = _git(
        private, "fetch", "--prune", remote, refspec, timeout=FETCH_TIMEOUT_S)
    if rc != 0:
        raise CoordinationUnavailable(
            f"coordination fetch failed: {_safe_detail(err or out)}")
    rc, commit, err = _git(private, "rev-parse", "--verify", remote_ref)
    if rc != 0 or not commit:
        raise CoordinationUnavailable(
            f"coordination branch {branch!r} does not exist on {remote}")
    return remote_ref, commit


def _state_initialized(private, ref):
    shallow_rc, shallow_out, _shallow_err = _git(
        private, "rev-parse", "--is-shallow-repository")
    if shallow_rc == 0 and shallow_out.strip() == "true":
        raise CoordinationUnavailable(
            "coordination state history is unavailable in a shallow repository")
    rc, out, err = _git(
        private, "log", "--diff-filter=A", "--format=%H", "-n", "1",
        ref, "--", STATE_REL.as_posix())
    if rc != 0:
        raise CoordinationUnavailable(
            f"cannot inspect coordination state history: {_safe_detail(err or out)}")
    return bool(out.strip())


@contextlib.contextmanager
def _detached_worktree(private, ref):
    """Yield a disposable checkout without taking the phase branch."""
    parent = Path(tempfile.mkdtemp(prefix="clio-phase-coordination-"))
    checkout = parent / "checkout"
    rc, _, err = _git(
        private, "worktree", "add", "--detach", str(checkout), ref)
    if rc != 0:
        shutil.rmtree(parent, ignore_errors=True)
        raise CoordinationUnavailable(
            f"cannot create coordination worktree: {_safe_detail(err)}")
    try:
        yield checkout
    finally:
        # The path is created and owned by this function. Removing it must
        # not touch the phase checkout, even when its branch is named master.
        # A clean coordination worktree needs no force; if an error left it
        # dirty, leave it for inspection rather than discarding changes.
        rc, _, _ = _git(private, "worktree", "remove", str(checkout))
        if rc == 0:
            shutil.rmtree(parent, ignore_errors=True)


def _commit_state(checkout, message):
    rc, _, err = _git(checkout, "add", "--", STATE_REL.as_posix())
    if rc != 0:
        raise CoordinationUnavailable(
            f"cannot stage coordination state: {_safe_detail(err)}")
    rc, out, err = _git(checkout, "commit", "-q", "-m", message)
    if rc != 0:
        combined = _safe_detail(f"{out} {err}")
        if "nothing to commit" in combined.lower():
            return None
        raise CoordinationUnavailable(
            f"coordination state commit failed: {combined}")
    rc, commit, _ = _git(checkout, "rev-parse", "HEAD")
    if rc != 0 or not commit:
        raise CoordinationUnavailable("coordination commit has no revision")
    return commit


def _transaction(private, remote, branch, mutate, message):
    """Run a read-modify-push transaction, retrying only rejected pushes."""
    last_error = None
    for _attempt in range(MAX_TRANSACTION_ATTEMPTS):
        ref, _commit = _fetch_ref(private, remote, branch)
        initialized = _state_initialized(private, ref)
        with _detached_worktree(private, ref) as checkout:
            state = _read_state_file(
                checkout / STATE_REL, allow_missing=not initialized)
            mutation = mutate(state)
            if not mutation.changed:
                return mutation.value
            _write_state_file(checkout / STATE_REL, state)
            new_commit = _commit_state(checkout, message)
            if new_commit is None:
                return mutation.value
            rc, out, err = _git(
                checkout, "push", remote, f"HEAD:refs/heads/{branch}",
                timeout=FETCH_TIMEOUT_S)
        if rc == 0:
            return mutation.value
        last_error = _safe_detail(f"{out} {err}")
    raise CoordinationUnavailable(
        f"coordination state push failed after retries: {last_error or 'unknown error'}")


def _base_revisions(root, private):
    public = _head(root) if _is_git_repo(root) else None
    private_revision = _head(private)
    return {"public": public, "private": private_revision}


class ReservationStore:
    """Read and mutate the shared reservation state for one repository."""

    def __init__(self, repo_root, private_repo=None, branch=None, remote=None):
        self.root, self.private = _resolve_private_repo(repo_root, private_repo)
        self.branch = _branch_from_env(branch)
        self.remote = _remote_from_env(remote)
        _assert_private_boundary(self.root, self.private, self.remote)

    def read(self):
        ref, commit = _fetch_ref(self.private, self.remote, self.branch)
        initialized = _state_initialized(self.private, ref)
        exists_rc, _, _ = _git(
            self.private, "cat-file", "-e", f"{ref}:{STATE_REL.as_posix()}")
        if exists_rc != 0:
            if initialized:
                raise CoordinationUnavailable(
                    "coordination state file was deleted from an initialized board")
            # A board may be initialized before its first claim. The commit
            # must exist, but an absent state file is an empty state.
            return _empty_state(), commit
        rc, raw, err = _git(self.private, "show", f"{ref}:{STATE_REL.as_posix()}")
        if rc != 0:
            raise CoordinationUnavailable(
                f"cannot read coordination state: {_safe_detail(err or raw)}")
        try:
            state = json.loads(raw)
        except ValueError as exc:
            raise CoordinationUnavailable(
                f"coordination state does not parse: {exc}") from exc
        return _validate_state(state), commit

    def _reserve_mutation(self, phase, machine_id, reservation_id, generation,
                          run_id, revisions, status):
        key, number = _phase_key(phase)
        machine_id = _validate_machine_id(machine_id)
        _validate_status(status)
        if status not in ACTIVE_STATUSES:
            raise CoordinationError("a new reservation must start as active")

        def mutate(state):
            existing = state["phases"].get(key)
            if existing is not None:
                if existing.get("status") in TERMINAL_STATUSES:
                    raise ReservationConflict(
                        number, existing,
                        f"phase is retained as {existing.get('status')}")
                if _owner_matches(existing, machine_id, reservation_id, generation):
                    existing["status"] = status
                    existing["heartbeat_at"] = _now()
                    return _Mutation(True, _reservation_from_record(
                        {**existing, "_phase": key}))
                raise ReservationConflict(number, existing)
            record = {
                "status": status,
                "machine_id": machine_id,
                "reservation_id": reservation_id,
                "generation": generation,
                "claimed_at": _now(),
                "heartbeat_at": _now(),
                # The selected answer is no automatic expiry.  Keep the
                # field for audit/tool compatibility, but never use it to
                # take over a live claim.
                "expires_at": None,
                "run_id": run_id or f"phase-{key}",
                "base_revisions": revisions,
            }
            state["phases"][key] = record
            return _Mutation(True, _reservation_from_record(
                {**record, "_phase": key}))

        return mutate

    def reserve(self, phase, machine_id, *, reservation_id=None, generation=None,
                run_id=None, base_revisions=None, status="claimed"):
        key, number = _phase_key(phase)
        machine_id = _validate_machine_id(machine_id)
        reservation_id = reservation_id or f"rsv-{secrets.token_hex(12)}"
        _validate_reservation_id(reservation_id)
        generation = generation if generation is not None else 1
        _validate_generation(generation)
        revisions = base_revisions or _base_revisions(self.root, self.private)
        mutate = self._reserve_mutation(
            number, machine_id, reservation_id, generation,
            run_id or f"phase-{key}", revisions, status)
        return _transaction(
            self.private, self.remote, self.branch, mutate,
            f"phase coordination: reserve {key} for {machine_id}")

    def _owned_mutation(self, reservation, next_status=None,
                        evidence_path=None, accepted_reason=None):
        if not isinstance(reservation, dict):
            raise CoordinationError("reservation must be an object")
        machine_id = _validate_machine_id(reservation.get("machine_id"))
        reservation_id = _validate_reservation_id(
            reservation.get("reservation_id"))
        generation = _validate_generation(reservation.get("generation"))
        phase = reservation.get("phase")
        key, _number = _phase_key(phase)
        if next_status is not None:
            next_status = _validate_status(next_status)
        if next_status == "accepted":
            # An operator close-out is a decision, not a machine verdict, and
            # the next operator needs to know which it was. Refuse to record
            # the status without the justification.
            if not isinstance(accepted_reason, str) or not accepted_reason.strip():
                raise CoordinationError(
                    "accepted requires --accept-reason saying why the operator "
                    "closed the phase without a passing checker")
            if len(accepted_reason) > 2000:
                raise CoordinationError("accepted reason is longer than 2000 characters")
        elif accepted_reason is not None:
            raise CoordinationError(
                "an acceptance reason is only valid for accepted status")
        receipt = None
        if next_status == "completed":
            if evidence_path is None:
                raise CoordinationError(
                    "completed requires a published completion receipt")
            receipt = _validate_publication_receipt(
                evidence_path, reservation, self.private, self.remote, self.branch)
        elif evidence_path is not None:
            raise CoordinationError(
                "publication receipts are only valid for completed status")

        def mutate(state):
            record = state["phases"].get(key)
            if record is None:
                raise ReservationFenced(
                    f"phase {key} has no current reservation")
            if not _owner_matches(record, machine_id, reservation_id, generation):
                raise ReservationFenced(
                    f"phase {key} reservation is fenced by a newer owner")
            if record.get("status") in TERMINAL_STATUSES:
                if next_status == record.get("status"):
                    return _Mutation(False, _reservation_from_record(
                        {**record, "_phase": key}))
                raise ReservationFenced(
                    f"phase {key} is already {record.get('status')}")
            if next_status is not None:
                record["status"] = next_status
            if next_status == "accepted":
                record["accepted_reason"] = accepted_reason.strip()
                record["accepted_at"] = _now()
            if receipt is not None:
                record["completion_receipt"] = receipt
            record["heartbeat_at"] = _now()
            return _Mutation(True, _reservation_from_record(
                {**record, "_phase": key}))

        return mutate

    def renew(self, reservation, status=None):
        mutate = self._owned_mutation(reservation, status)
        return _transaction(
            self.private, self.remote, self.branch, mutate,
            f"phase coordination: renew {reservation['phase']}")

    def set_status(self, reservation, status, *, evidence_path=None,
                   accepted_reason=None):
        mutate = self._owned_mutation(
            reservation, status, evidence_path=evidence_path,
            accepted_reason=accepted_reason)
        return _transaction(
            self.private, self.remote, self.branch, mutate,
            f"phase coordination: {status} {reservation['phase']}")

    def assert_owner(self, reservation):
        """Fetch the latest board and verify the three-part fence."""
        if not isinstance(reservation, dict):
            raise CoordinationError("reservation must be an object")
        key, _number = _phase_key(reservation.get("phase"))
        state, _commit = self.read()
        record = state["phases"].get(key)
        if record is None or not _owner_matches(
                record, reservation.get("machine_id"),
                reservation.get("reservation_id"), reservation.get("generation")):
            raise ReservationFenced(
                f"phase {key} is no longer owned by this reservation")
        if record.get("status") in TERMINAL_STATUSES:
            return dict(record)
        return dict(record)

    def takeover(self, phase, machine_id, *, confirm=False, run_id=None,
                 base_revisions=None, expected_reservation_id=None,
                 expected_generation=None):
        if not confirm:
            raise CoordinationError(
                "explicit operator takeover requires confirm=true")
        if expected_reservation_id is None or expected_generation is None:
            raise CoordinationError(
                "takeover requires the expected old reservation ID and generation")
        key, number = _phase_key(phase)
        machine_id = _validate_machine_id(machine_id)
        new_id = f"rsv-{secrets.token_hex(12)}"
        revisions = base_revisions or _base_revisions(self.root, self.private)
        current_state, _current_commit = self.read()
        current = current_state["phases"].get(key)
        if current is None:
            raise ReservationConflict(number, reason="phase has no claim")
        if expected_reservation_id is not None:
            expected_reservation_id = _validate_reservation_id(
                expected_reservation_id)
        if expected_generation is not None:
            expected_generation = _validate_generation(expected_generation)
        if ((expected_reservation_id is not None
             and current.get("reservation_id") != expected_reservation_id)
                or (expected_generation is not None
                    and current.get("generation") != expected_generation)):
            raise ReservationFenced(
                f"phase {key} changed; inspect the current owner before retrying")
        expected_generation = _validate_generation(current.get("generation"))
        expected_reservation_id = current.get("reservation_id")

        def mutate(state):
            old = state["phases"].get(key)
            if old is None:
                raise ReservationConflict(number, reason="phase has no claim")
            if (old.get("machine_id") == machine_id
                    and old.get("reservation_id") == new_id):
                return _Mutation(False, _reservation_from_record(
                    {**old, "_phase": key}))
            if (old.get("generation") != expected_generation
                    or old.get("reservation_id") != expected_reservation_id):
                raise ReservationFenced(
                    f"phase {key} changed before takeover could commit")
            publication = state.get("publication")
            if publication is not None:
                raise PublicationBusy(
                    "cannot take over a phase while its publication lock is held")
            if old.get("status") == "completed":
                raise ReservationConflict(
                    number, old, "completed reservations cannot be taken over")
            new = {
                "status": "claimed",
                "machine_id": machine_id,
                "reservation_id": new_id,
                "generation": _validate_generation(old.get("generation")) + 1,
                "claimed_at": _now(),
                "heartbeat_at": _now(),
                "expires_at": None,
                "run_id": run_id or f"phase-{key}",
                "base_revisions": revisions,
            }
            state["phases"][key] = new
            return _Mutation(True, _reservation_from_record(
                {**new, "_phase": key}))

        return _transaction(
            self.private, self.remote, self.branch, mutate,
            f"phase coordination: explicit takeover {key} by {machine_id}")

    def register_running(self, phase, machine_id, *, confirm=False, run_id=None):
        """Register a pre-coordination run as an active server claim."""
        if not confirm:
            raise CoordinationError(
                "registering a running phase requires confirm=true")
        return self.reserve(
            phase, machine_id, run_id=run_id, status="running")

    def acquire_publication(self, reservation):
        key, _number = _phase_key(reservation.get("phase"))
        machine_id = _validate_machine_id(reservation.get("machine_id"))
        reservation_id = _validate_reservation_id(
            reservation.get("reservation_id"))
        generation = _validate_generation(reservation.get("generation"))

        def mutate(state):
            record = state["phases"].get(key)
            if record is None or not _owner_matches(
                    record, machine_id, reservation_id, generation):
                raise ReservationFenced(
                    f"phase {key} is no longer owned by this reservation")
            if record.get("status") in TERMINAL_STATUSES:
                raise ReservationFenced(
                    f"phase {key} is already {record.get('status')}")
            current = state.get("publication")
            wanted = {
                "phase": key,
                "machine_id": machine_id,
                "reservation_id": reservation_id,
                "generation": generation,
                "acquired_at": _now(),
            }
            if current is not None:
                same = (current.get("phase") == key
                        and current.get("machine_id") == machine_id
                        and current.get("reservation_id") == reservation_id
                        and current.get("generation") == generation)
                if not same:
                    raise PublicationBusy(
                        f"publication lock is held by phase "
                        f"{current.get('phase', '?')}")
                return _Mutation(False, current)
            state["publication"] = wanted
            return _Mutation(True, wanted)

        return _transaction(
            self.private, self.remote, self.branch, mutate,
            f"phase coordination: publication lock {key}")

    def release_publication(self, reservation):
        key, _number = _phase_key(reservation.get("phase"))
        machine_id = _validate_machine_id(reservation.get("machine_id"))
        reservation_id = _validate_reservation_id(
            reservation.get("reservation_id"))
        generation = _validate_generation(reservation.get("generation"))

        def mutate(state):
            current = state.get("publication")
            if current is None:
                return _Mutation(False, None)
            same = (current.get("phase") == key
                    and current.get("machine_id") == machine_id
                    and current.get("reservation_id") == reservation_id
                    and current.get("generation") == generation)
            if not same:
                raise ReservationFenced("publication lock belongs to another phase")
            del state["publication"]
            return _Mutation(True, None)

        return _transaction(
            self.private, self.remote, self.branch, mutate,
            f"phase coordination: release publication lock {key}")


def reservation_file(repo_root, phase, private_repo=None):
    """Return the phase-local token path inside the private checkout."""
    key, _number = _phase_key(phase)
    root = Path(repo_root).resolve()
    private = (Path(private_repo).resolve() if private_repo
               else root / PRIVATE_REL)
    return private / "runs" / f"phase-{key}" / "reservation.json"


def publication_file(repo_root, phase):
    """Return the published completion receipt path for a phase."""
    key, _number = _phase_key(phase)
    root = Path(repo_root).resolve()
    return root / PRIVATE_REL / "runs" / f"phase-{key}" / PUBLICATION_NAME


def _receipt_commit(value, field):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-fA-F]{40,64}", value):
        raise CoordinationError(f"publication receipt has invalid {field}")
    return value.lower()


def _validate_publication_receipt(path, reservation, private_repo, remote, branch):
    path = Path(path).resolve()
    key, _number = _phase_key(reservation.get("phase"))
    expected = (Path(private_repo).resolve() / "runs" / f"phase-{key}"
                / PUBLICATION_NAME).resolve()
    if path != expected:
        raise CoordinationError("publication receipt is outside the phase run directory")
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise CoordinationError(
            f"publication receipt cannot be read: {exc}") from exc
    if not isinstance(data, dict) or data.get("version") != 1 \
            or data.get("state") != "published":
        raise CoordinationError("publication receipt is not a published receipt")
    if data.get("phase") != key:
        raise CoordinationError("publication receipt phase does not match reservation")
    owner = data.get("reservation")
    if not isinstance(owner, dict) or any(
            owner.get(field) != reservation.get(field)
            for field in ("machine_id", "reservation_id", "generation")):
        raise CoordinationError("publication receipt does not match reservation")
    for field in ("public_commit", "private_commit"):
        _receipt_commit(data.get(field), field)
    if not isinstance(data.get("published_at"), str) or not data["published_at"]:
        raise CoordinationError("publication receipt has no publication time")
    ref, _commit = _fetch_ref(private_repo, remote, branch)
    rel = expected.relative_to(Path(private_repo).resolve()).as_posix()
    rc, raw, err = _git(private_repo, "show", f"{ref}:{rel}")
    if rc != 0:
        raise CoordinationUnavailable(
            f"publication receipt is not present on the private remote: {_safe_detail(err or raw)}")
    try:
        remote_data = json.loads(raw)
    except ValueError as exc:
        raise CoordinationUnavailable(
            "remote publication receipt does not parse") from exc
    if remote_data != data:
        raise CoordinationUnavailable(
            "local and remote publication receipts differ")
    return {
        "path": str(path),
        "public_commit": data["public_commit"].lower(),
        "private_commit": data["private_commit"].lower(),
        "published_at": data["published_at"],
    }


def save_reservation_file(path, reservation):
    """Persist the fence token before a phase process is launched."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "phase": reservation["phase"],
        "machine_id": reservation["machine_id"],
        "reservation_id": reservation["reservation_id"],
        "generation": reservation["generation"],
        "run_id": reservation.get("run_id"),
    }
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)
    return payload


def load_reservation_file(path):
    try:
        data = json.loads(Path(path).read_text())
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        raise CoordinationError(f"reservation file is unreadable: {exc}") from exc
    if not isinstance(data, dict):
        raise CoordinationError("reservation file is not an object")
    for field in ("phase", "machine_id", "reservation_id", "generation"):
        if field not in data:
            raise CoordinationError(f"reservation file is missing {field}")
    _validate_machine_id(data["machine_id"])
    _validate_reservation_id(data["reservation_id"])
    _validate_generation(data["generation"])
    return data


def reservation_from_environment(phase, environ=None):
    """Read a driver-provided reservation without treating it as authority."""
    environ = os.environ if environ is None else environ
    rid = environ.get("CLIO_RESERVATION_ID")
    generation = environ.get("CLIO_RESERVATION_GENERATION")
    if not rid and not generation:
        return None
    if not rid or generation is None:
        raise CoordinationError(
            "CLIO_RESERVATION_ID and CLIO_RESERVATION_GENERATION must be set together")
    try:
        generation = int(generation)
    except ValueError as exc:
        raise CoordinationError("CLIO_RESERVATION_GENERATION is not an integer") from exc
    return {
        "phase": _phase_key(phase)[0],
        "machine_id": environ.get("CLIO_MACHINE_ID", "local-01"),
        "reservation_id": _validate_reservation_id(rid),
        "generation": _validate_generation(generation),
    }


def _print_json(value):
    print(json.dumps(value, indent=2, sort_keys=True))


def _cli_store(args):
    return ReservationStore(
        args.repo_root, private_repo=args.private_repo,
        branch=args.branch, remote=args.remote)


def _self_test_check(checks, name, ok, detail=""):
    checks.append({"check": name, "ok": bool(ok), "detail": detail})


def _git_test_repo(base, name, initial_state=None):
    """Create one local bare remote and one client checkout for self-tests."""
    remote = base / f"{name}-remote.git"
    subprocess.run(["git", "init", "--bare", "-q", str(remote)], check=True,
                   capture_output=True, text=True)
    _git(remote, "symbolic-ref", "HEAD", "refs/heads/master")
    seed = base / f"{name}-seed"
    subprocess.run(["git", "clone", "-q", str(remote), str(seed)], check=True,
                   capture_output=True, text=True)
    _git(seed, "config", "user.email", "coordination-test@example.com")
    _git(seed, "config", "user.name", "coordination test")
    _git(seed, "checkout", "-q", "-b", "master")
    (seed / "seed.txt").write_text("seed\n")
    if initial_state is not None:
        _write_state_file(seed / STATE_REL, initial_state)
    _git(seed, "add", ".")
    _git(seed, "commit", "-q", "-m", "coordination seed")
    _git(seed, "push", "-q", "-u", "origin", "master")
    clients = []
    for index in (1, 2):
        client = base / f"{name}-client-{index}"
        subprocess.run(["git", "clone", "-q", str(remote), str(client)], check=True,
                       capture_output=True, text=True)
        _git(client, "config", "user.email", "coordination-test@example.com")
        _git(client, "config", "user.name", "coordination test")
        clients.append(client)
    return remote, clients


def self_test_checks():
    """Exercise the shared board with two local clients; no network or repo state."""
    import threading

    checks = []
    base = Path(tempfile.mkdtemp(prefix="phase-reservations-selftest-"))
    try:
        remote, clients = _git_test_repo(base, "claims")
        # Each store owns a different real client checkout. The public side
        # is intentionally absent in this hermetic check; the private repo is
        # the only remote that can receive coordination state.
        root_a = base / "root-a"
        root_b = base / "root-b"
        root_a.mkdir()
        root_b.mkdir()
        store_a = ReservationStore(root_a, private_repo=clients[0])
        store_b = ReservationStore(root_b, private_repo=clients[1])

        barrier = threading.Barrier(2)
        results = []
        errors = []

        def claim(store, machine):
            barrier.wait()
            try:
                results.append(store.reserve(100601, machine))
            except Exception as exc:  # noqa: BLE001 - test records the failure
                errors.append(exc)

        threads = [
            threading.Thread(target=claim, args=(store_a, "server-01")),
            threading.Thread(target=claim, args=(store_b, "local-01")),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        _self_test_check(checks, "two clients race: one reservation wins",
                         len(results) == 1 and len(errors) == 1
                         and isinstance(errors[0], ReservationConflict),
                         f"results={len(results)} errors={[type(e).__name__ for e in errors]}")

        state, _commit = store_a.read()
        first = state["phases"].get("100601")
        _self_test_check(checks, "winning record is complete",
                         bool(first and first.get("reservation_id")
                              and first.get("generation") == 1
                              and first.get("machine_id") in {"server-01", "local-01"}),
                         str(first))

        # The winner can renew/complete; a second phase can be reserved at the
        # same time without changing the first phase's ordering.
        winner_machine = first["machine_id"]
        winner = {"phase": "100601", "machine_id": winner_machine,
                  "reservation_id": first["reservation_id"],
                  "generation": first["generation"]}
        store_a.renew(winner)
        try:
            store_a.set_status(winner, "completed")
            receipt_required = False
        except CoordinationError:
            receipt_required = True
        _self_test_check(checks, "completion requires a published receipt",
                         receipt_required, "missing receipt refused")
        receipt = _self_test_receipt(store_a, winner)
        store_a.set_status(winner, "completed", evidence_path=receipt)
        store_a.set_status(winner, "completed", evidence_path=receipt)
        other = store_b.reserve(100440, "server-01")
        _self_test_check(checks, "different phases can be reserved independently",
                         other["phase"] == "100440", str(other))

        # No automatic expiry: an old record remains fenced until the explicit
        # operator takeover increments its generation.
        old = store_a.reserve(100602, "local-01")
        replacement = store_a.takeover(
            100602, "server-01", confirm=True,
            expected_reservation_id=old["reservation_id"],
            expected_generation=old["generation"])
        try:
            store_a.renew(old)
            fenced = False
        except ReservationFenced:
            fenced = True
        _self_test_check(checks, "explicit takeover fences old generation",
                         fenced and replacement["generation"] == old["generation"] + 1,
                         f"old={old} replacement={replacement}")
        try:
            store_a.takeover(
                100602, "server-01", confirm=True,
                expected_reservation_id=old["reservation_id"],
                expected_generation=old["generation"])
            retry_fenced = False
        except ReservationFenced:
            retry_fenced = True
        _self_test_check(checks, "takeover retry cannot refence replacement",
                         retry_fenced, "expected old token")
        rejected = store_a.reserve(100603, "local-01")
        store_a.set_status(rejected, "rejected")
        rejected_takeover = store_a.takeover(
            100603, "server-01", confirm=True,
            expected_reservation_id=rejected["reservation_id"],
            expected_generation=rejected["generation"])
        _self_test_check(checks, "rejected work requires explicit takeover",
                         rejected_takeover["generation"] == rejected["generation"] + 1,
                         f"old={rejected} replacement={rejected_takeover}")

        deleted_ok, deleted_detail = _deleted_state_check(base)
        _self_test_check(checks, "deleted state fails closed",
                         deleted_ok, deleted_detail)
        key_ok, key_detail = _bad_phase_key_check(base)
        _self_test_check(checks, "noncanonical phase keys fail closed",
                         key_ok, key_detail)

        # A missing/failed board is unavailable, never treated as an empty
        # board that permits a launch.
        bad = ReservationStore(
            root_a, private_repo=clients[0], remote="does-not-exist")
        try:
            bad.read()
            unavailable = False
        except CoordinationUnavailable:
            unavailable = True
        _self_test_check(checks, "coordination fetch failure fails closed",
                         unavailable, "missing remote")

        lock_contender = store_b.reserve(100604, "server-01")
        pushurl_ok, pushurl_detail = _pushurl_boundary_check(base)
        _self_test_check(checks, "public pushurl boundary fails closed",
                         pushurl_ok, pushurl_detail)
        _self_test_check(checks, "publication lock blocks a valid second phase",
                         _publication_lock_check(
                             store_a, other, lock_contender), "claim-scoped")
    finally:
        shutil.rmtree(base, ignore_errors=True)
    return checks


def _deleted_state_check(base):
    remote, clients = _git_test_repo(base, "deleted-state")
    root = base / "deleted-root"
    root.mkdir()
    store = ReservationStore(root, private_repo=clients[0])
    store.reserve(100440, "server-01")
    deleter = base / "deleted-client"
    subprocess.run(["git", "clone", "-q", str(remote), str(deleter)],
                   check=True, capture_output=True, text=True)
    _git(deleter, "config", "user.email", "coordination-test@example.com")
    _git(deleter, "config", "user.name", "coordination test")
    _git(deleter, "rm", "-q", STATE_REL.as_posix())
    _git(deleter, "commit", "-q", "-m", "delete coordination state")
    _git(deleter, "push", "origin", "master")
    try:
        store.read()
        return False, "deleted state was accepted"
    except CoordinationUnavailable as exc:
        return True, str(exc)


def _bad_phase_key_check(base):
    bad = {
        "version": 1,
        "phases": {
            "1": {
                "status": "running", "machine_id": "server-01",
                "reservation_id": "rsv-bad-key", "generation": 1,
                "claimed_at": "x", "heartbeat_at": "x",
                "expires_at": None, "run_id": "phase-1",
                "base_revisions": {},
            }
        },
    }
    remote, clients = _git_test_repo(base, "bad-key", initial_state=bad)
    root = base / "bad-key-root"
    root.mkdir()
    store = ReservationStore(root, private_repo=clients[0])
    try:
        store.read()
        return False, "noncanonical phase key was accepted"
    except CoordinationUnavailable as exc:
        return True, str(exc)


def _self_test_receipt(store, reservation):
    _git(store.private, "fetch", "origin", "master")
    _git(store.private, "merge", "--ff-only", "origin/master")
    path = store.private / "runs" / f"phase-{reservation['phase']}" / PUBLICATION_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "phase": reservation["phase"],
        "state": "published",
        "reservation": {
            "machine_id": reservation["machine_id"],
            "reservation_id": reservation["reservation_id"],
            "generation": reservation["generation"],
        },
        "public_commit": "0" * 40,
        "private_commit": _head(store.private),
        "published_at": _now(),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n")
    _git(store.private, "add", "--", path.relative_to(store.private).as_posix())
    _git(store.private, "commit", "-q", "-m", "test publication receipt")
    _git(store.private, "push", "origin", "HEAD:master")
    return path


def _pushurl_boundary_check(base):
    public_remote = base / "public-boundary.git"
    private_remote = base / "private-boundary.git"
    for remote in (public_remote, private_remote):
        subprocess.run(["git", "init", "--bare", "-q", str(remote)],
                       check=True, capture_output=True, text=True)
        _git(remote, "symbolic-ref", "HEAD", "refs/heads/master")
    public = base / "public-boundary"
    private = base / "private-boundary"
    subprocess.run(["git", "clone", "-q", str(public_remote), str(public)],
                   check=True, capture_output=True, text=True)
    subprocess.run(["git", "clone", "-q", str(private_remote), str(private)],
                   check=True, capture_output=True, text=True)
    _git(private, "remote", "set-url", "--push", "origin", str(public_remote))
    root = public
    try:
        ReservationStore(root, private_repo=private)
        return False, "public pushurl was accepted"
    except CoordinationUnavailable as exc:
        return True, str(exc)


def _publication_lock_check(store, reservation, contender):
    store.acquire_publication(reservation)
    try:
        store.acquire_publication(contender)
        blocked = False
    except PublicationBusy:
        blocked = True
    store.release_publication(reservation)
    return blocked


def self_test():
    checks = self_test_checks()
    ok = all(item["ok"] for item in checks)
    _print_json({"coordination_self_test": "pass" if ok else "fail",
                 "checks": checks})
    return 0 if ok else 1


def _add_store_args(parser):
    parser.add_argument("--repo-root", default=".", help="public repo root")
    parser.add_argument("--private-repo", default=None,
                        help="override the nested private checkout path")
    parser.add_argument("--branch", default=None,
                        help="coordination branch (default: master)")
    parser.add_argument("--remote", default=None,
                        help="coordination remote (default: origin)")


def _add_reservation_args(parser):
    parser.add_argument("--phase", required=True)
    parser.add_argument("--machine-id", required=True)
    parser.add_argument("--reservation-id", required=True)
    parser.add_argument("--generation", required=True, type=int)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Shared phase reservations")
    sub = parser.add_subparsers(dest="command", required=False)

    reserve = sub.add_parser("reserve", help="claim an available phase")
    _add_store_args(reserve)
    reserve.add_argument("--phase", required=True)
    reserve.add_argument("--machine-id", required=True)
    reserve.add_argument("--run-id", default=None)
    reserve.add_argument("--status", choices=sorted(ACTIVE_STATUSES),
                          default="claimed")

    for name, help_text in (("renew", "renew an owned reservation"),
                            ("assert-owner", "verify the three-part fence"),
                            ("set-status", "change an owned reservation")):
        command = sub.add_parser(name, help=help_text)
        _add_store_args(command)
        _add_reservation_args(command)
        if name == "set-status":
            command.add_argument("--status", required=True,
                                 choices=sorted(STATUSES))
            command.add_argument(
                "--publication-receipt",
                help="published receipt path; required for completed")
            command.add_argument(
                "--accept-reason",
                help="why an operator closed the phase without a passing "
                     "checker; required for accepted, and recorded on the board")

    takeover = sub.add_parser("takeover", help="explicitly take over a live claim")
    _add_store_args(takeover)
    takeover.add_argument("--phase", required=True)
    takeover.add_argument("--machine-id", required=True)
    takeover.add_argument("--expected-reservation-id", required=True)
    takeover.add_argument("--expected-generation", required=True, type=int)
    takeover.add_argument("--confirm", action="store_true")

    register = sub.add_parser(
        "register-running", help="register a pre-coordination running phase")
    _add_store_args(register)
    register.add_argument("--phase", required=True)
    register.add_argument("--machine-id", required=True)
    register.add_argument("--run-id", default=None)
    register.add_argument("--confirm", action="store_true")

    release = sub.add_parser(
        "release-publication", help="explicitly release a stale publication lock")
    _add_store_args(release)
    _add_reservation_args(release)
    release.add_argument("--confirm", action="store_true")

    show = sub.add_parser("show", help="fetch and print the coordination state")
    _add_store_args(show)
    sub.add_parser("self-test", help="run hermetic two-client checks")
    parser.add_argument("--self-test", dest="legacy_self_test", action="store_true",
                        help=argparse.SUPPRESS)

    args = parser.parse_args(argv)
    if not args.command and not args.legacy_self_test:
        parser.error("a command is required")
    if args.legacy_self_test or args.command == "self-test":
        return self_test()
    try:
        store = _cli_store(args)
        if args.command == "reserve":
            result = store.reserve(
                args.phase, args.machine_id, run_id=args.run_id,
                status=args.status)
        elif args.command in {"renew", "assert-owner", "set-status"}:
            reservation = {
                "phase": _phase_key(args.phase)[0],
                "machine_id": args.machine_id,
                "reservation_id": args.reservation_id,
                "generation": args.generation,
            }
            if args.command == "renew":
                result = store.renew(reservation)
            elif args.command == "assert-owner":
                result = store.assert_owner(reservation)
            else:
                result = store.set_status(
                    reservation, args.status,
                    evidence_path=args.publication_receipt,
                    accepted_reason=args.accept_reason)
        elif args.command == "takeover":
            result = store.takeover(
                args.phase, args.machine_id, confirm=args.confirm,
                expected_reservation_id=args.expected_reservation_id,
                expected_generation=args.expected_generation)
            save_reservation_file(
                reservation_file(args.repo_root, args.phase,
                                  private_repo=store.private), result)
        elif args.command == "register-running":
            result = store.register_running(
                args.phase, args.machine_id, run_id=args.run_id,
                confirm=args.confirm)
            save_reservation_file(
                reservation_file(args.repo_root, args.phase,
                                  private_repo=store.private), result)
        elif args.command == "release-publication":
            if not args.confirm:
                raise CoordinationError(
                    "releasing a publication lock requires confirm=true")
            result = store.release_publication({
                "phase": _phase_key(args.phase)[0],
                "machine_id": args.machine_id,
                "reservation_id": args.reservation_id,
                "generation": args.generation,
            })
        else:
            result, _commit = store.read()
        _print_json({"state": "OK", "reservation": result}
                     if args.command not in {"show"} else result)
        return 0
    except ReservationConflict as exc:
        _print_json({"state": "WAIT_FOR_CLAIM", "phase": exc.phase,
                     "owner": exc.record.get("machine_id"),
                     "status": exc.record.get("status"),
                     "error": str(exc)})
        return 3
    except ReservationFenced as exc:
        _print_json({"state": "FENCED", "error": str(exc)})
        return 4
    except (CoordinationUnavailable, CoordinationError) as exc:
        _print_json({"state": "COORDINATION_UNAVAILABLE", "error": str(exc)})
        return 2


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
# Copyright 2026 Agent Memoir Developers (https://agentmemoir.com/)
# SPDX-License-Identifier: Apache-2.0
"""Fail-closed git sync for the two Clio checkouts.

Before a phase starts, and again before finalize publishes, the pipeline
must not run on a stale or diverged base. This module fetches each checkout
from its own configured upstream and brings it in line by fast-forward or a
plain merge, stopping the line only when it cannot do so safely.

Two modes, because "local is ahead" means different things:

* ``start`` (before a phase): bring the checkout in line with its remote.
  A strictly-behind branch is fast-forwarded; a diverged branch is merged
  with a plain merge commit that keeps every local commit and accepts the
  remote changes. Local commits ahead of the remote are fine here: the
  remote has nothing new, so nothing is pulled and those commits publish at
  finalize.
* ``push`` (before finalize pushes): the phase's own commits are local, so
  an ahead branch is verified as a fast-forward push. A diverged or behind
  remote is merged (or fast-forwarded) first so the push can proceed; a
  conflict is left in place (not aborted) for the finalize agent to resolve.

``commit_leftover_run_state`` is the fresh-start cleanup: when given a phase,
it commits and pushes only that phase's private ``runs/phase-<N>`` leftovers
(the runner writes ``ledger.json``/``run.json`` after finalize's commit) and
refuses staged paths outside that phase. ``--mode publish`` additionally
checks the phase's three-part reservation fence, takes the short publication
lock, verifies effective public/private Git push destinations, writes and pushes
``runs/phase-<N>/publication.json``, and performs the final sync-and-push
without force.

Hard safety rules, enforced by construction:

* Never ``git pull`` (this repo sets ``pull.rebase = true``, which would
  rewrite history), never rebase, never force-push, never reset, never
  stash, never ``clean``. Fast-forward when possible, otherwise a plain
  merge commit; a real conflict is aborted in start mode.
* Giving up is the last resort: a mechanical fast-forward or a clean merge
  is preferred. Only a genuine conflict, a dirty index, or a detached HEAD
  stops the line, and then local work is reported, never discarded.
* The nested ``private/clio-private`` checkout is synced only from its own
  remote; effective public/private fetch and push destinations are compared,
  so private content cannot cross into the public checkout.

Usage (run from the repo root):

    python3 private/clio-private/scripts/pipeline/gitsync.py --root . --mode start
    python3 private/clio-private/scripts/pipeline/gitsync.py --root . --mode push
    python3 private/clio-private/scripts/pipeline/gitsync.py --root . --mode publish --phase 100440
    python3 private/clio-private/scripts/pipeline/gitsync.py --self-test

Exit codes: 0 synced/verified, 1 blocked (operator decision required),
2 config or usage error. JSON goes to stdout in every case.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import urllib.parse
from pathlib import Path

PRIVATE_REL = Path("private") / "clio-private"
FETCH_TIMEOUT_S = 180
GIT_TIMEOUT_S = 60
MAX_SUBJECTS = 5


class ConfigError(Exception):
    """A usage or environment error (exit 2), not a sync conflict."""


def git(repo, *args, timeout=GIT_TIMEOUT_S, extra_env=None, raw=False):
    """Run one git command in repo. Returns (rc, stdout, stderr), stripped
    unless raw=True (porcelain status keeps its leading status column).

    GIT_TERMINAL_PROMPT=0 keeps a missing credential from hanging an
    unattended run on an interactive prompt; a timeout is a failure, not
    a hang."""
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    if extra_env:
        env.update(extra_env)
    try:
        p = subprocess.run(["git", "-C", str(repo), *args],
                           capture_output=True, text=True, timeout=timeout,
                           env=env)
    except FileNotFoundError:
        raise ConfigError("git is not on PATH")
    except subprocess.TimeoutExpired:
        return 124, "", f"git {' '.join(args)} timed out after {timeout}s"
    if raw:
        return p.returncode, p.stdout, p.stderr
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def is_git_repo(path):
    rc, out, _ = git(path, "rev-parse", "--is-inside-work-tree")
    return rc == 0 and out == "true"


def resolve_upstream(repo):
    """Return (branch, remote, remote_branch, why). why is None on success;
    otherwise it explains why the checkout cannot be synced safely."""
    rc, branch, _ = git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    if rc != 0 or not branch or branch == "HEAD":
        return None, None, None, "detached HEAD or unreadable current branch"
    rc, up, _ = git(repo, "rev-parse", "--abbrev-ref", "--symbolic-full-name",
                    "@{upstream}")
    if rc != 0 or not up:
        return branch, None, None, f"branch {branch!r} has no upstream"
    remote, _, remote_branch = up.partition("/")
    if not remote or not remote_branch:
        return branch, None, None, f"unreadable upstream {up!r}"
    return branch, remote, remote_branch, None


def remote_urls(repo, remote, *, push=False):
    args = ["remote", "get-url"]
    if push:
        args.append("--push")
    args.extend(["--all", remote])
    rc, out, _ = git(repo, *args)
    if rc != 0:
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def canonical_remote_url(value):
    value = (value or "").strip()
    if not value:
        return ""
    if "://" not in value and "@" not in value and ":" not in value:
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


def upstream_urls(repo, *, push=False):
    _branch, remote, _remote_branch, why = resolve_upstream(repo)
    if why or not remote:
        return set()
    return {
        canonical_remote_url(url)
        for url in remote_urls(repo, remote, push=push)
    }


def upstream_push_urls(repo):
    return upstream_urls(repo, push=True)


def classify(repo, upstream):
    """(local, tip, ahead, behind, relation) after a fetch."""
    local = git(repo, "rev-parse", "HEAD")[1]
    tip = git(repo, "rev-parse", upstream)[1]
    ahead = int(git(repo, "rev-list", "--count", f"{upstream}..HEAD")[1] or 0)
    behind = int(git(repo, "rev-list", "--count", f"HEAD..{upstream}")[1] or 0)
    if ahead == 0 and behind == 0:
        relation = "equal"
    elif ahead == 0:
        relation = "behind"
    elif behind == 0:
        relation = "ahead"
    else:
        relation = "diverged"
    return local, tip, ahead, behind, relation


def subjects(repo, rev_range):
    rc, out, _ = git(repo, "log", "--oneline", "--no-decorate",
                     f"-n{MAX_SUBJECTS}", rev_range)
    return out.splitlines() if rc == 0 and out else []


def unstaged(repo):
    rc, out, _ = git(repo, "diff", "--name-only")
    return out.splitlines() if rc == 0 and out else []


def blocked(info, reason, **extra):
    info = dict(info)
    info["ok"] = False
    info["action"] = "blocked"
    blockers = list(info.get("blockers", []))
    blockers.append(reason)
    info["blockers"] = blockers
    info.update(extra)
    return info


def _fast_forward(info, repo, upstream, behind):
    """Integrate a strictly-behind remote by fast-forward only (no merge
    commit). Refuses on a dirty index or an overlapping local edit."""
    _, staged, _ = git(repo, "diff", "--cached", "--name-only")
    if staged:
        return blocked(
            info, "staged changes present; commit or unstage before syncing",
            staged=staged.splitlines(),
            hint="the index must match HEAD for a fast-forward")
    rc, out, err = git(repo, "merge", "--ff-only", upstream)
    if rc != 0:
        return blocked(
            info, f"fast-forward merge refused: {err or out}",
            dirty=unstaged(repo),
            hint="commit or move the overlapping local edits, then rerun")
    after = git(repo, "rev-parse", "HEAD")[1]
    return dict(info, ok=True, action="fast-forwarded", after=after,
                hint=f"advanced {behind} commit(s) to {upstream}")


def _merge(info, repo, upstream, ahead, behind, abort_on_conflict=True):
    """Integrate diverged histories with a plain merge commit: accept the
    remote changes while keeping every local commit. Never rebases or
    forces. On a real conflict, start mode aborts and halts; push mode
    leaves the conflict in place so the finalize agent can resolve it."""
    _, staged, _ = git(repo, "diff", "--cached", "--name-only")
    if staged:
        return blocked(
            info, "staged changes present; commit or unstage before merging",
            staged=staged.splitlines(),
            hint="the index must match HEAD for a merge")
    rc, out, err = git(repo, "merge", "--no-edit", upstream,
                       extra_env={"GIT_MERGE_AUTOEDIT": "no"})
    if rc != 0:
        _, conflicts, _ = git(repo, "diff", "--name-only", "--diff-filter=U")
        aborted = None
        if abort_on_conflict:
            _, _, ab_err = git(repo, "merge", "--abort")
            aborted = not ab_err
        reason = ("clean merge impossible; remote changes conflict with "
                  "local work")
        hint = "resolve by hand; the pipeline will not rebase or force"
        if not abort_on_conflict:
            hint = ("resolve the conflicted files, `git add` them, and "
                    "complete the merge with `git commit`; never force or "
                    "rebase")
        return blocked(
            info, reason,
            conflicted=conflicts.splitlines() if conflicts else [],
            merge_error=(err or out),
            merge_aborted=aborted,
            hint=hint)
    after = git(repo, "rev-parse", "HEAD")[1]
    return dict(info, ok=True, action="merged", after=after,
                hint=f"merged {behind} remote commit(s) with {ahead} local "
                     f"commit(s); push will fast-forward")


def sync_one(repo, mode, remote=None, branch=None):
    """Bring one checkout in line with its remote, accepting changes where
    that is mechanically safe.

    Fast-forwards a strictly-behind branch; merges (never rebases) a
    diverged branch and keeps every local commit. In start mode a real
    conflict, a dirty index, or a detached HEAD halts with the merge
    aborted. In push mode an ahead branch is verified as a fast-forward
    push, and a conflict is left in place for the finalize agent to
    resolve. Returns a result dict; ok is the success flag."""
    repo = Path(repo).resolve()
    info = {"repo": str(repo), "mode": mode}
    if not is_git_repo(repo):
        return blocked(info, "not a git working tree")
    cur_branch, cur_remote, remote_branch, why = resolve_upstream(repo)
    if why:
        return blocked(info, why)
    branch = branch or cur_branch
    remote = remote or cur_remote
    if branch != cur_branch:
        return blocked(info, f"checkout is on {cur_branch!r}, not {branch!r}")
    info.update(branch=branch, remote=remote)
    rc, _, err = git(repo, "fetch", "--prune", remote, timeout=FETCH_TIMEOUT_S)
    if rc != 0:
        return blocked(info, f"git fetch {remote} failed", detail=err)
    upstream = f"{remote}/{remote_branch}"
    rc, tip, _ = git(repo, "rev-parse", "--verify", upstream)
    if rc != 0 or not tip:
        return blocked(info, f"upstream {upstream} does not exist after fetch")
    local, tip, ahead, behind, relation = classify(repo, upstream)
    info.update(upstream=upstream, before=local, remote_tip=tip,
                ahead=ahead, behind=behind, relation=relation,
                local_only=subjects(repo, f"{upstream}..HEAD"),
                remote_only=subjects(repo, f"HEAD..{upstream}"))
    if relation == "equal":
        return dict(info, ok=True, action="up-to-date",
                    hint="local and remote match")
    if relation == "ahead":
        if mode == "push":
            return dict(info, ok=True, action="verified",
                        hint="remote is an ancestor of local HEAD; "
                             "push will fast-forward")
        return dict(info, ok=True, action="ahead",
                    hint=f"remote has nothing new; {ahead} local commit(s) "
                         f"will publish at finalize")
    if relation == "behind":
        return _fast_forward(info, repo, upstream, behind)
    return _merge(info, repo, upstream, ahead, behind,
                  abort_on_conflict=(mode != "push"))


def sync_all(root, mode):
    """Sync the public checkout and the nested private checkout, if present."""
    root = Path(root).resolve()
    repos = [root]
    nested = root / PRIVATE_REL
    if is_git_repo(nested):
        repos.append(nested)
    if len(repos) == 2:
        public_fetch = upstream_urls(root)
        public_push = upstream_push_urls(root)
        private_fetch = upstream_urls(nested)
        private_push = upstream_push_urls(nested)
        if not public_fetch or not public_push or not private_fetch or not private_push:
            reason = ("cannot prove separate public/private Git destinations; "
                      "refusing to sync either checkout")
            results = [blocked({"repo": str(r), "mode": mode}, reason)
                       for r in repos]
            return {"ok": False, "mode": mode, "repos": results,
                    "summary": summarize(results, mode)}
        if public_push & private_push or public_push & private_fetch \
                or public_fetch & private_push:
            reason = ("nested private repo and public repo share a Git "
                      "push/fetch destination; refusing to sync either checkout")
            results = [blocked({"repo": str(r), "mode": mode}, reason)
                       for r in repos]
            return {"ok": False, "mode": mode, "repos": results,
                    "summary": summarize(results, mode)}
    results = [sync_one(r, mode) for r in repos]
    ok = all(r["ok"] for r in results)
    return {"ok": ok, "mode": mode, "repos": results,
            "summary": summarize(results, mode)}


def dirty_paths(repo):
    """Repo-relative paths with any staged, unstaged, or untracked change.

    Ignored files (for example the runner's .tui.log and .driver/) do not
    appear, so this is exactly the set a commit would carry."""
    rc, out, _ = git(repo, "status", "--porcelain=v1",
                     "--untracked-files=all", raw=True)
    paths = []
    for line in out.splitlines():
        if len(line) < 4:
            continue
        path = line[3:]
        if " -> " in path:  # renames: "XY old -> new"
            path = path.split(" -> ", 1)[1]
        paths.append(path.strip().strip('"'))
    return paths


def is_run_state(path):
    """True for the pipeline's own run-state paths inside the private repo."""
    return path == "runs" or path.startswith("runs/")


def _commit_and_push_run_state(repo, message, pathspec="runs"):
    """Commit one scoped run-state path and push without force.

    ``pathspec`` is deliberately narrow. A phase must never publish another
    phase's run directory merely because both are dirty at the same time.
    """
    branch, remote, remote_branch, why = resolve_upstream(repo)
    info = {"repo": str(repo), "pathspec": pathspec}
    if why:
        return blocked(info, why)
    _, staged, _ = git(repo, "diff", "--cached", "--name-only")
    if staged:
        prefix = pathspec.rstrip("/") + "/"
        outside = [p for p in staged.splitlines()
                   if p != pathspec and not p.startswith(prefix)]
        if outside:
            return blocked(info, "staged changes exist outside the current phase",
                           staged=outside,
                           hint="commit or unstage them before publishing")
    rc, _, err = git(repo, "add", "-A", "--", pathspec)
    if rc != 0:
        return blocked(info, f"could not stage {pathspec}: {err}")
    rc, out, err = git(repo, "commit", "-q", "-m", message)
    if rc != 0:
        combined = err or out
        if "nothing to commit" in combined.lower():
            return dict(info, ok=True, action="clean", hint=message)
        return blocked(info, f"commit of run state failed: {combined}")
    for attempt in (1, 2):
        rc, out, err = git(repo, "push", remote, branch)
        if rc == 0:
            after = git(repo, "rev-parse", "HEAD")[1]
            return dict(info, ok=True, action="committed-and-pushed",
                        after=after, hint=message)
        if attempt == 1:
            res = sync_one(repo, "start")
            if not res.get("ok"):
                return blocked(info, "remote moved and could not be "
                                    "integrated before pushing run state",
                               detail=res.get("summary"))
    return blocked(info, f"push of run state failed: {err or out}",
                   hint="resolve the remote by hand, then rerun")


def _phase_run_pathspec(phase):
    try:
        number = int(phase)
    except (TypeError, ValueError):
        raise ConfigError(f"invalid phase number: {phase!r}") from None
    if number < 0 or number > 999999:
        raise ConfigError(f"phase number out of range: {number}")
    return f"runs/phase-{number:06d}"


def commit_leftover_run_state(root, message, phase=None):
    """Commit only the current phase's private run state.

    With ``phase`` omitted, the legacy all-``runs`` scope remains available
    for standalone maintenance. The pipeline always supplies a phase so a
    concurrent phase's partial records cannot be swept into this publication.
    """
    root = Path(root).resolve()
    private = root / PRIVATE_REL
    pathspec = _phase_run_pathspec(phase) if phase is not None else "runs"
    results = []
    # The nested private checkout is a separate repo by design; if a host
    # lacks the global ignore for it, do not mistake it for public dirt.
    pub_dirty = [p for p in dirty_paths(root)
                 if not (p == "private" or p.startswith("private/"))]
    if pub_dirty:
        results.append(blocked(
            {"repo": str(root)},
            "public checkout has changes outside the pipeline's run state",
            dirty=pub_dirty,
            hint="commit or revert them, then rerun"))
    if is_git_repo(private):
        paths = dirty_paths(private)
        if phase is None:
            outside = [p for p in paths if not is_run_state(p)]
            inside = [p for p in paths if is_run_state(p)]
        else:
            prefix = pathspec + "/"
            # Unstaged files from another phase are deliberately left alone;
            # only staged paths outside this phase are dangerous because a
            # commit would carry them accidentally.
            _, staged, _ = git(private, "diff", "--cached", "--name-only")
            outside = [p for p in staged.splitlines()
                       if p != pathspec and not p.startswith(prefix)]
            inside = [p for p in paths
                      if p == pathspec or p.startswith(prefix)]
        if outside:
            results.append(blocked(
                {"repo": str(private)},
                "private checkout has changes outside the current phase"
                if phase is not None else "private checkout has changes outside runs/",
                dirty=outside,
                hint="commit or move them before publishing this phase"))
        elif inside:
            results.append(_commit_and_push_run_state(
                private, message, pathspec=pathspec))
        else:
            results.append({"repo": str(private), "ok": True,
                            "action": "clean"})
    ok = all(r.get("ok") for r in results)
    return {"ok": ok, "mode": "start-clean", "repos": results,
            "pathspec": pathspec,
            "summary": summarize(results, "start-clean")}


def _published_head(results, repo):
    for result in results:
        if result.get("repo") == str(repo) and result.get("action") == "pushed":
            return result.get("after")
    return None


def _write_publication_receipt(root, phase, reservation, results):
    private = root / PRIVATE_REL
    run_dir = private / "runs" / f"phase-{int(phase):06d}"
    if not run_dir.is_dir():
        raise ConfigError(f"phase run directory is missing: {run_dir}")
    public_commit = _published_head(results, root)
    private_commit = _published_head(results, private)
    if not public_commit or not private_commit:
        raise ConfigError("publication did not produce both repository heads")
    from phase_reservations import _now
    receipt = {
        "version": 1,
        "phase": f"{int(phase):06d}",
        "state": "published",
        "reservation": {
            "machine_id": reservation["machine_id"],
            "reservation_id": reservation["reservation_id"],
            "generation": reservation["generation"],
        },
        "public_commit": public_commit,
        "private_commit": private_commit,
        "published_at": _now(),
    }
    path = run_dir / "publication.json"
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    pushed = commit_leftover_run_state(
        root, f"pipeline: publish completion receipt for phase {int(phase):06d}",
        phase=phase)
    if not pushed.get("ok"):
        raise ConfigError(
            f"publication receipt was not pushed: {pushed.get('summary', 'unknown error')}")
    receipt["private_commit"] = private_commit
    receipt["path"] = str(path)
    return receipt, pushed


def _load_phase_reservation(root, phase, reservation_file=None,
                             machine_id=None, reservation_id=None,
                             generation=None):
    if reservation_file is None:
        reservation_file = root / PRIVATE_REL / "runs" / f"phase-{int(phase):06d}" / "reservation.json"
    try:
        data = json.loads(Path(reservation_file).read_text())
    except (OSError, ValueError) as exc:
        raise ConfigError(f"cannot read phase reservation: {exc}") from exc
    if machine_id:
        data["machine_id"] = machine_id
    if reservation_id:
        data["reservation_id"] = reservation_id
    if generation is not None:
        data["generation"] = int(generation)
    data["phase"] = f"{int(phase):06d}"
    return data


def _push_one(repo):
    branch, remote, _remote_branch, why = resolve_upstream(repo)
    if why:
        return blocked({"repo": str(repo)}, why)
    rc, out, err = git(repo, "push", remote, branch)
    if rc != 0:
        return blocked({"repo": str(repo)},
                       f"push failed: {err or out}",
                       hint="resolve the remote and rerun; never force-push")
    return {"repo": str(repo), "ok": True, "action": "pushed",
            "after": git(repo, "rev-parse", "HEAD")[1]}


def publish_phase(root, phase, *, reservation_file=None, machine_id=None,
                  reservation_id=None, generation=None, commit_run_state=True):
    """Check the phase fence, take the short publication lock, and publish.

    The caller must commit the phase's product changes first. This helper
    commits only leftover files in that phase's run directory, syncs both
    checkouts fail-closed, and performs normal pushes. It never stages an
    unrelated phase and never uses a force push.
    """
    root = Path(root).resolve()
    try:
        phase = int(phase)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"invalid phase number: {phase!r}") from exc
    if phase < 0 or phase > 999999:
        raise ConfigError(f"phase number out of range: {phase}")
    if not commit_run_state:
        raise ConfigError("publication requires phase-scoped run-state commit")
    try:
        from phase_reservations import (
            PublicationBusy,
            ReservationFenced,
            ReservationStore,
        )
        reservation = _load_phase_reservation(
            root, phase, reservation_file, machine_id, reservation_id, generation)
        store = ReservationStore(root)
        store.assert_owner(reservation)
        store.acquire_publication(reservation)
    except PublicationBusy as exc:
        return {"ok": False, "mode": "publish", "state": "PUBLICATION_BUSY",
                "error": str(exc), "phase": f"{int(phase):06d}"}
    except ReservationFenced as exc:
        return {"ok": False, "mode": "publish", "state": "FENCED",
                "error": str(exc), "phase": f"{int(phase):06d}"}
    except Exception as exc:  # noqa: BLE001 - normalize boundary errors
        return {"ok": False, "mode": "publish", "state": "COORDINATION_UNAVAILABLE",
                "error": str(exc), "phase": f"{int(phase):06d}"}

    results = []
    outcome = None
    try:
        if commit_run_state:
            clean = commit_leftover_run_state(
                root, f"pipeline: publish run state for phase {int(phase):06d}",
                phase=phase)
            results.append(clean)
            if not clean["ok"]:
                outcome = {"ok": False, "mode": "publish",
                           "phase": f"{int(phase):06d}", "state": "BLOCKED",
                           "repos": results, "summary": clean["summary"]}
        if outcome is None:
            dirty = [p for p in dirty_paths(root)
                     if not (p == "private" or p.startswith("private/"))]
            if is_git_repo(root / PRIVATE_REL):
                dirty += [f"private/clio-private/{p}"
                          for p in dirty_paths(root / PRIVATE_REL)]
            if dirty:
                outcome = {"ok": False, "mode": "publish",
                           "phase": f"{int(phase):06d}", "state": "BLOCKED",
                           "repos": results,
                           "error": "working tree is dirty after phase cleanup",
                           "dirty": dirty}
        if outcome is None:
            sync = sync_all(root, "push")
            results.append(sync)
            if not sync["ok"]:
                outcome = {"ok": False, "mode": "publish",
                           "phase": f"{int(phase):06d}", "state": "BLOCKED",
                           "repos": results, "summary": sync["summary"]}
        if outcome is None:
            for checkout in (root, root / PRIVATE_REL):
                if not is_git_repo(checkout):
                    continue
                store.assert_owner(reservation)
                pushed = _push_one(checkout)
                results.append(pushed)
                if not pushed.get("ok"):
                    outcome = {"ok": False, "mode": "publish",
                               "phase": f"{int(phase):06d}", "state": "BLOCKED",
                               "repos": results,
                               "summary": summarize([pushed], "publish")}
                    break
        if outcome is None:
            push_results = [r for r in results
                            if isinstance(r, dict) and "repo" in r]
            outcome = {"ok": True, "mode": "publish",
                       "phase": f"{int(phase):06d}", "state": "PUBLISHED",
                       "repos": results,
                       "summary": summarize(push_results, "publish")}
        if outcome.get("ok") and commit_run_state:
            receipt, receipt_result = _write_publication_receipt(
                root, phase, reservation, results)
            results.append(receipt_result)
            outcome["receipt"] = receipt
            outcome["repos"] = results
            outcome["summary"] = summarize(
                [r for r in results if isinstance(r, dict) and "repo" in r],
                "publish")
    except Exception as exc:  # noqa: BLE001 - publication is fail-closed
        outcome = {"ok": False, "mode": "publish",
                   "phase": f"{int(phase):06d}", "state": "BLOCKED",
                   "repos": results, "error": str(exc)}
    try:
        store.release_publication(reservation)
    except Exception as exc:  # noqa: BLE001 - a stale lock must be visible
        outcome = dict(outcome or {"ok": False, "mode": "publish",
                                   "phase": f"{int(phase):06d}"})
        outcome["ok"] = False
        outcome["state"] = "COORDINATION_UNAVAILABLE"
        outcome["error"] = f"could not release publication lock: {exc}"
    return outcome


def summarize(results, mode):
    parts = []
    for r in results:
        if r.get("ok"):
            parts.append(f"{r['repo']}: {r.get('action', 'ok')}")
        else:
            parts.append(f"{r['repo']}: BLOCKED "
                         f"({'; '.join(r.get('blockers', []))})")
    head = f"{mode} sync {'ok' if all(r.get('ok') for r in results) else 'BLOCKED'}"
    return f"{head}: " + "; ".join(parts)


def _check(checks, name, ok, detail=""):
    checks.append({"check": name, "ok": bool(ok), "detail": detail})


def _init_remote(tmp, name):
    """Bare remote with HEAD -> main, plus a clone at tmp/<name> that has
    one commit on main tracking origin/main."""
    remote = tmp / f"{name}-remote.git"
    subprocess.run(["git", "init", "--bare", "-q", str(remote)],
                   check=True, capture_output=True, text=True)
    git(remote, "symbolic-ref", "HEAD", "refs/heads/main")
    work = tmp / name
    subprocess.run(["git", "clone", "-q", str(remote), str(work)],
                   check=True, capture_output=True, text=True)
    git(work, "config", "user.email", "sync-test@example.com")
    git(work, "config", "user.name", "sync test")
    git(work, "checkout", "-q", "-b", "main")
    (work / "a.txt").write_text("one\n")
    git(work, "add", "a.txt")
    git(work, "commit", "-q", "-m", "init")
    git(work, "push", "-q", "-u", "origin", "main")
    return remote, work


def _remote_commit(remote, tmp, name, content="two\n"):
    """Push one commit to the remote from a throwaway clone."""
    other = tmp / f"other-{name}"
    subprocess.run(["git", "clone", "-q", str(remote), str(other)],
                   check=True, capture_output=True, text=True)
    git(other, "config", "user.email", "sync-test@example.com")
    git(other, "config", "user.name", "sync test")
    (other / "a.txt").write_text(content)
    git(other, "add", "a.txt")
    git(other, "commit", "-q", "-m", f"remote {name}")
    git(other, "push", "-q", "origin", "main")


def _local_commit(work, name):
    (work / "b.txt").write_text(f"{name}\n")
    git(work, "add", "b.txt")
    git(work, "commit", "-q", "-m", f"local {name}")


def _publication_receipt_check(base):
    d = base / "publication-receipt"
    d.mkdir()
    _public_remote, pub = _init_remote(d, "pub")
    nested = pub / PRIVATE_REL
    nested.parent.mkdir(parents=True, exist_ok=True)
    private_remote, _ = _init_remote(d, "priv")
    subprocess.run(["git", "clone", "-q", str(private_remote), str(nested)],
                   check=True, capture_output=True, text=True)
    git(nested, "config", "user.email", "sync-test@example.com")
    git(nested, "config", "user.name", "sync test")
    old_branch = os.environ.get("CLIO_PHASE_COORDINATION_BRANCH")
    os.environ["CLIO_PHASE_COORDINATION_BRANCH"] = "main"
    try:
        from phase_reservations import ReservationStore, save_reservation_file
        store = ReservationStore(pub, branch="main")
        reservation = store.reserve(100440, "server-01")
        run_dir = nested / "runs" / "phase-100440"
        run_dir.mkdir(parents=True, exist_ok=True)
        save_reservation_file(run_dir / "reservation.json", reservation)
        (run_dir / "run.json").write_text('{"state":"completed"}\\n')
        result = publish_phase(pub, 100440)
        if not result.get("ok") or result.get("state") != "PUBLISHED":
            return False, str(result)
        receipt_path = result.get("receipt", {}).get("path")
        if not receipt_path or not Path(receipt_path).is_file():
            return False, "publication receipt was not written"
        store.set_status(reservation, "completed", evidence_path=receipt_path)
        return store.read()[0]["phases"]["100440"]["status"] == "completed", \
            "receipt-backed completion"
    except Exception as exc:  # noqa: BLE001 - self-test reports the failure
        return False, str(exc)
    finally:
        if old_branch is None:
            os.environ.pop("CLIO_PHASE_COORDINATION_BRANCH", None)
        else:
            os.environ["CLIO_PHASE_COORDINATION_BRANCH"] = old_branch


def self_test_checks():
    """Stubbed-remote checks. Pure: temp dirs only, no repo state touched."""
    checks = []
    base = Path(tempfile.mkdtemp(prefix="gitsync-selftest-"))

    # 1. stale start is synced by fast-forward, preserving the remote work.
    d = base / "stale"
    d.mkdir()
    remote, work = _init_remote(d, "w")
    _remote_commit(remote, d, "w")
    res = sync_one(work, "start")
    _check(checks, "sync: stale start fast-forwards",
           res["ok"] and res["action"] == "fast-forwarded"
           and res["relation"] == "behind"
           and (work / "a.txt").read_text() == "two\n",
           f"action={res.get('action')} relation={res.get('relation')}")

    # 2. diverged start is merged cleanly, accepting remote changes while
    # keeping every local commit.
    d = base / "diverged"
    d.mkdir()
    remote, work = _init_remote(d, "w")
    _local_commit(work, "w")
    head_before = git(work, "rev-parse", "HEAD")[1]
    _remote_commit(remote, d, "w")
    res = sync_one(work, "start")
    parents = git(work, "rev-list", "--parents", "-n1", "HEAD")[1].split()
    _check(checks, "sync: diverged start merges and keeps local work",
           res["ok"] and res["action"] == "merged"
           and res["relation"] == "diverged"
           and git(work, "rev-parse", "HEAD^1")[1] == head_before
           and (work / "b.txt").is_file()
           and (work / "a.txt").read_text() == "two\n"
           and len(parents) == 3,
           f"action={res.get('action')} parents={parents}")

    # 2b. a conflicting divergence is aborted and halts, preserving local work.
    d = base / "conflict"
    d.mkdir()
    remote, work = _init_remote(d, "w")
    (work / "a.txt").write_text("local change\n")
    git(work, "add", "a.txt")
    git(work, "commit", "-q", "-m", "local change")
    _remote_commit(remote, d, "w", content="remote change\n")
    res = sync_one(work, "start")
    _check(checks, "sync: conflicting start aborts and preserves local work",
           (not res["ok"]) and res.get("conflicted") == ["a.txt"]
           and (work / "a.txt").read_text() == "local change\n"
           and not (work / ".git" / "MERGE_HEAD").exists(),
           f"conflicted={res.get('conflicted')}")

    # 2c. local commits ahead of the remote do not block a start; the remote
    # has nothing new and the commits publish at finalize.
    d = base / "ahead"
    d.mkdir()
    remote, work = _init_remote(d, "w")
    _local_commit(work, "w")
    res = sync_one(work, "start")
    _check(checks, "sync: ahead start proceeds (nothing to pull)",
           res["ok"] and res["action"] == "ahead"
           and (work / "b.txt").is_file(),
           f"action={res.get('action')}")

    # 3. clean push verifies the remote is an ancestor of local HEAD.
    d = base / "push-ok"
    d.mkdir()
    remote, work = _init_remote(d, "w")
    _local_commit(work, "w")
    res = sync_one(work, "push")
    _check(checks, "sync: clean final push verifies fast-forward",
           res["ok"] and res["action"] == "verified"
           and res["relation"] == "ahead",
           f"action={res.get('action')}")

    # 4. diverged final push merges the remote in, then push fast-forwards.
    d = base / "push-diverged"
    d.mkdir()
    remote, work = _init_remote(d, "w")
    _local_commit(work, "w")
    _remote_commit(remote, d, "w")
    res = sync_one(work, "push")
    _check(checks, "sync: diverged final push merges before pushing",
           res["ok"] and res["action"] == "merged"
           and (work / "a.txt").read_text() == "two\n"
           and (work / "b.txt").is_file(),
           f"action={res.get('action')}")

    # 4b. a conflicting final push leaves the conflict in place so the
    # finalize agent can resolve it (start mode aborts; push mode does not).
    d = base / "push-conflict"
    d.mkdir()
    remote, work = _init_remote(d, "w")
    (work / "a.txt").write_text("local change\n")
    git(work, "add", "a.txt")
    git(work, "commit", "-q", "-m", "local change")
    _remote_commit(remote, d, "w", content="remote change\n")
    res = sync_one(work, "push")
    _check(checks, "sync: conflicting final push leaves the merge to resolve",
           (not res["ok"]) and res.get("conflicted") == ["a.txt"]
           and "<<<<<<<" in (work / "a.txt").read_text()
           and (work / ".git" / "MERGE_HEAD").exists(),
           f"conflicted={res.get('conflicted')}")

    # 5. a remote that is ahead of local is fast-forwarded before a push.
    d = base / "push-behind"
    d.mkdir()
    remote, work = _init_remote(d, "w")
    _remote_commit(remote, d, "w")
    res = sync_one(work, "push")
    _check(checks, "sync: behind final push fast-forwards",
           res["ok"] and res["action"] == "fast-forwarded"
           and (work / "a.txt").read_text() == "two\n",
           f"action={res.get('action')} relation={res.get('relation')}")

    # 6. overlapping uncommitted edits block a fast-forward and survive it.
    d = base / "dirty"
    d.mkdir()
    remote, work = _init_remote(d, "w")
    _remote_commit(remote, d, "w")
    (work / "a.txt").write_text("local edit\n")
    res = sync_one(work, "start")
    _check(checks, "sync: overlapping dirty edit blocks and is preserved",
           (not res["ok"]) and (work / "a.txt").read_text() == "local edit\n",
           f"blockers={res.get('blockers')}")

    # 7. a staged change blocks before any merge runs.
    d = base / "staged"
    d.mkdir()
    remote, work = _init_remote(d, "w")
    _remote_commit(remote, d, "w")
    (work / "c.txt").write_text("staged\n")
    git(work, "add", "c.txt")
    res = sync_one(work, "start")
    _check(checks, "sync: staged change blocks before merge",
           (not res["ok"]) and res.get("staged") == ["c.txt"],
           f"staged={res.get('staged')}")

    # 7a. The private checkout is normally dirty after a phase: the runner
    # writes ledger.json/run.json after finalize's commit. When local HEAD
    # already equals the remote, start sync is a no-op and must not touch
    # those artifacts.
    d = base / "dirty-equal"
    d.mkdir()
    remote, work = _init_remote(d, "w")
    (work / "runs").mkdir()
    (work / "runs" / "ledger.json").write_text("{}\n")
    git(work, "add", "runs/ledger.json")
    git(work, "commit", "-q", "-m", "add ledger")
    git(work, "push", "-q", "origin", "main")
    (work / "runs" / "ledger.json").write_text('{"finalize": true}\n')
    res = sync_one(work, "start")
    _check(checks, "sync: dirty run artifacts do not block an up-to-date start",
           res["ok"] and res["action"] == "up-to-date"
           and (work / "runs" / "ledger.json").read_text()
           == '{"finalize": true}\n',
           f"action={res.get('action')}")

    # 7b. When the remote has moved, a fast-forward preserves dirty run
    # artifacts it does not touch.
    d = base / "dirty-unrelated"
    d.mkdir()
    remote, work = _init_remote(d, "w")
    (work / "runs").mkdir()
    (work / "runs" / "run.json").write_text("{}\n")
    git(work, "add", "runs/run.json")
    git(work, "commit", "-q", "-m", "add run")
    git(work, "push", "-q", "origin", "main")
    (work / "runs" / "run.json").write_text('{"state": "completed"}\n')
    _remote_commit(remote, d, "w")  # touches a.txt only
    res = sync_one(work, "start")
    _check(checks, "sync: ff preserves unrelated dirty run artifacts",
           res["ok"] and res["action"] == "fast-forwarded"
           and (work / "runs" / "run.json").read_text()
           == '{"state": "completed"}\n'
           and (work / "a.txt").read_text() == "two\n",
           f"action={res.get('action')}")

    # 8. sync_all fast-forwards both checkouts from their own remotes.
    d = base / "both"
    d.mkdir()
    pub_remote, pub = _init_remote(d, "pub")
    _remote_commit(pub_remote, d, "pub")
    nested = pub / PRIVATE_REL
    nested.parent.mkdir(parents=True, exist_ok=True)
    priv_remote, _ = _init_remote(d, "priv")
    subprocess.run(["git", "clone", "-q", str(priv_remote), str(nested)],
                   check=True, capture_output=True, text=True)
    git(nested, "config", "user.email", "sync-test@example.com")
    git(nested, "config", "user.name", "sync test")
    _remote_commit(priv_remote, d, "priv")
    res = sync_all(pub, "start")
    _check(checks, "sync: both checkouts fast-forward from own remotes",
           res["ok"] and all(r["action"] == "fast-forwarded"
                             for r in res["repos"]),
           res["summary"])

    # 9. a shared remote URL refuses both checkouts (private/public crossing).
    d = base / "shared"
    d.mkdir()
    remote, pub = _init_remote(d, "w")
    nested = pub / PRIVATE_REL
    nested.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "clone", "-q", str(remote), str(nested)],
                   check=True, capture_output=True, text=True)
    res = sync_all(pub, "start")
    _check(checks, "sync: shared remote URL refuses both checkouts",
           (not res["ok"]) and "share a Git push/fetch destination" in res["summary"],
           res["summary"])

    # 9b. a private pushurl aimed at the public remote is refused.
    d = base / "pushurl"
    d.mkdir()
    public_remote, pub = _init_remote(d, "pub")
    nested = pub / PRIVATE_REL
    nested.parent.mkdir(parents=True, exist_ok=True)
    private_remote, _ = _init_remote(d, "priv")
    subprocess.run(["git", "clone", "-q", str(private_remote), str(nested)],
                   check=True, capture_output=True, text=True)
    git(nested, "remote", "set-url", "--push", "origin", str(public_remote))
    res = sync_all(pub, "start")
    _check(checks, "sync: public pushurl boundary refuses both checkouts",
           (not res["ok"])
           and "share a Git push/fetch destination" in res["summary"],
           res["summary"])

    # 10. a fresh start commits and pushes only the private repo's runs/
    # leftovers, then the private tree is clean.
    d = base / "runstate"
    d.mkdir()
    _, pub = _init_remote(d, "pub")
    nested = pub / PRIVATE_REL
    nested.parent.mkdir(parents=True, exist_ok=True)
    priv_remote, _ = _init_remote(d, "priv")
    subprocess.run(["git", "clone", "-q", str(priv_remote), str(nested)],
                   check=True, capture_output=True, text=True)
    git(nested, "config", "user.email", "sync-test@example.com")
    git(nested, "config", "user.name", "sync test")
    (nested / "runs").mkdir()
    (nested / "runs" / "ledger.json").write_text("{}\n")
    git(nested, "add", "runs/ledger.json")
    git(nested, "commit", "-q", "-m", "ledger")
    git(nested, "push", "-q", "origin", "main")
    (nested / "runs" / "ledger.json").write_text('{"finalize": true}\n')
    res = commit_leftover_run_state(pub, "pipeline: test")
    _check(checks, "sync: start commits and pushes runs/ leftovers",
           res["ok"] and not dirty_paths(nested)
           and git(nested, "rev-parse", "HEAD")[1]
           == git(nested, "rev-parse", "origin/main")[1],
           res["summary"])

    # 10b. a dirty file outside runs/ blocks the start cleanup so a
    # half-finished edit is never auto-published.
    d = base / "runstate-outside"
    d.mkdir()
    _, pub = _init_remote(d, "pub")
    nested = pub / PRIVATE_REL
    nested.parent.mkdir(parents=True, exist_ok=True)
    priv_remote, _ = _init_remote(d, "priv")
    subprocess.run(["git", "clone", "-q", str(priv_remote), str(nested)],
                   check=True, capture_output=True, text=True)
    (nested / "priv.txt").write_text("human edit\n")
    res = commit_leftover_run_state(pub, "pipeline: test")
    _check(checks, "sync: start refuses dirty files outside runs/",
           (not res["ok"]) and "outside runs/" in res["summary"],
           res["summary"])

    # 11. Phase-scoped cleanup publishes only the requested run directory.
    d = base / "runstate-phase"
    d.mkdir()
    _, pub = _init_remote(d, "pub")
    nested = pub / PRIVATE_REL
    nested.parent.mkdir(parents=True, exist_ok=True)
    priv_remote, _ = _init_remote(d, "priv")
    subprocess.run(["git", "clone", "-q", str(priv_remote), str(nested)],
                   check=True, capture_output=True, text=True)
    git(nested, "config", "user.email", "sync-test@example.com")
    git(nested, "config", "user.name", "sync test")
    for number in (100440, 100601):
        path = nested / "runs" / f"phase-{number:06d}"
        path.mkdir(parents=True)
        (path / "run.json").write_text('{"state": "running"}\n')
    git(nested, "add", "runs")
    git(nested, "commit", "-q", "-m", "run dirs")
    git(nested, "push", "-q", "origin", "main")
    (nested / "runs" / "phase-100440" / "run.json").write_text('{"state": "completed"}\n')
    (nested / "runs" / "phase-100601" / "run.json").write_text('{"state": "blocked"}\n')
    res = commit_leftover_run_state(pub, "pipeline: phase test", phase=100440)
    _check(checks, "sync: cleanup is scoped to the current phase",
           res["ok"]
           and json.loads((nested / "runs" / "phase-100440" / "run.json").read_text())["state"] == "completed"
           and json.loads((nested / "runs" / "phase-100601" / "run.json").read_text())["state"] == "blocked"
           and "runs/phase-100601/run.json" in dirty_paths(nested),
           res["summary"])

    _check(checks, "publish: coordination failure maps to exit 2",
           result_exit_code({"ok": False, "state": "COORDINATION_UNAVAILABLE"}) == 2
           and result_exit_code({"ok": False, "state": "FENCED"}) == 1
           and result_exit_code({"ok": True, "state": "PUBLISHED"}) == 0,
           "state-specific exit codes")
    receipt_ok, receipt_detail = _publication_receipt_check(base)
    _check(checks, "publish: receipt-backed completion", receipt_ok,
           receipt_detail)

    return checks


def self_test():
    checks = self_test_checks()
    ok = all(c["ok"] for c in checks)
    print(json.dumps({"sync_self_test": "pass" if ok else "fail",
                      "checks": checks}, indent=2))
    return 0 if ok else 1


def result_exit_code(out):
    if out.get("state") in {"COORDINATION_UNAVAILABLE", "CONFIG_ERROR"}:
        return 2
    return 0 if out.get("ok") else 1


def main():
    ap = argparse.ArgumentParser(description="Fail-closed git sync.")
    ap.add_argument("--root", default=".",
                    help="repo root; syncs it and private/clio-private")
    ap.add_argument("--repo", default=None,
                    help="sync one checkout instead of --root")
    ap.add_argument("--mode", choices=["start", "push", "publish"], default="start",
                    help="start: sync before a phase; push: verify a "
                         "fast-forward; publish: claim-check and publish a phase")
    ap.add_argument("--phase", default=None,
                    help="phase number for --mode publish")
    ap.add_argument("--reservation-file", default=None,
                    help="phase-local reservation.json for --mode publish")
    ap.add_argument("--machine-id", default=None)
    ap.add_argument("--reservation-id", default=None)
    ap.add_argument("--generation", type=int, default=None)
    ap.add_argument("--self-test", action="store_true",
                    help="run stubbed-remote checks and exit")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    try:
        if args.mode == "publish":
            if args.phase is None:
                raise ConfigError("--phase is required with --mode publish")
            out = publish_phase(
                Path(args.root).resolve(), args.phase,
                reservation_file=args.reservation_file,
                machine_id=args.machine_id,
                reservation_id=args.reservation_id,
                generation=args.generation)
        elif args.repo:
            res = sync_one(Path(args.repo).resolve(), args.mode)
            out = {"ok": res["ok"], "mode": args.mode, "repos": [res],
                   "summary": summarize([res], args.mode)}
        else:
            out = sync_all(Path(args.root).resolve(), args.mode)
    except ConfigError as e:
        print(json.dumps({"ok": False, "mode": args.mode,
                          "state": "config_error", "error": str(e)}, indent=2))
        return 2
    print(json.dumps(out, indent=2))
    return result_exit_code(out)


if __name__ == "__main__":
    sys.exit(main())

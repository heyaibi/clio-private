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

``commit_leftover_run_state`` is the fresh-start cleanup: it commits and
pushes only the private repo's ``runs/`` leftovers (the runner writes
``ledger.json``/``run.json`` after finalize's commit) and refuses any dirty
path outside ``runs/``, so a half-finished human edit is never published.

Hard safety rules, enforced by construction:

* Never ``git pull`` (this repo sets ``pull.rebase = true``, which would
  rewrite history), never rebase, never force-push, never reset, never
  stash, never ``clean``. Fast-forward when possible, otherwise a plain
  merge commit; a real conflict is aborted in start mode.
* Giving up is the last resort: a mechanical fast-forward or a clean merge
  is preferred. Only a genuine conflict, a dirty index, or a detached HEAD
  stops the line, and then local work is reported, never discarded.
* The nested ``private/clio-private`` checkout is synced only from its own
  remote; if it shares the public repo's remote URL, both are refused, so
  private content can never cross into the public checkout.

Usage (run from the repo root):

    python3 private/clio-private/harness/gitsync.py --root . --mode start
    python3 private/clio-private/harness/gitsync.py --root . --mode push
    python3 private/clio-private/harness/gitsync.py --self-test

Exit codes: 0 synced/verified, 1 blocked (operator decision required),
2 config or usage error. JSON goes to stdout in every case.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
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


def remote_url(repo, remote):
    rc, out, _ = git(repo, "remote", "get-url", remote)
    return out if rc == 0 and out else None


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


def _upstream_url(repo):
    _, remote, _, why = resolve_upstream(repo)
    return None if why or not remote else remote_url(repo, remote)


def sync_all(root, mode):
    """Sync the public checkout and the nested private checkout, if present."""
    root = Path(root).resolve()
    repos = [root]
    nested = root / PRIVATE_REL
    if is_git_repo(nested):
        repos.append(nested)
    if len(repos) == 2:
        u_root, u_nested = _upstream_url(root), _upstream_url(nested)
        if u_root and u_nested and u_root == u_nested:
            reason = ("nested private repo and public repo share the same "
                      "remote URL; refusing to sync either checkout so "
                      "private content cannot cross into the public one")
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


def _commit_and_push_run_state(repo, message):
    """Commit the staged runs/ leftovers and push, retrying once after
    integrating a remote that moved. Never force-pushes."""
    branch, remote, remote_branch, why = resolve_upstream(repo)
    info = {"repo": str(repo)}
    if why:
        return blocked(info, why)
    git(repo, "add", "-A", "--", "runs")
    rc, out, err = git(repo, "commit", "-q", "-m", message)
    if rc != 0:
        return blocked(info, f"commit of run state failed: {err or out}")
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


def commit_leftover_run_state(root, message):
    """At a fresh start, commit and push only the private repo's runs/
    leftovers (the runner writes ledger.json/run.json after finalize's
    commit). Any dirty path outside runs/ in either checkout is a blocker
    for operator review, so a half-finished human edit is never published."""
    root = Path(root).resolve()
    private = root / PRIVATE_REL
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
        outside = [p for p in paths if not is_run_state(p)]
        inside = [p for p in paths if is_run_state(p)]
        if outside:
            results.append(blocked(
                {"repo": str(private)},
                "private checkout has changes outside runs/",
                dirty=outside,
                hint="commit or revert them, then rerun"))
        elif inside:
            results.append(_commit_and_push_run_state(private, message))
        else:
            results.append({"repo": str(private), "ok": True,
                            "action": "clean"})
    ok = all(r.get("ok") for r in results)
    return {"ok": ok, "mode": "start-clean", "repos": results,
            "summary": summarize(results, "start-clean")}


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
           (not res["ok"]) and "same remote URL" in res["summary"],
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

    return checks


def self_test():
    checks = self_test_checks()
    ok = all(c["ok"] for c in checks)
    print(json.dumps({"sync_self_test": "pass" if ok else "fail",
                      "checks": checks}, indent=2))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description="Fail-closed git sync.")
    ap.add_argument("--root", default=".",
                    help="repo root; syncs it and private/clio-private")
    ap.add_argument("--repo", default=None,
                    help="sync one checkout instead of --root")
    ap.add_argument("--mode", choices=["start", "push"], default="start",
                    help="start: fast-forward before a phase; "
                         "push: verify a fast-forward before publishing")
    ap.add_argument("--self-test", action="store_true",
                    help="run stubbed-remote checks and exit")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    try:
        if args.repo:
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
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

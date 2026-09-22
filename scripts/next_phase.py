#!/usr/bin/env python3
# Copyright 2026 Agent Memoir Developers (https://agentmemoir.com/)
# SPDX-License-Identifier: Apache-2.0
"""Pick the next uncompleted phase from the private roadmap.

Canonical layout: roadmap and workflow state live at
private/clio-private/roadmap and private/clio-private/.workflows in the
nested private repo. Root symlinks (roadmap/, .workflows/) preserve the old
call sites, so this script accepts both: it prefers the canonical private
paths and falls back to the root-level symlinks. Always invoke with the repo
root as cwd, e.g.:
  python3 private/clio-private/scripts/next_phase.py --repo .

A phase is complete when any of these holds:
  * private/clio-private/.workflows/phase-<N>/run.json exists with
    "state": "completed";
  * private/clio-private/.workflows/phase-<N>/ledger.json records a finalize
    step with signal "FINALIZE_DONE";
  * a private/clio-private/.workflows/phase-<N>/finalize-task-r*.log ends
    with FINALIZE_DONE;
  * the phase file carries a checked
    "- [x] ... Required approval is obtained" box (the finalize stage flips it);
  * private/clio-private/roadmap/index.md marks it Complete (row status or
    bold heading).

The index.md source exists because phase templates drift: some files never
carry the approval box. When index.md says Complete but no other marker is
present, we warn on stderr and still treat it as done, so a completed phase is
never silently re-run.

Prints "<number>\t<repo-relative path>" for the lowest incomplete phase and
exits 0; exits 1 when every phase is complete; exits 2 on a usage/state error.
Appendix files (phase-*-appendix-*.md) are references, never runnable phases.
"""
import argparse
import json
import re
import sys
import tempfile
from pathlib import Path

PHASE_RE = re.compile(r"^phase-(\d{4,6})-(?!appendix-).+\.md$")
INDEX_ROW_RE = re.compile(r"^\|\s*(\d{4,6})\s*\|")
INDEX_HEAD_RE = re.compile(r"^#{2,3}\s*(\d{4,6})\.\s")
APPROVAL = "Required approval is obtained"

PRIV = Path("private") / "clio-private"


def _resolve_dir(repo, name):
    """Canonical private dir first, root symlink second.

    repo/private/clio-private/<name> is authoritative. repo/<name> is the
    root symlink kept for back-compat. Returns None when neither exists.
    """
    canonical = repo / PRIV / name
    if canonical.is_dir():
        return canonical
    legacy = repo / name
    if legacy.is_dir():
        return legacy
    return None


def roadmap_dir(repo):
    return _resolve_dir(repo, "roadmap")


def workflows_dir(repo):
    return _resolve_dir(repo, ".workflows")


def file_approved(path):
    for line in path.read_text(errors="replace").splitlines():
        stripped = line.strip()
        if stripped.startswith("- [x]") and APPROVAL in stripped:
            return True
    return False


def run_dir(repo, number):
    base = workflows_dir(repo)
    if base is None:
        base = repo / PRIV / ".workflows"
    return base / f"phase-{number:06d}"


def run_completed(repo, number):
    rj = run_dir(repo, number) / "run.json"
    try:
        state = json.loads(rj.read_text())
    except (OSError, ValueError):
        return False
    return isinstance(state, dict) and state.get("state") == "completed"


def ledger_steps(repo, number):
    """Parsed steps map from ledger.json, or None when missing/unusable."""
    try:
        ledger = json.loads((run_dir(repo, number) / "ledger.json").read_text())
    except (OSError, ValueError):
        return None
    if not isinstance(ledger, dict):
        return None
    steps = ledger.get("steps")
    return steps if isinstance(steps, dict) else None


def ledger_present(repo, number):
    """A ledger.json exists and parses far enough to carry step proofs."""
    return ledger_steps(repo, number) is not None


def ledger_finalized(repo, number):
    """ledger.json records a finalize step with signal FINALIZE_DONE."""
    steps = ledger_steps(repo, number)
    if steps is None:
        return False
    fin = steps.get("finalize")
    return isinstance(fin, dict) and fin.get("signal") == "FINALIZE_DONE"


def finalize_log_done(repo, number):
    """A finalize-task-r*.log ends with a FINALIZE_DONE signal line."""
    try:
        logs = sorted(run_dir(repo, number).glob("finalize-task-r*.log"))
    except OSError:
        return False
    for log in logs:
        try:
            lines = log.read_text(errors="replace").splitlines()
        except OSError:
            continue
        for line in reversed(lines):
            stripped = line.strip()
            if not stripped:
                continue
            if stripped == "FINALIZE_DONE" or stripped.startswith("FINALIZE_DONE "):
                return True
            break
    return False


def index_complete(repo):
    """Phase numbers marked Complete in roadmap/index.md."""
    base = roadmap_dir(repo)
    if base is None:
        return set()
    path = base / "index.md"
    try:
        text = path.read_text(errors="replace")
    except OSError:
        return set()
    done = set()
    for line in text.splitlines():
        row = INDEX_ROW_RE.match(line)
        if row and "Complete" in line:
            done.add(int(row.group(1)))
            continue
        head = INDEX_HEAD_RE.match(line)
        if head and "**Complete**" in line:
            done.add(int(head.group(1)))
    return done


def is_done(repo, number, path, index_done):
    if run_completed(repo, number) or file_approved(path):
        return True
    if ledger_present(repo, number):
        # The ledger is runner-maintained and re-verified on resume; when it
        # parses, it outranks the raw agent-written finalize log, so a stale
        # DONE log cannot override a ledger with no finalize entry.
        return ledger_finalized(repo, number)
    if finalize_log_done(repo, number):
        return True
    if number in index_done:
        print(f"warning: phase {number} is marked Complete in index.md but has "
              f"no run.json/ledger/finalize-log/approval marker; treating it "
              f"as done",
              file=sys.stderr)
        return True
    return False


def candidates(repo):
    out = []
    base = roadmap_dir(repo)
    if base is None:
        return out
    for path in sorted(base.glob("phase-*.md")):
        match = PHASE_RE.match(path.name)
        if match:
            out.append((int(match.group(1)), path))
    return sorted(out)


def signals(repo, number, path, index_done):
    """Per-signal completion evidence for one phase (verbose/audit output)."""
    return {
        "run": run_completed(repo, number),
        "ledger": ledger_finalized(repo, number),
        "finalize_log": finalize_log_done(repo, number),
        "approval": file_approved(path),
        "index": number in index_done,
    }


def audit(repo):
    """Report index.md drift without editing anything. Returns issue count."""
    index_done = index_complete(repo)
    issues = 0
    for number, path in candidates(repo):
        s = signals(repo, number, path, index_done)
        markers = s["run"] or s["ledger"] or s["finalize_log"] or s["approval"]
        indexed = number in index_done
        if indexed and not markers:
            print(f"drift: phase {number} indexed Complete but has no marker "
                  f"({path.name})")
            issues += 1
        elif markers and not indexed:
            print(f"drift: phase {number} has completion markers but index is "
                  f"not Complete ({path.name})")
            issues += 1
    return issues


def select_next(repo):
    index_done = index_complete(repo)
    for number, path in candidates(repo):
        if not is_done(repo, number, path, index_done):
            return number, path
    return None


def self_test():
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        (repo / "roadmap").mkdir()
        (repo / ".workflows" / "phase-100030").mkdir(parents=True)
        (repo / ".workflows" / "phase-100040").mkdir(parents=True)
        (repo / "roadmap" / "phase-100010-alpha.md").write_text(
            "- [x] Required approval is obtained.\n")
        (repo / "roadmap" / "phase-100020-appendix-notes.md").write_text("x\n")
        (repo / "roadmap" / "phase-100020-beta.md").write_text(
            "- [ ] Required approval is obtained.\n")
        (repo / "roadmap" / "phase-100030-gamma.md").write_text("x\n")
        (repo / ".workflows" / "phase-100030" / "run.json").write_text(
            json.dumps({"state": "completed"}))
        # 100040: only index.md marks it Complete (template drift case).
        (repo / "roadmap" / "phase-100040-delta.md").write_text("x\n")
        (repo / ".workflows" / "phase-100040" / "run.json").write_text(
            json.dumps({"state": "rejected"}))
        (repo / "roadmap" / "index.md").write_text(
            "| 100040 | `1×` | [x](phase-100040-delta.md) | Complete — PASS |\n"
            "| 100020 | `1×` | [x](phase-100020-beta.md) | Plan ready |\n"
            "## 100010. alpha · `1×` · **Complete** · [x](phase-100010-alpha.md)\n")
        got = select_next(repo)
        assert got is not None and got[0] == 100020, got
        assert got[1].name == "phase-100020-beta.md", got
        (repo / "roadmap" / "phase-100020-beta.md").write_text(
            "- [x] Required approval is obtained.\n")
        assert select_next(repo) is None, select_next(repo)
    with tempfile.TemporaryDirectory() as tmp:
        # Each machine signal on its own phase: ledger-only and log-only each
        # count; a ledger without finalize outranks a stale DONE log; BLOCKED
        # logs and bare run dirs never count.
        repo = Path(tmp)
        (repo / "roadmap").mkdir()
        unchecked = "- [ ] Required approval is obtained.\n"
        (repo / "roadmap" / "phase-100010-alpha.md").write_text(unchecked)
        rd = repo / ".workflows" / "phase-100010"
        rd.mkdir(parents=True)
        (rd / "ledger.json").write_text(
            json.dumps({"steps": {"finalize": {"signal": "FINALIZE_DONE"}}}))
        (repo / "roadmap" / "phase-100020-beta.md").write_text(unchecked)
        rd2 = repo / ".workflows" / "phase-100020"
        rd2.mkdir(parents=True)
        (rd2 / "finalize-task-r1.log").write_text(
            "2026-01-01T00:00:00Z close-out complete\nFINALIZE_DONE r1nonce\n")
        (repo / "roadmap" / "phase-100030-gamma.md").write_text(unchecked)
        rd3 = repo / ".workflows" / "phase-100030"
        rd3.mkdir(parents=True)
        (rd3 / "ledger.json").write_text(
            json.dumps({"steps": {"developer": {"signal": "DEVELOPER_DONE"}}}))
        (rd3 / "finalize-task-r1.log").write_text(
            "2026-01-01T00:00:00Z close-out complete\nFINALIZE_DONE\n")
        (repo / "roadmap" / "phase-100040-delta.md").write_text(unchecked)
        rd4 = repo / ".workflows" / "phase-100040"
        rd4.mkdir(parents=True)
        (rd4 / "finalize-task-r1.log").write_text(
            "2026-01-01T00:00:00Z close-out blocked\nFINALIZE_BLOCKED: trouble\n")
        (repo / "roadmap" / "phase-100050-epsilon.md").write_text(unchecked)
        (repo / ".workflows" / "phase-100050").mkdir(parents=True)
        (repo / "roadmap" / "phase-100060-zeta.md").write_text(unchecked)
        got = select_next(repo)
        assert got is not None and got[0] == 100030, got
        assert got[1].name == "phase-100030-gamma.md", got
    with tempfile.TemporaryDirectory() as tmp:
        # Canonical private layout: private/clio-private/roadmap +
        # private/clio-private/.workflows. Helpers must prefer it and the
        # reported path must stay repo-relative for --input phase_file.
        repo = Path(tmp)
        priv_map = repo / PRIV / "roadmap"
        priv_wf = repo / PRIV / ".workflows" / "phase-100010"
        priv_map.mkdir(parents=True)
        priv_wf.mkdir(parents=True)
        (priv_map / "phase-100010-alpha.md").write_text(
            "- [ ] Required approval is obtained.\n")
        (priv_map / "index.md").write_text("Plan ready\n")
        assert roadmap_dir(repo) == priv_map, roadmap_dir(repo)
        assert workflows_dir(repo) == priv_wf.parent, workflows_dir(repo)
        got = select_next(repo)
        assert got is not None and got[0] == 100010, got
        assert got[1].relative_to(repo) == (
            PRIV / "roadmap" / "phase-100010-alpha.md"), got
    print("next_phase self-test: pass")


def main():
    parser = argparse.ArgumentParser(description="Next uncompleted roadmap phase.")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--verbose", action="store_true",
                        help="print per-signal evidence for every phase to stderr")
    parser.add_argument("--audit", action="store_true",
                        help="report index.md drift without changing anything; "
                             "exit 0 when clean, 1 when drift is found")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    repo = Path(args.repo).resolve()
    if roadmap_dir(repo) is None:
        print(f"error: no roadmap/ under {repo} "
              f"(looked for {PRIV}/roadmap and ./roadmap)", file=sys.stderr)
        return 2
    if args.audit:
        return 0 if audit(repo) == 0 else 1
    if args.verbose:
        index_done = index_complete(repo)
        for number, path in candidates(repo):
            s = signals(repo, number, path, index_done)
            print(f"{number}\t{path.name}\trun={int(s['run'])} "
                  f"ledger={int(s['ledger'])} log={int(s['finalize_log'])} "
                  f"box={int(s['approval'])} index={int(s['index'])}",
                  file=sys.stderr)
    nxt = select_next(repo)
    if nxt is None:
        return 1
    number, path = nxt
    print(f"{number}\t{path.relative_to(repo)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

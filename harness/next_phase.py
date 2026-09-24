#!/usr/bin/env python3
# Copyright 2026 Agent Memoir Developers (https://agentmemoir.com/)
# SPDX-License-Identifier: Apache-2.0
"""Pick the next uncompleted phase from the private roadmap.

Canonical layout: roadmap and run state live at
private/clio-private/roadmap and private/clio-private/runs in the
nested private repo. Always invoke with the repo root as cwd, e.g.:
  python3 private/clio-private/harness/next_phase.py --repo .

A phase is complete when any of these holds:
  * private/clio-private/runs/phase-<N>/run.json exists with
    "state": "completed";
  * private/clio-private/runs/phase-<N>/ledger.json records a finalize
    step with signal "FINALIZE_DONE";
  * private/clio-private/runs/phase-<N>/publication.json records a
    claim-checked published completion;
  * a private/clio-private/runs/phase-<N>/finalize-task-r*.log ends
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
With ``--server`` it first consults the private reservation board, reserves the
lowest incomplete phase, and prints a JSON result. It returns 3 with
``WAIT_FOR_CLAIM`` when that phase is owned by another live reservation.
Appendix files (phase-*-appendix-*.md) are references, never runnable phases.
Parked phases (number >= 900000) are roadmap-only and are ignored by selection,
audit, and verbose output.
"""
import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from phase_policy import is_runnable_phase  # noqa: E402 - path set just above
from phase_reservations import (  # noqa: E402 - path set just above
    CoordinationError,
    ReservationConflict,
    ReservationStore,
    reservation_file,
    save_reservation_file,
)

PHASE_RE = re.compile(r"^phase-(\d{4,6})-(?!appendix-).+\.md$")
INDEX_ROW_RE = re.compile(r"^\|\s*(\d{4,6})\s*\|")
INDEX_HEAD_RE = re.compile(r"^#{2,3}\s*(\d{4,6})\.\s")
APPROVAL = "Required approval is obtained"

PRIV = Path("private") / "clio-private"


def _resolve_dir(repo, name):
    """Canonical private dir first, legacy layout second.

    repo/private/clio-private/<name> is authoritative. repo/<name> is the
    legacy fallback. Returns None when neither exists.
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


def runs_dir(repo):
    return _resolve_dir(repo, "runs")


def file_approved(path):
    for line in path.read_text(errors="replace").splitlines():
        stripped = line.strip()
        if stripped.startswith("- [x]") and APPROVAL in stripped:
            return True
    return False


def run_dir(repo, number):
    base = runs_dir(repo)
    if base is None:
        base = repo / PRIV / "runs"
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


def publication_receipt_done(repo, number):
    path = run_dir(repo, number) / "publication.json"
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return False
    return (isinstance(data, dict)
            and data.get("version") == 1
            and data.get("state") == "published"
            and data.get("phase") == f"{int(number):06d}")


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
            number = int(row.group(1))
            if is_runnable_phase(number):
                done.add(number)
            continue
        head = INDEX_HEAD_RE.match(line)
        if head and "**Complete**" in line:
            number = int(head.group(1))
            if is_runnable_phase(number):
                done.add(number)
    return done


def is_done(repo, number, path, index_done):
    if (run_completed(repo, number) or file_approved(path)
            or publication_receipt_done(repo, number)):
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
              f"no run.json/ledger/publication/finalize-log/approval marker; treating it "
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
        if match and is_runnable_phase(int(match.group(1))):
            out.append((int(match.group(1)), path))
    return sorted(out)


def signals(repo, number, path, index_done):
    """Per-signal completion evidence for one phase (verbose/audit output)."""
    return {
        "run": run_completed(repo, number),
        "ledger": ledger_finalized(repo, number),
        "finalize_log": finalize_log_done(repo, number),
        "publication": publication_receipt_done(repo, number),
        "approval": file_approved(path),
        "index": number in index_done,
    }


def audit(repo):
    """Report index.md drift without editing anything. Returns issue count."""
    index_done = index_complete(repo)
    issues = 0
    for number, path in candidates(repo):
        s = signals(repo, number, path, index_done)
        markers = (s["run"] or s["ledger"] or s["finalize_log"]
                   or s["publication"] or s["approval"])
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


def _reservation_result(number, path, record, state="RESERVED"):
    return {
        "state": state,
        "phase": f"{number:06d}",
        "path": str(path),
        "machine_id": record.get("machine_id"),
        "status": record.get("status"),
        "reservation_id": record.get("reservation_id"),
        "generation": record.get("generation"),
        "run_id": record.get("run_id"),
    }


def select_server_phase(repo, machine_id, *, reserve=True, store=None):
    """Select the lowest incomplete phase and claim it on the shared board.

    A future claim is intentionally ignored until it becomes the lowest
    unfinished phase.  At that point the server waits; it never jumps over a
    blocked, paused, rejected, or actively running phase.
    """
    machine_id = machine_id or os.environ.get("CLIO_MACHINE_ID", "local-01")
    store = store or ReservationStore(repo)
    state, _commit = store.read()
    index_done = index_complete(repo)
    for number, path in candidates(repo):
        key = f"{number:06d}"
        record = state.get("phases", {}).get(key)
        if record is not None:
            status = record.get("status")
            if status in {"claimed", "running", "paused", "blocked"}:
                return {
                    "state": "WAIT_FOR_CLAIM",
                    "phase": key,
                    "path": str(path.relative_to(repo)),
                    "owner": record.get("machine_id"),
                    "status": status,
                    "reservation_id": record.get("reservation_id"),
                    "generation": record.get("generation"),
                }
            if status == "completed":
                if is_done(repo, number, path, index_done):
                    continue
                return {
                    "state": "COORDINATION_INCONSISTENT",
                    "phase": key,
                    "path": str(path.relative_to(repo)),
                    "error": "coordination says completed but no completion evidence exists",
                }
            return {
                "state": "WAIT_FOR_CLAIM",
                "phase": key,
                "path": str(path.relative_to(repo)),
                "owner": record.get("machine_id"),
                "status": status,
                "reservation_id": record.get("reservation_id"),
                "generation": record.get("generation"),
                "error": "explicit operator takeover is required",
            }
        if is_done(repo, number, path, index_done):
            continue
        if not reserve:
            result = _reservation_result(number, path, {}, "AVAILABLE")
            result["path"] = str(path.relative_to(repo))
            return result
        try:
            record = store.reserve(number, machine_id,
                                   run_id=f"phase-{key}")
        except ReservationConflict as exc:
            # The push race lost.  Read the winner rather than attempting an
            # overwrite or silently selecting a later phase.
            latest, _latest_commit = store.read()
            winner = latest.get("phases", {}).get(key, {})
            return {
                "state": "WAIT_FOR_CLAIM",
                "phase": key,
                "path": str(path.relative_to(repo)),
                "owner": winner.get("machine_id", exc.record.get("machine_id")),
                "status": winner.get("status", exc.record.get("status")),
                "reservation_id": winner.get("reservation_id"),
                "generation": winner.get("generation"),
            }
        result = _reservation_result(number, path, record)
        result["path"] = str(path.relative_to(repo))
        token_path = reservation_file(repo, number)
        try:
            save_reservation_file(token_path, record)
        except OSError as exc:
            raise CoordinationError(
                f"could not persist phase reservation token: {exc}") from exc
        return result
    return {"state": "NO_PHASE"}


def self_test():
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        (repo / "roadmap").mkdir()
        (repo / "runs" / "phase-100030").mkdir(parents=True)
        (repo / "runs" / "phase-100040").mkdir(parents=True)
        (repo / "roadmap" / "phase-100010-alpha.md").write_text(
            "- [x] Required approval is obtained.\n")
        (repo / "roadmap" / "phase-100020-appendix-notes.md").write_text("x\n")
        (repo / "roadmap" / "phase-100020-beta.md").write_text(
            "- [ ] Required approval is obtained.\n")
        (repo / "roadmap" / "phase-100030-gamma.md").write_text("x\n")
        (repo / "runs" / "phase-100030" / "run.json").write_text(
            json.dumps({"state": "completed"}))
        # 100040: only index.md marks it Complete (template drift case).
        (repo / "roadmap" / "phase-100040-delta.md").write_text("x\n")
        (repo / "runs" / "phase-100040" / "run.json").write_text(
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
        # Parked phases stay visible in the roadmap but are never selected.
        repo = Path(tmp)
        (repo / "roadmap").mkdir()
        (repo / "roadmap" / "phase-100010-alpha.md").write_text(
            "- [x] Required approval is obtained.\n")
        (repo / "roadmap" / "phase-900999-parked.md").write_text("x\n")
        (repo / "roadmap" / "index.md").write_text("Plan ready\n")
        assert select_next(repo) is None, select_next(repo)
        assert [n for n, _ in candidates(repo)] == [100010], candidates(repo)
    with tempfile.TemporaryDirectory() as tmp:
        # Each machine signal on its own phase: ledger-only and log-only each
        # count; a ledger without finalize outranks a stale DONE log; BLOCKED
        # logs and bare run dirs never count.
        repo = Path(tmp)
        (repo / "roadmap").mkdir()
        unchecked = "- [ ] Required approval is obtained.\n"
        (repo / "roadmap" / "phase-100010-alpha.md").write_text(unchecked)
        rd = repo / "runs" / "phase-100010"
        rd.mkdir(parents=True)
        (rd / "ledger.json").write_text(
            json.dumps({"steps": {"finalize": {"signal": "FINALIZE_DONE"}}}))
        (repo / "roadmap" / "phase-100020-beta.md").write_text(unchecked)
        rd2 = repo / "runs" / "phase-100020"
        rd2.mkdir(parents=True)
        (rd2 / "finalize-task-r1.log").write_text(
            "2026-01-01T00:00:00Z close-out complete\nFINALIZE_DONE r1nonce\n")
        (repo / "roadmap" / "phase-100030-gamma.md").write_text(unchecked)
        rd3 = repo / "runs" / "phase-100030"
        rd3.mkdir(parents=True)
        (rd3 / "ledger.json").write_text(
            json.dumps({"steps": {"developer": {"signal": "DEVELOPER_DONE"}}}))
        (rd3 / "finalize-task-r1.log").write_text(
            "2026-01-01T00:00:00Z close-out complete\nFINALIZE_DONE\n")
        (repo / "roadmap" / "phase-100040-delta.md").write_text(unchecked)
        rd4 = repo / "runs" / "phase-100040"
        rd4.mkdir(parents=True)
        (rd4 / "finalize-task-r1.log").write_text(
            "2026-01-01T00:00:00Z close-out blocked\nFINALIZE_BLOCKED: trouble\n")
        (repo / "roadmap" / "phase-100050-epsilon.md").write_text(unchecked)
        (repo / "runs" / "phase-100050").mkdir(parents=True)
        (repo / "roadmap" / "phase-100060-zeta.md").write_text(unchecked)
        got = select_next(repo)
        assert got is not None and got[0] == 100030, got
        assert got[1].name == "phase-100030-gamma.md", got
    with tempfile.TemporaryDirectory() as tmp:
        # Canonical private layout: private/clio-private/roadmap +
        # private/clio-private/runs. Helpers must prefer it and the
        # reported path must stay repo-relative for --input phase_file.
        repo = Path(tmp)
        priv_map = repo / PRIV / "roadmap"
        priv_wf = repo / PRIV / "runs" / "phase-100010"
        priv_map.mkdir(parents=True)
        priv_wf.mkdir(parents=True)
        (priv_map / "phase-100010-alpha.md").write_text(
            "- [ ] Required approval is obtained.\n")
        (priv_map / "index.md").write_text("Plan ready\n")
        assert roadmap_dir(repo) == priv_map, roadmap_dir(repo)
        assert runs_dir(repo) == priv_wf.parent, runs_dir(repo)
        got = select_next(repo)
        assert got is not None and got[0] == 100010, got
        assert got[1].relative_to(repo) == (
            PRIV / "roadmap" / "phase-100010-alpha.md"), got
    with tempfile.TemporaryDirectory() as tmp:
        class FakeStore:
            def __init__(self):
                self.state = {"version": 1, "phases": {}}
                self.reserved = []

            def read(self):
                return self.state, "fake"

            def reserve(self, phase, machine_id, **kwargs):
                record = {
                    "phase": f"{int(phase):06d}",
                    "machine_id": machine_id,
                    "reservation_id": f"rsv-{machine_id}",
                    "generation": 1,
                    "run_id": f"phase-{int(phase):06d}",
                }
                self.state["phases"][f"{int(phase):06d}"] = record
                self.reserved.append((int(phase), machine_id))
                return record

        repo = Path(tmp).resolve()
        (repo / "roadmap").mkdir()
        for number in (100440, 100460, 100601):
            (repo / "roadmap" / f"phase-{number}-synthetic.md").write_text("x\\n")
        fake = FakeStore()
        got = select_server_phase(repo, "server-01", store=fake)
        assert got["state"] == "RESERVED" and got["phase"] == "100440", got
        fake.state["phases"]["100440"]["status"] = "completed"
        (repo / PRIV / "runs" / "phase-100440").mkdir(parents=True, exist_ok=True)
        (repo / PRIV / "runs" / "phase-100440" / "run.json").write_text(
            json.dumps({"state": "completed"}))
        fake.state["phases"]["100601"] = {
            "status": "claimed", "machine_id": "local-01",
            "reservation_id": "rsv-local", "generation": 1,
            "run_id": "phase-100601",
        }
        got = select_server_phase(repo, "server-01", store=fake)
        assert got["state"] == "RESERVED" and got["phase"] == "100460", got
        fake.state["phases"]["100460"]["status"] = "completed"
        (repo / PRIV / "runs" / "phase-100460").mkdir(parents=True, exist_ok=True)
        (repo / PRIV / "runs" / "phase-100460" / "run.json").write_text(
            json.dumps({"state": "completed"}))
        got = select_server_phase(repo, "server-01", store=fake, reserve=False)
        assert got["state"] == "WAIT_FOR_CLAIM" and got["phase"] == "100601", got

        class FailingStore(FakeStore):
            def reserve(self, phase, machine_id, **kwargs):
                raise CoordinationError("coordination push failed")

        try:
            select_server_phase(repo, "server-01", store=FailingStore())
            launch_refused = False
        except CoordinationError:
            launch_refused = True
        assert launch_refused
    with tempfile.TemporaryDirectory() as tmp:
        # Exercise the real Git-backed store through the selector rather than
        # relying only on FakeStore for cross-machine ordering.
        from phase_reservations import _git_test_repo, _self_test_receipt
        remote, clients = _git_test_repo(Path(tmp), "real-ordering")
        repo = Path(tmp) / "root"
        nested = repo / PRIV
        (nested / "roadmap").mkdir(parents=True)
        (nested / "runs").mkdir()
        (nested / "roadmap" / "index.md").write_text("Plan ready\n")
        for number in (100440, 100460, 100601, 100602):
            (nested / "roadmap" / f"phase-{number}-synthetic.md").write_text("x\n")
        store_server = ReservationStore(repo, private_repo=clients[0])
        store_local = ReservationStore(repo, private_repo=clients[1])
        first = select_server_phase(repo, "server-01", store=store_server)
        assert first["state"] == "RESERVED" and first["phase"] == "100440", first
        local = store_local.reserve(100601, "local-01")
        (nested / "runs" / "phase-100601").mkdir()
        (nested / "runs" / "phase-100601" / "run.json").write_text(
            json.dumps({"state": "completed"}))
        local_receipt = _self_test_receipt(store_local, local)
        store_local.set_status(local, "completed", evidence_path=local_receipt)
        server = dict(store_server.read()[0]["phases"]["100440"])
        server["phase"] = "100440"
        (nested / "runs" / "phase-100440").mkdir(exist_ok=True)
        (nested / "runs" / "phase-100440" / "run.json").write_text(
            json.dumps({"state": "completed"}))
        server_receipt = _self_test_receipt(store_server, server)
        store_server.set_status(server, "completed", evidence_path=server_receipt)
        following = select_server_phase(repo, "server-01", store=store_server)
        assert following["state"] == "RESERVED" and following["phase"] == "100460", following
        following_record = dict(store_server.read()[0]["phases"]["100460"])
        following_record["phase"] = "100460"
        (nested / "runs" / "phase-100460").mkdir(exist_ok=True)
        (nested / "runs" / "phase-100460" / "run.json").write_text(
            json.dumps({"state": "completed"}))
        following_receipt = _self_test_receipt(
            store_server, following_record)
        store_server.set_status(
            following_record, "completed", evidence_path=following_receipt)
        store_local.reserve(100602, "local-01")
        waiting = select_server_phase(repo, "server-01", store=store_server)
        assert waiting["state"] == "WAIT_FOR_CLAIM" and waiting["phase"] == "100602", waiting

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
    parser.add_argument("--server", action="store_true",
                        help="select and reserve the lowest incomplete phase")
    parser.add_argument("--read-only", action="store_true",
                        help="with --server, inspect claims without writing")
    parser.add_argument("--machine-id", default=None,
                        help="stable host ID used by --server")
    parser.add_argument("--json", action="store_true",
                        help="with --server, print a machine-readable result")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    repo = Path(args.repo).resolve()
    if roadmap_dir(repo) is None:
        print(f"error: no roadmap/ under {repo} "
              f"(looked for {PRIV}/roadmap and ./roadmap)", file=sys.stderr)
        return 2
    if args.server:
        try:
            result = select_server_phase(
                repo, args.machine_id, reserve=not args.read_only)
        except CoordinationError as exc:
            result = {"state": "COORDINATION_UNAVAILABLE", "error": str(exc)}
            print(json.dumps(result, sort_keys=True))
            return 2
        print(json.dumps(result, sort_keys=True))
        return {"RESERVED": 0, "AVAILABLE": 0, "NO_PHASE": 1,
                "WAIT_FOR_CLAIM": 3,
                "COORDINATION_INCONSISTENT": 2}.get(result["state"], 2)
    if args.audit:
        return 0 if audit(repo) == 0 else 1
    if args.verbose:
        index_done = index_complete(repo)
        for number, path in candidates(repo):
            s = signals(repo, number, path, index_done)
            print(f"{number}\t{path.name}\trun={int(s['run'])} "
                  f"ledger={int(s['ledger'])} log={int(s['finalize_log'])} "
                  f"publication={int(s['publication'])} "
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

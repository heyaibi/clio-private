#!/usr/bin/env python3
"""Drive the real `clio mcp stdio` entry point with a snapshot-bearing store.

Phase-100760 reproduction (undeclared non-empty snapshot leaf).

Usage: driver.py BEFORE|AFTER
- BEFORE: control (declared-valid snapshot) + undeclared-leaf snapshot.
- AFTER: same two, plus nested and list undeclared-leaf probes.
"""
import json
import subprocess
import sys
import pathlib

DB = pathlib.Path("/tmp/opencode/clio-leaf-repro.db")
BIN = "/home/e1rcv4ogdmzught4sw9be5k2/clio/target/debug/clio"
SOURCE = "Ada met 1,000 users on 2026-04-03"

BASE_SNAP = {"entity": "Ada", "amount": 1000}


def req(i, method, params=None):
    msg = {"jsonrpc": "2.0", "id": i, "method": method}
    if params is not None:
        msg["params"] = params
    return msg


def call_store(proc, i, item_id, snapshot, extra_keys_note):
    snap = dict(BASE_SNAP)
    snap.update(snapshot)
    args = {
        "item": {"id": item_id, "gist": "Ada paid 1,000", "snapshot": snap},
        "category": "persona",
        "epistemic_kind": "fact",
        "source_text": SOURCE,
        "confidence": 0.9,
    }
    proc.stdin.write(json.dumps(req(i, "tools/call", {"name": "store", "arguments": args})) + "\n")
    proc.stdin.flush()


def call_get_snapshot(proc, i, item_id):
    proc.stdin.write(json.dumps(req(i, "tools/call", {"name": "get_snapshot", "arguments": {"item_id": item_id}})) + "\n")
    proc.stdin.flush()


def read_resp(proc, want_id):
    while True:
        line = proc.stdout.readline()
        if not line:
            raise RuntimeError("server closed stdout")
        msg = json.loads(line)
        if msg.get("id") == want_id:
            return msg


def main(mode):
    DB.unlink(missing_ok=True)
    proc = subprocess.Popen(
        [BIN, "mcp", "stdion" if False else "stdio", "--backend", "sqlite", "--db", str(DB)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    i = 0
    proc.stdin.write(json.dumps(req(i, "initialize", {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "repro", "version": "0"}})) + "\n")
    proc.stdin.flush()
    init = read_resp(proc, i)
    i += 1
    proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
    proc.stdin.flush()

    def store_and_report(item_id, snapshot, label):
        nonlocal i
        i += 1
        call_store(proc, i, item_id, snapshot, label)
        resp = read_resp(proc, i)
        content = resp.get("result", {})
        texts = "".join(c.get("text", "") for c in content.get("content", []) if isinstance(c, dict))
        decision = None
        try:
            decision = json.loads(texts)
        except Exception:
            decision = {"raw": texts}
        print(f"--- {label}: store -> pass={decision.get('pass')} reason={decision.get('rejection_reason')} id={decision.get('id')}")
        if decision.get("id"):
            i += 1
            call_get_snapshot(proc, i, decision["id"])
            sresp = read_resp(proc, i)
            stexts = "".join(c.get("text", "") for c in sresp.get("result", {}).get("content", []) if isinstance(c, dict))
            print(f"    get_snapshot -> {stexts}")

    print(f"initialize -> ok server={init['result']['serverInfo'] if 'serverInfo' in init.get('result', {}) else init.get('result')}")
    store_and_report("itm-leaf-control-1", {}, "control: declared-valid only")
    store_and_report("itm-leaf-top-1", {"invented_note": "unverified paraphrase"}, "undeclared TOP-LEVEL leaf")
    if mode == "AFTER":
        store_and_report("itm-leaf-nested-1", {"invented": {"deep": "unverified"}}, "undeclared NESTED leaf")
        store_and_report("itm-leaf-list-1", {"invented_list": ["a", "b"]}, "undeclared LIST leaf")
    proc.stdin.close()
    proc.wait(timeout=30)
    err = proc.stderr.read()
    if err.strip():
        print("--- stderr tail:", err.strip()[-600:])


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "BEFORE")
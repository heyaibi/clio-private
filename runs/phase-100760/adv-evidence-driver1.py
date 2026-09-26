#!/usr/bin/env python3
"""Adversary check: does an undeclared snapshot KEY leak into logs/rejection?

Drives the real `clio mcp stdio` entry point. Stores:
  1. control        - declared-only snapshot
  2. unlisted value - undeclared key, ordinary value
  3. secret in KEY  - undeclared key that is itself a secret-looking string
  4. secret in VALUE- undeclared key, secret-looking value (for contrast)
"""
import json
import pathlib
import subprocess
import sys

DB = pathlib.Path("/tmp/opencode/adv-leaf/adv.db")
BIN = "/home/e1rcv4ogdmzught4sw9be5k2/clio/target/debug/clio"
SOURCE = "Ada met 1,000 users on 2026-04-03"
BASE = {"entity": "Ada", "amount": 1000}


def req(i, method, params=None):
    m = {"jsonrpc": "2.0", "id": i, "method": method}
    if params is not None:
        m["params"] = params
    return m


def read_resp(proc, want):
    while True:
        line = proc.stdout.readline()
        if not line:
            raise RuntimeError("server closed stdout")
        msg = json.loads(line)
        if msg.get("id") == want:
            return msg


def main():
    DB.parent.mkdir(parents=True, exist_ok=True)
    DB.unlink(missing_ok=True)
    proc = subprocess.Popen(
        [BIN, "mcp", "stdio", "--backend", "sqlite", "--db", str(DB)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    i = 0
    proc.stdin.write(json.dumps(req(i, "initialize", {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "adv", "version": "0"}})) + "\n")
    proc.stdin.flush()
    read_resp(proc, i)
    proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
    proc.stdin.flush()

    def store(item_id, extra, label):
        nonlocal i
        i += 1
        snap = dict(BASE)
        snap.update(extra)
        args = {"item": {"id": item_id, "gist": "g", "snapshot": snap},
                "category": "persona", "epistemic_kind": "fact",
                "source_text": SOURCE, "confidence": 0.9}
        proc.stdin.write(json.dumps(req(i, "tools/call", {"name": "store", "arguments": args})) + "\n")
        proc.stdin.flush()
        resp = read_resp(proc, i)
        content = resp.get("result", {})
        texts = "".join(c.get("text", "") for c in content.get("content", []) if isinstance(c, dict))
        try:
            d = json.loads(texts)
        except Exception:
            d = {"raw": texts}
        print(f"--- {label}\n    pass={d.get('pass')} reason={d.get('rejection_reason')} id={d.get('id')}")

    store("itm-adv-1", {}, "1 control (declared only)")
    store("itm-adv-2", {"invented_note": "unverified paraphrase"}, "2 unlisted key, plain value")
    store("itm-adv-3", {"sk-live-LEAKEDKEY99": "x"}, "3 SECRET IN KEY NAME")
    store("itm-adv-4", {"api_key": "sk-live-LEAKEDVALUE88"}, "4 secret in value (contrast)")
    proc.stdin.close()
    proc.wait(timeout=60)
    err = proc.stderr.read()
    print("=== stderr ===")
    print(err.strip()[-4000:])


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Adversary check: does a previously-accepted non-default snapshot still work?

Exercises the public MCP tools that run span verification with
default_event_fields(): store, admit_preview, canonical_put.
"""
import json
import pathlib
import subprocess

DB = pathlib.Path("/tmp/opencode/adv-leaf/adv2.db")
BIN = "/home/e1rcv4ogdmzught4sw9be5k2/clio/target/debug/clio"
SOURCE = "primary_database_host is db-1.internal, port 5432, owned by the platform team."


def req(i, method, params=None):
    m = {"jsonrpc": "2.0", "id": i, "method": method}
    if params is not None:
        m["params"] = params
    return m


def read_resp(proc, want):
    while True:
        line = proc.stdout.readline()
        if not line:
            raise RuntimeError("closed")
        m = json.loads(line)
        if m.get("id") == want:
            return m


def main():
    DB.parent.mkdir(parents=True, exist_ok=True)
    DB.unlink(missing_ok=True)
    p = subprocess.Popen([BIN, "mcp", "stdio", "--backend", "sqlite", "--db", str(DB)],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL, text=True)
    i = 0
    p.stdin.write(json.dumps(req(i, "initialize", {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "adv", "version": "0"}})) + "\n")
    p.stdin.flush()
    read_resp(p, i)
    p.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
    p.stdin.flush()

    def call(name, args, label):
        nonlocal i
        i += 1
        p.stdin.write(json.dumps(req(i, "tools/call", {"name": name, "arguments": args})) + "\n")
        p.stdin.flush()
        r = read_resp(p, i)
        c = r.get("result", {})
        t = "".join(x.get("text", "") for x in c.get("content", []) if isinstance(x, dict))
        try:
            d = json.loads(t)
        except Exception:
            d = {"raw": t[:300]}
        print(f"--- {label}\n    ok={d.get('ok')} pass={d.get('pass')} reason={d.get('rejection_reason')} err={d.get('message')}")

    # canonical_put: snapshot describing a canonical slot, no entity/amount/date.
    call("canonical_put", {
        "key": "primary_database_host",
        "value": "db-1.internal",
        "category": "tool_config",
        "epistemic_kind": "fact",
        "snapshot": {"host": "db-1.internal", "port": 5432},
        "source_text": SOURCE,
    }, "canonical_put with {host,port} snapshot")

    # canonical_put with the declared-only shape, for contrast.
    call("canonical_put", {
        "key": "primary_database_host",
        "value": "db-1.internal",
        "category": "tool_config",
        "epistemic_kind": "fact",
        "snapshot": {"entity": "db-1.internal"},
        "source_text": SOURCE,
    }, "canonical_put with {entity} snapshot (declared)")

    # store with a rich but grounded snapshot.
    call("store", {
        "item": {"id": "itm-adv-rich", "gist": "db host",
                 "snapshot": {"entity": "db-1.internal", "owner": "platform team"}},
        "category": "tool_config", "epistemic_kind": "fact", "source_text": SOURCE,
    }, "store with {entity,owner} snapshot")

    p.stdin.close()
    p.wait(timeout=60)


if __name__ == "__main__":
    main()

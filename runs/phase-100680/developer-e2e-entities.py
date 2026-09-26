#!/usr/bin/env python3
"""Real-binary end-to-end check for the per-hit entities[] array.

Drives the built `clio` binary: MCP stdio transport for the write and the
retrieve, then the CLI `recall` and the CLI health surfaces against the same
store. Prints the payloads and asserts the boundary rules.
"""
import json
import subprocess
import sys
import os

REPO = "/home/e1rcv4ogdmzught4sw9be5k2/clio"
BIN = os.path.join(REPO, "target/debug/clio")
DB = "/tmp/opencode/ent-e2e.db"
BANK = "ent-e2e"
ENTITY = "Ada Lovelace"

if os.path.exists(DB):
    os.remove(DB)

requests = [
    {"jsonrpc": "2.0", "id": 1, "method": "initialize",
     "params": {"protocolVersion": "2025-11-25", "capabilities": {},
                "clientInfo": {"name": "e2e", "version": "0"}}},
    {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
     "params": {"name": "store", "arguments": {
         "item": {"id": "e2e-named", "subject_id": "subj",
                  "gist": "a note that mentions nothing by name",
                  "snapshot": {"entity": ENTITY, "amount": 1, "date": "2024-01-01"}},
         "category": "task_spec", "epistemic_kind": "fact",
         "source_text": "the Ada Lovelace note records amount 1 on 2024-01-01",
         "bank": BANK, "actor": "agent", "timestamp": "2024-01-01T00:00:00Z"}}},
    {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
     "params": {"name": "triple_add", "arguments": {
         "subject": "rust", "predicate": "used_by", "object": "agent",
         "epistemic_kind": "fact", "bank": BANK, "actor": "agent",
         "timestamp": "2024-01-01T00:00:00Z"}}},
]

reads = [
    {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
     "params": {"name": "retrieve", "arguments": {
         "bank": BANK, "query": "Lovelace", "limit": 5, "explain": True}}},
    {"jsonrpc": "2.0", "id": 5, "method": "tools/call",
     "params": {"name": "diagnose", "arguments": {"timestamp": "2024-01-01T00:00:00Z"}}},
    {"jsonrpc": "2.0", "id": 6, "method": "tools/call",
     "params": {"name": "verify", "arguments": {"bank": BANK, "timestamp": "2024-01-01T00:00:00Z"}}},
]

payload = "".join(json.dumps(r) + "\n" for r in requests)
proc = subprocess.run([BIN, "mcp", "stdio", "--db", DB, "--backend", "sqlite", "--bank", BANK],
                      input=payload, capture_output=True, text=True, timeout=180)
print("=== MCP stdio exit:", proc.returncode)
if proc.stderr.strip():
    print("stderr:", proc.stderr.strip()[:500])
responses = {}
for line in proc.stdout.splitlines():
    msg = json.loads(line)
    responses[msg["id"]] = msg

reindex = subprocess.run([BIN, "ops", "reindex", "--db", DB, "--backend", "sqlite",
                          "--target", "lexical", "--confirm"],
                         capture_output=True, text=True, timeout=300)
print("=== CLI ops reindex --target lexical (exit", reindex.returncode, ") ===")
print(reindex.stdout[:400])

proc2 = subprocess.run([BIN, "mcp", "stdio", "--db", DB, "--backend", "sqlite", "--bank", BANK],
                       input="".join(json.dumps(r) + "\n" for r in reads),
                       capture_output=True, text=True, timeout=180)
print("=== MCP stdio read session exit:", proc2.returncode)
for line in proc2.stdout.splitlines():
    msg = json.loads(line)
    responses[msg["id"]] = msg

store = responses[2]["result"]["structuredContent"]
print("store ok:", store["ok"], "item:", store.get("item_id"))
retrieve = responses[3]["result"]["structuredContent"]
print("=== MCP retrieve payload ===")
print(json.dumps(retrieve, indent=1, sort_keys=True))

hits = retrieve["hits"]
assert len(hits) == 1, hits
assert hits[0]["entities"] == [ENTITY], hits[0]["entities"]
explanation = retrieve["explanation"]
stripped = json.loads(json.dumps(retrieve))
for hit in stripped["hits"]:
    hit.pop("entities")
assert ENTITY not in json.dumps(stripped), "entity name outside hits[].entities"
assert "entity" not in json.dumps(explanation).lower(), explanation
print("MCP boundary ok: entity name only under hits[].entities; not in explanation/warnings")

for tool_id, name in ((5, "diagnose"), (6, "verify")):
    report = json.dumps(responses[tool_id]["result"]["structuredContent"])
    assert ENTITY not in report, f"{name} leaked the entity name: {report}"
print("MCP health boundary ok: diagnose/verify carry no entity name")

def cli(*args):
    out = subprocess.run([BIN, "--db", DB, "--backend", "sqlite", "--bank", BANK, *args],
                         capture_output=True, text=True, timeout=180)
    return out

recall_json = cli("recall", "Lovelace", "--limit", "5", "--output", "json")
print("=== CLI recall --output json (exit", recall_json.returncode, ") ===")
print(recall_json.stdout)
payload = json.loads(recall_json.stdout)
assert payload["hits"][0]["entities"] == [ENTITY], payload["hits"][0]

recall_text = cli("recall", "Lovelace", "--limit", "5", "--output", "text")
print("=== CLI recall --output text (exit", recall_text.returncode, ") ===")
print(recall_text.stdout)
assert ENTITY not in recall_text.stdout, "text view leaked an entity name"

for verb in ("ops diagnose", "ops verify"):
    health = cli(*verb.split())
    print(f"=== CLI {verb} (exit {health.returncode}) entity present: {ENTITY in health.stdout} ===")
    assert ENTITY not in health.stdout, f"{verb} leaked the entity name"

# `clio recall` has no --explain flag (the MCP retrieve tool owns the trace),
# so the CLI half of the boundary check is the text view plus the health verbs.
recall_explain = cli("recall", "Lovelace", "--limit", "5", "--explain", "--output", "json")
print("=== CLI recall --explain is a pre-existing usage error (exit",
      recall_explain.returncode, "):", recall_explain.stdout.strip()[:120])

print("ALL REAL-BINARY CHECKS PASSED")

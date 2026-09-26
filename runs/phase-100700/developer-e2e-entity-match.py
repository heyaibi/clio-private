#!/usr/bin/env python3
"""Real-binary end-to-end check for the derived per-hit `entity_match` reason.

Drives the built `clio` binary: MCP stdio transport for the write and the
retrieve (with `explain=true`), then the CLI `recall` JSON and text views and
the CLI health surfaces against the same store. Asserts the flag, the derived
text line, the absent-key case, and the diagnostic boundary.

Usage: python3 developer-e2e-entity-match.py [repo-root]
"""
import json
import os
import subprocess
import sys

REPO = sys.argv[1] if len(sys.argv) > 1 else "/Users/aiuser/Documents/projects/agentmemoir/clio"
BIN = os.path.join(REPO, "target/debug/clio")
DB = "/tmp/opencode/entity-match-e2e.db"
BANK = "match-e2e"
ENTITY = "Ada Lovelace"
MATCH_QUERY = "Ada Lovelace note"
PLAIN_QUERY = "mentions"

if os.path.exists(DB):
    os.remove(DB)

writes = [
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
]

reads = [
    {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
     "params": {"name": "reindex", "arguments": {
         "bank": BANK, "target": "lexical", "dry_run": False, "confirm": True}}},
    {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
     "params": {"name": "retrieve", "arguments": {
         "bank": BANK, "query": MATCH_QUERY, "limit": 5, "explain": True}}},
    {"jsonrpc": "2.0", "id": 5, "method": "tools/call",
     "params": {"name": "retrieve", "arguments": {
         "bank": BANK, "query": PLAIN_QUERY, "limit": 5}}},
]

proc = subprocess.run([BIN, "mcp", "stdio", "--db", DB, "--backend", "sqlite", "--bank", BANK],
                      input="".join(json.dumps(r) + "\n" for r in writes),
                      capture_output=True, text=True, timeout=180)
print("=== MCP stdio write session exit:", proc.returncode)
if proc.stderr.strip():
    print("stderr:", proc.stderr.strip()[:500])

proc2 = subprocess.run([BIN, "mcp", "stdio", "--db", DB, "--backend", "sqlite", "--bank", BANK],
                       input="".join(json.dumps(r) + "\n" for r in reads),
                       capture_output=True, text=True, timeout=180)
print("=== MCP stdio reindex+read session exit:", proc2.returncode)
responses = {}
for line in proc2.stdout.splitlines():
    msg = json.loads(line)
    responses[msg["id"]] = msg

reindex = responses[3]["result"]["structuredContent"]
print("=== MCP reindex --target lexical ===")
print(json.dumps(reindex, sort_keys=True))
assert reindex["ok"] is True, reindex
assert reindex["lexical_applied"] >= 1, reindex

matched = responses[4]["result"]["structuredContent"]
print("=== MCP retrieve (matching query) ===")
print(json.dumps(matched, indent=1, sort_keys=True))
named = next(h for h in matched["hits"] if h["item_id"] == "e2e-named")
assert named["entities"] == [ENTITY], named["entities"]
assert named.get("entity_match") is True, named
explanation = matched["explanation"]
assert "entity_match" not in json.dumps(explanation), explanation
stripped = json.loads(json.dumps(matched))
for hit in stripped["hits"]:
    hit.pop("entity_match")
assert "entity_match" not in json.dumps(stripped), "reason outside the hit objects"
print("MCP ok: flag only on the matching hit; explanation carries no entity_match")

plain = responses[5]["result"]["structuredContent"]
print("=== MCP retrieve (non-matching query) ===")
print(json.dumps(plain, indent=1, sort_keys=True))
plain_named = next(h for h in plain["hits"] if h["item_id"] == "e2e-named")
assert "entity_match" not in plain_named, plain_named
print("MCP ok: a non-matching query omits the key entirely")


def cli(*args):
    return subprocess.run([BIN, "--db", DB, "--backend", "sqlite", "--bank", BANK, *args],
                          capture_output=True, text=True, timeout=180)


recall_json = cli("recall", MATCH_QUERY, "--limit", "5", "--output", "json")
print("=== CLI recall --output json (exit", recall_json.returncode, ") ===")
print(recall_json.stdout)
payload = json.loads(recall_json.stdout)
cli_named = next(h for h in payload["hits"] if h["item_id"] == "e2e-named")
assert cli_named.get("entity_match") is True, cli_named
assert cli_named["entities"] == [ENTITY], cli_named

recall_text = cli("recall", MATCH_QUERY, "--limit", "5", "--output", "text")
print("=== CLI recall --output text (exit", recall_text.returncode, ") ===")
print(recall_text.stdout)
assert ("     [derived] entity match (display-only; not a ranking signal)"
        in recall_text.stdout), recall_text.stdout
for line in recall_text.stdout.splitlines():
    if line.startswith("Results for:"):
        continue
    assert ENTITY not in line, f"text view leaked an entity name: {line}"
print("CLI ok: JSON flag and text line agree; no entity name outside the query echo")

plain_text = cli("recall", PLAIN_QUERY, "--limit", "5", "--output", "text")
print("=== CLI recall text (non-matching query) ===")
print(plain_text.stdout)
assert "[derived]" not in plain_text.stdout, plain_text.stdout
print("CLI ok: a non-matching query prints no derived line")

for verb in ("ops diagnose", "ops verify"):
    health = cli(*verb.split())
    print(f"=== CLI {verb} (exit {health.returncode}) entity present: {ENTITY in health.stdout} ===")
    assert ENTITY not in health.stdout, f"{verb} leaked the entity name"

print("ALL REAL-BINARY CHECKS PASSED")

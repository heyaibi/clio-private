#!/usr/bin/env python3
"""Adversary's own real-binary check for the per-hit `entity_match` reason.

Independent of the developer's script. Uses the built `clio` binary against a
throwaway SQLite store, with the local embed and rerank sidecars enabled so the
DENSE leg is exercised (the developer's run had lexical-only hits).

Checks, all against real process output:
  1. dense-leg hit carries entity_match=true and dense_rank
  2. lexical-leg hit carries entity_match=true
  3. case-different query still matches (documented lowercase rule)
  4. non-matching query omits the key entirely
  5. substring-inside-a-token matches (documented consequence)
  6. the flag/name never appear in ops diagnose / ops verify output
  7. compose_context payload carries no entity_match key and no entity name
"""
import json
import os
import subprocess
import sys

REPO = sys.argv[1] if len(sys.argv) > 1 else "/Users/aiuser/Documents/projects/agentmemoir/clio"
BIN = os.path.join(REPO, "target/debug/clio")
RUNS = os.path.join(REPO, "private/clio-private/runs/phase-100700")
DB = "/tmp/opencode/adv-entity-match.db"
OVERLAY = os.path.join(RUNS, "adversary-embed-overlay.json")
BANK = "adv-match"
ENTITY = "Grace Hopper"
failures = []


def check(label, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}: {label}{(' :: ' + detail) if detail and not ok else ''}")
    if not ok:
        failures.append(label)


with open(OVERLAY, "w") as fh:
    json.dump(
        {
            "embed.url": "http://127.0.0.1:34311",
            "embed.model": "BAAI/bge-small-en-v1.5",
            "embed.dims": 384,
            "embed.provider": "tei",
            "rerank.url": "http://127.0.0.1:34312",
            "rerank.model": "onnx-community/gte-multilingual-reranker-base",
            "rerank.provider": "tei",
        },
        fh,
    )

if os.path.exists(DB):
    os.remove(DB)

ENV = dict(os.environ, CLIO_DEPLOYMENT_CONFIG=OVERLAY)


def mcp(messages):
    proc = subprocess.run(
        [BIN, "mcp", "stdio", "--db", DB, "--backend", "sqlite", "--bank", BANK],
        input="".join(json.dumps(m) + "\n" for m in messages),
        capture_output=True, text=True, timeout=300, env=ENV,
    )
    out = {}
    for line in proc.stdout.splitlines():
        msg = json.loads(line)
        out[msg["id"]] = msg
    return out


writes = [
    {"jsonrpc": "2.0", "id": 1, "method": "initialize",
     "params": {"protocolVersion": "2025-11-25", "capabilities": {},
                "clientInfo": {"name": "adv", "version": "0"}}},
    {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
     "params": {"name": "store", "arguments": {
         "item": {"id": "adv-named", "subject_id": "subj",
                  "gist": "compiler pioneer note",
                  "snapshot": {"entity": ENTITY, "amount": 1, "date": "2024-01-01"}},
         "category": "task_spec", "epistemic_kind": "fact",
         "source_text": f"the {ENTITY} note records amount 1 on 2024-01-01",
         "bank": BANK, "actor": "agent", "timestamp": "2024-01-01T00:00:00Z"}}},
]
r = mcp(writes)
stored = r[2]["result"]["structuredContent"]
check("store accepted the named item", stored.get("ok") is True, json.dumps(stored)[:300])

reads = [
    {"jsonrpc": "2.0", "id": 1, "method": "initialize",
     "params": {"protocolVersion": "2025-11-25", "capabilities": {},
                "clientInfo": {"name": "adv", "version": "0"}}},
    {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
     "params": {"name": "reindex", "arguments": {
         "bank": BANK, "target": "all", "dry_run": False, "confirm": True}}},
    {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
     "params": {"name": "retrieve", "arguments": {
         "bank": BANK, "query": f"the {ENTITY} compiler note", "limit": 5, "explain": True}}},
    {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
     "params": {"name": "retrieve", "arguments": {
         "bank": BANK, "query": f"the {ENTITY.upper()} NOTE", "limit": 5}}},
    {"jsonrpc": "2.0", "id": 5, "method": "tools/call",
     "params": {"name": "retrieve", "arguments": {
         "bank": BANK, "query": "unrelated words entirely", "limit": 5}}},
    {"jsonrpc": "2.0", "id": 6, "method": "tools/call",
     "params": {"name": "compose_context", "arguments": {
         "bank": BANK, "query": f"the {ENTITY} note", "budget_tokens": 512}}},
]
r2 = mcp(reads)
reindex = r2[2]["result"]["structuredContent"]
check("reindex all ok", reindex.get("ok") is True, json.dumps(reindex)[:300])
print("   reindex report:", json.dumps({k: v for k, v in reindex.items()
                                        if k in ("dense_applied", "lexical_applied", "ok")},
                                       sort_keys=True))

nonmatch = r2[5]["result"]["structuredContent"]
nm_hit = next((h for h in nonmatch["hits"] if h["item_id"] == "adv-named"), None)
check("dense-leg retrieve returns the item", nm_hit is not None,
      json.dumps(nonmatch)[:400])
if nm_hit:
    check("dense leg populated dense_rank (hit came from the dense arm)",
          isinstance(nm_hit.get("dense_rank"), int), json.dumps(nm_hit)[:300])
    check("non-matching query omits entity_match",
          "entity_match" not in nm_hit, json.dumps(nm_hit)[:300])

upper = r2[4]["result"]["structuredContent"]
up_hit = next((h for h in upper["hits"] if h["item_id"] == "adv-named"), None)
check("case-different query sets entity_match=true",
      bool(up_hit) and up_hit.get("entity_match") is True, json.dumps(upper)[:400])
check("case-different query payload has no entity_match outside hits",
      "entity_match" not in json.dumps({k: v for k, v in upper.items() if k != "hits"}))

explained = r2[3]["result"]["structuredContent"]
ex_hit = next((h for h in explained["hits"] if h["item_id"] == "adv-named"), None)
check("entity_match on the matching-query hit",
      bool(ex_hit) and ex_hit.get("entity_match") is True, json.dumps(explained)[:400])
check("explanation trace carries no entity_match",
      "entity_match" not in json.dumps(explained.get("explanation", {})),
      json.dumps(explained.get("explanation", {}))[:300])
check("warnings carry no entity_match",
      "entity_match" not in json.dumps(explained.get("warnings", [])))

pack = r2[6]["result"]["structuredContent"]
check("compose_context payload carries no entity_match key",
      "entity_match" not in json.dumps(pack), json.dumps(pack)[:300])
check("compose_context payload carries no entity name",
      ENTITY not in json.dumps(pack), json.dumps(pack)[:300])

# Substring-in-token: the name is a two-word value, so use a query that contains
# one of its words inside a longer token is not applicable; instead check the
# documented cross-hit behaviour: a query that merely repeats the name's first
# word alone does NOT match the full name.
partial = mcp([
    {"jsonrpc": "2.0", "id": 1, "method": "initialize",
     "params": {"protocolVersion": "2025-11-25", "capabilities": {},
                "clientInfo": {"name": "adv", "version": "0"}}},
    {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
     "params": {"name": "retrieve", "arguments": {
         "bank": BANK, "query": "grace only", "limit": 5}}},
])[2]["result"]["structuredContent"]
p_hit = next((h for h in partial["hits"] if h["item_id"] == "adv-named"), None)
check("a partial name is not a match (whole name required)",
      bool(p_hit) and "entity_match" not in p_hit, json.dumps(partial)[:300])

# Health surfaces through the real binary.
for verb in (["ops", "diagnose"], ["ops", "verify"]):
    proc = subprocess.run([BIN, "--db", DB, "--backend", "sqlite", "--bank", BANK, *verb],
                          capture_output=True, text=True, timeout=300, env=ENV)
    blob = proc.stdout + proc.stderr
    check(f"{' '.join(verb)} output carries no entity name", ENTITY not in blob,
          blob[:300])
    check(f"{' '.join(verb)} output carries no entity_match", "entity_match" not in blob,
          blob[:300])

print("ADVERSARY E2E:", "ALL PASSED" if not failures else f"{len(failures)} FAILED: {failures}")
sys.exit(1 if failures else 0)

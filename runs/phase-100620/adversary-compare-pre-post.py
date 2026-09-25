#!/usr/bin/env python3
"""Adversary r1 helper: compare pre-change and post-change `clio recall --output json`.

Read-only against the repository. It writes only under the run directory and a
scratch directory in $HOME (because /tmp is mounted noexec).

What it proves:
  * the hit order, the top-level `score`, `dense_rank`, `lexical_rank`,
    `consolidated`, and the `dedup` counters are byte-identical between the
    pre-change binary and the staged post-change binary on the same data;
  * the only payload difference is the new per-hit `scores` object.

Item timestamps are pushed into the future so `recency_score` returns exactly
1.0 (`age <= 0.0`), which removes the wall-clock term and makes the fused
score bit-reproducible across the two runs.
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys

RUN = os.path.dirname(os.path.abspath(__file__))
PRE = os.path.join(os.path.expanduser("~"), "adv-scratch", "pre", "target", "debug", "clio")
POST = "/home/e1rcv4ogdmzught4sw9be5k2/clio/target/debug/clio"
SCRATCH = os.path.join(os.path.expanduser("~"), "adv-scratch", "dbs")
FUTURE = "2099-01-01T00:00:00Z"
BANK = "cmpbank"
ITEMS = [
    "The staging deploy retries on ECONNRESET with exponential backoff",
    "Postgres ts_rank_cd scoring differs from sqlite bm25 ranking",
    "Reciprocal rank fusion uses k equal to sixty",
    "Unrelated note about gardening and tomato varieties",
]
QUERY = "deploy retry backoff fusion scoring"


def seed(binary: str, db: str) -> None:
    if os.path.exists(db):
        os.remove(db)
    env = dict(os.environ, CLIO_DEPLOYMENT_CONFIG="/nonexistent/deployment.json")
    for text in ITEMS:
        subprocess.run(
            [binary, "--db", db, "--backend", "sqlite", "--bank", BANK,
             "remember", text, "--category", "task_spec"],
            check=True, capture_output=True, env=env, timeout=180,
        )
    con = sqlite3.connect(db)
    con.execute("UPDATE items SET created_at=?, updated_at=?", (FUTURE, FUTURE))
    con.commit()
    rows = con.execute("SELECT count(*) FROM items").fetchone()[0]
    con.close()
    if rows != len(ITEMS):
        raise SystemExit(f"expected {len(ITEMS)} items, found {rows}")


def recall(binary: str, db: str, query: str = QUERY, explain: bool = False) -> dict:
    env = dict(os.environ, CLIO_DEPLOYMENT_CONFIG="/nonexistent/deployment.json")
    argv = [binary, "--db", db, "--backend", "sqlite", "--bank", BANK,
            "recall", query, "--output", "json", "--limit", "10"]
    if explain:
        argv.append("--explain")
    out = subprocess.run(
        argv, check=True, capture_output=True, text=True, env=env, timeout=180,
    )
    return json.loads(out.stdout)


def anonymize(value, ids: dict[str, str]):
    """Replace random per-database item ids with `<id-N>` in first-seen order.

    Two separate stores mint different item ids for the same content, so the ids
    must be normalized before the payloads can be compared. Everything else,
    including `score` and `lexical_rank`, is compared verbatim.
    """
    if isinstance(value, dict):
        return {k: anonymize(v, ids) for k, v in value.items()}
    if isinstance(value, list):
        return [anonymize(v, ids) for v in value]
    if isinstance(value, str) and value.startswith("itm-"):
        return ids.setdefault(value, f"<id-{len(ids)}>")
    return value


def stable_view(payload: dict) -> dict:
    """Everything except the new per-hit `scores` object, wall-clock metrics, and ids."""
    view = {k: v for k, v in payload.items() if k != "metrics"}
    hits = [
        {k: v for k, v in hit.items() if k != "scores"}
        for hit in view.get("hits", [])
    ]
    view["hits"] = hits
    return anonymize(view, {})


def main() -> int:
    os.makedirs(SCRATCH, exist_ok=True)
    # ONE shared store, seeded once. Two separately seeded stores are not
    # comparable: the write path stores slightly different `admission_score`
    # values for the same text run to run (observed 0.77 vs 0.7699999228395211
    # in clio-admission, which this phase does not touch), and `admission_score`
    # feeds the fused score through the importance boost.
    db = os.path.join(SCRATCH, "shared.db")
    seed(POST, db)
    pre = recall(PRE, db)
    post = recall(POST, db)

    failures: list[str] = []

    pre_view, post_view = stable_view(pre), stable_view(post)
    if pre_view != post_view:
        failures.append("non-`scores` payload differs between pre and post")
        for key in sorted(set(pre_view) | set(post_view)):
            if pre_view.get(key) != post_view.get(key):
                failures.append(f"  key {key!r}: pre={pre_view.get(key)!r} post={post_view.get(key)!r}")

    pre_hits, post_hits = pre.get("hits", []), post.get("hits", [])
    if len(pre_hits) != len(post_hits):
        failures.append(f"hit count differs: pre={len(pre_hits)} post={len(post_hits)}")
    if not post_hits:
        failures.append("no hits returned; comparison is vacuous")

    for a, b in zip(pre_hits, post_hits):
        if a["score"] != b["score"]:
            failures.append(f"top-level score differs: {a['score']!r} vs {b['score']!r}")
        if b["scores"]["final"] != b["score"]:
            failures.append(f"scores.final != score: {b['scores']['final']!r} vs {b['score']!r}")
        if sorted(b["scores"]) != ["final", "keyword", "reranker", "semantic"]:
            failures.append(f"unexpected scores keys: {sorted(b['scores'])}")
        if b["scores"]["reranker"] is not None:
            failures.append("scores.reranker is not null")

    report = {
        "hits": len(post_hits),
        "pre_scores": [h["score"] for h in pre_hits],
        "post_scores": [h["score"] for h in post_hits],
        "post_scores_object": [h["scores"] for h in post_hits],
        "pre_has_scores_object": "scores" in (pre_hits[0] if pre_hits else {}),
        "dedup_pre": pre.get("dedup"),
        "dedup_post": post.get("dedup"),
        "scenarios": [],
        "failures": failures,
    }

    # Second and third scenarios: two more queries, to widen the sample. The
    # hand-written `explanation` trace is not reachable from the CLI (no
    # `--explain` flag on `clio recall`), so it is verified by diff inspection:
    # `crates/clio-mcp/src/read_retrieve.rs` changes by +4 lines, test-module
    # registration only.
    for label, query in (
        ("second-query", "postgres bm25 ranking fusion"),
        ("third-query-no-match", "quantum chromodynamics lattice"),
    ):
        a = recall(PRE, db, query)
        b = recall(POST, db, query)
        same = stable_view(a) == stable_view(b)
        report["scenarios"].append({
            "scenario": label,
            "query": query,
            "hits": len(b.get("hits", [])),
            "pre_scores": [h["score"] for h in a.get("hits", [])],
            "post_scores": [h["score"] for h in b.get("hits", [])],
            "identical_excluding_scores": same,
        })
        if not same:
            failures.append(f"non-`scores` payload differs in scenario {label}")

    report["failures"] = failures
    with open(os.path.join(RUN, "adversary-pre-post-compare.json"), "w") as handle:
        json.dump(report, handle, indent=2)
    print(json.dumps(report, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

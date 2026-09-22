#!/usr/bin/env python3
"""Extractor quality tests — FR-4 fidelity against NuExtract (Compose extract).

Two layers (requirement.md §4.4 / §8):
  1. Unit: span_verify admits good snapshots and rejects paraphrases/hallucinations.
  2. Live: call EXTRACT_URL with coding-agent fixtures; require parseable JSON,
     template keys, span-faithful leaves, and gold-field verbatim matches.

Release bar (§8): ≥99% verbatim on admitted items for numbers/names/dates.
This harness reports fidelity and fails if live gold-field hit-rate is below
--min-fidelity (default 0.99). Use --min-fidelity 0.8 for a softer baseline
check on untuned NuExtract-tiny.

Usage:
  python3 private/clio-private/scripts/extract_quality.py              # unit + live if healthy
  python3 private/clio-private/scripts/extract_quality.py --unit-only
  python3 private/clio-private/scripts/extract_quality.py --live-only
  python3 private/clio-private/scripts/extract_quality.py --min-fidelity 0.8
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from span_verify import VerifyResult, parse_extract_output, verify_snapshot  # noqa: E402

EXTRACT_URL = "http://127.0.0.1:34313"


@dataclass(frozen=True)
class Case:
    id: str
    source: str
    template: dict[str, Any]
    # Fields that MUST appear verbatim in snapshot when present in source.
    gold: dict[str, str]
    # If True, expect model to leave field empty (absent from source).
    expect_empty: tuple[str, ...] = ()


# Coding-agent held-out style fixtures (numbers / names / error codes / dates).
CASES: list[Case] = [
    Case(
        id="borrow_e0382",
        source=(
            "User said: the build failed with E0382 borrow of moved value.\n"
            "Lesson: clone before move when both paths need ownership."
        ),
        template={"error": "", "lesson": ""},
        gold={"error": "E0382"},
    ),
    Case(
        id="rust_version",
        source="CI uses Rust 1.75.0 on ubuntu-22.04 for the clio build.",
        template={"rust_version": "", "os": ""},
        gold={"rust_version": "1.75.0", "os": "ubuntu-22.04"},
    ),
    Case(
        id="ports",
        source="Postgres listens on 34310; embed TEI on 34311; rerank on 34312.",
        template={"postgres_port": "", "embed_port": "", "rerank_port": ""},
        gold={"postgres_port": "34310", "embed_port": "34311", "rerank_port": "34312"},
    ),
    Case(
        id="oom_137",
        source="Container clio-rerank-1 exited with code 137 after using 6GB during warmup.",
        template={"exit_code": "", "service": "", "memory": ""},
        gold={"exit_code": "137", "service": "clio-rerank-1", "memory": "6GB"},
    ),
    Case(
        id="person_timeout",
        source="Owner Alice set HTTP timeout_seconds 30 on date 2026-09-16 for the extract probe.",
        template={"owner": "", "timeout_seconds": "", "date": ""},
        gold={"owner": "Alice", "timeout_seconds": "30", "date": "2026-09-16"},
    ),
    Case(
        id="model_ids",
        source=(
            "Embedder is BAAI/bge-small-en-v1.5; reranker is "
            "onnx-community/gte-multilingual-reranker-base."
        ),
        template={"embed_model": "", "rerank_model": ""},
        gold={
            "embed_model": "BAAI/bge-small-en-v1.5",
            "rerank_model": "onnx-community/gte-multilingual-reranker-base",
        },
    ),
    Case(
        id="file_line",
        source="panic at file src/memory/admit.rs line 214 bank_id default admission score NaN",
        template={"file": "", "line": "", "bank_id": ""},
        gold={"file": "src/memory/admit.rs", "line": "214", "bank_id": "default"},
    ),
    Case(
        id="absent_version",
        source="The deploy finished successfully with no further notes.",
        template={"version": "", "status": ""},
        gold={},
        expect_empty=("version",),
    ),
    Case(
        id="commit_sha",
        source="Merged commit ee277c2 into master after the load probe passed.",
        template={"commit": "", "branch": ""},
        gold={"commit": "ee277c2", "branch": "master"},
    ),
    Case(
        id="latency_numbers",
        source="Rerank p95 was 1.8 seconds; extract p95 was 2.0 seconds under smoke load.",
        template={"rerank_p95_s": "", "extract_p95_s": ""},
        gold={"rerank_p95_s": "1.8", "extract_p95_s": "2.0"},
    ),
]


def nuextract_prompt(template: dict[str, Any], source: str) -> str:
    tmpl = json.dumps(template, indent=4)
    return f"<|input|>\n### Template:\n{tmpl}\n### Text:\n{source}\n\n<|output|>"


def health(url: str) -> bool:
    try:
        with urllib.request.urlopen(url + "/health", timeout=3) as resp:
            return resp.status == 200
    except Exception:  # noqa: BLE001
        return False


def extract_once(url: str, prompt: str, timeout: float = 120.0) -> str:
    payload = {
        "prompt": prompt,
        "temperature": 0,
        "n_predict": 512,
        "stop": ["<|input|>"],
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url + "/completion",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode())
    # llama.cpp server: {"content": "..."} or OpenAI-ish
    if isinstance(body, dict):
        if "content" in body:
            text = str(body["content"])
            if text.strip():
                return text
            raise RuntimeError("empty extract content")
        choices = body.get("choices")
        if choices:
            text = str(choices[0].get("text") or choices[0].get("message", {}).get("content") or "")
            if text.strip():
                return text
            raise RuntimeError("empty extract choices")
    raise RuntimeError(f"unexpected extract response keys: {list(body) if isinstance(body, dict) else type(body)}")


def gold_hits(snapshot: dict[str, Any], gold: dict[str, str]) -> tuple[int, int, list[str]]:
    hit = 0
    miss: list[str] = []
    for k, want in gold.items():
        got = snapshot.get(k, "")
        if isinstance(got, (int, float)):
            got = str(got)
        if not isinstance(got, str):
            miss.append(f"{k}: non-string {got!r}")
            continue
        if want in got or got == want:
            hit += 1
        else:
            miss.append(f"{k}: want {want!r} got {got!r}")
    return hit, len(gold), miss


def run_unit() -> list[str]:
    fails: list[str] = []
    source = "Error E0382 on line 42; Alice uses Rust 1.75.0."
    good = {"error": "E0382", "line": "42", "owner": "Alice", "rust": "1.75.0", "x": ""}
    if not verify_snapshot(source, good).ok:
        fails.append("unit: good snapshot rejected")
    bad = verify_snapshot(source, {"error": "E9999", "owner": "Bob"})
    if bad.ok or len(bad.issues) < 2:
        fails.append(f"unit: bad snapshot not rejected ({bad})")
    # paraphrase must fail
    para = verify_snapshot(source, {"lesson": "the borrow checker complained about a move"})
    if para.ok:
        fails.append("unit: paraphrase incorrectly admitted")
    try:
        parse_extract_output('prefix {"a":"1"} suffix')
    except Exception as e:  # noqa: BLE001
        fails.append(f"unit: parse_extract_output: {e}")
    return fails


def run_live(url: str, min_fidelity: float, retry: bool) -> tuple[list[str], dict]:
    fails: list[str] = []
    gold_hit = 0
    gold_total = 0
    span_ok = 0
    parse_ok = 0
    rows: list[dict] = []

    for case in CASES:
        prompt = nuextract_prompt(case.template, case.source)
        raw = ""
        snapshot: Any = None
        v: VerifyResult | None = None
        attempts = 2 if retry else 1
        last_err = ""
        for attempt in range(attempts):
            try:
                raw = extract_once(url, prompt)
                snapshot = parse_extract_output(raw)
                if not isinstance(snapshot, dict):
                    raise ValueError(f"not an object: {snapshot!r}")
                # template keys present
                for k in case.template:
                    if k not in snapshot:
                        raise ValueError(f"missing key {k}")
                v = verify_snapshot(case.source, snapshot)
                if v.ok:
                    break
                last_err = f"span fail: {v.as_dict()}"
            except Exception as e:  # noqa: BLE001
                last_err = str(e)
                snapshot = None
                v = None
        else:
            # exhausted attempts
            pass

        row: dict[str, Any] = {"id": case.id, "raw": raw[:200], "ok": False}
        if snapshot is None or v is None:
            fails.append(f"live:{case.id}: {last_err}")
            row["error"] = last_err
            rows.append(row)
            gold_total += len(case.gold)
            continue

        parse_ok += 1
        if v.ok:
            span_ok += 1
        else:
            fails.append(f"live:{case.id}: admitted span fail after retry — {v.as_dict()}")

        h, t, miss = gold_hits(snapshot, case.gold)
        gold_hit += h
        gold_total += t
        if miss:
            fails.append(f"live:{case.id}: gold miss — {miss}")

        for k in case.expect_empty:
            val = snapshot.get(k, "")
            if val not in ("", [], None):
                fails.append(f"live:{case.id}: expected empty {k}, got {val!r}")

        row.update(
            {
                "ok": v.ok and not miss,
                "snapshot": snapshot,
                "span_ok": v.ok,
                "gold_miss": miss,
            }
        )
        rows.append(row)

    fidelity = (gold_hit / gold_total) if gold_total else 1.0
    # FR-4: only span-ok items are "admitted"; fidelity among gold fields on span-ok rows
    stats = {
        "cases": len(CASES),
        "parse_ok": parse_ok,
        "span_ok": span_ok,
        "gold_hit": gold_hit,
        "gold_total": gold_total,
        "fidelity": round(fidelity, 4),
        "min_fidelity": min_fidelity,
    }
    if fidelity < min_fidelity:
        fails.append(
            f"fidelity {fidelity:.2%} < min {min_fidelity:.2%} "
            f"({gold_hit}/{gold_total} gold fields) — §8 release bar is 99%"
        )
    return fails, {"stats": stats, "rows": rows}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--unit-only", action="store_true")
    ap.add_argument("--live-only", action="store_true")
    ap.add_argument("--min-fidelity", type=float, default=0.99, help="gold-field hit rate gate")
    ap.add_argument("--no-retry", action="store_true", help="disable FR-4 single retry")
    ap.add_argument("--extract-url", default=EXTRACT_URL)
    ap.add_argument("--json", action="store_true", help="print machine-readable summary")
    args = ap.parse_args()

    fails: list[str] = []
    report: dict[str, Any] = {}

    if not args.live_only:
        u = run_unit()
        fails.extend(u)
        report["unit_fail"] = len(u)
        print(f"unit: {'PASS' if not u else 'FAIL'} ({len(u)} issues)")

    if not args.unit_only:
        if not health(args.extract_url):
            print(f"live: SKIP (extract not healthy at {args.extract_url})")
            report["live"] = "skipped"
            if args.live_only:
                fails.append("extract service not healthy")
        else:
            live_fails, live_report = run_live(
                args.extract_url,
                args.min_fidelity,
                retry=not args.no_retry,
            )
            fails.extend(live_fails)
            report["live"] = live_report
            st = live_report["stats"]
            print(
                f"live: cases={st['cases']} parse={st['parse_ok']} "
                f"span_ok={st['span_ok']} fidelity={st['fidelity']:.2%} "
                f"(gate {st['min_fidelity']:.0%})"
            )
            for row in live_report["rows"]:
                mark = "OK" if row.get("ok") else "FAIL"
                print(f"  [{mark}] {row['id']}")

    if args.json:
        print(json.dumps({"fails": fails, "report": report}, indent=2))

    print("\n=== verdict ===")
    if fails:
        print("FAIL")
        for f in fails[:20]:
            print("-", f)
        if len(fails) > 20:
            print(f"- … {len(fails) - 20} more")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())

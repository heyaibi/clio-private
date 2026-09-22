#!/usr/bin/env python3
"""Agent Memoir sidecar load probe — smoke / sustained / soak.

Estimates (1 coding agent, Profile B/C):
  ~60 turns/hour · ~30 retrieves/hour · ~12 writes/hour
  Per retrieve: 1 embed + 1 rerank(≤32) + Postgres reads
  Per write: 1 extract + 1 embed(index)

Modes
  smoke      one spike burst (default; ~15s)
  sustained  constant arrival rate for --duration (default 5m)
  soak       same as sustained but longer default (30m) + latency-drift check

Sustained rates are ~10× the 1-agent average so we prove headroom, not idle.
Pass requires 0% errors, p95 under budgets, and (soak) last-window p95
not > 1.5× first-window p95 (detects leak / queue growth).

Usage:
  python3 private/clio-private/scripts/load_probe.py
  python3 private/clio-private/scripts/load_probe.py sustained --duration 300
  python3 private/clio-private/scripts/load_probe.py soak --duration 1800
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable

EMBED_URL = "http://127.0.0.1:34311"
RERANK_URL = "http://127.0.0.1:34312"
EXTRACT_URL = "http://127.0.0.1:34313"
PG_DSN = "postgres://clio:clio@127.0.0.1:34310/clio"

RERANK_DOCS = 32

# Spike budgets (seconds)
LIMITS = {"embed": 2.0, "rerank": 8.0, "extract": 15.0, "postgres": 0.05, "retrieve": 12.0}

# Sustained/soak: ~10× one-agent average (ops per second)
RATE = {
    "retrieve": 30 / 3600 * 10,  # ~0.083/s → ~5/min
    "write": 12 / 3600 * 10,  # ~0.033/s → ~2/min
    "postgres": 0.5,  # cheap chatter
}


@dataclass
class Sample:
    name: str
    sec: float
    err: str | None
    t: float  # wall time when finished


@dataclass
class Bucket:
    name: str
    samples: list[Sample] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def add(self, s: Sample) -> None:
        with self.lock:
            self.samples.append(s)

    def snapshot(self) -> list[Sample]:
        with self.lock:
            return list(self.samples)


def timed(fn: Callable[[], None]) -> tuple[float, str | None]:
    t0 = time.perf_counter()
    try:
        fn()
        return time.perf_counter() - t0, None
    except Exception as e:  # noqa: BLE001
        return time.perf_counter() - t0, str(e)


def http_json(url: str, payload: dict, timeout: float = 120.0) -> None:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        resp.read()


def health(url: str) -> bool:
    try:
        with urllib.request.urlopen(url + "/health", timeout=3) as resp:
            return resp.status == 200
    except Exception:  # noqa: BLE001
        return False


def pg_ping() -> None:
    import socket

    try:
        import psycopg

        with psycopg.connect(PG_DSN, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        return
    except ImportError:
        pass
    s = socket.create_connection(("127.0.0.1", 34310), timeout=3)
    s.close()


def embed_once() -> None:
    http_json(
        EMBED_URL + "/embed",
        {"inputs": "fix the rust borrow checker error in this function"},
    )


def rerank_once(texts: list[str]) -> None:
    http_json(
        RERANK_URL + "/rerank",
        {"query": "rust borrow checker", "texts": texts},
        timeout=180.0,
    )


def extract_once() -> None:
    prompt = (
        "<|input|>\n### Template:\n"
        '{"error":"","lesson":""}\n'
        "### Text:\n"
        "User said: the build failed with E0382 borrow of moved value.\n"
        "Lesson: clone before move when both paths need ownership.\n\n"
        "<|output|>"
    )
    http_json(
        EXTRACT_URL + "/completion",
        {"prompt": prompt, "temperature": 0, "n_predict": 128},
        timeout=180.0,
    )


def retrieve_once(texts: list[str]) -> None:
    """One agent retrieve turn: embed query + rerank candidates + pg."""
    embed_once()
    rerank_once(texts)
    pg_ping()


def write_once() -> None:
    """One memory write: extract + embed for index."""
    extract_once()
    embed_once()


def summarize(name: str, samples: list[Sample], workers: int | None = None) -> dict:
    if not samples:
        return {"name": name, "n": 0, "ok": 0, "errors": 0, "p50_s": None, "p95_s": None, "max_s": None}
    lat = sorted(s.sec for s in samples)
    errs = [s.err for s in samples if s.err]
    p50 = statistics.median(lat)
    p95 = lat[max(0, int(len(lat) * 0.95) - 1)]
    out = {
        "name": name,
        "n": len(samples),
        "ok": len(samples) - len(errs),
        "errors": len(errs),
        "error_sample": errs[:2],
        "p50_s": round(p50, 3),
        "p95_s": round(p95, 3),
        "max_s": round(max(lat), 3),
        "rps": round(len(samples) / max(1e-9, samples[-1].t - samples[0].t + 1e-9), 4)
        if len(samples) > 1
        else None,
    }
    if workers is not None:
        out["workers"] = workers
    return out


def window_p95(samples: list[Sample], start: float, end: float) -> float | None:
    lat = sorted(s.sec for s in samples if start <= s.t < end and not s.err)
    if len(lat) < 3:
        return None
    return lat[max(0, int(len(lat) * 0.95) - 1)]


def bench_burst(name: str, n: int, workers: int, fn: Callable[[], None]) -> dict:
    bucket = Bucket(name)
    t_wall0 = time.time()

    def one() -> None:
        sec, err = timed(fn)
        bucket.add(Sample(name, sec, err, time.time() - t_wall0))

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = [pool.submit(one) for _ in range(n)]
        for fut in as_completed(futs):
            fut.result()
    return summarize(name, bucket.snapshot(), workers=workers)


def run_smoke(up: dict[str, bool]) -> list[dict]:
    results = []
    texts = [f"candidate document number {i} about rust and memory" for i in range(RERANK_DOCS)]
    if up["embed"]:
        results.append(bench_burst("embed", 20, 20, embed_once))
    else:
        print("SKIP embed (down)")
    if up["rerank"]:
        results.append(bench_burst("rerank", 8, 2, lambda: rerank_once(texts)))
    else:
        print("SKIP rerank (down)")
    if up["extract"]:
        results.append(bench_burst("extract", 2, 2, extract_once))
    else:
        print("SKIP extract (down)")
    try:
        results.append(bench_burst("postgres", 40, 8, pg_ping))
    except Exception as e:  # noqa: BLE001
        print("SKIP postgres:", e)
    return results


def run_arrival(
    duration: float,
    up: dict[str, bool],
    *,
    soak: bool,
) -> tuple[list[dict], list[str]]:
    """Constant arrival-rate mixed workload; records every op for windowed p95."""
    texts = [f"candidate document number {i} about rust and memory" for i in range(RERANK_DOCS)]
    buckets = {
        "retrieve": Bucket("retrieve"),
        "write": Bucket("write"),
        "postgres": Bucket("postgres"),
        "embed": Bucket("embed"),
        "rerank": Bucket("rerank"),
        "extract": Bucket("extract"),
    }
    stop = threading.Event()
    t0 = time.time()
    # Cap in-flight so we don't stampede TEI on a slow box
    pool = ThreadPoolExecutor(max_workers=6)

    def record(name: str, fn: Callable[[], None]) -> None:
        sec, err = timed(fn)
        buckets[name].add(Sample(name, sec, err, time.time() - t0))

    def schedule(name: str, rate: float, fn: Callable[[], None]) -> None:
        if rate <= 0:
            return
        interval = 1.0 / rate
        next_t = time.time()

        def loop() -> None:
            nonlocal next_t
            while not stop.is_set():
                now = time.time()
                if now < next_t:
                    time.sleep(min(0.05, next_t - now))
                    continue
                next_t += interval
                if time.time() - t0 >= duration:
                    break
                pool.submit(record, name, fn)

        threading.Thread(target=loop, daemon=True).start()

    if up["embed"] and up["rerank"]:
        schedule("retrieve", RATE["retrieve"], lambda: retrieve_once(texts))
    elif up["embed"]:
        schedule("embed", RATE["retrieve"], embed_once)
    if up["extract"] and up["embed"]:
        schedule("write", RATE["write"], write_once)
    elif up["extract"]:
        schedule("extract", RATE["write"], extract_once)
    schedule("postgres", RATE["postgres"], pg_ping)

    print(
        f"running {'soak' if soak else 'sustained'} for {duration:.0f}s "
        f"(retrieve≈{RATE['retrieve']:.3f}/s write≈{RATE['write']:.3f}/s)…"
    )
    # Progress every 30s
    end = t0 + duration
    while time.time() < end:
        time.sleep(min(30.0, max(0.1, end - time.time())))
        elapsed = time.time() - t0
        n = sum(len(b.snapshot()) for b in buckets.values())
        print(f"  t={elapsed:.0f}s samples={n}")

    stop.set()
    time.sleep(0.5)
    pool.shutdown(wait=True, cancel_futures=False)

    results = []
    for key in ("retrieve", "write", "postgres", "embed", "rerank", "extract"):
        samples = buckets[key].snapshot()
        if samples:
            results.append(summarize(key, samples))

    failed: list[str] = []
    # Primary gates on workflow ops when present
    for r in results:
        lim = LIMITS.get(r["name"])
        if r["errors"]:
            failed.append(f"{r['name']}: {r['errors']} errors ({r.get('error_sample')})")
        elif lim is not None and r["p95_s"] is not None and r["p95_s"] > lim:
            failed.append(f"{r['name']}: p95 {r['p95_s']}s > {lim}s")

    if soak:
        for key in ("retrieve", "write", "rerank", "extract"):
            samples = buckets[key].snapshot()
            if len(samples) < 10:
                continue
            first = window_p95(samples, 0, duration / 3)
            last = window_p95(samples, duration * 2 / 3, duration + 1)
            if first and last and last > first * 1.5:
                failed.append(
                    f"{key}: soak drift p95 {first:.3f}s → {last:.3f}s (>1.5×)"
                )

    return results, failed


def verdict(results: list[dict], up: dict[str, bool], extra_failed: list[str] | None = None) -> int:
    failed = list(extra_failed or [])
    for r in results:
        lim = LIMITS.get(r["name"])
        if r["errors"]:
            failed.append(f"{r['name']}: {r['errors']} errors ({r.get('error_sample')})")
        elif lim is not None and r.get("p95_s") is not None and r["p95_s"] > lim:
            failed.append(f"{r['name']}: p95 {r['p95_s']}s > {lim}s")
    if not up["rerank"]:
        failed.append("rerank unavailable — Profile B/C retrieve not proven")

    print("\n=== verdict ===")
    if failed:
        # de-dupe while preserving order
        seen = set()
        uniq = []
        for f in failed:
            if f not in seen:
                seen.add(f)
                uniq.append(f)
        print("FAIL")
        for f in uniq:
            print("-", f)
        return 1
    print("PASS")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "mode",
        nargs="?",
        default="smoke",
        choices=["smoke", "sustained", "soak"],
        help="smoke=burst; sustained=arrival-rate; soak=sustained+drift",
    )
    ap.add_argument(
        "--duration",
        type=float,
        default=None,
        help="seconds for sustained/soak (default: 300 / 1800)",
    )
    args = ap.parse_args()
    duration = args.duration
    if duration is None:
        duration = 1800.0 if args.mode == "soak" else 300.0 if args.mode == "sustained" else 0.0

    print("=== Agent Memoir load probe ===")
    print(f"mode={args.mode}")
    print("turns/hour≈60 | retrieve/hour≈30 | write/hour≈12")
    if args.mode == "smoke":
        print("spike >> sustained rates (headroom check)\n")
    else:
        print(f"arrival-rate ~10× 1-agent avg for {duration:.0f}s\n")

    up = {
        "embed": health(EMBED_URL),
        "rerank": health(RERANK_URL),
        "extract": health(EXTRACT_URL),
    }
    print("health:", up)

    if args.mode == "smoke":
        results = run_smoke(up)
        print("\n=== results ===")
        for r in results:
            print(json.dumps(r))
        return verdict(results, up)

    results, soak_failed = run_arrival(duration, up, soak=(args.mode == "soak"))
    print("\n=== results ===")
    for r in results:
        print(json.dumps(r))
    # run_arrival already collected limit failures into soak_failed when soak;
    # for sustained, re-check via verdict only
    if args.mode == "sustained":
        return verdict(results, up)
    return verdict(results, up, extra_failed=soak_failed)


if __name__ == "__main__":
    sys.exit(main())

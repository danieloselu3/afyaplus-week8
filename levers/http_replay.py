"""Replay the 100-call fixture through the RUNNING service over HTTP (JWT, rate limit, cache).

    python levers/http_replay.py                          # one replica on :8000
    python levers/http_replay.py --ports 8000,8002        # round-robin over two replicas

With Redis behind both replicas, a message first seen on :8000 is a HIT on :8002.
Counts the X-Cache header and times every call. Writes levers/results/http_replay_<n>replica.json.
Needs a rate limit of at least 100/min for the coordinator, e.g. start the stack with
TRIAGE_RATE_LIMIT_PER_MIN=120 (declared in the README; the deploy default is 30).
"""
import argparse
import json
import sys
import time
from collections import Counter

import httpx

import _paths

COUNTY = "Nairobi"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ports", default="8000")
    ap.add_argument("--password", default="logistics2026")   # demo account from the Week 6 README
    args = ap.parse_args()
    ports = [int(p) for p in args.ports.split(",")]
    bases = [f"http://127.0.0.1:{p}" for p in ports]

    with httpx.Client(timeout=30) as client:
        health = [client.get(f"{b}/health").json() for b in bases]
        token = client.post(f"{bases[0]}/token",
                            json={"username": "mercy", "password": args.password}).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        calls = json.loads((_paths.FIXTURES / "traffic_100.json").read_text())
        rows = []
        for i, message in enumerate(calls):
            base = bases[i % len(bases)]
            started = time.perf_counter()
            r = client.post(f"{base}/triage", headers=headers,
                            json={"patient_message": message, "county": COUNTY})
            ms = (time.perf_counter() - started) * 1000
            rows.append({"i": i, "port": base.rsplit(":", 1)[1], "status": r.status_code,
                         "cache": r.headers.get("X-Cache"), "ms": round(ms, 1)})

    by_cache = Counter(r["cache"] for r in rows)
    by_port = {p: dict(Counter(r["cache"] for r in rows if r["port"] == str(p))) for p in ports}
    hits = by_cache.get("HIT", 0)
    lat = [r["ms"] for r in rows]
    hit_ms = [r["ms"] for r in rows if r["cache"] == "HIT"]
    miss_ms = [r["ms"] for r in rows if r["cache"] == "MISS"]
    summary = {
        "ports": ports, "cache_backend": [h["cache"] for h in health], "n": len(rows),
        "status_codes": dict(Counter(r["status"] for r in rows)), "x_cache": dict(by_cache),
        "by_port": by_port, "hit_rate": round(hits / len(rows), 3),
        "latency_ms_p50": _paths.percentile(lat, 50), "latency_ms_p95": _paths.percentile(lat, 95),
        "hit_ms_p95": _paths.percentile(hit_ms, 95) if hit_ms else None,
        "miss_ms_p50": _paths.percentile(miss_ms, 50) if miss_ms else None,
    }
    out = _paths.RESULTS / f"http_replay_{len(ports)}replica.json"
    out.write_text(json.dumps({"summary": summary, "calls": rows}, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    print(f"wrote {out.relative_to(_paths.ROOT)}")
    return 0 if summary["status_codes"] == {200: len(rows)} else 1


if __name__ == "__main__":
    sys.exit(main())

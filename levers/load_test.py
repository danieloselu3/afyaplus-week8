"""How much traffic one 0.5 vCPU replica can carry, and where it stops. No API spend.

Start one replica on the free stub, made as slow as a real model call, with no cache and
a rate limit high enough not to interfere:

    TRIAGE_BACKEND=stub STUB_LATENCY_MS=1000 TRIAGE_RATE_LIMIT_PER_MIN=100000 \\
      docker compose -f deploy/docker-compose.cost.yml up -d triage-api
    python levers/load_test.py

Every message is unique (no cache hits: the worst case). For each concurrency level it
sends a fixed number of requests and reports throughput and p95. Writes
levers/results/load_test.json, which deploy/hpa.yaml and the spike plan cite.
"""
import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import httpx

import _paths

LEVELS = [1, 5, 10, 20, 40, 60]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    ap.add_argument("--per-level", type=int, default=120)
    args = ap.parse_args()

    with httpx.Client(timeout=60) as c:
        health = c.get(f"{args.base}/health").json()
        token = c.post(f"{args.base}/token",
                       json={"username": "mercy", "password": "logistics2026"}).json()["access_token"]
    if health["model_backend"] != "stub":
        print("refusing: this load test must run against the stub backend (no API spend)")
        return 1
    headers = {"Authorization": f"Bearer {token}"}
    run_id = int(time.time())
    client = httpx.Client(timeout=60, limits=httpx.Limits(max_connections=100))

    def one(i: int) -> tuple[int, float]:
        started = time.perf_counter()
        r = client.post(f"{args.base}/triage", headers=headers,
                        json={"patient_message": f"Load test message {run_id}-{i}: mild cough",
                              "county": "Nairobi"})
        return r.status_code, (time.perf_counter() - started) * 1000

    rows = []
    print(f"{'concurrency':>11} {'requests':>8} {'ok':>4} {'req/s':>6} {'p50 ms':>7} {'p95 ms':>7}")
    for level in LEVELS:
        started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=level) as pool:
            results = list(pool.map(one, range(level * 10_000, level * 10_000 + args.per_level)))
        wall = time.perf_counter() - started
        lat = [ms for _, ms in results]
        ok = sum(1 for code, _ in results if code == 200)
        row = {"concurrency": level, "requests": len(results), "ok": ok,
               "req_per_s": round(len(results) / wall, 2),
               "p50_ms": round(_paths.percentile(lat, 50)), "p95_ms": round(_paths.percentile(lat, 95))}
        rows.append(row)
        print(f"{level:>11} {row['requests']:>8} {ok:>4} {row['req_per_s']:>6} {row['p50_ms']:>7} {row['p95_ms']:>7}")
    client.close()
    out = {"setup": {"replicas": 1, "cpu_limit": "0.5 vCPU", "memory_limit": "1 GiB",
                     "backend": "stub with STUB_LATENCY_MS (simulated model time)",
                     "cache": "none hit (every message unique)", "health": health},
           "levels": rows}
    (_paths.RESULTS / "load_test.json").write_text(json.dumps(out, indent=2) + "\n")
    print("wrote levers/results/load_test.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())

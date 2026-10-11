"""Why Redis only pays once there is more than one replica. No API calls, no spend.

    python levers/replica_hit_simulation.py

Replays fixtures/traffic_100.json round-robin over k replicas, each with its OWN
in-process cache (no Redis), and prints the hit rate. Compare with the measured
shared-Redis run in levers/results/http_replay_2replica.json (0.60 at 2 replicas).
"""
import json

import _paths


def separate_cache_hit_rate(calls: list[str], replicas: int) -> float:
    seen = [set() for _ in range(replicas)]
    hits = 0
    for i, message in enumerate(calls):
        cache = seen[i % replicas]
        if message in cache:
            hits += 1
        else:
            cache.add(message)
    return hits / len(calls)


if __name__ == "__main__":
    calls = json.loads((_paths.FIXTURES / "traffic_100.json").read_text())
    rows = {k: round(separate_cache_hit_rate(calls, k), 3) for k in (1, 2, 3)}
    for k, rate in rows.items():
        print(f"{k} replica(s), separate in-process caches: hit_rate={rate:.2f}")
    print("shared Redis cache, any replica count:        hit_rate=0.60 (measured, 2 replicas)")
    (_paths.RESULTS / "replica_hit_simulation.json").write_text(
        json.dumps({"separate_cache_hit_rate_by_replicas": rows,
                    "shared_redis_measured": "levers/results/http_replay_2replica.json"}, indent=2) + "\n")

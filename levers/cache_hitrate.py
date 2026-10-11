"""Lever 1 measurement: replay the same 100-call fixture with the cache OFF, then ON.

    python levers/cache_hitrate.py --mode off     # before: every call goes to the model
    python levers/cache_hitrate.py --mode on      # after: repeats are served from cache
    add --backend stub for a free dry run (no API key, no spend)

Fixture: fixtures/traffic_100.json = 40 unique messages + 60 seeded repeats (seed 7).
Writes levers/results/cache_<mode>[_stub].json. A live --mode off run also writes
fixtures/usage_recorded.json, the measured token shape cost/cost_model.py prices.
Exits 1 if --mode on lands under the 0.55 hit-rate target (Thursday Lab 1 gate).
"""
import argparse
import json
import os
import sys
import time
from datetime import date

import _paths

TARGET_HIT_RATE = 0.55


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["off", "on"], required=True)
    ap.add_argument("--backend", choices=["openai", "stub"], default="openai")
    args = ap.parse_args()

    # config.py reads these at import time, so set them before importing the API.
    os.environ["CACHE_ENABLED"] = "true" if args.mode == "on" else "false"
    os.environ["TRIAGE_BACKEND"] = args.backend
    os.environ["REDIS_URL"] = ""               # in-process dict; Redis is evidenced over HTTP
    from cache_triage import triage            # noqa: E402
    from config import OPENAI_MODEL            # noqa: E402
    from cost_model import api_usd             # noqa: E402

    calls = json.loads((_paths.FIXTURES / "traffic_100.json").read_text())
    rows = []
    for i, message in enumerate(calls):
        started = time.perf_counter()
        out = triage(message)
        ms = (time.perf_counter() - started) * 1000
        billed = out["_cache"] != "HIT"
        tin, tout = (out["tokens_in"], out["tokens_out"]) if billed else (0, 0)
        rows.append({"i": i, "message": message, "cache": out["_cache"], "ms": round(ms, 1),
                     "urgency": out["urgency"], "tokens_in": tin, "tokens_out": tout,
                     "usd": api_usd(tin, tout)})

    model_calls = [r for r in rows if r["cache"] != "HIT"]
    hits = len(rows) - len(model_calls)
    usd = sum(r["usd"] for r in rows)
    latencies = [r["ms"] for r in rows]
    summary = {
        "mode": args.mode, "backend": args.backend, "fixture": "fixtures/traffic_100.json",
        "n": len(rows), "unique": len(set(calls)), "hits": hits, "misses": len(model_calls),
        "hit_rate": round(hits / len(rows), 3), "model_calls": len(model_calls),
        "tokens_in": sum(r["tokens_in"] for r in rows), "tokens_out": sum(r["tokens_out"] for r in rows),
        "usd_total": round(usd, 6), "usd_per_1k_tokens_only": round(1000 * usd / len(rows), 4),
        "latency_ms_p50": _paths.percentile(latencies, 50),
        "latency_ms_p95": _paths.percentile(latencies, 95),
        "latency_ms_mean": round(sum(latencies) / len(latencies), 1),
        "date": date.today().isoformat(),
    }
    suffix = "" if args.backend == "openai" else "_stub"
    _paths.RESULTS.mkdir(exist_ok=True)
    out_file = _paths.RESULTS / f"cache_{args.mode}{suffix}.json"
    out_file.write_text(json.dumps({"summary": summary, "calls": rows}, indent=2) + "\n")

    if args.mode == "off" and args.backend == "openai":
        n = len(model_calls)
        usage = {"model": OPENAI_MODEL, "n_calls": n, "date": summary["date"],
                 "avg_prompt_tokens": round(summary["tokens_in"] / n, 1),
                 "avg_completion_tokens": round(summary["tokens_out"] / n, 1),
                 "source": "levers/cache_hitrate.py --mode off (fixtures/traffic_100.json)"}
        (_paths.FIXTURES / "usage_recorded.json").write_text(json.dumps(usage, indent=2) + "\n")

    print(f"mode={args.mode} backend={args.backend} n={summary['n']} hits={hits} "
          f"misses={summary['misses']} hit_rate={summary['hit_rate']:.2f}")
    print(f"model_calls={summary['model_calls']} tokens_in={summary['tokens_in']} "
          f"tokens_out={summary['tokens_out']} usd_total={summary['usd_total']:.6f} "
          f"usd_per_1k_tokens_only={summary['usd_per_1k_tokens_only']:.4f}")
    print(f"latency_ms p50={summary['latency_ms_p50']} p95={summary['latency_ms_p95']} "
          f"mean={summary['latency_ms_mean']}")
    print(f"wrote {out_file.relative_to(_paths.ROOT)}")
    if args.mode == "on" and summary["hit_rate"] < TARGET_HIT_RATE:
        print(f"FAIL: hit_rate {summary['hit_rate']:.2f} < target {TARGET_HIT_RATE}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

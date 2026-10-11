"""AfyaPlus triage: what one request costs, per 1,000, and per month at baseline and a 10x spike.

    python cost/cost_model.py            # prints the table, writes cost/cost_model_output.json

Every rate is a named constant with a footnote number. The footnotes are in
cost/cost_model.md. Rates were checked 2026-10-11; re-check before a board pack.
The token shape (tokens per request) is MEASURED, read from fixtures/usage_recorded.json,
which levers/cache_hitrate.py writes from a live gpt-4o-mini run. Without that file the
course's teaching shape (450 / 180) is used, and the output says so.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
USAGE_FILE = ROOT / "fixtures" / "usage_recorded.json"
OUTPUT_FILE = Path(__file__).resolve().parent / "cost_model_output.json"

# ---------- model prices, USD per 1M tokens [1] ----------
MODEL = "gpt-4o-mini"
PRICE_PROMPT_PER_M = 0.15
PRICE_COMPLETION_PER_M = 0.60
BATCH_API_DISCOUNT = 0.50            # OpenAI Batch API: 50% off both, results within 24 h [1]

# ---------- infra: Azure, South Africa North, pay-as-you-go [2] ----------
ACA_VCPU_ACTIVE_PER_S = 0.000024     # Container Apps consumption, per vCPU-second
ACA_GIB_ACTIVE_PER_S = 0.000003      # per GiB-second
ACA_PER_M_REQUESTS = 0.40
ACA_FREE_VCPU_S = 180_000            # monthly free grant per subscription [3]
ACA_FREE_GIB_S = 360_000
ACA_FREE_REQUESTS = 2_000_000
REPLICA_VCPU = 0.5                   # what docker-compose.cost.yml caps a replica at
REPLICA_GIB = 1.0
REDIS_C0_BASIC_PER_H = 0.0321        # Azure Cache for Redis Basic C0 (250 MB) [2]
LOG_INGEST_PER_GB = 3.36             # Log Analytics ingestion [2]; free tier NOT assumed
LOG_BYTES_PER_REQUEST = 2_000        # [A] request line + model line + audit line, ~3 x 600 B

# ---------- people [A] = teaching assumption, not AfyaPlus payroll ----------
OPS_HOURS_PER_MONTH = 6              # [A] on-call checks, prompt review, budget alert triage
OPS_RATE_USD_PER_H = 25.0            # [A] loaded hourly cost of a mid-level engineer in Nairobi

# ---------- traffic [A] (chosen at planning, 2026-10-11) ----------
DAYS_PER_MONTH = 30
BASELINE_PER_DAY = 2_000
SPIKE_MULTIPLIER = 10                # e.g. an outbreak month: 20,000 requests a day
AFTER_HOURS_SHARE = 0.20             # [A] share of messages arriving after clinic hours (batchable)
HOURS_PER_MONTH = 730                # Azure's billing month

# Teaching fallback when no live usage has been recorded (Week 7 Monday Lab 1).
COURSE_PROMPT_TOKENS, COURSE_COMPLETION_TOKENS = 450, 180


def token_shape() -> dict:
    """Average tokens per request: measured if available, else the course's teaching shape."""
    if USAGE_FILE.exists():
        u = json.loads(USAGE_FILE.read_text())
        return {"prompt": u["avg_prompt_tokens"], "completion": u["avg_completion_tokens"],
                "source": f"measured: {u['n_calls']} live {u['model']} calls on {u['date']}"}
    return {"prompt": COURSE_PROMPT_TOKENS, "completion": COURSE_COMPLETION_TOKENS,
            "source": "course teaching shape (no live usage recorded yet)"}


def api_usd(prompt_tokens: float, completion_tokens: float) -> float:
    """The token bill for one model call: prompt and completion priced separately."""
    return (prompt_tokens * PRICE_PROMPT_PER_M + completion_tokens * PRICE_COMPLETION_PER_M) / 1e6


def token_usd_month(requests: int, shape: dict, hit_rate: float = 0.0,
                    batch_saving: float = 0.0) -> float:
    """Cache hits are not sent to the model, so (1 - hit_rate) of requests are billed.
    When batching is on, the after-hours share of those billed requests goes through the
    queue (which reads the cache first) at (1 - batch_saving) of the one-call price."""
    unit = api_usd(shape["prompt"], shape["completion"])
    billed = requests * (1 - hit_rate)
    if not batch_saving:
        return billed * unit
    return billed * unit * ((1 - AFTER_HOURS_SHARE) + AFTER_HOURS_SHARE * (1 - batch_saving))


def container_usd_month(requests: int, replicas: int) -> float:
    """Conservative: every always-on replica is billed at the ACTIVE rate all month."""
    seconds = HOURS_PER_MONTH * 3600 * replicas
    vcpu = max(0.0, seconds * REPLICA_VCPU - ACA_FREE_VCPU_S) * ACA_VCPU_ACTIVE_PER_S
    mem = max(0.0, seconds * REPLICA_GIB - ACA_FREE_GIB_S) * ACA_GIB_ACTIVE_PER_S
    reqs = max(0, requests - ACA_FREE_REQUESTS) / 1e6 * ACA_PER_M_REQUESTS
    return vcpu + mem + reqs


def redis_usd_month() -> float:
    return REDIS_C0_BASIC_PER_H * HOURS_PER_MONTH


def logs_usd_month(requests: int) -> float:
    return requests * LOG_BYTES_PER_REQUEST / 1e9 * LOG_INGEST_PER_GB


def people_usd_month() -> float:
    return OPS_HOURS_PER_MONTH * OPS_RATE_USD_PER_H


def scenario(name: str, per_day: int, replicas: int, hit_rate: float, use_redis: bool,
             batch_saving: float = 0.0) -> dict:
    """One month of total cost of ownership (TCO), broken into the buckets Finance asks about."""
    shape = token_shape()
    requests = per_day * DAYS_PER_MONTH
    lines = {
        "model_tokens": token_usd_month(requests, shape, hit_rate, batch_saving),
        "containers": container_usd_month(requests, replicas),
        "redis": redis_usd_month() if use_redis else 0.0,
        "logs": logs_usd_month(requests),
        "people": people_usd_month(),
    }
    total = sum(lines.values())
    return {
        "scenario": name, "requests_per_day": per_day, "requests_per_month": requests,
        "replicas": replicas, "cache_hit_rate": hit_rate, "redis": use_redis,
        "batch_saving_after_hours": batch_saving,
        "lines_usd": {k: round(v, 2) for k, v in lines.items()},
        "total_usd_month": round(total, 2),
        "usd_per_request": total / requests,
        "usd_per_1k_total": round(1000 * total / requests, 4),
        "usd_per_1k_tokens_only": round(1000 * lines["model_tokens"] / requests, 4),
    }


def build(levers: dict) -> dict:
    """levers = measured inputs: hit rate with one shared cache, hit rate with two separate
    per-replica caches, and the batch saving at the recommended batch size."""
    spike_day = BASELINE_PER_DAY * SPIKE_MULTIPLIER
    hit, hit2, batch = levers["hit_rate_shared"], levers["hit_rate_2_separate"], levers["batch_saving"]
    scenarios = [
        scenario("baseline: no levers", BASELINE_PER_DAY, 1, 0.0, False),
        scenario("baseline: in-process cache", BASELINE_PER_DAY, 1, hit, False),
        scenario("baseline: cache + batch (RECOMMENDED)", BASELINE_PER_DAY, 1, hit, False, batch),
        scenario("10x spike: no levers", spike_day, 2, 0.0, False),
        scenario("10x spike: cache per replica + batch (RECOMMENDED)", spike_day, 2, hit2, False, batch),
        scenario("10x spike: shared Redis cache + batch", spike_day, 2, hit, True, batch),
    ]
    shape = token_shape()
    return {"model": MODEL, "token_shape": shape,
            "usd_per_model_call": api_usd(shape["prompt"], shape["completion"]),
            "levers": levers, "assumptions": {
                "days_per_month": DAYS_PER_MONTH, "baseline_per_day": BASELINE_PER_DAY,
                "spike_multiplier": SPIKE_MULTIPLIER, "after_hours_share": AFTER_HOURS_SHARE,
                "replica": f"{REPLICA_VCPU} vCPU / {REPLICA_GIB} GiB, billed active all month",
                "ops_hours_per_month": OPS_HOURS_PER_MONTH, "ops_rate_usd_per_h": OPS_RATE_USD_PER_H},
            "redis_break_even_requests_per_month": redis_break_even(levers),
            "scenarios": scenarios}


def redis_break_even(levers: dict) -> int:
    """Monthly volume where shared Redis saves more tokens than it costs, versus each of
    two replicas keeping its own cache: N * unit * (hit_shared - hit_separate) = Redis $."""
    shape = token_shape()
    gain = levers["hit_rate_shared"] - levers["hit_rate_2_separate"]
    unit = api_usd(shape["prompt"], shape["completion"])
    return round(redis_usd_month() / (unit * gain)) if gain > 0 else -1


BATCH_SIZE = 4   # recommended: the largest size with agreement >= 0.95 (levers/measurements.md)


def measured_levers() -> dict:
    """Lever inputs from levers/results/ (written by the lever scripts), else zeros."""
    res = ROOT / "levers" / "results"
    out = {"hit_rate_shared": 0.0, "hit_rate_2_separate": 0.0, "batch_saving": 0.0,
           "batch_size": BATCH_SIZE}
    if (res / "cache_on.json").exists():
        out["hit_rate_shared"] = json.loads((res / "cache_on.json").read_text())["summary"]["hit_rate"]
    if (res / "replica_hit_simulation.json").exists():
        sim = json.loads((res / "replica_hit_simulation.json").read_text())
        out["hit_rate_2_separate"] = sim["separate_cache_hit_rate_by_replicas"]["2"]
    if (res / "batch.json").exists():
        rows = json.loads((res / "batch.json").read_text())["after"]
        out["batch_saving"] = next(r["usd_saving_vs_before"] for r in rows
                                   if r["batch_size"] == BATCH_SIZE)
    return out


if __name__ == "__main__":
    model = build(measured_levers())
    OUTPUT_FILE.write_text(json.dumps(model, indent=2) + "\n")
    s = model["token_shape"]
    print(f"model={MODEL}  prices_per_1M prompt={PRICE_PROMPT_PER_M} completion={PRICE_COMPLETION_PER_M}")
    print(f"tokens/request prompt={s['prompt']} completion={s['completion']}  ({s['source']})")
    lv = model["levers"]
    print(f"usd_per_model_call={model['usd_per_model_call']:.6f}")
    print(f"levers (measured on fixtures): hit_rate shared={lv['hit_rate_shared']:.2f} "
          f"2 separate caches={lv['hit_rate_2_separate']:.2f}  batch(size {lv['batch_size']}) "
          f"saving={lv['batch_saving']:.3f} on the {AFTER_HOURS_SHARE:.0%} after-hours share")
    print()
    head = f"{'scenario':52} {'req/month':>10} {'tokens':>8} {'contnrs':>8} {'redis':>7} " \
           f"{'logs':>6} {'people':>7} {'TOTAL':>8} {'$/1k all':>9} {'$/1k tok':>9}"
    print(head)
    print("-" * len(head))
    for sc in model["scenarios"]:
        ln = sc["lines_usd"]
        print(f"{sc['scenario']:52} {sc['requests_per_month']:>10,} {ln['model_tokens']:>8.2f} "
              f"{ln['containers']:>8.2f} {ln['redis']:>7.2f} {ln['logs']:>6.2f} {ln['people']:>7.2f} "
              f"{sc['total_usd_month']:>8.2f} {sc['usd_per_1k_total']:>9.4f} {sc['usd_per_1k_tokens_only']:>9.4f}")
    be = model["redis_break_even_requests_per_month"]
    print(f"\nRedis pays for itself (vs a cache per replica, 2 replicas) above {be:,} "
          f"requests/month (~{be // DAYS_PER_MONTH:,}/day)")
    print(f"wrote {OUTPUT_FILE.relative_to(ROOT)}")

"""Lever 2 measurement: one call per message (before) vs N messages per call (after).

    python levers/batch_measure.py                   # live: batch sizes 4, 8 and 12
    python levers/batch_measure.py --backend stub    # free dry run

Before = the per-message calls already recorded live by `cache_hitrate.py --mode off`
(same model, same prompt rules, same 24 messages), so no message is paid for twice.
After  = fixtures/backlog_24.json drained through batch_worker.py at each batch size.
Quality = how often the batched urgency matches the one-call urgency for the same message,
next to how often the one-call path agrees with ITSELF on repeated messages (temperature 0
is not perfectly deterministic), so the batch number has a fair yardstick.
Writes levers/results/batch.json.
"""
import argparse
import json
import os
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path

import _paths


def single_call_baseline() -> tuple[dict, float]:
    """First recorded one-call answer per message, plus the one-call self-agreement rate."""
    rows = json.loads((_paths.RESULTS / "cache_off.json").read_text())["calls"]
    first, labels = {}, defaultdict(list)
    for r in rows:
        first.setdefault(r["message"], r)
        labels[r["message"]].append(r["urgency"])
    repeated = [v for v in labels.values() if len(v) > 1]
    pairs = sum(len(v) - 1 for v in repeated)
    agree = sum(sum(1 for x in v[1:] if x == v[0]) for v in repeated)
    return first, (agree / pairs if pairs else 1.0)


def run_batches(messages: list[str], size: int) -> dict:
    import batch_worker
    db = Path(tempfile.mkdtemp(prefix="afya-batch-")) / "jobs.sqlite"
    conn = batch_worker.init(db)
    for m in messages:
        batch_worker.enqueue(conn, m)
    calls, tin, tout, started = 0, 0, 0, time.perf_counter()
    for _ in range(100):                  # bounded: never loop forever on a poison batch
        out = batch_worker.process_once(conn, size)
        if not out["done"] and not out["failed"]:
            break
        calls += out["model_calls"]
        tin, tout = tin + out["tokens_in"], tout + out["tokens_out"]
    seconds = time.perf_counter() - started
    results = {}
    for text, result in conn.execute("SELECT text, result FROM jobs WHERE status='done'"):
        results[text] = json.loads(result)["urgency"]
    return {"batch_size": size, "model_calls": calls, "tokens_in": tin, "tokens_out": tout,
            "wall_seconds": round(seconds, 1), "status": batch_worker.counts(conn), "labels": results}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=["openai", "stub"], default="openai")
    ap.add_argument("--sizes", default="4,8,12")
    args = ap.parse_args()
    os.environ["TRIAGE_BACKEND"] = args.backend
    from cost_model import BATCH_API_DISCOUNT, api_usd   # noqa: E402

    backlog = json.loads((_paths.FIXTURES / "backlog_24.json").read_text())
    first, self_agreement = single_call_baseline()
    before = [first[m] for m in backlog]
    b_in, b_out = sum(r["tokens_in"] for r in before), sum(r["tokens_out"] for r in before)
    b_usd = api_usd(b_in, b_out)
    n = len(backlog)
    report = {
        "fixture": "fixtures/backlog_24.json", "n_messages": n, "backend": args.backend,
        "single_call_self_agreement": round(self_agreement, 3),
        "before": {"model_calls": n, "tokens_in": b_in, "tokens_out": b_out,
                   "usd_per_1k_messages": round(1000 * b_usd / n, 4),
                   "source": "levers/results/cache_off.json (live one-call answers)"},
        "after": [],
    }
    print(f"before: {n} calls, tokens_in={b_in} tokens_out={b_out}, "
          f"usd_per_1k_messages={1000 * b_usd / n:.4f}")
    print(f"one-call path agrees with itself on repeats: {self_agreement:.2f}")
    for size in [int(s) for s in args.sizes.split(",")]:
        run = run_batches(backlog, size)
        usd = api_usd(run["tokens_in"], run["tokens_out"])
        matched = sum(1 for m in backlog if run["labels"].get(m) == first[m]["urgency"])
        mismatches = [{"message": m, "one_call": first[m]["urgency"], "batched": run["labels"].get(m)}
                      for m in backlog if run["labels"].get(m) != first[m]["urgency"]]
        row = {**{k: v for k, v in run.items() if k != "labels"},
               "usd_per_1k_messages": round(1000 * usd / n, 4),
               "usd_per_1k_with_batch_api": round(1000 * usd * (1 - BATCH_API_DISCOUNT) / n, 4),
               "token_saving_vs_before": round(1 - (run["tokens_in"] + run["tokens_out"]) / (b_in + b_out), 3),
               "usd_saving_vs_before": round(1 - usd / b_usd, 3) if b_usd else None,
               "agreement_with_one_call": round(matched / n, 3), "mismatches": mismatches}
        report["after"].append(row)
        print(f"batch={size:>2}: {run['model_calls']} calls, tokens_in={run['tokens_in']} "
              f"tokens_out={run['tokens_out']}, usd_per_1k_messages={row['usd_per_1k_messages']:.4f} "
              f"(saving {row['usd_saving_vs_before']}), agreement={row['agreement_with_one_call']:.2f}, "
              f"status={run['status']}")
    out = _paths.RESULTS / ("batch.json" if args.backend == "openai" else "batch_stub.json")
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(f"wrote {out.relative_to(_paths.ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

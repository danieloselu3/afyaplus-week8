"""A/B split acceptance check (Week 8 Thursday Challenge 1), plus the live comparison.

    python ab_report.py                       # synthetic split check, writes ab_report.json
    python ab_report.py --log logs/ab_requests.jsonl   # also summarise real /triage traffic

1. 100 synthetic keys at PROMPT_B_PCT=20 must put 15-25 in B (exit 1 otherwise): proves the
   splitter actually splits. 2. The 47 Kenyan counties at the configured percentage: who is
   on the candidate right now. 3. With --log: per-variant counts, urgency mix, mean tokens
   and p50 latency from the metrics rows ab_metrics.py writes.
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import prompt_app
from ab_prompt_flag import assign_variant, bucket

COUNTIES = [  # Kenya's 47 counties
    "Mombasa", "Kwale", "Kilifi", "Tana River", "Lamu", "Taita Taveta", "Garissa", "Wajir",
    "Mandera", "Marsabit", "Isiolo", "Meru", "Tharaka Nithi", "Embu", "Kitui", "Machakos",
    "Makueni", "Nyandarua", "Nyeri", "Kirinyaga", "Muranga", "Kiambu", "Turkana", "West Pokot",
    "Samburu", "Trans Nzoia", "Uasin Gishu", "Elgeyo Marakwet", "Nandi", "Baringo", "Laikipia",
    "Nakuru", "Narok", "Kajiado", "Kericho", "Bomet", "Kakamega", "Vihiga", "Bungoma", "Busia",
    "Siaya", "Kisumu", "Homa Bay", "Migori", "Kisii", "Nyamira", "Nairobi"]


def summarise(log: Path) -> dict:
    rows = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]
    out = {}
    for v in ("A", "B"):
        r = [x for x in rows if x["variant"] == v]
        if not r:
            continue
        lat = sorted(x["latency_ms"] for x in r)
        billed = [x for x in r if x["cache"] != "HIT"]
        out[v] = {"n": len(r), "prompt_versions": sorted({x["prompt_version"] for x in r}),
                  "urgency": dict(Counter(x["urgency"] for x in r)),
                  "mean_tokens_billed": round(sum(x["tokens_in"] + x["tokens_out"] for x in billed)
                                              / max(len(billed), 1), 1),
                  "p50_latency_ms": lat[len(lat) // 2]}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", type=Path)
    args = ap.parse_args()
    counts = Counter(assign_variant(f"user-{i}", 20) for i in range(100))
    split_ok = 15 <= counts["B"] <= 25
    all_counties = sorted(COUNTIES)
    pct = prompt_app.CANDIDATE_PCT
    on_b = sorted(c for c in all_counties if assign_variant(c, pct) == "B") if prompt_app.CANDIDATE_VERSION else []
    report = {"synthetic": {"n": 100, "pct_b": 20, "counts": dict(counts), "band": [15, 25], "ok": split_ok},
              "live_config": {"candidate": prompt_app.CANDIDATE_VERSION, "traffic_pct": pct,
                              "counties_total": len(all_counties), "counties_on_B": on_b,
                              "buckets": {c: bucket(c) for c in on_b}}}
    if args.log:
        report["traffic"] = summarise(args.log)
    Path("ab_report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if split_ok else 1


if __name__ == "__main__":
    sys.exit(main())

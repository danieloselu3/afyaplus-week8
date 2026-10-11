"""API-hosted vs self-hosted break-even for AfyaPlus triage (Week 7 Monday Lab 2).

    python cost/breakeven.py        # prints, writes cost/breakeven_output.json

Break-even N: fixed + var*N = api*N  ->  N = fixed / (api - var).
The API side is the measured gpt-4o-mini cost per request from cost_model.py (one source
of truth). The container, logs and the people who run the API service exist on BOTH
paths, so they cancel out. Only what self-hosting ADDS is on the self-host side.
None of the self-host figures were run by us in production: they are ESTIMATES built from
list prices [2][4] and the one GPU we did rent (Week 4: vast.ai RTX 4090, $0.78/h).
"""
import json
from pathlib import Path

import cost_model as cm

GPU_OPTIONS = {                       # USD per hour, on-demand, checked 2026-10-11
    "Azure NV36ads A10 v5, South Africa North [2]": 4.672,
    "Azure NV36ads A10 v5, East US [2]": 3.20,
    "Azure NC4as T4 v3, East US [2] (16 GB: 8B model only if 4-bit)": 0.526,
    "vast.ai RTX 4090, Week 4 measured [4] (no SLA, not production)": 0.78,
}
PEOPLE_ONCALL_MONTHLY = 400.0         # [A] GPU patching, vLLM upgrades, capacity: the course's honest line
STORAGE_OBS_MONTHLY = 50.0            # [A] model weights, images, GPU metrics
SELFHOST_VAR_PER_REQ = 0.000005       # [A] egress/energy proxy, not zero
GPT4O_PRICE_MULTIPLE = 16.7           # gpt-4o list price / gpt-4o-mini, on both columns [1]


def break_even(api_per_req: float, fixed: float, var: float = SELFHOST_VAR_PER_REQ) -> float:
    margin = api_per_req - var
    return float("inf") if margin <= 0 else fixed / margin


def main() -> None:
    shape = cm.token_shape()
    api_per_req = cm.api_usd(shape["prompt"], shape["completion"])
    volume = cm.BASELINE_PER_DAY * cm.DAYS_PER_MONTH
    rows = []
    print(f"API side: gpt-4o-mini ${api_per_req:.6f}/request ({shape['source']})")
    print(f"AfyaPlus volume: {volume:,}/month baseline, {volume * cm.SPIKE_MULTIPLIER:,} at the 10x spike\n")
    print(f"{'self-host option':66} {'fixed $/mo':>10} {'break-even req/month':>21} {'x our volume':>12}")
    for name, per_h in GPU_OPTIONS.items():
        fixed = per_h * cm.HOURS_PER_MONTH + PEOPLE_ONCALL_MONTHLY + STORAGE_OBS_MONTHLY
        n = break_even(api_per_req, fixed)
        free_people = break_even(api_per_req, fixed - PEOPLE_ONCALL_MONTHLY)
        rows.append({"option": name, "gpu_usd_per_h": per_h, "fixed_usd_month": round(fixed, 2),
                     "break_even_requests_month": round(n),
                     "break_even_if_people_cost_zero": round(free_people),
                     # what-ifs the memo cites: a second GPU for redundancy, and gpt-4o prices
                     "break_even_two_gpus": round(break_even(api_per_req, fixed + per_h * cm.HOURS_PER_MONTH)),
                     "break_even_at_gpt4o_price": round(break_even(api_per_req * GPT4O_PRICE_MULTIPLE, fixed)),
                     "multiple_of_baseline_volume": round(n / volume)})
        print(f"{name:66} {fixed:>10,.0f} {n:>21,.0f} {n / volume:>11,.0f}x")
    cheapest = min(rows, key=lambda r: r["break_even_requests_month"])
    print(f"\nEven the cheapest option needs {cheapest['break_even_requests_month']:,} requests a month "
          f"({cheapest['multiple_of_baseline_volume']:,}x today). With on-call priced at $0 (dishonest) "
          f"it would still need {cheapest['break_even_if_people_cost_zero']:,}.")
    print("\nWhat-ifs (requests/month):")
    for r in rows:
        print(f"  {r['option'][:44]:44} two GPUs: {r['break_even_two_gpus']:>12,}   "
              f"if we paid gpt-4o prices: {r['break_even_at_gpt4o_price']:>10,} "
              f"({r['break_even_at_gpt4o_price'] / volume:,.0f}x today)")
    out = {"api_usd_per_request": api_per_req, "baseline_requests_month": volume,
           "people_oncall_monthly": PEOPLE_ONCALL_MONTHLY, "storage_obs_monthly": STORAGE_OBS_MONTHLY,
           "selfhost_var_per_req": SELFHOST_VAR_PER_REQ, "options": rows}
    (Path(__file__).resolve().parent / "breakeven_output.json").write_text(json.dumps(out, indent=2) + "\n")


if __name__ == "__main__":
    main()

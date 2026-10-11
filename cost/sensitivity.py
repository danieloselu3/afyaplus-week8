"""Which assumption moves the bill? Four sweeps over cost_model.py, no new constants.

    python cost/sensitivity.py

1. tokens per request (the course's grid), $/1k for tokens only
2. cache hit rate x traffic, monthly total
3. model price multiplier (a pricier model, or a price change), monthly total
4. people hours, monthly total: the line that dominates at AfyaPlus volume
"""
import cost_model as cm

BASE = cm.BASELINE_PER_DAY * cm.DAYS_PER_MONTH
SPIKE = BASE * cm.SPIKE_MULTIPLIER


def per_1k(prompt: float, completion: float) -> float:
    return 1000 * cm.api_usd(prompt, completion)


def month_total(requests: int, replicas: int, hit: float = 0.0, price_x: float = 1.0,
                ops_hours: float = cm.OPS_HOURS_PER_MONTH) -> float:
    shape = cm.token_shape()
    tokens = cm.token_usd_month(requests, shape, hit) * price_x
    return (tokens + cm.container_usd_month(requests, replicas) + cm.logs_usd_month(requests)
            + ops_hours * cm.OPS_RATE_USD_PER_H)


def main() -> None:
    shape = cm.token_shape()
    print(f"measured shape: prompt={shape['prompt']} completion={shape['completion']}\n")

    print("1. $/1k, tokens only (rows = prompt tokens, columns = completion tokens)")
    prompts, completions = [60, 123, 300, 450, 900], [15, 31, 80, 180, 360]
    print(f"{'prompt':>8}  " + "  ".join(f"c={c:<6}" for c in completions))
    for p in prompts:
        print(f"{p:>8}  " + "  ".join(f"{per_1k(p, c):8.4f}" for c in completions))
    base = per_1k(shape["prompt"], shape["completion"])
    print(f"measured baseline $/1k={base:.4f}; double the prompt: +{per_1k(2 * shape['prompt'], shape['completion']) - base:.4f}; "
          f"double the completion: +{per_1k(shape['prompt'], 2 * shape['completion']) - base:.4f}")
    print(f"course reference cell (450/180) = {per_1k(450, 180):.4f}  (Lab 1 prints 0.2018 incl. its 15% overhead)\n")

    print("2. monthly total by cache hit rate (1 replica baseline, 2 replicas spike)")
    print(f"{'hit rate':>9}  {'baseline':>9}  {'10x spike':>9}")
    for hit in (0.0, 0.2, 0.36, 0.4, 0.6):
        print(f"{hit:>9.2f}  {month_total(BASE, 1, hit):>9.2f}  {month_total(SPIKE, 2, hit):>9.2f}")
    print()

    print("3. monthly total by model price multiplier (no cache)")
    print(f"{'price x':>9}  {'baseline':>9}  {'10x spike':>9}  note")
    notes = {1: "gpt-4o-mini today", 2: "price doubles", 16.7: "gpt-4o list price, 16.7x on both [1]", 50: "stress test"}
    for x in (1, 2, 16.7, 50):
        print(f"{x:>9}  {month_total(BASE, 1, price_x=x):>9.2f}  {month_total(SPIKE, 2, price_x=x):>9.2f}  {notes[x]}")
    print()

    print("4. monthly total by people hours (no cache)")
    print(f"{'hours':>9}  {'baseline':>9}  {'10x spike':>9}")
    for h in (2, 6, 12, 24):
        print(f"{h:>9}  {month_total(BASE, 1, ops_hours=h):>9.2f}  {month_total(SPIKE, 2, ops_hours=h):>9.2f}")
    print("\nFinding: at AfyaPlus volume the token line is the smallest line. People hours and the "
          "always-on container move the total far more than any token lever.")


if __name__ == "__main__":
    main()

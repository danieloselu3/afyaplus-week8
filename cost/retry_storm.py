"""The incident bucket: what a retry storm adds to the token bill (Week 7 Monday Challenge 2).

    python cost/retry_storm.py        # prints, and writes cost/retry_storm_notes.txt

A buggy partner client that retries every timeout and 429 with no backoff. 5% of
requests enter the loop with 4 extra billed attempts on average, against a sane client
(max 1 retry, only on 503/timeout; the API's own OpenAI client uses max_retries=1).
"""
from pathlib import Path

import cost_model as cm

STORM_FRACTION = 0.05
EXTRA_ATTEMPTS_STORM = 4
EXTRA_ATTEMPTS_SANE = 0.2


def main() -> None:
    shape = cm.token_shape()
    unit = cm.api_usd(shape["prompt"], shape["completion"])
    lines = [f"unit_usd_per_model_call={unit:.6f}"]
    for label, per_day in (("baseline", cm.BASELINE_PER_DAY),
                           ("spike_10x", cm.BASELINE_PER_DAY * cm.SPIKE_MULTIPLIER)):
        n = per_day * cm.DAYS_PER_MONTH
        base = n * unit
        storm = base + n * STORM_FRACTION * EXTRA_ATTEMPTS_STORM * unit
        sane = base + n * STORM_FRACTION * EXTRA_ATTEMPTS_SANE * unit
        lines += [f"{label}: requests_month={n:,} tokens_month={base:.2f} storm={storm:.2f} "
                  f"sane={sane:.2f} amplification={storm / base:.3f}"]
    lines += ["",
              "The amplification (1.200) is the same at any volume: a fifth of the token bill buys nothing.",
              "In dollars it is small here because tokens are small here; the real cost of a storm at",
              "AfyaPlus volume is the rate limit tripping for honest clinicians, and the on-call hour.",
              "Controls in place: per-coordinator rate limit with Retry-After (rate_limit.py),",
              "OpenAI client max_retries=1 (triage_model.py), and the budget alerts in deploy/."]
    text = "\n".join(lines) + "\n"
    (Path(__file__).resolve().parent / "retry_storm_notes.txt").write_text(text)
    print(text, end="")


if __name__ == "__main__":
    main()

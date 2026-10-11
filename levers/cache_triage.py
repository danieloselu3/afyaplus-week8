"""Lever 1 harness: the course's `triage(message)` contract, over the API's real cache.

    python levers/cache_triage.py        # one live call: prints MISS HIT <backend> 0.5

The cache itself lives in response_cache.py because it ships inside the image
and runs on every /triage request. This file only gives the Thursday Lab 1 interface
(a `_cache` field of HIT or MISS) so the measurement scripts stay as the lab wrote them.
"""
import _paths  # noqa: F401  (puts the repo root on sys.path)
from response_cache import backend, cached_triage, hit_rate
from triage_model import triage_model

COUNTY = "Nairobi"


def triage(message: str, county: str = COUNTY) -> dict:
    result, status = cached_triage(triage_model, message, county)
    return {**result, "_cache": status, "_backend": backend()}


if __name__ == "__main__":
    m = "Fever for two days, drinking fluids"
    print(triage(m)["_cache"], triage(m)["_cache"], backend(), round(hit_rate(), 2))

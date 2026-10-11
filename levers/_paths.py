"""Shared paths for the lever scripts. Importing this puts the repo root and cost/ on sys.path,
so the levers measure the SAME code the service runs, not a copy of it."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "fixtures"
RESULTS = Path(__file__).resolve().parent / "results"
for path in (ROOT, ROOT / "cost"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


def percentile(values: list[float], pct: float) -> float:
    """Nearest-rank percentile: p95 = the value 95% of requests were at or under."""
    ordered = sorted(values)
    rank = max(1, -(-len(ordered) * pct // 100))     # ceil without importing math
    return ordered[int(rank) - 1]

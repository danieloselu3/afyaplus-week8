# tool_metrics.py - one counter store per process for MCP tool calls (Week 8 Thursday).
# Import timed_tool / tool_report / _stats from here; never copy them (two stores = an empty
# dashboard with no error to explain why).
#
# The logistics server runs in its OWN process (stdio), so its counters cannot be shared in
# memory. ingest_log() fills the same store from the one-line-per-call log it already writes:
#   ... tool=check_stock item='ors_sachets' county='None' outcome=ok ms=0
import re
from collections import defaultdict
from pathlib import Path
from time import perf_counter

_stats = defaultdict(lambda: {"n": 0, "err": 0, "ms_sum": 0.0})
_LINE = re.compile(r"tool=(?P<tool>\w+) .*outcome=(?P<outcome>\w+) ms=(?P<ms>\d+)")


def timed_tool(name: str, fn, *args, **kwargs):
    """Call fn, counting it under name. A raise is counted as an error and re-raised."""
    t0 = perf_counter()
    ok = True
    try:
        return fn(*args, **kwargs)
    except Exception:
        ok = False
        raise
    finally:
        _stats[name]["n"] += 1
        _stats[name]["ms_sum"] += (perf_counter() - t0) * 1000
        if not ok:
            _stats[name]["err"] += 1


def ingest_log(path: Path) -> int:
    """Count every MCP tool call in a logistics server log. 'error' (bad input returned as
    data) and 'exception' (a crash) both count as errors. Returns lines ingested."""
    n = 0
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = _LINE.search(line)
        if not m:
            continue
        s = _stats[m["tool"]]
        s["n"] += 1
        s["ms_sum"] += int(m["ms"])
        s["err"] += m["outcome"] != "ok"
        n += 1
    return n


def tool_report() -> dict:
    report = {}
    for name, s in _stats.items():
        n = max(s["n"], 1)
        report[name] = {"n": s["n"], "error_rate": round(s["err"] / n, 3), "avg_ms": round(s["ms_sum"] / n, 3)}
    return report


def reset() -> None:
    _stats.clear()

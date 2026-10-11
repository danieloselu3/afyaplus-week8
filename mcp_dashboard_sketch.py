"""MCP tool dashboard: per-tool calls, error rate and latency, with an alert line.

    python mcp_dashboard_sketch.py                       # reads logs/mcp_server.log
    python mcp_dashboard_sketch.py --log some/mcp_server.log

The pipeline's MCP health gate catches a dead server at deploy time. This catches a dying
tool at run time: an agent can "succeed" by failing check_stock three times and improvising,
and /triage would still log 200. Exit 1 if any tool is at or over ALERT_THRESHOLD.
"""
import argparse
import json
import sys
from pathlib import Path

from config import LOG_DIR
from tool_metrics import ingest_log, tool_report

ALERT_THRESHOLD = 0.10       # tuned in runbook.md, not in a chat thread
MIN_CALLS = 10               # do not page on 1 failure out of 2 calls


def alert_if_error_rate(tool: str, threshold: float = ALERT_THRESHOLD) -> bool:
    row = tool_report().get(tool) or {"n": 0, "error_rate": 0}
    if row["n"] >= MIN_CALLS and row["error_rate"] >= threshold:
        print("ALERT", tool, row)
        return True
    return False


def summary() -> dict:
    return tool_report()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", type=Path, default=LOG_DIR / "mcp_server.log")
    args = ap.parse_args()
    lines = ingest_log(args.log) if args.log.exists() else 0
    print(f"{lines} tool calls in {args.log}")
    print(json.dumps(summary(), indent=2))
    alerts = [t for t in summary() if alert_if_error_rate(t)]
    return 1 if alerts else 0


if __name__ == "__main__":
    sys.exit(main())

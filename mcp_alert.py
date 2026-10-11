"""The MCP error-rate alert, with a healthy control (Week 8 Thursday Challenge 2).

    python mcp_alert.py      # exit 0 only if check_stock alerts AND ping does not

50 check_stock calls, 6 of which fail (0.12 >= 0.10), and 20 healthy ping calls (0.00).
The control matters: an alert that fires on ping too has detected that alerting is on, not
that a dependency is failing. Writes mcp_alert_notes.txt.
"""
import sys
from pathlib import Path

import tool_metrics
from mcp_dashboard_sketch import alert_if_error_rate


def ok():
    return "ok"


def boom():
    raise RuntimeError("stock timeout")


def main() -> int:
    tool_metrics.reset()
    for _ in range(44):
        tool_metrics.timed_tool("check_stock", ok)
    for _ in range(6):
        try:
            tool_metrics.timed_tool("check_stock", boom)
        except RuntimeError:
            pass
    for _ in range(20):
        tool_metrics.timed_tool("ping", ok)
    report = tool_metrics.tool_report()
    stock_alert, ping_alert = alert_if_error_rate("check_stock"), alert_if_error_rate("ping")
    lines = [f"report={report}", f"stock_alert={stock_alert}", f"ping_alert={ping_alert}"]
    Path("mcp_alert_notes.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0 if stock_alert and not ping_alert else 1


if __name__ == "__main__":
    sys.exit(main())

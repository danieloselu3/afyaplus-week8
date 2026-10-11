import pytest

import mcp_alert
import mcp_dashboard_sketch as dash
import tool_metrics


@pytest.fixture(autouse=True)
def fresh_counters():
    tool_metrics.reset()
    yield
    tool_metrics.reset()


def test_ingest_counts_real_log_lines(tmp_path):
    log = tmp_path / "mcp_server.log"
    log.write_text(
        "2026-10-11 10:00:00,000 INFO logistics_mcp trace=a tool=check_stock item='ors_sachets' county='None' outcome=ok ms=3\n"
        "2026-10-11 10:00:01,000 INFO logistics_mcp trace=b tool=check_stock item='paracetamol' county='None' outcome=error ms=1\n"
        "2026-10-11 10:00:02,000 INFO logistics_mcp trace=c tool=get_delivery_eta from_clinic_id='C01' to_clinic_id='C04' outcome=exception ms=5\n"
        "a line that is not a tool call\n", encoding="utf-8")
    assert tool_metrics.ingest_log(log) == 3
    report = tool_metrics.tool_report()
    assert report["check_stock"] == {"n": 2, "error_rate": 0.5, "avg_ms": 2.0}
    assert report["get_delivery_eta"]["error_rate"] == 1.0


def test_a_raising_tool_is_counted_and_still_raises():
    with pytest.raises(RuntimeError):
        tool_metrics.timed_tool("check_stock", lambda: (_ for _ in ()).throw(RuntimeError("x")))
    assert tool_metrics.tool_report()["check_stock"]["error_rate"] == 1.0


def test_no_page_on_a_tiny_sample():
    tool_metrics.timed_tool("check_stock", lambda: "ok")
    with pytest.raises(RuntimeError):
        tool_metrics.timed_tool("check_stock", lambda: (_ for _ in ()).throw(RuntimeError("x")))
    assert dash.alert_if_error_rate("check_stock") is False         # 1 of 2 is not a signal yet


def test_threshold_is_inclusive_and_a_quiet_tool_never_alerts():
    for i in range(10):
        if i == 0:
            with pytest.raises(RuntimeError):
                tool_metrics.timed_tool("check_stock", lambda: (_ for _ in ()).throw(RuntimeError("x")))
        else:
            tool_metrics.timed_tool("check_stock", lambda: "ok")
    assert dash.alert_if_error_rate("check_stock") is True          # exactly 0.10
    assert dash.alert_if_error_rate("never_called") is False


def test_alert_challenge_fires_on_the_failing_tool_only(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert mcp_alert.main() == 0

import pytest
from app.window import SlidingWindow

def test_window_bucketed_addition_and_snapshot():
    window = SlidingWindow(window_seconds=60)
    base_t = 1000.0

    # Add 40 INFO events and 10 ERROR events at base_t
    for _ in range(40):
        window.add("INFO", service="payments", message="ok", now=base_t)
    for _ in range(10):
        window.add("ERROR", service="payments", message="DB connection timeout for tx_1234", now=base_t)

    snap = window.snapshot(now=base_t + 10)
    assert snap["total"] == 50
    assert snap["errors"] == 10
    assert snap["error_rate"] == pytest.approx(0.20, rel=1e-3)
    assert snap["events_per_sec"] == pytest.approx(50 / 60.0, abs=0.02)
    assert len(snap["top_errors"]) == 1
    assert "DB connection timeout for tx_<NUM>" in snap["top_errors"][0].message
    assert snap["top_errors"][0].count == 10

def test_window_eviction_after_window_seconds():
    window = SlidingWindow(window_seconds=10)
    t0 = 1000.0

    # Add errors at t=0
    for _ in range(5):
        window.add("ERROR", service="orders", now=t0)

    # Add normal at t=5
    for _ in range(5):
        window.add("INFO", service="orders", now=t0 + 5)

    # At t=6, all 10 in window
    snap_t6 = window.snapshot(now=t0 + 6)
    assert snap_t6["total"] == 10
    assert snap_t6["errors"] == 5

    # At t=12, errors at t0 should be evicted!
    snap_t12 = window.snapshot(now=t0 + 12)
    assert snap_t12["total"] == 5
    assert snap_t12["errors"] == 0
    assert snap_t12["error_rate"] == 0.0

def test_window_service_breakdown():
    window = SlidingWindow(window_seconds=60)
    window.add("ERROR", service="payments", now=1000)
    window.add("INFO", service="payments", now=1000)
    window.add("INFO", service="auth", now=1000)

    snap = window.snapshot(now=1005)
    assert "payments" in snap["services"]
    assert snap["services"]["payments"]["errors"] == 1
    assert snap["services"]["payments"]["total"] == 2
    assert "auth" in snap["services"]
    assert snap["services"]["auth"]["errors"] == 0

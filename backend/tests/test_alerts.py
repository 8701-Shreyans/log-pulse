import pytest
from app.alerts import AlertManager
from app.detector import DetectionResult
from app.models import Severity
from app.config import Settings

@pytest.fixture
def alert_mgr():
    cfg = Settings(
        CONFIRM_TICKS=2,
        RESOLVE_TICKS=2,
        ALERT_COOLDOWN_SEC=10.0
    )
    return AlertManager(config=cfg)

def test_alert_lifecycle_and_confirm_ticks(alert_mgr):
    # Tick 1: First breach -> Not yet confirmed
    res1 = DetectionResult(
        ts="2026-09-28T10:00:00Z", rate=0.08, z=5.0, severity=Severity.MEDIUM,
        breaching=True, baseline_mean=0.02, baseline_std=0.01,
        window_total=100, window_errors=8, top_errors=[]
    )
    emitted1 = alert_mgr.process(res1, now=1000.0)
    assert len(emitted1) == 0
    assert alert_mgr.has_open_alert() is False

    # Tick 2: Second consecutive breach -> Confirmed & OPENED!
    emitted2 = alert_mgr.process(res1, now=1005.0)
    assert len(emitted2) == 1
    assert emitted2[0].event == "OPENED"
    assert emitted2[0].severity == "MEDIUM"
    assert alert_mgr.has_open_alert() is True

    # Tick 3: Ongoing breach with same severity -> Deduplicated (No event)
    emitted3 = alert_mgr.process(res1, now=1010.0)
    assert len(emitted3) == 0

    # Tick 4: Escalation to CRITICAL -> Emits ESCALATED
    res_crit = DetectionResult(
        ts="2026-09-28T10:00:15Z", rate=0.60, z=12.0, severity=Severity.CRITICAL,
        breaching=True, baseline_mean=0.02, baseline_std=0.01,
        window_total=100, window_errors=60, top_errors=[]
    )
    emitted4 = alert_mgr.process(res_crit, now=1015.0)
    assert len(emitted4) == 1
    assert emitted4[0].event == "ESCALATED"
    assert emitted4[0].severity == "CRITICAL"

    # Tick 5: Calm -> Not yet resolved (1/2 calm ticks)
    res_calm = DetectionResult(
        ts="2026-09-28T10:00:20Z", rate=0.02, z=0.0, severity=Severity.NONE,
        breaching=False, baseline_mean=0.02, baseline_std=0.01,
        window_total=100, window_errors=2, top_errors=[]
    )
    emitted5 = alert_mgr.process(res_calm, now=1020.0)
    assert len(emitted5) == 0
    assert alert_mgr.has_open_alert() is True

    # Tick 6: Second calm tick -> Confirmed RESOLVED!
    emitted6 = alert_mgr.process(res_calm, now=1025.0)
    assert len(emitted6) == 1
    assert emitted6[0].event == "RESOLVED"
    assert emitted6[0].status == "RESOLVED"
    assert alert_mgr.has_open_alert() is False

def test_alert_acknowledgement(alert_mgr):
    res = DetectionResult(
        ts="2026-09-28T10:00:00Z", rate=0.08, z=5.0, severity=Severity.MEDIUM,
        breaching=True, baseline_mean=0.02, baseline_std=0.01,
        window_total=100, window_errors=8, top_errors=[]
    )
    alert_mgr.process(res, now=1000.0)
    alerts = alert_mgr.process(res, now=1005.0)
    assert len(alerts) == 1

    alert_id = alerts[0].id
    assert alerts[0].acknowledged is False

    success = alert_mgr.acknowledge(alert_id, by="oncall-dev")
    assert success is True
    history = alert_mgr.get_history()
    assert history[0].acknowledged is True
    assert history[0].acknowledged_by == "oncall-dev"


def test_alert_cooldown_blocks_reopen(alert_mgr):
    res = DetectionResult(
        ts="2026-09-28T10:00:00Z", rate=0.08, z=5.0, severity=Severity.MEDIUM,
        breaching=True, baseline_mean=0.02, baseline_std=0.01,
        window_total=100, window_errors=8, top_errors=[]
    )
    calm = DetectionResult(
        ts="2026-09-28T10:00:20Z", rate=0.02, z=0.0, severity=Severity.NONE,
        breaching=False, baseline_mean=0.02, baseline_std=0.01,
        window_total=100, window_errors=2, top_errors=[]
    )
    alert_mgr.process(res, now=1000.0)
    alert_mgr.process(res, now=1005.0)
    alert_mgr.process(calm, now=1010.0)
    resolved = alert_mgr.process(calm, now=1015.0)
    assert resolved[0].event == "RESOLVED"

    # Still in ALERT_COOLDOWN_SEC=10 window
    alert_mgr.process(res, now=1020.0)
    blocked = alert_mgr.process(res, now=1022.0)
    assert blocked == []
    assert alert_mgr.has_open_alert() is False

    # After cooldown, confirm ticks already accumulated — first post-cooldown tick should reopen
    reopened = alert_mgr.process(res, now=1030.0)
    assert len(reopened) == 1
    assert reopened[0].event == "OPENED"

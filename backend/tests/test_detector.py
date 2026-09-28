import pytest
from app.detector import AnomalyDetector
from app.baseline import Baseline
from app.config import Settings
from app.models import Severity

@pytest.fixture
def detector_and_baseline():
    cfg = Settings(
        Z_LOW=3.0,
        Z_MEDIUM=4.5,
        Z_HIGH=6.5,
        Z_CRITICAL=9.0,
        ABS_RATE_CRITICAL=0.50,
        MIN_ABS_RATE=0.05,
        MIN_EVENTS_IN_WINDOW=20
    )
    b = Baseline(warmup_samples=2, min_std=0.01)
    b.warmup_add(0.02)
    b.warmup_add(0.02)
    det = AnomalyDetector(config=cfg)
    return det, b

def test_detector_normal(detector_and_baseline):
    det, b = detector_and_baseline
    snap = {"error_rate": 0.02, "total": 100, "errors": 2, "top_errors": []}
    res = det.evaluate(snap, b)
    assert res.breaching is False
    assert res.severity == Severity.NONE
    assert res.z == pytest.approx(0.0, abs=0.1)

def test_detector_absolute_rate_floor(detector_and_baseline):
    det, b = detector_and_baseline
    # Baseline is 0.001 ± 0.001, rate is 0.03 (z could be 29, but rate is < 0.05 floor)
    b.mean = 0.001
    b.variance = 0.001 ** 2
    snap = {"error_rate": 0.03, "total": 100, "errors": 3, "top_errors": []}
    res = det.evaluate(snap, b)
    assert res.severity == Severity.NONE
    assert res.breaching is False

def test_detector_severity_boundaries(detector_and_baseline):
    det, b = detector_and_baseline
    b.mean = 0.02
    b.variance = (0.01) ** 2  # std = 0.01

    # LOW: z = 3.5 (rate = 0.055)
    snap_low = {"error_rate": 0.055, "total": 100, "errors": 6, "top_errors": []}
    assert det.evaluate(snap_low, b).severity == Severity.LOW

    # MEDIUM: z = 5.0 (rate = 0.07)
    snap_med = {"error_rate": 0.07, "total": 100, "errors": 7, "top_errors": []}
    assert det.evaluate(snap_med, b).severity == Severity.MEDIUM

    # HIGH: z = 7.0 (rate = 0.09)
    snap_high = {"error_rate": 0.09, "total": 100, "errors": 9, "top_errors": []}
    assert det.evaluate(snap_high, b).severity == Severity.HIGH

    # CRITICAL: z = 10.0 (rate = 0.12)
    snap_crit = {"error_rate": 0.12, "total": 100, "errors": 12, "top_errors": []}
    assert det.evaluate(snap_crit, b).severity == Severity.CRITICAL

    # CRITICAL: rate >= 50%
    snap_crit_rate = {"error_rate": 0.55, "total": 100, "errors": 55, "top_errors": []}
    assert det.evaluate(snap_crit_rate, b).severity == Severity.CRITICAL

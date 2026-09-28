import pytest
import os
import tempfile
from app.baseline import Baseline

def test_baseline_warmup_gating():
    baseline = Baseline(warmup_samples=5, alpha=0.1, min_std=0.01)
    assert baseline.ready is False

    for _ in range(4):
        baseline.warmup_add(0.02)
        assert baseline.ready is False

    baseline.warmup_add(0.02)
    assert baseline.ready is True
    assert baseline.mean == pytest.approx(0.02, rel=1e-3)
    assert baseline.std >= 0.01

def test_baseline_ewma_updates_and_std_floor():
    baseline = Baseline(warmup_samples=3, alpha=0.1, min_std=0.01)
    for _ in range(3):
        baseline.warmup_add(0.02)

    initial_mean = baseline.mean
    # Normal update increases mean
    baseline.update(0.08)
    assert baseline.mean > initial_mean
    assert baseline.std >= 0.01

def test_baseline_persistence():
    with tempfile.TemporaryDirectory() as tmpdir:
        persist_file = os.path.join(tmpdir, "baseline.json")
        b1 = Baseline(warmup_samples=2, persist_path=persist_file)
        b1.warmup_add(0.03)
        b1.warmup_add(0.03)
        assert b1.ready is True

        # Load in new baseline instance
        b2 = Baseline(warmup_samples=2, persist_path=persist_file)
        assert b2.ready is True
        assert b2.mean == pytest.approx(0.03, rel=1e-3)


def test_baseline_robust_median_mad_after_spike():
    baseline = Baseline(warmup_samples=5, alpha=0.1, min_std=0.01)
    for _ in range(5):
        baseline.warmup_add(0.02)

    for rate in [0.02, 0.02, 0.02, 0.02, 0.42, 0.02, 0.02, 0.02, 0.02]:
        baseline.update(rate)

    assert baseline.median < 0.05
    assert baseline.mad < 0.05
    assert baseline.robust_scale > 0

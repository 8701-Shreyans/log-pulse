from dataclasses import dataclass
from datetime import datetime, timezone
import time
from typing import Optional, List
from app.models import Severity, TopError
from app.baseline import Baseline
from app.config import Settings

@dataclass
class DetectionResult:
    ts: str
    rate: float
    z: float
    severity: Severity
    breaching: bool
    baseline_mean: float
    baseline_std: float
    window_total: int
    window_errors: int
    top_errors: List[TopError]

class AnomalyDetector:
    """
    Statistical Anomaly Detector calculating z-score against learned baseline.
    Applies absolute rate floor and maps deviation to Severity enum.
    """
    def __init__(self, config: Settings):
        self.cfg = config

    def classify_severity(self, z: float, rate: float) -> Severity:
        # 1. Absolute floor: ignore tiny rates below MIN_ABS_RATE
        if rate < self.cfg.MIN_ABS_RATE:
            return Severity.NONE

        # 2. Critical if absolute error rate >= 50% or z-score >= Z_CRITICAL
        if rate >= self.cfg.ABS_RATE_CRITICAL or z >= self.cfg.Z_CRITICAL:
            return Severity.CRITICAL

        # 3. Standard z-score thresholds
        if z >= self.cfg.Z_HIGH:
            return Severity.HIGH
        if z >= self.cfg.Z_MEDIUM:
            return Severity.MEDIUM
        if z >= self.cfg.Z_LOW:
            return Severity.LOW

        return Severity.NONE

    def evaluate(
        self,
        snapshot: dict,
        baseline: Baseline,
        now: Optional[float] = None
    ) -> DetectionResult:
        rate = snapshot["error_rate"]
        total = snapshot["total"]
        errors = snapshot["errors"]
        top_errors = snapshot.get("top_errors", [])

        center = baseline.median if baseline.history else baseline.mean
        scale = baseline.robust_scale if baseline.history else baseline.std
        mean = baseline.mean
        std = baseline.std

        # Use the robust center/scale for spiky error-rate distributions. The EWMA mean/std
        # is still kept for persistence and display, but a median/MAD-based z-score is far
        # less sensitive to a single burst of errors.
        z = (rate - center) / scale if scale > 0 else 0.0
        z = round(max(0.0, z), 2)

        # Reliability check: total in window must meet minimum
        if total < self.cfg.MIN_EVENTS_IN_WINDOW:
            severity = Severity.NONE
        else:
            severity = self.classify_severity(z, rate)

        breaching = severity > Severity.NONE

        ts_str = datetime.fromtimestamp(now or time.time(), tz=timezone.utc).isoformat()

        return DetectionResult(
            ts=ts_str,
            rate=rate,
            z=z,
            severity=severity,
            breaching=breaching,
            baseline_mean=round(mean, 4),
            baseline_std=round(std, 4),
            window_total=total,
            window_errors=errors,
            top_errors=top_errors
        )

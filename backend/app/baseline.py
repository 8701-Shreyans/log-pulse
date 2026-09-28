import math
import json
import os
import logging
from collections import deque
from typing import Optional, List
from app.models import BaselineState

logger = logging.getLogger("baseline")

class Baseline:
    """
    EWMA baseline with a robust median/MAD fallback for spiky error-rate distributions.

    The EWMA mean/variance still provides a smooth estimate of the current level, but the
    detector compares against the robust center and scale so a single anomaly does not distort
    the baseline and poison the next real alert.
    """
    def __init__(
        self,
        warmup_samples: int = 24,
        alpha: float = 0.05,
        min_std: float = 0.01,
        z_threshold: float = 3.0,
        persist_path: Optional[str] = None
    ):
        self.warmup_samples = warmup_samples
        self.alpha = alpha
        self.min_std = min_std
        self.z_threshold = z_threshold
        self.persist_path = persist_path

        self.samples: int = 0
        self.warmup_buffer: List[float] = []
        self.history: deque[float] = deque(maxlen=max(128, warmup_samples * 10))
        self.ready: bool = False
        self.mean: float = 0.0
        self.variance: float = min_std ** 2
        self.median: float = 0.0
        self.mad: float = min_std
        self.robust_scale: float = min_std

        # Try to load existing persisted baseline if available
        self.load()

    @property
    def std(self) -> float:
        calc_std = math.sqrt(max(0.0, self.variance))
        return max(calc_std, self.min_std, self.robust_scale)

    @property
    def upper_band(self) -> float:
        return self.median + (self.z_threshold * self.robust_scale)

    def _recompute_robust_stats(self):
        if not self.history:
            self.median = self.mean
            self.mad = self.min_std
            self.robust_scale = self.min_std
            return

        values = sorted(self.history)
        n = len(values)
        mid = n // 2
        if n % 2 == 0:
            self.median = (values[mid - 1] + values[mid]) / 2.0
        else:
            self.median = values[mid]

        deviations = [abs(v - self.median) for v in values]
        deviations = sorted(deviations)
        mad_index = len(deviations) // 2
        if len(deviations) % 2 == 0:
            self.mad = (deviations[mad_index - 1] + deviations[mad_index]) / 2.0
        else:
            self.mad = deviations[mad_index]

        self.robust_scale = max(self.mad * 1.4826, self.min_std)

    def warmup_add(self, error_rate: float):
        """Accumulate samples during warm-up phase."""
        if self.ready:
            return

        self.warmup_buffer.append(error_rate)
        self.history.append(error_rate)
        self.samples = len(self.warmup_buffer)

        # Update running mean for display during warmup
        self.mean = sum(self.warmup_buffer) / len(self.warmup_buffer)
        if len(self.warmup_buffer) > 1:
            var = sum((x - self.mean) ** 2 for x in self.warmup_buffer) / (len(self.warmup_buffer) - 1)
            self.variance = max(var, self.min_std ** 2)

        self._recompute_robust_stats()

        if len(self.warmup_buffer) >= self.warmup_samples:
            self.ready = True
            logger.info(
                "Baseline warm-up complete! Initialized baseline: "
                f"mean={self.mean:.4f}, median={self.median:.4f}, robust_scale={self.robust_scale:.4f}"
            )
            self.save()

    def update(self, error_rate: float):
        """Update EWMA baseline with a non-anomalous sample."""
        if not self.ready:
            self.warmup_add(error_rate)
            return

        self.samples += 1
        self.history.append(error_rate)
        diff = error_rate - self.mean
        self.mean += self.alpha * diff
        self.variance = (1.0 - self.alpha) * (self.variance + self.alpha * (diff ** 2))
        self.variance = max(self.variance, self.min_std ** 2)
        self._recompute_robust_stats()

    def state(self) -> BaselineState:
        warmup_progress = 1.0 if self.ready else (len(self.warmup_buffer) / max(1, self.warmup_samples))
        return BaselineState(
            mean=round(self.mean, 4),
            std=round(self.std, 4),
            samples=self.samples,
            ready=self.ready,
            upper_band=round(self.upper_band, 4),
            warmup_target=self.warmup_samples,
            warmup_progress=round(warmup_progress, 2),
            median=round(self.median, 4),
            mad=round(self.mad, 4),
            robust_scale=round(self.robust_scale, 4)
        )

    def reset(self):
        self.samples = 0
        self.warmup_buffer.clear()
        self.history.clear()
        self.ready = False
        self.mean = 0.0
        self.variance = self.min_std ** 2
        self.median = 0.0
        self.mad = self.min_std
        self.robust_scale = self.min_std

    def save(self):
        if not self.persist_path:
            return
        try:
            os.makedirs(os.path.dirname(os.path.abspath(self.persist_path)), exist_ok=True)
            data = {
                "mean": self.mean,
                "variance": self.variance,
                "samples": self.samples,
                "ready": self.ready,
                "median": self.median,
                "mad": self.mad,
                "robust_scale": self.robust_scale
            }
            with open(self.persist_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to persist baseline to {self.persist_path}: {e}")

    def load(self):
        if not self.persist_path or not os.path.exists(self.persist_path):
            return
        try:
            with open(self.persist_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.mean = float(data.get("mean", 0.0))
            self.variance = float(data.get("variance", self.min_std ** 2))
            self.samples = int(data.get("samples", 0))
            self.ready = bool(data.get("ready", False))
            self.median = float(data.get("median", self.mean))
            self.mad = float(data.get("mad", self.min_std))
            self.robust_scale = max(float(data.get("robust_scale", max(self.mad * 1.4826, self.min_std))), self.min_std)
            if self.ready:
                logger.info(f"Loaded existing baseline from {self.persist_path}: mean={self.mean:.4f}, median={self.median:.4f}, robust_scale={self.robust_scale:.4f}")
        except Exception as e:
            logger.warning(f"Could not load baseline file: {e}")

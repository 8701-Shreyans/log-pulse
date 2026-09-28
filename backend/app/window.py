from collections import deque, Counter
from dataclasses import dataclass, field
import time
from typing import Optional, Dict, Any, List
from app.models import TopError
from app.parser import normalize_error_signature

@dataclass
class Bucket:
    sec: int
    total: int = 0
    errors: int = 0
    warnings: int = 0
    error_counts: Counter = field(default_factory=Counter)
    service_error_counts: Counter = field(default_factory=Counter)

class SlidingWindow:
    """
    Time-bucketed 1-second sliding window ring buffer.
    Provides snapshot metrics (error rate, errors, events/sec, top errors) in O(window) time.
    """
    def __init__(self, window_seconds: int = 60):
        self.window = window_seconds
        self.buckets: deque[Bucket] = deque()
        self.service_windows: Dict[str, "SlidingWindow"] = {}

    def add(
        self,
        level: str,
        service: str = "unknown",
        message: str = "",
        now: Optional[float] = None
    ):
        sec = int(now if now is not None else time.time())

        if not self.buckets or self.buckets[-1].sec != sec:
            self.buckets.append(Bucket(sec=sec))

        b = self.buckets[-1]
        b.total += 1
        lvl_upper = level.upper()
        if lvl_upper == "ERROR":
            b.errors += 1
            if message:
                norm_msg = normalize_error_signature(message)
                b.error_counts[norm_msg] += 1
                b.service_error_counts[(norm_msg, service)] += 1
        elif lvl_upper == "WARNING":
            b.warnings += 1

        # Track per-service child window (without infinite recursion on service_windows)
        if service and service != "unknown":
            if service not in self.service_windows:
                self.service_windows[service] = SlidingWindow(window_seconds=self.window)
            sub_window = self.service_windows[service]
            sub_sec = sec
            if not sub_window.buckets or sub_window.buckets[-1].sec != sub_sec:
                sub_window.buckets.append(Bucket(sec=sub_sec))
            sub_b = sub_window.buckets[-1]
            sub_b.total += 1
            if lvl_upper == "ERROR":
                sub_b.errors += 1
            elif lvl_upper == "WARNING":
                sub_b.warnings += 1

    def _evict(self, now_sec: int):
        cutoff = now_sec - self.window
        while self.buckets and self.buckets[0].sec <= cutoff:
            self.buckets.popleft()

    def snapshot(self, now: Optional[float] = None) -> Dict[str, Any]:
        now_i = int(now if now is not None else time.time())
        self._evict(now_i)

        total = sum(b.total for b in self.buckets)
        errors = sum(b.errors for b in self.buckets)
        warnings = sum(b.warnings for b in self.buckets)

        # Aggregate top errors
        agg_counter: Counter = Counter()
        agg_service_counter: Counter = Counter()
        for b in self.buckets:
            agg_counter.update(b.error_counts)
            agg_service_counter.update(b.service_error_counts)

        top_errors_list: List[TopError] = []
        for (norm_msg, srv), count in agg_service_counter.most_common(5):
            top_errors_list.append(TopError(message=norm_msg, count=count, service=srv))

        error_rate = (errors / total) if total > 0 else 0.0
        events_per_sec = total / max(1, self.window)

        # Service breakdown
        service_breakdown = {}
        for srv, sub_win in self.service_windows.items():
            sub_win._evict(now_i)
            sub_total = sum(b.total for b in sub_win.buckets)
            sub_errors = sum(b.errors for b in sub_win.buckets)
            if sub_total > 0:
                service_breakdown[srv] = {
                    "total": sub_total,
                    "errors": sub_errors,
                    "error_rate": round(sub_errors / sub_total, 4)
                }

        return {
            "total": total,
            "errors": errors,
            "warnings": warnings,
            "error_rate": round(error_rate, 4),
            "events_per_sec": round(events_per_sec, 2),
            "top_errors": top_errors_list,
            "services": service_breakdown
        }

    def clear(self):
        self.buckets.clear()
        self.service_windows.clear()

from datetime import datetime, timezone
import time
import uuid
import threading
from typing import Optional, List, Dict
from collections import deque

from app.models import Alert, Severity, TopError
from app.detector import DetectionResult
from app.config import Settings

class AlertManager:
    """
    Manages alert state machine with hysteresis (confirm_ticks / resolve_ticks),
    severity escalation, cooldown flap protection, deduplication, and persistence.
    """
    def __init__(self, config: Settings):
        self.cfg = config
        self.lock = threading.Lock()

        # State per key
        self.active_alerts: Dict[str, Alert] = {}
        self.consecutive_breaches: Dict[str, int] = {}
        self.consecutive_calms: Dict[str, int] = {}
        self.last_resolved_time: Dict[str, float] = {}

        # Alert history store (newest first)
        self.alert_history: deque[Alert] = deque(maxlen=config.ALERT_HISTORY_LIMIT)

    def has_open_alert(self, key: str = "error_rate:global") -> bool:
        with self.lock:
            return key in self.active_alerts

    def process(
        self,
        result: Optional[DetectionResult],
        key: str = "error_rate:global",
        now: Optional[float] = None
    ) -> List[Alert]:
        """
        Process detection tick. Returns list of emitted Alert events (0 or 1).
        """
        if result is None:
            return []

        now_f = now if now is not None else time.time()
        now_iso = datetime.fromtimestamp(now_f, tz=timezone.utc).isoformat()
        events_to_emit: List[Alert] = []

        with self.lock:
            is_active = key in self.active_alerts
            current_alert = self.active_alerts.get(key)

            # Calm = not breaching, or z has fallen below RESOLVE_Z (hysteresis)
            is_calm = (not result.breaching) or (result.z < self.cfg.RESOLVE_Z)

            if not is_calm:
                # Reset calm counter
                self.consecutive_calms[key] = 0
                self.consecutive_breaches[key] = self.consecutive_breaches.get(key, 0) + 1

                # Cooldown check
                last_res = self.last_resolved_time.get(key, 0)
                in_cooldown = (now_f - last_res) < self.cfg.ALERT_COOLDOWN_SEC

                if not is_active:
                    # Check if confirm_ticks met and not in cooldown
                    if self.consecutive_breaches[key] >= self.cfg.CONFIRM_TICKS and not in_cooldown:
                        # Open new alert
                        alert_id = uuid.uuid4().hex[:8]
                        title = f"Error rate spike: {result.rate*100:.1f}% (baseline {result.baseline_mean*100:.1f}%)"
                        alert = Alert(
                            id=alert_id,
                            key=key,
                            status="OPEN",
                            event="OPENED",
                            severity=result.severity.label,
                            peak_severity=result.severity.label,
                            title=title,
                            error_rate=result.rate,
                            baseline_mean=result.baseline_mean,
                            baseline_std=result.baseline_std,
                            z_score=result.z,
                            window_seconds=self.cfg.WINDOW_SECONDS,
                            window_total=result.window_total,
                            window_errors=result.window_errors,
                            top_errors=result.top_errors,
                            opened_at=now_iso,
                            updated_at=now_iso,
                            publish_status={"cloudwatch": "pending", "sns": "pending"}
                        )
                        self.active_alerts[key] = alert
                        self.alert_history.appendleft(alert)
                        events_to_emit.append(alert)
                else:
                    # Alert is already OPEN: check for severity escalation
                    old_sev_val = Severity[current_alert.severity].value
                    new_sev_val = result.severity.value

                    # Update latest metrics on active alert
                    current_alert.error_rate = result.rate
                    current_alert.z_score = result.z
                    current_alert.window_total = result.window_total
                    current_alert.window_errors = result.window_errors
                    current_alert.top_errors = result.top_errors
                    current_alert.updated_at = now_iso

                    if new_sev_val > old_sev_val:
                        # Escalation!
                        current_alert.severity = result.severity.label
                        current_alert.peak_severity = result.severity.label
                        current_alert.event = "ESCALATED"
                        current_alert.title = f"Error rate escalated: {result.rate*100:.1f}% ({result.severity.label})"
                        self.alert_history.appendleft(current_alert)
                        events_to_emit.append(current_alert)
                    elif new_sev_val < old_sev_val:
                        # Downgrade: update current severity silently without spamming events
                        current_alert.severity = result.severity.label

            else:
                # Not breaching (calm)
                self.consecutive_breaches[key] = 0

                if is_active:
                    self.consecutive_calms[key] = self.consecutive_calms.get(key, 0) + 1
                    if self.consecutive_calms[key] >= self.cfg.RESOLVE_TICKS:
                        # Resolve alert
                        resolved_alert = self.active_alerts.pop(key)
                        resolved_alert.status = "RESOLVED"
                        resolved_alert.event = "RESOLVED"
                        resolved_alert.resolved_at = now_iso
                        resolved_alert.updated_at = now_iso
                        resolved_alert.title = f"Anomaly resolved: Error rate returned to {result.rate*100:.1f}%"
                        resolved_alert.error_rate = result.rate
                        resolved_alert.z_score = result.z
                        
                        self.last_resolved_time[key] = now_f
                        self.consecutive_calms[key] = 0
                        self.alert_history.appendleft(resolved_alert)
                        events_to_emit.append(resolved_alert)

        return events_to_emit

    def get_history(self, status: Optional[str] = None, limit: int = 50) -> List[Alert]:
        with self.lock:
            alerts = list(self.alert_history)
            if status:
                s_upper = status.upper()
                alerts = [a for a in alerts if a.status.upper() == s_upper]
            return alerts[:limit]

    def get_active(self) -> List[Alert]:
        with self.lock:
            return list(self.active_alerts.values())

    def acknowledge(self, alert_id: str, by: Optional[str] = None) -> bool:
        with self.lock:
            for alert in self.alert_history:
                if alert.id == alert_id:
                    alert.acknowledged = True
                    alert.acknowledged_by = by or "operator"
                    return True
            for alert in self.active_alerts.values():
                if alert.id == alert_id:
                    alert.acknowledged = True
                    alert.acknowledged_by = by or "operator"
                    return True
            return False

    def clear(self):
        with self.lock:
            self.active_alerts.clear()
            self.consecutive_breaches.clear()
            self.consecutive_calms.clear()
            self.last_resolved_time.clear()
            self.alert_history.clear()

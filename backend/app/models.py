from datetime import datetime, timezone
from enum import Enum, IntEnum
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field
import uuid

class Severity(IntEnum):
    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

    @property
    def label(self) -> str:
        return self.name

class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"

    @classmethod
    def normalize(cls, val: str) -> "LogLevel":
        v = str(val).strip().upper()
        if v in ("WARN", "WARNING"):
            return cls.WARNING
        if v in ("ERR", "ERROR", "CRIT", "CRITICAL", "FATAL", "EMERG", "ALERT"):
            return cls.ERROR
        if v == "DEBUG":
            return cls.DEBUG
        return cls.INFO

    def is_error(self) -> bool:
        return self == LogLevel.ERROR

class LogEvent(BaseModel):
    ts: datetime
    level: LogLevel
    service: str = "unknown"
    message: str
    raw: str

class TopError(BaseModel):
    message: str
    count: int
    service: str = "unknown"

class MetricPoint(BaseModel):
    ts: str
    error_rate: float
    total: int
    errors: int
    events_per_sec: float
    baseline_mean: float
    baseline_std: float
    upper_band: float
    z: float
    severity: str
    is_breach: bool

class BaselineState(BaseModel):
    mean: float
    std: float
    samples: int
    ready: bool
    upper_band: float
    warmup_target: int
    warmup_progress: float
    median: float = 0.0
    mad: float = 0.0
    robust_scale: float = 0.0

class Alert(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    key: str = "error_rate:global"
    status: Literal["OPEN", "RESOLVED"] = "OPEN"
    event: Literal["OPENED", "ESCALATED", "RESOLVED"] = "OPENED"
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = "LOW"
    peak_severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = "LOW"
    title: str
    error_rate: float
    baseline_mean: float
    baseline_std: float
    z_score: float
    window_seconds: int
    window_total: int
    window_errors: int
    top_errors: List[TopError] = Field(default_factory=list)
    opened_at: str
    updated_at: str
    resolved_at: Optional[str] = None
    acknowledged: bool = False
    acknowledged_by: Optional[str] = None
    publish_status: Dict[str, str] = Field(default_factory=lambda: {"cloudwatch": "pending", "sns": "pending"})

class Envelope(BaseModel):
    type: Literal["metric", "alert", "baseline", "log", "snapshot", "heartbeat"]
    seq: int
    ts: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    data: Any

class AppConfig(BaseModel):
    window_seconds: int
    eval_interval_sec: float
    min_events_in_window: int
    z_low: float
    z_medium: float
    z_high: float
    z_critical: float
    abs_rate_critical: float
    min_abs_rate: float
    publish_mode: str
    sim_enabled: bool

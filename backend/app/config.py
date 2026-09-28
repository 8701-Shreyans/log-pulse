import os
from typing import Literal, Optional, List, Any
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, model_validator

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @model_validator(mode="before")
    @classmethod
    def strip_inline_comments(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        cleaned: dict[str, Any] = {}
        for key, value in data.items():
            if isinstance(value, str):
                cleaned[key] = value.split(" #", 1)[0].strip()
            else:
                cleaned[key] = value
        return cleaned

    # --- Input ---
    LOG_FILE_PATH: str = Field(default="./data/app.log", description="Log file path to monitor")
    LOG_FORMAT: Literal["auto", "text", "json"] = Field(default="auto", description="Log format")
    TAIL_POLL_INTERVAL_SEC: float = Field(default=0.2, description="File tail poll interval in seconds")
    TAIL_FROM_START: bool = Field(default=False, description="Read from beginning of log on start if true")

    # --- Windowing ---
    WINDOW_SECONDS: int = Field(default=60, description="Sliding window length in seconds")
    EVAL_INTERVAL_SEC: float = Field(default=2.0, description="Interval in seconds to evaluate metric and detector")
    MIN_EVENTS_IN_WINDOW: int = Field(default=20, description="Minimum events in window for statistical reliability")

    # --- Baseline ---
    BASELINE_WARMUP_SAMPLES: int = Field(default=24, description="Warm-up evaluation samples before detection starts")
    BASELINE_ALPHA: float = Field(default=0.05, description="EWMA smoothing factor")
    BASELINE_MIN_STD: float = Field(default=0.01, description="Minimum standard deviation floor (1 percentage point)")
    FREEZE_BASELINE_DURING_ALERT: bool = Field(default=True, description="Freeze baseline updates when alert is active")
    BASELINE_PERSIST_PATH: str = Field(default="./data/baseline.json", description="File path to save/load baseline")

    # --- Detection Thresholds ---
    Z_LOW: float = Field(default=3.0, description="Z-score threshold for LOW severity")
    Z_MEDIUM: float = Field(default=4.5, description="Z-score threshold for MEDIUM severity")
    Z_HIGH: float = Field(default=6.5, description="Z-score threshold for HIGH severity")
    Z_CRITICAL: float = Field(default=9.0, description="Z-score threshold for CRITICAL severity")
    ABS_RATE_CRITICAL: float = Field(default=0.50, description="Absolute error rate that triggers CRITICAL severity")
    MIN_ABS_RATE: float = Field(default=0.05, description="Minimum absolute error rate before alerting (5%)")
    CONFIRM_TICKS: int = Field(default=2, description="Consecutive breaching ticks required before opening alert")
    RESOLVE_Z: float = Field(default=2.0, description="Z-score threshold below which state is considered calm")
    RESOLVE_TICKS: int = Field(default=3, description="Consecutive calm ticks before resolving alert")
    ALERT_COOLDOWN_SEC: float = Field(default=60.0, description="Minimum cooldown time in seconds before re-opening alert")

    # --- Alert Publishing ---
    PUBLISH_MODE: Literal["dry_run", "aws"] = Field(default="dry_run", description="Alert publishing mode")
    AWS_REGION: str = Field(default="ap-south-1", description="AWS Region")
    AWS_ACCESS_KEY_ID: Optional[str] = Field(default=None, description="AWS Access Key")
    AWS_SECRET_ACCESS_KEY: Optional[str] = Field(default=None, description="AWS Secret Key")
    AWS_SESSION_TOKEN: Optional[str] = Field(default=None, description="AWS Session Token")
    CW_LOG_GROUP: str = Field(default="/hackathon/log-anomaly-detector", description="CloudWatch Log Group")
    CW_LOG_STREAM: str = Field(default="alerts", description="CloudWatch Log Stream")
    SNS_TOPIC_ARN: Optional[str] = Field(default=None, description="SNS Topic ARN")
    SNS_MIN_SEVERITY: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = Field(default="MEDIUM", description="Min severity for SNS")
    AWS_ENDPOINT_URL: Optional[str] = Field(default=None, description="Custom AWS endpoint for LocalStack")
    AWS_MAX_RETRIES: int = Field(default=3, description="Max publish retry attempts")

    # --- API & Bus ---
    HOST: str = Field(default="0.0.0.0", description="API Host")
    PORT: int = Field(default=8000, description="API Port")
    CORS_ORIGINS: str = Field(default="*", description="Allowed CORS origins comma-separated")
    RING_BUFFER_SIZE: int = Field(default=2000, description="Max envelopes kept in memory ring buffer")
    ALERT_HISTORY_LIMIT: int = Field(default=200, description="Max alerts stored in memory history")
    ENABLE_SIM: bool = Field(default=True, description="Enable simulation control endpoints")
    SIM_CONTROL_PATH: str = Field(default="./data/sim_control.json", description="Simulation control flag file")

settings = Settings()

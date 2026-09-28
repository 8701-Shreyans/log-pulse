import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from app.models import Alert
from app.config import Settings

logger = logging.getLogger("publisher.cloudwatch")

try:
    import boto3
    from botocore.exceptions import ClientError, BotoCoreError
    BOTO3_AVAILABLE = True
except ImportError:
    boto3 = None
    ClientError = Exception
    BotoCoreError = Exception
    BOTO3_AVAILABLE = False

class CloudWatchPublisher:
    """
    Publishes structured alert logs to AWS CloudWatch Logs.
    Ensures log group and stream exist upon initial use.
    """
    name = "cloudwatch"

    def __init__(self, config: Settings):
        self.cfg = config
        self._client = None
        self._initialized = False

    def _get_client(self):
        if not BOTO3_AVAILABLE:
            raise RuntimeError("boto3 is not installed; cannot publish to CloudWatch")
        if self._client is None:
            kwargs: Dict[str, Any] = {"region_name": self.cfg.AWS_REGION}
            if self.cfg.AWS_ACCESS_KEY_ID and self.cfg.AWS_SECRET_ACCESS_KEY:
                kwargs["aws_access_key_id"] = self.cfg.AWS_ACCESS_KEY_ID
                kwargs["aws_secret_access_key"] = self.cfg.AWS_SECRET_ACCESS_KEY
                if self.cfg.AWS_SESSION_TOKEN:
                    kwargs["aws_session_token"] = self.cfg.AWS_SESSION_TOKEN
            if self.cfg.AWS_ENDPOINT_URL:
                kwargs["endpoint_url"] = self.cfg.AWS_ENDPOINT_URL

            self._client = boto3.client("logs", **kwargs)
        return self._client

    def _ensure_group_and_stream(self, client):
        if self._initialized:
            return
        try:
            client.create_log_group(logGroupName=self.cfg.CW_LOG_GROUP)
        except Exception:
            pass

        try:
            client.create_log_stream(
                logGroupName=self.cfg.CW_LOG_GROUP,
                logStreamName=self.cfg.CW_LOG_STREAM
            )
        except Exception:
            pass
        self._initialized = True

    def _sync_put_log(self, alert: Alert):
        client = self._get_client()
        self._ensure_group_and_stream(client)

        payload = {
            "service": "log-anomaly-detector",
            "event": alert.event,
            "severity": alert.severity,
            "alert_id": alert.id,
            "title": alert.title,
            "error_rate": alert.error_rate,
            "baseline_mean": alert.baseline_mean,
            "z_score": alert.z_score,
            "window_seconds": alert.window_seconds,
            "top_errors": [e.model_dump() for e in alert.top_errors]
        }

        # Epoch milliseconds
        ts_ms = int(time.time() * 1000)

        client.put_log_events(
            logGroupName=self.cfg.CW_LOG_GROUP,
            logStreamName=self.cfg.CW_LOG_STREAM,
            logEvents=[
                {
                    "timestamp": ts_ms,
                    "message": json.dumps(payload, default=str)
                }
            ]
        )

    async def publish(self, alert: Alert) -> None:
        await asyncio.to_thread(self._sync_put_log, alert)
        logger.info(f"Published alert {alert.id} to CloudWatch Log Group {self.cfg.CW_LOG_GROUP}")

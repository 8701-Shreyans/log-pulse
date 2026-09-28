import asyncio
import json
import logging
from typing import Optional, Dict, Any

from app.models import Alert, Severity
from app.config import Settings

logger = logging.getLogger("publisher.sns")

try:
    import boto3
    from botocore.exceptions import ClientError, BotoCoreError
    BOTO3_AVAILABLE = True
except ImportError:
    boto3 = None
    ClientError = Exception
    BotoCoreError = Exception
    BOTO3_AVAILABLE = False

class SnsPublisher:
    """
    Publishes critical alerts and notifications to an AWS SNS Topic.
    Filters by SNS_MIN_SEVERITY to avoid paging for low-severity deviations.
    """
    name = "sns"

    def __init__(self, config: Settings):
        self.cfg = config
        self._client = None

    def _get_client(self):
        if not BOTO3_AVAILABLE:
            raise RuntimeError("boto3 is not installed; cannot publish to SNS")
        if self._client is None:
            kwargs: Dict[str, Any] = {"region_name": self.cfg.AWS_REGION}
            if self.cfg.AWS_ACCESS_KEY_ID and self.cfg.AWS_SECRET_ACCESS_KEY:
                kwargs["aws_access_key_id"] = self.cfg.AWS_ACCESS_KEY_ID
                kwargs["aws_secret_access_key"] = self.cfg.AWS_SECRET_ACCESS_KEY
                if self.cfg.AWS_SESSION_TOKEN:
                    kwargs["aws_session_token"] = self.cfg.AWS_SESSION_TOKEN
            if self.cfg.AWS_ENDPOINT_URL:
                kwargs["endpoint_url"] = self.cfg.AWS_ENDPOINT_URL

            self._client = boto3.client("sns", **kwargs)
        return self._client

    def _should_publish(self, alert: Alert) -> bool:
        if not self.cfg.SNS_TOPIC_ARN:
            return False
        min_sev_val = Severity[self.cfg.SNS_MIN_SEVERITY].value
        alert_sev_val = Severity[alert.severity].value
        return alert_sev_val >= min_sev_val

    def _sync_publish(self, alert: Alert):
        client = self._get_client()
        subject = f"[{alert.severity}] Anomaly Alert: {alert.title}"[:100]

        top_err_str = "\n".join([f"  - {e.message} (count: {e.count})" for e in alert.top_errors])
        body = (
            f"=== LOG ANOMALY DETECTOR ALERT ===\n\n"
            f"Event: {alert.event}\n"
            f"Severity: {alert.severity} (Peak: {alert.peak_severity})\n"
            f"Title: {alert.title}\n"
            f"Error Rate: {alert.error_rate*100:.2f}%\n"
            f"Baseline: {alert.baseline_mean*100:.2f}% ± {alert.baseline_std*100:.2f}%\n"
            f"Deviation Z-Score: {alert.z_score:.2f}σ\n"
            f"Window: {alert.window_seconds}s (Total: {alert.window_total}, Errors: {alert.window_errors})\n"
            f"Timestamp: {alert.updated_at}\n\n"
            f"Top Error Signatures:\n{top_err_str or '  None'}\n\n"
            f"JSON Payload:\n{json.dumps(alert.model_dump(), indent=2)}"
        )

        client.publish(
            TopicArn=self.cfg.SNS_TOPIC_ARN,
            Subject=subject,
            Message=body,
            MessageAttributes={
                "severity": {"DataType": "String", "StringValue": alert.severity},
                "event": {"DataType": "String", "StringValue": alert.event},
                "alert_key": {"DataType": "String", "StringValue": alert.key}
            }
        )

    async def publish(self, alert: Alert) -> None:
        if not self._should_publish(alert):
            logger.debug(f"Skipping SNS publish for alert {alert.id} (severity {alert.severity} < {self.cfg.SNS_MIN_SEVERITY})")
            alert.publish_status["sns"] = "skipped"
            return

        await asyncio.to_thread(self._sync_publish, alert)
        logger.info(f"Published alert {alert.id} to SNS Topic {self.cfg.SNS_TOPIC_ARN}")

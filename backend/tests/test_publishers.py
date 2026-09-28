import pytest
import asyncio
from datetime import datetime, timezone

boto3 = pytest.importorskip("boto3")
moto = pytest.importorskip("moto")
from moto import mock_aws

from app.models import Alert
from app.config import Settings
from app.publishers.cloudwatch import CloudWatchPublisher
from app.publishers.sns import SnsPublisher
from app.publishers.dispatcher import PublisherDispatcher

@pytest.fixture
def mock_aws_env(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "ap-south-1")

@pytest.mark.asyncio
async def test_cloudwatch_publisher(mock_aws_env):
    with mock_aws():
        cfg = Settings(
            AWS_REGION="ap-south-1",
            CW_LOG_GROUP="/hackathon/test-alerts",
            CW_LOG_STREAM="alerts"
        )
        cw_pub = CloudWatchPublisher(config=cfg)
        alert = Alert(
            id="cw123",
            key="error_rate:global",
            title="Spike 40%",
            error_rate=0.40,
            baseline_mean=0.02,
            baseline_std=0.01,
            z_score=15.0,
            window_seconds=60,
            window_total=100,
            window_errors=40,
            opened_at="2026-09-28T10:00:00Z",
            updated_at="2026-09-28T10:00:00Z"
        )
        await cw_pub.publish(alert)

        # Verify CloudWatch has log event
        client = boto3.client("logs", region_name="ap-south-1")
        resp = client.get_log_events(
            logGroupName="/hackathon/test-alerts",
            logStreamName="alerts"
        )
        assert len(resp.get("events", [])) == 1

@pytest.mark.asyncio
async def test_sns_publisher(mock_aws_env):
    with mock_aws():
        sns = boto3.client("sns", region_name="ap-south-1")
        topic = sns.create_topic(Name="log-anomaly-alerts")
        topic_arn = topic["TopicArn"]

        cfg = Settings(
            AWS_REGION="ap-south-1",
            SNS_TOPIC_ARN=topic_arn,
            SNS_MIN_SEVERITY="MEDIUM"
        )
        sns_pub = SnsPublisher(config=cfg)
        alert = Alert(
            id="sns123",
            key="error_rate:global",
            severity="HIGH",
            title="Critical Spike",
            error_rate=0.50,
            baseline_mean=0.02,
            baseline_std=0.01,
            z_score=20.0,
            window_seconds=60,
            window_total=100,
            window_errors=50,
            opened_at="2026-09-28T10:00:00Z",
            updated_at="2026-09-28T10:00:00Z"
        )
        await sns_pub.publish(alert)

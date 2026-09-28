#!/usr/bin/env bash
set -euo pipefail

REGION=${AWS_REGION:-ap-south-1}
LG=${CW_LOG_GROUP:-/hackathon/log-anomaly-detector}
LS=${CW_LOG_STREAM:-alerts}
TOPIC_NAME="log-anomaly-alerts"

echo "=== AWS Resource Setup for Log Anomaly Detector ==="
echo "Region: $REGION"
echo "CloudWatch Log Group: $LG"
echo "CloudWatch Log Stream: $LS"

# 1. Create CloudWatch Log Group & Retention
echo "[1/3] Creating CloudWatch Log Group..."
aws logs create-log-group --log-group-name "$LG" --region "$REGION" || true
aws logs put-retention-policy --log-group-name "$LG" --retention-in-days 7 --region "$REGION"

# 2. Create CloudWatch Log Stream
echo "[2/3] Creating CloudWatch Log Stream..."
aws logs create-log-stream --log-group-name "$LG" --log-stream-name "$LS" --region "$REGION" || true

# 3. Create SNS Topic & Subscription
echo "[3/3] Creating SNS Topic..."
ARN=$(aws sns create-topic --name "$TOPIC_NAME" --region "$REGION" --query TopicArn --output text)
echo "SNS Topic ARN: $ARN"

if [ -n "${ALERT_EMAIL:-}" ]; then
  echo "Subscribing email $ALERT_EMAIL to topic..."
  aws sns subscribe --topic-arn "$ARN" --protocol email --notification-endpoint "$ALERT_EMAIL" --region "$REGION"
  echo "[!] Confirmation email sent to $ALERT_EMAIL. Please confirm before running demo."
fi

echo ""
echo "=== Setup Complete! Add these to your .env file ==="
echo "AWS_ENABLED=true"
echo "PUBLISH_MODE=aws"
echo "AWS_REGION=$REGION"
echo "CW_LOG_GROUP=$LG"
echo "CW_LOG_STREAM=$LS"
echo "SNS_TOPIC_ARN=$ARN"

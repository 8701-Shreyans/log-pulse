import logging
import json
from app.models import Alert
from app.publishers.base import Publisher

logger = logging.getLogger("publisher.console")

class ConsolePublisher:
    """
    Dry-run publisher that formats and logs alerts to stdout.
    Used by default when PUBLISH_MODE=dry_run or no AWS credentials are configured.
    """
    name = "console"

    async def publish(self, alert: Alert) -> None:
        payload = alert.model_dump(mode="json")
        logger.info(
            f"\n{'='*30} [ALERT: {alert.severity} ({alert.event})] {'='*30}\n"
            f"Title: {alert.title}\n"
            f"Z-Score: {alert.z_score:.2f} | Error Rate: {alert.error_rate*100:.1f}%\n"
            f"Top Errors: {[e.message for e in alert.top_errors]}\n"
            f"{json.dumps(payload, indent=2)}\n"
            f"{'='*80}"
        )

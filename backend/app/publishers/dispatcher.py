import asyncio
import logging
from typing import List, Optional

from app.models import Alert
from app.publishers.base import Publisher
from app.publishers.console import ConsolePublisher
from app.publishers.cloudwatch import CloudWatchPublisher
from app.publishers.sns import SnsPublisher
from app.config import Settings

logger = logging.getLogger("publisher.dispatcher")

class PublisherDispatcher:
    """
    Asynchronous queue dispatcher that routes alerts to publishers with retry and backoff.
    Never blocks the main detection loop.
    """
    def __init__(self, config: Settings):
        self.cfg = config
        self.queue: asyncio.Queue[Alert] = asyncio.Queue(maxsize=1000)
        self.publishers: List[Publisher] = []
        self._worker_task: Optional[asyncio.Task] = None
        self.is_running = False

        self.publish_successes = 0
        self.publish_failures = 0

        # Initialize publishers based on config
        if config.PUBLISH_MODE == "aws":
            self.publishers.append(CloudWatchPublisher(config))
            self.publishers.append(SnsPublisher(config))
            logger.info("Configured AWS CloudWatch and SNS publishers.")
        else:
            self.publishers.append(ConsolePublisher())
            logger.info("Configured Dry-Run Console publisher.")

    async def start(self):
        if not self.is_running:
            self.is_running = True
            self._worker_task = asyncio.create_task(self._worker_loop())
            logger.info("PublisherDispatcher worker started.")

    async def stop(self):
        self.is_running = False
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            logger.info("PublisherDispatcher worker stopped.")

    def enqueue(self, alert: Alert):
        """Enqueues an alert for asynchronous delivery."""
        try:
            self.queue.put_nowait(alert)
        except asyncio.QueueFull:
            logger.warning("Publisher queue full. Dropping oldest alert to prevent unbounded memory.")
            try:
                self.queue.get_nowait()
                self.queue.put_nowait(alert)
            except Exception:
                pass

    async def _worker_loop(self):
        while self.is_running:
            try:
                alert = await self.queue.get()
                await self._dispatch_alert(alert)
                self.queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in publisher dispatcher loop: {e}", exc_info=True)
                await asyncio.sleep(1)

    async def _dispatch_alert(self, alert: Alert):
        for pub in self.publishers:
            pub_name = getattr(pub, "name", "unknown")
            success = False
            backoff = 1.0

            for attempt in range(1, self.cfg.AWS_MAX_RETRIES + 1):
                try:
                    await pub.publish(alert)
                    alert.publish_status[pub_name] = "ok"
                    self.publish_successes += 1
                    success = True
                    break
                except Exception as e:
                    logger.warning(f"Publisher [{pub_name}] attempt {attempt}/{self.cfg.AWS_MAX_RETRIES} failed for alert {alert.id}: {e}")
                    if attempt < self.cfg.AWS_MAX_RETRIES:
                        await asyncio.sleep(backoff)
                        backoff *= 2.0

            if not success:
                logger.error(f"Publisher [{pub_name}] permanently failed for alert {alert.id}")
                alert.publish_status[pub_name] = "failed"
                self.publish_failures += 1

import asyncio
import logging
import time
from typing import Optional

from app.config import Settings
from app.models import MetricPoint, LogEvent, Severity
from app.parser import LogParser
from app.tailer import FileTailer
from app.window import SlidingWindow
from app.baseline import Baseline
from app.detector import AnomalyDetector
from app.alerts import AlertManager
from app.bus import EventBus
from app.publishers.dispatcher import PublisherDispatcher

logger = logging.getLogger("pipeline")

class Pipeline:
    """
    Central processing engine orchestrating log tailing, parsing,
    sliding window computation, baseline learning, anomaly detection, and alert dispatching.
    """
    def __init__(self, config: Settings, bus: EventBus):
        self.cfg = config
        self.bus = bus

        self.parser = LogParser(mode=config.LOG_FORMAT)
        self.tailer = FileTailer(
            filepath=config.LOG_FILE_PATH,
            poll_interval_sec=config.TAIL_POLL_INTERVAL_SEC,
            from_start=config.TAIL_FROM_START
        )
        self.window = SlidingWindow(window_seconds=config.WINDOW_SECONDS)
        self.baseline = Baseline(
            warmup_samples=config.BASELINE_WARMUP_SAMPLES,
            alpha=config.BASELINE_ALPHA,
            min_std=config.BASELINE_MIN_STD,
            z_threshold=config.Z_LOW,
            persist_path=config.BASELINE_PERSIST_PATH
        )
        self.detector = AnomalyDetector(config=config)
        self.alert_manager = AlertManager(config=config)
        self.dispatcher = PublisherDispatcher(config=config)

        self.is_running = False
        self._tailer_task: Optional[asyncio.Task] = None
        self._eval_task: Optional[asyncio.Task] = None
        self._last_log_stream_time: float = 0
        self.total_lines_processed = 0

    async def start(self):
        if not self.is_running:
            self.is_running = True
            await self.dispatcher.start()
            await self.tailer.start()
            self._tailer_task = asyncio.create_task(self._tailer_consumer_loop())
            self._eval_task = asyncio.create_task(self._evaluator_loop())
            logger.info("Pipeline processing started.")

    async def stop(self):
        self.is_running = False
        if self._tailer_task and not self._tailer_task.done():
            self._tailer_task.cancel()
        if self._eval_task and not self._eval_task.done():
            self._eval_task.cancel()
        await self.tailer.stop()
        await self.dispatcher.stop()
        self.baseline.save()
        logger.info("Pipeline stopped.")

    async def _tailer_consumer_loop(self):
        """Reads parsed lines from the FileTailer and pushes to the sliding window."""
        while self.is_running:
            try:
                line = await self.tailer.get_line()
                self.total_lines_processed += 1
                event: Optional[LogEvent] = self.parser.parse_line(line)

                if event:
                    # Use processing time for window bucketing (robust against log timestamp clock skew)
                    self.window.add(
                        level=event.level.value,
                        service=event.service,
                        message=event.message,
                        now=time.time()
                    )

                    # Stream sampled log event to WebSocket clients (rate limited, error prioritized)
                    now_t = time.time()
                    should_stream = event.level.is_error() or (now_t - self._last_log_stream_time >= 0.1)
                    if should_stream:
                        self._last_log_stream_time = now_t
                        self.bus.publish("log", event)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in tailer consumer loop: {e}", exc_info=True)
                await asyncio.sleep(0.1)

    async def _evaluator_loop(self):
        """Evaluates metrics, baseline, and detector periodically."""
        while self.is_running:
            try:
                await asyncio.sleep(self.cfg.EVAL_INTERVAL_SEC)
                now_f = time.time()
                snap = self.window.snapshot(now=now_f)
                rate = snap["error_rate"]
                total = snap["total"]
                errors = snap["errors"]

                reliable = total >= self.cfg.MIN_EVENTS_IN_WINDOW

                # Warm-up phase
                if reliable and not self.baseline.ready:
                    self.baseline.warmup_add(rate)

                # Detection evaluation
                result = None
                if reliable and self.baseline.ready:
                    result = self.detector.evaluate(snap, self.baseline, now=now_f)

                # Freeze EWMA during a breach or open alert so the outage is not learned as "normal".
                breaching = bool(result and result.breaching)
                has_active = self.alert_manager.has_open_alert()
                freeze = self.cfg.FREEZE_BASELINE_DURING_ALERT and (breaching or has_active)
                if reliable and self.baseline.ready and not freeze:
                    self.baseline.update(rate)
                    # Persist periodically so a restart skips warm-up
                    if self.baseline.samples % max(1, int(60 / max(0.1, self.cfg.EVAL_INTERVAL_SEC))) == 0:
                        self.baseline.save()

                # Build MetricPoint
                metric = MetricPoint(
                    ts=result.ts if result else time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now_f)),
                    error_rate=rate,
                    total=total,
                    errors=errors,
                    events_per_sec=snap["events_per_sec"],
                    baseline_mean=round(self.baseline.mean, 4),
                    baseline_std=round(self.baseline.std, 4),
                    upper_band=round(self.baseline.upper_band, 4),
                    z=result.z if result else 0.0,
                    severity=result.severity.label if result else "NONE",
                    is_breach=breaching
                )

                # Publish metric and baseline state
                self.bus.publish("metric", metric)
                self.bus.publish("baseline", self.baseline.state())

                # Process alerts
                alert_events = self.alert_manager.process(result, now=now_f)
                for alert in alert_events:
                    logger.info(f"Emitted Alert Event: [{alert.event}] {alert.title} (Severity: {alert.severity})")
                    self.bus.publish("alert", alert)
                    self.dispatcher.enqueue(alert)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in evaluator loop: {e}", exc_info=True)
                await asyncio.sleep(1.0)

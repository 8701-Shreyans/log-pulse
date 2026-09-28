import asyncio
import logging
from collections import deque
from typing import List, Dict, Any, Tuple, Set, Optional
from datetime import datetime, timezone

from app.models import Envelope, MetricPoint, Alert, LogEvent

logger = logging.getLogger("bus")

class EventBus:
    """
    In-memory pub/sub event bus with monotonic sequence numbering and ring buffer.
    Powers real-time WebSocket streaming and REST polling fallback.
    """
    def __init__(self, ring_buffer_size: int = 2000):
        self.ring_buffer_size = ring_buffer_size
        self._seq: int = 0
        self._buffer: deque[Envelope] = deque(maxlen=ring_buffer_size)
        self._subscribers: Set[asyncio.Queue[Envelope]] = set()
        self._lock = asyncio.Lock()

        # Dedicated metric and log buffers for fast API hydration
        self.metrics_buffer: deque[MetricPoint] = deque(maxlen=1000)
        self.logs_buffer: deque[LogEvent] = deque(maxlen=200)

    @property
    def latest_seq(self) -> int:
        return self._seq

    async def subscribe(self, maxsize: int = 200) -> asyncio.Queue[Envelope]:
        q: asyncio.Queue[Envelope] = asyncio.Queue(maxsize=maxsize)
        async with self._lock:
            self._subscribers.add(q)
        return q

    async def unsubscribe(self, q: asyncio.Queue[Envelope]):
        async with self._lock:
            self._subscribers.discard(q)

    def publish(self, event_type: str, data: Any) -> Envelope:
        """
        Publishes an event to the ring buffer and enqueues to all subscribers.
        """
        self._seq += 1
        seq = self._seq
        now_iso = datetime.now(timezone.utc).isoformat()

        # Build envelope
        # Convert pydantic models or dicts
        data_payload = data.model_dump(mode="json") if hasattr(data, "model_dump") else data
        envelope = Envelope(
            type=event_type,
            seq=seq,
            ts=now_iso,
            data=data_payload
        )

        self._buffer.append(envelope)

        # Cache specialized data
        if event_type == "metric" and isinstance(data, MetricPoint):
            self.metrics_buffer.append(data)
        elif event_type == "log" and isinstance(data, LogEvent):
            self.logs_buffer.append(data)

        # Fan-out with backpressure: drop oldest log/metric first; never drop alerts.
        for q in list(self._subscribers):
            try:
                q.put_nowait(envelope)
            except asyncio.QueueFull:
                self._enqueue_with_drop(q, envelope)

        return envelope

    def _enqueue_with_drop(self, q: asyncio.Queue, envelope: Envelope) -> None:
        """Drop oldest non-alert items until the new envelope fits. Alerts are preserved."""
        parked_alerts: List[Envelope] = []
        try:
            while True:
                try:
                    old_item = q.get_nowait()
                except asyncio.QueueEmpty:
                    break
                if old_item.type == "alert":
                    parked_alerts.append(old_item)
                else:
                    # Dropped a log/metric/heartbeat — room should exist after re-queue
                    break
            for alert_env in parked_alerts:
                try:
                    q.put_nowait(alert_env)
                except asyncio.QueueFull:
                    break
            try:
                q.put_nowait(envelope)
            except asyncio.QueueFull:
                if envelope.type == "alert":
                    logger.warning("Subscriber queue full of alerts; dropping oldest alert")
                    try:
                        q.get_nowait()
                        q.put_nowait(envelope)
                    except Exception:
                        pass
        except Exception:
            pass

    def since(self, seq: int, limit: int = 500) -> Tuple[List[Envelope], int]:
        """
        Returns all envelopes with seq > given seq, up to limit, and the latest seq.
        """
        items = [env for env in self._buffer if env.seq > seq]
        return items[:limit], self._seq

    def get_recent_metrics(self) -> List[dict]:
        return [m.model_dump(mode="json") for m in self.metrics_buffer]

    def get_recent_logs(self, limit: int = 100) -> List[dict]:
        logs = list(self.logs_buffer)[-limit:]
        return [l.model_dump(mode="json") for l in logs]

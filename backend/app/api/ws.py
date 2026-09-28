import asyncio
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.bus import EventBus
from app.pipeline import Pipeline
from app.config import settings

logger = logging.getLogger("ws")
ws_router = APIRouter(tags=["websocket"])

_pipeline: Pipeline = None
_bus: EventBus = None

def init_ws(pipeline: Pipeline, bus: EventBus):
    global _pipeline, _bus
    _pipeline = pipeline
    _bus = bus

@ws_router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    client_queue = await _bus.subscribe(maxsize=200)
    logger.info("WebSocket client connected.")

    # 1. Send initial snapshot on connect
    try:
        snapshot_data = {
            "metrics": _bus.get_recent_metrics(),
            "active_alerts": [a.model_dump(mode="json") for a in _pipeline.alert_manager.get_active()],
            "baseline": _pipeline.baseline.state().model_dump(mode="json"),
            "config": {
                "window_seconds": settings.WINDOW_SECONDS,
                "eval_interval_sec": settings.EVAL_INTERVAL_SEC,
                "z_low": settings.Z_LOW,
                "z_medium": settings.Z_MEDIUM,
                "z_high": settings.Z_HIGH,
                "z_critical": settings.Z_CRITICAL,
                "min_abs_rate": settings.MIN_ABS_RATE,
                "abs_rate_critical": settings.ABS_RATE_CRITICAL,
                "sim_enabled": settings.ENABLE_SIM
            },
            "latest_seq": _bus.latest_seq
        }
        await websocket.send_json({
            "type": "snapshot",
            "seq": _bus.latest_seq,
            "data": snapshot_data
        })
    except Exception as e:
        logger.warning(f"Failed to send initial snapshot: {e}")
        await _bus.unsubscribe(client_queue)
        return

    # Tasks for streaming to client and receiving client pings
    async def sender_task():
        last_heartbeat = asyncio.get_event_loop().time()
        while True:
            try:
                # Wait for next envelope or 15s heartbeat timeout
                try:
                    envelope = await asyncio.wait_for(client_queue.get(), timeout=15.0)
                    await websocket.send_text(envelope.model_dump_json())
                    client_queue.task_done()
                except asyncio.TimeoutError:
                    # Send periodic heartbeat
                    await websocket.send_json({
                        "type": "heartbeat",
                        "seq": _bus.latest_seq,
                        "data": {"time": asyncio.get_event_loop().time()}
                    })
            except (WebSocketDisconnect, asyncio.CancelledError):
                break
            except Exception as ex:
                logger.debug(f"Error sending envelope to WebSocket client: {ex}")
                break

    async def receiver_task():
        while True:
            try:
                data_text = await websocket.receive_text()
                if not data_text:
                    continue
                try:
                    msg = json.loads(data_text)
                    if msg.get("type") == "ping":
                        await websocket.send_json({"type": "pong", "seq": _bus.latest_seq})
                except Exception:
                    if data_text.strip() == "ping":
                        await websocket.send_text("pong")
            except (WebSocketDisconnect, asyncio.CancelledError):
                break
            except Exception as ex:
                logger.debug(f"Error receiving from WebSocket: {ex}")
                break

    sender = asyncio.create_task(sender_task())
    receiver = asyncio.create_task(receiver_task())

    done, pending = await asyncio.wait(
        [sender, receiver],
        return_when=asyncio.FIRST_COMPLETED
    )

    for task in pending:
        task.cancel()

    await _bus.unsubscribe(client_queue)
    logger.info("WebSocket client disconnected.")

import json
import os
import time
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Body

from app.config import settings
from app.models import Alert, AppConfig
from app.bus import EventBus
from app.pipeline import Pipeline

router = APIRouter(prefix="/api", tags=["api"])

# Global references injected on startup
_pipeline: Optional[Pipeline] = None
_bus: Optional[EventBus] = None
_start_time: float = time.time()

def init_routes(pipeline: Pipeline, bus: EventBus):
    global _pipeline, _bus, _start_time
    _pipeline = pipeline
    _bus = bus
    _start_time = time.time()

@router.get("/health")
async def get_health():
    uptime = time.time() - _start_time
    return {
        "status": "healthy",
        "uptime_seconds": round(uptime, 1),
        "tailing": _pipeline.tailer.is_running if _pipeline else False,
        "baseline_ready": _pipeline.baseline.ready if _pipeline else False,
        "total_lines_read": _pipeline.tailer.total_lines_read if _pipeline else 0,
        "parse_failures": _pipeline.parser.parse_failures if _pipeline else 0,
        "publish_mode": settings.PUBLISH_MODE,
        "publish_failures": _pipeline.dispatcher.publish_failures if _pipeline else 0,
        "active_ws_subscribers": len(_bus._subscribers) if _bus else 0,
        "ws_clients": len(_bus._subscribers) if _bus else 0,
    }

@router.get("/config", response_model=AppConfig)
async def get_config():
    return AppConfig(
        window_seconds=settings.WINDOW_SECONDS,
        eval_interval_sec=settings.EVAL_INTERVAL_SEC,
        min_events_in_window=settings.MIN_EVENTS_IN_WINDOW,
        z_low=settings.Z_LOW,
        z_medium=settings.Z_MEDIUM,
        z_high=settings.Z_HIGH,
        z_critical=settings.Z_CRITICAL,
        abs_rate_critical=settings.ABS_RATE_CRITICAL,
        min_abs_rate=settings.MIN_ABS_RATE,
        publish_mode=settings.PUBLISH_MODE,
        sim_enabled=settings.ENABLE_SIM
    )

@router.get("/metrics")
async def get_metrics(minutes: int = Query(30, ge=1, le=120)):
    if not _bus:
        return []
    return _bus.get_recent_metrics()

@router.get("/alerts", response_model=List[Alert])
async def get_alerts(
    status: Optional[str] = Query(None, description="Filter by status (OPEN, RESOLVED)"),
    limit: int = Query(50, ge=1, le=500)
):
    if not _pipeline:
        return []
    return _pipeline.alert_manager.get_history(status=status, limit=limit)

@router.get("/alerts/active", response_model=List[Alert])
async def get_active_alerts():
    if not _pipeline:
        return []
    return _pipeline.alert_manager.get_active()

@router.post("/alerts/{alert_id}/ack")
async def acknowledge_alert(
    alert_id: str,
    payload: Dict[str, Any] = Body(default_factory=dict)
):
    by = payload.get("by", "operator")
    if not _pipeline:
        raise HTTPException(status_code=500, detail="Pipeline not initialized")

    success = _pipeline.alert_manager.acknowledge(alert_id, by=by)
    if not success:
        raise HTTPException(status_code=404, detail="Alert not found")

    # Broadcast ack
    _bus.publish("alert", {
        "event": "ACKNOWLEDGED",
        "alert_id": alert_id,
        "acknowledged": True,
        "acknowledged_by": by
    })
    return {"status": "success", "alert_id": alert_id, "acknowledged": True, "by": by}

@router.get("/poll")
async def poll_feed(
    since_seq: int = Query(0, ge=0, description="Last received monotonic sequence number"),
    limit: int = Query(500, ge=1, le=1000)
):
    """
    Polling fallback endpoint for clients when WebSocket is disconnected.
    Returns all envelopes with seq > since_seq.
    """
    if not _bus:
        return {"items": [], "latest_seq": 0}
    items, latest_seq = _bus.since(since_seq, limit=limit)
    return {
        "items": [env.model_dump(mode="json") for env in items],
        "latest_seq": latest_seq
    }

@router.get("/logs/recent")
async def get_recent_logs(limit: int = Query(100, ge=1, le=200)):
    if not _bus:
        return []
    return _bus.get_recent_logs(limit=limit)

@router.post("/sim/spike")
async def trigger_sim_spike(
    duration_sec: int = Body(45, embed=True),
    error_ratio: float = Body(0.60, embed=True),
    scenario: str = Body("spike", embed=True)
):
    """
    Triggers simulated error anomaly via shared control file.
    """
    if not settings.ENABLE_SIM:
        raise HTTPException(status_code=403, detail="Simulation controls disabled by config")

    control_path = settings.SIM_CONTROL_PATH
    os.makedirs(os.path.dirname(os.path.abspath(control_path)), exist_ok=True)

    data = {
        "active": True,
        "scenario": scenario,
        "error_ratio": error_ratio,
        "expires_at": time.time() + duration_sec,
        "duration_sec": duration_sec
    }
    with open(control_path, "w", encoding="utf-8") as f:
        json.dump(data, f)

    return {"status": "success", "scenario": scenario, "error_ratio": error_ratio, "duration_sec": duration_sec}

@router.post("/sim/recover")
async def trigger_sim_recover():
    """
    Clears simulation error anomaly and restores normal baseline traffic.
    """
    if not settings.ENABLE_SIM:
        raise HTTPException(status_code=403, detail="Simulation controls disabled by config")

    control_path = settings.SIM_CONTROL_PATH
    if os.path.exists(control_path):
        try:
            with open(control_path, "w", encoding="utf-8") as f:
                json.dump({"active": False, "scenario": "normal", "error_ratio": 0.02}, f)
        except Exception:
            pass
    return {"status": "success", "message": "Simulation anomaly recovered to normal"}

@router.post("/reset")
async def reset_engine():
    """Resets sliding window, baseline, and active alerts."""
    if _pipeline:
        _pipeline.window.clear()
        _pipeline.baseline.reset()
        _pipeline.alert_manager.clear()
    return {"status": "success", "message": "Engine reset successfully"}

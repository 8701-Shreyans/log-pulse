import os
import asyncio
import tempfile
import pytest
from httpx import AsyncClient, ASGITransport

from app.config import Settings
from app.bus import EventBus
from app.pipeline import Pipeline
from app.api.routes import router, init_routes
from app.api.ws import ws_router, init_ws
from fastapi import FastAPI

@pytest.mark.asyncio
async def test_e2e_pipeline_and_alerting():
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = os.path.join(tmpdir, "test_app.log")
        with open(log_file, "w", encoding="utf-8") as f:
            f.write("")

        cfg = Settings(
            LOG_FILE_PATH=log_file,
            TAIL_FROM_START=True,
            TAIL_POLL_INTERVAL_SEC=0.02,
            EVAL_INTERVAL_SEC=0.05,
            BASELINE_WARMUP_SAMPLES=3,
            CONFIRM_TICKS=1,
            RESOLVE_TICKS=1,
            ALERT_COOLDOWN_SEC=0.5,
            MIN_EVENTS_IN_WINDOW=10,
            MIN_ABS_RATE=0.05,
            Z_LOW=3.0,
            PUBLISH_MODE="dry_run"
        )

        bus = EventBus(ring_buffer_size=500)
        pipeline = Pipeline(config=cfg, bus=bus)

        init_routes(pipeline=pipeline, bus=bus)
        init_ws(pipeline=pipeline, bus=bus)

        app = FastAPI()
        app.include_router(router)
        app.include_router(ws_router)

        try:
            await pipeline.start()

            # Phase 1: Write normal logs to warm up baseline
            with open(log_file, "a", encoding="utf-8") as f:
                for i in range(30):
                    f.write(f'2026-09-28 10:00:{i:02d} INFO service=auth msg="login ok"\n')
                f.flush()

            # Wait for baseline to warm up
            for _ in range(30):
                if pipeline.baseline.ready:
                    break
                await asyncio.sleep(0.05)

            assert pipeline.baseline.ready is True
            assert pipeline.alert_manager.has_open_alert() is False

            # Phase 2: Inject error spike
            with open(log_file, "a", encoding="utf-8") as f:
                for i in range(25):
                    f.write(f'2026-09-28 10:01:{i:02d} ERROR service=payments msg="DB timeout"\n')
                f.flush()

            # Wait for alert to open
            for _ in range(30):
                if pipeline.alert_manager.has_open_alert():
                    break
                await asyncio.sleep(0.05)

            assert pipeline.alert_manager.has_open_alert() is True
            active = pipeline.alert_manager.get_active()
            assert len(active) == 1

            # Phase 3: REST API verification
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get("/api/health")
                assert resp.status_code == 200
                assert resp.json()["status"] == "healthy"

                resp_alerts = await client.get("/api/alerts")
                assert resp_alerts.status_code == 200
                alerts_data = resp_alerts.json()
                assert len(alerts_data) >= 1

                # Test acknowledge
                alert_id = alerts_data[0]["id"]
                ack_resp = await client.post(f"/api/alerts/{alert_id}/ack", json={"by": "oncall-sre"})
                assert ack_resp.status_code == 200
                assert ack_resp.json()["acknowledged"] is True

                # Test poll fallback
                poll_resp = await client.get("/api/poll?since_seq=0")
                assert poll_resp.status_code == 200
                poll_data = poll_resp.json()
                assert len(poll_data["items"]) > 0

        finally:
            await pipeline.stop()
            # Brief yield to let file handle release on Windows
            await asyncio.sleep(0.1)

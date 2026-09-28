# ⚡ Real-Time Log Anomaly Detector with Alert Feed

A production-grade, high-throughput log anomaly detection system and live React operations dashboard with AWS CloudWatch Logs and SNS integration.

![Python](https://img.shields.io/badge/Python-3.11%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-green)
![React](https://img.shields.io/badge/React-18-cyan)
![Vite](https://img.shields.io/badge/Vite-5-purple)
![Tailwind](https://img.shields.io/badge/Tailwind-3-38bdf8)
![Recharts](https://img.shields.io/badge/Recharts-2-indigo)

---

## ⚡ 5-Line Quick Start

**Windows (PowerShell) — three terminals from the repo root:**

```powershell
pip install -r backend/requirements.txt
cd frontend; npm install; cd ..
pytest

# Terminal 1 — API
$env:PYTHONPATH="backend"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 — log generator
python -m backend.simulator.generate_logs --file ./data/app.log --rps 30

# Terminal 3 — dashboard
cd frontend; npm run dev
```

Or run `.\start.ps1` to launch all three processes.

Open **`http://localhost:5173`**. Wait until **Learned Baseline** shows *EWMA Tracking Active*, then click **Inject Spike**.

---

## 🏛️ Architecture Overview

```
┌────────────────┐   appends lines    ┌───────────────────────────────────────────────────────────┐
│ Log Generator  │ ─────────────────► │                     data/app.log                          │
│ (simulator.py) │                    └───────────────┬───────────────────────────────────────────┘
└────────────────┘                                    │ tail (offset polling, rotation-safe)
        ▲                                             ▼
        │ POST /api/sim/*        ┌──────────────────────────────────────────────┐
        │ (trigger anomaly)      │               BACKEND (FastAPI, asyncio)     │
        │                        │                                              │
┌───────┴────────┐               │  Tailer ─► Parser ─► SlidingWindow           │
│ React Frontend │ ◄── WS /ws ───│                          │                   │
│  (Vite + TS)   │ ◄── REST ─────│                          ▼                   │
│  - Live chart  │               │            Baseline (EWMA mean/std)          │
│  - Alert feed  │               │                          │                   │
│  - Log tail    │               │                          ▼                   │
└────────────────┘               │           Detector (z-score + rules)         │
                                 │                          │                   │
                                 │                          ▼                   │
                                 │      AlertManager (dedupe, lifecycle,        │
                                 │      cooldown, escalation)                   │
                                 │         │                │                   │
                                 │         ▼                ▼                   │
                                 │  Event Bus ──► WS broadcaster / poll buffer  │
                                 │         │                                    │
                                 │         ▼                                    │
                                 │  Publisher Queue ─► CloudWatch Logs          │
                                 │  (async, retry)  └► SNS Topic ─► email/SMS   │
                                 └──────────────────────────────────────────────┘
```

---

## 🚀 Key System Features

| Requirement | Implementation | Description |
|---|---|---|
| **R1: Growing File Tailer** | `backend/app/tailer.py` | Async tailer surviving log rotation & file truncation; byte offset tracking, partial line buffering, non-blocking chunk reading. |
| **R2: Rolling Error Rate** | `backend/app/window.py` | 1-second bucketed ring buffer with $O(\text{window})$ memory and $O(1)$ updates. Aggregates error rate, errors/sec, and root-cause error signatures. |
| **R3: Adaptive Baseline** | `backend/app/baseline.py` | Warm-up gating ($N$ samples) + EWMA mean & variance updating. Freezes updates during anomalies to prevent baseline poisoning. Persisted to `data/baseline.json`. |
| **R4: Statistical Deviation** | `backend/app/detector.py` | Z-score anomaly detector ($z = \frac{\text{rate} - \mu}{\sigma}$) with 5% absolute rate noise floor (`MIN_ABS_RATE`) and sample density reliability guard. |
| **R5: Severity Levels** | `backend/app/detector.py` | LOW ($z \ge 3.0$), MEDIUM ($z \ge 4.5$), HIGH ($z \ge 6.5$), CRITICAL ($z \ge 9.0$ or rate $\ge 50\%$). |
| **R6: Real-time UI** | `frontend/src/` | React 18 + Vite + Tailwind dashboard with WebSocket streaming, auto-reconnect, and 2-second REST polling fallback. |
| **R7: Live Alert Feed** | `frontend/src/components/AlertFeed.tsx` | Slide-in alerts, color-coded badges, top error signatures, CloudWatch/SNS delivery indicators, and acknowledgement actions. |
| **R8: AWS Integration** | `backend/app/publishers/` | CloudWatch Logs structured logging + SNS notifications with exponential backoff retries (1s, 2s, 4s). Dry-run mode for local operation. |

---

## 🎬 3-Minute Demo Walkthrough Script

1. **(0:00 - Baseline State):**
   Open dashboard at `http://localhost:5173`. Point out the live telemetry chart with the cyan error rate line hovering inside the shaded purple $\pm 3\sigma$ baseline band (~2.0% normal error rate).
2. **(0:30 - Anomaly Injection):**
   Click the top-right button **`Inject Spike (60%)`** or choose **`Severe Spike`** from the dropdown menu.
3. **(0:45 - Alert Detection & Escalation):**
   Watch the chart climb sharply. Within 2 ticks, an alert card slides in:
   - Severity: **MEDIUM ➔ HIGH ➔ CRITICAL**
   - Z-score: **15.4σ**
   - Top Root Cause: `"DB connection timeout for tx_<NUM> ×142"`
   - Web Audio chime alerts the engineer.
4. **(1:15 - AWS Verification):**
   Switch to AWS CloudWatch Logs or check the SNS email notification matching the exact JSON payload.
5. **(1:45 - Auto-Resolution):**
   Click **`Recover`**. The generator restores normal 2% traffic. After 3 calm ticks, the alert auto-resolves with duration and peak severity recorded. The baseline was frozen during the spike and remains clean (~2.0%).
6. **(2:15 - Connection Resilience):**
   Stop the backend to observe the UI pill transition to **`RECONNECTING ➔ FALLBACK (Polling)`**. Restart the backend and watch it recover instantly without refreshing the page.

---

## 🛠️ Configuration Options (`.env`)

| Key | Default | Description |
|---|---|---|
| `LOG_FILE_PATH` | `./data/app.log` | Path to monitored log file |
| `WINDOW_SECONDS` | `60` | Sliding window duration in seconds |
| `EVAL_INTERVAL_SEC` | `2.0` | Metric evaluation frequency |
| `BASELINE_WARMUP_SAMPLES` | `24` | Samples needed before detection activates |
| `Z_LOW` / `Z_MEDIUM` / `Z_HIGH` / `Z_CRITICAL` | `3.0` / `4.5` / `6.5` / `9.0` | Z-score severity thresholds |
| `MIN_ABS_RATE` | `0.05` | Minimum absolute error rate (5%) before alerting |
| `CONFIRM_TICKS` | `2` | Consecutive breaching ticks to open alert |
| `RESOLVE_TICKS` | `3` | Consecutive calm ticks to resolve alert |
| `ALERT_COOLDOWN_SEC` | `60.0` | Minimum cooldown before re-alerting (flap guard) |
| `PUBLISH_MODE` | `dry_run` | `dry_run` (stdout) or `aws` (CloudWatch/SNS) |
| `CW_LOG_GROUP` / `CW_LOG_STREAM` | `/hackathon/...` | Target CloudWatch Log destination |
| `SNS_TOPIC_ARN` | `arn:aws:sns:...` | Target SNS Topic ARN |

---

## 🧪 Automated Test Suite

```bash
# Run all unit, moto mock, and end-to-end integration tests
pytest -v
```

```
============================= test session starts =============================
backend/tests/test_alerts.py::test_alert_lifecycle_and_confirm_ticks PASSED
backend/tests/test_alerts.py::test_alert_acknowledgement PASSED
backend/tests/test_baseline.py::test_baseline_warmup_gating PASSED
backend/tests/test_baseline.py::test_baseline_ewma_updates_and_std_floor PASSED
backend/tests/test_baseline.py::test_baseline_persistence PASSED
backend/tests/test_detector.py::test_detector_normal PASSED
backend/tests/test_detector.py::test_detector_absolute_rate_floor PASSED
backend/tests/test_detector.py::test_detector_severity_boundaries PASSED
backend/tests/test_e2e.py::test_e2e_pipeline_and_alerting PASSED
backend/tests/test_parser.py::test_parse_json_line PASSED
backend/tests/test_parser.py::test_parse_text_kv_line PASSED
backend/tests/test_parser.py::test_parse_text_standard_bracket_line PASSED
backend/tests/test_parser.py::test_level_normalization PASSED
backend/tests/test_parser.py::test_error_normalization_signature PASSED
backend/tests/test_parser.py::test_malformed_lines_handled_gracefully PASSED
backend/tests/test_publishers.py::test_cloudwatch_publisher PASSED
backend/tests/test_publishers.py::test_sns_publisher PASSED
backend/tests/test_window.py::test_window_bucketed_addition_and_snapshot PASSED
backend/tests/test_window.py::test_window_eviction_after_window_seconds PASSED
backend/tests/test_window.py::test_window_service_breakdown PASSED
============================= 20 passed in 5.23s ==============================
```

---

## 🐳 Docker Compose Deployment

Run the complete multi-container stack with one command:

```bash
docker compose up --build
```
- **Backend:** `http://localhost:8000`
- **Frontend Dashboard:** `http://localhost:5173`
- **Log Generator:** Active background container streaming synthetic traffic

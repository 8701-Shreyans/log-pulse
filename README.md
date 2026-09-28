# Real-Time Log Anomaly Detector

A real-time log monitoring and anomaly detection project with a live dashboard. The included simulator writes realistic application-style logs at a normal error rate of about 2%, and can inject spikes, gradual ramps, traffic floods, or outages to exercise the detector.

The backend tails a growing log file, parses and aggregates events, learns a baseline, detects unusual error rates, and streams metrics and alerts to the dashboard. Alerts can be printed locally or published to AWS CloudWatch Logs and SNS.

## Features

- **File tailing and parsing:** follows a log file as it grows, handles truncation and rotation, and parses supported text and JSON formats.
- **Rolling metrics:** tracks event and error counts, error rate, throughput, and common error signatures in a time-based window.
- **Adaptive baseline:** learns normal behavior during warm-up; combines EWMA tracking with robust median/MAD statistics and avoids updating during active anomalies.
- **Anomaly alerts:** applies sample-reliability and absolute-rate guards, severity thresholds, confirmation ticks, cooldowns, acknowledgement, and resolution behavior.
- **Live dashboard:** displays metrics, baseline, telemetry, alert history, and recent log events using WebSockets with polling fallback.
- **Scenario simulator:** produces application-style logs and supports normal, spike, ramp, flood, outage, and flapping scenarios.
- **Optional publishing:** defaults to local dry-run output; AWS mode can publish alerts to CloudWatch Logs and SNS.
- **Docker Compose:** runs the backend, simulator, and frontend together.

## Requirements

- Python 3.11 or later
- Node.js 20 or later and npm
- Git (for cloning)
- Docker Desktop, if using the container setup

## Run locally on Windows

### 1. Install dependencies

Open PowerShell in the repository root:

```powershell
python -m pip install -r backend/requirements.txt
Set-Location frontend
npm install
Set-Location ..
```

### 2. Start the backend

In a PowerShell terminal from the repository root:

```powershell
$env:PYTHONPATH = "backend"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The API is available at `http://localhost:8000`; interactive API documentation is at `http://localhost:8000/docs`.

### 3. Start the simulator

In a second PowerShell terminal from the repository root:

```powershell
python -m backend.simulator.generate_logs --file ./data/app.log --rps 30
```

The simulator appends logs to `data/app.log`. Normal traffic has a 2% error ratio by default. Keep this process running while using the dashboard.

### 4. Start the dashboard

In a third PowerShell terminal:

```powershell
Set-Location frontend
npm run dev
```

Open `http://localhost:5173`. Allow the baseline to finish its warm-up before testing an anomaly. Use the dashboard's **Inject spike**, **Recover**, and scenario menu controls to trigger and clear simulated conditions.

### Optional: Windows launcher

From the repository root, run:

```powershell
.\start.ps1
```

The launcher installs missing dependencies and opens the backend, simulator, and frontend in separate processes.

## Run with Docker Compose

From the repository root:

```powershell
docker compose up --build
```

Open the dashboard at `http://localhost:5173`. The API is at `http://localhost:8000`. Compose starts the simulator automatically and persists its log and baseline data under the local `data` directory.

Stop the stack with `Ctrl+C`, or from another terminal run:

```powershell
docker compose down
```

## Simulator scenarios

The dashboard provides controls for these running-simulator scenarios:

| Scenario | Behavior |
|---|---|
| Normal | Continuous log stream with approximately 2% errors |
| Spike | Raises the error ratio for a limited duration |
| Gradual ramp | Increases the error ratio over time |
| Traffic flood | Increases volume and error ratio |
| Total outage | Raises the error ratio to 95% for a limited duration |
| Recover | Clears the active scenario and returns to normal traffic |

The simulator also supports a repeating flapping scenario from the command line; it alternates between calm and elevated error periods.

The simulator can also be started with command-line options:

```powershell
python -m backend.simulator.generate_logs --help
```

It supports `--file`, `--rps`, `--base-error`, `--scenario`, `--at`, `--duration`, and `--error-ratio`. The backend and simulator must share the simulation control file for dashboard-triggered scenarios; the default is `data/sim_control.json`.

## Configuration

The backend reads settings from environment variables and an optional `.env` file in the working directory. Start from the checked-in template:

```powershell
Copy-Item .env.example .env
```

Common settings:

| Variable | Default | Purpose |
|---|---:|---|
| `LOG_FILE_PATH` | `./data/app.log` | Log file monitored by the backend |
| `LOG_FORMAT` | `auto` | Parser mode: `auto`, `text`, or `json` |
| `WINDOW_SECONDS` | `60` | Rolling metric window |
| `EVAL_INTERVAL_SEC` | `2.0` | Metric and detector evaluation interval |
| `MIN_EVENTS_IN_WINDOW` | `20` | Minimum sample count before evaluation is reliable |
| `BASELINE_WARMUP_SAMPLES` | `24` | Number of evaluations used to learn the baseline |
| `FREEZE_BASELINE_DURING_ALERT` | `true` | Prevents active anomalies from being learned as normal |
| `MIN_ABS_RATE` | `0.05` | Minimum error rate considered for an alert |
| `Z_LOW` / `Z_MEDIUM` / `Z_HIGH` / `Z_CRITICAL` | `3` / `4.5` / `6.5` / `9` | Deviation thresholds for alert severity |
| `CONFIRM_TICKS` / `RESOLVE_TICKS` | `2` / `3` | Consecutive evaluations to open or resolve an alert |
| `PUBLISH_MODE` | `dry_run` | `dry_run` or `aws` |
| `AWS_REGION` | `ap-south-1` | AWS region when AWS publishing is enabled |
| `CW_LOG_GROUP` / `CW_LOG_STREAM` | `/hackathon/log-anomaly-detector` / `alerts` | CloudWatch destination |
| `SNS_TOPIC_ARN` | unset | SNS topic for notifications |
| `ENABLE_SIM` | `true` | Enables simulation control endpoints |
| `SIM_CONTROL_PATH` | `./data/sim_control.json` | Shared simulator-control file |

For AWS mode, configure AWS credentials using your normal AWS credential provider (such as the AWS CLI profile or environment) and set `PUBLISH_MODE=aws`. Set the CloudWatch destination and `SNS_TOPIC_ARN` as needed. The included infrastructure templates are in `infra/`.

## API overview

The FastAPI application exposes these main endpoints:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/health` | Health and pipeline status |
| `GET` | `/api/config` | Active application configuration |
| `GET` | `/api/metrics` | Recent metrics |
| `GET` | `/api/alerts` | Alert history |
| `GET` | `/api/alerts/active` | Active alerts |
| `POST` | `/api/alerts/{alert_id}/ack` | Acknowledge an alert |
| `GET` | `/api/logs/recent` | Recent parsed log events |
| `GET` | `/api/poll` | Event polling fallback |
| `POST` | `/api/sim/spike` | Trigger a simulator scenario |
| `POST` | `/api/sim/recover` | Return simulator to normal traffic |
| `POST` | `/api/reset` | Reset the detector state |
| WebSocket | `/ws` | Live metrics, alerts, baseline, and log events |

## Run tests

From the repository root, install backend dependencies if you have not already, then run:

```powershell
pytest -q
```

The test suite covers parsing, tailing, the rolling window, baseline and detection, alert lifecycle, publishers, and end-to-end pipeline behavior.

To verify the frontend production build:

```powershell
Set-Location frontend
npm run build
```

## Project structure

```text
backend/
  app/                 FastAPI application, pipeline, detector, APIs, publishers
  simulator/           Application-log generator and scenario controls
  tests/               Backend unit and integration tests
data/
  baseline.json        Persisted baseline state
frontend/
  src/                 React dashboard and components
infra/                 AWS setup script and CloudFormation resources
docker-compose.yml      Local multi-container setup
start.ps1              Windows local launcher
```

## Safety and data notes

- The simulator is intended for development and demonstrations; generated logs are synthetic.
- The default publisher is `dry_run`. AWS publishing is optional and requires valid AWS permissions and configuration.
- Keep real credentials in environment variables or a local `.env` file. Do not commit secrets.
- `.env` and generated log files are excluded by `.gitignore`; `.env.example` contains non-secret defaults.

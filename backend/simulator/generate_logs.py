#!/usr/bin/env python3
"""
Real-time Log Simulator with Anomaly Injection Scenarios & UI Control Hook.
"""
import os
import sys
import time
import math
import random
import json
import argparse
from datetime import datetime, timezone
from typing import Dict, Any, Optional

# Ensure backend can be imported if needed
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

SERVICES = [
    ("payments", 0.30, 0.02),
    ("auth", 0.25, 0.01),
    ("orders", 0.20, 0.015),
    ("search", 0.15, 0.005),
    ("gateway", 0.10, 0.01),
]

NORMAL_TEMPLATES = [
    "HTTP GET /api/v1/{service}/status - 200 OK latency_ms={latency}",
    "HTTP POST /api/v1/{service}/process - 200 OK tx_id={tx_id} latency_ms={latency}",
    "Cache lookup for key {service}_token_{user_id} HIT latency_ms={latency}",
    "Successfully processed message for user_id={user_id} order_id={order_id}",
    "Database read replica query completed in {latency}ms",
    "Session validation token granted for user_id={user_id}",
]

WARN_TEMPLATES = [
    "High memory watermark warning on node worker_{node_id}: 78% utilized",
    "Slow query detected on table '{service}_records' took {slow_latency}ms",
    "Downstream circuit breaker half-open for {service}_partner_api",
    "Outbound HTTP retry attempt 1 to webhook endpoint",
]

ERROR_TEMPLATES = [
    "DatabaseConnectionTimeoutException: Unable to acquire connection from pool (timeout: 5000ms)",
    "HTTP POST /api/v1/payments/charge - 500 Internal Server Error: Gateway timeout",
    "NullPointerException at OrderProcessingEngine.validate(OrderProcessingEngine.java:142)",
    "RedisClusterUnavailableException: Failed to connect to redis-master-0.internal:6379",
    "DeadlockDetected: Transaction tx_{tx_id} aborted on table 'inventory_locks'",
    "DownstreamServiceTimeout: auth-service did not reply within 3000ms",
    "DiskWriteIOError: Failed to append audit transaction to disk partition /var/log/audit",
    "SecuritySignatureMismatch: HMAC validation failed for incoming payload tx_{tx_id}",
]

CRITICAL_TEMPLATES = [
    "FATAL_HEAP_EXHAUSTION: OutOfMemoryError in Java Virtual Machine. Emergency dump initiated.",
    "CASCADE_FAILURE_TRIGGERED: All 5 database connection pools exhausted. Service failing health checks.",
    "CORRUPTED_STORAGE_SEGMENT: Integrity checksum failure on database WAL block {tx_id}",
]

def generate_log_line(error_ratio: float = 0.02, service_override: str = None) -> str:
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    
    # Pick service
    if service_override:
        service = service_override
    else:
        rand_srv = random.random()
        cumulative = 0.0
        service = SERVICES[0][0]
        for srv, weight, _ in SERVICES:
            cumulative += weight
            if rand_srv <= cumulative:
                service = srv
                break

    latency = random.randint(5, 45)
    slow_latency = random.randint(250, 750)
    tx_id = random.randint(100000, 999999)
    user_id = random.randint(1000, 9999)
    order_id = random.randint(50000, 99999)
    node_id = random.randint(1, 8)

    rand_val = random.random()

    if rand_val < error_ratio:
        if random.random() < 0.15:
            level = "CRITICAL"
            msg = random.choice(CRITICAL_TEMPLATES).format(tx_id=tx_id)
        else:
            level = "ERROR"
            msg = random.choice(ERROR_TEMPLATES).format(tx_id=tx_id, service=service)
    elif rand_val < (error_ratio + 0.05):
        level = "WARNING"
        msg = random.choice(WARN_TEMPLATES).format(
            service=service, slow_latency=slow_latency, node_id=node_id
        )
    else:
        level = "INFO"
        msg = random.choice(NORMAL_TEMPLATES).format(
            service=service, latency=latency, tx_id=tx_id, user_id=user_id, order_id=order_id
        )

    return f'{now_str} {level} service={service} msg="{msg}" latency_ms={latency}\n'

def check_sim_control(control_path: str) -> Optional[Dict[str, Any]]:
    if not control_path or not os.path.exists(control_path):
        return None
    try:
        with open(control_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("active") and data.get("expires_at", 0) > time.time():
            return data
    except Exception:
        pass
    return None

def run_simulator(
    filepath: str,
    rps: int = 30,
    base_error: float = 0.02,
    scenario: str = "normal",
    at_sec: int = 0,
    duration_sec: int = 0,
    error_ratio: float = 0.50,
    control_path: str = "./data/sim_control.json"
):
    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    print(f"[*] Starting Log Simulator on {filepath}")
    print(f"[*] Base RPS: {rps} | Baseline Error Rate: {base_error*100:.1f}%")
    print(f"[*] Scenario: {scenario} | Polling UI controls at {control_path}")
    print("[*] Press Ctrl+C to terminate.\n")

    start_time = time.time()
    total_written = 0
    last_ui_status_print = 0

    with open(filepath, "a", encoding="utf-8", buffering=1) as f:
        try:
            while True:
                now_t = time.time()
                elapsed = now_t - start_time

                # 1. Check UI control override
                ui_control = check_sim_control(control_path)
                current_scenario = scenario
                effective_err_ratio = base_error
                effective_rps = rps

                if ui_control:
                    current_scenario = ui_control.get("scenario", "spike")
                    effective_err_ratio = float(ui_control.get("error_ratio", 0.60))
                    if current_scenario == "flood":
                        effective_rps = rps * 8
                    elif current_scenario == "outage":
                        effective_err_ratio = max(effective_err_ratio, 0.95)
                    elif current_scenario == "ramp":
                        expires = float(ui_control.get("expires_at", now_t))
                        duration = float(ui_control.get("duration_sec", 60))
                        remaining = max(0.0, expires - now_t)
                        progress = 1.0 - (remaining / max(1.0, duration))
                        progress = min(1.0, max(0.0, progress))
                        effective_err_ratio = base_error + progress * (effective_err_ratio - base_error)
                    if now_t - last_ui_status_print > 5:
                        last_ui_status_print = now_t
                        print(f"[{elapsed:.1f}s] [UI TRIGGER ACTIVE] Scenario={current_scenario}, Error Ratio={effective_err_ratio*100:.1f}%")
                else:
                    # CLI Scenario Evaluation
                    if scenario == "spike":
                        if at_sec <= elapsed < (at_sec + duration_sec):
                            effective_err_ratio = error_ratio
                    elif scenario == "ramp":
                        if at_sec <= elapsed < (at_sec + duration_sec):
                            progress = (elapsed - at_sec) / max(1, duration_sec)
                            effective_err_ratio = base_error + progress * (error_ratio - base_error)
                    elif scenario == "flood":
                        if at_sec <= elapsed < (at_sec + duration_sec):
                            effective_rps = rps * 8
                            effective_err_ratio = error_ratio
                    elif scenario == "outage":
                        if at_sec <= elapsed < (at_sec + duration_sec):
                            effective_err_ratio = 0.95
                    elif scenario == "flapping":
                        # Alternate 15s calm, 15s spike
                        cycle = elapsed % 30
                        if cycle > 15:
                            effective_err_ratio = error_ratio

                # Daily sine wave volume modulation
                sine_factor = 1.0 + 0.15 * math.sin(elapsed / 60.0)
                actual_batch_count = max(1, int(effective_rps * sine_factor))
                delay_per_line = 1.0 / actual_batch_count

                for _ in range(actual_batch_count):
                    line = generate_log_line(effective_err_ratio)
                    f.write(line)
                    total_written += 1
                    time.sleep(delay_per_line)

                f.flush()

        except KeyboardInterrupt:
            print(f"\n[!] Simulator stopped. Total lines generated: {total_written}")

def main():
    parser = argparse.ArgumentParser(description="Real-time log generator with anomaly injection")
    parser.add_argument("--file", "-f", default="./data/app.log", help="Path to target log file (default: ./data/app.log)")
    parser.add_argument("--rps", "-r", type=int, default=30, help="Lines per second (default: 30)")
    parser.add_argument("--base-error", "-b", type=float, default=0.02, help="Normal baseline error rate (default: 0.02)")
    parser.add_argument("--scenario", "-s", choices=["normal", "spike", "ramp", "flood", "outage", "flapping"], default="normal", help="Simulation scenario")
    parser.add_argument("--at", type=int, default=0, help="Start scenario after N seconds")
    parser.add_argument("--duration", "-d", type=int, default=45, help="Duration of scenario in seconds")
    parser.add_argument("--error-ratio", "-e", type=float, default=0.55, help="Peak error ratio during scenario")
    parser.add_argument("--control-file", "-c", default="./data/sim_control.json", help="Path to UI control JSON file")

    args = parser.parse_args()
    run_simulator(
        filepath=args.file,
        rps=args.rps,
        base_error=args.base_error,
        scenario=args.scenario,
        at_sec=args.at,
        duration_sec=args.duration,
        error_ratio=args.error_ratio,
        control_path=args.control_file
    )

if __name__ == "__main__":
    main()

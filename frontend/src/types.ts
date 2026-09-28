export type Severity = 'NONE' | 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export interface TopError {
  message: string;
  count: number;
  service: string;
}

export interface MetricPoint {
  ts: string;
  error_rate: number;
  total: number;
  errors: number;
  events_per_sec: number;
  baseline_mean: number;
  baseline_std: number;
  upper_band: number;
  z: number;
  severity: Severity;
  is_breach: boolean;
}

export interface BaselineState {
  mean: number;
  std: number;
  samples: number;
  ready: boolean;
  upper_band: number;
  warmup_target: number;
  warmup_progress: number;
}

export interface Alert {
  id: string;
  key: string;
  status: 'OPEN' | 'RESOLVED';
  event: 'OPENED' | 'ESCALATED' | 'RESOLVED' | 'ACKNOWLEDGED';
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  peak_severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  title: string;
  error_rate: number;
  baseline_mean: number;
  baseline_std: number;
  z_score: number;
  window_seconds: number;
  window_total: number;
  window_errors: number;
  top_errors: TopError[];
  opened_at: string;
  updated_at: string;
  resolved_at?: string | null;
  acknowledged: boolean;
  acknowledged_by?: string | null;
  publish_status: Record<string, string>;
}

export interface LogLine {
  ts: string;
  level: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR';
  service: string;
  message: string;
  raw: string;
}

export interface AppConfig {
  window_seconds: number;
  eval_interval_sec: number;
  min_events_in_window: number;
  z_low: number;
  z_medium: number;
  z_high: number;
  z_critical: number;
  abs_rate_critical: number;
  min_abs_rate: number;
  publish_mode: string;
  sim_enabled: boolean;
}

export interface Envelope {
  type: 'metric' | 'alert' | 'baseline' | 'log' | 'snapshot' | 'heartbeat';
  seq: number;
  ts: string;
  data: any;
}

export type ConnectionState = 'live' | 'reconnecting' | 'polling' | 'offline';

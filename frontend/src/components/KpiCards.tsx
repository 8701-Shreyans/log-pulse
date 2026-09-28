import React from 'react';
import { AlertTriangle, TrendingUp, Target, BarChart2, Radio } from 'lucide-react';
import { MetricPoint, BaselineState, Alert } from '../types';
import { formatPct, formatNumber } from '../lib/format';

interface KpiCardsProps {
  latestMetric: MetricPoint | null;
  baseline: BaselineState | null;
  activeAlerts: Alert[];
}

export const KpiCards: React.FC<KpiCardsProps> = ({
  latestMetric,
  baseline,
  activeAlerts,
}) => {
  const errorRate = latestMetric?.error_rate ?? 0;
  const isBreach = latestMetric?.is_breach ?? false;
  const zScore = latestMetric?.z ?? 0;
  const eventsPerSec = latestMetric?.events_per_sec ?? 0;
  const totalEvents = latestMetric?.total ?? 0;
  const errors = latestMetric?.errors ?? 0;

  // Error rate color
  const getRateColor = () => {
    if (errorRate >= 0.5) return 'value-danger';
    if (zScore >= 3.0) return 'value-warning';
    return '';
  };

  return (
    <div className="kpi-grid">
      <div className={`kpi-item ${isBreach ? 'kpi-alert' : ''}`}>
        <div className="kpi-label">
          <span>Error rate</span>
          <TrendingUp />
        </div>
        <div className={`kpi-value ${getRateColor()}`}>
          {formatPct(errorRate)}
        </div>
        <div className="kpi-sub">
          <strong>{formatNumber(errors)}</strong> errors / {formatNumber(totalEvents)} events
        </div>
      </div>

      <div className="kpi-item">
        <div className="kpi-label">
          <span>Baseline</span>
          <Target />
        </div>
        <div className="kpi-value">
          {formatPct(baseline?.mean ?? 0)}{' '}
          <span className="kpi-sub">
            ± {formatPct(baseline?.std ?? 0.01)}
          </span>
        </div>
        <div className="kpi-sub">
          {baseline?.ready ? (
            <span className="value-success">Tracking active</span>
          ) : (
            <div className="space-y-1">
              <span>
                Learning {baseline?.samples ?? 0}/{baseline?.warmup_target ?? 24}
              </span>
              <div className="progress-track">
                <div
                  className="progress-fill"
                  style={{ width: `${(baseline?.warmup_progress ?? 0) * 100}%` }}
                />
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="kpi-item">
        <div className="kpi-label">
          <span>Sigma</span>
          <BarChart2 />
        </div>
        <div className={`kpi-value ${zScore >= 6.5 ? 'value-danger' : zScore >= 3 ? 'value-warning' : ''}`}>
          {zScore.toFixed(2)}σ
        </div>
        <div className="kpi-sub">
          Threshold <strong>≥ 3.00σ</strong>
        </div>
      </div>

      <div className={`kpi-item ${activeAlerts.length > 0 ? 'kpi-alert' : ''}`}>
        <div className="kpi-label">
          <span>Incidents</span>
          <AlertTriangle className={activeAlerts.length > 0 ? 'value-danger' : 'value-success'} />
        </div>
        <div className={`kpi-value ${activeAlerts.length > 0 ? 'value-danger' : ''}`}>
          {activeAlerts.length}
        </div>
        <div className="kpi-sub">
          {activeAlerts.length > 0 ? (
            <span className="value-danger">{activeAlerts[0].severity} severity</span>
          ) : (
            <span className="value-success">All clear</span>
          )}
        </div>
      </div>

      <div className="kpi-item">
        <div className="kpi-label">
          <span>Throughput</span>
          <Radio />
        </div>
        <div className="kpi-value">
          {eventsPerSec.toFixed(1)}{' '}
          <span className="kpi-sub">logs/s</span>
        </div>
        <div className="kpi-sub">
          {formatNumber(totalEvents)} total events
        </div>
      </div>
    </div>
  );
};

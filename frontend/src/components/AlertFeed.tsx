import React, { useState } from 'react';
import { AlertCircle, CheckCircle2, Cloud, Mail, Check, Filter } from 'lucide-react';
import { Alert } from '../types';
import { formatPct, formatRelativeTime, getSeverityBadgeClasses } from '../lib/format';

interface AlertFeedProps {
  alerts: Alert[];
  onAcknowledge: (alertId: string) => void;
}

export const AlertFeed: React.FC<AlertFeedProps> = ({ alerts, onAcknowledge }) => {
  const [filter, setFilter] = useState<string>('ALL');

  const filteredAlerts = alerts.filter((a) => {
    if (filter === 'ALL') return true;
    if (filter === 'RESOLVED') return a.status === 'RESOLVED' || a.event === 'RESOLVED';
    if (filter === 'OPEN') return a.status === 'OPEN';
    return a.severity === filter && a.status === 'OPEN';
  });

  return (
    <section className="panel alert-panel">
      <div className="panel-heading">
        <div>
          <h2 className="panel-title flex items-center gap-2">
            <AlertCircle className="w-4 h-4 color-forest" />
            Alert history <span className="alert-event">{alerts.length}</span>
          </h2>
          <p className="panel-kicker">Review, filter and acknowledge detected incidents.</p>
        </div>
        <div className="filter-row" aria-label="Filter alerts">
          <Filter className="w-3.5 h-3.5 color-muted mr-1" />
          {['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'OPEN', 'RESOLVED'].map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`filter-button ${
                filter === f
                  ? 'filter-button-active'
                  : ''
              }`}
            >
              {f}
            </button>
          ))}
        </div>
      </div>
      <div className="alert-panel-body">
        {filteredAlerts.length === 0 ? (
          <div className="empty-state">
            <CheckCircle2 className="w-5 h-5 color-success" />
            <p>No alerts match this filter. System stable.</p>
          </div>
        ) : (
          filteredAlerts.map((alert) => {
            const isResolved = alert.status === 'RESOLVED' || alert.event === 'RESOLVED';
            const badgeClass = isResolved ? getSeverityBadgeClasses('RESOLVED') : getSeverityBadgeClasses(alert.severity);

            return (
              <div
                key={alert.id + alert.updated_at}
                className={`alert-entry ${
                  isResolved
                    ? 'alert-entry-resolved'
                    : 'alert-entry-open'
                }`}
              >
                <div className="alert-entry-top">
                  <div className="alert-meta">
                    <span className={badgeClass}>
                      {isResolved ? 'RESOLVED' : alert.severity}
                    </span>
                    <span className="alert-event">{alert.event}</span>
                    <span className="alert-id">ID {alert.id}</span>
                  </div>
                  <span className="alert-time">{formatRelativeTime(alert.updated_at)}</span>
                </div>

                <div className="alert-title">
                  {alert.title}
                </div>

                <div className="alert-stats">
                  <div>
                    <span>Rate</span>
                    <strong>{formatPct(alert.error_rate)}</strong>
                  </div>
                  <div>
                    <span>Baseline</span>
                    <strong>{formatPct(alert.baseline_mean)}</strong>
                  </div>
                  <div>
                    <span>Z-score</span>
                    <strong>{alert.z_score.toFixed(1)}σ</strong>
                  </div>
                  <div>
                    <span>Errors / events</span>
                    <strong>{alert.window_errors}/{alert.window_total}</strong>
                  </div>
                </div>

                {alert.top_errors && alert.top_errors.length > 0 && (
                  <div>
                    <div className="signal-label">
                      Top signals
                    </div>
                    {alert.top_errors.map((err, i) => (
                      <div
                        key={i}
                        className="signal-row"
                      >
                        <span className="truncate">{err.message}</span>
                        <span className="signal-count">×{err.count} · {err.service}</span>
                      </div>
                    ))}
                  </div>
                )}

                <div className="alert-entry-footer">
                  <div className="publish-status">
                    <div className="publish-item">
                      <Cloud className="w-3.5 h-3.5" />
                      <span>CloudWatch <strong>{alert.publish_status?.cloudwatch ?? 'pending'}</strong></span>
                    </div>
                    <div className="publish-item">
                      <Mail className="w-3.5 h-3.5" />
                      <span>SNS <strong>{alert.publish_status?.sns ?? 'skipped'}</strong></span>
                    </div>
                  </div>

                  <div>
                    {alert.acknowledged ? (
                      <span className="acknowledged inline-flex items-center gap-1">
                        <Check className="w-3.5 h-3.5" /> ACKED
                      </span>
                    ) : (
                      <button
                        onClick={() => onAcknowledge(alert.id)}
                        className="ack-button"
                      >
                        ACK
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </section>
  );
};

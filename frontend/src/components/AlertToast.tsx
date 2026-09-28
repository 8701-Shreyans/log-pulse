import React, { useEffect } from 'react';
import { AlertTriangle, X } from 'lucide-react';
import { Alert } from '../types';
import { formatPct, getSeverityBadgeClasses } from '../lib/format';

interface AlertToastProps {
  alert: Alert | null;
  onDismiss: () => void;
}

export const AlertToast: React.FC<AlertToastProps> = ({ alert, onDismiss }) => {
  useEffect(() => {
    if (!alert) return;
    // Auto-dismiss after 8s unless CRITICAL
    if (alert.severity !== 'CRITICAL') {
      const timer = setTimeout(onDismiss, 6000);
      return () => clearTimeout(timer);
    }
  }, [alert, onDismiss]);

  if (!alert) return null;

  return (
    <div className="toast-shell" role="status" aria-live="polite">
      <div className="toast-content">
        <AlertTriangle className="toast-icon w-5 h-5" />
        <div className="flex-1">
          <div className="flex items-center justify-between gap-3">
            <span className={getSeverityBadgeClasses(alert.severity)}>
              {alert.severity} ANOMALY
            </span>
            <button
              onClick={onDismiss}
              className="toast-dismiss"
              aria-label="Dismiss alert notification"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>

          <div className="toast-title">{alert.title}</div>
          <div className="toast-copy">
            Error rate reached <strong className="value-danger">{formatPct(alert.error_rate)}</strong> (z={alert.z_score.toFixed(1)}σ).
          </div>
        </div>
      </div>
    </div>
  );
};

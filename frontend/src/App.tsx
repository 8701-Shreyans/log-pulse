import React from 'react';
import { useLiveFeed } from './hooks/useLiveFeed';
import { Header } from './components/Header';
import { KpiCards } from './components/KpiCards';
import { ErrorRateChart } from './components/ErrorRateChart';
import { AlertFeed } from './components/AlertFeed';
import { LogTail } from './components/LogTail';
import { AlertToast } from './components/AlertToast';

export const App: React.FC = () => {
  const {
    metrics,
    alerts,
    activeAlerts,
    baseline,
    logs,
    config,
    connection,
    audioEnabled,
    newAlertToast,
    setNewAlertToast,
    toggleAudio,
    acknowledgeAlert,
    triggerSpike,
    triggerRecover,
    resetEngine,
  } = useLiveFeed();

  const latestMetric = metrics.length > 0 ? metrics[metrics.length - 1] : null;

  return (
    <div className="app-shell">
      <Header
        connection={connection}
        audioEnabled={audioEnabled}
        onToggleAudio={toggleAudio}
        onReset={resetEngine}
        config={config}
        onTriggerSpike={triggerSpike}
        onTriggerRecover={triggerRecover}
      />

      <main className="dashboard-main">
        <section className="page-intro" aria-label="Dashboard overview">
          <div>
            <div className="eyebrow">Operations / Observability</div>
            <h2 className="section-heading">Signal, at a glance.</h2>
          </div>
          <div className="section-note">A live view of service health and incoming events.</div>
        </section>

        <KpiCards
          latestMetric={latestMetric}
          baseline={baseline}
          activeAlerts={activeAlerts}
        />

        <div className="dashboard-columns">
          <div className="flex flex-col">
            <ErrorRateChart metrics={metrics} config={config} />
          </div>

          <div className="flex flex-col">
            <AlertFeed alerts={alerts} onAcknowledge={acknowledgeAlert} />
          </div>
        </div>

        <LogTail logs={logs} />
      </main>

      <AlertToast
        alert={newAlertToast}
        onDismiss={() => setNewAlertToast(null)}
      />

      <footer className="site-footer">
        <div className="footer-brand">Log anomaly detector · adaptive baseline</div>
        <div className="footer-meta">
          <span>Publish mode <strong>{config?.publish_mode ?? 'DRY_RUN'}</strong></span>
          <span>Window <strong>{config?.window_seconds ?? 60}s</strong></span>
        </div>
      </footer>
    </div>
  );
};

export default App;

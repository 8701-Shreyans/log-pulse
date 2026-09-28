import { useState, useEffect, useRef, useCallback } from 'react';
import {
  MetricPoint,
  Alert,
  BaselineState,
  LogLine,
  AppConfig,
  Envelope,
  ConnectionState
} from '../types';

export function useLiveFeed() {
  const [metrics, setMetrics] = useState<MetricPoint[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [activeAlerts, setActiveAlerts] = useState<Alert[]>([]);
  const [baseline, setBaseline] = useState<BaselineState | null>(null);
  const [logs, setLogs] = useState<LogLine[]>([]);
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [connection, setConnection] = useState<ConnectionState>('reconnecting');
  const [audioEnabled, setAudioEnabled] = useState<boolean>(false);
  const [newAlertToast, setNewAlertToast] = useState<Alert | null>(null);

  const lastSeqRef = useRef<number>(0);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptsRef = useRef<number>(0);
  const pollingTimerRef = useRef<number | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);

  // Synthesize audio chime on alert
  const playAlertChime = useCallback((type: 'anomaly' | 'resolve' = 'anomaly') => {
    if (!audioEnabled) return;
    try {
      if (!audioCtxRef.current) {
        audioCtxRef.current = new (window.AudioContext || (window as any).webkitAudioContext)();
      }
      if (audioCtxRef.current.state === 'suspended') {
        audioCtxRef.current.resume();
      }
      const ctx = audioCtxRef.current;
      const now = ctx.currentTime;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);

      if (type === 'anomaly') {
        osc.type = 'sine';
        osc.frequency.setValueAtTime(880, now);
        osc.frequency.setValueAtTime(587.33, now + 0.12);
        gain.gain.setValueAtTime(0.15, now);
        gain.gain.exponentialRampToValueAtTime(0.01, now + 0.35);
        osc.start(now);
        osc.stop(now + 0.35);
      } else {
        osc.type = 'triangle';
        osc.frequency.setValueAtTime(440, now);
        osc.frequency.exponentialRampToValueAtTime(880, now + 0.25);
        gain.gain.setValueAtTime(0.12, now);
        gain.gain.exponentialRampToValueAtTime(0.01, now + 0.4);
        osc.start(now);
        osc.stop(now + 0.4);
      }
    } catch {
      // Audio not permitted without user gesture
    }
  }, [audioEnabled]);

  // Initial REST Hydration
  const hydrate = useCallback(async () => {
    try {
      const [cfgRes, metricsRes, alertsRes, activeRes, logsRes] = await Promise.all([
        fetch('/api/config'),
        fetch('/api/metrics?minutes=30'),
        fetch('/api/alerts?limit=50'),
        fetch('/api/alerts/active'),
        fetch('/api/logs/recent?limit=100')
      ]);

      if (cfgRes.ok) setConfig(await cfgRes.json());
      if (metricsRes.ok) {
        const mData = await metricsRes.json();
        setMetrics(mData);
      }
      if (alertsRes.ok) {
        const aData = await alertsRes.json();
        setAlerts(aData);
      }
      if (activeRes.ok) {
        const actData = await activeRes.json();
        setActiveAlerts(actData);
      }
      if (logsRes.ok) {
        const lData = await logsRes.json();
        setLogs(lData);
      }
    } catch (err) {
      console.warn('Hydration error:', err);
    }
  }, []);

  // Dispatch individual envelope
  const handleEnvelope = useCallback((env: Envelope) => {
    if (env.seq && env.seq <= lastSeqRef.current && env.type !== 'snapshot') {
      return; // Deduplicate
    }
    if (env.seq) {
      lastSeqRef.current = Math.max(lastSeqRef.current, env.seq);
    }

    switch (env.type) {
      case 'metric':
        setMetrics(prev => {
          const next = [...prev, env.data];
          return next.length > 720 ? next.slice(-720) : next;
        });
        break;

      case 'baseline':
        setBaseline(env.data);
        break;

      case 'alert': {
        const alertData: Alert = env.data;
        if (alertData.event === 'ACKNOWLEDGED') {
          setAlerts(prev => prev.map(a => a.id === (alertData as any).alert_id ? { ...a, acknowledged: true } : a));
          setActiveAlerts(prev => prev.map(a => a.id === (alertData as any).alert_id ? { ...a, acknowledged: true } : a));
        } else {
          setAlerts(prev => {
            const idx = prev.findIndex(a => a.id === alertData.id);
            if (idx >= 0) {
              const updated = [...prev];
              updated[idx] = alertData;
              return updated;
            }
            return [alertData, ...prev].slice(0, 200);
          });

          if (alertData.status === 'OPEN') {
            setActiveAlerts(prev => {
              const idx = prev.findIndex(a => a.id === alertData.id);
              if (idx >= 0) {
                const updated = [...prev];
                updated[idx] = alertData;
                return updated;
              }
              return [alertData, ...prev];
            });
            if (alertData.event === 'OPENED' || alertData.event === 'ESCALATED') {
              setNewAlertToast(alertData);
              playAlertChime('anomaly');
            }
          } else if (alertData.status === 'RESOLVED') {
            setActiveAlerts(prev => prev.filter(a => a.id !== alertData.id));
            playAlertChime('resolve');
          }
        }
        break;
      }

      case 'log':
        setLogs(prev => {
          const next = [...prev, env.data];
          return next.length > 200 ? next.slice(-200) : next;
        });
        break;

      case 'snapshot':
        if (env.data.metrics) setMetrics(env.data.metrics);
        if (env.data.active_alerts) setActiveAlerts(env.data.active_alerts);
        if (env.data.baseline) setBaseline(env.data.baseline);
        if (env.data.config) setConfig(env.data.config);
        if (env.data.latest_seq) lastSeqRef.current = env.data.latest_seq;
        break;

      default:
        break;
    }
  }, [playAlertChime]);

  // Polling fallback
  const startPolling = useCallback(() => {
    if (pollingTimerRef.current) return;
    setConnection('polling');

    pollingTimerRef.current = window.setInterval(async () => {
      try {
        const res = await fetch(`/api/poll?since_seq=${lastSeqRef.current}&limit=200`);
        if (res.ok) {
          const body = await res.json();
          if (Array.isArray(body.items)) {
            body.items.forEach((item: Envelope) => handleEnvelope(item));
          }
          if (body.latest_seq) {
            lastSeqRef.current = body.latest_seq;
          }
        }
      } catch (e) {
        setConnection('offline');
      }
    }, 2000);
  }, [handleEnvelope]);

  const stopPolling = useCallback(() => {
    if (pollingTimerRef.current) {
      clearInterval(pollingTimerRef.current);
      pollingTimerRef.current = null;
    }
  }, []);

  // WebSocket lifecycle
  const connectWs = useCallback(() => {
    if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) {
      return;
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnection('live');
        reconnectAttemptsRef.current = 0;
        stopPolling();
      };

      ws.onmessage = (evt) => {
        try {
          const envelope: Envelope = JSON.parse(evt.data);
          handleEnvelope(envelope);
        } catch (e) {
          console.error('Error parsing WS envelope:', e);
        }
      };

      ws.onclose = () => {
        setConnection('reconnecting');
        reconnectAttemptsRef.current += 1;

        if (reconnectAttemptsRef.current >= 3) {
          startPolling();
        }

        const delay = Math.min(15000, 1000 * Math.pow(1.5, reconnectAttemptsRef.current));
        setTimeout(connectWs, delay);
      };

      ws.onerror = () => {
        ws.close();
      };
    } catch (err) {
      startPolling();
    }
  }, [handleEnvelope, startPolling, stopPolling]);

  useEffect(() => {
    hydrate();
    connectWs();

    return () => {
      stopPolling();
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [hydrate, connectWs, stopPolling]);

  // Actions
  const acknowledgeAlert = async (alertId: string) => {
    try {
      const res = await fetch(`/api/alerts/${alertId}/ack`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ by: 'operator' }),
      });
      if (res.ok) {
        setAlerts(prev => prev.map(a => a.id === alertId ? { ...a, acknowledged: true } : a));
        setActiveAlerts(prev => prev.map(a => a.id === alertId ? { ...a, acknowledged: true } : a));
      }
    } catch (e) {
      console.error('Failed to ack alert:', e);
    }
  };

  const triggerSpike = async (durationSec = 45, errorRatio = 0.60, scenario = 'spike') => {
    try {
      await fetch('/api/sim/spike', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ duration_sec: durationSec, error_ratio: errorRatio, scenario }),
      });
    } catch (e) {
      console.error('Failed to trigger spike:', e);
    }
  };

  const triggerRecover = async () => {
    try {
      await fetch('/api/sim/recover', { method: 'POST' });
    } catch (e) {
      console.error('Failed to trigger recover:', e);
    }
  };

  const resetEngine = async () => {
    try {
      await fetch('/api/reset', { method: 'POST' });
      setAlerts([]);
      setActiveAlerts([]);
      setMetrics([]);
    } catch (e) {
      console.error('Failed to reset:', e);
    }
  };

  return {
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
    toggleAudio: () => setAudioEnabled(prev => !prev),
    acknowledgeAlert,
    triggerSpike,
    triggerRecover,
    resetEngine,
  };
}

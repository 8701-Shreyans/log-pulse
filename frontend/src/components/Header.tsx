import React from 'react';
import { Bell, BellOff, RefreshCw, Zap } from 'lucide-react';
import { ConnectionState, AppConfig } from '../types';
import { SimControls } from './SimControls';

interface HeaderProps {
  connection: ConnectionState;
  audioEnabled: boolean;
  onToggleAudio: () => void;
  onReset: () => void;
  config: AppConfig | null;
  onTriggerSpike: (durationSec?: number, errorRatio?: number, scenario?: string) => void;
  onTriggerRecover: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  connection,
  audioEnabled,
  onToggleAudio,
  onReset,
  config,
  onTriggerSpike,
  onTriggerRecover,
}) => {
  const getConnectionPill = () => {
    switch (connection) {
      case 'live':
        return (
          <span className="connection-state connection-live">
            <span className="connection-dot" />
            Live · WebSocket
          </span>
        );
      case 'polling':
        return (
          <span className="connection-state connection-polling">
            <span className="connection-dot" />
            Fallback · polling 2s
          </span>
        );
      case 'reconnecting':
        return (
          <span className="connection-state connection-reconnecting">
            <span className="connection-dot" />
            Reconnecting
          </span>
        );
      default:
        return (
          <span className="connection-state connection-offline">
            <span className="connection-dot" />
            Offline
          </span>
        );
    }
  };

  return (
    <header className="site-header">
      <div className="header-inner">
      <div className="brand-lockup">
        <div className="brand-mark"><Zap className="w-4 h-4" /></div>
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="brand-title">Log anomaly</h1>
            <span className="version-mark">v2.0</span>
          </div>
          <p className="brand-meta">Real-time service observability</p>
        </div>
      </div>

      <div className="header-actions">
        {getConnectionPill()}

        <button
          onClick={onToggleAudio}
          className={`control-button ${audioEnabled ? 'control-button-primary' : 'control-button-quiet'}`}
          title={audioEnabled ? 'Audio alerts enabled' : 'Audio alerts muted'}
        >
          {audioEnabled ? <Bell className="w-3.5 h-3.5" /> : <BellOff className="w-3.5 h-3.5" />}
          <span>{audioEnabled ? 'Audio on' : 'Audio off'}</span>
        </button>

        <button
          onClick={onReset}
          className="control-button control-button-quiet"
          title="Reset baseline calibration & sliding window"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Reset</span>
        </button>

        {config?.sim_enabled && (
          <SimControls
            onTriggerSpike={onTriggerSpike}
            onTriggerRecover={onTriggerRecover}
          />
        )}
      </div>
      </div>
    </header>
  );
};

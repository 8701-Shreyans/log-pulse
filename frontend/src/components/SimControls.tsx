import React, { useState } from 'react';
import { Flame, CheckCircle, ChevronDown, Activity, AlertOctagon } from 'lucide-react';

interface SimControlsProps {
  onTriggerSpike: (durationSec?: number, errorRatio?: number, scenario?: string) => void;
  onTriggerRecover: () => void;
}

export const SimControls: React.FC<SimControlsProps> = ({
  onTriggerSpike,
  onTriggerRecover,
}) => {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="relative">
      <div className="flex items-center gap-1.5">
        <button
          onClick={() => onTriggerSpike(45, 0.60, 'spike')}
          className="control-button control-button-primary"
        >
          <Flame className="w-3.5 h-3.5" />
          <span>Inject spike</span>
        </button>

        <button
          onClick={onTriggerRecover}
          className="control-button control-button-quiet"
        >
          <CheckCircle className="w-3.5 h-3.5" />
          <span>Recover</span>
        </button>

        <button
          onClick={() => setIsOpen(!isOpen)}
          className="control-button control-button-quiet"
          title="More scenario simulations"
        >
          <ChevronDown className="w-4 h-4" />
        </button>
      </div>

      {isOpen && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setIsOpen(false)} />
          <div className="scenario-menu">
            <div className="scenario-menu-title">
              Simulation scenarios
            </div>

            <button
              onClick={() => {
                onTriggerSpike(45, 0.60, 'spike');
                setIsOpen(false);
              }}
              className="scenario-option"
            >
              <Flame className="w-4 h-4 color-danger" />
              <div>
                <div><strong>Severe spike</strong><small>60% errors · 45 sec</small></div>
              </div>
            </button>

            <button
              onClick={() => {
                onTriggerSpike(60, 0.75, 'ramp');
                setIsOpen(false);
              }}
              className="scenario-option"
            >
              <Activity className="w-4 h-4 color-warning" />
              <div>
                <div><strong>Gradual ramp</strong><small>2% to 75% · 60 sec</small></div>
              </div>
            </button>

            <button
              onClick={() => {
                onTriggerSpike(30, 0.50, 'flood');
                setIsOpen(false);
              }}
              className="scenario-option"
            >
              <AlertOctagon className="w-4 h-4 color-muted" />
              <div>
                <div><strong>Traffic flood</strong><small>8× volume · 50% errors</small></div>
              </div>
            </button>

            <button
              onClick={() => {
                onTriggerSpike(30, 0.95, 'outage');
                setIsOpen(false);
              }}
              className="scenario-option"
            >
              <AlertOctagon className="w-4 h-4 text-rose-500" />
              <div>
                <div><strong>Total outage</strong><small>95% errors · 30 sec</small></div>
              </div>
            </button>

            <button
              onClick={() => {
                onTriggerRecover();
                setIsOpen(false);
              }}
              className="scenario-option"
            >
              <CheckCircle className="w-4 h-4 color-success" />
              <div>
                <div><strong>Recover normal</strong><small>Restore baseline traffic</small></div>
              </div>
            </button>
          </div>
        </>
      )}
    </div>
  );
};

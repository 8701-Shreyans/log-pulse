import React, { useState, useRef, useEffect } from 'react';
import { Terminal, Play, Pause, Trash2 } from 'lucide-react';
import { LogLine } from '../types';
import { formatTime } from '../lib/format';

interface LogTailProps {
  logs: LogLine[];
}

export const LogTail: React.FC<LogTailProps> = ({ logs }) => {
  const [autoScroll, setAutoScroll] = useState<boolean>(true);
  const [serviceFilter, setServiceFilter] = useState<string>('ALL');
  const scrollRef = useRef<HTMLDivElement | null>(null);

  // Extract unique services from logs
  const services = Array.from(new Set(logs.map((l) => l.service || 'unknown'))).filter(Boolean);

  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  const filteredLogs = logs.filter((l) => {
    if (serviceFilter === 'ALL') return true;
    return l.service === serviceFilter;
  });

  const getLevelColor = (level: string) => {
    switch (level) {
      case 'ERROR':
        return 'level-error';
      case 'WARNING':
        return 'level-warning';
      default:
        return 'level-info';
    }
  };

  return (
    <section className="panel log-panel">
      <div className="panel-heading">
        <div>
          <h2 className="panel-title flex items-center gap-2">
            <Terminal className="w-4 h-4 color-forest" />
            Recent log events
          </h2>
          <p className="panel-kicker">Inspect recent events by service and severity.</p>
        </div>

        <div className="log-toolbar">
          <span className="log-count">{logs.length} lines</span>
          <select
            value={serviceFilter}
            onChange={(e) => setServiceFilter(e.target.value)}
            className="log-select"
            aria-label="Filter logs by service"
          >
            <option value="ALL">ALL SERVICES</option>
            {services.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>

          <button
            onClick={() => setAutoScroll((prev) => !prev)}
            className="control-button control-button-quiet"
          >
            {autoScroll ? <Pause className="w-3 h-3" /> : <Play className="w-3 h-3" />}
            <span>{autoScroll ? 'Pause scroll' : 'Resume scroll'}</span>
          </button>
        </div>
      </div>

      <div
        ref={scrollRef}
        className="log-stream"
      >
        {filteredLogs.length === 0 ? (
          <div className="empty-state">No log events yet. New events will appear here.</div>
        ) : (
          filteredLogs.map((line, idx) => (
            <div
              key={idx}
              className="log-line"
            >
              <span className="log-time">{formatTime(line.ts)}</span>
              <span className={`log-level ${getLevelColor(line.level)}`}>
                {line.level}
              </span>
              <button
                type="button"
                onClick={() => setServiceFilter(line.service || 'unknown')}
                className="log-service"
                title="Filter by this service"
              >
                [{line.service}]
              </button>
              <span className="log-message">{line.message}</span>
            </div>
          ))
        )}
      </div>
    </section>
  );
};

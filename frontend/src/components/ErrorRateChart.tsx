import React, { useMemo } from 'react';
import {
  ComposedChart,
  Line,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  ReferenceArea,
} from 'recharts';
import { MetricPoint, AppConfig } from '../types';
import { formatTime } from '../lib/format';

interface ErrorRateChartProps {
  metrics: MetricPoint[];
  config: AppConfig | null;
}

export const ErrorRateChart: React.FC<ErrorRateChartProps> = ({ metrics, config }) => {
  // Transform data for chart
  const chartData = useMemo(() => {
    return metrics.map((m) => {
      const lower = Math.max(0, m.baseline_mean - 3.0 * m.baseline_std);
      const bandWidth = Math.max(0, m.upper_band - lower);

      return {
        time: formatTime(m.ts),
        rawTs: m.ts,
        errorRatePct: +(m.error_rate * 100).toFixed(2),
        baselineMeanPct: +(m.baseline_mean * 100).toFixed(2),
        upperBandPct: +(m.upper_band * 100).toFixed(2),
        bandLower: +(lower * 100).toFixed(2),
        bandWidth: +(bandWidth * 100).toFixed(2),
        z: m.z,
        total: m.total,
        errors: m.errors,
        isBreach: m.is_breach,
        severity: m.severity,
      };
    });
  }, [metrics]);

  // Compute maximum Y value for nice scaling
  const maxY = useMemo(() => {
    let max = 15;
    chartData.forEach((d) => {
      if (d.errorRatePct > max) max = d.errorRatePct;
      if (d.upperBandPct > max) max = d.upperBandPct;
    });
    return Math.min(100, Math.ceil((max + 5) / 10) * 10);
  }, [chartData]);

  const minAbsRatePct = (config?.min_abs_rate ?? 0.05) * 100;

  const breachAreas = useMemo(() => {
    const areas: { x1: string; x2: string }[] = [];
    let start: string | null = null;
    chartData.forEach((d, i) => {
      if (d.isBreach && start === null) {
        start = d.time;
      }
      const ended = start !== null && (!d.isBreach || i === chartData.length - 1);
      if (ended && start !== null) {
        areas.push({ x1: start, x2: d.time });
        start = null;
      }
    });
    return areas;
  }, [chartData]);

  return (
    <section className="panel chart-panel">
      <div className="panel-heading">
        <div>
          <h2 className="panel-title">
            Error rate over time
          </h2>
          <p className="panel-kicker">
            Rolling window · baseline envelope · anomaly threshold
          </p>
        </div>
        <div className="eyebrow">Live telemetry</div>
      </div>
      <div className="chart-canvas">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={chartData} margin={{ top: 10, right: 10, left: -15, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#d9d9cf" vertical={false} />
            <XAxis
              dataKey="time"
              stroke="#85867e"
              fontSize={10}
              tickLine={false}
              minTickGap={40}
            />
            <YAxis
              domain={[0, maxY]}
              stroke="#85867e"
              fontSize={10}
              tickLine={false}
              tickFormatter={(v) => `${v}%`}
            />

            <Tooltip
              content={({ active, payload }) => {
                if (!active || !payload || !payload.length) return null;
                const d = payload[0].payload;
                return (
                  <div className="chart-tooltip">
                    <div className="tooltip-top">
                      <span>{d.time}</span>
                      {d.isBreach && <span className="value-danger">{d.severity} breach</span>}
                    </div>
                    <div className="tooltip-row"><span>Error rate</span><strong>{d.errorRatePct}%</strong></div>
                    <div className="tooltip-row"><span>Baseline mean</span><span>{d.baselineMeanPct}%</span></div>
                    <div className="tooltip-row"><span>3σ upper threshold</span><span>{d.upperBandPct}%</span></div>
                    <div className="tooltip-row"><span>Z-score</span><strong>{d.z}σ</strong></div>
                    <div className="tooltip-row"><span>Events / errors</span><span>{d.total} / {d.errors}</span></div>
                  </div>
                );
              }}
            />

            {breachAreas.map((area, i) => (
              <ReferenceArea
                key={`${area.x1}-${area.x2}-${i}`}
                x1={area.x1}
                x2={area.x2}
                fill="#a64032"
                fillOpacity={0.1}
                ifOverflow="extendDomain"
              />
            ))}

            <ReferenceLine
              y={minAbsRatePct}
              stroke="#aa782e"
              strokeDasharray="4 4"
              strokeOpacity={0.65}
            />

            <Area
              dataKey="bandLower"
              stackId="band"
              stroke="none"
              fill="transparent"
              isAnimationActive={false}
            />
            <Area
              dataKey="bandWidth"
              stackId="band"
              stroke="#8da18a"
              strokeDasharray="2 2"
              strokeOpacity={0.65}
              fill="#dce5d9"
              fillOpacity={0.8}
              isAnimationActive={false}
            />

            <Line
              type="monotone"
              dataKey="baselineMeanPct"
              stroke="#7f8178"
              strokeWidth={1.5}
              strokeDasharray="5 5"
              dot={false}
              isAnimationActive={false}
            />

            <Line
              type="monotone"
              dataKey="errorRatePct"
              stroke="#2c3e2e"
              strokeWidth={2.2}
              dot={false}
              isAnimationActive={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <div className="chart-legend" aria-label="Chart legend">
        <span className="legend-item"><i className="legend-line" /> Rate</span>
        <span className="legend-item"><i className="legend-dash" /> Baseline</span>
        <span className="legend-item"><i className="legend-band" /> 3σ band</span>
      </div>
    </section>
  );
};

export function formatPct(val: number | undefined | null, decimals = 1): string {
  if (val === undefined || val === null || isNaN(val)) return '0.0%';
  return `${(val * 100).toFixed(decimals)}%`;
}

export function formatNumber(val: number | undefined | null): string {
  if (val === undefined || val === null || isNaN(val)) return '0';
  return val.toLocaleString();
}

export function formatTime(isoStr: string | undefined | null): string {
  if (!isoStr) return '--:--:--';
  try {
    const d = new Date(isoStr);
    return d.toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
  } catch {
    return isoStr;
  }
}

export function formatRelativeTime(isoStr: string): string {
  try {
    const diffMs = Date.now() - new Date(isoStr).getTime();
    const diffSec = Math.floor(diffMs / 1000);
    if (diffSec < 5) return 'just now';
    if (diffSec < 60) return `${diffSec}s ago`;
    const diffMin = Math.floor(diffSec / 60);
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHrs = Math.floor(diffMin / 60);
    return `${diffHrs}h ago`;
  } catch {
    return isoStr;
  }
}

export function getSeverityBadgeClasses(sev: string): string {
  switch (sev) {
    case 'CRITICAL':
      return 'severity-badge severity-critical';
    case 'HIGH':
      return 'severity-badge severity-high';
    case 'MEDIUM':
      return 'severity-badge severity-medium';
    case 'LOW':
      return 'severity-badge severity-low';
    default:
      return 'severity-badge severity-resolved';
  }
}

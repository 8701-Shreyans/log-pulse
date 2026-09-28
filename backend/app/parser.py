import re
import json
from datetime import datetime, timezone
from typing import Optional
from app.models import LogEvent, LogLevel

# Patterns for extracting key-value pairs or structured fields from text lines
# e.g. 2026-09-28T10:15:03.412Z ERROR service=payments msg="DB connection timeout"
# e.g. 2026-09-28 10:15:03.412 [payments] [ERROR] DB connection timeout
KV_PATTERN = re.compile(r'(\w+)=(?:"([^"]*)"|(\S+))')

# Regex patterns
# Handles:
# 1. 2026-09-28T10:15:03.412Z ERROR service=payments msg="DB connection timeout"
# 2. 2026-09-28 10:15:03 [auth] [WARN] Token expired
# 3. 2026-09-28 10:15:03 [WARN] Token expired
TEXT_STANDARD_RE = re.compile(
    r"^\[?(?P<ts>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?)\]?\s+"
    r"(?:(?:\[(?P<service_bracket>[^\]]+)\]\s+)?\[?(?P<level>[A-Z]{3,8})\]?|\[?(?P<level_alt>[A-Z]{3,8})\]?\s+(?:\[(?P<service_bracket_alt>[^\]]+)\])?)"
    r"\s*[-–—:]?\s*(?P<rest>.*)$"
)

# Normalization patterns for error clustering
UUID_RE = re.compile(r'\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b')
HEX_RE = re.compile(r'\b0x[0-9a-fA-F]+\b|\b[0-9a-fA-F]{16,}\b')
IP_RE = re.compile(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?::\d+)?\b')
NUM_RE = re.compile(r'(?<=[\s_=\-:\[(])\d+\b|\b\d+\b')

def normalize_error_signature(msg: str) -> str:
    """Normalize error messages by masking variable identifiers for clustering."""
    s = UUID_RE.sub("<UUID>", msg)
    s = HEX_RE.sub("<HEX>", s)
    s = IP_RE.sub("<IP>", s)
    s = NUM_RE.sub("<NUM>", s)
    return s.strip()

def parse_iso_ts(ts_str: str) -> Optional[datetime]:
    if not ts_str:
        return None
    s = ts_str.strip().replace(",", ".")
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except Exception:
            continue
    return None

class LogParser:
    def __init__(self, mode: str = "auto"):
        self.mode = mode
        self.parse_failures = 0
        self.total_parsed = 0

    def parse_line(self, raw_line: str) -> Optional[LogEvent]:
        if not raw_line:
            return None
        line = raw_line.strip()
        if not line:
            return None

        self.total_parsed += 1

        # 1. JSON parsing
        if self.mode in ("auto", "json") and line.startswith("{") and line.endswith("}"):
            try:
                data = json.loads(line)
                ts_raw = data.get("ts") or data.get("timestamp") or data.get("time") or data.get("@timestamp")
                dt = parse_iso_ts(str(ts_raw)) if ts_raw else datetime.now(timezone.utc)
                if not dt:
                    dt = datetime.now(timezone.utc)

                level_raw = data.get("level") or data.get("severity") or "INFO"
                level = LogLevel.normalize(str(level_raw))

                service = str(data.get("service") or data.get("app") or "unknown")
                msg = str(data.get("msg") or data.get("message") or str(data))

                return LogEvent(
                    ts=dt,
                    level=level,
                    service=service,
                    message=msg,
                    raw=line
                )
            except Exception:
                if self.mode == "json":
                    self.parse_failures += 1
                    return None

        # 2. Text parsing
        m = TEXT_STANDARD_RE.match(line)
        if m:
            g = m.groupdict()
            dt = parse_iso_ts(g["ts"]) or datetime.now(timezone.utc)
            lvl_str = g.get("level") or g.get("level_alt") or "INFO"
            level = LogLevel.normalize(lvl_str)
            service = g.get("service_bracket") or g.get("service_bracket_alt") or "unknown"
            rest = g.get("rest", "")

            # Check if rest contains key-value pairs (e.g. service=payments msg="...")
            extracted_msg = None
            extracted_service = None
            for key, val_q, val_u in KV_PATTERN.findall(rest):
                val = val_q if val_q != "" else val_u
                if key.lower() in ("msg", "message"):
                    extracted_msg = val
                elif key.lower() in ("service", "app"):
                    extracted_service = val

            if extracted_service:
                service = extracted_service
            msg = extracted_msg if extracted_msg else rest.strip()

            return LogEvent(
                ts=dt,
                level=level,
                service=service,
                message=msg or line,
                raw=line
            )

        # 3. Fallback: Search for level and timestamp keywords
        level_search = re.search(r"\b(CRITICAL|FATAL|ERROR|WARN|WARNING|INFO|DEBUG)\b", line, re.IGNORECASE)
        if level_search:
            level = LogLevel.normalize(level_search.group(1))
            return LogEvent(
                ts=datetime.now(timezone.utc),
                level=level,
                service="unknown",
                message=line,
                raw=line
            )

        # Malformed line
        self.parse_failures += 1
        return None

import pytest
from datetime import datetime, timezone
from app.parser import LogParser, normalize_error_signature
from app.models import LogLevel

def test_parse_json_line():
    parser = LogParser(mode="auto")
    line = '{"ts":"2026-09-28T10:15:03.412Z","level":"ERROR","service":"payments","msg":"DB connection timeout"}'
    event = parser.parse_line(line)

    assert event is not None
    assert event.level == LogLevel.ERROR
    assert event.service == "payments"
    assert event.message == "DB connection timeout"

def test_parse_text_kv_line():
    parser = LogParser(mode="auto")
    line = '2026-09-28T10:15:03.412Z ERROR service=payments msg="DB connection timeout" latency_ms=5021'
    event = parser.parse_line(line)

    assert event is not None
    assert event.level == LogLevel.ERROR
    assert event.service == "payments"
    assert "DB connection timeout" in event.message

def test_parse_text_standard_bracket_line():
    parser = LogParser(mode="auto")
    line = '2026-09-28 10:15:03 [auth] [WARN] Token expired'
    event = parser.parse_line(line)

    assert event is not None
    assert event.level == LogLevel.WARNING
    assert event.service == "auth"
    assert event.level.is_error() is False

def test_level_normalization():
    assert LogLevel.normalize("CRITICAL") == LogLevel.ERROR
    assert LogLevel.normalize("FATAL") == LogLevel.ERROR
    assert LogLevel.normalize("WARN") == LogLevel.WARNING
    assert LogLevel.normalize("WARNING") == LogLevel.WARNING
    assert LogLevel.normalize("INFO") == LogLevel.INFO
    assert LogLevel.normalize("DEBUG") == LogLevel.DEBUG

def test_error_normalization_signature():
    msg = "DB query failed for user_id=18492 with tx=a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d to 192.168.1.55"
    norm = normalize_error_signature(msg)
    assert "<UUID>" in norm
    assert "<IP>" in norm
    assert "<NUM>" in norm

def test_malformed_lines_handled_gracefully():
    parser = LogParser()
    assert parser.parse_failures == 0
    res = parser.parse_line("??? invalid non log gibberish ???")
    assert res is None
    assert parser.parse_failures == 1
    assert parser.parse_line("") is None

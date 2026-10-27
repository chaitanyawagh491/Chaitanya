import logging
import pytest
from pathlib import Path
from utils.log import SensitiveInfoFormatter, write_crash_report
from config import config

def test_sensitive_info_formatter_redacts_api_keys():
    test_key = "AIzaSySecretApiKeyForTesting123"
    config.set_api_key("gemini", test_key)
    
    formatter = SensitiveInfoFormatter("%(message)s")
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg=f"Sending request with key {test_key} to endpoint",
        args=(),
        exc_info=None
    )
    
    formatted = formatter.format(record)
    assert test_key not in formatted
    assert "[REDACTED_API_KEY]" in formatted
    assert "Sending request with key [REDACTED_API_KEY] to endpoint" in formatted

def test_crash_report_generation(tmp_path):
    report_file = tmp_path / "crash_test.log"
    exc = ValueError("Simulated unexpected test error")
    
    path = write_crash_report(
        crash_log_file=report_file,
        version="3.0.0",
        module="TestModule",
        function="test_fn",
        error=exc,
        recent_events=["Event A", "Event B"]
    )
    assert report_file.exists()
    
    content = report_file.read_text(encoding="utf-8")
    assert "PORTAL CLIENT — CRASH REPORT" in content
    assert "Simulated unexpected test error" in content
    assert "TestModule" in content
    assert "test_fn" in content
    assert "Event A" in content

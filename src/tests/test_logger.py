import pytest
import json
import logging
from src.logger import _SecretRedactionFilter, _JsonFormatter

def test_secret_redaction_filter():
    """Verify that sensitive data is redacted from log records."""
    redactor = _SecretRedactionFilter()
    
    # 1. Test Static Patterns
    assert redactor._sanitize("My token is 1234567890abcdef") == "My token is 1234567890abcdef" # Not long enough or high entropy?
    # Actually, the static patterns match specific keywords
    assert redactor._sanitize("access_token=secret_val") == "access_token=[MASKED]"
    assert redactor._sanitize('{"access_token": "secret_val"}') == '{"access_token": "[MASKED]"}'
    
    # 2. Test High Entropy (Mocking Env Var)
    import os
    os.environ["SUPER_SECRET_KEY"] = "xV9kL2mP5nR8jQ4tW7" # High entropy
    redactor.refresh_secrets()
    assert redactor._sanitize("Using key xV9kL2mP5nR8jQ4tW7") == "Using key [MASKED]"
    
    # 3. Test Authorization Header
    assert redactor._sanitize("Authorization: Bearer my_token") == "Authorization: Bearer [MASKED]"

def test_json_formatter_validity():
    """Verify that the formatter produces valid, expected JSON."""
    formatter = _JsonFormatter()
    logger = logging.getLogger("test_logger")
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="test.py", lineno=10,
        msg="Test Message", args=(), exc_info=None
    )
    record.event = "test_event"
    record.platform = "bluesky"
    
    formatted = formatter.format(record)
    data = json.loads(formatted)
    
    assert data["level"] == "INFO"
    assert data["message"] == "Test Message"
    assert data["event"] == "test_event"
    assert data["platform"] == "bluesky"
    assert "timestamp" in data

def test_entropy_calculation():
    """Verify entropy-based secret detection."""
    # Low entropy
    assert _SecretRedactionFilter._has_min_entropy("aaaaaaaa") is False
    # High entropy
    assert _SecretRedactionFilter._has_min_entropy("aB1!cD2@eE") is True # 10 chars, varied

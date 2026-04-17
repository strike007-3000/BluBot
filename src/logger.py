import os
import re
import json
import logging
import math
from collections import Counter
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Pattern

class _SecretRedactionFilter(logging.Filter):
    """
    Redacts secrets from all log content.
    Uses both keyword-based patterns and high-entropy string detection.
    """
    _MIN_SECRET_LENGTH = 8
    _MIN_SECRET_ENTROPY = 2.5

    def __init__(self) -> None:
        super().__init__()
        self._secret_patterns: List[Pattern[str]] = []
        self.refresh_secrets()

    @classmethod
    def _has_min_entropy(cls, value: str) -> bool:
        if len(value) < cls._MIN_SECRET_LENGTH:
            return False
        counts = Counter(value)
        length = len(value)
        entropy = -sum((count / length) * math.log2(count / length) for count in counts.values())
        return entropy >= cls._MIN_SECRET_ENTROPY

    @classmethod
    def _is_redactable_secret(cls, key: str, secret: str) -> bool:
        if not secret or len(secret) < cls._MIN_SECRET_LENGTH:
            return False
        sensitive_keys = {"KEY", "TOKEN", "PASSWORD", "SECRET", "JWT"}
        if any(s in key.upper() for s in sensitive_keys):
            return cls._has_min_entropy(secret)
        return False

    def refresh_secrets(self) -> None:
        patterns: List[Pattern[str]] = []
        seen = set()
        # 1. Capture environment variables
        for key, secret in os.environ.items():
            if self._is_redactable_secret(key, secret) and secret not in seen:
                seen.add(secret)
                patterns.append(re.compile(re.escape(secret)))
        
        # 2. Add static patterns for known token formats
        static_patterns = [
            r"(?P<key>access_token=)[^&'\s\"]+",
            r"(?P<key>(?:access_token|password|access_jwt|refresh_jwt|token|key)\":\s*\")[^\"]+",
            r"(?P<key>(?:auth|authorization|x-rpc-auth):\s*(?:Bearer\s+)?)[^\s'\",]+",
            r"(?P<key>Bearer\s+)[^\s'\",]+"
        ]
        for sp in static_patterns:
            patterns.append(re.compile(sp, re.IGNORECASE))
            
        self._secret_patterns = patterns

    def _sanitize(self, value: Any) -> Any:
        if value is None:
            return None
        text = str(value)
        if not self._secret_patterns:
            return text
        
        for pattern in self._secret_patterns:
            if 'key' in pattern.groupindex:
                text = pattern.sub(r"\g<key>[MASKED]", text)
            else:
                text = pattern.sub("[MASKED]", text)
        return text

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = self._sanitize(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(self._sanitize(arg) for arg in record.args)
        elif isinstance(record.args, dict):
            record.args = {k: self._sanitize(v) for k, v in record.args.items()}

        for attr, value in list(record.__dict__.items()):
            if isinstance(value, str) and attr not in {"levelname", "name", "event"}:
                record.__dict__[attr] = self._sanitize(value)
        return True

class _JsonFormatter(logging.Formatter):
    """Formats log records as single-line JSON strings."""
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "event": getattr(record, "event", "log_event"),
            "message": record.getMessage(),
            "platform": getattr(record, "platform", "system"),
            "mode": getattr(record, "mode", None),
        }
        # Add any extra fields passed
        for key, value in record.__dict__.items():
            if key.startswith("_") or key in payload or key in {
                "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
                "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
                "created", "msecs", "relativeCreated", "thread", "threadName",
                "processName", "process", "asctime",
            }:
                continue
            payload[key] = value
        return json.dumps({k: v for k, v in payload.items() if v is not None}, ensure_ascii=False)

class SafeLogger:
    """Structured, security-hardened logger with secret redaction and JSON output."""
    _logger = logging.getLogger("BluBot")
    _is_configured = False
    _context: Dict[str, Any] = {"platform": "system", "mode": None}
    _redaction_filter: Optional[_SecretRedactionFilter] = None

    @classmethod
    def _configure_if_needed(cls) -> None:
        if cls._is_configured:
            return
        cls._logger.setLevel(logging.DEBUG)
        cls._logger.propagate = False
        
        handler = logging.StreamHandler()
        handler.setFormatter(_JsonFormatter())
        
        cls._redaction_filter = _SecretRedactionFilter()
        handler.addFilter(cls._redaction_filter)
        
        cls._logger.handlers.clear()
        cls._logger.addHandler(handler)
        cls._is_configured = True

    @classmethod
    def configure(cls, platform: Optional[str] = None, mode: Optional[str] = None):
        cls._configure_if_needed()
        if platform: cls._context["platform"] = platform
        if mode: cls._context["mode"] = mode

    @classmethod
    def _emit(cls, level: int, event: str, message: str, **fields):
        cls._configure_if_needed()
        payload = {**cls._context, **fields, "event": event}
        cls._logger.log(level, message, extra=payload)

    @staticmethod
    def info(message: str, event: str = "info", **fields):
        SafeLogger._emit(logging.INFO, event, message, **fields)

    @staticmethod
    def warn(message: str, event: str = "warning", **fields):
        SafeLogger._emit(logging.WARNING, event, message, **fields)

    @staticmethod
    def error(message: str, event: str = "error", **fields):
        SafeLogger._emit(logging.ERROR, event, message, **fields)

    @staticmethod
    def debug(message: str, event: str = "debug", **fields):
        if os.environ.get("DEBUG", "false").lower() == "true":
            SafeLogger._emit(logging.DEBUG, event, message, **fields)

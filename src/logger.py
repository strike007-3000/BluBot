import os
import re

class SafeLogger:
    """Utility to log messages while masking sensitive tokens and secrets."""
    
    # Pre-compiled list of regexes for common token patterns
    FORBIDDEN_PATTERNS = [
        r"(access_token=)[^&]+",
        r"(access_token\":\s*\")[^\"]+",
        r"(password\":\s*\")[^\"]+",
        r"(THREADS_ACCESS_TOKEN=)[^&]+"
    ]

    @staticmethod
    def sanitize(message):
        text = str(message)
        # 1. Static pattern masking
        for pattern in SafeLogger.FORBIDDEN_PATTERNS:
            text = re.sub(pattern, r"\1[MASKED]", text, flags=re.IGNORECASE)
        
        # 2. Dynamic environment variable masking
        sensitive_keys = ["KEY", "TOKEN", "PASSWORD", "SECRET"]
        for k, v in os.environ.items():
            if any(s in k.upper() for s in sensitive_keys) and v and len(v) > 5:
                text = text.replace(v, "[MASKED]")
        return text

    @staticmethod
    def info(message):
        print(f"INFO: {SafeLogger.sanitize(message)}", flush=True)

    @staticmethod
    def warn(message):
        print(f"WARNING: {SafeLogger.sanitize(message)}", flush=True)

    @staticmethod
    def error(message):
        print(f"ERROR: {SafeLogger.sanitize(message)}", flush=True)

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
        
        # 1. Static pattern masking (Improved for JWTs and Auth headers)
        patterns = SafeLogger.FORBIDDEN_PATTERNS + [
            r"(access_jwt\":\s*\")[^\"]+",
            r"(refresh_jwt\":\s*\")[^\"]+",
            r"(x-rpc-auth:\s*)[^\s']+",
            r"(Authorization:\s*Bearer\s*)[^\s']+"
        ]
        for pattern in patterns:
            text = re.sub(pattern, r"\1[MASKED]", text, flags=re.IGNORECASE)
        
        # 2. Dynamic environment variable masking
        sensitive_keys = ["KEY", "TOKEN", "PASSWORD", "SECRET"]
        for k, v in os.environ.items():
            if any(s in k.upper() for s in sensitive_keys) and v and len(v) > 5:
                text = text.replace(v, "[MASKED]")

        # 3. Active File Redaction (BlueSky Session String)
        try:
            # We assume SESSION_FILE_PATH logic here, but to avoid circular imports 
            # we check the common path directly or pass it in.
            session_path = "bluesky_session.txt"
            if os.path.exists(session_path):
                with open(session_path, "r", encoding="utf-8") as f:
                    session_content = f.read().strip()
                    if session_content and len(session_content) > 10:
                        text = text.replace(session_content, "[MASKED_SESSION]")
        except Exception:
            pass # Never let the logger fail

        return text

    @staticmethod
    def debug(message):
        if os.environ.get("DEBUG", "false").lower() == "true":
            print(f"DEBUG: {SafeLogger.sanitize(message)}", flush=True)

    @staticmethod
    def info(message):
        print(f"INFO: {SafeLogger.sanitize(message)}", flush=True)

    @staticmethod
    def warn(message):
        print(f"WARNING: {SafeLogger.sanitize(message)}", flush=True)

    @staticmethod
    def error(message):
        print(f"ERROR: {SafeLogger.sanitize(message)}", flush=True)

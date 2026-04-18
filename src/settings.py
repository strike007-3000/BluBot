import os
from dataclasses import dataclass, field
from typing import List, Optional
from .logger import SafeLogger
from dotenv import load_dotenv

@dataclass(frozen=True)
class Settings:
    """Centralized, typed configuration for BluBot."""
    # API Credentials
    gemini_key: str
    nvidia_key: Optional[str] = None
    bsky_handle: str = ""
    bsky_password: str = ""
    mastodon_token: Optional[str] = None
    mastodon_base_url: Optional[str] = None
    threads_token: Optional[str] = None
    threads_user_id: Optional[str] = None
    gist_id: Optional[str] = None
    gist_token: Optional[str] = None
    
    # Modes & Flags
    is_dry_run: bool = False
    is_ci: bool = False
    github_event: str = "schedule"
    image_provider: str = "nvidia"
    enable_image_gen: bool = True
    enable_bio_management: bool = True
    enable_interactions: bool = True
    
    # Observability
    log_format: str = "pretty" # "pretty" or "json"
    
    # Limits
    bluesky_limit: int = 300
    mastodon_limit: int = 500
    threads_limit: int = 500
    max_thread_parts: int = 2
    max_api_retries: int = 3
    backoff_factor: float = 3.0
    thread_pause_min: int = 10
    thread_pause_max: int = 30
    
    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        
        is_dry_run = os.getenv("DRY_RUN", "false").lower() == "true"
        is_ci = os.getenv("CI", "false").lower() == "true"
        image_provider = os.getenv("IMAGE_PROVIDER", "nvidia")
        
        # Core validation logic moved from config.py
        settings_dict = {
            "gemini_key": os.getenv("GEMINI_KEY", ""),
            "enable_image_gen": os.getenv("ENABLE_IMAGE_GEN", "true").lower() == "true",
            "enable_bio_management": os.getenv("ENABLE_BIO_MGMT", "true").lower() == "true",
            "enable_interactions": os.getenv("ENABLE_INTERACTIONS", "true").lower() == "true",
            "log_format": os.getenv("LOG_FORMAT", "json" if is_ci else "pretty").lower(),
            "max_thread_parts": int(os.getenv("MAX_THREAD_PARTS", "2")),
            "gist_id": os.getenv("GIST_ID"),
            "gist_token": os.getenv("GIST_TOKEN"),
            "nvidia_key": os.getenv("NVIDIA_KEY"),
            "bsky_handle": os.getenv("BSKY_HANDLE", ""),
            "bsky_password": os.getenv("BSKY_APP_PASSWORD", ""),
            "mastodon_token": os.getenv("MASTODON_ACCESS_TOKEN"),
            "mastodon_base_url": os.getenv("MASTODON_BASE_URL"),
            "threads_token": os.getenv("THREADS_ACCESS_TOKEN"),
            "threads_user_id": os.getenv("THREADS_USER_ID"),
            "is_dry_run": is_dry_run,
            "is_ci": is_ci,
            "github_event": os.getenv("GITHUB_EVENT_NAME", "schedule"),
            "image_provider": image_provider,
,ReplacementChunks:[{AllowMultiple:false,EndLine:64,ReplacementContent:        }
        
        if is_dry_run:
            # Inject mock credentials for dry run diagnostic
            if not settings_dict["bsky_handle"]: 
                settings_dict["bsky_handle"] = "mock_value"
                os.environ["BSKY_HANDLE"] = "mock_value"
            if not settings_dict["bsky_password"]: 
                settings_dict["bsky_password"] = "mock_value"
                os.environ["BSKY_APP_PASSWORD"] = "mock_value"
            SafeLogger.info("Settings: DRY_RUN enabled. Using mock credentials where missing.")

        return cls(**{k: v for k, v in settings_dict.items() if v is not None})

    @property
    def is_manual_run(self) -> bool:
        """Determines if the current execution was manually triggered."""
        is_manual = self.github_event != "schedule" or not self.is_ci
        if is_manual:
            SafeLogger.info(f"Settings: Manual run detected (Event: {self.github_event}). Bypassing scheduling blocks.")
        return is_manual

    def validate(self) -> bool:
        """Validates critical settings and returns True if valid."""
        # In dry run, we allow missing keys as the diagnostic script handles its own mocking
        if self.is_dry_run:
            return True

        if not self.gemini_key:
            SafeLogger.error("Settings: Missing GEMINI_KEY.")
            return False
            
        if self.image_provider == "nvidia" and not self.nvidia_key:
            SafeLogger.error("Settings: NVIDIA image provider selected but NVIDIA_KEY is missing.")
            return False
            
        if not self.bsky_handle or not self.bsky_password:
            SafeLogger.error("Settings: Missing Bluesky credentials.")
            return False
            
        return True

# Singleton instance
settings = Settings.from_env()

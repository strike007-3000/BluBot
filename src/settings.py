import os
from dataclasses import dataclass, field
from typing import List, Optional
from .logger import SafeLogger
from dotenv import load_dotenv

@dataclass(frozen=True)
class Settings:
    """Centralized, typed configuration for BluBot."""
    # API Credentials
    gemini_key: str = ""
    llm_provider: str = "codex"
    llm_fallback_providers: str = "claude,gemini"
    codex_model: Optional[str] = None
    claude_model: Optional[str] = None
    nvidia_key: Optional[str] = None
    bsky_handle: str = ""
    bsky_password: str = ""
    mastodon_token: Optional[str] = None
    mastodon_base_url: Optional[str] = None
    threads_token: Optional[str] = None
    threads_user_id: Optional[str] = None
    gist_id: Optional[str] = None
    gist_token: Optional[str] = None
    thinking_budget: Optional[int] = None
    gemini_model: str = "models/gemini-2.5-flash-lite"
    
    # Modes & Flags
    is_dry_run: bool = False
    is_ci: bool = False
    github_event: str = "schedule"
    image_provider: str = "huggingface"
    pollinations_api_url: str = "" # will load from config constant in from_env
    pollinations_api_key: Optional[str] = None
    huggingface_api_key: Optional[str] = None
    huggingface_image_model: str = ""
    enable_image_gen: bool = True
    youtube_api_key: Optional[str] = None
    youtube_region_codes: List[str] = field(default_factory=lambda: ["US", "RU", "UA"])
    youtube_language_hints: List[str] = field(default_factory=lambda: ["ru", "en"])
    youtube_seed_queries: List[str] = field(default_factory=lambda: [
        "Claude Code",
        "OpenAI Codex",
        "AI agents MCP",
        "n8n automation",
    ])
    enable_hybrid_auto_posting: bool = True
    min_post_score_for_auto: int = 80
    max_auto_posts_per_day: int = 1
    min_post_interval_minutes: int = 30
    auto_queue_ttl_hours: int = 24
    enable_bio_management: bool = True
    enable_interactions: bool = True
    enable_bsky_comment_replies: bool = True
    enable_mastodon_comment_replies: bool = False
    enable_threads_comment_replies: bool = False
    
    # Telegram Integration Config
    telegram_bot_token: Optional[str] = None
    telegram_user_id: Optional[str] = None
    telegram_channel_id: Optional[str] = None
    telegram_timeout_minutes: int = 0
    enable_telegram_approval: bool = False
    
    # Platform Hashtag Controls
    enable_hashtags_bsky: bool = True
    enable_hashtags_mastodon: bool = True
    enable_hashtags_threads: bool = True
    
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
        image_provider = os.getenv("IMAGE_PROVIDER", "huggingface")
        
        # Parse thinking budget safely
        tb_env = os.getenv("THINKING_BUDGET")
        thinking_budget = int(tb_env) if tb_env and tb_env.strip().isdigit() else None

        from .config import POLLINATIONS_API_URL, HF_IMAGE_MODEL


        # Core validation logic moved from config.py
        settings_dict = {
            "gemini_key": os.getenv("GEMINI_KEY", ""),
            "llm_provider": os.getenv("LLM_PROVIDER", "codex").lower(),
            "llm_fallback_providers": os.getenv("LLM_FALLBACK_PROVIDERS", "claude,gemini").lower(),
            "codex_model": os.getenv("CODEX_MODEL"),
            "claude_model": os.getenv("CLAUDE_MODEL"),
            "enable_image_gen": os.getenv("ENABLE_IMAGE_GEN", "false").lower() == "true",
            "enable_bio_management": os.getenv("ENABLE_BIO_MGMT", "true").lower() == "true",
            "enable_interactions": os.getenv("ENABLE_INTERACTIONS", "true").lower() == "true",
            "youtube_api_key": os.getenv("YOUTUBE_API_KEY"),
            "youtube_region_codes": [r.strip() for r in os.getenv("YOUTUBE_REGION_CODES", "US,RU,UA").split(",") if r.strip()],
            "youtube_language_hints": [h.strip() for h in os.getenv("YOUTUBE_LANGUAGE_HINTS", "ru,en").split(",") if h.strip()],
            "youtube_seed_queries": [q.strip() for q in os.getenv("YOUTUBE_SEED_QUERIES", "Claude Code,OpenAI Codex,AI agents MCP,n8n automation").split(",") if q.strip()],
            "enable_hybrid_auto_posting": os.getenv("ENABLE_HYBRID_AUTO_POSTING", "true").lower() == "true",
            "min_post_score_for_auto": int(os.getenv("MIN_POST_SCORE_FOR_AUTO", "80")) if os.getenv("MIN_POST_SCORE_FOR_AUTO", "80").strip().isdigit() else 80,
            "max_auto_posts_per_day": int(os.getenv("MAX_AUTO_POSTS_PER_DAY", "1")) if os.getenv("MAX_AUTO_POSTS_PER_DAY", "1").strip().isdigit() else 1,
            "min_post_interval_minutes": int(os.getenv("MIN_POST_INTERVAL_MINUTES", "30")) if os.getenv("MIN_POST_INTERVAL_MINUTES", "30").strip().isdigit() else 30,
            "auto_queue_ttl_hours": int(os.getenv("AUTO_QUEUE_TTL_HOURS", "24")) if os.getenv("AUTO_QUEUE_TTL_HOURS", "24").strip().isdigit() else 24,
            "enable_bsky_comment_replies": os.getenv("ENABLE_BSKY_COMMENT_REPLIES", "true").lower() == "true",
            "enable_mastodon_comment_replies": os.getenv("ENABLE_MASTODON_COMMENT_REPLIES", "false").lower() == "true",
            "enable_threads_comment_replies": os.getenv("ENABLE_THREADS_COMMENT_REPLIES", "false").lower() == "true",
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
            "pollinations_api_url": os.getenv("POLLINATIONS_API_URL", POLLINATIONS_API_URL),
            "pollinations_api_key": os.getenv("POLLINATIONS_API_KEY"),
            "huggingface_api_key": os.getenv("HUGGINGFACE_API_KEY"),
            "huggingface_image_model": os.getenv("HUGGINGFACE_IMAGE_MODEL", HF_IMAGE_MODEL),
            "thinking_budget": thinking_budget,
            "gemini_model": os.getenv("GEMINI_MODEL", "models/gemini-2.5-flash-lite"),
            
            # Telegram configuration
            "telegram_bot_token": os.getenv("TELEGRAM_BOT_TOKEN"),
            "telegram_user_id": os.getenv("TELEGRAM_USER_ID"),
            "telegram_channel_id": os.getenv("TELEGRAM_CHANNEL_ID"),
            "telegram_timeout_minutes": int(os.getenv("TELEGRAM_TIMEOUT_MINUTES", "0")),
            "enable_telegram_approval": os.getenv("ENABLE_TELEGRAM_APPROVAL", "true").lower() == "true",

            # Hashtags configuration
            "enable_hashtags_bsky": os.getenv("ENABLE_HASHTAGS_BSKY", "false").lower() == "true",
            "enable_hashtags_mastodon": os.getenv("ENABLE_HASHTAGS_MASTODON", "true").lower() == "true",
            "enable_hashtags_threads": os.getenv("ENABLE_HASHTAGS_THREADS", "true").lower() == "true",
        }
        
        if is_dry_run:
            # Inject mock credentials for dry run diagnostic
            if not settings_dict["bsky_handle"]: 
                settings_dict["bsky_handle"] = "mock_value"
                os.environ["BSKY_HANDLE"] = "mock_value"
            if not settings_dict["bsky_password"]: 
                settings_dict["bsky_password"] = "mock_value"
                os.environ["BSKY_APP_PASSWORD"] = "mock_value"
            if not settings_dict.get("gemini_key"):
                settings_dict["gemini_key"] = "mock_gemini_key"
                os.environ["GEMINI_KEY"] = "mock_gemini_key"
            SafeLogger.info("Settings: DRY_RUN enabled. Using mock credentials where missing.")

        return cls(**{k: v for k, v in settings_dict.items() if v is not None})

    @property
    def is_manual_run(self) -> bool:
        """Determines if the current execution was manually triggered (Persona logic)."""
        return self.github_event == "workflow_dispatch"

    @property
    def should_bypass_rest(self) -> bool:
        """Determines if scheduling rest locks should be ignored (Infrastructure logic)."""
        # Bypass if not in CI (local) or if triggered by anything other than the cron schedule (Push, Dispatch)
        return not self.is_ci or self.github_event != "schedule"

    def validate(self) -> bool:
        """Validates critical settings and returns True if valid."""
        # In dry run, we allow missing keys as the diagnostic script handles its own mocking
        if self.is_dry_run:
            return True

        supported_providers = {"codex", "claude", "gemini"}
        if self.llm_provider not in supported_providers:
            SafeLogger.error(f"Settings: Unsupported LLM_PROVIDER '{self.llm_provider}'.")
            return False

        if self.llm_provider == "gemini" and not self.gemini_key:
            SafeLogger.error("Settings: GEMINI_KEY is required when LLM_PROVIDER=gemini.")
            return False

        if self.enable_telegram_approval and (
            not self.telegram_bot_token or not self.telegram_user_id
        ):
            SafeLogger.error("Settings: Telegram approval requires TELEGRAM_BOT_TOKEN and TELEGRAM_USER_ID.")
            return False

        if not self.telegram_channel_id and not (
            self.bsky_handle
            or (self.mastodon_token and self.mastodon_base_url)
            or (self.threads_token and self.threads_user_id)
        ):
            SafeLogger.error("Settings: Configure TELEGRAM_CHANNEL_ID or another broadcast target.")
            return False
            
        return True

# Singleton instance
settings = Settings.from_env()

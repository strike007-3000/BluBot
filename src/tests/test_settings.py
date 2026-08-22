import pytest
import os
from src.settings import Settings

def test_settings_from_env_default(monkeypatch):
    """Verify that Settings.from_env() reads correct defaults."""
    monkeypatch.setenv("CI", "false")
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("GEMINI_KEY", "test_gemini")
    monkeypatch.setenv("BSKY_HANDLE", "test_handle")
    monkeypatch.setenv("BSKY_APP_PASSWORD", "test_pass")
    
    settings = Settings.from_env()
    assert settings.gemini_key == "test_gemini"
    assert settings.bsky_handle == "test_handle"
    assert settings.bsky_password == "test_pass"
    assert settings.is_dry_run is False
    assert settings.is_manual_run is False
    assert settings.should_bypass_rest is True # not in CI default

def test_settings_validation_dry_run():
    """Verify that validate() always returns True in dry run."""
    settings = Settings(gemini_key="", is_dry_run=True)
    assert settings.validate() is True

def test_settings_validation_missing_keys():
    """Verify validate() fails when required production keys are missing."""
    settings = Settings(llm_provider="unsupported", telegram_channel_id="@channel")
    assert settings.validate() is False

    settings = Settings(llm_provider="gemini", gemini_key="", telegram_channel_id="@channel")
    assert settings.validate() is False

    settings = Settings(llm_provider="codex")
    assert settings.validate() is False

def test_settings_validation_success():
    """Verify validate() succeeds with valid parameters."""
    settings = Settings(llm_provider="codex", telegram_channel_id="@channel")
    assert settings.validate() is True

def test_settings_is_manual_run():
    """Verify is_manual_run checks correct github event."""
    settings_schedule = Settings(gemini_key="key", github_event="schedule")
    assert settings_schedule.is_manual_run is False

    settings_dispatch = Settings(gemini_key="key", github_event="workflow_dispatch")
    assert settings_dispatch.is_manual_run is True

def test_settings_should_bypass_rest():
    """Verify should_bypass_rest determines when rest is bypassed."""
    # Not in CI -> bypass rest
    s1 = Settings(gemini_key="key", is_ci=False, github_event="schedule")
    assert s1.should_bypass_rest is True

    # In CI, scheduled run -> DO NOT bypass rest
    s2 = Settings(gemini_key="key", is_ci=True, github_event="schedule")
    assert s2.should_bypass_rest is False

    # In CI, workflow dispatch -> bypass rest
    s3 = Settings(gemini_key="key", is_ci=True, github_event="workflow_dispatch")
    assert s3.should_bypass_rest is True

def test_telegram_settings_defaults(monkeypatch):
    """Verify that settings correctly capture Telegram environment variables."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_USER_ID", "98765")
    monkeypatch.setenv("TELEGRAM_CHANNEL_ID", "@ai_news")
    monkeypatch.setenv("TELEGRAM_TIMEOUT_MINUTES", "10")
    monkeypatch.setenv("ENABLE_TELEGRAM_APPROVAL", "true")
    monkeypatch.setenv("ENABLE_HASHTAGS_BSKY", "true")
    monkeypatch.setenv("GEMINI_KEY", "test_gemini")
    monkeypatch.setenv("BSKY_HANDLE", "test_handle")
    monkeypatch.setenv("BSKY_APP_PASSWORD", "test_pass")

    settings = Settings.from_env()
    assert settings.telegram_bot_token == "123:abc"
    assert settings.telegram_user_id == "98765"
    assert settings.telegram_channel_id == "@ai_news"
    assert settings.telegram_timeout_minutes == 10
    assert settings.enable_telegram_approval is True
    assert settings.enable_hashtags_bsky is True


def test_hybrid_auto_post_settings(monkeypatch):
    monkeypatch.setenv("ENABLE_HYBRID_AUTO_POSTING", "false")
    monkeypatch.setenv("MIN_POST_SCORE_FOR_AUTO", "91")
    monkeypatch.setenv("MAX_AUTO_POSTS_PER_DAY", "3")
    monkeypatch.setenv("MIN_POST_INTERVAL_MINUTES", "45")
    monkeypatch.setenv("AUTO_QUEUE_TTL_HOURS", "12")

    settings = Settings.from_env()

    assert settings.enable_hybrid_auto_posting is False
    assert settings.min_post_score_for_auto == 91
    assert settings.max_auto_posts_per_day == 3
    assert settings.min_post_interval_minutes == 45
    assert settings.auto_queue_ttl_hours == 12


def test_hybrid_auto_post_invalid_numbers_use_defaults(monkeypatch):
    monkeypatch.setenv("MIN_POST_SCORE_FOR_AUTO", "invalid")
    monkeypatch.setenv("MAX_AUTO_POSTS_PER_DAY", "invalid")
    monkeypatch.setenv("MIN_POST_INTERVAL_MINUTES", "invalid")
    monkeypatch.setenv("AUTO_QUEUE_TTL_HOURS", "invalid")

    settings = Settings.from_env()

    assert settings.min_post_score_for_auto == 80
    assert settings.max_auto_posts_per_day == 1
    assert settings.min_post_interval_minutes == 30
    assert settings.auto_queue_ttl_hours == 24

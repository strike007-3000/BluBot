import pytest
import os
from src.settings import Settings

def test_settings_from_env_default(monkeypatch):
    """Verify that Settings.from_env() reads correct defaults."""
    monkeypatch.setenv("CI", "false")
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
    # Missing everything
    settings = Settings(gemini_key="", bsky_handle="", bsky_password="")
    assert settings.validate() is False

    # Missing Bluesky keys
    settings = Settings(gemini_key="key", bsky_handle="", bsky_password="")
    assert settings.validate() is False

    # Missing Nvidia Key but selecting Nvidia provider
    settings = Settings(gemini_key="key", bsky_handle="h", bsky_password="p", image_provider="nvidia", nvidia_key="")
    assert settings.validate() is False

def test_settings_validation_success():
    """Verify validate() succeeds with valid parameters."""
    settings = Settings(gemini_key="key", bsky_handle="h", bsky_password="p", image_provider="nvidia", nvidia_key="nkey")
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

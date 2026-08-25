import pytest
import os
from unittest.mock import MagicMock, patch
from src.config import validate_config, validate_gemini_model_priority

def test_validate_config_dry_run_injection():
    """Verify that missing config variables are injected with mocks in DRY_RUN mode."""
    # Ensure variables are missing
    os.environ.pop("BSKY_HANDLE", None)
    os.environ.pop("BSKY_APP_PASSWORD", None)
    os.environ["DRY_RUN"] = "true"

    # Needs GEMINI_KEY to pass model priority validation unless mocked
    os.environ["GEMINI_KEY"] = "mock_key_with_entropy_xV9kL2m"

    # Run validation
    with pytest.MonkeyPatch().context() as mp:
        mp.setenv("CI", "true") # Skip real API call in validate_gemini_model_priority
        result = validate_config()

    assert result is True
    assert os.environ.get("BSKY_HANDLE") == "mock_value"
    assert os.environ.get("BSKY_APP_PASSWORD") == "mock_value"

def test_validate_config_failure_in_production():
    """Verify that missing mandatory config causes failure in non-DRY_RUN mode."""
    os.environ["DRY_RUN"] = "false"
    os.environ.pop("BSKY_HANDLE", None)

    # result = validate_config()
    # assert result is False
    # Use patch to avoid actually logging errors to stderr during test if possible
    # But let's just assert the return value
    assert validate_config() is False

def test_gemini_priority_validation_ci_mode():
    """Verify that validation passes in CI mode without real API keys."""
    os.environ["CI"] = "true"
    assert validate_gemini_model_priority() is True

def test_validate_gemini_model_priority_pruning(monkeypatch):
    """Verify that validate_gemini_model_priority prunes model priority based on API listing."""
    monkeypatch.setenv("CI", "false")
    monkeypatch.setenv("GEMINI_KEY", "test_key")

    from src.config import GEMINI_MODEL_PRIORITY
    original_priority = list(GEMINI_MODEL_PRIORITY)

    mock_client = MagicMock()
    m1 = MagicMock()
    m1.name = "models/gemini-3.5-flash-lite"
    m2 = MagicMock()
    m2.name = "models/gemini-2.5-flash-lite"
    mock_model_list = [m1, m2]
    mock_client.models.list.return_value = mock_model_list

    with patch("google.genai.Client", return_value=mock_client):
        assert validate_gemini_model_priority() is True

    assert "models/gemini-3.5-flash-lite" in GEMINI_MODEL_PRIORITY
    assert "models/gemini-2.5-flash-lite" in GEMINI_MODEL_PRIORITY
    assert "models/gemini-3.7-flash" not in GEMINI_MODEL_PRIORITY

    # Restore original priority list for other tests
    GEMINI_MODEL_PRIORITY.clear()
    GEMINI_MODEL_PRIORITY.extend(original_priority)

def test_validate_gemini_model_priority_does_not_match_preview_alias(monkeypatch):
    """A preview API ID must not keep the similarly named stable model active."""
    monkeypatch.setenv("CI", "false")
    monkeypatch.setenv("GEMINI_KEY", "test_key")

    from src.config import GEMINI_MODEL_PRIORITY
    original_priority = list(GEMINI_MODEL_PRIORITY)
    mock_client = MagicMock()
    preview = MagicMock()
    preview.name = "models/gemini-3.5-flash-lite-preview"
    fallback = MagicMock()
    fallback.name = "gemini-2.5-flash-lite"
    mock_client.models.list.return_value = [preview, fallback]

    with patch("google.genai.Client", return_value=mock_client):
        assert validate_gemini_model_priority() is True

    assert "models/gemini-3.5-flash-lite" not in GEMINI_MODEL_PRIORITY
    assert GEMINI_MODEL_PRIORITY == ["models/gemini-2.5-flash-lite"]
    GEMINI_MODEL_PRIORITY.clear()
    GEMINI_MODEL_PRIORITY.extend(original_priority)

def test_exact_gemini_model_priority_order():
    """Verify GEMINI_MODEL_PRIORITY matches the exact approved list and excludes unapproved models."""
    from src.config import GEMINI_MODEL_PRIORITY, ALT_TEXT_MODELS, VISUAL_PROMPT_MODEL

    expected_priority = [
        "models/gemini-3.5-flash-lite",
        "models/gemini-3.7-flash",
        "models/gemini-3.6-flash",
        "models/gemini-2.5-flash-lite",
    ]

    assert GEMINI_MODEL_PRIORITY == expected_priority
    assert ALT_TEXT_MODELS == ["models/gemini-3.5-flash-lite", "models/gemini-2.5-flash-lite"]
    assert VISUAL_PROMPT_MODEL == "models/gemini-3.5-flash-lite"

    unapproved = [
        "models/gemini-3.1-flash-lite",
        "models/gemma-4-31b-it",
        "models/gemma-4-26b-a4b-it",
        "models/gemma-3-27b-it",
        "models/gemini-2.5-flash",
        "models/gemini-2.5-pro"
    ]
    for model in unapproved:
        assert model not in GEMINI_MODEL_PRIORITY

def test_get_version(tmp_path):
    from src.config import get_version
    import src.config

    # 1. Test existing version file
    test_version_file = tmp_path / "VERSION"
    test_version_file.write_text("v3.9.0\n", encoding="utf-8")

    original_path = src.config.VERSION_FILE_PATH
    src.config.VERSION_FILE_PATH = str(test_version_file)
    try:
        assert get_version() == "v3.9.0"

        # 2. Test missing version file (graceful degradation)
        if test_version_file.exists():
            test_version_file.unlink()
        assert get_version() == "Unknown"
    finally:
        src.config.VERSION_FILE_PATH = original_path

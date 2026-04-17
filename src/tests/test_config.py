import pytest
import os
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

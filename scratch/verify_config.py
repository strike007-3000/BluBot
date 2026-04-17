import os
import sys
from unittest.mock import patch

# Mock Logger to avoid spam
import logging
logging.basicConfig(level=logging.ERROR)

sys.path.append(os.getcwd())

from src.config import validate_config

def test_config_validation():
    # Test 1: Partial Threads (Token only)
    with patch.dict(os.environ, {
        "BSKY_HANDLE": "test", 
        "BSKY_APP_PASSWORD": "test", 
        "GEMINI_KEY": "test", 
        "NVIDIA_KEY": "test",
        "THREADS_ACCESS_TOKEN": "token_only"
    }):
        print("Testing Partial Threads (Token only)...")
        assert validate_config() is False
        print("Success: Correctly rejected partial Threads config.")

    # Test 2: Full Threads
    with patch.dict(os.environ, {
        "BSKY_HANDLE": "test", 
        "BSKY_APP_PASSWORD": "test", 
        "GEMINI_KEY": "test", 
        "NVIDIA_KEY": "test",
        "THREADS_ACCESS_TOKEN": "token",
        "THREADS_USER_ID": "uid"
    }):
        print("Testing Full Threads...")
        # Note: validate_gemini_model_priority might fail if GEMINI_KEY is invalid, 
        # so we might need to mock it too.
        with patch('src.config.validate_gemini_model_priority', return_value=True):
            assert validate_config() is True
            print("Success: Correctly accepted full Threads config.")

if __name__ == "__main__":
    try:
        test_config_validation()
        print("\nAll config tests passed!")
    except AssertionError as e:
        print(f"\nTest failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nAn error occurred: {e}")
        sys.exit(1)

import asyncio
import os
import sys

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from bot import update_status_dashboard
from src.config import STATUS_FILE_PATH

async def test_dashboard():
    print("--- Dashboard Migration Diagnostic ---")
    
    # Clean up
    if os.path.exists(STATUS_FILE_PATH):
        os.remove(STATUS_FILE_PATH)
        print("Cleaned up existing STATUS.md.")

    # 1. Test Initialization
    print("\n[Case 1] Dashboard Initialization")
    await update_status_dashboard("Morning", "Artificial Intelligence")
    
    if os.path.exists(STATUS_FILE_PATH):
        with open(STATUS_FILE_PATH, "r", encoding="utf-8") as f:
            content = f.read()
            if "Artificial Intelligence" in content and "Morning" in content:
                print("OK: STATUS.md initialized correctly.")
            else:
                print("FAIL: Initialization content mismatch.")
    else:
        print("FAIL: STATUS.md not created.")

    # 2. Test Update
    print("\n[Case 2] Dashboard Update")
    await update_status_dashboard("Evening", "Robotics")
    
    with open(STATUS_FILE_PATH, "r", encoding="utf-8") as f:
        content = f.read()
        if "Robotics" in content and "Evening" in content and "Morning" not in content:
            print("OK: STATUS.md updated correctly.")
        else:
            print("FAIL: Update failed or content mismatch.")

    print("\n--- Diagnostic Complete ---")

if __name__ == "__main__":
    asyncio.run(test_dashboard())

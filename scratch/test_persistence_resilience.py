import os
import json
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.utils import load_seen_articles, save_seen_articles
from src.config import SEEN_FILE_PATH

def test_persistence_resilience():
    print("--- BluBot Persistence Resilience Diagnostic ---")
    
    # Clean setup
    if os.path.exists(SEEN_FILE_PATH): os.remove(SEEN_FILE_PATH)
    bak_path = f"{SEEN_FILE_PATH}.bak"
    if os.path.exists(bak_path): os.remove(bak_path)
    
    test_data = {"links": ["https://example.com/resilience"], "recent_topics": ["Security"], "last_dialect": "SAGE"}
    
    # 1. Test Normal Save
    print("\n[Case 1] Normal Save")
    save_seen_articles(test_data)
    if os.path.exists(SEEN_FILE_PATH):
        print("OK: Primary state file created.")
    else:
        print("FAIL: Primary state file missing.")

    # 2. Test Backup Creation
    print("\n[Case 2] Backup Rotation")
    new_data = {"links": ["https://example.com/v2"], "recent_topics": ["Persistence"]}
    save_seen_articles(new_data)
    if os.path.exists(bak_path):
        with open(bak_path, "r") as f:
            bak_data = json.load(f)
            if bak_data == test_data:
                print("OK: Backup (.bak) contains previous state.")
            else:
                print("FAIL: Backup content mismatch.")
    else:
        print("FAIL: Backup file missing.")

    # 3. Test Corruption Recovery
    print("\n[Case 3] Primary Corruption Recovery")
    with open(SEEN_FILE_PATH, "w") as f:
        f.write("{ CORRUPT_JSON ...")
    
    recovered = load_seen_articles()
    # Note: load_seen_articles returns the backup data if primary is corrupt
    if recovered == test_data:
        print("OK: Correctly recovered from backup after primary corruption.")
    else:
        print(f"FAIL: Recovery failed. Got: {recovered}")

    # 4. Test Total Local Failure
    print("\n[Case 4] Total Local Failure (Fallback to Default)")
    with open(bak_path, "w") as f:
        f.write("MORE CORRUPTION")
    
    final = load_seen_articles()
    if final["links"] == []:
        print("OK: Correctly fell back to default state after total local failure.")
    else:
        print("FAIL: Fallback failed.")

    print("\n--- Diagnostic Complete ---")

if __name__ == "__main__":
    test_persistence_resilience()

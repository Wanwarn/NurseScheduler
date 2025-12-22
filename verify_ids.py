
from app import load_requests_from_csv, NURSE_NAMES, convert_to_thai_shifts
import pandas as pd
import os

def verify_ids():
    print("--- Verifying Nurse ID Refactor ---")
    
    # 1. Check NURSE_NAMES keys
    expected_keys = ['ER01', 'ER02', 'ER03', 'ER04', 'ER05', 'ER06', 'ER07', 'ER08', 'ER09', 'ER10']
    keys = list(NURSE_NAMES.keys())
    # Sort for comparison (ignoring dict order)
    if sorted(keys) == sorted(expected_keys):
        print("PASS: NURSE_NAMES keys updated correctly.")
    else:
        print(f"FAIL: NURSE_NAMES keys mismatch. Found: {keys}")

    # 2. Check Migration Logic
    # Create dummy csv with old IDs
    dummy_csv = "leave_requests.csv"
    df = pd.DataFrame([{'nurse': 'ER1', 'date': 1, 'type': 'Off', 'month': 10, 'year': 2025},
                       {'nurse': 'ER9', 'date': 2, 'type': 'Off', 'month': 10, 'year': 2025},
                       {'nurse': 'ER10', 'date': 3, 'type': 'Off', 'month': 10, 'year': 2025}])
    df.to_csv(dummy_csv, index=False)
    
    # Load and check migration
    requests = load_requests_from_csv()
    ids = [r['nurse'] for r in requests]
    expected_ids = ['ER01', 'ER09', 'ER10']
    
    if sorted(ids) == sorted(expected_ids):
        print("PASS: Migration logic (ER1->ER01) works correctly.")
    else:
        print(f"FAIL: Migration logic failed. Got: {ids}")
        
    # Clean up
    if os.path.exists(dummy_csv):
        os.remove(dummy_csv)

    print("\n--- Verification Complete ---")

if __name__ == "__main__":
    verify_ids()

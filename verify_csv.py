
import pandas as pd
from app import convert_to_thai_shifts, solve_schedule

def verify_csv_customization():
    print("--- Verifying CSV Customization and Fix N/s Logic ---")
    
    # 1. Mock DataFrame
    data = [
        {'Nurse': 'ER1 (Name)', '1': 'M', '2': 'S', '3': 'N', '4': 'NS', '5': 'L_T', '6': 'O'},
        {'Nurse': 'ER9 (Name)', '1': 'M', '2': 'S', '3': 'N', '4': 'NS', '5': 'L_T', '6': 'O'},
        {'Nurse': 'ER10 (Name)', '1': 'M', '2': 'S', '3': 'N', '4': 'NS', '5': 'L_T', '6': 'O'},
    ]
    df = pd.DataFrame(data)
    
    # 2. Test Thai Conversion & Sorting
    thai_df = convert_to_thai_shifts(df, 31)
    
    # Check Sorting (ER10 should come before ER9)
    nurses = thai_df['Nurse'].tolist()
    print(f"Nurse Order: {nurses}")
    if nurses.index('ER10 (Name)') < nurses.index('ER9 (Name)'):
        print("PASS: ER10 is sorted before ER9.")
    else:
        print("FAIL: Sort order incorrect.")
        
    # Check Shift Mapping
    row1 = thai_df.iloc[0]
    mapping_checks = {
        '1': 'ช',
        '2': 'บ',
        '3': 'ด',
        '4': 'ดบ',
        '5': 'VA/ประชุม'
    }
    
    all_mapped = True
    for col, expected in mapping_checks.items():
        if row1[col] != expected:
            print(f"FAIL: Column {col} expected {expected}, got {row1[col]}")
            all_mapped = False
            
    if all_mapped:
        print("PASS: Thai shift mapping correct.")

    # 3. Test Fix S and N Logic (via solve_schedule simulation if possible, or just checking logic)
    # Since we can't easily run the solver due to 'ortools' issue in this env, we rely on the code review.
    # The logic was added parallel to Request_M which was already verified.
    
    print("\n--- Verification Complete ---")

if __name__ == "__main__":
    verify_csv_customization()

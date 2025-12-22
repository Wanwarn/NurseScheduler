
import pandas as pd
from app import solve_schedule
import calendar

def verify_constraints():
    year = 2025
    month = 10
    days_in_month = 31
    nurses = [f'ER{i}' for i in range(1, 11)]
    requests = []

    print("--- Testing with On-call ENABLED ---")
    df = solve_schedule(year, month, days_in_month, nurses, requests, enable_oncall=True)

    if df is not None:
        print("Schedule generated successfully.")
        
        # Check constraints
        violation_count = 0
        backup_usage = 0
        
        for index, row in df.iterrows():
            nurse = row['Nurse'].split(' ')[0] # Extract ID e.g., ER1
            
            for d in range(1, 11): # On-call days 1-10
                val = str(row[str(d)])
                has_oncall = '📞' in val
                has_m = val.startswith('M')
                has_ns = val.startswith('NS')
                
                if has_oncall:
                    if has_m:
                        print(f"VIOLATION: {nurse} has M and On-call on day {d}")
                        violation_count += 1
                    if has_ns:
                        print(f"VIOLATION: {nurse} has NS and On-call on day {d}")
                        violation_count += 1
                    
                    if nurse in ['ER4', 'ER8']:
                        print(f"NOTE: Backup nurse {nurse} assigned On-call on day {d}")
                        backup_usage += 1
                        
        if violation_count == 0:
            print("PASS: No M/NS conflicts with On-call.")
        else:
            print(f"FAIL: {violation_count} conflicts found.")
            
        print(f"Backup usage count (ER4/ER8): {backup_usage}")
        
    else:
        print("FAIL: Could not generate schedule.")

    print("\n--- Testing with On-call DISABLED ---")
    df_disabled = solve_schedule(year, month, days_in_month, nurses, requests, enable_oncall=False)
    
    if df_disabled is not None:
        oncall_found = False
        for index, row in df_disabled.iterrows():
            for d in range(1, 32):
                 if '📞' in str(row[str(d)]):
                     oncall_found = True
                     break
        if not oncall_found:
             print("PASS: No On-call assigned when disabled.")
        else:
             print("FAIL: On-call assigned even when disabled.")
    else:
        print("FAIL: Could not generate schedule (Disabled Mode).")

if __name__ == "__main__":
    verify_constraints()

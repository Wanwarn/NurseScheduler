
import pandas as pd
from app import solve_schedule
import sys

def verify_base_schedule():
    print("--- Verifying Base Schedule Feasibility ---")
    year = 2025
    month = 10
    days_in_month = 31
    nurses = [f'ER{i:02}' for i in range(1, 11)] # ER01..ER10
    requests = []

    print(f"Nurses: {nurses}")
    print(f"Year: {year}, Month: {month}")
    
    try:
        df = solve_schedule(year, month, days_in_month, nurses, requests, enable_oncall=False)
        if df is not None:
            print("PASS: Base schedule is FEASIBLE.")
            # Basic validation
            print(df.head())
        else:
            print("FAIL: Base schedule is INFEASIBLE.")
            sys.exit(1)
            
    except Exception as e:
        print(f"CRASH: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    verify_base_schedule()

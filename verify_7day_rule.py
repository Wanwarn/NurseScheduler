from app import solve_schedule
import pandas as pd

def test_7day_limit():
    print("Testing 7-Day Consecutive Work Rule with Previous Month Data...")
    
    nurses = [f'ER{i}' for i in range(1, 11)]
    year = 2026
    month = 1
    days_in_month = 5
    
    # Empty requests
    requests = []
    fix_requests = []
    staffing_overrides = []
    
    # Simulate ER1 worked 7 days straight at the end of previous month
    # D-7 to D-1 all matching work shifts
    prev_month_data = {
        'ER1': ['M', 'M', 'M', 'M', 'M', 'M', 'M'], # 7 days work
        'ER2': ['O', 'O', 'O', 'O', 'O', 'O', 'O']  # 0 days work
    }
    
    print(f"Previous Month Data for ER1: {prev_month_data['ER1']} (7 consecutive work days)")
    
    # Override staffing to minimum to ensure solvability
    staffing_overrides = [
        {'start': 1, 'end': 5, 'shift': 'M', 'count': 1, 'month': 1, 'year': 2026},
        {'start': 1, 'end': 5, 'shift': 'S', 'count': 1, 'month': 1, 'year': 2026},
        {'start': 1, 'end': 5, 'shift': 'N', 'count': 1, 'month': 1, 'year': 2026}
    ]
    
    # We must patch the function call to accept the override properly or just pass it
    df = solve_schedule(
        year, month, days_in_month, nurses, 
        requests, fix_requests, staffing_overrides,
        enable_oc=False, prev_month_data=prev_month_data
    )
    
    if df is not None:
        # Check ER1 Day 1
        er1_row = df[df['Nurse'].str.contains('ER1')].iloc[0]
        day1_shift = er1_row['1']
        
        print(f"ER1 Day 1 Shift: '{day1_shift}'")
        
        if day1_shift == '' or day1_shift == 'O' or day1_shift is None:
            print("PASS: ER1 is OFF on Day 1 as expected.")
        else:
            print(f"FAIL: ER1 has shift '{day1_shift}' on Day 1!")
            
        # Check ER2 Day 1 (Should probably work to meet demand)
        er2_row = df[df['Nurse'].str.contains('ER2')].iloc[0]
        day1_shift_er2 = er2_row['1']
        print(f"ER2 Day 1 Shift: '{day1_shift_er2}'")
        
    else:
        print("FAIL: Could not solve schedule.")

if __name__ == "__main__":
    test_7day_limit()

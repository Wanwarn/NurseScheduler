# -*- coding: utf-8 -*-
import gspread
from oauth2client.service_account import ServiceAccountCredentials

SCOPE = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
SHEET_URL = 'https://docs.google.com/spreadsheets/d/1js5h70Abv1MIKrmZUBe3xypoCE4BXIo6_gEhBuJ5k8k/edit'

creds = ServiceAccountCredentials.from_json_keyfile_name('service_account.json', SCOPE)
client = gspread.authorize(creds)
sheet = client.open_by_url(SHEET_URL)

def add_timestamp_column(ws, col_letter, header_row=1):
    """Add timestamp column and hide it"""
    # Check if timestamp column exists
    headers = ws.row_values(header_row)
    if 'timestamp' not in headers:
        # Add timestamp header
        col_index = ord(col_letter.upper()) - ord('A') + 1
        ws.update_cell(header_row, col_index, 'timestamp')
        print(f'  Added timestamp column at {col_letter}')
    
    # Hide the timestamp column using Sheets API
    col_index = ord(col_letter.upper()) - ord('A')
    request_body = {
        "requests": [{
            "updateDimensionProperties": {
                "range": {
                    "sheetId": ws.id,
                    "dimension": "COLUMNS",
                    "startIndex": col_index,
                    "endIndex": col_index + 1
                },
                "properties": {
                    "hiddenByUser": True
                },
                "fields": "hiddenByUser"
            }
        }]
    }
    sheet.batch_update(request_body)
    print(f'  Hidden column {col_letter}')

# ==========================================
# Setup LeaveRequests - add timestamp at column G
# ==========================================
print('[1/3] LeaveRequests...')
ws_leave = sheet.worksheet('LeaveRequests')
# Update headers
current = ws_leave.row_values(1)
if 'timestamp' not in current:
    ws_leave.update('A1:G1', [['nurse', 'date', 'month', 'year', 'type', 'priority', 'timestamp']])
add_timestamp_column(ws_leave, 'G')

# ==========================================
# Setup FixRequests - add timestamp at column F
# ==========================================
print('[2/3] FixRequests...')
ws_fix = sheet.worksheet('FixRequests')
current = ws_fix.row_values(1)
if 'timestamp' not in current:
    ws_fix.update('A1:F1', [['nurse', 'shift', 'dates', 'month', 'year', 'timestamp']])
add_timestamp_column(ws_fix, 'F')

# ==========================================
# Setup StaffingOverrides - add timestamp at column G
# ==========================================
print('[3/3] StaffingOverrides...')
ws_staff = sheet.worksheet('StaffingOverrides')
current = ws_staff.row_values(1)
if 'timestamp' not in current:
    ws_staff.update('A1:G1', [['start', 'end', 'shift', 'count', 'month', 'year', 'timestamp']])
add_timestamp_column(ws_staff, 'G')

print('')
print('[DONE] Timestamp columns added and hidden!')
print('Users will not see them, but Admin will see timestamps in the app.')

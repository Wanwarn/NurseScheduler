# -*- coding: utf-8 -*-
import gspread
from oauth2client.service_account import ServiceAccountCredentials

SCOPE = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
SHEET_URL = 'https://docs.google.com/spreadsheets/d/1js5h70Abv1MIKrmZUBe3xypoCE4BXIo6_gEhBuJ5k8k/edit'

creds = ServiceAccountCredentials.from_json_keyfile_name('service_account.json', SCOPE)
client = gspread.authorize(creds)
sheet = client.open_by_url(SHEET_URL)

# Define dropdown values
NURSES = ['ER1', 'ER2', 'ER3', 'ER4', 'ER5', 'ER6', 'ER7', 'ER8', 'ER9', 'ER10']
LEAVE_TYPES = ['Off', 'Leave', 'Train']  # แยก Leave (ลา) และ Train (ประชุม/อบรม)
SHIFTS = ['M', 'S', 'N']

def set_dropdown(worksheet, cell_range, values):
    """Set dropdown validation using Sheets API directly"""
    request_body = {
        "requests": [{
            "setDataValidation": {
                "range": {
                    "sheetId": worksheet.id,
                    "startRowIndex": int(cell_range.split(':')[0][1:]) - 1,
                    "endRowIndex": int(cell_range.split(':')[1][1:]),
                    "startColumnIndex": ord(cell_range.split(':')[0][0].upper()) - ord('A'),
                    "endColumnIndex": ord(cell_range.split(':')[1][0].upper()) - ord('A') + 1
                },
                "rule": {
                    "condition": {
                        "type": "ONE_OF_LIST",
                        "values": [{"userEnteredValue": v} for v in values]
                    },
                    "showCustomUi": True,
                    "strict": True
                }
            }
        }]
    }
    sheet.batch_update(request_body)

# ==========================================
# Setup LeaveRequests sheet
# ==========================================
print('[1/3] Setting up LeaveRequests...')
try:
    ws_leave = sheet.worksheet('LeaveRequests')
except:
    ws_leave = sheet.add_worksheet(title='LeaveRequests', rows=100, cols=10)

# Add headers
current_data = ws_leave.get_all_values()
if not current_data or (len(current_data) > 0 and current_data[0][0] == ''):
    ws_leave.update(values=[['nurse', 'date', 'month', 'year', 'type', 'priority']], range_name='A1:F1')

set_dropdown(ws_leave, 'A2:A100', NURSES)
set_dropdown(ws_leave, 'E2:E100', LEAVE_TYPES)
print('[OK] LeaveRequests - nurse, type dropdowns added')

# ==========================================
# Setup FixRequests sheet
# ==========================================
print('[2/3] Setting up FixRequests...')
try:
    ws_fix = sheet.worksheet('FixRequests')
except:
    ws_fix = sheet.add_worksheet(title='FixRequests', rows=100, cols=10)

current_data = ws_fix.get_all_values()
if not current_data or (len(current_data) > 0 and current_data[0][0] == ''):
    ws_fix.update(values=[['nurse', 'shift', 'dates', 'month', 'year']], range_name='A1:E1')

set_dropdown(ws_fix, 'A2:A100', NURSES)
set_dropdown(ws_fix, 'B2:B100', SHIFTS)
print('[OK] FixRequests - nurse, shift dropdowns added')

# ==========================================
# Setup StaffingOverrides sheet
# ==========================================
print('[3/3] Setting up StaffingOverrides...')
try:
    ws_staff = sheet.worksheet('StaffingOverrides')
except:
    ws_staff = sheet.add_worksheet(title='StaffingOverrides', rows=100, cols=10)

current_data = ws_staff.get_all_values()
if not current_data or (len(current_data) > 0 and current_data[0][0] == ''):
    ws_staff.update(values=[['start', 'end', 'shift', 'count', 'month', 'year']], range_name='A1:F1')

set_dropdown(ws_staff, 'C2:C100', SHIFTS)
print('[OK] StaffingOverrides - shift dropdown added')

print('')
print('[DONE] All dropdown validations configured!')
print('Users can now select from dropdown lists in Google Sheet.')

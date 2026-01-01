# -*- coding: utf-8 -*-
import gspread
from oauth2client.service_account import ServiceAccountCredentials

SCOPE = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
SHEET_URL = 'https://docs.google.com/spreadsheets/d/1js5h70Abv1MIKrmZUBe3xypoCE4BXIo6_gEhBuJ5k8k/edit'

creds = ServiceAccountCredentials.from_json_keyfile_name('service_account.json', SCOPE)
client = gspread.authorize(creds)
sheet = client.open_by_url(SHEET_URL)

# Rename to Thai
try:
    ws = sheet.worksheet('Guidelines')
    ws.update_title('คำแนะนำ')
except:
    try:
        ws = sheet.worksheet('คำแนะนำ')
    except:
        ws = sheet.add_worksheet(title='คำแนะนำ', rows=50, cols=10)

ws.clear()

guidelines = [
    ['=== ระบบจัดตารางเวร - คำแนะนำ ==='],
    [''],
    ['[เป้าหมายวันหยุด]'],
    ['แต่ละคนควรได้หยุด ส-อา/นักขัตฤกษ์ ประมาณ 3-4 วัน/เดือน'],
    [''],
    ['[การขอหยุด - LeaveRequests]'],
    ['- ขอหยุดวัน ส-อา: ไม่เกิน 2-3 คน/สัปดาห์'],
    ['- ลา/ประชุมพร้อมกัน: ไม่เกิน 2 คน/วัน'],
    ['- ลา/ประชุมต่อคน: ไม่เกิน 10 วัน/เดือน'],
    [''],
    ['[การขอ Fix เวร - FixRequests]'],
    ['- ขอ Fix เวร: ไม่เกิน 3 คน/สัปดาห์'],
    ['- รวมทั้งเดือน: ไม่เกิน 12-15 คำขอ'],
    [''],
    ['==================================='],
    [''],
    ['[รูปแบบการกรอกข้อมูล]'],
    [''],
    ['--- Sheet: LeaveRequests ---'],
    ['nurse', 'date', 'month', 'year', 'type', 'priority'],
    ['ER2', '5', '1', '2026', 'Off', '1'],
    ['ER3', '10', '1', '2026', 'Leave_Train', '1'],
    [''],
    ['คำอธิบาย:'],
    ['- nurse: ชื่อพยาบาล (ER1-ER10)'],
    ['- date: วันที่ (1-31)'],
    ['- month: เดือน (1-12)'],
    ['- year: ปี ค.ศ. (2026)'],
    ['- type: Off = ขอหยุด, Leave = ลา, Train = ประชุม/อบรม'],
    ['- priority: 1 = สำคัญมาก, 10 = สำคัญน้อย'],
    [''],
    ['--- Sheet: FixRequests ---'],
    ['nurse', 'shift', 'dates', 'month', 'year'],
    ['ER5', 'M', '1,8,15,22', '1', '2026'],
    ['ER9', 'N', '3,10', '1', '2026'],
    [''],
    ['คำอธิบาย:'],
    ['- nurse: ชื่อพยาบาล (ER1-ER10)'],
    ['- shift: M = เช้า, S = บ่าย, N = ดึก'],
    ['- dates: วันที่ คั่นด้วยจุลภาค (เช่น 1,8,15,22)'],
    ['- month: เดือน (1-12)'],
    ['- year: ปี ค.ศ. (2026)'],
    [''],
    ['--- Sheet: StaffingOverrides ---'],
    ['start', 'end', 'shift', 'count', 'month', 'year'],
    ['1', '10', 'N', '2', '1', '2026'],
    [''],
    ['คำอธิบาย:'],
    ['- start: วันเริ่มต้น'],
    ['- end: วันสิ้นสุด'],
    ['- shift: N = ดึก, S = บ่าย'],
    ['- count: จำนวนคนที่ต้องการ'],
    ['- month: เดือน'],
    ['- year: ปี ค.ศ.'],
]

ws.update(values=guidelines, range_name='A1')
print('Done! Guidelines in Thai added to Google Sheet.')

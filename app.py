import streamlit as st
from ortools.sat.python import cp_model
import pandas as pd
import calendar
import os # อย่าลืม import os

# --- Thai Public Holidays 2025-2026 ---
THAI_HOLIDAYS = {
    2025: {
        1: [1],           # วันขึ้นปีใหม่
        2: [12],          # วันมาฆบูชา
        4: [6, 7, 13, 14, 15, 16],  # วันจักรี + สงกรานต์
        5: [1, 4, 5, 12], # วันแรงงาน + ฉัตรมงคล + วิสาขบูชา
        6: [2, 3],        # วันเฉลิมฯ พระราชินี
        7: [10, 11, 28],  # วันอาสาฬหบูชา + เข้าพรรษา + เฉลิมฯ ร.10
        8: [11, 12],      # วันแม่แห่งชาติ
        10: [13, 23],     # วันสวรรคต ร.9 + ปิยมหาราช
        12: [5, 10, 31],  # วันพ่อ + รัฐธรรมนูญ + สิ้นปี
    },
    2026: {
        1: [1, 2],        # วันขึ้นปีใหม่
        3: [3],           # วันมาฆบูชา
        4: [6, 13, 14, 15],  # วันจักรี + สงกรานต์
        5: [1, 4],        # วันแรงงาน + ฉัตรมงคล
        6: [1, 3],        # วันวิสาขบูชา (ชดเชย) + เฉลิมฯ พระราชินี
        7: [28, 29, 30],  # เฉลิมฯ ร.10 + อาสาฬหบูชา + เข้าพรรษา
        8: [12],          # วันแม่แห่งชาติ
        10: [13, 23],     # วันสวรรคต ร.9 + ปิยมหาราช
        12: [5, 7, 10, 31],  # วันพ่อ + ชดเชย + รัฐธรรมนูญ + สิ้นปี
    }
}

def is_holiday(year, month, day):
    """ตรวจสอบว่าเป็นวันหยุดนักขัตฤกษ์หรือไม่"""
    if year in THAI_HOLIDAYS and month in THAI_HOLIDAYS[year]:
        return day in THAI_HOLIDAYS[year][month]
    return False

def get_holiday_name(year, month, day):
    """รับชื่อวันหยุด (สำหรับ tooltip)"""
    holiday_names = {
        (2025, 1, 1): "วันขึ้นปีใหม่", (2025, 2, 12): "วันมาฆบูชา",
        (2025, 4, 6): "วันจักรี", (2025, 4, 13): "วันสงกรานต์",
        (2025, 5, 1): "วันแรงงาน", (2025, 5, 12): "วันวิสาขบูชา",
        (2025, 6, 3): "วันเฉลิมฯ พระราชินี", (2025, 7, 28): "วันเฉลิมฯ ร.10",
        (2025, 8, 12): "วันแม่แห่งชาติ", (2025, 10, 13): "วันสวรรคต ร.9",
        (2025, 10, 23): "วันปิยมหาราช", (2025, 12, 5): "วันพ่อแห่งชาติ",
        (2025, 12, 10): "วันรัฐธรรมนูญ", (2025, 12, 31): "วันสิ้นปี",
        (2026, 1, 1): "วันขึ้นปีใหม่", (2026, 3, 3): "วันมาฆบูชา",
        # ... สามารถเพิ่มชื่อวันหยุดได้
    }
    return holiday_names.get((year, month, day), "วันหยุดราชการ")

# --- Nurse Names Mapping ---
NURSE_NAMES = {
    'ER1': 'นูรีซาน',
    'ER2': 'อัมรี',
    'ER3': 'ฮาบีบูเลาะ',
    'ER4': 'มัรวาน',
    'ER5': 'อานูรา',
    'ER6': 'อูไมซะห์',
    'ER7': 'นูรีฮัน',
    'ER8': 'ฮูสนี',
    'ER9': 'นูซีลัน',
    'ER10': 'ซัมนะห์',
}

# ==========================================
# ☁️ Google Sheets Integration (วางทับส่วน CSV เดิม)
# ==========================================
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ตั้งค่าการเชื่อมต่อ
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
SHEET_URL = "https://docs.google.com/spreadsheets/d/1js5h70Abv1MIKrmZUBe3xypoCE4BXIo6_gEhBuJ5k8k/edit?usp=sharing"
CREDENTIALS_FILE = "service_account.json"

def connect_gsheet():
    """เชื่อมต่อกับ Google Sheets"""
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, SCOPE)
        client = gspread.authorize(creds)
        sheet = client.open_by_url(SHEET_URL)
        return sheet
    except Exception as e:
        st.error(f"❌ เชื่อมต่อ Google Sheets ไม่สำเร็จ: {e}")
        return None

# --- Helper: แปลงชื่อจาก dropdown กลับเป็นรหัส ER ---
def extract_nurse_id(nurse_value):
    """แปลง 'ER1 (นูรีซาน)' -> 'ER1' หรือ 'นูรีซาน' -> 'ER1'"""
    if not nurse_value:
        return None
    
    nurse_str = str(nurse_value).strip()
    
    # กรณี 1: รูปแบบ "ER1 (ชื่อ)" -> ดึง ER1 ออกมา
    if nurse_str.startswith('ER') and '(' in nurse_str:
        return nurse_str.split('(')[0].strip()
    
    # กรณี 2: รูปแบบ "ER1" หรือ "ER10" โดยตรง
    if nurse_str.startswith('ER') and nurse_str[2:].replace('0', '').isdigit():
        return nurse_str
    
    # กรณี 3: ชื่อจริงโดยตรง -> หา mapping กลับ
    for er_id, name in NURSE_NAMES.items():
        if name in nurse_str or nurse_str in name:
            return er_id
    
    # กรณี 4: คืนค่าเดิม (อาจเป็น ER1-ER10 อยู่แล้ว)
    return nurse_str

# --- Leave Requests ---
def load_requests_from_gsheet():
    try:
        sh = connect_gsheet()
        if not sh: return []
        records = sh.worksheet("LeaveRequests").get_all_records()
        
        from datetime import datetime
        sync_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # แปลงชื่อ nurse กลับเป็นรหัส ER และเพิ่ม timestamp ถ้าไม่มี
        for r in records:
            r['nurse'] = extract_nurse_id(r.get('nurse'))
            # ถ้า timestamp ว่างหรือไม่มี ให้ใส่เวลาที่ดึงข้อมูล
            if not r.get('timestamp'):
                r['timestamp'] = f"(synced: {sync_time})"
        return records
    except: return []

def save_requests_to_gsheet():
    """บันทึกข้อมูลจาก session_state ไปยัง Google Sheet (รวมกับข้อมูลเดิม)"""
    try:
        sh = connect_gsheet()
        if not sh: return
        ws = sh.worksheet("LeaveRequests")
        
        # Header ที่ถูกต้อง (พร้อม timestamp)
        headers = ['nurse', 'date', 'month', 'year', 'type', 'priority', 'timestamp']
        
        # 1. อ่านข้อมูลเดิมจาก Google Sheet
        existing_records = ws.get_all_records()
        
        # 2. สร้าง set ของข้อมูลที่มีอยู่แล้ว (nurse, date, month, year) เพื่อเช็ค duplicate
        existing_keys = set()
        for r in existing_records:
            key = (str(r.get('nurse', '')), str(r.get('date', '')), str(r.get('month', '')), str(r.get('year', '')))
            existing_keys.add(key)
        
        # 3. หาข้อมูลใหม่ที่ยังไม่มีใน Sheet
        new_records = []
        for req in st.session_state.requests:
            key = (str(req.get('nurse', '')), str(req.get('date', '')), str(req.get('month', '')), str(req.get('year', '')))
            if key not in existing_keys:
                new_records.append(req)
                existing_keys.add(key)  # ป้องกัน duplicate ในรอบเดียวกัน
        
        # 4. ถ้ามีข้อมูลใหม่ ให้ append ต่อท้าย
        if new_records:
            next_row = len(existing_records) + 2  # +1 for header, +1 for 0-index
            data = []
            for req in new_records:
                row = [
                    req.get('nurse', ''),
                    req.get('date', ''),
                    req.get('month', ''),
                    req.get('year', ''),
                    req.get('type', ''),
                    req.get('priority', ''),
                    req.get('timestamp', '')
                ]
                data.append(row)
            ws.update(values=data, range_name=f'A{next_row}')
            st.success(f"✅ เพิ่มข้อมูลใหม่ {len(new_records)} รายการ ต่อท้าย Google Sheet")
        else:
            st.info("ℹ️ ไม่มีข้อมูลใหม่ที่ต้องบันทึก (ข้อมูลทั้งหมดมีอยู่แล้วใน Sheet)")
            
    except Exception as e: st.error(f"Error saving requests: {e}")

# --- Fix Requests ---
def load_fix_requests_from_gsheet():
    try:
        sh = connect_gsheet()
        if not sh: return []
        records = sh.worksheet("FixRequests").get_all_records()
        
        from datetime import datetime
        sync_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        for r in records:
            # แปลงชื่อ nurse กลับเป็นรหัส ER
            r['nurse'] = extract_nurse_id(r.get('nurse'))
            if isinstance(r.get('dates'), str) and r['dates']:
                r['dates'] = [int(x) for x in r['dates'].split(',')]
            elif isinstance(r.get('dates'), int):
                r['dates'] = [r['dates']]
            # ถ้า timestamp ว่างหรือไม่มี ให้ใส่เวลาที่ดึงข้อมูล
            if not r.get('timestamp'):
                r['timestamp'] = f"(synced: {sync_time})"
        return records
    except: return []

def save_fix_requests_to_gsheet():
    """บันทึกข้อมูลจาก session_state ไปยัง Google Sheet (รวมกับข้อมูลเดิม)"""
    try:
        sh = connect_gsheet()
        if not sh: return
        ws = sh.worksheet("FixRequests")
        
        headers = ['nurse', 'shift', 'dates', 'month', 'year', 'timestamp']
        
        # 1. อ่านข้อมูลเดิมจาก Google Sheet
        existing_records = ws.get_all_records()
        
        # 2. สร้าง set ของข้อมูลที่มีอยู่แล้ว
        existing_keys = set()
        for r in existing_records:
            key = (str(r.get('nurse', '')), str(r.get('shift', '')), str(r.get('dates', '')), str(r.get('month', '')), str(r.get('year', '')))
            existing_keys.add(key)
        
        # 3. หาข้อมูลใหม่
        new_records = []
        for item in st.session_state.fix_requests:
            dates_str = ",".join(map(str, item.get('dates', []))) if isinstance(item.get('dates'), list) else str(item.get('dates', ''))
            key = (str(item.get('nurse', '')), str(item.get('shift', '')), dates_str, str(item.get('month', '')), str(item.get('year', '')))
            if key not in existing_keys:
                new_records.append(item)
                existing_keys.add(key)
        
        # 4. Append ต่อท้าย
        if new_records:
            next_row = len(existing_records) + 2
            data = []
            for item in new_records:
                dates_str = ",".join(map(str, item.get('dates', []))) if isinstance(item.get('dates'), list) else str(item.get('dates', ''))
                row = [item.get('nurse', ''), item.get('shift', ''), dates_str, item.get('month', ''), item.get('year', ''), item.get('timestamp', '')]
                data.append(row)
            ws.update(values=data, range_name=f'A{next_row}')
            st.success(f"✅ เพิ่ม Fix Request ใหม่ {len(new_records)} รายการ")
        else:
            st.info("ℹ️ ไม่มี Fix Request ใหม่ที่ต้องบันทึก")
    except Exception as e: st.error(f"Error saving fix requests: {e}")

# --- Staffing Overrides ---
def load_staffing_overrides_from_gsheet():
    try:
        sh = connect_gsheet()
        if not sh: return []
        return sh.worksheet("StaffingOverrides").get_all_records()
    except: return []

def save_staffing_overrides_to_gsheet():
    try:
        sh = connect_gsheet()
        if not sh: return
        ws = sh.worksheet("StaffingOverrides")
        
        headers = ['start', 'end', 'shift', 'count', 'month', 'year', 'timestamp']
        
        # 1. อ่านข้อมูลเดิม
        existing_records = ws.get_all_records()
        
        # 2. สร้าง set ของข้อมูลที่มีอยู่
        existing_keys = set()
        for r in existing_records:
            key = (str(r.get('start', '')), str(r.get('end', '')), str(r.get('shift', '')), str(r.get('month', '')), str(r.get('year', '')))
            existing_keys.add(key)
        
        # 3. หาข้อมูลใหม่
        new_records = []
        for item in st.session_state.staffing_overrides:
            key = (str(item.get('start', '')), str(item.get('end', '')), str(item.get('shift', '')), str(item.get('month', '')), str(item.get('year', '')))
            if key not in existing_keys:
                new_records.append(item)
                existing_keys.add(key)
        
        # 4. Append ต่อท้าย
        if new_records:
            next_row = len(existing_records) + 2
            data = []
            for item in new_records:
                row = [item.get('start', ''), item.get('end', ''), item.get('shift', ''), item.get('count', ''), item.get('month', ''), item.get('year', ''), item.get('timestamp', '')]
                data.append(row)
            ws.update(values=data, range_name=f'A{next_row}')
            st.success(f"✅ เพิ่ม Staffing Override ใหม่ {len(new_records)} รายการ")
        else:
            st.info("ℹ️ ไม่มี Staffing Override ใหม่ที่ต้องบันทึก")
    except Exception as e: st.error(f"Error saving staffing overrides: {e}")

# --- Helper Function ---
def get_week_occurrence(day):
    return (day - 1) // 7 + 1

def diagnose_scheduling_issues(year, month, days_in_month, nurses, requests, staffing_overrides, enable_oc):
    """วิเคราะห์ปัญหาที่อาจทำให้จัดตารางไม่ได้"""
    issues = []
    
    # นับจำนวนคนที่ลาแต่ละวัน
    off_per_day = {d: [] for d in range(1, days_in_month + 1)}
    leave_per_day = {d: [] for d in range(1, days_in_month + 1)}
    
    for req in requests:
        if req.get('month') == month and req.get('year') == year:
            if req.get('nurse') in nurses:
                d = req.get('date')
                if 1 <= d <= days_in_month:
                    if req.get('type') == 'Off':
                        off_per_day[d].append(req['nurse'])
                    elif req.get('type') == 'Leave_Train':
                        leave_per_day[d].append(req['nurse'])
    
    # ตรวจสอบแต่ละวัน
    for d in range(1, days_in_month + 1):
        weekday = calendar.weekday(year, month, d)
        is_special_day = weekday >= 5 or is_holiday(year, month, d)
        
        # จำนวนคนที่ว่าง (ไม่ได้ลา Off หรือ L_T)
        unavailable = set(off_per_day[d]) | set(leave_per_day[d])
        available = [n for n in nurses if n not in unavailable]
        available_count = len(available)
        
        # ความต้องการขั้นต่ำ
        req_m = 4 if is_special_day else 3  # เวรเช้า
        req_s = 2  # เวรบ่าย  
        req_n = 1  # เวรดึก
        
        # ตรวจสอบ Override
        for override in staffing_overrides:
            if override.get('month') == month and override.get('year') == year:
                if override.get('start', 1) <= d <= override.get('end', days_in_month):
                    if override.get('shift') == 'N':
                        req_n = override.get('count', 1)
                    elif override.get('shift') == 'S':
                        req_s = override.get('count', 2)
        
        # OC ต้องการอีก 1 คน (ถ้าเปิดใช้งาน และเป็นวันที่ 1-10)
        req_oc = 1 if enable_oc and d <= 10 else 0
        
        # ต้องการอย่างน้อย M + S + N + OC (แม้จะซ้อนได้บางส่วน แต่ใช้ประมาณการ)
        min_needed = req_m + req_s + req_n + req_oc
        
        # ER1 Fix: ศุกร์ M, อื่นๆ Off
        er1_available_for_m = 1 if 'ER1' in available and weekday == 4 else 0
        
        # คนที่ลา/ประชุม นับเป็น M ได้
        leave_count = len(leave_per_day[d])
        
        # จำนวนคนที่ต้องการทำเวรจริง (หลังหักคนลา)
        need_for_m = max(0, req_m - leave_count - er1_available_for_m)
        need_for_sn = req_s + req_n
        
        # คนที่ว่างหลังหัก ER1 (ER1 ทำได้แค่ M ศุกร์)
        workers = [n for n in available if n != 'ER1']
        
        if len(off_per_day[d]) > 0 and available_count < need_for_m + need_for_sn:
            day_type = "ส-อา/นักขัตฤกษ์" if is_special_day else "วันธรรมดา"
            issues.append({
                'day': d,
                'weekday': ['จ','อ','พ','พฤ','ศ','ส','อา'][weekday],
                'type': day_type,
                'off_nurses': off_per_day[d],
                'leave_nurses': leave_per_day[d],
                'available': available_count,
                'needed_m': req_m,
                'needed_s': req_s,
                'needed_n': req_n,
                'needed_oc': req_oc,
                'er1_status': 'หยุดเสาร์-อาทิตย์/นักขัตฤกษ์' if 'ER1' in available and is_special_day and weekday != 4 else 'พร้อม'
            })
    
    return issues

def generate_diagnosis_md(issues, total_nurses=10):
    """สร้างรายงานปัญหาแบบละเอียด"""
    md = []
    
    # Group issues by exact same problem type for summary? No, user wants case by case.
    
    md.append("### ⚠️ พบปัญหาในการจัดเวร")
    md.append("ระบบไม่สามารถจัดตารางได้เนื่องจาก **คนไม่พอ** ในบางวันครับ")
    md.append("")
    
    for issue in issues:
        d = issue['day']
        wd = issue['weekday']
        
        # Calculate totals
        total_off = len(issue['off_nurses']) + len(issue['leave_nurses'])
        
        # Special check for ER1 implicit off
        er1_note = ""
        er1_off = 0
        if issue['er1_status'].startswith('หยุด'):
             er1_note = f"\n*   **ER1:** {issue['er1_status']} (ตามเงื่อนไข Fix) -> รวมเป็นคนหยุด {total_off + 1} คน"
             er1_off = 1
        
        needed_total = issue['needed_m'] + issue['needed_s'] + issue['needed_n'] + issue['needed_oc']
        available_real = issue['available'] - er1_off
        missing = needed_total - available_real
        
        # Format the block
        md.append(f"#### 📅 วันที่ {d} ({wd})")
        
        # List who is off/leave
        who_off = []
        if issue['off_nurses']:
            who_off.append(f"ขอหยุด: {', '.join(issue['off_nurses'])}")
        if issue['leave_nurses']:
            who_off.append(f"ลา/ประชุม: {', '.join(issue['leave_nurses'])}")
            
        md.append(f"*   **คนขอหยุด/ลา:** {total_off} คน ({'; '.join(who_off)}){er1_note}")
        md.append(f"*   **เหลือคนทำงาน:** {total_nurses} - {total_off + er1_off} = **{available_real} คน**")
        md.append(f"*   **ความต้องการขั้นต่ำ:** เช้า({issue['needed_m']}) + บ่าย({issue['needed_s']}) + ดึก({issue['needed_n']}) = **{needed_total} คน**")
        md.append(f"*   **ผลลัพธ์:** คนขาด {missing} คน (มี {available_real} แต่ต้องการ {needed_total}) ทำให้จัดไม่ได้ครับ")
        md.append("")
    
    md.append("### 💡 วิธีแก้ไข")
    md.append("*   **ลดคนลา:** ในวันที่มีปัญหา ต้องมีคนขอหยุด/ลาให้น้อยลง เพื่อให้เหลือคนพอ")
    md.append("*   **ลดเวร:** ใช้เมนู **'👥 กำลังคนพิเศษ'** เพื่อลดจำนวนเวรเช้า (M) ในวันนั้นๆ ลง (เช่น จาก 4 เหลือ 3)")
    md.append("")
    
    return "\n".join(md)

def parse_previous_month_schedule(uploaded_file, nurses):
    """อ่านไฟล์ตารางเดือนก่อนและดึงข้อมูล 7 วันสุดท้าย"""
    if uploaded_file is None:
        return None
    
    try:
        # ลองอ่านไฟล์ด้วย encoding ต่างๆ
        df = None
        for encoding in ['utf-8', 'cp874', 'utf-16', 'tis-620']:
            try:
                df = pd.read_csv(uploaded_file, encoding=encoding)
                break
            except UnicodeDecodeError:
                continue
            except Exception as e:
                # ถ้าเป็น error อื่นๆ (เช่น separators) อาจจะข้ามไป
                continue
        
        if df is None:
            return None

        
        # หา column ที่เป็นตัวเลข (วันที่)
        date_cols = [col for col in df.columns if col.isdigit() or any(c.isdigit() for c in str(col))]
        
        if not date_cols:
            return None
        
        # เรียงลำดับและเอา 7 วันสุดท้าย
        # ลบ emoji ออกก่อนเรียง
        def extract_day(col):
            return int(''.join(filter(str.isdigit, str(col))))
        
        date_cols_sorted = sorted(date_cols, key=extract_day)
        last_7_days = date_cols_sorted[-7:] if len(date_cols_sorted) >= 7 else date_cols_sorted
        
        # สร้าง dict: nurse -> list of shifts (7 วันสุดท้าย)
        prev_data = {}
        for _, row in df.iterrows():
            nurse_col = str(row.iloc[0])  # Column แรกคือชื่อพยาบาล
            
            # Extract nurse ID - รองรับหลายรูปแบบ
            nurse_id = None
            
            # รูปแบบ 1: "ER1", "ER2", ... "ER10"
            # เรียงลำดับ nurse ตามความยาวจากมากไปน้อย เพื่อป้องกัน ER1 ไป match กับ ER10
            sorted_nurses = sorted(nurses, key=len, reverse=True)
            for n in sorted_nurses:
                if n in nurse_col:
                    nurse_id = n
                    break
            
            # รูปแบบ 2: "Nurse 1", "Nurse 2", ... "Nurse 10"
            if nurse_id is None:
                import re
                match = re.search(r'Nurse\s*(\d+)', nurse_col)
                if match:
                    num = int(match.group(1))
                    nurse_id = f'ER{num}'
            
            if nurse_id and nurse_id in nurses:
                shifts = []
                for col in last_7_days:
                    shift = str(row[col]) if col in row.index else ''
                    # แปลงกลับเป็น code (รองรับทั้งภาษาอังกฤษและภาษาไทย)
                    shift = shift.strip()
                    
                    # Thai abbreviations mapping
                    if shift == 'บ':  # บ่าย
                        shift = 'S'
                    elif shift == 'ช':  # เช้า
                        shift = 'M'
                    elif shift == 'ค':  # ดึก
                        shift = 'N'
                    elif shift == 'ดบ':  # ดึก+บ่าย (NS)
                        shift = 'NS'
                    elif shift in ['o', 'O', '']:  # Off
                        shift = 'O'
                    elif shift in ['VA', 'ประชุม']:  # ลา/ประชุม
                        shift = 'L_T'
                    elif shift in ['ncd', 'NCD']:
                        shift = 'O'
                    elif 'ลา' in shift or 'อบรม' in shift or 'ประชุม' in shift:
                        shift = 'L_T'
                    elif 'OC' in shift or '📞' in shift:
                        shift = 'OC'
                    elif shift in ['M', 'S', 'N', 'NS']:
                        pass  # ใช้ค่าเดิม
                    else:
                        shift = 'O'  # default
                    
                    prev_data[nurse_id] = prev_data.get(nurse_id, []) + [shift]
        
        return prev_data
    except Exception as e:
        return None

# --- 1. ฟังก์ชันจัดตาราง (Scheduler Engine) ---
def solve_schedule(year, month, days_in_month, nurses, requests, fix_requests=None, staffing_overrides=None, enable_oc=True, prev_month_data=None):
    if fix_requests is None:
        fix_requests = []
    if staffing_overrides is None:
        staffing_overrides = []
    
    model = cp_model.CpModel()
    
    # เพิ่ม NS (บ่าย+ดึก 16 ชม.) เป็น OT shift, OC = On-Call Standby
    shifts = ['S', 'M', 'N', 'O', 'L_T', 'NS', 'OC'] 
    work_shifts = ['S', 'M', 'N', 'L_T', 'NS']  # NS นับเป็นวันทำงาน (OC ไม่นับ)
    
    # กลุ่มพยาบาลสำหรับเวร OC (On-Call วันที่ 1-10)
    oc_hard_ban = ['ER1', 'ER7']      # Hard: ห้ามเด็ดขาด
    oc_soft_avoid = ['ER4', 'ER8']    # Soft: ขอเลี่ยง (จัดให้คนอื่นก่อน)
    oc_normal_pool = [n for n in nurses if n not in oc_hard_ban + oc_soft_avoid]

    shifts_var = {}
    for n in nurses:
        for d in range(1, days_in_month + 1):
            for s in shifts:
                shifts_var[(n, d, s)] = model.NewBoolVar(f'shift_{n}_{d}_{s}')

    # ==========================================
    # 0. Cross-Month Constraints (ข้อมูลจากเดือนก่อน)
    # ==========================================
    if prev_month_data:
        for n in nurses:
            if n in prev_month_data and len(prev_month_data[n]) >= 1:
                last_shift = prev_month_data[n][-1]  # เวรวันสุดท้ายของเดือนก่อน
                
                # ห้าม N/NS → M ข้ามเดือน (ทำดึกเดือนก่อน → ห้ามเช้าวันที่ 1)
                if last_shift in ['N', 'NS']:
                    model.Add(shifts_var[(n, 1, 'M')] == 0)
                
                # ห้าม S → N/NS ข้ามเดือน (ทำบ่ายเดือนก่อน → ห้ามดึกวันที่ 1)
                if last_shift == 'S':
                    model.Add(shifts_var[(n, 1, 'N')] == 0)
                    model.Add(shifts_var[(n, 1, 'NS')] == 0)
                
                # ห้าม Off → N/NS ข้ามเดือน
                if last_shift == 'O':
                    model.Add(shifts_var[(n, 1, 'N')] == 0)
                    model.Add(shifts_var[(n, 1, 'NS')] == 0)
                    model.Add(shifts_var[(n, 1, 'OC')] == 0)
            
            # นับวันทำงานต่อเนื่องข้ามเดือน (กฎ 7 วันใน 8 วัน)
            if n in prev_month_data and len(prev_month_data[n]) >= 7:
                # นับจำนวนวันทำงานติดกันจากท้ายเดือนก่อน
                consecutive_work = 0
                for s in reversed(prev_month_data[n]):
                    if s in ['S', 'M', 'N', 'L_T', 'NS']:
                        consecutive_work += 1
                    else:
                        break  # หยุดนับเมื่อเจอวันหยุด
                
                # ถ้าทำงานติดกัน X วันท้ายเดือนก่อน → วันแรกๆ ของเดือนใหม่ต้องหยุด
                if consecutive_work >= 7:
                    # ทำงาน 7 วันติด → วันที่ 1 ต้องหยุด (Hard)
                    for work_s in ['S', 'M', 'N', 'NS']:
                        model.Add(shifts_var[(n, 1, work_s)] == 0)
                elif consecutive_work >= 6:
                    # ทำงาน 6 วันติด → วันที่ 1-2 ต้องมีหยุดอย่างน้อย 1 วัน
                    model.Add(
                        shifts_var[(n, 1, 'O')] + shifts_var[(n, 2, 'O')] >= 1
                    )
                elif consecutive_work >= 5:
                    # ทำงาน 5 วันติด → วันที่ 1-3 ต้องมีหยุดอย่างน้อย 1 วัน  
                    model.Add(
                        shifts_var[(n, 1, 'O')] + shifts_var[(n, 2, 'O')] + shifts_var[(n, 3, 'O')] >= 1
                    )

    # ==========================================
    # 🎯 คำนวณเป้าหมายวันทำการ (Auto Calculate Work Days)
    # ==========================================
    
    # 1. นับวันหยุด "เสาร์-อาทิตย์"
    weekends = 0
    for d in range(1, days_in_month + 1):
        if calendar.weekday(year, month, d) >= 5:  # 5=เสาร์, 6=อาทิตย์
            weekends += 1
            
    # 2. นับวันหยุด "นักขัตฤกษ์" (เฉพาะที่ตรงกับ จันทร์-ศุกร์)
    holidays_weekday = 0
    holiday_list = THAI_HOLIDAYS.get(year, {}).get(month, [])
    for d in holiday_list:
        if calendar.weekday(year, month, d) < 5:  # เฉพาะ จ-ศ
            holidays_weekday += 1
            
    # 3. สรุปเป้าหมายวันทำงานปกติ (Target)
    target_work_days = days_in_month - (weekends + holidays_weekday)
    
    # แสดงค่าใน Terminal เพื่อเช็คความถูกต้อง
    print(f"[TARGET] Month {month}/{year}: {days_in_month} days, holidays {weekends+holidays_weekday}, target work = {target_work_days} days")
    
    # ==========================================
    # 1. กฎพื้นฐานและกำลังคน (Hard Constraints)
    # ==========================================
    for d in range(1, days_in_month + 1):
        weekday = calendar.weekday(year, month, d)
        is_weekend = weekday >= 5 

        # สถานะเดียวต่อวัน
        for n in nurses:
            model.Add(sum(shifts_var[(n, d, s)] for s in shifts) == 1)

        # กำลังคน (NS นับเป็นทั้ง S และ N)
        # วันหยุดนักขัตฤกษ์ ต้องการคนเท่าวันเสาร์-อาทิตย์ (M=4)
        is_special_day = is_weekend or is_holiday(year, month, d)
        
        # ค่า Default: N+NS >= 1, S+NS >= 2
        n_req = 1
        s_req = 2
        
        # ตรวจสอบ Override จาก staffing_overrides
        for override in staffing_overrides:
            if override.get('month') == month and override.get('year') == year:
                if override.get('start', 1) <= d <= override.get('end', days_in_month):
                    if override.get('shift') == 'N':
                        n_req = override.get('count', 1)
                    elif override.get('shift') == 'S':
                        s_req = override.get('count', 2)
        
        # N + NS >= n_req (RELAXED - อย่างน้อย n_req คน)
        model.Add(sum(shifts_var[(n, d, 'N')] + shifts_var[(n, d, 'NS')] for n in nurses) >= n_req)
        # S + NS >= s_req (RELAXED - อย่างน้อย s_req คน)
        model.Add(sum(shifts_var[(n, d, 'S')] + shifts_var[(n, d, 'NS')] for n in nurses) >= s_req)
        req_m = 4 if is_special_day else 3  # เสาร์-อาทิตย์ หรือ วันหยุดนักขัตฤกษ์ = 4 คน
        model.Add(sum(shifts_var[(n, d, 'M')] for n in nurses) >= req_m)  # RELAXED

    # กฎการสลับเวร
    for n in nurses:
        for d in range(1, days_in_month):
            # ห้าม S -> N (บ่ายตามด้วยดึก)
            model.Add(shifts_var[(n, d, 'S')] + shifts_var[(n, d + 1, 'N')] <= 1)
            model.Add(shifts_var[(n, d, 'S')] + shifts_var[(n, d + 1, 'NS')] <= 1)
            # ห้าม N -> S (ดึกตามด้วยบ่าย)
            model.Add(shifts_var[(n, d, 'N')] + shifts_var[(n, d + 1, 'S')] <= 1)
            model.Add(shifts_var[(n, d, 'NS')] + shifts_var[(n, d + 1, 'S')] <= 1)
    
    # ห้าม S -> M -> N (บ่าย -> เช้า -> ดึก ใน 3 วันติด)
    for n in nurses:
        for d in range(1, days_in_month - 1):
            # ถ้า S วันที่ d และ M วันที่ d+1 → ห้าม N วันที่ d+2
            model.Add(shifts_var[(n, d, 'S')] + shifts_var[(n, d + 1, 'M')] + shifts_var[(n, d + 2, 'N')] <= 2)
            model.Add(shifts_var[(n, d, 'S')] + shifts_var[(n, d + 1, 'M')] + shifts_var[(n, d + 2, 'NS')] <= 2)
    
    # S -> O -> N (บ่าย -> หยุด -> ดึก = เสียวันหยุดฟรี) - SOFT CONSTRAINT
    # เหตุผล: S เลิกเที่ยงคืน, O ไม่ได้พักจริง, N ต้องมาเที่ยงคืน
    s_o_n_penalty = []
    for n in nurses:
        for d in range(1, days_in_month - 1):
            # สร้าง penalty แทน hard constraint
            pen1 = model.NewBoolVar(f'son_pen_{n}_{d}')
            model.Add(shifts_var[(n, d, 'S')] + shifts_var[(n, d + 1, 'O')] + shifts_var[(n, d + 2, 'N')] <= 2 + pen1)
            s_o_n_penalty.append(pen1)
            
            pen2 = model.NewBoolVar(f'sons_pen_{n}_{d}')
            model.Add(shifts_var[(n, d, 'S')] + shifts_var[(n, d + 1, 'O')] + shifts_var[(n, d + 2, 'NS')] <= 2 + pen2)
            s_o_n_penalty.append(pen2)

    # ==========================================
    # กฎเวรดึก (N) เดี่ยว - ต้องทำงานก่อนดึก และหยุดหลังดึก
    # ==========================================
    o_before_n_penalty = []  # Soft: O → N ควรหลีกเลี่ยง
    n_skip_day_penalty = []  # Soft: N-O-N ควรหลีกเลี่ยง
    
    for n in nurses:
        # 1. ห้าม N-N, NS-NS, N-NS, NS-N (ดึกติดกัน) - HARD (ต้องบังคับ)
        for d in range(1, days_in_month):
            model.Add(shifts_var[(n, d, 'N')] + shifts_var[(n, d + 1, 'N')] <= 1)
            model.Add(shifts_var[(n, d, 'NS')] + shifts_var[(n, d + 1, 'NS')] <= 1)
            model.Add(shifts_var[(n, d, 'N')] + shifts_var[(n, d + 1, 'NS')] <= 1)
            model.Add(shifts_var[(n, d, 'NS')] + shifts_var[(n, d + 1, 'N')] <= 1)
        
        # 2. O-N, O-NS (ควรทำงานก่อนดึก) - SOFT (ลดจุด แต่ยอมได้ถ้าจำเป็น)
        for d in range(1, days_in_month):
            # สร้างตัวแปร penalty แทน hard constraint
            penalty_on = model.NewBoolVar(f'o_n_penalty_{n}_{d}')
            model.Add(shifts_var[(n, d, 'O')] + shifts_var[(n, d + 1, 'N')] <= 1 + penalty_on)
            o_before_n_penalty.append(penalty_on)
            
            penalty_ons = model.NewBoolVar(f'o_ns_penalty_{n}_{d}')
            model.Add(shifts_var[(n, d, 'O')] + shifts_var[(n, d + 1, 'NS')] <= 1 + penalty_ons)
            o_before_n_penalty.append(penalty_ons)
        
        # 3. N-O-N, NS-O-NS (ควรหลีกเลี่ยงดึกสลับวัน) - SOFT
        for d in range(1, days_in_month - 1):
            pen1 = model.NewBoolVar(f'non_pen_{n}_{d}')
            model.Add(shifts_var[(n, d, 'N')] + shifts_var[(n, d + 2, 'N')] <= 1 + pen1)
            n_skip_day_penalty.append(pen1)
            
            pen2 = model.NewBoolVar(f'nson_pen_{n}_{d}')
            model.Add(shifts_var[(n, d, 'NS')] + shifts_var[(n, d + 2, 'NS')] <= 1 + pen2)
            n_skip_day_penalty.append(pen2)
            
            pen3 = model.NewBoolVar(f'n_ns_pen_{n}_{d}')
            model.Add(shifts_var[(n, d, 'N')] + shifts_var[(n, d + 2, 'NS')] <= 1 + pen3)
            n_skip_day_penalty.append(pen3)
            
            pen4 = model.NewBoolVar(f'ns_n_pen_{n}_{d}')
            model.Add(shifts_var[(n, d, 'NS')] + shifts_var[(n, d + 2, 'N')] <= 1 + pen4)
            n_skip_day_penalty.append(pen4)

    # ==========================================
    # กฎเวร NS (บ่าย+ดึก 16 ชม.) - OT Shift (ลดความซับซ้อน)
    # ==========================================
    nurses_for_ns = [n for n in nurses if n not in ['ER1', 'ER7']]  # ยกเว้น ER1, ER7
    
    for n in nurses_for_ns:
        # NS ต้องห่างกันอย่างน้อย 4 วัน (ง่ายขึ้น)
        for d in range(1, days_in_month - 3):
            model.Add(shifts_var[(n, d, 'NS')] + shifts_var[(n, d + 1, 'NS')] + 
                     shifts_var[(n, d + 2, 'NS')] + shifts_var[(n, d + 3, 'NS')] + 
                     shifts_var[(n, d + 4, 'NS')] <= 1)
        
        # หลัง NS ต้อง Off วันถัดไป (1 วัน - hard)
        for d in range(1, days_in_month):
            # NS วันที่ d → วันที่ d+1 ห้ามทำงาน (ต้องเป็น O)
            for work_s in ['S', 'M', 'N', 'NS']:
                model.Add(shifts_var[(n, d, 'NS')] + shifts_var[(n, d + 1, work_s)] <= 1)
    
    # ER1 และ ER7 ห้ามทำ NS
    for d in range(1, days_in_month + 1):
        model.Add(shifts_var[('ER1', d, 'NS')] == 0)
        model.Add(shifts_var[('ER7', d, 'NS')] == 0)
    
    # ==========================================
    # กระจาย NS เท่าเทียม แต่ลดให้น้อยที่สุด (NS = ทางเลือกสุดท้าย)
    # ==========================================
    # NS เป็น optional ไม่บังคับ แต่ถ้าต้องใช้ให้กระจายเท่าๆ กัน
    
    for n in nurses_for_ns:
        ns_total = sum(shifts_var[(n, d, 'NS')] for d in range(1, days_in_month + 1))
        # ไม่บังคับขั้นต่ำ แต่จำกัดสูงสุด 2 เวร/เดือน (ลดลงจาก 3)
        model.Add(ns_total <= 2)  # สูงสุด 2 เวร NS/เดือน

    # ==========================================
    # ทำงานต่อเนื่อง: ห้ามเกิน 6 วันติด (HARD), ยอมให้ 7 วันถ้าจำเป็น (SOFT)
    # ==========================================
    seven_day_streak_penalty = []
    
    for n in nurses:
        # กรณีปกติ: ตรวจสอบทุกช่วง 8 วันติดต่อกัน
        for d in range(1, days_in_month - 6):  # d ถึง d+7 (8 วัน)
            # HARD: ห้ามเกิน 7 วันทำงานใน 8 วันติดต่อกัน
            model.Add(sum(sum(shifts_var[(n, d + k, s)] for s in work_shifts) for k in range(8)) <= 7)
        
        # เพิ่ม constraint สำหรับวันท้ายเดือน (เช็คย้อนหลัง)
        for d in range(8, days_in_month + 1):
            # ตรวจสอบ 8 วันย้อนหลัง (d-7 ถึง d)
            model.Add(sum(sum(shifts_var[(n, d - k, s)] for s in work_shifts) for k in range(8)) <= 7)
        
        # SOFT: prefer ไม่เกิน 6 วันติด
        for d in range(1, days_in_month - 5):  # d ถึง d+6 (7 วัน)
            work_in_7_days = sum(sum(shifts_var[(n, d + k, s)] for s in work_shifts) for k in range(7))
            is_7_day_streak = model.NewBoolVar(f'7day_streak_{n}_{d}')
            model.Add(work_in_7_days <= 6 + is_7_day_streak)
            model.Add(work_in_7_days >= 7 * is_7_day_streak)
            seven_day_streak_penalty.append(is_7_day_streak)
        
        # กรณีข้ามเดือน: วันที่ 1-7 ต้องรวมข้อมูลจากเดือนก่อน
        if prev_month_data and n in prev_month_data:
            prev_shifts = prev_month_data[n]  # 7 วันสุดท้ายของเดือนก่อน
            
            for d in range(1, min(8, days_in_month + 1)):
                days_from_prev = max(0, 8 - d)  # จำนวนวันที่ต้องดูจากเดือนก่อน
                
                if days_from_prev > 0 and days_from_prev <= len(prev_shifts):
                    # นับวันทำงานจากเดือนก่อน
                    prev_work_count = sum(
                        1 for s in prev_shifts[-days_from_prev:] 
                        if s in ['S', 'M', 'N', 'L_T', 'NS']
                    )
                    
                    # จำกัดวันทำงานเดือนนี้ให้ไม่เกิน 7 - prev_work_count
                    max_curr_work = max(0, 7 - prev_work_count)
                    model.Add(
                        sum(sum(shifts_var[(n, k, s)] for s in work_shifts) 
                            for k in range(1, d + 1)) <= max_curr_work
                    )
    
    # ป้องกัน NS หลังทำงานติด 6 วัน (เพราะ NS = 2 เวร จะทำให้เกิน 7 เวร)
    for n in nurses_for_ns:
        for d in range(7, days_in_month + 1):
            # ถ้า 6 วันก่อนหน้าทำงานทั้งหมด แล้ววันนี้เป็น NS = 8 เวร (เกิน!)
            # ดังนั้น ถ้าจะทำ NS ต้องมี Off อย่างน้อย 1 วันใน 6 วันก่อนหน้า
            prev_work = sum(sum(shifts_var[(n, d - k, s)] for s in ['S', 'M', 'N', 'NS']) for k in range(1, 7))
            # ถ้าทำงาน 6 วันก่อนหน้า (prev_work=6) แล้ว NS ห้าม
            model.Add(prev_work + shifts_var[(n, d, 'NS')] <= 6)

    # ==========================================
    # กฎเวร OC (On-Call Standby) - เฉพาะวันที่ 1-10
    # ==========================================
    oc_avoid_penalty = []  # สำหรับ Soft Constraint ER4, ER8
    
    if enable_oc:
        # วันที่ 1-10 ต้องมี OC อย่างน้อย 1 คน
        for d in range(1, min(11, days_in_month + 1)):
            model.Add(sum(shifts_var[(n, d, 'OC')] for n in nurses) >= 1)
        
        # วันที่ 11+ ห้ามมี OC
        for d in range(11, days_in_month + 1):
            for n in nurses:
                model.Add(shifts_var[(n, d, 'OC')] == 0)
        
        # ER1, ER7 ห้ามทำ OC เด็ดขาด (Hard Constraint)
        for d in range(1, days_in_month + 1):
            for n in oc_hard_ban:
                model.Add(shifts_var[(n, d, 'OC')] == 0)
        
        # กฎ OC - OC ต้องห่างกันอย่างน้อย 3 วัน
        for n in nurses: # RE-ENABLED Partial
            for d in range(1, min(10, days_in_month)):
            #     # ห้าม OC ติดกัน (OC-OC)
                model.Add(shifts_var[(n, d, 'OC')] + shifts_var[(n, d + 1, 'OC')] <= 1)
                # ห้าม OC แล้วเช้า (OC-M)
                model.Add(shifts_var[(n, d, 'OC')] + shifts_var[(n, d + 1, 'M')] <= 1)
                # ห้าม Off แล้ว OC (O-OC) -- RELAXED
                # model.Add(shifts_var[(n, d, 'O')] + shifts_var[(n, d + 1, 'OC')] <= 1)
            
            # OC ต้องห่างกันอย่างน้อย 3 วัน (ในช่วง 1-10)
            # แก้ไข: Loop ถึงแค่วันที่ d+3 ยังอยู่ในเดือน
            for d in range(1, min(8, days_in_month - 3 + 1)):
                model.Add(shifts_var[(n, d, 'OC')] + shifts_var[(n, d + 1, 'OC')] + 
                         shifts_var[(n, d + 2, 'OC')] + shifts_var[(n, d + 3, 'OC')] <= 1)
        
        # ER4, ER8 ขอเลี่ยง (Soft Constraint - ลด penalty ใน objective)
        for d in range(1, min(11, days_in_month + 1)):
            for n in oc_soft_avoid:
                oc_avoid_penalty.append(shifts_var[(n, d, 'OC')])
    else:
        # ถ้าปิด OC → ห้ามทุกคนทำ OC
        for d in range(1, days_in_month + 1):
            for n in nurses:
                model.Add(shifts_var[(n, d, 'OC')] == 0)

    # ==========================================
    # 2. เงื่อนไขรายบุคคล (Preferences & Fix)
    # ==========================================
    preferred_constraints = [] 
    er7_m_shifts = []
    er7_sn_shifts = []

    for d in range(1, days_in_month + 1):
        wd = calendar.weekday(year, month, d)
        week_occurrence = get_week_occurrence(d)

        # ER1 (Hard Fix): จ-พฤ NCD, ศุกร์ M, ส-อา หยุด, วันหยุดนักขัตฤกษ์ หยุด
        is_hol = is_holiday(year, month, d)
        if is_hol or wd in [5, 6]:  # วันหยุดนักขัตฤกษ์ หรือ ส-อา = หยุด
            model.Add(shifts_var[('ER1', d, 'O')] == 1)
        elif wd in [0, 1, 2, 3]:  # จ-พฤ = NCD (แสดงเป็น O ในตาราง)
            model.Add(shifts_var[('ER1', d, 'O')] == 1)
        elif wd == 4:  # ศุกร์ = M
            model.Add(shifts_var[('ER1', d, 'M')] == 1)

        # ER3 (Soft Fix): วันพุธ พฤหัส ทุกสัปดาห์ (เท่าที่ได้ ไม่เบียดเบียนผู้อื่น)
        if wd in [2, 3]:  # วันพุธ = 2, วันพฤหัส = 3
            preferred_constraints.append(shifts_var[('ER3', d, 'M')])

        # [REMOVED] ER5 & ER10 pattern - User จะใช้ฟังก์ชัน Fix เวรแทน

        # [REMOVED] ER9 Hardcode - ใช้ fix_requests จาก UI แทน
        # ตอนนี้ ER9 (และคนอื่น) สามารถขอเวร Fix ผ่าน UI ได้

        er7_m_shifts.append(shifts_var[('ER7', d, 'M')])
        er7_sn_shifts.append(shifts_var[('ER7', d, 'S')])
        er7_sn_shifts.append(shifts_var[('ER7', d, 'N')])

    # ER7 (Contract - RELAXED): 
    # - เช้า+ลา/อบรม ≈ 10 เวร (ตามสัญญา ±1)
    # - บ่าย+ดึก ≈ 10 เวร (ตามสัญญา ±1)
    er7_lt_shifts = [shifts_var[('ER7', d, 'L_T')] for d in range(1, days_in_month + 1)]
    model.Add(sum(er7_m_shifts) + sum(er7_lt_shifts) >= 9)   # M + ลา/ประชุม >= 9
    model.Add(sum(er7_m_shifts) + sum(er7_lt_shifts) <= 11)  # M + ลา/ประชุม <= 11
    model.Add(sum(er7_sn_shifts) >= 9)   # S+N >= 9
    model.Add(sum(er7_sn_shifts) <= 11)  # S+N <= 11
    
    # ER7 ดึก (N) สูงสุด 4 เวร/เดือน
    er7_n_shifts = [shifts_var[('ER7', d, 'N')] for d in range(1, days_in_month + 1)]
    model.Add(sum(er7_n_shifts) <= 4)  # N ไม่เกิน 4

    # ==========================================
    # 2.1 ขอเวร Fix จาก UI (Dynamic Shift Fix Requests)
    # ==========================================
    for req in fix_requests:
        if req.get('month') == month and req.get('year') == year:
            nurse = req.get('nurse')
            shift = req.get('shift')
            dates = req.get('dates', [])
            if nurse in nurses and shift in ['M', 'S', 'N']:
                for d in dates:
                    if 1 <= d <= days_in_month:
                        preferred_constraints.append(shifts_var[(nurse, d, shift)])

    # สร้าง set ของ (nurse, date) ที่อนุญาตให้มี L_T
    allowed_lt = set()
    
    # จัดการคำขอ (Requests)
    for req in requests:
        # FIX: ตรวจสอบว่าเป็นของเดือน/ปี ปัจจุบันหรือไม่?
        # (ต้องใช้ .get() เผื่อข้อมูลเก่าไม่มี key month/year)
        req_month = req.get('month', month) 
        req_year = req.get('year', year)
        
        if req_month == month and req_year == year: # ต้องตรงกันเป๊ะๆ ถึงจะเอามาคิด
           # เพิ่ม .get() และเช็คว่ามี key หรือไม่
            if req.get('nurse') and req['nurse'] in nurses:
                if req['type'] == 'Off':
                    # SOFT: พยายามให้หยุดตามขอ แต่ถ้าคนไม่พอ อาจจัดเวรให้แทน
                    # น้ำหนักตามลำดับ: priority 1 = 10 repeats, priority 2 = 9, ... priority 10 = 1
                    priority = req.get('priority', 1)
                    weight = max(1, 11 - priority)  # priority 1 → weight 10, priority 10 → weight 1
                    for _ in range(weight):
                        preferred_constraints.append(shifts_var[(req['nurse'], req['date'], 'O')])
                elif req['type'] in ['Leave_Train', 'Leave', 'Train']:  # รองรับทั้งแบบเก่าและใหม่
                    model.Add(shifts_var[(req['nurse'], req['date'], 'L_T')] == 1)
                    allowed_lt.add((req['nurse'], req['date']))
    
    # FIX: ห้าม L_T ถ้าไม่มีคำขอลา - ป้องกัน solver จัดเวร "ลา/อบรม" เองโดยไม่มีคำขอ
    for n in nurses:
        for d in range(1, days_in_month + 1):
            if (n, d) not in allowed_lt:
                model.Add(shifts_var[(n, d, 'L_T')] == 0)

    # ==========================================
    # 3. ระบบเกลี่ยเวร (Fairness Logic)
    # ==========================================
    
    # กลุ่มที่ต้องเกลี่ยเวรรวม (ตัด ER1 และ ER7 ออกจากเวรรวม เพราะมี M fix)
    rotating_nurses = [n for n in nurses if n not in ['ER1', 'ER7']]
    # กลุ่มที่ต้องเกลี่ยเวร S/N (รวม ER7 เพื่อให้ S และ N เท่ากัน)
    nurses_for_sn_fairness = [n for n in nurses if n not in ['ER1']]
    
    total_work_per_nurse = {}
    work_days_diff = []  # เก็บค่าความต่างจากเป้าหมาย
    
    for n in rotating_nurses:
        # นับรวม M, S, N, L_T (ไม่รวม NS เพราะ NS นับเป็น OT)
        total_work_per_nurse[n] = sum(sum(shifts_var[(n, d, s)] for s in ['M', 'S', 'N', 'L_T']) for d in range(1, days_in_month + 1))
        
        # Constraint: ให้วันทำงานใกล้เคียงเป้าหมาย (±2) - RELAXED
        # ใช้ target_work_days ที่คำนวณไว้ข้างบนแล้ว
        model.Add(total_work_per_nurse[n] >= target_work_days - 2)
        model.Add(total_work_per_nurse[n] <= target_work_days + 2)
        
        # สร้างตัวแปร Diff: |จำนวนวันที่ทำ - เป้าหมายเดือนนี้|
        diff = model.NewIntVar(0, days_in_month, f'diff_work_{n}')
        model.AddAbsEquality(diff, total_work_per_nurse[n] - target_work_days)
        work_days_diff.append(diff)

    # กฎบังคับ: เวรรวมห้ามต่างกันเกิน 1 (เพื่อความแฟร์สูงสุด)
    for n1 in rotating_nurses:
        for n2 in rotating_nurses:
            if n1 == n2: continue
            model.Add(total_work_per_nurse[n1] - total_work_per_nurse[n2] <= 1)
    
    # ==========================================
    # 3.0.1 NS Penalty: ทำให้ NS เป็นทางเลือกสุดท้าย
    # ==========================================
    ns_penalty = []
    for n in nurses_for_ns:
        for d in range(1, days_in_month + 1):
            ns_penalty.append(shifts_var[(n, d, 'NS')])
    
    # ==========================================
    # 3.0.2 Prefer เวรเช้าวันหยุด (แทน NS)
    # ==========================================
    # Prefer เวรเช้าวันหยุด (ส-อา, นักขัตฤกษ์) เพื่อเติมให้ครบเป้า แทนที่จะใช้ NS
    holiday_morning_bonus = []
    weekend_days = [d for d in range(1, days_in_month + 1) if calendar.weekday(year, month, d) >= 5]
    holiday_days = THAI_HOLIDAYS.get(year, {}).get(month, [])
    special_days = list(set(weekend_days + holiday_days))
    
    for n in rotating_nurses:
        for d in special_days:
            # ให้คะแนนบวกสำหรับ M ในวันหยุด (ทดแทน NS)
            holiday_morning_bonus.append(shifts_var[(n, d, 'M')])
    
    # ==========================================
    # 3.1 วันหยุดของแต่ละคน = วันหยุดของเดือน (เสาร์-อาทิตย์ + นักขัตฤกษ์)
    # ==========================================
    target_off_days = weekends + holidays_weekday  # ใช้ตัวแปรที่คำนวณไว้แล้วข้างบน
    
    # กำหนดให้ทุกคน (ยกเว้น ER1) มีวันหยุดใกล้เคียงกับ target (±1)
    for n in rotating_nurses:
        off_days = sum(shifts_var[(n, d, 'O')] for d in range(1, days_in_month + 1))
        # RELAXED: Off อนุญาตให้ต่างจาก target ได้ ±1 วัน
        model.Add(off_days >= target_off_days - 1)
        model.Add(off_days <= target_off_days + 1)
    
    # ==========================================
    # 3.2 เกลี่ยวันหยุดพิเศษ (ส-อา + นักขัตฤกษ์) ให้ทุกคนได้หมุนเวียนเท่ากัน
    # ==========================================
    # สร้าง list วันพิเศษ (ส-อา + นักขัตฤกษ์)
    special_days = [d for d in range(1, days_in_month + 1) 
                    if calendar.weekday(year, month, d) >= 5 or is_holiday(year, month, d)]
    
    # นับ special day offs ของแต่ละคน (เฉพาะ 'O' เท่านั้น ไม่นับ L_T)
    special_offs_per_nurse = {}
    for n in rotating_nurses:
        special_offs_per_nurse[n] = sum(shifts_var[(n, d, 'O')] for d in special_days)
    
    # RELAXED: เกลี่ยให้ต่างกันไม่เกิน 1 (ยืดหยุ่นขึ้น)
    for n1 in rotating_nurses:
        for n2 in rotating_nurses:
            if n1 != n2:
                model.Add(special_offs_per_nurse[n1] - special_offs_per_nurse[n2] <= 1)
    
    # ==========================================
    # 4. เกลี่ยเวรบ่าย (S) และดึก (N) แยกกัน ต่างกันไม่เกิน 1
    # ==========================================
    s_shifts_per_nurse = {}
    n_shifts_per_nurse = {}
    
    for n in nurses_for_sn_fairness:
        # NS นับเป็นทั้ง S และ N
        s_shifts_per_nurse[n] = sum(shifts_var[(n, d, 'S')] + shifts_var[(n, d, 'NS')] for d in range(1, days_in_month + 1))
        n_shifts_per_nurse[n] = sum(shifts_var[(n, d, 'N')] + shifts_var[(n, d, 'NS')] for d in range(1, days_in_month + 1))
    
    # เวรบ่าย (S) ต่างกันไม่เกิน 1
    for n1 in nurses_for_sn_fairness:
        for n2 in nurses_for_sn_fairness:
            if n1 == n2: continue
            model.Add(s_shifts_per_nurse[n1] - s_shifts_per_nurse[n2] <= 1)
    
    # เวรดึก (N) ต่างกันไม่เกิน 1
    for n1 in nurses_for_sn_fairness:
        for n2 in nurses_for_sn_fairness:
            if n1 == n2: continue
            model.Add(n_shifts_per_nurse[n1] - n_shifts_per_nurse[n2] <= 1)

    # ==========================================
    # 5. Soft Constraint: หลัง N ควร Off 2 วัน (ยกเว้น ER3)
    # ==========================================
    off_after_night_constraints = []
    nurses_for_off_rule = [n for n in nurses if n not in ['ER1', 'ER3']]  # ยกเว้น ER1 (สัญญาพิเศษ) และ ER3
    
    for n in nurses_for_off_rule:
        for d in range(1, days_in_month - 1):  # ต้องเหลือ 2 วันหลัง N
            # ถ้าทำ N วันที่ d แล้ว Off d+1 และ Off d+2 = ดี (ให้คะแนน)
            off_after_night_constraints.append(shifts_var[(n, d + 1, 'O')])
    
    # ==========================================
    # 6. Soft Constraint: พยายามให้หยุด 2 วันติดกัน (O-O)
    # ==========================================
    consecutive_off_constraints = []
    for n in rotating_nurses:
        for d in range(1, days_in_month):
            # ให้คะแนนเมื่อมี O-O ติดกัน
            consecutive_off_constraints.append(shifts_var[(n, d, 'O')] + shifts_var[(n, d + 1, 'O')])
    
    # ==========================================
    # 7. Soft Constraint: Separation - หลีกเลี่ยงคู่พยาบาลขึ้นเวรเดียวกัน
    # ==========================================
    separation_pairs = [('ER2', 'ER7')]  # คู่ที่ต้องการแยก
    separation_penalty = []
    
    for (n1, n2) in separation_pairs:
        if n1 in nurses and n2 in nurses:
            for d in range(1, days_in_month + 1):
                for shift in ['S', 'M', 'N']:  # เวรบ่าย, เช้า, ดึก
                    # สร้างตัวแปรสำหรับเช็คว่าซ้อนกันหรือไม่
                    same_shift = model.NewBoolVar(f'same_{n1}_{n2}_{d}_{shift}')
                    # ถ้าทั้งคู่ทำเวรเดียวกัน same_shift = 1
                    model.Add(shifts_var[(n1, d, shift)] + shifts_var[(n2, d, shift)] <= 1 + same_shift)
                    model.Add(shifts_var[(n1, d, shift)] + shifts_var[(n2, d, shift)] >= 2 * same_shift)
                    separation_penalty.append(same_shift)
    
    # รวม soft constraints ทั้งหมดเข้าด้วยกัน
    # น้ำหนัก: preferred_constraints (M fix) > separation > O→N penalty > N-O-N penalty > consecutive_off > off_after_night > oc_avoid
    model.Maximize(
        sum(preferred_constraints) * 100 + 
        sum(consecutive_off_constraints) * 5 +
        sum(off_after_night_constraints) +
        sum(holiday_morning_bonus) * 25 -  # โบนัสสำหรับ M ในวันหยุด (ทดแทน NS)
        sum(separation_penalty) * 30 -  # ลบคะแนนเมื่อ ER2-ER7 ซ้อนเวรกัน
        sum(oc_avoid_penalty) * 20 -  # ลบคะแนนเมื่อ ER4, ER8 ทำ OC
        sum(o_before_n_penalty) * 15 -  # ลบคะแนนเมื่อ O→N (ควรหลีกเลี่ยง)
        sum(n_skip_day_penalty) * 10 -  # ลบคะแนนเมื่อ N-O-N (ดึกสลับวัน)
        sum(ns_penalty) * 50 -  # Penalty สูงสำหรับ NS (ใช้เป็นทางเลือกสุดท้าย)
        sum(s_o_n_penalty) * 35 -  # Penalty สำหรับ S-O-N (เสียวันหยุดฟรี)
        sum(seven_day_streak_penalty) * 45 -  # Penalty สำหรับทำงาน 7 วันติด (prefer 6 วัน)
        sum(work_days_diff) * 40  # Penalty สำหรับวันทำงานที่ต่างจากเป้าหมาย
    )

    # Solve
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 20.0
    status = solver.Solve(model)

    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        schedule_data = []
        for n in nurses:
            # แสดง ID + ชื่อจริง
            display_name = f"{n} ({NURSE_NAMES.get(n, '')})"
            row = {'Nurse': display_name}
            for d in range(1, days_in_month + 1):
                for s in shifts:
                    if solver.Value(shifts_var[(n, d, s)]):
                        display = s if s not in ['O'] else ""
                        if s == 'L_T': display = "ลา/อบรม"
                        if s == 'NS': display = "NS"  # แสดง NS (บ่าย+ดึก)
                        if s == 'OC': display = "📞OC"  # แสดง On-Call
                        if n == 'ER1' and s == 'O': 
                            wd = calendar.weekday(year, month, d)
                            if wd in [0, 1, 2, 3]: display = "NCD"
                        row[str(d)] = display
                        break
            schedule_data.append(row)
        return pd.DataFrame(schedule_data)
    else:
        return None

# --- UI Setup ---
st.set_page_config(page_title="ระบบจัดตารางเวร ER_KPH v2.4", layout="wide")

# --- Password Protection ---
def check_password():
    """Returns True if password is correct"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    
    if st.session_state.authenticated:
        return True
    
    st.title("🔐 เข้าสู่ระบบ")
    password = st.text_input("รหัสผ่าน", type="password")
    
    if st.button("เข้าสู่ระบบ"):
        # เปลี่ยนรหัสผ่านตรงนี้ได้เลย
        if password == "er_kph2024":
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("❌ รหัสผ่านไม่ถูกต้อง")
    
    st.info("💡 ติดต่อผู้ดูแลระบบเพื่อขอรหัสผ่าน")
    return False

if not check_password():
    st.stop()

st.title("🏥 ระบบจัดตารางเวรพยาบาล (ER_KPH)")
st.caption("**v2.4** | 🆕 ผ่อนคลาย Constraints | Debug ตารางคำขอ | ขอเวร Fix ผ่าน UI | 🔐 Protected")

# Session State
if 'schedule_df' not in st.session_state: st.session_state.schedule_df = None
if 'requests' not in st.session_state: 
    st.session_state.requests = load_requests_from_gsheet()
if 'fix_requests' not in st.session_state:
    st.session_state.fix_requests = load_fix_requests_from_gsheet()
if 'staffing_overrides' not in st.session_state:
    st.session_state.staffing_overrides = load_staffing_overrides_from_gsheet()

# Sidebar
with st.sidebar:
    st.header("⚙️ ตั้งค่า")
    year = st.number_input("ปี (ค.ศ.)", 2024, 2030, 2025)
    month = st.selectbox("เดือน", range(1, 13), 10)
    _, days_in_month = calendar.monthrange(year, month)
    nurses_list = [f'ER{i}' for i in range(1, 11)]
    
    # ==========================================
    # 📊 Benchmark: เป้าหมายวันหยุดพิเศษ
    # ==========================================
    st.markdown("---")
    st.header("📊 เป้าหมายวันหยุด (Benchmark)")
    
    # คำนวณวันพิเศษทั้งหมด
    weekend_days_list = [d for d in range(1, days_in_month + 1) if calendar.weekday(year, month, d) >= 5]
    holiday_days_list = THAI_HOLIDAYS.get(year, {}).get(month, [])
    special_days_set = set(weekend_days_list + holiday_days_list)
    total_special_days = len(special_days_set)
    
    # จำนวนพยาบาลที่หมุนเวียน (ไม่รวม ER1)
    rotating_count = 9  # ER2-ER10
    
    # เป้าหมายวันหยุดพิเศษต่อคน
    target_special_off = total_special_days / rotating_count
    target_special_off_int = int(target_special_off)
    
    # แสดง Benchmark
    col_b1, col_b2 = st.columns(2)
    with col_b1:
        st.metric("🗓️ วันพิเศษในเดือน", f"{total_special_days} วัน", 
                  help=f"ส-อา: {len(weekend_days_list)}, นักขัตฤกษ์: {len(holiday_days_list)}")
    with col_b2:
        st.metric("🎯 เป้าหมายหยุดพิเศษ/คน", f"~{target_special_off_int} วัน",
                  help=f"= {total_special_days} วัน ÷ {rotating_count} คน (ไม่รวม ER1)")
    
    st.caption(f"💡 แต่ละคนควรได้หยุด ส-อา/นักขัตฤกษ์ ประมาณ **{target_special_off_int}-{target_special_off_int+1} วัน**")
    
    # ==========================================
    # 📋 คำแนะนำ Fix Request
    # ==========================================
    st.markdown("---")
    st.header("📋 คำแนะนำ Fix Request")
    
    # คำนวณจำนวน Fix ที่เหมาะสม
    weeks_in_month = (days_in_month + 6) // 7  # จำนวนสัปดาห์โดยประมาณ
    
    # คำแนะนำ: ไม่เกิน 2-3 คนต่อสัปดาห์ขอหยุด ส-อา
    st.info(f"""
    **💡 คำแนะนำเพื่อป้องกัน Infeasible:**
    
    📅 **ขอหยุด ส-อา/นักขัตฤกษ์:**
    - แนะนำ: ไม่เกิน **2-3 คน/สัปดาห์** ขอหยุดวัน ส-อา
    - ทั้งเดือน: ไม่เกิน **{min(weeks_in_month * 2, total_special_days)} คำขอ** หยุดวันพิเศษ
    
    📝 **ลา/ประชุม (นับเป็นเวรเช้า):**
    - แนะนำ: ไม่เกิน **2 คน/วัน** ลาพร้อมกัน
    - ทั้งเดือน: ไม่เกิน **{days_in_month // 3} วัน** ต่อคน
    
    📌 **ขอ Fix เวร (M/S/N):**
    - แนะนำ: ไม่เกิน **3 คน/สัปดาห์** ขอ Fix เวรธรรมดา
    - ทั้งเดือน: ไม่เกิน **{weeks_in_month * 3} คำขอ** Fix เวร
    """)
    
    # ตรวจสอบคำขอที่มีอยู่และแสดงคำเตือน
    if st.session_state.requests or st.session_state.fix_requests:
        # นับคำขอหยุดวันพิเศษ
        special_off_requests = []
        for req in st.session_state.requests:
            if req.get('month') == month and req.get('year') == year:
                if req.get('type') == 'Off' and req.get('date') in special_days_set:
                    special_off_requests.append(req)
        
        # นับคำขอลา/ประชุม
        leave_requests = []
        leave_by_day = {}  # เก็บว่าวันไหนมีใครลาบ้าง
        for req in st.session_state.requests:
            if req.get('month') == month and req.get('year') == year:
                if req.get('type') == 'Leave_Train':
                    leave_requests.append(req)
                    d = req.get('date')
                    if d not in leave_by_day:
                        leave_by_day[d] = []
                    leave_by_day[d].append(req.get('nurse'))
        
        # นับคำขอ Fix เวร
        fix_count = sum(1 for req in st.session_state.fix_requests 
                       if req.get('month') == month and req.get('year') == year)
        
        # แสดงสถานะปัจจุบัน
        st.markdown("**📊 สถานะคำขอปัจจุบัน:**")
        
        warning_shown = False
        
        # คำเตือนถ้าขอหยุดวันพิเศษเยอะ
        if len(special_off_requests) > weeks_in_month * 2:
            st.warning(f"⚠️ มีคำขอหยุดวัน ส-อา/นักขัตฤกษ์ **{len(special_off_requests)} คำขอ** (แนะนำไม่เกิน {weeks_in_month * 2})")
            warning_shown = True
            
            # แสดงรายละเอียดว่าใครขอ
            off_by_nurse = {}
            for req in special_off_requests:
                n = req.get('nurse')
                off_by_nurse[n] = off_by_nurse.get(n, 0) + 1
            
            if off_by_nurse:
                sorted_nurses = sorted(off_by_nurse.items(), key=lambda x: -x[1])
                st.caption(f"คนที่ขอหยุดวันพิเศษ: " + ", ".join([f"{n}({c})" for n, c in sorted_nurses]))
        
        # คำเตือนถ้าลา/ประชุมเยอะเกินในวันเดียวกัน
        days_with_many_leaves = [(d, nurses) for d, nurses in leave_by_day.items() if len(nurses) > 2]
        if days_with_many_leaves:
            for d, nurses in sorted(days_with_many_leaves):
                st.warning(f"⚠️ วันที่ **{d}** มีคนลา/ประชุม **{len(nurses)} คน**: {', '.join(nurses)} (แนะนำไม่เกิน 2 คน/วัน)")
            warning_shown = True
        
        # คำเตือนถ้ามีคนลาเยอะเกิน
        leave_by_nurse = {}
        for req in leave_requests:
            n = req.get('nurse')
            leave_by_nurse[n] = leave_by_nurse.get(n, 0) + 1
        
        max_leave_per_person = days_in_month // 3
        nurses_with_many_leaves = [(n, c) for n, c in leave_by_nurse.items() if c > max_leave_per_person]
        if nurses_with_many_leaves:
            for n, c in sorted(nurses_with_many_leaves, key=lambda x: -x[1]):
                st.warning(f"⚠️ **{n}** ลา/ประชุม **{c} วัน** (แนะนำไม่เกิน {max_leave_per_person} วัน/คน)")
            warning_shown = True
        
        # คำเตือนถ้า Fix เวรเยอะ
        if fix_count > weeks_in_month * 3:
            st.warning(f"⚠️ มีคำขอ Fix เวร **{fix_count} คำขอ** (แนะนำไม่เกิน {weeks_in_month * 3})")
            warning_shown = True
        
        if not warning_shown:
            leave_count = len(leave_requests)
            st.success(f"✅ หยุดวันพิเศษ: {len(special_off_requests)}/{weeks_in_month * 2} | ลา/ประชุม: {leave_count} | Fix: {fix_count}/{weeks_in_month * 3}")
    
    st.markdown("---")
    st.header("📞 เวร On-Call (OC)")
    enable_oc = st.checkbox("เปิดใช้งานเวร On-Call (วันที่ 1-10)", value=False, 
                            help="เวร OC = Standby ดึก 400 บาท/เวร | ER1,ER7 ห้ามทำ | ER4,ER8 ขอเลี่ยง")
    
    st.markdown("---")
    st.header("📂 ตารางเดือนก่อน")
    st.caption("Upload ไฟล์ gsheet ตารางเดือนก่อน เพื่อใช้กฎข้ามเดือน (N→M, S→N)")
    
    tab_upload, tab_manual = st.tabs(["📂 Upload gsheet", "✍️ Manual Entry"])
    prev_month_data = None

    with tab_upload:
        prev_month_file = st.file_uploader("เลือกไฟล์ gsheet", type=['gsheet'], key="prev_month_upload")
        
        if prev_month_file is not None:
            prev_month_data = parse_previous_month_schedule(prev_month_file, nurses_list)
            if prev_month_data:
                st.success(f"✅ อ่านข้อมูล {len(prev_month_data)} พยาบาล")
                # แสดงเวรวันสุดท้ายของแต่ละคน
                last_day_info = []
                for n, shifts in prev_month_data.items():
                    if shifts:
                        last_day_info.append({'พยาบาล': n, 'เวรวันสุดท้าย': shifts[-1]})
                if last_day_info:
                    st.dataframe(pd.DataFrame(last_day_info), hide_index=True)
            else:
                st.error("❌ ไม่สามารถอ่านไฟล์ได้ ตรวจสอบ Encoding หรือรูปแบบไฟล์")

    with tab_manual:
        st.caption("หรือกรอกข้อมูลเวร 7 วันสุดท้ายของเดือนก่อนด้วยตัวคุณเอง (M, S, N, O, NS)")
        
        # Init manual data
        if 'manual_prev_data' not in st.session_state:
            rows = []
            for n in nurses_list:
                rows.append({
                    'Nurse': n, 
                    'D-7': '', 'D-6': '', 'D-5': '', 'D-4': '', 'D-3': '', 'D-2': '', 'D-1 (วานนี้)': ''
                })
            st.session_state.manual_prev_data = pd.DataFrame(rows)

        edited_prev = st.data_editor(
            st.session_state.manual_prev_data, 
            key="manual_prev_editor",
            hide_index=True,
            num_rows="fixed"
        )
        st.session_state.manual_prev_data = edited_prev

        use_manual = st.checkbox("✅ ใช้ข้อมูลจากตาราง Manual นี้", value=False)
        
        if use_manual:
            # Convert DF to dict for solver
            prev_month_data = {}
            # Columns to read
            cols = ['D-7', 'D-6', 'D-5', 'D-4', 'D-3', 'D-2', 'D-1 (วานนี้)']
            for _, row in edited_prev.iterrows():
                nurse_id = row['Nurse']
                shifts = []
                for c in cols:
                    val = str(row[c]).strip().upper()
                    if val in ['M', 'S', 'N', 'NS', 'L_T', 'O', '']:
                        shifts.append(val if val else 'O')
                    else:
                        shifts.append('O') # Default to Off if invalid
                prev_month_data[nurse_id] = shifts
            st.info(f"ใช้ข้อมูล Manual Entry สำหรับ {len(prev_month_data)} พยาบาล")
    
    st.markdown("---")
    st.header("☁️ ดึงข้อมูลจาก Google Sheet")
    st.caption("👥 User กรอกข้อมูลใน Google Sheet โดยตรง → 🔄 Admin กดปุ่มดึงข้อมูล")
    
    # แสดง link ไปยัง Google Sheet
    st.markdown(f"📎 [เปิด Google Sheet]({SHEET_URL})")
    
    col_sync1, col_sync2 = st.columns(2)
    
    with col_sync1:
        if st.button("🔄 ดึงข้อมูลจาก Google Sheet", type="primary"):
            with st.spinner("กำลังดึงข้อมูล..."):
                try:
                    # โหลดข้อมูลใหม่จาก Google Sheet
                    new_requests = load_requests_from_gsheet()
                    new_fix_requests = load_fix_requests_from_gsheet()
                    new_staffing = load_staffing_overrides_from_gsheet()
                    
                    st.session_state.requests = new_requests
                    st.session_state.fix_requests = new_fix_requests
                    st.session_state.staffing_overrides = new_staffing
                    
                    st.success(f"✅ ดึงข้อมูลสำเร็จ! วันลา: {len(new_requests)}, Fix: {len(new_fix_requests)}, กำลังคน: {len(new_staffing)}")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ เกิดข้อผิดพลาด: {e}")
    
    with col_sync2:
        if st.button("📤 บันทึกไปยัง Google Sheet"):
            with st.spinner("กำลังบันทึก..."):
                try:
                    save_requests_to_gsheet()
                    save_fix_requests_to_gsheet()
                    save_staffing_overrides_to_gsheet()
                    st.success("✅ บันทึกสำเร็จ!")
                except Exception as e:
                    st.error(f"❌ เกิดข้อผิดพลาด: {e}")
    
    # แสดงคำแนะนำรูปแบบข้อมูลใน Google Sheet
    with st.expander("📋 รูปแบบข้อมูลใน Google Sheet"):
        st.markdown("""
        **Sheet: LeaveRequests**
        | nurse | date | month | year | type | priority |
        |-------|------|-------|------|------|----------|
        | ER2 | 5 | 1 | 2026 | Off | 1 |
        | ER3 | 10 | 1 | 2026 | Leave_Train | 1 |
        
        - `type`: `Off` = ขอหยุด, `Leave_Train` = ลา/ประชุม
        - `priority`: 1 = สำคัญมาก, 10 = สำคัญน้อย
        
        ---
        
        **Sheet: FixRequests**
        | nurse | shift | dates | month | year |
        |-------|-------|-------|-------|------|
        | ER5 | M | 1,8,15,22 | 1 | 2026 |
        | ER9 | N | 3,10 | 1 | 2026 |
        
        - `shift`: `M` = เช้า, `S` = บ่าย, `N` = ดึก
        - `dates`: วันที่ คั่นด้วยจุลภาค (comma)
        
        ---
        
        **Sheet: StaffingOverrides**
        | start | end | shift | count | month | year |
        |-------|-----|-------|-------|-------|------|
        | 1 | 10 | N | 2 | 1 | 2026 |
        
        - `shift`: `N` = ดึก, `S` = บ่าย
        - `count`: จำนวนคนที่ต้องการ
        """)
    
    st.markdown("---")
    st.header("📝 บันทึกวันลา (ผ่าน App)")
    
    with st.form("req_form", clear_on_submit=True):
        r_nurse = st.selectbox("ชื่อพยาบาล", nurses_list)
        r_type = st.radio("ประเภท", ["ขอหยุด (Off)", "ลา (Leave)", "ประชุม/อบรม (Train)"], horizontal=True)
        r_dates = st.multiselect("เลือกวันที่", range(1, days_in_month + 1))
        r_priority = st.number_input("ลำดับความสำคัญ (1=สำคัญมาก, 10=สำคัญน้อย)", min_value=1, max_value=10, value=1, 
                                      help="ถ้าคนไม่พอ ลำดับเลขน้อยจะได้หยุดก่อน")
        
        # แก้ไขส่วนบันทึกข้อมูล (เพิ่ม month และ year)
        if st.form_submit_button("เพิ่มรายการ") and r_dates:
            if 'ขอหยุด' in r_type:
                code = 'Off'
            elif 'ลา' in r_type:
                code = 'Leave'
            else:
                code = 'Train'
            
            # สร้าง timestamp
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            for d in r_dates:
                # FIX: บันทึกเดือนและปีไปด้วย + priority + timestamp
                st.session_state.requests.append({
                    'nurse': r_nurse,
                    'date': d,
                    'month': month,
                    'year': year,
                    'type': code,
                    'priority': r_priority,
                    'timestamp': timestamp
                })
            save_requests_to_gsheet() 
            st.success(f"เพิ่มแล้ว! (ลำดับ {r_priority})")

    if st.session_state.requests:
        req_df = pd.DataFrame(st.session_state.requests)
        # แสดง timestamp ถ้ามี
        if 'timestamp' in req_df.columns:
            st.caption("🕐 timestamp = วันเวลาที่คีย์ข้อมูล")
        edited_df = st.data_editor(req_df, num_rows="dynamic", key="editor")
        if edited_df is not None: st.session_state.requests = edited_df.to_dict('records')
        
        # ปุ่ม Reset ล้างรายการวันลาทั้งหมด
        if st.button("🗑️ ล้างรายการวันลาทั้งหมด", type="secondary"):
            st.session_state.requests = []
            save_requests_to_gsheet()
            st.rerun()
    
    # ==========================================
    # 📌 ขอเวร Fix (Shift Fix Request)
    # ==========================================
    st.markdown("---")
    st.header("📌 ขอเวร Fix")
    
    with st.form("fix_form", clear_on_submit=True):
        f_nurse = st.selectbox("ชื่อพยาบาล", nurses_list, key="fix_nurse")
        f_shift = st.radio("ประเภทเวร", ["เช้า (M)", "บ่าย (S)", "ดึก (N)"], horizontal=True)
        
        # เลือกแบบระบุ "วัน" หรือ "วันที่"
        f_mode = st.radio("ระบุแบบ", ["📅 วันที่", "📆 วัน (จันทร์-อาทิตย์)"], horizontal=True)
        
        # แสดงทั้ง 2 ตัวเลือก แต่ใช้ตาม mode
        col1, col2 = st.columns(2)
        with col1:
            f_dates = st.multiselect("เลือกวันที่", range(1, days_in_month + 1), key="fix_dates",
                                      help="ใช้เมื่อเลือก '📅 วันที่'")
        with col2:
            day_options = ["จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์", "เสาร์", "อาทิตย์"]
            f_days = st.multiselect("เลือกวัน", day_options, key="fix_days",
                                     help="ใช้เมื่อเลือก '📆 วัน'")
        
        # แปลงวันเป็นวันที่
        day_map = {"จันทร์": 0, "อังคาร": 1, "พุธ": 2, "พฤหัสบดี": 3, "ศุกร์": 4, "เสาร์": 5, "อาทิตย์": 6}
        dates_from_days = []
        for d in range(1, days_in_month + 1):
            wd = calendar.weekday(year, month, d)
            for day_name in f_days:
                if wd == day_map[day_name]:
                    dates_from_days.append(d)
        
        # เลือกใช้ตาม mode
        if "วันที่" in f_mode:
            selected_dates = f_dates
            if f_dates:
                st.info(f"📅 เลือกวันที่: {', '.join(map(str, f_dates))}")
        else:
            selected_dates = dates_from_days
            if f_days:
                st.info(f"📆 วัน {', '.join(f_days)} → วันที่: {', '.join(map(str, dates_from_days))}")
        
        if st.form_submit_button("เพิ่มรายการ"):
            if selected_dates:
                shift_code = {'เช้า (M)': 'M', 'บ่าย (S)': 'S', 'ดึก (N)': 'N'}[f_shift]
                
                # สร้าง timestamp
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                st.session_state.fix_requests.append({
                    'nurse': f_nurse,
                    'shift': shift_code,
                    'dates': selected_dates,
                    'month': month,
                    'year': year,
                    'timestamp': timestamp
                })
                save_fix_requests_to_gsheet()
                st.success(f"✅ เพิ่มคำขอ Fix เวร {f_shift} สำหรับ {f_nurse} วันที่ {', '.join(map(str, selected_dates))} แล้ว!")
            else:
                st.warning("⚠️ กรุณาเลือกวันที่หรือวันก่อน")
    
    if st.session_state.fix_requests:
        # แสดงรายการ fix requests พร้อม checkbox สำหรับลบรายบุคคล
        st.caption("✅ เลือกรายการที่ต้องการลบ แล้วกดปุ่ม 'ลบรายการที่เลือก'")
        
        # เก็บ index ของรายการที่จะลบ
        indices_to_delete = []
        
        for idx, req in enumerate(st.session_state.fix_requests):
            if req.get('month') == month and req.get('year') == year:
                col1, col2 = st.columns([0.1, 0.9])
                with col1:
                    if st.checkbox("", key=f"del_fix_{idx}", label_visibility="collapsed"):
                        indices_to_delete.append(idx)
                with col2:
                    dates_str = ', '.join(map(str, req.get('dates', [])))
                    st.write(f"**{req['nurse']}** - เวร **{req['shift']}** - วันที่ {dates_str}")
        
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("🗑️ ลบรายการที่เลือก", type="secondary", disabled=len(indices_to_delete) == 0):
                # ลบจากท้ายไปหน้าเพื่อไม่ให้ index เลื่อน
                for idx in sorted(indices_to_delete, reverse=True):
                    st.session_state.fix_requests.pop(idx)
                save_fix_requests_to_gsheet()
                st.rerun()
        with col_btn2:
            if st.button("🗑️ ล้างทั้งหมด", type="secondary"):
                st.session_state.fix_requests = []
                save_fix_requests_to_gsheet()
                st.rerun()
    
    # ==========================================
    # 👥 กำลังคนพิเศษ (Staffing Override)
    # ==========================================
    st.markdown("---")
    st.header("👥 กำลังคนพิเศษ")
    st.caption("กำหนดจำนวนคนที่ต้องการในช่วงวันที่เฉพาะ (แทนค่า default)")
    
    with st.form("staffing_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            s_start = st.number_input("ตั้งแต่วันที่", min_value=1, max_value=days_in_month, value=1)
        with col2:
            s_end = st.number_input("ถึงวันที่", min_value=1, max_value=days_in_month, value=10)
        
        s_shift = st.radio("ประเภทเวร", ["ดึก (N)", "บ่าย (S)"], horizontal=True)
        s_count = st.number_input("จำนวนคน", min_value=1, max_value=5, value=2)
        
        if st.form_submit_button("เพิ่มรายการ"):
            shift_code = 'N' if 'ดึก' in s_shift else 'S'
            st.session_state.staffing_overrides.append({
                'start': int(s_start),
                'end': int(s_end),
                'shift': shift_code,
                'count': int(s_count),
                'month': month,
                'year': year
            })
            save_staffing_overrides_to_gsheet()
            st.success(f"เพิ่มกำลังคนพิเศษ: วันที่ {s_start}-{s_end} เวร {s_shift} = {s_count} คน")
    
    if st.session_state.staffing_overrides:
        # แสดงรายการ staffing overrides
        staff_display = []
        for ov in st.session_state.staffing_overrides:
            if ov.get('month') == month and ov.get('year') == year:
                staff_display.append({
                    'วันที่': f"{ov['start']}-{ov['end']}",
                    'เวร': ov['shift'],
                    'จำนวนคน': ov['count']
                })
        if staff_display:
            st.dataframe(pd.DataFrame(staff_display), hide_index=True)
        
        if st.button("🗑️ ล้างกำลังคนพิเศษทั้งหมด", type="secondary"):
            st.session_state.staffing_overrides = []
            save_staffing_overrides_to_gsheet()
            st.rerun()
    
    st.markdown("---")
    
    # ==========================================
    # ⚠️ Pre-check Validation (ตรวจสอบก่อนจัดตาราง)
    # ==========================================
    st.header("⚠️ ตรวจสอบข้อมูลก่อนจัดตาราง")
    
    # คำนวณวันพิเศษ
    weekend_days_check = [d for d in range(1, days_in_month + 1) if calendar.weekday(year, month, d) >= 5]
    holiday_days_check = THAI_HOLIDAYS.get(year, {}).get(month, [])
    special_days_check = set(weekend_days_check + holiday_days_check)
    weeks_check = (days_in_month + 6) // 7
    
    issues_found = []
    warnings_found = []
    
    # --- 1. ตรวจสอบวันที่ซ้ำกัน (คนเดียวกัน ขอหลายอย่างในวันเดียว) ---
    nurse_day_requests = {}  # {(nurse, day): [types]}
    for req in st.session_state.requests:
        if req.get('month') == month and req.get('year') == year:
            key = (req.get('nurse'), req.get('date'))
            if key not in nurse_day_requests:
                nurse_day_requests[key] = []
            nurse_day_requests[key].append(req.get('type'))
    
    for req in st.session_state.fix_requests:
        if req.get('month') == month and req.get('year') == year:
            for d in req.get('dates', []):
                key = (req.get('nurse'), d)
                if key not in nurse_day_requests:
                    nurse_day_requests[key] = []
                nurse_day_requests[key].append(f"Fix_{req.get('shift')}")
    
    duplicate_days = [(k, v) for k, v in nurse_day_requests.items() if len(v) > 1]
    if duplicate_days:
        for (nurse, day), types in duplicate_days:
            issues_found.append(f"🔴 **{nurse}** วันที่ {day}: มีคำขอซ้ำ ({', '.join(types)})")
    
    # --- 2. ตรวจสอบวันที่มีคนขอหยุดเยอะเกินไป ---
    off_per_day = {}
    leave_per_day = {}
    for req in st.session_state.requests:
        if req.get('month') == month and req.get('year') == year:
            d = req.get('date')
            if req.get('type') == 'Off':
                off_per_day[d] = off_per_day.get(d, []) + [req.get('nurse')]
            elif req.get('type') == 'Leave_Train':
                leave_per_day[d] = leave_per_day.get(d, []) + [req.get('nurse')]
    
    # วันที่มีคนขอหยุด/ลารวมกันเกิน 4 คน = อาจ Infeasible
    for d in range(1, days_in_month + 1):
        total_unavailable = len(off_per_day.get(d, [])) + len(leave_per_day.get(d, []))
        if total_unavailable >= 5:
            issues_found.append(f"🔴 วันที่ {d}: มีคน **{total_unavailable} คน** ไม่ว่าง (หยุด+ลา) → อาจจัดไม่ได้!")
        elif total_unavailable >= 4:
            warnings_found.append(f"🟡 วันที่ {d}: มีคน {total_unavailable} คน ไม่ว่าง → ใกล้เกินโควต้า")
    
    # --- 3. ตรวจสอบวันพิเศษที่มีคนขอหยุดเยอะ ---
    special_off_count = 0
    for req in st.session_state.requests:
        if req.get('month') == month and req.get('year') == year:
            if req.get('type') == 'Off' and req.get('date') in special_days_check:
                special_off_count += 1
    
    max_special_off = weeks_check * 2
    if special_off_count > max_special_off * 1.5:
        issues_found.append(f"🔴 ขอหยุดวัน ส-อา/นักขัตฤกษ์: **{special_off_count} คำขอ** (เกินโควต้ามาก, แนะนำไม่เกิน {max_special_off})")
    elif special_off_count > max_special_off:
        warnings_found.append(f"🟡 ขอหยุดวัน ส-อา: {special_off_count} คำขอ (เกินโควต้า {max_special_off})")
    
    # --- 4. ตรวจสอบ Fix Request เยอะเกิน ---
    fix_count = sum(1 for req in st.session_state.fix_requests 
                   if req.get('month') == month and req.get('year') == year)
    max_fix = weeks_check * 3
    if fix_count > max_fix * 1.5:
        issues_found.append(f"🔴 Fix เวร: **{fix_count} คำขอ** (เกินโควต้ามาก, แนะนำไม่เกิน {max_fix})")
    elif fix_count > max_fix:
        warnings_found.append(f"🟡 Fix เวร: {fix_count} คำขอ (เกินโควต้า {max_fix})")
    
    # --- 5. ตรวจสอบคนที่ลาเยอะเกิน ---
    leave_by_nurse = {}
    for req in st.session_state.requests:
        if req.get('month') == month and req.get('year') == year:
            if req.get('type') == 'Leave_Train':
                n = req.get('nurse')
                leave_by_nurse[n] = leave_by_nurse.get(n, 0) + 1
    
    max_leave = days_in_month // 3
    for n, count in leave_by_nurse.items():
        if count > max_leave:
            warnings_found.append(f"🟡 {n} ลา/ประชุม {count} วัน (เกินแนะนำ {max_leave} วัน)")
    
    # --- แสดงผลการตรวจสอบ ---
    if issues_found:
        st.error("### 🚨 พบปัญหาที่อาจทำให้จัดตารางไม่ได้")
        for issue in issues_found:
            st.markdown(issue)
        
        st.info("""
        **💡 คำแนะนำ:**
        - ลดจำนวนคนขอหยุด/ลาในวันที่มีปัญหา
        - ลบคำขอที่ซ้ำซ้อน
        - ใช้ "กำลังคนพิเศษ" เพื่อลดจำนวนเวรในวันนั้น
        """)
        can_proceed = False
    elif warnings_found:
        st.warning("### ⚠️ พบข้อควรระวัง (อาจจัดได้ แต่ควรตรวจสอบ)")
        for warn in warnings_found:
            st.markdown(warn)
        can_proceed = True
    else:
        st.success("### ✅ ข้อมูลผ่านการตรวจสอบ พร้อมจัดตาราง!")
        can_proceed = True
    
    # ปุ่มรีเซ็ตทุกอย่าง (ล้างวันลา + ล้างตารางเวรเก่า)
    if st.button("🔄 รีเซ็ตทั้งหมด (ล้างวันลา+ตาราง+Fix+กำลังคน)", type="secondary"):
        st.session_state.requests = []
        st.session_state.fix_requests = []
        st.session_state.staffing_overrides = []
        st.session_state.schedule_df = None
        save_requests_to_gsheet()
        save_fix_requests_to_gsheet()
        save_staffing_overrides_to_gsheet()
        st.rerun()

    st.markdown("---")
    
    # ปุ่มประมวลผล (แสดงสถานะตาม can_proceed)
    if issues_found:
        st.warning("⚠️ แนะนำให้แก้ไขปัญหาก่อนจัดตาราง หรือกดปุ่มด้านล่างเพื่อลองจัดดู")
    
    if st.button("🚀 ประมวลผลจัดตาราง", type="primary"):
        with st.spinner("กำลังคำนวณและเกลี่ยเวร..."):
            df = solve_schedule(
                year, month, days_in_month, nurses_list, 
                st.session_state.requests,
                st.session_state.fix_requests, st.session_state.staffing_overrides,
                enable_oc=enable_oc, prev_month_data=prev_month_data
            )
            if df is not None:
                st.session_state.schedule_df = df
                st.success("จัดตารางสำเร็จ!")
            else:
                st.error("❌ ไม่สามารถจัดตารางได้! (เงื่อนไขขัดแย้งกัน)")
                
                # วิเคราะห์ปัญหา
                issues = diagnose_scheduling_issues(
                    year, month, days_in_month, nurses_list,
                    st.session_state.requests, st.session_state.staffing_overrides, enable_oc
                )
                
                if issues:
                    st.error("⚠️ ไม่สามารถจัดตารางได้ เนื่องจากคนไม่พอในบางวัน")
                    
                    # Generate and display detailed report
                    report_md = generate_diagnosis_md(issues)
                    st.markdown(report_md)
                    
                    # Old expander usage (can remove or keep as raw data)
                    with st.expander("ดูข้อมูลดิบ (JSON)"):
                        st.json(issues)
                else:
                    st.error("💡 จัดตารางไม่สำเร็จ อาจเกิดจาก:")
                    st.markdown("""
                    *   กฎดึกติดกัน (N -> N)
                    *   กฎบ่ายต่อดึก (S -> M)
                    *   ข้อจำกัดพยาบาลเฉพาะ (ER7 M+ลา <= 10)
                    *   กฎ 7 วันทำงานติดกัน
                    """)
                
                # ==========================================
                # DEBUG: แสดงตารางสรุปคำขอทั้งหมด
                # ==========================================
                st.markdown("---")
                st.subheader("📋 สรุปคำขอทั้งหมด (Debug)")
                
                # สร้างตารางแสดงคำขอ
                debug_data = []
                
                # 1. วันลา/ประชุม (Leave_Train)
                for req in st.session_state.requests:
                    if req.get('month') == month and req.get('year') == year:
                        if req.get('type') == 'Leave_Train':
                            debug_data.append({
                                'พยาบาล': req.get('nurse'),
                                'วันที่': req.get('date'),
                                'ประเภท': '📝 ลา/ประชุม (L_T)',
                                'หมายเหตุ': req.get('reason', '-')
                            })
                
                # 2. ขอหยุด (Off)
                for req in st.session_state.requests:
                    if req.get('month') == month and req.get('year') == year:
                        if req.get('type') == 'Off':
                            debug_data.append({
                                'พยาบาล': req.get('nurse'),
                                'วันที่': req.get('date'),
                                'ประเภท': '🚫 ขอหยุด (Off)',
                                'หมายเหตุ': req.get('reason', '-')
                            })
                
                # 3. ขอเวร Fix
                for req in st.session_state.fix_requests:
                    if req.get('month') == month and req.get('year') == year:
                        dates = req.get('dates', [])
                        for d in dates:
                            debug_data.append({
                                'พยาบาล': req.get('nurse'),
                                'วันที่': d,
                                'ประเภท': f"📌 Fix เวร {req.get('shift')}",
                                'หมายเหตุ': f"ขอเวร {req.get('shift')}"
                            })
                
                if debug_data:
                    # เรียงตามวันที่
                    debug_df = pd.DataFrame(debug_data)
                    debug_df = debug_df.sort_values(by=['วันที่', 'พยาบาล'])
                    st.dataframe(debug_df, hide_index=True, use_container_width=True)
                    
                    # สรุปรายวัน (หาวันที่มีหลายคนขอ)
                    st.markdown("### 🔍 วันที่มีคำขอหลายรายการ")
                    day_counts = debug_df.groupby('วันที่').size().reset_index(name='จำนวนคำขอ')
                    multi_request_days = day_counts[day_counts['จำนวนคำขอ'] > 1]
                    if not multi_request_days.empty:
                        for _, row in multi_request_days.iterrows():
                            d = row['วันที่']
                            count = row['จำนวนคำขอ']
                            day_detail = debug_df[debug_df['วันที่'] == d]
                            nurses_str = ", ".join(f"{r['พยาบาล']}({r['ประเภท'].split()[0]})" for _, r in day_detail.iterrows())
                            st.warning(f"📅 **วันที่ {d}**: {count} คำขอ → {nurses_str}")
                    else:
                        st.success("✅ ไม่มีวันที่มีคำขอซ้ำซ้อน")
                    
                    # หาคนที่มีคำขอซ้อนกัน (ขอ Off แต่ก็ขอ Fix ด้วย)
                    st.markdown("### ⚠️ ตรวจสอบคำขอที่ขัดกัน")
                    conflicts = []
                    for nurse in nurses_list:
                        nurse_reqs = debug_df[debug_df['พยาบาล'] == nurse]
                        for d in nurse_reqs['วันที่'].unique():
                            day_reqs = nurse_reqs[nurse_reqs['วันที่'] == d]
                            if len(day_reqs) > 1:
                                types = day_reqs['ประเภท'].tolist()
                                conflicts.append({
                                    'พยาบาล': nurse,
                                    'วันที่': d,
                                    'คำขอ': " + ".join(types)
                                })
                    
                    if conflicts:
                        for c in conflicts:
                            st.error(f"❌ **{c['พยาบาล']}** วันที่ {c['วันที่']}: {c['คำขอ']}")
                    else:
                        st.success("✅ ไม่มีคำขอที่ขัดกัน (คนเดียวกันวันเดียวกัน)")
                else:
                    st.info("ไม่มีคำขอใดๆ ในเดือนนี้")

# --- Main Content ---
if st.session_state.schedule_df is not None:
    tab1, tab2, tab3, tab4 = st.tabs(["📅 ตารางเวร", "💰 ค่าตอบแทนและค่าเวร", "📅 ปฏิทินวันหยุด", "📊 คะแนน"])
    
    with tab1:
        st.subheader(f"ตารางเวรเดือน {month}/{year}")
        
        # แสดงข้อมูลวันหยุดในเดือนนี้
        holidays_in_month = THAI_HOLIDAYS.get(year, {}).get(month, [])
        if holidays_in_month:
            st.info(f"📅 **วันหยุดนักขัตฤกษ์ในเดือนนี้:** {', '.join(map(str, holidays_in_month))}")
        
        st.caption("💡 **สามารถแก้ไขเวรได้โดยตรง** | 🟡 = วันหยุดนักขัตฤกษ์ | 🔵 = เสาร์-อาทิตย์")
        
        # สร้าง styled column names เพื่อแสดงวันหยุด
        styled_df = st.session_state.schedule_df.copy()
        
        # เปลี่ยนชื่อ column เพื่อแสดงวันหยุด/weekend
        new_columns = {'Nurse': 'พยาบาล'}
        for d in range(1, days_in_month + 1):
            col_name = str(d)
            if col_name in styled_df.columns:
                wd = calendar.weekday(year, month, d)
                is_weekend = wd >= 5
                is_hol = is_holiday(year, month, d)
                
                if is_hol:
                    new_columns[col_name] = f"🟡{d}"
                elif is_weekend:
                    new_columns[col_name] = f"🔵{d}"
                else:
                    new_columns[col_name] = col_name
        
        styled_df = styled_df.rename(columns=new_columns)
        
        # ใช้ data_editor แทน dataframe เพื่อให้แก้ไขได้
        edited_schedule = st.data_editor(
            styled_df, 
            width='stretch',
            key="schedule_editor",
            num_rows="fixed"  # ไม่ให้เพิ่ม/ลบแถว
        )
        
        # ปุ่มบันทึกการแก้ไขและประมวลผลใหม่
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("💾 บันทึกการแก้ไข", type="primary"):
                # แปลง column กลับเป็นชื่อเดิมก่อนบันทึก
                reverse_columns = {'พยาบาล': 'Nurse'}
                for d in range(1, days_in_month + 1):
                    for prefix in ['🟡', '🔵', '']:
                        styled_name = f"{prefix}{d}"
                        if styled_name in edited_schedule.columns:
                            reverse_columns[styled_name] = str(d)
                            break
                save_df = edited_schedule.rename(columns=reverse_columns)
                st.session_state.schedule_df = save_df
                st.success("บันทึกการแก้ไขแล้ว! ค่าตอบแทนจะถูกคำนวณใหม่โดยอัตโนมัติ")
                st.rerun()
        with col_btn2:
            if st.button("🔄 รีเซ็ตการแก้ไข (คืนค่าเดิม)"):
                st.rerun()

    with tab2:
        st.subheader("สรุปรายได้และภาระงาน")
        
        # คำนวณวันหยุดอัตโนมัติ (เสาร์-อาทิตย์ + วันหยุดนักขัตฤกษ์)
        weekend_count = sum(1 for d in range(1, days_in_month + 1) if calendar.weekday(year, month, d) >= 5)
        holiday_count = len([d for d in THAI_HOLIDAYS.get(year, {}).get(month, []) 
                            if calendar.weekday(year, month, d) < 5])  # นับเฉพาะวันหยุดที่ไม่ตรงกับ ส-อา
        total_off_days = weekend_count + holiday_count
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("📅 วันหยุด (ส-อา + นักขัตฤกษ์)", f"{total_off_days} วัน")
            st.caption(f"ส-อา: {weekend_count}, นักขัตฤกษ์: {holiday_count}")
        with col2:
            rate_sn = st.number_input("ค่าเวร บ่าย/ดึก (บาท/เวร)", value=360)
        with col3:
            ot_rate = st.number_input("ค่าตอบแทน OT (บาท/เวร)", value=800)
            
        std_work_days = days_in_month - total_off_days
        st.info(f"💡 เกณฑ์วันทำงานปกติ: **{std_work_days} วัน** = {days_in_month} - {total_off_days} (เกินจากนี้คิดเป็น OT)")
        
        summary_data = []
        for index, row in st.session_state.schedule_df.iterrows():
            # หา column ที่ถูกต้อง (อาจเป็นเลขธรรมดาหรือมี emoji นำหน้า)
            shifts = []
            for d in range(1, days_in_month + 1):
                col_name = str(d)
                # ลองหา column ที่ตรงกัน
                if col_name in row.index:
                    shifts.append(row[col_name])
                else:
                    # ลองหา column ที่มี emoji นำหน้า
                    found = False
                    for prefix in ['🟡', '🔵', '']:
                        styled_col = f"{prefix}{d}"
                        if styled_col in row.index:
                            shifts.append(row[styled_col])
                            found = True
                            break
                    if not found:
                        shifts.append('')  # ถ้าหาไม่เจอให้เป็นค่าว่าง
            
            c_m = shifts.count('M')
            c_s = shifts.count('S')
            c_n = shifts.count('N')
            c_ns = shifts.count('NS')  # นับ NS แยก
            c_oc = sum(1 for s in shifts if '📞OC' in str(s))  # นับ OC
            c_lt = shifts.count('ลา/อบรม')
            
            # รวม ลา/ประชุม กับเวรเช้า
            c_m_plus_lt = c_m + c_lt
            
            # NS นับเป็น 2 เวร (S+N) ในวันเดียว
            total_work = c_m + c_s + c_n + c_ns + c_lt
            
            # คำนวณเงิน
            # NS ได้ค่าเวร 2 เท่า (บ่าย+ดึก)
            shift_allowance = (c_s + c_n + c_ns * 2) * rate_sn  # NS = 2 เวร
            oc_allowance = c_oc * 400  # ค่าเวร OC = 400 บาท
            ot_shifts = max(0, total_work - std_work_days) + c_ns  # NS นับเป็น OT ด้วย
            ot_pay = ot_shifts * ot_rate  # เงิน OT
            total_income = shift_allowance + oc_allowance + ot_pay  # รวมเงินทั้งหมด
            
            summary_data.append({
                'ชื่อ': row['Nurse'],
                'เวรเช้า+ลา (M)': c_m_plus_lt,
                'เวรบ่าย (S)': c_s,
                'เวรดึก (N)': c_n,
                'NS (OT)': c_ns,  # แสดง NS แยก
                'OC': c_oc,  # แสดง On-Call
                'รวมวันทำงาน': total_work,
                'ค่าเวร บ่าย/ดึก': f"{shift_allowance:,}",
                'ค่า OC': f"{oc_allowance:,}",
                'OT (เวร)': ot_shifts,
                'เงิน OT': f"{ot_pay:,}",
                'รวมรายได้สุทธิ': f"{total_income:,}"
            })
            
        df_sum = pd.DataFrame(summary_data)
        st.dataframe(df_sum, width='stretch')
        
        # Download
        csv = df_sum.to_csv(index=False).encode('utf-8')
        st.download_button("📥 ดาวน์โหลดรายงานรายได้", csv, "salary_report.csv", "text/csv")
    
    with tab3:
        st.subheader("📅 ปฏิทินวันหยุดราชการ")
        
        # สร้างปฏิทินวันหยุด
        holidays_this_year = THAI_HOLIDAYS.get(year, {})
        
        if holidays_this_year:
            for m in range(1, 13):
                if m in holidays_this_year:
                    month_name = ['', 'ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.', 
                                  'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.'][m]
                    days_list = holidays_this_year[m]
                    st.markdown(f"**{month_name}:** {', '.join(map(str, days_list))}")
        else:
            st.warning(f"ยังไม่มีข้อมูลวันหยุดสำหรับปี {year}")
        
        # นับจำนวนวันหยุดเสาร์-อาทิตย์ในเดือนปัจจุบัน
        weekend_count = sum(1 for d in range(1, days_in_month + 1) if calendar.weekday(year, month, d) >= 5)
        holiday_count = len(THAI_HOLIDAYS.get(year, {}).get(month, []))
        
        st.markdown("---")
        st.metric("วันเสาร์-อาทิตย์ในเดือนนี้", f"{weekend_count} วัน", delta=None)
        st.metric("วันหยุดนักขัตฤกษ์ในเดือนนี้", f"{holiday_count} วัน", delta=None)
    
    with tab4:
        st.subheader("📊 คะแนนความยุติธรรมและความสมดุล")
        
        df = st.session_state.schedule_df
        nurses_list = [f'ER{i}' for i in range(1, 11)]
        
        # คำนวณวัน ส-อา และวันหยุดนักขัตฤกษ์
        weekend_days = [d for d in range(1, days_in_month + 1) if calendar.weekday(year, month, d) >= 5]
        holiday_days = THAI_HOLIDAYS.get(year, {}).get(month, [])
        special_days = list(set(weekend_days + holiday_days))
        
        # คำนวณคะแนนแต่ละคน
        score_data = []
        for _, row in df.iterrows():
            nurse_name = str(row.iloc[0])
            nurse_id = None
            for nid in nurses_list:
                if nid in nurse_name:
                    nurse_id = nid
                    break
            if not nurse_id:
                continue
            
            # 1. นับวันหยุดในวัน ส-อา/นักขัตฤกษ์
            off_on_special = 0
            for d in special_days:
                col = str(d)
                for c in df.columns:
                    if str(d) in str(c):
                        col = c
                        break
                if col in row.index:
                    val = str(row[col])
                    if val in ['O', ''] or 'NCD' in val:
                        off_on_special += 1
            
            # 2. นับเวร S, N (ไม่รวม NS)
            c_s = 0
            c_n = 0
            c_ns = 0
            for col in df.columns[1:]:
                val = str(row[col])
                if val == 'S':
                    c_s += 1
                elif val == 'N':
                    c_n += 1
                elif val == 'NS' or 'NS' in val:
                    c_ns += 1
            
            # 3. เช็ค Fix Request Compliance
            fix_total = 0
            fix_matched = 0
            for fix in st.session_state.fix_requests:
                if fix.get('nurse') == nurse_id and fix.get('month') == month and fix.get('year') == year:
                    fix_total += 1
                    d = fix.get('date')
                    shift = fix.get('shift')
                    col = str(d)
                    for c in df.columns:
                        if str(d) in str(c):
                            col = c
                            break
                    if col in row.index:
                        actual = str(row[col])
                        if shift in actual:
                            fix_matched += 1
            
            fix_rate = (fix_matched / fix_total * 100) if fix_total > 0 else None
            
            score_data.append({
                'พยาบาล': nurse_name,
                '🏖️ หยุด ส-อา/นักขัตฤกษ์': f"{off_on_special}/{len(special_days)}",
                '🌅 เวร S': c_s,
                '🌙 เวร N': c_n,
                '🌙🌅 เวร NS': c_ns,
                '⚖️ S+N (สมดุล)': c_s + c_n,
                '✅ Fix Rate': f"{fix_rate:.0f}%" if fix_rate is not None else "ไม่มี"
            })
        
        if score_data:
            score_df = pd.DataFrame(score_data)
            st.dataframe(score_df, hide_index=True, width='stretch')
            
            # สถิติ
            st.markdown("---")
            col1, col2, col3 = st.columns(3)
            
            # ความยุติธรรม ส-อา
            off_counts = [int(s['🏖️ หยุด ส-อา/นักขัตฤกษ์'].split('/')[0]) for s in score_data if 'ER1' not in s['พยาบาล']]
            if off_counts:
                with col1:
                    avg_off = sum(off_counts) / len(off_counts)
                    st.metric("⌀ หยุด ส-อา (ไม่รวม ER1)", f"{avg_off:.1f} วัน")
                    st.caption(f"ต่ำสุด: {min(off_counts)}, สูงสุด: {max(off_counts)}")
            
            # ความสมดุล S+N
            sn_counts = [s['⚖️ S+N (สมดุล)'] for s in score_data if 'ER1' not in s['พยาบาล'] and 'ER7' not in s['พยาบาล']]
            if sn_counts:
                with col2:
                    avg_sn = sum(sn_counts) / len(sn_counts)
                    st.metric("⌀ เวร S+N (ไม่รวม ER1,7)", f"{avg_sn:.1f}")
                    st.caption(f"ต่ำสุด: {min(sn_counts)}, สูงสุด: {max(sn_counts)}")
            
            # Fix Rate
            fix_rates = [float(s['✅ Fix Rate'].replace('%', '')) for s in score_data if s['✅ Fix Rate'] != 'ไม่มี']
            if fix_rates:
                with col3:
                    avg_fix = sum(fix_rates) / len(fix_rates)
                    st.metric("⌀ Fix Request สำเร็จ", f"{avg_fix:.0f}%")
                    st.caption(f"ต่ำสุด: {min(fix_rates):.0f}%, สูงสุด: {max(fix_rates):.0f}%")
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

# --- Nurse Names Mapping (กันลืม) ---
NURSE_NAMES = {
    'ER1': 'บูรีซาน',
    'ER2': 'อัมรี',
    'ER3': 'ฮาบีบูเลาะ',
    'ER4': 'มัรวาน',
    'ER5': 'อานูรา',
    'ER6': 'อูไมซะห์',
    'ER7': 'บูรีฮัน',
    'ER8': 'สูสนี',
    'ER9': 'นูซีลัน',
    'ER10': 'ซัมนะห์',
}

CSV_FILE = "leave_requests.csv"
FIX_REQUESTS_FILE = "fix_requests.csv"
STAFFING_OVERRIDES_FILE = "staffing_overrides.csv"

def load_requests_from_csv():
    if os.path.exists(CSV_FILE):
        df = pd.read_csv(CSV_FILE)
        return df.to_dict('records')
    return []

def save_requests_to_csv():
    if st.session_state.requests:
        df = pd.DataFrame(st.session_state.requests)
        df.to_csv(CSV_FILE, index=False)
    else:
        if os.path.exists(CSV_FILE):
            os.remove(CSV_FILE)

def load_fix_requests_from_csv():
    if os.path.exists(FIX_REQUESTS_FILE):
        df = pd.read_csv(FIX_REQUESTS_FILE)
        # Convert dates string back to list
        df['dates'] = df['dates'].apply(lambda x: [int(d) for d in str(x).split(',')] if pd.notna(x) else [])
        return df.to_dict('records')
    return []

def save_fix_requests_to_csv():
    if st.session_state.fix_requests:
        df = pd.DataFrame(st.session_state.fix_requests)
        # Convert dates list to comma-separated string for CSV
        df['dates'] = df['dates'].apply(lambda x: ','.join(map(str, x)) if x else '')
        df.to_csv(FIX_REQUESTS_FILE, index=False)
    else:
        if os.path.exists(FIX_REQUESTS_FILE):
            os.remove(FIX_REQUESTS_FILE)

def load_staffing_overrides_from_csv():
    if os.path.exists(STAFFING_OVERRIDES_FILE):
        df = pd.read_csv(STAFFING_OVERRIDES_FILE)
        return df.to_dict('records')
    return []

def save_staffing_overrides_to_csv():
    if st.session_state.staffing_overrides:
        df = pd.DataFrame(st.session_state.staffing_overrides)
        df.to_csv(STAFFING_OVERRIDES_FILE, index=False)
    else:
        if os.path.exists(STAFFING_OVERRIDES_FILE):
            os.remove(STAFFING_OVERRIDES_FILE)

# --- Helper Function ---
def get_week_occurrence(day):
    return (day - 1) // 7 + 1

# --- 1. ฟังก์ชันจัดตาราง (Scheduler Engine) ---
def solve_schedule(year, month, days_in_month, nurses, requests, er5_er10_pattern='new', fix_requests=None, staffing_overrides=None):
    if fix_requests is None:
        fix_requests = []
    if staffing_overrides is None:
        staffing_overrides = []
    
    model = cp_model.CpModel()
    
    # เพิ่ม NS (บ่าย+ดึก 16 ชม.) เป็น OT shift
    shifts = ['S', 'M', 'N', 'O', 'L_T', 'NS'] 
    work_shifts = ['S', 'M', 'N', 'L_T', 'NS']  # NS นับเป็นวันทำงาน

    shifts_var = {}
    for n in nurses:
        for d in range(1, days_in_month + 1):
            for s in shifts:
                shifts_var[(n, d, s)] = model.NewBoolVar(f'shift_{n}_{d}_{s}')

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
        
        # N + NS >= n_req
        model.Add(sum(shifts_var[(n, d, 'N')] + shifts_var[(n, d, 'NS')] for n in nurses) >= n_req)
        # S + NS >= s_req
        model.Add(sum(shifts_var[(n, d, 'S')] + shifts_var[(n, d, 'NS')] for n in nurses) >= s_req)
        req_m = 4 if is_special_day else 3  # เสาร์-อาทิตย์ หรือ วันหยุดนักขัตฤกษ์ = 4 คน
        model.Add(sum(shifts_var[(n, d, 'M')] for n in nurses) == req_m)

    # กฎการสลับเวร (ห้าม S -> N, รวม NS ด้วย)
    for n in nurses:
        for d in range(1, days_in_month):
            model.Add(shifts_var[(n, d, 'S')] + shifts_var[(n, d + 1, 'N')] <= 1)
            model.Add(shifts_var[(n, d, 'S')] + shifts_var[(n, d + 1, 'NS')] <= 1)

    # ==========================================
    # กฎเวรดึก (N) เดี่ยว - ต้องทำงานก่อนดึก และหยุดหลังดึก
    # ==========================================
    for n in nurses:
        # 1. ห้าม N-N, NS-NS, N-NS, NS-N (ดึกติดกัน)
        for d in range(1, days_in_month):
            model.Add(shifts_var[(n, d, 'N')] + shifts_var[(n, d + 1, 'N')] <= 1)
            model.Add(shifts_var[(n, d, 'NS')] + shifts_var[(n, d + 1, 'NS')] <= 1)
            model.Add(shifts_var[(n, d, 'N')] + shifts_var[(n, d + 1, 'NS')] <= 1)
            model.Add(shifts_var[(n, d, 'NS')] + shifts_var[(n, d + 1, 'N')] <= 1)
        
        # 2. ห้าม O-N, O-NS (ต้องทำงานก่อนดึก)
        for d in range(1, days_in_month):
            model.Add(shifts_var[(n, d, 'O')] + shifts_var[(n, d + 1, 'N')] <= 1)
            model.Add(shifts_var[(n, d, 'O')] + shifts_var[(n, d + 1, 'NS')] <= 1)
        
        # 3. ห้าม N-O-N, NS-O-NS (ห้ามดึกสลับวัน)
        for d in range(1, days_in_month - 1):
            model.Add(shifts_var[(n, d, 'N')] + shifts_var[(n, d + 2, 'N')] <= 1)
            model.Add(shifts_var[(n, d, 'NS')] + shifts_var[(n, d + 2, 'NS')] <= 1)
            model.Add(shifts_var[(n, d, 'N')] + shifts_var[(n, d + 2, 'NS')] <= 1)
            model.Add(shifts_var[(n, d, 'NS')] + shifts_var[(n, d + 2, 'N')] <= 1)

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

    # ทำงานต่อเนื่องสูงสุด 7 วัน (รวม NS)
    for n in nurses:
        for d in range(1, days_in_month - 6):
            model.Add(sum(sum(shifts_var[(n, d + k, s)] for s in work_shifts) for k in range(8)) <= 7)
    
    # ป้องกัน NS หลังทำงานติด 6 วัน (เพราะ NS = 2 เวร จะทำให้เกิน 7 เวร)
    for n in nurses_for_ns:
        for d in range(7, days_in_month + 1):
            # ถ้า 6 วันก่อนหน้าทำงานทั้งหมด แล้ววันนี้เป็น NS = 8 เวร (เกิน!)
            # ดังนั้น ถ้าจะทำ NS ต้องมี Off อย่างน้อย 1 วันใน 6 วันก่อนหน้า
            prev_work = sum(sum(shifts_var[(n, d - k, s)] for s in ['S', 'M', 'N', 'NS']) for k in range(1, 7))
            # ถ้าทำงาน 6 วันก่อนหน้า (prev_work=6) แล้ว NS ห้าม
            model.Add(prev_work + shifts_var[(n, d, 'NS')] <= 6)

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

        # ER5 & ER10 (Soft Fix): ขึ้นกับ pattern ที่เลือก
        if er5_er10_pattern == 'old':  # Pattern เก่า (ก.ย. 2025)
            # ER5: อังคาร สัปดาห์ 1,4
            if wd == 1 and week_occurrence in [1, 4]:
                preferred_constraints.append(shifts_var[('ER5', d, 'M')])
            # ER10: อังคาร สัปดาห์ 2,3
            if wd == 1 and week_occurrence in [2, 3]:
                preferred_constraints.append(shifts_var[('ER10', d, 'M')])
        else:  # Pattern ใหม่ (default)
            # ER5: ทุกวันจันทร์
            if wd == 0:
                preferred_constraints.append(shifts_var[('ER5', d, 'M')])
            # ER10: ทุกวันศุกร์
            if wd == 4:
                preferred_constraints.append(shifts_var[('ER10', d, 'M')])

        # [REMOVED] ER9 Hardcode - ใช้ fix_requests จาก UI แทน
        # ตอนนี้ ER9 (และคนอื่น) สามารถขอเวร Fix ผ่าน UI ได้

        er7_m_shifts.append(shifts_var[('ER7', d, 'M')])
        er7_sn_shifts.append(shifts_var[('ER7', d, 'S')])
        er7_sn_shifts.append(shifts_var[('ER7', d, 'N')])

    # ER7 (Hard Fix): เช้า+ลา = 10 (รวมวันลา/ประชุมด้วย), บ่าย+ดึก ไม่เกิน 10
    er7_lt_shifts = [shifts_var[('ER7', d, 'L_T')] for d in range(1, days_in_month + 1)]
    model.Add(sum(er7_m_shifts) + sum(er7_lt_shifts) == 10)  # M + ลา/ประชุม = 10
    model.Add(sum(er7_sn_shifts) <= 10)  # S+N ไม่เกิน 10
    
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
           if req['nurse'] in nurses:
                if req['type'] == 'Off':
                    model.Add(shifts_var[(req['nurse'], req['date'], 'O')] == 1)
                elif req['type'] == 'Leave_Train':
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
    
    for n in rotating_nurses:
        # นับรวม M, S, N, L_T
        total_work_per_nurse[n] = sum(sum(shifts_var[(n, d, s)] for s in work_shifts) for d in range(1, days_in_month + 1))

    # กฎบังคับ: เวรรวมห้ามต่างกันเกิน 1 (เพื่อความแฟร์สูงสุด)
    for n1 in rotating_nurses:
        for n2 in rotating_nurses:
            if n1 == n2: continue
            model.Add(total_work_per_nurse[n1] - total_work_per_nurse[n2] <= 1)
    
    # ==========================================
    # 3.1 วันหยุดของแต่ละคน = วันหยุดของเดือน (เสาร์-อาทิตย์ + นักขัตฤกษ์)
    # ==========================================
    # คำนวณจำนวนวันหยุดในเดือน
    weekend_count = sum(1 for d in range(1, days_in_month + 1) if calendar.weekday(year, month, d) >= 5)
    holiday_count = len([d for d in THAI_HOLIDAYS.get(year, {}).get(month, []) 
                        if calendar.weekday(year, month, d) < 5])  # นับเฉพาะวันหยุดที่ไม่ตรงกับ ส-อา
    target_off_days = weekend_count + holiday_count
    
    # กำหนดให้ทุกคน (ยกเว้น ER1) มีวันหยุดใกล้เคียงกับ target
    for n in rotating_nurses:
        off_days = sum(shifts_var[(n, d, 'O')] for d in range(1, days_in_month + 1))
        # อนุญาตให้ Off ต่างจาก target ได้ ±2 (เพื่อความยืดหยุ่นกับกฎดึกเดี่ยว)
        model.Add(off_days >= target_off_days - 2)
        model.Add(off_days <= target_off_days + 2)
    
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
    
    # เกลี่ยให้ต่างกันไม่เกิน 2 วัน
    for n1 in rotating_nurses:
        for n2 in rotating_nurses:
            if n1 != n2:
                model.Add(special_offs_per_nurse[n1] - special_offs_per_nurse[n2] <= 2)
    
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
    # น้ำหนัก: preferred_constraints (M fix) > separation > consecutive_off > off_after_night
    model.Maximize(
        sum(preferred_constraints) * 100 + 
        sum(consecutive_off_constraints) * 5 +
        sum(off_after_night_constraints) -
        sum(separation_penalty) * 30  # ลบคะแนนเมื่อ ER2-ER7 ซ้อนเวรกัน
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
st.set_page_config(page_title="ระบบจัดตารางเวร ER_KPH v2.3", layout="wide")
st.title("🏥 ระบบจัดตารางเวรพยาบาล (ER_KPH)")
st.caption("**v2.3** | 🆕 ขอเวร Fix ผ่าน UI | กำลังคนพิเศษตามช่วงวันที่ | เกลี่ย ส-อา/นักขัตฤกษ์")

# Session State
if 'schedule_df' not in st.session_state: st.session_state.schedule_df = None
if 'requests' not in st.session_state: 
    st.session_state.requests = load_requests_from_csv()
if 'fix_requests' not in st.session_state:
    st.session_state.fix_requests = load_fix_requests_from_csv()
if 'staffing_overrides' not in st.session_state:
    st.session_state.staffing_overrides = load_staffing_overrides_from_csv()

# Sidebar
with st.sidebar:
    st.header("⚙️ ตั้งค่า")
    year = st.number_input("ปี (ค.ศ.)", 2024, 2030, 2025)
    month = st.selectbox("เดือน", range(1, 13), 10)
    _, days_in_month = calendar.monthrange(year, month)
    nurses_list = [f'ER{i}' for i in range(1, 11)]
    
    st.markdown("---")
    st.header("📅 Pattern เวรเช้า ER5/ER10")
    er5_er10_pattern = st.radio(
        "เลือก Pattern:",
        options=['new', 'old'],
        format_func=lambda x: "🆕 ใหม่: ER5=จันทร์ทุกสัปดาห์, ER10=ศุกร์ทุกสัปดาห์" if x == 'new' else "📆 เก่า (ก.ย.25): ER5=อังคาร wk1,4, ER10=อังคาร wk2,3",
        index=0,
        help="เลือก pattern เวรเช้า Fix ของ ER5 และ ER10"
    )
    
    st.markdown("---")
    st.header("📝 บันทึกวันลา")
    
    with st.form("req_form", clear_on_submit=True):
        r_nurse = st.selectbox("ชื่อพยาบาล", nurses_list)
        r_type = st.radio("ประเภท", ["ขอหยุด (Off)", "ลา/ประชุม (นับงาน)"])
        r_dates = st.multiselect("เลือกวันที่", range(1, days_in_month + 1))
        
        # แก้ไขส่วนบันทึกข้อมูล (เพิ่ม month และ year)
        if st.form_submit_button("เพิ่มรายการ") and r_dates:
            code = 'Off' if 'ขอหยุด' in r_type else 'Leave_Train'
            for d in r_dates:
                # FIX: บันทึกเดือนและปีไปด้วย!
                st.session_state.requests.append({
                    'nurse': r_nurse,
                    'date': d,
                    'month': month,  # เพิ่มบรรทัดนี้ (เอาค่ามาจากตัวแปร month ด้านบน)
                    'year': year,    # เพิ่มบรรทัดนี้
                    'type': code
                })
            # เพิ่ม Code Save ลงไฟล์ทันทีตรงนี้ (ดูข้อ 3)
            save_requests_to_csv() 
            st.success("เพิ่มแล้ว (จำเดือน/ปี แม่นยำ!)")

    if st.session_state.requests:
        req_df = pd.DataFrame(st.session_state.requests)
        edited_df = st.data_editor(req_df, num_rows="dynamic", key="editor")
        if edited_df is not None: st.session_state.requests = edited_df.to_dict('records')
        
        # ปุ่ม Reset ล้างรายการวันลาทั้งหมด
        if st.button("🗑️ ล้างรายการวันลาทั้งหมด", type="secondary"):
            st.session_state.requests = []
            save_requests_to_csv()
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
        f_mode = st.radio("ระบุแบบ", ["📅 วันที่ (เลือกวันที่เฉพาะ)", "📆 วัน (ทุกวันจันทร์, อังคาร, ฯลฯ)"], horizontal=True)
        
        if "วันที่" in f_mode:
            # แบบเดิม: เลือกวันที่เฉพาะ
            f_dates = st.multiselect("เลือกวันที่", range(1, days_in_month + 1), key="fix_dates")
            selected_dates = f_dates
        else:
            # แบบใหม่: เลือกวัน (จันทร์-อาทิตย์)
            day_options = ["จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์", "เสาร์", "อาทิตย์"]
            f_days = st.multiselect("เลือกวัน", day_options, key="fix_days")
            
            # แปลงวันเป็นวันที่ในเดือนนี้
            day_map = {"จันทร์": 0, "อังคาร": 1, "พุธ": 2, "พฤหัสบดี": 3, "ศุกร์": 4, "เสาร์": 5, "อาทิตย์": 6}
            selected_dates = []
            for d in range(1, days_in_month + 1):
                wd = calendar.weekday(year, month, d)
                for day_name in f_days:
                    if wd == day_map[day_name]:
                        selected_dates.append(d)
            
            if f_days:
                st.caption(f"📅 วันที่ที่ตรงกัน: {', '.join(map(str, selected_dates))}")
        
        if st.form_submit_button("เพิ่มรายการ") and selected_dates:
            shift_code = {'เช้า (M)': 'M', 'บ่าย (S)': 'S', 'ดึก (N)': 'N'}[f_shift]
            st.session_state.fix_requests.append({
                'nurse': f_nurse,
                'shift': shift_code,
                'dates': selected_dates,
                'month': month,
                'year': year
            })
            save_fix_requests_to_csv()
            st.success(f"เพิ่มคำขอ Fix เวร {f_shift} สำหรับ {f_nurse} วันที่ {', '.join(map(str, selected_dates))} แล้ว!")
    
    if st.session_state.fix_requests:
        # แสดงรายการ fix requests
        fix_display = []
        for req in st.session_state.fix_requests:
            if req.get('month') == month and req.get('year') == year:
                fix_display.append({
                    'พยาบาล': req['nurse'],
                    'เวร': req['shift'],
                    'วันที่': ', '.join(map(str, req.get('dates', [])))
                })
        if fix_display:
            st.dataframe(pd.DataFrame(fix_display), hide_index=True)
        
        if st.button("🗑️ ล้างคำขอ Fix ทั้งหมด", type="secondary"):
            st.session_state.fix_requests = []
            save_fix_requests_to_csv()
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
            save_staffing_overrides_to_csv()
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
            save_staffing_overrides_to_csv()
            st.rerun()
    
    # ==========================================
    # ปุ่มควบคุม
    # ==========================================
    st.markdown("---")
    
    # ปุ่มรีเซ็ตทุกอย่าง (ล้างวันลา + ล้างตารางเวรเก่า)
    if st.button("🔄 รีเซ็ตทั้งหมด (ล้างวันลา+ตาราง+Fix+กำลังคน)", type="secondary"):
        st.session_state.requests = []
        st.session_state.fix_requests = []
        st.session_state.staffing_overrides = []
        st.session_state.schedule_df = None
        save_requests_to_csv()
        save_fix_requests_to_csv()
        save_staffing_overrides_to_csv()
        st.rerun()

    st.markdown("---")
    if st.button("🚀 ประมวลผลจัดตาราง", type="primary"):
        with st.spinner("กำลังคำนวณและเกลี่ยเวร..."):
            df = solve_schedule(
                year, month, days_in_month, nurses_list, 
                st.session_state.requests, er5_er10_pattern,
                st.session_state.fix_requests, st.session_state.staffing_overrides
            )
            if df is not None:
                st.session_state.schedule_df = df
                st.success("จัดตารางสำเร็จ!")
            else:
                st.error("ไม่สามารถจัดตารางได้! (เงื่อนไขขัดแย้งกัน)")

# --- Main Content ---
if st.session_state.schedule_df is not None:
    tab1, tab2, tab3 = st.tabs(["📅 ตารางเวร", "💰 ค่าตอบแทนและค่าเวร", "📅 ปฏิทินวันหยุด"])
    
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
            c_lt = shifts.count('ลา/อบรม')
            
            # รวม ลา/ประชุม กับเวรเช้า
            c_m_plus_lt = c_m + c_lt
            
            # NS นับเป็น 2 เวร (S+N) ในวันเดียว
            total_work = c_m + c_s + c_n + c_ns + c_lt
            
            # คำนวณเงิน
            # NS ได้ค่าเวร 2 เท่า (บ่าย+ดึก)
            shift_allowance = (c_s + c_n + c_ns * 2) * rate_sn  # NS = 2 เวร
            ot_shifts = max(0, total_work - std_work_days) + c_ns  # NS นับเป็น OT ด้วย
            ot_pay = ot_shifts * ot_rate  # เงิน OT
            total_income = shift_allowance + ot_pay  # รวมเงินทั้งหมด
            
            summary_data.append({
                'ชื่อ': row['Nurse'],
                'เวรเช้า+ลา (M)': c_m_plus_lt,
                'เวรบ่าย (S)': c_s,
                'เวรดึก (N)': c_n,
                'NS (OT)': c_ns,  # แสดง NS แยก
                'รวมวันทำงาน': total_work,
                'ค่าเวร บ่าย/ดึก': f"{shift_allowance:,}",
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
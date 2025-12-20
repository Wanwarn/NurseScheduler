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

CSV_FILE = "leave_requests.csv"

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
        # ถ้าไม่มีข้อมูล ให้ลบไฟล์ทิ้ง หรือสร้างไฟล์ว่าง
        if os.path.exists(CSV_FILE):
            os.remove(CSV_FILE)

# --- Helper Function ---
def get_week_occurrence(day):
    return (day - 1) // 7 + 1

# --- 1. ฟังก์ชันจัดตาราง (Scheduler Engine) ---
def solve_schedule(year, month, days_in_month, nurses, requests):
    model = cp_model.CpModel()
    
    shifts = ['S', 'M', 'N', 'O', 'L_T'] 
    work_shifts = ['S', 'M', 'N', 'L_T'] 

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

        # กำลังคน (ไม่นับ L_T)
        # วันหยุดนักขัตฤกษ์ ต้องการคนเท่าวันเสาร์-อาทิตย์ (M=4)
        is_special_day = is_weekend or is_holiday(year, month, d)
        
        model.Add(sum(shifts_var[(n, d, 'N')] for n in nurses) == 1)
        model.Add(sum(shifts_var[(n, d, 'S')] for n in nurses) == 2)
        req_m = 4 if is_special_day else 3  # เสาร์-อาทิตย์ หรือ วันหยุดนักขัตฤกษ์ = 4 คน
        model.Add(sum(shifts_var[(n, d, 'M')] for n in nurses) == req_m)

    # กฎการสลับเวร (ห้าม S -> N)
    for n in nurses:
        for d in range(1, days_in_month):
            model.Add(shifts_var[(n, d, 'S')] + shifts_var[(n, d + 1, 'N')] <= 1)

    # ==========================================
    # กฎเวรดึก (N) เดี่ยว - ต้องทำงานก่อนดึก และหยุดหลังดึก
    # ==========================================
    for n in nurses:
        # 1. ห้าม N-N (ดึกติดกัน)
        for d in range(1, days_in_month):
            model.Add(shifts_var[(n, d, 'N')] + shifts_var[(n, d + 1, 'N')] <= 1)
        
        # 2. ห้าม O-N (ต้องทำงานก่อนดึก ไม่ใช่หยุดแล้วมาดึก)
        for d in range(1, days_in_month):
            model.Add(shifts_var[(n, d, 'O')] + shifts_var[(n, d + 1, 'N')] <= 1)
        
        # 3. ห้าม N-O-N (ห้ามดึกสลับวัน)
        for d in range(1, days_in_month - 1):
            model.Add(shifts_var[(n, d, 'N')] + shifts_var[(n, d + 2, 'N')] <= 1)

    # ทำงานต่อเนื่องสูงสุด 7 วัน
    for n in nurses:
        for d in range(1, days_in_month - 6):
            model.Add(sum(sum(shifts_var[(n, d + k, s)] for s in work_shifts) for k in range(8)) <= 7)

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

        # ER3 (Soft Fix): วันจันทร์ทุกสัปดาห์ (เท่าที่ได้ ไม่เบียดเบียนผู้อื่น)
        if wd == 0:  # วันจันทร์ = 0
            preferred_constraints.append(shifts_var[('ER3', d, 'M')])

        # ER5 (Soft Fix): วันจันทร์ สัปดาห์ 1,4 & ศุกร์ สัปดาห์ 1 (เปลี่ยนจากอังคารเป็นจันทร์)
        if (wd == 0 and week_occurrence in [1, 4]) or (wd == 4 and week_occurrence == 1):
            preferred_constraints.append(shifts_var[('ER5', d, 'M')])

        # ER9 (Soft Fix): อังคาร สัปดาห์ 2,3
        if wd == 1 and week_occurrence in [2, 3]:
            preferred_constraints.append(shifts_var[('ER9', d, 'M')])

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
    # 4. เกลี่ยเวรบ่าย (S) และดึก (N) แยกกัน ต่างกันไม่เกิน 1
    # ==========================================
    s_shifts_per_nurse = {}
    n_shifts_per_nurse = {}
    
    for n in nurses_for_sn_fairness:
        s_shifts_per_nurse[n] = sum(shifts_var[(n, d, 'S')] for d in range(1, days_in_month + 1))
        n_shifts_per_nurse[n] = sum(shifts_var[(n, d, 'N')] for d in range(1, days_in_month + 1))
    
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
            # สร้าง indicator variable สำหรับ pattern: N -> O -> O
            # ใช้วิธีง่าย: ให้คะแนนเมื่อ Off หลัง N
            off_after_night_constraints.append(shifts_var[(n, d + 1, 'O')])
            # ให้น้ำหนักน้อยกว่า preferred_constraints เพื่อไม่ให้กระทบ soft fix อื่น
    
    # รวม soft constraints ทั้งหมดเข้าด้วยกัน โดยให้ preferred_constraints มีน้ำหนักมากกว่า
    # เป้าหมาย: พยายามทำตาม Soft Fix (Fix M) + Off หลัง N
    model.Maximize(sum(preferred_constraints) * 10 + sum(off_after_night_constraints))

    # Solve
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 20.0
    status = solver.Solve(model)

    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        schedule_data = []
        for n in nurses:
            row = {'Nurse': n}
            for d in range(1, days_in_month + 1):
                for s in shifts:
                    if solver.Value(shifts_var[(n, d, s)]):
                        display = s if s not in ['O'] else ""
                        if s == 'L_T': display = "ลา/อบรม"
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
st.set_page_config(page_title="ระบบจัดตารางเวร ER_KPH v2.0", layout="wide")
st.title("🏥 ระบบจัดตารางเวรพยาบาล (ER_KPH)")
st.caption("**v2.0** | วันหยุดนักขัตฤกษ์ 🟡 | เกลี่ยเวร S/N (Diff ≤ 1) | ดึกเดี่ยว | ER7 สัญญาพิเศษ")

# Session State
if 'schedule_df' not in st.session_state: st.session_state.schedule_df = None
if 'requests' not in st.session_state: 
    st.session_state.requests = load_requests_from_csv() # โหลดจากไฟล์เมื่อเริ่มโปรแกรม

# Sidebar
with st.sidebar:
    st.header("⚙️ ตั้งค่า")
    year = st.number_input("ปี (ค.ศ.)", 2024, 2030, 2025)
    month = st.selectbox("เดือน", range(1, 13), 10)
    _, days_in_month = calendar.monthrange(year, month)
    nurses_list = [f'ER{i}' for i in range(1, 11)]
    
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
            st.rerun()
    
    # ปุ่มรีเซ็ตทุกอย่าง (ล้างวันลา + ล้างตารางเวรเก่า)
    if st.button("🔄 รีเซ็ตทั้งหมด (ล้างวันลา+ตาราง)", type="secondary"):
        st.session_state.requests = []
        st.session_state.schedule_df = None
        st.rerun()

    st.markdown("---")
    if st.button("🚀 ประมวลผลจัดตาราง", type="primary"):
        with st.spinner("กำลังคำนวณและเกลี่ยเวร..."):
            df = solve_schedule(year, month, days_in_month, nurses_list, st.session_state.requests)
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
            c_lt = shifts.count('ลา/อบรม')
            
            # รวม ลา/ประชุม กับเวรเช้า
            c_m_plus_lt = c_m + c_lt
            
            total_work = c_m + c_s + c_n + c_lt
            
            # คำนวณเงิน
            shift_allowance = (c_s + c_n) * rate_sn # ค่าเวรบ่าย+ดึก
            ot_shifts = max(0, total_work - std_work_days) # จำนวนเวร OT
            ot_pay = ot_shifts * ot_rate # เงิน OT
            total_income = shift_allowance + ot_pay # รวมเงินทั้งหมด
            
            summary_data.append({
                'ชื่อ': row['Nurse'],
                'เวรเช้า+ลา (M)': c_m_plus_lt,  # รวม M + ลา/ประชุม
                'เวรบ่าย (S)': c_s,
                'เวรดึก (N)': c_n,
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
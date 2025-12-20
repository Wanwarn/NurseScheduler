import streamlit as st
from ortools.sat.python import cp_model
import pandas as pd
import calendar
import os # อย่าลืม import os

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
        model.Add(sum(shifts_var[(n, d, 'N')] for n in nurses) == 1)
        model.Add(sum(shifts_var[(n, d, 'S')] for n in nurses) == 2)
        req_m = 4 if is_weekend else 3
        model.Add(sum(shifts_var[(n, d, 'M')] for n in nurses) == req_m)

    # กฎการสลับเวร (ห้าม S -> N)
    for n in nurses:
        for d in range(1, days_in_month):
            model.Add(shifts_var[(n, d, 'S')] + shifts_var[(n, d + 1, 'N')] <= 1)

    # ดึก (N) ต่อเนื่องไม่เกิน 2 วัน
    for n in nurses:
        for d in range(1, days_in_month - 1):
            model.Add(shifts_var[(n, d, 'N')] + shifts_var[(n, d + 1, 'N')] + shifts_var[(n, d + 2, 'N')] <= 2)

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

        # ER1 (Hard Fix): จ-พฤ NCD, ศุกร์ M, ส-อา หยุด
        if wd in [0, 1, 2, 3]: model.Add(shifts_var[('ER1', d, 'O')] == 1) 
        elif wd == 4: model.Add(shifts_var[('ER1', d, 'M')] == 1)
        elif wd in [5, 6]: model.Add(shifts_var[('ER1', d, 'O')] == 1)

        # ER3 (Soft Fix): พุธ & พฤหัส สัปดาห์ 1, 3
        if wd in [2, 3] and week_occurrence in [1, 3]:
            preferred_constraints.append(shifts_var[('ER3', d, 'M')])

        # ER5 (Soft Fix): อังคาร สัปดาห์ 1,4 & ศุกร์ สัปดาห์ 1
        if (wd == 1 and week_occurrence in [1, 4]) or (wd == 4 and week_occurrence == 1):
            preferred_constraints.append(shifts_var[('ER5', d, 'M')])

      # ER9 (Soft Fix): อังคาร สัปดาห์ 2,3
        if wd == 1 and week_occurrence in [2, 3]:
            preferred_constraints.append(shifts_var[('ER9', d, 'M')])

        er7_m_shifts.append(shifts_var[('ER7', d, 'M')])
        er7_sn_shifts.append(shifts_var[('ER7', d, 'S')])
        er7_sn_shifts.append(shifts_var[('ER7', d, 'N')])

    # ER7 (Hard Fix): เช้า 10, บ่าย+ดึก 10
    model.Add(sum(er7_m_shifts) == 10)
    model.Add(sum(er7_sn_shifts) == 10)

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

    # ==========================================
    # 3. ระบบเกลี่ยเวร (Fairness Logic)
    # ==========================================
    
    # กลุ่มที่ต้องเกลี่ยเวร (ตัด ER1 และ ER7 ออก เพราะมีจำนวนเวร Fix ตายตัวตามเงื่อนไขสัญญา)
    rotating_nurses = [n for n in nurses if n not in ['ER1', 'ER7']]
    
    total_work_per_nurse = {}
    
    for n in rotating_nurses:
        # นับรวม M, S, N, L_T
        total_work_per_nurse[n] = sum(sum(shifts_var[(n, d, s)] for s in work_shifts) for d in range(1, days_in_month + 1))

    # กฎบังคับ: เวรรวมห้ามต่างกันเกิน 1 (เพื่อความแฟร์สูงสุด)
    # หากทำไม่ได้ Solver จะยอมตัด Soft Fix (Fix M) ทิ้งเพื่อให้ได้ความเท่าเทียม
    for n1 in rotating_nurses:
        for n2 in rotating_nurses:
            if n1 == n2: continue
            model.Add(total_work_per_nurse[n1] - total_work_per_nurse[n2] <= 1)

    # เป้าหมาย: พยายามทำตาม Soft Fix (Fix M) ให้มากที่สุดเท่าที่กฎความเท่าเทียมจะยอม
    model.Maximize(sum(preferred_constraints))

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
st.set_page_config(page_title="ระบบจัดตารางเวร ER_KPH", layout="wide")
st.title("🏥 ระบบจัดตารางเวรพยาบาล (ER_KPH)")
st.caption("Updated: คำนวณค่าเวรบ่าย/ดึก (360บ.) และเกลี่ยเวรให้เท่ากัน (Diff <= 1)")

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
    tab1, tab2 = st.tabs(["📅 ตารางเวร", "💰 ค่าตอบแทนและค่าเวร"])
    
    with tab1:
        st.subheader(f"ตารางเวรเดือน {month}/{year}")
        st.info("💡 **สามารถแก้ไขเวรได้โดยตรง** โดยคลิกที่ช่องที่ต้องการแก้ไข แล้วพิมพ์: M (เช้า), S (บ่าย), N (ดึก), ลา/อบรม, หรือเว้นว่างไว้ (หยุด)")
        
        # ใช้ data_editor แทน dataframe เพื่อให้แก้ไขได้
        edited_schedule = st.data_editor(
            st.session_state.schedule_df, 
            width='stretch',
            key="schedule_editor",
            num_rows="fixed"  # ไม่ให้เพิ่ม/ลบแถว
        )
        
        # ปุ่มบันทึกการแก้ไขและประมวลผลใหม่
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("💾 บันทึกการแก้ไข", type="primary"):
                st.session_state.schedule_df = edited_schedule
                st.success("บันทึกการแก้ไขแล้ว! ค่าตอบแทนจะถูกคำนวณใหม่โดยอัตโนมัติ")
                st.rerun()
        with col_btn2:
            if st.button("🔄 รีเซ็ตการแก้ไข (คืนค่าเดิม)"):
                st.rerun()

    with tab2:
        st.subheader("สรุปรายได้และภาระงาน")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            holidays = st.number_input("จำนวนวันหยุดนักขัตฤกษ์", 0, 15, 2)
        with col2:
            rate_sn = st.number_input("ค่าเวร บ่าย/ดึก (บาท/เวร)", value=360)
        with col3:
            ot_rate = st.number_input("ค่าตอบแทน OT (บาท/เวร)", value=720)
            
        std_work_days = days_in_month - holidays
        st.info(f"💡 เกณฑ์วันทำงานปกติ: **{std_work_days} วัน** (เกินจากนี้คิดเป็น OT)")
        
        summary_data = []
        for index, row in st.session_state.schedule_df.iterrows():
            shifts = [row[str(d)] for d in range(1, days_in_month + 1)]
            
            c_m = shifts.count('M')
            c_s = shifts.count('S')
            c_n = shifts.count('N')
            c_lt = shifts.count('ลา/อบรม')
            
            total_work = c_m + c_s + c_n + c_lt
            
            # คำนวณเงิน
            shift_allowance = (c_s + c_n) * rate_sn # ค่าเวรบ่าย+ดึก
            ot_shifts = max(0, total_work - std_work_days) # จำนวนเวร OT
            ot_pay = ot_shifts * ot_rate # เงิน OT
            total_income = shift_allowance + ot_pay # รวมเงินทั้งหมด
            
            summary_data.append({
                'ชื่อ': row['Nurse'],
                'เวรเช้า (M)': c_m,
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
"""
Scheduler engine for NurseApp - OR-Tools CP-SAT Solver
Extracted from app.py for maintainability
"""
import logging
import calendar
import pandas as pd
from ortools.sat.python import cp_model

from src.config import THAI_HOLIDAYS, NURSE_NAMES, is_holiday
from src.utils import get_week_occurrence

logger = logging.getLogger(__name__)


# --- 1. ฟังก์ชันจัดตาราง (Scheduler Engine) ---
def solve_schedule(year, month, days_in_month, nurses, requests, fix_requests=None, staffing_overrides=None, enable_oc=True, prev_month_data=None, ns_target=0, external_staff=None, strict_48hrs=True, oc_1_10=True, oc_11_20=False, oc_21_end=False, strict_smn=True, strict_nn=False):
    if fix_requests is None:
        fix_requests = []
    if staffing_overrides is None:
        staffing_overrides = []
    if external_staff is None:
        external_staff = []
    
    model = cp_model.CpModel()
    
    # เพิ่ม NS (บ่าย+ดึก 16 ชม.) เป็น OT shift, OC = On-Call Standby
    shifts = ['S', 'M', 'N', 'O', 'L_T', 'NS', 'OC'] 
    work_shifts = ['S', 'M', 'N', 'L_T', 'NS']  # NS นับเป็นวันทำงาน (OC ไม่นับสำหรับเกลี่ยเวร)
    active_shifts = ['S', 'M', 'N', 'L_T', 'NS', 'OC']  # รวม OC สำหรับนับวันทำงานต่อเนื่อง (พยาบาลยังต้องอยู่เวร)
    
    # กลุ่มพยาบาลสำหรับเวร OC
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
            
            # นับวันทำงานต่อเนื่องข้ามเดือน (กฎ 6 วัน ≤48 ชม./สัปดาห์)
            if n in prev_month_data and len(prev_month_data[n]) >= 7:
                consecutive_work = 0
                for s in reversed(prev_month_data[n]):
                    if s in ['S', 'M', 'N', 'L_T', 'NS']:
                        consecutive_work += 1
                    else:
                        break  # หยุดนับเมื่อเจอวันหยุด
                
                if consecutive_work >= 6:
                    for work_s in ['S', 'M', 'N', 'NS']:
                        model.Add(shifts_var[(n, 1, work_s)] == 0)
                elif consecutive_work >= 5:
                    model.Add(
                        shifts_var[(n, 1, 'O')] + shifts_var[(n, 2, 'O')] >= 1
                    )
                elif consecutive_work >= 4:
                    model.Add(
                        shifts_var[(n, 1, 'O')] + shifts_var[(n, 2, 'O')] + shifts_var[(n, 3, 'O')] >= 1
                    )

    # ==========================================
    # 🎯 คำนวณเป้าหมายวันทำการ (Auto Calculate Work Days)
    # ==========================================
    weekends = 0
    for d in range(1, days_in_month + 1):
        if calendar.weekday(year, month, d) >= 5:
            weekends += 1
            
    holidays_weekday = 0
    holiday_list = THAI_HOLIDAYS.get(year, {}).get(month, [])
    for d in holiday_list:
        if calendar.weekday(year, month, d) < 5:
            holidays_weekday += 1
            
    target_work_days = days_in_month - (weekends + holidays_weekday)
    logger.info(f"[TARGET] Month {month}/{year}: {days_in_month} days, holidays {weekends+holidays_weekday}, target work = {target_work_days} days")
    
    # ==========================================
    # 1. กฎพื้นฐานและกำลังคน (Hard Constraints)
    # ==========================================
    for d in range(1, days_in_month + 1):
        weekday = calendar.weekday(year, month, d)
        is_weekend = weekday >= 5 

        for n in nurses:
            model.Add(sum(shifts_var[(n, d, s)] for s in shifts) == 1)

        is_special_day = is_weekend or is_holiday(year, month, d)
        n_req = 1
        s_req = 2
        
        for override in staffing_overrides:
            if override.get('month') == month and override.get('year') == year:
                if override.get('start', 1) <= d <= override.get('end', days_in_month):
                    if override.get('shift') == 'N':
                        n_req = override.get('count', 1)
                    elif override.get('shift') == 'S':
                        s_req = override.get('count', 2)
        
        ext_m = sum(1 for ext in external_staff if ext.get('date') == d and ext.get('month') == month and ext.get('year') == year and ext.get('shift') == 'M')
        ext_s = sum(1 for ext in external_staff if ext.get('date') == d and ext.get('month') == month and ext.get('year') == year and ext.get('shift') == 'S')
        ext_n = sum(1 for ext in external_staff if ext.get('date') == d and ext.get('month') == month and ext.get('year') == year and ext.get('shift') == 'N')
        n_req = max(0, n_req - ext_n)
        s_req = max(0, s_req - ext_s)
        
        if ext_m + ext_s + ext_n > 0:
            logger.info(f"[EXT] Day {d}: external M={ext_m}, S={ext_s}, N={ext_n}")
        
        model.Add(sum(shifts_var[(n, d, 'N')] + shifts_var[(n, d, 'NS')] for n in nurses) == n_req)
        model.Add(sum(shifts_var[(n, d, 'S')] + shifts_var[(n, d, 'NS')] for n in nurses) == s_req)
        req_m = 4 if is_special_day else 3
        req_m = max(0, req_m - ext_m)
        model.Add(sum(shifts_var[(n, d, 'M')] for n in nurses) == req_m)

    # ==========================================
    # กฎการสลับเวร (Shift Transitions)
    # ==========================================
    for n in nurses:
        for d in range(1, days_in_month):
            # ห้าม S -> N (บ่ายตามด้วยดึก)
            model.Add(shifts_var[(n, d, 'S')] + shifts_var[(n, d + 1, 'N')] <= 1)
            model.Add(shifts_var[(n, d, 'S')] + shifts_var[(n, d + 1, 'NS')] <= 1)

    # ------------------------------------------
    # 3.1 Rule S->M->N (บ่าย -> เช้า -> ดึก)
    # ------------------------------------------
    smn_penalty_list = []
    for n in nurses:
        for d in range(1, days_in_month - 1):
            if strict_smn:
                model.Add(shifts_var[(n, d, 'S')] + shifts_var[(n, d + 1, 'M')] + shifts_var[(n, d + 2, 'N')] <= 2)
                model.Add(shifts_var[(n, d, 'S')] + shifts_var[(n, d + 1, 'M')] + shifts_var[(n, d + 2, 'NS')] <= 2)
            else:
                pen_smn = model.NewBoolVar(f'smn_pen_{n}_{d}')
                model.Add(shifts_var[(n, d, 'S')] + shifts_var[(n, d + 1, 'M')] + shifts_var[(n, d + 2, 'N')] <= 2 + pen_smn)
                model.Add(shifts_var[(n, d, 'S')] + shifts_var[(n, d + 1, 'M')] + shifts_var[(n, d + 2, 'NS')] <= 2 + pen_smn)
                smn_penalty_list.append(pen_smn)
    
    # S -> O -> N, NS -> O -> N (บ่าย/ดึก+บ่าย -> หยุด -> ดึก) - HARD CONSTRAINT
    s_o_n_penalty = []
    for n in nurses:
        for d in range(1, days_in_month - 1):
            model.Add(shifts_var[(n, d, 'S')] + shifts_var[(n, d + 1, 'O')] + shifts_var[(n, d + 2, 'N')] <= 2)
            model.Add(shifts_var[(n, d, 'S')] + shifts_var[(n, d + 1, 'O')] + shifts_var[(n, d + 2, 'NS')] <= 2)
            model.Add(shifts_var[(n, d, 'NS')] + shifts_var[(n, d + 1, 'O')] + shifts_var[(n, d + 2, 'N')] <= 2)
            model.Add(shifts_var[(n, d, 'NS')] + shifts_var[(n, d + 1, 'O')] + shifts_var[(n, d + 2, 'NS')] <= 2)

    # ==========================================
    # 3.2 Rule Consecutive Nights (N->N modified)
    # ==========================================
    o_before_n_penalty = []
    n_skip_day_penalty = []
    nn_consecutive_penalty = []
    
    for n in nurses:
        # NS (16 ชม.) ห้ามติดกันเด็ดขาดทุกกรณี
        for d in range(1, days_in_month):
            model.Add(shifts_var[(n, d, 'NS')] + shifts_var[(n, d + 1, 'NS')] <= 1)
            model.Add(shifts_var[(n, d, 'N')] + shifts_var[(n, d + 1, 'NS')] <= 1)
            model.Add(shifts_var[(n, d, 'NS')] + shifts_var[(n, d + 1, 'N')] <= 1)
        
        if strict_nn:
            # HARD MODE: ห้ามดึกติดกันเด็ดขาด (N -> N ห้าม)
            for d in range(1, days_in_month):
                model.Add(shifts_var[(n, d, 'N')] + shifts_var[(n, d + 1, 'N')] <= 1)
        else:
            # SOFT MODE: อนุญาต N -> N ได้สูงสุด 2 วันติดกัน
            # แต่บังคับ HARD ว่า วันที่ 3 (d+2) ต้องเป็น 'O' หรือ 'S' เท่านั้น (ห้าม M, N, NS, L_T)
            for d in range(1, days_in_month - 1):
                model.Add(shifts_var[(n, d, 'N')] + shifts_var[(n, d + 1, 'N')] + shifts_var[(n, d + 2, 'M')] <= 2)
                model.Add(shifts_var[(n, d, 'N')] + shifts_var[(n, d + 1, 'N')] + shifts_var[(n, d + 2, 'N')] <= 2)
                model.Add(shifts_var[(n, d, 'N')] + shifts_var[(n, d + 1, 'N')] + shifts_var[(n, d + 2, 'NS')] <= 2)
                model.Add(shifts_var[(n, d, 'N')] + shifts_var[(n, d + 1, 'N')] + shifts_var[(n, d + 2, 'L_T')] <= 2)
            
            # Soft Penalty: หักคะแนนเพื่อลดการจัดดึกติดกัน
            for d in range(1, days_in_month):
                nn_pen = model.NewBoolVar(f'nn_pen_{n}_{d}')
                model.Add(shifts_var[(n, d, 'N')] + shifts_var[(n, d + 1, 'N')] <= 1 + nn_pen)
                nn_consecutive_penalty.append(nn_pen)
        
        # 2. O-N, O-NS (ควรทำงานก่อนดึก) - SOFT
        for d in range(1, days_in_month):
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
    # 4. กฎช่วงวันลา/อบรม (Leave/Train Boundary Constraints)
    # ==========================================
    # NOTE: L_T boundary bonus จะถูกเพิ่มภายหลังใน section "Post L_T Boundary"
    # หลังจาก allowed_lt ถูก populate แล้ว
    lt_boundary_bonus = []

    # ==========================================
    # กฎเวร NS (บ่าย+ดึก 16 ชม.) - OT Shift
    # ==========================================
    nurses_for_ns = [n for n in nurses if n not in ['ER1']]
    
    for n in nurses_for_ns:
        for d in range(1, days_in_month - 3):
            model.Add(shifts_var[(n, d, 'NS')] + shifts_var[(n, d + 1, 'NS')] + 
                      shifts_var[(n, d + 2, 'NS')] + shifts_var[(n, d + 3, 'NS')] + 
                      shifts_var[(n, d + 4, 'NS')] <= 1)
        
        for d in range(1, days_in_month):
            for work_s in ['S', 'M', 'N', 'NS']:
                model.Add(shifts_var[(n, d, 'NS')] + shifts_var[(n, d + 1, work_s)] <= 1)
    
    for d in range(1, days_in_month + 1):
        model.Add(shifts_var[('ER1', d, 'NS')] == 0)
    
    ns_penalty = []
    for n in nurses_for_ns:
        ns_total = sum(shifts_var[(n, d, 'NS')] for d in range(1, days_in_month + 1))
        ns_excess = model.NewIntVar(0, days_in_month, f'ns_excess_{n}')
        model.Add(ns_excess >= ns_total - ns_target)
        ns_penalty.append(ns_excess)

    # ==========================================
    # 1. กฎ 48 ชม./สัปดาห์ (48 Hours/Week Limit)
    # ==========================================
    pen_48hrs_list = []
    six_day_streak_penalty = []
    
    for n in nurses:
        # ตรวจสอบทุกช่วง 7 วันติดต่อกัน (d ถึง d+6)
        for d in range(1, days_in_month - 5):
            total_hours = sum(
                8 * shifts_var[(n, d + k, 'M')] +
                8 * shifts_var[(n, d + k, 'S')] +
                8 * shifts_var[(n, d + k, 'N')] +
                8 * shifts_var[(n, d + k, 'L_T')] +
                16 * shifts_var[(n, d + k, 'NS')]
                for k in range(7)
            )
            if strict_48hrs:
                model.Add(total_hours <= 48)
            else:
                pen_48h = model.NewIntVar(0, 112, f'pen_48h_{n}_{d}')
                model.Add(pen_48h >= total_hours - 48)
                pen_48hrs_list.append(pen_48h)
        
        # เช็คช่วง 7 วันย้อนหลังปลายเดือน
        for d in range(max(7, days_in_month - 5), days_in_month + 1):
            total_hours_end = sum(
                8 * shifts_var[(n, d - k, 'M')] +
                8 * shifts_var[(n, d - k, 'S')] +
                8 * shifts_var[(n, d - k, 'N')] +
                8 * shifts_var[(n, d - k, 'L_T')] +
                16 * shifts_var[(n, d - k, 'NS')]
                for k in range(7)
            )
            if strict_48hrs:
                model.Add(total_hours_end <= 48)
            else:
                pen_48h_end = model.NewIntVar(0, 112, f'pen_48h_end_{n}_{d}')
                model.Add(pen_48h_end >= total_hours_end - 48)
                pen_48hrs_list.append(pen_48h_end)
    
    # ป้องกัน NS หลังทำงานใกล้เต็มโควต้า 48 ชม.
    for n in nurses_for_ns:
        for d in range(7, days_in_month + 1):
            prev_hours = sum(
                8 * shifts_var[(n, d - k, 'M')] +
                8 * shifts_var[(n, d - k, 'S')] +
                8 * shifts_var[(n, d - k, 'N')] +
                8 * shifts_var[(n, d - k, 'L_T')] +
                16 * shifts_var[(n, d - k, 'NS')]
                for k in range(1, 7)
            )
            if strict_48hrs:
                model.Add(prev_hours + 16 * shifts_var[(n, d, 'NS')] <= 48)

    # ==========================================
    # 2. กฎเวร OC (On-Call Standby) - 3 ช่วง
    # ==========================================
    oc_avoid_penalty = []
    active_oc_days = set()
    if enable_oc:
        if oc_1_10:
            active_oc_days.update(range(1, min(11, days_in_month + 1)))
        if oc_11_20:
            active_oc_days.update(range(11, min(21, days_in_month + 1)))
        if oc_21_end:
            active_oc_days.update(range(21, days_in_month + 1))

    for d in range(1, days_in_month + 1):
        if d in active_oc_days:
            model.Add(sum(shifts_var[(n, d, 'OC')] for n in nurses) >= 1)
        else:
            for n in nurses:
                model.Add(shifts_var[(n, d, 'OC')] == 0)

    for d in range(1, days_in_month + 1):
        for n in oc_hard_ban:
            model.Add(shifts_var[(n, d, 'OC')] == 0)

    for n in nurses:
        for d in range(1, days_in_month):
            model.Add(shifts_var[(n, d, 'OC')] + shifts_var[(n, d + 1, 'OC')] <= 1)
            model.Add(shifts_var[(n, d, 'OC')] + shifts_var[(n, d + 1, 'M')] <= 1)

        for d in range(1, days_in_month - 3 + 1):
            model.Add(shifts_var[(n, d, 'OC')] + shifts_var[(n, d + 1, 'OC')] + 
                      shifts_var[(n, d + 2, 'OC')] + shifts_var[(n, d + 3, 'OC')] <= 1)

    for d in active_oc_days:
        for n in oc_soft_avoid:
            oc_avoid_penalty.append(shifts_var[(n, d, 'OC')])


    # ==========================================
    # 2. เงื่อนไขรายบุคคล (Preferences & Fix)
    # ==========================================
    preferred_constraints = [] 
    er7_m_shifts = []
    er7_sn_shifts = []

    # สร้าง set ของวันที่ ER1 ขอลา (เพื่อเช็ควันศุกร์)
    er1_leave_days = set()
    for req in requests:
        req_month = req.get('month', month)
        req_year = req.get('year', year)
        if req_month == month and req_year == year:
            if req.get('nurse') == 'ER1' and req.get('type') in ['Leave_Train', 'Leave', 'Train']:
                er1_leave_days.add(req.get('date'))
    
    # สร้าง dict ของวันที่ ER1 มี fix request (เพื่อ override hard O ในวันหยุด/สุดสัปดาห์)
    er1_fix_days = {}
    for req in fix_requests:
        if req.get('nurse') == 'ER1' and req.get('month') == month and req.get('year') == year:
            shift = req.get('shift')
            if shift in ['M', 'S', 'N']:
                for d in req.get('dates', []):
                    er1_fix_days[d] = shift
    
    for d in range(1, days_in_month + 1):
        wd = calendar.weekday(year, month, d)
        week_occurrence = get_week_occurrence(d)

        # ER1 (Hard Fix): จ-พฤ NCD, ศุกร์ M, ส-อา หยุด, วันหยุดนักขัตฤกษ์ หยุด
        # ถ้ามี fix request → override ได้ (บังคับเวรตามที่ขอแทนหยุด)
        is_hol = is_holiday(year, month, d)
        if is_hol or wd in [5, 6]:  # วันหยุดนักขัตฤกษ์ หรือ ส-อา
            if d in er1_fix_days:
                # มี fix request → บังคับเวรตามที่ขอ (override วันหยุด)
                model.Add(shifts_var[('ER1', d, er1_fix_days[d])] == 1)
                logger.info(f"[ER1] Fix override: day {d} → {er1_fix_days[d]} (holiday/weekend)")
            else:
                model.Add(shifts_var[('ER1', d, 'O')] == 1)
        elif wd in [0, 1, 2, 3]:  # จ-พฤ = NCD (แสดงเป็น O ในตาราง)
            model.Add(shifts_var[('ER1', d, 'O')] == 1)
        elif wd == 4:  # ศุกร์
            # ถ้า ER1 ลาวันศุกร์นี้ → ไม่บังคับ M (จะถูกบังคับ L_T ในส่วน requests ด้านล่าง)
            # ระบบจะจัดคนอื่นมาทำเวร M แทนให้ครบ 3 คน
            if d not in er1_leave_days:
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
        # NS นับเป็น 2 เวร: 1 S + 1 N (16 ชม. = บ่าย+ดึก)
        er7_sn_shifts.append(shifts_var[('ER7', d, 'NS')])  # นับเป็น S
        er7_sn_shifts.append(shifts_var[('ER7', d, 'NS')])  # นับเป็น N

    # ==========================================
    # [FIXED] ER7 Contract: เช้า 10, บ่าย+ดึก = 10, รวม 20 เวร
    # ==========================================
    er7_lt_shifts = [shifts_var[('ER7', d, 'L_T')] for d in range(1, days_in_month + 1)]
    er7_ns_shifts = [shifts_var[('ER7', d, 'NS')] for d in range(1, days_in_month + 1)]
    
    # รวมผลรวมเวรต่างๆ ของ ER7
    er7_total_m = sum(er7_m_shifts)
    er7_total_lt = sum(er7_lt_shifts)  # วันลา/อบรม (นับรวมในโควตาเช้า)
    er7_total_sn = sum(er7_sn_shifts)  # บ่าย + ดึก + NS*2
    er7_total_ns = sum(er7_ns_shifts)  # NS เพื่อใช้ในการนับ N ทั้งหมด
    
    # --- กฎข้อที่ 1: เวรเช้า + ลา ต้องเท่ากับ 10 (Hard Constraint) ---
    model.Add(er7_total_m + er7_total_lt == 10)
    
    # --- กฎข้อที่ 2: บ่าย + ดึก + NS*2 ต้องเท่ากับ 10 (Hard Constraint) ---
    model.Add(er7_total_sn == 10)
    
    # --- กฎข้อที่ 3: N ทั้งหมด (N + NS) ห้ามเกิน 4 ---
    # NS นับเป็น N ด้วย เพราะ NS = S+N (16 ชม.)
    er7_n_shifts = [shifts_var[('ER7', d, 'N')] for d in range(1, days_in_month + 1)]
    model.Add(sum(er7_n_shifts) + er7_total_ns <= 4)  # N + NS ≤ 4
    
    logger.info("[ER7] Contract: M+leave=10, S+N+NS*2=10, N+NS<=4, Total=20")

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
                    try:
                        priority = int(req.get('priority', 1))
                    except (ValueError, TypeError):
                        priority = 1
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
    # 4. Post L_T Boundary - ใช้เฉพาะวันที่มีคำขอลาจริง
    # ==========================================
    for (nurse, lt_day) in allowed_lt:
        # 4.1 Before L_T (วันก่อนลา): ห้าม S ก่อน L_T (HARD)
        if lt_day > 1:
            model.Add(shifts_var[(nurse, lt_day - 1, 'S')] + shifts_var[(nurse, lt_day, 'L_T')] <= 1)
            
            # SOFT: Prefer O ก่อน L_T (โบนัส)
            is_o_before = model.NewBoolVar(f'o_before_lt_{nurse}_{lt_day}')
            model.Add(shifts_var[(nurse, lt_day - 1, 'O')] >= is_o_before)
            model.Add(shifts_var[(nurse, lt_day, 'L_T')] >= is_o_before)
            lt_boundary_bonus.append(is_o_before)
        
        # 4.2 After L_T (วันหลังลา): ห้าม N และ NS หลัง L_T (HARD)
        if lt_day < days_in_month:
            model.Add(shifts_var[(nurse, lt_day, 'L_T')] + shifts_var[(nurse, lt_day + 1, 'N')] <= 1)
            model.Add(shifts_var[(nurse, lt_day, 'L_T')] + shifts_var[(nurse, lt_day + 1, 'NS')] <= 1)
            
            # SOFT: Prefer O หลัง L_T (โบนัส)
            is_o_after = model.NewBoolVar(f'o_after_lt_{nurse}_{lt_day}')
            model.Add(shifts_var[(nurse, lt_day + 1, 'O')] >= is_o_after)
            model.Add(shifts_var[(nurse, lt_day, 'L_T')] >= is_o_after)
            lt_boundary_bonus.append(is_o_after)

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
        
        # [แก้] ลบ Hard Constraint ทิ้ง ใช้ Soft Constraint อย่างเดียว
        # model.Add(total_work_per_nurse[n] >= target_work_days - 2)  # <-- ลบ
        # model.Add(total_work_per_nurse[n] <= target_work_days + 2)  # <-- ลบ
        
        # สร้างตัวแปร Diff: |จำนวนวันที่ทำ - เป้าหมายเดือนนี้|
        diff = model.NewIntVar(0, days_in_month, f'diff_work_{n}')
        model.AddAbsEquality(diff, total_work_per_nurse[n] - target_work_days)
        work_days_diff.append(diff)

    # กฎบังคับ: เวรรวมห้ามต่างกันเกิน 2 (ผ่อนคลายเพื่อความยืดหยุ่น)
    for n1 in rotating_nurses:
        for n2 in rotating_nurses:
            if n1 == n2: continue
            model.Add(total_work_per_nurse[n1] - total_work_per_nurse[n2] <= 2)
    
    # ==========================================
    # 3.0.1 NS Avoidance Penalty: ทำให้ NS เป็นทางเลือกสุดท้าย
    # ==========================================
    ns_avoidance_penalty = []
    for n in nurses_for_ns:
        for d in range(1, days_in_month + 1):
            ns_avoidance_penalty.append(shifts_var[(n, d, 'NS')])
    
    # ==========================================
    # 3.0.2 Prefer เวรเช้าวันหยุด (แทน NS)
    # ==========================================
    # Prefer เวรเช้าวันหยุด (ส-อา, นักขัตฤกษ์) เพื่อเติมให้ครบเป้า แทนที่จะใช้ NS
    holiday_morning_bonus = []
    weekend_days = [d for d in range(1, days_in_month + 1) if calendar.weekday(year, month, d) >= 5]
    holiday_days = THAI_HOLIDAYS.get(year, {}).get(month, [])
    special_days_for_bonus = list(set(weekend_days + holiday_days))
    
    for n in rotating_nurses:
        for d in special_days_for_bonus:
            # ให้คะแนนบวกสำหรับ M ในวันหยุด (ทดแทน NS)
            holiday_morning_bonus.append(shifts_var[(n, d, 'M')])
    
    # ==========================================
    # 3.1 วันหยุดของแต่ละคน - คำนวณจากจำนวนเวรจริง (ไม่ใช่ปฏิทิน)
    # ==========================================
    # คำนวณจำนวนเวรทั้งหมดต่อวัน แล้วหาจำนวนวันหยุดจริงที่เป็นไปได้
    total_shifts_needed = 0
    for d in range(1, days_in_month + 1):
        wd = calendar.weekday(year, month, d)
        is_sp = wd >= 5 or is_holiday(year, month, d)
        day_m = 4 if is_sp else 3
        total_shifts_needed += day_m + 2 + 1  # M + S(2) + N(1)
    
    num_rotating = len(rotating_nurses)
    if num_rotating > 0:
        avg_shifts = total_shifts_needed / num_rotating
        actual_off_per_nurse = max(0, int(days_in_month - avg_shifts))
        # ใช้ค่าที่น้อยกว่าระหว่าง calendar-based กับ staffing-based
        target_off_days = min(weekends + holidays_weekday, actual_off_per_nurse + 2)
    else:
        target_off_days = weekends + holidays_weekday
    
    logger.info(f"[OFF] Calendar off={weekends + holidays_weekday}, Actual capacity off={actual_off_per_nurse if num_rotating > 0 else 'N/A'}, Target off={target_off_days}")
    
    # กำหนดให้ทุกคน (ยกเว้น ER1) มีวันหยุดใกล้เคียงกับ target (±2)
    for n in rotating_nurses:
        off_days = sum(shifts_var[(n, d, 'O')] for d in range(1, days_in_month + 1))
        # RELAXED: Off อนุญาตให้ต่างจาก target ได้ ±2 วัน
        model.Add(off_days >= max(0, target_off_days - 2))
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
    
    # RELAXED: เกลี่ยให้ต่างกันไม่เกิน 2 (ยืดหยุ่นขึ้น)
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
    
    # เวรบ่าย (S) ต่างกันไม่เกิน 2
    for n1 in nurses_for_sn_fairness:
        for n2 in nurses_for_sn_fairness:
            if n1 == n2: continue
            model.Add(s_shifts_per_nurse[n1] - s_shifts_per_nurse[n2] <= 2)
    
    # เวรดึก (N) ต่างกันไม่เกิน 2
    for n1 in nurses_for_sn_fairness:
        for n2 in nurses_for_sn_fairness:
            if n1 == n2: continue
            model.Add(n_shifts_per_nurse[n1] - n_shifts_per_nurse[n2] <= 2)
    
    # ==========================================
    # 4.1 เกลี่ย OT (NS) ให้เท่ากัน ±1
    # ==========================================
    # OT = เมื่อทำงาน > 8 ชม./วัน
    # NS = 16 ชม. (S+N) = 1 OT (ไม่ใช่ 2 OT)
    # ยกเว้น ER1 (ไม่ทำ NS) และ ER7 (มี contract พิเศษ)
    nurses_for_ot_fairness = [n for n in nurses if n not in ['ER1', 'ER7']]
    ot_per_nurse = {}
    
    for n in nurses_for_ot_fairness:
        # OT = จำนวน NS (เพราะ NS 16 ชม. = 1 OT)
        ot_per_nurse[n] = sum(shifts_var[(n, d, 'NS')] for d in range(1, days_in_month + 1))
    
    # เกลี่ย OT ต่างกันไม่เกิน 2
    for n1 in nurses_for_ot_fairness:
        for n2 in nurses_for_ot_fairness:
            if n1 == n2: continue
            model.Add(ot_per_nurse[n1] - ot_per_nurse[n2] <= 2)

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
    
    # ==========================================
    # 8. Hard Constraint: ห้าม O-เวร-O (ห้ามทำงาน 1 วันเดี่ยวๆ แล้วหยุด)
    # ==========================================
    # เหตุผล: ถ้าหยุดวันก่อนและหยุดวันหลัง ห้ามทำงานแค่ 1 วันตรงกลาง
    # ยกเว้น ER1 (สัญญาพิเศษ: NCD จ-พฤ → M ศ → Off ส-อา = O-M-O ทุกสัปดาห์)
    # OC และ L_T ไม่ถือเป็นเวรทำงานปกติ จึงอนุญาตให้อยู่ตรงกลางได้
    nurses_for_isolated_rule = [n for n in nurses if n != 'ER1']
    
    for n in nurses_for_isolated_rule:
        for d in range(2, days_in_month):  # d ตั้งแต่วันที่ 2 ถึง days_in_month-1
            # ถ้า O(d-1) + O(d+1) = 2 → d ต้องเป็น O/OC/L_T (ห้ามทำงาน)
            model.Add(
                shifts_var[(n, d - 1, 'O')] + shifts_var[(n, d + 1, 'O')]
                <= 1 + shifts_var[(n, d, 'O')] + shifts_var[(n, d, 'OC')] + shifts_var[(n, d, 'L_T')]
            )
    
    # รวม soft constraints ทั้งหมดเข้าด้วยกัน
    model.Maximize(
        sum(preferred_constraints) * 100 + 
        sum(consecutive_off_constraints) * 5 +
        sum(off_after_night_constraints) +
        sum(holiday_morning_bonus) * 25 +  # โบนัสสำหรับ M ในวันหยุด (ทดแทน NS)
        sum(lt_boundary_bonus) * 60 -     # โบนัสสำหรับ O ก่อน/หลัง ลา (L_T)
        sum(separation_penalty) * 30 -     # ลบคะแนนเมื่อ ER2-ER7 ซ้อนเวรกัน
        sum(oc_avoid_penalty) * 100 -     # หักหนัก: เลี่ยงจัดเวร OC ให้ ER4, ER8
        sum(o_before_n_penalty) * 80 -     # ลบคะแนนเมื่อ O→N (หลีกเลี่ยงดึกหลังหยุด)
        sum(n_skip_day_penalty) * 10 -     # ลบคะแนนเมื่อ N-O-N (ดึกสลับวัน)
        sum(nn_consecutive_penalty) * 15 - # ลบคะแนนน้อย: N→N อนุญาตได้สูงสุด 2 ติด (ในโหมด Soft)
        sum(smn_penalty_list) * 80 -       # หักคะแนนถ้าเกิด S->M->N (ในโหมด Soft)
        sum(pen_48hrs_list) * 200 -        # หักคะแนนถ้าเกิน 48 ชม./สัปดาห์ (ในโหมด Soft)
        sum(ns_avoidance_penalty) * 500 -  # หักหนักๆ ให้ NS เป็นทางเลือกสุดท้าย
        sum(ns_penalty) * 200 -            # หักคะแนน NS excess (เกินจาก ns_target)
        sum(s_o_n_penalty) * 35 -          # Penalty สำหรับ S-O-N (เสียวันหยุดฟรี)
        sum(six_day_streak_penalty) * 45 -  # Penalty สำหรับทำงาน 6 วันติด
        sum(work_days_diff) * 50           # หักคะแนนถ้าวันทำงานไม่ตรงเป้า
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
                            # แสดง NCD เฉพาะวันจ-พฤ ที่ไม่ใช่วันหยุดนักขัตฤกษ์
                            if wd in [0, 1, 2, 3] and not is_holiday(year, month, d):
                                display = "NCD"
                        row[str(d)] = display
                        break
            schedule_data.append(row)
        return pd.DataFrame(schedule_data)
    else:
        return None

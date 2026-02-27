"""
Google Sheets integration for NurseApp
"""
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import pandas as pd
import calendar
import logging

from src.config import SCOPE, CREDENTIALS_FILE, get_sheet_url, get_thai_time, NURSE_NAMES
from src.utils import extract_nurse_id

logger = logging.getLogger(__name__)


@st.cache_resource(ttl=300)
def connect_gsheet():
    """เชื่อมต่อกับ Google Sheets (รองรับทั้ง local และ Streamlit Cloud)"""
    try:
        # วิธีที่ 1: ใช้ Streamlit Cloud Secrets (สำหรับ deploy บน cloud)
        if hasattr(st, 'secrets') and 'gcp_service_account' in st.secrets:
            from google.oauth2.service_account import Credentials
            creds = Credentials.from_service_account_info(
                st.secrets["gcp_service_account"],
                scopes=SCOPE
            )
            client = gspread.authorize(creds)
        # วิธีที่ 2: ใช้ไฟล์ service_account.json (สำหรับรันบนเครื่อง local)
        elif os.path.exists(CREDENTIALS_FILE):
            creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, SCOPE)
            client = gspread.authorize(creds)
        else:
            st.error("❌ ไม่พบ credentials! กรุณาตั้งค่า Secrets หรือใส่ไฟล์ service_account.json")
            return None
        
        sheet = client.open_by_url(get_sheet_url())
        return sheet
    except gspread.exceptions.APIError as e:
        logger.error(f"Google Sheets API error: {e}")
        st.error(f"❌ Google Sheets API error: {e}")
        return None
    except gspread.exceptions.SpreadsheetNotFound as e:
        logger.error(f"Spreadsheet not found: {e}")
        st.error(f"❌ ไม่พบ Spreadsheet: {e}")
        return None
    except Exception as e:
        logger.exception(f"Unexpected error connecting to Google Sheets: {e}")
        st.error(f"❌ เชื่อมต่อ Google Sheets ไม่สำเร็จ: {e}")
        return None


# --- Leave Requests ---
def load_requests_from_gsheet():
    """โหลดข้อมูลวันลาจาก Google Sheets"""
    try:
        sh = connect_gsheet()
        if not sh:
            return []
        records = sh.worksheet("LeaveRequests").get_all_records()
        records = [r for r in records if r.get('nurse') and str(r.get('nurse')).strip()]
        
        sync_time = get_thai_time()
        
        for r in records:
            r['nurse'] = extract_nurse_id(r.get('nurse'))
            try:
                r['date'] = int(r.get('date', 0))
                r['month'] = int(r.get('month', 0))
                r['year'] = int(r.get('year', 0))
            except (ValueError, TypeError):
                pass
            if not r.get('timestamp'):
                r['timestamp'] = f"(synced: {sync_time})"
        return records
    except gspread.exceptions.WorksheetNotFound:
        logger.warning("LeaveRequests worksheet not found")
        return []
    except Exception as e:
        logger.exception(f"Error loading requests: {e}")
        return []


def save_requests_to_gsheet():
    """บันทึกข้อมูลจาก session_state ไปยัง Google Sheet (รวมกับข้อมูลเดิม)"""
    try:
        sh = connect_gsheet()
        if not sh:
            return
        ws = sh.worksheet("LeaveRequests")
        
        headers = ['nurse', 'date', 'month', 'year', 'type', 'priority', 'timestamp']
        
        existing_records = ws.get_all_records()
        existing_records = [r for r in existing_records if r.get('nurse') and str(r.get('nurse')).strip()]
        
        existing_keys = set()
        for r in existing_records:
            key = (str(r.get('nurse', '')), str(r.get('date', '')), str(r.get('month', '')), 
                   str(r.get('year', '')), str(r.get('type', '')))
            existing_keys.add(key)
        
        new_records = []
        for req in st.session_state.requests:
            key = (str(req.get('nurse', '')), str(req.get('date', '')), str(req.get('month', '')), 
                   str(req.get('year', '')), str(req.get('type', '')))
            if key not in existing_keys:
                new_records.append(req)
                existing_keys.add(key)
        
        if new_records:
            all_values = ws.get_all_values()
            next_row = len(all_values) + 1
            
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
            
    except Exception as e:
        logger.exception(f"Error saving requests: {e}")
        st.error(f"Error saving requests: {e}")


# --- External Staff ---
def load_external_staff_from_gsheet():
    """โหลดข้อมูลคนนอกหน่วยงานจาก Google Sheets"""
    try:
        sh = connect_gsheet()
        if not sh:
            return []
        try:
            records = sh.worksheet("ExternalStaff").get_all_records()
        except gspread.exceptions.WorksheetNotFound:
            logger.warning("ExternalStaff worksheet not found")
            return []
        
        sync_time = get_thai_time()
        
        for r in records:
            try:
                r['date'] = int(r.get('date', 0))
                r['month'] = int(r.get('month', 0))
                r['year'] = int(r.get('year', 0))
            except (ValueError, TypeError):
                pass
            if not r.get('timestamp'):
                r['timestamp'] = f"(synced: {sync_time})"
        return records
    except Exception as e:
        logger.exception(f"Error loading external staff: {e}")
        return []


def save_external_staff_to_gsheet():
    """บันทึกข้อมูลคนนอกหน่วยงานไปยัง Google Sheet"""
    try:
        sh = connect_gsheet()
        if not sh:
            return
        try:
            ws = sh.worksheet("ExternalStaff")
        except gspread.exceptions.WorksheetNotFound:
            ws = sh.add_worksheet(title="ExternalStaff", rows=100, cols=10)
            ws.update(values=[['name', 'shift', 'date', 'month', 'year', 'timestamp']], range_name='A1')
        
        existing_records = ws.get_all_records()
        existing_keys = set()
        for r in existing_records:
            key = (str(r.get('name', '')), str(r.get('shift', '')), str(r.get('date', '')),
                   str(r.get('month', '')), str(r.get('year', '')))
            existing_keys.add(key)
        
        new_records = []
        for item in st.session_state.external_staff:
            key = (str(item.get('name', '')), str(item.get('shift', '')), str(item.get('date', '')),
                   str(item.get('month', '')), str(item.get('year', '')))
            if key not in existing_keys:
                new_records.append(item)
                existing_keys.add(key)
        
        if new_records:
            next_row = len(existing_records) + 2
            data = []
            for item in new_records:
                row = [item.get('name', ''), item.get('shift', ''), item.get('date', ''),
                       item.get('month', ''), item.get('year', ''), item.get('timestamp', '')]
                data.append(row)
            ws.update(values=data, range_name=f'A{next_row}')
            st.success(f"✅ เพิ่มข้อมูลคนนอกหน่วยงานใหม่ {len(new_records)} รายการ")
        else:
            st.info("ℹ️ ไม่มีข้อมูลคนนอกใหม่ที่ต้องบันทึก")
    except Exception as e:
        logger.exception(f"Error saving external staff: {e}")
        st.error(f"Error saving external staff: {e}")


# --- Fix Requests ---
def load_fix_requests_from_gsheet():
    """โหลดข้อมูล Fix Requests จาก Google Sheets"""
    try:
        sh = connect_gsheet()
        if not sh:
            return []
        records = sh.worksheet("FixRequests").get_all_records()
        
        sync_time = get_thai_time()
        
        for r in records:
            r['nurse'] = extract_nurse_id(r.get('nurse'))
            if isinstance(r.get('dates'), str) and r['dates']:
                r['dates'] = [int(x) for x in r['dates'].split(',')]
            elif isinstance(r.get('dates'), int):
                r['dates'] = [r['dates']]
            try:
                r['month'] = int(r.get('month', 0))
                r['year'] = int(r.get('year', 0))
            except (ValueError, TypeError):
                pass
            if not r.get('timestamp'):
                r['timestamp'] = f"(synced: {sync_time})"
        return records
    except gspread.exceptions.WorksheetNotFound:
        logger.warning("FixRequests worksheet not found")
        return []
    except Exception as e:
        logger.exception(f"Error loading fix requests: {e}")
        return []


def save_fix_requests_to_gsheet():
    """บันทึก Fix Requests ไปยัง Google Sheet"""
    try:
        sh = connect_gsheet()
        if not sh:
            return
        ws = sh.worksheet("FixRequests")
        
        headers = ['nurse', 'shift', 'dates', 'month', 'year', 'timestamp']
        
        existing_records = ws.get_all_records()
        
        existing_keys = set()
        for r in existing_records:
            key = (str(r.get('nurse', '')), str(r.get('shift', '')), str(r.get('dates', '')), 
                   str(r.get('month', '')), str(r.get('year', '')))
            existing_keys.add(key)
        
        new_records = []
        for item in st.session_state.fix_requests:
            dates_str = ",".join(map(str, item.get('dates', []))) if isinstance(item.get('dates'), list) else str(item.get('dates', ''))
            key = (str(item.get('nurse', '')), str(item.get('shift', '')), dates_str, 
                   str(item.get('month', '')), str(item.get('year', '')))
            if key not in existing_keys:
                new_records.append(item)
                existing_keys.add(key)
        
        if new_records:
            next_row = len(existing_records) + 2
            data = []
            for item in new_records:
                dates_str = ",".join(map(str, item.get('dates', []))) if isinstance(item.get('dates'), list) else str(item.get('dates', ''))
                row = [item.get('nurse', ''), item.get('shift', ''), dates_str, 
                       item.get('month', ''), item.get('year', ''), item.get('timestamp', '')]
                data.append(row)
            ws.update(values=data, range_name=f'A{next_row}')
            st.success(f"✅ เพิ่ม Fix Request ใหม่ {len(new_records)} รายการ")
        else:
            st.info("ℹ️ ไม่มี Fix Request ใหม่ที่ต้องบันทึก")
    except Exception as e:
        logger.exception(f"Error saving fix requests: {e}")
        st.error(f"Error saving fix requests: {e}")


# --- Staffing Overrides ---
def load_staffing_overrides_from_gsheet():
    """โหลด Staffing Overrides จาก Google Sheets"""
    try:
        sh = connect_gsheet()
        if not sh:
            return []
        records = sh.worksheet("StaffingOverrides").get_all_records()
        for r in records:
            try:
                r['start'] = int(r.get('start', 1))
                r['end'] = int(r.get('end', 31))
                r['count'] = int(r.get('count', 1))
                r['month'] = int(r.get('month', 0))
                r['year'] = int(r.get('year', 0))
            except (ValueError, TypeError):
                pass
        return records
    except gspread.exceptions.WorksheetNotFound:
        logger.warning("StaffingOverrides worksheet not found")
        return []
    except Exception as e:
        logger.exception(f"Error loading staffing overrides: {e}")
        return []


def save_staffing_overrides_to_gsheet():
    """บันทึก Staffing Overrides ไปยัง Google Sheet"""
    try:
        sh = connect_gsheet()
        if not sh:
            return
        ws = sh.worksheet("StaffingOverrides")
        
        headers = ['start', 'end', 'shift', 'count', 'month', 'year', 'timestamp']
        
        existing_records = ws.get_all_records()
        
        existing_keys = set()
        for r in existing_records:
            key = (str(r.get('start', '')), str(r.get('end', '')), str(r.get('shift', '')), 
                   str(r.get('month', '')), str(r.get('year', '')))
            existing_keys.add(key)
        
        new_records = []
        for item in st.session_state.staffing_overrides:
            key = (str(item.get('start', '')), str(item.get('end', '')), str(item.get('shift', '')), 
                   str(item.get('month', '')), str(item.get('year', '')))
            if key not in existing_keys:
                new_records.append(item)
                existing_keys.add(key)
        
        if new_records:
            next_row = len(existing_records) + 2
            data = []
            for item in new_records:
                row = [item.get('start', ''), item.get('end', ''), item.get('shift', ''), 
                       item.get('count', ''), item.get('month', ''), item.get('year', ''), 
                       item.get('timestamp', '')]
                data.append(row)
            ws.update(values=data, range_name=f'A{next_row}')
            st.success(f"✅ เพิ่ม Staffing Override ใหม่ {len(new_records)} รายการ")
        else:
            st.info("ℹ️ ไม่มี Staffing Override ใหม่ที่ต้องบันทึก")
    except Exception as e:
        logger.exception(f"Error saving staffing overrides: {e}")
        st.error(f"Error saving staffing overrides: {e}")


# --- Summary Log ---
def ensure_summary_log_sheet():
    """สร้าง Worksheet 'SummaryLog' ถ้ายังไม่มี"""
    try:
        sh = connect_gsheet()
        if not sh:
            return None
        try:
            ws = sh.worksheet("SummaryLog")
        except gspread.exceptions.WorksheetNotFound:
            ws = sh.add_worksheet(title="SummaryLog", rows=100, cols=15)
            headers = ['Timestamp', 'Month', 'Year', 'Nurse', 'WorkDays', 
                       'Shift_M', 'Shift_S', 'Shift_N', 'Shift_NS']
            ws.update(values=[headers], range_name='A1')
        return ws
    except Exception as e:
        logger.exception(f"Error with SummaryLog sheet: {e}")
        st.error(f"❌ Error with SummaryLog sheet: {e}")
        return None


def calculate_nurse_summary(schedule_df, year, month, days_in_month):
    """คำนวณยอดรวมของพยาบาลทุกคนในเดือน"""
    summary_data = []
    timestamp = get_thai_time()
    
    for _, row in schedule_df.iterrows():
        nurse = row.get('Nurse', row.iloc[0])
        
        shifts = []
        for d in range(1, days_in_month + 1):
            col_name = str(d)
            shift_val = ''
            for prefix in ['🟡', '🔵', '']:
                possible_col = f"{prefix}{d}"
                if possible_col in row.index:
                    shift_val = str(row[possible_col])
                    break
                elif col_name in row.index:
                    shift_val = str(row[col_name])
                    break
            shifts.append(shift_val)
        
        c_m = shifts.count('M')
        c_s = shifts.count('S')
        c_n = shifts.count('N')
        c_ns = shifts.count('NS')
        c_lt = sum(1 for s in shifts if 'ลา' in s or 'อบรม' in s)
        
        work_days = c_m + c_s + c_n + c_ns + c_lt
        
        summary_data.append({
            'timestamp': timestamp,
            'month': month,
            'year': year,
            'nurse': nurse,
            'work_days': work_days,
            'shift_m': c_m,
            'shift_s': c_s,
            'shift_n': c_n,
            'shift_ns': c_ns
        })
    
    return summary_data


def save_summary_to_gsheet(summary_data, year, month):
    """บันทึก Summary ลง SummaryLog (ลบข้อมูลเดิมถ้ามี month/year ซ้ำ)"""
    try:
        ws = ensure_summary_log_sheet()
        if not ws:
            return False
        
        all_data = ws.get_all_values()
        if len(all_data) > 1:
            header = all_data[0]
            month_idx = header.index('Month') if 'Month' in header else 1
            year_idx = header.index('Year') if 'Year' in header else 2
            
            rows_to_keep = [all_data[0]]
            deleted_count = 0
            for row in all_data[1:]:
                if len(row) > max(month_idx, year_idx):
                    try:
                        if int(row[month_idx]) == month and int(row[year_idx]) == year:
                            deleted_count += 1
                            continue
                    except (ValueError, IndexError):
                        pass
                rows_to_keep.append(row)
            
            if deleted_count > 0:
                ws.clear()
                if rows_to_keep:
                    ws.update(values=rows_to_keep, range_name='A1')
                st.info(f"🔄 ลบข้อมูลเดิมของเดือน {month}/{year} ออก {deleted_count} แถว แล้วบันทึกใหม่")
        
        next_row = len(ws.get_all_values()) + 1
        data_rows = []
        for s in summary_data:
            data_rows.append([
                s['timestamp'], s['month'], s['year'], s['nurse'],
                s['work_days'], s['shift_m'], s['shift_s'], s['shift_n'], s['shift_ns']
            ])
        
        if data_rows:
            ws.update(values=data_rows, range_name=f'A{next_row}')
        
        return True
    except Exception as e:
        logger.exception(f"Error saving summary: {e}")
        st.error(f"❌ Error saving summary: {e}")
        return False


def load_summary_from_gsheet():
    """โหลดข้อมูล Summary ทั้งหมดจาก SummaryLog"""
    try:
        sh = connect_gsheet()
        if not sh:
            return None
        try:
            ws = sh.worksheet("SummaryLog")
            records = ws.get_all_records()
            
            column_mapping = {
                'shift_m': 'Shift_M', 'shift_M': 'Shift_M',
                'shift_s': 'Shift_S', 'shift_S': 'Shift_S',
                'shift_n': 'Shift_N', 'shift_N': 'Shift_N',
                'shift_ns': 'Shift_NS', 'shift_NS': 'Shift_NS',
                'workdays': 'WorkDays', 'work_days': 'WorkDays',
                'nurse': 'Nurse', 'month': 'Month', 'year': 'Year',
                'timestamp': 'Timestamp', 'month_year': 'Month_Year'
            }
            
            normalized_records = []
            for record in records:
                new_record = {}
                for key, value in record.items():
                    new_key = column_mapping.get(key.lower(), key)
                    new_record[new_key] = value
                normalized_records.append(new_record)
            
            return normalized_records
        except gspread.exceptions.WorksheetNotFound:
            return None
    except Exception as e:
        logger.exception(f"Error loading summary: {e}")
        st.error(f"❌ Error loading summary: {e}")
        return None


# --- Previous Schedule ---
def load_previous_schedule_from_gsheet(nurses):
    """ดึงตารางเวรเดือนก่อนจาก Google Sheets (Sheet: PreviousSchedule)"""
    try:
        sh = connect_gsheet()
        if not sh:
            return None
        
        try:
            ws = sh.worksheet("PreviousSchedule")
        except gspread.exceptions.WorksheetNotFound:
            return None
        
        all_values = ws.get_all_values()
        if len(all_values) < 2:
            return None
        
        header = all_values[0]
        
        date_cols = []
        for i, col in enumerate(header):
            clean_col = ''.join(filter(str.isdigit, str(col)))
            if clean_col.isdigit():
                date_cols.append((i, int(clean_col)))
        
        if not date_cols:
            return None
        
        date_cols_sorted = sorted(date_cols, key=lambda x: x[1])
        last_7_cols = date_cols_sorted[-7:] if len(date_cols_sorted) >= 7 else date_cols_sorted
        
        prev_data = {}
        for row in all_values[1:]:
            if len(row) < 1:
                continue
            
            nurse_cell = str(row[0])
            
            nurse_id = None
            sorted_nurses = sorted(nurses, key=len, reverse=True)
            for n in sorted_nurses:
                if n in nurse_cell:
                    nurse_id = n
                    break
            
            if nurse_id and nurse_id in nurses:
                shifts = []
                for col_idx, day_num in last_7_cols:
                    if col_idx < len(row):
                        shift_val = str(row[col_idx]).strip()
                        
                        if shift_val in ['M', 'เช้า']:
                            shift = 'M'
                        elif shift_val in ['S', 'บ่าย']:
                            shift = 'S'
                        elif shift_val in ['N', 'ดึก']:
                            shift = 'N'
                        elif shift_val in ['NS']:
                            shift = 'NS'
                        elif shift_val in ['NCD']:
                            shift = 'O'
                        elif 'ลา' in shift_val or 'อบรม' in shift_val or 'ประชุม' in shift_val:
                            shift = 'L_T'
                        elif 'OC' in shift_val or '📞' in shift_val:
                            shift = 'OC'
                        elif shift_val in ['', 'O', '-']:
                            shift = 'O'
                        else:
                            shift = 'O'
                        
                        shifts.append(shift)
                    else:
                        shifts.append('O')
                
                prev_data[nurse_id] = shifts
        
        return prev_data if prev_data else None
        
    except Exception as e:
        logger.exception(f"Error loading previous schedule: {e}")
        st.error(f"❌ Error loading previous schedule: {e}")
        return None


def save_schedule_to_gsheet(schedule_df, year, month):
    """บันทึกตารางเวรที่จัดเสร็จลง Google Sheets (Sheet: PreviousSchedule)"""
    try:
        sh = connect_gsheet()
        if not sh:
            return False
        
        try:
            ws = sh.worksheet("PreviousSchedule")
        except gspread.exceptions.WorksheetNotFound:
            ws = sh.add_worksheet(title="PreviousSchedule", rows=20, cols=40)
        
        _, days_in_month = calendar.monthrange(year, month)
        
        header = ['พยาบาล'] + [str(d) for d in range(1, days_in_month + 1)]
        
        data = [header]
        
        for _, row in schedule_df.iterrows():
            nurse_name = row.get('Nurse', row.iloc[0])
            row_data = [nurse_name]
            
            for d in range(1, days_in_month + 1):
                col_name = str(d)
                shift_val = ''
                
                for prefix in ['🟡', '🔵', '']:
                    possible_col = f"{prefix}{d}"
                    if possible_col in row.index:
                        shift_val = str(row[possible_col])
                        break
                    elif col_name in row.index:
                        shift_val = str(row[col_name])
                        break
                
                if shift_val == 'nan' or (isinstance(shift_val, float) and pd.isna(shift_val)):
                    shift_val = ''
                
                row_data.append(shift_val)
            
            data.append(row_data)
        
        metadata_row = [f'Updated: {year}/{month}'] + ['' for _ in range(days_in_month)]
        data.append(metadata_row)
        
        ws.clear()
        ws.update(values=data, range_name='A1')
        
        summary_data = calculate_nurse_summary(schedule_df, year, month, days_in_month)
        if save_summary_to_gsheet(summary_data, year, month):
            st.success("✅ บันทึกสรุปยอดรายเดือนเรียบร้อย!")
        
        return True
        
    except Exception as e:
        logger.exception(f"Error saving schedule to GSheet: {e}")
        st.error(f"❌ Error saving schedule to GSheet: {e}")
        return False

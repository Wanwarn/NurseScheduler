"""
Utility helper functions for NurseApp
"""
import pandas as pd
import re


def extract_nurse_id(nurse_value):
    """แปลง 'ER1 (นูรีซาน)' -> 'ER1' หรือ 'นูรีซาน' -> 'ER1'"""
    from src.config import NURSE_NAMES
    
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


def get_week_occurrence(day):
    """Get which occurrence of the week the day falls in (1-5)"""
    return (day - 1) // 7 + 1


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
            except Exception:
                continue
        
        if df is None:
            return None

        # หา column ที่เป็นตัวเลข (วันที่)
        date_cols = [col for col in df.columns if col.isdigit() or any(c.isdigit() for c in str(col))]
        
        if not date_cols:
            return None
        
        # เรียงลำดับและเอา 7 วันสุดท้าย
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
            sorted_nurses = sorted(nurses, key=len, reverse=True)
            for n in sorted_nurses:
                if n in nurse_col:
                    nurse_id = n
                    break
            
            # รูปแบบ 2: "Nurse 1", "Nurse 2", ... "Nurse 10"
            if nurse_id is None:
                match = re.search(r'Nurse\s*(\d+)', nurse_col)
                if match:
                    num = int(match.group(1))
                    nurse_id = f'ER{num}'
            
            if nurse_id and nurse_id in nurses:
                shifts = []
                for col in last_7_days:
                    shift = str(row[col]) if col in row.index else ''
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
    except Exception:
        return None

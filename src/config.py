"""
Configuration constants and helper functions for NurseApp
"""
import streamlit as st
from datetime import datetime
import pytz
import calendar

# --- App Version ---
APP_VERSION = "2.8.0"  # อัปเดต: 2026-05-18 - Major refactor: ลบ legacy solver, ลบ duplicate code, ใช้ src/ modules

# --- Thai Timezone Helper ---
def get_thai_time():
    """คืนค่าเวลาไทย (Asia/Bangkok) ไม่ว่าจะรันที่ไหนก็ตาม"""
    bangkok_tz = pytz.timezone('Asia/Bangkok')
    return datetime.now(bangkok_tz).strftime("%Y-%m-%d %H:%M:%S")


# --- Thai Public Holidays 2025-2027 ---
THAI_HOLIDAYS = {
    2025: {
        1: [1, 29],       # วันขึ้นปีใหม่ + ตรุษจีน
        2: [12],          # วันมาฆบูชา
        3: [31],          # วันอีดิลฟิตรี
        4: [6, 7, 13, 14, 15, 16],  # วันจักรี + สงกรานต์
        5: [1, 4, 5, 12], # วันแรงงาน + ฉัตรมงคล + วิสาขบูชา
        6: [2, 3, 7],     # วันเฉลิมฯ พระราชินี + อีดิลอัฏฮา
        7: [10, 11, 28],  # วันอาสาฬหบูชา + เข้าพรรษา + เฉลิมฯ ร.10
        8: [11, 12],      # วันแม่แห่งชาติ
        10: [13, 23],     # วันสวรรคต ร.9 + ปิยมหาราช
        12: [5, 10, 31],  # วันพ่อ + รัฐธรรมนูญ + สิ้นปี
    },
    2026: {
        1: [1, 2],        # วันขึ้นปีใหม่
        2: [17],          # ตรุษจีน
        3: [3, 20],       # วันมาฆบูชา + อีดิลฟิตรี
        4: [6, 13, 14, 15],  # วันจักรี + สงกรานต์
        5: [1, 4, 27],    # วันแรงงาน + ฉัตรมงคล + อีดิลอัฏฮา
        6: [1, 3],        # วันวิสาขบูชา (ชดเชย) + เฉลิมฯ พระราชินี
        7: [28, 29, 30],  # เฉลิมฯ ร.10 + อาสาฬหบูชา + เข้าพรรษา
        8: [12],          # วันแม่แห่งชาติ
        10: [13, 23],     # วันสวรรคต ร.9 + ปิยมหาราช
        12: [5, 7, 10, 31],  # วันพ่อ + ชดเชย + รัฐธรรมนูญ + สิ้นปี
    },
    2027: {
        # TODO: อัปเดตจากประกาศวันหยุดราชการอย่างเป็นทางการ
        1: [1],           # วันขึ้นปีใหม่
        4: [6, 13, 14, 15],  # วันจักรี + สงกรานต์
        5: [1, 4],        # วันแรงงาน + ฉัตรมงคล
        6: [3],           # วันเฉลิมฯ พระราชินี
        7: [28],          # วันเฉลิมฯ ร.10
        8: [12],          # วันแม่แห่งชาติ
        10: [13, 23],     # วันสวรรคต ร.9 + ปิยมหาราช
        12: [5, 10, 31],  # วันพ่อ + รัฐธรรมนูญ + สิ้นปี
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

# --- Google Sheets Configuration ---
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
CREDENTIALS_FILE = "service_account.json"

def get_sheet_url():
    """Get Google Sheet URL from secrets or fallback"""
    return st.secrets.get("app", {}).get(
        "sheet_url", 
        "https://docs.google.com/spreadsheets/d/1js5h70Abv1MIKrmZUBe3xypoCE4BXIo6_gEhBuJ5k8k/edit?usp=sharing"
    )

def get_app_password():
    """Get app password from secrets (no fallback for security)"""
    return st.secrets.get("app", {}).get("password", "")

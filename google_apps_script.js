// ===========================================
// Google Apps Script สำหรับ Nurse Scheduler
// ติดตั้งใน Google Sheet: Extensions > Apps Script
// ===========================================

// ฟังก์ชันนี้จะทำงานอัตโนมัติเมื่อมีการแก้ไขข้อมูล
function onEdit(e) {
    var sheet = e.source.getActiveSheet();
    var range = e.range;
    var row = range.getRow();
    var col = range.getColumn();

    // ข้ามถ้าเป็น header row
    if (row === 1) return;

    // กำหนดตำแหน่ง timestamp column สำหรับแต่ละ sheet
    var timestampCol = -1;
    var dataStartCol = 1;
    var dataEndCol = 1;

    if (sheet.getName() === "LeaveRequests") {
        timestampCol = 7; // Column G
        dataEndCol = 6;   // Column F (priority)
    } else if (sheet.getName() === "FixRequests") {
        timestampCol = 6; // Column F
        dataEndCol = 5;   // Column E (year)
    } else if (sheet.getName() === "StaffingOverrides") {
        timestampCol = 7; // Column G
        dataEndCol = 6;   // Column F (year)
    }

    // ถ้าไม่ใช่ sheet ที่ต้องการ ให้ข้าม
    if (timestampCol === -1) return;

    // ถ้าแก้ไขใน column ที่เป็นข้อมูล (ไม่ใช่ timestamp)
    if (col >= dataStartCol && col <= dataEndCol) {
        // ใส่ timestamp อัตโนมัติ
        var timestamp = Utilities.formatDate(new Date(), Session.getScriptTimeZone(), "yyyy-MM-dd HH:mm:ss");
        sheet.getRange(row, timestampCol).setValue(timestamp);
    }
}

// ฟังก์ชันสำหรับ unhide timestamp column (ถ้าต้องการดู)
function showTimestampColumns() {
    var ss = SpreadsheetApp.getActiveSpreadsheet();

    var sheets = ["LeaveRequests", "FixRequests", "StaffingOverrides"];
    var cols = [7, 6, 7]; // G, F, G

    for (var i = 0; i < sheets.length; i++) {
        try {
            var sheet = ss.getSheetByName(sheets[i]);
            if (sheet) {
                sheet.showColumns(cols[i]);
            }
        } catch (e) {
            Logger.log("Error showing column in " + sheets[i] + ": " + e);
        }
    }
}

// ฟังก์ชันสำหรับ hide timestamp column (ซ่อนจาก user)
function hideTimestampColumns() {
    var ss = SpreadsheetApp.getActiveSpreadsheet();

    var sheets = ["LeaveRequests", "FixRequests", "StaffingOverrides"];
    var cols = [7, 6, 7]; // G, F, G

    for (var i = 0; i < sheets.length; i++) {
        try {
            var sheet = ss.getSheetByName(sheets[i]);
            if (sheet) {
                sheet.hideColumns(cols[i]);
            }
        } catch (e) {
            Logger.log("Error hiding column in " + sheets[i] + ": " + e);
        }
    }
}

@echo off
title Nurse Scheduler App
echo ========================================
echo   Starting Nurse Scheduler App...
echo ========================================
echo.

cd /d "%~dp0"

echo Activating virtual environment...
call .venv\Scripts\activate.bat

echo.
echo Starting Streamlit server...
echo App will open at: http://localhost:8501
echo.
echo Press Ctrl+C to stop the server
echo ========================================
echo.

streamlit run app.py

pause

@echo off
echo =========================================================================
echo Starting ZYROO AI Document Intelligence Studio (Streamlit Web UI)
echo =========================================================================
cd /d "%~dp0\.."
..\.venv\Scripts\python.exe -m streamlit run app.py
pause

@echo off
echo =========================================================================
echo Running ZYROO Week 6 Automated Verification & Quality Gate Suite
echo =========================================================================
cd /d "%~dp0\.."
..\.venv\Scripts\python.exe test_week6.py
pause

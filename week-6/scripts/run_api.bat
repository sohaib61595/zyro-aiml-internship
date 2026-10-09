@echo off
echo =========================================================================
echo Starting ZYROO AI Document Platform REST API (FastAPI + Swagger Docs)
echo Interactive OpenAPI Docs: http://127.0.0.1:8000/docs
echo =========================================================================
cd /d "%~dp0\.."
..\.venv\Scripts\python.exe -m uvicorn api:app --reload --port 8000
pause

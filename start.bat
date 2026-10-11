@echo off
title AI Government Research Agent
echo ===================================================
echo Starting AI Government Research Agent...
echo Frontend and Backend unified on: http://localhost:8000
echo ===================================================
cd /d "%~dp0"
start "" http://localhost:8000
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause

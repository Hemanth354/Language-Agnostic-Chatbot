@echo off
title Language Agnostic Campus Chatbot (SIH 2025)
cd /d "%~dp0"

echo =================================================================
echo   Language Agnostic Chatbot - Smart India Hackathon 2025
echo   Theme: Smart Education | Team TechTitans RGUKTN
echo =================================================================
echo.

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not found in PATH.
    echo Please install Python 3.10+ from python.org
    pause
    exit /b 1
)

echo Starting Campus Bot (Frontend + Backend on FastAPI)...
python run.py

pause


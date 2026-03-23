@echo off
title Skydash.NET Web UI
color 0B

echo ===================================================
echo   Starting Skydash.NET Dashboard...
echo ===================================================

if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment 'venv' not found.
    echo Please run 'install.bat' first to set up the project.
    pause
    exit /b
)

call venv\Scripts\activate.bat
python app.py
pause

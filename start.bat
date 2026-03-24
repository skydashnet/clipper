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

:: Ensure waitress is installed for stable server
pip install waitress -q 2>nul

echo.
echo [*] Launching browser in 2 seconds...
start "" "http://localhost:5000"

python app.py
pause

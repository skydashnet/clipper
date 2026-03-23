@echo off
title Skydash.NET Clipper - Setup & Installation
color 0A

echo ===================================================
echo   Skydash.NET - Heatmap Clip Extractor Setup
echo ===================================================
echo.

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.10+ and try again.
    pause
    exit /b
)

:: Create Virtual Environment
echo [*] Creating Python Virtual Environment (venv)...
if not exist "venv\" (
    python -m venv venv
)
echo [*] Activating venv...
call venv\Scripts\activate.bat

:: Install Packages
echo [*] Installing required Python packages...
pip install --upgrade pip
pip install flask yt-dlp faster-whisper requests

echo.
echo ===================================================
echo   System Dependency Validation
echo ===================================================

:: Check FFmpeg
ffmpeg -version >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] FFmpeg is missing! The tool will NOT work without it.
    echo Please install FFmpeg (e.g. via 'winget install ffmpeg')
) else (
    echo [OK] FFmpeg found.
)

:: Check aria2c
aria2c --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] aria2 is missing! Downloads will be extremely slow.
    echo Please install aria2 (e.g. via 'winget install aria2')
) else (
    echo [OK] aria2c found.
)

:: Check Node.js
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] Node.js is missing! Some videos might fail to download.
    echo Please install Node.js (e.g. via 'winget install OpenJS.NodeJS')
) else (
    echo [OK] Node.js found.
)

echo.
echo ===================================================
echo   Installation Complete!
echo ===================================================
echo To start the Web UI, double-click 'start.bat' or run:
echo   venv\Scripts\activate
echo   python app.py
echo.
pause

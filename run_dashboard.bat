@echo off
title ASX Critical Minerals Dashboard
echo ===================================================
echo Starting ASX Critical Minerals Local Web Server...
echo Keep this window open while using the dashboard.
echo ===================================================
echo.
python server.py
if %ERRORLEVEL% neq 0 (
    echo.
    echo ---------------------------------------------------
    echo ERROR: Python failed to start server.py.
    echo Please ensure Python is installed and added to PATH.
    echo ---------------------------------------------------
    pause
)

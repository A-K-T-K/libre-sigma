@echo off
title LibRE Sigma Launcher
cd /d "%~dp0"

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [LibRE Sigma Error] Python was not found in PATH.
    echo Please install Python 3.10+ from https://www.python.org and check "Add Python to PATH".
    pause
    exit /b 1
)

python start.py %*
if %errorlevel% neq 0 (
    pause
)

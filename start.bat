@echo off
REM start.bat - Launch the OTS Federation Setup Helper (Terminal / CLI)
REM
REM This script runs the pure terminal interface that works in any
REM Windows console environment (cmd.exe, PowerShell, Windows Terminal).
REM
REM Usage:
REM     start.bat
REM     .\start.bat

REM Enable UTF-8 output so Unicode characters display correctly.
chcp 65001 >nul 2>&1
set PYTHONIOENCODING=utf-8

REM Try the most common Python 3 command names.
where python3 >nul 2>&1 && (
    python3 "%~dp0src\OTS_Federation_CLI.py" %*
    goto :EOF
)

where python >nul 2>&1 && (
    python "%~dp0src\OTS_Federation_CLI.py" %*
    goto :EOF
)

where py >nul 2>&1 && (
    py -3 "%~dp0src\OTS_Federation_CLI.py" %*
    goto :EOF
)

echo ERROR: Python 3 is not installed or not found on PATH.
echo Please install Python 3 from https://www.python.org/downloads/
pause

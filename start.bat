@echo off
REM start.bat - Launch the OTS Federation Setup Helper (Terminal / CLI)
REM
REM This script runs the pure terminal interface that works in any
REM Windows console environment (cmd.exe, PowerShell, Windows Terminal).
REM
REM Usage:
REM     start.bat
REM     .\start.bat

python "%~dp0src\OTS_Federation_CLI.py" %*

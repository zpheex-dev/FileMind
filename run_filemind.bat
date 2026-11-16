@echo off
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%~dp0src;%PYTHONPATH%"

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m filemind.gui.app
    exit /b %errorlevel%
)

where py >nul 2>nul
if not errorlevel 1 (
    py -3 -m filemind.gui.app
) else (
    python -m filemind.gui.app
)

if errorlevel 1 (
    echo FileMind could not start. Check that Python and the project dependencies are installed.
    pause
    exit /b 1
)

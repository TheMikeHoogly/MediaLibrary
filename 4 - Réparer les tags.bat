@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo IMPORTANT : arrete le serveur (Ctrl+C) avant.
echo.
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" repair_tags.py
) else (
    python repair_tags.py
)
pause

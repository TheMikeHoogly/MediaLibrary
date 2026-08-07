@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo IMPORTANT : arrete le serveur (Ctrl+C) avant ce test.
echo.
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m pip install --quiet --disable-pip-version-check pillow pillow-heif piexif
    ".venv\Scripts\python.exe" test_tagging.py 5
) else (
    pip install --quiet --disable-pip-version-check pillow pillow-heif piexif
    python test_tagging.py 5
)
pause

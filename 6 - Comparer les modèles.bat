@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo IMPORTANT : arrete le serveur (Ctrl+C) avant la comparaison.
echo (Le premier appel de chaque modele inclut son chargement : plus lent.)
echo.
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" compare_models.py 5
) else (
    python compare_models.py 5
)
pause

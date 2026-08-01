@echo off
chcp 65001 >nul
cd /d "%~dp0"
REM Contenu en ASCII pur : cmd.exe relit le fichier par decalage d'octets.
echo ==============================================================
echo   MAINTENANCE DES MEDIAS - une passe a la demande
echo ==============================================================
echo.
echo   Le serveur lance DEJA cette maintenance tout seul en fond
echo   (thread d'arriere-plan). Ce lanceur ne sert qu'a FORCER une
echo   passe maintenant, par exemple juste apres un recensement.
echo.
echo   IMPORTANT : arrete le serveur avant, car cette passe peut
echo   MODIFIER l'index (dedoublonnage), et l'index a un seul
echo   ecrivain. Les etapes reglees sur "propose" (rangement par
echo   annee, renommage) ne s'appliquent pas ici.
echo.
echo   Ce qui se fait, si c'est du :
echo     - dedoublonnage : applique les quarantaines encore en
echo       attente du plan (reversible, journal undo)
echo     - purge : efface la corbeille de plus de 30 jours
echo       (seulement si la canonique existe encore)
echo.
pause

set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

echo.
echo   Passe de maintenance en cours...
echo --------------------------------------------------------------
"%PY%" maintenance.py
if errorlevel 1 (
    echo.
    echo   La passe a signale une erreur. Rien d'irreversible :
    echo   dedoublonnage en quarantaine, purge avec filet.
    pause
    exit /b 1
)

echo.
echo   Termine. Detail dans docs\maintenance_report.json et
echo   docs\maintenance.log. Tu peux relancer le serveur.
echo.
pause

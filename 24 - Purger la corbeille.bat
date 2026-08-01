@echo off
chcp 65001 >nul
cd /d "%~dp0"
REM Contenu en ASCII pur : cmd.exe relit le fichier par decalage d'octets.
echo ==============================================================
echo   PURGE DE LA CORBEILLE DE RANGEMENT - Phase 3b
echo ==============================================================
echo.
echo   Supprime DEFINITIVEMENT les doublons mis en quarantaine il y
echo   a plus de 30 jours. C'est le SEUL geste destructif du chantier.
echo.
echo   Garde-fous : un groupe n'est purge que si sa copie CANONIQUE
echo   (celle qu'on garde) existe toujours ; sinon il est conserve.
echo   Rien de recent (moins de 30 jours) n'est touche.
echo.
echo   Etape 1 : APERCU (dry-run), rien n'est supprime.
echo --------------------------------------------------------------

set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

"%PY%" purger_corbeille.py --jours 30
if errorlevel 1 (
    echo.
    echo   Echec de l'apercu. Rien n'a ete supprime.
    pause
    exit /b 1
)

echo.
echo   Etape 2 : pour SUPPRIMER reellement ce qui est liste ci-dessus,
echo   reponds O. Sinon reponds N (rien ne sera supprime).
echo.
choice /c ON /n /m "Purger maintenant ? [O]ui / [N]on : "
if errorlevel 2 (
    echo   Annule. Rien n'a ete supprime.
    pause
    exit /b 0
)

"%PY%" purger_corbeille.py --jours 30 --appliquer
echo.
echo   Termine.
pause

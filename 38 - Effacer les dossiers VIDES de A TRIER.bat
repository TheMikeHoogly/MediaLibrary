@echo off
chcp 65001 >nul
cd /d "%~dp0"
REM Contenu en ASCII pur : cmd.exe relit le fichier par decalage d'octets.
echo ==============================================================
echo   EFFACER LES DOSSIERS VIDES de "_A TRIER"
echo ==============================================================
echo.
echo   Etape 1 : recensement (lecture seule, quelques minutes sur le
echo   NAS). Un dossier est VIDE s'il ne contient aucun fichier a
echo   aucune profondeur. Ceux qui ne portent que des scories
echo   (Thumbs.db, desktop.ini) sont comptes a part et GARDES.
echo.
echo   Serveur allume ou non : indifferent (aucun fichier touche).
echo --------------------------------------------------------------

set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

"%PY%" inventaire_dossiers_vides.py
if errorlevel 1 goto ECHEC

echo.
echo   Etape 2 : apercu de l'effacement (rien n'est efface).
"%PY%" effacer_dossiers_vides.py
echo.
choice /c ON /n /m "Effacer ces dossiers vides maintenant ? [O]ui / [N]on : "
if errorlevel 2 goto FIN

"%PY%" effacer_dossiers_vides.py --appliquer
echo.
echo   Termine. Journal : _journal_dossiers_vides.jsonl
goto FIN

:ECHEC
echo.
echo   Echec du recensement. Rien n'a ete efface.

:FIN
pause

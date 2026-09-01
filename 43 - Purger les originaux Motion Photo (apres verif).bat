@echo off
chcp 65001 >nul
cd /d "%~dp0"
REM Contenu en ASCII pur : cmd.exe relit le fichier par decalage d'octets.
REM Pas de bloc entre parentheses : des goto.
echo ==============================================================
echo   PURGER LES ORIGINAUX MOTION PHOTO - l'etape 2 du strip
echo ==============================================================
echo.
echo   A lancer APRES le bat 42 et APRES avoir verifie des stills.
echo   Les photo.jpg_original, versions completes avec video, sont
echo   DEPLACES en quarantaine .corbeille-rangement, avec manifeste.
echo   Rien n'est supprime ici - le bat 24 purgera la corbeille.
echo.
echo   Etape 1 : APERCU, rien n'est deplace.
echo --------------------------------------------------------------

set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

"%PY%" appliquer_purge_motionphoto.py
if errorlevel 1 goto ECHEC

echo.
choice /c ON /n /m "Mettre ces originaux en quarantaine ? [O]ui / [N]on : "
if errorlevel 2 goto ATRIER
"%PY%" appliquer_purge_motionphoto.py --appliquer
if errorlevel 1 goto ECHEC

:ATRIER
echo.
echo   Les 125 jpg_original de _A TRIER, laisses par l'ancien
echo   repair_file, sont l'etat 1 du strip - decision du 29/08 :
echo   leur purge est cette etape 2.
choice /c ON /n /m "Les mettre en quarantaine aussi ? [O]ui / [N]on : "
if errorlevel 2 goto FIN
"%PY%" appliquer_purge_motionphoto.py --appliquer --aussi-racine b64:TjpcUGhvdG9zXF9BIFRSSUVS
if errorlevel 1 goto ECHEC
goto FIN

:ECHEC
echo.
echo   ECHEC - lire les messages ci-dessus. Rien d'autre n'a ete tente.

:FIN
pause

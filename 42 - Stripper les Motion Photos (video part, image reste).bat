@echo off
chcp 65001 >nul
cd /d "%~dp0"
REM Contenu en ASCII pur : cmd.exe relit le fichier par decalage d'octets.
REM Pas de bloc entre parentheses : des goto.
echo ==============================================================
echo   STRIP MOTION PHOTO - la video embarquee part, l'image reste
echo ==============================================================
echo.
echo   Regle du 29/08 : une Motion Photo ne garde que son image.
echo   Compte du 01/09, mesure_motion_photos : 2441 Motion Photos,
echo   8,64 Go de video, toutes chez Mike, 2021-2026.
echo.
echo   Methode prouvee par banc, verifier_strip_motionphoto :
echo   exiftool -trailer:all= , image identique au pixel. Chaque
echo   fichier modifie laisse photo.jpg_original - la version
echo   complete, c'est l'UNDO. La purge de ces originaux est le
echo   bat 43, APRES verification des stills.
echo.
echo   SERVEUR ARRETE exige - le script le verifie. Fenetre
echo   "MediaLibrary - Serveur", ou "arret" dans _commande_serveur.txt.
echo.
echo   Etape 1 : APERCU, rien n'est ecrit.
echo --------------------------------------------------------------

set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

"%PY%" appliquer_strip_motionphoto.py
if errorlevel 1 goto ECHEC

echo.
choice /c ON /n /m "Essai sur 20 fichiers d'abord, serveur ARRETE ? [O]ui / [N]on : "
if errorlevel 2 goto TOUT
"%PY%" appliquer_strip_motionphoto.py --appliquer --limite 20
if errorlevel 1 goto ECHEC
echo.
echo   Regarde quelques stills strippes avant de continuer.
echo.

:TOUT
choice /c ON /n /m "Stripper TOUT le reste maintenant ? [O]ui / [N]on : "
if errorlevel 2 goto FIN
"%PY%" appliquer_strip_motionphoto.py --appliquer
if errorlevel 1 goto ECHEC
echo.
echo   Termine. Manifeste : docs\strip_motionphoto_manifeste.json
goto FIN

:ECHEC
echo.
echo   ECHEC - lire les messages ci-dessus. Rien d'autre n'a ete tente.

:FIN
pause

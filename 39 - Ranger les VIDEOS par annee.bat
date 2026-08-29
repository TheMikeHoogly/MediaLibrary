@echo off
chcp 65001 >nul
cd /d "%~dp0"
REM Contenu en ASCII pur : cmd.exe relit le fichier par decalage d'octets.
echo ==============================================================
echo   RANGEMENT DES VIDEOS PAR ANNEE - "_A TRIER" vers Photos Mike\AAAA
echo ==============================================================
echo.
echo   Les videos (.mp4...) ne sont pas dans l'index : elles se datent
echo   par leur NOM (AAAAMMJJ_HHMMSS), sinon par ExifTool, sinon par
echo   le dossier annee du Takeout - jamais par la date de fichier.
echo   Meme cible que les photos (Photos Mike\AAAA), meme journal undo,
echo   aucun ecrasement (collision = sautee).
echo.
echo   IMPORTANT : ARRETE LE SERVEUR d'abord (meme regle que le bat 26 ;
echo   le rangeur le PROUVE et refuse sinon).
echo.
echo   Etape 1 : le plan (lecture seule, ~20 s sur le NAS).
echo --------------------------------------------------------------

set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

"%PY%" inventaire_videos.py
if errorlevel 1 goto ECHEC

echo.
echo   Etape 2 : APERCU (dry-run), rien n'est deplace.
"%PY%" appliquer_plan_annee.py --plan docs\plan_rangement_videos.json
if errorlevel 1 goto ECHEC

echo.
choice /c ON /n /m "Deplacer un lot de 20 videos maintenant ? [O]ui / [N]on : "
if errorlevel 2 goto FIN

"%PY%" appliquer_plan_annee.py --plan docs\plan_rangement_videos.json --appliquer --limite 20
echo.
echo   Lot applique. Verifie le resultat sur le NAS, puis le RESTE
echo   (73 Go : plusieurs minutes, c'est un deplacement sur le meme volume).
echo.
choice /c ON /n /m "Deplacer TOUT le reste maintenant ? [O]ui / [N]on : "
if errorlevel 2 goto FIN

"%PY%" appliquer_plan_annee.py --plan docs\plan_rangement_videos.json --appliquer
echo.
echo   Termine.
goto FIN

:ECHEC
echo.
echo   Echec. Rien n'a ete deplace.

:FIN
echo   Pour annuler : appliquer_plan_annee.py --undo docs\undo_annee_XXXX.json --appliquer
pause

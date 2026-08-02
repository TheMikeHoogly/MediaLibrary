@echo off
chcp 65001 >nul
cd /d "%~dp0"
REM Contenu en ASCII pur : cmd.exe relit le fichier par decalage d'octets.
echo ==============================================================
echo   RANGEMENT PAR ANNEE - "_A TRIER" vers AAAA
echo ==============================================================
echo.
echo   Deplace les fichiers de "_A TRIER" vers un dossier par annee
echo   (base sur la date de prise de vue). Sans date fiable, un fichier
echo   va dans "_SANS_DATE" - on ne devine jamais l'annee.
echo.
echo   Le plan doit avoir ete genere avant (page Reglages, bouton
echo   "Plan de rangement par annee", ou au demarrage du serveur) :
echo   il lit docs\plan_rangement_annee.json.
echo.
echo   IMPORTANT : ARRETE LE SERVEUR d'abord (ecrivain unique de la
echo   base). Aucun ecrasement : une collision au dossier annee est
echo   sautee. Reversible via le journal undo ecrit dans docs\.
echo.
echo   Etape 1 : APERCU (dry-run), rien n'est deplace.
echo --------------------------------------------------------------

set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

"%PY%" appliquer_plan_annee.py
if errorlevel 1 (
    echo.
    echo   Echec de l'apercu. Rien n'a ete deplace.
    pause
    exit /b 1
)

echo.
echo   Etape 2 : pour DEPLACER reellement, commence par un PETIT LOT
echo   (20 fichiers) afin de verifier le resultat sur le NAS.
echo.
choice /c ON /n /m "Deplacer un lot de 20 maintenant ? [O]ui / [N]on : "
if errorlevel 2 goto FIN

"%PY%" appliquer_plan_annee.py --appliquer --limite 20
echo.
echo   Lot applique. Verifie le resultat, puis relance pour le RESTE.
echo.
choice /c ON /n /m "Deplacer TOUT le reste maintenant ? [O]ui / [N]on : "
if errorlevel 2 goto FIN

"%PY%" appliquer_plan_annee.py --appliquer
echo.
echo   Termine.

:FIN
echo   Fin. Pour annuler : appliquer_plan_annee.py --undo docs\undo_annee_XXXX.json --appliquer
pause

@echo off
chcp 65001 >nul
cd /d "%~dp0"
REM Contenu en ASCII pur : cmd.exe relit le fichier par decalage d'octets.
echo ==============================================================
echo   DEDOUBLONNER "_A TRIER" - retirer ce qui est DEJA range
echo ==============================================================
echo.
echo   Compare chaque fichier de "_A TRIER" a son homonyme du fonds
echo   par l'IMAGE (pixels, pas l'octet : deux copies de la meme
echo   photo different de quelques octets de tags). Ce qui est un
echo   vrai doublon part en ".corbeille-rangement" (reversible ;
echo   le bat 24 la vide apres 30 jours). Un fichier qui porte un
echo   nom absent de la copie gardee est mis de cote (revue), pas
echo   retire.
echo.
echo   IMPORTANT : le SERVEUR doit etre ALLUME (contrairement au
echo   bat 26). L'outil ne touche pas la base ; le serveur purge
echo   l'index des fichiers disparus a son prochain scan.
echo.
echo   Etape 1 : DETECTION (lecture seule ; peut prendre du temps -
echo   il lit l'image de chaque collision sur le NAS).
echo --------------------------------------------------------------

set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

"%PY%" verifier_doublons_atrier.py
if errorlevel 1 (
    echo.
    echo   Echec de la detection. Rien n'a ete deplace.
    pause
    exit /b 1
)

echo.
echo   Etape 2 : APERCU de ce qui serait retire (dry-run).
echo --------------------------------------------------------------
"%PY%" deplacer_doublons_atrier.py

echo.
choice /c ON /n /m "Retirer les doublons confirmes vers la corbeille ? [O]ui / [N]on : "
if errorlevel 2 goto FIN

"%PY%" deplacer_doublons_atrier.py --appliquer

echo.
echo   Termine. Pour annuler : "%PY%" deplacer_doublons_atrier.py --undo
echo   La corbeille se videra d'elle-meme au bat 24 (apres 30 jours).

:FIN
pause

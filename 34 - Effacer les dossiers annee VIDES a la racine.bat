@echo off
chcp 65001 >nul
cd /d "%~dp0"
REM Contenu en ASCII pur : cmd.exe relit le fichier par decalage d'octets.
echo ==============================================================
echo   EFFACER LES DOSSIERS ANNEE VIDES A LA RACINE DE "Photos"
echo ==============================================================
echo.
echo   Depuis le 26/08 le fonds vit sous "Photos Mike". Les dossiers
echo   "Photos\2005" ... "Photos\2026" a la racine n'ont plus de raison
echo   d'exister - UNE FOIS VIDES.
echo.
echo   Ce script n'efface QUE des dossiers vides : il utilise "rd" sans
echo   /s, qui REFUSE un dossier contenant encore quoi que ce soit.
echo   Le 29/08 ils portaient 1 217 photos (3,7 Go) rangees la par
echo   erreur : les effacer aurait ete une perte. D'abord :
echo     1. inventaire_racine_photos.py -^> "dossiers VIDES : 17"
echo     2. puis ce script.
echo.
echo   Etape 1 : inventaire (lecture seule, ~10 s).
echo --------------------------------------------------------------

set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

"%PY%" inventaire_racine_photos.py --exemples=1
if errorlevel 1 (
    echo.
    echo   Inventaire impossible. Rien n'a ete efface.
    pause
    exit /b 1
)

echo.
echo   Si un dossier annee porte encore des fichiers ci-dessus, reponds
echo   NON : "rd" le refusera de toute facon, mais autant le savoir.
echo.
choice /c ON /n /m "Effacer les dossiers annee VIDES de la racine ? [O]ui / [N]on : "
if errorlevel 2 goto FIN

set "RACINE=\\NAS-Bremblens\home\Photos"
set /a EFFACES=0
set /a REFUSES=0
for /l %%A in (2000,1,2030) do (
    if exist "%RACINE%\%%A\" (
        rd "%RACINE%\%%A" 2>nul && (
            echo   + efface : %%A
            set /a EFFACES+=1
        ) || (
            echo   ! refuse ^(pas vide^) : %%A
            set /a REFUSES+=1
        )
    )
)
echo.
echo   Effaces : %EFFACES%   Refuses ^(non vides^) : %REFUSES%
if not "%REFUSES%"=="0" (
    echo   Un dossier refuse contient encore des fichiers : rien n'y a
    echo   ete touche. Range-les d'abord ^(26 - Ranger par annee.bat^).
)

:FIN
pause

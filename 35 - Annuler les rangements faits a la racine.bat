@echo off
chcp 65001 >nul
cd /d "%~dp0"
REM Contenu en ASCII pur : cmd.exe relit le fichier par decalage d'octets.
echo ==============================================================
echo   ANNULER LES QUATRE RANGEMENTS FAITS A LA RACINE (27 et 28/08)
echo ==============================================================
echo.
echo   Le plan par annee visait "Photos\AAAA" au lieu de
echo   "Photos\Photos Mike\AAAA" : 1 217 photos du Takeout ont ete
echo   rangees a la racine. Ce script REJOUE A L'ENVERS les quatre
echo   journaux d'annulation (du plus recent au plus ancien) : les
echo   fichiers reviennent sous "_A TRIER\Takeout Google\AAAA" et
echo   l'index est re-cle (sept magasins). Ensuite, serveur redemarre,
echo   le plan se regenere vers "Photos Mike", et "26 - Ranger par
echo   annee.bat" les range au bon endroit.
echo.
echo   IMPORTANT : le SERVEUR doit etre ARRETE (ecrivain unique de la
echo   base) - le script le PROUVE avant de toucher a quoi que ce soit.
echo.
echo   Etape 1 : APERCU (dry-run) des quatre journaux, rien n'est deplace.
echo --------------------------------------------------------------

set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

set "J1=docs\undo_annee_20260828_212019.json"
set "J2=docs\undo_annee_20260828_210546.json"
set "J3=docs\undo_annee_20260827_215102.json"
set "J4=docs\undo_annee_20260827_213627.json"

for %%J in ("%J1%" "%J2%" "%J3%" "%J4%") do (
    if not exist "%%~J" (
        echo   ABSENT : %%~J  -  rien ne sera fait.
        pause
        exit /b 1
    )
)

for %%J in ("%J1%" "%J2%" "%J3%" "%J4%") do (
    echo.
    echo   --- apercu : %%~J
    "%PY%" appliquer_plan_annee.py --undo "%%~J"
    if errorlevel 1 (
        echo.
        echo   Echec de l'apercu. Rien n'a ete deplace.
        pause
        exit /b 1
    )
)

echo.
echo   Etape 2 : ANNULER pour de vrai, journal par journal, du plus
echo   recent au plus ancien. Un dossier annee de la racine devenu
echo   vide est retire au passage ; le journal reste dans docs\.
echo.
choice /c ON /n /m "Annuler les quatre rangements maintenant ? [O]ui / [N]on : "
if errorlevel 2 goto FIN

for %%J in ("%J1%" "%J2%" "%J3%" "%J4%") do (
    echo.
    echo   --- annulation : %%~J
    "%PY%" appliquer_plan_annee.py --undo "%%~J" --appliquer
    if errorlevel 1 (
        echo.
        echo   ARRET sur ce journal : les suivants ne sont PAS rejoues.
        echo   Regarde le message ci-dessus avant de relancer.
        pause
        exit /b 1
    )
)

echo.
echo   Termine. Suite : "0 - Demarrer le serveur.bat" (le plan se
echo   regenere vers "Photos Mike"), puis l'arreter et lancer
echo   "26 - Ranger par annee.bat", puis "34 - Effacer les dossiers
echo   annee VIDES a la racine.bat".

:FIN
pause

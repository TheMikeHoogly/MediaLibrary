@echo off
chcp 65001 >nul
cd /d "%~dp0"
REM Contenu en ASCII pur : cmd.exe relit le fichier par decalage d'octets.
setlocal EnableDelayedExpansion

set "CIBLE=D:\essai-restauration"
set "NAS=\\nas-bremblens\home\Uploads"
set "DEPOT=https://github.com/TheMikeHoogly/MediaLibrary.git"

set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

echo ==============================================================
echo   REPETITION DE RESTAURATION - chantier 12
echo ==============================================================
echo.
echo   "PC mort lundi, tout revit vendredi." Tant qu'une restauration
echo   n'a pas eu lieu, "on a une sauvegarde" est une promesse, pas
echo   un fait.
echo.
echo   Ce lanceur remonte un PC NEUF a cote, dans un dossier d'essai,
echo   et chronometre. Il ne touche NI a la base vivante, NI au NAS,
echo   NI a ce dossier de projet : il ne fait que LIRE le NAS et
echo   ECRIRE dans le dossier d'essai.
echo.
echo     Dossier d'essai : %CIBLE%
echo     Sauvegarde lue  : %NAS%
echo.
echo   Prevois environ 300 Mo et quelques minutes de copie reseau.
echo.

if /i "%CIBLE%"=="%CD%" (
    echo   REFUS : le dossier d'essai est le dossier du projet.
    echo   Change CIBLE en tete de ce fichier.
    pause
    exit /b 1
)

if not exist "%NAS%\photos.db.bak" (
    echo   La sauvegarde est introuvable : %NAS%\photos.db.bak
    echo   Le NAS est-il monte ? Le serveur a-t-il deja sauvegarde ?
    pause
    exit /b 1
)

if exist "%CIBLE%\*" (
    echo   ATTENTION : %CIBLE% n'est pas vide.
    echo   La repetition doit partir d'un dossier NEUF, sinon elle
    echo   mesure un melange d'ancien et de restaure.
    echo.
    choice /c ON /n /m "   Continuer quand meme ? [O]ui / [N]on : "
    if errorlevel 2 (
        echo   Annule. Rien n'a ete ecrit.
        pause
        exit /b 0
    )
)

echo.
choice /c ON /n /m "   Lancer la repetition maintenant ? [O]ui / [N]on : "
if errorlevel 2 (
    echo   Annule. Rien n'a ete ecrit.
    pause
    exit /b 0
)

for /f "delims=" %%t in ('"%PY%" -c "import time;print(int(time.time()))"') do set "T0=%%t"

echo.
echo --------------------------------------------------------------
echo   Etape 1/4 : ce que GIT rend (le code)
echo --------------------------------------------------------------
if not exist "%CIBLE%" mkdir "%CIBLE%"
if exist "%CIBLE%\.git" (
    echo   Depot deja present, clone saute.
) else (
    git clone "%DEPOT%" "%CIBLE%"
    if errorlevel 1 (
        echo.
        echo   Le clone a echoue. La cause la plus frequente : le
        echo   dossier n'etait pas vide - git refuse de cloner dedans.
        echo   Vide %CIBLE% ou change CIBLE, puis relance.
        pause
        exit /b 1
    )
)

echo.
echo --------------------------------------------------------------
echo   Etape 2/4 : la BASE et le journal des jugements
echo --------------------------------------------------------------
robocopy "%NAS%" "%CIBLE%" photos.db.bak journal_jugements.jsonl /NJH /NJS /NP /R:2 /W:5
if %ERRORLEVEL% GEQ 8 (
    echo.
    echo   La copie depuis le NAS a echoue.
    pause
    exit /b 1
)
REM Relance du lanceur : la base d'un essai PRECEDENT gene le renommage.
REM Seul fichier que ce script efface, et il vit dans le dossier d'essai.
if exist "%CIBLE%\photos.db" del /q "%CIBLE%\photos.db"
ren "%CIBLE%\photos.db.bak" "photos.db"
if errorlevel 1 (
    echo.
    echo   Impossible de renommer photos.db.bak en photos.db.
    pause
    exit /b 1
)

echo.
echo --------------------------------------------------------------
echo   Etape 3/4 : les ARTEFACTS que la base ne porte pas
echo --------------------------------------------------------------
echo   Reglages saisis a la main, journaux de deplacement, et les
echo   quarantaines : sans eux un PC neuf ne voit plus aucune photo,
echo   et plus aucun geste n'est annulable.
echo.
robocopy "%NAS%\artefacts" "%CIBLE%" /E /NJH /NJS /NP /R:2 /W:5
if %ERRORLEVEL% GEQ 8 (
    echo.
    echo   La copie des artefacts a echoue.
    pause
    exit /b 1
)

for /f "delims=" %%t in ('"%PY%" -c "import time;print(int(time.time()))"') do set "T1=%%t"
set /a SECONDES=%T1%-%T0%
set /a MINUTES=SECONDES/60
set /a RESTE=SECONDES%%60

echo.
echo ==============================================================
echo   RESTAURATION TERMINEE en %MINUTES% min %RESTE% s
echo ==============================================================
echo.
echo   Ce qui n'est PAS compte dedans, et c'est voulu : yolo11s.pt,
echo   yolo11n.pt (ultralytics) et cities1000.txt (bat 18) se
echo   re-telechargent, et ne mettent aucune decision humaine en jeu.
echo.

echo --------------------------------------------------------------
echo   Etape 4/4 : le seul juge - les decisions humaines, nom par nom
echo --------------------------------------------------------------
echo   Un total identique ne prouve rien : deux erreurs qui se
echo   compensent donnent le meme total. On ventile par NOM.
echo.
"%PY%" mesure_copie_base.py
if errorlevel 1 (
    echo.
    echo   La copie de la base vivante a echoue : sans elle, pas de
    echo   comparaison. La restauration, elle, est faite.
    pause
    exit /b 1
)

"%PY%" verifier_restauration.py --vivant copie.db --restaure "%CIBLE%" --json _repetition.json

echo.
echo ==============================================================
echo   Duree de la restauration : %MINUTES% min %RESTE% s
echo ==============================================================
echo.
echo   Cherche "REPETITION REUSSIE" ci-dessus. Le rapport ne l'ecrit
echo   que si l'integrite, les tables, le nombre de noms ET chaque
echo   nom concordent. Detail machine : _repetition.json
echo.
echo   Le dossier d'essai peut etre supprime a la main quand tu as
echo   note le resultat. Ce lanceur ne supprime jamais rien.
echo.
pause

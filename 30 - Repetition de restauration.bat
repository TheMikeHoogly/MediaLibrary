@echo off
chcp 65001 >nul
cd /d "%~dp0"
REM Contenu en ASCII pur : cmd.exe relit le fichier par decalage d'octets.
setlocal EnableDelayedExpansion

REM Dossier d'essai : modifiable ici, ou passe en argument
REM   "30 - Repetition de restauration.bat" E:\autre-essai
set "CIBLE=C:\temp\essai-restauration"
if not "%~1"=="" set "CIBLE=%~1"

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

REM --- Garde-fous : tout ce qui peut manquer se dit AVANT d'ecrire ---
if /i "%CIBLE%"=="%CD%" (
    echo   REFUS : le dossier d'essai est le dossier du projet.
    echo   Passe un autre chemin en argument, ou change CIBLE en tete.
    pause
    exit /b 1
)

for %%d in ("%CIBLE%") do set "LECTEUR=%%~dd"
if not exist "%LECTEUR%\" (
    echo   REFUS : le lecteur %LECTEUR% n'existe pas sur ce PC.
    echo   Relance avec un chemin valide, par exemple :
    echo      "%~nx0" C:\temp\essai-restauration
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

REM Chrono en batch pur : le "1xx-100" evite que 08 et 09 passent pour
REM de l'octal, et aucun guillemet imbrique ne peut casser la ligne.
set "H=%TIME: =0%"
set /a T0=(1%H:~0,2%-100)*3600+(1%H:~3,2%-100)*60+(1%H:~6,2%-100)

echo.
echo --------------------------------------------------------------
echo   Etape 1/4 : ce que GIT rend (le code)
echo --------------------------------------------------------------
if not exist "%CIBLE%\" mkdir "%CIBLE%"
if not exist "%CIBLE%\" (
    echo   Impossible de creer %CIBLE%. Chemin ou droits ?
    pause
    exit /b 1
)
if exist "%CIBLE%\.git" (
    echo   Depot deja present, clone saute.
) else (
    git clone "%DEPOT%" "%CIBLE%"
    if errorlevel 1 (
        echo.
        echo   Le clone a echoue. Deux causes usuelles : le dossier
        echo   n'etait pas vide (git refuse), ou le reseau/GitHub n'a
        echo   pas repondu. Le message de git ci-dessus tranche.
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

set "H=%TIME: =0%"
set /a T1=(1%H:~0,2%-100)*3600+(1%H:~3,2%-100)*60+(1%H:~6,2%-100)
set /a SECONDES=T1-T0
if %SECONDES% LSS 0 set /a SECONDES=SECONDES+86400
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

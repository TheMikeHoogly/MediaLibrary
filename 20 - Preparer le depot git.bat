@echo off
chcp 65001 >nul
cd /d "%~dp0"
REM Contenu en ASCII pur : cmd.exe relit le fichier par decalage d'octets.

where git >nul 2>&1
if errorlevel 1 (
    echo   git est introuvable. Installe-le depuis https://git-scm.com
    echo   puis relance ce script.
    pause
    exit /b 1
)

if exist ".git" goto :enregistrer

REM ==============================================================
REM  Premier passage : creation du depot
REM ==============================================================
echo ==============================================================
echo   PREPARATION DU DEPOT GIT
echo ==============================================================
echo.
echo   server.py fait plus de 8 500 lignes et n'a AUCUN historique.
echo   Apres une session de modifications, rien ne permet de revenir
echo   sur un changement precis.
echo.
echo   Ce script cree un depot LOCAL. Il n'envoie rien en ligne.
echo.
echo   NE SERONT PAS VERSIONNES (voir .gitignore) :
echo     - photos.db          chemins, tags et empreintes de tes photos
echo     - animal_thumbs      1 674 decoupes
echo     - face_thumbs        20 648 vignettes de visages
echo     - recuperees         photos personnelles reconstruites
echo     - eval\*.json        jeux d'evaluation avec chemins reels
echo     - data_dir.txt etc.  chemins prives et jetons
echo.
echo   Seuls le CODE et la DOCUMENTATION partent dans le depot.
echo.
pause

echo.
echo   Etape 1 sur 3 : initialisation
echo --------------------------------------------------------------
git init
git branch -M main

echo.
echo   Etape 2 sur 3 : verification de ce qui serait versionne
echo --------------------------------------------------------------
git add -A
git --no-pager diff --cached --name-only > "%TEMP%\gitlist.txt"
echo   Nombre de fichiers retenus :
find /c /v "" < "%TEMP%\gitlist.txt"
call :controle_fuite "%TEMP%\gitlist.txt"
if errorlevel 1 (
    git reset
    pause
    exit /b 1
)
echo.
echo   Liste complete : %TEMP%\gitlist.txt
git --no-pager count-objects -vH | findstr size-pack

echo.
choice /c ON /n /m "   Creer le premier enregistrement ? [O]ui / [N]on : "
if errorlevel 2 (
    git reset
    echo.
    echo   Annule. Le depot existe mais reste vide.
    pause
    exit /b 0
)

echo.
echo   Etape 3 sur 3 : premier enregistrement
echo --------------------------------------------------------------
git commit -m "Phototheque locale : serveur, pipelines IA, evaluations"
echo.
echo ==============================================================
echo   DEPOT LOCAL PRET
echo ==============================================================
echo.
echo   Relance ce script quand tu veux enregistrer tes prochaines
echo   modifications : chaque enregistrement est un point de retour.
echo.
echo   Pour publier sur GitHub, en depot PRIVE :
echo     1. Cree un depot vide sur github.com (sans README)
echo     2. git remote add origin https://github.com/TON-COMPTE/NOM.git
echo     3. git push -u origin main
echo.
echo   Active ensuite le connecteur GitHub dans les reglages de
echo   claude.ai : Claude pourra proposer des modifications sous
echo   forme de pull requests relisibles.
echo.
pause
exit /b 0

REM ==============================================================
REM  Passages suivants : enregistrer les modifications
REM ==============================================================
:enregistrer
echo ==============================================================
echo   ENREGISTRER LES MODIFICATIONS
echo ==============================================================
echo.
echo   Chaque enregistrement est un point de retour possible.
echo.
echo   Derniers enregistrements :
echo --------------------------------------------------------------
git --no-pager log --oneline -8
echo.
echo   Modifications depuis le dernier :
echo --------------------------------------------------------------
git --no-pager status --short
echo.

git --no-pager status --porcelain > "%TEMP%\gitchg.txt"
for /f %%A in ('find /c /v "" ^< "%TEMP%\gitchg.txt"') do set NCHG=%%A
if "%NCHG%"=="0" (
    echo   Rien a enregistrer : tout est deja sauvegarde.
    echo.
    pause
    exit /b 0
)

call :controle_fuite "%TEMP%\gitchg.txt"
if errorlevel 1 (
    pause
    exit /b 1
)

echo.
choice /c ON /n /m "   Enregistrer ces modifications ? [O]ui / [N]on : "
if errorlevel 2 (
    echo.
    echo   Annule. Rien n'a ete enregistre.
    pause
    exit /b 0
)

set "MSG="
set /p MSG=  Decris le changement en une ligne (Entree = date du jour) :
if "%MSG%"=="" set "MSG=Modifications du %DATE%"

git add -A
git commit -m "%MSG%"

echo.
echo   Enregistre. Pour revenir en arriere plus tard :
echo     git --no-pager log --oneline     voir l'historique
echo     git checkout -- FICHIER          annuler un fichier modifie
echo     git revert IDENTIFIANT           defaire un enregistrement
echo.
git --no-pager remote -v | findstr origin >nul
if errorlevel 1 (
    echo   Aucun depot distant. Pour publier sur GitHub :
    echo     git remote add origin https://github.com/TON-COMPTE/NOM.git
    echo     git push -u origin main
) else (
    echo   Pour envoyer sur GitHub : git push
)
echo.
pause
exit /b 0

REM ==============================================================
REM  Controle de fuite : aucune donnee privee ne doit etre versionnee
REM ==============================================================
:controle_fuite
findstr /i /c:"photos.db" /c:"thumbs" /c:"recuperees" /c:"data_dir" ^
    /c:"dossier_uploads" /c:"hf_token" /c:".venv" %1 >nul
if errorlevel 1 (
    echo     [OK] aucune donnee privee dans la liste.
    exit /b 0
)
echo.
echo     [ALERTE] des fichiers sensibles sont retenus :
findstr /i /c:"photos.db" /c:"thumbs" /c:"recuperees" /c:"data_dir" ^
    /c:"dossier_uploads" /c:"hf_token" /c:".venv" %1
echo.
echo     Corrige .gitignore AVANT de continuer.
exit /b 1

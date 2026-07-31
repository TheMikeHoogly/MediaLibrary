@echo off
chcp 65001 >nul
cd /d "%~dp0"
REM Contenu en ASCII pur : cmd.exe relit le fichier par decalage d'octets.
echo ==============================================================
echo   PREPARATION DU DEPOT GIT
echo ==============================================================
echo.
echo   server.py fait plus de 8 500 lignes et n'a AUCUN historique.
echo   Apres une session de modifications, rien ne permet de revenir
echo   sur un changement precis.
echo.
echo   Ce script cree un depot local. Il n'envoie RIEN en ligne :
echo   la publication sur GitHub reste une decision separee.
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

where git >nul 2>&1
if errorlevel 1 (
    echo   git est introuvable. Installe-le depuis https://git-scm.com
    echo   puis relance ce script.
    pause
    exit /b 1
)

if exist ".git" (
    echo.
    echo   Un depot existe deja. Etat actuel :
    echo --------------------------------------------------------------
    git status --short
    echo.
    pause
    exit /b 0
)

echo.
echo   Etape 1 sur 3 : initialisation
echo --------------------------------------------------------------
git init
git branch -M main

echo.
echo   Etape 2 sur 3 : verification de ce qui serait versionne
echo --------------------------------------------------------------
git add -A
echo.
echo   Fichiers retenus :
git diff --cached --name-only
echo.
echo   Taille totale :
git count-objects -vH | findstr size-pack

echo.
echo   Verifie cette liste. Aucune photo, aucune base, aucun chemin
echo   prive ne doit y figurer.
echo.
choice /c ON /n /m "   Creer le premier commit ? [O]ui / [N]on : "
if errorlevel 2 (
    git reset
    echo.
    echo   Annule. Le depot existe mais reste vide.
    pause
    exit /b 0
)

echo.
echo   Etape 3 sur 3 : premier commit
echo --------------------------------------------------------------
git commit -m "Phototheque locale : serveur, pipelines IA, evaluations"
echo.
echo ==============================================================
echo   DEPOT LOCAL PRET
echo ==============================================================
echo.
echo   Pour publier sur GitHub, en depot PRIVE :
echo.
echo     1. Cree un depot vide sur github.com (sans README)
echo     2. git remote add origin https://github.com/TON-COMPTE/NOM.git
echo     3. git push -u origin main
echo.
echo   Ensuite seulement, active le connecteur GitHub dans les
echo   reglages de claude.ai : Claude pourra alors proposer des
echo   modifications sous forme de pull requests relisibles.
echo.
pause

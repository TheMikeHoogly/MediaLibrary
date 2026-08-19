@echo off
REM ============================================================
REM   Fusionner la branche courante dans main - MediaLibrary
REM
REM   Fait un FAST-FORWARD de main COTE REMOTE, sans jamais
REM   faire "git checkout main" en local. Cela contourne le
REM   verrou fichier de server.py tenu par le serveur : aucun
REM   fichier du repertoire de travail n'est reecrit.
REM
REM   A lancer sur la machine de Mike (identifiants GitHub
REM   presents). Le sandbox Claude ne peut pas pousser.
REM
REM   ASCII PUR obligatoire (voir CLAUDE.md / verifier_bat.py).
REM ============================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================================
echo   Fusionner la branche dans main - MediaLibrary
echo ============================================================
echo.

git rev-parse --is-inside-work-tree >nul 2>&1
if errorlevel 1 (
  echo ERREUR : ce dossier n'est pas un depot git.
  pause
  exit /b 1
)

REM --- Verrou git perime (.git\index.lock) ---
REM   Un client git graphique ouvert sur le depot, ou un process git plante,
REM   laisse un .lock qui bloque les operations git.
set "GITLOCK="
if exist ".git\index.lock" set "GITLOCK=1"
if exist ".git\HEAD.lock" set "GITLOCK=1"
if not defined GITLOCK goto :apres_verrou
echo ATTENTION : un verrou git est present dans .git (index.lock ou HEAD.lock).
echo   Cause habituelle : un client git graphique ouvert sur ce depot,
echo   ou un process git precedent qui a plante.
echo   Ferme ce client s'il est ouvert sur ce depot avant de continuer.
echo.
choice /c ON /n /m "Supprimer ce verrou et continuer ? (O = oui / N = annuler) : "
if errorlevel 2 (
  echo Annule : le verrou est laisse en place.
  pause
  exit /b 1
)
del /q ".git\*.lock" 2>nul
del /q ".git\refs\heads\*.lock" 2>nul
if exist ".git\index.lock" (
  echo Echec : impossible de supprimer le verrou. Un client git tourne encore ?
  echo Ferme-le completement, puis relance ce script.
  pause
  exit /b 1
)
echo Verrou supprime.
echo.
:apres_verrou

for /f "delims=" %%b in ('git branch --show-current') do set "BRANCH=%%b"
echo Branche courante : !BRANCH!
for /f "delims=" %%c in ('git log -1 --oneline') do echo Dernier commit   : %%c
echo.

if "!BRANCH!"=="main" (
  echo Tu es deja sur main : rien a fusionner.
  echo Bascule d'abord sur ta branche de travail.
  pause
  exit /b 1
)

REM --- Verifier qu'il ne reste rien a commiter ---
git diff --quiet && git diff --cached --quiet
if errorlevel 1 (
  echo ATTENTION : des modifications ne sont pas commitees :
  echo.
  git status -s
  echo.
  echo Commit d'abord avec "27 - Commit de session.bat", puis relance.
  pause
  exit /b 1
)

REM --- Synchroniser les references distantes ---
echo Recuperation de l'etat distant (git fetch)...
git fetch origin
if errorlevel 1 (
  echo Echec du fetch. Verifie ta connexion / tes identifiants GitHub.
  pause
  exit /b 1
)
echo.

REM --- La fusion est-elle un fast-forward propre ? ---
REM   main doit etre un ancetre de la branche courante.
git merge-base --is-ancestor origin/main HEAD
if errorlevel 1 (
  echo ============================================================
  echo   FUSION IMPOSSIBLE EN FAST-FORWARD
  echo ============================================================
  echo   main a avance de son cote : la branche a diverge.
  echo   Il faut une vraie fusion ^(merge commit ou rebase^), qui
  echo   REECRIT server.py en local -- donc serveur ARRETE d'abord.
  echo.
  echo   Etapes manuelles, serveur arrete :
  echo     git checkout main
  echo     git pull origin main
  echo     git merge !BRANCH!
  echo     git push origin main
  echo     git checkout !BRANCH!
  echo.
  pause
  exit /b 1
)

echo Fast-forward possible : main est un ancetre de !BRANCH!.
echo.
echo Ce script va :
echo   1. Pousser !BRANCH! sur origin
echo   2. Avancer main sur origin jusqu'au sommet de !BRANCH!
echo   3. Mettre a jour la ref locale main (sans checkout)
echo.
choice /c ON /n /m "Continuer ? (O = oui / N = annuler) : "
if errorlevel 2 (
  echo Annule. Rien n'a change.
  pause
  exit /b 0
)
echo.

REM --- 1. Publier la branche ---
echo [1/3] Push de la branche !BRANCH!...
git push origin HEAD
if errorlevel 1 (
  echo Echec du push de la branche. Abandon.
  pause
  exit /b 1
)
echo.

REM --- 2. Fast-forward de main cote remote (pas de checkout local) ---
echo [2/3] Fast-forward de main sur origin...
git push origin HEAD:main
if errorlevel 1 (
  echo Echec du push vers main. main a peut-etre avance entre-temps.
  echo Relance le script ^(il refera le fetch et le controle^).
  pause
  exit /b 1
)
echo.

REM --- 3. Mettre a jour la ref locale main sans la checkouter ---
echo [3/3] Mise a jour de la ref locale main...
git fetch origin main:main
if errorlevel 1 (
  echo main distant est a jour, mais la ref locale n'a pas pu suivre.
  echo Sans gravite : elle se mettra a jour au prochain fetch.
)
echo.

echo ============================================================
echo   FUSION REUSSIE
echo ============================================================
echo   !BRANCH! est mergee dans main (local et distant).
echo.
echo   PROCHAINES ACTIONS :
echo   - Prochain chantier : Claude proposera la branche et le
echo     titre via SESSION_COMMIT.txt ^(lu par le bat 27^).
echo     A la main : git checkout -b feat/mon-chantier
echo     ^(depuis ici : la branche est au niveau de main^)
echo   - Branche terminee ? Pour la supprimer ^(optionnel^) :
echo     git push origin --delete !BRANCH!
echo     git branch -d !BRANCH!   ^(bascule d'abord ailleurs^)
echo.
pause
exit /b 0

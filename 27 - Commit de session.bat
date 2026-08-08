@echo off
REM ============================================================
REM   Commit de session - MediaLibrary
REM   Automatise : branche (optionnelle) + add -A + commit + push.
REM   ASCII PUR obligatoire (voir CLAUDE.md / verifier_bat.py).
REM ============================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================================
echo   Commit de session - MediaLibrary
echo ============================================================
echo.

git rev-parse --is-inside-work-tree >nul 2>&1
if errorlevel 1 (
  echo ERREUR : ce dossier n'est pas un depot git.
  pause
  exit /b 1
)

REM --- Verrou git perime (.git\index.lock) ---
REM   Deja rencontre 2x : un client git (GitKraken Desktop) ouvert sur le
REM   depot, ou un process git plante, laisse un .lock qui bloque tout commit.
if not exist ".git\index.lock" goto :apres_verrou
echo ATTENTION : un verrou git est present : .git\index.lock
echo   Cause habituelle : GitKraken Desktop ouvert sur ce depot,
echo   ou un process git precedent qui a plante.
echo   Ferme GitKraken Desktop s'il est ouvert sur ce depot avant de continuer.
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
echo.
echo Etat du depot :
git status -s
echo.

REM --- Branche (optionnel) ---
REM La plupart du temps : repondre N pour commiter sur la branche courante.
choice /c ON /n /m "Creer une NOUVELLE branche ? (O = oui / N = rester sur !BRANCH!) : "
if errorlevel 2 goto :apres_branche
set "NEWBR="
set /p "NEWBR=Nom de la nouvelle branche : "
if "!NEWBR!"=="" (
  echo Nom vide : on reste sur !BRANCH!.
  goto :apres_branche
)
git checkout -b "!NEWBR!"
if errorlevel 1 (
  echo Echec de creation de la branche. Abandon.
  pause
  exit /b 1
)
set "BRANCH=!NEWBR!"
:apres_branche

REM --- Message de commit ---
set "MSG="
set /p "MSG=Message de commit : "
if "!MSG!"=="" (
  echo Message vide. Abandon, rien n'a ete commite.
  pause
  exit /b 1
)

git add -A
git commit -m "!MSG!"
if errorlevel 1 (
  echo.
  echo Rien a commiter ^(ou echec du commit^).
  pause
  exit /b 1
)

echo.
echo Commit fait sur la branche !BRANCH!.
echo.

REM --- Push (optionnel) ---
choice /c ON /n /m "Pousser vers origin maintenant ? (O = oui / N = non) : "
if errorlevel 2 goto :rappel
git push -u origin "!BRANCH!"
if errorlevel 1 (
  echo.
  echo Le push a echoue. Tu peux reessayer : git push -u origin !BRANCH!
)

:rappel
echo.
echo ------------------------------------------------------------
echo   RAPPEL fin de session :
echo   - ROADMAP.md et PROMPT_NOUVELLE_SESSION.md a jour ?
echo     ^(Claude les prepare pour la prochaine session.^)
echo   - Redemarrer le serveur si le code a change :
echo     "0 - Demarrer le serveur.bat"
echo ------------------------------------------------------------
echo.
pause

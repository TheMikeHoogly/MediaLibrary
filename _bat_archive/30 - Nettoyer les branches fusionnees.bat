@echo off
REM ============================================================
REM   Nettoyer les branches fusionnees - MediaLibrary
REM
REM   Supprime les branches de travail DEJA fusionnees dans main
REM   (local, puis optionnellement sur GitHub). Sans risque :
REM   "git branch -d" REFUSE de supprimer une branche dont le
REM   travail n'est pas dans main -- il n'y a donc aucun moyen
REM   de perdre du code avec ce script.
REM
REM   Ne touche jamais : main, la branche courante.
REM   Ne fait AUCUN checkout : server.py n'est pas reecrit, le
REM   serveur peut rester allume.
REM
REM   ASCII PUR obligatoire (voir CLAUDE.md).
REM ============================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================================
echo   Nettoyer les branches fusionnees - MediaLibrary
echo ============================================================
echo.

git rev-parse --is-inside-work-tree >nul 2>&1
if errorlevel 1 (
  echo ERREUR : ce dossier n'est pas un depot git.
  pause
  exit /b 1
)

for /f "delims=" %%b in ('git branch --show-current') do set "BRANCH=%%b"
echo Branche courante : !BRANCH!   ^(elle ne sera pas touchee^)
echo.

echo Recuperation de l'etat distant (git fetch)...
git fetch --prune origin
if errorlevel 1 (
  echo Echec du fetch. Verifie ta connexion / tes identifiants GitHub.
  echo Le nettoyage local reste possible ; le distant sera ignore.
)
echo.

REM --- Liste des candidates : fusionnees dans main, hors main et courante ---
set "N=0"
echo Branches fusionnees dans main, donc supprimables :
echo ------------------------------------------------------------
for /f "tokens=* delims= " %%b in ('git branch --merged main --format="%%(refname:short)"') do (
  if not "%%b"=="main" if not "%%b"=="!BRANCH!" (
    set /a N+=1
    echo   %%b
  )
)
echo ------------------------------------------------------------
if "!N!"=="0" (
  echo Aucune branche a nettoyer : le depot est deja propre.
  echo.
  pause
  exit /b 0
)
echo !N! branche^(s^) candidate^(s^).
echo.
echo Rappel : tout leur travail est deja dans main. Supprimer ces
echo etiquettes ne supprime aucun commit ni aucun fichier.
echo.

choice /c ON /n /m "Supprimer ces branches EN LOCAL ? (O = oui / N = annuler) : "
if errorlevel 2 (
  echo Annule. Rien n'a change.
  pause
  exit /b 0
)
echo.

set "SUPPR=0"
set "ECHEC=0"
for /f "tokens=* delims= " %%b in ('git branch --merged main --format="%%(refname:short)"') do (
  if not "%%b"=="main" if not "%%b"=="!BRANCH!" (
    git branch -d "%%b" >nul 2>&1
    if errorlevel 1 (
      set /a ECHEC+=1
      echo   REFUS  %%b   ^(git protege : travail absent de main^)
    ) else (
      set /a SUPPR+=1
      echo   ok     %%b
    )
  )
)
echo.
echo Local : !SUPPR! supprimee^(s^), !ECHEC! refusee^(s^).
echo.

REM --- Volet distant (optionnel) ---
echo Les memes branches peuvent aussi etre retirees de GitHub.
echo Elles y sont visibles dans la liste des branches du depot.
echo.
choice /c ON /n /m "Nettoyer aussi sur GitHub ? (O = oui / N = non) : "
if errorlevel 2 (
  echo Distant laisse tel quel.
  echo.
  echo Termine.
  pause
  exit /b 0
)
echo.

set "RSUPPR=0"
for /f "tokens=* delims= " %%b in ('git branch -r --merged main --format="%%(refname:short)"') do (
  set "RB=%%b"
  set "RB=!RB:origin/=!"
  if not "!RB!"=="main" if not "!RB!"=="!BRANCH!" if not "!RB!"=="HEAD" (
    git push origin --delete "!RB!" >nul 2>&1
    if errorlevel 1 (
      echo   echec  !RB!
    ) else (
      set /a RSUPPR+=1
      echo   ok     !RB!
    )
  )
)
echo.
echo Distant : !RSUPPR! branche^(s^) supprimee^(s^) sur GitHub.
echo.
echo ============================================================
echo   NETTOYAGE TERMINE
echo ============================================================
echo   main est intacte, ainsi que la branche courante.
echo   Aucun commit n'a ete supprime.
echo.
pause
exit /b 0

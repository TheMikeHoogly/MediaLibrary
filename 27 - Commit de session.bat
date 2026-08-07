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

for /f "delims=" %%b in ('git branch --show-current') do set "BRANCH=%%b"
echo Branche courante : !BRANCH!
echo.
echo Etat du depot :
git status -s
echo.

REM --- Branche (optionnel) ---
set "NEWBR="
set /p "NEWBR=Creer une NOUVELLE branche ? (nom, ou Entree pour rester) : "
if not "!NEWBR!"=="" (
  git checkout -b "!NEWBR!"
  if errorlevel 1 (
    echo Echec de creation de la branche. Abandon.
    pause
    exit /b 1
  )
  set "BRANCH=!NEWBR!"
)

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

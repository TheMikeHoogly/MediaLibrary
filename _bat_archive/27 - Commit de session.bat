@echo off
REM ============================================================
REM   Commit de session - MediaLibrary
REM   Automatise : branche + add -A + commit + push.
REM
REM   Lit SESSION_COMMIT.txt (prepare par Claude en fin de
REM   session) et propose par defaut la branche et le titre.
REM   Entree = accepter la proposition. Sans ce fichier, le
REM   script pose les questions comme avant.
REM   Format du fichier (ASCII, sans guillemets ni "!") :
REM     branche=feat/mon-chantier
REM     titre=Mon titre de commit
REM
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
REM   Deja rencontre : un client git graphique ouvert sur le depot, ou un
REM   process git plante, laisse un .lock qui bloque tout commit.
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

REM --- Propositions de la session (SESSION_COMMIT.txt) ---
set "SUG_BRANCHE="
set "SUG_TITRE="
if exist "SESSION_COMMIT.txt" (
  for /f "usebackq eol=# tokens=1* delims==" %%a in ("SESSION_COMMIT.txt") do (
    if /i "%%a"=="branche" set "SUG_BRANCHE=%%b"
    if /i "%%a"=="titre" set "SUG_TITRE=%%b"
  )
)

echo Branche courante  : !BRANCH!
if defined SUG_BRANCHE echo Branche proposee  : !SUG_BRANCHE!
if defined SUG_TITRE echo Titre propose     : !SUG_TITRE!
echo.
echo Etat du depot :
git status -s
echo.

REM --- Branche ---
if not defined SUG_BRANCHE goto :branche_manuelle
if /i "!SUG_BRANCHE!"=="!BRANCH!" goto :apres_branche
choice /c ON /n /m "Basculer sur la branche proposee !SUG_BRANCHE! ? (O = oui / N = rester sur !BRANCH!) : "
if errorlevel 2 goto :branche_manuelle
git checkout -b "!SUG_BRANCHE!" 2>nul
if not errorlevel 1 goto :branche_ok
git checkout "!SUG_BRANCHE!"
if errorlevel 1 (
  echo Echec de bascule sur !SUG_BRANCHE!. Abandon.
  pause
  exit /b 1
)
:branche_ok
set "BRANCH=!SUG_BRANCHE!"
goto :apres_branche

:branche_manuelle
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
if defined SUG_TITRE (
  set /p "MSG=Message de commit [Entree = titre propose] : "
  if "!MSG!"=="" set "MSG=!SUG_TITRE!"
) else (
  set /p "MSG=Message de commit : "
)
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

REM La proposition est consommee : elle ne doit pas etre reproposee.
if exist "SESSION_COMMIT.txt" del /q "SESSION_COMMIT.txt"

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
echo   PROCHAINES ACTIONS :
echo   - Code valide en reel ? Fusionner dans main :
echo     "28 - Fusionner la branche dans main.bat"
echo   - Redemarrer le serveur si le code a change :
echo     "0 - Demarrer le serveur.bat"
echo   - ROADMAP.md et PROMPT_NOUVELLE_SESSION.md a jour ?
echo     ^(Claude les prepare pour la prochaine session.^)
echo ------------------------------------------------------------
echo.
pause

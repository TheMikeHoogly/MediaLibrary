@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"
title MediaLibrary - Serveur

REM ============================================================
REM   SUPERVISEUR DU SERVEUR
REM
REM   Il lance server.py, et le RELANCE quand celui-ci sort avec
REM   le code 42 - le code que server.py rend quand le fichier
REM   _commande_serveur.txt dit "redemarrer".
REM
REM   Pourquoi un superviseur plutot qu'un serveur qui se relance
REM   tout seul : un processus ne peut pas garantir que son port
REM   est libere avant de le reprendre. Ici, l'ancien est MORT
REM   quand le nouveau demarre.
REM
REM   "arret" ne tue PAS cette fenetre : le superviseur attend,
REM   et repart des que la commande repasse a "marche". Sinon un
REM   arret serait sans retour pour qui ne peut pas lancer de
REM   processus sur cette machine.
REM
REM   Fermer cette fenetre arrete tout - comme avant.
REM ============================================================

set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
set "CMDFILE=_commande_serveur.txt"
set "GENFILE=_generation.txt"
set /a ECHECS=0

REM --- GENERATION : a qui appartient cette machine ? -----------
REM   Le bat 0 ecrit un jeton neuf dans %GENFILE% a chaque
REM   demarrage. Ce superviseur retient celui qu'il a lu en
REM   naissant ; s'il change, c'est qu'un nouveau demarrage a eu
REM   lieu et que cette fenetre est l'ancienne : elle se retire.
REM
REM   Pourquoi pas taskkill par titre de fenetre : il ne retrouve
REM   PAS fiablement les fenetres console. Le 20/08 il n'a rien
REM   tue, l'ancien superviseur a survecu, a cru a un plantage
REM   quand on a tue son serveur par PID, et en a relance un
REM   second. Un fichier ne se devine pas.
set "GEN="
if exist "%GENFILE%" set /p GEN=<"%GENFILE%"
set "GEN=!GEN: =!"

:boucle
set "GENNOW="
if exist "%GENFILE%" set /p GENNOW=<"%GENFILE%"
set "GENNOW=!GENNOW: =!"
if not "!GENNOW!"=="!GEN!" (
  echo.
  echo [superviseur] Un nouveau demarrage a eu lieu - cette fenetre est
  echo [superviseur] l'ancienne, elle se retire pour ne pas relancer un
  echo [superviseur] second serveur.
  timeout /t 4 >nul
  exit /b 0
)

set "CMD=marche"
if exist "%CMDFILE%" set /p CMD=<"%CMDFILE%"
set "CMD=!CMD: =!"

if /i "!CMD!"=="arret" (
  echo [superviseur] Serveur ARRETE sur commande. Il repartira des que
  echo [superviseur] %CMDFILE% repassera a "marche".
  timeout /t 3 >nul
  goto boucle
)

echo.
echo [superviseur] Demarrage du serveur...
"%PY%" server.py
set "CODE=!ERRORLEVEL!"
echo.
echo [superviseur] Le serveur s'est arrete (code !CODE!).

if "!CODE!"=="42" (
  set /a ECHECS=0
  echo [superviseur] Redemarrage demande - on relance.
  timeout /t 2 >nul
  goto boucle
)

set /a ECHECS+=1
if !ECHECS! GEQ 5 (
  echo.
  echo [superviseur] Cinq arrets anormaux d'affilee. J'arrete la pour ne pas
  echo [superviseur] boucler indefiniment : l'erreur est dans les lignes
  echo [superviseur] ci-dessus. Relance ce bat une fois corrigee.
  echo.
  pause
  exit /b 1
)
echo [superviseur] Arret anormal !ECHECS!/5 - nouvelle tentative dans 5 s.
echo [superviseur] (Ctrl+C ou fermer la fenetre pour ne pas relancer.)
timeout /t 5 >nul
goto boucle

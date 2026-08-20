@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"
title MediaLibrary - Git

REM ============================================================
REM   AGENT GIT
REM
REM   Il surveille _commande_git.txt et, quand il y lit autre
REM   chose que "rien", lance git_agent.py. Celui-ci CONTROLE
REM   avant de livrer : verrou, branche, fichiers, serveur a
REM   jour, tests, bats, lint. Il refuse plutot que de graver
REM   une observation fausse.
REM
REM   Pourquoi une fenetre separee et pas le serveur : le
REM   serveur est l'OBJET du commit, un git qui bloque
REM   bloquerait une requete, et un serveur du reseau local
REM   capable de lancer git est une surface qu'on ne veut pas.
REM
REM   Pourquoi pas le superviseur du serveur : il est bloque
REM   tant que server.py tourne, il ne peut rien surveiller.
REM
REM   Fermer cette fenetre ferme le canal - et rien d'autre.
REM   Le serveur continue, les gestes manuels du bat 27 aussi.
REM ============================================================

set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
set "CMDFILE=_commande_git.txt"
set "GENFILE=_generation.txt"

REM --- GENERATION : meme regle que le superviseur du serveur ---
REM   Le bat 0 ecrit un jeton neuf a chaque demarrage ; si celui
REM   qu'on lit differe de celui qu'on a lu en naissant, cette
REM   fenetre est l'ancienne et se retire. Deux agents git qui
REM   liraient la meme commande la joueraient deux fois.
set "GEN="
if exist "%GENFILE%" set /p GEN=<"%GENFILE%"
set "GEN=!GEN: =!"

if not exist "git_agent.py" (
  echo ERREUR : git_agent.py est introuvable dans ce dossier.
  pause
  exit /b 1
)

REM Etat de depart : rien a faire. Sinon une commande laissee par
REM une session precedente partirait toute seule au demarrage.
> "%CMDFILE%" echo rien

echo.
echo [agent git] En ecoute sur %CMDFILE%.
echo [agent git] Mots acceptes : rien ^| ping ^| commit ^| livrer
echo [agent git] "commit" = controles + commit + push, main INTACTE.
echo [agent git] "livrer" = idem, plus le fast-forward de main.
echo [agent git] "ping"   = signe de vie, ne touche a rien.
echo.
echo [agent git] NE PAS FERMER cette fenetre : elle est le canal par
echo [agent git] lequel la sandbox livre. La fermer ne casse rien
echo [agent git] d'autre, mais les commits redeviennent manuels.
echo.

:boucle
set "GENNOW="
if exist "%GENFILE%" set /p GENNOW=<"%GENFILE%"
set "GENNOW=!GENNOW: =!"
if not "!GENNOW!"=="!GEN!" (
  echo.
  echo [agent git] Un nouveau demarrage a eu lieu - cette fenetre se retire.
  timeout /t 4 >nul
  exit /b 0
)

REM Signe de vie : ce fichier est TOUCHE a chaque tour. Son age dit si
REM l'agent ecoute encore - sans lui, une fenetre morte-nee etait
REM indiscernable d'une fenetre en ecoute (arrive le 19/08, personne
REM ne s'en est apercu avant de chercher pourquoi rien ne se livrait).
> "_agent_git_vu.txt" echo en ecoute

set "CMD=rien"
if exist "%CMDFILE%" set /p CMD=<"%CMDFILE%"
set "CMD=!CMD: =!"

REM Toute lecture qui n'est PAS exactement "rien" passe la main a
REM Python - y compris une lecture douteuse. Python est tolerant
REM (BOM, LF, CRLF) et fait autorite ; une commande lue de travers
REM coute un lancement pour rien, jamais une livraison perdue.
if /i not "!CMD!"=="rien" (
  echo.
  echo [agent git] Commande lue : "!CMD!"
  "%PY%" git_agent.py --executer
  echo.
)

timeout /t 3 >nul
goto boucle

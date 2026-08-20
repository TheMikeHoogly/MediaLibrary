@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"
title MediaLibrary - Bancs

REM ============================================================
REM   AGENT DES BANCS
REM
REM   Il surveille _commande_banc.txt et, quand il y lit autre
REM   chose que "rien", lance banc_agent.py. Celui-ci CONTROLE
REM   avant de lancer : famille du script, absence de chemin,
REM   arguments simples. Il ne connait aucun shell, et il ne
REM   lance que ce qui MESURE - jamais ce qui ecrit.
REM
REM   Pourquoi il existe : le 20/08 un banc n'a pas pu tourner
REM   depuis la sandbox (sa sortie reseau lui refuse le LAN, ou
REM   vit le serveur qui detient SigLIP). Il a fallu que Mike le
REM   lance a la main - et sa sortie a refute la conclusion tiree
REM   de deux echantillons. Le banc avait raison d'exister ;
REM   l'aller-retour par le clavier coutait une demi-journee.
REM
REM   Pourquoi une TROISIEME fenetre : un banc peut durer dix
REM   minutes. Loge dans la fenetre de l'agent git, il bloquerait
REM   le canal de livraison pendant tout ce temps - c'est-a-dire
REM   exactement au moment ou l'on veut livrer ce qu'on vient de
REM   mesurer.
REM
REM   Fermer cette fenetre ferme le canal - et rien d'autre.
REM ============================================================

set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
set "CMDFILE=_commande_banc.txt"
set "GENFILE=_generation.txt"

REM --- GENERATION : meme regle que les deux autres superviseurs ---
REM   Le bat 0 ecrit un jeton neuf a chaque demarrage ; si celui
REM   qu'on lit differe de celui qu'on a lu en naissant, cette
REM   fenetre est l'ancienne et se retire. Deux agents qui
REM   liraient le meme ordre le joueraient deux fois.
set "GEN="
if exist "%GENFILE%" set /p GEN=<"%GENFILE%"
set "GEN=!GEN: =!"

if not exist "banc_agent.py" (
  echo ERREUR : banc_agent.py est introuvable dans ce dossier.
  pause
  exit /b 1
)

REM Etat de depart : rien a faire. Sinon un ordre laisse par une
REM session precedente partirait tout seul au demarrage.
> "%CMDFILE%" echo rien

echo.
echo [bancs] En ecoute sur %CMDFILE%.
echo [bancs] Ordre = le nom d'un banc et ses arguments, par exemple :
echo [bancs]   mesure_espece_recherche.py --base copie.db --exemples 14
echo [bancs] Familles admises : mesure_ verifier_ diagnostic_ comptes_
echo [bancs]                    inventaire_ test_ eval_
echo [bancs] "ping" = signe de vie, ne lance rien.
echo [bancs] La sortie va dans _banc_sortie.txt, le rapport dans
echo [bancs] _etat_banc.json.
echo.
echo [bancs] NE PAS FERMER cette fenetre : elle est le canal par
echo [bancs] lequel la sandbox MESURE. La fermer ne casse rien
echo [bancs] d'autre, mais les bancs redeviennent manuels.
echo.

:boucle
set "GENNOW="
if exist "%GENFILE%" set /p GENNOW=<"%GENFILE%"
set "GENNOW=!GENNOW: =!"
if not "!GENNOW!"=="!GEN!" (
  echo.
  echo [bancs] Un nouveau demarrage a eu lieu - cette fenetre se retire.
  timeout /t 4 >nul
  exit /b 0
)

REM Signe de vie : ce fichier est TOUCHE a chaque tour. Son age dit
REM si l'agent ecoute encore - meme raison que pour l'agent git,
REM ou une fenetre morte-nee etait indiscernable d'une fenetre en
REM ecoute (19/08).
> "_agent_banc_vu.txt" echo en ecoute

set "CMD="
if exist "%CMDFILE%" set /p CMD=<"%CMDFILE%"
set "TEST=!CMD: =!"

REM Un ordre contient des espaces ; on ne compare donc que sur une
REM copie sans espaces, et on garde l'original pour l'affichage.
REM Toute lecture qui n'est ni vide ni "rien" passe la main a
REM Python, qui est tolerant (BOM, LF, CRLF) et fait autorite.
if not "!TEST!"=="" if /i not "!TEST!"=="rien" (
  echo.
  echo [bancs] Ordre lu : "!CMD!"
  "%PY%" banc_agent.py --executer
  echo.
)

timeout /t 3 >nul
goto boucle

@echo off
chcp 65001 >nul
cd /d "%~dp0"

REM === Remettre le pilotage a "marche" ===
REM   Sinon un "arret" laisse par une session precedente arreterait le
REM   serveur aussitot relance, sans que rien ne le dise.
> "_commande_serveur.txt" echo marche

REM === Remettre l'agent git a "rien" ===
REM   Meme raison : une commande laissee par une session precedente
REM   partirait toute seule au demarrage.
> "_commande_git.txt" echo rien

REM === Arreter toute ancienne session du serveur avant de relancer ===
set "PORT=8080"

REM   Le superviseur d'abord : s'il survivait, il relancerait le serveur
REM   qu'on vient de tuer, et deux serveurs se disputeraient le port.
echo Arret d'un eventuel superviseur precedent...
taskkill /F /FI "WINDOWTITLE eq MediaLibrary - Serveur*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq MediaLibrary - Git*" >nul 2>&1
echo Arret des anciennes sessions du serveur sur le port %PORT%...
for /f "tokens=5" %%P in ('netstat -ano -p TCP ^| findstr /C:":%PORT% " ^| findstr "LISTENING"') do (
    echo   Processus %%P arrete.
    taskkill /F /PID %%P >nul 2>&1
)

REM === Environnement Python isole - cree une seule fois ===
if not exist ".venv\Scripts\python.exe" (
    echo Creation de l'environnement Python isole - une seule fois...
    python -m venv .venv
)

echo Verification des dependances pillow, pillow-heif, piexif...
".venv\Scripts\python.exe" -m pip install --quiet --disable-pip-version-check pillow pillow-heif piexif

REM === Lancer le SUPERVISEUR dans une FENETRE SEPAREE ===
REM   Il tient la meme place qu'avant (une fenetre qui reste ouverte,
REM   fermee = tout s'arrete), mais il sait relancer le serveur quand
REM   _commande_serveur.txt dit "redemarrer". C'est ce qui permet de
REM   verifier une modification sans passer par le clavier de Mike.
echo Demarrage du serveur (sous superviseur) dans une nouvelle fenetre...
if not exist "superviseur.bat" (
    echo   superviseur.bat introuvable - demarrage direct, sans redemarrage
    echo   pilote par fichier.
    start "MediaLibrary - Serveur" ".venv\Scripts\python.exe" server.py
) else (
    start "MediaLibrary - Serveur" cmd /c "superviseur.bat"
)


REM === Lancer l'AGENT GIT dans une fenetre separee ===
REM   Il surveille _commande_git.txt et livre dans git APRES controle
REM   (serveur a jour, tests verts, bats ASCII, lint propre). Fermer sa
REM   fenetre ferme le canal sans rien casser d'autre : les gestes
REM   manuels de "27 - Git.bat" restent disponibles en toutes
REM   circonstances.
if not exist "superviseur_git.bat" (
    echo   superviseur_git.bat introuvable - pas d'agent git, les commits
    echo   restent manuels ^(27 - Git.bat^).
) else (
    echo Demarrage de l'agent git dans une nouvelle fenetre...
    start /min "MediaLibrary - Git" cmd /c "superviseur_git.bat"
)

echo.
echo Serveur lance sur le port %PORT%. Cette fenetre va se fermer.
timeout /t 3 >nul

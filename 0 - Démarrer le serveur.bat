@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"
set "PORT=8080"

REM ============================================================
REM   DEMARRAGE - serveur + agent git
REM
REM   ORDRE IMPORTANT (corrige le 19/08) : les preparatifs LENTS
REM   (venv, pip) passent AVANT de liberer le port. Avant, on
REM   tuait l'ancien serveur puis on faisait 40 secondes de pip :
REM   un orphelin qui finissait de se lever reprenait le port
REM   pendant ce temps, le nouveau serveur n'arrivait plus a se
REM   lier, et le superviseur le relancait cinq fois. Deux
REM   processus, aucun message clair.
REM
REM   Et on ne demarre JAMAIS si le port est encore tenu : mieux
REM   vaut ne rien lancer et le dire que lancer un deuxieme
REM   serveur qui se battra pour le port.
REM ============================================================

REM === Remettre les deux pilotages a leur etat neutre ===
REM   Sinon un "arret" ou un "livrer" laisse par une session
REM   precedente partirait tout seul au demarrage.
> "_commande_serveur.txt" echo marche
> "_commande_git.txt" echo rien

REM === GENERATION : ce demarrage prend la main ===
REM   Jeton neuf, ecrit AVANT tout le reste. Les superviseurs
REM   d'une session precedente le relisent a chaque tour ; le
REM   voyant change, ils se retirent d'eux-memes.
REM
REM   C'est ce qui remplace le taskkill par titre de fenetre : il
REM   ne retrouve PAS fiablement les fenetres console (constate le
REM   20/08 - deux fenetres "MediaLibrary - Serveur" survivantes).
REM   Un titre se devine, un fichier se lit.
> "_generation.txt" echo %RANDOM%%RANDOM%%RANDOM%

REM === Preparatifs LENTS d'abord - le port est encore tenu ===
if not exist ".venv\Scripts\python.exe" (
    echo Creation de l'environnement Python isole - une seule fois...
    python -m venv .venv
)
echo Verification des dependances pillow, pillow-heif, piexif...
".venv\Scripts\python.exe" -m pip install --quiet --disable-pip-version-check pillow pillow-heif piexif

REM === MAINTENANT seulement, liberer la place ===
REM   Le superviseur d'abord, avec /T : sans lui, son enfant
REM   python survit a la mort de la fenetre et garde le port.
echo.
echo Retrait des fenetres precedentes (par la generation)...
REM   Best effort en plus, jamais a la place : quand il marche,
REM   taskkill va plus vite que la boucle du superviseur.
taskkill /F /T /FI "WINDOWTITLE eq MediaLibrary - Serveur*" >nul 2>&1
taskkill /F /T /FI "WINDOWTITLE eq MediaLibrary - Git*" >nul 2>&1

echo Liberation du port %PORT%...
set /a ESSAIS=0
:attendre_port
set "OCCUPE="
for /f "tokens=5" %%P in ('netstat -ano -p TCP ^| findstr /C:":%PORT% " ^| findstr "LISTENING"') do set "OCCUPE=%%P"
if not defined OCCUPE goto :port_libre
set /a ESSAIS+=1
if !ESSAIS! GEQ 10 goto :port_bloque
echo   Processus !OCCUPE! tient encore le port - arret, tentative !ESSAIS!/10...
taskkill /F /T /PID !OCCUPE! >nul 2>&1
timeout /t 2 >nul
goto :attendre_port

:port_bloque
echo.
echo ============================================================
echo   LE PORT %PORT% EST ENCORE OCCUPE - RIEN N'A ETE LANCE
echo ============================================================
echo   Le processus !OCCUPE! refuse de mourir. Demarrer un second
echo   serveur maintenant en ferait deux qui se disputent le port,
echo   ce qui est exactement le probleme qu'on evite ici.
echo.
echo   A faire : ouvrir le gestionnaire des taches, terminer
echo   python.exe (PID !OCCUPE!), puis relancer ce script.
echo.
pause
exit /b 1

:port_libre
echo   Port %PORT% libre.

REM   Laisser aux anciens superviseurs le temps de faire UN tour de
REM   boucle : leur serveur vient d'etre tue, ils se reveillent, ils
REM   lisent la generation et se retirent. Sans cette pause, on
REM   lancerait le nouveau pendant que l'ancien croit encore a un
REM   plantage - et il en relancerait un second.
echo   Retrait des anciens superviseurs...
timeout /t 8 >nul
echo.

REM === Le SERVEUR, sous superviseur, dans sa fenetre ===
REM   Fenetre fermee = tout s'arrete, comme avant. Le superviseur
REM   sait relancer le serveur quand _commande_serveur.txt dit
REM   "redemarrer" : c'est ce qui permet de verifier une
REM   modification sans passer par le clavier de Mike.
echo Demarrage du serveur (sous superviseur)...
if not exist "superviseur.bat" (
    echo   superviseur.bat introuvable - demarrage direct, sans
    echo   redemarrage pilote par fichier.
    start "MediaLibrary - Serveur" ".venv\Scripts\python.exe" server.py
) else (
    start "MediaLibrary - Serveur" cmd /c "superviseur.bat"
)

REM === L'AGENT GIT, dans sa fenetre, VISIBLE ===
REM   Visible et non minimisee a dessein : une fenetre qu'on ne
REM   voit pas se ferme par megarde, et le canal disparait sans
REM   que personne ne le remarque (arrive le 19/08).
REM   Il surveille _commande_git.txt et livre APRES controle.
del /q "_agent_git_vu.txt" >nul 2>&1
if not exist "superviseur_git.bat" (
    echo   superviseur_git.bat introuvable - pas d'agent git, les
    echo   commits restent manuels ^(27 - Git.bat^).
) else (
    echo Demarrage de l'agent git...
    start "MediaLibrary - Git" cmd /c "superviseur_git.bat"
)

REM === Verifier que l'agent a bien pris la main ===
REM   Il touche _agent_git_vu.txt a chaque tour de boucle. Sans ce
REM   controle, une fenetre morte-nee etait indiscernable d'une
REM   fenetre en ecoute - c'etait le cas le 19/08.
if exist "superviseur_git.bat" (
    timeout /t 6 >nul
    if exist "_agent_git_vu.txt" (
        echo   Agent git : en ecoute.
    ) else (
        echo.
        echo   ATTENTION : l'agent git n'a pas donne signe de vie en 6 s.
        echo   Sa fenetre "MediaLibrary - Git" est-elle ouverte ? Sans lui
        echo   les commits restent manuels, le reste fonctionne.
        echo.
    )
)

echo.
echo Serveur lance sur le port %PORT%.
echo.
echo EXACTEMENT DEUX fenetres doivent rester : "MediaLibrary - Serveur"
echo et "MediaLibrary - Git". S'il y en a une troisieme, elle vient
echo d'une session precedente bloquee sur "pause" - elle ne sert plus
echo a rien et peut etre fermee a la main.
timeout /t 8 >nul

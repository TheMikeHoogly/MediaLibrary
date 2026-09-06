@echo off
chcp 65001 >nul
cd /d "%~dp0"
REM Contenu en ASCII pur : cmd.exe relit le fichier par decalage d'octets.
REM Pas de bloc entre parentheses : des goto.
echo ==============================================================
echo   PHOTOS PERDUES - rapatrier ce qui existe, ranger le reste
echo ==============================================================
echo.
echo   942 fichiers de 2 a 3 Mo sont remplis du texte
echo   "Read error in the sector !" - sequelle de la recuperation
echo   d'un disque tombe en panne. Ils ne redeviendront pas des
echo   photos. Le registre de ce qu'ils etaient est dans git :
echo   docs\photos_perdues.md - il survit a tout ce qui suit.
echo.
echo   ETAPE 1 : rapatrier les 4 photos de 2019 qui n'existent
echo   QUE dans le Takeout Google. A faire AVANT le reste : apres,
echo   la coquille n'est plus la pour dire ou remettre la photo.
echo.
echo   ETAPE 2 : les coquilles restantes partent en quarantaine
echo   sous .corbeille-rangement, arborescence gardee, avec un
echo   manifeste. RIEN N'EST SUPPRIME - le bat 24 purgera.
echo.
echo   Le serveur peut RESTER ALLUME : ce script ne touche pas a
echo   la base. Un fichier disparu sort de l'index tout seul au
echo   scan suivant, un fichier restaure est repris pour analyse.
echo.
echo   Annulation : appliquer_perdues.py --undo docs\undo_perdues_*.json --appliquer
echo --------------------------------------------------------------

set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

if not exist "docs\perdues_ailleurs.json" goto SANSRAPPORT
if not exist "docs\photos_perdues.json" goto SANSRAPPORT

echo.
echo   ETAPE 1 - apercu du rapatriement.
"%PY%" appliquer_perdues.py --restaurer
if errorlevel 1 goto ECHEC
echo.
choice /c ON /n /m "Rapatrier ces photos maintenant ? [O]ui / [N]on : "
if errorlevel 2 goto ETAPE2
"%PY%" appliquer_perdues.py --restaurer --appliquer
if errorlevel 1 goto ECHEC

:ETAPE2
echo.
echo   ETAPE 2 - apercu de la mise en quarantaine.
"%PY%" appliquer_perdues.py --corbeille
if errorlevel 1 goto ECHEC
echo.
choice /c ON /n /m "Faire un essai sur 20 fichiers d'abord ? [O]ui / [N]on : "
if errorlevel 2 goto TOUT
"%PY%" appliquer_perdues.py --corbeille --limite 20 --appliquer
if errorlevel 1 goto ECHEC
echo.
echo   Va regarder la quarantaine, puis reviens.
pause

:TOUT
echo.
choice /c ON /n /m "Mettre TOUTES les coquilles en quarantaine ? [O]ui / [N]on : "
if errorlevel 2 goto FIN
"%PY%" appliquer_perdues.py --corbeille --appliquer
if errorlevel 1 goto ECHEC
echo.
echo   Termine. L'index se nettoiera tout seul au prochain scan
echo   approfondi - au plus tard dans l'heure.
goto FIN

:SANSRAPPORT
echo.
echo   Rapports absents. Relance d'abord, par l'agent banc :
echo     verifier_images_illisibles.py --base copie.db
echo     inventaire_photos_perdues.py --base copie.db
echo     verifier_perdues_ailleurs.py --index copie.db --ou ...
echo   Rien n'a ete fait.
goto FIN

:ECHEC
echo.
echo   ECHEC - lire les messages ci-dessus. Rien d'autre n'a ete tente.

:FIN
pause

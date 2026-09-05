@echo off
chcp 65001 >nul
cd /d "%~dp0"
REM Contenu en ASCII pur : cmd.exe relit le fichier par decalage d'octets.
echo ==============================================================
echo   ENRICHIR LES LIEUX  -  geocodage inverse HORS LIGNE
echo ==============================================================
echo.
echo   Nomme les photos geolocalisees en les groupant par lieu, puis en
echo   geocodant chaque centre contre le gazetteer LOCAL cities1000.txt.
echo   Hors ligne, deterministe : aucune coordonnee ne sort d'ici.
echo.
echo   Deux sorties :
echo     - gps_places.json  : cle photo -^> libelle de lieu. Le serveur le
echo       relit tout seul quand le fichier change - pas de redemarrage.
echo     - lieux.txt        : ajouts marques et reversibles, avec un .bak,
echo       pour que la recherche par lieu connaisse ces noms.
echo.
echo   Le serveur peut RESTER ALLUME : la base est lue en LECTURE SEULE.
echo   Prealable, une seule fois : le bat 18 telecharge le gazetteer.
echo.
echo   A faire avant la campagne de re-tagging - un lieu connu entre dans
echo   les faits donnes au modele, et ne coute pas une seconde de GPU.
echo.
echo   Etape 1 : APERCU, rien n'est ecrit.
echo --------------------------------------------------------------

set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

if not exist "cities1000.txt" goto SANSGAZ

"%PY%" enrichir_lieux.py
if errorlevel 1 goto REFUS

echo.
choice /c ON /n /m "Ecrire ces lieux maintenant (gps_places.json + lieux.txt, avec .bak) ? [O]ui / [N]on : "
if errorlevel 2 goto FIN

"%PY%" enrichir_lieux.py --ecrire
if errorlevel 1 goto REFUS
echo.
echo   Termine. Le serveur reprendra gps_places.json de lui-meme.
echo   Pour annuler les ajouts de lieux.txt : remets lieux.txt.bak a sa place.
goto FIN

:SANSGAZ
echo.
echo   Gazetteer ABSENT : cities1000.txt n'est pas la.
echo   Lance d'abord "18 - Telecharger le gazetteer (geocodage).bat".
echo   Rien n'a ete fait.
goto FIN

:REFUS
echo.
echo   Le script a REFUSE ou a echoue : lis son message ci-dessus.
echo   Rien n'a ete ecrit.

:FIN
pause

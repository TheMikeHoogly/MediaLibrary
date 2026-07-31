@echo off
chcp 65001 >nul
cd /d "%~dp0"
REM Contenu en ASCII pur : cmd.exe relit le fichier par decalage d'octets.
echo ==============================================================
echo   RECENSEMENT DES DOUBLONS - Phase 0 (lecture seule)
echo ==============================================================
echo.
echo   Ce script parcourt le NAS et compte, SANS RIEN MODIFIER :
echo     - les doublons EXACTS (par contenu, pas par nom)
echo     - les octets recuperables
echo     - la repartition "_A TRIER" contre dossiers annee
echo     - les fichiers sans date fiable (candidats _SANS_DATE)
echo.
echo   Aucune ecriture ailleurs que deux rapports dans docs\ :
echo     docs\recensement.md   (synthese lisible)
echo     docs\recensement.json (detail par groupe de doublons)
echo.
echo   Il ne hashe que les fichiers de MEME taille : le gros du
echo   fonds n'est jamais lu en entier. Prevois tout de meme du
echo   temps, et lance-le de preference hors des heures d'usage.
echo.
pause

set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

echo.
echo   Analyse en cours (lecture seule)...
echo --------------------------------------------------------------
"%PY%" recensement_doublons.py
if errorlevel 1 (
    echo.
    echo   Le recensement a echoue. Rien n'a ete modifie.
    pause
    exit /b 1
)

echo.
echo   Termine. Ouvre docs\recensement.md pour la synthese, ou
echo   demande a Claude de la lire et de proposer la suite.
echo.
pause

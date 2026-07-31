@echo off
chcp 65001 >nul
cd /d "%~dp0"
REM Contenu en ASCII pur : cmd.exe relit le fichier par decalage d'octets.
echo ==============================================================
echo   VERIFICATION D'ESPECE DES DETECTIONS D'ANIMAUX
echo ==============================================================
echo.
echo   YOLO11 classe selon COCO, qui ne contient ni singe, ni renard,
echo   ni lama, ni peluche : tout mammifere poilu tombe dans "cat"
echo   ou "dog". D'ou les groupes de macaques presentes comme
echo   "9 apparitions de ce chat".
echo.
echo   SigLIP 2 relit les decoupes deja en cache dans animal_thumbs
echo   et marque celles qui ne sont pas ce que YOLO croyait. Elles
echo   sont alors ECARTEES du regroupement et du nommage.
echo.
echo   Aucun acces au NAS. Rien n'est supprime, l'espece d'origine
echo   est conservee, et aucun nom attribue n'est touche.
echo.
echo   Prerequis : "14 - Installer la recherche semantique.bat".
echo   Le serveur peut rester allume pour la simulation ; arrete-le
echo   avant d'appliquer.
echo.
pause

set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

echo.
echo   Etape 1 sur 2 : analyse (lecture seule) + echantillon
echo --------------------------------------------------------------
"%PY%" verifier_especes.py --exporter 24
if errorlevel 1 (
    echo.
    echo   Analyse impossible. Rien n'a ete modifie.
    pause
    exit /b 1
)

echo.
echo   Regarde le tableau "YOLO -^> SigLIP" ci-dessus : les lignes
echo   marquees d'un point d'exclamation sont les desaccords.
echo   Les decoupes suspectes ont ete copiees dans eval\especes\ :
echo   tu peux demander a Claude de verifier que les rejets sont
echo   justifies AVANT d'appliquer.
echo.
choice /c ON /n /m "   Appliquer maintenant ? [O]ui / [N]on : "
if errorlevel 2 goto :fin

echo.
echo   Etape 2 sur 2 : application
echo --------------------------------------------------------------
"%PY%" verifier_especes.py --appliquer
if errorlevel 1 (
    echo.
    echo   Echec. La base n'a pas ete modifiee.
    pause
    exit /b 1
)
echo.
echo   Relance le serveur, puis clique "Recalculer" sur la page
echo   Animaux : les groupes suspects auront disparu.

:fin
echo.
pause

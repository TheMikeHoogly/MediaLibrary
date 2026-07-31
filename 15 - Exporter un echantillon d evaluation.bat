@echo off
chcp 65001 >nul
cd /d "%~dp0"
REM Contenu en ASCII pur : cmd.exe relit le fichier par decalage d'octets.
echo ==============================================================
echo   ECHANTILLON D'EVALUATION DU TAGGING
echo ==============================================================
echo.
echo   Exporte 24 photos de ton corpus, reduites a 640 px, dans
echo   eval\echantillon\, avec les tags que SigLIP 2 leur attribue.
echo.
echo   BUT : Claude peut alors OUVRIR ces images, juger les tags
echo   lui-meme et ecrire la verite terrain. Le tagging devient
echo   mesurable au lieu d'etre juge a l'oeil.
echo.
echo   Le tirage est REPRODUCTIBLE : le meme corpus donne toujours
echo   le meme echantillon, donc deux modeles restent comparables.
echo.
echo   VIE PRIVEE : ce sont de vraies photos de famille. Elles sont
echo   copiees dans le dossier du projet pour etre examinees, sans
echo   leurs donnees EXIF. Supprime eval\echantillon\ ensuite.
echo.
pause

set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

echo.
echo   Export en cours...
echo --------------------------------------------------------------
"%PY%" semantic.py --exporter 24
if errorlevel 1 (
    echo.
    echo   Echec. Verifie que "14 - Installer la recherche semantique.bat"
    echo   est bien passe et que le NAS est accessible.
    pause
    exit /b 1
)

echo.
echo ==============================================================
echo   ETAPE SUIVANTE
echo ==============================================================
echo   Dis a Claude : "evalue l'echantillon".
echo   Il ouvrira eval\echantillon\*.jpg, comparera aux tags de
echo   eval\echantillon.json, et ecrira eval\verite.json.
echo.
echo   Puis, a chaque changement de modele, de seuil ou de gabarit :
echo     .venv\Scripts\python.exe semantic.py --evaluer
echo.
pause

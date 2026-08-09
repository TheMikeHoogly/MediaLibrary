@echo off
chcp 65001 >nul
cd /d "%~dp0"
REM Contenu en ASCII pur : cmd.exe relit le fichier par decalage d'octets.
echo ==============================================================
echo   GAZETTEER DE LIEUX - TELECHARGEMENT UNIQUE (GEOCODAGE)
echo ==============================================================
echo.
echo   Le geocodage inverse est OFFLINE : il ne s'appuie sur aucune
echo   API cloud (vie privee des GPS familiaux, autonomie du serveur).
echo   Il a besoin d'une base locale de lieux : GeoNames cities1000
echo   (toutes les localites de plus de 1000 habitants, ~150 000
echo   lignes, ~13 Mo une fois decompresse).
echo.
echo   Ce script telecharge cette base UNE SEULE FOIS dans le dossier
echo   du projet (cities1000.txt). Ensuite, enrichir_lieux.py tourne
echo   sans reseau.
echo.
echo   Source : https://download.geonames.org (donnees CC BY 4.0).
echo   Rien d'autre n'est modifie.
echo.
pause

set "URL=https://download.geonames.org/export/dump/cities1000.zip"
set "ZIP=%~dp0cities1000.zip"
set "TXT=%~dp0cities1000.txt"

if exist "%TXT%" (
    echo.
    echo   cities1000.txt existe deja. Rien a faire.
    echo   Supprime-le d'abord si tu veux le retelecharger.
    echo.
    pause
    exit /b 0
)

echo.
echo   Etape 1 sur 2 : telechargement
echo --------------------------------------------------------------
powershell -NoProfile -Command "try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%URL%' -OutFile '%ZIP%' -UseBasicParsing } catch { Write-Host $_.Exception.Message; exit 1 }"
if errorlevel 1 (
    echo.
    echo   Telechargement impossible. Verifie ta connexion.
    echo   Rien n'a ete installe.
    if exist "%ZIP%" del "%ZIP%"
    pause
    exit /b 1
)

echo.
echo   Etape 2 sur 2 : decompression
echo --------------------------------------------------------------
powershell -NoProfile -Command "try { Expand-Archive -Path '%ZIP%' -DestinationPath '%~dp0' -Force } catch { Write-Host $_.Exception.Message; exit 1 }"
if errorlevel 1 (
    echo.
    echo   Decompression impossible.
    if exist "%ZIP%" del "%ZIP%"
    pause
    exit /b 1
)

if exist "%ZIP%" del "%ZIP%"

if not exist "%TXT%" (
    echo.
    echo   Echec : cities1000.txt introuvable apres decompression.
    pause
    exit /b 1
)

echo.
echo ==============================================================
echo   OK - gazetteer pret : cities1000.txt
echo ==============================================================
echo.
echo   Prochaine etape (dans le .venv) :
echo     .venv\Scripts\python.exe enrichir_lieux.py
echo   (apercu ; ajoute --ecrire pour appliquer)
echo.
pause

@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ================================================
echo  1/2 : Installation de qwen3-vl:4b (3,3 Go)
echo  (peut prendre plusieurs minutes selon ta connexion)
echo ================================================
ollama pull qwen3-vl:4b
if errorlevel 1 (
    echo ERREUR : le telechargement a echoue. Rien n'a ete supprime.
    pause
    exit /b 1
)

echo.
echo ================================================
echo  2/2 : Suppression des modeles inutiles
echo ================================================
ollama rm qwen2.5:14b
ollama rm gemma4:e2b
ollama rm mistral:latest
ollama rm mistral:7b-instruct-q4_0

echo.
echo === RESULTAT === > ollama_report.txt
ollama list >> ollama_report.txt 2>&1
echo. >> ollama_report.txt
echo === TAILLE DOSSIER MODELES === >> ollama_report.txt
powershell -NoProfile -Command "$p=Join-Path $env:USERPROFILE '.ollama\models'; '{0:N1} Go' -f ((Get-ChildItem -Recurse -File $p | Measure-Object Length -Sum).Sum/1GB)" >> ollama_report.txt 2>&1

echo.
echo Termine ! Nouveau rapport dans ollama_report.txt
type ollama_report.txt
echo.
echo Retourne dire a Claude que c'est fait.
pause

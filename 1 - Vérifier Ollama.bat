@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Analyse en cours...

echo === OLLAMA LIST === > ollama_report.txt
ollama list >> ollama_report.txt 2>&1

echo. >> ollama_report.txt
echo === OLLAMA VERSION === >> ollama_report.txt
ollama --version >> ollama_report.txt 2>&1

echo. >> ollama_report.txt
echo === TAILLE DOSSIER MODELES === >> ollama_report.txt
powershell -NoProfile -Command "$p=Join-Path $env:USERPROFILE '.ollama\models'; if(Test-Path $p){'{0:N1} Go' -f ((Get-ChildItem -Recurse -File $p | Measure-Object Length -Sum).Sum/1GB)} else {'Dossier non trouve: ' + $p}" >> ollama_report.txt 2>&1

echo. >> ollama_report.txt
echo === ESPACE DISQUE === >> ollama_report.txt
powershell -NoProfile -Command "Get-PSDrive -PSProvider FileSystem | Format-Table Name, @{n='Libre(Go)';e={[math]::Round($_.Free/1GB,1)}}, @{n='Total(Go)';e={[math]::Round(($_.Used+$_.Free)/1GB,1)}}" >> ollama_report.txt 2>&1

echo. >> ollama_report.txt
echo === GPU === >> ollama_report.txt
nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv >> ollama_report.txt 2>&1

echo.
echo Termine ! Le rapport est dans ollama_report.txt
echo Retourne dire a Claude que c'est fait.
pause

@echo off
chcp 65001 >nul
cd /d "%~dp0"
REM Contenu en ASCII pur : cmd.exe relit le fichier par decalage d'octets.
echo ==============================================================
echo   REPARATION DE LA CONFIGURATION GPU
echo ==============================================================
echo.
echo   Constat : le torch installe est la build CPU, et un dossier
echo   orphelin "~orch" traine dans le venv (desinstallation pip
echo   interrompue). Resultat : YOLO, DINOv2 et InsightFace tournent
echo   tous sur CPU. Seul Ollama utilise la carte.
echo.
echo   IMPORTANT : arrete le serveur (Ctrl+C) ET ferme tout autre
echo   terminal Python. Sinon pip ne pourra pas remplacer torch,
echo   et c'est exactement ce qui a cree l'orphelin la premiere fois.
echo.
echo   Telechargement d'environ 2,5 Go. Il faut ~6 Go libres.
echo.
pause

set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

echo.
echo   Etape 1 sur 4 : diagnostic
echo --------------------------------------------------------------
"%PY%" reparer_gpu.py --diagnostic

echo.
choice /c ON /n /m "   Lancer la reparation ? [O]ui / [N]on : "
if errorlevel 2 goto :fin

echo.
echo   Etape 2 sur 4 : suppression des dossiers orphelins
echo --------------------------------------------------------------
"%PY%" reparer_gpu.py --nettoyer
if errorlevel 1 (
    echo.
    echo   Le nettoyage a echoue : un processus tient les fichiers.
    echo   Ferme tout, puis relance ce script. Rien n'a ete casse.
    pause
    exit /b 1
)

echo.
echo   Etape 3 sur 4 : installation de torch CUDA 13
echo --------------------------------------------------------------
"%PY%" reparer_gpu.py --installer
if errorlevel 1 (
    echo.
    echo   Installation impossible. Ton environnement reste utilisable
    echo   en CPU, rien n'est perdu.
    pause
    exit /b 1
)

echo.
echo   Etape 4 sur 4 : verification
echo --------------------------------------------------------------
"%PY%" reparer_gpu.py --verifier
if errorlevel 1 (
    echo.
    echo   Pour revenir a l'etat d'origine :
    echo     .venv\Scripts\python.exe reparer_gpu.py --restaurer-cpu
    pause
    exit /b 1
)

:fin
echo.
pause

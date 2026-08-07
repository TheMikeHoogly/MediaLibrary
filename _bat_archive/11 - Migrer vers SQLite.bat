@echo off
chcp 65001 >nul
cd /d "%~dp0"
REM Contenu volontairement en ASCII pur : cmd.exe relit le fichier par
REM decalage d'octets, et l'UTF-8 multi-octets desaligne son parseur.
echo ==============================================================
echo   MIGRATION DES INDEX VERS SQLite
echo ==============================================================
echo.
echo   IMPORTANT : arrete le serveur (Ctrl+C) avant de continuer.
echo.
echo   Ce script NE TOUCHE PAS aux fichiers .json du NAS.
echo   Ils restent en place ; supprimer photos.db suffit a revenir
echo   a l'etat d'origine.
echo.

set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

echo   Etape 1 sur 3 : verification du code sur donnees de test
echo --------------------------------------------------------------
"%PY%" test_store_sqlite.py
if errorlevel 1 (
    echo.
    echo   ECHEC des tests. Migration annulee, rien n'a ete modifie.
    pause
    exit /b 1
)

echo.
echo   Etape 2 sur 3 : simulation sur tes vrais index (lecture seule)
echo --------------------------------------------------------------
"%PY%" migrate_to_sqlite.py
if errorlevel 1 (
    echo.
    echo   Des index sont illisibles. Migration annulee.
    pause
    exit /b 1
)

echo.
echo   Etape 3 sur 3 : appliquer la migration
echo --------------------------------------------------------------
echo.
choice /c ON /n /m "   Appliquer maintenant ? [O]ui / [N]on : "
if errorlevel 2 goto :fin
echo.
"%PY%" migrate_to_sqlite.py --appliquer
if errorlevel 1 (
    echo.
    echo   La verification a echoue. Supprime photos.db pour revenir
    echo   a l'etat d'origine. Les .json n'ont pas ete touches.
    pause
    exit /b 1
)
echo.
echo   Relance le serveur : il utilisera photos.db automatiquement.

:fin
echo.
pause

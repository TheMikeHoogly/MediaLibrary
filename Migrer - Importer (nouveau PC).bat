@echo off
chcp 65001 >nul
cd /d "%~dp0"
REM Contenu en ASCII pur : cmd.exe relit le fichier par decalage d'octets.
echo ==============================================================
echo   MIGRATION - IMPORT de l'etat (a lancer sur le NOUVEAU PC)
echo ==============================================================
echo.
echo   Restaure la base d'index et la config depuis l'archive creee
echo   sur l'ancien PC. A faire APRES l'installation (1 - Installer).
echo.
set /p ARCHIVE=Chemin complet de l'archive migration_XXXX.zip :

if not exist "%ARCHIVE%" (
    echo   Fichier introuvable : %ARCHIVE%
    pause
    exit /b 1
)

python migrer.py importer "%ARCHIVE%"

echo.
echo   Verifie l'install : python installer.py --check
echo   Puis lance le raccourci "0 - Demarrer le serveur" (bat).
echo.
pause

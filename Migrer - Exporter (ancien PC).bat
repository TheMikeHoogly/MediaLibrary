@echo off
chcp 65001 >nul
cd /d "%~dp0"
REM Contenu en ASCII pur : cmd.exe relit le fichier par decalage d'octets.
echo ==============================================================
echo   MIGRATION - EXPORT de l'etat (a lancer sur l'ANCIEN PC)
echo ==============================================================
echo.
echo   Cree une archive avec la base d'index (photos.db) et la config
echo   locale. Le CODE n'est PAS inclus : il se recupere par git clone.
echo.
echo   IMPORTANT : arrete le serveur avant, pour une base coherente.
echo.
pause

python migrer.py exporter

echo.
echo   Copie l'archive (dossier "migration\") sur le nouveau PC, puis
echo   lance la-bas "Migrer - Importer (nouveau PC).bat".
echo.
pause

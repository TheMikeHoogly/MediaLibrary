@echo off
chcp 65001 >nul
cd /d "%~dp0"
REM Contenu en ASCII pur : cmd.exe relit le fichier par decalage d'octets.
echo ==============================================================
echo   REMETTRE LES MOTS-CLES ANGLAIS DANS kw_en  (index seul)
echo ==============================================================
echo.
echo   22196 photos (52 %%) ont un kw_en VIDE et un kw_fr qui porte les
echo   deux langues a la suite : la liste ecrite dans le XMP, relue telle
echo   quelle quand l'index a ete reconstruit. Les puces montrent de
echo   l'anglais ("chair", "sky") qui n'est pas une faute du tagueur.
echo.
echo   Ce script scinde chaque liste en son bloc francais et son bloc
echo   anglais (regle scission_fr_en.py, mesuree : 22190 sur 22196),
echo   dans l'INDEX seulement - le fichier XMP ne change pas.
echo   Reversible : appliquer_scission_fr_en.py --undo docs\undo_scission_*.json --appliquer
echo.
echo   SERVEUR ARRETE, meme pour l'apercu (il ouvre photos.db) - le
echo   script le verifie. Fenetre "MediaLibrary - Serveur", ou "arret"
echo   dans _commande_serveur.txt.
echo.
echo   Etape 1 : APERCU, rien n'est ecrit.
echo --------------------------------------------------------------

set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

"%PY%" appliquer_scission_fr_en.py --exemples 8
if errorlevel 1 goto REFUS

echo.
choice /c ON /n /m "Scinder ces entrees maintenant (index seul, reversible) ? [O]ui / [N]on : "
if errorlevel 2 goto FIN

"%PY%" appliquer_scission_fr_en.py --appliquer
if errorlevel 1 goto REFUS
echo.
echo   Termine. Redemarre le serveur ("marche" dans _commande_serveur.txt).
goto FIN

:REFUS
echo.
echo   Le script a REFUSE ou a echoue : lis son message ci-dessus.
echo   Le cas courant : le serveur tourne encore. Rien n'a ete ecrit.

:FIN
pause

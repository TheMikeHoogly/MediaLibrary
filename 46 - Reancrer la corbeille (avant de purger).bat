@echo off
chcp 65001 >nul
cd /d "%~dp0"
REM Contenu en ASCII pur : cmd.exe relit le fichier par decalage d octets.
echo ==============================================================
echo   REANCRER LA CORBEILLE - retrouver les copies gardees
echo ==============================================================
echo.
echo   La corbeille de rangement refuse de se purger : elle a note
echo   ou vivait chaque copie GARDEE, et le rangement par annee les
echo   a deplacees depuis. Sans copie gardee vivante, purger le
echo   doublon detruirait la derniere trace de la photo.
echo.
echo   Cet outil recherche chaque copie gardee par son EMPREINTE
echo   (sha256), jamais par son nom : au 06/09, 3 canoniques sur 40
echo   retrouvees par le nom etaient une AUTRE photo.
echo.
echo   Il ne supprime rien. Il corrige les manifestes, et tout se
echo   defait (journal d annulation dans docs\).
echo.
echo   Compte environ 40 minutes : chaque photo est relue sur le NAS.
echo --------------------------------------------------------------
echo   Etape 1 : APERCU, rien n est ecrit.
echo.

set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

"%PY%" reancrer_corbeille.py
if errorlevel 1 (
    echo.
    echo   Echec de l apercu. Rien n a ete ecrit.
    pause
    exit /b 1
)

echo.
echo   Etape 2 : pour ECRIRE les manifestes listes ci-dessus,
echo   reponds O. Sinon reponds N (rien ne sera modifie).
echo.
choice /c ON /n /m "Reancrer maintenant ? [O]ui / [N]on : "
if errorlevel 2 (
    echo   Annule. Rien n a ete modifie.
    pause
    exit /b 0
)

"%PY%" reancrer_corbeille.py --appliquer
echo.
echo   Termine. Lance ensuite le bat 24 pour purger ce qui a
echo   retrouve sa copie gardee.
pause

@echo off
chcp 65001 >nul
cd /d "%~dp0"
REM Contenu en ASCII pur : cmd.exe relit le fichier par decalage d'octets.
echo ==============================================================
echo   NETTOYAGE DE FIN DE SESSION
echo ==============================================================
echo.
echo   Deux volets, tous deux surs :
echo     1. Met en QUARANTAINE REVERSIBLE les dossiers/fichiers de
echo        travail ephemeres a la racine (dossiers --..., __pycache__,
echo        .fuse_hidden..., .pyc, dossiers vides connus). Rien n'est
echo        supprime : tout part dans _corbeille_session\AAAA-MM-JJ\
echo        avec un manifest.json. Tu vides la corbeille quand tu veux.
echo     2. Controle la coherence des fichiers de suivi *.md
echo        (references orphelines, bloat, dates perimees).
echo.
echo   Preserve : _bat_archive, recuperees, *_thumbs, docs, ui, eval,
echo   uploads, .git, .venv et tous les fichiers source/donnees.
echo.
echo   Etape 1 : APERCU (dry-run), rien n'est deplace.
echo --------------------------------------------------------------

set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

"%PY%" nettoyer_session.py
if errorlevel 1 (
    echo.
    echo   Echec de l'apercu. Rien n'a ete deplace.
    pause
    exit /b 1
)

echo.
echo   Etape 2 : pour DEPLACER en quarantaine ce qui est liste
echo   ci-dessus, reponds O. Sinon reponds N (rien ne bouge).
echo   Rappel : le deplacement est reversible (voir manifest.json).
echo.
choice /c ON /n /m "Nettoyer maintenant ? [O]ui / [N]on : "
if errorlevel 2 (
    echo   Annule. Rien n'a ete deplace.
    pause
    exit /b 0
)

"%PY%" nettoyer_session.py --appliquer
echo.
echo   Termine. Le lint *.md ci-dessus est informatif : corrige les
echo   docs a la main si besoin.
pause

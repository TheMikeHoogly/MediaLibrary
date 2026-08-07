@echo off
chcp 65001 >nul
cd /d "%~dp0"
REM Contenu en ASCII pur : cmd.exe relit le fichier par decalage d'octets,
REM et l'UTF-8 multi-octets desaligne son parseur.
echo ==============================================================
echo   SORTIE DES EMBEDDINGS VERS LA TABLE BLOB
echo ==============================================================
echo.
echo   IMPORTANT : arrete le serveur (Ctrl+C) avant de continuer.
echo.
echo   Les vecteurs quittent le JSON pour une table BLOB dediee.
echo   Les octets float16 sont conserves a l'identique : les
echo   regroupements et les seuils donnent les memes resultats.
echo.
echo   Prerequis : "11 - Migrer vers SQLite.bat" deja passe.
echo.

set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

echo   Etape 1 sur 3 : verification du magasin de vecteurs
echo --------------------------------------------------------------
"%PY%" test_vectors.py
if errorlevel 1 (
    echo.
    echo   ECHEC des tests. Rien n'a ete modifie.
    pause
    exit /b 1
)

echo.
echo   Etape 2 sur 3 : simulation sur ta base (lecture seule)
echo --------------------------------------------------------------
"%PY%" migrate_embeddings.py
if errorlevel 1 (
    echo.
    echo   Conditions non reunies. Rien n'a ete modifie.
    pause
    exit /b 1
)

echo.
echo   Etape 3 sur 3 : appliquer
echo --------------------------------------------------------------
echo.
choice /c ON /n /m "   Appliquer maintenant ? [O]ui / [N]on : "
if errorlevel 2 goto :fin
echo.
"%PY%" migrate_embeddings.py --appliquer
if errorlevel 1 (
    echo.
    echo   La verification a echoue. Restaure photos.db.bak depuis le
    echo   NAS, ou relance "11 - Migrer vers SQLite.bat" : les
    echo   fichiers .json d'origine sont toujours intacts.
    pause
    exit /b 1
)
echo.
echo   Relance le serveur.

:fin
echo.
pause

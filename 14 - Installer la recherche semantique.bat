@echo off
chcp 65001 >nul
cd /d "%~dp0"
REM Contenu en ASCII pur : cmd.exe relit le fichier par decalage d'octets.
echo ==============================================================
echo   RECHERCHE SEMANTIQUE - INSTALLATION ET BANC D'ESSAI
echo ==============================================================
echo.
echo   Installe SigLIP 2 (encodeur image + texte multilingue), puis
echo   MESURE sur 20 photos de ton corpus avant de toucher au reste.
echo.
echo   Ce script ne modifie NI server.py NI ta base : il ne fait
echo   qu'installer une bibliotheque et mesurer. Si le modele ne
echo   tient pas dans les 4 Go, tu le sais en deux minutes.
echo.
echo   Telechargement : quelques Mo de bibliotheques + 1,5 Go de
echo   modele (mis en cache, telecharge une seule fois).
echo   Le serveur peut rester allume : le banc lit la base en lecture.
echo.
pause

set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

echo.
echo   Etape 1 sur 4 : etat avant installation
echo --------------------------------------------------------------
"%PY%" semantic.py --diagnostic

echo.
echo   Etape 2 sur 4 : installation d'open_clip_torch
echo --------------------------------------------------------------
echo   (torch n'est PAS reinstalle : --no-deps evite que pip
echo    remplace ta build CUDA par une build CPU)
"%PY%" -m pip install --disable-pip-version-check open_clip_torch --no-deps
if errorlevel 1 goto :echec
REM transformers porte la tour TEXTE de SigLIP 2 : sans lui, le modele se
REM telecharge mais refuse de se charger. Il ne depend pas de torch.
"%PY%" -m pip install --disable-pip-version-check ftfy regex timm huggingface_hub transformers
if errorlevel 1 goto :echec

echo.
echo   Controle : pip n'a-t-il pas remplace torch CUDA par une build CPU ?
"%PY%" -c "import torch,sys; ok = torch.version.cuda is not None; print('  torch', torch.__version__, '->', 'CUDA intact' if ok else 'BUILD CPU - REGRESSION'); sys.exit(0 if ok else 1)"
if errorlevel 1 (
    echo.
    echo   pip a remplace ta build CUDA. Repare avec "13 - Reparer le GPU.bat".
    pause
    exit /b 1
)

echo.
echo   Etape 3 sur 4 : etat apres installation
echo --------------------------------------------------------------
"%PY%" semantic.py --diagnostic

echo.
echo   Etape 4 sur 4 : banc d'essai sur 20 photos reelles
echo --------------------------------------------------------------
echo   Premier lancement : le modele se telecharge (~400 Mo).
echo.
"%PY%" semantic.py --banc 20
if errorlevel 1 goto :echec

echo.
echo ==============================================================
echo   LIRE LE RESULTAT
echo ==============================================================
echo   - "ms par image" et l'extrapolation en minutes donnent le
echo     cout reel de l'indexation de tes 30 682 photos.
echo   - "VRAM libre pendant l'encodage" doit rester positif :
echo     sinon le modele est trop gros pour cohabiter avec Ollama.
echo   - Le controle de coherence doit associer des tags plausibles
echo     aux photos. Si les tags sont absurdes, le modele ou le
echo     gabarit de prompt est mauvais - on le corrige avant d'aller
echo     plus loin.
echo.
echo   Ensuite, au choix :
echo     .venv\Scripts\python.exe semantic.py --indexer 500
echo     .venv\Scripts\python.exe semantic.py --chercher "chat sur le canape"
echo.
goto :fin

:echec
echo.
echo   ECHEC. Rien n'a ete modifie dans le projet.
echo   Pour retirer la bibliotheque :
echo     .venv\Scripts\python.exe -m pip uninstall open_clip_torch
echo.

:fin
pause

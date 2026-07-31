@echo off
chcp 65001 >nul
cd /d "%~dp0"
REM Contenu en ASCII pur : cmd.exe relit le fichier par decalage d'octets.
echo ==============================================================
echo   RE-IDENTIFICATION ANIMALE : DINOv2 CONTRE MegaDescriptor
echo ==============================================================
echo.
echo   Le pipeline distingue Caline, Inti et Luna avec un encodeur
echo   GENERALISTE (DINOv2). MegaDescriptor est entraine pour la
echo   re-identification d'individus animaux. L'audit initial le
echo   recommandait ; il n'avait jamais ete mesure.
echo.
echo   Ce script MESURE, il ne migre rien. Il ne touche ni a la
echo   base, ni a server.py, ni a tes noms attribues.
echo.
echo   Tout tourne sur les decoupes deja en cache dans
echo   animal_thumbs : aucun acces au NAS.
echo.
echo   Premier lancement : environ 120 Mo de modele a telecharger.
echo.
pause

set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

echo.
echo   Etape 1 sur 2 : mesure de reference (DINOv2, rien a telecharger)
echo --------------------------------------------------------------
"%PY%" eval_animaux.py
if errorlevel 1 (
    echo.
    echo   Mesure impossible. Rien n'a ete modifie.
    pause
    exit /b 1
)

echo.
echo   Etape 2 sur 2 : comparaison avec MegaDescriptor
echo --------------------------------------------------------------
"%PY%" eval_animaux.py --modeles T-224,L-224

echo.
echo ==============================================================
echo   COMMENT LIRE LE RESULTAT
echo ==============================================================
echo   rang-1  la plus proche voisine est-elle le bon animal ?
echo   mAP     qualite du classement complet
echo.
echo   Regarde SURTOUT les confusions : une moyenne peut progresser
echo   sans rien regler si l'erreur porte toujours sur la meme
echo   paire d'animaux.
echo.
echo   Si MegaDescriptor gagne nettement, montre la sortie a Claude :
echo   la migration passe par un bump de ANIMAL_PIPELINE_VERSION,
echo   qui recalcule les empreintes en PRESERVANT tes noms.
echo.
pause

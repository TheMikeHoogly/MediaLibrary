@echo off
chcp 65001 >nul
cd /d "%~dp0"
REM Contenu en ASCII pur : cmd.exe relit le fichier par decalage d'octets.
echo ==============================================================
echo   COMPARAISON EQUITABLE DES ENCODEURS D'ANIMAUX
echo ==============================================================
echo.
echo   Le premier banc etait BIAISE, et il faut le refaire :
echo.
echo     - DINOv2 utilisait ses empreintes de production, calculees
echo       sur la decoupe PLEINE RESOLUTION, sans marge.
echo     - MegaDescriptor recevait les vignettes d'affichage de
echo       256 px, avec 15 pour cent de marge en plus.
echo.
echo   Le verdict "MegaDescriptor perd" reposait donc en partie
echo   sur un handicap impose. Ce script refabrique des decoupes
echo   IDENTIQUES pour tous les modeles.
echo.
echo   Le NAS doit etre accessible : environ 530 photos relues,
echo   puis mises en cache dans eval\crops_res. Le script affiche
echo   sa progression tous les 100 fichiers.
echo.
echo   Ce script MESURE, il ne migre rien.
echo.
pause

set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

echo.
echo   Etape 1 sur 2 : pleine resolution, tous les modeles
echo --------------------------------------------------------------
echo   C'est la comparaison de reference : ce que recoit vraiment
echo   le pipeline aujourd'hui.
echo.
"%PY%" eval_animaux.py --equitable --modeles T-224,L-224
if errorlevel 1 (
    echo.
    echo   Mesure impossible. Rien n'a ete modifie.
    pause
    exit /b 1
)

echo.
echo   Etape 2 sur 2 : la resolution change-t-elle quelque chose ?
echo --------------------------------------------------------------
"%PY%" eval_animaux.py --resolutions 256,512

echo.
echo ==============================================================
echo   COMMENT LIRE LE RESULTAT
echo ==============================================================
echo   Etape 1 dit quel modele est vraiment le meilleur, a armes
echo   egales. Si MegaDescriptor rattrape son retard, ma conclusion
echo   precedente etait fausse.
echo.
echo   Etape 2 dit si la resolution compte. Regarde surtout les
echo   confusions Inti / Luna : c'est la seule paire qui pose
echo   vraiment probleme.
echo.
echo   Resultats ecrits dans eval\animaux.json
echo.
pause

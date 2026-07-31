@echo off
chcp 65001 >nul
cd /d "%~dp0"
REM Contenu en ASCII pur : cmd.exe relit le fichier par decalage d'octets.
echo ==============================================================
echo   IMAGES ILLISIBLES - INVENTAIRE ET RECUPERATION
echo ==============================================================
echo.
echo   987 photos sur 30 682 sont illisibles : ni taguees, ni
echo   analysees pour les visages ou les animaux. Invisibles a
echo   tout le systeme.
echo.
echo   Ce script lit les PREMIERS OCTETS de chaque fichier pour
echo   savoir ce qu'il contient vraiment - l'extension ment souvent
echo   apres une recuperation de disque. Il distingue :
echo.
echo     - 0 octet              perdu, rien a tenter
echo     - JPEG tronque         recuperable en grande partie
echo     - format brut (RAW)    PAS abime : decodeur manquant
echo     - en-tete detruit      les donnees survivent peut-etre plus
echo                            loin : on cherche un flux JPEG dans
echo                            tout le fichier
echo     - octets aleatoires    ce que la recuperation a rendu
echo.
echo   Relancer ce script est SANS RISQUE : il ne relit que les
echo   originaux, qui ne sont jamais modifies.
echo.
echo   GARANTIE : tes fichiers d'origine ne sont JAMAIS modifies.
echo   Les images reconstruites vont dans le dossier "recuperees".
echo.
echo   Le NAS doit etre accessible. Le serveur peut rester allume.
echo.
pause

set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

echo.
echo   Etape 1 sur 2 : inventaire (lecture seule)
echo --------------------------------------------------------------
"%PY%" inventaire_illisibles.py --exporter 12
if errorlevel 1 (
    echo.
    echo   Inventaire impossible. Rien n'a ete modifie.
    pause
    exit /b 1
)

echo.
echo   Le tableau ci-dessus dit combien de fichiers sont
echo   recuperables et pourquoi. Montre-le a Claude si tu veux
echo   son avis avant d'aller plus loin.
echo.
choice /c ON /n /m "   Tenter la recuperation maintenant ? [O]ui / [N]on : "
if errorlevel 2 goto :fin

echo.
echo   Etape 2 sur 2 : recuperation
echo --------------------------------------------------------------
echo   Cela peut prendre du temps : chaque fichier est relu depuis
echo   le NAS.
echo.
"%PY%" inventaire_illisibles.py --reparer
echo.
echo   Regarde le dossier "recuperees" avant d'en faire quoi que
echo   ce soit : une image reconstruite peut etre partielle, avec
echo   le bas gris ou raye. Tes originaux sont intacts.

:fin
echo.
pause

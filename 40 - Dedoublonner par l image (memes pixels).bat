@echo off
chcp 65001 >nul
cd /d "%~dp0"
REM Contenu en ASCII pur : cmd.exe relit le fichier par decalage d'octets.
REM Pas de bloc entre parentheses : des goto.
echo ==============================================================
echo   DEDOUBLONNER PAR L'IMAGE - memes pixels, XMP diverge
echo ==============================================================
echo.
echo   Lit docs\doublons_image.json, ecrit par mesure_doublons_image.py
echo   dans la nuit du 29 au 30/08 : 2757 groupes IDENTIQUES au pixel,
echo   2929 retraits, 10,45 Go. La copie de "Photos Mike" reste, sinon
echo   la copie rangee par annee. Les noms humains qu'une copie retiree
echo   porte et que la canonique n'a pas sont recopies AVANT le retrait,
echo   dans le XMP et dans l'index. Une canonique sans texte IA herite
echo   de celui de la copie.
echo.
echo   Le retrait va dans N:\Photos\.corbeille-rangement\dedup_image_*,
echo   avec un manifeste que le bat 24 reconnait apres 30 jours.
echo   Reversible : appliquer_doublons_image.py --undo docs\undo_doublons_*.json --appliquer
echo.
echo   SERVEUR ARRETE pour l'etape 2 - le script le verifie, il ecrit
echo   dans photos.db. Fenetre "MediaLibrary - Serveur", ou "arret" dans
echo   _commande_serveur.txt.
echo.
echo   Etape 1 : APERCU, rien n'est deplace.
echo --------------------------------------------------------------

set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

"%PY%" verifier_doublons_image.py --entre-proprietaires
if errorlevel 1 goto ECHEC

echo.
echo   Lot 1 = les groupes ENTRE proprietaires (Flo + Mike), tranche le 30/08.
choice /c ON /n /m "Retirer ces copies maintenant, serveur ARRETE ? [O]ui / [N]on : "
if errorlevel 2 goto FIN

"%PY%" appliquer_doublons_image.py --appliquer --entre-proprietaires
if errorlevel 1 goto REFUS
echo.
echo   Termine. Redemarre le serveur : l'index compte 1 entree de moins par
echo   copie retiree, les fiches gardent leurs decisions.
echo.
choice /c ON /n /m "Passer aussi le reste (chez un meme proprietaire) ? [O]ui / [N]on : "
if errorlevel 2 goto FIN
"%PY%" verifier_doublons_image.py
if errorlevel 1 goto ECHEC
choice /c ON /n /m "Retirer ces copies maintenant ? [O]ui / [N]on : "
if errorlevel 2 goto FIN
"%PY%" appliquer_doublons_image.py --appliquer
if errorlevel 1 goto REFUS
echo.
echo   Termine. Pour annuler la derniere fournee :
echo   "%PY%" appliquer_doublons_image.py --undo docs\undo_doublons_XXXX.json --appliquer
goto FIN

:REFUS
echo.
echo   Le script a REFUSE ou a echoue : lis son message ci-dessus.
echo   Le cas courant : le serveur tourne encore. Rien n'a ete perdu.
goto FIN

:ECHEC
echo.
echo   Echec de l'apercu. Rien n'a ete deplace.

:FIN
pause

@echo off
chcp 65001 >nul
cd /d "%~dp0"
REM Contenu en ASCII pur : cmd.exe relit le fichier par decalage d'octets.
REM Pas de bloc parenthese : uniquement des goto.
echo ==============================================================
echo   RAPATRIER CE QUE GOOGLE PORTE MIEUX QUE LE NAS
echo ==============================================================
echo.
echo   La verification ne compte plus AUCUNE absente : le NAS porte
echo   tout ce que Google detient, par le NOM. Mais elle compte
echo   autre chose, et c'est le sujet de ce script.
echo.
echo   Quand le NAS est plus GROS de quelques kilo-octets, c'est un
echo   bloc XMP : nos propres tags. C'est benin, et c'est le cas le
echo   plus frequent de loin.
echo.
echo   Quand le NAS est plus PETIT, c'est autre chose. Google porte
echo   alors une version que nous n'avons pas -- une video embarquee
echo   que nous avons jetee, ou une photo que le NAS ne detient
echo   qu'en version reduite.
echo.
echo   COMBIEN, c'est l'etape a blanc qui le dit. Ce texte ne recite
echo   aucun chiffre : il en annoncait du 28/08 qui n'etaient plus
echo   vrais onze jours plus tard.
echo.
echo   Effacer chez Google en croyant que le NAS a la photo perdrait
echo   la BONNE version. Ce script rapatrie ces fichiers-la, sous
echo   "_A TRIER\Google porte mieux\<annee>" -- un dossier a part,
echo   pour qu'on sache qu'ils attendent un arbitrage et qu'ils ne
echo   se melangent pas au reste.
echo.
echo   Rien n'est ecrase : la version du NAS reste ou elle est. Tu
echo   auras donc les deux, et c'est voulu -- c'est toi qui tranches.
echo.
echo   Le seuil se choisit au lancement.
echo.
echo   Journal d'annulation dans _corbeille_copies.
echo.
echo   Etape 1 : A BLANC. Rien n'est ecrit.
echo   Etape 2 : copie, seulement si tu reponds O.
echo.

set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

REM LE RAPPORT LE PLUS FRAIS, jamais un fige. Ce bat lisait
REM `_rapport_google_apres2.json`, la mesure du 28/08 : onze jours plus
REM tard le fonds avait change (dedoublonnage, strip Motion Photo,
REM coquilles en quarantaine) et le verdict avec lui. `_google.json` est
REM ce qu'ecrit la DERNIERE execution de verifier_photos_google.py --
REM celle que le bat 49 exige de toute facon avant d'effacer.
REM
REM PLUS DE LISTE FILTREE A LA MAIN. Le 09/09 le rapport brut proposait
REM 1913 fichiers, dont 1814 etaient des Motion Photos strippees par le
REM bat 42 : le NAS y est plus petit parce que NOUS lui avons retire la
REM video, pas parce que Google porte une meilleure image. Les copier
REM aurait DEFAIT le strip. Ce tri vivait dans un JSON filtre a la main,
REM qui serait retombe au prochain Takeout ; il vit maintenant dans
REM copier_absentes.py, qui lit docs\strip_motionphoto_manifeste.json.
REM Verifie le 09/09 : le filtre du code rend exactement les memes 99
REM gardes et 1814 ecartes que le tri manuel, sans un seul desaccord.
set "RAPPORT=_google.json"
if not exist "%RAPPORT%" goto :sansrapport

echo   Quel seuil ?
echo     [1] 100 Ko - seulement les gros ecarts (videos tronquees,
echo         photos reduites). C'est ce qui a servi la 1re fois.
echo     [2] tout ecart - ferme completement la question : plus AUCUN
echo         fichier ou Google porte plus que le NAS.
echo.
choice /c 12 /n /m "Seuil : [1] 100 Ko / [2] tout ecart : "
if errorlevel 2 goto :seuiltout
set "SEUIL=100000"
goto :seuilpret
:seuiltout
set "SEUIL=1"
:seuilpret
echo.
echo   Seuil retenu : %SEUIL% octets.
echo.
pause

echo.
echo   Etape 1 sur 2 : A BLANC
echo --------------------------------------------------------------
"%PY%" copier_absentes.py --rapport "%RAPPORT%" --verdict PROBABLE --nas-plus-petit-de %SEUIL% --etiquette "Google porte mieux" --json _copie_google_mieux.json
if errorlevel 1 goto :rouge

echo.
echo   Etape 2 sur 2 : COPIE
echo --------------------------------------------------------------
echo.
choice /c ON /n /m "Copier maintenant ? [O]ui / [N]on : "
if errorlevel 2 goto :annule

"%PY%" copier_absentes.py --rapport "%RAPPORT%" --verdict PROBABLE --nas-plus-petit-de %SEUIL% --etiquette "Google porte mieux" --copier --json _copie_google_mieux.json
if errorlevel 1 goto :echec
goto :fin

:sansrapport
echo.
echo   %RAPPORT% est introuvable. Il vient de la verification :
echo.
echo     "%PY%" verifier_photos_google.py --takeout "C:\GOOGLE PHOTOS\extrait" --json _rapport_google_apres.json
echo.
pause
exit /b 2

:rouge
echo.
echo   VERDICT ROUGE - rien n'a ete ecrit.
echo   Lis le rapport ci-dessus : place insuffisante, cible hors
echo   "_A TRIER", ou rien a rapatrier.
echo.
pause
exit /b 1

:annule
echo.
echo   Annule. Rien n'a ete ecrit.
echo.
pause
exit /b 0

:echec
echo.
echo   La copie s'est interrompue, ou une copie n'a pas ete relue a
echo   la bonne taille. Ce qui est ecrit reste bon : relance ce
echo   script, il reprend ou il en est.
echo.
pause
exit /b 1

:fin
echo.
echo ==============================================================
echo   TERMINE
echo ==============================================================
echo.
echo   Ensuite :
echo     1. "26 - Ranger par annee.bat"
echo     2. relancer la verification Google
echo     3. quand elle ne compte plus de NAS-plus-petit, l'effacement
echo        GLOBAL chez Google devient sur.
echo.
pause
exit /b 0

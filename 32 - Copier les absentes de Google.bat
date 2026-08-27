@echo off
chcp 65001 >nul
cd /d "%~dp0"
REM Contenu en ASCII pur : cmd.exe relit le fichier par decalage d'octets.
REM Pas de bloc parenthese : uniquement des goto.
echo ==============================================================
echo   RAPATRIER CE QUI N'EXISTE QUE CHEZ GOOGLE
echo ==============================================================
echo.
echo   Le 27/08, la verification a compte 3776 medias de l'export
echo   Takeout que le NAS ne porte pas : 12.6 Go, dont 2017 videos,
echo   concentres sur 2024, 2025 et 2026.
echo.
echo   Ces fichiers ne vivent aujourd'hui qu'a UN seul endroit, et
echo   c'est chez un tiers dont le quota est a 96 pour cent. Tant
echo   qu'il en reste un, RIEN ne s'efface chez Google.
echo.
echo   Ce script les copie sous "_A TRIER\Takeout Google\<annee>",
echo   la ou la chaine existante les reprend : rangement par annee,
echo   scan, tagging, visages.
echo.
echo   Trois garde-fous :
echo     - rien n'est ecrase. Un homonyme de meme taille est saute,
echo       d'une autre taille il prend un nom suffixe et se dit ;
echo     - la cible doit etre sous "_A TRIER" ;
echo     - la place est verifiee, et chaque copie est RELUE.
echo.
echo   Journal d'annulation dans _corbeille_copies : la liste exacte
echo   de ce qui a ete ecrit.
echo.
echo   Etape 1 : A BLANC. Rien n'est ecrit.
echo   Etape 2 : copie, seulement si tu reponds O.
echo.

set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

if not exist "_google.json" goto :sansrapport
pause

echo.
echo   Etape 1 sur 2 : A BLANC
echo --------------------------------------------------------------
"%PY%" copier_absentes.py --json _copie_absentes.json
if errorlevel 1 goto :rouge

echo.
echo   Etape 2 sur 2 : COPIE
echo --------------------------------------------------------------
echo.
choice /c ON /n /m "Copier maintenant ? [O]ui / [N]on : "
if errorlevel 2 goto :annule

"%PY%" copier_absentes.py --copier --json _copie_absentes.json
if errorlevel 1 goto :echec
goto :fin

:sansrapport
echo.
echo   _google.json est introuvable. Il vient de la verification :
echo.
echo     "%PY%" verifier_photos_google.py --takeout "C:\GOOGLE PHOTOS\extrait\Takeout\Google Photos" --json _google.json
echo.
pause
exit /b 2

:rouge
echo.
echo   VERDICT ROUGE - rien n'a ete ecrit.
echo   Lis le rapport ci-dessus : place insuffisante, cible hors
echo   "_A TRIER", ou aucune photo absente a copier.
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
echo   OK - les absentes sont sur le NAS
echo ==============================================================
echo.
echo   Suite, dans cet ORDRE - il compte :
echo     1. laisser le serveur SCANNER. Le rangement par annee
echo        travaille depuis l'index : tant que ces photos n'y sont
echo        pas, son plan ne les voit pas. Rien ne presse, elles
echo        sont deja sous "Takeout Google\<annee>", donc datees.
echo     2. "26 - Ranger par annee.bat", une fois qu'elles y sont
echo     3. relancer la verification :
echo        "%PY%" verifier_photos_google.py --takeout "..." --json _google.json
echo.
echo   NE RIEN EFFACER chez Google avant que cette verification ne
echo   compte ZERO absente. Et le quota ne bouge qu'une fois la
echo   CORBEILLE Google videe.
echo.
pause

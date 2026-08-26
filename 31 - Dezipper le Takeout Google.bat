@echo off
chcp 65001 >nul
cd /d "%~dp0"
REM Contenu en ASCII pur : cmd.exe relit le fichier par decalage d'octets.
REM Pas de bloc parenthese : uniquement des goto.
echo ==============================================================
echo   TAKEOUT GOOGLE - DEZIPPAGE
echo ==============================================================
echo.
echo   L'export Google Takeout arrive en une dizaine de .zip
echo   numerotes qui, ouverts dans le meme dossier, reconstituent
echo   un seul arbre Takeout\Google Photos.
echo.
echo   Trois pannes silencieuses guettent, et ce script les regarde
echo   AVANT d'ecrire le premier octet :
echo     - un lot manquant : l'arbre parait complet, et la suite
echo       declarerait ABSENTES des photos que Google detient ;
echo     - la place : un disque plein laisse un fichier tronque
echo       qui porte le bon nom ;
echo     - les chemins longs des albums, au-dela de 260 caracteres.
echo.
echo   Etape 1 : INVENTAIRE. Rien n'est ecrit.
echo   Etape 2 : extraction, seulement si tu reponds O.
echo.
echo   Reprenable : ce qui est deja ouvert a la bonne taille est
echo   saute. Relancer apres une coupure ne recommence pas tout.
echo.

set "SRC=C:\GOOGLE PHOTOS"
if not "%~1"=="" set "SRC=%~1"

set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

echo   Source : %SRC%
echo   Cible  : %SRC%\extrait
echo.
pause

echo.
echo   Etape 1 sur 2 : INVENTAIRE
echo --------------------------------------------------------------
"%PY%" dezipper_takeout.py --source "%SRC%" --json _takeout.json
if errorlevel 1 goto :rouge

echo.
echo   Etape 2 sur 2 : EXTRACTION
echo --------------------------------------------------------------
echo.
choice /c ON /n /m "Extraire maintenant ? [O]ui / [N]on : "
if errorlevel 2 goto :annule

"%PY%" dezipper_takeout.py --source "%SRC%" --extraire --json _takeout.json
if errorlevel 1 goto :echec
goto :fin

:rouge
echo.
echo   VERDICT ROUGE - rien n'a ete ecrit.
echo   Lis le rapport ci-dessus : lot manquant, zip illisible,
echo   conflit entre deux exports, ou place insuffisante.
echo   Un lot manquant se retelecharge depuis takeout.google.com.
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
echo   L'extraction s'est interrompue. Ce qui est ecrit reste bon :
echo   relance ce script, il reprend ou il en est.
echo.
pause
exit /b 1

:fin
echo.
echo ==============================================================
echo   OK - arbre Takeout ouvert
echo ==============================================================
echo.
echo   Prochaine etape : la verification, qui dit pour chaque photo
echo   de Google si le NAS la porte. Le chemin exact est affiche
echo   ci-dessus par le script.
echo.
echo     .venv\Scripts\python.exe verifier_photos_google.py --takeout "..."
echo.
echo   Un seul verdict ABSENT interdit tout effacement chez Google.
echo.
pause

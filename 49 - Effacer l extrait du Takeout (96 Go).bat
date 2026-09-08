@echo off
chcp 65001 >nul
cd /d "%~dp0"
REM Contenu en ASCII pur : cmd.exe relit le fichier par decalage d'octets.
REM Pas de bloc parenthese multi-lignes : uniquement des goto.
setlocal
set "GP=C:\GOOGLE PHOTOS"
set "EXTRAIT=%GP%\extrait"
set "GPHOTOS=%EXTRAIT%\Takeout\Google Photos"

set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

echo ==============================================================
echo   EFFACER L'EXTRAIT DU TAKEOUT - LA DERNIERE COPIE
echo ==============================================================
echo.
echo   Les 45 archives .zip sont deja parties (bat 48). Ce qui
echo   reste, "extrait", est la SEULE copie de l'export Google.
echo   Apres ce script, il n'y a plus de retour.
echo.
echo   Ce n'est donc PAS le meme geste que le bat 48. Le 48
echo   effacait un doublon prouve ; celui-ci efface un original.
echo   Il ne se lance que si le NAS porte tout, et il le REPROUVE
echo   maintenant -- un rapport de la semaine derniere ne dit rien
echo   d'aujourd'hui. Le 08/09, la meme verification est passee de
echo   0 absente le 28/08 a 570 en onze jours, le fonds ayant
echo   change entre les deux.
echo.
echo --------------------------------------------------------------
echo   Etape 1 sur 3 : PREUVE. Le NAS porte-t-il tout ?
echo --------------------------------------------------------------
echo.
if not exist "%GPHOTOS%" goto :pasdextrait
echo   Comptage en cours (environ trois minutes : l'export ET le
echo   fonds entier sont parcourus).
echo.

REM L'ORDRE EST DESCENDANT, et ce n'est pas un detail : sous cmd.exe,
REM `if errorlevel N` signifie "N OU PLUS". Ecrit dans l'autre sens,
REM `if errorlevel 1` attrapait aussi le code 2 et la branche :casse
REM n'aurait JAMAIS servi -- un dossier introuvable se serait lu comme
REM "il reste des absentes". Message faux, mais dans le sens prudent :
REM c'est exactement ce qui l'aurait rendu invisible longtemps.
"%PY%" verifier_photos_google.py --takeout "%GPHOTOS%" --json _google.json
if errorlevel 2 goto :casse
if errorlevel 1 goto :absentes

echo.
echo   ZERO absente. Le NAS porte tout ce que l'export contient.
echo.
echo --------------------------------------------------------------
echo   Etape 2 sur 3 : ce qui va disparaitre
echo --------------------------------------------------------------
echo.
echo   Le dossier "%EXTRAIT%" en entier, soit environ 96 Go.
echo.
echo   Ce qui RESTE apres : le NAS, et lui seul. Rappel de la
echo   ROADMAP (12 bis) : la copie hors site n'existe pas encore.
echo   Un NAS chez soi ne protege ni du feu, ni du vol, ni d'une
echo   fausse manoeuvre. Si la sauvegarde cloud n'est pas encore
echo   en place, attendre coute 96 Go et ne coute rien d'autre.
echo.
echo --------------------------------------------------------------
echo   Etape 3 sur 3 : confirmation
echo --------------------------------------------------------------
echo.
echo   C'est DEFINITIF : ces fichiers ne passent pas par la
echo   corbeille Windows, elle refuserait 96 Go. Ecris EFFACER en
echo   majuscules, ou n'importe quoi d'autre pour renoncer.
echo.
set "REP="
set /p REP=Effacer l'extrait du Takeout ? 
if /i not "%REP%"=="EFFACER" goto :renonce

echo.
echo   Effacement en cours (quelques minutes, 25000 fichiers)...
rmdir /s /q "%EXTRAIT%"
echo.
if exist "%EXTRAIT%" goto :reste
echo   Termine. L'extrait est efface.
goto :place

:reste
echo   ATTENTION : le dossier existe encore. Un fichier etait
echo   peut-etre ouvert par un autre programme. Relance ce script.
goto :place

:place
echo.
echo   Espace libre sur C: maintenant :
for /f "tokens=1,2" %%A in ('powershell -NoProfile -Command "$d=Get-PSDrive C; '{0:N0} {1:N0}' -f ($d.Free/1GB), (($d.Used+$d.Free)/1GB)"') do echo     %%A Go libres sur %%B Go
echo.
pause
endlocal
exit /b 0

:absentes
echo.
echo ==============================================================
echo   ARRET. Le NAS ne porte pas tout.
echo ==============================================================
echo.
echo   La liste des absentes est dans _google.json, et elle est
echo   affichee ci-dessus. RIEN n'a ete efface.
echo.
echo   La suite, DANS CET ORDRE :
echo     1. "32 - Copier les absentes de Google.bat"
echo        il les copie sous "_A TRIER\Takeout Google\<annee>" ;
echo     2. relancer CE script : il refait la preuve tout seul.
echo.
echo   Ne pas contourner cette etape. Une absente effacee ici
echo   n'existe plus nulle part.
echo.
pause
exit /b 1

:casse
echo.
echo   La verification n'a pas pu tourner (dossier introuvable ?).
echo   Rien n'a ete efface.
echo.
pause
exit /b 2

:pasdextrait
echo   "%GPHOTOS%" est introuvable.
echo   L'extrait a peut-etre deja ete efface. Rien a faire.
echo.
pause
exit /b 0

:renonce
echo.
echo   Renonce. Rien n'a ete efface.
echo.
pause
exit /b 0

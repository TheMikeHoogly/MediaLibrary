@echo off
chcp 65001 >nul
cd /d "%~dp0"
REM Contenu en ASCII pur : cmd.exe relit le fichier par decalage d'octets.
REM Pas de bloc parenthese multi-lignes : uniquement des goto.
setlocal
set "GP=C:\GOOGLE PHOTOS"
set "EXTRAIT=%GP%\extrait"
set "GPHOTOS=%EXTRAIT%\Takeout\Google Photos"
set "ATRIER=\\NAS-Bremblens\home\Photos\_A TRIER"

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
echo   Ce n'est donc PAS le meme geste que le bat 48 : le 48
echo   effacait un doublon prouve, celui-ci efface un original.
echo.
echo   Cinq controles s'enchainent, dans cet ordre. Chacun peut
echo   arreter le script, et aucun n'est contournable.
echo.
pause

echo.
echo --------------------------------------------------------------
echo   1 sur 5 : les listes FILTREES sont retirees
echo --------------------------------------------------------------
echo.
echo   `_google_a_rapatrier.json` a servi au bat 33 le 08/09 pour
echo   ecarter 1814 Motion Photos strippees. Ce tri vit desormais
echo   dans copier_absentes.py, qui lit le manifeste du bat 42 : le
echo   bat 33 ne lit plus cette liste. Elle ne sert donc plus a
echo   rien, et la laisser trainer ferait croire le contraire.
echo.
if not exist "_google_a_rapatrier.json" goto :pasdefiltre
del /f /q "_google_a_rapatrier.json"
echo   Retiree.
goto :etape2
:pasdefiltre
echo   Absente - rien a retirer.

:etape2
echo.
echo --------------------------------------------------------------
echo   2 sur 5 : plus rien n'attend dans "_A TRIER"
echo --------------------------------------------------------------
echo.
if not exist "%ATRIER%\Takeout Google" goto :atrierok
echo   ARRET. "_A TRIER\Takeout Google" existe encore.
echo.
echo   Des fichiers venus du Takeout n'ont pas ete ranges. Lance
echo   "26 - Ranger par annee.bat", et regarde ce qui reste : au
echo   09/09 c'etaient 14 fichiers SANS EXTENSION que le rangement
echo   ne savait pas classer - des videos de Motion Photo, dont
echo   Mike ne veut plus. Les identifier AVANT d'effacer la source.
echo.
pause
exit /b 1
:atrierok
echo   Rien n'attend. Le dossier n'existe plus.

echo.
echo --------------------------------------------------------------
echo   3 sur 5 : PREUVE. Le NAS porte-t-il tout ?
echo --------------------------------------------------------------
echo.
if not exist "%GPHOTOS%" goto :pasdextrait
echo   Comptage en cours (environ trois minutes : l'export ET le
echo   fonds entier sont parcourus). Ce controle lit le DISQUE, pas
echo   l'index du serveur : il n'attend aucun scan.
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
echo   4 sur 5 : ce qui disparait, et que rien ne rendra
echo --------------------------------------------------------------
echo.
echo   - le dossier "%EXTRAIT%", environ 96 Go ;
echo   - avec lui, les ~2400 VIDEOS des Motion Photos. Le strip du
echo     03/09 les a retirees du NAS ; Google en est le dernier
echo     detenteur au monde. Regle de Mike, 09/09 : une Motion
echo     Photo ne garde que son image. C'est donc voulu - mais
echo     c'est dit ici, une fois, avant le geste.
echo.
echo   Ce qui RESTE apres : le NAS, et lui seul.
echo   La copie hors site (ROADMAP 12 bis) n'existe pas encore.
echo   Un NAS chez soi ne protege ni du feu, ni du vol, ni d'une
echo   fausse manoeuvre. Si la sauvegarde cloud n'est pas branchee,
echo   attendre coute 96 Go et ne coute rien d'autre.
echo.

echo --------------------------------------------------------------
echo   5 sur 5 : confirmation
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
echo   PROCHAIN PAS, et il compte : la copie hors site (12 bis).
echo   Le fonds n'a plus qu'un seul exemplaire.
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
echo     2. "26 - Ranger par annee.bat" ;
echo     3. relancer CE script : il refait les cinq controles.
echo.
echo   Ne pas contourner. Une absente effacee ici n'existe plus
echo   nulle part.
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

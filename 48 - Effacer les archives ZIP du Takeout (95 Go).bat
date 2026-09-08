@echo off
chcp 65001 >nul
cd /d "%~dp0"
REM Contenu en ASCII pur : cmd.exe relit le fichier par decalage d'octets.
setlocal
set "GP=C:\GOOGLE PHOTOS"

echo ==============================================================
echo   EFFACER LES 45 ARCHIVES .ZIP DU TAKEOUT GOOGLE
echo ==============================================================
echo.
echo   Le Takeout occupe 191 Go sur C:, DEUX FOIS le meme contenu :
echo     - 45 fichiers .zip            environ 96 Go  (les archives)
echo     - le dossier "extrait"        environ 96 Go  (leur contenu)
echo.
echo   Ce script efface les .zip et GARDE "extrait". Pourquoi celui-la :
echo   l'extrait est LISIBLE tel quel - on peut y chercher une photo,
echo   la copier, la comparer. Les .zip, eux, demanderaient 96 Go
echo   libres pour etre rouverts, et il n'y en a plus.
echo.
echo   Ce qui reste APRES : une sauvegarde complete, entiere, verifiee.
echo.
echo --------------------------------------------------------------
echo   Etape 1 sur 3 : PREUVE. L'extrait est-il vraiment complet ?
echo --------------------------------------------------------------
echo.
echo   Rien ne sera efface si ce controle n'est pas vert. Il relit le
echo   sommaire des 45 lots et demande au disque si chaque membre est
echo   la, a la bonne taille. Un fichier ecrit a moitie porte le bon
echo   nom et ne manque a personne : c'est LUI qu'on cherche.
echo.

set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

"%PY%" verifier_takeout_ouvert.py --json _rapport_takeout_avant_purge.json
if errorlevel 1 (
    echo.
    echo ==============================================================
    echo   ARRET. L'extrait n'est PAS complet.
    echo ==============================================================
    echo.
    echo   Les .zip sont donc la seule copie entiere : on n'y touche pas.
    echo   Relance d'abord le bat 31 ^(dezipper^) - il reprend ou il en
    echo   est et ne reecrit que ce qui manque - puis reviens ici.
    echo.
    pause
    exit /b 1
)

echo.
echo --------------------------------------------------------------
echo   Etape 2 sur 3 : ce qui va disparaitre
echo --------------------------------------------------------------
echo.
if not exist "%GP%\takeout-*.zip" (
    echo   Aucun fichier takeout-*.zip dans "%GP%".
    echo   Ils ont peut-etre deja ete effaces. Rien a faire.
    echo.
    pause
    exit /b 0
)
dir /b "%GP%\takeout-*.zip" | find /c ".zip" > "%TEMP%\_nzip.txt"
set /p NZIP=<"%TEMP%\_nzip.txt"
del "%TEMP%\_nzip.txt" >nul 2>&1
echo   %NZIP% archive(s) dans "%GP%"
echo   Le dossier "extrait" n'est PAS touche.
echo.
echo --------------------------------------------------------------
echo   Etape 3 sur 3 : confirmation
echo --------------------------------------------------------------
echo.
echo   C'est DEFINITIF : ces fichiers ne passent pas par la corbeille
echo   Windows (elle refuserait 96 Go). Ecris OUI en majuscules pour
echo   confirmer, ou n'importe quoi d'autre pour renoncer.
echo.
set "REP="
set /p REP=Effacer les %NZIP% archives ? 
if /i not "%REP%"=="OUI" (
    echo.
    echo   Renonce. Rien n'a ete efface.
    echo.
    pause
    exit /b 0
)

echo.
echo   Effacement en cours...
del /f /q "%GP%\takeout-*.zip"
echo.
if exist "%GP%\takeout-*.zip" (
    echo   ATTENTION : il reste des .zip. Un fichier etait peut-etre
    echo   ouvert par un autre programme. Relance ce script.
) else (
    echo   Termine. Les 45 archives sont effacees.
)
echo.
echo   Espace libre sur C: maintenant :
for /f "tokens=1,2" %%A in ('powershell -NoProfile -Command "$d=Get-PSDrive C; '{0:N0} {1:N0}' -f ($d.Free/1GB), (($d.Used+$d.Free)/1GB)"') do echo     %%A Go libres sur %%B Go
echo.
echo   Le dossier "extrait" reste votre sauvegarde complete du Takeout.
echo   Rappel ROADMAP : ne pas y toucher avant la copie hors site, et
echo   avant d'avoir cherche dedans les 942 fichiers au contenu perdu.
echo.
pause
endlocal

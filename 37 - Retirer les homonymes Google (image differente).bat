@echo off
chcp 65001 >nul
cd /d "%~dp0"
REM Contenu en ASCII pur : cmd.exe relit le fichier par decalage d'octets.
echo ==============================================================
echo   RETIRER LES HOMONYMES A IMAGE DIFFERENTE de "_A TRIER"
echo ==============================================================
echo.
echo   Cas "Google porte mieux" : une copie re-encodee par Google dont
echo   le fonds a deja un homonyme, IMAGE differente. Ce n'est pas un
echo   doublon au sens du hachage : c'est une DECISION humaine (29/08,
echo   la version du NAS reste, ses XMP et son GPS avec).
echo.
echo   Lit docs\doublons_atrier.json, cle homonymes_differents, ecrite
echo   par le bat 36 ou par verifier_doublons_atrier.py. Une copie qui
echo   porte un nom absent de l'homonyme est GARDEE.
echo.
echo   SERVEUR ALLUME. Reversible : deplacer_doublons_atrier.py --undo,
echo   corbeille .corbeille-rangement, vidangee par le bat 24.
echo.
echo   Etape 1 : APERCU, rien n'est deplace.
echo --------------------------------------------------------------

set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

"%PY%" deplacer_doublons_atrier.py --homonymes-differents
if errorlevel 1 goto ECHEC

echo.
choice /c ON /n /m "Retirer ces copies maintenant ? [O]ui / [N]on : "
if errorlevel 2 goto FIN

"%PY%" deplacer_doublons_atrier.py --homonymes-differents --appliquer
echo.
echo   Termine. Le plan par annee doit tomber a 0 au prochain calcul.
goto FIN

:ECHEC
echo.
echo   Echec de l'apercu. Rien n'a ete deplace.

:FIN
pause

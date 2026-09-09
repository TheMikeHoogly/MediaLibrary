@echo off
chcp 65001 >nul
cd /d "%~dp0"
REM Contenu en ASCII pur : cmd.exe relit le fichier par decalage d'octets.
REM Pas de bloc parenthese multi-lignes : uniquement des goto.
REM NE PAS reecrire ce fichier pendant qu'il tourne (lecon du 09/09 : un
REM decalage de 70 octets a fait executer un fragment de ligne).
setlocal

set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

echo ==============================================================
echo   GRAND MENAGE DU DEPOT
echo ==============================================================
echo.
echo   Ce script ne connait PAS la liste de ce qu'il va deplacer.
echo   Il applique une politique -- des familles de fichiers, chacune
echo   avec sa raison -- puis il demande a l'inventaire, relance a
echo   l'instant, QUI LIT chaque candidat. Un fichier lu par du code,
echo   par une convention ou par un motif ne part pas, meme si la
echo   politique le nommait.
echo.
echo   C'est la regle du projet, ecrite dans le .gitignore apres la
echo   bevue du 08/09 : "c'est le ROLE qui decide, pas le prefixe".
echo.
echo   RIEN N'EST EFFACE. Les fichiers sont DEPLACES sous
echo   "_corbeille_menage\<horodatage>\", arborescence gardee, avec
echo   un manifeste, et une commande pour tout remettre.
echo.
echo   Quatre familles : rapports perimes, la quarantaine du 08/09,
echo   les archives de carnet, les pages mortes.
echo.
echo   Les journaux d'annulation (28,9 Mo) sont HORS politique par
echo   defaut. 88 des 89 sont gitignores, donc absents du depot :
echo   c'est la seule chose de cette liste qu'on ne peut pas
echo   recuperer. L'etape 3 les propose a part.
echo.
pause

echo.
echo --------------------------------------------------------------
echo   1 sur 4 : APERCU. Rien ne bouge.
echo --------------------------------------------------------------
echo.
"%PY%" appliquer_menage.py
set "CODE=%ERRORLEVEL%"
echo.
echo   code retour de l'apercu : %CODE%
if not "%CODE%"=="0" goto :casse

echo.
echo --------------------------------------------------------------
echo   2 sur 4 : les fichiers ci-dessus, dans la corbeille du menage
echo --------------------------------------------------------------
echo.
echo   Relis la liste. Elle vient d'etre calculee, pas recitee.
echo.
choice /c ON /n /m "Deplacer ces fichiers ? [O]ui / [N]on : "
if errorlevel 2 goto :sansfichiers

"%PY%" appliquer_menage.py --appliquer
set "CODE=%ERRORLEVEL%"
echo.
echo   code retour du deplacement : %CODE%
if "%CODE%"=="0" goto :etape3
echo.
echo   Des fichiers n'ont pas pu bouger (voir ci-dessus). Les autres
echo   sont deplaces, et le manifeste les liste. Rien n'est perdu.
goto :etape3

:sansfichiers
echo.
echo   Rien n'a ete deplace.

:etape3
echo.
echo --------------------------------------------------------------
echo   3 sur 4 : les JOURNAUX D'ANNULATION -- une decision a part
echo --------------------------------------------------------------
echo.
echo   28,9 Mo dans "docs\undo_*.json". Ils permettent d'annuler des
echo   rangements deja faits : dedoublonnage, rangement par annee,
echo   scission FR/EN. Mike a dit le 08/09 qu'il n'y reviendrait pas.
echo.
echo   Mais 88 sur 89 sont gitignores : les effacer les perd pour de
echo   bon. C'est pour ca qu'ils ne sont pas dans la politique.
echo.
echo   Recommandation : garder 30 jours. Les plus vieux ne servent
echo   plus a rien -- les fichiers qu'ils decrivent ont bouge depuis.
echo.
choice /c 123 /n /m "Journaux : [1] ne pas y toucher / [2] plus de 30 j / [3] plus de 90 j : "
if errorlevel 3 goto :j90
if errorlevel 2 goto :j30
goto :etape4

:j30
set "JOURS=30"
goto :journaux
:j90
set "JOURS=90"

:journaux
echo.
echo   APERCU des journaux de plus de %JOURS% jours :
echo.
"%PY%" appliquer_menage.py --journaux %JOURS%
echo.
choice /c ON /n /m "Deplacer AUSSI ces journaux ? [O]ui / [N]on : "
if errorlevel 2 goto :etape4
"%PY%" appliquer_menage.py --journaux %JOURS% --appliquer

:etape4
echo.
echo --------------------------------------------------------------
echo   4 sur 4 : ce qui reste a faire, et qui n'est pas automatique
echo --------------------------------------------------------------
echo.
echo   La corbeille du menage n'est PAS videe par ce script. Regarde
echo   ce qu'elle contient, laisse passer quelques jours, puis
echo   efface-la a la main. Un menage qui efface le jour meme n'est
echo   pas un menage, c'est un pari.
echo.
echo   Pour tout remettre en place, la commande exacte est affichee
echo   ci-dessus, et elle est aussi dans le manifeste.
echo.
pause
endlocal
exit /b 0

:casse
echo.
echo   L'apercu s'est arrete sur le code %CODE%, et rien n'a bouge.
echo.
echo   Code 2 : l'inventaire n'a pas pu tourner. Sans lui il n'y a
echo   pas de veto, donc pas de menage -- c'est voulu.
echo   Code 9009 : Python n'a pas pu etre lance. Verifier que
echo   ".venv\Scripts\python.exe" existe, sinon que "python" repond
echo   dans ce dossier.
echo.
pause
endlocal
exit /b 2

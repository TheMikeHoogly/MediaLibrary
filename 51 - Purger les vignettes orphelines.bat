@echo off
setlocal
chcp 65001 >nul 2>&1
cd /d "%~dp0"
title Purger les vignettes orphelines

set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

echo ==============================================================
echo   PURGER LES VIGNETTES ORPHELINES
echo ==============================================================
echo.
echo   Trois dossiers servent de cache : photo_thumbs, face_thumbs
echo   et animal_thumbs. Mesure du 16/09 : 50 668 fichiers, 1 552 Mo,
echo   dont 3 234 ORPHELINS pour 107 Mo, presque tous dans
echo   photo_thumbs - des photos renommees ou dedoublonnees.
echo.
echo   Une vignette orpheline n'est pas une perte. C'est un CALCUL
echo   mis de cote, et il se refait a la premiere demande en lisant
echo   l'original sur le NAS. La reversibilite, ici, c'est la
echo   regeneration : pas de corbeille, un journal.
echo.
echo   CE QUI A CHANGE LE 16/09 :
echo     - l'index se lit dans une COPIE de la base, fabriquee a
echo       l'etape 1. photos.db, la base du serveur, n'est plus
echo       jamais ouverte. Une copie de plus de 30 minutes est
echo       refusee ;
echo     - les TROIS caches sont traites : la campagne de retag est
echo       finie, photo_thumbs n'est plus ecarte ;
echo     - l'age d'une vignette est celui de sa CREATION : le
echo       plancher de 7 jours protege enfin celles d'hier.
echo.
echo   Les garde-fous d'avant restent : moins de 5 pourcent de noms
echo   reconnus dans un dossier, et le dossier est REFUSE en bloc.
echo.
echo   Le serveur peut rester allume.
echo.
pause

echo.
echo --------------------------------------------------------------
echo   1 sur 4 : COPIE de la base. photos.db n'est que LUE.
echo --------------------------------------------------------------
echo.
"%PY%" mesure_copie_base.py
set "CODE=%ERRORLEVEL%"
echo.
echo   code retour de la copie : %CODE%
if not "%CODE%"=="0" goto :casse

echo.
echo --------------------------------------------------------------
echo   2 sur 4 : APERCU. Rien ne bouge.
echo --------------------------------------------------------------
echo.
"%PY%" appliquer_purge_vignettes.py --base copie.db
set "CODE=%ERRORLEVEL%"
echo.
echo   code retour de l'apercu : %CODE%
if not "%CODE%"=="0" goto :casse

echo.
echo --------------------------------------------------------------
echo   3 sur 4 : effacer ce qui est liste ci-dessus
echo --------------------------------------------------------------
echo.
echo   Relis la liste. Elle vient d'etre calculee, pas recitee.
echo   Si tu attends plus de 30 minutes, le script refusera : la
echo   copie serait trop vieille. Relance alors ce bat.
echo.
set "REP="
set /p "REP=Effacer ces vignettes ? [O]ui / [N]on : "
if /I not "%REP%"=="O" goto :rien

"%PY%" appliquer_purge_vignettes.py --base copie.db --appliquer
set "CODE=%ERRORLEVEL%"
echo.
echo   code retour de la purge : %CODE%
if not "%CODE%"=="0" goto :casse

echo.
echo --------------------------------------------------------------
echo   4 sur 4 : ce qui se passe ensuite
echo --------------------------------------------------------------
echo.
echo   Les premieres pages de galerie que tu ouvriras peuvent etre
echo   un peu plus lentes : une vignette manquante se refait a la
echo   volee, une seule fois.
echo.
echo   Le journal de ce qui est parti est dans docs\.
echo.
pause
goto :fin

:rien
echo.
echo   Rien n'a ete efface.
echo.
pause
goto :fin

:casse
echo.
echo   ECHEC : lis les lignes au-dessus. Le script a refuse ou a
echo   rencontre une erreur - dans les deux cas il n'a rien efface.
echo.
pause

:fin
endlocal

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
echo   et animal_thumbs. Rien ne les a jamais purges.
echo.
echo   Mesure du 10/09 : 47 327 fichiers, 722 Mo, dont 36 773
echo   ORPHELINS pour 541 Mo -- trois quarts du poids.
echo.
echo   Une vignette orpheline n'est pas une perte. C'est un CALCUL
echo   mis de cote, et il se refait a la premiere demande en lisant
echo   l'original sur le NAS. La reversibilite, ici, c'est la
echo   regeneration : pas de corbeille, un journal.
echo.
echo   DEUX GARDE-FOUS, et ils visent MON code, pas tes fichiers :
echo     1. si moins de 5 pourcent des fichiers d'un dossier
echo        correspondent a un nom vivant, le dossier est REFUSE en
echo        bloc -- ce n'est pas un cache perime, c'est ma formule
echo        de nommage qui a cesse de parler la meme langue que
echo        server.py ;
echo     2. rien de plus jeune que 7 jours n'est touche.
echo.
pause

echo.
echo --------------------------------------------------------------
echo   1 sur 3 : APERCU. Rien ne bouge.
echo --------------------------------------------------------------
echo.
"%PY%" appliquer_purge_vignettes.py
set "CODE=%ERRORLEVEL%"
echo.
echo   code retour de l'apercu : %CODE%
if not "%CODE%"=="0" goto :casse

echo.
echo --------------------------------------------------------------
echo   2 sur 3 : effacer ce qui est liste ci-dessus
echo --------------------------------------------------------------
echo.
echo   Relis la liste. Elle vient d'etre calculee, pas recitee.
echo.
set "REP="
set /p "REP=Effacer ces vignettes ? [O]ui / [N]on : "
if /I not "%REP%"=="O" goto :rien

"%PY%" appliquer_purge_vignettes.py --appliquer
set "CODE=%ERRORLEVEL%"
echo.
echo   code retour de la purge : %CODE%
if not "%CODE%"=="0" goto :casse

echo.
echo --------------------------------------------------------------
echo   3 sur 3 : ce qui se passe ensuite
echo --------------------------------------------------------------
echo.
echo   Les premieres pages de galerie que tu ouvriras seront un peu
echo   plus lentes : les vignettes manquantes se refont a la volee,
echo   une seule fois chacune. C'est le prix de la place rendue, et
echo   il ne se paie qu'une fois.
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
echo   ECHEC : lis la ligne au-dessus. Le script a refuse ou a
echo   rencontre une erreur -- dans les deux cas il n'a rien efface.
echo.
pause

:fin
endlocal

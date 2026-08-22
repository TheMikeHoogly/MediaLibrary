@echo off
chcp 65001 >nul
cd /d "%~dp0"
REM Contenu en ASCII pur : cmd.exe relit le fichier par decalage d'octets.
REM Aucun bloc entre parentheses : une parenthese dans un echo A L'INTERIEUR
REM d'un bloc le FERME, et cmd meurt sur "ou etait inattendu" (22/08). Ici,
REM tout se fait par goto : il n'y a pas de bloc a fermer.
setlocal EnableDelayedExpansion

REM Dossier d'essai : modifiable ici, ou passe en argument
REM   "30 - Repetition de restauration.bat" E:\autre-essai
set "CIBLE=C:\temp\essai-restauration"
if not "%~1"=="" set "CIBLE=%~1"

set "NAS=\\nas-bremblens\home\Uploads"
set "DEPOT=https://github.com/TheMikeHoogly/MediaLibrary.git"

set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

echo ==============================================================
echo   REPETITION DE RESTAURATION - chantier 12
echo ==============================================================
echo.
echo   "PC mort lundi, tout revit vendredi." Tant qu'une restauration
echo   n'a pas eu lieu, "on a une sauvegarde" est une promesse, pas
echo   un fait.
echo.
echo   Ce lanceur remonte un PC NEUF a cote, dans un dossier d'essai,
echo   et chronometre. Il ne touche NI a la base vivante, NI au NAS,
echo   NI a ce dossier de projet : il ne fait que LIRE le NAS et
echo   ECRIRE dans le dossier d'essai.
echo.
echo     Dossier d'essai : %CIBLE%
echo     Sauvegarde lue  : %NAS%
echo.
echo   Prevois environ 300 Mo et quelques minutes de copie reseau.
echo.
echo   CONSEIL : arrete le serveur pendant la repetition. Un PC neuf
echo   n'en a pas, et surtout le serveur pousse 276 Mo sur le NAS
echo   toutes les heures - deux gros transferts qui se disputent le
echo   meme partage SMB, c'est l'ERREUR 59 assuree.
echo   Pour l'arreter : ecris "arret" dans _commande_serveur.txt,
echo   ou ferme sa fenetre.
echo.

REM --- Garde-fous : tout ce qui peut manquer se dit AVANT d'ecrire ---
if /i not "%CIBLE%"=="%CD%" goto :cible_ok
echo   REFUS : le dossier d'essai est le dossier du projet.
echo   Passe un autre chemin en argument, ou change CIBLE en tete.
goto :fin_erreur

:cible_ok
for %%d in ("%CIBLE%") do set "LECTEUR=%%~dd"
if exist "%LECTEUR%\" goto :lecteur_ok
echo   REFUS : le lecteur %LECTEUR% n'existe pas sur ce PC.
echo   Relance avec un chemin valide, par exemple :
echo      "%~nx0" C:\temp\essai-restauration
goto :fin_erreur

:lecteur_ok
if exist "%NAS%\photos.db.bak" goto :nas_ok
echo   La sauvegarde est introuvable : %NAS%\photos.db.bak
echo   Le NAS est-il monte ? Le serveur a-t-il deja sauvegarde ?
goto :fin_erreur

:nas_ok
if not exist "%CIBLE%\*" goto :vide_ok
echo   ATTENTION : %CIBLE% n'est pas vide.
echo   La repetition doit partir d'un dossier NEUF, sinon elle
echo   mesure un melange d'ancien et de restaure.
echo.
choice /c ON /n /m "   Continuer quand meme ? [O]ui / [N]on : "
if errorlevel 2 goto :annule

:vide_ok
echo.
choice /c ON /n /m "   Lancer la repetition maintenant ? [O]ui / [N]on : "
if errorlevel 2 goto :annule

REM Chrono en batch pur : le "1xx-100" evite que 08 et 09 passent pour
REM de l'octal, et aucun guillemet imbrique ne peut casser la ligne.
set "H=%TIME: =0%"
set /a T0=(1%H:~0,2%-100)*3600+(1%H:~3,2%-100)*60+(1%H:~6,2%-100)

echo.
echo --------------------------------------------------------------
echo   Etape 1/4 : ce que GIT rend (le code)
echo --------------------------------------------------------------
if not exist "%CIBLE%\" mkdir "%CIBLE%"
if exist "%CIBLE%\" goto :dossier_ok
echo   Impossible de creer %CIBLE%. Chemin ou droits ?
goto :fin_erreur

:dossier_ok
if not exist "%CIBLE%\.git" goto :clone
echo   Depot deja present, clone saute.
goto :apres_clone

:clone
git clone "%DEPOT%" "%CIBLE%"
if not errorlevel 1 goto :apres_clone
echo.
echo   Le clone a echoue. Deux causes usuelles : le dossier n'etait
echo   pas vide - git refuse d'y cloner - ou le reseau n'a pas
echo   repondu. Le message de git ci-dessus tranche.
goto :fin_erreur

:apres_clone
echo.
echo --------------------------------------------------------------
echo   Etape 2/4 : la BASE et le journal des jugements
echo --------------------------------------------------------------
robocopy "%NAS%" "%CIBLE%" journal_jugements.jsonl /NJH /NJS /NP /R:2 /W:5
if %ERRORLEVEL% LSS 8 goto :journal_ok
echo.
echo   La copie du journal des jugements a echoue.
goto :fin_erreur

:journal_ok
echo.
echo   La base fait 250 Mo. Copie NON BUFFERISEE ^(/J^) : c'est le mode
echo   recommande pour les gros fichiers sur SMB, et il evite une
echo   bonne part des "ERREUR 59".
echo.
REM La date du fichier AVANT et APRES : si elle change, c'est la
REM sauvegarde horaire du serveur qui a remplace photos.db.bak sous la
REM poignee ouverte - `backup_to` fait un os.replace atomique cote NAS.
REM Deviner la cause coute plus cher que la mesurer.
for %%f in ("%NAS%\photos.db.bak") do set "BAK_AVANT=%%~tf"
robocopy "%NAS%" "%CIBLE%" photos.db.bak /J /NJH /NJS /NP /R:3 /W:10
set "RC=%ERRORLEVEL%"
for %%f in ("%NAS%\photos.db.bak") do set "BAK_APRES=%%~tf"
if %RC% LSS 8 goto :base_copiee
echo.
echo   La copie de la base a echoue.
if not "%BAK_AVANT%"=="%BAK_APRES%" goto :cause_sauvegarde
echo.
echo   La date de photos.db.bak n'a pas bouge pendant la copie :
echo   ce n'est donc PAS la sauvegarde horaire. Reste une coupure de
echo   session SMB - l'ERREUR 59 classique sur un transfert long.
echo   Relance ce lanceur : il est re-entrant, le clone sera saute.
echo   Si ca recommence, copie photos.db.bak a la main dans
echo   l'explorateur, renomme-le photos.db, puis relance.
goto :fin_erreur

:cause_sauvegarde
echo.
echo   CAUSE TROUVEE : photos.db.bak a change pendant la copie.
echo      avant : %BAK_AVANT%
echo      apres : %BAK_APRES%
echo   C'est la sauvegarde horaire du serveur : elle remplace le
echo   fichier d'un seul coup sur le NAS, et la copie en cours perd
echo   sa poignee. Attends deux minutes et relance - ou arrete le
echo   serveur le temps de la repetition, ce qu'un PC neuf fait de
echo   toute facon.
goto :fin_erreur

:base_copiee
REM Relance du lanceur : la base d'un essai PRECEDENT gene le renommage.
REM Seul fichier que ce script efface, et il vit dans le dossier d'essai.
if exist "%CIBLE%\photos.db" del /q "%CIBLE%\photos.db"
ren "%CIBLE%\photos.db.bak" "photos.db"
if not errorlevel 1 goto :artefacts
echo.
echo   Impossible de renommer photos.db.bak en photos.db.
goto :fin_erreur

:artefacts
echo.
echo --------------------------------------------------------------
echo   Etape 3/4 : les ARTEFACTS que la base ne porte pas
echo --------------------------------------------------------------
echo   Reglages saisis a la main, journaux de deplacement, et les
echo   quarantaines : sans eux un PC neuf ne voit plus aucune photo,
echo   et plus aucun geste n'est annulable.
echo.
robocopy "%NAS%\artefacts" "%CIBLE%" /E /NJH /NJS /NP /R:2 /W:5
if %ERRORLEVEL% LSS 8 goto :chrono_fin
echo.
echo   La copie des artefacts a echoue.
goto :fin_erreur

:chrono_fin
set "H=%TIME: =0%"
set /a T1=(1%H:~0,2%-100)*3600+(1%H:~3,2%-100)*60+(1%H:~6,2%-100)
set /a SECONDES=T1-T0
if %SECONDES% LSS 0 set /a SECONDES=SECONDES+86400
set /a MINUTES=SECONDES/60
set /a RESTE=SECONDES%%60

echo.
echo ==============================================================
echo   RESTAURATION TERMINEE en %MINUTES% min %RESTE% s
echo ==============================================================
echo.
echo   Ce qui n'est PAS compte dedans, et c'est voulu : yolo11s.pt,
echo   yolo11n.pt d'ultralytics et cities1000.txt du bat 18 se
echo   re-telechargent, et ne mettent aucune decision humaine en jeu.
echo.

echo --------------------------------------------------------------
echo   Etape 4/4 : le seul juge - les decisions humaines, nom par nom
echo --------------------------------------------------------------
echo   Un total identique ne prouve rien : deux erreurs qui se
echo   compensent donnent le meme total. On ventile par NOM.
echo.
"%PY%" mesure_copie_base.py
if not errorlevel 1 goto :comparer
echo.
echo   La copie de la base vivante a echoue : sans elle, pas de
echo   comparaison. La restauration, elle, est faite.
goto :fin_erreur

:comparer
"%PY%" verifier_restauration.py --vivant copie.db --restaure "%CIBLE%" --json _repetition.json

echo.
echo ==============================================================
echo   Duree de la restauration : %MINUTES% min %RESTE% s
echo ==============================================================
echo.
echo   Cherche "REPETITION REUSSIE" ci-dessus. Le rapport ne l'ecrit
echo   que si l'integrite, les tables, le nombre de noms ET chaque
echo   nom concordent. Detail machine : _repetition.json
echo.
echo   Le dossier d'essai peut etre supprime a la main quand tu as
echo   note le resultat. Ce lanceur ne supprime jamais rien.
echo.
pause
exit /b 0

:annule
echo   Annule. Rien n'a ete ecrit.
pause
exit /b 0

:fin_erreur
echo.
pause
exit /b 1

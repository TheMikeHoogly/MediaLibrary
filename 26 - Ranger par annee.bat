@echo off
chcp 65001 >nul
cd /d "%~dp0"
REM Contenu en ASCII pur : cmd.exe relit le fichier par decalage d'octets.
REM Aucun bloc parenthese : un echo qui porte une parenthese DANS un bloc
REM ferme le bloc et tue le script sur un message qui ne nomme rien.
echo ==============================================================
echo   RANGEMENT PAR ANNEE - "_A TRIER" vers AAAA
echo ==============================================================
echo.
echo   Deplace les fichiers de "_A TRIER" vers un dossier par annee,
echo   d'apres la date de prise de vue. Sans date fiable, un fichier
echo   va dans "_SANS_DATE" - on ne devine jamais l'annee.
echo.
echo   Le plan doit avoir ete genere avant - page Reglages, bouton
echo   "Plan de rangement par annee", ou au demarrage du serveur :
echo   il lit docs\plan_rangement_annee.json.
echo.
echo   Aucun ecrasement : une collision au dossier annee est SAUTEE.
echo   Reversible via le journal undo ecrit dans docs\.
echo.

set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

echo --------------------------------------------------------------
echo   Etape 0 : CE QUE LE PLAN VA RENCONTRER
echo.
echo   Une cible deja prise n'est PAS une permission d'effacer : le
echo   meme nom peut porter la meme photo - un doublon - ou une
echo   autre. Ce controle compare les deux et le DIT.
echo --------------------------------------------------------------
echo.

"%PY%" verifier_plan_annee.py
if errorlevel 3 goto RIEN_A_RANGER
if errorlevel 2 goto SANS_VERDICT

echo.
choice /c ON /n /m "Continuer vers l'apercu du rangement ? [O]ui / [N]on : "
if errorlevel 2 goto FIN
goto APERCU

:RIEN_A_RANGER
echo.
echo   Rien ne peut etre range : le plan est vide, ou chaque cible
echo   est deja prise. Le serveur n est PAS arrete.
echo   Doublons : bat 36. Voisins et differents : a regarder, puis
echo   renommer - le detail est dans plan_annee_collisions.json.
goto FIN

:SANS_VERDICT
echo.
echo   Le controle n'a pas pu juger les collisions - exiftool absent.
echo   On peut continuer : le rangement ne recouvre jamais rien, il
echo   saute simplement les cibles prises.
echo.
choice /c ON /n /m "Continuer quand meme ? [O]ui / [N]on : "
if errorlevel 2 goto FIN

:APERCU
echo.
echo --------------------------------------------------------------
echo   Etape 1 : APERCU du rangement. Rien n'est deplace.
echo --------------------------------------------------------------
echo.

"%PY%" appliquer_plan_annee.py
if errorlevel 1 goto ECHEC_APERCU

echo.
echo --------------------------------------------------------------
echo   Etape 2 : ARRETER LE SERVEUR
echo.
echo   Il est l'ecrivain unique de photos.db. Deux ecrivains, c'est
echo   une base corrompue. Ce script peut l'arreter pour toi et le
echo   redemarrer a la fin - la fenetre "MediaLibrary - Serveur"
echo   doit tourner.
echo --------------------------------------------------------------
echo.
choice /c ON /n /m "Arreter le serveur maintenant ? [O]ui / [N]on : "
if errorlevel 2 goto SANS_ARRET

echo arret> _commande_serveur.txt
echo   Ordre d'arret ecrit. J'attends 12 secondes.
timeout /t 12 /nobreak >nul
set "REDEMARRER=1"
goto LOT

:SANS_ARRET
echo.
echo   Tres bien. Si le serveur repond encore, le rangement REFUSERA
echo   d'ecrire et te le dira - rien ne sera abime.
echo.

:LOT
echo.
echo   Etape 3 : un PETIT LOT de 20 d'abord, pour verifier sur le NAS.
echo.
choice /c ON /n /m "Deplacer un lot de 20 maintenant ? [O]ui / [N]on : "
if errorlevel 2 goto RELANCE

"%PY%" appliquer_plan_annee.py --appliquer --limite 20
if errorlevel 1 goto ECHEC_LOT

echo.
echo   Lot applique. Verifie le resultat sur le NAS.
echo.
choice /c ON /n /m "Deplacer TOUT le reste maintenant ? [O]ui / [N]on : "
if errorlevel 2 goto RELANCE

"%PY%" appliquer_plan_annee.py --appliquer
if errorlevel 1 goto ECHEC_RESTE

echo.
echo   Termine.
goto RELANCE

:ECHEC_APERCU
echo.
echo   Echec de l'apercu. Rien n'a ete deplace.
goto RELANCE

:ECHEC_LOT
echo.
echo   Le lot de 20 a echoue. Lis le message ci-dessus : le plan est
echo   peut-etre perime, ou le serveur tourne encore.
goto RELANCE

:ECHEC_RESTE
echo.
echo   Le reste a echoue. Le lot de 20, lui, est bien applique.
goto RELANCE

:RELANCE
if not defined REDEMARRER goto FIN
echo.
echo   Je redemarre le serveur.
echo marche> _commande_serveur.txt
timeout /t 3 /nobreak >nul

:FIN
echo.
echo   Pour annuler : appliquer_plan_annee.py --undo docs\undo_annee_XXXX.json --appliquer
echo   Pour retirer les doublons vers la corbeille reversible : bat 36.
pause

@echo off
REM ============================================================
REM   GIT - MediaLibrary : guichet unique
REM
REM   Remplace et unifie les anciens bats 27 (commit de session),
REM   28 (fusion dans main) et 30 (nettoyage des branches). Le
REM   code eprouve de chacun est repris tel quel, en sous-routine.
REM
REM   Rien n'est fait sans confirmation. Aucun "checkout main" :
REM   le repertoire de travail n'est jamais reecrit, donc le
REM   verrou de server.py ne gene pas et le serveur peut rester
REM   allume.
REM
REM   Le menu affiche l'etat du depot, l'etat du SERVEUR, et le
REM   geste conseille. Apres un commit qui touche du code Python,
REM   il propose le redemarrage : sans lui, on observerait
REM   l'ancienne version -- et une observation fausse est pire
REM   qu'une observation absente.
REM
REM   ASCII PUR obligatoire (voir CLAUDE.md / verifier_bat.py).
REM ============================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"
set "DEPOT=https://github.com/TheMikeHoogly/MediaLibrary"
set "PORT=8080"

git rev-parse --is-inside-work-tree >nul 2>&1
if errorlevel 1 (
  echo ERREUR : ce dossier n'est pas un depot git.
  pause
  exit /b 1
)

call :verrou
if errorlevel 1 exit /b 1

REM ============================================================
REM   MENU
REM ============================================================
:menu
cls
call :etat
echo ============================================================
echo   GIT - MediaLibrary
echo ============================================================
echo   Branche : !BRANCH!
echo   Arbre   : !TXT_ARBRE!
echo   Main    : !TXT_AVANCE!
echo   Distant : !TXT_DISTANT!
echo   Serveur : !TXT_SERVEUR!
echo ------------------------------------------------------------
echo   Conseille : !CONSEIL!
echo ------------------------------------------------------------
echo   1. Commit de session       add -A + commit + push
echo   2. Fusionner dans main     fast-forward, sans checkout
echo   3. Nettoyer les branches deja fusionnees
echo   4. Nouveau chantier        creer une branche
echo   5. Etat detaille           status, log, branches
echo   6. Ouvrir GitHub dans le navigateur
echo   7. Redemarrer le serveur   pour observer le code commite
echo   8. Agent git                dernier controle, dernier commit
echo   0. Quitter
echo ------------------------------------------------------------
echo   Ordre d'une session : 1 commit, puis 7 redemarrage, puis
echo   observation en reel, puis 2 fusion. Le choix 1 propose
echo   lui-meme le redemarrage quand le commit touche du .py.
echo.
choice /c 123456780 /n /m "Ton choix : "
set "CH=!ERRORLEVEL!"
if "!CH!"=="1" call :commit
if "!CH!"=="2" call :fusion
if "!CH!"=="3" call :branches
if "!CH!"=="4" call :nouvelle
if "!CH!"=="5" call :detail
if "!CH!"=="6" call :github
if "!CH!"=="7" call :redemarrer
if "!CH!"=="8" call :agent
if "!CH!"=="9" goto :fin
goto :menu

:fin
echo.
echo Termine.
exit /b 0

REM ============================================================
REM   ETAT DU DEPOT - lecture seule, aucun geste
REM ============================================================
:etat
set "BRANCH="
for /f "delims=" %%b in ('git branch --show-current') do set "BRANCH=%%b"
if not defined BRANCH set "BRANCH=HEAD detachee"

set "NMOD=0"
for /f %%n in ('git status --porcelain ^| find /c /v ""') do set "NMOD=%%n"
set "TXT_ARBRE=propre, rien a commiter"
if not "!NMOD!"=="0" set "TXT_ARBRE=!NMOD! fichiers modifies ou non suivis"

set "AHEAD=0"
for /f %%n in ('git rev-list --count main..HEAD 2^>nul') do set "AHEAD=%%n"
set "TXT_AVANCE=au niveau de main, rien a fusionner"
if not "!AHEAD!"=="0" set "TXT_AVANCE=!AHEAD! commits d'avance sur main"

set "PUB=0"
git rev-parse --verify --quiet "refs/remotes/origin/!BRANCH!" >nul 2>&1
if not errorlevel 1 set "PUB=1"
set "NPUSH=0"
set "TXT_DISTANT=branche jamais poussee sur GitHub"
if "!PUB!"=="1" set "TXT_DISTANT=publiee, a jour avec origin"
if "!PUB!"=="1" for /f %%n in ('git rev-list --count refs/remotes/origin/!BRANCH!..HEAD 2^>nul') do set "NPUSH=%%n"
if not "!NPUSH!"=="0" set "TXT_DISTANT=publiee, !NPUSH! commits non pousses"

set "SRV=0"
for /f "tokens=5" %%P in ('netstat -ano -p TCP ^| findstr /C:":!PORT! " ^| findstr "LISTENING"') do set "SRV=1"
set "TXT_SERVEUR=arrete"
if "!SRV!"=="1" set "TXT_SERVEUR=en marche sur le port !PORT!"

set "CONSEIL=1. Commit de session"
if "!NMOD!"=="0" set "CONSEIL=2. Fusionner dans main - seulement si observe en reel"
if "!NMOD!"=="0" if "!AHEAD!"=="0" set "CONSEIL=4. Nouveau chantier, ou 3. Nettoyer les branches"
if "!BRANCH!"=="main" set "CONSEIL=4. Nouveau chantier - on ne travaille pas sur main"
exit /b 0

REM ============================================================
REM   VERROU GIT PERIME (.git\index.lock)
REM   Cause habituelle : un client git graphique ouvert sur le
REM   depot, ou un process git precedent qui a plante.
REM ============================================================
:verrou
set "GITLOCK="
if exist ".git\index.lock" set "GITLOCK=1"
if exist ".git\HEAD.lock" set "GITLOCK=1"
if not defined GITLOCK exit /b 0
echo ATTENTION : un verrou git est present dans .git (index.lock ou HEAD.lock).
echo   Cause habituelle : un client git graphique ouvert sur ce depot,
echo   ou un process git precedent qui a plante.
echo   Ferme ce client s'il est ouvert sur ce depot avant de continuer.
echo.
choice /c ON /n /m "Supprimer ce verrou et continuer ? (O = oui / N = annuler) : "
if errorlevel 2 (
  echo Annule : le verrou est laisse en place.
  pause
  exit /b 1
)
del /q ".git\*.lock" 2>nul
del /q ".git\refs\heads\*.lock" 2>nul
if exist ".git\index.lock" (
  echo Echec : impossible de supprimer le verrou. Un client git tourne encore ?
  echo Ferme-le completement, puis relance ce script.
  pause
  exit /b 1
)
echo Verrou supprime.
echo.
exit /b 0

REM ============================================================
REM   1. COMMIT DE SESSION   (ex-bat 27)
REM   Lit SESSION_COMMIT.txt (prepare par Claude en fin de
REM   session) et propose par defaut la branche et le titre.
REM   Entree = accepter la proposition. Sans ce fichier, les
REM   questions sont posees a la main.
REM   Format (ASCII, sans guillemets ni "!") :
REM     branche=feat/mon-chantier
REM     titre=Mon titre de commit
REM ============================================================
:commit
cls
echo ============================================================
echo   1. COMMIT DE SESSION
echo ============================================================
echo.
call :verrou
if errorlevel 1 exit /b 0

set "SUG_BRANCHE="
set "SUG_TITRE="
if exist "SESSION_COMMIT.txt" (
  for /f "usebackq eol=# tokens=1* delims==" %%a in ("SESSION_COMMIT.txt") do (
    if /i "%%a"=="branche" set "SUG_BRANCHE=%%b"
    if /i "%%a"=="titre" set "SUG_TITRE=%%b"
  )
)

echo Branche courante  : !BRANCH!
if defined SUG_BRANCHE echo Branche proposee  : !SUG_BRANCHE!
if defined SUG_TITRE echo Titre propose     : !SUG_TITRE!
echo.
echo Etat du depot :
git status -s
echo.

if not defined SUG_BRANCHE goto :branche_manuelle
if /i "!SUG_BRANCHE!"=="!BRANCH!" goto :apres_branche
choice /c ON /n /m "Basculer sur la branche proposee !SUG_BRANCHE! ? (O = oui / N = rester sur !BRANCH!) : "
if errorlevel 2 goto :branche_manuelle
git checkout -b "!SUG_BRANCHE!" 2>nul
if not errorlevel 1 goto :branche_ok
git checkout "!SUG_BRANCHE!"
if errorlevel 1 (
  echo Echec de bascule sur !SUG_BRANCHE!. Abandon.
  pause
  exit /b 0
)
:branche_ok
set "BRANCH=!SUG_BRANCHE!"
goto :apres_branche

:branche_manuelle
choice /c ON /n /m "Creer une NOUVELLE branche ? (O = oui / N = rester sur !BRANCH!) : "
if errorlevel 2 goto :apres_branche
set "NEWBR="
set /p "NEWBR=Nom de la nouvelle branche : "
if "!NEWBR!"=="" (
  echo Nom vide : on reste sur !BRANCH!.
  goto :apres_branche
)
git checkout -b "!NEWBR!"
if errorlevel 1 (
  echo Echec de creation de la branche. Abandon.
  pause
  exit /b 0
)
set "BRANCH=!NEWBR!"
:apres_branche

set "MSG="
if defined SUG_TITRE (
  set /p "MSG=Message de commit [Entree = titre propose] : "
  if "!MSG!"=="" set "MSG=!SUG_TITRE!"
) else (
  set /p "MSG=Message de commit : "
)
if "!MSG!"=="" (
  echo Message vide. Abandon, rien n'a ete commite.
  pause
  exit /b 0
)

git add -A
git commit -m "!MSG!"
if errorlevel 1 (
  echo.
  echo Rien a commiter ^(ou echec du commit^).
  pause
  exit /b 0
)

REM La proposition est consommee : elle ne doit pas etre reproposee.
if exist "SESSION_COMMIT.txt" del /q "SESSION_COMMIT.txt"

echo.
echo Commit fait sur la branche !BRANCH!.
echo.

choice /c ON /n /m "Pousser vers origin maintenant ? (O = oui / N = non) : "
if errorlevel 2 goto :rappel_commit
git push -u origin "!BRANCH!"
if errorlevel 1 (
  echo.
  echo Le push a echoue. Tu peux reessayer : git push -u origin !BRANCH!
)

REM --- Le commit touche-t-il du code que le SERVEUR charge ? ---
REM   Si oui, le serveur qui tourne execute encore l'ANCIENNE version :
REM   observer maintenant, c'est observer le code d'avant. C'est la seule
REM   etape de la sequence que rien ne rappelait.
REM
REM   Les bancs de mesure (mesure_*.py) et les tests (test_*.py) ne sont
REM   JAMAIS importes par le serveur : les compter ferait sonner l'alerte
REM   pour rien, et une alerte qui sonne pour rien s'ignore.
set "PYCHANGE="
git show --name-only --pretty=format: HEAD | findstr /i /r "\.py$" | findstr /v /i /r "^test_ ^mesure_" >nul 2>&1
if not errorlevel 1 set "PYCHANGE=1"
if not defined PYCHANGE goto :rappel_commit
echo.
echo ------------------------------------------------------------
echo   CE COMMIT TOUCHE DU CODE CHARGE PAR LE SERVEUR
echo ------------------------------------------------------------
echo   Il n'y a PAS de rechargement a chaud : le serveur qui tourne
echo   execute encore la version d'avant. Observer sans redemarrer,
echo   c'est observer l'ancien code.
echo.
choice /c ON /n /m "Redemarrer le serveur maintenant ? (O = oui / N = non) : "
if errorlevel 2 goto :rappel_commit
call :redemarrer

:rappel_commit
echo.
echo ------------------------------------------------------------
echo   PROCHAINES ACTIONS :
echo   - Observer en reel : http://192.168.0.13:!PORT!
echo   - Valide en reel ? Revenir ici et choisir 2 pour fusionner.
echo   - ROADMAP.md et PROMPT_NOUVELLE_SESSION.md a jour ?
echo     ^(Claude les prepare pour la prochaine session.^)
echo ------------------------------------------------------------
echo.
pause
exit /b 0

REM ============================================================
REM   2. FUSIONNER DANS MAIN   (ex-bat 28)
REM   Fast-forward de main COTE REMOTE, sans jamais faire
REM   "git checkout main" en local : aucun fichier du repertoire
REM   de travail n'est reecrit, donc le verrou de server.py tenu
REM   par le serveur ne gene pas.
REM ============================================================
:fusion
cls
echo ============================================================
echo   2. FUSIONNER LA BRANCHE DANS MAIN
echo ============================================================
echo.
call :verrou
if errorlevel 1 exit /b 0

echo Branche courante : !BRANCH!
for /f "delims=" %%c in ('git log -1 --oneline') do echo Dernier commit   : %%c
echo.

if "!BRANCH!"=="main" (
  echo Tu es deja sur main : rien a fusionner.
  echo Bascule d'abord sur ta branche de travail.
  pause
  exit /b 0
)

git diff --quiet && git diff --cached --quiet
if errorlevel 1 (
  echo ATTENTION : des modifications ne sont pas commitees :
  echo.
  git status -s
  echo.
  echo Commit d'abord ^(choix 1 du menu^), puis reviens ici.
  pause
  exit /b 0
)

echo Recuperation de l'etat distant (git fetch)...
git fetch origin
if errorlevel 1 (
  echo Echec du fetch. Verifie ta connexion / tes identifiants GitHub.
  pause
  exit /b 0
)
echo.

REM main doit etre un ancetre de la branche courante.
git merge-base --is-ancestor origin/main HEAD
if errorlevel 1 (
  echo ============================================================
  echo   FUSION IMPOSSIBLE EN FAST-FORWARD
  echo ============================================================
  echo   main a avance de son cote : la branche a diverge.
  echo   Il faut une vraie fusion ^(merge commit ou rebase^), qui
  echo   REECRIT server.py en local -- donc serveur ARRETE d'abord.
  echo.
  echo   Etapes manuelles, serveur arrete :
  echo     git checkout main
  echo     git pull origin main
  echo     git merge !BRANCH!
  echo     git push origin main
  echo     git checkout !BRANCH!
  echo.
  pause
  exit /b 0
)

echo Fast-forward possible : main est un ancetre de !BRANCH!.
echo.
echo Rappel : on ne fusionne qu'APRES observation en reel.
echo.
echo Ce script va :
echo   1. Pousser !BRANCH! sur origin
echo   2. Avancer main sur origin jusqu'au sommet de !BRANCH!
echo   3. Mettre a jour la ref locale main (sans checkout)
echo.
choice /c ON /n /m "Continuer ? (O = oui / N = annuler) : "
if errorlevel 2 (
  echo Annule. Rien n'a change.
  pause
  exit /b 0
)
echo.

echo [1/3] Push de la branche !BRANCH!...
git push origin HEAD
if errorlevel 1 (
  echo Echec du push de la branche. Abandon.
  pause
  exit /b 0
)
echo.

echo [2/3] Fast-forward de main sur origin...
git push origin HEAD:main
if errorlevel 1 (
  echo Echec du push vers main. main a peut-etre avance entre-temps.
  echo Relance ce choix ^(il refera le fetch et le controle^).
  pause
  exit /b 0
)
echo.

echo [3/3] Mise a jour de la ref locale main...
git fetch origin main:main
if errorlevel 1 (
  echo main distant est a jour, mais la ref locale n'a pas pu suivre.
  echo Sans gravite : elle se mettra a jour au prochain fetch.
)
echo.

echo ============================================================
echo   FUSION REUSSIE
echo ============================================================
echo   !BRANCH! est fusionnee dans main, local et distant.
echo.
echo   PROCHAINES ACTIONS :
echo   - Prochain chantier : choix 4 du menu, ou Claude proposera
echo     la branche via SESSION_COMMIT.txt, lu au choix 1.
echo   - Branches terminees qui trainent : choix 3.
echo.
pause
exit /b 0

REM ============================================================
REM   3. NETTOYER LES BRANCHES FUSIONNEES   (ex-bat 30)
REM   Sans risque : "git branch -d" REFUSE de supprimer une
REM   branche dont le travail n'est pas dans main. Aucun commit
REM   ne peut etre perdu. Aucun checkout : serveur non gene.
REM ============================================================
:branches
cls
echo ============================================================
echo   3. NETTOYER LES BRANCHES DEJA FUSIONNEES
echo ============================================================
echo.
echo Branche courante : !BRANCH!   ^(elle ne sera pas touchee^)
echo.

echo Recuperation de l'etat distant (git fetch)...
git fetch --prune origin
if errorlevel 1 (
  echo Echec du fetch. Verifie ta connexion / tes identifiants GitHub.
  echo Le nettoyage local reste possible ; le distant sera ignore.
)
echo.

set "N=0"
echo Branches fusionnees dans main, donc supprimables :
echo ------------------------------------------------------------
for /f "tokens=* delims= " %%b in ('git branch --merged main --format="%%(refname:short)"') do (
  if not "%%b"=="main" if not "%%b"=="!BRANCH!" (
    set /a N+=1
    echo   %%b
  )
)
echo ------------------------------------------------------------
if "!N!"=="0" (
  echo Aucune branche a nettoyer : le depot est deja propre.
  echo.
  pause
  exit /b 0
)
echo !N! branches candidates.
echo.
echo Rappel : tout leur travail est deja dans main. Supprimer ces
echo etiquettes ne supprime aucun commit ni aucun fichier.
echo.

choice /c ON /n /m "Supprimer ces branches EN LOCAL ? (O = oui / N = annuler) : "
if errorlevel 2 (
  echo Annule. Rien n'a change.
  pause
  exit /b 0
)
echo.

set "SUPPR=0"
set "ECHEC=0"
for /f "tokens=* delims= " %%b in ('git branch --merged main --format="%%(refname:short)"') do (
  if not "%%b"=="main" if not "%%b"=="!BRANCH!" (
    git branch -d "%%b" >nul 2>&1
    if errorlevel 1 (
      set /a ECHEC+=1
      echo   REFUS  %%b   ^(git protege : travail absent de main^)
    ) else (
      set /a SUPPR+=1
      echo   ok     %%b
    )
  )
)
echo.
echo Local : !SUPPR! supprimees, !ECHEC! refusees.
echo.

echo Les memes branches peuvent aussi etre retirees de GitHub.
echo.
choice /c ON /n /m "Nettoyer aussi sur GitHub ? (O = oui / N = non) : "
if errorlevel 2 (
  echo Distant laisse tel quel.
  echo.
  pause
  exit /b 0
)
echo.

set "RSUPPR=0"
for /f "tokens=* delims= " %%b in ('git branch -r --merged main --format="%%(refname:short)"') do (
  set "RB=%%b"
  set "RB=!RB:origin/=!"
  if not "!RB!"=="main" if not "!RB!"=="!BRANCH!" if not "!RB!"=="HEAD" (
    git push origin --delete "!RB!" >nul 2>&1
    if errorlevel 1 (
      echo   echec  !RB!
    ) else (
      set /a RSUPPR+=1
      echo   ok     !RB!
    )
  )
)
echo.
echo Distant : !RSUPPR! branches supprimees sur GitHub.
echo.
echo main est intacte, ainsi que la branche courante.
echo Aucun commit n'a ete supprime.
echo.
pause
exit /b 0

REM ============================================================
REM   4. NOUVEAU CHANTIER
REM   La branche part de la branche COURANTE : c'est correct
REM   juste apres une fusion reussie, elle est alors au niveau
REM   de main. "git checkout -b" ne reecrit aucun fichier.
REM ============================================================
:nouvelle
cls
echo ============================================================
echo   4. NOUVEAU CHANTIER - creer une branche
echo ============================================================
echo.
echo La nouvelle branche part de la branche COURANTE, !BRANCH!.
echo C'est correct juste apres une fusion reussie : elle est
echo alors au niveau de main.
echo.
if not "!NMOD!"=="0" (
  echo ATTENTION : l'arbre n'est pas propre. Les !NMOD! modifications
  echo en cours suivront sur la nouvelle branche.
  echo.
)
if not "!AHEAD!"=="0" (
  echo ATTENTION : !AHEAD! commits de cette branche ne sont pas
  echo dans main. Fusionne d'abord ^(choix 2^) si c'est valide.
  echo.
)
set "NB="
set /p "NB=Nom de la nouvelle branche, vide = annuler : "
if "!NB!"=="" (
  echo Annule.
  pause
  exit /b 0
)
git checkout -b "!NB!"
if errorlevel 1 (
  echo Echec de la creation de la branche.
) else (
  echo Branche !NB! creee et active.
)
echo.
pause
exit /b 0

REM ============================================================
REM   7. REDEMARRER LE SERVEUR
REM   Delegue a "0 - Demarrer le serveur.bat", qui sait deja
REM   arreter le processus a l'ecoute du port avant de relancer.
REM   Le nom de ce bat porte un accent ; ce fichier-ci est en
REM   ASCII PUR, donc on le retrouve par JOKER, jamais en
REM   l'ecrivant.
REM ============================================================
:redemarrer
cls
echo ============================================================
echo   7. REDEMARRER LE SERVEUR
echo ============================================================
echo.
REM   `dir /b` developpe le joker a coup sur et rend le nom NU : un
REM   `for` sur un motif entre guillemets ne garantit pas les deux.
set "BAT0="
for /f "delims=" %%f in ('dir /b "0 - D*marrer le serveur.bat" 2^>nul') do set "BAT0=%%f"
if not defined BAT0 goto :bat0_absent
if not exist "!BAT0!" goto :bat0_absent
goto :bat0_trouve

:bat0_absent
echo Introuvable : le bat de demarrage du serveur.
echo Il commence normalement par "0 - D" et se trouve ici :
echo   !CD!
echo.
pause
exit /b 0

:bat0_trouve
echo Bat de demarrage : !BAT0!
echo.
echo Il va ARRETER le processus qui ecoute sur le port !PORT!, puis
echo relancer le serveur dans une fenetre separee. Les traitements
echo en cours ^(tagging, scan^) sont interrompus.
echo.
choice /c ON /n /m "Redemarrer maintenant ? (O = oui / N = annuler) : "
if errorlevel 2 (
  echo Annule. Le serveur n'a pas ete touche.
  echo.
  pause
  exit /b 0
)
echo.
call "!BAT0!"
echo.
echo ------------------------------------------------------------
echo   Serveur relance dans sa propre fenetre.
echo   Observer en reel : http://192.168.0.13:!PORT!
echo   On ne fusionne ^(choix 2^) qu'APRES cette observation.
echo ------------------------------------------------------------
echo.
pause
exit /b 0

REM ============================================================
REM   8. AGENT GIT
REM   L'agent (fenetre "MediaLibrary - Git", lancee par le bat 0)
REM   surveille _commande_git.txt et livre APRES controle. Ce
REM   choix montre ce qu'il a tente, et pourquoi il a refuse.
REM
REM   Ce qu'il RAPPORTE n'est pas ce qui s'est PASSE : la preuve
REM   reste git lui-meme, choix 5.
REM ============================================================
:agent
cls
echo ============================================================
echo   8. AGENT GIT - dernier rapport
echo ============================================================
echo.
REM   Le signe de vie vient de _agent_git_vu.txt, touche a chaque
REM   tour de boucle : un titre de fenetre se devine, un fichier
REM   date se lit. git_agent.py --etat l'affiche en premier.
set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" git_agent.py --etat
echo.
echo ------------------------------------------------------------
echo   Controler SANS rien livrer  : %PY% git_agent.py --controle
echo   Reveiller / tester le canal : ecrire "ping" dans
echo                                 _commande_git.txt
echo   Canal ferme ? relancer "0 - Demarrer le serveur.bat"
echo   Ce que git dit vraiment     : choix 5 de ce menu
echo ------------------------------------------------------------
echo.
pause
exit /b 0

REM ============================================================
REM   5. ETAT DETAILLE - lecture seule
REM ============================================================
:detail
cls
echo ============================================================
echo   5. ETAT DETAILLE
echo ============================================================
echo.
echo -- git status -sb
git status -sb
echo.
echo -- 8 derniers commits
git log --oneline -8
echo.
echo -- commits de !BRANCH! absents de main
git log --oneline main..HEAD
echo.
echo -- branches locales
git branch -vv
echo.
pause
exit /b 0

REM ============================================================
REM   6. OUVRIR GITHUB
REM ============================================================
:github
cls
echo ============================================================
echo   6. OUVRIR GITHUB
echo ============================================================
echo   !DEPOT!
echo.
echo   1. Le depot
echo   2. Les branches
echo   3. Les commits de !BRANCH!
echo   4. Comparer !BRANCH! avec main
echo   0. Retour
echo.
choice /c 12340 /n /m "Ton choix : "
set "G=!ERRORLEVEL!"
if "!G!"=="1" start "" "!DEPOT!"
if "!G!"=="2" start "" "!DEPOT!/branches"
if "!G!"=="3" start "" "!DEPOT!/commits/!BRANCH!"
if "!G!"=="4" start "" "!DEPOT!/compare/main...!BRANCH!"
exit /b 0

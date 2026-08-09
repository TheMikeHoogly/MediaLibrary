# Prompt de démarrage — à coller dans une nouvelle conversation

> Copie tout le bloc ci-dessous dans une nouvelle conversation Cowork, après
> avoir connecté le dossier `C:\Prog\Claude\MediaLibrary`.
>
> Dernière mise à jour : **10 août 2026 (soir) — validation en réel.** **#3 archive
> « (Inconnus) » : ✅ VALIDÉ EN RÉEL** (checklist entière passée via Claude-in-Chrome, serveur
> tournant avec le nouveau code — voir bloc #3 ci-dessous). **+ BUG CURATEUR : ✅ VALIDÉ EN
> RÉEL** — saisir un nom neuf depuis « À vérifier » crée bien la fiche `PEOPLE_STORE`
> (`/api/people/list` 342→343). **+ bat `0 - Démarrer le serveur.bat`** : tue l'ancienne session
> (port 8080) puis lance le serveur dans une FENÊTRE SÉPARÉE. **PROCHAIN CHANTIER**, au choix par
> valeur : `/reglages` en **tour de contrôle** (demande Mike — statut des workers ; item 5) —
> renforcé par le constat perf ci-dessous ; activer le géocodage `gps_place` (gestes Mike) ;
> ou item 6 (page « Sujets » unifiée).
>
> **GESTE MIKE — commit/push si pas encore fait.** Le serveur a été redémarré (le code #3 +
> fix curateur tourne, validé). Reste éventuellement à **committer/pousser** le non-commité :
> `server.py` (#3 + fix curateur + `purge_cles_fantomes` + `build_suggestions`),
> `0 - Démarrer le serveur.bat`, `verifier_orphelins.py`, `test_verifier_orphelins.py`,
> `ROADMAP.md`, ce fichier. bat 28 déjà commité/poussé.
>
> **⚠ LEÇON MÉTHODE Claude-in-Chrome (cette session).** Clics et captures ne marchent QUE si
> l'onglet Chrome de `/people` est **au premier plan** (onglet caché → rendu gelé, viewport
> minuscule, **clics ignorés sans erreur**). Vérifier `document.visibilityState` avant de
> conclure. Les mutations = vrais clics UI ; la vérif d'état = `fetch` GET (fiable). `/people`
> rend **~11 300 vignettes d'un coup** (2081 groupes + 342 personnes) = vraie cause des
> lenteurs → argument fort pour l'item 5 (allègement / « centre de tâches »).

---

## ══ #3 — archive « (Inconnus) » : ✅ VALIDÉ EN RÉEL (checklist déroulée) ══

**Besoin (mots de Mike).** Beaucoup de visages proposés dans `/people` sont des personnes
qu'il ne reconnaît pas. Les **archiver sous « (Inconnus) »** pour les sortir de la file
« À vérifier », **afin de les re-tagger correctement** plus tard s'il se souvient d'un nom.

**Décisions confirmées par Mike (10/08).** 1) Persistance : archive **RÉVERSIBLE en base,
SANS XMP**. 2) Structure : **clusters SÉPARÉS** sous une vue « Inconnus ».

**Livré (server.py, écrit sur la machine — non commité, redémarrage requis).**
- Cible **`__inconnu__`** côté visages → champ `inconnu` (miroir animaux). Routage explicite
  dans `attribuer_visages` (plus de collision avec `non_group`), libellé dans `_marquer_visages`.
- **Nommer un cluster lève `inconnu`** (`_nommer_membres_visages`, réversible dans `defaire`).
- Exclusion des archivés de « Groupes à nommer » (`_gather_faces`) ET « À vérifier »
  (`build_suggestions`).
- Vue séparée : `INCONNU_CACHE`/`INCONNU_LOCK`, `_gather_inconnus()`, `build_inconnus()`
  (seuil min=1 → aucun singleton caché), `desarchiver_visages()`. `_invalider_groupes_visages`
  reset aussi `INCONNU_CACHE`.
- Endpoints : `GET /api/people/inconnus` (build paresseux, `at==0` = à (re)construire, vide =
  état valide), `POST /api/people/desarchiver`.
- UI `PEOPLE_PAGE` : bouton « Archiver (inconnu) » sur la carte de groupe + entrée `SPECIAUX_P`
  (sous-ensemble) ; section « Inconnus (archivés) » chargée à la demande (bouton « Afficher »,
  `INCONNU_SHOWN`), `carteInconnu()` (nommer → lève l'archive ; « Réactiver » → `desarchiver`).
- Vérifs faites : `py_compile` vert ; `node --check` vert sur le JS ajouté (carteGroupeP + vue
  Inconnus). Pas de `.bat` touché.

**CHECKLIST — ✅ DÉROULÉE EN RÉEL le 10/08 (soir) sur `/people` (192.168.0.13:8080,
Claude-in-Chrome), serveur redémarré avec le nouveau code :**
1. ✅ « Archiver (inconnu) » sur une carte de groupe → `POST /api/assign` (200), le groupe
   quitte « Groupes à nommer » (2081→2080).
2. ✅ « Afficher » sous « Inconnus (archivés) » → compteur `(1)`, carte « 18 visage(s)
   archivé(s) » avec vignettes + champ *Attribuer* + *Réactiver* ; non reproposé en « À vérifier ».
3. ✅ **Nommer** un groupe d'inconnus (nom neuf de test) → il quitte les inconnus (count→0),
   la personne est créée (`/api/people/list` +1) ; `_nommer_membres_visages` lève bien l'`inconnu`.
4. ✅ « Réactiver » → `POST /api/people/desarchiver` (200), retour dans « Groupes à nommer »
   (2080→2081). **Round-trip sans perte** (count personnes/groupes revenus à l'identique).
5. ✅ Cohabitation OK : cartes de groupe = *Attribuer / Rejeter le groupe / Archiver (inconnu)* ;
   cartes « À vérifier » = *Oui / Aucun / C'est un animal*.
6. ✅ **Fix curateur (nouveau nom)** : saisir un nom neuf depuis « À vérifier » crée bien la
   fiche `PEOPLE_STORE` (la personne apparaît dans `/api/people/list`, 342→343 — exactement ce
   que le bug cassait). Nettoyage post-test via « Gérer → Supprimer » (retour à 342).

> **NUANCE mesurée (pas un bug).** « Archiver » comme « Attribuer 18 » agit sur le **sous-ensemble
> de 18 visages** affiché : le serveur plafonne `membres`/`crops` d'un cluster à 18 (`size` = total
> réel, ex. 63). Cohérent avec tout le curateur. Le nommage/archivage porte donc sur ces 18.
> Reste non exercé formellement : « accepter/corriger un nom **existant** » depuis « À vérifier »
> (même code que le nom neuf, faible risque) et la persistance **après un vrai redémarrage**
> (vérifiée au niveau fiche en base, pas re-testée après reboot).

Repères code (server.py) : `CIBLE_INCONNU`/`CIBLES_SPECIALES` l.~2478 ; `attribuer_visages`,
`_marquer_visages`, `_nommer_membres_visages` (bloc ~2865-2960) ; `_gather_faces`,
`build_clusters`, `_gather_inconnus`, `build_inconnus`, `desarchiver_visages` (bloc ~6720-6970) ;
`build_suggestions` (exclusion `inconnu`) ; `SPECIAUX_P` + `carteGroupeP` + `carteInconnu` +
`loadInconnus` (PEOPLE_PAGE) ; endpoints `_serve_people_inconnus` / `_do_people_post`.

**Discipline (rappel).** Une correction n'est acquise qu'une fois son effet observé en réel —
ici, dérouler la checklist avant de cocher #3 comme fait dans la ROADMAP.

---

> Rappel session 09/08 (matin) : géocodage inverse OFFLINE `gps_place`
> (`geocode.py` + `enrichir_lieux.py` + bat 18 + câblage `server.py`) codé et testé
> en sandbox — reste à activer côté Mike (bloc dédié plus bas).
>
> Note : `main` est **À JOUR** — fusionnée le 09/08 (soir) par `git push origin HEAD:main`
> (fast-forward vers `e6a7564`, qui inclut tout le travail 08/08 + géocodage + le
> renfort `verifier_bat.py`). `main == origin/main == feat/menage-ui-gpu-0807`.

---

Tu reprends le projet **MediaLibrary** — photothèque familiale locale à IA
(~30 000 photos sur NAS, serveur Python stdlib pur, pipelines Ollama/InsightFace/
YOLO/DINOv2, RTX 3050 4 Go). Dossier : `C:\Prog\Claude\MediaLibrary`. Tout
l'état vit dans les fichiers, pas dans l'historique de conversation.

**Lis d'abord, dans l'ordre :** `CLAUDE.md` (règles absolues) → `ROADMAP.md`
(carte des priorités, réécrite au propre le 08/08 — « À faire, par ordre de
valeur ») → `eval/DECISIONS.md` (idées déjà **rejetées sur mesure** :
MegaDescriptor, contre-exemples, `sqlite-vec`, injection des noms au prompt,
détecteur ML de triage) → selon le sujet : `docs/RANGEMENT_2026.md`,
`docs/AUDIT_EXTERNE_2026.md`, et les skills `.claude/skills/` (`monolith-surgery`
**avant tout edit de `server.py`**, `photo-ui` pour l'UI, `vision-eval` pour un
seuil/modèle).

## Garde-fous à ne jamais oublier

- **Les noms attribués par un humain (`personne:` / `animal:`) ne se perdent
  jamais.** Ils vivent dans les XMP des fichiers. Tout déplacement/renommage
  passe par `rekey_everywhere` (transporte tags + visages/personnes/animaux +
  vecteur sémantique).
- **Ne pas ouvrir `photos.db` (WAL) depuis le sandbox Linux** — le serveur (sur
  la machine de Mike) est l'écrivain unique. Les tests qui touchent la vraie base
  la **copient** d'abord. Conséquence : la logique risquée vit dans des **modules
  purs** testables hors machine (`fichiers.py`, `renommage.py`, `interet.py`,
  `tagging_meta.py`…) + `test_*.py`. `server.py` ouvre les stores au niveau module
  → **ne pas l'importer** dans un test du sandbox.
- **Un score parfait est une alarme, un proxy n'est pas le juge.** Vérifier
  l'**effet réel** d'une correction (la notation humaine a renversé « V2 ≈ V0 » ;
  trois diagnostics ont été justes sans traiter la vraie cause).
- **Zéro dépendance au démarrage** (imports lourds paresseux) ; côté client,
  **zéro build, zéro npm**.
- **`server.py` fait ~9 400 lignes.** Charge `monolith-surgery` avant d'y toucher.
  Toute modif risquée passe par une **branche**. Garde-fous : `python
  verifier_ui_tokens.py` (0 interdit dur) pour l'UI, `python verifier_bat.py`
  (**ASCII pur**, lire sa sortie) pour les `.bat`, `py_compile` + `test_*.py`.

## Outillage (ce qui marche)

- **Git** marche dans le shell (`origin = TheMikeHoogly/MediaLibrary`). Commits au
  fil de l'eau sur une branche. Si un verrou périmé bloque (`.git/*.lock`), demander
  une fois `mcp__cowork__allow_cowork_file_delete` puis `rm -f .git/*.lock`.
  **`git push` et les merges dans `main` sont des gestes de Mike** (le sandbox ne
  pousse pas ; et merger en local échoue tant que le serveur verrouille `server.py`
  — préférer éditer en place sur une branche, puis Mike pousse/merge). Éditer un
  fichier ouvert par le serveur marche (écriture en place), mais **un `git checkout`
  qui doit réécrire `server.py` échoue** → faire avancer un ref par `update-ref` +
  `git reset` si besoin (cf. session 07/08).
- **Tester en RÉEL le site** : le serveur tourne chez Mike (**192.168.0.13:8080**).
  Utiliser **Claude-in-Chrome** (`mcp__claude-in-chrome__*`) pour naviguer,
  screenshoter, exécuter du JS de diagnostic (`fetch('/api/...')`, aller-retours
  réversibles sur les vraies données). C'est ce qui a trouvé des bugs que les
  maquettes cachaient. **Le serveur ne recharge pas le code à chaud** : une modif de
  `server.py` n'est active qu'après un **redémarrage** (`0 - Démarrer le serveur.bat`).
- **Computer-use** (`mcp__computer-use__*`) disponible pour lire l'écran de Mike
  (ex. Gestionnaire des tâches pour la RAM). `request_access` d'abord.
- **Avancer en autonomie** : quand Mike dit « continue », il n'est souvent pas au
  PC — avancer sans question bloquante, décisions raisonnables, aller au bout.
- **Connecteurs** : Figma connecté. Les autres (Slack, Notion…) demandent un OAuth
  côté claude.ai. Pour un besoin externe ponctuel (ex. géocodage inverse des GPS),
  chercher d'abord au **registre MCP** avant d'écrire du code jetable.
- **Multi-appareils (Dispatch)** : Mike peut piloter depuis téléphone ou PC, mais le
  travail s'exécute **sur le PC** (mêmes fichiers, même serveur). PC allumé + Claude
  Desktop ouvert + dossier connecté requis.

## ══ ÉTAT AU 9 AOÛT 2026 (soir) — LIRE EN PREMIER ══

### 1. Propositions « À vérifier » SANS IMAGE sur `/people` — fix IMPLÉMENTÉ 10/08 (reste commit+redémarrage Mike)

**FAIT le 10/08 (édité en place, NON commité — la choréo git est un geste de Mike).**
- `server.py`, `build_suggestions()` : garde-fou clés fantômes. Juste avant l'auto-attribution
  et l'ajout d'une proposition `add`, on écarte un candidat dont `_resolve_key(k)` n'est pas un
  fichier — **uniquement si la racine est joignable** (probe `_racine_ok(UPLOAD_DIR)` + ancre
  pour les clés absolues), jamais quand le NAS est déconnecté (sinon tout passerait pour
  disparu). Un seul `is_file()` par vrai candidat. Ne touche QUE des propositions : aucun nom
  perdu. `py_compile` OK.
- `verifier_orphelins.py` (read-only) : ajout de `basename_cle()` + `est_fantome()` et
  classement des orphelins en **FANTOME** (doublon malformé dont un sibling présent partage le
  basename — cas ARZOPA, purge sans risque) vs **disparu**. Rapport enrichi (« dont FANTOMES :
  N »). `test_verifier_orphelins.py` 19/19 (bac à sable).
- **Reste (Mike) :** `27 - Commit de session.bat` → push, **redémarrer** le serveur, vérifier
  que les 3 cartes ARZOPA sans vignette de `/people` disparaissent ; puis
  `.venv\Scripts\python.exe verifier_orphelins.py --filtre ARZOPA` pour chiffrer les fantômes,
  et décider de la purge (cause racine — étendre le nettoyage de `FACE_STORE`).

**Diagnostic d'origine (conservé) :**

**Symptôme (constaté par Mike).** Dans la file « À vérifier » de `/people`, certaines
cartes s'affichent sans vignette (image cassée), à côté d'autres qui en ont une.

**Cause, VÉRIFIÉE en direct sur le serveur (Chrome, `/api/curator/list`).** Ce sont des
**clés fantômes** dans `FACE_STORE` : le même fichier ARZOPA existe deux fois, sous une
clé correcte (`ads\ARZOPA\5bBcn6-…JPG` → vignette 200) ET une clé malformée
(`ARZOPA/5bBcn6-…JPG`, slash avant, sans la racine `ads\`). `_resolve_key` (server.py
l.1345 : clé absolue = chemin direct, sinon `UPLOAD_DIR / clé`) pointe la clé fantôme
vers `Uploads/ARZOPA/…` qui n'existe pas → `/api/facecrop` renvoie **404** → image
cassée. Sur 19 propositions actuelles, **3 sont dans ce cas, toutes ARZOPA**.
`build_suggestions()` (server.py ~l.7282) propose **toute** empreinte de `FACE_STORE`
**sans jamais vérifier que le fichier se résout** → les clés mortes passent dans la file.
C'est le résidu du cas « ARZOPA » : `forget_everywhere` ne purge que les clés dont le
fichier a *disparu d'un dossier scanné*, pas une clé fantôme qui n'a jamais correspondu
à un chemin réel.

**Fix proposé (à IMPLÉMENTER, non fait — Mike n'a pas encore dit go) :**
1. **Garde-fou dans `build_suggestions()`** : ignorer un item `add` si
   `_resolve_key(k)` n'est pas un fichier. Coût = un `is_file()` local par visage
   candidat, **aucun risque de perte de nom** (ça ne touche que des propositions, jamais
   un nom confirmé). `monolith-surgery` avant d'éditer `server.py` ; redémarrage = geste Mike.
2. **Cause racine** : étendre `verifier_orphelins.py` (read-only) pour compter aussi les
   clés qui **ne se résolvent pas** (pas seulement les fichiers disparus), puis purger ces
   clés fantômes ARZOPA de `FACE_STORE`.

### 2. `verifier_bat.py` renforcé — FAIT, commité/poussé (commit `e6a7564`)

Il vérifiait l'ASCII mais **pas** les fins de ligne. Ajout d'un contrôle : un `.bat` en
**LF pur** (ou mixte) est signalé (« fins de ligne : N ligne(s) en LF au lieu de CRLF »),
même classe de bug silencieux que le non-ASCII. Sert aussi de hook `PostToolUse` → bloque
désormais à l'écriture un `.bat` en LF. Testé (flag un `.bat` LF, laisse passer les CRLF).

### 3. RÉSOLU (10/08) : `28 - Fusionner la branche dans main.bat` — « qui était inattendu »

**Vraie cause (mesurée, ce n'était PAS l'eol).** Deux `echo` À L'INTÉRIEUR d'un bloc
`if errorlevel 1 ( … )` contenaient des **parenthèses non échappées** : L101
`echo   Il faut une vraie fusion (merge commit ou rebase), qui` (bloc 96-113) et L145
`echo Relance le script (il refera le fetch et le controle).` (bloc 143-148). Dans un
bloc `( )`, un `)` nu dans un `echo` **ferme le bloc prématurément** (le `(` en milieu de
texte, lui, est ignoré — asymétrie du parseur). Le mot qui suivait, `qui`, devenait le
token inattendu → message littéral « **qui** était inattendu ». Le bloc plantait au PARSE,
donc quelle que soit la valeur d'errorlevel (la condition n'a pas besoin d'être vraie).

**Comment on l'a trouvée — la bonne méthode après 2 fausses pistes (eol, puis parenthèses
« équilibrées »).** On avait écarté à tort : ASCII (verifier_bat OK), octets cachés (blob
propre), eol (mesuré `CR=172 LF=172` = CRLF propre — l'eol n'était PAS le problème), et
une simu de parenthèses qui les comptait *équilibrées* (elle modélisait mal cmd : le `(`
d'un echo ne compte pas, le `)` si). Décisif : rejouer le VRAI bat 28 **écho activé**
(`Get-Content … | Select-Object -Skip 1 | Set-Content _dbg28.bat; cmd /c _dbg28.bat`) →
la dernière commande affichée avant l'erreur a nommé la ligne. Leçon : quand la déduction
statique tourne en rond, **instrumenter et mesurer sur la vraie machine** (echo on).

**Correctif appliqué (natif Windows, CRLF préservé) — vérifié `verifier_bat.py` vert :**
échapper les parens des deux lignes en `^(` `^)`, via
`[IO.File]::ReadAllText`/`WriteAllText` + `.Replace(...)` (jamais depuis le sandbox).
bat 28 relancé sans erreur, `main` fusionnée.

**⚠ LEÇON EOL (toujours valable pour l'écriture des `.bat`).** Écrire/convertir un `.bat`
**depuis le sandbox** n'atteint PAS Windows en CRLF propre. Corriger un `.bat` **côté
Windows** (PowerShell `ReadAllText`/`WriteAllText`). Ne **jamais**
`open(f,'wb').write(open(f,'rb').read())` (`wb` tronque avant que `rb` lise → vide le
fichier). Garde-fou : `verifier_bat.py` signale désormais aussi le LF nu.

---

## ══ ÉTAT AU 8 AOÛT 2026 — LIRE EN PREMIER ══

### Session git + cross-pipeline (dernière en date)

- **`feat/menage-ui-gpu-0807` a été mergée dans `main`** par fast-forward côté remote
  (nouveau `28 - Fusionner la branche dans main.bat` : `git push origin HEAD:main` sans
  checkout local → contourne le verrou `server.py`). `main` == `origin/main` à jour.
- **Outillage git ajouté** : `28 - Fusionner…bat`, `docs/GIT_WORKFLOW.md` (workflow
  complet documenté), et un **garde-fou anti-verrou** dans les bats 27 **et** 28 (détecte
  `.git\index.lock`/`HEAD.lock`, propose de le supprimer après confirmation — cause
  habituelle : GitKraken Desktop ouvert sur le dépôt). `.gitignore` : artefacts
  `plan_renommage`/`undo_renommage` ignorés.
- **GitKraken** : compte + CLI (`gk`) authentifiés côté Mike, MAIS le **connecteur MCP**
  refuse encore (auth `context=mcp` distincte, et le connecteur se déconnecte/reconnecte
  en boucle dans la preview). Config prête ; à retester « teste GitKraken » quand stable.
  Le `.bat` 28 fait le merge sans GitKraken de toute façon.
- **Orphelins de suppression (BUG trouvé ET corrigé 08/08).** `_sync_dir` étape 4 ne
  purgeait que le TagStore ; visages/animaux/vecteurs d'un fichier disparu restaient
  (« ARZOPA »). Diagnostic `verifier_orphelins.py` (read-only) : **4569 orphelins, 0
  nommé**. Correctif en place : `vectors.delete_all` (+test_vectors 34/34) + `forget_everywhere`
  câblé dans `_sync_dir` étape 4, noms préservés (fiches keyées par nom). **Reste Mike** :
  committer + **redémarrer** (le scan de démarrage purge le backlog en cascade), puis
  relancer `verifier_orphelins.py` → doit tomber à ~0. Détections : `server.py`
  (`forget_everywhere`, `_sync_dir`), `vectors.py` (`delete_all`).
- **Garde SigLIP humain/animal (item 12b) — MESURÉ 08/08 → REJETÉ tel quel.**
  `verifier_visages.py` a tourné : pic VRAM 2707 Mo OK, mais **18 % de faux rejets**
  (vrais humains endormis/près d'un chat lus « cat »), scores chevauchants → pas de
  seuil global viable (détail `eval/DECISIONS.md`). **Ne pas câbler.** Si on y revient :
  re-mesurer sur découpes SANS marge (0,3 embarque le chat voisin). Remède Mutz retenu =
  l'action manuelle « C'est un animal » déjà livrée.
- **Cross-pipeline (ROADMAP item 2) — CODÉ, à valider en réel.** `server.py`, UI seule :
  `/people` option **« C'est un animal (pas une personne) »** (`SPECIAUX_P` → `__pas_visage__`) ;
  `/pets` miroir **« C'est une personne (pas un animal) »** (`SPECIAUX` → `__pas_animal__`).
  `py_compile` OK. **RESTE (geste Mike) : commit (bat 27) + push + REDÉMARRER le serveur +
  tester** sur le groupe Mutz. Non commité au moment d'écrire (le sandbox n'a pas les droits
  d'écrire refs/locks dans `.git` — édition de fichiers OK, choréo git = côté Mike).

### Branches et commits en attente

- **`main` == `origin/main`** — porte tout l'intégré jusqu'à la session « ménage »
  (mergée le 08/08 par fast-forward via `28 - Fusionner la branche dans main.bat`).
- **`feat/menage-ui-gpu-0807`** (branche courante, exécutée par le serveur) — porte,
  AU-DESSUS de `main`, le travail de cette 2ᵉ session. Déjà commité : garde-fou
  anti-verrou des bats + workflow git. **NON commité au moment d'écrire** (la choréo
  git est un geste de Mike — le sandbox ne peut pas écrire dans `.git`) :
  - `server.py` — action cross-pipeline (`SPECIAUX_P`, curateur `.anim`), + `forget_everywhere`
    câblé dans `_sync_dir` étape 4 ;
  - `vectors.py` — `delete_all` (+ `test_vectors.py` 34/34) ;
  - `verifier_visages.py`, `verifier_orphelins.py` + leurs tests (15/15 chacun) ;
  - `docs/GIT_WORKFLOW.md`, `.gitignore`, et ROADMAP/DECISIONS/ce fichier.
- **Publier** : `27 - Commit de session.bat` (répondre N, message, push), puis — une
  fois validé en réel — `28 - Fusionner la branche dans main.bat`.

### Diagnostic GPU / RAM (08/08, mesuré — pas de bug de device)

Le GPU **fait** le tagging (Ollama résident ~3,5 Go, util en **rafales ~91 %**). Le
frein n'est pas la sélection de device mais : **(1) la RAM** — machine chargée, RAM
libre ~1,4 Go proche du plancher `REEMBED_MIN_RAM_GB=1.5` qui déclenche l'auto-bridage
(`system_busy`) ; le serveur lui-même est sain (~1,95 Go), le reste est Claude Desktop
(~1 Go), Chrome, Defender, apps de fond. **(2) l'I/O NAS** par photo (~20 s hors-GPU).
Levier sans code : **fermer les apps de fond** pendant un gros run. Sur 4 Go partagés,
Ollama + vision ne tiennent pas ensemble sur le GPU → `FACE_USE_GPU=False` volontaire.

### GÉOCODAGE INVERSE `gps_place` — codé le 09/08, À ACTIVER (gestes Mike)

Tout est écrit et testé en sandbox ; il reste 3 gestes sur la machine de Mike (réseau
requis pour le seul téléchargement du gazetteer, une fois) :

1. **Télécharger le gazetteer (une seule fois)** : lancer `18 - Telecharger le gazetteer
   (geocodage).bat`. Il pose `cities1000.txt` (~13 Mo, GeoNames) dans le dossier du projet.
2. **Lancer le batch** (dans le `.venv`) : `.venv\Scripts\python.exe enrichir_lieux.py`
   (aperçu, dry-run — montre les clusters nommés) ; si le plan est bon,
   `.venv\Scripts\python.exe enrichir_lieux.py --ecrire`. Ça écrit `gps_places.json`
   (clé→lieu) et ajoute les nouveaux lieux à `lieux.txt` (backup `.bak`, bloc marqué
   supprimable — **réversible**).
3. **Regénérer le plan de renommage + redémarrer** : au prochain démarrage, ou via
   `/reglages` → « Renommage intelligent » → Générer le plan, les noms des photos GPS
   gagnent leur segment de lieu (ex. `…_bremblens_…`). Le serveur relit `gps_places.json`
   automatiquement (cache mtime).

Détails d'archi et pourquoi offline : voir ROADMAP item 3. Pièces : `geocode.py` (pur,
35/35), `enrichir_lieux.py` (23/23), `test_*` associés, `18 - …bat` (ASCII vérifié),
`server.py` (`gps_places_connus` + `construire_plan(..., gps_places=…)`). **Le serveur
n'importe pas `geocode`** (lit juste le JSON) → zéro dépendance ajoutée. Non commité au
moment d'écrire (choréo git = geste Mike) : `geocode.py`, `test_geocode.py`,
`enrichir_lieux.py`, `test_enrichir_lieux.py`, `18 - Telecharger le gazetteer
(geocodage).bat`, `server.py`, `ROADMAP.md`, ce fichier. `.gitignore` : penser à ignorer
`cities1000.txt` et `gps_places.json` (artefacts locaux/générés — voir plus bas).

### Session 08/08 — clôturée (rappel, plus rien à faire)

Committée + poussée + serveur redémarré. Le fix orphelins (`forget_everywhere`) est actif
(le log de maintenance montre « … entrée(s) de fichiers disparus retirée(s) »). L'action
cross-pipeline « C'est un animal » / « C'est une personne » est en prod : la valider à
l'occasion sur le groupe **Mutz** (`/people`) reste utile mais non bloquant. Garde SigLIP
humain/animal : **REJETÉE** (mesurée, 18 % de faux rejets — ne pas recâbler).

### Gestes de fond, toujours prioritaires (la valeur est dans la DONNÉE)

- **Confirmer ~100 propositions de visages** dans `/people` (priorité n°1, vérité
  terrain à 0,8 %, tri clavier prêt).
- **Appliquer les lots de renommage** (`/reglages` → « Renommage intelligent », plan = **2114**).
- **Mesurer le gain tagging** (débit tag/min) après le redémarrage.

### Prochains code utiles (par valeur, cf. `ROADMAP.md`)

Géocodage inverse : **codé + carte câblée**, reste à activer (bloc ci-dessus). Le popup de
la Carte affiche déjà 📍 le lieu dès que `gps_places.json` existe (rien sinon). Ensuite :
fait `image_type` (SigLIP) pour enrichir encore les noms — mais discipline `vision-eval`
(protocole pré-enregistré + mesure VRAM AVANT câblage, cf. bancs triage/visages) ; partage
du vocabulaire de recherche à la Carte ; redesign étape B (centre de tâches, registre
papier) ; page « Sujets » unifiée ; garde humain/animal seulement si **re-mesure sur
découpes SANS marge** ; HDBSCAN / AdaFace en réserve.

Après lecture : dis **« Go »** pour un débrief + prochaines étapes (protocole
`CLAUDE.md`), ou attaque directement le point le plus utile en proposant un plan
court avant d'écrire du code.

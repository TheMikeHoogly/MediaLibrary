# Prompt de démarrage — à coller dans une nouvelle conversation

> Copie tout le bloc ci-dessous dans une nouvelle conversation Cowork, après
> avoir connecté le dossier `C:\Prog\Claude\MediaLibrary`.
>
> Dernière mise à jour : **9 août 2026 (soir)**. Trois choses cette session :
> (1) diagnostic des **propositions sans image** sur `/people` ; (2) `verifier_bat.py`
> renforcé (contrôle des fins de ligne) — commité/poussé ; (3) galère `.bat` LF/CRLF
> encore ouverte. Détail dans la section « ÉTAT AU 9 AOÛT (soir) » plus bas.
>
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

### 1. Propositions « À vérifier » SANS IMAGE sur `/people` — diagnostiqué, fix NON câblé

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

### 3. BLOCAGE OUVERT : `28 - Fusionner la branche dans main.bat` — « qui était inattendu »

**Symptôme.** bat 28 plante juste après `echo Recuperation de l'etat distant (git
fetch)...` avec l'erreur cmd française « qui était inattendu » (= un token inattendu, un
`)` typiquement), dans le bloc `if errorlevel 1 (…)` lignes 86-90.

**Écarté (mesuré).** (a) **Non-ASCII** : le fichier est ASCII pur (`verifier_bat.py` OK).
(b) **Contenu** : les octets commités (git HEAD) sont propres, structure identique aux
blocs `if errorlevel 1 (…)` qui, eux, parsent bien (l.24, 73) ; et **bat 28 tournait le
08/08**. (c) **bat 27**, lui, tourne (CRLF natif) et a des blocs identiques.

**Ce qui reste suspect : les fins de ligne côté Windows de bat 28.** cmd.exe déraille sur
les blocs `(` multi-lignes en LF. MAIS `git checkout -- *.bat` (censé appliquer
`eol=crlf`) n'a **pas** débloqué — donc soit l'eol n'est pas réappliqué sur la machine de
Mike, soit c'est autre chose.

**⚠ LEÇON DE MÉTHODE (importante).** Écrire/convertir un `.bat` **depuis le sandbox**
n'atteint PAS Windows comme un CRLF propre (translation de fins de ligne du montage,
voire double-CR). **Ne jamais corriger l'eol d'un `.bat` depuis le sandbox** — le faire
côté Windows (git, ou PowerShell natif). Et **ne jamais** utiliser
`open(f,'wb').write(open(f,'rb').read())` : `wb` tronque le fichier AVANT que `rb` ne
lise → il **vide** le fichier (ça a vidé les 14 `.bat`, restaurés ensuite par
`git checkout -- *.bat`).

**Prochaines étapes bat 28 (au choix, côté Mike/Windows) :**
- **Contourner (le plus simple)** : `git push origin HEAD:main` fait la fusion sans bat 28.
- **Diagnostiquer l'eol réel** (PowerShell, natif Windows) :
  `$b=[IO.File]::ReadAllBytes("28 - Fusionner la branche dans main.bat"); "CR=$(($b|?{$_-eq13}).Count) LF=$(($b|?{$_-eq10}).Count)"`
  (CR<LF ⇒ LF nu ; CR>LF ⇒ double-CR).
- **Forcer un CRLF propre** (PowerShell, lit TOUT avant d'écrire) :
  `Get-ChildItem *.bat|%{ $t=([IO.File]::ReadAllText($_.FullName)) -replace "`r","" -replace "`n","`r`n"; [IO.File]::WriteAllText($_.FullName,$t) }` puis `python verifier_bat.py`.
- **Si ça résiste toujours** : réécrire les blocs `if errorlevel 1 (…)` de bat 28 en
  `if errorlevel 1 goto :label` (ou `cmd || ( … )` sur UNE ligne), immunisés contre l'eol
  — mais l'écrire **côté Windows**, pas depuis le sandbox.

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

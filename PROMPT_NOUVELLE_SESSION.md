# Prompt de démarrage — à coller dans une nouvelle conversation

> Copie tout le bloc ci-dessous dans une nouvelle conversation Cowork, après
> avoir connecté le dossier `C:\Prog\Claude\MediaLibrary`.
>
> Dernière mise à jour : **7 août 2026** (session « affichage + renommage intelligent » : renommage complet et vérifié en réel, prêt à appliquer).

---

Tu reprends le projet **MediaLibrary** — photothèque familiale locale à IA
(~30 000 photos sur NAS, serveur Python stdlib pur, pipelines Ollama/InsightFace/
YOLO/DINOv2, RTX 3050 4 Go). Dossier : `C:\Prog\Claude\MediaLibrary`. Tout
l'état vit dans les fichiers, pas dans l'historique de conversation.

**Lis d'abord, dans l'ordre :** `CLAUDE.md` (règles absolues) → `ROADMAP.md`
(état + chantiers par valeur) → `eval/DECISIONS.md` (idées déjà **rejetées sur
mesure** : MegaDescriptor, contre-exemples, `sqlite-vec`, injection des noms au
prompt) → selon le sujet : `docs/RANGEMENT_2026.md`, `docs/AUDIT_EXTERNE_2026.md`,
et les skills `.claude/skills/` (`monolith-surgery` **avant tout edit de
`server.py`**, `photo-ui` pour l'UI, `vision-eval` pour un seuil/modèle).

## Garde-fous à ne jamais oublier

- **Les noms attribués par un humain (`personne:` / `animal:`) ne se perdent
  jamais.** Ils vivent dans les XMP des fichiers. Tout déplacement/renommage
  passe par `rekey_everywhere` (transporte tags + visages/personnes/animaux +
  vecteur sémantique).
- **Ne pas ouvrir `photos.db` (WAL) depuis le sandbox Linux** — le serveur (sur
  la machine de Mike) est l'écrivain unique. Les tests qui touchent la vraie base
  la **copient** d'abord. Les passes Ollama/GPU tournent chez Mike, via les `.bat`
  numérotés (**ASCII pur** : `python verifier_bat.py` et **lire sa sortie**).
- **Un score parfait est une alarme, un proxy n'est pas le juge.** Vérifier
  l'**effet réel** d'une correction (la notation humaine a renversé « V2 ≈ V0 »).
- **Zéro dépendance au démarrage** (imports lourds paresseux) ; côté client,
  **zéro build, zéro npm**.
- **`server.py` fait ~9 400 lignes.** Charge `monolith-surgery` avant d'y toucher.
  Toute modif risquée passe par une **branche**. Garde-fou UI : `python
  verifier_ui_tokens.py` (0 interdit dur attendu). Tests : `test_*.py`.

## Outillage (ce qui marche depuis la session)

- **Git autonome** : `git` marche dans le shell (`origin =
  TheMikeHoogly/MediaLibrary`). Commits au fil de l'eau. Si un verrou périmé
  bloque (`.git/*.lock`), demander une fois `mcp__cowork__allow_cowork_file_delete`
  puis `rm -f .git/*.lock`. **`git push` impossible depuis le sandbox** (proxy) —
  **c'est Mike qui pousse** depuis sa machine.
- **Tester en RÉEL le site** : le serveur tourne chez Mike (192.168.0.13:8080).
  Utiliser **Claude-in-Chrome** (`mcp__claude-in-chrome__*`) pour naviguer,
  screenshoter, exécuter du JS de diagnostic (ex. `fetch('/api/...')`). C'est ce
  qui a trouvé des bugs que les maquettes cachaient. Aperçus visuels rapides :
  outil `mcp__visualize__show_widget` (maquette, pas le vrai site).
- **Avancer en autonomie** : quand Mike dit « continue », il n'est souvent pas au
  PC — avancer sans question bloquante, prendre les décisions raisonnables, aller
  au bout de la roadmap. Redémarrer le serveur = arrêter/relancer
  `0 - Démarrer le serveur.bat` (Mike, pas de git à taper si le dossier est déjà
  sur la bonne branche).
- **Figma** connecté (testé `whoami`), disponible pour bâtir la bibliothèque de
  composants « chambre noire » si on veut la source de vérité du design. Les
  autres connecteurs (Slack, Notion…) demandent un OAuth côté claude.ai.
- **Travail multi-appareils (Dispatch).** Mike peut lancer/poursuivre une session
  depuis son **téléphone** ou son **PC** : c'est la même conversation continue, mais
  **le travail s'exécute sur le PC** (fichiers locaux du dossier `MediaLibrary`,
  connecteurs, Chrome). Prérequis : **PC allumé + Claude Desktop ouvert**, le dossier
  `C:\Prog\Claude\MediaLibrary` connecté à la session Cowork, et l'accès aux fichiers
  activé dans Dispatch. Conséquence pratique : que la consigne vienne du PC ou du
  mobile, c'est le **même dépôt local** et le même serveur (chez Mike) — `git push`
  reste un geste que **Mike** fait sur le PC.

## ══ ÉTAT AU 7 AOÛT 2026 — LIRE EN PREMIER ══

### Branches (IMPORTANT)

- **`main`** porte le travail des sessions précédentes (renommage, affichage…).
- **`integration-2026-08-07`** = branche de test de la session du 07/08 (soir).
  Elle **merge deux correctifs** prêts à valider en réel :
  - `feat/pets-rejeter-groupe` (`868fde1`) — bouton « Rejeter le groupe » sur `/pets`.
  - `fix/curateur-faux-positifs` (`0347793`) — carte « Faux positif ? » : option
    « C'est correct » + les mêmes propositions ne reviennent plus.
  - + l'outil `27 - Commit de session.bat`.
  **Pour tester les deux d'un coup : `git checkout integration-2026-08-07` puis
  redémarrer le serveur.** Si OK → merger `integration-2026-08-07` dans `main` +
  `git push` (geste de Mike).
- `git push` impossible depuis le sandbox — **c'est Mike qui pousse**. Vérifier
  `git status` / `origin/main` en début de session.
- **Fin de session** : lancer `27 - Commit de session.bat` (branche + add +
  commit + push, ASCII pur) ; Claude met à jour ROADMAP.md + ce fichier.

### Fait le 07/08 (soir) — sur `integration-2026-08-07`, À VALIDER EN RÉEL

- **Carte Animaux (`/pets`) : bouton « Rejeter le groupe »** à parité avec les
  visages. Backend : cible `__non_group__` → flag `non_group` réversible (distinct
  de `suspect`/`inconnu`), exclu du regroupement. `868fde1`.
- **Curateur « Faux positif ? » (`/people`) : corrigé.** Le backend
  `curator_reject` (marque `confirmed` → plus jamais reproposé) existait mais l'UI
  ne l'appelait jamais pour les faux positifs ; re-taguer le même nom tombait sur
  un no-op muet → la même proposition revenait sans fin. Désormais 3 actions
  claires : **« ✓ Oui, c'est X »** (confirme, ne plus signaler + enrichit la
  signature), **« ✗ Retirer le tag »** (vrai faux positif), **« c'est… »**
  (corrige : retire l'ancien tag erroné). Clavier : Espace/O = garder, X = retirer.
  Backend durci (`attribuer_visage`) : re-confirmer = confirmé ; corriger/pas-un-
  visage retire le tag erroné. `0347793`. **Repro logique 4/4** ; à valider en réel.
- **Outil `27 - Commit de session.bat`** (branche + add + commit + push, ASCII pur).

### Fait cette session (03-07/08) — LE NEUF

- **Renommage intelligent (point 20) : COMPLET et vérifié en réel — PRÊT À
  APPLIQUER (Mike n'a pas encore lancé de lot).** Flux de bout en bout dans
  `/reglages` → Maintenance :
  - **Générateur** `plan_renommage.py` (pur, `test_plan_renommage.py` **9/9**) +
    `server.generer_plan_renommage()` (in-process, lecture seule) → écrit
    `docs/plan_renommage.{json,md}`. Ne cible QUE les **noms bruts**
    (`est_nom_brut` : Screenshot_/VideoCapture_/IMG_/-WA/Scan_/Photo0#/hash) ;
    laisse les noms déjà datés. **Décisions Mike** : (a) noms bruts seulement ;
    (b) **ne pas** renommer les fichiers **sans date fiable** (pas de `00000000_`) ;
    (c) **forcer le français** dans le sujet quand la description IA déborde en
    anglais (kw_fr) ; (d) suffixe de collision **lisible** `-2/-3` (pas un hash).
  - **Applicateur in-process réversible** `appliquer_renommage(limite, dry)` :
    renomme EN PLACE + `rekey_everywhere` (aucun nom humain perdu) + **journal
    undo** ; garde-fous : source existe, cible n'existe PAS (jamais d'écrasement),
    clé cible absente de l'index, **par lots** (`RENOMMAGE_LOT=200`),
    `annuler_renommage()` idempotent. Endpoints `POST /api/maint/rename-{check,
    apply,undo}` + boutons **Vérifier à blanc / Appliquer un lot / Annuler**.
  - **Décision de conception** : application **IN-PROCESS** → **PAS besoin
    d'arrêter le serveur** (le « serveur arrêté » des `.bat` vient de ce qu'ils
    ouvrent `photos.db` en 2ᵉ processus ; SQLite = 1 écrivain).
  - **Vérifié en réel (Chrome + lecture de `docs/`)** : plan = **2114 à renommer**
    (1531 dates précises YYYYMMDD, 583 année-seule YYYY0000), 0 nom `00000000`,
    « à blanc » = 2114 applicables / 0 sauté. **Reste : Mike applique les lots**
    (Vérifier → Appliquer un lot → contrôler NAS → répéter ; Annuler si besoin).
  - Note dates : `resolve_datestamp` priorise l'**EXIF `taken`** ; sur ces 2114
    bruts l'EXIF est absent (captures/WhatsApp/exports réduits) → date du nom
    (1531) ou année du dossier (583). Correct et attendu.
- **Correctif date renommage** : `path_year()` ne scanne plus que le **dossier**
  (jamais le nom) — un `IMG_1998` n'est plus lu comme l'année 1998.
- **Affichage harmonisé + tri chronologique réversible** (`feat/affichage-detail`) :
  galerie `GALLERY_PAGE` (couvre Galerie/Dossiers/Uploads) — bouton **Date** trie
  sur la **date de prise** (`taken`, repli `mtime`), **du plus ancien au plus
  récent par défaut, reclic pour inverser** (flèche ↑/↓) ; **Nom** idem (A-Z/Z-A) ;
  le diaporama **Démo** suit l'ordre courant de la planche. Fiches détail
  Animaux/Personnes : chronologique ascendant ; **chargement fiabilisé** (openCat
  vérifie `r.ok` + bouton **Réessayer**, `_serve_cat_photos` ne renvoie plus de
  500 non-JSON — corrige l'« Erreur de chargement » de Caline sous charge) ; menu
  `d-mode` lisible.
- **Page Animaux** (`fix/pets-names-lazy`) : port du correctif `/people` (tempête
  de `/api/names`) — `listeProps` au **focus** + **dédup in-flight** de
  `chargerNoms`.
- **Triage (point 21) = MERGÉ (`4cb9aef`)** — filtre par motif + suppression
  réversible dans la galerie `/files` (session précédente).

### Rangement par année (point 19) : FAIT ET APPLIQUÉ (03/08)

Appliqué en réel par Mike, index re-clé et stable. `_A TRIER` ne contient presque
plus que des fichiers sans date ; les rebuts datés sont dans les dossiers année.

### Fait sessions précédentes (01-02/08) — rappel

- **Redesign « chambre noire » — étape A (tokenisation) : les 7 pages + la barre
  de nav.** Couleurs/polices en dur → tokens `ui/tokens.css`. Sémantique des
  accents : **fixateur** (teal) = sélection/filtre actif ; **veilleuse** (orange)
  = IA en cours/focus ; **encre** (rouge) = destructif ; **papier** = principal +
  onglet nav actif. Garde-fou `verifier_ui_tokens.py` (**0 interdit dur** sur les
  10 constantes de page).
- **Redesign — étape B (structurel)** : **planche contact** (`GALLERY .grid` en
  `auto-fill`+`clamp()` + `content-visibility`) ; **View Transitions**
  (`@view-transition` dans `base.css`) ; modale « nommer rapidement » sur
  **papier** (concept deux registres) ; **tri au clavier** du curateur `/people`
  (Espace/Entrée = oui, X = non, Z = annuler, lettre = corriger — sert la
  **priorité n°1** : confirmer vite ~100 propositions).
- **Correctifs tagging** (aussi sur `main`) : `/api/names` n'était plus tronqué à
  `[:40]` (Mathilde, 110 photos, redevenait « Nouveau ») → `[:2000]` ;
  `scan_uploads` scanne enfin les **sous-dossiers d'Uploads** (`rglob`, ARZOPA
  n'était jamais tagué). Diagnostiqués **en direct** via Chrome.
- **Gestion de fichiers sur `/browse`** (point 18) : `fichiers.py` (pur, testé
  **`test_fichiers.py` 23/23** — dont « aucun nom humain perdu ») + routes
  `/api/files/rename|move|mkdir|delete|undo` (`_do_files_post`, `file_ops()`,
  re-clé via `rekey_everywhere`). Supprimer = **quarantaine réversible**, jamais
  `rm`. UI : rangées sélectionnables + barre d'actions **papier** (couper/coller
  via `sessionStorage`, nouveau dossier, annuler).
- **Centre de contrôle `/reglages`** (onglet ⚙ dans la nav) : hub central.
  « Outils & pages » (liens vers Galerie/Dossiers/Carte/Personnes/Animaux/Upload/
  **Santé** — cette dernière n'était atteignable que par URL) ; état live
  (hw/files/comptes) ; **maintenance** (badge auto/pause, table des étapes,
  actions sûres : lancer un cycle, Pause `MAINT_PAUSED`, recensement, **plan de
  rangement par année**) ; réglages (modèle/versions/seuils/racines) en lecture
  seule. Endpoints `GET /api/maint/status`, `POST /api/maint/{run,toggle,census,
  plan-annee}`.
- **Plan de rangement par année** (point 19, lecture seule) : `rangement_annee.py`
  (pur, testé **10/10**) + `server.generer_plan_annee()` → `_A TRIER` →
  `<base>/AAAA/` via `_best_time`, `_SANS_DATE/` si pas de date fiable. **Ne
  déplace RIEN** — juste `docs/plan_rangement_annee.{json,md}`.
- **Petits bugs corrigés** : champ `.qui` blanc (input sans `type` raté par
  `input[type=text]`) ; bouton « Nommer rapidement » enterré sous 324 cartes
  (section « Groupes à nommer » remontée avant « Personnes nommées »).

### Prochaines étapes, par valeur (roadmap de la suite)

1. **Renommage intelligent (point 20) — FAIT et vérifié, PRÊT À APPLIQUER.** Le
   geste qui reste est **HUMAIN, à Mike** : `/reglages` → Maintenance → **« Plan de
   renommage »** → relire `docs/plan_renommage.md` → **« Vérifier à blanc »** →
   **« Appliquer un lot »** (200, réversible) → contrôler sur le NAS → répéter
   jusqu'à 0 ; **« Annuler »** si besoin. Plan actuel = **2114 à renommer**. **Reste
   code, optionnel/non bloquant** : enrichir les 2 faits `None` — **lieu** par
   géocodage inverse des GPS (684 photos géolocalisées ; **chercher un connecteur
   au registre MCP** avant d'écrire du code jetable) et **type** par SigLIP — pour
   des noms plus riches.
2. **Priorité n°1 reconnaissance — confirmer ~100 propositions** (`/people`, tri
   clavier prêt). Le geste HUMAIN qui vaut plus que tout changement d'algo (vérité
   terrain à 0,8 %). Option code : `1`–`9` = assigner à une personne connue,
   `Maj+clic` = plage.
3. **Harmonisation carte Animaux — ✓ FAIT sur `feat/pets-rejeter-groupe`
   (`868fde1`, 07/08, à valider en réel puis merger).** `carteGroupe` (`/pets`) a
   le bouton visible **« Rejeter le groupe »** à parité avec `carteGroupeP`.
   Backend : cible `__non_group__` pour `attribuer_animaux` → flag `non_group`
   réversible (distinct de `suspect`/`inconnu`) ; `_nommable` le saute, donc le
   regroupement l'exclut — miroir de `_marquer_visages`. UI : `envoyer(cible,
   tous)` sur TOUS les membres + toast d'annulation. `__pas_animal__`/`__inconnu__`
   restaient visibles dans les propositions. Vérifs vertes (`py_compile`,
   `verifier_ui_tokens` 0 dur, repro logique isolée — photos.db WAL non ouvrable
   depuis le sandbox). **RESTE : Mike valide en réel (rejeter un groupe sur
   `/pets`, annuler) + merge.**
4. **Étape B — reste redesign** : registre **papier** sur les cartes de clusters
   toujours visibles (`.cl` /people, `.group` /pets) — gros changement du flux de
   nommage, valider en réel d'abord ; **centre de tâches** remplaçant `#pending`
   (données `hw_state()`/`system_busy()`/files) ; **numéro de vue** sur la planche
   contact. **Affichage** : porter le sélecteur d'ordre réversible (fait sur la
   galerie) aux fiches détail Animaux/Personnes si on veut l'unifier partout.
5. **Triage (point 21) — MERGÉ (`4cb9aef`).** Filtre par motif + suppression
   réversible dans la galerie. Mineurs optionnels notés (`classer_regle` appelé 2×
   quand motif actif ; `except` large qui avale un bug de règle ; undo global).
6. **Édition des réglages depuis `/reglages`** (aujourd'hui lecture seule) : seuils,
   autonomie/cadence de maintenance, racines — avec garde-fous.
7. **Reconnaissance (algo)** : regroupement par **densité** (HDBSCAN / Chinese
   Whispers) au lieu du seuil global ; **AdaFace** sur le ré-embedding des visages
   faibles. La garde AMONT de 12b (`verifier_visages.py`, SigLIP humain vs
   animal/objet) reste à **mesurer** avant activation (`vision-eval`).
8. **Une seule page « Sujets »** (fusion Personnes + Animaux, filtre par type ;
   le lieu comme 3ᵉ facette) — `SubjectStore` déjà unifié.
9. **Éval tagging** (parké, tranché) : (a) mesurer un V2 « assertions sans
   impératif de noms » + fusion programmatique des noms/date/lieu ; (b)
   comparatif de modèles (`gemma4:e2b` FR natif vs `qwen3-vl:2b`) via
   `eval_tagging.py --modele … --variantes V0`, rejeter si le pic VRAM frôle 4 Go.
10. **Multi-utilisateur / foyer partagé** (ROADMAP, futur) : `owner` par racine,
    dédoublonnage scopé, rangement configurable par racine, renommage de racine,
    comptes/droits. Noté pour plus tard.
11. **Bibliothèque Figma** comme source de vérité des composants (optionnel).

### Cap long terme (garder en tête dans l'architecture)

**Multimodalité** : images → **vidéo** → **audio** (dans cet ordre). Plusieurs
briques incluent déjà les vidéos (rangement, dédoublonnage, renommage, vue
Dossiers) ; le pipeline IA ne tague encore que les photos. **Recherche AI** en
langage naturel dans le serveur (« les étés à Bremblens avec Luna ») — c'est là
que la compression de contexte et l'exposition du serveur en MCP prendront sens.

## Référence — chantiers déjà bouclés (rappel)

- **Rangement & dédoublonnage** (`docs/RANGEMENT_2026.md`) : recensement Phase 0
  (34 305 fichiers, 261 groupes de doublons, **8,4 Go**, 12 714 sous `_A TRIER`),
  plan + applicateur + purge **faits, testés, appliqués en vrai (8,4 Go
  récupérés)**. Orchestrateur de maintenance dans le serveur (`maintenance.py`,
  `run_cycle`, autonomie par étape). Point de re-clé unique `rekey_everywhere`
  testé sur copie. Renommage intelligent : cœur déterministe `renommage.py` +
  `renommage_facts.py` + dry-run faits et testés (reste : l'application réelle).
- **Installateur nouveau PC** : `installer.py` + `migrer.py` + `INSTALLATION.md`
  (à valider sur un vrai nouveau PC).
- **Fondations design** : `ui/tokens.css` + `base.css` + `components.css`,
  `ui_shared_css()` injecté par `_send_html`, `bundle.py` → `dist/`,
  `test_ui_bundle.py` 4/4.
- **Reconnaissance** : SigLIP 2 (recherche sémantique), recherche à 3 dimensions
  (qui/où/quoi), reconnaissance animale à 97,4 % rang-1. Correctif SMB Errno 22
  (lecture avec retry) mergé.

Après lecture : dis **« Go »** pour un débrief + prochaines étapes (protocole
`CLAUDE.md`), ou attaque directement le point le plus utile en proposant un plan
court avant d'écrire du code.

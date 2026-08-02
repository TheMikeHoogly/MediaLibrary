# Prompt de démarrage — à coller dans une nouvelle conversation

> Copie tout le bloc ci-dessous dans une nouvelle conversation Cowork, après
> avoir connecté le dossier `C:\Prog\Claude\MediaLibrary`.
>
> Dernière mise à jour : **2 août 2026** (fin de session UI/features).

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

## ══ ÉTAT AU 2 AOÛT 2026 — LIRE EN PREMIER ══

### Branches (IMPORTANT)

- **`integration`** = `main` + TOUT le neuf ci-dessous. **Mike la fait tourner.**
  C'est la branche de test unique. **Reste à valider en réel puis merger dans
  `main` et pousser.**
- `main` = les correctifs de tagging seuls. `feat/file-ops` et
  `feat/control-center` = les deux features isolées (pour merge séparé si besoin).
- Quand tout est validé : `git checkout main && git merge integration`, puis Mike
  `git push`.

### Fait cette session (02/08) — sur `integration`

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

1. **Valider `integration` en réel** (Mike, en cours) : /browse
   (déplacer/renommer/supprimer/annuler un fichier de test), /reglages (actions),
   tri clavier /people, correctifs Mathilde/ARZOPA. Puis **merger dans `main` +
   pousser**.
2. **Priorité n°1 reconnaissance — confirmer ~100 propositions** (`/people`,
   maintenant rapide au clavier). C'est le geste HUMAIN qui vaut plus que tout
   changement d'algo (voir ROADMAP « À faire », Reconnaissance §1). Outillage
   prêt ; il « suffit » que Mike le fasse. Peut-être ajouter `1`–`9` = assigner à
   une personne connue, `Maj+clic` = plage.
3. **Rangement par année — APPLICATEUR FAIT ET TESTÉ (02/08, branche
   `feat/rangement-annee-apply`), reste à valider en réel.** `appliquer_plan_annee.py`
   (calqué sur `appliquer_plan.py`) : serveur arrêté, **dry-run par défaut**,
   `--appliquer`/`--limite N`/`--undo`. Refuse toute collision au dst (jamais
   d'écrasement), re-clé via `rekey_stores` (miroir de `rekey_everywhere`), journal
   undo. `test_appliquer_plan_annee.py` vert, `26 - Ranger par annee.bat` (ASCII).
   `generer_plan_annee()` émet désormais `new_key` par move. **Validation réelle** :
   générer le plan depuis `/reglages`, arrêter le serveur, lancer le `.bat` (dry-run
   → lot de 20 → reste), vérifier sur le NAS, merger la branche. **Reste après** :
   **application du renommage intelligent** sur `_Uploads` (cœur déterministe
   `renommage.py` déjà fait et testé ; reste à brancher l'application + provenance
   + GPS inversé/type SigLIP pour les 2 faits à None).
4. **Étape B — reste redesign** : propager le registre **papier** aux cartes de
   clusters toujours visibles (`.cl` sur `/people`, `.group` sur `/pets`) — gros
   changement du flux de nommage, valider en réel d'abord ; **centre de tâches**
   remplaçant le bandeau `#pending` (données `hw_state()`/`system_busy()`/files) ;
   **numéro de vue** sur les cellules de la planche contact.
5. **Édition des réglages depuis `/reglages`** (aujourd'hui lecture seule) : seuils,
   autonomie/cadence de maintenance, racines — avec garde-fous.
6. **Reconnaissance (algo)** : regroupement par **densité** (HDBSCAN / Chinese
   Whispers) au lieu du seuil global ; **AdaFace** sur le ré-embedding des visages
   faibles. La garde AMONT de 12b (`verifier_visages.py`, SigLIP humain vs
   animal/objet) reste à **mesurer** avant activation (`vision-eval`).
7. **Une seule page « Sujets »** (fusion Personnes + Animaux, filtre par type ;
   le lieu comme 3ᵉ facette) — `SubjectStore` déjà unifié.
8. **Éval tagging** (parké, tranché) : (a) mesurer un V2 « assertions sans
   impératif de noms » + fusion programmatique des noms/date/lieu ; (b)
   comparatif de modèles (`gemma4:e2b` FR natif vs `qwen3-vl:2b`) via
   `eval_tagging.py --modele … --variantes V0`, rejeter si le pic VRAM frôle 4 Go.
9. **Bibliothèque Figma** comme source de vérité des composants (optionnel).

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

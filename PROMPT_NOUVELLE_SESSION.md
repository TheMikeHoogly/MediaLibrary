# Prompt de démarrage — à coller dans une nouvelle conversation

> Copie tout le bloc ci-dessous dans une nouvelle conversation Cowork, après
> avoir connecté le dossier `C:\Prog\Claude\MediaLibrary`.
>
> Dernière mise à jour : **3 août 2026** (fin de session triage : mesuré, tranché, pivoté).

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

## ══ ÉTAT AU 3 AOÛT 2026 — LIRE EN PREMIER ══

### Branches (IMPORTANT)

- **`main` == `origin/main`**, porte l'état courant (sessions 01-03/08 : redesign,
  `/browse`, `/reglages`, rangement par année générateur+applicateur, banc triage +
  pivot). Des branches de suivi existent encore mais `main` fait foi. `git push` =
  geste de Mike (impossible depuis le sandbox).
- **Triage (point 21) = FAIT, REVU ET MERGÉ dans `main` (03/08, `4cb9aef`, poussé
  sur `origin/main`).** Filtre par motif + suppression réversible dans la galerie.
  Revue de diff faite (1 correctif Medium `b5e5773` : clé absolue pour racines
  supplémentaires non indexées). Branche `feat/triage-galerie` fusionnée (ff).

### Rangement par année (point 19) : FAIT ET APPLIQUÉ (03/08)

Appliqué en réel par Mike, index re-clé et stable. `_A TRIER` ne contient presque
plus que des fichiers sans date ; les rebuts datés sont dans les dossiers année.

### Fait cette session (02/08)

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

1. **Rangement par année — FAIT ET APPLIQUÉ (03/08)** (voir la section dédiée
   ci-dessus). Plus rien à faire ; l'index est stable.
2. **Triage (ROADMAP point 21) — ✓ FAIT, REVU ET MERGÉ dans `main` (03/08,
   `4cb9aef`).** La mesure avait écarté le détecteur ML
   (décision écrite `eval/DECISIONS.md` du 03/08) : rebut fiable minuscule
   (`inventaire_rebuts.py` → **462/33 109 = 1,4 %**), **surtout des photos à
   garder**. Livré : **filtre par motif/dossier + suppression individuelle
   réversible dans la galerie `/files`** — `?motif=` (chips `capture`/`document`/
   `facture` en `--fixateur`, lecture seule, `import interet` paresseux) ;
   `_key_to_target` (clé STORE → idx/rel) ; `/api/files/delete {key}` →
   `FileOps.delete` (quarantaine réversible + re-clé) ; bouton supprimer `--encre`
   cible 44 px dans la **visionneuse** + toast undo 10 s ; `'key'` ajouté aux DEUX
   constructions de `file_data`. Vérifs vertes : `py_compile`, `verifier_ui_tokens`
   (0 interdit dur), `test_interet` 16/16, `test_fichiers` 23/23, `test_ui_bundle`,
   démarrage zéro-dep confirmé. **Revue de diff FAITE (03/08)** : 1 correctif
   Medium commité (`b5e5773`) — clé absolue pour les racines supplémentaires non
   indexées (la suppression par clé retombait à tort sous Uploads). Tests verts.
   **Mergé (ff) dans `main` (`4cb9aef`) et poussé sur `origin/main` par Mike
   (03/08).** La prochaine session doit charger le correctif au redémarrage du
   serveur. Jamais d'étiquette « rebut », jamais d'auto-sélection.
3. **Priorité n°1 reconnaissance — confirmer ~100 propositions** (`/people`,
   maintenant rapide au clavier). C'est le geste HUMAIN qui vaut plus que tout
   changement d'algo (voir ROADMAP « À faire », Reconnaissance §1). Outillage
   prêt ; il « suffit » que Mike le fasse. Peut-être ajouter `1`–`9` = assigner à
   une personne connue, `Maj+clic` = plage.
4. **Renommage intelligent (ROADMAP point 20)** — brancher l'application sur
   `_Uploads` (cœur déterministe `renommage.py` + `renommage_facts.py` faits et
   testés ; reste : re-clé via `rekey_everywhere` + provenance + undo + GPS
   inversé/type SigLIP pour les 2 faits à `None`). Peut passer après le rangement.
5. **Étape B — reste redesign** : propager le registre **papier** aux cartes de
   clusters toujours visibles (`.cl` sur `/people`, `.group` sur `/pets`) — gros
   changement du flux de nommage, valider en réel d'abord ; **centre de tâches**
   remplaçant le bandeau `#pending` (données `hw_state()`/`system_busy()`/files) ;
   **numéro de vue** sur les cellules de la planche contact.
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

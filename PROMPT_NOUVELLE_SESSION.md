# Prompt de démarrage — à coller dans une nouvelle conversation

> Copie tout le bloc ci-dessous dans une nouvelle conversation Cowork, après
> avoir connecté le dossier `C:\Prog\Claude\MediaLibrary`.

---

Tu reprends le projet **MediaLibrary** — photothèque familiale locale à IA
(~30 000 photos sur NAS, serveur Python stdlib, pipelines Ollama/InsightFace/
YOLO/DINOv2, RTX 3050 4 Go). Dossier : `C:\Prog\Claude\MediaLibrary`. Tout
l'état vit dans les fichiers, pas dans l'historique.

**Lis d'abord, dans l'ordre :**
1. `CLAUDE.md` — règles absolues.
2. `ROADMAP.md` — état et chantiers par ordre de valeur.
3. `eval/DECISIONS.md` — ce qui a déjà été **rejeté sur mesure** (ne pas
   reproposer : MegaDescriptor, contre-exemples, `sqlite-vec`, injection des
   noms au prompt de tagging).
4. Selon le chantier : `docs/AUDIT_EXTERNE_2026.md`, `docs/RANGEMENT_2026.md`,
   et les skills de `.claude/skills/` — `monolith-surgery` **avant tout edit de
   `server.py`**, `photo-ui` pour l'interface, `vision-eval` pour un
   seuil/modèle.

**Garde-fous à ne jamais oublier :**
- **Ne pas ouvrir `photos.db` (WAL) depuis un sandbox Linux** — le copier en
  `/tmp` en lecture seule. Les passes Ollama/GPU tournent sur la machine de
  Mike, via les `.bat` numérotés (ASCII pur : passer `python verifier_bat.py`
  et **lire sa sortie**).
- **Les noms attribués par un humain (`personne:` / `animal:`) ne se perdent
  jamais.** Ils vivent dans les XMP des fichiers.
- **Un score parfait est une alarme, un proxy n'est pas le juge.** La notation
  humaine a renversé un verdict automatique (« V2 ≈ V0 » était faux). Toujours
  vérifier l'effet réel d'une correction.
- **Zéro dépendance au démarrage** (imports lourds paresseux) ; côté client,
  **zéro build, zéro npm**.

**Outillage :**
- **Git : commits AUTONOMES depuis la session (résolu le 01/08).** `git` marche
  dans le shell (`origin = TheMikeHoogly/MediaLibrary`). L'identité locale est
  posée (`git config user.name/email`). Branche **`main`**, à jour et **poussée
  sur GitHub** (tout le travail du 01/08 est publié).
  - **Cause des blocages passés** : le montage refuse TOUTE suppression depuis le
    sandbox (`rm` → EPERM), donc un verrou git périmé (`index.lock`, `HEAD.lock`,
    `*.lock`) laissé par une op interrompue ne pouvait pas être effacé et bloquait
    les commits suivants.
  - **Solution** : l'outil `mcp__cowork__allow_cowork_file_delete` (une approbation
    pour le dossier) débloque `rm` PARTOUT, y compris `.git/`. Commit normal =
    aucune approbation nécessaire (mise à jour de ref par rename, qui passe sur le
    montage) ; si un verrou périmé traîne, demander la permission une fois puis
    `rm -f .git/*.lock`. **Plus de fichiers MESSAGE_COMMIT ni de commit côté hôte.**
  - Réflexe : commiter au fil de l'eau après chaque lot vérifié, message clair.
  - **`git push` est IMPOSSIBLE depuis le sandbox** (le proxy réseau bloque
    github.com : « 403 from proxy after CONNECT »). Les commits restent LOCAUX ;
    c'est Mike qui publie depuis sa machine (`git push -u origin <branche>`).
- **Figma** — connecteur actif et fonctionnel (testé via `whoami`), prêt pour le
  redesign UI « chambre noire ».
- Les autres connecteurs (Slack, Notion…) exigent un OAuth via les réglages
  claude.ai ; sans effet sur les chantiers en cours.

**Correctif Errno 22 SMB — mergé dans `main`.** Le défaut de lecture SMB
**transitoire** (Visages/Animaux sur `_Uploads/ARZOPA`, sonde `diag_errno22.py`)
était écrit comme échec permanent ; `_load_bgr` lit désormais avec retry +
décodage mémoire, les workers ne poisonnent plus, les scans repassent les
`failed` transitoires (`test_errno22_fix.py`). Le serveur a tourné le 01/08
(page `/people` OK) ; vérifier au besoin que ces fichiers `_Uploads/ARZOPA`
repassent bien.

**➡ SESSION EN COURS = DESIGN UI/UX** — décidé avec Mike le 01/08. Le chantier
**Rangement & dédoublonnage est bouclé de bout en bout** (recensement → plan →
application : **8,4 Go récupérés** → purge planifiée → orchestrateur de
maintenance auto dans le serveur). On travaille l'**interface** (voir ROADMAP,
section « Interface — redesign chambre noire », points 9-12 + **bugs observés
12a/12b**). Charge la skill `photo-ui` et suis `monolith-surgery` (une page à la
fois).

**Bugs `/people` (01/08) — état :**
- **12a — ✓ FAIT et validé en réel par Mike (01/08).** Débordement horizontal des contrôles
  « À vérifier » corrigé dans `PEOPLE_PAGE` : rangée `.cl .row` responsive
  (`min-width:0`, libellé/champs élastiques, repli pleine largeur sous 900 px,
  cibles 44 px), largeur fixe inline du champ retirée.
- **12b — ✓ FAIT côté UI + backend réversible, validé en réel par Mike (01/08).** Attribution
  unifiée par sous-ensemble portée sur les visages (miroir animaux) :
  `attribuer_visages`/`_nommer_membres_visages`/`_marquer_visages`,
  `/api/assign` `genre:'visage'`+`membres`, cibles `__pas_visage__` /
  `__non_group__`, `_gather_faces` saute ces flags, UI `carteGroupeP` (vignettes
  sélectionnables, Attribuer N, Rejeter le groupe, « Ce n'est pas un visage »,
  toast d'annulation 10 s). `py_compile` OK.
  **RESTE : la garde AMONT (vraie cause), à MESURER avant de câbler (`vision-eval`)**
  — `verifier_visages.py` en passe séparée (SigLIP « humain vs animal/objet ») +
  plancher `det_score`, avec entrée `eval/DECISIONS.md` (précision, faux rejets,
  pic VRAM) AVANT activation. Ne pas l'imposer sans preuve : le marquage humain
  réversible tient l'usage en attendant.

**Prochain pas concret** : 12a/12b validés en réel (01/08). Attaquer soit la
garde amont mesurée (12b, `vision-eval` : `verifier_visages.py` + plancher
`det_score`), soit les fondations du redesign chambre noire (points 9-11,
extraction `ui/` d'abord).

Le rangement par année des `_A TRIER` et l'installateur nouveau PC restent
ouverts (voir plus bas) mais ne sont pas la priorité immédiate.

**État des chantiers — la PRIORITÉ est le n°2 (design, voir le cap ci-dessus) ;
le n°3 (rangement) est bouclé, le n°1 reste en réserve :**
1. **Éval tagging (tranché, deux pas ciblés restants).** Hybride assertions+image
   adopté ; impératif de noms rejeté (coûteux, VRAM au plafond). (a) Noter/mesurer
   un V2 « assertions en contexte, **sans** impératif » (~4,3 s), puis brancher la
   **fusion programmatique** des noms/date/lieu dans la description. (b) **Comparatif
   de modèles** (veille juillet 2026) : le banc porte `--modele`/`--variantes` —
   lancer `python eval_tagging.py --modele qwen3-vl:2b --variantes V0` puis
   `--modele gemma4:e2b --variantes V0`, comparer pic VRAM (rejeter si frôle 4 Go)
   et qualité. Candidats : `gemma4:e2b` (FR natif, edge), `ministral-3-3b`,
   `moondream3`. Voir `eval/DECISIONS.md` et la « Veille modèles » de `ROADMAP.md`.
2. **Redesign UI/UX « chambre noire »** (ROADMAP, section Interface, points 9-12
   + composants signature). Une page à la fois, extraite puis redessinée, via
   Figma. Commencer par la page d'upload ou « Sujets ».
3. **Rangement & dédoublonnage** (`docs/RANGEMENT_2026.md`) — **le plus avancé.**
   - Phase 0 : **✓ TERMINÉE (01/08, ~4 h 37).** `docs/recensement.{md,json}` +
     `recensement_console.log` écrits. Chiffres : 34 305 fichiers, 261 groupes de
     doublons par contenu, 291 retirables, **8,4 Go**, 12 714 sous `_A TRIER`,
     991 sans date. Décisions ouvertes tranchées : le dédoublonnage vaut l'effort,
     le rangement `_A TRIER` est le gros du volume.
   - **Phase 2 — plan de dédoublonnage : ✓ FAIT (01/08).** `plan_rangement.py`
     (lecture seule) → `docs/plan_rangement.{json,md}` : **291 quarantaines,
     8,4 Go** vers `.corbeille-rangement/`, provenance par op, **0 fusion de nom
     requise** (les 16 copies nommées ont des noms déjà sur la canonique). Reste
     Phase 2 : rangement par année des 12 714 `_A TRIER` (besoin de l'inventaire
     complet — enrichir `recensement_doublons.py` ou dériver de l'index).
   - **Phase 3 — applicateur : ✓ FAIT et testé (01/08).** `appliquer_plan.py`
     (+ `test_appliquer_plan.py`, end-to-end vert) applique les 291 quarantaines,
     réversible : re-vérifie sha256, fusionne noms avant retrait, déplace vers
     `.corbeille-rangement/` + manifeste, re-clé l'index (primitives de
     `rekey_everywhere`), journal undo. Dry-run défaut, `--limite N`, `--undo`.
     **Appliqué en vrai (01/08) : 290 quarantaines, ~8,4 Go récupérés** (serveur
     arrêté, 2 journaux undo gardés).
   - **Phase 3b — purge corbeille : ✓ FAIT et testé (01/08).**
     `purger_corbeille.py` (+ test, + `24 - Purger la corbeille.bat` ASCII pur)
     supprime définitivement les groupes > 30 j **seulement si la canonique
     existe encore** (filet anti-perte ; `--verifier-canon` re-hash). Dry-run par
     défaut. **Reste rangement : par année des `_A TRIER`** (inventaire complet
     à produire).
   - **Orchestrateur de maintenance intégré au serveur : ✓ FAIT et testé (01/08).**
     `maintenance.py` `run_cycle(sv)` appelé par un thread `maintenance_orchestrator`
     dans `server.py` (config `MAINTENANCE_AUTO`, défaut True). Remplace le Task
     Scheduler. Cadence + autonomie par étape : purge/dédoublonnage **auto**,
     recensement (lourd)/renommage/rangement **propose**. Mutations in-process via
     `rekey_everywhere` (écrivain unique), lecture seule en sous-processus,
     priorité UI (`system_busy() or ui_recent()`). Testé avec FauxServeur
     (`test_maintenance.py`). `25 - Maintenance.bat` = passe manuelle (serveur
     arrêté). **À VALIDER EN RÉEL** : démarrage serveur + 1er cycle (édition
     monolithe non testable hors machine ; 1er cycle = no-op attendu).
   - **Installateur / migration nouveau PC : ✓ FAIT (01/08).** `installer.py`
     (venv, torch CUDA/CPU auto, deps via `requirements.txt`, `ollama pull`,
     gabarits config, `--check` doctor, `--prewarm`, `--autostart` raccourci
     démarrage) ; `migrer.py` export/import de l'état (photos.db+wal/shm + configs
     .txt) en zip, **testé** (`test_migrer.py`) ; lanceurs `1 - Installer (nouveau
     PC).bat`, `Migrer - Exporter/Importer …bat` (ASCII pur) ; runbook
     `INSTALLATION.md`. Rappel : les daemons vivent dans le serveur → « démarrer
     le serveur » relance tout ; noms humains dans les XMP (voyagent avec le NAS).
     **À valider sur le vrai nouveau PC** (installer.py non testable hors Windows ;
     `--check` pour diagnostiquer).
   - Prérequis Phase 1 : `vectors.rekey_prefix`/`rekey_prefix_all` **faits et
     testés** (`test_rekey_vectors.py` 12/12, `test_vectors` 29/29).
   - **Renommage intelligent** : spec convergée avec Mike (voir RANGEMENT, section
     « Renommage intelligent ») — format `YYYYMMDD_<lieu-ou-type>_<sujet>.ext`,
     tirets + ASCII, **automatique** sur `_Uploads`, entièrement réversible.
   - **Point de re-clé unique : ✓ FAIT ET TESTÉ (01/08).**
     `rekey_everywhere(old, new, save=True)` dans `server.py` (après
     `photo_vectors()` — le vrai nom de la globale, PAS `get_photo_vec`) :
     `STORE.rekey` + stores faces/people/animals/pets (`rekey`+`save`, transport
     auto des vecteurs) + `photo_vectors().rekey_prefix_all`. Branché au scan
     (~l. 1715, `save=False` + batch-save). Bug corrigé dans `vectors.py` :
     `rekey_prefix_all` ratait la clé **nue** du sémantique (`kind='photo'`) —
     déplacée maintenant aussi, en transaction. Validé sur COPIE de la base
     (`test_rekey_everywhere.py`, tout vert ; `test_rekey_vectors` 12/12,
     `test_vectors` 29/29).
   - **Renommage intelligent — cœur déterministe : ✓ FAIT ET TESTÉ (01/08).**
     `renommage.py` (stdlib pure, AUCUNE mutation) : `propose_basename(facts)`
     assemble `YYYYMMDD_<lieu-ou-type>_<sujet>.ext` + assainit (ASCII `œ/æ/ø/ß`,
     tirets, chars Windows, réservés, plafond 120 + troncature mot, collision
     `-<4hex>`, idempotence). `test_renommage.py` ~40 assertions vertes +
     dry-run sur 161 vrais noms accentués. Défauts appliqués (à valider par
     Mike) : sujet casse conservée, lieu/type minuscule, noms multiples **triés**
     `-et-` (spec montrait `Mike-et-Flo`, choisi le tri pour déterminisme).
   - **Résolveur de faits + dry-run : ✓ FAITS (01/08, lecture seule).**
     `renommage_facts.resolve_facts(key, entry, lieux)` (reflète `_best_time`/
     `lieux_connus`) + `dry_run_renommage.py` (sur copie). Le dry-run a corrigé 3
     défauts : description non distillée, `-et-al` doublé, faux lieu (hostname
     `NAS-Bremblens` puis dossier `_Uploads`) → on retire `\\hôte\partage` et les
     composants préfixés `_`. Voir RANGEMENT « Résolveur de faits + dry-run ».
   - **Tranché + appliqué (01/08)** : (a) **heure dans le nom** —
     `YYYYMMDD-HHMMSS` quand connue (collisions 475→353) ; (b) **`lieux.txt`
     nettoyé** par `nettoyer_lieux.py` (liste blanche géo : 97→28 vrais lieux,
     réversible via `lieux.txt.bak`, option `--ollama`). Dette : `lieux_connus()`
     régénère la liste brute si le fichier est supprimé — à rebrancher plus tard.
   - **Prochain pas serveur** : brancher (a) l'**application** du renommage sur
     `_Uploads` — renommage réel + `rekey_everywhere` + provenance (JSON+XMP) +
     undo, `resolve_facts` complété par GPS inversé + type SigLIP (les 2 faits à
     None aujourd'hui) — MUTE le NAS : après le recensement, sur copie, revue ; et
     (b) le futur **worker « appliquer un plan »**. Migrer aussi la détection de
     déplacement du scan (~l. 1705) de « nom + taille » vers la signature de
     contenu (Phase 2). Charge `monolith-surgery`.

Cap long terme (voir ROADMAP) : **multimodalité** (images → vidéo → audio) et
**recherche AI** en langage naturel dans le serveur. À garder en tête dans les
décisions d'architecture.

Après lecture, dis-moi par lequel tu commences (ou attaque le plus utile) et
propose un plan court avant d'écrire du code. Astuce : dis simplement **« Go »**
et je te fais le débrief + prochaines étapes (protocole décrit dans `CLAUDE.md`).

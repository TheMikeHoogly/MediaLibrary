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

**Outillage (état 31/07) :**
- **Git : accès local en session** — le dossier est un vrai dépôt
  (`origin = TheMikeHoogly/MediaLibrary`), `git` marche dans le shell (diff, log,
  branches, commit). La revue de diff avant de toucher `server.py` ne dépend PAS
  du connecteur GitHub MCP (OAuth non activable depuis la session). Le connecteur
  distant ne sert qu'aux issues/PR en ligne.
- **Figma** — connecteur actif et fonctionnel (testé via `whoami`), prêt pour le
  redesign UI « chambre noire ».
- Les autres connecteurs (Slack, Notion…) exigent un OAuth via les réglages
  claude.ai ; sans effet sur les chantiers en cours.

**Correctif en attente de vérification :** branche `fix/smb-errno22-retry`
(commit `2d7ad19`, revue de code passée) —
l'Errno 22 SMB (Visages/Animaux sur `_Uploads/ARZOPA`) est un défaut de lecture
**transitoire** (pas une corruption : sonde `diag_errno22.py`) qui était écrit
comme échec **permanent**. `_load_bgr` lit maintenant avec retry + décodage
mémoire, les workers ne poisonnent plus sur `ImageReadError`, et les scans
repassent les `failed` transitoires. Testé en isolation (`test_errno22_fix.py`).
**Reste : relancer le serveur, observer que ces fichiers repassent, puis merger.**

**➡ PROCHAINE SESSION = DESIGN UI/UX** — décidé avec Mike le 01/08. Le chantier
**Rangement & dédoublonnage est bouclé de bout en bout** (recensement → plan →
application : **8,4 Go récupérés** → purge planifiée → orchestrateur de
maintenance auto dans le serveur). On passe à l'**interface** (voir ROADMAP,
section « Interface — redesign chambre noire », points 9-12 + **bugs observés
12a/12b**). Charge la skill `photo-ui` et suis `monolith-surgery` (une page à la
fois). **Deux bugs concrets à traiter en priorité** (page `/people`,
`PEOPLE_PAGE`) :
- **12a** — les contrôles « À vérifier » (Oui/Nom/Aucun) débordent à droite,
  scroll horizontal même en plein écran → rangée non responsive (`flex-wrap`,
  `min-width:0`, repli des actions sous ~900 px).
- **12b** — un groupe de personnes mélangeait des nuques + **2 découpes de chat**
  (Caline), sans moyen de le rejeter ni d'en retirer des vignettes. Correction
  intelligente (détail dans ROADMAP 12b) : **UI** — sélection par vignette +
  « Rejeter ce groupe » + « Pas un visage » (port depuis les animaux) ; **amont**
  — garde de validité de visage (SigLIP « humain vs animal/objet » + plancher
  `det_score`) pour que chats/non-visages n'entrent pas dans les clusters, et
  plancher de reconnaissabilité pour ne pas proposer de groupe ingérable.

Le rangement par année des `_A TRIER` et l'installateur nouveau PC restent
ouverts (voir plus bas) mais ne sont pas la priorité immédiate.

**Où on en est — trois chantiers ouverts (commencer par le 3) :**
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

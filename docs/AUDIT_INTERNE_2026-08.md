# Audit interne — 11 août 2026

> Triple audit par agents (incohérences / optimisations-robustesse / stratégie roadmap),
> mené après livraison du GpuArbiter. Ce fichier est le **détail** ; la ROADMAP ne garde
> que l'ordre des priorités. Chaque constat est vérifié dans le code (ancre grep fournie).
> Rien ici ne repropose une idée rejetée de `eval/DECISIONS.md`.

## 1. Incohérences (par gravité)

### Importantes
- **I1. Workers visages/animaux hors ordonnanceur.** `POIDS_FOND` déclare `visages: 4.0`
  et `animaux: 2.0`, mais seuls `semantique`/`empreintes_chats`/`reembed` passent par
  `creneau()` ; `face_worker` et `animal_worker` consomment leurs files sans garde. La
  promesse « un seul travail lourd à la fois » ne couvre pas les deux boucles les plus
  lourdes ; `ORDO.etat()` affichera `tours: {visages: 0, animaux: 0}` pour toujours.
  → Envelopper les deux workers dans `creneau()` (ou retirer les clés et corriger l'état).
- **I2. `gps_places.json` = 7ᵉ magasin keyé par chemin, ignoré de `rekey_everywhere` et
  `forget_everywhere`.** Latent tant que gps_place est inactif — mais les deux gestes en
  attente (activer gps_place PUIS renommer 2114 fichiers) orphelineraient les libellés.
  → Corriger AVANT d'activer gps_place. Voir aussi O10 (index vectors).
- **I3. Tests ArbitreGPU. RÉGLÉ 11/08** : 11 vérifications ajoutées (priorités, éviction,
  refus « en vol », matérialisation sans double compte, ménage plancher/sauf) — 27/27.
- **I4. `classifier.py` contient encore `Modele`/`Banque`/`MARGE_NEGATIVE`** (contre-exemples,
  REJETÉS 30–31/07) en code mort avec docstring élogieux ; `server.py` n'importe que
  `prototypes`. → Supprimer ou marquer « REJETÉ, conservé pour banc d'essai ».

### Moyennes
- **I5.** /reglages affirme en dur « visages : CPU (seul Ollama utilise le GPU) » — faux
  depuis le GPU adaptatif + arbitre. → Libellé dynamique (`FACE_LAST_ENGINE`, baux).
- **I6.** `etat['gpu']`/`etat['ordonnanceur']` ne vivent que dans `/api/search/status` ;
  /reglages ne les affiche pas (`/api/maint/status` ne les expose pas). → Les ajouter à
  `/api/maint/status` + une carte /reglages « GPU : baux/refus/évictions ».
- **I7. RÉGLÉ 22/08, et MESURÉ D'ABORD.** `tagging_meta.parse_tag_nomme()` est la règle
  unique : préfixe lu sans égard à la casse, nom rendu tel quel (règle 2). Elle remplace
  les six lectures divergentes — curateur ADD (`ptags`), curateur REMOVE (`pidx` en
  minuscules, la FICHE faisant foi sur l'orthographe de ce qui part en suggestion ou en
  retrait), compteur de `noms_pour_saisie`, garde-fou des clés fantômes,
  `renommage_facts.names_from_entry`, `_norm_import_kw` (qui canonise désormais le
  préfixe). **Le fonds a été interrogé AVANT** (`mesure_noms_casse.py`, 18 tests, banc
  sur copie) : sur **37 707 tags nommés — 0 préfixe non canonique, 0 doublon de casse,
  3 tags en casse divergente** (`animal:luna` / fiche `Luna`). C'était donc un défaut
  LATENT, à ne pas annoncer comme une réparation. Observé après redémarrage : `/api/names`
  passe Luna de 207 à 210, les personnes inchangées.
  **Ce que la mesure a trouvé en chemin, et qui n'est PAS de la casse** : `personne:Florine`
  sur **153 photos sans aucune fiche** (149 partagées avec `personne:Flo`) — la galerie la
  propose en puce de filtre, `/api/names` l'ignore. Jugement humain, voir `QUESTIONS_MIKE.md`.
- **I8.** Routes orphelines : `/api/pets/name` + `name_pet_cluster` (remplacés par
  `/api/assign` genre animal) ; `/api/hardware` sans client. → Supprimer/statuer.
- **I9.** CLAUDE.md dit « quatre pipelines » (sans SigLIP), PROMPT idem — le code en câble 5.
  → RÉGLÉ 11/08 (CLAUDE.md + PROMPT corrigés).
- **I10.** Compteurs périmés : « ~9 400 lignes » (réel ~12 000), « 7 pages » (réel 9 gabarits :
  REGLAGES et SUBJECTS en plus ; les passes tokens/DESIGN ne couvrent que les 7 historiques).
  → RÉGLÉ 11/08 dans CLAUDE.md ; le skill monolith-surgery reste à rafraîchir (geste éditeur
  de skill, hors dépôt).
- **I11.** `docs/RANGEMENT_2026.md` + `maintenance.py` disent le renommage « pas branché »
  alors que l'apply manuel par lots existe (`/api/maint/rename-apply`). Seul l'auto-apply
  du cycle n'existe pas. → Reformuler les deux.
- **I12.** Les journaux d'undo (3 familles) + états de maintenance s'écrivent dans `docs/`
  (versionné, whitelisté du nettoyage) → accumulation sans borne, chemins NAS privés.
  → `docs/journaux/` gitignoré + purge des undo appliqués > 30 j.

### Détails
- **I13.** `SEMANTIC_SCAN_MAX` : constante morte. **I14.** `ArbitreGPU.total_mb` jamais lu.
- **I15.** README : « Cinq décisions » (réel ~24) ; « Demarrer le serveur.bat » sans « 0 - ».
- **I16.** PROMPT listait encore « GpuArbiter (session dédiée) » en futur. RÉGLÉ 11/08.
- **I17.** Baux = seuils `*_MIN_FREE_MB` (pas l'empreinte réelle des modèles) — conservateur,
  corrigé par la matérialisation ; commentaire ajouté un jour si ça gêne.

## 2. Optimisations / robustesse (par impact)

### Fort
- **O1. Vignettes de grille = originaux pleine résolution** (galerie, carte, diaporama :
  2–6 Mo/case lus sur NAS). Un `/api/thumb?key=` (JPEG 512 px, cache disque, motif
  `_serve_facecrop` existant) ≈ −98 % d'octets NAS en navigation. Effort M. **Meilleur
  ratio du lot.**
- **O2. `_send_file` lit tout en RAM, sans `Range`** : un .mp4 de 500 Mo = 500 Mo RAM/requête,
  pas de seek vidéo mobile. → Stream par blocs 1 Mo + `Accept-Ranges`. Effort S/M.
- **O3. `media_roots()` sans cache** : stats SMB à chaque requête ; NAS débranché = toute
  l'UI gèle sur timeouts. → TTL 5–10 s invalidé sur mtime config. Effort S.
- **O4. Écritures `vectors` sans `STORE.lock`** (`put_many_b64`/`rekey_prefix_all` sur la
  connexion partagée) : « transaction within transaction » / vecteurs emportés par un
  ROLLBACK possible. → Sérialiser derrière `STORE.lock`. Effort S.
- **O5. `maintenance_loop` sans try/except** : première exception = plus de scan NI BACKUP
  jusqu'au redémarrage, silencieusement. → try/except + « dernier scan à HH:MM » dans
  /reglages. Effort S.
- **O6. `SEMANTIC_LOCK` tenu pendant un lot de 16 images** (10–30 s CPU) : une recherche
  attend la fin du lot. → Sous-lots de 4 + test `ui_recent()` entre deux. Effort S/M.

### Moyen
- **O7.** Recherche nommée : `_cles_portant` scanne 64 676 entrées en `lower()` par requête ;
  `_tag_index()` (cache 60 s) donne l'O(1) — ajouter une variante insensible à la casse.
  Idem `_cles_du_lieu` (cache lieu→clés TTL).
- **O8.** `build_suggestions` : décodage b64 + matmul PAR visage toutes les 240 s (~16 k) —
  même remède que le re-score du 10/08 (empiler F une fois, un seul `F @ C.T`, mémo décodes).
  Minutes → secondes.
- **O9.** Backfill sémantique : re-scan complet des clés à chaque lot de 16 + `put_many_b64`
  vide tout le cache matrice (recherche pendant l'encodage = reconstruction 30 k blobs).
  → `deja` incrémental + append incrémental dans `matrice()`.
- **O10. Index manquant `vectors(k)`** : `rekey_prefix_all`/`delete_all` filtrent `k>=?`
  sans `kind` → scan des 130 576 lignes ×2 par photo renommée. Avec le plan de 2114
  renommages : ~850 k lignes/lot. → `CREATE INDEX ix_vectors_k`. Effort S. **À faire
  AVANT les lots de renommage** (avec I2).
- **O11.** Aucune compression HTTP : gzip stdlib si `Accept-Encoding` et > 4 Ko (×5–10 sur
  les JSON/HTML de plusieurs Mo). Effort S.
- **O12.** Échec d'écriture XMP `personne:` jeté en silence + `PERSON_QUEUE` en RAM →
  friction avec la règle « les noms survivent dans les fichiers ». → Journal JSONL
  append-only des écritures en attente, rejoué au démarrage. Effort S/M.
- **O13.** `rglob` complet des racines NAS toutes les 5 min → cadences différenciées
  (Uploads 5 min, NAS 30–60 min). ~−90 % d'énumérations SMB.

### Faible
- **O14.** `_reconcilier` re-hash tout le store sous lock à chaque `save()` (2–4 s) →
  dirty-only en courant, passe complète au backup. **O15.** Caches `face_thumbs`/
  `animal_thumbs` non bornés (md5 de bbox → orphelins à chaque ré-embedding) → purge
  maintenance des md5 non régénérables.

## 3. Angles morts stratégiques

- **A. La vérité terrain n'est pas protégée.** Confirmations/exclusions/rejets humains
  vivent uniquement dans `photos.db` ; `backup_db()` = copie jamais restaurée, aucun
  `integrity_check`, snapshot sur le même site. L'actif le plus coûteux à reproduire est
  le moins assuré. → Tâche `backup_verify` (restauration à blanc + comptage confirmed/
  exclude) + export JSONL append-only des jugements humains.
- **B. Dérive XMP↔SQLite non surveillée** (écritures exiftool échouées avalées ; aucun
  réconciliateur périodique). La promesse « le travail survit à l'app » n'est jamais testée.
- **C. Pas de budget 100 k photos** : les murs se découvrent après impact (cf. /sujets
  45 s → 0,8 s). Un test de charge synthétique ×3 suffirait.
- **D. Versions de pipeline : seuls les animaux en ont une.** Visages, sémantique, tagging :
  un changement de modèle mélangerait les embeddings sans alarme (le PLAN tagging note la
  version « à créer »).
- **E. Un seul PC** : reconstruction bare-metal non testée ; `ensure_exiftool()` télécharge
  au premier démarrage. « PC mort lundi → revivre quand ? »
- **F. Harnais d'éval hors dépôt ?** Vérifier que `eval_*.py` référencés par DECISIONS sont
  bien versionnés (reproductibilité des verdicts).

## 4. Suite proposée (résumé — l'ordre vit dans ROADMAP)

Portail : commit GpuArbiter (fait : vérifié en réel 11/08 soir, bail semantique matérialisé,
27/27 tests). Puis : **assurance-vie de la vérité terrain** (angle mort A) → **éval tagging
V2 AVANT les lots de renommage** (le jeu figé de 150 photos est keyé par chemin — le
renommage invaliderait le banc, mode de panne déjà documenté) → **Knowledge Builder**
(adopté le 31/07, jamais câblé, zéro occurrence dans server.py) → **file de confirmation
triée par incertitude** (marge entre 1er/2ᵉ prototype, jamais le score absolu — métrique :
confirmations/minute, pas l'accord modèle-humain, circularité) → gps_place (après I2+O10)
→ lots de renommage → `/api/similar` (cosinus sur l'existant, navigation par similarité)
→ doublons proches bridés (>0,98 + même journée, quarantaine réversible, 50 paires jugées
avant tout geste). Écartés avec raison : HDBSCAN tant que vérité terrain < ~5 % (étalon
circulaire) ; récits LLM automatiques (hallucination sur souvenirs — garder la rangée
« même jour, autres années », requête date sans IA) ; MCP en réserve (Knowledge Builder
en est le prérequis naturel). Vision : une **mémoire familiale à provenance** — chaque fait
affiché porte sa source et son statut humain ; deux tests de vérité : « PC mort lundi,
tout revit vendredi » et « aucun fait affirmé sans provenance ».

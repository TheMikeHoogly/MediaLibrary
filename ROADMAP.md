# Feuille de route — MediaLibrary

L'état vit dans les fichiers, pas dans l'historique de conversation. Ce fichier
est la **carte des priorités** ; le détail vit ailleurs et est référencé :
`eval/DECISIONS.md` (évaluations tranchées), `docs/RANGEMENT_2026.md` (rangement/
dédoublonnage), `docs/AUDIT_EXTERNE_2026.md` (direction tagging), `PROMPT_NOUVELLE_
SESSION.md` (reprise exacte), et l'historique git (chaque chantier fini y est).

Dernière mise à jour : **10 août 2026 (soir)**. **Chantier #3 — archive « (Inconnus) » :
CODÉ, à valider en réel.** Côté visages : nouvelle cible `__inconnu__` (champ `inconnu` sur
la détection, réversible, JAMAIS de XMP), exclue de « Groupes à nommer » et de « À vérifier » ;
nommer un cluster lève l'archive ; nouvelle vue « Inconnus (archivés) » (clusters séparés,
seuil min=1) avec re-tag ou « Réactiver » ; endpoints `/api/people/inconnus` (GET) et
`/api/people/desarchiver` (POST). `server.py` édité en place (py_compile OK, `node --check` OK
sur le JS ajouté), **écrit sur la machine**. **Reste (Mike) : commit + REDÉMARRER + valider
en réel** sur `/people` (archiver un groupe → il quitte la file et apparaît sous « Inconnus » ;
le nommer → il en sort et devient une personne). Précédemment : fix propositions sans image +
purge clés fantômes (commit+redémarrage encore dus), bat 28 RÉSOLU. Reste aussi ouvert :
géocodage `gps_place` à activer. Détail dans `PROMPT_NOUVELLE_SESSION.md`.

---

## État des branches

- **`main` == `origin/main` == `feat/menage-ui-gpu-0807` == `e6a7564`** (fusion 09/08 soir
  par `git push origin HEAD:main`, fast-forward). Porte TOUT l'intégré : travail 08/08
  (cross-pipeline, orphelins, garde SigLIP rejetée), géocodage inverse `gps_place`, carte
  avec lieu, et le renfort `verifier_bat.py` (contrôle des fins de ligne).
- La branche `feat/menage-ui-gpu-0807` reste la branche de travail exécutée par le serveur ;
  elle est maintenant au même niveau que `main`. Prochain chantier = nouveaux commits dessus
  (ou une branche neuve depuis `main`), puis `git push origin HEAD:main` pour refusionner.
- `git push` et les merges dans `main` sont des **gestes de Mike** (le sandbox ne pousse
  pas). La fusion sans checkout local = `git push origin HEAD:main` (contourne le verrou
  `server.py` ET le `.bat` 28 cassé — cf. `PROMPT_NOUVELLE_SESSION.md`).

---

## Fait et vérifié (rappel — ne pas reproposer)

Le détail de chacun est dans git + `eval/DECISIONS.md`.

| Domaine | Acquis |
|---|---|
| **Stockage** | Migration SQLite (64 676 entrées) ; embeddings en table BLOB ; `photos.db` local WAL, sauvegarde NAS par snapshot |
| **GPU** | torch **CUDA** `2.13.0+cu130` + `onnxruntime_gpu` ; `FACE_USE_GPU=False` **volontaire** (VRAM 4 Go prise par Ollama) |
| **Reconnaissance** | SigLIP 2 (recherche sémantique, 90 % rang-1) ; recherche 3D qui/où/quoi ; animaux 97,4 % rang-1 ; prototypes multiples (personnes) ; vérif d'espèce SigLIP |
| **Nommage** | Attribution unifiée (sous-ensemble, noms multiples, annulation 10 s) côté personnes ET animaux ; rejet de groupe / « pas un visage » réversibles |
| **Fichiers** | Gestion `/browse` (renommer/déplacer/supprimer réversible via quarantaine) ; upload de dossiers ; correctif SMB Errno 22 ; `rekey_everywhere` (aucun nom humain perdu) |
| **Rangement** | Recensement (34 305 fichiers) ; dédoublonnage par contenu **appliqué** (8,4 Go) ; rangement par année **appliqué** ; purge corbeille ; orchestrateur de maintenance dans le serveur |
| **Renommage** | Cœur + plan + applicateur in-process réversible **prêts** (plan = 2114) — reste le geste humain d'appliquer les lots |
| **UI** | Design system « chambre noire » (tokens sur les 7 pages, plancher a11y, `verifier_ui_tokens` 0 interdit dur) ; planche contact ; tri clavier du curateur ; centre de contrôle `/reglages` ; bloc renommage numéroté |
| **Tagging** | `qwen3-vl:2b` (SOTA compact confirmé) ; hybride assertions+image adopté ; **1 seule lecture exiftool/photo** (session 08/08, testé) |
| **Méthode** | `verifier_bat.py` + hook ASCII ; `eval/DECISIONS.md` ; installateur nouveau PC |

---

## À faire — par ordre de valeur

### 1. Confirmer la vérité terrain humaine (priorité n°1)

91 photos confirmées par un humain sur 12 072 taguées (**0,8 %**). Deux bancs ont
rendu 100 % parce que la mesure était devenue circulaire (auto-attribution). **Confirmer
~100 propositions dans `/people` vaut plus que tout changement d'algorithme.** Le tri
clavier est prêt (Espace/O = oui, X = non, Z = annuler, lettre = corriger). Option
code : `1`–`9` pour assigner à une personne connue, `Maj+clic` pour une plage.

> **CHANTIER #3 — archive « (Inconnus) » : CODÉ (10/08 soir), à valider en réel.**
> Défauts confirmés par Mike : archive **réversible en base, SANS XMP** ; **clusters séparés**
> sous une vue « Inconnus ». Livré (server.py, écrit sur la machine) : cible `__inconnu__`
> côté visages (champ `inconnu`, miroir du côté animaux) ; exclusion de « Groupes à nommer »
> (`_gather_faces`) et « À vérifier » (`build_suggestions`) ; **nommer un cluster lève
> l'archive** (`_nommer_membres_visages`) ; `INCONNU_CACHE` + `build_inconnus()` (seuil min=1,
> ne cache aucun singleton) ; `desarchiver_visages()` ; endpoints `/api/people/inconnus` +
> `/api/people/desarchiver`. UI `PEOPLE_PAGE` : bouton « Archiver (inconnu) » + entrée
> `SPECIAUX_P` (sous-ensemble) ; section « Inconnus (archivés) » chargée à la demande
> (« Afficher »), re-tag par nommage ou « Réactiver ». py_compile + `node --check` verts.
> **Reste (Mike) : commit + REDÉMARRER + valider en réel.** Vérifs : archiver un groupe le
> sort de la file et le fait apparaître sous « Inconnus » ; le nommer le sort des inconnus et
> crée/enrichit la personne ; « Réactiver » le renvoie dans « Groupes à nommer » ; toasts
> d'annulation OK sur les trois gestes.

### 2. Détections d'animaux mal classées en visages — et l'inverse (Mutz)

**Symptôme observé (08/08) :** le chien **Mutz** (cocker) forme un groupe de 25
« visages » sur `/people` alors qu'il n'a rien à y faire (il est déjà, correctement,
dans Animaux). **Cause :** le pipeline visages n'a **aucun garde humain/animal** — il
accepte toute détection InsightFace de `det_score ≥ FACE_DET_THRESHOLD = 0.50` (seuil
bas pour capter profils/flous), et une face canine frontale passe.

- **Correction manuelle immédiate — existe déjà** : « Rejeter le groupe »
  (`__non_group__`) ou « Ce n'est pas un visage » (`__pas_visage__`) sur le groupe
  `/people`. Réversible. À faire dès maintenant pour Mutz.
- **Action explicite et symétrique — FAIT (branche courante, à valider en réel).**
  `/people` : option **« C'est un animal (pas une personne) »** (→ `__pas_visage__`) dans
  les **trois** surfaces — cartes de groupe (`SPECIAUX_P`) ET curateur de faux-positifs
  (bouton `.anim`, cas `remove` et `ajout`). `/pets` : miroir
  **« C'est une personne (pas un animal) »** (→ `__pas_animal__`, `SPECIAUX`). UI seule,
  aucune modif backend : réutilise les cibles spéciales déjà gérées par
  `attribuer_visages`/`attribuer_animaux`, réversible via le toast. `py_compile` OK.
  Reste à observer en réel sur le groupe Mutz. L'option « confirme côté animaux » a été
  volontairement écartée du périmètre (lien découpe visage ↔ détection YOLO non trivial).
- **Le vrai fix automatique = item 7 ci-dessous (garde amont 12b)** : une vérification
  SigLIP « visage humain vs animal/objet » + plancher `det_score` empêcherait le groupe
  de se former. Mutz est le cas d'école qui justifie de le mesurer et l'activer.
  Discipline `vision-eval` : ne jamais écarter un vrai visage humain (mesurer les faux
  rejets, le pic VRAM, décision écrite) avant d'activer.

### 3. Appliquer les lots de renommage (geste humain, prêt)

Flux complet dans `/reglages` → « Renommage intelligent » (bloc numéroté depuis 08/08) :
Générer le plan → Vérifier à blanc → Appliquer un lot (200, réversible) → répéter →
Annuler si besoin. Plan actuel = **2114 fichiers**. Reste code **optionnel** : enrichir
le fait `image_type` (SigLIP) pour des noms plus riches. Le fait **`gps_place` est FAIT**
(géocodage inverse offline, cf. ci-dessous) — reste à le faire tourner (geste Mike).

**Géocodage inverse `gps_place` — CODÉ (09/08), à activer (geste Mike).**
Décision d'archi : **offline**, pas de connecteur cloud. Le registre MCP n'offrait que
TomTom (OAuth par session, cloud) — inadapté à un batch serveur autonome, et discutable côté
vie privée des GPS familiaux. À la place, un **gazetteer local** GeoNames `cities1000` +
plus-proche-voisin en **stdlib pure**. Pièces livrées et testées en sandbox :
`geocode.py` (module pur, 35/35), `test_geocode.py`, `enrichir_lieux.py` (batch : lit
`photos.db` en **lecture seule**, clusterise les points, géocode les centroïdes, écrit
`gps_places.json` + ajoute des lieux à `lieux.txt` de façon **réversible**, 23/23),
`test_enrichir_lieux.py`, `18 - Telecharger le gazetteer (geocodage).bat` (ASCII pur, vérifié).
Câblage `server.py` minimal : `gps_places_connus()` (cache mtime) alimente
`construire_plan(..., gps_places=…)` — la plomberie de `plan_renommage`/`renommage_facts`
existait déjà. **Le serveur n'importe PAS `geocode`** (il ne lit que le JSON) → zéro
dépendance ajoutée. Bout-en-bout vérifié : un point Bremblens → `…_bremblens_…jpg`.
**Reste (Mike) :** lancer le bat 18 (téléchargement unique), puis
`.venv\Scripts\python.exe enrichir_lieux.py` (aperçu) puis `--ecrire`, puis **redémarrer**.

### 4. Valider + merger la branche « ménage » (`feat/menage-ui-gpu-0807`)

- **Renommage UI** : validé en réel. **Bats** : archivés, sûrs.
- **Optimisation tagging** (1 lecture exiftool/photo) : testée (`test_tagging_meta.py`
  15/15), **à valider en réel** après un redémarrage — mesurer le débit tag/min
  avant/après pour chiffrer le gain.
- Puis `git push` de la branche, et merge dans `main` (une fois le serveur arrêtable).

### 5. Redesign « chambre noire » — étape B (reste)

Étape A (tokenisation) et l'essentiel de l'étape B sont faits. Reste : **centre de
tâches** remplaçant le bandeau `#pending` (données déjà là : `hw_state()`,
`system_busy()`, tailles des files) ; **registre papier** sur les cartes de clusters
toujours visibles (`/people`, `/pets`) — gros changement du flux de nommage, valider en
réel d'abord ; **numéro de vue** en marge de la planche contact ; porter le **sélecteur
d'ordre réversible** (fait sur la galerie) aux fiches détail Animaux/Personnes.

### 6. Une seule page « Sujets »

Fusionner Personnes et Animaux en une page unique (mêmes gestes, filtre par type, le
**lieu** comme 3ᵉ facette). `SubjectStore` est déjà unifié — c'est surtout de l'UI.
Convergence naturelle avec l'item 2 (action cross-pipeline).

### 7. Reconnaissance — algorithme

- **Garde amont humain/animal (12b)** — **MESURÉ le 08/08 → REJETÉ tel quel.**
  `verifier_visages.py` + test 15/15 ont tourné : pic VRAM 2707 Mo (OK) mais
  **18 % de faux rejets** (7/40 écartés = vrais humains endormis/près d'un chat, lus
  « cat »), scores 0,10–0,15 **chevauchant** les vrais non-humains → aucun seuil global
  ne sépare. Détail : `eval/DECISIONS.md`. **Ne pas câbler.** Piste la plus prometteuse
  si on y revient : **re-mesurer sur découpes SANS marge** (la marge 0,3 embarque le chat
  voisin). En attendant, le remède Mutz est l'**action manuelle** « C'est un animal »
  livrée (cartes de groupe + curateur `/people` + miroir `/pets`).
- **Regroupement par densité** (HDBSCAN / Chinese Whispers) au lieu d'un seuil global
  unique — un seuil ne sert pas à la fois des portraits nets et des profils de 90 px.
- **AdaFace** sur le chemin de ré-embedding des visages faibles.
- **Écrire les tags SigLIP** (aujourd'hui seulement proposés, `semantic.py --tags`) —
  décision à prendre car ils modifieraient les XMP.

> La reconnaissance **animale** est à un bon point d'arrêt (97,4 %, 6 erreurs sur 7 sur
> la seule paire Inti/Luna). Le gain restant est dans la **donnée** (plus de confirmations),
> pas dans l'algorithme ni la résolution (mesurés sans effet — `DECISIONS.md`).

### 8. Recherche — carte & lieux

Le géocodage inverse qui enrichit `lieux.txt` est **codé** (cf. item 3) — une fois lancé
par Mike, `lieux.txt` gagne les communes des 684 GPS et la recherche par lieu les reconnaît.
**Marqueurs de la Carte : FAIT (09/08)** — `/api/geo` expose `lieu` (depuis `gps_places.json`)
et le popup l'affiche (📍, dégradation gracieuse si absent). Reste : faire partager à la page
Carte le vocabulaire de la barre de recherche.

### 9. Éval tagging (parké, déjà tranché)

- Mesurer un V2 « assertions **en contexte, sans impératif de noms** » (version à 4,3 s,
  jamais notée) + **fusion programmatique** des noms/date/lieu (Knowledge Builder), plutôt
  que de quémander les noms au LLM (16 % d'obéissance, rejeté).
- Comparatif de modèles : `gemma4:e2b` (FR natif) vs `qwen3-vl:2b`, via
  `eval_tagging.py --modele … --variantes V0` — **rejeter tout modèle dont le pic VRAM
  frôle 4 Go** pendant qu'Ollama est résident.

### 10. Données & finitions

- **Propositions « À vérifier » sans image sur `/people` (diagnostiqué 09/08, fix IMPLÉMENTÉ
  10/08 — à valider en réel).** Clés fantômes dans `FACE_STORE` : même photo ARZOPA sous une
  clé correcte (`ads\ARZOPA\…`) ET une clé malformée (`ARZOPA/…`, slash avant, sans racine
  `ads\`) qui ne se résout pas → `/api/facecrop` 404 → carte sans vignette (vérifié en direct :
  3/19, toutes ARZOPA). **Fait :** garde-fou dans `build_suggestions()` (`server.py`) — une
  proposition/auto-attribution `add` dont `_resolve_key(k)` n'est pas un fichier est écartée,
  **seulement si la racine est joignable** (jamais NAS déconnecté — leçon `verifier_orphelins`).
  Un seul `is_file()` sur les vrais candidats ; ne touche que des propositions, aucun nom perdu.
  `py_compile` OK. Et `verifier_orphelins.py` (read-only) distingue désormais une **clé
  fantôme** (doublon malformé dont un sibling présent partage le basename — purge sans risque)
  d'un vrai fichier disparu (`basename_cle`/`est_fantome`). **Cause racine traitée (10/08) :**
  `purge_cles_fantomes()` s'exécute une fois au démarrage de `maintenance_loop` — retire de
  FACE/ANIMAL_STORE les doublons malformés (via `forget_everywhere`, jamais une clé nommée),
  détection peu coûteuse (`cles_fantomes_par_collision` ne stat que les basenames en
  collision). Logique pure testée, `test_verifier_orphelins` 23/23. Effet UI déjà **observé
  en réel** (19 → 12 propositions, 0 vignette cassée). **Reste (Mike) :** commit + redémarrage
  → une ligne `🧹 N clé(s) fantôme(s) purgée(s)` confirmera le nettoyage du store.
- **Purge de suppression incomplète (BUG — diagnostiqué ET corrigé le 08/08).**
  `_sync_dir` étape 4 ne retirait un fichier disparu que du **TagStore** ; visages/
  animaux/vecteurs restaient orphelins (cas « ARZOPA »). Diagnostic (`verifier_orphelins.py`,
  read-only) : **4569 orphelins, 0 nommé** (48 `par_humain`, jugements sur photos
  disparues, sans objet). Correctif **implémenté** : `vectors.delete_all` (2 formes
  suffixe+clé nue, test_vectors 34/34), `forget_everywhere` (miroir de
  `rekey_everywhere`) câblé dans `_sync_dir` étape 4. Noms **préservés par
  construction** (fiches PEOPLE/PETS keyées par nom, jamais touchées). **Reste
  (geste Mike)** : committer + **redémarrer** — le `scan_uploads` de démarrage purge
  le backlog en cascade — puis relancer `verifier_orphelins.py` pour confirmer ~0.
- **Fiche « Flo »** (3 478 photos, 80 références, 17 exclusions) probablement mal
  constituée — c'est elle qui rend Florine ambiguë.
- **Doublons de fiches** entre personnes et animaux.
- **Édition des réglages depuis `/reglages`** (aujourd'hui lecture seule) : seuils,
  cadence/autonomie de maintenance, racines — avec garde-fous.
- **Ingestion** : 2ᵉ passe de récupération des 945 fichiers à en-tête détruit
  (`17 - Recuperer les images illisibles.bat`) ; remettre `recuperees/` sur le NAS.

---

## En réserve — futur, non prioritaire

**Multi-utilisateur / foyer partagé.** Un `owner` par racine (Mike, Flo…), dédoublonnage
scopé par racine, rangement configurable par racine, outil de renommage de racine,
puis comptes/droits (le serveur est aujourd'hui ouvert sur le réseau local, sans auth).
Le multi-racines et l'opt-in du rangement existent déjà. Décidé (02/08) : plus tard.

**Multimodalité & recherche AI.** Trajectoire images → **vidéo** → **audio** (dans cet
ordre). Plusieurs briques incluent déjà les vidéos (rangement, dédoublonnage, renommage,
vue Dossiers) ; le pipeline IA ne tague encore que les photos. Cap produit : une
**recherche AI en langage naturel** dans le serveur (« les étés à Bremblens avec Luna »).
C'est là que la **compression de contexte** et **exposer le serveur en MCP** (`mcp-builder`)
prendront leur sens. Toute nouvelle abstraction se conçoit en gardant ces modalités en tête.

**Bibliothèque Figma** comme source de vérité des composants « chambre noire » (optionnel,
sans build step ni npm).

---

## Deux réflexes de méthode

1. **Un score parfait est une alarme, pas un succès** — deux bancs de ce projet ne
   mesuraient pas ce qu'ils prétendaient (l'un circulaire, l'autre inéquitable).
2. **Une correction n'est acquise qu'une fois son effet observé en réel** — trois
   diagnostics successifs ont été justes sans traiter la vraie cause. Un proxy
   automatique n'est pas le juge (la notation humaine a renversé « V2 ≈ V0 »).

Idées déjà **rejetées sur mesure** (ne pas reproposer) : contre-exemples de
classification, prototypes multiples pour les **animaux**, **MegaDescriptor** (deux fois),
résolution des découpes, `sqlite-vec`, injection des noms au prompt, détecteur ML de
triage. Détail chiffré dans `eval/DECISIONS.md`.

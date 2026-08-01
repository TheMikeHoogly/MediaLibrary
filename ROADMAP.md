# Feuille de route

Ce fichier survit aux sessions, contrairement à une liste de tâches en mémoire.
Il est référencé par `CLAUDE.md`, donc relu au début de chaque session.

Dernière mise à jour : 31 juillet 2026.

---

## Fait, et vérifié

| # | Chantier | Preuve |
|---|---|---|
| 1 | **Migration SQLite** — `TagStore` → `SqliteStore`, écriture incrémentale | 64 676 entrées migrées et vérifiées, 42/42 tests. 48,8 Mo réécrits par `set()` → une ligne |
| 2 | **Embeddings hors JSON** — table BLOB, octets float16 préservés | 19 309 vecteurs sortis, base 58,8 → 47,2 Mo, `people` 11,5 Mo → 147 Ko |
| 3 | **Réparation GPU** — build CPU + orphelin `~orch` | `torch 2.13.0+cu130`, InsightFace sur CUDA |
| 4 | **Recherche sémantique SigLIP 2** — encodeur, index vectoriel, route, UI | 90 % de justesse au rang 1 ; recherche en 0,7 ms sur 8 730 vecteurs |
| 5 | **Recherche hybride** — noms humains + sens de l'image | 326 noms reconnus, y compris composés |
| 6 | **Vérification d'espèce** — SigLIP contre les classes COCO | 23 rejets justifiés sur 24 relus un par un |
| 7 | **Nommage généralisé** — chats → tous animaux, par espèce | `ANIMAL_NAMEABLE`, espèce déduite du groupe |
| 8 | **Attribution unifiée** — une action au lieu de boutons binaires | Sous-ensembles, noms multiples, annulation 10 s |
| 9 | **Prototypes multiples** (personnes) | 97,4 % contre 96,7 %, 0 régression |
| 10 | **Ordonnanceur + arbitre VRAM** | Tour de rôle à déficit, 16/16 tests |
| 11 | **Garde-fous de méthode** — `verifier_bat.py`, hook, journal de décisions | Règle ASCII bloquée à l'écriture |
| 12 | **MegaDescriptor rejeté, mesure valide** | À armes égales : DINOv2 97,4 % contre 94,0 %. Banc validé contre la production (97,4 % / 85,6 % vs 85,5 %) |
| 13 | **Résolution des découpes : sans effet** | 256 px 97,8 %, pleine résolution 97,4 %, 512 px 97,0 % — deux photos d'écart, du bruit |
| 14 | **Circularité du banc détectée et corrigée** | 100 % de justesse = alarme, pas succès : la vérité terrain était auto-générée |
| 15 | **Récupération d'images corrompues** | 987 fichiers inventoriés, orientation et analyse profonde corrigées |
| 16 | **Recherche à trois dimensions** — qui / où / quoi | `Luna à Bremblens en hiver` : tag humain + dossier + sens. `lieux.txt` déduit des chemins, 120 lieux |

## Prochaine étape décidée

**Assertions vs pixels : mesuré, noté à l'aveugle et tranché (31/07, voir
`eval/DECISIONS.md`).** Verdict en deux temps. Proxies automatiques : V1 (pixels
jetés) disqualifié (33 % de descriptions « méta ») ; l'impératif de noms au prompt
est inefficace (16 % d'ancrage) et coûteux (× 2,6, VRAM 3 950 Mo au ras du
plafond). **Notation humaine (40 cartes) : l'hybride V2 gagne — meilleure
description dans 60 % des cas contre 30 % pour l'image seule**, hallucination à
peine plus haute (8 % vs 5 %), et il gagne dans les trois catégories. Les
assertions **améliorent** donc la description ; c'est la mesure automatique seule
(« V2 ≈ V0 ») qui l'avait manqué.

**Cap retenu :** garder **l'hybride assertions + image** (apport confirmé par
l'humain), mais **sans l'impératif de noms** (c'est lui le surcoût, pas les
assertions), et **attacher les noms/date/lieu par fusion programmatique** plutôt
que de les quémander au LLM (16 % d'obéissance). Le LLM reçoit les faits *en
contexte* pour mieux décrire ; la couche d'assertions à provenance garantit le
fait exact — ce qui débloque aussi la priorité n°1 (protéger les confirmations
humaines), puis cache de raisonnement et mémoire globale.

**Prochain pas éval, ciblé (mesurer avant de bâtir) :** noter/mesurer un V2
« assertions en contexte, **sans** impératif » (version à 4,3 s, jamais notée car
écrasée). Si elle garde l'avantage de qualité sans le surcoût, c'est le prompt de
production, doublé de la fusion programmatique.

**Veille modèles (état de l'art, juillet 2026).** Le titulaire `qwen3-vl:2b`
reste **aligné SOTA** — Qwen3-VL est « le modèle de vision à battre en 2026 », et
le 2B (~1,9 Go) en est le plancher compact ; le 4B (~6 Go) déborderait les 4 Go
partagés, ce qui confirme le rejet passé du `qwen3-vl:4b`. **Nouveau challenger à
tester : `gemma4:e2b`** (Google, avril 2026, Apache 2.0) — ~2,3 Md effectifs
pensés pour l'edge (donc *a priori* dans 4 Go), **vision native + 140 langues
dont le français** (atout sur nos descriptions FR), présent sur Ollama
(`gemma4:e2b-it-q4_K_M`). Plans B : `ministral-3-3b` (Mistral, français natif),
`moondream3` (excellent en sortie structurée/étiquetage mais orienté anglais).
À écarter : 4B+/MoE trop gros pour 4 Go, Marlin-2B (vidéo), SmolLM3 (texte).

Le banc est prêt pour ce comparatif : `eval_tagging.py` porte `--modele` et
`--variantes`. Protocole (l'« option modèle » du plan, jamais lancée) :

```
python eval_tagging.py --modele qwen3-vl:2b --variantes V0
python eval_tagging.py --modele gemma4:e2b  --variantes V0
```

Chaque run écrit `tagging_results__<modele>.json` (fichiers non écrasés) avec le
**pic VRAM** ; on rejette tout modèle qui frôle les 4 Go pendant qu'Ollama est
résident (`keep_alive 30m`), puis on tranche la qualité entre les deux fichiers
(mêmes 150 photos figées). Sources archivées dans la discussion du 31/07.

Le point 7 (magasin de sujets commun) est **fait et vérifié**. La page
« Sujets » unifiée (point 8) et le plancher d'accessibilité restent en attente.

## Outillage et connecteurs

Les connecteurs s'autorisent dans les réglages de claude.ai (section
Connecteurs), par OAuth — jamais depuis une session Claude Code. Trois servent
directement les chantiers en cours ; les intégrer au flux de travail est un
objectif à part entière, pas un accessoire.

- **GitHub** (dépôt privé `TheMikeHoogly/MediaLibrary`). Dépôt local créé par
  `20 - Preparer le depot git.bat`, publié par `21 - Publier sur GitHub.bat`.
  Connecteur actif → trois usages concrets : (1) **revue de code sur diff/PR**
  (skill `engineering:code-review`) **avant** toute modification du monolithe —
  `server.py` fait 8 500 lignes sans filet ; (2) les chantiers de cette ROADMAP
  deviennent des **issues** suivies ; (3) un **historique** enfin présent. Règle :
  toute modif risquée de `server.py` passe par une branche + revue, pas par un
  edit direct sur `main`.
  > **Réglé (31/07) :** le dossier est un vrai dépôt git (`origin =
  > TheMikeHoogly/MediaLibrary`) et `git` est accessible **en local** depuis la
  > session (diff, log, branches, commit). La revue de diff avant de toucher
  > `server.py` ne dépend donc **pas** du connecteur GitHub MCP (dont l'OAuth
  > n'est pas activable depuis une session). Le connecteur distant reste utile
  > pour les issues/PR en ligne, mais n'est plus bloquant pour le cœur du travail.
- **Compétences utiles au projet** (récap 31/07, à charger selon la tâche) :
  `engineering:code-review` (revue de diff avant `server.py`, faisable en git
  local), `engineering:testing-strategy`/`debug`/`architecture`,
  `design:accessibility-review` (sert directement le plancher d'accessibilité,
  point 10), `design:design-critique`/`design-system`/`ux-copy` (redesign
  « chambre noire »), `data:*` + `graphing`/`create-viz` (interroger `photos.db`,
  visualiser le recensement, valider les bancs — cohérent avec « un proxy n'est
  pas le juge »), `mcp-builder` (exposer la recherche du serveur comme MCP — cap
  recherche AI ci-dessous). Hors sujet : les compétences banque/RH/support/ops.
- **Compression de prompts/contexte — à garder pour la phase recherche AI, pas
  maintenant.** Les outils type LLMLingua / LLMLingua-2 élaguent les tokens à
  faible information (2× à 5× de compression) via un petit modèle de scoring.
  Pertinent le jour où la recherche AI assemblera **beaucoup** de descriptions
  dans une seule requête LLM. Aujourd'hui non : nos prompts de tagging sont
  courts, le LLM est **local** (le coût n'est pas le token mais la **VRAM/temps**
  sur 4 Go), et ajouter un modèle de compression contredirait « zéro dépendance
  au démarrage » et la VRAM déjà au plafond. Le levier tokens **côté sessions
  Claude** est déjà en place : l'état vit dans les fichiers, on ouvre des sessions
  fraîches. Mesurer avant d'implémenter, comme toujours.
- **Figma** — moteur du redesign UI (section Interface ci-dessous). Le design
  system « chambre noire » existe en prototype (`ui/prototype.html`) ; les skills
  Figma (`figma-generate-library`, `figma-design-to-code`) le poussent en
  **bibliothèque de composants** versionnée, source de vérité du design, puis
  regénèrent le CSS/HTML **natif** des pages depuis ces composants — sans jamais
  introduire de build step ni de dépendance npm.
- **Registre MCP** — pour tout besoin ponctuel d'un service externe (ex. le
  géocodage inverse des 684 photos GPS du point 14), chercher d'abord un
  connecteur au registre avant d'écrire du code jetable.

## En cours

- **Correctif Errno 22 SMB (branche `fix/smb-errno22-retry`, commit `2d7ad19`,
  revue de code passée — à vérifier en réel puis merger).** Symptôme :
  `⚠ Visages/Animaux … : [Errno 22] Invalid
  argument` sur des fichiers `_Uploads/ARZOPA`. Diagnostic (sonde
  `diag_errno22.py`) : **le fichier n'est pas corrompu** — il se décode
  parfaitement, en local comme via SMB en isolation ; l'Errno 22 est un défaut
  de lecture SMB **transitoire sous charge concurrente** (recensement des
  doublons + workers). Le bug réel : un hoquet transitoire était écrit comme
  `failed` **permanent**, et le scan saute ensuite toute clé déjà dans le store
  → une photo saine exclue à jamais. Correctif : `_load_bgr` lit les octets avec
  retry (`_read_bytes_retry`) puis décode en mémoire (`io.BytesIO`) ;
  `face_worker`/`animal_worker` retentent `ImageReadError` 3× sans poisonner ;
  les scans re-enqueuent les `failed` transitoires (`_is_transient_io_fail`), donc
  les entrées déjà poisonnées repassent seules. Testé en isolation
  (`test_errno22_fix.py`, tout vert). **Reste : observer l'effet réel** — relancer
  le serveur, vérifier que ces fichiers repassent et réussissent, puis merger.
- **Encodage sémantique du fonds** — 29 549 photos encodées sur 30 682
  (96 %). Terminé pour l'essentiel.
- **Seconde passe de récupération** — les 945 fichiers à en-tête détruit n'ont
  jamais reçu la recherche de flux JPEG. Relancer
  `17 - Recuperer les images illisibles.bat`.
- **Remettre `recuperees/` sur le NAS** — ces images sont hors photothèque,
  donc ni taguées ni analysées.

## À faire, par ordre de valeur

### Reconnaissance

1. **Étoffer la vérité terrain humaine** — 91 photos confirmées sur 12 072
   taguées (0,8 %). Le banc de classification rejoué à l'échelle réelle a
   rendu 100 % : la mesure était devenue circulaire, l'auto-attribution ayant
   posé presque tous les tags. Corrigé (le jeu se limite aux confirmations
   humaines), mais 23 visages ne permettent pas de trancher. **Confirmer une
   centaine de propositions dans l'interface vaudrait plus que n'importe quel
   changement d'algorithme.**
2. **Regroupement par densité** (HDBSCAN, Chinese Whispers) à la place du
   seuil global unique. Un seuil ne peut pas servir à la fois des portraits
   nets et des profils de 90 px.
3. **AdaFace** sur le chemin de ré-embedding des visages faibles.
4. **Écrire les tags SigLIP** — aujourd'hui seulement proposés
   (`semantic.py --tags`). Décision à prendre : ils modifieraient les XMP.
5. **Comparer `qwen3-vl:2b` à SigLIP** sur le même échantillon annoté.
6. *(facultatif)* `MegaDescriptor-DINOv2-518` — dernière variante non testée.
   Peu d'espoir vu l'écart, mais `--equitable --modeles DINOv2-518` suffit.

> **La reconnaissance animale est à un bon point d'arrêt.** 97,4 % de rang-1,
> sept erreurs dont six sur la seule paire Inti/Luna — deux chats qui se
> ressemblent vraiment. Ni le modèle ni la résolution n'y changent rien : le
> gain restant est dans la donnée, pas dans l'algorithme.

### Harmonisation personnes / animaux / lieux

Le principe : **tout outil créé d'un côté doit servir de l'autre.** Les deux
pipelines résolvent le même problème — regrouper, nommer, corriger — et n'ont
divergé que par accident d'écriture.

| Capacité | Animaux | Personnes | À faire |
|---|---|---|---|
| Attribution unifiée (sous-ensemble, noms multiples, annulation) | oui | partiel | porter la sélection par vignette et les noms multiples côté visages |
| Vérification par SigLIP (« ce n'est pas un chat ») | oui | non | équivalent visages : rejeter un non-visage (statue, affiche, reflet) |
| Curateur avec suggestions et auto-attribution | non | oui | porter côté animaux : proposer des rattachements au lieu d'attendre un regroupement |
| « Trouver d'autres photos de X » | oui | oui | unifier le code, aujourd'hui dupliqué |
| Prototypes multiples | non (mesuré défavorable) | oui | rien à faire, décidé sur mesure |
| Fiche avec avatar, exclusions, confirmations | partiel | oui | même structure des deux côtés |

7. ✓ **FAIT (31/07)** — **Un magasin de sujets commun** (`SubjectStore`).
   `PEOPLE_STORE` et `PETS_STORE` unifiés derrière une seule abstraction ;
   14 fonctions devenues des wrappers. Vérifié contre la base réelle : aucune
   régression, aucun nom perdu. `find_more` applique désormais `exclude` aussi
   aux animaux.
8. **Une seule page « Sujets »** au lieu de Personnes et Animaux séparées :
   même gestes, filtre par type. Le lieu devient une troisième facette.

### Interface — redesign UI/UX « chambre noire »

Chantier à part entière : rendre l'application **belle, utile et agréable**, pas
seulement fonctionnelle. Aujourd'hui les 7 pages sont des chaînes littérales
dans `server.py`, antérieures au design system — la page d'upload emploie encore
le bleu iOS `#0a84ff` et des gris neutres, précisément les interdits de la skill
`photo-ui`. Le redesign applique la direction « chambre noire » partout, en
gardant le serveur stdlib **zéro build, zéro dépendance npm**. Ancrages : skill
`photo-ui` (tokens, composants, plancher d'accessibilité), `ui/prototype.html`,
et le **connecteur Figma** comme source de vérité des composants.

Méthode (règle `monolith-surgery`, non négociable) : **une page à la fois**,
d'abord extraite à l'identique vers `ui/`, ensuite redessinée — jamais les deux
mélangés. Un `bundle.py` réinjecte les assets pour conserver le livrable
mono-fichier. La bibliothèque Figma est le contrat ; `figma-design-to-code`
regénère le CSS/HTML natif. La page « Sujets » (point 8) et le garde-fou
d'upload (point 17) adoptent le nouveau système en premier — deux occasions de
valider les composants Figma sur du réel avant de propager aux pages historiques.

9. **Fondations** — extraire les 7 pages vers `ui/` (`tokens.css` + `base.css`),
   remplacer chaque valeur en dur par un token « chambre noire », corriger au
   passage les divergences existantes (`.pchip` vs `.chip`). Construire la
   bibliothèque Figma correspondante (`figma-generate-library`) et un `bundle.py`
   qui préserve le livrable mono-fichier.
10. **Plancher d'accessibilité (bloquant)** — `:focus-visible` partout, contraste
    AA, cibles 44 px, `prefers-reduced-motion`, `<button>`/`<a>` sémantiques,
    `alt` rédigés, navigation clavier. Aucun de ces sept points n'est satisfait
    aujourd'hui ; ils se traitent comme des tests, pas des intentions.
11. **Planche contact justifiée** — densité par `auto-fill` + `clamp()`, liseré
    `--veilleuse` par photo pour l'état pipeline, numéro de vue en marge ;
    `content-visibility` puis **virtual scroll** au-delà de ~2 000 vignettes.
    C'est la signature visuelle de l'app.
12. **Raccourcis clavier de tri** — `1`–`9` pour assigner, `Espace` confirmer,
    `X` rejeter, `Z` annuler, `Maj+clic` pour une plage ; documentés dans l'UI.
    Sert directement la priorité n°1 (confirmer vite 100 propositions).

Composants et gestes signature à intégrer au fil des pages (non numérotés, ils
traversent le chantier) :

- **Deux registres** — salle sombre pour *regarder* (`--salle`, planche contact),
  papier pour *décider* (`--feuille`, panneaux de nommage). Accents à sens
  unique : `--veilleuse` = IA en cours, `--fixateur` = confirmé humain,
  `--encre` = destructif. Jamais un accent « décoratif ».
- **Centre de tâches** — remplace le bandeau `#pending` : tâche en cours, restant
  à faire, appareil (`CPU`/`GPU`), bouton **Pause**. Données déjà disponibles
  (`hw_state()`, `system_busy()`, tailles des files).
- **View Transitions** (multi-document, sans SPA) sur galerie → photo → personne
  via `view-transition-name` — la seule animation qui mérite d'exister ici.
- **Toast d'annulation 10 s** pour toute action destructive (`role="status"`,
  `aria-live="polite"`), cohérent avec l'invariant « geste destructif différé et
  annulable ».

### Recherche

13. **Adapter l'encodage au matériel en temps réel** — `_device_cible()` décide
    déjà GPU/CPU selon la VRAM libre, mais la taille de lot, la précision et
    la résolution d'entrée restent fixes. Les rendre fonction de
    `hw_state()` : gros lots quand la carte est libre, repli progressif sinon.
14. **Carte et lieux dans la recherche** — les 684 photos géolocalisées
    devraient enrichir `lieux.txt` par géocodage inverse, et la page Carte
    partager le même vocabulaire que la barre de recherche.

### Données

15. **Fiche « Flo »** — 3 478 photos, 80 références, 17 exclusions. Fiche
    probablement mal constituée : c'est elle qui rend Florine ambiguë.
16. **Doublons de fiches** entre personnes et animaux.

### Ingestion et organisation des fichiers

17. ✓ **FAIT (31/07)** — **Upload de répertoires entiers depuis le téléphone.**
    La page d'upload (`HTML_PAGE`) a un second bouton « Choisir un dossier »
    (`<input webkitdirectory multiple>`, pris en charge par Chrome Android ; iOS
    Safari ne le gère pas). Le client envoie le `webkitRelativePath` de chaque
    fichier dans un champ `relpath` ; le serveur l'assainit via
    `_safe_upload_rel` (composants nettoyés comme un nom de fichier, `..` et
    racine absolue neutralisés, sous-dossiers préservés) et écrit sous
    `UPLOAD_DIR` en **préservant l'arborescence**. Les doublons sont sautés par
    **contenu, pas par nom** (`_upload_content_dup` : même taille d'abord, puis
    même sha256, réponse `SKIP`) — la même image revenant sous un autre nom ou
    dans un autre album est reconnue, et la page ne fabrique plus de doublons.
    Progression = compteurs envoyées / ignorées / erreurs. Invariant UI > NAS
    respecté : `note_heavy_activity()` est appelé en tête de chaque POST, donc
    chaque upload fait céder le travail de fond.

    > Deux modes cohabitent sans risque : un `relpath` avec sous-dossier =
    > mode DOSSIER (structure + dedup) ; un nom simple = mode PLAT (horodaté,
    > comportement historique inchangé). Les photos de sous-dossier sont
    > **taguées à l'upload** via `enqueue(clé_relative)` — indépendant du scan
    > racine, qui reste plat. Leur clé contient `/`, donc elles sont hors du
    > périmètre de purge du scan Uploads (`own = clés sans /`) : jamais
    > supprimées par mégarde. Reste à surveiller : une suppression manuelle sur
    > le NAS ne sera pas répercutée dans l'index (staleness mineure, comme pour
    > un dossier non configuré en `dossiers_a_taguer`).
18. **Réorganiser le système de fichiers depuis la vue « Dossiers ».** `/browse`
    (`BROWSE_PAGE`) est aujourd'hui en lecture seule. Ajouter des opérations sur
    photos **et vidéos** directement sur le NAS : déplacer, renommer, créer des
    dossiers, déplacements par lot depuis la sélection. Contraintes : chaque
    déplacement re-clé l'index (`TagStore.rekey`) pour ne perdre ni tags ni
    embeddings, opérations annulables, jamais de perte de nom humain. Les vidéos
    entrent ici dans le périmètre (le pipeline ne traite aujourd'hui que les
    photos).

19. **Dédoublonnage et rangement automatique par année.** Chantier à part entière,
    spécifié en détail dans **`docs/RANGEMENT_2026.md`** (problème mesuré,
    architecture, spec Phase 0, prérequis, décisions ouvertes, procédure de
    reprise). **Pour démarrer une nouvelle session** : « Lis
    `docs/RANGEMENT_2026.md`, charge `monolith-surgery`, et attaque la Phase 0. »

    Contexte mesuré : 37 % du fonds (10 882 photos) dort sous `_A TRIER`, mais le
    proxy nom+taille ne trouve que 133 doublons — le vrai volume ne se connaît
    qu'en **hashant les fichiers**, car des images identiques ont des noms
    différents. Principe retenu : un **démon d'analyse séparé** (lecture seule,
    hors serveur) produit un **plan à provenance** que le **serveur applique**
    (source unique de vérité pour l'index, `rekey` + undo). Dédoublonnage **sans
    perte** = détection par **contenu** (taille puis sha256, jamais le nom),
    fusion de l'union des tags/noms dans la copie canonique, puis **quarantaine
    réversible** (jamais de `rm`). Rangement par année via `_best_time`, le geste
    « `_A TRIER` → année » automatisé. Vidéos incluses.

    Séquencement, ordre non négociable (garantie « aucune info perdue ») :

    - **Phase 0 — recensement lecture seule** — écrit et validé, **lancé une fois
      (01/08) mais SANS RÉSULTAT CAPTURÉ : à relancer.** (`recensement_doublons.py`
      + `23 - Recenser les doublons.bat`, ASCII, `verifier_bat` vert). Le run a été
      interrompu avant l'écriture finale (`build_reports` n'écrit `docs/recensement.
      {md,json}` qu'à la toute fin) : les deux rapports **n'existent pas** sur le
      disque, la fenêtre du terminal s'est fermée avant. **Relancer depuis une
      fenêtre déjà ouverte, en capturant le log**, pour ne pas reperdre la sortie :
      `python recensement_doublons.py 2>&1 | Tee-Object docs\recensement_console.log`.
      Idée en attente (au choix de Mike) : ajouter une **écriture incrémentale**
      (checkpoint) au script pour qu'un run long survive à une coupure. Ce qu'il
      produira : vrai nombre de doublons **par contenu**, Go récupérables, carte
      `_A TRIER`/années, fichiers sans date — les chiffres qui trancheront les
      4 décisions ouvertes.
    - **Phase 1 — prérequis serveur, bloquant** : `vectors.rekey_prefix(old, new)`
      — ✓ **FAIT ET TESTÉ (31/07)** (`test_rekey_vectors.py` 12/12, `test_vectors`
      29/29). Octets préservés, borne `\x1f`, idempotent, collision bruyante.
      **Carte des empreintes corrigée** (voir `docs/RANGEMENT_2026.md`,
      « Avancement 31/07 ») : les stores faces/animaux transportent déjà leurs
      vecteurs via `rekey`+`save` ; les vrais trous sont le sémantique `PHOTO_VEC`
      (couvert par `rekey_prefix`) et le fait que le scan (~l. 1715) ne re-clé
      **que** le store `tags`. **Point de re-clé unique : ✓ FAIT ET TESTÉ
      (01/08).** `rekey_everywhere(old, new, save=True)` dans `server.py`
      (tags + FACE/PEOPLE/ANIMAL/PETS + `photo_vectors().rekey_prefix_all`),
      idempotent, branché au scan (batch-save). Bug corrigé au passage :
      `rekey_prefix_all` ratait la clé **nue** du sémantique (`kind='photo'`,
      0/30 826 avec séparateur) — désormais déplacée aussi, en transaction.
      Validé sur **copie** de la base réelle (`test_rekey_everywhere.py` : nom
      humain + visage + sémantique déplacés octet pour octet, idempotent ;
      `test_rekey_vectors` 12/12, `test_vectors` 29/29 inchangés). **Reste
      (non bloquant)** : la détection de déplacement du scan (~l. 1705) matche
      par **nom + taille** et rate les fichiers renommés ET déplacés → passer à
      la signature de contenu quand le démon écrira un hash par fichier (Phase 2).
      Le point de re-clé est prêt pour le renommage intelligent et le worker
      « appliquer un plan ».
    - **Phase 2 — démon d'analyse** produisant le plan JSON à provenance, relu
      par un humain avant application.
    - **Phase 3 — automatisation planifiée** (nightly), toujours quarantaine +
      undo.

    Note : le garde-fou anti-doublon **à l'upload** (point 17, `_upload_content_dup`)
    est déjà en place — il empêche d'*ajouter* des doublons ; ce chantier-ci
    nettoie ceux **déjà** sur le NAS.

---

## Cap long terme — multimodalité et recherche AI

Le projet a commencé par les **images** ; il ira vers la **vidéo** puis
l'**audio** (chantiers de fin de roadmap, dans cet ordre). Cette trajectoire doit
rester présente dans chaque décision d'architecture, même en travaillant sur les
images :

- Plusieurs briques incluent **déjà** les vidéos dans leur périmètre — rangement,
  dédoublonnage par contenu, renommage `YYYYMMDD_…`, vue Dossiers. Le pipeline IA,
  lui, ne tague encore que les photos ; la vidéo (échantillonnage de trames,
  éventuelle transcription) puis l'audio viendront ensuite.
- **Cap produit : une recherche AI dans le serveur**, où l'on pose des questions
  riches en langage naturel sur le fonds (« les étés à Bremblens avec Luna »,
  « les vidéos de Noël »). Cela suppose d'assembler des assertions/descriptions
  (à terme multimodales) et de les passer à un LLM de raisonnement — c'est là, et
  seulement là, que la **compression de contexte** (voir Outillage) deviendra
  pertinente, et que **exposer le serveur comme MCP** (`mcp-builder`) prendrait
  son sens, pour que n'importe quel agent interroge la médiathèque.

Ordre de valeur : consolider les images (reconnaissance, rangement, renommage,
UI), **puis** la vidéo, **puis** l'audio. Toute nouvelle abstraction (magasin de
vecteurs, magasin de sujets, schéma d'index) se conçoit en gardant ces deux
modalités futures à l'esprit, pour ne pas avoir à tout refaire.

## Décisions documentées

Toute évaluation aboutit à une entrée dans `eval/DECISIONS.md`. Quatre idées y
ont été **rejetées sur mesure** : les contre-exemples pour la classification,
les prototypes multiples pour les animaux, **MegaDescriptor** (deux fois :
une mesure invalide, puis une mesure valide), la **résolution des découpes**,
et `sqlite-vec`
(numpy exhaustif suffit, 10 ms sur 100 000 vecteurs).

Rejeter une idée sur mesure vaut autant qu'en adopter une : c'est ce qui évite
de la retester dans six mois. **Encore faut-il que la mesure soit valide** :
deux entrées du journal documentent des bancs d'essai qui ne mesuraient pas ce
qu'ils prétendaient — l'un circulaire, l'autre inéquitable.

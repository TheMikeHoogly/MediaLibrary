# Rangement, dédoublonnage et archivage — proposition

Réflexion d'architecture, non figée. Rédigée à la demande de Mike (31/07/2026).
Aucun code ne s'écrit avant la Phase 0 (recensement) et une décision chiffrée,
selon la règle du projet « mesurer d'abord ».

## Le problème, tel que décrit et tel que mesuré

Mike range ses photos ainsi : dépôt sur le NAS sous `_A TRIER`, puis copie dans
des dossiers par année (`2010`, `2011`…). Il oublie souvent d'effacer la copie
d'origine dans `_A TRIER`, d'où des doublons. La grande majorité des photos
n'ont pas de nom exploitable, donc une organisation **par année** vaut mieux
qu'une arborescence profonde.

Mesure sur l'index (copie lecture seule de `photos.db`, 29 647 photos) :

| Constat | Chiffre |
|---|---|
| Photos sous un chemin `_A TRIER` | 10 882 (**37 %**) |
| Photos sous un dossier année (`AAAA`) | 16 927 |
| Portant un nom humain (`personne:`/`animal:`) | 12 874 |
| Doublons « même nom + même taille » | 133 fichiers, ~0,3 Go |

**Ce que la mesure apprend, et qui change le plan :** le proxy par nom+taille ne
trouve presque rien (133), alors que 37 % du fonds est en zone de transit. Donc
soit les copies sont **renommées** en passant dans les années (le proxy les
rate), soit les vrais doublons ne se voient qu'au **contenu**. **On ne peut pas
chiffrer le dédoublonnage depuis l'index seul** — il faut hasher les fichiers.
C'est l'argument central pour une Phase 0 de recensement avant toute suppression.

Le vrai gros problème, lui, est déjà visible : **37 % du corpus dort dans
`_A TRIER`**, non rangé. La réorganisation par année a de la valeur
indépendamment du nombre de doublons.

## La contrainte qui gouverne tout : cohérence fichiers ↔ index ↔ XMP

Un rangement déplace et supprime des fichiers sur le NAS. Or l'état du projet
est réparti sur trois supports qui doivent rester d'accord :

1. **Les XMP dans les fichiers** — les noms humains (`personne:`, `animal:`) y
   sont écrits. Ils **voyagent avec le fichier** : un déplacement ne les perd
   pas, et `reconcile_named_tags()` / `reimport_name_tags()` savent les
   réimporter depuis les fichiers. C'est la source de vérité la plus robuste.
2. **L'index SQLite `photos.db`**, clé = **chemin**. Un déplacement rend la clé
   obsolète. Le serveur sait déjà re-clé les **tags** : au scan, il détecte un
   fichier déplacé par signature (nom + taille) et appelle `STORE.rekey(old,
   new)` — « index mis à jour sans re-tagging » (`server.py` ~1640).
3. **Les vecteurs** (empreintes visages / animaux / sémantique) dans la table
   BLOB, clé = **chemin** aussi. **Ici est le trou** : `vectors.py` a
   `delete_prefix` mais **aucun `rekey`**. Un déplacement re-clé les tags mais
   **oriente les empreintes vers le vide** — elles seraient recalculées (coûteux
   sur CPU, tout le pipeline tourne sur CPU) ou perdues.

> **Prérequis technique n° 1 : un `rekey_prefix(old, new)` dans `vectors.py`**,
> appelé sur le même chemin que `STORE.rekey`. Sans lui, tout déplacement de
> masse détruit le travail d'embeddings. C'est la première chose à écrire, avant
> même le démon.

Rappel des invariants (voir `monolith-surgery`) que le rangement ne doit pas
casser : noms humains jamais perdus, écriture d'index atomique, opérations
annulables, l'UI garde la priorité sur le NAS.

## Principe directeur : le démon PROPOSE, le serveur EXÉCUTE

Mike imagine un démon séparé qui range les fichiers. L'intention est juste — le
calcul lourd (hasher 30 000 fichiers, empreintes perceptuelles) n'a rien à faire
dans le serveur. Mais **laisser un second processus muter à la fois les fichiers
et la base pendant que le serveur tourne** désynchronise les caches mémoire du
serveur (`STORE.data`) et double les écrivains sur l'index — fragile.

La séparation propre est fonctionnelle, pas seulement « un autre programme » :

- **Le démon d'analyse (séparé, hors serveur, lecture seule)** parcourt le NAS,
  hashe, regroupe les doublons, calcule les dates, et produit un **plan de
  rangement** : un fichier JSON d'opérations proposées (déplacer, fusionner,
  mettre en quarantaine), **à provenance** (chaque opération dit pourquoi et sur
  quelle preuve). Il n'écrit jamais un fichier photo ni la base. Il peut tourner
  la nuit, en `nice`, et se met en pause quand le serveur signale de l'activité
  UI (même contrat que `REEMBED_UI_QUIET`).
- **Le serveur applique le plan** via un worker dédié qui possède déjà l'index,
  les caches, la file exiftool et la priorité UI. Chaque opération passe par
  `STORE.rekey` + `vectors.rekey_prefix` + mise à jour XMP, en transaction, et
  **annulable**. Un plan relu par un humain, appliqué par lots.

On garde ainsi une **source unique de vérité pour la mutation d'index**, on
réutilise `rekey`/`reconcile`, et le démon reste bien séparé pour ce qui coûte.
C'est aussi cohérent avec la direction « assertions à provenance » de l'audit :
un plan de rangement *est* un ensemble d'assertions sourcées.

## Dédoublonnage sans perte d'information

« Sans perte » ne veut pas seulement dire « ne pas effacer le mauvais fichier »,
mais **fusionner l'information avant de retirer une copie**.

- **La détection se fait sur le CONTENU, jamais sur le nom.** Deux images
  identiques peuvent porter des noms différents (renommées en passant dans un
  dossier année, ré-exportées, etc.). Leur seul point commun garanti est la
  **taille en octets** — mêmes dimensions, même encodage → mêmes octets. La
  taille est donc le **premier discriminant**, le hash confirme. C'est aussi
  pourquoi le recensement de l'index par nom+taille ne trouve que 133 doublons :
  il rate structurellement les copies renommées. **Corollaire à corriger** : la
  détection de déplacement du serveur (`scan`, ~l. 1640) matche elle aussi par
  *nom + taille* ; un fichier renommé ET déplacé lui apparaît comme
  suppression + nouveauté, et perd son rekey. Elle devrait migrer vers la
  signature de contenu.
- **Doublon exact** : contenu identique. Détection en deux temps pour tenir sur
  30 000 fichiers — d'abord regroupement par **taille** (gratuit, déjà dans
  l'index), puis hash complet (`sha256` ou `xxhash`) uniquement sur les groupes
  de même taille. Fiable, sans faux positif, indépendant du nom.
- **Quasi-doublon** (même photo ré-encodée, redimensionnée, tournée) : empreinte
  perceptuelle (pHash/dHash). **Jamais supprimé automatiquement** — catégorie à
  revue humaine, car deux photos proches d'une rafale ne sont pas des doublons.
- **Fusion avant retrait** : parmi les copies d'un groupe, on choisit une
  **canonique** (voir plus bas), on migre vers elle l'**union** des tags et des
  noms des autres copies (dans son XMP via exiftool **et** dans l'index), puis
  seulement on retire les autres.
- **Retrait = quarantaine réversible**, jamais `rm`. Les copies retirées vont
  dans une `.corbeille-rangement/` sur le NAS avec un manifeste (origine, groupe,
  canonique retenue, date), conservées N jours puis purgées. Annulable, à
  l'image de tous les gestes destructifs du projet (délai + undo).

**Choix de la canonique** : préférer la copie déjà dans un dossier année à celle
de `_A TRIER` ; à défaut, la plus renseignée (noms humains, puis tags). La copie
`_A TRIER` est presque toujours celle à retirer — c'est le geste que Mike fait à
la main.

## Réorganisation par année

- Cible : `Photos/AAAA/` (option `AAAA/AAAA-MM` si un jour utile ; par défaut
  année seule, comme demandé).
- Date : `_best_time()` existe déjà — `DateTimeOriginal` → `CreateDate` →
  `ModifyDate`, puis date lisible dans le nom de fichier, puis `_SANS_DATE/` si
  rien. On ne devine jamais : sans date fiable, la photo va dans un bac explicite
  à trancher, pas dans une année au hasard.
- Le geste « `_A TRIER` → année » est automatisé : un fichier de `_A TRIER`
  absent ailleurs est **déplacé** vers son année (tags et empreintes re-clés) ;
  un fichier de `_A TRIER` déjà présent ailleurs (par hash) est **mis en
  quarantaine** (c'est le doublon oublié).
- **Vidéos incluses** : elles se déplacent et se rangent comme les photos (le
  pipeline IA ne les tague pas, mais le rangement ne les ignore pas).

## Doublons à l'upload (page web) — garde-fou de première ligne

Il ne suffit pas de nettoyer après coup : **la page d'upload ne doit pas
fabriquer les doublons** que le démon devra ensuite retirer. Deux pièges y
existaient et sont désormais traités (`server.py`, handler `/upload`) :

- Le mode « fichiers » horodatait chaque nom, donc ré-envoyer la même photo la
  dupliquait ; le mode dossier ne comparait que par chemin + taille.
- **Correctif en place** : avant d'écrire, le serveur cherche un fichier au
  **contenu identique** sous `UPLOAD_DIR` — **même taille d'abord, puis même
  sha256**, quel que soit le nom ou le sous-dossier — et répond `SKIP` si trouvé.
  Le contrôle couvre les deux modes et les fichiers d'un même album entre eux
  (index taille→chemins mis en cache, TTL court, complété à chaque écriture).

Portée volontairement limitée à l'arbre `UPLOAD_DIR` : c'est un garde-fou local
et bon marché (on ne hashe que les fichiers de même taille). Le dédoublonnage à
l'échelle du NAS entier (`_A TRIER`, années) reste le travail du démon, avec sa
fusion d'information et sa quarantaine réversible. Le jour où le démon écrit un
hash de contenu dans l'index pour chaque fichier, ce garde-fou pourra
s'appuyer dessus et couvrir tout le fonds sans surcoût.

## Ne pas perturber le serveur

- Démon d'analyse : lecture seule, `nice`, planifié la nuit, cède à l'UI.
- Exécution : worker serveur à priorité UI, par lots, `note_heavy_activity`
  respecté, chaque opération annulable, **dry-run par défaut**.
- **Journal de provenance** : chaque déplacement et chaque fusion sont tracés
  (d'où vient le fichier, quelle copie a été retenue, quelles infos fusionnées).
  Auditable, réversible, et matière à confiance avant d'automatiser.

## Séquencement proposé (mesurer d'abord)

1. **Phase 0 — Recensement, lecture seule, sur le NAS.** Un script indépendant
   hashe tous les fichiers et rend un rapport : vrai nombre de doublons exacts et
   quasi-doublons, octets récupérables, cartographie de `_A TRIER` vs années,
   fichiers sans date fiable. **Aucune écriture.** C'est ce rapport qui dit si le
   dédoublonnage vaut l'effort et calibre les seuils. Livrable immédiat et utile.
2. **Phase 1 — Prérequis serveur.** `vectors.rekey_prefix(old, new)` + un worker
   « appliquer un plan de rangement » (déplacer / fusionner / quarantaine),
   idempotent, annulable, testé sur **copie** de la base réelle avant tout usage
   en vrai.
3. **Phase 2 — Démon d'analyse.** Produit le plan JSON à provenance ; l'humain
   le relit ; le serveur l'applique par lots.
4. **Phase 3 — Automatisation planifiée** (nightly), toujours quarantaine +
   undo, jamais de suppression dure.

## Décisions tranchées (avec Mike, 31/07)

1. **Suppression des doublons : quarantaine réversible 30 jours.** Jamais de `rm`
   direct. Les copies retirées vont dans `.corbeille-rangement/` sur le NAS avec
   manifeste (origine, groupe, canonique retenue, date), purgées après 30 jours.
2. **Granularité des dossiers : année seule** (`Photos/AAAA/`). Pas d'année/mois.
3. **Quasi-doublons (pHash) : revue humaine obligatoire pour commencer.** Aucun
   auto-retrait au départ. **Cap visé : un maximum d'automatisation à l'avenir** —
   au fur et à mesure que la confiance se mesure (précision du seuil sur un jeu
   relu), on pourra auto-retirer au-dessus d'un seuil très prudent. Les doublons
   *exacts* (sha256), eux, ne sont pas concernés par cette prudence : contenu
   identique = décision sûre.
4. **Qui mute la base : plan / exécution séparés.** Le démon d'analyse (lecture
   seule) PROPOSE un plan à provenance ; le serveur, seul écrivain de l'index,
   l'APPLIQUE (rekey + undo). Pas de démon autonome mutant la base en parallèle.

Ces choix figent la Phase 2/3 : quarantaine 30 j, année seule, quasi-doublons en
revue (automatisation croissante ensuite), source unique de vérité côté serveur.

---

## Spécification de la Phase 0 — recensement (à implémenter en premier)

But : un chiffre, pas une intuition. **Lecture seule, aucune écriture sur le NAS
ni sur `photos.db`.** Le démon complet viendra après, sur la foi de ce rapport.

**Fichier** : `recensement_doublons.py` (script autonome, hors `server.py`, stdlib
+ `Pillow` déjà présent). Lancé par un `.bat` numéroté (ASCII pur, cf. règle
absolue), p. ex. `23 - Recenser les doublons.bat`.

**Entrées** : les racines réelles du fonds — `UPLOAD_DIR`, plus les dossiers de
`dossiers_a_taguer.txt` et `dossiers_a_explorer.txt` (mêmes racines que
`media_roots()`). Extensions : `IMAGE_EXT` + vidéos (`.mp4 .mov .avi …`).

**Algorithme** (taille d'abord, hash ensuite — jamais le nom) :

1. Énumérer tous les fichiers, noter `(chemin, taille, mtime)`. Ignorer les
   chemins cachés (`.`, `@eaDir`, `#recycle`) comme `_is_hidden_path`.
2. Grouper par **taille**. Une taille unique = pas de doublon possible, on ne la
   hashe pas (économie majeure).
3. Pour chaque groupe de taille ≥ 2 : hash rapide (premiers + derniers 64 Ko),
   re-grouper ; puis `sha256` complet uniquement sur les sous-groupes encore
   collés. Un groupe final de même sha256 = doublons exacts, **quel que soit le
   nom**.
4. Quasi-doublons (optionnel, phase 0.5) : pHash sur une réduction 32×32, à ne
   **rapporter que**, jamais agir.

**Sorties** (dans `eval/` ou `docs/`, lecture humaine) :

- `recensement.json` : groupes de doublons, chemins, taille, octets récupérables,
  et pour chaque groupe la **canonique proposée** (règle : dossier année >
  `_A TRIER` ; puis le plus renseigné selon l'index — croiser avec `STORE.data`
  en **lecture seule**, copie `/tmp` si depuis un bac à sable).
- `recensement.md` : synthèse chiffrée — nb de doublons exacts, Go récupérables,
  répartition `_A TRIER` vs années, fichiers **sans date EXIF fiable** (candidats
  `_SANS_DATE`), plus grosses années.

**Garde-fous** : ouvrir `photos.db` en lecture seule (`mode=ro`), ou mieux, ne
lire que le système de fichiers pour la Phase 0 et ne croiser l'index qu'ensuite.
N'écrire nulle part ailleurs que les deux rapports. Respecter l'UI : `nice`,
pauses, exécution hors heures d'usage.

## Prérequis technique bloquant (Phase 1, avant tout déplacement)

`vectors.rekey_prefix(old_key, new_key)` dans `vectors.py`, sur le modèle de
`delete_prefix` (mêmes bornes de préfixe `k` … `k + '￿'`), appelé partout où
`STORE.rekey` l'est déjà (`server.py` ~l. 1640, et le futur worker de rangement).
Test : sur copie de la base, déplacer une photo nommée, vérifier que ses tags,
ses visages et ses empreintes chat/sémantique suivent, et qu'aucun nom humain
n'est perdu. Sans ce test vert, aucun déplacement de masse.

## Comment reprendre ce chantier dans une nouvelle session

1. Lire ce document en entier, puis `ROADMAP.md` point 19.
2. Charger la skill `monolith-surgery` (le worker d'exécution touchera
   `server.py`) et `vision-eval` si un seuil de quasi-doublon est en jeu.
3. Commencer par la **Phase 0** ci-dessus — c'est un livrable isolé, sans risque,
   qui donne les chiffres pour trancher les 4 décisions ouvertes.
4. Ne rien supprimer ni déplacer tant que : (a) le rapport Phase 0 est relu,
   (b) `vectors.rekey_prefix` est écrit **et testé** sur copie, (c) la quarantaine
   réversible est en place. Ordre non négociable — c'est la garantie « aucune
   info perdue ».

---

## Avancement — 31 juillet 2026 (session)

**Phase 0 livrée (à lancer par Mike).** `recensement_doublons.py` (autonome,
stdlib + Pillow, **lecture seule**) et son lanceur `23 - Recenser les
doublons.bat` (ASCII pur, passe `verifier_bat.py`) sont écrits. Le script lit
les vraies racines (`dossier_uploads.txt` + `dossiers_a_taguer.txt` +
`dossiers_a_explorer.txt`, dédupliquées comme `media_roots()`), énumère les
médias (mêmes `IMAGE_EXT` + vidéos), ignore les chemins cachés, **groupe par
taille puis hash** (rapide 64 Ko, puis sha256 complet uniquement sur les
collisions), et écrit `docs/recensement.md` + `docs/recensement.json`. Il
rapporte : doublons exacts par **contenu**, octets récupérables, canonique
proposée par groupe (dossier année > `_A TRIER` > chemin le plus court),
répartition `_A TRIER`/année/autre, et dates classées **exif / nom / chemin
(approx.) / aucune** (candidats `_SANS_DATE`). Validé sur un arbre fabriqué :
doublon renommé détecté, faux doublon de même taille correctement séparé,
`@eaDir` et non-médias ignorés. **Rien n'est écrit ailleurs que les deux
rapports.** Il reste à le lancer sur le NAS pour obtenir les vrais chiffres qui
tranchent les 4 décisions ouvertes.

**Prérequis Phase 1, partie 1 : `vectors.rekey_prefix` écrit et testé.**
`VectorStore.rekey_prefix(kind, old, new)` et `rekey_prefix_all(old, new)` sont
dans `vectors.py`. Ils réécrivent en une requête SQL le seul préfixe
`{clé_photo}` des clés `{clé_photo}\x1f{champ}\x1f{index}`, **octets préservés à
l'identique**. Borne prise sur `old + '\x1f'` (le séparateur exact que `_ecrire`
utilise déjà pour purger) : un déplacement de `a/b.jpg` n'emporte jamais
`a/b.jpg2`. Idempotent (rejoué → 0), collision sur l'index UNIQUE →
`IntegrityError` sans corruption partielle. Prouvé par `test_rekey_vectors.py`
(12/12) ; `test_vectors.py` reste vert (29/29).

**Correction de la carte des empreintes — plus fine que ce que ce document
disait.** En câblant, j'ai vérifié où vivent réellement les vecteurs, et le
« trou » n'est pas exactement celui décrit plus haut :

- Il y a **plusieurs `Store`** (`store_sqlite.py`), un par table — `tags`,
  `faces`, `people`, `animals`, `pets` — chacun avec **son propre**
  `VectorStore` (sur sa propre connexion), keyé par le nom de table comme
  `kind`. Plus le **sémantique** `PHOTO_VEC = VectorStore(STORE.cx)`
  (`server.py` ~l. 1880), un magasin encore distinct.
- Pour les stores **à vecteurs** (faces/people/animals/pets), `Store.rekey` +
  `save()` **transportent déjà** les empreintes : `_reconcilier` supprime
  l'ancienne clé (donc son préfixe vecteur) et ré-`extraire` la nouvelle depuis
  l'entrée en mémoire, où les embeddings sont toujours présents (réinjectés au
  chargement). Donc, contrairement à ce que ce doc affirmait, un `rekey` sur
  ces stores **ne perd pas** les empreintes.
- **Les deux vrais trous :** (1) le sémantique `PHOTO_VEC` n'a **aucun chemin de
  re-clé** — c'est précisément ce que `rekey_prefix` couvre ; (2) à
  `server.py` ~l. 1715, la détection de déplacement du scan ne re-clé **que le
  store `tags`** (`STORE.rekey`) : elle n'appelle jamais `FACE_STORE.rekey`,
  `ANIMAL_STORE.rekey`, etc., ni ne re-clé `PHOTO_VEC`. Un fichier déplacé
  garde donc ses détections visages/animaux **sous l'ancienne clé** (orphelines,
  purgées au scan suivant) et son embedding sémantique orphelin.

**Prochain pas (à faire dans une session relue, monolith-surgery + copie de la
base réelle).** Écrire le point de re-clé unique appelé à chaque déplacement —
au scan (`server.py` ~l. 1715) et dans le futur worker « appliquer un plan » —
qui, pour `old → new`, doit :
1. re-clé le store `tags` (`STORE.rekey`, déjà fait) ;
2. re-clé **chaque** store de sujets présent (`FACE_STORE`, `PEOPLE_STORE`,
   `ANIMAL_STORE`, `PETS_STORE`) via leur `rekey` + `save` (transport auto des
   vecteurs) — repérer les noms exacts des globales dans `server.py` ;
3. re-clé le sémantique via `get_photo_vec().rekey_prefix_all(old, new)`.

À tester sur **copie** de la base réelle : déplacer une photo nommée + avec
visage + avec embedding sémantique, vérifier que tags, détections et empreintes
suivent, et qu'aucun nom humain n'est perdu. Sans ce test vert, aucun
déplacement de masse (invariant du chantier).

---

## Avancement — 1 août 2026 (session) : le point de re-clé unique est FAIT et TESTÉ

**`rekey_everywhere(old, new, mtime=None, save=True)`** est écrit dans
`server.py` (juste après `photo_vectors()`) et **branché au scan** (~l. 1715,
`save=False` + batch-save des cinq stores). Il compose, en un geste idempotent :
`STORE.rekey` (tags, décide du déplacement) + `rekey`+`save` sur
`FACE_STORE`/`PEOPLE_STORE`/`ANIMAL_STORE`/`PETS_STORE` (le `save` transporte
leurs vecteurs via `delete_prefix` + ré-`extraire`) + `photo_vectors().rekey_prefix_all`
(sémantique). `save=False` diffère toutes les sauvegardes au batch appelant.

**Deux corrections de fond découvertes en câblant :**

1. **Le nom réel de la globale est `photo_vectors()`, pas `get_photo_vec()`**
   (ce doc et la ROADMAP l'appelaient à tort ainsi). Vérifié par grep, comme
   l'exige `monolith-surgery` (« repérer les noms exacts des globales »).

2. **BUG dans `vectors.rekey_prefix_all`, attrapé par le test sur données
   réelles.** Les vecteurs sémantiques (`kind='photo'`) sont keyés par le
   **chemin NU** (`k == chemin`, un vecteur par photo), **sans** le suffixe
   `\x1f{champ}\x1f{i}` des visages/animaux. Or `rekey_prefix_all` ne bornait
   que sur `old + '\x1f'` : il **excluait** la clé nue et laissait le vecteur
   sémantique orphelin sous l'ancienne clé. Sur la base réelle : **0/30 826
   vecteurs `photo` portent un séparateur** — le cas nu était donc la totalité,
   pas un cas rare. Corrigé : `rekey_prefix_all` déplace maintenant **aussi** la
   clé nue (`UPDATE … WHERE k = old`), dans la **même transaction** que la forme
   à préfixe (collision → rollback, échec bruyant, pas de corruption partielle).
   La clé nue est appariée à l'identique, donc un voisin `{old}2` reste intact.

   > Rappel de méthode du projet vérifié une fois de plus : *un test qui passe
   > n'est pas un test qui prouve*. La première version « verte » du test ne
   > capturait le vecteur sémantique que par préfixe (0 ligne) — la vérification
   > d'octets tournait à vide. Corrigé pour apparier la clé nue : c'est alors
   > qu'il a exposé le bug de `rekey_prefix_all`.

**Preuve.** `test_rekey_everywhere.py` — **lecture d'une COPIE `/tmp` de la base
réelle, jamais la vraie** — tire une photo réelle portant un nom humain + un
vecteur visage + un vecteur sémantique, applique la séquence exacte de
`rekey_everywhere`, et vérifie : nom(s) `personne:`/`animal:` préservé(s),
détections et empreintes (visage + sémantique) déplacées **octet pour octet**,
plus rien sous l'ancienne clé, totaux de vecteurs inchangés, idempotence
(rejeu = no-op). Tout vert (ex. run : `_Uploads/ARZOPA/…` avec
`personne:Flo`+`personne:Mike`, 2 visages + 1 sémantique). Régressions
inchangées : `test_rekey_vectors.py` 12/12, `test_vectors.py` 29/29.

**Reste sur ce prérequis (non bloquant pour le principe, déjà couvert) :** la
détection de déplacement du scan matche encore par **nom + taille**
(`server.py` ~l. 1705-1712) et rate un fichier **renommé** ET déplacé (vu comme
suppression + nouveauté). À migrer vers la signature de **contenu** quand le
démon d'analyse écrira un hash par fichier dans l'index (Phase 2). Le point de
re-clé, lui, est prêt à être appelé par le renommage intelligent et le worker
« appliquer un plan ».

---

## Renommage intelligent — spec convergée (31/07, avec Mike)

Nouveau volet du chantier, décidé avec Mike : au-delà de ranger par année,
**renommer** les fichiers de façon lisible, chronologique et auto-descriptive.
**On commence par `_Uploads`** — bac à sable sûr, fichiers récents du téléphone,
tagging à l'upload déjà en place — avant de propager aux années historiques.

**Place dans le flux.** Le nom n'est fabriqué qu'**en dernier**, quand tous les
faits sont connus :

> upload → tag LLM (déjà fait à l'upload) → visages/animaux → géocodage si GPS →
> assemblage du nom depuis les assertions → application (renommage NAS + re-clé
> d'index + journal de provenance + undo).

C'est cohérent avec la direction « assertions à provenance / fusion
programmatique » : déterministe quand on peut, LLM seulement en dernier recours.

**Format retenu**

```
YYYYMMDD_<lieu-ou-type>_<sujet>.<ext>
```

- **`_`** sépare les trois champs ; **`-`** sépare les mots dans un champ.
- **Tri lexicographique = chronologique** grâce à `YYYYMMDD` (8 chiffres, et non
  6 : c'est aussi le seul format que `_fname_time` sait relire → la date inscrite
  redevient lisible par le système).

**Champ 1 — date.** `_best_time()` : EXIF → date dans le nom → année du dossier.
Aucune date fiable → préfixe **`00000000`** (regroupe et signale les indatés en
tête de tri ; jamais de date inventée).

**Champ 2 — lieu, sinon type.** Lieu par ordre de confiance : (1) GPS inversé
(684 photos géolocalisées) ; (2) lieu déduit du chemin (`lieux.txt`, 120
lieux) ; (3) tag humain de lieu. À défaut de lieu : **type d'image** issu du
vocabulaire contrôlé SigLIP (portrait, groupe, paysage, animal, document,
affiche, oeuvre-d-art…) — déterministe, borné, sans hallucination.

**Champ 3 — sujet.** Noms humains d'abord : un `personne:`/`animal:` présent fait
le cœur du nom (`Luna`, `Mike-et-Flo`) — le fait le plus fiable du corpus, déjà
dans le XMP. À défaut seulement, distiller la **description LLM** en un slug
court. C'est la seule partie non déterministe, donc la plus encadrée.

**Assainissement (décisions Mike).**
- **Repli ASCII** (sécurité + rétrocompatibilité SMB) : `unicodedata` NFKD +
  suppression des diacritiques, plus une petite table pour les cas que NFKD ne
  couvre pas (`œ`→`oe`, `æ`→`ae`, `ø`→`o`, `ß`→`ss`).
- **Tirets, lisible.** Espaces et ponctuation → `-` ; caractères interdits
  Windows (`/ \ : * ? " < > |`) et de contrôle retirés ; pas de nom réservé
  (`CON`, `PRN`…). Défaut proposé (à valider) : lieu/type en minuscules, sujet
  conserve la casse des noms propres.
- **Longueur.** Nom complet plafonné (proposé : **≤ 120 caractères**), champ
  sujet tronqué sur une frontière de mot. Surveiller le **chemin entier** (NAS +
  arborescence) sous ~260 caractères, pas seulement le nom.
- **Collisions.** Deux fichiers produisant le même nom → suffixe court
  `-<4 hex du sha256>`.

**Automatisme : direct (décision Mike).** Sur `_Uploads`, renommage
**automatique**, sans revue préalable — mais **entièrement réversible**, ce qui
rend le garde-fou de réversibilité d'autant plus critique :
- **Idempotence** : un fichier déjà au format (`^\d{8}_…` + trace « auto-renommé »
  dans la provenance) n'est pas re-préfixé.
- **Provenance + undo** : nom d'origine conservé (journal JSON **et** champ XMP),
  renommage annulable par lot — même invariant que tous les gestes mutateurs.
- **Re-clé** : chaque renommage passe par le point de re-clé unique (Phase 1) —
  `STORE.rekey` + stores sujets + `PHOTO_VEC.rekey_prefix_all` — pour ne perdre
  ni tags, ni détections, ni empreintes, ni nom humain.

**Exemple.** `IMG_20190704_123045.jpg` (GPS = Bremblens, `personne:Luna`) →
`20190704_bremblens_Luna.jpg`. Sans lieu ni nom : `20190704_paysage_lac-au-couchant.jpg`.

**Micro-décisions encore ouvertes** (défauts proposés ci-dessus, à confirmer) :
casse exacte du champ sujet, plafond précis de longueur, et présence ou non d'un
`SANSDATE` explicite en plus du `00000000`.

**Avancement — 1 août 2026 : le CŒUR DÉTERMINISTE est codé et testé.**
`renommage.py` (stdlib pure, **aucune mutation NAS/index**) fait l'assemblage
`YYYYMMDD_<lieu-ou-type>_<sujet>.<ext>` et tout l'assainissement : repli ASCII
(NFKD + table `œ/æ/ø/ß/ł/đ/þ`…), tirets, retrait des caractères Windows
interdits, neutralisation des noms réservés (`CON`, `COM1`…), plafond 120 avec
troncature du sujet **sur frontière de mot**, suffixe de collision
`-<4 hex sha256(graine)>`, idempotence (`^\d{8}_` **plus** trace de provenance,
pour ne pas re-préfixer une photo d'appareil `20190704_…`). API : `propose_basename(facts)`
où `facts` porte les faits déjà résolus par l'appelant (date `_best_time`,
GPS/`lieux.txt`/tag lieu, type SigLIP, noms, description).

Défauts implémentés (les micro-décisions ci-dessus, à valider par Mike) : sujet
en **casse conservée** (noms propres), lieu/type et sujet-issu-de-description en
**minuscules** ; plafond **120** ; **`00000000`** sans `SANSDATE` séparé ; noms
multiples **triés** (déterminisme) joints par `-et-`, plafonnés à 3 puis
`-et-al` — la spec illustrait `Mike-et-Flo` (ordre d'entrée) ; j'ai préféré le
tri pour qu'un même cliché produise **toujours** le même nom quel que soit
l'ordre des tags. À trancher.

Preuve : `test_renommage.py` (≈40 assertions vertes) — repli ASCII, slug, champs,
assemblage, plafond/troncature, réservés, collision, idempotence, les deux
exemples de la spec (`…_bremblens_Luna.jpg`, `…_paysage_lac-au-couchant.jpg`),
plus un **dry-run sur copie de la base réelle** : 161 vrais noms humains accentués
(`Ordoñez`, `Aurélie de Lalande`, `Béa`…) → slugs ASCII sûrs, zéro caractère
interdit.

**Résolveur de faits + dry-run — FAITS (01/08, lecture seule).**
`renommage_facts.py` (pur, aucune mutation) reflète `_best_time` / `_fname_time`
/ `_path_year` / `lieux_connus` : `resolve_facts(key, entry, lieux)` assemble le
dict `facts` (date+précision, lieu-chemin, noms, description, ext, graine) depuis
une entrée d'index. `dry_run_renommage.py` l'applique sur une **copie** de la
base et montre les noms proposés pour `_Uploads` — c'est ce qui se relit avant
d'activer l'application.

Le dry-run (1 025 photos `_Uploads` indexées) a **exposé trois défauts, tous
corrigés avant toute mutation** — l'intérêt même du dry-run :

1. **Sujet-description monstrueux** : sans nom, je slugais la description LLM
   entière. Ajout de `_distill()` (retire les articles de tête, garde les
   connecteurs internes, plafonne à 5 mots) → `vue-panoramique-d-une-montagne`,
   `deux-cocktails-sur-une-table` au lieu d'un pavé de 110 caractères.
2. **`-et-al` doublé** (`Alba-et-Flo-et-Flora-et-et-al`) → corrigé en
   `…-et-Flora-et-al`.
3. **Faux lieu** : d'abord « Bremblens » venait du **hostname** `\\NAS-Bremblens`
   (corrigé : on retire `\\hôte\partage`), puis « Upload » venait du dossier de
   transit `_Uploads` matchant une entrée parasite de `lieux.txt` (corrigé : on
   exclut les composants préfixés `_`, convention des dossiers système du
   projet). Résultat honnête : **0 lieu-chemin** sur `_Uploads` (photos du
   téléphone, sans dossier-lieu) — le lieu viendra du **GPS EXIF** (géocodage) et
   le type du **SigLIP**, tous deux branchés à l'application côté serveur.

Chiffres du dry-run : 795/1 025 avec nom humain, dates toutes `exact` (noms de
fichier horodatés), **475 collisions** de nom (rafales même date+mêmes noms)
résolues par le suffixe `-<4hex>`. Tests : `test_renommage.py` reste vert après
les correctifs.

**Deux décisions tranchées (01/08, avec Mike) et appliquées :**

- **Heure injectée dans le nom.** Le champ date devient `YYYYMMDD-HHMMSS` quand
  l'heure est connue (EXIF `taken` ou nom horodaté), `YYYYMMDD` sinon. Réduit les
  collisions de rafale (dry-run : 475 → 353) et préserve l'ordre intra-journée.
  `field_date` et l'idempotence acceptent les deux formes ; résiduel géré par le
  suffixe `-<4hex>` stable. Ex. `20260608-083049_lac-bleu-entoure-de-montagnes.jpg`.
- **`lieux.txt` nettoyé sémantiquement.** `nettoyer_lieux.py` valide par **liste
  blanche géographique** (le savoir « lieu vs non-lieu ») : 97 entrées → **28
  vrais lieux**, 59 rejetées (événements, activités, marques, patronymes). Les
  entrées multi-mots sont décomposées (`Appart Bremblens` → `Bremblens` ;
  `CoRo Manifestation Birmanie Genève` → `Birmanie`, `Genève` ;
  `SanBorjaTriniSRZ` → `San Borja`, `Trinidad`, `Santa Cruz` via camelCase +
  alias). Réversible (`lieux.txt.bak` + rejetés en commentaires). Option
  `--ollama` pour valider les inconnus au LLM local (futurs dossiers). Vérifié
  sur photos réelles : `20070000_birmanie_Virginie-Thurre.jpg`, plus aucun faux
  « Upload ». **À noter (dette) :** `server.lieux_connus()` REGÉNÈRE la liste
  heuristique brute si le fichier est supprimé — brancher `nettoyer_lieux` dans
  cette génération, ou ne pas supprimer le fichier.

**Reste (application, mutant — différé sciemment).** Le renommage RÉEL touche le
NAS : renommage du fichier + `rekey_everywhere` (fait) + journal de provenance
(nom d'origine en JSON **et** XMP) + undo par lot, appelé à l'upload sur
`_Uploads`. Il attend (a) la fin du recensement (ne pas muter le NAS pendant
qu'il le parcourt) et (b) une session relue testée sur copie. Il branchera
`resolve_facts` sur le GPS inversé et le type SigLIP (les deux faits laissés à
None aujourd'hui). Le cœur et le résolveur, eux, sont prêts et prouvés.

# Performance — ce qui est mesuré, et ce qui reste à faire

> Ouvert le **10/09/2026 au soir**, pendant la campagne de retag. Tout ce qui
> est chiffré ici a été **observé sur la machine de Mike**, pas estimé. Quand un
> chiffre manque, c'est écrit en toutes lettres — une performance supposée n'est
> pas une performance.

---

## 0. La règle de ce chantier

**Mesurer d'abord, sur la vraie machine, sous la vraie charge.**

Ce projet a déjà payé pour l'avoir oublié. Le 09/09, un instrument aveugle a
annoncé 136 Ko de ménage là où il y en avait 349,8 Mo. Le 10/09, une correction
de cache posée sur deux chemins d'écriture sur trois est passée verte parce que
le banc listait les chemins connus au lieu de compter les absents. Un chiffre
qu'on n'a pas vu tomber n'est pas un chiffre.

D'où l'ordre, non négociable :

1. une **horloge** dit quelle route coûte ;
2. un **banc** dit pourquoi, en comparant deux écritures sur la même donnée ;
3. la correction est écrite, **testée contre l'ancienne écriture prise pour
   oracle**, livrée, puis **réobservée en réel** ;
4. la même horloge dit si le chiffre a bougé.

Sans l'étape 4, on n'a pas optimisé : on a espéré.

---

## 1. L'horloge des routes — l'instrument

Livrée le 10/09 (`feat/horloge-des-routes`, fusionnée en `743fef9`).

Elle se pose dans les enveloppes de `do_GET` / `do_POST`, jamais dans le
routeur de 250 lignes : une horloge qui oblige à toucher chaque branche finit
par ne mesurer que les branches qu'on a pensé à instrumenter.

- `_route_perf(methode, chemin)` replie les routes à argument —
  `/media/`, `/uploads/`, `/face_thumbs/`, `/animal_thumbs/` deviennent
  `préfixe + '*'`. Sans ce repliage, `/api/thumb?key=…` ferait 44 604 lignes de
  tableau et aucune information.
- `_perf_note` **ne lève jamais**. Un instrument qui fait tomber la requête
  qu'il mesure est pire que pas d'instrument.
- Six seaux : `< 30 ms`, `30–100`, `100–300`, `300–1 000`, `1 000–3 000`,
  `> 3 000`. Le total dit où part le temps de la machine ; les seaux disent ce
  que **ressent** celui qui attend. Les deux vues sont nécessaires et ne
  désignent pas le même coupable.
- `_perf_routes.json` est déposé à chaque cycle de maintenance (~5 min) et
  `/api/perf` le rend à la demande.

> Le 10/09 à 22:56, le fichier a d'abord semblé absent : le banc l'a cherché
> **2 min 40 avant** le premier cycle. Ce n'était pas une panne. Un instrument
> qui écrit périodiquement doit dire *quand* il écrira — celui-ci le dit
> maintenant dans son message d'absence.

### Le premier relevé — 10 min de trafic réel, 10/09 22:56 → 23:06

| Route | n | total | pire | ce que ça dit |
|---|---:|---:|---:|---|
| `GET /files` | 2 | 32,7 s | **31,4 s** | la page la plus utilisée du site |
| `GET /api/corbeille` | 2 | 8,2 s | 4,88 s | **sous `FILE_OPS_LOCK`** |
| `GET /api/pets/list` | 1 | 2,87 s | 2,87 s | boucle imbriquée |
| `GET /api/geo` | 2 | 1,95 s | 993 ms | tout l'index à chaque ouverture de la carte |
| `GET /api/maint/status` | 4 | 1,68 s | 532 ms | **les quatre** entre 300 ms et 1 s |
| `GET /api/sensibles` | 10 | 1,27 s | 448 ms | |
| `GET /api/facecrop` | 432 | 846 ms | 47 ms | **431 sous 30 ms** — le cache tient |
| `GET /api/status` | 27 | 509 ms | 29,9 ms | |
| `/map`, `/reglages`, `/people`, `/pets`, `/` | 8 | 75 ms | 12,8 ms | les gabarits ne coûtent rien |

Deux choses à lire ici, et la seconde est la plus importante.

**Les pages HTML ne coûtent rien.** `/map` rend en 12,8 ms. Ce n'est donc ni le
gabarit, ni le CSS, ni la compression : tout le temps est dans les **données**
qu'une route va chercher.

**Le cache de vignettes tient.** 432 découpes de visages servies, 431 sous
30 ms. C'est la correction du 10/09 (cache indépendant du `mtime`, estampille
séparée) observée sous charge réelle, pendant la campagne. Rien à y refaire.

---

## 2. `GET /files` : 31,4 s — trouvé, mesuré, corrigé

### Le banc

`mesure_parcours_dossier.py`, lancé sur `Photos Mike/2022`
(**2 465 photos**, partage SMB), trois tours, méthodes **alternées** pour que le
cache SMB ne favorise pas celle qui passe en second :

```
iterdir + is_file (actuel)   froid   26,05 s    meilleur  25,55 s    x 1,0
os.scandir                   froid  308,5 ms    meilleur 308,5 ms    x 82,8
os.scandir + stat            froid  322,8 ms    meilleur 322,8 ms    x 79,2
```

**Un facteur 84.** Et le coupable n'est pas le réseau : **10,57 ms par
fichier**, alors qu'un aller-retour SMB en coûte 0,3 à 2. C'est le **nombre**
d'appels qui payait.

`Path.is_file()` est un `stat()` — un aller-retour par fichier. Et l'ancienne
écriture faisait **deux tournées** du dossier : une pour les fichiers, une pour
les sous-dossiers. `os.scandir` reçoit le type dans la ligne de répertoire
elle-même : le partage répond **une fois** pour le dossier entier.

Le troisième relevé mérite d'être lu deux fois : `os.scandir + stat` ne coûte
que **14 ms de plus** que `scandir` seul. Sous Windows, la taille et la date
viennent de la même ligne de répertoire. Le repli « le fichier n'est pas dans
l'index, je fais un `stat()` » peut donc devenir gratuit lui aussi.

### La part de l'index

Sur la même requête, `_index_entries_under` balaie les **44 121** clés de
l'index — quel que soit le dossier demandé :

```
_pkey actuel (un objet Path par clé)   264,1 ms
sans construire de Path                 21,6 ms   x 12,2
carte déjà normalisée                    5,7 ms   x 46,2
```

**Mais 264 ms sur 26 300, c'est 1,0 %.** Le noter, ne pas s'y précipiter :
c'est exactement le genre de chiffre qui séduit et qui ne change rien.
Il devient intéressant *après* la correction du parcours — pas avant.

### Ce qui a été fait

`_lister_dossier(dossier, rec)`, posé à côté de `_is_hidden_path`, appelé par
`_serve_gallery`. `os.scandir` en mode simple, `os.walk` en récursif — et en
récursif, l'élagage se fait **dans `dirs[:]`**, donc `@eaDir` (qui contient une
vignette Synology par photo) n'est plus **parcouru** avant d'être jeté.

`test_parcours_dossier.py` — **16 bancs, verts**. Le principe : l'**ancienne
implémentation est gardée dans le fichier de test et sert d'oracle**. Chaque
banc construit un arbre (dossiers cachés `.` `@` `#`, extensions en majuscules,
non-médias, imbrication à trois niveaux, tri insensible à la casse) et vérifie
que les deux écritures rendent **exactement** la même chose, ordre compris.

Deux bancs comptent ce que le changement prétend économiser : ils
**interceptent `os.stat`** et exigent une division par dix au moins. Une
optimisation qui ne se compte pas est une intention.

Deux bancs relisent `server.py` par l'arbre syntaxique : `_serve_gallery`
appelle bien `_lister_dossier`, et il n'y reste **ni `rglob` ni `.iterdir()`**.
C'est la leçon du 10/09 — une correction posée à côté de l'ancien chemin laisse
la session suivante croire aux deux.

Une différence de comportement est assumée et écrite dans la docstring : en
récursif, un lien symbolique **cassé** portant une extension média entrait
autrefois puis ressortait par `is_file()`. Le vérifier coûterait un `stat()`
par fichier — c'est-à-dire tout ce qu'on vient d'économiser.

### Réobservé en réel — et ce que l'observation corrige

Serveur redémarré **23:19:45 sur le code de 23:19:22**, zéro traceback,
campagne reprise. Trois ouvertures de dossier plus tard, l'horloge dit :

| | avant (10/09 22:56) | après (11/09) |
|---|---:|---:|
| `/files` **à froid** | 31,4 s | **10,2 s** |
| `/files` **à chaud** | 1,35 s | ~1,6 s |

**Le banc promettait 84×, la page a rendu 3×. Les deux chiffres sont justes**,
et l'écart enseigne quelque chose qu'aucun banc ne pouvait dire :

- Le banc mesurait **le parcours seul** : 26,05 s → 308 ms. Ce gain-là a bien
  eu lieu — il représente les **21 secondes** qui ont disparu du chemin froid.
- Mais `/files` ne fait pas que parcourir. Les ~10 s restantes sont
  **l'enrichissement des 2 465 photos** (`_faits_pour` sur chacune), le
  balayage de l'index, et la sérialisation du JSON. Je ne les avais pas
  mesurées ; je les avais supposées petites. Elles ne le sont pas.
- Et **à chaud, rien n'a changé** — parce que rien n'avait à changer : Windows
  garde les métadonnées du répertoire en cache, donc les 2 465 `stat()` de
  l'ancienne écriture ne touchaient déjà plus le réseau. L'ancien code n'était
  catastrophique **que sur un dossier pas vu depuis un moment** — c'est-à-dire
  exactement le geste que Mike fait quand il cherche une photo.

> La leçon, et elle vaut pour la suite de ce chantier : **un banc qui isole un
> morceau prouve le gain de ce morceau, pas celui de la page.** Il faut les
> deux mesures, et c'est la seconde qui compte.

Reste donc à savoir où partent les 10 secondes froides. C'est une **horloge de
phases dans `_serve_gallery`** — posée le 11/09 au matin, § 2 bis.

---

## 2 bis. L'horloge de phases — et les 10 secondes qui ne sont pas revenues

Livrée le 11/09 (`feat/horloge-de-phases-galerie`).

- `_Phases` : `top(nom)` range le temps écoulé depuis le top précédent, donc
  **la somme des phases est le temps de la fonction** ; un oubli se voit comme
  une phase trop grosse, pas comme un temps disparu. Une sous-phase porte un
  point (`enrichir.faits`) et fait PARTIE de sa parente.
- `/api/perf` et `_perf_routes.json` gagnent `phases` (agrégat par route) et
  `derniers` (les 20 dernières exécutions en détail — c'est là qu'on lit UNE
  ouverture froide, que l'agrégat noierait). **Aucun nom de dossier** n'y
  entre : la route se lit sans garde admin (règle 10).
- **La page rendue est inchangée, et c'est prouvé** : l'arbre syntaxique de
  `_serve_gallery` instrumentée, une fois l'instrumentation retirée et les cinq
  valeurs sorties du littéral réinsérées, est **identique** à celui d'avant.
  Les bancs durables (`test_horloge_phases.py`, 15) tiennent les arguments des
  appels chronométrés, l'ordre des phases et l'absence de nom de dossier —
  trois mutations écrites exprès, trois rouges.

### Le relevé — 11/09, 08:15 → 08:18, serveur redémarré à 08:14:41, campagne en cours

| ouverture | photos | total | `index` | `carte_cles` | `parcours` | `enrichir` | reste |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2019 — 1ʳᵉ requête après démarrage | 81 | 1 488 ms | 511 | **784** | 31 | 16 | 146 |
| 2023 | 2 098 | 1 711 ms | 481 | — | 533 | 379 | 318 |
| 2022 | 2 465 | 1 935 ms | **772** | — | 357 | 437 | 369 |
| 2021 | 1 602 | 1 231 ms | 477 | — | 210 | 295 | 249 |
| 2022, rouverte | 2 465 | 1 652 ms | 450 | — | 373 | 472 | 357 |
| 2018, récursif | 1 789 | 1 627 ms | 393 | — | 430 | 547 | 257 |
| **2020 — vraiment froide, cache de clés expiré** | 1 084 | **4 091 ms** | 500 | **618** | **2 638** | 166 | 169 |
| 2017 | 23 | 585 ms | 378 | — | 122 | — | 85 |

`—` : moins de 20 ms. `stats_nas` (le repli `stat()` par photo absente de
l'index) vaut **0 partout**.

**Ce que ce relevé dit, dans l'ordre où il le dit :**

1. **Les 10,2 s d'hier ne sont pas revenues.** Huit ouvertures, dont une
   première requête après démarrage et un dossier jamais ouvert de la
   matinée : de 0,6 à 4,1 s. Je n'ai **pas** d'explication mesurée du chiffre
   d'hier. L'horloge reste en place, et si une ouverture à 10 s se reproduit
   chez Mike, `derniers` dira laquelle des phases l'a faite — c'est la seule
   manière honnête de clore ce point.
2. **Deux balayages de TOUTE la photothèque à chaque ouverture, quelle que
   soit la taille du dossier.** `index` (`_index_entries_under`, un `_pkey` —
   donc un objet `Path` — par clé, sur 44 604) coûte **378 à 772 ms même pour
   23 photos**. `carte_cles` (`_key_index`) le rejoint **dès que son TTL de
   60 s a expiré** : 618 à 784 ms. Quelqu'un qui ouvre un dossier toutes les
   deux minutes paie donc **~1 à 1,5 s de balayage par clic** avant qu'une
   seule photo du dossier soit regardée. Le banc d'hier avait isolé `_pkey` à
   264 ms ; sous la vraie charge c'est 1,5 à 3 fois plus.
3. **Le parcours froid n'est pas gratuit.** `scandir` a tenu sa promesse sur
   un dossier tiède (210–533 ms pour 1 600–2 465 photos), mais 2020 vraiment
   froid prend **2,6 s pour 1 084 photos, 2,4 ms par fichier**. C'est dix fois
   mieux que l'ancien code (10,57 ms), et c'est désormais le réseau qui paie,
   pas le nombre d'appels. Le balayage du NAS que la maintenance lance après
   chaque démarrage réchauffe de toute façon les répertoires en quelques
   minutes.
4. **L'enrichissement est sain** : ~0,18 ms par photo, réparti à parts égales
   entre clé, dossier, dates et faits. Pas une cible — sauf en récursif, où
   `faits` monte à 304 ms sur 1 789 photos.
5. **La planche entière en JSON (§ 3.7) coûte peu côté serveur** : 1,4 à
   1,7 million de caractères pour ~2 000 photos, mais `json.dumps` 25–30 ms,
   gabarit ~50, envoi (gzip + socket) 55–81 ms. Ce que le NAVIGATEUR paie pour
   analyser ce JSON n'est pas mesuré.

---

## 2 ter. Les deux balayages par clic — `_pkey` mémoïsé

Livré le 11/09 (`fix/deux-balayages-par-clic`), une heure après le relevé qui
l'a désigné.

**Ce qui a changé** : rien de la règle. `_pkey(p)` rend toujours
`Path(p).as_posix().lower()` ; pour une **chaîne**, le résultat est gardé
(`lru_cache`, borne 131 072). La carte `_key_index` se rebâtit à l'identique de
`fichiers.build_key_index` — même ordre, même gagnant quand deux clés se
normalisent pareil, même clé écartée si elle lève — mais la normalisation de
chaque clé (`fichiers.norm(_resolve_key(k))`) est gardée elle aussi.
`UPLOAD_DIR` est fixé au chargement : rien ne peut périmer.

**Preuves avant livraison** (`test_pkey_memoire.py`, 10 bancs) : l'ancienne
expression sert d'oracle **avec `PureWindowsPath`** — les règles de Windows,
pas celles de la sandbox — sur quinze chemins tordus (UNC, casse, double
séparateur, `.`, séparateur final, accents, `ß`, clés d'Uploads relatives) ;
la carte est comparée au VRAI `build_key_index` de `fichiers.py` ; et la
seconde reconstruction de la carte est **comptée : zéro `Path` construit**.
Trois mutations (règle réécrite en `replace`, clé d'Uploads mal résolue,
premier gagnant au lieu du dernier) : trois rouges.

**Réobservé** — serveur redémarré 08:30:47, campagne en cours, énumération du
NAS lancée à 08:31:55 :

| | avant (08:15–08:18) | après (08:33–08:35) |
|---|---:|---:|
| `index`, 1ʳᵉ ouverture après démarrage | 511 ms | 710 ms (la mémoire se remplit) |
| `index`, ouvertures suivantes | 393 · 450 · 477 · 481 · 500 · 772 | **137 · 139 · 156** · 430 |
| `carte_cles`, TTL expiré | 618 · 784 ms | **44 ms** |
| 2022 (2 465 photos), total | 1 935 · 1 652 ms | 1 696 ms |
| 2021 (1 602 photos), total | 1 231 ms | 1 124 ms |

Le gain est là où il était attendu : **~340 ms de moins sur `index`** à chaque
clic, **~650 ms de moins** une fois par minute sur la carte — **et ce second
gain se fait verrou tenu** : pendant la reconstruction, toute vignette qui
vérifie sa visibilité par `_key_index` attendait.

**Ce qu'il ne dit pas encore** :
- Une ouverture (2017, 23 photos) a encore payé **430 ms** d'`index`. Deux
  suspects, **aucun mesuré** : `_pkey(Path(UPLOAD_DIR).resolve())`, qui fait un
  aller-retour SMB à chaque appel pour tout dossier hors Uploads, et la
  contention du GIL avec les fils CPU (visages, DINOv2, encodage sémantique)
  qui démarraient à ce moment-là. Les ~140 ms qui restent sont la VUE
  (`STORE.data.items()` filtre 44 604 clés par le prédicat de visibilité).
- Les totaux bougent peu sur 2022/2021, parce que `parcours` était ce
  matin-là plus lent qu'au premier relevé (429–642 ms contre 210–373) :
  l'énumération du NAS tournait. **Comparer phase par phase, pas les totaux**
  — c'est exactement ce que l'horloge de phases permet.

---

## 3. Ce qui est trouvé et pas encore fait

Par ordre de gain mesuré, pas par ordre de facilité.

### 3.0 `GET /api/thumb` — 1,80 s de moyenne, et c'est le nouveau premier

Il n'apparaissait pas dans le relevé du 10/09 : cette fenêtre-là n'a servi que
des découpes de visages, toutes en cache. Sur la fenêtre du 11/09 (5 h 40),
il prend la tête :

```
GET /api/thumb    n = 35    total 62,9 s    pire 4,33 s
seaux : 7 entre 300 ms et 1 s | 24 entre 1 et 3 s | 4 au-dessus de 3 s
```

**28 vignettes sur 35 ont mis plus d'une seconde.** Une vignette absente du
cache se fabrique en lisant la photo pleine taille depuis le NAS, puis en la
redimensionnant — pendant que la campagne tient le disque.

La piste évidente : **le tagueur ouvre déjà chaque photo**. Il pourrait écrire
la vignette au passage, pour le prix d'un `resize` qu'il paie de toute façon en
mémoire. 40 600 photos retaguées = 40 600 vignettes qui n'auraient plus jamais
à être fabriquées à la demande.

À vérifier d'abord, parce que ça change le raisonnement : **combien de photos
n'ont pas encore de vignette ?** `mesure_caches_vignettes.py` sait compter le
cache ; il suffit de le croiser avec l'index. Si le fonds est déjà couvert à
95 %, ces 35 requêtes sont un cas de bord et ce point redescend.

---

### 3.1 `GET /api/corbeille` — 4,88 s, verrou tenu

```python
with FILE_OPS_LOCK:
    entrees = file_ops().corbeille()
```

Le parcours de `.corbeille-effacements\` sur le NAS se fait **sous le verrou
global des opérations de fichiers**. Pendant ces 4,9 secondes, aucun
déplacement, aucune mise en privé, aucune restauration ne peut partir — pour
une route qui ne fait que **lire**.

Deux choses, dans cet ordre :
1. le parcours souffre très probablement du **même mal** que `/files`
   (un `stat()` par entrée) — à mesurer avec le même banc ;
2. la lecture n'a pas à tenir le verrou d'écriture. Un instantané pris sous
   verrou, formaté dehors, suffit.

> Le point 2 ne se fait pas à l'aveugle : `FILE_OPS_LOCK` protège aussi la
> re-clé de l'index. Il faut **lire pourquoi il a été posé là** avant de le
> relâcher — c'est le genre de garde-fou qu'on retire une fois et qu'on
> regrette six mois.

### 3.2 `GET /api/pets/list` — 2,87 s, une boucle dans une boucle — **FAIT le 11/09**

> **Livré** (`fix/sujets-en-une-passe`). Une passe unique,
> `_premieres_vignettes(tags, entrees, index, vignette)`, sert tous les chats à
> la fois et s'arrête quand chacun a sa vignette ; le repli de `people_list`
> (fiches sans avatar) passe par la même fonction. **Oracle** : les deux
> fonctions d'avant, recopiées verbatim dans `test_sujets_une_passe.py`,
> comparées sur 300 magasins tirés au hasard (graine fixe), avec un banc qui
> exige que les tirages aient bien produit les cas durs ; le nombre de
> balayages est COMPTÉ (6 → 1 pour six chats). Quatre mutations, quatre rouges.
>
> **Réobservé** (serveur redémarré 08:44:40) : `/api/pets/list`
> **2 271 · 2 545 ms → 282 · 299 ms**, et la réponse est **identique au
> caractère près** (même longueur, même empreinte FNV-1a avant et après).
> `/api/people/list` : 137–139 → 143 ms, réponse identique — rien à gagner
> aujourd'hui, les 354 fiches ont toutes un avatar et le repli ne sert pas ;
> la correction y protège le jour où le curateur n'a pas tourné.

```python
for pk, pe in PETS_STORE.data.items():        # ~17 chats
    for k, e in ANIMAL_STORE.data.items():    # ~40 584 entrées
        if not _kw_has(STORE.data.get(k), f"animal:{nm}"):
```

**17 × 40 584 ≈ 690 000 tours**, plus un balayage complet de `STORE.data`
avant, pour compter les tags. Tout ça pour trouver **une vignette par chat**.

La correction est d'école : **une seule passe** sur `ANIMAL_STORE` qui bâtit
`{nom → première découpe}`, puis les 17 chats se servent dedans. O(N) au lieu
de O(N × P).

C'est le meilleur rapport gain/risque de la liste : fonction isolée, sans
verrou, sans NAS, et son résultat se compare octet pour octet avec l'ancien.

**L'espèce de bug mérite un nom** : *un balayage de toute la photothèque
imbriqué dans une boucle sur les sujets.* `/api/people/list` (318 ms) est de la
même famille — à vérifier au même moment.

### 3.3 `GET /api/geo` — 993 ms à chaque ouverture de la carte

Balayage complet des 44 121 entrées, avec `_pkey(k)` (donc un `Path` par clé),
`_url_for_key`, `Path(k).name` et `_best_time` sur chaque photo géolocalisée.
Rien de faux — mais c'est un **agrégat de toute la photothèque reconstruit à
chaque clic**, alors qu'il ne change qu'au rythme du tagging.

Même patron que `_key_index` : un instantané en cache, invalidé par le nombre
d'entrées et un TTL. Le mécanisme existe déjà, il suffit de s'en servir.

### 3.4 `GET /api/maint/status` — 532 ms, quatre fois sur quatre

Deux coûts, et le premier est le plus surprenant :

- **`hw_state()` lance `nvidia-smi` en sous-processus.** Le cache de 8 s ne
  couvre pas une page qui interroge plus souvent, et sous charge GPU (la
  campagne) `nvidia-smi` met du temps à répondre. **La page des réglages paie
  une création de processus par interrogation.**
- `STORE.tagged_count()` rebalaie les 44 121 entrées à chaque appel, sans
  cache.

Aucun des deux ne demande de réécriture : un cache un peu plus long côté
`hw_state` pour les lecteurs non prioritaires, un compteur tenu à jour côté
store. **À mesurer avant** : un banc qui chronomètre `nvidia-smi` seul, GPU
occupé et GPU libre, dira si c'est bien lui.

### 3.5 Le serveur parle **HTTP/1.0**

`Handler` ne pose pas `protocol_version = 'HTTP/1.1'`. Conséquence : la
connexion est **fermée après chaque réponse**. Les 432 découpes de visages du
relevé, ce sont 432 connexions TCP et 432 fils.

C'est aussi, très probablement, la vraie cause de la panne déjà notée dans
`MARCHE_A_SUIVRE.md` — « une planche pouvait prendre les six connexions que
Chrome ouvre par site ». Avec `keep-alive`, Chrome **réutilise** ses six
sockets au lieu de les rouvrir sans cesse.

**Ce changement ne se fait pas sans instrument.** En HTTP/1.1, une réponse sans
`Content-Length` juste désynchronise la connexion : le navigateur attend des
octets qui ne viennent pas, et la page **reste suspendue** — une panne bien
pire que la lenteur qu'on corrige. Il faut donc, dans cet ordre :

1. `verifier_content_length.py` — par l'arbre syntaxique, **tout** chemin qui
   appelle `send_response` atteint un `end_headers` précédé d'un
   `Content-Length` (ou d'un encodage en morceaux). Les chemins connus
   (`_repondre`, `_send_file`, les quatre écritures directes de vignettes)
   le font ; ce sont les autres qu'il faut trouver ;
2. le drapeau ;
3. réobservation par l'horloge sur une planche complète.

### 3.6 Les médias ne portent ni `Last-Modified` ni `ETag`

`_send_file` sert les octets, gère `Range` (audit O2) — mais ne dit pas au
navigateur ce qu'il a déjà. Revenir en arrière sur une photo de 5 Mo la
**retélécharge entièrement depuis le NAS**.

`Last-Modified` + réponse `304` sur `If-Modified-Since` : peu de code, aucun
risque de cohérence (le `mtime` est déjà la source de vérité du reste du
projet), et le retour arrière devient instantané.

### 3.7 La planche entière dans une seule page

`_serve_gallery` sérialise **tout** `file_data` dans `__FILE_JSON__`. Pour
2 465 photos, chaque entrée portant nom, clé, URL, taille, dates, faits
(date · lieu · noms), jusqu'à 20 tags, GPS et description, cela fait **plusieurs
mégaoctets de JSON** fabriqués, compressés, puis analysés par le navigateur —
avant la première vignette.

C'est le plus gros chantier de la liste et le seul qui touche l'interface
(pagination, ou chargement par tranches). Il ne se commence **qu'après** avoir
réobservé `/files` : avec 26 s de moins, le classement aura changé, et il se
peut que ce point passe devant — ou derrière.

### 3.8 `_pkey` construit un `Path` par appel

264 ms par balayage complet, ×12 pour rien. `_index_entries_under` peut se
servir de `_key_index()` — déjà bâtie, déjà en cache, déjà invalidée
correctement — au lieu de renormaliser 44 121 clés.

**Attention** : ne pas changer `_pkey` lui-même. `Path(p).as_posix()` et
`str(p).replace('\\','/')` ne sont **pas** équivalents sur les cas tordus
(double séparateur, `.` intermédiaire, séparateur final), et `_pkey` est la
normalisation de clé de tout l'index. C'est l'appelant qu'on corrige, pas la
règle.

---

## 4. Ce qui a été vérifié et qui va bien

À ne pas rouvrir sans raison neuve :

- **La compression** (audit O11) : gzip au-delà de 4 Ko, seulement sur du
  texte, gardée seulement si elle gagne, `Vary: Accept-Encoding` posé même
  quand elle n'a pas servi. Un seul endroit compresse.
- **Le streaming des médias** (audit O2) : blocs d'1 Mo, `Range` géré, `416`
  hors bornes. Un `.mp4` de 500 Mo ne passe plus par la RAM.
- **Le cache des vignettes** : 431 découpes sur 432 sous 30 ms, mesuré pendant
  la campagne.
- **Les gabarits HTML** : 10 à 13 ms. Le rendu des pages n'est pas un sujet.
- **`flush()` au lieu de `save()`** (audit O14) : 627,2 ms de re-hachage sous
  verrou par dossier, ramenés à 0,1 ms.

---

## 5. L'ordre — reclassé le 11/09 au matin

**Fait le 11/09** : l'horloge de phases (§ 2 bis), les deux balayages par clic
(§ 2 ter), `/api/pets/list` en une passe (§ 3.2).

1. **Compter les vignettes manquantes**, puis décider si le tagueur doit les
   écrire au passage (3.0). `/api/thumb` reste premier au temps total.
2. **`/api/corbeille`** — d'abord le banc de parcours, ensuite la question du
   verrou, et seulement si la raison du verrou est comprise.
3. **`/api/geo`** — instantané en cache, patron `_key_index`. Profite déjà en
   partie de `_pkey` mémoïsé : le re-mesurer avant d'y toucher.
4. **`nvidia-smi`** — le mesurer avant de toucher au cache.
5. **HTTP/1.1** — l'instrument `Content-Length` d'abord, le drapeau ensuite.
6. **`Last-Modified` sur les médias.**
7. **Le reste de `index` dans la galerie** : ~140 ms de VUE (le prédicat de
   visibilité sur 44 604 clés) et un 430 ms isolé non expliqué —
   `_pkey(Path(UPLOAD_DIR).resolve())` fait un aller-retour SMB à chaque appel
   hors Uploads : suspect, pas mesuré.
8. **La planche entière (3.7)** : côté serveur, 150 ms sur 1,9 s. Ne se
   reconsidère qu'avec une mesure du côté navigateur.

---

## 6. Les instruments de ce chantier

| Fichier | Ce qu'il fait |
|---|---|
| `mesure_routes.py` | classe `_perf_routes.json` par temps total, une vue « latence ressentie » par seuils, et depuis le 11/09 **où part le temps** (phases) et les dernières exécutions en détail |
| `mesure_parcours_dossier.py` | compare `iterdir`/`scandir`/`scandir+stat` sur un vrai dossier du NAS, méthodes alternées ; et `_pkey` sur les vraies clés, depuis **`copie.db`** — jamais `photos.db` |
| `test_horloge_routes.py` | 16 bancs : l'horloge compte juste, et ne fait jamais tomber une requête |
| `test_parcours_dossier.py` | 16 bancs : l'ancienne écriture sert d'oracle ; deux bancs comptent les `stat()` |
| `test_sujets_une_passe.py` | 7 bancs : `pets_list`/`people_list` d'avant, recopiées verbatim, servent d'oracle sur 300 tirages ; le nombre de balayages est compté |
| `test_pkey_memoire.py` | 10 bancs : `_pkey` mémoïsé rend l'ancienne expression sous `PureWindowsPath` ; la carte égale le vrai `build_key_index` ; la 2ᵉ reconstruction ne construit aucun `Path` |
| `test_horloge_phases.py` | 15 bancs : les phases se succèdent, le détail est borné, rien ne lève ; `_serve_gallery` garde ses arguments et ne livre aucun nom de dossier |

Les deux bancs `mesure_` tournent sur l'agent de banc. L'espace dans un
argument passe par le jeton `b64:` :
`--dossier b64:UGhvdG9zIE1pa2UvMjAyMg` = `Photos Mike/2022`.

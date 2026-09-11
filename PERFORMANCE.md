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
n'ont pas encore de vignette ?**

#### Mesuré le 11/09 au matin — deux bancs, et une décision qui revient à Mike

**`mesure_couverture_vignettes.py`** (sur `copie.db`, 2,5 jours) recalcule le
nom exact de chaque vignette et regarde si le fichier existe :

```
photos (images, hors échecs)   39 999
vignette 512 PRÉSENTE             818    2,0 %
vignette 512 ABSENTE           39 181   98,0 %
vignette 1600 présente              0
cache : 3 577 fichiers .jpg dans photo_thumbs
Photos Mike 2,7 % · Photos Flo 1,5 % · Photos Papa 0,3 %
```

**Le fonds n'est pas couvert : il est vide.** Le changement de formule du 10/09
(nom sans mtime) a rendu orphelin tout l'ancien cache, et seules les photos
regardées depuis ont une vignette. Ce n'est donc pas un cas de bord : **presque
chaque case de galerie** lit l'original sur le NAS.

**`mesure_fabrication_vignette.py`** (`Photos Mike/2023`, 12 JPEG, campagne en
cours) sépare les deux coûts d'une fabrication :

```
lecture NAS        376 ms en moyenne pour 2,3 Mo   (163 à 606 ms)
décodage actuel    108 ms
décodage « draft » 93 ms   → ×1,2 seulement ; 9 photos sur 12 IDENTIQUES
fabrication        ~480 ms par vignette, ~5,3 h pour les 39 181 absentes
```

- **C'est le NAS qui coûte, pas Pillow** : 78 % du temps est la lecture du
  fichier (~6 Mo/s pendant la campagne). Le serveur, lui, met 1 à 4 s parce que
  la grille en demande six à la fois, qui se disputent le même disque.
- **`draft` est REJETÉ** : l'hypothèse que `exif_transpose` forçait un décodage
  pleine taille coûteux ne tient pas sur les vraies photos (×1,2, et le plus
  souvent une sortie identique). Pas de changement d'écriture pour ça.
- **Donc la seule vraie économie est de ne pas relire le fichier.** Le tagueur
  le lit déjà : `image_to_b64` l'ouvre, le tourne, le réduit à 896 px. En tirer
  la vignette 512 coûte quelques millisecondes, **zéro octet NAS de plus**.
  Mais la campagne ne repasse que sur ce qu'il lui reste ; pour le reste du
  fonds, il faut un fil de fond (~5 h de lectures NAS, ~2 Go sur C:, qui cède
  la main à l'interface comme les autres).

**Tranché par Mike le 11/09 : « les deux ».** (a) le tagueur maintenant,
(b) un fil de fond pour le reste, après la campagne.

#### (a) Livré le 11/09 au soir — `feat/vignette-du-tagueur`

`image_to_b64(path, vignette=…)` : après la réduction à 896 px, une COPIE de
l'image en mémoire donne la vignette 512 (`_deposer_vignette`, JPEG q82 comme
`_serve_thumb`), écrite atomiquement, **jamais par-dessus une vignette
existante, jamais depuis une image réduite sous 512 px, et sans tampon** — c'est
`_retamponner_vignettes`, déjà appelé après `write_metadata`, qui la date. Si
la passe échoue avant, la vignette garde sa date de création, que
`_vignette_a_jour` refuse : elle sera refaite, jamais servie périmée.

**Bancs** (`test_vignette_du_tagueur.py`, 12) : l'image envoyée à l'IA est
**identique octet pour octet** avec ou sans vignette — la campagne n'est pas
touchée ; orientation et taille égales à `_serve_thumb`, PSNR > 38 dB contre
son écriture ; ordre image → XMP → tampon lu dans `tagger_worker` ; cache
inécrivable sans exception. Quatre mutations, quatre rouges.

**Réobservé** (serveur redémarré 18:38:31) :
- les **6 premières photos retaguées ont leur vignette**, et chacune porte
  **exactement le mtime de la photo sur le NAS** (lu dans `N:\Photos`) — donc
  « à jour » pour le serveur ; orientation vérifiée à l'œil sur la portrait ;
- `/api/thumb` sur ces clés : **5 à 7 ms**, et les octets servis sont ceux du
  fichier écrit par le tagueur (même taille exacte) ;
- temps de tagging : **15,3 s** en moyenne sur les 22 premières, contre 14,4 s
  sur les 60 d'avant le redémarrage — dans la dispersion (13 à 19 s), et sur
  des photos différentes ; la vignette elle-même coûte quelques ms. À relire
  sur un plus grand nombre avant d'en conclure quoi que ce soit.

#### (b) Livré le 11/09 au soir — `feat/vignettes-de-fond`

`vignettes_loop`, lancé par `fil_surveille`. Il fabrique les vignettes 512
manquantes ou périmées, **les plus récentes d'abord**, par lots de 20, et
seulement quand il ne dispute rien : **file de tagging vide** (la campagne en
tient 500 en permanence : il attend), **`ui_recent`** consulté entre DEUX photos
d'un même lot, un **créneau de fond** (`creneau('vignettes')`), et un plancher de
**20 Go libres** sur le disque, sous lequel il s'arrête et le dit. Photo
illisible : notée, sautée. La fabrication est **une seule fonction**,
`_fabriquer_vignette`, que `_serve_thumb` utilise désormais aussi — prouvée
identique octet pour octet à l'ancienne écriture de la route.

**Un lot TÉMOIN** de 3 photos part au démarrage, campagne ou pas : le chemin est
prouvé dans le journal aujourd'hui, pas découvert le jour où la campagne finit.
L'état complet se lit dans **`/api/serveur` → `vignettes`**.

**Bancs** (`test_vignettes_de_fond.py`, 15) : la liste (écarts, ordre, index qui
bouge pendant le compte), le tampon, la photo illisible, et le fil lui-même —
campagne en cours, UI au milieu d'un lot, disque plein, créneau refusé, fil
désactivé qui dort au lieu de mourir. Mutations : campagne ignorée, coupure UI
retirée, tampon retiré, disque ignoré, témoin retiré — cinq rouges. (Rendre un
lot interrompu à la file n'est pas tenu par un banc : sans lui, la liste se
recalcule au passage suivant et retrouve les mêmes photos.)

**Réobservé** (serveur redémarré 18:58:17) :
- `🖼 Vignettes de fond — lot témoin : 3/3 en 2.2 s`, zéro traceback ;
- `/api/serveur` : `"etat": "attend la fin du tagging"`, `"temoin": {"faites": 3}` ;
- les trois photos les plus récentes (`Photos Mike\2026\20260824_19…`) ont leur
  vignette, **au mtime exact** du fichier sur le NAS ; servie en 8 ms ;
- la route refactorisée : une photo jamais vue, **1 304 ms** (fabriquée), puis
  **18 ms** (servie du cache), mêmes octets.

**À vérifier quand la campagne finit** : `vignettes.etat` passe à `fabrique`,
`a_faire` descend (~39 000 au départ), `echecs` reste petit.

---

### 3.1 `GET /api/corbeille` — 4,88 s, verrou tenu — **FAIT le 11/09**

> **Mesuré** (`mesure_corbeille.py`, 252 effacements, NAS, méthodes alternées) :
> l'écriture de `FileOps.corbeille` faisait `exists` + `is_dir` + `stat` —
> **trois allers-retours SMB par panier**. À froid 3 374 ms ; à chaud 230 ms.
> Un seul `os.stat` : **67 ms à chaud, ×3,4**, mêmes (existe, octets) sur les
> 252 entrées. (Le « premier » passage des deux autres méthodes profitait du
> cache chauffé par la première : seul le « meilleur » se compare.)
>
> **Pourquoi le verrou était là, lu avant d'y toucher** : `FILE_OPS_LOCK`
> protège les séquences *lire le journal → modifier → réécrire* et la re-clé de
> l'index. La liste, elle, ne fait que LIRE le journal — réécrit atomiquement
> (`.tmp` puis `replace`) — puis interroger le disque. Seul l'instantané du
> journal reste sous verrou (`journal_instantane`) ; les 252 `stat` passent
> dehors. Au pire, un panier restauré à l'instant apparaît « absent » jusqu'au
> rechargement.
>
> **Livré** (`fix/corbeille-hors-verrou`) : `fichiers._present_et_taille`, un
> `stat` (+ un `scandir` par dossier). **Oracle** : l'ancienne écriture
> recopiée dans `test_corbeille_une_lecture.py` (absent, vide, dossier
> imbriqué, dossier vide) ; les appels à `os.stat` sont comptés ; l'arbre de la
> route dit que le verrou ne couvre que l'instantané. Deux mutations, deux rouges.
>
> **Réobservé** (redémarré 19:09:00) : **4 234 · 4 200 ms → 930 à 2 065 ms**
> (cinq appels), et la réponse est **identique** (252 entrées, 603 305 825
> octets, même empreinte). Le serveur reste bien plus lent que le banc (67 ms) :
> **hypothèse, non mesurée** — chaque `stat` rend le GIL, et le reprendre attend
> l'intervalle de bascule (5 ms) tant que des fils CPU tournent (visages,
> DINOv2, encodage) : 252 × ~5 ms ≈ 1,3 s, l'ordre de grandeur observé. Si
> c'est cela, **toute boucle d'entrées-sorties du serveur paie ce péage**, et
> c'est un sujet en soi.

Ancien constat :

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

### 3.3 `GET /api/geo` — 993 ms à chaque ouverture de la carte — **allégé le 11/09**

> **Mesuré avant** (11/09 19:34, après `_pkey` mémoïsé et le péage du GIL) :
> **812 · 814 · 1 029 ms**. Le code demandait `_pkey(root)` pour chaque racine
> et chaque photo géolocalisée — un `Path` Windows à chaque fois, puisque la
> mémoire de `_pkey` ne gardait que les chaînes.
>
> **Livré** (`fix/pkey-des-path-et-carte`) : un `Path` passe par sa chaîne
> (`Path(str(p))` est le même chemin, donc la même clé) — bénéfice pour TOUS
> les appelants qui passent des `Path`, pas seulement la carte. Et l'horloge de
> phases est posée sur `_serve_geo` (prouvée sans effet par l'arbre syntaxique).
> Oracle sous `PureWindowsPath` sur les quinze cas tordus ; un `DirEntry`, dont
> `str()` n'est pas le chemin, passe par le calcul direct (banc).
>
> **Réobservé** (redémarré 19:36:40) : **540 · 578 · 674 ms**, 5 649 points.
> Les phases disent où est le reste : `boucle` 260–343 ms (`_best_time`, un
> `Path(k).name` et deux `quote` par point), `envoi` ~80 ms (**3,25 Mo** de
> JSON compressés à chaque ouverture), `vue` 61–92, `json` ~50. L'instantané en
> cache reste possible s'il devient utile ; à ~0,5 s pour une page qu'on ouvre
> rarement, il ne passe pas devant.

Ancien constat :

Balayage complet des 44 121 entrées, avec `_pkey(k)` (donc un `Path` par clé),
`_url_for_key`, `Path(k).name` et `_best_time` sur chaque photo géolocalisée.
Rien de faux — mais c'est un **agrégat de toute la photothèque reconstruit à
chaque clic**, alors qu'il ne change qu'au rythme du tagging.

Même patron que `_key_index` : un instantané en cache, invalidé par le nombre
d'entrées et un TTL. Le mécanisme existe déjà, il suffit de s'en servir.

### 3.4 `GET /api/maint/status` — **mesuré et allégé le 11/09 au soir**, et ce n'était pas `nvidia-smi`

La page /reglages la rappelle **toutes les 6 s**. Horloge de phases posée
d'abord (`test_horloge_maint_status.py` : corps identique à l'ancienne écriture,
recopiée en oracle), puis relevé sous campagne :

| phase | ms (10 appels) | ce que c'est |
|---|---:|---|
| `tagged_count` + `_tagging_pipe_counts` + boucle de `_retag_etat` | **70–135 chacun, ~250 à trois** | trois balayages des 44 603 entrées |
| `comptes` (trois `len()`) | **51–107** | voir § 3.11 — la vue |
| `hw` | 0 ou 54–134 | `nvidia-smi`, un appel sur deux (cache 8 s, page à 6 s) |
| `docs`, `arbitres`, `vecteurs` | 6–20, 0 ou ~85, 0–13 | secondaires |

**Livré** (`_passe_index`) : les trois comptes en UNE passe, mêmes filtres,
même ordre ; `_retag_etat(passe)` ne rebalaie que si la cible a changé entre
deux lectures. `test_passe_index.py` : 400 index tirés au hasard contre les
trois écritures d'avant recopiées, et le compte des parcours (3 → 1).
**Observé** : 280–560 ms → **200–460 ms**, la passe à 140–220 ms. Le reste du
temps n'est pas dans la route : § 3.10 et § 3.11.

### 3.5 Le serveur parlait **HTTP/1.0** — **livré le 12/09**

`Handler` ne posait pas `protocol_version` : la connexion se fermait après
CHAQUE réponse. Les 432 découpes de visages d'un relevé, c'étaient 432
poignées de main TCP et 432 fils — et, très probablement, la panne notée dans
`MARCHE_A_SUIVRE.md` (« une planche pouvait prendre les six connexions que
Chrome ouvre par site »).

**L'instrument D'ABORD, le drapeau ensuite.** En HTTP/1.1, une réponse sans
`Content-Length` ne se termine plus par la fermeture de la socket : le client
attend des octets qui ne viennent pas et **la page reste suspendue** — une
panne pire que la lenteur qu'on corrige. `verifier_content_length.py` suit,
par l'arbre syntaxique, chaque `end_headers()` jusqu'à son `send_response()` :
**12 réponses écrites à la main, 8 conformes, 4 sans longueur** — trois `302`
(la porte, `/faces`, le repli de vignette) et le `416` des plages hors bornes.
Toutes corrigées (`Content-Length: 0` : sans corps, et le dire).
`test_verifier_content_length.py` (12 bancs) montre à l'instrument des cas
conformes et fautifs écrits exprès — un outil qui juge ne témoigne pas de
lui-même.

**Puis le drapeau**, avec `timeout = 30` : une connexion gardée ouverte retient
un fil de `ThreadingHTTPServer`, et trente secondes sans un octet le rendent.

**Observé en réel** (même dossier, mêmes 120 vignettes déjà en cache, 6 en
parallèle, campagne en cours) :

| | connexions TCP | médiane par vignette | total |
|---|---:|---:|---:|
| HTTP/1.0 | **120** puis 120 | 14–20 ms | 463–538 ms |
| HTTP/1.1 | **4** puis **0** | 11–13 ms | 598–606 ms |

Le total ne bouge pas — il est tenu par le serveur, pas par les connexions —
et c'est la SEULE façon honnête de le dire : ce qui change, c'est que la
planche ne consomme plus les six connexions du navigateur, et qu'une requête
coûte une poignée de main en moins. Vérifié aussi sous le nouveau protocole :
`/media` entier (200), une plage (206, `Content-Range`), une plage hors bornes
(**416 en 26 ms, plus de suspension**), un 404, la galerie compressée, et la
redirection de `/faces`.

### 3.6 Les médias ne disaient pas de quand ils datent — **livré le 12/09**

`_send_file` servait les octets et gérait `Range` (audit O2), mais ne disait
pas au navigateur ce qu'il avait déjà : **revenir en arrière sur une photo de
5 Mo la retéléchargeait entièrement depuis le NAS.**

`Last-Modified` vient du `mtime` — la source de vérité du reste du projet — et
du MÊME `stat` que la taille servie (deux `stat` diraient deux vérités). Un
`If-Modified-Since` à jour rend **304**. Le cache est en **`no-cache`, pas en
`max-age`** : nos propres écritures XMP changent les fichiers par dizaines de
milliers pendant une campagne, et un cache muet servirait une version périmée
pendant des heures ; là, le navigateur revalide, et paie un `stat`.

**Observé en réel** sur une photo de 1,6 Mo :

| requête | réponse | octets | temps |
|---|---|---:|---:|
| première | 200 | 1 599 130 | 334 ms |
| avec `If-Modified-Since` à jour | **304** | **0** | 41 ms |
| avec une date plus ancienne | 200 | 1 599 130 | 34 ms |
| une PLAGE + `If-Modified-Since` | **206** (jamais 304) | 1 024 | 33 ms |

Ce dernier cas est le piège que le banc tient : répondre « rien à renvoyer » à
qui demande les octets 0-1023 d'une vidéo casserait le seek.
`test_last_modified.py` : 9 bancs, dont la comparaison à la seconde et les
en-têtes tordus qu'un client peut envoyer.

### 3.7 La planche entière dans une seule page — **MESURÉE côté navigateur le 12/09, et ce n'est pas là**

`_serve_gallery` sérialise TOUT `file_data` dans `__FILE_JSON__`. Pour le
dossier 2022 en récursif : **2 519 photos, 1 708 829 caractères**, 1,86 Mo une
fois décodés, **265 Ko sur le fil** (gzip). La question ouverte depuis le
10/09 était : que coûte tout ça au NAVIGATEUR, avant la première vignette ?

Trois chargements de la même page (campagne en cours) :

| | serveur (requête → 1ᵉʳ octet) | après la réponse → DOM prêt | `JSON.parse` de la planche | total |
|---|---:|---:|---:|---:|
| 1 | 1 496 ms | 226 ms | 6,3 ms | 1 905 ms |
| 2 | 1 869 ms | 254 ms | 8,0 ms | 2 207 ms |
| 3 | 1 625 ms | 209 ms | 12,8 ms | 1 924 ms |

**Le navigateur analyse 1,7 million de caractères en une dizaine de
millisecondes**, et construit ses 2 521 `<img>` en ~230 ms : un huitième du
temps. Les sept huitièmes sont dans le serveur. **Paginer la planche — le plus
gros chantier de la liste, et le seul qui touche l'interface — ne rendrait
donc presque rien** tant que la page coûte 1,5 s à fabriquer. Le point est
CLOS jusqu'à ce que le serveur descende sous la demi-seconde ; alors il se
rouvrira, et cette mesure sera à refaire.

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

### 3.9 Le péage du GIL — **MESURÉ et RÉGLÉ le 11/09 au soir**

L'hypothèse du § 3.1 (un `stat` qui attend le GIL) mesurée sur la machine,
`mesure_peage_gil.py`, 100 `stat`, fils CPU purs Python à côté, conditions
alternées :

```
un stat LOCAL                  seul      +1 fil CPU   +3 fils CPU   débit CPU, 3 fils
défaut (bascule 5 ms)          0,04 ms   6–15 ms      31–37 ms       100 %
bascule 1 ms seule             0,06      14,65        37,28          118 %
minuteur 1 ms + bascule 1 ms   0,04      1,41         4,13           125 %
bascule 0,5 ms                 0,06      0,06         0,13            16 %
```

- **Pire que prévu** : sous Windows, la reprise du GIL attend le PAS DU
  MINUTEUR (15,6 ms), pas l'intervalle de bascule — baisser l'intervalle seul
  ne change rien.
- **Minuteur à 1 ms + bascule à 1 ms** : ×10 sur le `stat` local, sans perte de
  débit pour les fils de calcul.
- **Sous 1 ms, piège** : les fils de calcul se disputent le GIL et tombent à
  16 % de débit. C'est un PLANCHER, tenu dans le code et par un banc.

**Livré** (`fix/peage-du-gil`) : `regler_peage_gil()` au tout début de
`__main__`, avant le premier fil — `sys.setswitchinterval(1 ms)` et
`timeBeginPeriod(1)` pour ce processus (Windows le rend à sa sortie). Ne lève
jamais ; l'état se lit dans `/api/serveur` → `gil`. `test_peage_gil.py`,
10 bancs (plancher, Windows sans `ctypes`, `winmm` absent, refus, ordre).

**Réobservé** (redémarré 19:25:35, journal : `⏱ GIL : bascule 1.0 ms, minuteur
Windows 1 ms`) :

| | avant (19:15) | après (19:29–19:31) |
|---|---:|---:|
| `/api/corbeille` (252 `stat` NAS) | 2 303 · 2 355 · 2 502 ms | 983 · 1 013 · 1 227 · 1 333 · 1 401 · 1 717 ms |
| `/files` 2022 à chaud | 1 416 ms | 1 231 ms |
| vignette en cache | 5–11 ms | 4–7 ms |
| tagging d'une photo | 15,4 s (63 photos) | 15,1 s (21 photos) |

Le gain est **×1,5 à ×2 sur la corbeille**, pas ×10 : les fils de calcul du
serveur passent l'essentiel de leur temps dans du code natif (ONNX, torch,
numpy), qui relâche déjà le GIL ; et le NAS lui-même répondait à ~6 ms par
`stat` ce soir-là (banc, colonne « seul »), soit ~1,5 s pour 252 — **la
corbeille est maintenant au prix du réseau**. Aucune régression visible : le
tagging est au même temps, zéro traceback.

---

### 3.10 La machine PAGINE — `llama-server` tenait 13,7 Go (11/09 au soir)

Écartés d'abord, instruments posés pour ça (`sondes.py`, lues dans
`/api/serveur` → `sondes`) : le **ramasse-miettes** (0–1 ms pendant les
requêtes ; mais une collecte complète de **230–430 ms toutes les ~40 s**,
qui gèle tous les fils) et le **GIL** (un fil qui dort 20 ms se réveille avec
0,4–0,9 ms de retard moyen).

`mesure_memoire.py` et `diagnostic_ollama_memoire.py` (agent de banc) :

| | avant `ollama stop` (21:14) | après (21:21) |
|---|---:|---:|
| RAM disponible | **0,4–0,8 Go** / 15,7 | 3,0 Go |
| fichier d'échange utilisé | 5,08 Go | 2,45 Go |
| pages relues du disque /s | 30 – **1 363** | 0 – 95 (pics 1 016) |
| `llama-server.exe` privé | **13,68 Go** (en RAM 6,13), lancé il y a **60 h** | 5,90 → 6,20 Go en 2 min |
| serveur privé / hors RAM | 2,44 Go / 44 % | 2,46 Go / 65 % |

Ollama déclare le modèle à **3,47 Go** (contexte 4 096, 1 requête) : ~10 Go
d'écart. **Ce n'est PAS une fuite lente — vérifié le 12/09 à 00 h 10.** Après
le redémarrage du PC et une mise à jour d'Ollama (0.33.3 → 0.34.0), le
processus était **déjà à 13,53 Go de privé après 20 minutes** de campagne,
contre 5,90 Go juste après un chargement. Le moteur RÉSERVE donc ~13,5 Go
d'engagement mémoire en quelques dizaines de minutes, une fois pour toutes :
`ollama stop` rend la place, et elle est reprise dans l'heure. La machine
engage 27 Go pour 15,7 Go de RAM — **elle paginera tant que ce chiffre
tiendra** (RAM libre : 0,5 Go, serveur à 31 % hors RAM). **La mémoire hôte épinglée par CUDA est ÉCARTÉE** : Mike a relancé Ollama
avec `GGML_CUDA_NO_PINNED=1` (vu dans l'environnement du runner par
`diagnostic_ollama_memoire.py`), et le privé remonte à **13,33 Go en
17 minutes** — 13,53 sans la variable. Le tagging ne bouge pas non plus
(médiane 12 s sur 40 photos contre 13 s sur 120). Ce qui PÈSE vraiment sur la
RAM n'est d'ailleurs pas l'engagement de 13,3 Go, dont la moitié n'est jamais
touchée, mais ses **7,8 Go résidents** pour un modèle de 3,47 Go. La cause
reste inconnue ; la question, réduite, vit dans `QUESTIONS_MIKE.md`. Au passage : le modèle n'a que **1,74 Go en
VRAM** avant, **1,21 Go** après rechargement (`--no-mmproj-offload` : la VRAM
libre au chargement décide), le reste calcule sur le CPU (2,7 cœurs).
`vmmem` (la VM de Claude sur ce PC) tient 4 Go de plus.

### 3.11 La VUE par utilisateur coûte ~3 µs par clé, sur chaque lecture agrégée

Le vrai coupable des « trois `len()` » : le CPU du fil (`_Phases`, depuis le
11/09 : `cpu_ms` et `defauts` par phase) **égale** le temps écoulé — 47 ms de
calcul, 2 défauts de page. Depuis les comptes (29/08), `STORE.data`,
`FACE_STORE.data`… rendent sous un utilisateur connecté une `VueFiltree` dont
`len`, `values`, `items`, l'itération appellent le prédicat de visibilité
**clé par clé** (`visible` → `est_prive` + `sensible_en_attente`) : ~0,7 µs en
sandbox, ~3 µs sur la machine chargée. 40 583 visages → 47 ms ; l'index → le
gros de la passe. **Toutes les routes qui agrègent le paient.**

**Livré** (`fix/vue-rapide`) : réécriture EXACTE du prédicat (`est_prive`
d'abord — 10 clés sur 44 604 sont dans un PRIVE —, `visible` seulement pour
elles, `peut_juger` seulement pour les sensibles), `en_attente` sans détour,
`filter()` natif dans `VueFiltree`. **Mesuré sur la machine de Mike, sur les
44 604 vraies clés** (`mesure_vue.py`, conditions alternées, meilleur de 5) :

| geste | avant | après | |
|---|---:|---:|---:|
| `len(vue)` | 44,8 ms | 27,0 ms | ×1,66 |
| `list(vue)` | 97,9 | 71,2 | ×1,37 |
| `vue.values()` | 53,3 | 31,9 | ×1,67 |
| `vue.items()` | 63,6 | 44,1 | ×1,44 |
| le prédicat seul | 0,99 µs/clé | 0,81 µs/clé | |

Comptes identiques des deux côtés. En REQUÊTE le gain se lit mal — `comptes`
passe de 51–74 à 37–83 ms, `passe` de 149–241 à 118–260 : la machine varie
plus que le gain, et c'est pour ça que le banc alterne les conditions.
`test_vue_rapide.py` : les écritures d'avant en oracle sur 6 000 clés (PRIVE
à toutes les profondeurs et casses, deux séparateurs, entrées abîmées), pour
chaque utilisateur — zéro écart ; trois mutations, trois rouges. Au-delà, il
faut un cache invalidé par une génération du magasin — à décider, la règle
17b ne tolère pas un cache approximatif.

**En la lisant, trois défauts de CORRECTION** (reproduits sur le vrai
`SubjectStore`, `test_ecriture_sous_la_vue.py`) : une écriture de fiche sous un
utilisateur effaçait ses citations invisibles (règle 2) ; `rename`/`delete`
plantaient (`VueFiches` sans `pop`) ; `values`/`items` rendaient les fiches
brutes (17b). Corrigés au goulot : `visibilite.restaurer_fiche`.
**Exposition mesurée** (`mesure_citations_cachees.py`, copie du 11/09 21:41) :
0 fiche ne cite une photo invisible à Mike ou à Flo — le défaut était latent.

### 3.12 Le ramasse-miettes : gelé et espacé — **livré le 12/09**

La sonde du 11/09 l'a chiffré : une **collecte complète toutes les ~100 s,
348 ms en moyenne, 509 ms au pire**, tous fils arrêtés. Ce processus porte
l'index (44 604), les visages (40 584), les animaux et les fiches — chargés au
démarrage, vivants jusqu'à l'arrêt, et parcourus à chaque collecte complète
pour n'y rien trouver.

`gc.freeze()` au début de `__main__` (après les sondes, avant le premier fil,
donc APRÈS le chargement des magasins) sort **505 000 objets** de ce parcours.
Et c'est là que la mesure a corrigé le geste :

| | collectes complètes | moyenne | pire | temps de gel par seconde de service |
|---|---|---:|---:|---:|
| sans rien | 21 en 2 133 s (1/102 s) | 348 ms | 509 ms | 3,43 ms/s |
| **gel seul** | 20 en 560 s (**1/28 s**) | 96 ms | 201 ms | **3,42 ms/s** |
| gel + `threshold2 = 100` | 4 en 666 s (1/167 s) | 151 ms | 210 ms | **0,91 ms/s** |

**Le gel seul ne gagne rien en temps total** : CPython déclenche une collecte
complète quand les objets promus dépassent le quart de ce qu'il SUIT, et le
gel vient de retirer 505 000 objets de ce dénominateur — les pauses sont 3,6 ×
plus courtes et 3,7 × plus fréquentes. Il fallait les deux : le gel pour la
durée, le seuil pour la fréquence. **Ensemble : ×3,8 sur le temps total, et la
pire pause passe de 509 à 210 ms.** `test_gel_gc.py` (8 bancs) tient l'ordre
d'appel, le fait que ce qui naît APRÈS reste ramassé, et qu'un interpréteur
qui refuse ne fait pas tomber le serveur.

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

## 5. L'ordre — reclassé le 12/09 à 01 h

**Fait le 11/09** : horloge de phases (§ 2 bis), deux balayages par clic
(§ 2 ter), `/api/pets/list` (§ 3.2), vignettes (§ 3.0), corbeille (§ 3.1),
péage du GIL (§ 3.9), `/api/maint/status` en une passe (§ 3.4), sondes GC/GIL
et CPU/défauts par phase (§ 3.10, § 3.11).

**Fait le 12/09** : la vue accélérée (§ 3.11), le ramasse-miettes gelé et
espacé (§ 3.12), HTTP/1.1 et son instrument (§ 3.5), `Last-Modified` (§ 3.6).
Et **§ 3.7 mesurée côté navigateur, puis écartée**.

0. **Quand la campagne finit** : `/api/serveur` → `vignettes` passe à
   `fabrique` ; relancer `mesure_couverture_vignettes.py`.
1. **Les 13,5 Go d'Ollama** (§ 3.10) : la piste CUDA est écartée par la
   mesure. Ce qui reste se joue APRÈS la campagne — un modèle qui tient dans
   les 4 Go de VRAM ne garderait pas 7,8 Go en RAM ; d'ici là, la machine
   pagine et les routes paient.
2. **La vue (§ 3.11)** : réécriture exacte livrée (×1,4–1,6) — la réobserver
   dans `comptes` de `/api/maint/status` ; puis la décision sur un cache à
   génération.
3. **Ce qui reste dans `_serve_gallery`** : 1,5 à 1,9 s pour 2 519 photos,
   dont ~140 ms de `index` et un `_pkey(Path(UPLOAD_DIR).resolve())` qui fait
   un aller-retour SMB à chaque appel (§ 3.8). La planche entière (§ 3.7) est
   mesurée et écartée : le navigateur n'y est pour rien.
6. **La planche entière (3.7)** : seulement avec une mesure côté navigateur.

---

## 6. Les instruments de ce chantier

| Fichier | Ce qu'il fait |
|---|---|
| `mesure_routes.py` | classe `_perf_routes.json` par temps total, une vue « latence ressentie » par seuils, et depuis le 11/09 **où part le temps** (phases) et les dernières exécutions en détail |
| `mesure_parcours_dossier.py` | compare `iterdir`/`scandir`/`scandir+stat` sur un vrai dossier du NAS, méthodes alternées ; et `_pkey` sur les vraies clés, depuis **`copie.db`** — jamais `photos.db` |
| `test_horloge_routes.py` | 16 bancs : l'horloge compte juste, et ne fait jamais tomber une requête |
| `test_parcours_dossier.py` | 16 bancs : l'ancienne écriture sert d'oracle ; deux bancs comptent les `stat()` |
| `mesure_couverture_vignettes.py` | combien de photos ont leur vignette 512 (sur `copie.db`, noms recalculés) |
| `mesure_fabrication_vignette.py` | ce que coûte une vignette : lecture NAS contre décodage, et la variante `draft` |
| `mesure_peage_gil.py` | ce que coûte un `stat` quand des fils CPU tournent, selon la bascule du GIL et le minuteur de Windows ; et le débit CPU en face |
| `mesure_corbeille.py` | la liste de la corbeille : `exists+is_dir+stat` contre un `stat`, sur le vrai journal |
| `test_vignette_du_tagueur.py`, `test_vignettes_de_fond.py`, `test_corbeille_une_lecture.py` | 12, 15 et 4 bancs, chacun avec l'ancienne écriture en oracle |
| `test_sujets_une_passe.py` | 7 bancs : `pets_list`/`people_list` d'avant, recopiées verbatim, servent d'oracle sur 300 tirages ; le nombre de balayages est compté |
| `test_pkey_memoire.py` | 10 bancs : `_pkey` mémoïsé rend l'ancienne expression sous `PureWindowsPath` ; la carte égale le vrai `build_key_index` ; la 2ᵉ reconstruction ne construit aucun `Path` |
| `sondes.py`, `test_sondes.py` | collectes du GC par génération et retard d'un fil à reprendre le GIL, lues dans `/api/serveur` ; 14 bancs |
| `mesure_memoire.py` | RAM du système, processus regroupés par nom, serveur (plage de travail / privé), défauts de page, compteurs Windows |
| `mesure_cpu.py` | occupation par cœur, processus par cœurs consommés, CPU de chaque fil du serveur |
| `diagnostic_ollama_memoire.py` | ce qu'Ollama déclare (`/api/ps`) contre ce que `llama-server` tient ; drapeaux de mémoire, jamais un chemin |
| `test_horloge_maint_status.py`, `test_passe_index.py` | 8 et 5 bancs, anciennes écritures en oracle |
| `test_last_modified.py` | 9 bancs : la règle à la seconde, les en-têtes tordus, le 304 qui ne vole pas une plage |
| `verifier_content_length.py`, `test_verifier_content_length.py` | toute réponse dit-elle sa longueur ? (le feu vert d'HTTP/1.1) ; 12 bancs sur des cas écrits exprès |
| `test_gel_gc.py` | 8 bancs : le gel, le seuil, ce qui naît après, un interpréteur qui refuse |
| `mesure_vue.py`, `test_vue_rapide.py` | ce que coûte la vue sur les vraies clés, deux écritures alternées ; 5 bancs d'équivalence sur 6 000 clés tirées |
| `test_horloge_phases.py` | 15 bancs + 4 (CPU et défauts par phase) : les phases se succèdent, le détail est borné, rien ne lève ; `_serve_gallery` garde ses arguments et ne livre aucun nom de dossier |

Les deux bancs `mesure_` tournent sur l'agent de banc. L'espace dans un
argument passe par le jeton `b64:` :
`--dossier b64:UGhvdG9zIE1pa2UvMjAyMg` = `Photos Mike/2022`.

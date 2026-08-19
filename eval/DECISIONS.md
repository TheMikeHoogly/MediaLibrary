# Décisions tranchées

> Chaque piste, son verdict, pour ne rien re-proposer. Détail : git ; les
> adoptés stabilisés vivent dans les Acquis du `ROADMAP.md`.

## Reconnaissance, triage, stockage

| Idée / piste | Verdict | Raison |
|---|---|---|
| Garde humain/animal auto (SigLIP 0-shot) | **REJETÉ** (08/08) | 18 % faux rejets. |
| MegaDescriptor plutôt que DINOv2 | **REJETÉ** (31/07) | À armes égales, DINOv2 garde +3,4 pts (r1). |
| `sqlite-vec` ; embeddings INT8 | **REJETÉ** (11/08) | Cosinus numpy sur BLOB suffit. INT8 : ×2, recall@10 0,9685. |

## Tagging / description

| Idée / piste | Verdict | Raison |
|---|---|---|
| Injecter les noms dans le prompt | **REJETÉ** (31/07) | Ignoré 84 % du temps, coût ×2,6. Le LLM décrit, il n'identifie pas. |
| **Re-passe de tagging (~50 h GPU)** | **CLOSE** (16/08, `docs/PROTOCOLE_3B_TAGGING.md`) | 147 paires en aveugle : V2CTX préféré 63,9 % mais hallucinations DOUBLÉES. Le critère est un ET. |
| V2CTX (prompt de PROD) hallucine plus que V0 | **OUVERT** (16/08) | Le banc mesurait la re-passe ; il a mesuré le prompt EN PROD. Adopté sur un 25-15, il DOUBLE les hallucinations. **Pas de V0 sans protocole.** |
| Faits en contexte pour DOCUMENTS/reçus | **HYPOTHÈSE** (16/08) | Strate « piège » : 83 %, seule qui passe — POST-HOC, 30 photos. |
| Modèle de tagging plus GROS | **PARQUÉ** (16/08) | Plafond DUR (4 Go partagés) ; les faits en contexte n'achètent pas la description. |

## Renommage

| Idée / piste | Verdict | Raison |
|---|---|---|
| Appliquer les 7 058 renommages | **FAIT** (17/08) | 36 lots, **0 sauté**, undo complet. |
| Chercher le mécanisme des −250 sans instrument | **REJETÉ → instrument OBSERVÉ** (18/08) | Rien n'était perdu, rien ne comptait : `comptes_index.py` compte au GOULOT (`inexpliqué` 0). |
| Le repli sur le NOM est gardé comme `taken` | **CORRIGÉ** (19/08) | Le scanner écrit le scan dans `DateTimeOriginal` **et** dans le nom : le garde-fou du 17/08 ne fermait qu'une porte sur deux. 73 refusés. |
| Le plan revient sur ce qu'il a renommé | **CORRIGÉ, OBSERVÉ** (19/08) | `est_nom_annee_seule` ne rend un `YYYY0000_` que si la date est devenue précise. Plan régénéré à **0**. |

## Pilotage du serveur

| Idée / piste | Verdict | Raison |
|---|---|---|
| Route HTTP, ou serveur qui se relance seul | **REJETÉ** (19/08) | Il ne peut garantir que son port est libéré, et s'il rate son réveil la sandbox reste dehors. Superviseur séparé, code 42. |
| `arret` coupe aussi le superviseur | **REJETÉ** (19/08) | Un arrêt sans retour est un piège, Mike absent : `arret` met le superviseur en ATTENTE. `device_bash` ne sachant pas SUPPRIMER, le protocole est en écriture seule ; illisible → `marche`. |

## Lieux · recherche (chantier 14a)

| Idée / piste | Verdict | Raison |
|---|---|---|
| Gazetteer `cities1000` SEUL | **CORRIGÉ** (14/08) | Il s'arrête à 1 000 hab. : le domicile (1 257 photos) sortait « Bussigny ». |
| API de géocodage cloud (TomTom, OSM…) | **REJETÉ** | Vie privée du GPS familial ; clé/quota/réseau. |
| Chercher un lieu dans le SEUL chemin | **CORRIGÉ** (15/08) | 6 595 photos ont un `gps_place` que leur dossier ignore. Chemin **OU** géocodé. |
| `_best_time` comme source d'année d'un filtre | **REJETÉ** (15/08) | Il retombe sur `mtime` : le tagging de 2026 a réécrit une photo de 1998. Précise, sinon DOSSIER. |
| **Backfill ÉCRIT du champ `faits`** | **REJETÉ** (19/08) | Un champ figé se périme : sur 81 pourvues, la VUE en corrige **4**. Gravé 43 064 fois pour rien — la vue coûte **1,11 ms** par page de 50. |
| **Segments entiers = la bonne règle pour ce qu'on VOIT** | **FAUX, résultat du chantier** (19/08) | Sur 876 lieux « collés », ~330 sont VRAIS (« Yani2004 » 219, « AchumaniAlto » 48). D'où la découpe sur les frontières de CASSE et de CHIFFRES : « Vallorbe » reste entier, « Cousins&Cousines » ne rend jamais « Ins ». |
| **Règle de lieu unifiée sur ses trois appelants** | **ADOPTÉ, OBSERVÉ** (19/08) | `places_list` et `_cles_du_lieu` délèguent à `faits_vue.lieux_du_chemin` (`tous=True`). « Ins » **493 → 5** ; recherche **499 → 11 dont 0** de « Cousins&Cousines ». Page **2 119 → 1 539 ms**. |
| Le NOM DE FICHIER comme source de lieu | **ADOPTÉ, limite assumée** (19/08) | Sur 61 paires non couvertes par le GPS : **52 vraies** contre **9 fausses** qu'aucune règle syntaxique n'attrapera (« Grupo en la Laguna »). Un booléen à basculer. |
| « France & Belgique » : deux lieux ou aucun ? | **TRANCHÉ PAR LA RÈGLE** (19/08) | `tous=True` les rend tous deux : France **574**, Belgique **157**. |
| Règle de lieu dupliquée serveur / banc | **CORRIGÉ, OBSERVÉ** (19/08) | Tout délègue à `faits_vue`, que les bancs IMPORTENT. « Bremblens » : 2 398, non 30 682. |
| Vecteurs des photos sorties de l'index | **TRAITÉ** (17/08) | 2 374 purgés, quarantaine réversible. **0 muet sur 1 600 résultats**. |
| **Faits AFFICHÉS depuis la vue (planche + visionneuse)** | **ADOPTÉ, OBSERVÉ** (19/08) | Un producteur client, un assembleur serveur, les quatre modes de `/files` partagés. `q=Ins` : 11 photos — 11 dates, 11 lieux, 5 noms, page **1 048–1 462 ms** contre 1 539. `q=montagne` : 1 500 photos en **477–1 082 ms**. |
| **Index inversé des noms, en DEUX passes** | **ADOPTÉ, MESURÉ** (19/08) | Page de 50 : **1,11 ms** contre **9,65 ms** par balayage naïf (**×8,7**). Une passe unique est REJETÉE : `exclude` fait autorité partout, et un retrait posé par une fiche vue APRÈS celle qui attribue ne retirerait rien. |
| Couverture « honnête » à 69,14 % | **PÉRIMÉ → 69,95 %** (19/08) | 30 122 photos avec un fait NON-date — `lieux.txt` a grossi. Dénominateur du filtre (14a-iv), jamais les 99,79 %. |
| Le `mtime` comme date de repli pour CLASSER | **CORRIGÉ, OBSERVÉ** (19/08) | Le filtre le refusait, le tri le gardait : 257 photos datées de 2026 par leur tagging. Sans-date en FIN et COMPTÉES. |
| La page `/files?q=` se taisait | **CORRIGÉ, OBSERVÉ** (19/08) | `/api/search` disait ce qu'il avait compris ; la page, non. Même producteur. |
| « Fichier absent » comme seul critère de purge | **CORRIGÉ** (17/08) | « Il existe » ne dit pas « il sera re-tagué » : 91 photos hors racine scannée. |

## Dates de prise de vue

| Idée / piste | Verdict | Raison |
|---|---|---|
| Aplatir les trois dates EXIF en `min()` | **REJETÉ** (13/08) | `ModifyDate` est souvent la date du SCAN : un 1995 numérisé partait en 2005. Cru **seulement** si son année est dans le CHEMIN. |
| Corriger les dates d'un nom de SCAN | **REJETÉ** (14/08) | 139 réveillons et 914 à un an sont légitimes ; les 215 à ≥ 4 ans sont inséparables. |
| Plancher 1990 des années d'un CHEMIN | **CORRIGÉ → 1900** (14/08) | « 1985 » ne rendait aucune année ; 716 rendues. |
| Les deux planchers 1990 restants | **PARKÉ chiffré** (15/08) | 0 et 7 photos, couplés — Résiduels du ROADMAP. |
| `_path_years` lisait le NOM DE FICHIER | **CORRIGÉ** (14/08) | `119-1908_IMG.JPG` sous un dossier 2002 : `min()` reculait 38 photos de 94 ans. |
| `DateTimeOriginal` cru sans condition au RENOMMAGE | **CORRIGÉ** (17/08) | `date_de_scan_presumee` : une date POSTÉRIEURE de plus d'un an à TOUTES les années du dossier n'est pas crue (12 → 0). |
| Le garde-fou est SYMÉTRIQUE | **REJETÉ** (17/08) | Une date ANTÉRIEURE au dossier est l'EXIF qui corrige un dossier d'import : **1 347** contre 72. |
| Corriger `taken` en BASE | **REJETÉ** (19/08) | 72 corrections face à **1 347** antérieures légitimes — et `taken` est une LECTURE de l'EXIF. Comme `faits`, la correction est une VUE. |
| Le garde-fou de la date de SCAN passe à la LECTURE | **ADOPTÉ, OBSERVÉ** (19/08) | `faits_vue.date_credible` INJECTÉ dans `meme_jour.epoch_precis` : une implémentation pour le tri, le filtre, « même jour » et le fait. **70** photos perdent une date précise fausse. Observé : `Photos Papa\1983\20150810_…` a quitté le « 10 août ». |
| `_best_time` était une COPIE de `epoch_precis` | **CORRIGÉ** (19/08) | Sa branche 1 n'a pas suivi le garde-fou : la galerie datait de 2006 ce que la recherche datait déjà de 1985. Elle délègue. |
| Écrire `None` pour tout un lot ExifTool | **REJETÉ** (13/08) | Un lot raté (NAS muet) est indiscernable d'un lot vide : on n'écrit que si ExifTool a PARLÉ. |
| Plafond 2100 de la date lue dans un NOM | **PARKÉ chiffré** (19/08) | `22082010141.jpg` se lit « 2082 » : 72 en base, coût 0. |

## Interface

| Idée / piste | Verdict | Raison |
|---|---|---|
| Deux ordres de tri suffisent (Date, Nom) | **FAUX, OBSERVÉ** (19/08) | Il y en a TROIS : celui que rend `/api/search`. `/files?q=` allumait « Date ↑ » devant un ordre venu du serveur, et le clic était avalé. **Bouton « Pertinence »**, visible quand un classement existe. |

> **Méthode : `eval/METHODE.md`** — ici *ce qui a été tranché*, là *comment*.

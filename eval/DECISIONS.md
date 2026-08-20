# Décisions tranchées

> Chaque piste, son verdict, pour ne rien re-proposer. Détail : git ; les
> adoptés stabilisés vivent dans les Acquis du `ROADMAP.md`.

## Reconnaissance, triage, stockage

| Idée / piste | Verdict | Raison |
|---|---|---|
| Garde humain/animal auto (SigLIP 0-shot) | **REJETÉ** (08/08) | 18 % faux rejets. |
| MegaDescriptor plutôt que DINOv2 | **REJETÉ** (31/07) | DINOv2 garde +3,4 pts r1. |
| `sqlite-vec` ; embeddings INT8 | **REJETÉ** (11/08) | Cosinus numpy sur BLOB suffit ; INT8 recall@10 0,9685. |

## Tagging / description

| Idée / piste | Verdict | Raison |
|---|---|---|
| Injecter les noms dans le prompt | **REJETÉ** (31/07) | Ignoré 84 % du temps, ×2,6. Le LLM décrit, il n'identifie pas. |
| **Re-passe de tagging (~50 h GPU)** | **CLOSE** (16/08, `docs/PROTOCOLE_3B_TAGGING.md`) | 147 paires en aveugle : V2CTX préféré 63,9 % mais hallucinations DOUBLÉES. |
| V2CTX (prompt de PROD) hallucine plus que V0 | **OUVERT** (16/08) | Le banc mesurait la re-passe ; il a mesuré le prompt EN PROD. Adopté sur un 25-15, il DOUBLE les hallucinations. |
| Faits en contexte pour DOCUMENTS/reçus | **HYPOTHÈSE** (16/08) | Strate « piège » 83 %, seule qui passe — POST-HOC, 30 photos. |
| Modèle de tagging plus GROS | **PARQUÉ** (16/08) | Plafond DUR de 4 Go partagés. |

## Renommage

| Idée / piste | Verdict | Raison |
|---|---|---|
| Appliquer les 7 058 renommages | **FAIT** (17/08) | 36 lots, **0 sauté**, undo complet. |
| Chercher les −250 sans instrument | **REJETÉ → instrument OBSERVÉ** (18/08) | Rien n'était perdu, rien ne comptait : `comptes_index.py` compte au GOULOT (`inexpliqué` 0). |
| Le repli sur le NOM est gardé comme `taken` | **CORRIGÉ** (19/08) | Le scanner écrit le scan dans `DateTimeOriginal` **et** dans le nom : le garde-fou du 17/08 ne fermait qu'une porte sur deux. |
| Le plan revient sur ce qu'il a renommé | **CORRIGÉ, OBSERVÉ** (19/08) | `est_nom_annee_seule` n'agit que si la date est devenue précise (plan à **0**). |

## Pilotage du serveur et livraison git

| Idée / piste | Verdict | Raison |
|---|---|---|
| Route HTTP, ou serveur qui se relance seul | **REJETÉ** (19/08) | Il ne peut garantir que son port est libéré, et s'il rate son réveil la sandbox reste dehors. |
| `arret` coupe aussi le superviseur | **REJETÉ** (19/08) | Un arrêt sans retour est un piège, Mike absent : `arret` met le superviseur en ATTENTE. Protocole en écriture seule ; illisible → `marche`. |
| **Livrer dans git depuis la sandbox** | **ADOPTÉ, OBSERVÉ** (19/08) | `git` lancé depuis la VM laisse un `.git/index.lock` qu'elle ne sait pas supprimer : ce n'était jamais un principe, une impossibilité. Un agent WINDOWS (`git_agent.py`) lance le vrai git, et le verrou disparaît. Premier acte observé : il s'est commité lui-même (`a43f9d0`), push et fast-forward compris. |
| Libérer le port PUIS faire les préparatifs lents | **CORRIGÉ** (19/08) | Le bat 0 tuait l'ancien serveur, puis lançait 40 s de `pip` : un orphelin qui finissait de se lever reprenait le port pendant ce temps, le nouveau ne se liait plus, le superviseur le relançait 5 fois. **Deux processus vus par Mike le 19/08.** Le lent passe AVANT ; et si le port reste tenu après 10 tentatives, on ne lance RIEN — un second serveur est pire qu'un démarrage refusé. |
| Une fenêtre d'agent minimisée | **REJETÉ** (19/08) | Elle s'est fermée sans que personne le voie, et rien ne le disait : une fenêtre morte-née était indiscernable d'une fenêtre en écoute. Fenêtre VISIBLE, `_agent_git_vu.txt` touché à chaque tour, commande `ping` inerte, et le bat 0 contrôle le signe de vie après 6 s. |
| L'agent est un bouton déporté | **REJETÉ** (19/08) | Il est la **porte** : refus tant que le serveur ne fait pas tourner le code visé, qu'un test est rouge, qu'un `.bat` n'est pas ASCII ou que le lint crie. D'où l'ordre **inversé** : observer AVANT de commiter. |
| `force=` lève tous les contrôles | **REJETÉ** (19/08) | Il lève les négociables. Jamais le verrou, jamais `main`, jamais un binaire (`photos.db` = 290 Mo), jamais un `checkout` vers une branche EXISTANTE — qui réécrirait `server.py` sous le serveur. Six tests vérifient exactement ce qu'il n'ouvre pas. |
| Loger l'agent dans le serveur | **REJETÉ** (19/08) | Le serveur est l'OBJET du commit ; un git qui bloque bloquerait une requête ; un serveur du réseau local capable de lancer git est une surface qu'on ne veut pas. |

## Lieux · recherche (chantier 14a)

| Idée / piste | Verdict | Raison |
|---|---|---|
| Gazetteer `cities1000` SEUL | **CORRIGÉ** (14/08) | Il s'arrête à 1 000 hab. : le domicile sortait « Bussigny ». |
| API de géocodage cloud (TomTom, OSM…) | **REJETÉ** | Vie privée du GPS familial ; clé/quota/réseau. |
| Chercher un lieu dans le SEUL chemin | **CORRIGÉ** (15/08) | 6 595 photos ont un `gps_place` que leur dossier ignore. |
| `_best_time` comme source d'année d'un filtre | **REJETÉ** (15/08) | Il retombe sur `mtime` : le tagging de 2026 a réécrit une photo de 1998. Précise, sinon DOSSIER. |
| **Backfill ÉCRIT du champ `faits`** | **REJETÉ** (19/08) | Un champ figé se périme : sur 81 pourvues, la VUE en corrige **4**. Gravé 43 064 fois pour rien. |
| **Segments entiers = la bonne règle pour ce qu'on VOIT** | **FAUX, et c'est le résultat du chantier** (19/08) | Sur 876 lieux « collés », ~330 sont VRAIS — « Yani2004 » (219), « AchumaniAlto » (48), « CuevaMarkusIrpavi » (6). D'où la découpe des mots sur les frontières de CASSE et de CHIFFRES : « Vallorbe » reste entier, « Cousins&Cousines » ne rend jamais « Ins ». |
| **Règle de lieu unifiée sur ses trois appelants** | **ADOPTÉ, OBSERVÉ** (19/08) | `places_list` et `_cles_du_lieu` délèguent à `faits_vue.lieux_du_chemin` (`tous=True` : une photo compte dans CHAQUE lieu). « Ins » **493 → 5** ; recherche **499 → 11 dont 0** de « Cousins&Cousines ». Gains : Sud France 315, San Borja 82, Vallée d'Aoste 81, Rurrenabaque 55. Page **2 119 → 1 539 ms**. |
| Le NOM DE FICHIER comme source de lieu | **ADOPTÉ, limite assumée** (19/08) | 132 paires dont **71 déjà couvertes par le GPS**. Sur les 61 restantes : **52 vraies** contre **9 fausses** qu'aucune règle syntaxique n'attrapera (« Grupo en la Laguna », « MisionSuiza » — en Bolivie). Un booléen à basculer. |
| « France & Belgique » : deux lieux ou aucun ? | **TRANCHÉ PAR LA RÈGLE** (19/08) | `tous=True` les rend tous deux : 574 et 157. |
| Règle de lieu dupliquée serveur / banc | **CORRIGÉ, OBSERVÉ** (19/08) | Tout délègue à `faits_vue`, que les bancs IMPORTENT (« Bremblens » : 2 398, non 30 682). |
| Vecteurs des photos sorties de l'index | **TRAITÉ** (17/08) | 2 374 purgés, réversible. **0 muet sur 1 600 résultats**. |
| **Faits AFFICHÉS depuis la vue (planche + visionneuse)** | **ADOPTÉ, OBSERVÉ** (19/08) | Un seul producteur client (`faitsHtml`), un seul assembleur serveur (`faits_vue.assertions`), les quatre modes de `/files` partagés. Observé : `q=Ins` 11 photos — 11 dates, 11 lieux, 5 noms ; page **1 048–1 462 ms** contre 1 539 ms. `q=montagne` : 1 500 photos en **477–1 082 ms**. |
| **Index inversé des noms, en DEUX passes** | **ADOPTÉ, MESURÉ** (19/08) | Page de 50 : **1,11 ms** contre **9,65 ms** naïf (**×8,7**). Une passe unique est REJETÉE : `exclude` fait autorité partout, et un retrait posé par une fiche vue APRÈS celle qui attribue ne retirerait rien. |
| Couverture « honnête » à 69,14 % | **PÉRIMÉ → 69,95 %** (19/08) | 30 122 photos avec un fait NON-date. Dénominateur du filtre (14a-iv), jamais les 99,79 %. |
| Le `mtime` comme date de repli pour CLASSER | **CORRIGÉ, OBSERVÉ** (19/08) | Le filtre le refusait, le tri le gardait : 257 photos datées de 2026 par leur tagging. |
| La page `/files?q=` se taisait | **CORRIGÉ, OBSERVÉ** (19/08) | `/api/search` disait ce qu'il avait compris ; la page, non. |
| « Fichier absent » comme seul critère de purge | **CORRIGÉ** (17/08) | « Il existe » ne dit pas « il sera re-tagué » : 91 photos hors racine. |

## Dates de prise de vue

| Idée / piste | Verdict | Raison |
|---|---|---|
| Aplatir les trois dates EXIF en `min()` | **REJETÉ** (13/08) | `ModifyDate` est souvent la date du SCAN : un 1995 numérisé partait en 2005. |
| Corriger les dates d'un nom de SCAN | **REJETÉ** (14/08) | 139 réveillons et 914 à un an sont légitimes ; les 215 à ≥ 4 ans, inséparables. |
| Plancher 1990 des années d'un CHEMIN | **CORRIGÉ → 1900** (14/08) | « 1985 » ne rendait rien ; 716 rendues. |
| Les deux planchers 1990 restants | **PARKÉ chiffré** (15/08) | 0 et 7 photos, couplés. |
| `_path_years` lisait le NOM DE FICHIER | **CORRIGÉ** (14/08) | `119-1908_IMG.JPG` sous un dossier 2002 : 38 photos reculées de 94 ans. |
| `DateTimeOriginal` cru sans condition au RENOMMAGE | **CORRIGÉ** (17/08) | `date_de_scan_presumee` : une date postérieure de plus d'un an à TOUTES les années du dossier n'est pas crue (12 → 0). |
| Le garde-fou est SYMÉTRIQUE | **REJETÉ** (17/08) | Une date ANTÉRIEURE au dossier est l'EXIF qui corrige un import : **1 347** contre 72. |
| Corriger `taken` en BASE | **REJETÉ** (19/08) | 72 corrections face à **1 347** antérieures légitimes — et `taken` est une LECTURE de l'EXIF : la correction est une VUE. |
| Le garde-fou de la date de SCAN passe à la LECTURE | **ADOPTÉ, OBSERVÉ** (19/08) | `faits_vue.date_credible` INJECTÉ dans `meme_jour.epoch_precis` (comme `fname_time`) : une implémentation pour le tri, le filtre, « même jour » et le fait. **70** photos perdent une date précise fausse et retombent sur l'année du dossier. Observé : `Photos Papa\1983\20150810_…` a quitté le « 10 août ». |
| `_best_time` était une COPIE de `epoch_precis` | **CORRIGÉ** (19/08) | Sa branche 1 n'avait pas suivi le garde-fou : la galerie datait de 2006 ce que la recherche datait de 1985. |
| Écrire `None` pour tout un lot ExifTool | **REJETÉ** (13/08) | Un lot raté (NAS muet) est indiscernable d'un lot vide : on n'écrit que si ExifTool a PARLÉ. |
| Plafond 2100 de la date lue dans un NOM | **PARKÉ chiffré** (19/08) | `22082010141.jpg` se lit « 2082 » : 72 en base, coût 0. |

## Interface

| Idée / piste | Verdict | Raison |
|---|---|---|
| Les noms répétés sous la visionneuse | **RETIRÉS** (19/08, choix de Mike) | La ligne de faits les dit déjà, triés, sans préfixe et avec leur source ; `personne:Cédric Baudin` sous elle était du bruit, et le préfixe est un détail d'implémentation. État vide RÉDIGÉ : « aucun mot-clé au-delà des noms » — « pas encore de tags » mentirait sur une photo nommée. Le FILTRE de la planche garde les tags nommés : y chercher « personne:Luna » a du sens. |
| Deux ordres de tri suffisent (Date, Nom) | **FAUX, OBSERVÉ** (19/08) | Il y en a TROIS : celui que rend `/api/search`. Le clic sur « Date » était avalé. **Bouton « Pertinence »**, visible quand un classement existe. |

## Gouvernance de ce fichier

| Idée / piste | Verdict | Raison |
|---|---|---|
| Sortir les verdicts clos dans une archive à budget propre | **REJETÉ** (19/08, choix de Mike) | Précédent de `METHODE.md` (16/08), mais deux fichiers à consulter valent moins qu'un seul complet : le réflexe « ne rien re-proposer » suppose de tout relire d'un coup d'œil. |
| **Budget porté de 9 000 à 12 000 octets** | **ADOPTÉ** (19/08, choix de Mike) | À 8 969 pour 9 000, la seule marge restante était la PRÉCISION des raisons — or c'est elle que le seuil protégeait. Condenser encore aurait vidé le fichier de ce qui empêche de re-proposer. Le seuil garde son rôle contre le récit ; le détail des travaux reste dans git. |

> **Méthode : `eval/METHODE.md`** — ici *ce qui a été tranché*, là *comment*.

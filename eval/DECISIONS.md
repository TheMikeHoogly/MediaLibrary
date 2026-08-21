# Décisions tranchées

> **Ce qui a été tranché sur la PHOTOTHÈQUE** — reconnaissance, tagging,
> renommage, lieux, dates, interface. Chaque piste, son verdict, pour ne rien
> re-proposer.
>
> L'OUTILLAGE (les trois canaux, le pilotage, la livraison git) vit dans
> `docs/DECISIONS_OUTILLAGE.md` depuis le 20/08 : le réflexe « ne rien
> re-proposer » est par DOMAINE, et qui travaille la recherche n'a jamais
> besoin de savoir pourquoi `taskkill` a échoué.
>
> Détail des travaux : git. La méthode : `eval/METHODE.md`. Les adoptés
> stabilisés : Acquis du `ROADMAP.md`.

## Reconnaissance, triage, stockage

| Idée / piste | Verdict | Raison |
|---|---|---|
| Garde humain/animal auto (SigLIP 0-shot) | **REJETÉ** (08/08) | 18 % faux rejets. |
| **« Vérité terrain 0,8 % » mélangeait deux mesures** | **CORRIGÉ, PARQUÉ** (21/08, choix de Mike) | Ce dont le PRODUIT a besoin : **18 863** photos portent un `personne:` (44,8 % du fonds vivant, 352 noms) — les gens qu'on connaît sont couverts. Ce dont un ALGORITHME a besoin : **1 196** visages rattachés sur **71 868** (1,66 %). Seul le chantier 9 dépend du second. Et le compte était incomplet : les **1 496 exclusions** sont des étiquettes humaines — « ce visage n'est PAS Flo » évalue un clustering aussi bien qu'un rattachement. Vérité terrain réelle : **2 692 décisions**, pas 1 196. On ne comptait que les positifs. |
| MegaDescriptor plutôt que DINOv2 | **REJETÉ** (31/07) | DINOv2 garde +3,4 pts r1. |
| `sqlite-vec` ; embeddings INT8 | **REJETÉ** (11/08) | Cosinus numpy sur BLOB suffit ; INT8 recall@10 0,9685. |

## Tagging / description

| Idée / piste | Verdict | Raison |
|---|---|---|
| Injecter les noms dans le prompt | **REJETÉ** (31/07) | Ignoré 84 % du temps, ×2,6. Le LLM décrit, il n'identifie pas. |
| **Re-passe de tagging (~50 h GPU)** | **CLOSE** (16/08, `docs/PROTOCOLE_3B_TAGGING.md`) | 147 paires en aveugle : V2CTX préféré 63,9 %, hallucinations DOUBLÉES. |
| V2CTX (prompt de PROD) hallucine plus que V0 | **OUVERT** (16/08) | Le banc mesurait la re-passe ; il a mesuré le prompt EN PROD. Adopté sur un 25-15, il DOUBLE les hallucinations. |
| Faits en contexte pour DOCUMENTS/reçus | **HYPOTHÈSE** (16/08) | Strate « piège » 83 %, seule qui passe — POST-HOC, 30 photos. |
| Modèle de tagging plus GROS | **PARQUÉ** (16/08) | Plafond DUR de 4 Go partagés. |
| **Re-passe de tagging INCRÉMENTALE, sur événement de connaissance** | **OUVERT — protocole à écrire** (21/08, proposé par Mike) | Ce qui est CLOS, c'est la re-passe en LOT (50 h GPU). Un agent qui ne re-décrit que les photos dont la connaissance a CHANGÉ est une autre proposition : le goutte-à-goutte lève l'obstacle des 4 Go de VRAM. Trois conditions avant tout code — un banc en aveugle sur un ET (apport **et** hallucination) ; une **frontière de provenance** entre ce que le modèle a VU et ce qu'on lui a DIT, sans quoi la concordance du 5ᵉ axe mesurerait son propre écho ; un journal avant/après. Et le périmètre est plus petit qu'il n'y paraît : `faits` étant une VUE, la médiathèque apprend DÉJÀ sans LLM — seule la prose de la description reste en jeu. |
| **Injecter les faits fait RÉCITER le modèle** | **MESURÉ, et c'est une contrainte d'architecture** (20-21/08) | Les 82 photos taguées avec les faits en contexte ont dû être écartées du banc d'espèce : leur accord avec YOLO ne prouvait rien, on leur avait soufflé la réponse. Toute reprise du tagging doit donc SÉPARER les deux provenances — c'est la circularité de `METHODE.md`, devenue coûteuse le jour où un axe de recherche s'est mis à dépendre de l'indépendance du tagueur. |

## Renommage

| Idée / piste | Verdict | Raison |
|---|---|---|
| Appliquer les 7 058 renommages | **FAIT** (17/08) | 36 lots, **0 sauté**, undo complet. |
| Chercher les −250 sans instrument | **REJETÉ → instrument OBSERVÉ** (18/08) | Rien n'était perdu, rien ne comptait : `comptes_index.py` compte au GOULOT. |
| Le repli sur le NOM gardé comme `taken` | **CORRIGÉ** (19/08) | Le scanner écrit le scan dans `DateTimeOriginal` **et** dans le nom : le garde-fou du 17/08 ne fermait qu'une porte sur deux. |
| Le plan revient sur ce qu'il a renommé | **CORRIGÉ** (19/08) | `est_nom_annee_seule` n'agit que si la date est devenue précise (plan à **0**). |

## Lieux · recherche (chantier 14a)

| Idée / piste | Verdict | Raison |
|---|---|---|
| Gazetteer `cities1000` SEUL | **CORRIGÉ** (14/08) | Il s'arrête à 1 000 hab. : le domicile sortait « Bussigny ». |
| API de géocodage cloud (TomTom, OSM…) | **REJETÉ** | Vie privée du GPS familial ; clé/quota/réseau. |
| Chercher un lieu dans le SEUL chemin | **CORRIGÉ** (15/08) | 6 595 photos ont un `gps_place` que leur dossier ignore. |
| `_best_time` comme source d'année d'un filtre | **REJETÉ** (15/08) | Il retombe sur `mtime` : le tagging de 2026 a réécrit une photo de 1998. Précise, sinon DOSSIER. |
| **Backfill ÉCRIT du champ `faits`** | **REJETÉ** (19/08) | Un champ figé se périme : sur 81 pourvues, la VUE en corrige **4**. Gravé 43 064 fois pour rien. |
| **Segments entiers = la bonne règle pour ce qu'on VOIT** | **FAUX, et c'est le résultat du chantier** (19/08) | Sur 876 lieux « collés », ~330 sont VRAIS — « Yani2004 » (219), « AchumaniAlto » (48). D'où la découpe des mots sur les frontières de CASSE et de CHIFFRES : « Vallorbe » reste entier, « Cousins&Cousines » ne rend jamais « Ins ». |
| **Règle de lieu unifiée sur ses trois appelants** | **ADOPTÉ, OBSERVÉ** (19/08) | `places_list` et `_cles_du_lieu` délèguent à `faits_vue.lieux_du_chemin` (`tous=True` : une photo compte dans CHAQUE lieu). « Ins » **493 → 5** ; recherche **499 → 11 dont 0** de « Cousins&Cousines ». Gains : Sud France 315, San Borja 82, Vallée d'Aoste 81, Rurrenabaque 55. Page **2 119 → 1 539 ms**. |
| Le NOM DE FICHIER comme source de lieu | **ADOPTÉ, limite assumée** (19/08) | 132 paires dont **71 déjà couvertes par le GPS**. Sur les 61 restantes : **52 vraies** contre **9 fausses** qu'aucune règle syntaxique n'attrapera (« Grupo en la Laguna »). Un booléen à basculer. |
| « France & Belgique » : deux lieux ou aucun ? | **TRANCHÉ PAR LA RÈGLE** (19/08) | `tous=True` les rend tous deux : 574 et 157. |
| Règle de lieu dupliquée serveur / banc | **CORRIGÉ** (19/08) | Tout délègue à `faits_vue`, que les bancs IMPORTENT (« Bremblens » : 2 398, non 30 682). |
| Vecteurs des photos sorties de l'index | **TRAITÉ** (17/08) | 2 374 purgés, réversible. **0 muet sur 1 600 résultats**. |
| **Faits AFFICHÉS depuis la vue (planche + visionneuse)** | **ADOPTÉ, OBSERVÉ** (19/08) | Un seul producteur client (`faitsHtml`), un seul assembleur serveur (`faits_vue.assertions`), les quatre modes de `/files` partagés. `q=Ins` : 11 photos — 11 dates, 11 lieux, 5 noms ; page **1 048–1 462 ms** contre 1 539. `q=montagne` : 1 500 photos en **477–1 082 ms**. |
| **Index inversé des noms, en DEUX passes** | **ADOPTÉ, MESURÉ** (19/08) | Page de 50 : **1,11 ms** contre **9,65 ms** au balayage naïf (**×8,7**) ; index entier 2,234 s. Une passe unique est REJETÉE : `exclude` fait autorité partout, et un retrait posé par une fiche vue APRÈS celle qui attribue ne retirerait rien. Six tests. |
| Couverture « honnête » à 69,14 % | **PÉRIMÉ → 69,95 %** (19/08) | 30 122 photos avec un fait NON-date. Dénominateur du filtre, jamais les 99,79 %. |
| Le `mtime` comme date de repli pour CLASSER | **CORRIGÉ, OBSERVÉ** (19/08) | Le filtre le refusait, le tri le gardait : 257 photos datées de 2026 par leur tagging. |
| La page `/files?q=` se taisait | **CORRIGÉ, OBSERVÉ** (19/08) | `/api/search` disait ce qu'il avait compris ; la page, non. |
| « Fichier absent » comme seul critère de purge | **CORRIGÉ** (17/08) | « Il existe » ne dit pas « il sera re-tagué » : 91 photos hors racine. |
| **Le FILTRE des noms lit les `kw` bruts** | **CORRIGÉ, OBSERVÉ** (20/08, 14a-iv) | L'affichage lisait les fiches, le filtre lisait l'index : deux chemins pour une même question, donc deux réponses. **13 photos** que la recherche rendait alors qu'`exclude` avait retiré le nom (Mike 6, Flo 5, Silvio 1, Danica 1), **0** dans l'autre sens — les 363 tags nommés balayés sur copie. `_autorite_des_noms` : une implémentation, deux appelants. Observé après redémarrage : Silvio **495 → 494**, Danica **325 → 324**, les clés exclues absentes. |
| La FICHE fait foi sur l'ORTHOGRAPHE | **ADOPTÉ, OBSERVÉ** (20/08) | L'index porte des mots-clés écrits avant elle : « Luna · luna » sur 2 photos — le même chat nommé deux fois — et « luna » seul sur 1. Seule la graphie change, jamais le nom ; la recherche compare en minuscules. |
| **Portée du filtre déterministe : 92,74 %** | **MESURÉ** (20/08) | Sur les **30 122** photos à fait NON-date, nom ou lieu en atteint **27 936**. Les **2 186** autres n'ont qu'une ESPÈCE. |
| SigLIP retrouve ce que YOLO a vu | **FAUX, MESURÉ** (20/08, `mesure_espece_recherche.py`) | Rappel dans le top-1500 — ce que la page montre : chat 50,1 % (plafond de page 60 %), chien 50,3 %, oiseau 48,3 %, cheval 72,6 %, mouton 58,7 %, vache 52,2 %. Les 4 750 photos détectées ont TOUTES un vecteur : elles ne sont pas muettes, elles sont mal classées. |
| **`det_score` dit l'ESPÈCE** | **FAUX** (20/08) | Il dit « il y a un animal ici », pas laquelle. `chien` **0,866** sur `…chat-gris-et-blanc-allonge.jpg`, `cheval` **0,934** sur *chien, homme, barrière*, `mouton` **0,919** sur *alpaca, chèvre*, `vache` **0,808** sur *sculpture, fontaine*. Un seuil à 0,5 tenait sur deux échantillons de 12 — la table complète des six espèces l'a réfuté, et c'est Mike qui a lancé le banc. `sp_ia`, la vérification d'espèce, ne couvre que **766 détections sur 7 969**, et seulement le chat. |
| **La matière du 5ᵉ axe : la CONCORDANCE** | **ADOPTÉ** (20/08, choix de Mike) | Deux regards indépendants, YOLO et le tagueur (81 photos écartées : taguées AVEC les faits, elles récitent). Chat **2 316** (92,6 % d'accord), chien 356, oiseau 195, cheval 114, mouton 61, vache 43 — **3 065**. Le tagueur voit **760** chats que YOLO rate. Forme : un jeton `espece:` explicite, jamais une promotion silencieuse. |
| **Ce que le jeton `espece:` AJOUTE** | **MESURÉ** (21/08, `mesure_axe_espece.py`) | Sur la concordance stricte — **3 134** photos — **1 018** ne sont rendues par AUCUN des six mots tapés aujourd'hui ; chat **1 135** à lui seul, soit **47,7 %** de sa concordance (le rappel de SigLIP mesuré le 20/08, vu de l'autre côté). Et sur les **2 186** photos à ESPÈCE SEULE — chiffre retrouvé à l'identique par un second chemin, donc c'en est un — le jeton en atteint **1 499**, dont **409** que rien d'autre ne sort. L'axe rend quelque chose. |
| **Le vrai gain du jeton n'est pas le rappel, c'est la PRÉCISION** | **MESURÉ** (21/08) | Le sémantique remplit TOUJOURS la page : `q=mouton` rend **1 500** photos dont **28** moutons confirmés ; `espece:mouton` en rendrait **32**, tous confirmés par deux regards. Vache : **1 455** des 1 500 sont hors concordance. Le jeton ne gagne pas surtout des photos — il en **retire 1 468**. C'est l'argument qui manquait au 20/08, qui ne comptait que ce qu'on gagne. |
| **Règle ÉLARGIE (poney, brebis, chaton, veau…)** | **REJETÉE, MESURÉE** (21/08) | **+43** photos sur 3 134 (1,4 %) et **+5** sur l'AJOUT : une liste de synonymes à maintenir par espèce, pour un gain qui tient dans le bruit. On câble la STRICTE — le mot et son pluriel, en MOT ENTIER (« château » n'est pas un chat), dans `kw_fr` **ou** `desc`. Les deux sources comptent : le mouton se dit surtout dans `desc` (**38** des 81), le chat presque toujours dans les deux (2 988 sur 3 206). |
| **La concordance du 20/08 n'existait qu'en CHIFFRES** | **CORRIGÉ** (21/08) | Aucun script ne la calculait : ce tableau en portait les résultats, pas la règle. Réécrite en code (`dit_l_espece`, les 82 photos taguées AVEC les faits écartées car elles récitent), elle rend **3 134** contre **3 065** publiés — chat +64, oiseau +44, mouton −29. Même famille, pas le même trait : le trait d'hier ne lisait probablement que `kw_fr`. Un chiffre qu'on ne sait pas reproduire n'est pas une mesure. |
| **Le 5ᵉ axe `espece:` CÂBLÉ (forme A)** | **ADOPTÉ, OBSERVÉ** (21/08) | Un jeton que l'utilisateur ÉCRIT, extrait **avant** les noms — contrairement aux trois autres axes — parce qu'un préfixe n'est ambigu avec rien, alors que le retirer tard le serait. Il filtre sur la CONCORDANCE, calculée à la volée depuis l'ANIMAL_STORE : **4 750** photos portent une détection contre 43 000 entrées d'index, donc **aucun cache à invalider** — une photo taguée il y a dix secondes est filtrable tout de suite. Observé après redémarrage (`code_a_jour` vrai, `verifier_jeton_espece.py`) : `espece:chat` rend **1 500** sur **2 386**, **0 en trop** face à la règle partagée ; `espece:licorne` rend **0** et l'annonce ; `espèce:Chats Luna` rend **198**, les deux axes dits dans la ligne. Le mot NU reste du SENS. Les 82 photos taguées AVEC les faits sont GARDÉES ici alors que le banc les écarte : le banc mesure un accord, et un accord soufflé ne prouve rien ; l'utilisateur, lui, cherche sa photo de chat. |

## Dates de prise de vue

| Idée / piste | Verdict | Raison |
|---|---|---|
| Aplatir les trois dates EXIF en `min()` | **REJETÉ** (13/08) | `ModifyDate` est souvent la date du SCAN : un 1995 numérisé partait en 2005. |
| Corriger les dates d'un nom de SCAN | **REJETÉ** (14/08) | 139 réveillons et 914 à un an sont légitimes ; les 215 à ≥ 4 ans, inséparables. |
| Plancher 1990 des années d'un CHEMIN | **CORRIGÉ → 1900** (14/08) | « 1985 » ne rendait rien ; 716 rendues. |
| `_path_years` lisait le NOM DE FICHIER | **CORRIGÉ** (14/08) | `119-1908_IMG.JPG` sous un dossier 2002 : 38 photos reculées de 94 ans. |
| `DateTimeOriginal` cru sans condition au RENOMMAGE | **CORRIGÉ** (17/08) | `date_de_scan_presumee` : une date postérieure de plus d'un an à TOUTES les années du dossier n'est pas crue (12 → 0). |
| Le garde-fou est SYMÉTRIQUE | **REJETÉ** (17/08) | Une date ANTÉRIEURE au dossier est l'EXIF qui corrige un import : **1 347** contre 72. |
| Corriger `taken` en BASE | **REJETÉ** (19/08) | 72 corrections face à **1 347** antérieures légitimes — `taken` est une LECTURE de l'EXIF : la correction est une VUE. |
| Le garde-fou de la date de SCAN passe à la LECTURE | **ADOPTÉ, OBSERVÉ** (19/08) | `faits_vue.date_credible` INJECTÉ dans `meme_jour.epoch_precis` : une implémentation pour le tri, le filtre, « même jour » et le fait. **70** photos perdent une date précise fausse. Observé : `Photos Papa\1983\20150810_…` a quitté le « 10 août ». |
| `_best_time` était une COPIE de `epoch_precis` | **CORRIGÉ** (19/08) | Sa branche 1 n'avait pas suivi le garde-fou : la galerie datait de 2006 ce que la recherche datait de 1985. |
| Écrire `None` pour tout un lot ExifTool | **REJETÉ** (13/08) | Un lot raté (NAS muet) est indiscernable d'un vide : on n'écrit que si ExifTool a PARLÉ. |
| Planchers 1990 restants ; plafond 2100 | **PARKÉ chiffré** (15 et 19/08) | 0 et 7 photos, couplés ; `22082010141.jpg` se lit « 2082 » — 72 en base, coût 0. |

## Interface

| Idée / piste | Verdict | Raison |
|---|---|---|
| Les noms répétés sous la visionneuse | **RETIRÉS, OBSERVÉ** (19/08, choix de Mike) | La ligne de faits les dit déjà, triés, sans préfixe et avec leur source. État vide RÉDIGÉ : « aucun mot-clé au-delà des noms » — « pas encore de tags » mentirait sur une photo nommée. Le FILTRE de la planche les garde : y chercher « personne:Luna » a du sens. |
| **Les puces d'espèce INSÈRENT le jeton** | **ADOPTÉ, OBSERVÉ** (21/08) | Six puces sous la barre, en mode IA seulement. Cliquer AJOUTE `espece:chat` à ce qui est tapé au lieu de le remplacer : le jeton se compose avec les autres axes (« Luna » + un clic = 198 photos). Bascule au second clic, `aria-pressed` porté, état pris de ce que le SERVEUR a compris — jamais d'une relecture locale de la requête, qui finirait par contredire le moteur. |
| **Sur une page de résultats, filtrer dedans MENT** | **CORRIGÉ, OBSERVÉ** (21/08) | `/files?q=` ne charge que le résultat de la requête précédente ; l'affiner côté client n'intersecte donc que CE sous-ensemble. Observé : après `espece:chat`, cliquer « chien » annonçait **3 photos** — le fonds en a **354**, et le vrai croisement chat ∧ chien en a **5**. Trois chiffres, un seul vrai. Une puce cliquée est une intention explicite : elle RELANCE la requête côté serveur. La barre suit la même règle depuis le choix de Mike : sur une page de résultats elle **cesse de chercher à chaque frappe** — renaviguer en cours de frappe rechargerait la page sous les doigts — et attend **Entrée**, avec un indice « ↵ Entrée pour relancer » tant que le texte diffère. Entre-temps le compte affiché reste celui de la requête PRÉCÉDENTE, ce qui est vrai. Hors mode IA la barre filtre des mots-clés dans la planche chargée : là, filtrer dans ce qui est là est exactement ce qu'on demande. Observé : `montagne` tapé sur la page des chats n'a rien changé au compte, `Entrée` a rendu **1 500** photos de montagne. |
| Deux ordres de tri suffisent (Date, Nom) | **FAUX, OBSERVÉ** (19/08) | Il y en a TROIS : celui que rend `/api/search`. Le clic sur « Date » était avalé. **Bouton « Pertinence »**, visible quand un classement existe. |

## Gouvernance de ce fichier

| Idée / piste | Verdict | Raison |
|---|---|---|
| Sortir les verdicts clos dans une archive PAR STATUT | **REJETÉ** (19/08, choix de Mike) | Précédent de `METHODE.md` (16/08), mais elle coupe un même domaine en deux selon l'ÂGE : il faudrait relire les deux fichiers, et le réflexe « ne rien re-proposer » suppose de tout voir d'un coup d'œil. |
| **Découper par DOMAINE** | **ADOPTÉ** (20/08, choix de Mike) | Ce que l'archive par statut n'avait pas : le réflexe est lui-même par domaine. L'OUTILLAGE part dans `docs/DECISIONS_OUTILLAGE.md` — qui travaille la recherche n'a jamais besoin de savoir pourquoi `taskkill` a échoué, et réciproquement. Chaque fichier reste COMPLET pour son propre réflexe. |
| **Budget 9 000 → 12 000 → 50 000 octets** | **ADOPTÉ** (19 puis 20/08, choix de Mike) | Le 19/08 : à 8 969 pour 9 000, la seule marge restante était la PRÉCISION des raisons — or c'est elle que le seuil protégeait. Le 20/08, re-dépassé le lendemain (six verdicts neufs, tous chiffrés) : porté à 50 000. **Ce que le seuil ne fait plus** : il ne protège plus contre le récit, il ne rattrape qu'un emballement franc. Ce qui protège du récit, c'est la FORME — un tableau, une ligne par verdict, un chiffre ou une réfutation dans chaque raison. La marge retrouvée a d'abord servi à RENDRE la précision rognée le jour même. |

> **Méthode : `eval/METHODE.md`** — ici *ce qui a été tranché*, là *comment*.

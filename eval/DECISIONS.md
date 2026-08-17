# Décisions tranchées

> Chaque piste, son verdict, pour ne rien re-proposer. Chiffres : git.

## Reconnaissance (visages, animaux)

| Idée / piste | Verdict | Raison |
|---|---|---|
| Prototypes multiples par sujet (k ≤ 4) | **ADOPTÉ** (30/07) | Corrige 3 cas, n'en casse aucun ; p≈0,25. **Défavorable aux ANIMAUX** : centroïde unique. |
| Contre-exemples (exclusions comme négatifs) | **REJETÉ** (30/07) | Dégrade partout (−8,7 %). |
| Garde humain/animal auto (SigLIP zéro-shot) | **REJETÉ** (08/08) | Vrais visages et statues/chats se chevauchent : 18 % faux rejets. Remède : action « C'est un animal ». |
| Garde visages sur découpes SANS marge · deux signaux | **PARKÉ** | Seules pistes restantes (la marge 0,3 embarque le chat voisin). |
| Vérification d'espèce (SigLIP relit YOLO) | **ADOPTÉ** (30/07) | 96 % ; corrige macaques et peluches classés chat. |
| MegaDescriptor plutôt que DINOv2 | **REJETÉ** (31/07) | À armes égales DINOv2 garde +3,4 pts. |
| Découpes en plus haute résolution | **REJETÉ** (31/07) | Aucun effet (256 px ne touche que l'affichage). |
| Optimiser plus la re-ID animale | **CLOS** (31/07) | 97,4 % rang-1. Le reste = données. |

## Tagging / description

| Idée / piste | Verdict | Raison |
|---|---|---|
| Tagging vocabulaire contrôlé SigLIP 2 (vs VLM) | **ADOPTÉ** (30/07) | 90 % top-1, 100 % top-3, déterministe. |
| V1 — assertions seules, pixels jetés | **REJETÉ** (31/07) | Descriptions « méta » un tiers du temps ; préférence 10 %. |
| Injecter les noms dans le prompt | **REJETÉ** (31/07) | Ignoré 84 % du temps, coût ×2,6. Le LLM décrit, il n'affirme pas l'identité. |
| Noms/date/lieu par fusion programmatique (Knowledge Builder) | **ADOPTÉ** (31/07) | Faits structurés en post-traitement déterministe : débloque la provenance. |
| **Re-passe complète de tagging (~50 h GPU)** | **CLOSE** (16/08, banc 3b) | 147 paires en aveugle. V2CTX préféré **94/147 (63,9 %, p = 0,0009)**, au-dessus du seuil pré-enregistré (86) — **mais hallucinations doublées : 24 contre 13, apparié 15 contre 4, p = 0,019**. Le critère est un ET, sa branche basse dit « hallucinations en hausse → close ». Et **hors des 30 pièges : 69/117 (59,0 %, p = 0,064), sous le seuil** — tout l'écart venait des documents. |
| V2CTX (prompt de PROD) hallucine plus que V0 | **OUVERT** (16/08) | Le banc mesurait la re-passe ; il a mesuré le prompt EN PRODUCTION. Adopté le 12/08 sur un 25-15, il double les hallucinations sur 147 photos — chaque photo taguée le paie. **Ne pas revenir à V0 sans protocole.** |
| Faits en contexte pour DOCUMENTS/reçus/captures | **HYPOTHÈSE** (16/08) | Strate « piège » : **25/30 (83 %, p = 0,0003)**, la seule qui passe. Plausible, mais POST-HOC sur 30 photos : ça vaut une hypothèse, pas une décision. Protocole propre ou rien. |
| Modèle de tagging plus GROS | **PARQUÉ** (16/08) | Plafond DUR (4 Go partagés). Et le banc 3b a montré que les faits en contexte n'achètent pas la description : aucune hypothèse ne reste. |

## Triage / stockage

| Idée / piste | Verdict | Raison |
|---|---|---|
| Détecteur ML de rebut, détection auto du flou | **REJETÉ par conception** (03/08) | Rebut évident = règle simple ; subtil non isolable sans risquer une bonne photo. Retenu : vue groupée par règle + suppression réversible, le subtil à l'humain. |
| `sqlite-vec` ; embeddings en INT8 | **REJETÉ** (11/08) | Cosinus numpy sur BLOB suffit. INT8 : gain ×2 seulement (159→80 Mo), recall@10 0,9685 — « sans perte » réfuté. |

## Lieux (géocodage inverse hors ligne)

| Idée / piste | Verdict | Raison |
|---|---|---|
| Nommer les lieux au SEUL gazetteer `cities1000` | **CORRIGÉ** (14/08) | Il s'arrête à 1 000 hab. : le domicile (1 257 photos) sortait « Bussigny », et ce libellé part dans les noms de fichiers. `lieux_locaux.txt` : locaux prioritaires (1,5 km) + alias. |
| API de géocodage cloud (TomTom, OSM…) | **REJETÉ** | Vie privée du GPS familial, clé/quota/réseau au démarrage. Gazetteer LOCAL. |

## Recherche (chantier 14a)

| Idée / piste | Verdict | Raison |
|---|---|---|
| Chercher un lieu dans le SEUL chemin du fichier | **CORRIGÉ** (15/08) | Depuis `gps_place`, 6 595 photos ont un lieu que leur dossier ignore. Chemin **OU** lieu géocodé — observé : Lausanne 120 → 1 031. |
| `_best_time` comme source d'année d'un filtre | **REJETÉ** (15/08) | Il retombe sur `mtime` : le tagging de 2026 a réécrit une photo de 1998. Source dédiée : précise, sinon DOSSIER, jamais `mtime` ; un test tombe si on la rebranche. |
| Une seule précision de date pour tous les filtres | **REJETÉ** (15/08) | Exiger le jour partout cache 3 824 photos ; l'accepter partout invente un mois. |
| Filtrer sans dire combien on écarte | **REJETÉ** (15/08) | « 3 photos » se lit « il n'y en a que 3 ». `sans_date` compté et affiché. |
| Fêtes MOBILES (Pâques) | **REJETÉ** (15/08) | Mal placée d'un jour = pire qu'absente. Fixes seulement. |
| Laisser les vecteurs des photos sorties de l'index | **TRAITÉ** (17/08) | 2 374 vecteurs `photo` purgés, **quarantaine réversible** (`_corbeille_vecteurs/`, b64, `--restaurer`). Observé après redémarrage : **0 muet sur 1 600 résultats** (2,6 % avant), 0 orphelin base contre base. Ventilation : 2 143 ARZOPA (clé absolue ET relative), 138 = 69 clés malformées comptées deux fois, 91 `.corbeille-rangement`, 2 disparus. |
| « Fichier absent » comme seul critère de purge | **CORRIGÉ** (17/08) | « Le fichier existe » ne dit pas « il sera re-tagué » : 91 photos bien présentes vivaient hors de toute racine scannée (`.corbeille-rangement`) — muettes à vie. Trois cas, pas deux : absent → purge ; présent HORS PORTÉE → purge ; présent sous racine scannée → épargné (0 en pratique). Règle du scan répliquée dans `sera_re_tague()`, pas devinée. |

## Dates de prise de vue

| Idée / piste | Verdict | Raison |
|---|---|---|
| Aplatir DateTimeOriginal/CreateDate/ModifyDate en `min()` | **REJETÉ** (13/08) | `ModifyDate` est souvent la date du SCAN : un 1995 numérisé partait en 2005. Retenu : `ModifyDate` cru **seulement** si son année est dans le CHEMIN. |
| Corriger les dates venant d'un nom de fichier de SCAN | **REJETÉ** (14/08) | 4,0 % contredisent l'année du chemin, mais 139 réveillons et 914 à 1 an d'écart sont légitimes ; les 215 à ≥ 4 ans en sont inséparables. |
| Plancher 1990 des années lues dans un CHEMIN | **CORRIGÉ → 1900** (14/08) | « 1985 » ne rendait aucune année : `_best_time` tombait sur `mtime`. Observé : 716 photos rendues, 0 régression. |
| Les deux planchers 1990 restants (`_fname_time`, `meme_jour.ANNEE_MIN`) | **PARKÉ chiffré** (15/08) | `ANNEE_MIN` coûte **0 photo**, mais seulement parce que `_fname_time` refuse déjà une année < 1990 dans le NOM DE FICHIER — ce qui coûte **7 photos**. **Couplés** : qui touche l'un touche l'autre. |
| `_path_years` lisait le NOM DE FICHIER | **CORRIGÉ** (14/08) | `119-1908_IMG.JPG` dans un dossier 2002 → `min()` reculait la photo de 94 ans. 38 photos. |
| `DateTimeOriginal` cru sans condition au RENOMMAGE | **CORRIGÉ** (17/08) | `date_fiable` ne garde que `ModifyDate` — un scanner qui remplit `DateTimeOriginal` passe au travers, sa propre docstring le dit. Sans effet visible jusqu'au renommage : **12 photos de « Photos Papa » sous 1990/1993/2003 recevaient un nom en 2007** (trois lots de scan, horodatages espacés de 12 à 20 s). Garde-fou `renommage_facts.date_de_scan_presumee` : une date précise POSTÉRIEURE de plus d'un an à toutes les années du dossier n'est pas crue → repli `YYYY0000`. **Asymétrique** : une date ANTÉRIEURE est au contraire l'EXIF qui a raison contre un dossier d'import (`2026\Photos Floflo` → vraies dates 2014-2018, 20 cas, intacts). Tolérance d'un an = les 139 réveillons du 14/08. Observé : 12 → 0, les 12 noms redeviennent identiques au plan du 12/08, 0 effet de bord. |
| Corriger `taken` en BASE pour ces photos | **OUVERT** (17/08) | Le garde-fou protège le NOM, pas l'index. Second chemin, serveur vivant : `/api/jour` place `1990_Achumani\IMG_1307.jpg` au **1ᵉʳ mai 2007**. Donc tri chronologique, filtre par période et « même jour » se trompent encore. **Portée non mesurée** — le plan ne voit que les noms bruts. Compter d'abord. |
| Écrire `None` pour tout un lot ExifTool | **REJETÉ** (13/08) | Un lot raté (NAS muet) est indiscernable d'un lot vide. On n'écrit que pour les fichiers dont ExifTool a PARLÉ. |

> **Les invariants de méthode ont leur fichier : `eval/METHODE.md`.**
> Ce registre-ci dit *ce qui a été tranché* ; l'autre dit *comment on tranche*.
> Les deux se lisent en début de session.

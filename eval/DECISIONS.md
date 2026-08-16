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
| Laisser les vecteurs des photos sorties de l'index | **À TRAITER** (15/08) | `/api/search` remonte **2 374 photos absentes de `tags`** — résultats MUETS, 2,6 % des résultats. 2 143 = ARZOPA (supprimé le 08/08), 91 en corbeille ; aucun jumeau dans `tags`, purge sans perte. |

## Dates de prise de vue

| Idée / piste | Verdict | Raison |
|---|---|---|
| Aplatir DateTimeOriginal/CreateDate/ModifyDate en `min()` | **REJETÉ** (13/08) | `ModifyDate` est souvent la date du SCAN : un 1995 numérisé partait en 2005. Retenu : `ModifyDate` cru **seulement** si son année est dans le CHEMIN. |
| Corriger les dates venant d'un nom de fichier de SCAN | **REJETÉ** (14/08) | 4,0 % contredisent l'année du chemin, mais 139 réveillons et 914 à 1 an d'écart sont légitimes ; les 215 à ≥ 4 ans en sont inséparables. |
| Plancher 1990 des années lues dans un CHEMIN | **CORRIGÉ → 1900** (14/08) | « 1985 » ne rendait aucune année : `_best_time` tombait sur `mtime`. Observé : 716 photos rendues, 0 régression. |
| Les deux planchers 1990 restants (`_fname_time`, `meme_jour.ANNEE_MIN`) | **PARKÉ chiffré** (15/08) | `ANNEE_MIN` coûte **0 photo**, mais seulement parce que `_fname_time` refuse déjà une année < 1990 dans le NOM DE FICHIER — ce qui coûte **7 photos**. **Couplés** : qui touche l'un touche l'autre. |
| `_path_years` lisait le NOM DE FICHIER | **CORRIGÉ** (14/08) | `119-1908_IMG.JPG` dans un dossier 2002 → `min()` reculait la photo de 94 ans. 38 photos. |
| Écrire `None` pour tout un lot ExifTool | **REJETÉ** (13/08) | Un lot raté (NAS muet) est indiscernable d'un lot vide. On n'écrit que pour les fichiers dont ExifTool a PARLÉ. |

> **Les invariants de méthode ont leur fichier : `eval/METHODE.md`.**
> Ce registre-ci dit *ce qui a été tranché* ; l'autre dit *comment on tranche*.
> Les deux se lisent en début de session.

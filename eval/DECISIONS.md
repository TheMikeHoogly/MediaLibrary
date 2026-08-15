# Décisions tranchées — MediaLibrary

> Registre condensé : chaque piste évaluée, son verdict, pour ne rien
> re-proposer. Chiffres et logs : git.

## Reconnaissance — visages (personnes)

| Idée / piste | Verdict | Raison (1 ligne) |
|---|---|---|
| Prototypes multiples par sujet (k ≤ 4) | **ADOPTÉ** (30/07) | Corrige 3 cas, n'en casse aucun ; gain non significatif (p≈0,25), gardé faute de dégât. |
| Contre-exemples (exclusions comme négatifs) | **REJETÉ** (30–31/07) | Dégrade à toutes les marges (−8,7 %). |
| Garde humain/animal auto (SigLIP zéro-shot) | **REJETÉ** (08/08) | Les vrais visages (endormis, près d'un chat) chevauchent statues/chats : 18 % faux rejets. |
| Remède fausses faces (chien Mutz) | **ADOPTÉ** (08/08) | Action « C'est un animal » : zéro faux rejet. |
| Garde visages sur découpes SANS marge · à deux signaux | **PARKÉ** | Seules pistes restantes (la marge 0,3 embarque le chat voisin ; sinon sortir du seuil global). |

## Reconnaissance — animaux

| Idée / piste | Verdict | Raison |
|---|---|---|
| Vérification d'espèce (SigLIP relit YOLO/COCO) | **ADOPTÉ** (30/07) | 96 % ; corrige macaques et peluches classés chat. |
| Prototypes multiples pour animaux | **REJETÉ** (30/07) | Défavorable (99,8→99,6 %) ; centroïde unique. |
| MegaDescriptor à la place de DINOv2 | **REJETÉ** (31/07) | À armes égales DINOv2 garde +3,4 pts. |
| Augmenter la résolution des découpes | **REJETÉ** (31/07) | Aucun effet mesurable ; le plafond 256 px ne touche que l'affichage. |
| Optimiser plus la re-ID animale | **CLOS** (31/07) | 97,4 % rang-1 ; 7 erreurs sur Inti/Luna. Le reste = données, pas algo. |

## Tagging / description

| Idée / piste | Verdict | Raison |
|---|---|---|
| Tagging vocabulaire contrôlé SigLIP 2 (vs VLM) | **ADOPTÉ** (30/07) | 90 % top-1, 100 % top-3 ; déterministe. |
| V1 — assertions seules, pixels jetés | **REJETÉ** (31/07) | Descriptions « méta » un tiers du temps ; préférence 10 %. |
| Modèle de tagging plus GROS | **À MESURER** | Plafond DUR : 4 Go partagés, `qwen3-vl:4b` déborde. Apporte-t-il encore quelque chose QUAND les faits sont en contexte ? Protocole : `docs/PROTOCOLE_3B_TAGGING.md`. |
| Injecter les noms dans le prompt | **REJETÉ** (31/07) | Nom ignoré 84 % du temps ; coût ×2,6. Le LLM décrit, il n'affirme pas l'identité. **Vaut pour tout re-tagging** (ROADMAP 3c). |
| Noms/date/lieu par fusion programmatique (Knowledge Builder) | **ADOPTÉ** (31/07) | Faits structurés en post-traitement déterministe ; débloque la provenance. |
| V2 — hybride assertions + image | **ADOPTÉ (principe)** (31/07) | Préféré 2 contre 1. |
| Re-passe complète de tagging MAINTENANT (~50 h GPU) | **PARKÉ** (14/08, mesure 3a) | 42 060 des 42 078 entrées en `pipe` v0 : taguées au prompt V0 = **image seule**, zéro fait en contexte par construction. Elles en recevraient aujourd'hui, mais ces faits sont **déjà dans l'index** — la re-passe n'achète que la **description**, sur un 25-15 à p = 0,15. Débloqué par 3b. |
| V2 « assertions en contexte, sans impératif » | **ADOPTÉ** (12/08) | Aveugle A/B vs V0, 40 photos : 25–15 (**p = 0,15** — assez pour le prompt de prod, PAS pour payer une re-passe). Noms via le Knowledge Builder. |

## Triage / stockage / rebut

| Idée / piste | Verdict | Raison |
|---|---|---|
| Détecteur ML de rebut | **REJETÉ par conception** (03/08) | Rebut évident = règle simple ; rebut subtil non isolable sans risquer une bonne photo. |
| Détection auto du flou | **REJETÉ** (03/08) | Flou rare et risqué à signaler ; au mieux clé de tri. |
| Cap triage retenu | **ADOPTÉ** (03/08) | Vue groupée par règle + suppression réversible ; le subtil reste à l'humain. |
| `sqlite-vec` pour la recherche | **REJETÉ** | Cosinus numpy sur BLOB suffit. |
| Embeddings en INT8 (au lieu de f16) | **REJETÉ** (11/08) | Gain ×2 seulement (159→80 Mo) ; recall@10 0,9685 (« sans perte » réfuté). Mesure : `eval/eval_int8_vectors.py`. |

## Lieux (géocodage inverse offline)

| Idée / piste | Verdict | Raison |
|---|---|---|
| Nommer les lieux au SEUL gazetteer `cities1000` | **CORRIGÉ** (14/08) | Il s'arrête à 1 000 habitants : le domicile (**1 257 photos**) sortait « Bussigny », commune voisine — et ce libellé part dans les noms de fichiers. `lieux_locaux.txt` : lieux locaux prioritaires (rayon 1,5 km, pour ne pas avaler l'amas voisin à 2,44 km) + alias (Sitten→Sion, arrondissements→Paris). |
| API de géocodage cloud (TomTom, OSM…) | **REJETÉ** | GPS d'un fonds familial : vie privée, clé/quota/réseau au démarrage. Gazetteer LOCAL. |

## Dates de prise de vue

| Idée / piste | Verdict | Raison |
|---|---|---|
| Aplatir DateTimeOriginal / CreateDate / ModifyDate en `min()` | **REJETÉ** (13/08) | `ModifyDate` seul est souvent la date du SCAN : un 1995 numérisé partait en 2005. |
| `ModifyDate` seul cru si son année est parmi celles du CHEMIN | **ADOPTÉ** (13/08) | Attrape le scan sans rien inventer : contradiction → `None`, la photo garde son repli. Comparé à l'ENSEMBLE des années. Ne couvre pas un scanner qui remplit `DateTimeOriginal`. |
| Corriger les dates venant d'un nom de fichier de SCAN | **REJETÉ** (14/08) | 4,0 % des dates précises contredisent l'année du chemin, mais 139 réveillons et 914 à 1 an d'écart sont légitimes. Restent 215 à ≥ 4 ans, inséparables des 914. |
| Plancher 1990 des années lues dans un CHEMIN | **CORRIGÉ → 1900** (14/08) | Bon pour une date d'appareil, pas pour un nom de dossier : « 1985 » ne rendait aucune année, `_best_time` tombait sur `mtime`, `date_fiable` se désarmait. Observé : 716 photos rendues, 0 régression. |
| `_path_years` lisait le NOM DE FICHIER | **CORRIGÉ** (14/08) | `119-1908_IMG.JPG` dans un dossier 2002 rendait `{1908, 2002}` : `min()` reculait la photo de 94 ans. 38 photos. |
| Écrire `None` (« lu, rien trouvé ») pour tout un lot ExifTool | **REJETÉ** (13/08) | Un lot raté (NAS muet, timeout) est indiscernable d'un lot vide : `None` condamnerait la photo. On n'écrit que pour les fichiers dont ExifTool a parlé. |

## Méthode (invariants à ne pas réapprendre)

- **Circularité de l'auto-évaluation** : un système qui apprend de ses décisions contamine son
  banc. Vérité terrain = **confirmations humaines** seules.
- **Comparaison à armes égales** : vérifier ce que chaque modèle *reçoit vraiment* — un banc
  biaisé a produit un verdict sans fondement (30/07).
- **Un proxy n'est pas le juge final** : ils disaient « V2 ≈ V0 », l'humain a tranché 2 contre
  1. Noter à l'aveugle. Et un bon score MOYEN n'est pas un feu vert : ce qui compte est
  souvent le coût des faux rejets (une bonne photo cachée > un rebut manqué).
- **Fragilité du corpus** : clés corrompues et mutation concurrente ont invalidé des runs →
  `--mesurer` alerte au-delà de 15 % de clés mortes.
- **Ordre imposé (`vision-eval`)** : hypothèse + protocole *avant* de mesurer, puis décider,
  câbler. **Un écart de 5 photos n'est pas un vainqueur** (14/08) : 25-15 sur 40 donne
  p = 0,15. Dimensionner le banc AVANT (≈123 paires pour une préférence de 62,5 %) — surtout
  quand il porte une décision de dizaines d'heures de GPU.
- **Mesurer par le chemin de code de la DONNÉE, pas par une vue** (14/08) : les dossiers-
  témoins semblaient inchangés — la vue ne trouvait pas les entrées. Par clé : 0 % → 60 %.
- **Trois façons de perdre une capacité en silence** (14/08) : un **effet de bord à l'import**
  s'exécute chez tous ceux qui LISENT le fichier ; un **repli silencieux déguise la cause en
  symptôme** ; une **protection qui s'annule** doit se COMPTER.
- **Un banc qui RECOPIE la prod finit par mesurer autre chose qu'elle** (14/08) : dates en
  epoch brut (150/150), lieux inventés par la branche de secours de `lieux_connus`, prompt
  resté à la variante impérative. Le banc IMPORTE la prod, il ne la réécrit plus.
- **Un avant/après n'existe que si l'AVANT a été enregistré** (14/08) : `faits` ne date que de
  kb1 — comparer alors/aujourd'hui sur des entrées v0 répond toujours « tout est nouveau ».
  Tautologie déguisée en mesure. **Chercher le fait qui tient sans journal** : le prompt v0
  était l'image seule, donc zéro fait en contexte, sans rien avoir à relire.
- **Un référentiel générique nomme mal le particulier** (14/08) : `cities1000` ignore les
  villages sous 1 000 habitants et a nommé le domicile du nom de la commune voisine
  (1 257 photos). Prévoir la reprise en main humaine là où la donnée publique s'arrête.
- **Chercher un défaut en trouve un autre, plus gros** (14/08) : la piste valait 62 photos ;
  la mesure faite pour la CLASSER en a exhumé 714.
- **Mesurer la matière première avant de bâtir dessus** (13/08) : « même jour » supposait des
  dates au jour près ; 29 % n'en avait. **Un travail de fond silencieux est suspect.**

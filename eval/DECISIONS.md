# Décisions tranchées — MediaLibrary

> Registre condensé : chaque piste évaluée et son verdict, pour ne rien
> re-proposer. Chiffres et logs de run : git.

## Reconnaissance — visages (personnes)

| Idée / piste | Verdict | Raison (1 ligne) |
|---|---|---|
| Prototypes multiples par sujet (k ≤ 4) | **ADOPTÉ** (30/07) | Corrige 3 cas, n'en casse aucun ; gain non significatif (p≈0,25), gardé faute de dégradation. |
| Contre-exemples (exclusions comme négatifs) | **REJETÉ** (30–31/07) | Dégrade à toutes les marges (−8,7 % top-1). |
| Garde humain/animal auto (SigLIP zéro-shot sur découpes) | **REJETÉ** (08/08) | Les vrais visages (endormis, près d'un chat) chevauchent statues/chats : 18 % faux rejets. |
| Remède fausses faces (chien Mutz) | **ADOPTÉ** (08/08) | Action manuelle « C'est un animal » : zéro faux rejet. |
| Garde visages sur découpes SANS marge | **PARKÉ** | Seule piste restante (la marge 0,3 embarque le chat voisin). |
| Garde à deux signaux (non-humain net ET embedding faible) | **PARKÉ** | Alternative au seuil global. |

## Reconnaissance — animaux

| Idée / piste | Verdict | Raison |
|---|---|---|
| Vérification d'espèce (SigLIP relit YOLO/COCO) | **ADOPTÉ** (30/07) | 96 % ; corrige macaques/peluches classés chat. |
| Prototypes multiples pour animaux | **REJETÉ** (30/07) | Défavorable (99,8→99,6 %) ; centroïde unique. |
| MegaDescriptor à la place de DINOv2 | **REJETÉ** (31/07) | À armes égales DINOv2 garde +3,4 pts ; hors-distribution sur chats. |
| Augmenter la résolution des découpes | **REJETÉ** (31/07) | Aucun effet mesurable ; le plafond 256 px ne touche que l'affichage. |
| Optimiser plus la re-ID animale | **CLOS** (31/07) | 97,4 % rang-1 ; 7 erreurs sur la paire Inti/Luna. Le reste = données, pas algo. |

## Tagging / description

| Idée / piste | Verdict | Raison |
|---|---|---|
| Tagging vocabulaire contrôlé SigLIP 2 (vs VLM) | **ADOPTÉ** (30/07) | 90 % top-1, 100 % top-3 ; déterministe, tag ajouté sans réanalyse. |
| V1 — assertions seules, pixels jetés | **REJETÉ** (31/07) | Descriptions « méta » un tiers du temps ; préférence 10 %. |
| Modèle de tagging plus GROS (« plus lent mais plus précis ») | **À MESURER** (14/08) | Plafond DUR : 4 Go partagés, `qwen3-vl:4b` déborde déjà. Au banc : apporte-t-il encore quelque chose QUAND les faits sont en contexte (v2ctx) ? À trancher AVANT la re-passe — ROADMAP 3b. |
| Injecter les noms dans le prompt | **REJETÉ** (31/07) | Nom ignoré 84 % du temps ; coût ×2,6, VRAM au plafond. Le LLM décrit, il n'affirme pas l'identité. **Vaut encore pour tout re-tagging** (ROADMAP 3c). |
| Noms/date/lieu par fusion programmatique (Knowledge Builder), pas via prompt | **ADOPTÉ** (31/07) | Faits structurés en post-traitement déterministe ; débloque la provenance. |
| V2 — hybride assertions + image | **ADOPTÉ (principe)** (31/07) | Préféré 2 contre 1. |
| Re-passe complète de tagging MAINTENANT (~50 h GPU) | **PARKÉ** (14/08, mesure 3a) | 42 060 des 42 078 entrées en `pipe` v0, taguées au prompt V0 = **image seule** : zéro fait en contexte, par construction. Elles en recevraient aujourd'hui (date 41 818 · nom 18 886 · lieu 5 814), mais ces faits sont **déjà dans l'index** : la re-passe n'achète que la **description**, dont tout le fondement est un 25-15 sur 40 photos, p = 0,15. Débloqué par 3b. Chiffres : `mesure_repasse.txt`. |
| V2 « assertions en contexte, sans impératif de noms » | **ADOPTÉ** (12/08) | Aveugle A/B vs V0, 40 photos : préférée 25–15 (**écart non significatif, p = 0,15** — assez pour le prompt de prod, PAS pour payer une re-passe), 4,26 s/photo vs 5,4 et 11,1. Noms via le Knowledge Builder. |

## Triage / stockage / rebut

| Idée / piste | Verdict | Raison |
|---|---|---|
| Détecteur ML de rebut (nom + flou + SigLIP) | **REJETÉ par conception** (03/08) | Rebut évident = règle simple ; rebut subtil non isolable sans risquer une bonne photo. |
| Détection auto du flou comme flag | **REJETÉ** (03/08) | Flou rare et risqué à signaler ; au mieux clé de tri. |
| Cap triage retenu | **ADOPTÉ** (03/08) | Vue groupée par règle + suppression réversible ; le subtil reste à l'humain. |
| `sqlite-vec` pour la recherche vectorielle | **REJETÉ** | Cosinus numpy sur BLOB suffit. |
| Embeddings en INT8 (au lieu de f16) | **REJETÉ** (11/08) | Gain ×2 seulement (159→80 Mo) ; recall@10 0,9685 (« sans perte » réfuté) et perte du « identique au bit près ». Mesure : `eval/eval_int8_vectors.py`. |

## Dates de prise de vue

| Idée / piste | Verdict | Raison |
|---|---|---|
| Aplatir DateTimeOriginal / CreateDate / ModifyDate en un `min()` | **REJETÉ** (13/08) | `ModifyDate` seul est souvent la date du SCAN : un 1995 numérisé en 2005 partait en 2005. Champs séparés. |
| `ModifyDate` seul cru si son année figure parmi celles du CHEMIN | **ADOPTÉ** (13/08) | Attrape le scan sans rien inventer : contradiction → `None`, la photo garde son repli. Comparé à l'ENSEMBLE des années du chemin. N'attrape PAS un scanner qui remplit `DateTimeOriginal`. |
| Corriger les photos datées par un nom de fichier de SCAN | **REJETÉ** (14/08) | Sur 38 254 photos à date précise, 4,0 % contredisent l'année du chemin — mais 139 réveillons et 914 à 1 an d'écart sont légitimes. Restent 215 à ≥ 4 ans, dont 62 du nom : aucune règle ne les sépare des 914. |
| Plancher 1990 des années lues dans un CHEMIN | **CORRIGÉ → 1900** (14/08) | Bon pour une date d'appareil, pas pour un nom de dossier : « 1985 » ne rendait aucune année, `_best_time` tombait sur `mtime` et `date_fiable` se désarmait. Observé : 716 photos rendues, 0 régression sur 20 239 fichiers. |
| `_path_years` lisait le NOM DE FICHIER, pas seulement les dossiers | **CORRIGÉ** (14/08) | `119-1908_IMG.JPG` dans un dossier 2002 rendait `{1908, 2002}` : `min()` reculait la photo de 94 ans. Masqué par le plancher 1990. 38 photos, 0 qui perd son repli. |
| Écrire `None` (« lu, rien trouvé ») pour tout un lot ExifTool | **REJETÉ** (13/08) | Un lot raté (NAS muet, timeout) est indiscernable d'un lot vide : `None` condamnerait la photo. On n'écrit que pour les fichiers dont ExifTool a parlé (`valeurs_a_ecrire`) ; les muets sont comptés. |

## Méthode (invariants à ne pas réapprendre)

- **Circularité de l'auto-évaluation** : un système qui apprend de ses décisions contamine
  son banc. Vérité terrain = **confirmations humaines** seules. Le manque réel est presque
  toujours la donnée humaine.
- **Comparaison à armes égales** : vérifier ce que chaque modèle *reçoit vraiment*
  (résolution, marge, source) — un banc biaisé a produit un verdict sans fondement (30/07).
- **Un proxy n'est pas le juge final** : les proxies disaient « V2 ≈ V0 », l'humain a tranché
  2 contre 1. Prévoir une notation à l'aveugle.
- **Un bon score moyen n'est pas un feu vert** : ce qui compte est souvent le coût des faux
  rejets (une bonne photo cachée > un rebut manqué).
- **Fragilité du corpus** : clés corrompues et mutation concurrente ont invalidé des runs →
  `--mesurer` alerte si >15 % des clés ne résolvent plus.
- **Ordre imposé (`vision-eval`)** : hypothèse + protocole *avant* de mesurer, puis mesurer,
  décider, câbler. **Un écart de 5 photos n'est pas un vainqueur** (14/08) : 25-15 sur 40
  donne p = 0,15. Dimensionner le banc AVANT (≈123 photos pour une préférence de 62,5 %) —
  surtout quand la décision qu'il porte coûte des dizaines d'heures de GPU.
- **Mesurer par le chemin de code de la DONNÉE, pas par une vue** (14/08) : les
  dossiers-témoins semblaient inchangés — la vue ne trouvait pas les entrées (casse des clés
  SMB). Lue par clé d'index : 0 % → 60 %.
- **Trois façons de perdre une capacité en silence** (14/08) : (a) un **effet de bord à
  l'import** s'exécute chez tous ceux qui LISENT le fichier ; (b) un **repli silencieux
  déguise la cause en symptôme du repli** (le 404 visait le secours, la panne était un
  `except OSError` muet) ; (c) une **protection qui s'annule** doit se COMPTER.
- **Un avant/après n'existe que si l'AVANT a été enregistré** (14/08) : `faits` ne date que de
  kb1 — comparer alors/aujourd'hui sur des entrées v0 répond toujours « tout est nouveau ».
  Tautologie déguisée en mesure. **Chercher le fait qui tient sans journal** : ici, le prompt
  v0 était l'image seule, donc zéro fait en contexte, sans avoir rien à relire.
- **Chercher un défaut en trouve souvent un autre, plus gros** (14/08) : la piste de départ
  valait 62 photos ; la mesure faite pour la CLASSER en a exhumé 714.
- **Mesurer la matière première avant de bâtir dessus** (13/08) : « même jour » supposait des
  dates au jour près ; 29 % de la photothèque n'en avait aucune, à cause d'un bug de démarrage
  vieux de plusieurs mois. **Un travail de fond silencieux est un travail de fond suspect.**

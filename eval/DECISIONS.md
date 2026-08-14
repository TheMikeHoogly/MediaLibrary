# Décisions tranchées — MediaLibrary

> Registre condensé : chaque piste évaluée, avec son verdict, pour ne rien
> re-proposer. Le détail chiffré et les logs de run vivent dans git.

## Reconnaissance — visages (personnes)

| Idée / piste | Verdict | Raison (1 ligne) |
|---|---|---|
| Prototypes multiples par sujet (k ≤ 4) | **ADOPTÉ** (30/07) | Corrige 3 cas, n'en casse aucun ; gain non significatif (p≈0,25), gardé faute de dégradation. |
| Contre-exemples (exclusions comme négatifs) | **REJETÉ** (30–31/07) | Dégrade à toutes les marges (−8,7 % top-1). |
| Garde humain/animal auto (SigLIP zéro-shot sur découpes) | **REJETÉ** (08/08) | Les vrais visages (endormis, près d'un chat) chevauchent statues/chats : 18 % faux rejets, aucun seuil ne sépare. |
| Remède fausses faces (chien Mutz) | **ADOPTÉ** (08/08) | Action manuelle « C'est un animal » : zéro faux rejet. |
| Garde visages sur découpes SANS marge | **PARKÉ** | Seule piste restante (la marge 0,3 embarque le chat voisin). |
| Garde à deux signaux (non-humain net ET embedding faible) | **PARKÉ** | Alternative au seuil global. |

## Reconnaissance — animaux

| Idée / piste | Verdict | Raison |
|---|---|---|
| Vérification d'espèce (SigLIP relit YOLO/COCO) | **ADOPTÉ** (30/07) | 96 % ; corrige macaques/peluches classés chat. `par_humain` jamais réévalué. |
| Prototypes multiples pour animaux | **REJETÉ** (30/07) | Défavorable (99,8→99,6 %) ; centroïde unique. |
| MegaDescriptor à la place de DINOv2 | **REJETÉ** (31/07) | À armes égales DINOv2 garde +3,4 pts ; hors-distribution sur chats. |
| Augmenter la résolution des découpes | **REJETÉ** (31/07) | Aucun effet mesurable ; le plafond 256 px ne touche que l'affichage. |
| Optimiser plus la re-ID animale | **CLOS** (31/07) | 97,4 % rang-1 ; 7 erreurs sur la seule paire Inti/Luna. Le reste = données, pas algo. |

## Tagging / description

| Idée / piste | Verdict | Raison |
|---|---|---|
| Tagging vocabulaire contrôlé SigLIP 2 (vs VLM) | **ADOPTÉ** (30/07) | 90 % top-1, 100 % top-3 ; déterministe, tag ajouté sans réanalyse. |
| V1 — assertions seules, pixels jetés | **REJETÉ** (31/07) | Descriptions « méta » un tiers du temps ; préférence humaine 10 %. |
| Modèle de tagging plus GROS (« plus lent mais plus précis ») | **À MESURER** (14/08) | Plafond DUR : 4 Go partagés, `qwen3-vl:4b` déborde déjà. Question au banc : un modèle plus gros apporte-t-il encore quelque chose QUAND les faits sont donnés en contexte (v2ctx) ? À trancher AVANT le re-tagging (~51 h GPU) — ROADMAP 3. |
| Injecter les noms dans le prompt | **REJETÉ** (31/07) | Le modèle ignore le nom 84 % du temps ; coût ×2,6, VRAM au plafond. Le LLM décrit, il n'affirme pas l'identité. **Vaut encore pour tout re-tagging** (ROADMAP 3c). |
| Noms/date/lieu par fusion programmatique (Knowledge Builder), pas via prompt | **ADOPTÉ** (31/07) | Faits structurés en post-traitement déterministe ; débloque la provenance. |
| V2 — hybride assertions + image | **ADOPTÉ (principe)** (31/07) | Préféré par l'humain 2 contre 1. |
| V2 « assertions en contexte, sans impératif de noms » | **ADOPTÉ** (12/08) | Aveugle A/B vs V0, 40 photos : préférée **25–15**, **4,26 s/photo** vs 5,4 (V0) et 11,1 (V2 impérative). **Variante de prod** ; les noms passent par le Knowledge Builder. |

## Triage / stockage / rebut

| Idée / piste | Verdict | Raison |
|---|---|---|
| Détecteur ML de rebut (nom + flou + SigLIP) | **REJETÉ par conception** (03/08) | Rebut évident = règle simple ; rebut subtil non isolable sans risquer une bonne photo. |
| Détection auto du flou comme flag | **REJETÉ** (03/08) | Flou rare et risqué à signaler ; au mieux clé de tri, jamais un flag. |
| Cap triage retenu | **ADOPTÉ** (03/08) | Vue groupée par règle + suppression réversible ; le subtil reste à l'humain. |
| `sqlite-vec` pour la recherche vectorielle | **REJETÉ** | Cosinus numpy sur BLOB suffit ; dépendance évitée. |
| Embeddings en INT8 (au lieu de f16) | **REJETÉ** (11/08) | Gain ×2 seulement (159→80 Mo) ; recall@10 0,9685 (« sans perte » réfuté) et perte du « identique au bit près » de `vectors.py`. Mesure : `eval/eval_int8_vectors.py`. |

## Dates de prise de vue

| Idée / piste | Verdict | Raison |
|---|---|---|
| Aplatir DateTimeOriginal / CreateDate / ModifyDate en un `min()` | **REJETÉ** (13/08) | `ModifyDate` seul est souvent la date du SCAN : un 1995 numérisé en 2005 partait en 2005. Champs séparés. |
| `ModifyDate` seul cru si son année figure parmi celles du CHEMIN | **ADOPTÉ** (13/08) | Attrape le scan sans rien inventer : en cas de contradiction, `None`, et la photo garde son repli. Comparé à l'ENSEMBLE des années, jamais au seul `min`. N'attrape PAS un scanner qui remplit `DateTimeOriginal`. |
| Corriger les photos datées par un nom de fichier de SCAN | **REJETÉ** (14/08) | Sur 38 254 photos à date précise : 4,0 % contredisent l'année du chemin, mais 139 réveillons et 914 à 1 an d'écart sont légitimes. Reste **215 à ≥ 4 ans (0,56 %)**, dont **62** venant du nom (le gros lot EXIF est une GoPro à l'horloge fausse). Aucune règle ne sépare ces 215 des 914 sans risquer de vraies dates. |
| Plancher 1990 des années lues dans un CHEMIN | **CORRIGÉ → 1900** (14/08) | Bon pour une date d'appareil, pas pour un nom de dossier : « 1985 » ne rendait aucune année, donc `_best_time` tombait sur `mtime` (**714 photos de 1982-1989 datées de 2026**) et `date_fiable` se désarmait. `server._path_years` + `renommage_facts.path_year` ; observé : 716 photos rendues à leur décennie, 0 régression sur 20 239 fichiers. |
| `_path_years` lisait le NOM DE FICHIER, pas seulement les dossiers | **CORRIGÉ** (14/08) | `119-1908_IMG.JPG` dans un dossier 2002 rendait `{1908, 2002}`, `min()` reculait la photo de 94 ans. Masqué par le plancher 1990, donc à boucher en le descendant. 38 photos concernées, **0 qui perd son repli** (une vraie date de nom passe avant, par `_fname_time`). |
| Écrire `None` (« lu, rien trouvé ») pour tout un lot ExifTool | **REJETÉ** (13/08) | Un lot raté (NAS muet, timeout) est indiscernable d'un lot vide : `None` condamnerait la photo pour toujours. On n'écrit que pour les fichiers dont ExifTool a parlé (`valeurs_a_ecrire`), les « muets » sont comptés dans `/reglages`. Vaut aussi pour `namechk`. |

## Méthode (invariants à ne pas réapprendre)

- **Circularité de l'auto-évaluation** : un système qui apprend de ses décisions contamine
  son banc. Vérité terrain = **confirmations humaines** seules (`confirmed`). Le manque réel
  est presque toujours la donnée humaine.
- **Comparaison à armes égales** : vérifier ce que chaque modèle *reçoit vraiment*
  (résolution, marge, source) — un banc biaisé a produit un verdict sans fondement (30/07).
- **Un proxy n'est pas le juge final** : les proxies disaient « V2 ≈ V0 », l'humain a tranché
  2 contre 1. Prévoir une notation à l'aveugle. Vaut pour le banc « modèle plus gros ».
- **Un bon score moyen n'est pas un feu vert** : la métrique qui compte est souvent le coût
  des faux rejets (une bonne photo cachée > un rebut manqué).
- **Fragilité du corpus** : clés corrompues et mutation concurrente ont invalidé des runs →
  `--mesurer` alerte si >15 % des clés ne résolvent plus.
- **Ordre imposé (`vision-eval`)** : hypothèse + protocole *avant* de mesurer, puis mesurer,
  décider, câbler. Écart minimal (≥ 5 photos) avant de déclarer un vainqueur.
- **Mesurer par le chemin de code de la DONNÉE, pas par une vue** (14/08) : après la
  réparation des dates, les dossiers-témoins semblaient inchangés — la vue ne trouvait pas les
  entrées (casse des clés SMB). Lue par clé d'index : 0 % → 60 %.
- **Trois façons de perdre une capacité en silence** (14/08, le même jour) : (a) un **effet
  de bord à l'import** s'exécute chez tous ceux qui LISENT le fichier — les `mkdir` au niveau
  module ont fabriqué sous POSIX deux dossiers `\\NAS-Bremblens\home\…` que Windows relit en
  UNC ; (b) un **repli silencieux déguise la cause en symptôme du repli** — le « 404 » visait
  le téléchargement de secours, la panne était un `except OSError` muet ; (c) un **garde-fou
  sans point de comparaison ne garde rien** — le plancher 1990 rendait le chemin muet
  précisément sur les dossiers que `date_fiable` devait protéger. Une protection qui s'annule
  doit se COMPTER.
- **Chercher un défaut en trouve souvent un autre, plus gros** (14/08) : la piste de départ
  valait 62 photos ; la mesure faite pour la CLASSER en a exhumé 714.
- **Mesurer la matière première avant de bâtir dessus** (13/08) : « même jour » supposait des
  dates au jour près ; 29 % de la photothèque n'en avait aucune, à cause d'un bug de démarrage
  vieux de plusieurs mois. **Un travail de fond silencieux est un travail de fond suspect.**

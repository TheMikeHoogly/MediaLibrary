# Décisions tranchées — MediaLibrary

> Registre condensé : chaque piste déjà évaluée, avec son verdict, pour ne rien
> re-proposer. Le détail chiffré, les logs de run et les matrices de confusion vivent
> dans l'historique git (ce fichier était le journal narratif de 37 Ko).

## Reconnaissance — visages (personnes)

| Idée / piste | Verdict | Raison (1 ligne) |
|---|---|---|
| Prototypes multiples par sujet (k ≤ 4) | **ADOPTÉ** (30/07) | Corrige 3 cas, n'en casse aucun ; gain non significatif (p≈0,25), gardé faute de dégradation. |
| Contre-exemples (exclusions comme négatifs) | **REJETÉ** (30–31/07) | Dégrade à toutes les marges ; massif quand exclusions nombreuses (8,7 % top-1). |
| Garde humain/animal auto (SigLIP zéro-shot sur découpes) | **REJETÉ** (08/08) | Scores des vrais visages (endormis, près d'un chat) chevauchent statues/chats : 18 % faux rejets, aucun seuil global ne sépare. VRAM OK (2707 Mo). |
| Remède fausses faces (chien Mutz) | **ADOPTÉ** (08/08) | Action manuelle « C'est un animal » (/people, miroir /pets) : zéro faux rejet. |
| Garde visages sur découpes SANS marge | **PARKÉ** | Seule piste restante (marge 0,3 embarque le chat voisin) ; à mesurer avant câblage. |
| Garde à deux signaux (non-humain net ET embedding faible) | **PARKÉ** | Alternative au seuil global, à mesurer. |

## Reconnaissance — animaux

| Idée / piste | Verdict | Raison |
|---|---|---|
| Vérification d'espèce (SigLIP relit YOLO/COCO) | **ADOPTÉ** (30/07) | Précision 96 % ; corrige macaques/peluches classés chat. Garde-fou : `par_humain` jamais réévalué. |
| Prototypes multiples pour animaux | **REJETÉ** (30/07) | Défavorable (99,8→99,6 %) ; centroïde unique conservé. |
| MegaDescriptor à la place de DINOv2 | **REJETÉ** (31/07) | À armes égales DINOv2 garde +3,4 pts ; MegaDescriptor hors-distribution sur chats d'intérieur. |
| Augmenter la résolution des découpes | **REJETÉ** (31/07) | Aucun effet mesurable ; le plafond 256 px ne concerne que l'affichage. |
| Optimiser plus la re-ID animale | **CLOS** (31/07) | 97,4 % rang-1 ; 7 erreurs sur la seule paire Inti/Luna. Gain restant = données, pas algo. |

## Tagging / description

| Idée / piste | Verdict | Raison |
|---|---|---|
| Tagging vocabulaire contrôlé SigLIP 2 (vs VLM) | **ADOPTÉ** (30/07) | 90 % top-1, 100 % top-3 ; déterministe, ajout de tag sans réanalyse. |
| V1 — assertions seules, pixels jetés | **REJETÉ** (31/07) | Descriptions « méta » un tiers du temps ; préférence humaine 10 %. |
| Injecter les noms dans le prompt | **REJETÉ** (31/07) | Modèle ignore le nom 84 % du temps ; coût ×2,6, VRAM au plafond. Le LLM décrit, n'affirme pas l'identité. |
| V2 — hybride assertions + image | **ADOPTÉ (principe)** (31/07) | Préféré par l'humain 2 contre 1. |
| Noms/date/lieu par fusion programmatique (Knowledge Builder), pas via prompt | **ADOPTÉ** (31/07) | Faits structurés en post-traitement déterministe ; débloque la provenance. |
| V2 « assertions en contexte, sans impératif de noms » | **ADOPTÉ** (12/08) | Aveugle A/B vs V0, 40 photos, notes via `/eval` : préférée **25–15** (écart ≥ 5 : ok), hallucinations 6 vs 4 (jugées contre la photo, n faible) ; **4,26 s/photo** vs 5,4 (V0) et 11,1 (V2 impérative), JSON malformé 0,7 %. Réponses réutilisées de `tagging_results.v2avant.json` — zéro GPU. C'est la **variante de prod** : les noms passent par le Knowledge Builder (fusion programmatique), jamais par le prompt. |

## Triage / stockage / rebut

| Idée / piste | Verdict | Raison |
|---|---|---|
| Détecteur ML de rebut (nom + flou + SigLIP zéro-shot) | **REJETÉ par conception** (03/08) | Rebut évident = règle simple (coût nul) ; rebut subtil non isolable sans risquer une bonne photo. SigLIP = 3878 Mo. |
| Détection auto du flou comme flag | **REJETÉ** (03/08) | Flou rare et risqué à signaler ; au mieux clé de tri, jamais un flag. |
| Cap triage retenu | **ADOPTÉ** (03/08) | Vue groupée par règle + suppression individuelle réversible ; rebut subtil laissé à l'humain. |
| `sqlite-vec` pour la recherche vectorielle | **REJETÉ** | Recherche cosinus numpy sur BLOB suffit ; dépendance évitée (zéro-dépendance). |
| Embeddings stockés en INT8 (au lieu de f16) | **REJETÉ** (11/08) | Gain réel ×2 seulement (base déjà f16, et locale — pas de SMB) : 159→80 Mo ; recall@10 sémantique 0,9685 (« sans perte » réfuté), bascules de seuil 0,0004–0,0062 %, et perte de la garantie « identique au bit près » de `vectors.py`. Mesure : `eval/eval_int8_vectors.py` (130 576 vecteurs réels). |

## Dates de prise de vue

| Idée / piste | Verdict | Raison |
|---|---|---|
| Aplatir DateTimeOriginal / CreateDate / ModifyDate en un seul `min()` | **REJETÉ** (13/08) | `ModifyDate` seul est souvent la date du SCAN d'un vieux tirage : un 1995 numérisé en 2005 partait en 2005 dans toute vue chronologique. Les champs restent séparés (`champs_dates_item`). |
| `ModifyDate` seul cru si son année figure parmi celles du CHEMIN | **ADOPTÉ** (13/08) | Attrape le scan sans rien inventer : en cas de contradiction on rend `None`, la photo garde son repli « année du dossier » (statu quo). Comparé à l'ENSEMBLE des années, jamais au seul `min` — un dossier « Photos 2005-2010\2008\ » faisait sinon reculer la photo de 3 ans (défaut trouvé en relecture). Portée : n'attrape PAS un scanner qui remplit `DateTimeOriginal`. |
| Corriger les photos datées par un nom de fichier de SCAN | **REJETÉ** (14/08) | Mesuré par `/api/jour` sur les 38 254 photos à date précise : 4,0 % contredisent les années du chemin, mais 139 sont des réveillons et 914 à 1 an d'écart (photo de janvier dans le dossier de l'an d'avant) — tous légitimes. Il reste **215 photos à ≥ 4 ans d'écart (0,56 %)**, dont **62 seulement** viennent du nom de fichier ; le gros lot EXIF n'est pas un scan mais une GoPro à l'horloge fausse (`Seychelles 2025\Plongée` → 2016). Aucune règle ne sépare ces 215 des 914 légitimes sans risquer de vraies dates. |
| Plancher 1990 des années lues dans un CHEMIN | **CORRIGÉ → 1900** (14/08) | Le plancher convient à une date d'appareil photo, pas à un nom de dossier : un dossier « 1985 » ne rendait aucune année, donc (a) `_best_time` tombait sur `mtime` — **714 photos de 1982-1989 datées de 2026**, la date de copie NAS — et (b) le garde-fou `date_fiable` se désarme sans année de chemin, laissant 13 photos de 1985 à la date de leur numérisation (16/11/2006). Corrigé dans `server._path_years` et `renommage_facts.path_year`. |
| `_path_years` lisait le NOM DE FICHIER, pas seulement les dossiers | **CORRIGÉ** (14/08) | `119-1908_IMG.JPG` (numéro de séquence de scanner) dans un dossier 2002 rendait `{1908, 2002}` ; `_path_year_num` prend le `min()` → recul de 94 ans. Masqué jusqu'ici par le plancher 1990, il fallait le boucher en le descendant. `renommage_facts.path_year` excluait déjà le nom et documentait pourquoi. Mesuré sur 19 384 fichiers : 38 photos tirées en arrière, **0 qui perd son repli** (une vraie date de nom passe avant, par `_fname_time`). |
| Écrire `None` (« lu, rien trouvé ») pour tout un lot ExifTool | **REJETÉ** (13/08) | Un lot raté (NAS muet, timeout) est indiscernable d'un lot vide : écrire `None` condamne la photo pour toujours (les backfills sautent les entrées qui portent la clé). On n'écrit que pour les fichiers dont ExifTool a parlé (`valeurs_a_ecrire`), et les « muets » sont comptés dans `/reglages`. Vaut aussi pour `namechk` (noms). |

## Méthode (invariants à ne pas réapprendre)

- **Circularité de l'auto-évaluation** : un système qui apprend de ses décisions contamine
  son banc. Vérité terrain = **confirmations humaines** uniquement (`confirmed`), protégées —
  sinon noyées (0,8 % mesuré). Le manque réel est presque toujours la donnée humaine.
- **Comparaison à armes égales** : vérifier ce que chaque modèle *reçoit vraiment* (résolution,
  marge, source) — un banc biaisé a produit un verdict sans fondement (MegaDescriptor 30/07).
- **Un proxy n'est pas le juge final** : les proxies disaient « V2 ≈ V0 », l'humain a tranché
  2 contre 1. Prévoir une notation à l'aveugle.
- **Un bon score moyen n'est pas un feu vert** : la métrique qui compte peut être le coût des
  faux positifs / faux rejets (une bonne photo cachée > un rebut manqué).
- **Fragilité du corpus** : clés corrompues à la saisie (antislashs Windows lus en octal JS) et
  mutation concurrente (rangement déplaçant les fichiers) ont invalidé des runs → `--mesurer`
  alerte si >15 % des clés ne résolvent plus.
- **Ordre imposé (`vision-eval`)** : hypothèse + protocole *avant* de mesurer, puis mesurer,
  décider, et seulement ensuite câbler. Exiger un écart minimal (≥ 5 photos) avant un vainqueur.
- **Mesurer par le chemin de code de la DONNÉE, pas par une vue** (14/08) : après la
  réparation des dates, les dossiers-témoins semblaient inchangés — la vue dossier ne trouvait
  simplement pas les entrées (casse des clés SMB). La même mesure lue par clé d'index montrait
  0 % → 60 %. Une vue peut mentir sur la donnée ; vérifier par le chemin qui l'écrit.
- **Un garde-fou qui n'a rien à quoi se comparer ne garde rien** (14/08) : `date_fiable`
  croit `ModifyDate` quand le chemin ne porte aucune année (« rien à contredire ») — règle
  saine, sauf que le plancher 1990 rendait le chemin muet précisément sur les dossiers
  d'avant 1990, c'est-à-dire sur les photos que le garde-fou existait pour protéger. Le cas
  où une protection s'annule doit être compté, pas seulement écrit.
- **Chercher un défaut en trouve souvent un autre, plus gros** (14/08) : la piste de départ
  (scans datés par leur nom) valait 62 photos ; la mesure faite pour la classer a exhumé les
  714 photos des années 80 datées de 2026. La mesure a rapporté dix fois la correction.
- **Mesurer la matière première avant de bâtir dessus** (13/08) : le chantier « même jour »
  supposait des dates au jour près ; 29 % de la photothèque n'en avait aucune, et la cause était
  un bug de démarrage vieux de plusieurs mois. Une heure de mesure a valu plus que la
  fonctionnalité prévue. **Un travail de fond silencieux est un travail de fond suspect.**

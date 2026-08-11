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
| V2 « assertions en contexte, sans impératif de noms » (~4,3 s) | **PARKÉ / à mesurer** | Jamais notée (écrasée) ; hypothèse : qualité conservée sans surcoût. |

## Triage / stockage / rebut

| Idée / piste | Verdict | Raison |
|---|---|---|
| Détecteur ML de rebut (nom + flou + SigLIP zéro-shot) | **REJETÉ par conception** (03/08) | Rebut évident = règle simple (coût nul) ; rebut subtil non isolable sans risquer une bonne photo. SigLIP = 3878 Mo. |
| Détection auto du flou comme flag | **REJETÉ** (03/08) | Flou rare et risqué à signaler ; au mieux clé de tri, jamais un flag. |
| Cap triage retenu | **ADOPTÉ** (03/08) | Vue groupée par règle + suppression individuelle réversible ; rebut subtil laissé à l'humain. |
| `sqlite-vec` pour la recherche vectorielle | **REJETÉ** | Recherche cosinus numpy sur BLOB suffit ; dépendance évitée (zéro-dépendance). |
| Embeddings stockés en INT8 (au lieu de f16) | **REJETÉ** (11/08) | Gain réel ×2 seulement (base déjà f16, et locale — pas de SMB) : 159→80 Mo ; recall@10 sémantique 0,9685 (« sans perte » réfuté), bascules de seuil 0,0004–0,0062 %, et perte de la garantie « identique au bit près » de `vectors.py`. Mesure : `eval/eval_int8_vectors.py` (130 576 vecteurs réels). |

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

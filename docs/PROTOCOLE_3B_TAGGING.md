# Protocole 3b — le banc qui décide de la re-passe de tagging

> Écrit **avant** toute mesure (skill `vision-eval`, étape 0). Rien de ce
> document ne se réécrit après avoir vu les chiffres : ce qui change, ce sont
> les résultats consignés dans `eval/DECISIONS.md`.
> Contexte et chiffres d'entrée : mesure 3a (`mesure_repasse.txt`).

## Ce qui est en jeu

La re-passe complète vaut **~50 h GPU**. La mesure 3a a montré qu'elle
n'achète **que la description** : les faits (date, noms, lieu, espèce) sont déjà
dans l'index et servent la recherche à zéro GPU. Donc la seule question qui
justifie la dépense est :

> **Une description écrite AVEC les faits en contexte vaut-elle mieux qu'une
> description écrite sans ?** Et si oui, de combien, et sur quelles photos ?

Tout le fondement actuel est un **25-15 sur 40 photos** (12/08). Recompté depuis
les données brutes (`eval/notes_v2sans.json` × `eval/rating_map_v2sans.json`) :
25-15 confirmé, aucun biais de position (A choisi 21 fois sur 40), mais
**p = 0,15** — et les hallucinations relevées vont dans le mauvais sens
(V2 : 6, V0 : 4). On ne paie pas 50 h là-dessus.

## Trois défauts du banc, à corriger AVANT de mesurer

Vérifiés dans `eval/tagging_results.json` (les 150 lignes stockent le bloc
`assert` réellement envoyé au modèle) :

1. **La date asserted était un epoch brut, sur 150 photos / 150.** Le modèle a
   lu « `- Date : 1230807600.0 (EXIF)` ». Cause : `eval_tagging._fmt_date` fait
   `strftime('%-d %B %Y')`, invalide sous Windows → `except` → `str(t)`. Le
   correctif existe déjà en PROD (`tagging_meta.format_date_fr`, écrit pour cette
   raison) mais n'a jamais été porté dans le banc.
2. **Le lieu asserted ne venait pas de `lieux.txt`.** Le banc a tourné le 30/07,
   `lieux.txt` n'existait que depuis le 01/08 : `lieux_connus()` est tombé sur sa
   branche de secours (déduction depuis les dossiers) et a affirmé des lieux
   inventés — « TRIER », « Calinous », « Visite », « Bolivie MicFlo » — sous une
   provenance **fausse**, « (chemin du dossier) ». Recoupement sur les 150
   photos : **118 désaccords** avec le lieu que la production calculerait
   aujourd'hui ; 126/150 portaient un lieu, contre 14 % dans la vraie
   photothèque.
3. **Les prompts du banc ont dérivé de la production.** `eval_tagging.prompt_v2`
   contient encore le bloc IMPÉRATIF que la prod a retiré (v2ctx). Et les sorties
   du « V2 sans impératif » noté le 12/08 n'ont **jamais été écrites dans un
   fichier de résultats** — elles ne vivent que dans `rating_v2sans.html`. Le
   verdict adopté n'est donc pas reproductible.

**Règle qui en découle : le banc n'écrit plus ses propres prompts.** Il importe
`tagging_meta.prompt_tagging` / `faits_structures` et l'assemblage de faits de
`server._assertions_pour`. Un banc qui recopie la prod finit par mesurer autre
chose qu'elle — c'est arrivé trois fois ici.

## Hypothèse (étape 0)

> Les descriptions produites **avec les faits en contexte** (v2ctx, prompt de
> prod) sont préférées à celles produites **sans** (V0, image seule), et ne
> hallucinent pas davantage. Métrique : préférence humaine en aveugle, par paire,
> sur l'échantillon figé.

Hypothèse secondaire, même banc, même échantillon :

> **Un modèle plus gros n'apporte plus rien quand les faits sont donnés.** Si
> c'est vrai, le gain est dans les faits, pas dans le modèle — et la question du
> modèle est close pour de bon (plafond DUR : 4 Go de VRAM partagés).

## Ordre imposé

1. **`gps_place` d'abord (bat 18).** 6 317 photos ont un GPS et aucun lieu :
   mesurer les faits en contexte avant d'avoir les vrais lieux, c'est mesurer une
   photothèque qu'on n'aura plus la semaine suivante. Coût : zéro GPU.
2. **Puis le banc**, sur l'échantillon **figé** `eval/tagging_v1.json`
   (150 photos, quotas riche 50 / pauvre 50 / piège 30 / incertain 20).
   **Ne pas le régénérer** : c'est ce qui rend les mesures comparables entre
   elles. Le lancer **avant** les lots de renommage, qui le rendront caduc.
3. **Puis seulement** la décision sur la passe (ROADMAP 3c).

## Mesure

| | |
|---|---|
| Variantes | **V0** (image seule, prompt historique) · **V2CTX** (prompt de PROD, verbatim de `tagging_meta.prompt_tagging`) · en option **V2CTX-gros** (même prompt, modèle candidat) |
| Photos | les **150** de l'échantillon figé, assertions **recalculées** (dates lisibles, lieux de `lieux.txt` + `gps_place`) |
| Notation | **aveugle, par paire** (A/B mélangés, `generer_rating`), **les 150 paires** — plus le sous-ensemble de 40 |
| Relevés par photo | préférence (A/B), hallucination cochée par variante, secondes/photo, sortie malformée |
| VRAM | pic en inférence par lot (`VramSampler`), en charge réaliste — critère de rejet immédiat s'il empiète sur `FACE_GPU_MIN_FREE_MB` |
| Coût | 2 × 150 appels ≈ **25 min GPU** (3 variantes ≈ 35 min), contre 50 h pour la passe |

## Critère de décision — écrit d'avance

- **v2ctx gagne** si la préférence atteint **≥ 88 sur 150** (p = 0,041 ; 87
  donnerait 0,060 — le seuil exact, pas un chiffre rond) **et** que son taux
  d'hallucination n'est pas supérieur à celui de V0. Alors la re-passe est
  justifiée dans son principe → on choisit la strate (ROADMAP 3c : « nom » =
  19 608 photos, 23,2 h).
- **Entre 76 et 87** : écart réel possible mais non démontré. **La passe ne se
  fait pas.** On peut relancer le banc sur un échantillon élargi si, et seulement
  si, quelqu'un a une raison neuve d'y croire.
- **≤ 75, ou hallucinations en hausse** : la re-passe est **close**, définitivement.
  Le gain était dans les faits, pas dans la description — et les faits sont déjà là.

`python eval_tagging.py --depouiller` applique ce critère et sort la ventilation
par strate. Il reproduit à l'identique le 25-15 / p = 0,15 du 12/08 (vérifié).
- Le résultat est consigné dans `eval/DECISIONS.md` **quel qu'il soit**. Une
  évaluation sans décision écrite ne compte pas.

## Pièges propres à ce banc

- **Noter une photo dont on connaît la variante.** La notation est aveugle et le
  mapping A/B est tiré au sort par photo (`rating_map*.json`). Ne pas le lire
  avant d'avoir fini.
- **Compter une préférence sur une photo « piège »** (document, reçu, capture)
  comme un gain de description : les 30 pièges se dépouillent à part.
- **Oublier que le juge est unique.** 150 jugements d'une seule personne
  mesurent une préférence, pas une vérité. C'est assez pour décider d'une
  dépense GPU ; ça ne dit pas que les descriptions sont « bonnes ».
- **Rejouer une variante sur des assertions stockées** (`row['assert']`) : c'est
  ainsi que les epochs de juillet se sont invités dans la mesure du 12/08.
  Les assertions se recalculent à chaque passe.

## Amendement du 15/08/2026 — l'échantillon avait bougé sous le banc

**Écrit AVANT toute notation, et avant tout résultat.** C'est la seule condition
qui permet d'amender un critère pré-enregistré sans le vider de son sens.

Une première passe a tourné le 15/08 à 09:16 et s'est arrêtée à **85 photos sur
150**. Cause : `eval/tagging_v1.json` fige l'échantillon depuis le 30/07, mais
« Ranger par année » a depuis déplacé les fichiers —
`_A TRIER\250914_Samsung_Mike\20250730_151021.jpg` est devenu
`2025\20250730_151021.jpg`. **65 clés étaient mortes** (63 sous `_A TRIER`), la
boucle les a sautées une par une, et rien n'a dit le total.

Deux dégâts, pas un :

- le critère **≥ 88 sur 150** devenait arithmétiquement hors d'atteinte ;
- les **quotas de strates** que l'échantillon existe pour préserver étaient
  cassés — pièges 12/30, riches 28/50, pauvres 32/50, incertains 13/20.

Cette passe est **abandonnée**. Ses résultats ne sont pas notés.

### Réparation retenue — suivre le renommage, ne PAS régénérer

`recler_echantillon.py` apparie par NOM DE FICHIER et **seulement si le jumeau
est unique** ; deux candidats ne sont jamais départagés (un nom en double dans
deux dossiers mettrait une AUTRE photo dans le banc). Ce sont les mêmes photos,
les mêmes strates, des chemins à jour — le même geste que `rekey_everywhere`.

Bilan : **62 re-clées**, 2 ambiguës (le fichier existe en double), 1 disparue.

### Nouveau critère — pour n = 147

Calculé avec `_binom_p` du banc lui-même, à α < 0,05 bilatéral :

| n | seuil | p au seuil | p juste en dessous |
|---|---|---|---|
| 150 (initial) | 88 | 0,0409 | 87 → 0,0600 |
| **147 (retenu)** | **86** | **0,0474** | 85 → 0,0692 |

- **≥ 86 sur 147** *et* pas plus d'hallucinations que V0 → la re-passe est
  justifiée dans son principe (choix de la strate, ROADMAP 3c).
- **76 à 85** → écart possible, non démontré. **La passe ne se fait pas.**
- **≤ 75, ou hallucinations en hausse** → la re-passe est **close**.

Les 30 pièges se dépouillent toujours à part.

### Garde-fou ajouté

`eval_tagging.py` compte les clés mortes **avant le premier appel Ollama** et
refuse au-delà de **15 %** (même seuil que `--mesurer`), en indiquant le
re-clage. `--forcer` passe outre, en disant que le critère ne s'applique plus.
Un avertissement noyé dans un log de 25 minutes ne protège personne.

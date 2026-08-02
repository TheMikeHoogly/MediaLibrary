# Journal des décisions d'évaluation

Une entrée par évaluation. Sans trace écrite, on reteste six mois plus tard un
réglage déjà écarté — c'est ce qui est arrivé avec `qwen3-vl:4b`, heureusement
documenté dans `modele.txt`.

---

## 2026-07-30 — SigLIP 2 ViT-B/16-256 pour le tagging par vocabulaire contrôlé

**Hypothèse.** Le tagging par VLM génératif (`qwen3-vl:2b`) est lent et non
déterministe — le code contient `_salvage_tags()` et `parse_tags()` pour
rattraper le JSON malformé. Un encodeur zéro-shot contre un vocabulaire
contrôlé devrait être déterministe et permettre d'ajouter un tag sans
réanalyser les photos.

**Jeu de validation.** `eval/echantillon` — 24 photos tirées du corpus réel par
empreinte stable de la clé (même corpus → même échantillon, donc deux modèles
restent comparables). 20 annotées, 4 exclues faute de tag applicable.

**Configuration.** `ViT-B-16-SigLIP2-256` / `webli`, float16 sur CUDA,
gabarit « une photo de {} », vocabulaire de 38 tags, images réduites à 512 px.

**Résultat.** Justesse au rang 1 : **90 %** (18/20). Rappel dans le top 3 :
**100 %** (20/20).

Désaccords : une libellule lue comme `oiseau` (le vocabulaire n'avait pas
`insecte`), un troupeau de lamas lu comme `photo de groupe` (vraie erreur).

**Décision : ADOPTÉ.** Vocabulaire complété de `insecte`, `animal sauvage`,
`objet`, `affiche`, `oeuvre d art`, `photo ratee`, `cheval`, `velo`.

**Reste à faire.** Évaluer `qwen3-vl:2b` sur le même échantillon : cette mesure
porte sur SigLIP seul, pas sur l'écart avec le tagging en place.

---

## 2026-07-30 — Vérification d'espèce des détections d'animaux

**Hypothèse.** YOLO11 classe selon COCO, qui n'a ni singe, ni renard, ni lama,
ni peluche. Tout mammifère poilu tombe donc dans `cat` ou `dog`, d'où des
groupes de macaques présentés comme « 9 apparitions de ce chat ».

**Protocole.** 766 découpes en cache relues par SigLIP 2 contre un vocabulaire
ouvert de 22 libellés. Suspect si le désaccord est net (score ≥ 0,05,
marge ≥ 0,010). 24 découpes suspectes exportées et relues une à une.

**Résultat.** 723 chats confirmés, 25 désaccords. **23 rejets sur 24 justifiés**
(macaques, figurines, peluche, paon, statues) — un seul faux rejet : un chat
crème roulé en boule, lu comme un lapin.

**Décision : ADOPTÉ.** Précision 96 %, coût d'erreur faible (1 détection sur
723 correctes). Garde-fou ajouté : un jugement humain (`par_humain`) n'est
jamais réévalué, et nommer une détection lève un `suspect`.

---

## 2026-07-30 — Prototypes multiples et contre-exemples (personnes et animaux)

**Hypothèse.** Une personne photographiée sur vingt ans n'est pas un point dans
l'espace des empreintes. Un centroïde unique tombe entre les modes et se
rapproche mécaniquement des fiches voisines — d'où le blocage mesuré entre
Florine et Flo (écart de 0,03 sur les mêmes visages). Deux corrections
envisagées : plusieurs prototypes par sujet, et l'usage des exclusions comme
contre-exemples.

**Protocole.** Vérité terrain = photos portant exactement un tag `personne:` et
contenant exactement un visage. **Les références de chaque fiche sont retirées
du jeu de test** — sinon on évalue le modèle sur ses propres exemples.
389 visages de test, 318 fiches. Même protocole côté animaux : 561 détections,
7 fiches.

**Résultats.**

| Variante | top-1 personnes | précision auto |
|---|---|---|
| centroïde unique (état antérieur) | 96,7 % | 98,1 % |
| + contre-exemples | 95,4 % | 98,1 % |
| **prototypes multiples (k ≤ 4)** | **97,4 %** | **98,4 %** |
| prototypes + contre-exemples | 95,9 % | 98,3 % |

Balayage de k : 1 → 96,7 %, 3 → 96,9 %, **4 → 97,4 %**, 6 → 96,7 %.
Au-delà de 4, la fragmentation dégrade.

Animaux, même essai : k=1 → **99,8 %**, k=2 → 99,6 %, k=3 → 99,3 %, k=4 → 99,6 %.

**Décisions.**

1. **Prototypes multiples ADOPTÉS pour les personnes.** Discordance : 3 cas
   corrigés, **0 cassé**. Sur les 16 visages que le centroïde ne savait pas
   trancher, 11/16 corrects deviennent 13/16. Le gain n'est **pas
   statistiquement significatif** (test binomial exact, p ≈ 0,25 sur 3 paires
   discordantes) — il est adopté parce qu'il n'a rien dégradé, pas parce qu'il
   est prouvé. À réévaluer sur un jeu plus large.

2. **Prototypes REJETÉS pour les animaux.** Mesure défavorable (99,8 → 99,6 %).
   Des chats photographiés sur quelques années n'ont pas les facettes multiples
   d'un humain sur vingt ans. Ils gardent le centroïde unique.

3. **Contre-exemples REJETÉS.** Dégradent à toutes les marges testées
   (0,20 à −0,10). L'idée était séduisante — une exclusion humaine porte
   l'information la plus fiable du corpus — mais la règle « disqualifier si un
   négatif est plus proche » élimine surtout les bons candidats. Une
   formulation plus fine (pondération plutôt que disqualification) reste
   possible ; en l'état, c'est non.

**Limites à connaître.**

- Une partie des tags de la vérité terrain a été posée par l'auto-attribution
  du système lui-même : la mesure porte autant sur la cohérence avec les
  décisions passées que sur la justesse absolue.
- 389 visages, c'est peu. Suffisant pour écarter une idée nuisible, insuffisant
  pour prouver un gain de moins d'un point.

---

## 2026-07-31 — MegaDescriptor contre DINOv2 (re-identification animale)

**Hypothèse.** L'audit initial recommandait MegaDescriptor, modèle de fondation
dédié à la re-identification animale, décrit dans la littérature comme
surpassant nettement DINOv2 et CLIP sur cette tâche. Le pipeline utilise
`vit_base_patch14_dinov2`, un encodeur généraliste.

**Protocole.** Re-identification galerie/requête. Pour chaque animal nommé, ses
détections sont coupées en deux par empreinte stable de la clé — aucun
chevauchement, donc aucune fuite. 3 animaux, 531 découpes locales
(Caline 359, Luna 87, Inti 85), galerie 264 / requêtes 267.

**Résultat.**

| Modèle | rang-1 | mAP | erreurs |
|---|---|---|---|
| **DINOv2 `vit_base_patch14` (en place)** | **97,4 %** | **85,5 %** | 7 |
| MegaDescriptor-L-224 | 93,3 % | 72,9 % | 17 |
| MegaDescriptor-T-224 | 89,9 % | 67,2 % | 23 |

> **⚠ CETTE MESURE EST INVALIDE — voir l'entrée du 31/07 ci-dessous.**
> La comparaison était inéquitable : DINOv2 utilisait ses empreintes de
> production (découpe pleine résolution, sans marge) tandis que MegaDescriptor
> recevait les vignettes d'affichage de 256 px avec 15 % de marge. Le verdict
> ci-dessous repose donc en partie sur un handicap imposé.

**Décision : REJETÉ. La recommandation de l'audit est réfutée par la mesure.**

**Interprétation.** MegaDescriptor est entraîné sur des jeux de faune sauvage —
individus à motifs distinctifs (léopards, baleines, tortues), photographiés
dans des conditions homogènes. Des chats domestiques d'intérieur, en poses et
éclairages très variables, sont hors de sa distribution. DINOv2, entraîné en
auto-supervision sur un corpus généraliste immense, transfère mieux à ce cas.

Ce n'est pas un défaut de MegaDescriptor : c'est un rappel qu'un modèle
« état de l'art sur sa tâche » ne l'est pas sur *une autre* tâche qui lui
ressemble.

**Ce que la matrice de confusion apprend, et qui compte plus que la moyenne.**

- DINOv2 : `Inti→Luna ×4`, `Luna→Inti ×2`, `Caline→Inti ×1`.
  **Six erreurs sur sept portent sur la paire Inti/Luna.**
- MegaDescriptor : erreurs dispersées sur toutes les paires, y compris
  `Caline↔Luna` que DINOv2 ne confond jamais.

Le vrai problème restant n'est donc pas le modèle, c'est **une seule paire
d'animaux**. Une moyenne globale ne l'aurait pas montré.

**Limites de cette mesure.**

- 606 détections sans vignette en cache ont été ignorées.
- Les découpes font 256 px de côté maximum (plafond posé par `crop.thumbnail`
  dans `server.py`). Les trois modèles reçoivent donc une image déjà réduite :
  aucun ne dispose du détail fin qui distinguerait deux chats proches.
- 3 animaux seulement, dont un qui représente 68 % du corpus.

**Piste suivante, ciblée.** Augmenter la résolution des découpes plutôt que
changer de modèle, et mesurer sur la seule paire Inti/Luna. `MegaDescriptor-
DINOv2-518` mérite aussi un essai : c'est un DINOv2 affiné pour la re-ID
animale à 518 px, qui combinerait peut-être les deux forces.

---

## 2026-07-31 — Le banc de classification était devenu circulaire

**Ce qui s'est passé.** Rejoué à l'échelle réelle (47 349 visages contre 7 531
lors de la première mesure), le banc a rendu **100 % de justesse** pour toutes
les variantes, avec 100 % de précision sur l'automatique.

Un score parfait n'est pas un bon résultat, c'est un signal d'alarme.

**Diagnostic.** La vérité terrain était « les photos portant un tag
`personne:` ». Or l'auto-attribution du système a posé la quasi-totalité de ces
tags entre-temps. Mesuré : **91 photos confirmées par un humain sur 12 072
taguées, soit 0,8 %.** Le banc demandait donc au modèle s'il était d'accord
avec lui-même.

C'est la limite que la première entrée signalait déjà — « la mesure porte
autant sur la cohérence que sur la justesse » — mais elle était alors
marginale. Elle est devenue totale.

**Correction.** Le jeu de test se restreint désormais aux photos **confirmées
par un humain** (`confirmed`). `--tous` permet de revenir à l'ancien
comportement, avec un avertissement explicite.

**Ce que donne la mesure honnête** (23 visages seulement) :

| Variante | top-1 |
|---|---|
| centroïde unique | 95,7 % |
| prototypes multiples | 91,3 % |
| + contre-exemples | 8,7 % |

**Conséquences.**

1. **Les contre-exemples sont confirmés nuisibles**, cette fois massivement
   (8,7 %). La règle « disqualifier si un négatif est plus proche » élimine
   presque tous les bons candidats quand les exclusions sont nombreuses
   (456 sur ce corpus). Décision maintenue : rejetés.
2. **Les prototypes multiples n'ont plus de justification mesurée.** Ils
   passent derrière le centroïde sur ce jeu. Mais 23 visages ne permettent
   pas de trancher : un écart d'une photo vaut 4,3 points. **Ils restent en
   place faute de preuve dans un sens comme dans l'autre** — à réévaluer.
3. **Le vrai manque est la donnée humaine.** 0,8 % de confirmations, c'est
   trop peu pour piloter quoi que ce soit. Confirmer une centaine de
   propositions dans l'interface vaudrait plus que n'importe quel changement
   d'algorithme.

**Leçon de méthode.** Un système qui apprend de ses propres décisions
contamine sa propre évaluation. Il faut préserver une source de vérité
indépendante — ici, les confirmations humaines — et la protéger explicitement,
sans quoi elle est noyée par le volume automatique.

---

## 2026-07-31 — La comparaison MegaDescriptor était inéquitable

**Comment c'est apparu.** En préparant le test de résolution, vérification de
ce que `server.py` donne réellement au modèle. `embed_cats_one_batch()` fait
`im.crop(box)` sur l'image **d'origine, en pleine résolution, sans marge**, puis
laisse le transform du modèle redimensionner.

Or le banc du 30/07 comparait :

| | entrée reçue |
|---|---|
| DINOv2 | empreintes de production → découpe pleine résolution, sans marge |
| MegaDescriptor | vignettes `animal_thumbs` → **256 px, avec 15 % de marge** |

**Deux biais cumulés, tous deux en défaveur de MegaDescriptor** : une image
huit à dix fois moins définie, et un cadrage différent. L'écart mesuré
(97,4 % contre 93,3 %) ne peut donc pas être attribué au modèle.

**Ce que ça invalide.** La conclusion « MegaDescriptor est rejeté » n'est pas
établie. Elle n'est pas non plus infirmée — elle est **sans fondement** tant
que la mesure n'est pas refaite à armes égales.

**Ce que ça invalide aussi : ma propre hypothèse suivante.** J'avais conclu que
« les découpes plafonnées à 256 px brident les trois modèles ». C'est faux pour
DINOv2 en production, qui n'a jamais vu ces vignettes. Le plafond de 256 px ne
concerne que l'affichage.

**Correction apportée.** `eval_animaux.py --equitable` refabrique des découpes
identiques pour tous les modèles, avec la géométrie du calcul d'empreinte
(aucune marge) et en pleine résolution. `--resolutions` teste ensuite l'effet
de la taille, tous modèles inclus.

**Leçon de méthode.** Comparer deux modèles suppose de vérifier ce que chacun
reçoit vraiment, pas ce qu'on croit lui donner. Ici, l'un lisait une base de
données et l'autre un dossier de vignettes : rien dans le code ne le signalait.

---

## 2026-07-31 — Comparaison refaite à armes égales : DINOv2 confirmé

**Protocole corrigé.** Toutes les découpes refabriquées depuis les originaux,
même géométrie que `embed_cats_one_batch()` (aucune marge), même résolution
pour tous les modèles. 531 découpes, galerie 264 / requêtes 267.

**Validation du banc.** DINOv2 réencodé en pleine résolution donne
97,4 % / 85,6 %, contre 97,4 % / 85,5 % pour les empreintes de production.
Le banc reproduit donc fidèlement la production — sans cette vérification,
aucun des chiffres suivants ne vaudrait rien.

**Résultat, tous modèles sur les mêmes entrées.**

| Modèle | rang-1 | mAP | (biaisé, 30/07) |
|---|---|---|---|
| **DINOv2** | **97,4 %** | **85,6 %** | 97,4 % |
| MegaDescriptor-L-224 | 94,0 % | 72,9 % | 93,3 % |
| MegaDescriptor-T-224 | 92,1 % | 68,9 % | 89,9 % |

MegaDescriptor gagne bien 0,7 à 2,2 points avec des entrées correctes — le
biais était réel — mais **l'écart de 3,4 points en faveur de DINOv2 subsiste**.

**Décision : MegaDescriptor REJETÉ**, cette fois sur une mesure valide.

**Effet de la résolution : AUCUN.**

| Résolution | rang-1 | mAP |
|---|---|---|
| 256 px | 97,8 % | 84,6 % |
| pleine résolution | 97,4 % | 85,6 % |
| 512 px | 97,0 % | 85,1 % |

Deux photos d'écart sur 267 : du bruit. **L'hypothèse « les découpes de 256 px
brident la reconnaissance » est réfutée.** Le plafond de 256 px ne concerne que
l'affichage, et il n'y a rien à changer.

**Ce qui reste, et qui ne bouge à aucune configuration.** La confusion
Inti ↔ Luna : 3 à 4 erreurs dans chaque essai, sur 7 au total. Deux chats qui
se ressemblent réellement. Aucun modèle ni aucune résolution testés ne la
réduisent.

**Conclusion pratique : arrêter d'optimiser ce pipeline.** 97,4 % de rang-1
avec sept erreurs concentrées sur une paire est un bon point d'arrêt. Comme
pour les visages, le gain restant est dans la **donnée** — plus de références
confirmées pour Inti et Luna — pas dans l'algorithme.

**Bug corrigé dans le banc.** Il annonçait « 256 px gagne +0,4 point », soit
une seule photo sur 267. Il exige désormais un écart d'au moins cinq photos
avant de désigner un vainqueur, et dit explicitement « trop peu pour conclure »
en dessous.

---

## 2026-07-31 — Assertions vs pixels pour le tagging (V0 / V1 / V2)

**Hypothèse.** L'audit externe (`docs/AUDIT_EXTERNE_2026.md`) proposait de cesser
de donner les pixels au LLM et de lui fournir les *assertions* des modèles
spécialisés (noms, espèce, lieu, date, tags), en pariant que cela réduit les
hallucinations, améliore la cohérence, sans appauvrir la description. Banc :
`eval_tagging.py`, protocole `eval/PLAN_assertions_vs_pixels.md`.

**Jeu.** `eval/tagging_v1.json` — 150 photos figées par empreinte de clé,
réparties 50 riches / 50 pauvres / 30 pièges / 20 incertaines. Modèle figé
`qwen3-vl:2b`. Le banc ne fait que lire la base.

**Variantes.** V0 = image seule + prompt en place (référence). V1 = assertions
seules, sans image. V2 = hybride (assertions + image). V2 a été mesurée en deux
versions du prompt : sans exigence de noms, puis **avec** un impératif « emploie
les noms assertés ».

**Résultats (proxies automatiques ; 1 photo `V2_stale` exclue de V2, fichier
disparu entre deux passes).**

| Mesure | V0 | V1 | V2 (sans exig.) | V2 (avec exig.) |
|---|---|---|---|---|
| Secondes / photo | 5,4 | 3,9 | 4,3 | **11,1** |
| VRAM pic (Mo) | — | — | 2 959 | **3 950** (plafond 4 096) |
| JSON malformé | 0 % | 0 % | 0,7 % | 0,7 % |
| Ancrage des noms* | 4 % | 21 % | 3 % | **16 %** |
| Desc. moyenne (car.) | 100 | 90 | 119 | 137 |
| Descriptions « méta »** | 2/150 | **50/150** | 5/150 | 2/149 |

\* part des photos avec un nom asserté où ce nom apparaît dans la sortie.
\** description qui parle de la *liste de faits* au lieu de la scène.

**Ce que la mesure établit.**

1. **L'argument « fiabilité » de l'hypothèse tombe.** `qwen3-vl:2b` produit déjà
   du JSON propre (0 % de malformé). Les assertions ne réparent pas un problème
   qui n'existait quasiment pas.
2. **V1 (jeter les pixels, LLM texte) est disqualifié.** Privé d'image, il décrit
   la liste de faits — *« Un document avec une image de Luna, chat, herbe… »* —
   dans **33 %** des cas.
3. **Injecter les noms dans le prompt de tagging ne marche pas.** Même en
   IMPOSANT le nom, le modèle l'ignore 84 % du temps quand il voit l'image :
   « Mike, reconnaissance faciale » → « un homme ». L'ancrage monte de 3 % à
   16 %, sans plus — et V1 (sans image) reste devant à 21 %, ce qui confirme que
   ce sont les **pixels** qui tirent le modèle vers le générique.
4. **Le coût est prohibitif.** Le prompt impératif fait passer V2 de 4,3 à
   11,1 s/photo et pousse la VRAM à 3 950 Mo, au ras des 4 096 — le débordement
   que l'invariant n°4 signale (vitesse ÷ ~2). Le ralentissement ne vient pas
   d'une sortie plus longue (365 vs 335 car.) mais du prompt lui-même.
5. **Circularité bornée.** Recouvrement sortie ↔ tags fournis : 0,29 pour V0 (qui
   ne les voit pas) contre 0,41 pour V1/V2 — +0,11, pas de la régurgitation.
6. **Cohérence non mesurable sur ce jeu.** 8 groupes (dossier, jour) seulement
   ont ≥ 2 photos (39 paires) : l'échantillonnage dispersé défait la métrique.
   `0,0` partout est du bruit — le proxy de cohérence est à retirer ou à mesurer
   sur un sous-échantillon de rafales dédié.

**Décision.**

- **V1 (assertions seules) : REJETÉ.** Descriptions « méta » dans un tiers des
  cas. La piste « LLM texte, pixels jetés » de l'audit n'est pas tenable telle
  quelle sur ce modèle.
- **Injecter les noms dans le prompt de tagging : REJETÉ.** Inefficace (16 %) et
  coûteux (× 2,6, VRAM au plafond). Le LLM décrit ce qu'il voit, pas l'identité
  qu'on lui affirme.
- **Direction retenue : ne pas quémander au LLM des faits qu'il possède déjà
  ailleurs.** Les noms sont des faits structurés (`personne:` / `animal:`), la
  date et le lieu aussi. Le bon niveau pour les faire figurer dans la sortie
  n'est pas le prompt mais une **fusion programmatique** (Knowledge Builder) :
  le LLM garde son rôle sur les pixels (V0 inchangé, le moins cher), et la couche
  d'assertions attache ce qu'elle sait — nom en préfixe de description, tags
  d'identité — en post-traitement déterministe. Cela débloque aussi la provenance
  visée par l'audit sans faire porter au LLM une tâche qu'il exécute mal.

**Mise à jour — notation à l'aveugle (40 cartes, `notes.json`).** J'avais écrit
que la notation « ne rouvrirait pas le verdict ». **C'était faux, et il faut le
corriger.** Résultats, désanonymisés via `rating_map.json` :

| | V0 | V1 | V2 |
|---|---|---|---|
| Meilleure description (vote) | 12/40 (30 %) | 4/40 (10 %) | **24/40 (60 %)** |
| Cartes taxées d'hallucination | 2 (5 %) | 6 (15 %) | 3 (8 %) |

V2 gagne dans les **trois catégories** (riche 11-7, piège 7-3, incertain 6-2).
**L'humain préfère nettement la description hybride** (assertions + image) à
l'image seule, pour une hallucination à peine plus haute. Autrement dit : les
assertions **améliorent la qualité de description** — la partie de l'hypothèse de
l'audit qui portait sur la richesse/justesse est **validée**. Ce que la mesure
automatique seule (« V2 ≈ V0 en richesse ») avait manqué.

**Décision révisée.**

- **V1 : REJETÉ** (confirmé : 10 % de préférence, 15 % d'hallucination, 33 % de
  descriptions « méta »).
- **Hybride assertions + image : ADOPTÉ sur le principe.** L'apport des
  assertions à la description est réel et confirmé par l'humain, surtout sur les
  photos riches en faits.
- **L'impératif de noms reste REJETÉ** : c'est lui qui coûte × 2,6 et pousse la
  VRAM au plafond, pour un ancrage de seulement 16 %. Le gain de qualité vient
  des **assertions comme contexte**, pas de l'ordre d'employer les noms — les
  deux versions de V2 partageaient les assertions, seule la coûteuse a été notée.
- **Les noms restent attachés par fusion programmatique**, pas quémandés au LLM
  (16 % d'obéissance). Le LLM reçoit les faits *en contexte* pour écrire une
  meilleure description ; la couche d'assertions garantit le nom exact.

**Prochain pas ciblé (à mesurer, ne rien bâtir avant) :** re-noter/mesurer un V2
« assertions en contexte, **sans** impératif de noms » (la version à 4,3 s /
2 959 Mo, jamais notée car écrasée). Hypothèse : il garde l'avantage de qualité
sans le surcoût. Si confirmé, c'est le nouveau prompt de production, doublé de la
fusion programmatique des noms/date/lieu.

**Leçon de méthode.** Double. (1) Prolonge MegaDescriptor : on a demandé le nom
explicitement, le modèle a refusé — le bon niveau pour injecter un fait connu
n'est pas le prompt, c'est la fusion après coup. (2) **Un proxy automatique n'est
pas le juge final** : les proxies disaient « V2 ≈ V0 », l'œil humain dit « V2
gagne 2 contre 1 ». Sans la notation, on aurait figé la mauvaise conclusion.

---

## 2026-08-02 — Détecteurs de rebut pour le triage (point 21) — PROTOCOLE PRÉ-ENREGISTRÉ

**Statut : banc écrit et testé (logique pure), DÉCISION EN ATTENTE du run sur la
machine réelle.** Entrée posée *avant* la mesure, comme l'exige `vision-eval`
(étape 0 : formuler l'hypothèse avant de mesurer). À compléter après le run.

**Hypothèse (le défaut observé et la métrique qui le prouverait).** Une part
notable des 12 501 fichiers sous `_A TRIER` sont des rebuts (documents scannés,
captures d'écran, factures/reçus, photos floues ou ratées). Hypothèse : trois
signaux **gratuits** — heuristique de nom, variance du Laplacien (flou), zéro-shot
SigLIP sur des libellés rebut — suffisent à les **proposer** au triage sans
nouveau modèle lourd. La métrique qui tranche n'est pas la justesse moyenne mais
le **coût des faux positifs** : combien de **bonnes photos** seraient signalées à
tort (une bonne photo cachée coûte plus qu'un rebut manqué).

**Jeu de validation (figé, corpus réel).** `eval/interet_v1.json` — ~200 photos
tirées de `_A TRIER` par empreinte de clé (sha1, même corpus → même échantillon),
étiquetées **à la main** par Mike via `eval/interet_etiquetage.html` en
`garder | document | capture | facture | flou | errone`
(→ `eval/interet_labels.json`). Le banc ne lit que l'index et les fichiers ;
il n'écrit aucun tag, ne supprime rien.

**Ce qui est comparé.** Trois signaux, mesurés séparément puis combinés :
1. **Nom** (`interet.indice_nom`) — `Screenshot_`, `-WA####`, `VideoCapture_`,
   `Scan_`, `facture/recu`… détecteur binaire, coût nul.
2. **Flou** (`interet.score_flou`, variance du Laplacien, CPU) — balayage de seuil,
   sens « rebut si variance < seuil ».
3. **SigLIP zéro-shot** — libellés rebut (`interet.LIBELLES_SIGLIP`, réutilise
   l'encodeur de `semantic.py`, **sans toucher** `vocabulaire_tags.txt`), score
   max par catégorie, balayage de seuil.

**Métriques (par signal et par seuil, `eval/interet_results.json`).** Précision /
rappel / F1 ; **`fp_bonnes`** = bonnes photos signalées à tort à chaque seuil ;
seuil retenu = meilleur F1 **sous une borne de faux positifs** (`meilleur_seuil(…,
fp_max=n/50)`) — si aucun seuil ne tient la borne, le signal est **à ne pas activer
seul**. Pic **VRAM** mesuré pendant l'encodage SigLIP (rejet si trop proche des
seuils du pipeline en place : `FACE_GPU_MIN_FREE_MB = 1200` exigé côté visages).
Temps par image + extrapolation à `_A TRIER`.

**Garde-fous de méthode déjà en place.** Logique pure isolée dans `interet.py`,
**`test_interet.py` 15/15** dans le bac à sable (nom, flou synthétique, assemblage,
métriques, balayage). Le classifieur ne fait que **proposer** ; la suppression
reste le geste humain, réversible (`FileOps.delete` → `.corbeille-rangement/`).

**Décision : à écrire après le run** (adopté / rejeté / à revoir, par signal et
seuil). Ne rien câbler dans le serveur ni bâtir la vue de triage avant cette
entrée — c'est l'ordre imposé par `vision-eval` (mesurer, décider, puis bâtir).

**Lancer la mesure (machine réelle, NAS monté) :**

```
python eval_interet.py --echantillon 200   # tire l'échantillon + page d'étiquetage
#   ... étiqueter dans eval/interet_etiquetage.html, déposer interet_labels.json ...
python eval_interet.py --mesurer           # SigLIP + flou + nom, métriques + VRAM
```

---

## Annexe — bugs trouvés par les bancs d'essai eux-mêmes

**2026-07-30, banc de classification :**

- `prototypes(vecteurs, max_proto=MAX_PROTOTYPES)` évaluait sa valeur par défaut
  à la définition : le balayage de k mesurait quatre fois la même chose.
- En posant `p["c"] = P[0]`, le chemin « faux positif » notait avec une facette
  arbitraire au lieu du centroïde et produisait **131 fausses alertes**. Corrigé
  en scorant l'ajout et le retrait de la même façon (maximum sur les facettes).

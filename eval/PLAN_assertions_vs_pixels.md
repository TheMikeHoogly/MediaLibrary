# Protocole d'éval — assertions vs pixels pour le tagging

Suite à l'audit externe (voir `docs/AUDIT_EXTERNE_2026.md`) et à la décision
« mesurer d'abord ». Rédigé selon la skill `vision-eval`. **Aucune ligne de
harness ne s'écrit avant que ce protocole soit figé.**

Dernière mise à jour : 31 juillet 2026.

## Étape 0 — Hypothèse

Le tagging actuel envoie au LLM **les pixels seuls** (`PROMPT`, `qwen3-vl:2b`,
image 896 px). Le LLM est le composant le plus lent, le moins déterministe et
celui qui hallucine le plus ; le code porte déjà `_salvage_tags()` et
`parse_tags()` pour rattraper son JSON cassé.

**Hypothèse.** Fournir au LLM les *assertions* déjà produites par les modèles
spécialisés (noms de personnes/animaux confirmés, espèce, lieu déduit du chemin,
date, tags SigLIP) et lui demander de les **mettre en langage** :

1. réduit les hallucinations (il n'invente plus « un chat gris » quand DINOv2 a
   dit « Luna ») ;
2. améliore la cohérence inter-photos d'une même scène ;
3. ne dégrade **pas** la richesse de description au point de rater la longue
   traîne visuelle qu'aucun autre modèle n'a été chargé de voir.

Le point 3 est le risque réel : SigLIP/YOLO donnent des catégories, pas
« un cerf-volant au loin ». C'est ce que le banc doit trancher.

## Étape 1 — Jeu de validation figé

150 photos tirées du corpus réel par **empreinte stable de la clé** (même
corpus → même échantillon, deux variantes restent comparables). Versionné dans
`eval/tagging_v1.json`.

Répartition visée, pour ne pas mesurer que le cas favorable :

- ~50 photos **riches en assertions** (au moins un `personne:`/`animal:`
  confirmé, ou un lieu connu) — là où l'hybride devrait briller ;
- ~50 photos **pauvres en assertions** (paysage, repas, objet, sans nom) — là
  où l'image seule garde peut-être l'avantage ;
- ~30 photos **pièges** : documents/reçus/écrans (le prompt actuel a une règle
  anti-transcription), scènes nocturnes, groupes ;
- ~20 photos où l'auto-attribution est **incertaine** (visages faibles), pour
  voir si l'hybride propage une fausse assertion.

## Étape 2 — Variantes comparées

Toutes produisent le **même schéma JSON** (`keywords_en`, `keywords_fr`,
`description_fr`), pour rester comparables et compatibles avec `parse_tags()`.

| Variante | Entrée du LLM | Modèle |
|---|---|---|
| **V0 (référence)** | image seule + `PROMPT` actuel | `qwen3-vl:2b` |
| **V1 assertions seules** | assertions en texte, **sans image** | `qwen3-vl:2b` |
| **V2 hybride** | assertions **+ image**, prompt guidé | `qwen3-vl:2b` |
| V0′, V2′ (option modèle) | idem V0 et V2 | `qwen2.5-vl:3b` |

Le « Knowledge Builder v0 » du banc assemble les assertions **depuis la base**
(pas de nouveau calcul GPU) : `kw_fr`/`kw_en` existants, tags `personne:` et
`animal:` de l'index, espèce depuis `ANIMAL_STORE`, lieu via
`_folder_link_for_key`/`lieux_connus`, date via `_best_time`. Chaque assertion
porte sa **source** et, si disponible, sa confiance — c'est le germe de la
couche à provenance discutée dans l'audit.

## Étape 3 — Métriques (vs pipeline en place = V0)

- **Justesse / hallucination** : la description mentionne-t-elle un élément
  *contredit* par les assertions (mauvais nom, mauvaise espèce) ou absent de la
  photo ? Jugé à l'aveugle (voir plus bas).
- **Cohérence** : deux photos d'une même scène/rafale reçoivent-elles des tags
  proches ? (regroupement par dossier + date rapprochée).
- **Richesse** : nb de tags corrects et spécifiques ; la description capte-t-elle
  un détail hors assertions ?
- **Taux de JSON malformé** : nb de rattrapages `_salvage_tags()` par variante
  (un signal de fiabilité ; doit chuter en V1).
- **Secondes / photo**, extrapolées à 30 000 photos.

## Étape 4 — VRAM et migration

- Pic de VRAM **en inférence par lot**, `qwen3-vl:2b` vs `qwen2.5-vl:3b`,
  **pendant qu'Ollama est résident** (`keep_alive: 30m`), via `Moniteur GPU.bat`
  / `nvidia-smi`. Rejet immédiat si débordement RAM système (le sinistre
  `qwen3-vl:4b`).
- Écrire les tags reste piloté par une **version de pipeline** de tagging (à
  créer, sur le modèle d'`ANIMAL_PIPELINE_VERSION`) : changer de modèle ou de
  variante = bump = recalcul maîtrisé, jamais d'index mixte silencieux.
- **Aucun nom humain n'est touché** : le banc lit, il n'écrit pas de XMP.

## Étape 5 — Décision écrite

Une entrée dans `eval/DECISIONS.md` : hypothèse, jeu, VRAM, métriques par
variante, coût, décision (adopté/rejeté/à revoir), raison. Si le résultat change
l'architecture (le LLM cesse de voir les pixels), produire un ADR avec
`engineering:architecture`.

## Pièges spécifiques à ce banc

- **Circularité.** Les assertions viennent en partie de l'auto-attribution. Un
  banc qui juge la description « juste » parce qu'elle répète l'assertion
  mesure la cohérence, pas la vérité. → le jugement d'hallucination se fait
  **contre la photo**, pas contre les assertions.
- **Score parfait = alarme.** Déjà vu deux fois sur ce projet.
- **Ne pas confondre variante et modèle** : figer le modèle en comparant V0/V1/V2,
  figer la variante en comparant 2b/3b.

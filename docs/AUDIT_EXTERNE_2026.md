# Audit externe 2026 — vers une base de connaissances

Revue externe reçue le 31 juillet 2026, et évaluation interne. Ce document fige
la réflexion pour ne pas la reperdre ; il n'engage aucun code tant qu'une
mesure n'a pas tranché (voir `eval/PLAN_assertions_vs_pixels.md`).

## Ce que propose l'audit

Le projet n'est plus une photothèque mais un **système de compréhension
multimodale** : SigLIP (contenu), InsightFace (personnes), DINOv2 (individus
animaux), YOLO (espèces), chemins NAS (lieu), XMP (savoir validé). Le LLM ne
serait qu'un composant parmi d'autres — et le plus lent, le plus coûteux, le
moins déterministe, celui qui hallucine le plus.

Recommandation centrale : **cesser de donner les pixels au LLM**. Lui fournir
plutôt ce que les autres modèles ont compris, et lui demander de le mettre en
langage. Il passe de *moteur de vision* à *moteur de raisonnement*.

Chantiers proposés, par impact décroissant : (1) **Scene Graph** — représentation
unique de la connaissance d'une photo ; (2) **Knowledge Builder** — couche
d'arbitrage qui fusionne les assertions des modèles (fiabilité, priorité,
rejet) ; (3) **Prompt Builder** — génère le prompt depuis le graphe ; (4) **cache
de raisonnement** — une photo déjà décrite ne repasse jamais au LLM ; (5)
**versionnement de la connaissance** — une correction humaine (Luna→Inti)
devient une version tracée ; (6) **mémoire globale** — une base interrogeable
(« quand Luna est-elle apparue ? »). Le modèle (Qwen2.5-VL-3B) n'est plus jugé
limitant ; à ne changer qu'après mesure rigoureuse.

## Évaluation interne

**Direction juste : orchestration > modèle.** Sur une RTX 3050 4 Go partagée
avec Ollama, réduire le rôle du LLM est cohérent avec toutes les décisions du
projet.

**Le Knowledge Builder existe déjà, en germe et validé.** La « vérification
d'espèce » (SigLIP arbitrant le `cat`/`dog` de YOLO), ADOPTÉE le 30/07 à 96 %
de précision, *est* une couche d'arbitrage entre deux experts. L'audit
généralise une chose déjà mesurée et retenue — bon signe.

**Deux chantiers s'emboîtent avec les invariants.** Le cache de raisonnement
est le pendant de « les versions de pipeline gouvernent les recalculs ». Le
versionnement à **provenance** (assertion = valeur + confiance + source +
confirmé\_humain) sert directement la priorité n°1 du ROADMAP : protéger la
vérité humaine (0,8 % de confirmations) de la noyade par l'auto-attribution —
la cause exacte de la circularité qui a faussé le banc deux fois.

**Nuances, dans l'esprit « décider avec des chiffres ».**

- *Assertions-only est un pari, pas une évidence.* SigLIP/YOLO donnent des
  catégories, pas la longue traîne visuelle qu'un VLM attrape. Nourrir le LLM
  d'assertions seules risque des descriptions plus plates. → à mesurer :
  assertions seules vs assertions+image vs image seule. Pari interne : l'hybride
  gagne (les faits *guident* le VLM au lieu de le remplacer).
- *Un Scene Graph bâti sur des tags auto-attribués ré-importe la circularité.*
  Le graphe doit porter la provenance dès le premier jour.
- *Modèle :* Qwen2.5-VL-3B sur 4 Go partagés avec le `keep_alive 30m` d'Ollama
  sera juste — mesurer le pic VRAM (qwen3-vl:4b déjà rejeté pour débordement).
  Et si le LLM devient texte-only, un petit **LLM texte** suffirait, libérant la
  VRAM pour SigLIP/InsightFace — au prix de la capacité « attrape-tout » du VLM.

## Décision de séquencement

1. **Mesurer d'abord** l'hypothèse assertions-vs-pixels (`eval/PLAN_assertions_vs_pixels.md`,
   `eval_tagging.py`). Rien ne se bâtit avant ce verdict.
2. Selon le résultat : une couche d'assertions **à provenance** (Knowledge
   Builder généralisé), qui débloque aussi la priorité n°1.
3. Puis cache de raisonnement, versionnement, et à terme la mémoire globale.

La mémoire familiale interrogeable est la belle finalité ; elle suppose le
graphe d'abord.

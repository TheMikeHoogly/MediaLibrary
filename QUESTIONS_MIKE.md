# Questions en attente de Mike

> Carnet des choix qui lui appartiennent, accumulés pendant une traite
> autonome. Une entrée = une question, ma recommandation, et ce que je fais
> en attendant. **Vidée dès qu'elle est répondue** — la réponse part dans
> `eval/DECISIONS.md` si elle tranche, dans `ROADMAP.md` si elle priorise.
> Protocole : `CLAUDE.md`, « Traite autonome ».

## 20/08 — l'ESPÈCE comme 5ᵉ axe du filtre ?

**La question.** Le filtre déterministe (nom **ou** lieu) atteint **27 936**
des **30 122** photos qui portent un fait NON-date. Les **2 186** restantes
(7,26 %) n'ont qu'une ESPÈCE détectée par YOLO — chat 3 112, oiseau 1 782,
chien 1 381, mouton 719, vache 645, cheval 330. Faut-il en faire un axe de
filtre, pour que « chat » restreigne aux photos où un chat a été DÉTECTÉ ?

**Ma recommandation : pas en ET.** Un filtre ne se juge pas sur ce qu'il
trouve mais sur ce qu'il écarte : YOLO rate des chats, et « chat » ne
rendrait alors plus que ce que YOLO a vu — SigLIP, lui, en trouve d'autres.
Ce serait un rétrécissement SILENCIEUX, exactement ce que le projet compte
ailleurs (`sans_date`). Deux formes acceptables si tu y tiens : un **OU**
(les détections remontent en tête, le reste suit), ou une **puce** de la
planche (« a un animal détecté ») qui dit ce qu'elle fait.

**En attendant** : rien n'est câblé, l'espèce reste invisible du filtre et de
la ligne de faits ; « chat » part entier à SigLIP, comme avant.

## Réglées

- **19/08 — noms affichés deux fois dans la visionneuse.** Recommandation
  suivie : les tags `personne:` / `animal:` sont retirés de la ligne de tags,
  la ligne de faits les porte seule. Le filtre de la planche les garde.
- **19/08 — `eval/DECISIONS.md` à saturation.** Mike a tranché CONTRE ma
  recommandation d'archive : budget porté de 9 000 à 12 000 octets. Deux
  fichiers à consulter valent moins qu'un seul complet. La marge retrouvée a
  d'abord servi à RENDRE la précision rognée le matin même.

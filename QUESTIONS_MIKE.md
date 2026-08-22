# Questions en attente de Mike

> Carnet des choix qui lui appartiennent, accumulés pendant une traite
> autonome. Une entrée = une question, ma recommandation, et ce que je fais
> en attendant. **Vidée dès qu'elle est répondue** — la réponse part dans
> `eval/DECISIONS.md` si elle tranche, dans `ROADMAP.md` si elle priorise.
> Protocole : `CLAUDE.md`, « Traite autonome ».

*Aucune question en attente.*

## Réglées

- **22/08 — appliquer le re-clé des 748 décisions ?** Recommandation suivie :
  **appliqué**. Résultat : **787 décisions sur 685 clés, 97 fiches**. Observé —
  décisions posées sur une clé hors index **928 → 140**. L'audit de la
  quarantaine dit le reste : 788 sorties, **734 arrivées appariées** (même type,
  même index, autre chemin), **54 fusions** de doublons, **0 sans
  contrepartie** — aucune décision humaine perdue, règle 2 tenue.

- **22/08 — que faire du résidu ?** Recommandation suivie : **le garder**. Il
  reste **140 décisions** (117 rattachements, 13 exclusions, 10 confirmations)
  sur des clés dont aucun journal ne connaît la destination, et les **120 clés**
  protégées de la purge du 21/08. Rien n'est purgé : le résidu ne coûte plus
  rien de mesurable, et le jour même, 787 décisions déclarées « déjà perdues »
  se sont révélées récupérables dès qu'une source de preuve nouvelle est
  apparue.

- **21/08 — après le sauvetage : purger, ou chercher la cause d'abord ?**
  Recommandation suivie : **la CAUSE d'abord**. 787 décisions pointant déjà
  dans le vide, c'est une fuite active, pas un résidu — purger avant, c'est
  effacer la scène. La cause a été trouvée le soir même (la cascade suit
  l'index, qui a déjà oublié la clé) et l'angle mort de l'instrument est bouché.

- **21/08 — les 2 374 fiches de visages orphelines, dont 125 portent une
  décision humaine.** Recommandation suivie : **sauver d'abord, purger
  ensuite**. Un instrument cherche, pour chacune des 125, si la photo vit sous
  une autre clé, et nomme celles qui n'ont pas de jumeau ; la purge en
  quarantaine réversible ne vient qu'après. Mike a aussi retenu qu'il faut
  chercher la CAUSE — le 17/08 avait purgé un magasin sur deux sans que ça se
  voie.

- **21/08 — le réservoir de visages sous le seuil de 0,40.** Recommandation
  suivie : **juger 30 propositions de la tranche 0,35–0,40 avant de toucher un
  seuil**. 28 684 visages sous le seuil, mais un meilleur voisin médian à 0,21 :
  le seuil n'est pas ce qui les retient. Abaisser sans jugement serait un pari
  sur des noms.

- **21/08 — la barre de recherche mentait sur une page de résultats.**
  Recommandation suivie : elle cesse de chercher à chaque frappe et attend
  **Entrée**, qui relance la requête côté serveur ; un indice « ↵ Entrée pour
  relancer » paraît tant que le texte diffère. Observé — `montagne` tapé sur la
  page des chats ne touche plus au compte, `Entrée` rend 1 500 photos.

- **20/08 — `eval/DECISIONS.md` à saturation, deuxième fois en deux jours.**
  Recommandation suivie : découpage par DOMAINE, l'outillage part dans
  `docs/DECISIONS_OUTILLAGE.md`. Mike a en plus porté le budget à **50 000**.
  La marge retrouvée a d'abord servi à RENDRE la précision rognée le jour même
  — comme le 19/08.
- **20/08 — l'ESPÈCE comme 5ᵉ axe.** Mike a demandé un CHIFFRE plutôt qu'un
  principe, et le chiffre a tranché contre ma recommandation : **A**, une
  puce explicite. Mais le banc complet, lancé par lui, a aussi réfuté le
  critère que je proposais (voir `eval/DECISIONS.md`, `det_score`).
- **20/08 — `commit` ne poussait rien.** Recommandation suivie : l'agent
  pousse la branche dans les DEUX modes, `main` reste intacte. Observé —
  `refs/remotes/origin/feat/…` créée par l'agent lui-même.
- **19/08 — noms affichés deux fois dans la visionneuse.** Recommandation
  suivie : les tags `personne:` / `animal:` sont retirés de la ligne de tags,
  la ligne de faits les porte seule. Le filtre de la planche les garde.
- **19/08 — `eval/DECISIONS.md` à saturation.** Mike a tranché CONTRE ma
  recommandation d'archive : budget porté de 9 000 à 12 000 octets. Deux
  fichiers à consulter valent moins qu'un seul complet. La marge retrouvée a
  d'abord servi à RENDRE la précision rognée le matin même.

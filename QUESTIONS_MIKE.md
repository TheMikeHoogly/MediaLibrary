# Questions en attente de Mike

> Carnet des choix qui lui appartiennent, accumulés pendant une traite
> autonome. Une entrée = une question, ma recommandation, et ce que je fais
> en attendant. **Vidée dès qu'elle est répondue** — la réponse part dans
> `eval/DECISIONS.md` si elle tranche, dans `ROADMAP.md` si elle priorise.
> Protocole : `CLAUDE.md`, « Traite autonome ».

- **22/08 — 748 décisions humaines attendent un clic.** Le rangement les avait
  décrochées de leur photo (cause trouvée et corrigée : `rekey_everywhere` ne
  re-clait pas les fiches `PEOPLE`/`PETS`, keyées par NOM). La réparation est
  livrée, l'aperçu à blanc a tourné sur le serveur vivant — **804 clés mortes,
  685 à re-clé, 119 sans destination connue, 0 hors bornes**, mêmes nombres que
  le banc. **Ma recommandation : appliquer.** Aucun fichier n'est touché, rien
  n'est inventé (les journaux d'annulation disent où chaque photo est partie),
  et c'est entièrement réversible — quarantaine `_corbeille_decisions/`, bouton
  « 3 · Annuler ». **Le geste** : `/reglages` → « Décisions humaines restées sur
  l'ancien chemin » → **2 · Appliquer**. Puis, pour observer :
  `verifier_recle_decisions.py --base copie.db` doit passer de **928** décisions
  hors index à **~180**.
  *En attendant* : je n'écris rien sur le fonds (la sandbox n'en a pas le
  droit), et je passe aux points suivants.

- **22/08 — que faire du résidu, une fois le re-clé appliqué ?** Il restera deux
  poches : **124 décisions sur 106 clés** dont aucun journal ne connaît la
  destination, et les **120 clés** que la purge du 21/08 a protégées parce
  qu'elles portaient un jugement, alors que leurs photos n'existent plus.
  **Ma recommandation : les GARDER, et ne pas rouvrir le sujet.** Trois raisons.
  (1) Le résidu est passé de 2 374 clés à 120 : il ne coûte plus rien de
  mesurable. (2) Ce sont des décisions humaines, et la règle 2 dit qu'elles ne
  se perdent jamais — les purger est irréversible, les garder ne l'est pas.
  (3) Surtout, aujourd'hui même, **787 décisions déclarées « déjà perdues » se
  sont révélées récupérables à 685** dès qu'une source de preuve nouvelle est
  apparue (les journaux d'annulation). Déclarer une décision définitivement
  morte est un pari que ce projet vient de perdre une fois.
  *En attendant* : rien n'est purgé, et `verifier_orphelins.py --sans-disque`
  continue de les compter.

*Aucune autre question en attente.*

## Réglées

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

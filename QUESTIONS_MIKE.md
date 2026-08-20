# Questions en attente de Mike

> Carnet des choix qui lui appartiennent, accumulés pendant une traite
> autonome. Une entrée = une question, ma recommandation, et ce que je fais
> en attendant. **Vidée dès qu'elle est répondue** — la réponse part dans
> `eval/DECISIONS.md` si elle tranche, dans `ROADMAP.md` si elle priorise.
> Protocole : `CLAUDE.md`, « Traite autonome ».

## 20/08 — `eval/DECISIONS.md` déborde encore : 13 156 pour 12 000

**Le fait.** Six verdicts neufs aujourd'hui — le filtre des noms, l'orthographe
des fiches, `det_score` qui ne dit pas l'espèce, la concordance, le troisième
canal, `commit` qui pousse. Tous portent un chiffre ou une réfutation. J'ai
condensé trois fois ; les 1 156 octets qui manquent ne peuvent plus venir que
de la PRÉCISION des raisons, c'est-à-dire de ce que le seuil protège (ton
arbitrage du 19/08). J'ai donc livré avec `force=` et une raison tracée plutôt
que de rogner en silence.

**Ma recommandation : découper par DOMAINE, pas par statut.** Sortir les
verdicts d'INFRASTRUCTURE (les trois canaux, le pilotage, la livraison git —
17 lignes) dans `docs/DECISIONS_OUTILLAGE.md`, à budget propre. Ce n'est pas
l'archive que tu as rejetée le 19/08 : elle coupait un même domaine en deux
selon l'âge, donc il fallait relire les deux. Ici le réflexe « ne rien
re-proposer » est lui-même par domaine — qui travaille la recherche n'a jamais
besoin de savoir pourquoi `taskkill` a échoué, et réciproquement. Précédent que
tu as accepté : `METHODE.md`, sorti le 16/08.

**Si tu préfères plus simple** : porter le budget à 15 000. Ça marche, et ça
repousse la question d'une semaine — la vraie cause est que le projet produit
des verdicts plus vite qu'il n'en retire.

**En attendant** : rien n'est déplacé, le fichier est complet, le lint crie.

## Réglées

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

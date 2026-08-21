# Questions en attente de Mike

> Carnet des choix qui lui appartiennent, accumulés pendant une traite
> autonome. Une entrée = une question, ma recommandation, et ce que je fais
> en attendant. **Vidée dès qu'elle est répondue** — la réponse part dans
> `eval/DECISIONS.md` si elle tranche, dans `ROADMAP.md` si elle priorise.
> Protocole : `CLAUDE.md`, « Traite autonome ».

### La barre de recherche sur une page de RÉSULTATS (21/08)

`/files?q=…` ne charge que le résultat de la requête. Taper autre chose dans la
barre filtre **dans ce sous-ensemble** : après `espece:chat`, chercher
`espece:chien` annonçait **3 photos** alors que le fonds en a **354**. Le
défaut est ANCIEN — il vaut pour n'importe quelle requête, pas seulement pour
le 5ᵉ axe — mais les puces le rendaient facile à rencontrer, donc elles
relancent désormais la requête côté serveur.

**Ma recommandation** : que la barre fasse pareil, mais seulement sur `Entrée`
— renaviguer à chaque frappe (elle cherche 450 ms après la dernière touche)
donnerait une page qui se recharge pendant qu'on tape. Le compte resterait
faux entre deux `Entrée`, à moins d'afficher « dans ces 1 500 photos » tant
qu'on n'a pas relancé.

**En attendant** : rien touché à la barre ; les puces, elles, disent vrai.

## Réglées

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

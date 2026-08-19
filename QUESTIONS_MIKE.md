# Questions en attente de Mike

> Carnet des choix qui lui appartiennent, accumulés pendant une traite
> autonome. Une entrée = une question, ma recommandation, et ce que je fais
> en attendant. **Vidée dès qu'elle est répondue** — la réponse part dans
> `eval/DECISIONS.md` si elle tranche, dans `ROADMAP.md` si elle priorise.
> Protocole : `CLAUDE.md`, « Traite autonome ».

## 1. Les noms s'affichent deux fois dans la visionneuse

Depuis 14a-iii, la ligne de faits rend `date · lieu · noms`, et les tags
juste en dessous répètent `personne:Cédric Baudin`, `personne:Silvio`… Vu à
l'écran le 19/08.

**Recommandation** : retirer les `personne:` / `animal:` de la ligne de tags
de la visionneuse — la ligne de faits les dit mieux (triés, sans préfixe, avec
leur source). Les tags gardent tout le reste. Réversible, ~10 lignes.

**En attendant** : rien touché, les deux lignes coexistent.

## 2. `eval/DECISIONS.md` est structurellement à saturation

8 969 octets pour un budget de 9 000. Chaque session ajoute des verdicts et
aucun ne peut disparaître — c'est la raison d'être du fichier. J'ai condensé
une vingtaine de raisons le 19/08 ; la marge est épuisée.

**Recommandation** : appliquer le précédent du 16/08 (`eval/METHODE.md` a reçu
son budget propre) — sortir les verdicts d'un domaine clos dans
`eval/DECISIONS_ARCHIVE.md`, budget propre, cité en tête de `DECISIONS.md`.
Rien n'est perdu, rien n'échappe au lint. L'autre voie — relever le budget —
désarme le garde-fou.

**En attendant** : je condense au fil de l'eau, ce qui ronge la précision des
raisons.

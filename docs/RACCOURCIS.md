# Raccourcis clavier — relevé du 26/08/2026

> **Relevé DANS le code**, pas de mémoire : ce sont les touches réellement
> écoutées par les pages de `ui/pages`. **Source unique du panneau `?` de
> l'interface** (30/08) : `ui/global.js` lit ce fichier via `/api/raccourcis`
> et le rend tel quel — jusqu'au marqueur `panneau: fin` ci-dessous. Une
> section dont le titre nomme la page courante (`/sujets`, « Galerie »…)
> remonte en tête avec une pastille « ici ».
>
> Version lisible pour Mike : artefact « Raccourcis de la photothèque ».

## Partout — la barre commune (`ui/global.js`, 30/08)

| Touche | Effet |
|---|---|
| `/` | Met le focus dans « Décris la photo… » (recherche IA sur tout le fonds) — sauf quand on tape déjà dans un champ |
| `Entrée` (dans le champ) | Ouvre la galerie des résultats (`/files?q=`) |
| `?` | Ouvre ou ferme ce pense-bête (aussi le bouton `?` de la barre) ; `Échap` le ferme |

## Juger les propositions de noms — `/sujets`, onglet Classification

N'agit que sur la carte ACTIVE (encadrée), et seulement dans cet onglet.

| Touche | Effet |
|---|---|
| `Espace` / `Entrée` / `O` | Oui, c'est cette personne — passe à la suivante |
| `X` / `Suppr` | Non, ce n'est pas elle |
| `Z` | Annuler le dernier jugement |
| toute lettre `A`–`Z` | Met le focus dans « qui ? » et y inscrit la lettre |
| `Entrée` (dans le champ) | Attribuer le nom saisi |
| `Échap` (dans le champ) | Sortir du champ sans rien attribuer |

## Trancher un échantillon — `/tranche`

| Touche | Effet |
|---|---|
| `1` | Juste |
| `2` | Faux |
| `3` | Indécidable |
| `Z` | Cas précédent |

## Juger le résidu — `/residu`

Les candidats portent une lettre, `A`–`H` (`LETTRES = 'ABCDEFGH'`).

| Touche | Effet |
|---|---|
| `A`–`H` | Cocher / décocher ce candidat |
| `Entrée` | Valider la sélection |
| `0` | « Aucun de ceux-là » — un verdict, pas un abandon |
| `Z` | Cas précédent |

## Visionneuse — Galerie, Animaux

| Touche | Effet |
|---|---|
| `←` `→` | Photo précédente / suivante |
| `Échap` | Fermer |
| `Entrée` / `Espace` | Sur une vignette : l'ouvrir (26/08) |

## Diaporama — Galerie, Carte, Animaux, Personnes

| Touche | Effet |
|---|---|
| `←` `→` | Reculer / avancer |
| `Espace` | Pause / reprise |
| `Échap` | Arrêter |

## Champs de saisie

| Touche | Effet |
|---|---|
| `Entrée` | Valider le nom saisi (personne, animal, groupe) |
| `Entrée` | Barre de recherche : lancer la recherche côté serveur |
| `Échap` | Carte : vider la recherche et tout réafficher |

## Deux pièges

- Sur `/sujets`, rien ne se passe tant qu'aucune carte n'est active.
- Dans un champ de saisie, les raccourcis de jugement sont **volontairement**
  neutralisés — sinon taper « Zoé » annulerait le jugement précédent au
  premier caractère.

<!-- panneau: fin -->

## Le point 6 du plancher : CLOS le 31/08

« Documente les raccourcis dans l'interface elle-même » : le panneau `?`
(bouton dans la barre commune, touche `?`, `Échap` ferme) est rendu par
`ui/global.js` — la brique JS commune, injectée sur toutes les pages comme
`tokens.css` et `base.css` — à partir de CE fichier. Et **l'instrument
existe** : `verifier_raccourcis.py` relève les touches réellement écoutées
dans `ui/pages/*.html` + `ui/global.js`, les compare à ce relevé, et rend
deux chiffres — les touches écoutées qu'on ne peut pas deviner, et celles
que le relevé promet sans que personne ne les écoute. **Ce fichier n'est
donc plus une copie à maintenir : il est mesuré.** Le lancer après toute
touche ajoutée ou retirée (famille `verifier_`, donc par l'agent banc).

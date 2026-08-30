# Raccourcis clavier — relevé du 26/08/2026

> **Relevé DANS le code**, pas de mémoire : ce sont les touches réellement
> écoutées par les onze pages de `ui/pages`. Source unique pour le futur
> panneau `?` dans l'interface — quand il existera, **il se lira ici**, et
> cette page cessera d'être une copie à maintenir.
>
> Version lisible pour Mike : artefact « Raccourcis de la photothèque ».

## Partout — la barre commune (`ui/global.js`, 30/08)

| Touche | Effet |
|---|---|
| `/` | Met le focus dans « Décris la photo… » (recherche IA sur tout le fonds) — sauf quand on tape déjà dans un champ |
| `Entrée` (dans le champ) | Ouvre la galerie des résultats (`/files?q=`) |

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

## Ce qui manque, et pourquoi c'est le point 6 du plancher

**Une seule page affiche ses raccourcis** (`/sujets`, une ligne `.kbd-hint`).
Les six autres contextes ne les disent nulle part : il faut les connaître pour
s'en servir — l'inverse de ce que fait un raccourci. Le plancher
d'accessibilité exige « documente les raccourcis dans l'interface elle-même » ;
c'est la sixième de ses sept règles, et elle n'a **ni instrument ni mise en
œuvre**.

Ce que ça demande : un **fichier JS commun injecté sur toutes les pages**,
comme `tokens.css` et `base.css` le sont déjà (`_UI_GLOBAL_FILES`). Il
n'existe pas encore — ce serait le premier. Sans lui, écrire le panneau `?`
onze fois recréerait exactement la divergence que `components.css` a servi à
supprimer.

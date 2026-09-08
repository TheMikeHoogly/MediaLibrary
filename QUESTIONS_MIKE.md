# Questions en attente de Mike

> Carnet des choix qui lui appartiennent, accumulés pendant une traite
> autonome. Une entrée = une question, ma recommandation, et ce que je fais
> en attendant. **Vidée dès qu'elle est répondue** — la réponse part dans
> `eval/DECISIONS.md` si elle tranche, dans `docs/DECISIONS_OUTILLAGE.md` si
> elle touche l'outillage, dans `ROADMAP.md` si elle priorise.
> Protocole : `CLAUDE.md`, « Traite autonome ».
>
> **Vidée le 08/09 au matin** : « les 214 candidats » — Mike a répondu **(b)**,
> masquer et trier dans l'onglet. **213 photos masquées** (une avait déjà été
> re-taguée et perdu son mot-clé entre la mesure et le geste), chacune avec le
> motif qui l'a proposée, 0 refus, 0 candidat restant. Le verdict vit dans
> `ROADMAP.md`.
>
> **Vidée le 07/09 au soir** : la question du `_exiftool_tmp` orphelin, posée
> et répondue dans la même session (Mike : « ok pour tes recommandations »).
> Le verdict vit dans `eval/DECISIONS.md`, le correctif dans git, le récit
> dans `ROADMAP.md`. Une question résolue qui reste ici cesse d'être lisible,
> et c'est le premier endroit qu'on lit en reprenant.

## En attente

### 1. Les onglets de navigation font 32 px, ta règle dit 44 (08/09)

**Ce qui a été mesuré**, sur la page réelle, pas dans le CSS : les cinq onglets
(`📷 Galerie`, `📁 Dossiers`, `🗺️ Carte`, `🗂️ Sujets`, `🔒 Sensibles`) font
**32 px de haut**. Le plancher du design system dit 44, et **tu l'as tranché
toi-même le 26/08** : « une seule cible, 44 px, partout » — parce qu'une règle
que le système s'écrit et ne tient pas ailleurs cesse d'être une règle. La
décision a été appliquée au chip de filtre. Elle n'a jamais atteint
`.appnav a.tab`.

Ce n'est pas une faute au sens WCAG (32 px passe le seuil 2.5.8 de 24 px). C'est
une incohérence avec ta propre décision, et la barre de navigation est
précisément ce qu'on vise au pouce sur un téléphone.

**Pourquoi je ne l'ai pas fait tout seul** : passer de 32 à 44 px change la
hauteur de la barre sur **toutes** les pages du site. C'est une modification
visuelle globale, pas un correctif local — elle t'appartient.

**Ce que je propose** : `min-height: var(--touch)` sur `.appnav a.tab`, sans
toucher au padding horizontal ni à la typographie. La barre gagne 12 px de haut.
Dis-moi oui, ou dis-moi qu'on assume 32 px pour la nav et je l'écris comme une
exception datée dans `eval/DECISIONS_UI.md` — les deux se défendent, ce qui ne
se défend pas c'est qu'aucun des deux ne soit écrit.

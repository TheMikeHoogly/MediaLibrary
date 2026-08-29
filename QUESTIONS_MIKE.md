# Questions en attente de Mike

> Carnet des choix qui lui appartiennent, accumulés pendant une traite
> autonome. Une entrée = une question, ma recommandation, et ce que je fais
> en attendant. **Vidée dès qu'elle est répondue** — la réponse part dans
> `eval/DECISIONS.md` si elle tranche, dans `docs/DECISIONS_OUTILLAGE.md` si
> elle touche l'outillage, dans `ROADMAP.md` si elle priorise.
> Protocole : `CLAUDE.md`, « Traite autonome ».
>
> **Vidée le 28/08** : les dix-neuf entrées réglées entre le 19 et le 28/08
> ont été retirées — leur verdict vit dans les fichiers de décisions, leur
> récit dans git. Un carnet de questions qui garde ses réponses cesse d'être
> lisible, et c'est le premier endroit qu'on lit en reprenant.

## En attente

### 1. Où vit la corbeille des effacements ? (29/08 soir, étape 6)
Aujourd'hui `C:\Prog\Claude\MediaLibrary\.corbeille-rangement` — sur le PC,
alors que « effacer, c'est effacer du NAS » et que la corbeille du
dédoublonnage est `\\NAS-Bremblens\home\Photos\.corbeille-rangement` (même
nom, autre disque). Six mois d'effacements sur le disque du PC, c'est du
poids qui n'est pas sauvegardé par le snapshot NAS. **Recommandation** :
la déplacer sur le NAS, dans un dossier à part (`\\NAS…\Photos\_CORBEILLE`)
que le scan ignore (`_is_hidden_path`) — un `FILES_TRASH_DIR` à changer et une
migration des paniers existants (0 aujourd'hui). En attendant : rien ne
change, la corbeille est vide.

### 2. Les 831 doublons Flo/Mike : quelle copie est la CANONIQUE ? (29/08 soir)
`Photos Flo\2016 Indonésie` ↔ `Photos Mike\2016\07 Voyage en Indonésie`
(506), Calinous (260). Retirer la copie de l'un, c'est décider que la photo
est à l'autre (17c : le dossier dit le propriétaire). **Recommandation** : ne
rien retirer ENTRE propriétaires sans ton mot — mesurer d'abord (banc
d'image, lecture seule), et proposer une règle sur les chiffres : garder les
deux si chacun en est l'auteur de fait, ou une seule avec les décisions
FUSIONNÉES. Chez un même propriétaire (1 980 groupes chez Mike), la copie
rangée par année l'emporte sur celle d'un dossier thématique — à confirmer.

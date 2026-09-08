# Questions en attente de Mike

> Carnet des choix qui lui appartiennent, accumulés pendant une traite
> autonome. Une entrée = une question, ma recommandation, et ce que je fais
> en attendant. **Vidée dès qu'elle est répondue** — la réponse part dans
> `eval/DECISIONS.md` si elle tranche, dans `docs/DECISIONS_OUTILLAGE.md` si
> elle touche l'outillage, dans `ROADMAP.md` si elle priorise.
> Protocole : `CLAUDE.md`, « Traite autonome ».
>
> **Vidée le 07/09 au soir** : la question du `_exiftool_tmp` orphelin, posée
> et répondue dans la même session (Mike : « ok pour tes recommandations »).
> Le verdict vit dans `eval/DECISIONS.md`, le correctif dans git, le récit
> dans `ROADMAP.md`. Une question résolue qui reste ici cesse d'être lisible,
> et c'est le premier endroit qu'on lit en reprenant.

## En attente

### 1. Les 214 candidats : je les masque, ou tu les regardes d'abord ? (08/09)

**Ce qu'il y a.** Le filet lit les mots-clés que le tagueur a déjà écrits et
propose **214 photos** à ton regard : 144 portent « document », 94 « facture »,
10 « reçu », 9 « capture », 4 une pièce d'identité (une photo peut compter
double). C'est un filet, pas un verdict — il dit « regarde celle-là ».

Vérifié en ouvrant des photos, pas en lisant du code : `facture` a sorti un
**permis de circulation nominatif** de Florine (nom, adresse, date de
naissance) dans `Photos Flo/Appartement Bremblens`. Le filet sert. Et deux
mots ont été retirés parce qu'ils proposaient des souvenirs : `passeport`
tombait sur une vieille photo de famille numérisée, `code qr` sur un panneau
publicitaire.

**Ce que je n'ai PAS fait, et pourquoi.** Rien n'est masqué. Poser l'axe sur
214 photos d'un coup, c'est les retirer de la galerie de toute la famille sur
la foi d'un mot-clé — un geste qui t'appartient, pas la conséquence d'une
requête. `GET /api/sensibles/candidats` est en lecture seule.

**Trois voies, et ma recommandation :**

**(a) Tu regardes d'abord, en une planche.** Je fabrique une planche contact
des 214 (comme celle du 06/09, mais elle sera lisible — c'est le point de
`eval/METHODE.md`), tu coches, je masque ce que tu désignes. Le plus sûr, et
ça prend une demi-heure de ton temps.

**(b) Je masque les 214 et tu tries dans l'onglet.** → **Ma recommandation.**
C'est exactement ce que l'onglet Sensibles existe pour faire : masquer d'abord,
juger ensuite, trois gestes par photo, tout réversible. Le coût d'un faux
positif est qu'une photo de famille disparaît de la galerie pendant quelques
jours — le coût d'un faux négatif est qu'un permis de circulation reste visible
de tous. Et l'onglet t'annonce le nombre tout seul.

**(c) Je ne masque que les plus sûrs** — `carte d'identité`, `permis de
conduire`, `iban`, `reçu` (une vingtaine) — et le reste attend la fin de la
campagne, quand le nouveau modèle aura re-tagué tout le fonds et que le filet
sera à jour (aujourd'hui **7 des 214** seulement portent le nouveau
vocabulaire).

**Ce que je fais en attendant** : rien sur tes photos. Le filet est mesurable
quand tu veux (`GET /api/sensibles/candidats`), et le compte montera tout seul
à mesure que la campagne avance.

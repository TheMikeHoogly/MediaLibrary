# Questions en attente de Mike

> Carnet des choix qui lui appartiennent, accumulés pendant une traite
> autonome. Une entrée = une question, ma recommandation, et ce que je fais
> en attendant. **Vidée dès qu'elle est répondue** — la réponse part dans
> `eval/DECISIONS.md` si elle tranche, dans `docs/DECISIONS_OUTILLAGE.md` si
> elle touche l'outillage, dans `ROADMAP.md` si elle priorise.
> Protocole : `CLAUDE.md`, « Traite autonome ».
>
> **Vidée le 08/09 après-midi** : « les onglets font 32 px » — Mike : « ok pour
> 44 px partout ». Implémenté, puis AUDITÉ : la décision touchait cinq onglets
> et en a révélé cinq autres endroits (la marque, la sous-nav Sujets, trois
> champs de recherche, deux boutons de la carte, six faux `.btn` sur
> `/reglages`). Les verdicts vivent dans `eval/DECISIONS_UI.md`.
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

### 1. `eval/DECISIONS.md` est à 96 % de son budget (08/09)

**Le chiffre.** 96 019 octets sur 100 000. Il reste **~4 Ko**, soit deux ou trois
verdicts. `ROADMAP.md` suit à **89 %** (89 005). Les autres sont larges :
`docs/DECISIONS_OUTILLAGE.md` 25 %, `eval/DECISIONS_UI.md` 14 %, `CLAUDE.md` 11 %.

**Pourquoi ça revient.** Tu as tranché le 07/09 — il y a un jour — en découpant
par DOMAINE : `eval/DECISIONS_UI.md` est sorti du carnet et a libéré 8,5 Ko. Ils
sont déjà repris. Ce n'est pas que le découpage ait raté : c'est que **le rythme
d'écriture dépasse ce qu'un découpage libère**. Quatre relèvements de seuil ont
été consommés avant d'avoir servi, un découpage l'a été en vingt-quatre heures.

**Trois voies, et ma recommandation :**

**(a) Un second découpage par domaine.** Le carnet contient encore deux gros
domaines mélangés : la VISIBILITÉ (privé, sensible, comptes, qui voit quoi) et
le TAGGING (modèles, prompts, campagnes, vocabulaire). Sortir l'un des deux
libère beaucoup — et qui travaille la visibilité n'a jamais besoin de lire les
verdicts sur le vocabulaire du tagueur. C'est ton propre argument du 07/09,
appliqué une fois de plus.

**(b) Condenser les entrées anciennes.** → **Ma recommandation, EN PLUS de (a).**
Les verdicts de plus d'un mois qui ont été appliqués, observés et ne sont plus
discutés peuvent perdre leur récit et garder leur règle. Ce qui protège, c'est la
RÈGLE ; le récit sert le jour où on hésite. Mais fait seul, ça repousse de deux
semaines.

**(c) Relever le seuil.** Ça n'a jamais rien réglé quatre fois de suite, et
chaque relèvement rend le carnet moins lisible. Je le mentionne pour être
complet, pas pour le proposer.

**Ce que je fais en attendant** : j'écris les nouveaux verdicts UI dans
`eval/DECISIONS_UI.md`, qui est large. Mais un verdict sur la photothèque n'a
plus qu'un ou deux emplacements devant lui.

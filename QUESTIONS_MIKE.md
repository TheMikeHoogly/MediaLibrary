# Questions en attente de Mike

> Carnet des choix qui lui appartiennent, accumulés pendant une traite
> autonome. Une entrée = une question, ma recommandation, et ce que je fais
> en attendant. **Vidée dès qu'elle est répondue** — la réponse part dans
> `eval/DECISIONS.md` si elle tranche, dans `docs/DECISIONS_OUTILLAGE.md` si
> elle touche l'outillage, dans `ROADMAP.md` si elle priorise.
> Protocole : `CLAUDE.md`, « Traite autonome ».
>
> **Vidée le 11/09** : « qui fabrique les 39 181 vignettes absentes ? » (98 %
> du fonds sans vignette de grille). Mike : **« les deux »** — le tagueur au
> passage dès maintenant (livré le soir même), un fil de fond pour le reste
> après la campagne. Le verdict vit dans `eval/DECISIONS.md`, les chiffres
> dans `PERFORMANCE.md` § 3.0.
>
> **Vidée le 10/09 au soir** : « le cache de vignettes est éteint à 4,5 % — le
> refait-on ? » Mike : **« ok, je te suis ! »**. Les deux gestes sont livrés :
> le nom ne porte plus le mtime, et nos propres écritures de tags re-tamponnent
> la vignette au lieu de la jeter. Le verdict vit dans `eval/DECISIONS.md`.
>
> **Vidée le 08/09 au soir** : le budget de `eval/DECISIONS.md`. Mike :
> « augmente le budget de +25 %, je suis toutes tes recommandations ». Les
> deux gestes ensemble — budget à **125 000** et second découpage par domaine
> (`eval/DECISIONS_TAGGING.md`, 31,6 Ko sortis) : **96 019 → 64 729 octets**,
> de 96 % de l'ancien seuil à **52 % du nouveau**. La condensation des
> verdicts anciens, ma troisième recommandation, n'a PAS été faite et c'est
> délibéré : elle demande de relire pour décider quoi perdre, et un carnet
> qu'on n'a plus besoin de raccourcir ne se raccourcit pas au chausse-pied.
> Elle reste disponible le jour où le seuil redevient proche.
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

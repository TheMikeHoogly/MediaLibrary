# Questions en attente de Mike

> Carnet des choix qui lui appartiennent, accumulés pendant une traite
> autonome. Une entrée = une question, ma recommandation, et ce que je fais
> en attendant. **Vidée dès qu'elle est répondue** — la réponse part dans
> `eval/DECISIONS.md` si elle tranche, dans `docs/DECISIONS_OUTILLAGE.md` si
> elle touche l'outillage, dans `ROADMAP.md` si elle priorise.
> Protocole : `CLAUDE.md`, « Traite autonome ».

---

## Le cache de vignettes est éteint pendant la campagne — le refait-on ?

**Ce que j'ai mesuré le 10/09** (`mesure_service_vignettes.py`, sur ta machine) :

```
  photos avec une vignette 512  utilisable :   1995  (4.5 %)
  photos avec une vignette 1600 utilisable :     80  (0.2 %)

  photos dont le mtime a change dans le dernier jour :  6524  (14.6 %)
                                        en 7 jours    : 29196  (65.5 %)
```

**Le cache est éteint, et c'est nous qui l'éteignons.** Une vignette s'appelle
`md5(clé|taille|MTIME)`. Écrire un tag XMP change le mtime **sans changer un
seul pixel** — donc chaque photo retaguée jette ses vignettes. La campagne en
périme ~6 500 par jour ; la galerie ne peut en refaire que ce qu'on regarde.
Résultat : **95 % des cases de galerie relisent l'original sur le NAS**, 2 à
6 Mo au lieu de ~50 Ko. C'est une partie de ce que tu ressens quand une planche
met du temps à venir.

Et aucun champ de l'index ne décrit les PIXELS : le cache est indexé sur une
identité de FICHIER pour retrouver une image qui, elle, n'a pas bougé.

### Ce que je propose, en deux gestes qui vont ensemble

1. **Séparer le NOM de la VALIDITÉ.** La vignette s'appellerait `md5(clé|taille)`
   — sans mtime — et porterait, dans son propre mtime de fichier, celui de la
   photo dont elle vient. Valide si les deux concordent. Conséquence : **un seul
   fichier par (photo, taille), et plus jamais d'orphelin** — une vignette
   périmée est écrasée, pas dupliquée. **O15 disparaît à sa racine** : la purge
   devient une migration unique au lieu d'une corvée qui revient.
2. **Ne plus jeter ce que nous savons intact.** C'est le serveur lui-même qui
   écrit les XMP : à ce moment-là, il SAIT que seuls les métadonnées ont changé.
   Il lui suffit alors de re-tamponner la vignette existante (`os.utime`, une
   microseconde) au lieu de la laisser périmer. Un tag écrit ne coûterait plus
   une relecture de 2 à 6 Mo sur le NAS.

**Ma recommandation : oui, et maintenant plutôt qu'après la campagne** — c'est
pendant qu'elle tourne que le défaut coûte le plus cher. Le changement ne
touche ni le prompt, ni la version du pipeline, ni un index : uniquement la
mécanique du cache.

**Ce que ça coûte, dit franchement** : au premier redémarrage, les vignettes
actuelles ne répondent plus au nouveau nom. Mais elles ne répondent déjà
qu'à 4,5 % — la perte réelle est de **1 995 vignettes**, refaites au fil de la
navigation. Et le bat 51 reste utile une dernière fois pour vider l'ancien
format.

**Ce que je fais en attendant** : rien sur cette mécanique. La mesure est
livrée, l'analyse est ici, et le geste attend ton feu vert.
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

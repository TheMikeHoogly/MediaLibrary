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

## La mémoire de la machine — 13,5 Go engagés par le moteur d'Ollama (12/09, 00 h)

**Ce qui est mesuré** (`mesure_memoire.py`, `diagnostic_ollama_memoire.py`,
sur ta machine) : 27 Go d'engagement mémoire pour 15,7 Go de RAM, **0,5 Go
libre**, 3,8 Go de fichier d'échange, et jusqu'à **1 300 pages relues du
disque par seconde**. Le serveur de la photothèque a entre 31 % et 65 % de sa
mémoire hors RAM : chaque parcours de l'index la relit sur le disque, et c'est
une part du prix des routes (§ 3.10, § 3.11 de `PERFORMANCE.md`).

**Qui la tient** : `llama-server.exe` (le moteur d'Ollama) — **13,53 Go
privés** pour un modèle déclaré à 3,47 Go, contexte 4 096, une requête à la
fois. Ce n'est pas une fuite lente : après le redémarrage du PC il était à
5,9 Go, et **de retour à 13,5 Go vingt minutes plus tard**. Ensuite, `vmmem`
(la VM de Claude sur ton PC) à 4 Go, le serveur à 2,4 Go.

**La question t'appartient** : c'est ta machine, et deux des trois leviers
touchent ton confort, pas le code.

| Piste | Ce qu'elle coûte | Ce qu'elle rapporterait |
|---|---|---|
| ~~**(a) `GGML_CUDA_NO_PINNED=1`**~~ — **ESSAYÉ le 12/09 à 00 h 20, ÉCARTÉ** | — | **13,33 Go après 17 min**, contre 13,53 sans la variable ; tagging inchangé (médiane 12 s contre 13 s). La variable ne sert donc à rien : `setx GGML_CUDA_NO_PINNED ""` pour la retirer, ou la laisser, elle ne coûte rien non plus. |
| **(b) Vivre avec** | rien | rien ; le serveur reste 1,5 à 3 × plus lent qu'il ne devrait, tant que la campagne tourne |
| **(c) Fermer la VM de Claude quand je ne travaille pas** | tu perds l'accès à tes dossiers depuis Claude | 4 Go d'engagement en moins |

**Ce que la mesure a appris** : le chiffre à regarder n'est pas l'engagement
de 13,3 Go — la moitié n'est jamais touchée — mais les **7,8 Go RÉSIDENTS**
du moteur pour un modèle de 3,47 Go. C'est ça qui ne laisse que 0,5 Go à la
machine.

**Ma recommandation, maintenant : (b) jusqu'au 14/09.** Il reste ~6 700 photos
à re-taguer, soit une journée. Pendant la campagne, le modèle et son prompt
sont gelés (règle du chantier), donc la seule variable libre est la mémoire de
la machine, et aucun réglage mesuré ne la rend. **Après la campagne**, la
question redevient ouverte et se pose autrement : un modèle qui tient
ENTIÈREMENT dans les 4 Go de VRAM (qwen3-vl:2b y tenait) ne garderait pas
7,8 Go en RAM — à instruire avec `vision-eval`, pas à décider ici.

**En attendant** : rien n'est touché ; les bancs sont écrits et se relancent
en une ligne (`diagnostic_ollama_memoire.py`, `mesure_memoire.py`).

---


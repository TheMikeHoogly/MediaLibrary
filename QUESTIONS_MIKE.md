# Questions en attente de Mike

**Deux questions ouvertes (19/09) — la brique 1, le filet « intime ».**
Les briques 2, 3, 4, 5 et 6 du chantier 19 sont livrées et fusionnées. Il ne
reste que celle-ci, et elle a été MESURÉE deux fois sans rien câbler.

**1. La file de revue (a), ou un modèle dédié (b) ?**
Le zéro-shot SigLIP ne sépare pas l'intime du témoin (mesuré le 17/09) ; sur
les captures d'écran, il ne reste que l'extension `.png` — 443 fichiers
(mesuré le 19/09).
*Recommandation* : **(a), la file de revue**. 443 fichiers, c'est un nombre
qu'on regarde ; ils vont dans l'onglet Sensibles de leur PROPRIÉTAIRE, classés,
et c'est lui qui tranche. Aucune règle ne prétend savoir, aucun faux masquage.
**(b) un modèle dédié** demande un jeu de validation que **Flo et toi** devez
constituer — je ne regarde pas ces photos, et un banc qui les afficherait
serait exactement ce qu'on veut empêcher.
*En attendant* : rien n'est câblé, rien n'est masqué.

**2. Rendre le signal LISIBLE : trois champs au passage de la vignette ?**
Ni l'appareil (EXIF `Make`/`Model`), ni la largeur, ni la hauteur ne sont dans
la base — c'est pour ça que le « signal franc » du plan n'est aux trois quarts
pas lisible. Le serveur ouvre déjà chaque image pour fabriquer sa vignette :
les poser au passage coûte trois champs, pas une campagne.
*Recommandation* : **oui, mais seulement si tu veux la suite (b)** — pour la
file de revue (a), `.png` suffit à constituer la liste. Si tu dis oui, c'est
un petit chantier propre : trois champs, une passe de rattrapage optionnelle,
et le filet captures devient mesurable pour de bon.
*En attendant* : rien n'est ajouté au pipeline.

---

**Aucune question ouverte.** (18/09)

---



---

> Carnet des choix qui lui appartiennent, accumulés pendant une traite
> autonome. Une entrée = une question, ma recommandation, et ce que je fais
> en attendant. **Vidée dès qu'elle est répondue** — la réponse part dans
> `eval/DECISIONS.md` si elle tranche, dans `docs/DECISIONS_OUTILLAGE.md` si
> elle touche l'outillage, dans `ROADMAP.md` si elle priorise.
> Protocole : `CLAUDE.md`, « Traite autonome ».
>
> **Vidée le 18/09** : les trois entrées de la traite de la nuit. (1) « Je
> fusionne les deux branches ? » — les écrans regardés, tout est dans `main`.
> (2) « Qui pose les adresses e-mail ? » Mike : **« c'est moi qui vais poser
> les adresses pour l'instant »** — d'où le bouton « Adresse » des Réglages,
> et les deux adresses vérifiées dans son Gmail (`flolaeser@gmail.com`,
> `markushuegli@gmail.com`). (3) « Le SMTP ? » Mike : **« je suis ta
> recommandation »** — donc NON. Les deux verdicts sont dans
> `eval/DECISIONS.md`.
>
> **Vidée le 16/09** : « la veille — 30 min puis écran noir, pas de
> reprise, légende ? ». Mike : **« ok pour tes recommandations. ajoute le
> lieu »**. Constantes inchangées ; la légende dit « Lieu · mois année »,
> le lieu venant de `_faits_pour` (la même vue que la galerie).
>
> **Vidée le 15/09 au soir** : « ton oui aux 8 heures tient-il pour une
> SEMAINE ? » Mike : **« oublie. on ne va pas passer 8 jours de plus a
> mesurer un ancien modele. soit tu trouves un superbe candidat qui vaudrait
> la peine, soit on oublie »**. Recherche faite : sous 4 Go de VRAM, le champ
> de septembre 2026 est `qwen3.5:4b` (en place), `qwen3-vl:4b` (déjà écarté :
> débordement, ~3× plus lent), `qwen3-vl:2b` (l'ancien), `gemma3:4b` et
> `minicpm-v4.6` (1 B). Tout ce qui est franchement meilleur — Qwen3-VL 8B,
> Gemma 4 26B — demande une AUTRE carte. **Il n'y a pas de candidat superbe :
> le plafond de 4 Go est la contrainte, pas le choix du modèle.** La campagne
> est ABANDONNÉE ; la page de préférence en aveugle et le tirage ciblé
> tombent avec elle. Verdict dans `eval/DECISIONS.md`.
>
> **Vidée le 15/09** : « ok pour ta recommandation » — l'expérience unique,
> deux modèles × deux prompts sur le même tirage. **Elle a tourné** : 240
> lignes, 0 sortie malformée, `qwen3.5:4b` à 9,6 s/photo contre 3,2 s pour
> `qwen3-vl:2b`. Elle a aussi fait tomber le chiffre des « 8 heures » —
> tranché par l'entrée ci-dessus. Détail dans `ROADMAP.md` § B.
>
> **Vidée le 14/09 au soir** : « les 9 vidéos de la salle étaient 25 à 50 %
> plus longues chez Google — coupe volontaire, ou versions longues perdues ? »
> Mike : **« oui, les coupes étaient de moi, tout est en ordre »**. Rien n'est
> perdu, et le verdict de la salle est complet : pour les images comme pour
> les vidéos, **c'est le NAS qui porte la bonne version**, parce que c'est lui
> qui porte le travail de Mike.
>
> **Vidée le 14/09** : « la salle d'arbitrage ». Mike a regardé les paires
> dans `/arbitrage` et tranché : **les retouches sont les siennes**, le NAS
> gagne, la salle est effacée. Le verdict et sa mécanique vivent dans
> `eval/DECISIONS.md` ; ce que la protection de la salle a changé est dans
> `ROADMAP.md` § B8.
>
> **Vidée le 13/09** : « la galerie envoie 1,86 Mo d'un coup — on pagine ? »
> Mike : **« ok pour tes recommandations »** → **(c), le chargement à la
> demande**. Le jalon vit dans `ROADMAP.md` § C3 — et sa CIBLE a changé le
> 14/09, quand la marche du NAS a été coupée : ce n'est plus `enrichir` mais
> `mode_index`.
>
> **Vidée le 12/09** : « les 13,5 Go du moteur d'Ollama ». Mike a essayé (a)
> — `GGML_CUDA_NO_PINNED=1` — **écarté par la mesure**, puis a tranché
> **(b) : on vit avec** jusqu'à la fin de la campagne. La décision est
> **périmée depuis** que la campagne est finie (`ROADMAP.md` § B2).
>
> **Vidée le 11/09** : « qui fabrique les 39 181 vignettes absentes ? »
> Mike : **« les deux »**. Livré ; chiffres dans `PERFORMANCE.md` § 3.0.
>
> **Vidée le 10/09 au soir** : « le cache de vignettes est éteint à 4,5 % — le
> refait-on ? » Mike : « ok, je te suis ! ». Les deux gestes sont livrés.
>
> **Vidée le 08/09 au soir** : le budget de `eval/DECISIONS.md`. Mike :
> « augmente le budget de +25 %, je suis toutes tes recommandations ».
> **96 019 → 64 729 octets** ; la condensation des verdicts anciens n'a PAS
> été faite et c'est délibéré — elle reste disponible le jour où le seuil
> redevient proche.
>
> **Vidée le 08/09 après-midi** : « les onglets font 32 px » — Mike : « ok pour
> 44 px partout ». Implémenté puis AUDITÉ : la décision touchait cinq onglets
> et en a révélé cinq autres endroits. Verdicts dans `eval/DECISIONS_UI.md`.
>
> **Vidée le 08/09 au matin** : « les 214 candidats » — Mike a répondu **(b)**.
> **213 photos masquées**, 0 refus, 0 candidat restant.
>
> **Vidée le 07/09 au soir** : le `_exiftool_tmp` orphelin. Mike : « ok pour
> tes recommandations ». Une question résolue qui reste ici cesse d'être
> lisible, et c'est le premier endroit qu'on lit en reprenant.

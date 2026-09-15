# Questions en attente de Mike

## OUVERTE — **les « 8 heures » n'existent pas : ce sont 8 JOURS** (15/09)

Tu as dit oui à 8 heures de GPU. **Le chiffre était faux, et c'est moi qui te
l'avais donné.** La ligne de `ROADMAP.md` disait « 40 525 photos × ~17,6 s =
~8 h de GPU ». La multiplication ne tient pas :

    40 525 × 17,6 s = 713 240 s = 198 h = 8,3 JOURS

Une erreur d'unité, recopiée telle quelle à chaque relecture. **Et la réalité
le confirme** : la dernière campagne a été lancée le 05/09 et finie dans la
nuit du 12 au 13/09 — **7,5 jours**, soit 16,0 s/photo, à 10 % du chiffre
écrit. Les deux se recoupent ; seule l'unité était fausse.

**Le plancher, mesuré ce matin** sur le tirage en aveugle, modèle chaud, sans
vignettes ni XMP ni scan concurrent :

| modèle | par photo | une campagne entière |
|---|---:|---:|
| `qwen3.5:4b` (prod) | 9,6 s | **4,5 jours** |
| `qwen3-vl:2b` (l'ancien) | 3,2 s | **1,5 jour** |

**La question** : est-ce que ton « oui » tient pour **une semaine** de GPU pris
et de prompt figé, et non pour une nuit ? C'est la même décision, ce n'est pas
le même prix.

**Ma recommandation** : ne rien relancer avant d'avoir la page de préférence
en aveugle. Si `qwen3-vl:2b` tague aussi bien que `qwen3.5:4b` — et le tirage
ne permet PAS d'en décider, il faut ton œil — alors la vraie décision n'est
plus « quel nouveau modèle » mais « revenir à celui qui va trois fois plus
vite », et la campagne tombe de 4,5 jours à 1,5.

**En attendant** : rien n'est lancé. Le tirage est gelé
(`eval/tirage_aveugle.json`), ses 240 réponses sont enregistrées, et elles
serviront telles quelles à la page de préférence — aucune mesure à refaire.

---

---

> Carnet des choix qui lui appartiennent, accumulés pendant une traite
> autonome. Une entrée = une question, ma recommandation, et ce que je fais
> en attendant. **Vidée dès qu'elle est répondue** — la réponse part dans
> `eval/DECISIONS.md` si elle tranche, dans `docs/DECISIONS_OUTILLAGE.md` si
> elle touche l'outillage, dans `ROADMAP.md` si elle priorise.
> Protocole : `CLAUDE.md`, « Traite autonome ».
>
> **Vidée le 15/09** : « ok pour ta recommandation » — l'expérience unique,
> deux modèles × deux prompts sur le même tirage. **Elle a tourné** : 240
> lignes, 0 sortie malformée, `qwen3.5:4b` à 9,6 s/photo contre 3,2 s pour
> `qwen3-vl:2b`. Elle a aussi fait tomber le chiffre des « 8 heures » —
> question rouverte ci-dessus. Détail dans `ROADMAP.md` § B.
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

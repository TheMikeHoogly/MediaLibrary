# Questions en attente de Mike

## Ouverte — **les 9 vidéos de `Google porte mieux`** (14/09)

Tu as effacé toute la salle d'arbitrage après avoir vu les paires, et tu as
donné la cause pour les IMAGES : les retouches sont les tiennes, le NAS gagne.
C'est net et c'est clos.

**Les 9 VIDÉOS, elles, n'étaient pas dans ce cas.** Mesuré avant l'effacement
(`mesure_salle_arbitrage.py`, durées lues par exiftool) : la copie de Google
était **25 à 50 % plus longue** que celle du fonds.

| fichier | Google | NAS |
|---|---:|---:|
| `20250510_213412.mp4` | 42,6 s | 33,5 s |
| `20250510_213701.mp4` | **111,6 s** | **71,6 s** |
| `20250510_214847.mp4` | 24,3 s | 15,8 s |
| `20250717_212635.mp4` | 17,9 s | 11,0 s |
| `20250814_203639.mp4` | 24,3 s | 16,0 s |
| `20250814_213911.mp4` | **25,3 s** | **13,2 s** |
| `20250814_214518.mp4` | 28,40 s | 28,39 s |
| `20250814_222300.mp4` | 82,0 s | 60,0 s |
| `20250815_000138.mp4` | 64,9 s | 62,3 s |

**La question** : ces coupes sont-elles de toi, comme les rotations — auquel
cas tout est en ordre et cette entrée se vide — ou les versions longues
sont-elles parties sans que tu l'aies voulu ?

**Ma recommandation** : ouvrir deux ou trois de ces vidéos dans
`Photos Mike\2025` et regarder si elles finissent là où tu les as coupées. Si
oui, rien à faire. Sinon, deux endroits où chercher **avant que ça expire** :
la corbeille du NAS (`#recycle` sur le partage, si elle est activée) et
l'extrait du Takeout, s'il n'a pas été effacé par le bat 49. **La corbeille de
l'application ne les a pas** — vérifié, aucune entrée depuis la salle, tu les
as effacées depuis Windows.

**En attendant** : je ne touche à rien. Aucun outil ne peut plus les
ressusciter et aucun ne va les chercher.

---

> Carnet des choix qui lui appartiennent, accumulés pendant une traite
> autonome. Une entrée = une question, ma recommandation, et ce que je fais
> en attendant. **Vidée dès qu'elle est répondue** — la réponse part dans
> `eval/DECISIONS.md` si elle tranche, dans `docs/DECISIONS_OUTILLAGE.md` si
> elle touche l'outillage, dans `ROADMAP.md` si elle priorise.
> Protocole : `CLAUDE.md`, « Traite autonome ».
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

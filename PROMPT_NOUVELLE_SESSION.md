# Reprise — MediaLibrary, après la session du 12 septembre 2026

> **Ce fichier est ÉPHÉMÈRE.** Il décrit un état, pas des règles. Les règles
> vivent dans `CLAUDE.md`, le plan dans `ROADMAP.md`, les verdicts dans
> `eval/DECISIONS.md` et `docs/DECISIONS_OUTILLAGE.md`. **Les chiffres du
> chantier performance sont dans `PERFORMANCE.md`** (§ 3.13 à 3.18 pour la
> galerie, § 5 pour l'ordre).

---

## 0. La consigne de Mike

> « concentre toi sur la performance (toujours en attendant la fin du
> tagging). fais une analyse en profondeur, des tests utiles et intelligents »
> — « sois le plus autonome possible ».

Et, le 12/09 : **« fais en sorte d'implémenter une double-vérification
systématique suite à une analyse »** → c'est la **règle n° 11 de `CLAUDE.md`**,
née de quatre fautes de la même matinée. Elle a mordu dans l'heure : voir
§ 2 ci-dessous.

La campagne de retag commande toujours tout : GPU pris, **prompt
intouchable**. **Relevé le 12/09 à 12h15 : 3 537 restantes, 1 abandon**
(`/api/maint/status` → `config.retag`, la seule source juste : `counts.tagues`
compte les photos taguées un jour, pas celles de CETTE passe). 119 photos en
35 min → ~17,6 s chacune → elle finit **au petit matin du 13/09**. La section
C du `ROADMAP` s'ouvre tout de suite après.

---

## 1. Livré le 12/09 — la page `/files` divisée par deux

`Photos Mike/2022`, 2 519 photos, récursif, réobservé en réel à chaque étape :

| | matin | soir |
|---|---:|---:|
| `parcours` | 715 ms | **46 ms** (8 ms cache chaud) |
| `index` | 112 à 136 ms | **47 ms** |
| `marques` | 76 à 114 ms | **29 ms** |
| `enrichir` (mode navigation) | 455 ms | 325 ms |
| `enrichir` (dès qu'un tag est coché) | 455 ms | **0,0 ms** |
| la page entière | 1 493 à 1 870 ms | **633 à 820 ms** |

Six gestes, chacun avec son banc et sa réobservation :

1. **Le dossier de tête était énuméré DEUX fois** en récursif (§ 3.13).
2. **Le lien de dossier était calculé par PHOTO** alors qu'il ne dépend que du
   dossier ; **la date précise était demandée deux fois** par photo (§ 3.13).
3. **La page bâtissait 2 519 fiches pour en montrer 336** dès qu'un tag est
   coché — les quatre modes « la grille est un résultat » remplacent
   `file_data` (§ 3.14).
4. **Le cache de listage** (§ 3.15 la preuve, § 3.16 le geste) : un `stat` par
   dossier surveillé dit si le listage est encore vrai, pour 2 à 9 % du prix
   d'une énumération. `_lister_dossier` n'a pas bougé — elle garde son oracle
   et ses 20 bancs ; `_lister_dossier_frais` décide. **Aucune invalidation
   explicite n'est câblée** : une écriture du serveur change la date du
   dossier comme n'importe quelle autre.
5. **La vue était consultée 44 605 fois pour 2 519 réponses** dans `index` :
   balayer l'index BRUT, ne demander à la vue que les clés retenues (§ 3.17).
6. **La date précise était calculée une TROISIÈME fois**, dans la passe des
   marques (§ 3.18) : les quatre branches la rangent sous `'_ep'`, la passe la
   `pop` pour chaque entrée. Sentinelle `recherche.A_CALCULER` obligatoire —
   `None` est une réponse légitime d'`epoch_precis`.

7. **Le LIEU était demandé 2 519 fois pour deux réponses** (§ 3.19) : il ne
   dépend que du DOSSIER, comme le lien de dossier du § 3.13. Mémo par
   requête dans `lieu_pour`, GPS laissé dehors (il est par photo) —
   `enrichir.faits.regle.lieu` **31,3 → 5,8 ms**. Et **c'est l'instrument qui
   a désigné la cible** : j'allais parier sur la date, les § 3.13 et 3.18 y
   ayant déjà trouvé deux redites. C'eût été le mauvais chantier.

**69 bancs verts** à la livraison — c'est la règle 2 qui les lance tous
(voir § 4), et elle met ~6 minutes.

---

## 2. La règle n° 11, et ce qu'elle a attrapé le jour même

J'allais sortir la reconstruction de `_key_index` de son verrou, sur la foi
d'un « 620 à 870 ms, une fois par minute » lu dans les docs — et répété deux
fois à Mike. Remesuré : **~40 ms**. Le chiffre datait d'AVANT la mémoïsation
du 11/09, le § 2 ter de `PERFORMANCE.md` portait déjà la bonne valeur (44 ms)
pendant que le commentaire du code et deux autres sections gardaient
l'ancienne. **Un chantier entier reposait sur un chiffre périmé.** Corrigé
partout. Les 620–870 ms existent : c'est le PREMIER build après un démarrage.

---

## 2 bis. Livré aussi le 12/09 — hors performance

**`exiftool -P`** : le tagueur ne détruit plus la date des fichiers. La preuve
tenait dans un seul dossier — les vidéos de `2022`, qu'il ne touche pas,
portaient 50 jours distincts de 2022 ; les images taguées, un seul jour.
Observé en réel : une photo taguée sous les yeux du banc garde sa date.
Verdict et chiffres dans `eval/DECISIONS.md`.

**Le tri des dépôts d'Uploads** (`ROADMAP` B5) : la lampe dans l'entête, la
page `/tri`, la date et le déposant notés à l'arrivée, et les deux gestes —
garder (→ `_A TRIER`) et effacer (→ corbeille, annulable). **248 dépôts
attendent une décision de Mike**, le plus ancien depuis 30 jours. Trois choses
apprises en l'éprouvant, toutes dans les bancs :
- le carnet enregistre une **ARRIVÉE**, pas une attente — le purger à la
  décision cassait l'annulation ;
- une décision **retire** le dépôt de la vue au lieu de la refaire : le client
  SMB de Windows garde les métadonnées d'un dossier quelques secondes, et la
  lampe comptait encore un geste qu'on venait de faire ;
- `Uploads` n'a **pas** d'état « déjà trié » : décider fait sortir le fichier.

La vue est un **tableau** depuis le même jour (tri, filtre nom/dossier,
sélection multiple, gestes groupés, annulation du lot). Deux défauts trouvés
en le regardant tourner, tous deux hors de ce chantier : `_url_for_key` ne
servait aucune clé d'Uploads **en sous-dossier** — 193 dépôts sur 248 sans
vignette — et `[hidden]` perdait contre le `display:` des composants, ce que
trois pages rustinaient déjà chacune de leur côté (corrigé dans `base.css`).

## 3. Ce que la session suivante doit faire, dans l'ordre

0. **Vérifier l'état réel** : `.git/logs/refs/heads/main`, et l'UBR Windows
   (§ 4) avant de compter sur `device_bash`.
1. **`PERFORMANCE.md` § 5, point 3 — les DATES, 118 ms.** C'est le plus gros
   thème restant (`enrichir.dates` 86 + `enrichir.faits.regle.date` 32).
   `epoch_precis` rend le **minimum** du `taken` et de la date du NOM ;
   `date_et_source` rend le `taken` **en priorité** : règles DIFFÉRENTES sur
   les MÊMES deux lectures. Passer `_ep` à la seconde serait un défaut muet —
   ce qui se partage, ce sont les lectures. **Commencer par le banc** qui
   compare `server._fname_time` et `renommage_facts.fname_datetime` sur un
   corpus : « miroir déclaré » n'est pas « miroir mesuré ». Ensuite `motifs`
   (67 ms, la dernière post-passe qui relit `STORE.data` par photo) et le
   `Path(...)` de `_resolve_key` (48 ms, mémoïsable).
2. **B5 — le tri des dépôts, à voir à l'usage** : le mur de 7 jours est-il le
   bon, faut-il un geste groupé pour les 248 hérités ? Ne rien changer avant
   que Mike s'en soit servi une fois.
3. **Les 13,5 Go d'Ollama** : rien pendant la campagne (choix de Mike du
   12/09). Après : un modèle qui tient dans les 4 Go de VRAM (`vision-eval`).

---

## 4. Les pièges

- **Windows : KB5124008 (26200.9445) casse Plan9**, donc `device_bash`.
  Reconnu par Microsoft et Anthropic, correctif annoncé « dans un cumulatif
  suivant ». La machine tourne en **UBR 9278**, Windows Update est **en pause
  jusqu'au 17.10**. `Get-HotFix` MENT sur ce sujet ; la vérité est
  `(Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion').UBR`.
  **Vers le 16.10** : masquer le KB (`IsHidden`) s'il est reproposé.
- **`device_bash` marche et le NAS est monté** dans la VM sous
  `$HOME/mnt/Photos` — `CLAUDE.md` dit encore le contraire. Les MESURES
  restent l'affaire de l'agent de banc : la VM n'a ni les latences de Windows
  ni le LAN.
- **Canaux** : écrire `rien`, puis l'ordre UNE fois, puis ATTENDRE que le
  canal repasse à `rien` avant de lire la sortie. Une sortie lue pendant
  qu'elle s'écrit répond sur le run d'AVANT — deux conclusions fausses de
  suite le 12/09.
- **Chrome** : le serveur se regarde par là, jamais par le navigateur intégré.
  La racine du NAS est `dir=1`, pas `dir=0`.
- **Comparer phase par phase**, et **CPU contre temps écoulé** : c'est ce qui
  a montré que `parcours` était de l'attente (15,6 ms de CPU pour 692).
- **Un banc peut être ROUGE sans que rien ne le lance** : `tests_pour`
  appariait par NOM seul. Depuis le 12/09 il lance aussi tout `test_*.py` dont
  le TEXTE cite un module touché — **63 bancs** étaient invisibles, dont 59
  citent `server.py`, et **CINQ étaient rouges** depuis des livraisons
  entières. Un `livrer` qui touche `server.py` lance donc beaucoup et dure
  plusieurs minutes : c'est voulu. Son seul trou est nommé,
  `git_agent.BANCS_A_LA_MAIN`.
- **Un banc qui lit le source par le TEXTE mesure une orthographe.** Les cinq
  rouges cherchaient `'jour': _jour_de(`, `_pkey(k).startswith(pref)`… — le
  sens n'avait pas bougé, l'écriture si. Réécrire sur l'ARBRE (`ast`), et se
  méfier d'un compte : deux d'entre eux annonçaient le mauvais NOMBRE.
- **`_banc_sortie.txt` porte son EN-TÊTE** (`# <banc>.py`, `# code 0 — 94 s`) :
  c'est LUI qui dit de quel run on lit la sortie. Le 12/09, deux lectures ont
  été attribuées au mauvais banc faute de la lire — et `test_cache_vignettes`
  dure 94 s, plus que la fenêtre d'attente qu'on croyait large.
- `server.py` : skill `monolith-surgery` ; UI : `photo-ui`.

---

## 5. Protocole (inchangé)

Éditer → redémarrer (`uptime_s` > 60 d'abord) → **observer en réel** →
`SESSION_COMMIT.txt` → `livrer` → **vérifier dans `.git/logs/refs/heads/main`**.

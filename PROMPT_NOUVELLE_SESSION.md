# Reprise — MediaLibrary, après la session du 12 septembre 2026

> **Ce fichier est ÉPHÉMÈRE.** Il décrit un état, pas des règles. Les règles
> vivent dans `CLAUDE.md`, le plan dans `ROADMAP.md`, les verdicts dans
> `eval/DECISIONS.md` et `docs/DECISIONS_OUTILLAGE.md`. **Les chiffres du
> chantier performance sont dans `PERFORMANCE.md`** (§ 3.13 à 3.16 pour la
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
intouchable**, fin attendue vers le **14/09**.

---

## 1. Livré le 12/09 — la page `/files` divisée par deux

`Photos Mike/2022`, 2 519 photos, récursif, réobservé en réel à chaque étape :

| | matin | soir |
|---|---:|---:|
| `parcours` | 715 ms | **8 ms** |
| `enrichir` (mode navigation) | 455 ms | 275 à 481 ms |
| `enrichir` (dès qu'un tag est coché) | 455 ms | **0,0 ms** |
| la page entière | 1 493 à 1 870 ms | **732 à 1 092 ms** |

Quatre gestes, chacun avec son banc et sa réobservation :

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

52 bancs verts sur la machine (20 + 18 + 14).

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
1. **`PERFORMANCE.md` § 5, point 3** — ce qui reste dans `_serve_gallery`, par
   ordre de poids : `enrichir` (275–481 ms de CPU), `index` (93–146 ms, c'est
   le § 3.8 écrit le 11/09 et jamais fait), `marques` et `motifs` (deux
   post-passes qui relisent `STORE.data` par photo).
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
- `server.py` : skill `monolith-surgery` ; UI : `photo-ui`.

---

## 5. Protocole (inchangé)

Éditer → redémarrer (`uptime_s` > 60 d'abord) → **observer en réel** →
`SESSION_COMMIT.txt` → `livrer` → **vérifier dans `.git/logs/refs/heads/main`**.

# Reprise — MediaLibrary, après la session du 13 septembre 2026

> **Ce fichier est ÉPHÉMÈRE.** Il décrit un état, pas des règles. Les règles
> vivent dans `CLAUDE.md`, le plan dans `ROADMAP.md`, les verdicts dans
> `eval/DECISIONS.md` et `docs/DECISIONS_OUTILLAGE.md`, les chiffres de
> performance dans `PERFORMANCE.md`.

---

## 0. Ce qui a changé pendant la nuit du 12 au 13

**La campagne de retag est FINIE.** C'est le fait qui commande toute la
session : elle bloquait le GPU, le prompt et la mémoire depuis le 05/09.

| | |
|---|---:|
| photos portant `qwen3.5:4b\|v3fr\|kb1` | **40 525 / 40 525** |
| abandons | **1** |
| vignettes de grille présentes | **40 525 — 100 %** (98 % manquaient le 11/09) |
| GPU | **0 %**, 3 773 Mo libres |
| RAM disponible | **5,2 Go (33 %)** contre 0,5 pendant |
| index | 44 665 entrées, 4 133 vidéos, 8 échecs |

**Trois contraintes tombent d'un coup** : le prompt redevient touchable, le GPU
est rendu, la machine ne pagine plus. La difficulté n'est plus d'attendre,
c'est de CHOISIR — `ROADMAP.md` section B les classe par valeur.

**Ce qui n'a pas bougé** : les **248 dépôts d'`Uploads`** attendent toujours
Mike (le plus vieux a 31 jours). C'est le seul point de la roadmap immobile.

---

## 1. Deux garde-fous ont tenu — vérifiés, pas supposés

- **L'élargissement FR→EN n'est pas mort en silence.** Le retag FR seul a vidé
  `kw_en` : **0 sur 40 525**, mesuré. Le dictionnaire appris est donc tombé à
  `appris: 0` et l'élargissement aurait disparu SANS UNE LIGNE D'ERREUR. Le gel
  du 05/09 le sert : `source: gelé`, **3 862 paires**. **Ne jamais « nettoyer »
  `dico_fr_en.json`** — c'est la seule copie de cette matière.
- **`exiftool -P`** : 40 000 XMP réécrits dans la nuit, aucune date de fichier
  détruite.

---

## 2. Ce que la session du 12/09 a livré (détail : git + `PERFORMANCE.md`)

Neuf livraisons, de `cb96ecf` à `0617ede`. La page `/files` d'un dossier de
2 519 photos : **1 493–1 870 ms → 544–763 ms**, en retirant **douze calculs
refaits** (§ 3.13 à 3.23). Il n'y a plus de gros caillou : `enrichir` reste
premier à 220 ms mais aucun de ses morceaux ne dépasse 55 ms, et ~90 ms vont à
fabriquer les 2 519 dictionnaires eux-mêmes.

**Le prochain gain est décidé** (Mike, 13/09) : **chargement à la demande** —
les ~300 premières fiches, le reste en scrollant. Ce que ça engage est écrit
dans `ROADMAP.md` § C3, et le piège y est nommé : **le tri et les filtres
restent faits par le SERVEUR**.

Trois outils neufs, qui servent au-delà de leur chantier :
`mesure_miroir_dates.py` (deux couples de lecteurs comparés sur les 44 966
fichiers du fonds), `test_miroir_dates.py`, `test_motifs_galerie.py`.

---

## 3. Ce que la session suivante doit faire, dans l'ordre

0. **Vérifier l'état réel AVANT de lire les docs** :
   `.git/logs/refs/heads/main`, `/api/maint/status` → `config.retag`, et l'UBR
   Windows (§ 4). Une doc décrit l'intention de la fin de session précédente,
   pas ce que Mike a fait après.
1. **`ROADMAP.md` section B** — elle est classée par valeur. Le bilan de la
   campagne (B1) et l'abandon (B4) se font à froid et ne coûtent rien ; le
   choix du modèle de vision (B2) engage une campagne entière.
2. **Ne pas toucher au prompt sans avoir posé la question** : le prompt EST la
   version du pipeline, une phrase ajoutée relance 40 000 photos et une nuit
   de GPU.
3. **Si Mike a trié ses dépôts** (A1), B8 s'ouvre : le mur de 7 jours est-il
   le bon, faut-il un geste groupé ?

---

## 4. Les pièges

- **Windows : KB5124008 casse Plan9**, donc `device_bash`. La machine tourne en
  **UBR 9278**, Windows Update est **en pause jusqu'au 17.10**. `Get-HotFix`
  MENT ; la vérité est
  `(Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion').UBR`.
  **Vers le 16.10** : masquer le KB s'il est reproposé.
- **`device_bash` marche, et le NAS est monté** dans la VM sous
  `$HOME/mnt/Photos` — mais la VM n'atteint pas le LAN : tout ce qui interroge
  le serveur passe par l'agent de banc ou par Chrome.
- **Canaux** : écrire `rien`, puis l'ordre UNE fois, puis ATTENDRE que le canal
  repasse à `rien`. Et **`_banc_sortie.txt` porte un EN-TÊTE** (`# <banc>.py`,
  `# code 0 — 94 s`) : c'est LUI qui dit de quel run on lit la sortie. Deux
  lectures ont été attribuées au mauvais banc le 12/09 faute de la lire.
- **Chrome, jamais le navigateur intégré.** La racine du NAS est `dir=1`, et
  `/files` prend `dir=<index>/<sous-chemin>`, pas un chemin absolu.
- **Un `livrer` qui touche `server.py` lance ~70 bancs et dure ~6 minutes** :
  c'est voulu (trois règles de sélection, dont le graphe des imports). Ne pas
  conclure à un blocage avant d'avoir attendu.
- **Un banc qui lit le source par le TEXTE mesure une orthographe.** Cinq
  étaient rouges depuis des livraisons entières. Écrire sur l'ARBRE (`ast`), et
  exclure la docstring avant d'y chercher un appel.
- **Comparer phase par phase**, et **CPU contre temps écoulé** : le total de la
  page varie de ±20 % avec la charge et ne juge rien.
- `server.py` : skill `monolith-surgery` ; UI : `photo-ui`.

---

## 5. Protocole (inchangé)

Éditer → redémarrer (`uptime_s` > 60 d'abord) → **observer en réel** →
`SESSION_COMMIT.txt` → `livrer` → **vérifier dans `.git/logs/refs/heads/main`**.

Et, après toute analyse : **la contre-vérifier** (règle 11) — la falsifier, pas
la confirmer ; prouver que la mesure est fraîche ; nommer ce qui n'est
qu'hérité d'une doc.

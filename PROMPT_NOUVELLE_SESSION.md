# Reprise — MediaLibrary, après la session PERFORMANCE du 11 septembre 2026

> **Ce fichier est ÉPHÉMÈRE.** Il décrit un état, pas des règles. Les règles
> vivent dans `CLAUDE.md`, le plan dans `ROADMAP.md`, les verdicts dans
> `eval/DECISIONS.md` et `docs/DECISIONS_OUTILLAGE.md`. **Tous les chiffres du
> chantier sont dans `PERFORMANCE.md`** — ce document n'en est que l'entrée.

---

## 0. La consigne de Mike

> « concentre toi sur la performance (toujours en attendant la fin du tagging).
> fais une analyse en profondeur, des tests utiles et intelligents »
> — puis, le 11/09 au soir : « sois le plus autonome possible, fais les tests,
> tu as accès aux folders et à Chrome ».

---

## 1. Ce qui commande toujours tout : la campagne de retag

Fin attendue vers le **14/09**. Le GPU est pris, le NAS disputé, **le prompt est
intouchable**. Une mesure prise pendant la campagne est une borne haute.

---

## 2. Ce qui a été livré le 11/09 — huit branches, toutes sur `main`

| Commit | Quoi | Observé en réel |
|---|---|---|
| `23c5dac` | horloge de PHASES dans la galerie | les 10 s froides d'hier ne reviennent pas |
| `825c4a2` | `_pkey` mémoïsé (chaînes) | `index` ~480 → ~140 ms ; carte des clés ~700 → 44 ms |
| `4ba4bfd` | `/api/pets/list` en une passe | 2,5 s → 0,29 s, réponse identique |
| `36d269c` | le tagueur écrit la vignette 512 au passage | 5–7 ms, mtime exact, image IA inchangée |
| `f30231c` | fil de fond des vignettes (après la campagne) | lot témoin 3/3 ; attend la file vide |
| `b63ff0b` | corbeille : un `stat` par panier, hors verrou | 4,2 s → ~1,2 s, réponse identique |
| `0680d44` | péage du GIL : minuteur Windows + bascule à 1 ms | corbeille 2,3 s → 1,0–1,7 s ; tagging inchangé |
| `8d3b183` | `_pkey` des `Path` + phases de la carte | `/api/geo` 0,9 → 0,57 s |

Mesures qui ont décidé : **98 % des photos sans vignette de grille** ; une
fabrication = 78 % de lecture NAS ; **un `stat` attend ~15 ms dès qu'un fil de
calcul Python tourne** (pas du minuteur Windows) — jamais de bascule sous 1 ms
(débit CPU à 16 %).

---

## 3. Ce que la session suivante doit faire

0. **Quand la campagne finit** : `/api/serveur` → `vignettes` doit passer de
   `attend la fin du tagging` à `fabrique`, et `a_faire` descendre (~39 000).
   Puis `mesure_couverture_vignettes.py` (sur une copie fraîche de la base)
   pour le compte ferme.
1. **`/api/maint/status`** (0,3–0,4 s, page /reglages) : poser les phases
   d'abord. Suspects : les balayages de l'index (`len(STORE.data)` sur la vue,
   `tagged_count`, `_tagging_pipe_counts`, `_retag_etat`) et les JSON de
   `docs/` relus à chaque appel — **pas forcément `nvidia-smi`**, que
   `hw_state` garde déjà 8 s.
2. **Le reste de la galerie** : ~140 ms de vue dans `index` ;
   `_pkey(Path(UPLOAD_DIR).resolve())` fait un aller-retour SMB à chaque appel.
3. **HTTP/1.1** — l'instrument `Content-Length` d'abord, le drapeau ensuite.
4. **`Last-Modified` sur les médias.**

---

## 4. Les pièges

- **`device_bash` hors service** depuis la mise à jour Windows du 08/09 :
  éditer et tester dans la sandbox, écrire par le pont, **vérifier par `sha1`**
  après re-staging (le pont a encore rendu une version périmée le 11/09).
- **Canaux** : fichiers CRLF préparés dans `outputs/canal/`, deux écritures,
  puis vérification. L'agent git ignore la seconde écriture d'un même ordre
  (« pas de titre » : `SESSION_COMMIT.txt` a déjà été consommé) — sans effet.
- **Chrome** : onglet caché → un JavaScript de plus de 45 s expire ; une mesure
  par appel. Une URL à paramètres dans le résultat est bloquée : ne renvoyer
  que des chiffres. Onglets du groupe MCP qui changent d'id : relire le contexte.
- **Comparer phase par phase, jamais les totaux** : le NAS varie du simple au
  triple d'une heure à l'autre pendant la campagne.
- `server.py` : skill `monolith-surgery` ; UI : `photo-ui`.

---

## 5. Protocole (inchangé)

Éditer → redémarrer (`uptime_s` > 60 d'abord) → **observer en réel**
(`/api/serveur` `code_a_jour`, `/api/perf` et ses `derniers`, le journal) →
`SESSION_COMMIT.txt` → `livrer` → **vérifier dans `.git/logs/refs/heads/main`**.
Branches `feat|fix|chore|docs|test/…` ; `.bat` en ASCII pur.

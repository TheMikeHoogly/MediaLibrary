# Reprise — MediaLibrary, après la session du 12 septembre 2026 au matin

> **Ce fichier est ÉPHÉMÈRE.** Il décrit un état, pas des règles. Les règles
> vivent dans `CLAUDE.md`, le plan dans `ROADMAP.md`, les verdicts dans
> `eval/DECISIONS.md` et `docs/DECISIONS_OUTILLAGE.md`. **Les chiffres du
> chantier performance sont dans `PERFORMANCE.md`** (§ 3.13 pour la galerie,
> § 5 pour l'ordre).

---

## 0. La consigne de Mike

> « concentre toi sur la performance (toujours en attendant la fin du
> tagging). fais une analyse en profondeur, des tests utiles et intelligents »
> — « sois le plus autonome possible, fais les tests, tu as accès aux folders
> et à Chrome ».

La campagne de retag commande toujours tout : GPU pris, **prompt
intouchable**, fin attendue vers le **14/09**.

---

## 1. Livré le 12/09 au matin

**`_serve_gallery` : trois redites, la moitié du temps de la page.** Aucune ne
calculait rien de neuf (détail et tableaux : `PERFORMANCE.md` § 3.13).

| | avant | après |
|---|---:|---:|
| `parcours` (le dossier énuméré DEUX fois en récursif) | 715 ms | **378 ms** |
| `enrichir.dossier` (le lien de dossier calculé par PHOTO) | 69 ms | **46 ms** |
| `enrichir.dates` (la date précise demandée DEUX fois) | 108 ms | **90 ms** |

Réobservé en réel, même page (2 519 photos), 5 chargements, campagne en cours.
Les QUATRE branches qui remplissent `file_data` passent par les mêmes portes
(`_lien_dossier_memo`, `_best_time_depuis`, `_jour_depuis`) — pas seulement
celle qui avait été mesurée. 32 bancs verts sur la machine.

---

## 2. L'état de la machine — Windows, et ce qui a failli tout casser

**KB5124008 (26200.9445) casse Plan9**, donc `device_bash`. C'est reconnu par
Microsoft ET par Anthropic, le correctif est annoncé « dans un cumulatif
suivant » (octobre, probablement). Au 12/09 : Mike l'a désinstallé, la machine
tourne en **UBR 9278**, DISM ne porte aucun paquet 5124008, `device_bash`
marche. **Windows Update est en pause jusqu'au 17.10.**

- `Get-HotFix` MENT sur ce sujet (journal d'historique) : la vérité est
  `(Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion').UBR`.
- Le masquage du KB (`IsHidden`) n'a pas pu être posé : pause active, donc
  rien n'est proposé, donc rien à masquer. **À refaire vers le 16.10**, si le
  cumulatif d'octobre n'a pas corrigé Plan9.

---

## 3. Ce que la session suivante doit faire, dans l'ordre

0. **Vérifier l'état réel** : `.git/logs/refs/heads/main` doit porter le
   commit de la galerie — une doc décrit une intention, git dit ce qui est
   fusionné. Et l'UBR (ci-dessus) avant de compter sur `device_bash`.
1. **`PERFORMANCE.md` § 5, point 3** : ce qui reste dans `_serve_gallery`, par
   ordre de poids. `parcours` (378 ms) est de l'attente SMB pure — pour
   descendre il faut un **cache de listage de dossier**, donc une décision de
   Mike sur la fraîcheur (une photo déposée à l'instant apparaîtrait avec un
   retard). `index` (125 ms) est le § 3.8, déjà écrit et jamais fait.
2. **La reconstruction de `_key_index`** : 620 à 870 ms **VERROU TENU**, une
   fois par minute (TTL). Pendant ce temps toute vignette qui vérifie sa
   visibilité attend. Bâtir hors verrou puis publier sous verrou, avec une
   génération pour ne pas écraser une invalidation — et garder l'invalidation
   EXPLICITE synchrone (un renommage ne doit pas servir une clé morte).
3. **Les 13,5 Go d'Ollama** : rien à faire pendant la campagne (choix de Mike
   du 12/09). Après : un modèle qui tient dans les 4 Go de VRAM (`vision-eval`).

---

## 4. Les pièges

- **`device_bash` marche** (12/09) et **le NAS est monté** dans la VM sous
  `$HOME/mnt/Photos` — nouveau, `CLAUDE.md` dit encore le contraire. Les
  MESURES, elles, restent l'affaire de l'agent de banc : la VM n'a ni les
  latences de Windows ni le LAN.
- **Un banc qui parse `server.py` fonction par fonction avec
  `ast.get_source_segment` met 95 s** là où un découpage par lignes en met 1.
  `test_galerie_enrichissement.py` en garde la trace — et reste lent pour une
  raison NON trouvée : à chercher si le banc gêne.
- **Canaux** : un ordre écrit DEUX fois relance le banc deux fois ; écrire
  `rien`, puis l'ordre UNE fois, puis ATTENDRE que le canal repasse à `rien`
  avant de lire la sortie — un banc de 95 s lu au bout de 30 en rend un vieux.
- **Chrome** : le serveur se regarde par là, jamais par le navigateur intégré.
  La racine du NAS est `dir=1`, pas `dir=0`.
- **Comparer phase par phase**, et **CPU contre temps écoulé** : c'est ce qui
  a montré que `parcours` était de l'attente (15,6 ms de CPU pour 692).
- `server.py` : skill `monolith-surgery` ; UI : `photo-ui`.

---

## 5. Protocole (inchangé)

Éditer → redémarrer (`uptime_s` > 60 d'abord) → **observer en réel** →
`SESSION_COMMIT.txt` → `livrer` → **vérifier dans `.git/logs/refs/heads/main`**.

# Reprise — MediaLibrary, session PERFORMANCE (11 septembre 2026, suite)

> **Ce fichier est ÉPHÉMÈRE.** Il décrit un état, pas des règles. Les règles
> vivent dans `CLAUDE.md`, le plan dans `ROADMAP.md`, les verdicts dans
> `eval/DECISIONS.md`, `eval/DECISIONS_UI.md`, `eval/DECISIONS_TAGGING.md` et
> `docs/DECISIONS_OUTILLAGE.md`. **L'analyse de performance complète, avec tous
> les chiffres, est dans `PERFORMANCE.md`** — ce document-ci n'en est que le
> point d'entrée. Si ce fichier contredit un carnet, **le carnet a raison**.

---

## 0. La consigne de Mike, mot pour mot

> « concentre toi sur la performance (toujours en attendant la fin du tagging).
> fais une analyse en profondeur, des tests utiles et intelligents et prépare
> la future session qui consistera à augmenter les performances de notre
> application dans tous les domaines. »

**« dans tous les domaines » ne veut pas dire « partout à la fois ».** La seule
manière d'y arriver est de mesurer, corriger le plus gros, **re-mesurer**, et
laisser le nouveau classement décider de la suite. Le premier tour l'a déjà
prouvé : le point n° 1 du 10/09 a été corrigé, et le classement du 11/09 n'a
plus la même tête.

---

## 1. Ce qui commande toujours tout : la campagne de retag

Elle tourne depuis le 05/09. Fin attendue autour du **14/09**.

- Le GPU est pris : tout banc qui appelle Ollama avec un autre modèle attend.
- **Le prompt est intouchable** — il EST la version du pipeline (`v3fr`). Y
  toucher rouvrirait les ~12 000 photos déjà refaites.
- Le NAS est disputé. **Une mesure prise pendant la campagne n'est pas une
  mesure prise à vide** : l'écrire à côté du chiffre, toujours.

Ce chantier-ci est compatible : il touche le **chemin de service** (routes
HTTP, parcours de dossier, caches), jamais le calcul IA.

---

## 2. Ce qui a été fait, et qui est sur `main`

**L'horloge des routes** (`feat/horloge-des-routes`, 10/09) : chaque requête
comptée dans `do_GET`/`do_POST`, `_perf_routes.json` à chaque cycle de
maintenance, `/api/perf` à la demande, `mesure_routes.py` pour classer.

**`_lister_dossier` en `os.scandir`** (`fix/parcours-dossier-scandir`, 10/09).

**L'horloge de PHASES dans `_serve_gallery`** (`feat/horloge-de-phases-galerie`,
11/09 matin). `/api/perf` rend maintenant `phases` (agrégat) et `derniers` (les
20 dernières ouvertures, phase par phase, **sans nom de dossier**). Page rendue
prouvée identique par l'arbre syntaxique ; 15 bancs dans
`test_horloge_phases.py`.

**`_pkey` mémoïsé sur les chaînes** (`fix/deux-balayages-par-clic`, 11/09
matin). `index` 393–772 → **137–156 ms** par clic ; reconstruction de
`_key_index` (TTL, verrou tenu) 618–784 → **44 ms**. Règle inchangée, prouvée
sous `PureWindowsPath` ; 10 bancs dans `test_pkey_memoire.py`.

**`/api/pets/list` en une passe** (`fix/sujets-en-une-passe`, 11/09 matin).
2,3–2,5 s → **~290 ms**, réponse identique au caractère près. Le repli de
`people_list` suit la même fonction. Oracle verbatim sur 300 tirages dans
`test_sujets_une_passe.py`.

**La vignette de grille écrite par le tagueur** (`feat/vignette-du-tagueur`,
11/09 soir, choix de Mike). Mesuré avant : **98 % des photos sans vignette**,
78 % d'une fabrication = lecture NAS. Observé après : chaque retag laisse sa
vignette, au mtime exact, servie en 5–7 ms. Image envoyée à l'IA inchangée
(banc). Bancs de mesure : `mesure_couverture_vignettes.py`,
`mesure_fabrication_vignette.py`.

**Le fil de fond des vignettes** (`feat/vignettes-de-fond`, 11/09 soir) : fabrique
le reste quand la file de tagging est vide, cède à l'UI, 20 Go de plancher.
Lot témoin au démarrage : 3/3 en 2,2 s. État dans `/api/serveur` → `vignettes`.

**`/api/corbeille` hors verrou** (`fix/corbeille-hors-verrou`, 11/09 soir) : un
`stat` par panier au lieu de trois, et seul l'instantané du journal reste sous
`FILE_OPS_LOCK`. 4,2 s → 0,9–2,1 s, réponse identique.

**Le péage du GIL** (`fix/peage-du-gil`, 11/09 soir) : minuteur Windows à 1 ms
et bascule à 1 ms au démarrage. Un `stat` sous charge CPU : 6–37 ms → 1,4–4,1 ms
au banc ; corbeille réelle 2,3–2,5 s → 1,0–1,7 s. **Jamais sous 1 ms** (débit
CPU à 16 %).

---

## 3. Le résultat, honnêtement

Huit ouvertures de `/files` relevées le 11/09 entre 08:15 et 08:18 (tableau
complet : `PERFORMANCE.md` § 2 bis) :

- **Les 10,2 s froides d'hier ne sont pas revenues** : 0,6 à 4,1 s. Pas
  d'explication mesurée ; l'horloge reste posée, `derniers` dira la phase si
  ça se reproduit chez Mike.
- **Le vrai coût est ailleurs** : deux balayages de TOUTE la photothèque à
  chaque clic, quelle que soit la taille du dossier — `index`
  (`_index_entries_under`, 378–772 ms, même pour 23 photos) et `carte_cles`
  (`_key_index`, 618–784 ms dès que son TTL de 60 s a expiré).
- Le parcours froid existe encore (2020 : 2,6 s pour 1 084 photos, 2,4 ms par
  fichier — dix fois mieux qu'avant, mais c'est le réseau).
- L'enrichissement (~0,18 ms/photo), le JSON, le gabarit et l'envoi sont
  petits.

---

## 4. L'ordre pour la suite

Détail et précautions : `PERFORMANCE.md` § 5.

0. **Quand la campagne finit (~14/09)** : `/api/serveur` → `vignettes` doit
   passer à `fabrique` et `a_faire` descendre (~39 000) ; relancer
   `mesure_couverture_vignettes.py` pour le compte ferme.
1. ~~Le péage du GIL~~ — réglé (`PERFORMANCE.md` § 3.9). Si un fil de calcul
   semble ralenti, regarder `/api/serveur` → `gil` et relancer
   `mesure_peage_gil.py` : le plancher d'1 ms ne se franchit pas.
2. **`/api/geo`** — re-mesurer, puis cache.
3. **`nvidia-smi`** — le mesurer d'abord.
4. **HTTP/1.1** — l'instrument `Content-Length` d'abord.
5. **`Last-Modified` sur les médias.**

---

## 5. Les pièges qui coûtent du temps

**`device_bash` est CASSÉ depuis le 11/09 au matin** — « A Windows update
released September 8 prevents Claude's workspace from reaching your files ».
Staging et commit marchent ; le shell sur le PC, non. Conséquences : éditer et
tester **dans le sandbox** (les bancs AST s'y lancent tels quels), écrire les
canaux **par `device_commit_files`** (`printf 'redemarrer\r\n'` dans un
fichier de `/mnt/user-data/outputs/`, deux écritures, puis vérification), et
contrôler une écriture par **empreinte** : re-stager et comparer le `sha1`,
plus sûr que la taille. Le 11/09, les quatre fichiers livrés étaient justes du
premier coup.

**`/api/perf` lu par Claude in Chrome** : un résultat JavaScript qui contient
une URL à paramètres est bloqué (« Cookie/query string data »). Ne renvoyer
que des chiffres.

**Le pont écrit une version PÉRIMÉE du fichier.** Une quinzaine de fois en deux
jours. **Parade systématique** : après chaque `device_commit_files`,
re-committer une seconde fois, puis **vérifier la TAILLE** par un listing de
dossier. Pour un fichier de canal, écrire `rien` d'abord — une reprise périmée
écrira alors `rien`, ce qui est sans effet. Le 10/09, `SESSION_COMMIT.txt` a
demandé **trois** écritures.

**Le banc refuse les espaces dans un argument.** `--dossier "Photos Mike/2022"`
est rejeté ; il faut le jeton `b64:` suivi du base64url du texte UTF-8 —
`--dossier b64:UGhvdG9zIE1pa2UvMjAyMg`.

**Un instrument qui écrit périodiquement doit dire QUAND.** Le 10/09,
`_perf_routes.json` a semblé absent : le banc l'a cherché 2 min 40 avant le
premier cycle de maintenance. Ce n'était pas une panne.

**Ne jamais réécrire un `.bat` pendant qu'il tourne.** `cmd.exe` reprend à
l'octet mémorisé : +70 octets lui font exécuter un fragment de ligne.

**Une assertion peut lire un COMMENTAIRE au lieu du code.** Assertir sur
l'appel, par l'AST.

**Un instrument qui se lit lui-même se donne toujours raison.** Et une liste
blanche ne compte jamais les absents — c'est ce qui a fait passer verte, le
10/09, une correction posée sur deux chemins d'écriture sur trois.

**Le banc n'a pas de session HTTP.** Un banc lancé par l'agent est renvoyé sur
`/connexion`. Pour une vraie observation : passer par le navigateur connecté de
Mike (Claude in Chrome), pas par le volet intégré — celui-ci classe
`192.168.0.13` comme site à risque et ne donne l'accès qu'une action à la fois.

---

## 6. Ce que j'attends de Mike

1. **Relancer le bat 50** quand il passe par là (47 fichiers, 34,8 Mo ;
   répondre **2** à l'étape 3).
2. **Lancer le bat 51** — `face_thumbs` + `animal_thumbs`, 32 458 fichiers,
   227 Mo. C'est un arriéré, pas une corvée qui revient.
3. **Le bat 43 puis le bat 24** pour les Motion Photos (~9,27 Go).
4. **Vider `_corbeille_menage\` à la main**, dans quelques jours.
5. **Lire la page `/aide`** — ce n'est pas une tâche, c'est un jugement.

Rien de tout cela ne bloque le chantier performance.

---

## 7. Rappels de protocole qui ne changent pas

- **Éditer → redémarrer → OBSERVER EN RÉEL → livrer.** « Observer » veut dire
  regarder la chose elle-même : la page dans le navigateur, `/api/perf`, le
  journal. Pas le rapport d'un agent.
- **Git ne se lance jamais depuis la VM.** On écrit `livrer` dans
  `_commande_git.txt`. **Vérifier dans `.git/logs/refs/heads/main`, jamais dans
  son rapport.**
- Branches : `feat|fix|chore|docs|test/nom-en-minuscules`. **`perf/` est
  refusé** — un chantier de performance livre en `fix/` ou `feat/`.
- Les `.bat` sont en **ASCII pur**, **CRLF**, contrôlés par `verifier_bat.py`.
- `SESSION_COMMIT.txt` en ASCII pur : `branche=` puis `titre=`.
- `server.py` : lire la skill `monolith-surgery` avant d'y toucher ; toute UI
  passe par `photo-ui`.
- Les bancs `mesure_` ne lisent **jamais** `photos.db` — le serveur l'a
  ouverte. Ils travaillent sur `copie.db` ou sur un dossier temporaire.

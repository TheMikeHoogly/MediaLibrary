# Reprise — MediaLibrary, session PERFORMANCE (11 septembre 2026)

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

**L'horloge des routes** (`feat/horloge-des-routes` → `743fef9`). Elle compte
chaque requête dans les enveloppes de `do_GET`/`do_POST`, replie les routes à
argument, ne lève jamais, et dépose `_perf_routes.json` à chaque cycle de
maintenance. `/api/perf` le rend à la demande. `mesure_routes.py` le classe.
16 bancs dans `test_horloge_routes.py`.

**`_lister_dossier`** (`fix/parcours-dossier-scandir` → `8eba291`). `os.scandir`
au lieu de `iterdir()` + un `stat()` par fichier ; `os.walk` avec élagage dans
`dirs[:]` en récursif. 16 bancs dans `test_parcours_dossier.py`, dont deux qui
**comptent les appels à `os.stat`** et deux qui relisent `server.py` par l'AST
pour vérifier que l'ancien chemin a bien disparu. L'ancienne implémentation est
gardée **dans le fichier de test** et sert d'oracle.

**`mesure_parcours_dossier.py`**, le banc qui a tranché : sur `Photos
Mike/2022` (2 465 photos, SMB), **26,05 s → 308 ms**, facteur 84.

---

## 3. Le résultat, honnêtement

| | avant | après |
|---|---:|---:|
| `/files` **à froid** | 31,4 s | **10,2 s** |
| `/files` **à chaud** | 1,35 s | ~1,6 s |

**Le banc promettait 84×, la page a rendu 3×.** Les deux chiffres sont justes,
et l'écart est la chose la plus utile apprise ce soir :

- les **21 secondes** gagnées sur le chemin froid sont bien celles du parcours ;
- les **~10 s qui restent** sont l'enrichissement des 2 465 photos, le balayage
  de l'index et la sérialisation du JSON — que je n'avais pas mesurés, et que
  j'avais supposés petits ;
- **à chaud rien n'a bougé**, parce que Windows gardait déjà les métadonnées du
  répertoire : l'ancien code n'était catastrophique que sur un dossier pas vu
  depuis un moment. C'est-à-dire exactement le geste de quelqu'un qui cherche
  une photo.

> **La règle qui sort de là** : un banc qui isole un morceau prouve le gain de
> ce morceau, pas celui de la page. Il faut les deux mesures, et c'est la
> seconde qui décide.

---

## 4. L'ordre pour cette session

Le détail, les chiffres et les précautions de chaque point sont dans
`PERFORMANCE.md`. Résumé :

1. **Horloge de phases dans `_serve_gallery`.** Cinq `perf_counter` au même
   patron que l'horloge des routes, rendus dans le même fichier. ~10 s froides
   à expliquer : **tout le reste de cette liste est plus petit que ce qu'on
   ignore.**
2. **Compter les vignettes manquantes.** `/api/thumb` est le nouveau premier du
   classement (35 requêtes, 62,9 s, **28 au-dessus d'une seconde**). Si le fonds
   est mal couvert, la piste est que **le tagueur écrive la vignette au
   passage** — il ouvre déjà la photo. Mesurer d'abord, décider ensuite.
3. **`/api/pets/list`** — 2,87 s pour une boucle sur 17 chats **imbriquée dans
   un balayage des 40 584 entrées**. Une seule passe suffit. Meilleur
   gain/risque de la liste ; `/api/people/list` est de la même famille.
4. **`/api/corbeille`** — 4,88 s **sous `FILE_OPS_LOCK`**. D'abord le banc de
   parcours (même mal que `/files` ?), ensuite seulement la question du verrou,
   et uniquement si la raison pour laquelle il a été posé là est comprise.
5. **`/api/geo`** — 993 ms, agrégat de toute la photothèque reconstruit à chaque
   ouverture de la carte. Instantané en cache, patron `_key_index`.
6. **`nvidia-smi`** — `hw_state()` lance un sous-processus ; les quatre appels à
   `/api/maint/status` ont tous mis entre 300 ms et 1 s. Le chronométrer seul,
   GPU occupé puis libre, avant de toucher au cache.
7. **HTTP/1.1.** Le serveur parle HTTP/1.0 : une connexion TCP par vignette.
   **Ne pas poser le drapeau sans l'instrument** — une réponse sans
   `Content-Length` en HTTP/1.1 suspend la page au lieu de la ralentir.
   `verifier_content_length.py` (par l'AST) d'abord.
8. **`Last-Modified` + `304` sur les médias.** Revenir sur une photo de 5 Mo la
   retélécharge entièrement depuis le NAS.
9. **Reclasser** avec le relevé suivant. La planche entière en un seul JSON
   (§ 3.7 de `PERFORMANCE.md`) et `_pkey` (§ 3.8) attendent ce reclassement :
   leur place d'aujourd'hui a été calculée sur une page qui mettait 31 s.

---

## 5. Les pièges qui coûtent du temps

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

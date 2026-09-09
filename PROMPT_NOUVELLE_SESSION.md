# Reprise — MediaLibrary, au soir du 9 septembre 2026

> **Ce fichier est ÉPHÉMÈRE.** Il décrit un état, pas des règles. Les règles
> vivent dans `CLAUDE.md`, le plan dans `ROADMAP.md`, les verdicts dans
> `eval/DECISIONS.md`, `eval/DECISIONS_UI.md`, `eval/DECISIONS_TAGGING.md` et
> `docs/DECISIONS_OUTILLAGE.md`. Si ce fichier contredit un carnet, **le carnet
> a raison** : lui a été relu, celui-ci a été écrit vite.

---

## 1. Ce qui commande tout : la campagne de retag

Elle tourne depuis le 05/09 (`retag_actif.txt` posé). Au 08/09 au matin,
compté **dans le journal** heure par heure : **~190 photos/heure**, 16 s
médian, **~27 800 restantes** → environ six jours, donc autour du **14/09**.

**Trois conséquences, et elles ferment des portes :**

- Le GPU est pris. Tout banc qui appelle Ollama avec un autre modèle est à
  reporter.
- **Le prompt est intouchable.** Le prompt EST la version du pipeline
  (`v3fr`) : y ajouter une phrase rendrait candidates les ~12 000 photos déjà
  refaites. La question au tagueur sur les documents sensibles n'est donc pas
  « reportée par prudence », elle est **empêchée**.
- Les optimisations O8, O9, O14 et O15 touchent des boucles de calcul : après
  la campagne.

Lire l'avancement : `/api/maint/status` → `config.retag`. **Compter dans le
journal, ne pas diviser une durée par 24 h** — c'est ce qui a fait annoncer
4 jours là où il en restait 6.

---

## 2. Ce qui s'est fait le 09/09 — dix-sept livraisons

Vérifiées une par une dans `.git/logs/refs/heads/main`, jamais sur le rapport
de l'agent.

**Le Takeout Google est CLOS.** Le bat 49 est passé de bout en bout : cinq
contrôles, l'étape 3 bis qui a jugé les **14 absentes jetables** (moitiés
vidéo de Motion Photos sans extension, deux preuves chacune), le `EFFACER`
écrit en toutes lettres. **C: de 171,2 à 236 Go libres sur 932.** Plus de
Takeout, ni zip ni extrait.

**Le chantier 18 est clos pour l'essentiel.** Mike a trié les 213 photos
sensibles : 60 à la corbeille, 7 en privé, le reste rendu à la galerie. **Il
en reste UNE** (`Photos Flo\Appartement Bremblens\20210630_200127.jpg`).

**Deux défauts trouvés en le regardant faire**, tous deux corrigés et observés
en réel :
- l'onglet se rechargeait depuis le haut après chaque verdict — invivable sur
  213 fiches, invisible à la relecture ;
- l'API ressuscitait **67 dossiers déjà clos** (68 annoncées là où il y en
  avait 1) parce que le drapeau `sensible` survit au déménagement d'une photo.

**La roadmap redevient une carte** : 108 881 → 31 871 octets, de 87 % à 25 %
du budget. Le récit des travaux finis est sorti du carnet et vit dans git.

**Trois lignes d'audit fermées sans une ligne de code** : `animal:luna`
(personne ne lit la casse de ce tag), et l'adoption de `components.css` par
`reglages`, `browse` et `faces` (la première avait raison, la deuxième était
conforme, la troisième n'est plus servie).

**Deux gains mesurés** : la compression HTTP (O11) — `/files` 157 → 48 ko,
`/pets` 88 → 29 ko, lu sur le fil — et le bouton « Annuler » du bandeau, qui
était à **1,02:1**, du noir sur du noir, sur le seul contrôle qui rattrape une
mise à la corbeille.

**Deux instruments neufs** : `inventaire_fichiers_orphelins.py` (qui lit quoi)
et `appliquer_menage.py` + **bat 50**, où la politique propose et l'inventaire
oppose son veto.

---

## 3. Le ménage est fait — et l'angle mort avait CINQ portes

**Bat 50, second passage, 21:27 : 506 fichiers déplacés, 49,3 Mo**, manifeste
dans `_corbeille_menage\20260909_212726\`, réversible par `--annuler`. Le
premier passage n'en avait déplacé que 14 et **retenu 810** — ce déséquilibre
était le vrai résultat de la journée.

Le veto (« un fichier que l'inventaire n'a pas vu est retenu : ne pas savoir
n'est pas savoir que non ») a fait exactement son travail à chaque fois. C'est
`inventaire_fichiers_orphelins.py` qui était aveugle, **et il l'était par cinq
portes différentes**, corrigées et remesurées une par une :

| # | La porte | Ce qu'elle cachait |
|---|---|---|
| 1 | filtre d'**extension** — `_fichiers()` ne rendait que du texte | tous les binaires : `.pyc`, `.jpg`, `.b64`, `.jsonl` |
| 2 | élagage de **dossier** — `__pycache__` dans `IGNORES` | 122 `.pyc` de plus, invisibles *après* le correctif 1 |
| 3 | élagage **par nom nu, à toute profondeur** | **579 des 800 fichiers de `_to_delete\`** |
| 4 | le **nettoyeur** compté comme lecteur de ses propres cibles | `_rapport_perdus_takeout.json`, `_rapport_sef_avant.json` |
| 5 | l'**instrument lui-même**, via les commentaires du correctif | les quatre fichiers dont je venais d'écrire l'histoire |

**La porte 3** est la leçon d'ingénierie : `_corbeille_session` désignait la
corbeille **vivante**, à la racine, mais comparé au nom **nu** il faisait aussi
taire la corbeille **morte** archivée dans la quarantaine. *Une protection qui
vise un dossier particulier doit nommer sa **place**, pas seulement son nom.*
Même défaut sur `JAMAIS_ORPHELIN`, qui protégeait une copie de `photos.db` de
283 Mo. Les deux sont ancrés à la racine (`IGNORES_RACINE` / `IGNORES_PARTOUT`).

**La porte 5 est la leçon de méthode, et elle est humiliante :** en écrivant
dans les commentaires du correctif *pourquoi* `_rapport_google_apres2.json`
avait été protégé à tort, j'ai fait de l'instrument son lecteur. Au passage
suivant, mesuré, les quatre fichiers étaient de nouveau `LU PAR DU CODE` — lus
par l'outil qui venait d'expliquer que personne ne les lisait. **Écrire
l'histoire d'une erreur la refaisait.** La règle est maintenant écrite une
bonne fois : *rien de la chaîne de ménage n'est un lecteur* — ni l'instrument,
ni son banc, ni le nettoyeur, ni le sien, ni leurs rapports, ni leurs
manifestes. **Un outil qui juge ne témoigne pas.**

Et la leçon qui les relie toutes : **réparer la porte 1 ne suffisait pas, et
je m'étais déclaré content.** Ce qui a rendu chaque porte suivante visible,
c'est le compteur de fichiers parcourus imprimé en tête du rapport —
719 → 3 761 → 3 883 → 4 465 → 3 944 (la dernière baisse est saine : la
corbeille du ménage n'est plus reparcourue). *Quand on corrige un angle mort,
on cherche ses autres portes avant de se déclarer content.*

`test_inventaire_fichiers_orphelins.py` : **26 bancs**, au moins un par porte.

### Deux défauts du bat 50 lui-même, corrigés

- **L'étape 3 promettait un choix qu'elle ne pouvait pas tenir.** Mike a
  répondu « 2 » (journaux > 30 j) et lu « Rien à déplacer » — **35 des 44
  journaux sont `LU PAR UN MOTIF`**, forcément : `undo_*.json` EST le motif.
  Le veto ne pouvait rien laisser passer. Pour cette famille seule, le jugement
  vient désormais de l'**âge**, que Mike fournit et qui est plus fort ;
  `LU PAR DU CODE` reste un veto (`docs/plan_rangement.json` est lu par les
  bats 26 et 39). *Une option de menu qui ne peut jamais rien faire est une
  promesse que l'outil ne tiendra pas.*
- **`_rapport_google_apres2.json` déclaré mort par Mike.** Réglé sans liste
  d'exception : le bat 33 le nommait dans un `REM` **pour dire qu'il avait
  cessé de le lire**, et sa ligne 105 `echo`ait un exemple nommant
  `_rapport_google_apres.json`. Les deux mentions retirées du bat, la leçon
  gardée. L'instrument distingue maintenant `REM`, `::` et `echo` non redirigé
  (mais **pas** `echo x > fichier`, qui écrit pour de bon — c'est le canal de
  commande de tout ce projet).

### Ce que le prochain bat 50 déplacerait — mesuré

| famille | fichiers | poids |
|---|---|---|
| journaux d'annulation (> 30 j) | 34 | 20,6 Mo |
| rapports périmés | 7 | 14,1 Mo |
| quarantaine, reliquat | 6 | 0,1 Mo |
| **total proposé** | **47** | **34,8 Mo** |

**Ce qui reste et qui ne bougera pas tout seul : 283 Mo dans un seul
fichier**, `_to_delete\menage_20260908\_avant_deplacement\photos.db`, la
copie de la base d'avant le ménage du 08/09. L'inventaire la range en
`LU PAR DU CODE` parce que le code cite `photos.db` partout et qu'il **ne peut
pas distinguer la base vivante de sa copie**. C'est une limite honnête, pas un
bogue : elle demande une décision de Mike, pas une règle de plus.

Enfin : `_corbeille_menage\` n'est **pas** vidée par le bat, et c'est voulu.
Quelques jours, puis à la main.

---

## 4. LE PLAN DE LA PROCHAINE SESSION — arbitré le 09/09 au soir

**Le cadre ne change pas : la campagne de retag tourne jusqu'au ~14/09.** Donc
pas de GPU, pas de prompt, pas de serveur arrêté. Ce plan ne contient que ce
qui vit sous cette contrainte, et il est ordonné : le premier point d'abord.

### P1 — Réviser `CLAUDE.md` et `MARCHE_A_SUIVRE.md` (le point le plus important)

**Ces deux fichiers n'ont pas été relus le 09/09, et je l'ai dit deux fois sans
le faire.** Ce sont les fichiers de RÈGLES : ce que la prochaine session lira
avant toute chose. Or la journée a produit exactement le genre de matière qui
doit y vivre, et qui aujourd'hui n'existe que dans un carnet éphémère :

1. **Un outil qui juge ne témoigne pas.** Cinq fois le même défaut, dont une
   fabriquée en documentant les quatre autres.
2. **Une protection doit nommer la place, pas seulement le nom.**
3. **Quand on corrige un angle mort, on cherche ses autres portes** — et le
   moyen de les voir est un compteur d'étendue imprimé à chaque passage.
4. **Ne jamais réécrire un `.bat` pendant qu'il tourne** (`cmd.exe` reprend à
   l'octet mémorisé).
5. **La parade au pont qui écrit une version périmée** : re-stager, comparer la
   TAILLE, re-committer. Coûté six fois dans la journée, et encore quatre fois
   le soir. C'est le défaut d'outillage le plus coûteux du projet et il n'est
   écrit nulle part dans les règles.

Objectif : que ces cinq règles soient dans `CLAUDE.md`/`MARCHE_A_SUIVRE.md`
avec leur mesure, et que ce qui y est périmé en sorte. **Zéro GPU, zéro NAS,
zéro serveur.** C'est aussi le meilleur usage d'une session pendant que la
machine calcule.

### P2 — Fermer le ménage

1. Relancer le **bat 50** : 47 fichiers, 34,8 Mo (dont les journaux, qui
   marchent enfin). Répondre « 2 » à l'étape 3.
2. **Décider des 283 Mo** : la copie de `photos.db` du 08/09. Question à Mike,
   pas règle à écrire.
3. Dans quelques jours, vider `_corbeille_menage\` à la main.

### P3 — L'audit, ce qui n'a pas besoin du GPU

- **O14 — `_reconcilier` re-hashe tout le store sous verrou à chaque
  `save()`.** C'est du chemin de service, pas du calcul IA : mesurable et
  réparable maintenant. **C'est le meilleur gain de perfomance restant.**
- **O15 — les caches de vignettes.** Même famille.
- O8 et O9 (matmul par visage, backfill sémantique) touchent des boucles de
  calcul : **après** la campagne, pas avant.

### P4 — À Mike, quand il veut

La dernière photo sensible ; lire la page `/aide` (chantier 17, étape 7 : ce
n'est pas une tâche, c'est un jugement — sa famille lira ce texte).

### P5 — Quand la campagne s'arrête (~14/09), et pas avant

La question au tagueur sur les documents sensibles (3 bis c) — **empêchée**,
pas reportée : toucher au prompt rouvrirait ~12 000 photos déjà refaites ; la
re-mesure des Motion Photos arrivées depuis le 03/09 (demande le serveur
arrêté) ; et le **bilan chiffré** de cette première passe officielle du fonds.

### En fin de projet — décision de Mike du 09/09

La copie hors site. Le fait qui ne se répète plus mais qui reste vrai : depuis
l'effacement du Takeout, **le NAS est le seul exemplaire des ~40 000 photos**.
Le jour venu, deux choses ensemble : choisir le fournisseur, **et** écrire le
banc qui prouve que la copie distante contient ce que le NAS contient.

---

## 5. Les pièges qui ont coûté du temps le 09/09

**Le pont écrit une version PÉRIMÉE du fichier.** Arrivé six fois dans la
journée, sur des `.md`, un `.py`, un `SESSION_COMMIT.txt` et deux
`_commande_*.txt`. Symptôme : l'agent refuse en citant une assertion qui passe
pourtant en local, ou un agent exécute un ordre qu'on croyait avoir remplacé.
**Parade, systématique** : après chaque `device_commit_files`, re-stager et
comparer la TAILLE. Si elle diffère, re-committer — la seconde tentative
passe. Le diagnostic par la taille coûte un aller-retour ; le chercher
ailleurs en coûte trois.

**Ne jamais réécrire un `.bat` pendant que Mike le lance.** `cmd.exe` rouvre
le fichier après chaque commande et reprend à l'octet mémorisé. Une
reformulation de +70 octets pendant l'exécution du bat 49 lui a fait exécuter
un fragment de ligne, d'où « Python est introuvable » puis un message
d'arrêt faux. Démontré en recalculant l'offset sur les deux versions.

**Une assertion peut lire un COMMENTAIRE au lieu du code.** Trois fois cette
semaine : `min-height:36px` trouvé dans le commentaire qui expliquait son
retrait, `Content-Length` trouvé dans une docstring. Assertir sur l'appel.

**Un instrument qui se lit lui-même se donne toujours raison.**
`inventaire_fichiers_orphelins.py` comptait sa propre sortie comme lecteur, et
sa première version rangeait toute la suite de tests en orphelins parce que
« cité par un nom » n'est pas « a un lecteur ».

**Le banc a besoin d'une session.** `verifier_pages_composants.py` lancé par
l'agent est renvoyé sur `/connexion` et ne prouve rien. Pour un vrai regard :
passer par le navigateur connecté de Mike et lire les styles **calculés**.

---

## 6. Ce que j'attends de Mike

1. **Une décision sur les 283 Mo** — la copie de `photos.db` dans
   `_to_delete\menage_20260908\_avant_deplacement\`. Elle est retenue par le
   veto et le restera : l'instrument ne peut pas distinguer la base vivante de
   sa copie. C'est un `del` manuel, ou rien.
2. **Un lancement du bat 50** quand il passe par là (47 fichiers, 34,8 Mo).
3. Rien d'autre. La campagne tourne toute seule.

---

## 7. Rappels de protocole qui ne changent pas

- **Éditer → redémarrer → OBSERVER EN RÉEL → livrer.** L'ordre n'est pas
  négociable, et « observer » veut dire regarder la chose elle-même : la page
  dans le navigateur, les styles calculés, le compte rendu par l'API.
- **Git ne se lance jamais depuis la VM.** On écrit `livrer` dans
  `_commande_git.txt` ; l'agent Windows vérifie, committe, pousse, fusionne.
  **Vérifier dans `.git/logs/refs/heads/main`, jamais dans son rapport.**
- Branches : `feat|fix|chore|docs|test/nom-en-minuscules`. `perf/` est refusé.
- Les `.bat` sont en **ASCII pur**, contrôlés par `verifier_bat.py`.
- `SESSION_COMMIT.txt` en ASCII pur : `branche=` puis `titre=`.

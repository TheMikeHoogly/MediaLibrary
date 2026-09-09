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

## 3. Le bat 50 : le veto a eu raison, mon instrument est à moitié aveugle

**Lancé et terminé le 09/09 à 20:23. 14 fichiers déplacés, 0 échec**, manifeste
dans `_corbeille_menage\20260909_202315\`. Environ 340 Ko.

**Et 810 fichiers retenus par le veto.** Ce déséquilibre est le résultat, pas
un détail. La sortie console en donne la raison, fichier par fichier, et elle
accuse l'instrument :

- **`_to_delete\` contient 800 fichiers et 366,8 Mo** — dont **560 `.pyc`**.
  J'avais annoncé « 136 Ko » à Mike. Faux de trois ordres de grandeur.
- `inventaire_fichiers_orphelins.py` ne PARCOURT que les fichiers texte
  (`EXT_LECTEURS`). **609 binaires n'ont donc jamais été examinés** → famille
  `non vu` → retenus, comme le veto l'exige (« ne pas savoir n'est pas savoir
  que non »).
- Les `_rapport_*` sont retenus pour une autre raison : `LU PAR DU CODE` ou
  `LU PAR UN MOTIF`. À vérifier avant de conclure — **une citation dans un
  commentaire `REM` d'un `.bat` compte aujourd'hui comme une lecture**, et ce
  n'en est pas une.

**Le veto a fait exactement son travail. C'est la mesure en amont qui est
incomplète, et ma recommandation à Mike en a hérité.**

### Le correctif, et c'est la première tâche de demain

1. **Séparer PARCOURIR de LIRE.** N'importe quel fichier peut être un
   CANDIDAT ; seul un fichier texte peut être un LECTEUR. Aujourd'hui les deux
   sont filtrés par la même liste d'extensions.
2. **Dire tout haut ce qu'on n'a pas examiné.** Un rapport qui range 609
   fichiers en « non vu » sans le crier laisse croire à un inventaire complet.
   Le nombre de non-vus doit sortir dans le bilan, pas dans le détail.
3. **Distinguer une citation en COMMENTAIRE d'une lecture réelle.** Au minimum,
   imprimer la ligne citante pour qu'un humain tranche.
4. Ensuite seulement, relancer le bat 50 : les 366 Mo de `_to_delete\` sont le
   vrai gisement, et ils sont toujours là.

Le reste de la corbeille du ménage n'est pas vidé, et c'est voulu.

## 4. Ce qui est ouvert, dans l'ordre

**À Mike, quand il veut** — la dernière photo sensible ; lire la page `/aide`
(chantier 17, étape 7 : ce n'est pas une tâche, c'est un jugement, sa famille
lira ce texte).

**De mon côté, sans GPU ni prompt** — la révision de `CLAUDE.md` et de
`MARCHE_A_SUIVRE.md`, qui n'ont **pas** été relus le 09/09 ; les points
d'audit restants une fois la campagne finie.

**Quand la campagne s'arrête** — la question au tagueur (3 bis c), la
re-mesure des Motion Photos arrivées depuis le 03/09 (demande le serveur
arrêté), et le bilan chiffré de cette première passe officielle du fonds.

**En fin de projet, décision de Mike du 09/09** — la copie hors site. Le fait
qui ne se répète plus mais qui reste vrai : depuis l'effacement du Takeout, le
NAS est le seul exemplaire des ~40 000 photos.

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

## 6. Ce que j'attends de Mike demain matin

1. **La sortie console du bat 50** — c'est le seul point vraiment bloquant.
2. Rien d'autre. La campagne tourne toute seule ; le reste est de mon côté.

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

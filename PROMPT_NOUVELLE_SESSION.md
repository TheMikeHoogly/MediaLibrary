# Amorce de reprise — MediaLibrary

> À coller après connexion de `C:\Prog\Claude\MediaLibrary`. Règles et
> protocole : `CLAUDE.md`. Ici : **l'état et le prochain pas, rien d'autre.**

Tu reprends **MediaLibrary**. **VÉRIFIE avant de lire** : `.git/HEAD`,
`.git/logs/HEAD` et `.git/logs/refs/heads/main` disent ce qui a été commité et
FUSIONNÉ — ce document, non. Puis `ROADMAP.md`, `eval/DECISIONS.md`,
`eval/METHODE.md` — et `docs/DECISIONS_OUTILLAGE.md` si le sujet touche aux
canaux, à la livraison ou au MCP. Débrief en 2–3 lignes, puis on attaque.

## Où on en est (05/09/2026 — chantier 2 quater décidé, GO de Mike reçu)

**Git** : dernier commit fusionné dans `main` = `b99d1ed` (vérifier
`.git/logs/refs/heads/main`). Chaîne de la session qui vient de finir :
`4a5dab4` (qwen3-vl 2b vs 4b, 8 photos) → `bb4cfb7` (+ qwen3.5 2b/4b,
`--sortie` configurable sur `mesure_modele_vision.py`) → `ba529e8` (chantier
**2 quater** créé, `ROADMAP.md` dégonflée 91 ko → 42 ko) → `dd3de22` (2 quater
RÉVISÉ : passe unique coordonnée au lieu d'une pré-passe en 2 phases, mesurée
par `mesure_detection_cpu.py`) → `b99d1ed` (clarification : préservation des
identités humaines pendant le retag, vérifiée dans le code). **Serveur : PAS
redémarré pendant cette suite** — aucun `server.py` touché, uniquement
`ROADMAP.md`/`eval/DECISIONS.md` et deux bancs de mesure. Il tourne donc
toujours sur le code observé le 03/09 ~19:16 (session 71). **`QUESTIONS_MIKE.md`
: vide.**

**DÉCISION : re-tagger le fonds ENTIER, FR seul, avec `qwen3.5:4b` — Mike a
donné le GO pour l'implémentation (05/09 soir).** Résumé, le détail complet
(mesures, raisonnement, invariants vérifiés) vit dans `ROADMAP.md` chantier
**2 quater** et dans `eval/DECISIONS.md` section « Tagging / description » :

- Passage au FR seul (fin du bilingue) → tout le fonds redevient candidat au
  retag, pas seulement les 22 196 entrées « v0 » du 2 bis.
- `qwen3.5:4b` (MÊME gabarit VRAM que `qwen3-vl:4b`, 3,4 Go) bat `qwen3-vl:4b`
  sur les corrections concrètes (chat calico, lac/océan, fuite de noms) et
  tourne **~3× plus vite** (11,3 s/photo contre 35,2 s), quasi la vitesse
  actuelle de `qwen3-vl:2b` en prod.
- **Une seule passe coordonnée** (détecter visages + animaux JUSTE AVANT
  chaque appel Ollama, dans le pipeline de retag lui-même) bat la première
  idée d'une pré-passe séparée en 2 phases — mesuré (`mesure_detection_cpu.py`) :
  ~10 % de surcoût pour 100 % de couverture, contre une pré-passe qui n'aurait
  rattrapé qu'une partie du travail.
- **Mike voit ce retag complet, UNIQUE, comme la « première passe officielle »
  de MediaLibrary** — un soin d'initialisation, PAS un changement de la
  logique standard de `tagger_worker` (qui reste inchangée pour les uploads
  du quotidien : pas de re-tagging automatique d'une photo déjà taguée).
- **Garde-fou vérifié dans le code, pas supposé** : les noms `personne:Nom` /
  `animal:Nom` ne vivent PAS dans les mots-clés Ollama mais dans les fiches
  durables `PEOPLE_STORE`/`PETS_STORE` ; `_noms_attendus()` les réinjecte à
  CHAQUE écriture du worker de tagging (commentaire du code : « PÉRENNITÉ : ne
  jamais perdre les tags nommés »). La détection visages/animaux du retag ne
  se déclenche QUE si l'entrée manque encore dans `FACE_STORE`/`ANIMAL_STORE`
  — jamais de re-détection qui romprait un cluster déjà nommé. **Le pipeline
  de retag à écrire DOIT réutiliser cette même logique de fusion
  (`_merge_named_tags`, `_noms_attendus`), pas la contourner.**

## Prochain pas

**1. Attaquer l'implémentation, chantier 2 quater, DANS L'ORDRE (`ROADMAP.md`
en a le détail) — rien de tout ça n'est encore codé :**
1. `tagging_meta.py` : FR seul (retirer `keywords_en` du schéma JSON envoyé à
   Ollama) + consigne anti-répétition explicite. Étendre/vérifier ses tests
   avant livraison.
2. `server.py` : `MODEL` bascule vers `qwen3.5:4b` **via `modele.txt`** (pas
   une ligne de code — aucun redémarrage-preuve requis par `git_agent`,
   ce fichier n'est pas dans le graphe d'import). `TAGGING_PIPELINE_VERSION`
   bumpée en même temps que le prompt (ex. `"qwen3.5:4b|v3fr|kb1"`) — bumper
   seul ne déclenche rien tant que le levier de l'étape 4 n'existe pas.
3. `enrichir_lieux.py` tourne une fois (rafraîchit `gps_places.json`,
   indépendant, sans urgence particulière).
4. `server.py` : le levier `retag_actif.txt` + le bloc de scan pipe-aware
   (piggyback sur le bloc existant de `_sync_dir`, « fichiers modifiés ») +
   le pipeline de retag dédié qui détecte visages/animaux AVANT de tagger
   (si l'entrée manque encore dans `FACE_STORE`/`ANIMAL_STORE`) — livré et
   testé, mais **PAS activé** (fichier absent = rien ne bouge, `tagger_worker`
   standard inchangé).
5. Test d'endurance thermique sur une fenêtre LONGUE (heures, pas minutes) —
   l'endurance n'a été prouvée que par rafales de ~450 s (chantier
   confidentialité, 04/09).
6. `retag_actif.txt` posé → la campagne démarre, observée (`/sante`, boucle
   thermique, spot-checks < 10 photos de temps en temps sur le format ET les
   hallucinations type « lgbtq »).

**Pendant la campagne (une fois l'étape 6 lancée), ce qui reste sûr à faire
avancer** : 1 bis (`.btn` canonique), l'étape 7 du chantier 17 (onboarding),
le reste de l'audit, toute doc/UI/CSS. **À éviter ou reporter** : la phase 2
vidéo (1 octies), tout nouveau banc `mesure_`/`eval_` GPU, tout chantier qui
bumperait une AUTRE version de pipeline en même temps (confusion de
diagnostic).

**2. Chantier 18 (confidentialité) : la mesure est FINIE, la liste ATTEND
Mike.** `docs/sensibles_echantillon.json` (90/90, 04/09 soir) : 66 « non »,
19 illisibles, 1 facture, 1 banque, 3 administratif — à JUGER photo par
photo, rien n'a bougé.

**3. Items non touchés depuis session 71 (03/09), statut À REVÉRIFIER — le
journal git ne dit rien de ces sujets, ils ne se prouvent qu'en réel :**
- Bat 42 (strip Motion Photo, ~8,6 Go à rendre) était EN COURS le 03/09 soir
  — demander à Mike où ça en est avant de supposer que bat 43 (purge des
  `_original`) a suivi.
- Ventilation dégagée mais pas nettoyée en profondeur : feu vert PARTIEL de
  Mike pour tester quand même, prudence thermique (voir aussi le test
  d'endurance de l'étape 5 ci-dessus, qui répond au même besoin pour 2 quater).
- La Carte a deux champs (barre commune + « Rechercher (noms, lieux, sens) »)
  : à trancher avec Mike — garder les deux ou fondre.
- 9 septembre au matin : Windows a-t-il demandé le redémarrage du Patch
  Tuesday ? (`Get-WinEvent -FilterHashtable @{LogName='System'; Id=1074}`,
  ne pas confondre avec la coupure thermique brutale du 29/08 — Id 41).
- UNIFIER le re-clé (`server.rekey_everywhere`,
  `deplacer_dossiers.recle_une_cle`, `appliquer_plan.rekey_stores` : trois
  copies d'une même règle, déjà divergentes une fois).

## En fin de projet

- **La copie hors site (12 bis)** attend la fin du chantier 17 : DS224+ →
  Infomaniak Swiss Backup, ~CHF 6/mois pour 1 To, clé imprimée, restauration
  d'épreuve. Ne PAS toucher au Takeout `C:\GOOGLE PHOTOS\extrait` avant.
- **HTTPS : FAIT** — `https://msi-mike.goat-draco.ts.net/`.

## Réflexes

### Mesurer

**Un marqueur n'est pas la chose.** `SEFT` en queue ≠ Motion Photo : 16 519
JPEG portent un trailer SEF de MÉTADONNÉES sans vidéo. Et un `ftyp` nu dans
l'entropie JPEG ment — 3 « Motion » sur 3 avaient une vidéo estimée à 100 %
du fichier avant que la boîte soit validée (taille big-endian + brand
lisible). L'annuaire `SEFH` en queue DIT s'il y a un bloc `MotionPhoto_Data` —
sans lecture pleine.

**Les fils n'accélèrent pas un partage SMB déjà saturé** : 8 lecteurs ont fait
MOINS que 1 (2,6 contre 4,5 fichiers/s) et semé 21 `EINVAL` muets. Mesurer
avant de paralléliser — et une erreur non nommée et non cachée rend
« TERMINÉ » inatteignable.

**La bonne ÉCHELLE, sinon la bonne conclusion sur les mauvaises données.**
Dérive par rapport à QUOI — le signal thermique du 29/08 était ENTRE les
sessions, pas dedans (`ROADMAP.md`, sessions 57→63).

**Ne JAMAIS supposer un chiffre gagné avant de l'avoir mesuré en réel sur la
machine cible.** Le « 9+ jours » du 04/09 pour le retag qwen3-vl:4b mélangeait
deux mesures ; corrigé en « ~16 jours » après re-calcul propre — et le passage
à qwen3.5:4b l'a ramené à ~5 jours, comparable au débit actuel. Trois chiffres
différents pour la même question en une semaine : le chiffre solide était le
RATIO (~3×), jamais le nombre de jours absolu tiré de 8 photos difficiles.

**Le canal du banc n'admet que `[A-Za-z0-9_.:/=-]`** (espaces via jeton
`b64:`), plafond **600 s** : un banc long est REPRENABLE (cache écrit à
chaque passe) et se lance avec `--budget-s 450`.

**Ne JAMAIS lancer `unittest discover` depuis la VM** : plusieurs tests
importent `server.py`, qui ouvre `photos.db` — la VM ne sait même pas
l'ouvrir en LECTURE par-dessus le montage (`disk I/O error` immédiat,
observé le 03/09, rien écrit). Un test qui a besoin du code de `server.py`
le lit par `ast` (voir `test_ui_global.py`, `test_upload_precontrole.py`),
il ne l'importe pas.

**ExifTool sous Windows perd les accents des arguments** : argfile UTF-8 BOM
(`server._run_exiftool`, repris par `appliquer_strip_motionphoto`).

**`device_bash` tronque une commande trop longue SANS le dire (~4 Ko).** Un
`cat > fichier << 'EOF'` dont le payload dépasse ce seuil part amputé — le
heredoc échoue (« here-document … delimited by end-of-file ») ou pire, écrit
un fichier tronqué sans erreur visible. Pour transférer un script Python avec
des accents (non ASCII, donc en base64) : découper le `.b64` en morceaux
d'environ 1200 octets, les concaténer par `cat >>` successifs, puis vérifier
la taille cumulée (`wc -c`) ET le `sha256sum` des deux côtés — CLOUD et
Windows — avant de décoder et d'exécuter. Repéré et contourné le 05/09
(transfert de `patch_roadmap2.py`, `patch_roadmap3.py`).

### Lire

**Le journal du serveur d'abord**, depuis la dernière bannière :

    L=$(grep -n "===== DEMARRAGE" _journal_serveur.log | tail -1 | cut -d: -f1)
    tail -n +$L _journal_serveur.log | grep -n "FIL MORT\|THREAD MORT\|Traceback"

**Savoir d'où vient un chiffre.** `verifier_photos_google` lit le DISQUE ;
`generer_plan_annee` lit l'index en mémoire — les confondre a coûté des heures.

**Le plan n'est régénéré QUE par le bouton Réglages / `POST
/api/maint/plan-annee`.** `plan_vise_la_racine` et `plan_perime` gardent.

**`.git/logs/refs/heads/main` se lit en texte, sans `git`.** Chaque ligne
donne l'ancien et le nouveau hash, l'auteur, l'horodatage UNIX (`+0200`, donc
UTC+2 chez Mike) et l'action (`fetch … fast-forward` pour une fusion de
`git_agent`). `_etat_git.json` a un tableau `historique` (pas seulement
`dernier`) qui garde titre + commit + branche des dix dernières livraisons —
plus rapide qu'un `git log` pour retrouver CE QUI a été livré et QUAND, sans
jamais invoquer `git`.

### Juger

**Avant de RECOMMANDER une règle, relire `eval/DECISIONS.md` en entier sur le
sujet.** Le carnet des décisions n'est pas un journal — c'est la contrainte.
**Une clôture n'est pas éternelle** : la re-passe de tagging en lot avait été
CLOSE le 16/08 (gain net non prouvé) ; le 05/09 elle est redevenue une
décision active — pas parce que l'ancienne mesure était fausse, mais parce
que deux faits nouveaux (FR seul rend le statu quo intenable, un modèle
mesurablement meilleur existe) changent la question posée. La clôture du
16/08 reste vraie SUR CE QU'ELLE MESURAIT ; elle ne s'applique plus à une
question différente.

**Un rattrapage ne doit jamais dépendre de la ressource qui vient de tomber.**

**Un `replace` sur un motif présent DEUX fois touche le mauvais — `assert
count == 1` avant.**

**Un banc vert n'est pas un regard.**

### Toucher

**`ui/pages/` et `ui/*.css` sont relus À CHAUD** ; seul `server.py` exige un
redémarrage — qui interrompt tagging et scan.

**Jamais deux écrivains sur `photos.db`.** Le serveur est l'écrivain unique ;
les applicateurs le PROUVENT (`refus_d_ecriture` : HTTP + verrou).

**Un `_exiftool_tmp` condamne sa photo** — balayage jamais par défaut ; le
strip le VÉRIFIE fichier par fichier.

> **`N:\Photos` se CONNECTE à chaque session** (picker « Add folder », non
> persistant) : demander à Mike au « Go ». Connecté : `device_list_dir` /
> `device_stage_files` / `device_commit_files` — mais PAS monté dans
> `device_bash` (réseau) : un script sur tout le fonds passe par l'agent banc
> (Windows, UNC).
>
> **Piège git via `device_bash`** : jamais de git d'ici (`.git/index.lock`
> résiduel indélébile) — même un `rev-parse` en lecture seule est à éviter,
> la règle est catégorique, pas seulement pour les écritures ; un lock qui
> traîne se renomme (`mv`), ne s'efface pas. Un `git status` de simple
> curiosité EST une violation, même si son verdict était juste (commis par
> erreur le 05/09, noté ici pour ne pas recommencer) : `_etat_git.json` (champ
> `historique`) et les fichiers `.git/logs/*` lus en texte suffisent toujours.
>
> **Piège d'horloge** : `device_bash` est en **UTC** (−2 h chez Mike).

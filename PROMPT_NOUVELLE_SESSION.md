# Amorce de reprise — MediaLibrary

> À coller après connexion de `C:\Prog\Claude\MediaLibrary`. Règles et
> protocole : `CLAUDE.md`. Ici : **l'état et le prochain pas, rien d'autre.**

Tu reprends **MediaLibrary**. **VÉRIFIE avant de lire** : `.git/HEAD`,
`.git/logs/HEAD` et `.git/logs/refs/heads/main` disent ce qui a été commité et
FUSIONNÉ — ce document, non. Puis `ROADMAP.md`, `eval/DECISIONS.md`,
`eval/METHODE.md` — et `docs/DECISIONS_OUTILLAGE.md` si le sujet touche aux
canaux, à la livraison ou au MCP. Débrief en 2–3 lignes, puis on attaque.

## Où on en est (05/09/2026 soir — chantier 2 quater : étapes 1, 2 et 4 LIVRÉES)

**Git** : dernier commit fusionné dans `main` = celui de cette session
(vérifier `.git/logs/refs/heads/main`, jamais ce document). Avant elle :
`32cb83b` (préparation de la session d'implémentation). **Le serveur a été
REDÉMARRÉ et observé** — c'était exigé, `server.py` a changé.

**Ce qui est codé et livré (rien n'est ACTIVÉ) :**

1. **`tagging_meta.py` en FR seul.** `REGLES_JSON` ne demande plus
   `keywords_en` ; s'y ajoutent une exigence de vrai français (sans la case
   anglaise, le modèle déverse ses anglicismes dans la case française —
   « inflatable », « gruppe », « castle gonflable » observés) et une consigne
   anti-répétition (mots-clés distincts entre eux, description qui dit la
   scène au lieu de recopier la liste). Chaque consigne répond à un défaut
   VU dans `docs/comparaison_modeles_vision*.json`, pas à une intuition.
2. **`modele.txt` → `qwen3.5:4b`** et `TAGGING_PIPELINE_VERSION` =
   `"qwen3.5:4b|v3fr|kb1"`. Depuis le redémarrage, les uploads du quotidien
   sont donc tagués par le nouveau modèle avec le nouveau prompt.
3. **Le levier de campagne, livré INERTE.** `retag_actif.txt` est ABSENT : tant
   qu'il l'est, rien ne bouge et `tagger_worker` se comporte comme avant. Posé,
   le scan approfondi enfile par lots de 500 les entrées dont le `pipe` n'est
   pas la cible ; le retirer arrête la campagne au lot suivant.

**Deux écarts assumés par rapport au croquis de la ROADMAP** (détail dans
`ROADMAP.md` 2 quater et `eval/DECISIONS.md`) : la campagne ne RETIRE rien de
l'index (le geste `remove_many` du bloc « fichiers modifiés » viderait la
photothèque sur cinq jours), et un retag raté CONSERVE l'entrée
(`_echec_retag`, marque `retag_fail` qui sert aussi de garde anti-boucle) au
lieu de l'écraser par un `failed` — un timeout d'Ollama aurait sinon coûté à la
photo ses mots-clés, sa date et son GPS.

**Tests** : `test_tagging_meta.py` (logique pure : prompt FR seul, levier,
sélection des clés) et `test_retag_campagne.py` (16, cablage lu sur le code de
prod par `ast`, sans importer `server.py`).

## Prochain pas

**1. RÉPONDRE À LA QUESTION DU DICTIONNAIRE — avant tout le reste.**
`QUESTIONS_MIKE.md` porte une entrée, la seule : l'élargissement FR→EN de la
recherche (+0,075 de rappel, mesuré le 30/08) réapprend sa traduction toutes
les 6 h sur les entrées BILINGUES de l'index. Le FR seul les efface une à une :
à la fin de la campagne le dictionnaire serait vide et l'élargissement mourrait
SANS ERREUR. Recommandation écrite : le geler sur disque avant de poser
`retag_actif.txt`. Ne pas lancer la campagne avant d'avoir tranché.

**2. Ce qui reste du chantier 2 quater, dans l'ordre :**
- **Étape 3** : `enrichir_lieux.py` une passe (rafraîchit `gps_places.json`,
  hors ligne, hors GPU). **Ne tourne PAS depuis la VM** : il lit `photos.db`,
  que la VM ne sait pas ouvrir par-dessus le montage. Geste de Mike, ou banc.
- **Étape 5** : endurance thermique sur une fenêtre LONGUE (heures) —
  l'endurance n'est prouvée que par rafales de ~450 s (04/09).
- **Étape 6** : poser `retag_actif.txt` (vide = la version courante) → la
  campagne démarre, observée : `/api/serveur` → `config.retag`
  (`reste`, `en_file`, `abandons`), boucle thermique, et des spot-checks de
  moins de 10 photos de temps en temps sur le FORMAT (6-10 mots-clés courts,
  pas une phrase) ET les hallucinations type « lgbtq ».

**Pendant la campagne, ce qui reste sûr à faire avancer** : 1 bis (`.btn`
canonique), l'étape 7 du chantier 17 (onboarding), le reste de l'audit, toute
doc/UI/CSS. **À éviter** : la phase 2 vidéo (1 octies), tout nouveau banc
`mesure_`/`eval_` qui appelle Ollama avec un AUTRE modèle, tout chantier qui
bumperait une autre version de pipeline en même temps.

**3. Chantier 18 (confidentialité) : la mesure est FINIE, la liste ATTEND
Mike.** `docs/sensibles_echantillon.json` (90/90, 04/09 soir) : 66 « non »,
19 illisibles, 1 facture, 1 banque, 3 administratif — à JUGER photo par photo,
rien n'a bougé.

**4. Items non touchés depuis la session 71 (03/09), statut À REVÉRIFIER — le
journal git ne dit rien de ces sujets, ils ne se prouvent qu'en réel :**
- Bat 42 (strip Motion Photo, ~8,6 Go à rendre) était EN COURS le 03/09 soir —
  demander à Mike où ça en est avant de supposer que bat 43 a suivi.
- Ventilation dégagée mais pas nettoyée en profondeur : feu vert PARTIEL de
  Mike pour tester quand même, prudence thermique.
- La Carte a deux champs de recherche (barre commune + le sien) : à trancher.
- 9 septembre au matin : Windows a-t-il demandé le redémarrage du Patch
  Tuesday ? (`Get-WinEvent … Id=1074` ; ne pas confondre avec Id 41, thermique).
- UNIFIER le re-clé (`server.rekey_everywhere`, `deplacer_dossiers.recle_une_cle`,
  `appliquer_plan.rekey_stores` : trois copies d'une même règle).

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

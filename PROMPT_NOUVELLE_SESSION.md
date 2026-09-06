# Amorce de reprise — MediaLibrary

> À coller après connexion de `C:\Prog\Claude\MediaLibrary`. Règles et
> protocole : `CLAUDE.md`. Ici : **l'état et le prochain pas, rien d'autre.**

Tu reprends **MediaLibrary**. **VÉRIFIE avant de lire** : `.git/HEAD`,
`.git/logs/HEAD` et `.git/logs/refs/heads/main` disent ce qui a été commité et
FUSIONNÉ — ce document, non. Puis `ROADMAP.md`, `eval/DECISIONS.md`,
`eval/METHODE.md` — et `docs/DECISIONS_OUTILLAGE.md` si le sujet touche aux
canaux, à la livraison ou au MCP. Débrief en 2–3 lignes, puis on attaque.

## Où on en est (06/09/2026 matin — LA CAMPAGNE TOURNE)

**Git** : dernier commit fusionné dans `main` = celui de la fin de session
(vérifier `.git/logs/refs/heads/main`, jamais ce document). La session des 05
et 06/09 a livré, dans l'ordre : le chantier 2 quater (étapes 1, 2, 4), le gel
du dictionnaire FR→EN, le banc d'endurance, le bat 44, l'onboarding `/aide`,
la cadence NAS, le classement des échecs, les images tronquées, le registre des
photos perdues et le bat 45.

**La campagne de retag est EN COURS depuis le 05/09 16:50** — `retag_actif.txt`
posé (fichier VIDE, la forme sûre). Au moment d'écrire : ~4 200 photos
re-taguées, ~35 800 restantes, **0 abandon**, GPU à 54 °C, aucun bridage.
**Débit médian 14 s/photo** sur plus de 4 500 mesures → **encore ~6 jours**.
Le journal est l'instrument : `grep 'tagué en' _journal_serveur.log`.

**Ce qui a été appris et qui change les chiffres annoncés** : le banc
d'endurance mesurait l'appel au modèle SEUL (8,9 s) ; la production paie en
plus deux passages d'ExifTool sur le NAS et les détections. 14 s est le vrai
chiffre, mesuré sur des milliers de photos, pas sur huit.

**Les photos perdues — RÉGLÉ.** 942 fichiers étaient des coquilles de 2 à 3 Mo
remplies de « Read error in the sector ! » (récupération d'un vieux disque).
Registre dans git (`docs/photos_perdues.md`, 1983→2021), 309 homonymes intacts
retrouvés dont 299 déjà sur le NAS, **4 photos de 2019 rapatriées du Takeout**,
**938 coquilles en quarantaine** (`.corbeille-rangement\perdues_2026090610*`),
**3,03 Go rendus**. L'index se purge tout seul, scan après scan : 942 → 752 au
moment d'écrire, il finira seul. `/sante` : 53 vrais problèmes.

**L'après-midi du 06/09 a répondu aux quatre questions de Mike** :

1. **Chantier 18, les 24 photos non-« non » ont été REGARDÉES** (planches-contact
   basse définition, `verifier_planches_sensibles.py`). **6 sont vraiment
   sensibles**, 18 sans objet. Le banc en avait manqué 4 — toutes rangées sous
   `illisible`, qui ne veut pas dire « fichier illisible » mais « le modèle n'a
   pas répondu ». **Et il a mesuré `qwen3-vl:2b`, l'ancien modèle** : la mesure
   du 04/09 est à refaire sur `qwen3.5:4b` après la campagne, avec ces 24
   verdicts humains comme vérité terrain.
2. **La corbeille : 27,6 Go bloqués, pas 3 Go.** Le rangement par année a
   déplacé les canoniques ; 15 groupes sur 389 ont encore la leur au chemin
   noté. `reancrer_corbeille.py` + **bat 46** les retrouvent **par l'empreinte,
   jamais par le nom** (3 faux sur 40 vérifiés). Le bat 24 ne sert qu'après.
3. **`/aide` : le FR/EN est retiré** (le fonds passe en français seul) et les
   pages nommées sont devenues des liens. L'élargissement FR→EN reste ACTIF
   dans le moteur — utile tant que 35 000 photos portent encore des mots
   anglais ; ce n'est plus une promesse faite au lecteur, c'est une mécanique.
4. **Galerie** : une seule bascule replie les DEUX barres de filtre (mots-clés
   et personnes) ; un filtre actif la force à ressortir, avec son compte.
   Nouveau tri **Dossier** (groupe par répertoire, chronologique dedans) —
   vérifié en réel : 248 photos, 2 dossiers, 2 blocs contigus.

**`QUESTIONS_MIKE.md` est VIDE.** Rien n'attend de décision — mais deux gestes
attendent la main de Mike : le **bat 46 puis le bat 24**, et le jugement des
**6 photos sensibles** (liste dans `ROADMAP.md`, section 3 bis).

## Prochain pas

**0. D'ABORD : la campagne va-t-elle bien ?** `/api/maint/status` →
`config.retag` (`reste`, `en_file`, `abandons`) ; `en_file` à 0 pendant
longtemps = le GPU jeûne, c'est le défaut à traquer. Puis le débit
(`tagué en`), puis la température au journal (`🌡`, `🔥 CHAUD` ≥ 85 °C).
`abandons` > 0 : lire `retag_fail` dans les entrées concernées.

**1. Ce qui est SÛR à faire avancer pendant la campagne** : l'onboarding
`/aide` si Mike l'a relu et veut le retoucher (c'est SON texte, sa famille le
lira), le reste de l'audit interne, toute doc/UI/CSS, l'adoption de
`components.css` par `browse`, `faces` et `reglages` — `/map` est le TÉMOIN,
on n'y touche pas.

**2. À ÉVITER tant que la campagne tourne** : la phase 2 vidéo (1 octies), tout
banc `mesure_`/`eval_` qui appelle Ollama avec un AUTRE modèle (il ferait
swapper le premier sur une carte à 4 Go), tout chantier qui bumperait une autre
version de pipeline, et l'unification du re-clé — elle touche le chemin de
mutation de l'index (les trois copies ont été comparées le 05/09 : elles sont
COHÉRENTES aujourd'hui, `appliquer_plan` se passe légitimement du 7e magasin
puisqu'il ne fait qu'un aller-retour vers la corbeille).

**3. Ce qui attend un geste de MIKE**, rien d'urgent :
- **Chantier 18 (confidentialité)** : `docs/sensibles_echantillon.json`
  (90/90, 04/09) — 66 « non », 19 illisibles, 1 facture, 1 banque,
  3 administratif, **à juger photo par photo**. Rien n'a bougé.
- **Bat 24** pour purger la corbeille quand il voudra les 3,03 Go pour de bon
  (les 938 coquilles y sont, avec leurs manifestes).
- **`/aide`** : relire les sept points et dire si le ton convient.

**4. À REVÉRIFIER, ça ne se prouve qu'en réel** :
- **9 septembre au matin** : Windows a-t-il demandé le redémarrage du Patch
  Tuesday ? (`Get-WinEvent -FilterHashtable @{LogName='System'; Id=1074}` — ne
  pas confondre avec Id 41, la coupure thermique).
- La Carte garde son propre champ de recherche en plus de celui de la barre :
  à trancher avec Mike (garder les deux, ou fondre).
- Ventilation dégagée mais pas nettoyée en profondeur ; l'endurance est prouvée
  sur ~1 h de charge (75 °C, aucun bridage), pas sur cinq jours.

## En fin de projet

- **La copie hors site (12 bis)** attend la fin du chantier 17 : DS224+ →
  Infomaniak Swiss Backup, ~CHF 6/mois pour 1 To, clé imprimée, restauration
  d'épreuve. Ne PAS toucher au Takeout `C:\GOOGLE PHOTOS\extrait` avant.
- **HTTPS : FAIT** — `https://msi-mike.goat-draco.ts.net/`.

## Réflexes

### Mesurer

**Le seau « je n'ai pas compris » n'est pas un seau vide.** Le banc sensibles
rendait `illisible` quand le modèle ne répondait pas — 19 fois sur 90 — et
personne ne regardait dedans : c'est là que dormaient un extrait de casier
judiciaire, une carte d'assurance-maladie et deux relevés bancaires. Le
non-verdict doit compter comme À REVOIR, jamais comme rien.

**Un banc mesure le modèle qu'il NOMME, pas celui qui tourne.** `mesure_sensibles.py`
porte `qwen3-vl:2b` en dur ; `modele.txt` dit `qwen3.5:4b` depuis le 05/09.
La doc annonçait « le modèle de PROD » : elle avait raison la veille du
changement, et faux le lendemain. Relire `modele.txt` avant de citer une mesure.

**Un zéro parfait est une alarme au même titre qu'un cent.** Le premier passage
du banc corbeille a rendu « 374 disparues, 0 retrouvée » : il lisait
`tags_index.json`, un fichier que le passage à SQLite avait laissé mort. Un
index vide fait une réponse fausse qui a l'air d'une réponse — désormais le
banc refuse de conclure quand l'index est vide.

**Une mesure prise dans une fenêtre minimisée ne vaut rien** : Chrome rendait
`innerWidth = 0`, et les hauteurs lues (grille à 1 292 px) étaient l'effet du
repli, pas du design. Vérifier le viewport avant de croire un pixel.


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

**Un banc mesure CE QU'IL MESURE, pas ce qu'on croit.** Le banc d'endurance
rendait 8,9 s/photo — l'appel au modèle SEUL. La production paie en plus deux
passages d'ExifTool sur le NAS et les détections : **14 s**, mesurés sur des
milliers de photos. Avant d'extrapoler un banc à une campagne, demander ce que
le banc n'exécute PAS.

**Le POIDS d'un fichier ne dit rien de son contenu.** 941 fichiers de 2 à 3 Mo
étaient entièrement remplis du texte « Read error in the sector ! ». Un seuil
de taille minimale — l'hypothèse de départ — n'en aurait écarté aucun, et
aurait eu l'air de marcher. Une vignette se juge sur ses PIXELS
(`tagging_meta.classe_contenu`), et un fichier se juge sur ses OCTETS DE TÊTE.

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

**Un instrument ne condamne JAMAIS ce qu'il n'a pas vu — et ne passe jamais au
vert dessus.** `verifier_pages_composants` rendait « 10 griefs » sans avoir lu
une ligne (la porte était fermée). Corrigé — puis ses propres tests ont attrapé
la correction inverse : classer une redirection en « non regardée » l'avait
rendu VERT dessus, ce qui était l'incident du témoin `/faces`. Il faut les deux
règles : **pas de faute sans lecture, pas de vert sans preuve.**

**« Déjà fait » n'est pas un échec.** La passe complète du bat 45 criait vingt
« ECHEC » sur les vingt fichiers de l'essai, déjà déplacés. Aucune donnée en
jeu, mais un faux échec fait chercher une panne qui n'existe pas et noie les
vrais.

**Un `return` anticipé emporte le travail qui SUIT.** `classer_echecs` sortait
avant `retenter_tronquees()` quand il n'y avait rien à classer : la passe des
tronquées n'a jamais tourné au premier essai, et aucun test structurel ne l'a
vu — seule l'absence de la ligne au journal.

### Toucher

**`ui/pages/` et `ui/*.css` sont relus À CHAUD** ; seul `server.py` exige un
redémarrage — qui interrompt tagging et scan.

**Jamais deux écrivains sur `photos.db`.** Le serveur est l'écrivain unique ;
les applicateurs le PROUVENT (`refus_d_ecriture` : HTTP + verrou).

**Un `_exiftool_tmp` condamne sa photo** — balayage jamais par défaut ; le
strip le VÉRIFIE fichier par fichier.

> **`N:\Photos` se CONNECTE à chaque session** (picker « Add folder », non
> persistant) : demander à Mike au « Go ». Connecté : `device_list_dir` /
> `device_stage_files` / `device_commit_files` — **et, CONTRAIREMENT à ce que
> ce document a dit jusqu'au 05/09, il EST monté dans `device_bash`**
> (`$HOME/mnt/Photos`) et il se lit. Mesuré : le listage est rapide (2 140
> fichiers d'un dossier en 1 s) mais la lecture fichier par fichier plafonne à
> **~5 fichiers/s** — donc un coup d'œil ou une poignée de photos, oui ; un
> script sur TOUT le fonds, non, il passe toujours par l'agent banc (Windows,
> UNC, natif).
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
>
> **Le NAS est monté dans `device_bash`** (`$HOME/mnt/Photos`) — la doc a
> longtemps dit le contraire. Le listage est rapide, la lecture fichier par
> fichier plafonne à **~5 fichiers/s** : un coup d'œil oui, un script sur tout
> le fonds non (agent banc). `copie.db` s'ouvre en `mode=ro` depuis la VM ;
> `photos.db`, jamais.

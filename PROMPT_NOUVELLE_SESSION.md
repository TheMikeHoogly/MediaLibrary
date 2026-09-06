# Amorce de reprise — MediaLibrary

> À coller après connexion de `C:\Prog\Claude\MediaLibrary`. Règles et
> protocole : `CLAUDE.md`. Ici : **l'état et le prochain pas, rien d'autre.**

Tu reprends **MediaLibrary**. **VÉRIFIE avant de lire** : `.git/HEAD`,
`.git/logs/HEAD` et `.git/logs/refs/heads/main` disent ce qui a été commité et
FUSIONNÉ — ce document, non. Puis `ROADMAP.md`, `eval/DECISIONS.md`,
`eval/METHODE.md` — et `docs/DECISIONS_OUTILLAGE.md` si le sujet touche aux
canaux, à la livraison ou au MCP. Débrief en 2–3 lignes, puis on attaque.

## Où on en est (06/09/2026 soir)

**Git** : dernier commit fusionné dans `main` — le vérifier dans
`.git/logs/refs/heads/main`, jamais ici. Six livraisons le 06/09.

**LA CAMPAGNE DE RETAG TOURNE, et elle est en forme.** 11–16 s/photo, GPU à
81 % et 57 °C, la file se recharge toutes les ~18 minutes (500 par lot). Levier :
`retag_actif.txt`, fichier VIDE — ne pas l'effacer. Instruments :
`/reglages` → `config.retag`, et `grep 'en file de RE-TAGGING' _journal_serveur.log`.

**La journée a été une journée de PANNES, pas de fonctionnalités.** Trois, toutes
silencieuses, toutes trouvées par la mesure et pas par la relecture :

1. **La file de retag jeûnait derrière le NAS.** Elle se remplissait dans
   `_sync_dir`, appelée APRÈS un `rglob` de 44 000 fichiers sur SMB — 632 s à
   1 473 s d'ordinaire, **plus de 85 minutes** le jour où une passe de
   maintenance et 2 139 vignettes sont tombées dessus. GPU à 0 % pendant deux
   heures sans que rien ne casse. → `remplir_file_retag()` en tête de
   `scan_uploads`, avant tout contact avec le disque.
2. **`loading="lazy"` ne borne rien.** Une planche de 2 139 tuiles prenait les
   six connexions de Chrome pendant des dizaines de minutes — au point qu'un
   AUTRE onglet vers le serveur n'obtenait jamais de connexion (sa requête
   n'apparaît même pas dans le journal). → `window.Vignettes` : observateur à
   marge choisie + file plafonnée à 4 en vol. **Observé** : 585 tuiles,
   30 chargées, 555 en attente.
3. **« Déjà fait » criait ENCORE « ECHEC »** — bat 42 cette fois, après le
   bat 45 la semaine passée. La leçon était écrite ; elle n'avait été appliquée
   qu'à un seul outil.

**La corbeille de rangement : CLOSE.** Bat 46 (325 réancrages sur preuve
d'empreinte) puis bat 24 : **25,36 Go rendus**, à 0,2 Go de la prévision.
Restent 77 groupes — 33 récents qui partiront seuls, et **37 qui sont la
DERNIÈRE copie d'une photo** (165 Mo) plus 6 doublons confirmés et 4 illisibles
(`docs/corbeille_dernieres_copies.json`). Le garde-fou avait raison depuis le
début.

**Le chantier 18 a changé de forme, décidé par Mike.** Il ne veut pas cliquer
photo par photo sur des liens que je lui colle : il veut que l'application DISE
ce qu'elle a trouvé. Spec dans `eval/DECISIONS.md` (06/09) et ROADMAP § 3 bis.

## Prochain pas

**0. D'ABORD : la campagne va-t-elle bien ?** `/reglages` → `config.retag`
(`reste`, `en_file`, `abandons`). `en_file` à 0 longtemps = le GPU jeûne.
Puis le débit (`tagué en`) et la température (`🌡`, `🔥 CHAUD` ≥ 85 °C).

**1. L'ONGLET SENSIBLES — le chantier que Mike attend.** Spec complète dans
`eval/DECISIONS.md`. Trois morceaux, dans cet ordre :
  a. l'axe `sensible` dans l'index (jamais le XMP) + le filtre au magasin qui
     lit un ÉTAT en plus du CHEMIN — c'est le vrai changement : `visibilite`
     ne décidait jusqu'ici que sur le chemin ;
  b. la route `/sensibles` et sa page, aux trois gestes (Rendre privée /
     Corbeille / « non » mémorisé) ;
  c. la question posée dans la MÊME invocation du tagueur (pas de cinquième
     pipeline), puis la passe rétroactive.
**Ne pas commencer par (c)** : détecter avant de savoir montrer produirait un
fonds à moitié masqué sans écran pour le démasquer.

**2. Trois dettes de la journée, courtes** :
  - le remplissage de la file passe encore APRÈS le travail de démarrage du
    serveur (résolution des 45 000 clés) : ~15 min de GPU perdu à chaque
    redémarrage ;
  - la maintenance se met en retrait quand l'UI est active, **pas quand un scan
    tourne** — deux balayages SMB simultanés, c'est la panne n° 1 ci-dessus ;
  - restaurer les 37 dernières copies de la corbeille (l'outil reste à écrire ;
    le manifeste garde leur chemin d'origine).

**3. Reprendre la mesure des sensibles sur `qwen3.5:4b`** (l'ancienne portait
sur `qwen3-vl:2b`, l'ancien modèle de prod), avec les 24 verdicts humains du
06/09 comme vérité terrain.

**Ce qui attend la main de Mike** : `MARCHE_A_SUIVRE.md` à la racine — six
sections à cocher.

## En fin de projet

- **La copie hors site (12 bis)** attend la fin du chantier 17 : DS224+ →
  Infomaniak Swiss Backup, ~CHF 6/mois pour 1 To, clé imprimée, restauration
  d'épreuve. Ne PAS toucher au Takeout `C:\GOOGLE PHOTOS\extrait` avant.
- **HTTPS : FAIT** — `https://msi-mike.goat-draco.ts.net/`.

## Réflexes

### Mesurer

**Un attribut du navigateur n'est pas une garantie.** `loading="lazy"` était en
place sur la vue Dossiers et n'a rien empêché : sa marge appartient au
navigateur, et surtout il ne BORNE pas le nombre de requêtes en vol. Il avait
l'air de faire le travail — c'est ce qui a rendu la panne invisible pendant des
semaines. Ce qui protège, c'est ce qu'on écrit soi-même et qu'on peut mesurer.

**Regarder n'est pas toujours le bon instrument.** Pour les 54 groupes de
corbeille, les planches-contact montraient des chats et des mariages : elles
répondaient « oui, ça compte » à une question qu'on ne posait pas. La vraie
question — « cette photo existe-t-elle encore ailleurs ? » — était une question
de machine. Choisir l'instrument AVANT de le fabriquer.

**Une sonde qui coûte autant que ce qu'elle mesure est un échec de conception.**
479 s pour relire 389 manifestes et savoir où en était le bat 46 — parce que
l'outil, lui, ne disait rien. C'est au travail de rendre des comptes, pas à
l'observateur de le deviner.

**Chercher le banc AVANT d'éditer.** J'ai changé la signature de
`verifier_apres` sans voir `test_appliquer_strip_motionphoto.py` : six bancs
rouges, deux refus de l'agent Git. Le refus est une bonne nouvelle ; l'avoir
mérité n'en est pas une.

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

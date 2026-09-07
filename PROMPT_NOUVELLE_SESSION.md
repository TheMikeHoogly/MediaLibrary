# Amorce de reprise — MediaLibrary

> À coller après connexion de `C:\Prog\Claude\MediaLibrary`. Règles et
> protocole : `CLAUDE.md`. Ici : **l'état et le prochain pas, rien d'autre.**

Tu reprends **MediaLibrary**. **VÉRIFIE avant de lire** : `.git/HEAD`,
`.git/logs/HEAD` et `.git/logs/refs/heads/main` disent ce qui a été commité et
FUSIONNÉ — ce document, non. Puis `ROADMAP.md`, `eval/DECISIONS.md`,
`eval/METHODE.md` — et `docs/DECISIONS_OUTILLAGE.md` si le sujet touche aux
canaux, à la livraison ou au MCP. Débrief en 2–3 lignes, puis on attaque.

## Où on en est (07/09/2026, matin)

**Git** : dernier commit fusionné dans `main` — le vérifier dans
`.git/logs/refs/heads/main`, jamais ici.

**LA CAMPAGNE DE RETAG TOURNE, et elle est en forme.** Lu sur la machine le
07/09 à 07:30 (`/api/maint/status` → `config.retag`) : **8 368 faites, reste
31 629, 0 abandon**, 12–16 s/photo → **~5 jours**. Levier : `retag_actif.txt`,
fichier VIDE — ne pas l'effacer. Instruments : `/reglages` → `config.retag`, et
`grep 'en file de RE-TAGGING' _journal_serveur.log`.

**Deux dettes du 06/09 fermées le 07/09, MESURÉES en réel** (récit complet dans
ROADMAP, § « Où on en est ») :

1. **Le GPU ne jeûne plus au redémarrage.** `remplir_file_retag()` passe en
   TÊTE de `maintenance_loop`, avant ExifTool et les trois passes de purge —
   il ne lit que l'index en mémoire. Le délai bannière → premier lot valait
   **69 s à 81 min selon l'humeur du NAS** (relevé sur les quatre redémarrages
   du 06/09) ; il vaut **9 s**, deux fois observé, et ces 9 s sont le
   chargement des magasins SQLite.
2. **La maintenance cède à un balayage NAS en cours** (`SCAN_NAS_EN_COURS`,
   posé avant le `try` du scan, levé dans son `finally`). Observé :
   `boucle.scan_nas` à `true` pendant l'énumération initiale. Et le journal
   nomme désormais la vraie cause (`raison_busy()`) au lieu de crier « UI
   active » quoi qu'il arrive. **L'autre moitié reste ouverte** : l'ordre
   INVERSE (étape lourde déjà partie, puis le scan qui arrive dessus).

**La corbeille de rangement : CLOSE côté purge** (25,36 Go rendus le 06/09).
Restent 77 groupes — 33 récents qui partiront seuls, 36 doublons réels, 4
coquilles « Read error in the sector ! », et **3 vraies photos sans jumeau
connu, à RESTAURER** (`docs/corbeille_par_pixels.json`). **L'outil est écrit
et vérifié** (`restaurer_corbeille.py` + bat 47) — il attend la main de Mike,
déplacer des fichiers de l'archive n'étant pas un geste d'agent.

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

**2. Deux dettes courtes** :
  - les 3 vraies dernières copies : **l'outil est prêt**, c'est le bat 47 qui
    attend Mike — vérifier au retour que le geste a été fait (le manifeste du
    groupe porte alors `restaure_le`), puis le bat 24 ;
  - la seconde moitié du garde-fou NAS : un scan qui arrive sur une étape
    lourde de maintenance DÉJÀ partie. Attention, la ligne `nas = first or
    deep or (cycle % NAS_SCAN_CYCLES == 0)` porte un garde-fou voulu, avec son
    banc — ne pas la changer sans mesure.

**3. Reprendre la mesure des sensibles sur `qwen3.5:4b`** (l'ancienne portait
sur `qwen3-vl:2b`, l'ancien modèle de prod), avec les 24 verdicts humains du
06/09 comme vérité terrain. **Après la campagne** : un banc qui appelle Ollama
pendant qu'elle tourne dispute au tagueur la seule ressource dont il a besoin.

**Ce qui attend la main de Mike** : `MARCHE_A_SUIVRE.md` à la racine.

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

**Un chiffre moyen peut cacher qu'il n'y a pas de chiffre.** La doc annonçait
« ~15 min de GPU perdu à chaque redémarrage ». Mesuré sur les quatre
redémarrages du 06/09 : 69 s, 99 s, 51 min, 81 min. Ce n'était pas un coût, mais
une DÉPENDANCE — au NAS — et une moyenne la faisait passer pour un coût fixe,
donc pour quelque chose de supportable. Avant de citer une durée, regarder sa
dispersion : c'est elle qui dit s'il y a une panne dessous.

**Un instrument juste sur le principe peut mesurer la mauvaise grandeur.** Le
banc de la corbeille cherchait par sha256 dans un fonds dédoublonné par les
PIXELS : 37 « dernières copies » dont 30 étaient de vrais doublons. Rien
n'était faux dans le code — il répondait exactement à la question qu'on lui
posait, et ce n'était pas la bonne. Avant d'écrire un banc, demander par quel
critère la donnée qu'on interroge a été produite.

**Regarder n'est pas toujours le bon instrument.** Pour les 54 groupes de
corbeille, les planches-contact montraient des chats et des mariages : elles
répondaient « oui, ça compte » à une question qu'on ne posait pas. La vraie
question — « cette photo existe-t-elle encore ailleurs ? » — était une question
de machine. Choisir l'instrument AVANT de le fabriquer.

**Un drapeau qu'on ne voit pas ne se prouve pas.** `SCAN_NAS_EN_COURS` ne fait
céder la maintenance que quand une étape est DUE — c'est-à-dire une fois par
jour. Un banc vert et rien à observer avant 19h : la correction serait partie
sans preuve. Une ligne dans `/api/maint/status` (`boucle.scan_nas`) a suffi à
la voir en réel à 88 s d'uptime. Quand une correction n'est visible que
rarement, c'est le drapeau qu'il faut exposer, pas la preuve qu'il faut
attendre.

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
il ne l'importe pas — et ceux-là tournent très bien depuis la VM, un par un
(`python3 -m unittest test_x`, ~20 s chacun).

**ExifTool sous Windows perd les accents des arguments** : argfile UTF-8 BOM
(`server._run_exiftool`, repris par `appliquer_strip_motionphoto`).

**Pour transférer un script accentué vers la machine : `device_commit_files`,
pas un heredoc.** `device_bash` tronque une commande trop longue SANS le dire
(~4 Ko) : un `cat > f << 'EOF'` amputé écrit un fichier tronqué sans erreur
visible, et le découpage du base64 en morceaux se recopie mal (une seule espace
glissée dans un morceau et le sha256 ne tombe plus). Écrire le fichier dans le
bac du conteneur, puis `device_commit_files` vers un `_tmp_*.py` à la racine :
l'UTF-8 passe intact, en un appel, sans vérification à faire. Ensuite `rm` —
et ne JAMAIS laisser traîner un fichier de travail non gitignoré à la racine,
l'agent Git le prendrait.

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

**Un grep large attrape des innocents** : `grep -i "echec"` sur le journal
sortait une photo taguée « jeu d'echecs ». Lire la ligne, pas le compte.

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
count == 1` avant.** Et une assertion d'ORDRE se trompe de la même façon :
`corps.index('try:')` prenait le PREMIER `try:` de la fonction, très loin du
geste jugé — le banc criait rouge sur du code juste. Juger la FENÊTRE qui suit
le geste, pas le fichier entier.

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
redémarrage — qui interrompt tagging et scan (9 s de GPU perdu depuis le 07/09,
plus 1 à 25 minutes d'énumération pendant lesquelles le GPU, lui, travaille).

**Jamais deux écrivains sur `photos.db`.** Le serveur est l'écrivain unique ;
les applicateurs le PROUVENT (`refus_d_ecriture` : HTTP + verrou).

**Un `_exiftool_tmp` condamne sa photo** — balayage jamais par défaut ; le
strip le VÉRIFIE fichier par fichier.

> **`N:\Photos` se CONNECTE à chaque session** (picker « Add folder », non
> persistant) : demander à Mike au « Go ». Connecté : `device_list_dir` /
> `device_stage_files` / `device_commit_files` — **et il EST monté dans
> `device_bash`** (`$HOME/mnt/Photos`). Mesuré : le listage est rapide (une
> racine en 0,1 s, 2 140 fichiers d'un dossier en 1 s) mais la lecture fichier
> par fichier plafonne à **~5 fichiers/s** — donc un coup d'œil ou une poignée
> de photos, oui ; un script sur TOUT le fonds, non, il passe toujours par
> l'agent banc (Windows, UNC, natif).
>
> **Piège git via `device_bash`** : jamais de git d'ici (`.git/index.lock`
> résiduel indélébile) — même un `rev-parse` en lecture seule est à éviter,
> la règle est catégorique, pas seulement pour les écritures ; un lock qui
> traîne se renomme (`mv`), ne s'efface pas. Un `git status` de simple
> curiosité EST une violation, même si son verdict était juste (commis par
> erreur le 05/09, noté ici pour ne pas recommencer) : `_etat_git.json` (champ
> `historique`) et les fichiers `.git/logs/*` lus en texte suffisent toujours.
>
> **`device_bash` ne peut ni effacer ni déplacer** dans les dossiers montés
> (`rm`, `mv` → « Operation not permitted ») tant que Mike n'a pas approuvé la
> demande de suppression. Un fichier de travail écrit à la racine y reste
> donc — et l'agent Git le prendrait. Écrire ses brouillons HORS de `mnt/`
> (`$HOME`), et ne rien poser à la racine du dépôt qu'on ne sache pas retirer.
>
> **Piège d'horloge** : `device_bash` est en **UTC** (−2 h chez Mike).
>
> `copie.db` s'ouvre en `mode=ro` depuis la VM ; `photos.db`, jamais.

# Amorce de reprise — MediaLibrary

> À coller après connexion de `C:\Prog\Claude\MediaLibrary`. Règles et
> protocole : `CLAUDE.md`. Ici : **l'état et le prochain pas, rien d'autre.**

Tu reprends **MediaLibrary**. **VÉRIFIE avant de lire** : `.git/HEAD`,
`.git/logs/HEAD` et `.git/logs/refs/heads/main` disent ce qui a été commité et
FUSIONNÉ — ce document, non. Puis `ROADMAP.md`, `eval/DECISIONS.md`,
`eval/METHODE.md` — `eval/DECISIONS_UI.md` si le sujet touche à l'écran
(sorti du carnet le 07/09), `docs/DECISIONS_OUTILLAGE.md` s'il touche aux
canaux, à la livraison ou au MCP. Débrief en 2–3 lignes, puis on attaque.

## Où on en est (08/09/2026, matin)

**Git** : dernier commit fusionné dans `main` — le vérifier dans
`.git/logs/refs/heads/main`, jamais ici. Six livraisons les 07 et 08/09.

**LA CAMPAGNE DE RETAG TOURNE.** Levier : `retag_actif.txt`, fichier VIDE —
ne pas l'effacer. Au 08/09 07:00 : **~12 200 faites, reste ~27 800, 0 abandon**,
14 s/photo médian → **~4 jours**. Instruments : `/reglages` → `config.retag`,
et `grep 'en file de RE-TAGGING' _journal_serveur.log`.

**LE CHANTIER 18 : (a) ET (b) SONT FAITS.**
- **(a) l'axe `sensible`** — la visibilité ne se décide plus sur le seul
  CHEMIN. Les cinq magasins et le garde des octets consultent l'ÉTAT ; l'axe
  vit en base, jamais dans le XMP. Qui lève un masque : le propriétaire ET
  l'admin (tranché par Mike le 07/09 — sinon une photo d'un dossier sans compte
  serait masquée à tort pour toujours).
- **(b) la page `/sensibles`** — trois gestes, **Corbeille en premier**
  (« la médiathèque conserve des souvenirs, pas des documents », Mike, 07/09),
  puis Rendre privée, puis Pas sensible. Chaque geste passe par la route qui
  existait déjà. L'onglet de nav reste **caché tant qu'il n'y a rien**.

**(c) EST EMPÊCHÉE PAR LA CAMPAGNE, et c'est le fait neuf du 08/09.** La spec
veut la question « dans la MÊME invocation du tagueur ». Or le prompt EST la
version du pipeline (`v3fr`) : y ajouter une phrase rendrait candidates les
12 000 photos déjà refaites. Rien n'a été touché.

**À la place : un FILET, disponible aujourd'hui.** Le prompt exige déjà des
mots génériques pour un document, donc le signal est DANS l'index.
`tagging_meta.candidat_sensible` est une règle pure (aucun modèle, aucun GPU,
aucun NAS) et `GET /api/sensibles/candidats` la mesure en lecture seule.
**560 → 278 → 214** après deux resserrages sur le vrai fonds. Il s'améliore
tout seul : 7 des 214 seulement portent déjà le nouveau vocabulaire.

**CE QUI ATTEND MIKE** : `QUESTIONS_MIKE.md` — masquer les 214, ou seulement
les plus sûrs, ou lui montrer une planche d'abord. Et `MARCHE_A_SUIVRE.md`
pour le reste.

## Prochain pas

**0. D'ABORD : la campagne va-t-elle bien ?** `/reglages` → `config.retag`
(`reste`, `en_file`, `abandons`). `en_file` à 0 longtemps = le GPU jeûne.
Puis le débit (`tagué en`) et la température (`🌡`, `🔥 CHAUD` ≥ 85 °C).
Et : `grep "Temporary file" _journal_serveur.log` doit rendre **zéro** — c'est
le défaut du 07/09, corrigé ; s'il revient, la correction a lâché.

**1. La réponse de Mike sur les 214** (`QUESTIONS_MIKE.md`). S'il dit oui, le
geste est un `POST /api/sensibles/etat` par lot avec `etat: 'en_attente'` et un
motif — la route existe, elle refuse nommément ce qui n'est pas à lui.

**2. Ce qui reste à REGARDER sur la page `/sensibles`** :
  - les **PIXELS** : le 08/09 la fenêtre Chrome de Mike était minimisée
    (`innerWidth = 0`) et une mesure prise là ne vaut rien ;
  - le masquage **POUR LES AUTRES**, prouvé par banc seulement — l'admin voit
    tout par construction, la preuve demande deux comptes (Mike et Flo).

**3. La seconde moitié du garde-fou NAS** : un scan qui arrive sur une étape
lourde de maintenance DÉJÀ partie. Attention, la ligne `nas = first or deep or
(cycle % NAS_SCAN_CYCLES == 0)` porte un garde-fou voulu, avec son banc — ne
pas la changer sans mesure.

**4. Reprendre la mesure des sensibles sur `qwen3.5:4b`**, avec les 24 verdicts
humains du 06/09 comme vérité terrain — **après la campagne** : un banc qui
interroge le modèle maintenant lui prend le GPU.

**5. (c), quand la campagne sera finie.** Deux voies, aucune tranchée :
bumper une fois le fonds à jour, ou sortir la question du prompt de tagging —
ce que la spec refusait (« pas de cinquième pipeline »). C'est une question
pour Mike, pas une évidence technique.

## En fin de projet

- **La copie hors site (12 bis)** attend la fin du chantier 17 : DS224+ →
  Infomaniak Swiss Backup, ~CHF 6/mois pour 1 To, clé imprimée, restauration
  d'épreuve. Ne PAS toucher au Takeout `C:\GOOGLE PHOTOS\extrait` avant.
- **HTTPS : FAIT** — `https://msi-mike.goat-draco.ts.net/`.
- **Deux brouillons sont DANS l'index** : `_collage6.py` et `_collage7.py`,
  les scripts d'un soir qui ont fabriqué les planches du 06/09. Le motif
  `_collage*.py` est entré dans `.gitignore` le 08/09, mais un `.gitignore` ne
  détache rien : `git rm --cached _collage6.py _collage7.py`, geste de Mike.
- **Le 9 septembre au matin** : le Patch Tuesday est tombé le 8. Vérifier que
  Windows a DEMANDÉ avant de redémarrer (trois réglages posés le 28/08, aucun
  prouvé) — et si la machine a redémarré, relancer le bat 0, sinon rien ne
  repart.

## Réflexes

### Mesurer

**Un attribut du navigateur n'est pas une garantie.** `loading="lazy"` était en
place sur la vue Dossiers et n'a rien empêché : sa marge appartient au
navigateur, et surtout il ne BORNE pas le nombre de requêtes en vol. Ce qui
protège, c'est ce qu'on écrit soi-même et qu'on peut mesurer.

**Un chiffre moyen peut cacher qu'il n'y a pas de chiffre.** La doc annonçait
« ~15 min de GPU perdu à chaque redémarrage ». Mesuré sur les quatre
redémarrages du 06/09 : 69 s, 99 s, 51 min, 81 min. Ce n'était pas un coût mais
une DÉPENDANCE — au NAS — et la moyenne la faisait passer pour supportable.
Avant de citer une durée, regarder sa dispersion.

**Un instrument qui interroge le mauvais CHAMP répond parfaitement à la
question qu'on lui pose.** La passe des tmp orphelins cherchait `retag_fail`,
la marque du TAGUEUR — mais ces photos-là sont fermées par
`retro_write_metadata` (`write_fails` + `file_error`). Elle a rendu « 0 photo »
sur quatorze tmp bien présents, banc vert à l'appui. Avant d'écrire une passe
de rattrapage, chercher TOUS les endroits qui posent la marque qu'on veut lever.

**« Rien à faire » n'est pas « échec ».** `ramasser_tmp_exiftool` rend False
quand il REFUSE d'effacer et quand il n'y a RIEN à effacer ; la passe lisait
les deux comme un refus et laissait 9 photos fermées alors que plus rien ne les
fermait. Même famille que le seau « illisible ».

**Un mot français d'un seul terme décrit une SCÈNE au moins aussi souvent
qu'une pièce.** Le filet des candidats proposait 560 photos : `relevé` (cheveux
relevés), `lettre` (les lettres d'une citation), `message` et `conversation`
(deux personnes qui se parlent). Puis, après avoir OUVERT les photos,
`passeport` (une vieille photo de famille numérisée) et `code qr` (un panneau
publicitaire). 214 restent. **Ce qui est fiable, c'est ce que le PROMPT impose**
(`document`, `recu`, `capture`) — un contrat, pas une devinette sur le
vocabulaire du modèle.

**Un instrument juste sur le principe peut mesurer la mauvaise grandeur.** Le
banc de la corbeille cherchait par sha256 dans un fonds dédoublonné par les
PIXELS : 37 « dernières copies » dont 30 étaient de vrais doublons. Avant
d'écrire un banc, demander par quel critère la donnée interrogée a été produite.

**Un drapeau qu'on ne voit pas ne se prouve pas.** `SCAN_NAS_EN_COURS` ne fait
céder la maintenance que quand une étape est DUE — une fois par jour. Une ligne
dans `/api/maint/status` (`boucle.scan_nas`) a suffi à le voir en réel à 88 s
d'uptime. Quand une correction n'est visible que rarement, c'est le drapeau
qu'il faut exposer, pas la preuve qu'il faut attendre.

**Un banc VERT sur la VM peut être ROUGE chez Mike : la console est en
cp1252.** `test_tmp_exiftool` imprimait un `⚠` ; sous UTF-8 il passait, sous
cp1252 les trois cas de refus tombaient sur `UnicodeEncodeError`. Le serveur
est protégé (`journal_serveur`), un banc lancé à la main ne l'est pas. Parade :
capturer la sortie (`redirect_stdout`), ce qui permet en plus d'exiger que le
refus soit NOMMÉ. Contrôle : `PYTHONIOENCODING=cp1252 python3 -m unittest …`.

**Une sonde qui coûte autant que ce qu'elle mesure est un échec de conception.**
479 s pour relire 389 manifestes et savoir où en était le bat 46 — parce que
l'outil ne disait rien. C'est au travail de rendre des comptes.

**Chercher le banc AVANT d'éditer.** Signature changée sans voir
`test_appliquer_strip_motionphoto.py` : six bancs rouges, deux refus de l'agent
Git. Le refus est une bonne nouvelle ; l'avoir mérité n'en est pas une.

**Le seau « je n'ai pas compris » n'est pas un seau vide.** Le banc sensibles
rendait `illisible` quand le modèle ne répondait pas — 19 fois sur 90 — et
c'est là que dormaient les pièces les plus sensibles de l'échantillon.

**Un banc mesure le modèle qu'il NOMME, pas celui qui tourne.** Relire
`modele.txt` avant de citer une mesure.

**Un zéro parfait est une alarme au même titre qu'un cent.** « 374 disparues,
0 retrouvée » : le banc lisait un `tags_index.json` que le passage à SQLite
avait laissé mort.

**Une mesure prise dans une fenêtre minimisée ne vaut rien** : Chrome rend
`innerWidth = 0`. Vérifier le viewport avant de croire un pixel — et avant de
juger une page, la redimensionner (`resize_window`) ne suffit pas si la fenêtre
est réduite.

**Un marqueur n'est pas la chose.** `SEFT` en queue ≠ Motion Photo : 16 519
JPEG portent un trailer SEF de MÉTADONNÉES sans vidéo.

**Les fils n'accélèrent pas un partage SMB déjà saturé** : 8 lecteurs ont fait
MOINS que 1 (2,6 contre 4,5 fichiers/s).

**Ne JAMAIS supposer un chiffre gagné avant de l'avoir mesuré en réel sur la
machine cible.** Trois chiffres différents pour la même question en une
semaine ; le solide était le RATIO (~3×), jamais le nombre de jours absolu.

**Le canal du banc n'admet que `[A-Za-z0-9_.:/=-]`** (espaces via jeton
`b64:`), plafond **600 s** : un banc long est REPRENABLE et se lance avec
`--budget-s 450`.

**Ne JAMAIS lancer `unittest discover` depuis la VM** : plusieurs tests
importent `server.py`, qui ouvre `photos.db` — la VM ne sait pas l'ouvrir
par-dessus le montage. Un test qui a besoin du code de `server.py` le lit par
`ast` ; ceux-là tournent très bien depuis la VM, un par un (~20 s chacun).

**ExifTool sous Windows perd les accents des arguments** : argfile UTF-8 BOM.

**Pour transférer un script accentué : `device_commit_files`, pas un heredoc**
(`device_bash` tronque à ~4 Ko sans le dire). **Mais** `device_commit_files`
peut écrire la version PRÉCÉDENTE du fichier : deux fois en deux jours, un
fichier édité puis committé sous le MÊME `devicePath` est arrivé dans son état
d'avant, sans que rien le dise. Parade : committer sous un nom NEUF puis `mv`
en place, ou vérifier après coup par un `grep`. Les deux fois, c'est un banc
qui l'a vu.

**`device_stage_files` échoue sur `N:\Photos`** (« Could not stat ») alors que
`device_bash` y accède : pour REGARDER une photo, la copier d'abord dans
`C:\Prog\Claude\MediaLibrary` (`cp` depuis `$HOME/mnt/Photos/…`), la stager de
là, puis l'effacer.

**Un banc mesure CE QU'IL MESURE.** Le banc d'endurance rendait 8,9 s/photo —
l'appel au modèle SEUL ; la production paie deux passages d'ExifTool en plus :
**14 s**. Demander ce que le banc n'exécute PAS.

**Le POIDS d'un fichier ne dit rien de son contenu.** 941 fichiers de 2 à 3 Mo
étaient remplis du texte « Read error in the sector ! ».

### Lire

**Le journal du serveur d'abord**, depuis la dernière bannière :

    L=$(grep -n "===== DEMARRAGE" _journal_serveur.log | tail -1 | cut -d: -f1)
    tail -n +$L _journal_serveur.log | grep -n "FIL MORT\|THREAD MORT\|Traceback"

Le journal est **borné à 4 Mo + une archive** : après une nuit de campagne, la
dernière bannière peut avoir quitté `_journal_serveur.log` (elle est dans
`_journal_serveur.log.1`). Un `max()` sur une liste vide, c'est ça.

**Un grep large attrape des innocents** : `grep -i "echec"` sortait une photo
taguée « jeu d'echecs ». Lire la ligne, pas le compte.

**Savoir d'où vient un chiffre.** `verifier_photos_google` lit le DISQUE ;
`generer_plan_annee` lit l'index en mémoire.

**`.git/logs/refs/heads/main` se lit en texte, sans `git`.** `_etat_git.json`
a un tableau `historique` : plus rapide qu'un `git log`, sans jamais invoquer
git.

### Juger

**Avant de RECOMMANDER une règle, relire `eval/DECISIONS.md` en entier sur le
sujet.** Le carnet n'est pas un journal — c'est la contrainte. **Une clôture
n'est pas éternelle** : elle reste vraie SUR CE QU'ELLE MESURAIT.

**Le carnet des décisions se DÉCOUPE quand il déborde** (choix de Mike, 20/08
puis 07/09) : l'outillage dans `docs/DECISIONS_OUTILLAGE.md`, l'écran dans
`eval/DECISIONS_UI.md`. Condenser les verdicts de Mike ou relever le seuil sont
les deux mauvaises réponses.

**Un rattrapage ne doit jamais dépendre de la ressource qui vient de tomber.**

**Un `replace` sur un motif présent DEUX fois touche le mauvais — `assert
count == 1` avant.** Et une assertion d'ORDRE se trompe pareil :
`corps.index('try:')` prenait le PREMIER `try:` de la fonction. Juger la
FENÊTRE qui suit le geste, pas le fichier entier.

**Un banc juge du CODE, pas d'une prose** : `_corps()` retire la docstring,
sinon un banc tombe sur l'explication de ce qu'il vérifie.

**Un banc vert n'est pas un regard.** Deux mots du filet n'ont été retirés
qu'après avoir OUVERT les photos.

**Un instrument ne condamne JAMAIS ce qu'il n'a pas vu — et ne passe jamais au
vert dessus.** Pas de faute sans lecture, pas de vert sans preuve.

**« Déjà fait » n'est pas un échec.** Deux bats l'ont crié à tort (45 puis 42).

**Un `return` anticipé emporte le travail qui SUIT.**

### Toucher

**`ui/pages/` et `ui/*.css` sont relus À CHAUD** ; seul `server.py` exige un
redémarrage — qui coûte 9 s de GPU depuis le 07/09, plus l'énumération pendant
laquelle le GPU, lui, travaille.

**Le prompt EST la version du pipeline.** Toucher à `REGLES_JSON` ou à
`prompt_tagging` oblige à bumper `TAGGING_PIPELINE_VERSION`, et un bump rend
candidat tout le fonds. Pendant une campagne, c'est interdit.

**Jamais deux écrivains sur `photos.db`.** Le serveur est l'écrivain unique.

**Un `_exiftool_tmp` orphelin fermait la photo pour toujours** — corrigé le
07/09 : `write_metadata` le ramasse SUR PREUVE (photo présente et plus grosse
que le tmp) puis réessaie une fois, et le `except` du timeout ramasse ce qu'il
vient d'orpheliner. Le balayage du disque reste interdit.

> **`N:\Photos` se CONNECTE à chaque session** (picker « Add folder », non
> persistant) : demander à Mike au « Go ». Il EST monté dans `device_bash`
> (`$HOME/mnt/Photos`) : listage rapide, lecture à ~5 fichiers/s — un coup
> d'œil oui, un script sur tout le fonds non (agent banc).
>
> **Piège git via `device_bash`** : jamais de git d'ici (`.git/index.lock`
> résiduel indélébile), même en lecture seule. `_etat_git.json` et les
> `.git/logs/*` lus en texte suffisent toujours.
>
> **`device_bash` ne peut ni effacer ni déplacer** dans les dossiers montés
> tant que Mike n'a pas approuvé la demande de suppression. Écrire ses
> brouillons HORS de `mnt/` (`$HOME`), et ne rien poser à la racine du dépôt
> qu'on ne sache pas retirer — l'agent Git le prendrait.
>
> **Piège d'horloge** : `device_bash` est en **UTC** (−2 h chez Mike).
>
> `copie.db` s'ouvre en `mode=ro` depuis la VM ; `photos.db`, jamais.

# Amorce de reprise — MediaLibrary

> À coller après connexion de `C:\Prog\Claude\MediaLibrary`. Règles et
> protocole : `CLAUDE.md`. Ici : **l'état et le prochain pas, rien d'autre.**

Tu reprends **MediaLibrary**. **VÉRIFIE avant de lire** : `.git/HEAD`,
`.git/logs/HEAD` et `.git/logs/refs/heads/main` disent ce qui a été commité et
FUSIONNÉ — ce document, non. Puis `ROADMAP.md`, `eval/DECISIONS.md`,
`eval/METHODE.md`. **QUATRE carnets, découpés par domaine** :
`eval/DECISIONS.md` (la photothèque : reconnaissance, visibilité, recherche),
`eval/DECISIONS_TAGGING.md` (ce que le MODÈLE écrit — sorti le 08/09),
`eval/DECISIONS_UI.md` (l'écran — 07/09), `docs/DECISIONS_OUTILLAGE.md` (les
canaux, la livraison, le pont — 20/08). Budget de chacun : **125 000 octets**
depuis le 08/09. Débrief en 2–3 lignes, puis on attaque.

## Où on en est (08/09/2026, fin de journée)

**Git** : dernier commit fusionné dans `main` — le vérifier dans
`.git/logs/refs/heads/main`, jamais ici. **Onze livraisons le 08/09.**

**LA CAMPAGNE DE RETAG TOURNE.** Levier : `retag_actif.txt`, fichier VIDE —
ne pas l'effacer. Lu sur la machine le **08/09 à 23:54** (`config.retag`) :
**reste 23 467, en file 817, abandons 0** — soit **~3 800 photos faites dans la
journée**, malgré cinq redémarrages. Débit des trois dernières heures : 236,
218, 210 — **~220/h**, donc **~4,5 jours** encore. Zéro `Traceback` au journal.

**Le débit se COMPTE dans le journal, il ne se calcule pas** : **~200 photos par
heure**, mesuré heure par heure sur une journée (200, 196, 172, 191, 216, 175,
178, 239, 265), **14 à 16 s médian**. Reste donc **~5 à 6 jours**. Les
« 14 s → 4 jours » de la veille divisaient une durée par photo par 24 h, ce qui
suppose le GPU occupé sans interruption : la maintenance et le reste
s'intercalent. *Une durée par photo n'est pas un débit.*

**Sur les « abandons », deux lectures VRAIES qui ne parlent pas de la même
chose** — et je me suis trompé en corrigeant l'une par l'autre. Le compteur
`config.retag.abandons` dit **0** : aucune photo prise puis lâchée. Le journal
porte **13 lignes « abandon — listé sur /sante »** : des **refus d'entrée**, des
fichiers déjà connus comme malades que le tagueur ne prend jamais (Mumi 6,
Sandra 5, Sista 2, tous dans `Photos Flo`). Le même mot pour deux gestes.
**Ne corrige jamais un compteur par un journal sans vérifier qu'ils comptent la
même chose.**

Instruments : `/reglages` → `config.retag`, `grep 'tagué en' _journal_serveur.log
| awk '{print substr($1,1,2)}' | uniq -c` pour le débit horaire, et
`grep abandon _journal_serveur.log` pour les refus d'entrée.

**LE CHANTIER 18 : (a) ET (b) SONT FAITS.**
- **(a) l'axe `sensible`** — la visibilité ne se décide plus sur le seul
  CHEMIN. Les cinq magasins et le garde des octets consultent l'ÉTAT ; l'axe
  vit en base, jamais dans le XMP. Qui lève un masque : le propriétaire ET
  l'admin (tranché par Mike le 07/09 — sinon une photo d'un dossier sans compte
  serait masquée à tort pour toujours).
- **(b) la page `/sensibles`** — trois gestes, **Corbeille en premier**
  (« la médiathèque conserve des souvenirs, pas des documents », Mike, 07/09),
  puis Rendre privée, puis Pas sensible. Chaque geste passe par la route qui
  existait déjà. L'onglet de nav reste **caché tant qu'il n'y a rien** — et il
  l'est VRAIMENT depuis le 08/09 seulement : il portait `hidden` et s'affichait
  quand même, sur toutes les pages, parce qu'une classe posant `display` bat le
  `[hidden]` de la feuille du navigateur.

**(c) EST EMPÊCHÉE PAR LA CAMPAGNE, et c'est le fait neuf du 08/09.** La spec
veut la question « dans la MÊME invocation du tagueur ». Or le prompt EST la
version du pipeline (`v3fr`) : y ajouter une phrase rendrait candidates les
12 000 photos déjà refaites. Rien n'a été touché.

**À la place : un FILET, disponible aujourd'hui.** Le prompt exige déjà des
mots génériques pour un document, donc le signal est DANS l'index.
`tagging_meta.candidat_sensible` est une règle pure (aucun modèle, aucun GPU,
aucun NAS) et `GET /api/sensibles/candidats` la mesure en lecture seule.
**560 → 278 → 214** après deux resserrages sur le vrai fonds.

**ET LE GESTE A ÉTÉ FAIT** (Mike, 08/09 : « go pour ta recommandation b »).
**213 photos masquées** — une de moins que la mesure, re-taguée entre-temps et
ayant perdu son mot-clé : le filet respire avec la campagne. **0 refus, 0
candidat restant.** Chacune porte SON motif, pas un motif de lot. Le tri des
213 dans l'onglet est maintenant du travail de Mike : trois gestes par photo,
tout réversible, rien n'a bougé sur le disque.

**LE 08/09 A ÉTÉ LE PREMIER JOUR OÙ ON A VU LES PIXELS**, et ça a coûté cinq
défauts qu'aucune relecture n'avait vus. Tous dans `eval/DECISIONS_UI.md` :
l'onglet `hidden` qui s'affichait ; la page qui bâtissait ses 213 fiches d'un
coup (63 299 px, moteur de rendu **gelé**) — ramenée à 12 159 px par des
tranches de 40 et `loading="lazy"` (7 requêtes au lieu de 213) ; le lien
« Ouvrir la photo en grand » à 18 px ; les cibles tactiles sous 44 px sur
douze pages ; et six `class="btn"` sur `/reglages` **sans la feuille qui
définit `.btn`**.

**44 PX PARTOUT, tranché par Mike le 08/09, implémenté et audité.** Corrigés :
les 5 onglets d'`appnav` (32 px), la marque « Photos » (20), la sous-navigation
Sujets (`min-height:36px` écrit EN DUR, 4 pages), les champs de recherche de la
galerie (33), de la carte (36) et des personnes (33), les 2 boutons de la barre
de la carte (36 et 34), et `/reglages` qui a adopté `components.css`. **Mesuré
après** : `/files` — la page la plus utilisée — **104 contrôles, 0 sous 44 px**.
Tout ce qui reste sous 44 est un `<a>` DANS un `<p>`, exempté par WCAG 2.5.8, ou
un contrôle Leaflet. **L'exemption est désormais ÉCRITE** : c'est son absence
qui avait laissé les onglets à 32 px pendant treize jours.

**L'ESPACE DISQUE : mesuré le 08/09, et ce n'est pas où on le cherchait.**
C: n'a que **75,5 Go libres sur 1 To**. Le ménage du dépôt (les « undo », les
rapports, les quarantaines) rend **0,4 Go**, pas cent — c'est déplacé dans
`_to_delete\`, à vider à la main. Le vrai gisement est une DUPLICATION :
`C:\GOOGLE PHOTOS` pèse **191 Go**, deux fois le même contenu (45 `.zip` +
leur extrait). `verifier_takeout_ouvert.py` a prouvé l'extrait complet
(45 lots, 0 absent, 0 tronqué) : **`48 - Effacer les archives ZIP du Takeout
(95 Go).bat`** refait la preuve puis efface, sur un OUI. Le NAS, lui, a
**2 980 Go libres** — ses 35,5 Go de `.corbeille-rangement` ne gênent
personne, et le Takeout n'y est PAS. Détail chiffré : ROADMAP § 1 septies.
L'instrument : `mesure_espace_disque.py --ou depot|takeout|nas|corbeilles`,
lancé par l'agent des bancs (le pont lit 110 fichiers/s, un `du` y prend
des heures — 22 s côté Windows contre un dépassement de délai côté VM).

**LE TAKEOUT : où en est la chaîne, au soir du 08/09.** Mike a lancé le bat 48
(**45 archives `.zip` effacées, C: de 75,5 à 171,2 Go libres**) puis le bat 32
(**570 médias copiés sous `_A TRIER\Takeout Google\<année>`, 0 grief**, journal
d'annulation dans `_corbeille_copies\copie_20260908_223100.jsonl`, 570 lignes
exactement). Il reste `C:\GOOGLE PHOTOS\extrait`, 95,78 Go — la SEULE copie
désormais.

**OÙ EN EST LA CHAÎNE, au matin du 09/09** : bat 32 fait (570 copiées),
**bat 26 fait** (613 rangées vers `Photos Mike\<année>`), vérification faite
(**ABSENT 0**), **bat 33 fait** (99 rapatriées, 1 814 vidéos de Motion Photo
écartées). **Il reste** : laisser le scan reprendre les 613 déplacées et les 99
arrivées, **relancer `verifier_photos_google.py`** — le compte bougera — puis
**bat 49**. Ne pas sauter la vérification : la copie place les fichiers, c'est
le SCAN qui les fait exister pour elle. Et rappeler à Mike, avant qu'il
confirme, que la copie hors site (12 bis) n'existe toujours pas.

**UNE RÈGLE PRODUIT NEUVE, ET ELLE COMMANDE** (Mike, 09/09) : *une Motion
Photo ne garde que son image, et sa vidéo ne se rapatrie JAMAIS* — même quand
Google en est le dernier détenteur et que l'effacement est définitif. C'était
un réglage involontaire du téléphone. **Le vrai correctif est en amont** :
couper « Photo animée » dans l'appareil photo Samsung, sinon le bat 42 devra
repasser indéfiniment.

**DEUX RESTES CONNUS** : 14 fichiers SANS EXTENSION (2 à 11 Ko) dans
`_A TRIER\Takeout Google\2024|2025`, jamais lus — `device_stage_files` refuse
`N:\Photos` (« Could not stat ») et le montage de `device_bash` était tombé le
09/09 ; y revenir quand le pont va bien. Et le libellé du bat 26 : « source
absente » 613 fois pour dire « déjà rangée ».

**CE QUI ATTEND MIKE** : rien à décider — `QUESTIONS_MIKE.md` est vide. Les
gestes : bat 26 puis bat 49 (dans l'ordre ci-dessus), vider `_to_delete\`
(366 Mo), et trier les 213 photos sensibles. Et `MARCHE_A_SUIVRE.md` pour le
reste.

## Prochain pas

**0. D'ABORD : la campagne va-t-elle bien ?** `/reglages` → `config.retag`
(`reste`, `en_file`, `abandons`). `en_file` à 0 longtemps = le GPU jeûne.
Puis le débit (`tagué en`) et la température (`🌡`, `🔥 CHAUD` ≥ 85 °C).
Et : `grep "Temporary file" _journal_serveur.log` doit rendre **zéro** — c'est
le défaut du 07/09, corrigé ; s'il revient, la correction a lâché.

**1. LA CHAÎNE DU TAKEOUT, là où Mike l'a laissée** (voir plus haut) : scan →
bat 26 → vérification → bat 49. C'est le seul fil qui attend un geste ce
matin-là. Tout le reste peut attendre la fin de la campagne.

**1 bis. Les carnets vont bien, ne pas y revenir.** Budget 125 000,
`eval/DECISIONS.md` à ~54 % après la sortie du TAGGING. La troisième voie —
condenser les verdicts anciens — reste disponible et n'a PAS été utilisée :
elle demande de relire pour décider quoi perdre, et ça ne se fait pas au
chausse-pied. C'est le levier du jour où le seuil redevient proche.

**2. REGARDER LES PIXELS — c'est acquis, et voilà comment.** Deux navigateurs, et
la différence compte :
  - **Le Chrome de Mike** (`mcp__claude-in-chrome__*`) porte SA session : c'est le
    seul qui atteint les pages authentifiées. Il faut qu'il soit **connecté** et
    la fenêtre **non minimisée**. Adresse : `http://192.168.0.13:8080` (pas
    `localhost`, qui viserait la machine du navigateur).
  - **Le volet Navigateur de l'app** a son propre profil, donc **aucune session** :
    il sert pour la page de connexion et rien d'autre tant que Mike n'y ouvre pas
    une session lui-même (taper un mot de passe n'appartient pas à Claude).

  **Deux pièges payés le 08/09.** (i) `document.visibilityState === 'hidden'` :
  une image `lazy` ne se charge JAMAIS dans un onglet qui n'est pas au premier
  plan — j'en ai tiré une conclusion fausse et failli l'écrire dans le dépôt.
  Lire `visibilityState` ET `innerWidth` AVANT d'interpréter. (ii) L'extension
  **gèle** si on lui demande douze iframes dans un seul appel : mesurer **une
  page par appel**, et repartir d'un onglet neuf quand le moteur ne répond plus.

  **Reste à voir** : le masquage **POUR LES AUTRES**, prouvé par banc seulement —
  l'admin voit tout par construction, la preuve demande deux comptes (Mike et
  Flo). Et les **3 pages qui n'ont pas adopté `components.css`** (`browse`,
  `faces`, `map`) — aucune ne ment aujourd'hui, mais la première qui écrira
  `class="btn"` mentira.

**3. Le garde-fou NAS est COMPLET depuis le 08/09** — les deux sens. La
maintenance cède à un scan qui tourne (06/09) ET le scan REPORTE son volet NAS
quand une étape lourde parcourt déjà le fonds, sans perdre l'échéance et avec
un plafond de 3 reports. **Ce qui n'est pas prouvé, et il faut le dire** : la
collision elle-même n'a jamais été observée — le banc tient la mécanique, le
redémarrage montre la non-régression. Si un jour `⏸ scan NAS reporte` apparaît
au journal, c'est la première observation réelle : la noter.

**4. Reprendre la mesure des sensibles sur `qwen3.5:4b`**, avec les 24 verdicts
humains du 06/09 comme vérité terrain — **après la campagne** : un banc qui
interroge le modèle maintenant lui prend le GPU.

**5. (c), quand la campagne sera finie.** Deux voies, aucune tranchée :
bumper une fois le fonds à jour, ou sortir la question du prompt de tagging —
ce que la spec refusait (« pas de cinquième pipeline »). C'est une question
pour Mike, pas une évidence technique.

**6. Les Motion Photos arrivées depuis le 03/09** — le chantier est clos pour
celles d'alors (bats 42 et 43 faits, vérifiés par deux instruments le 08/09),
mais `_Uploads` en dépose de nouvelles. `mesure_motion_photos.py` compte ;
**le bat 42 exige le serveur ARRÊTÉ**, donc après la campagne.

**7. LE FILET DES SENSIBLES SE REMPLIT TOUT SEUL — le vérifier de temps en
temps.** Au 08/09 23:54, `GET /api/sensibles/candidats` rend **1** : une photo
re-taguée dans la journée porte un mot-clé du filet. C'est exactement ce qui
était annoncé le matin (« le compte montera tout seul à mesure que la campagne
avance »), et c'est la première preuve que ça marche. Les 570 rapatriées du
Takeout — dont **394 captures d'écran** — vont s'y ajouter dès qu'elles seront
taguées : Mike les jettera d'un clic depuis l'onglet.

## En fin de projet

- **La copie hors site (12 bis)** attend la fin du chantier 17 : DS224+ →
  Infomaniak Swiss Backup, ~CHF 6/mois pour 1 To, clé imprimée, restauration
  d'épreuve. **C'est devenu URGENT le 08/09** : Mike a effacé les 45 `.zip` du
  Takeout et veut effacer l'extrait. Après ce geste, **le NAS est la seule
  copie du fonds** — il est chez lui, il ne protège ni du feu, ni du vol, ni
  d'une fausse manœuvre. Le lui redire avant le bat 49, sans dramatiser : il a
  tranché en connaissance de cause, la sauvegarde cloud est prévue.
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

**Une règle sans son EXCEPTION écrite ne tient pas.** Le plancher disait
« cibles tactiles ≥ 44 px » sans dire pour QUOI : les onglets sont restés à
32 px pendant treize jours, et personne n'avait tort — chacun jugeait dans son
coin faute de texte. La règle complète, écrite le 08/09 : **le plancher vaut
pour tout ce qui SE VISE — bouton, onglet, chip, champ, barre d'outils — et
jamais pour un lien porté par une ligne de texte** (WCAG 2.5.8 l'exempte). Quand
une règle du système est enfreinte quelque part, le premier réflexe est de
chercher si l'exception est légitime **et écrite** : si elle l'est, l'écrire ;
sinon, corriger.

**Une décision se propage par le JETON, jamais par un nombre.** `min-height:36px`
écrit en dur dans la sous-navigation a survécu à deux décisions de Mike sur la
même valeur. `var(--touch)` les aurait suivies toutes seules.

**Un nom de classe qui ne fait rien est pire qu'une classe absente.** Six
`class="btn"` sur `/reglages` sans `components.css` : le nom du design system,
aucun de ses comportements. Une classe absente se voit ; une classe muette fait
croire que la règle s'applique. `components.css` est OPT-IN — vérifier le
marqueur `<!--UI:components-->` avant de faire confiance à un `.btn`.

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

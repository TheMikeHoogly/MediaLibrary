# Feuille de route — MediaLibrary

Carte des **priorités**, rien d'autre. Les récits de travaux terminés vivent
dans **git** ; les rejets dans `eval/DECISIONS.md` (photothèque) et
`docs/DECISIONS_OUTILLAGE.md` (canaux, pilotage, livraison) ; la méthode dans
`eval/METHODE.md` ; l'éphémère dans `PROMPT_NOUVELLE_SESSION.md`. Audits :
`docs/AUDIT_INTERNE_2026-08.md`, `docs/AUDIT_EXTERNE_2026.md`, `docs/RANGEMENT_2026.md`.

> **`N:\\Photos` se connecte à chaque session** — règle dans `CLAUDE.md`
> (« Tester en réel »), depuis le 29/08.

## Priorité (26/08/2026, refixée session 53) — le garde-fou est POSÉ

**Le point 1 est fait, prouvé, livré** (voir l'état de session 53 ci-dessous) :
un jeton `<axe>:<valeur>` insatisfaisable rend RIEN et le DIT sur les cinq
axes, la barre comprend enfin ce que les pastilles écrivent, et le contrôle
NÉGATIF est un banc (`verifier_filtre_negatif.py`, 15 contrôles, deux canaux).
Le point 4 de la liste précédente — le déplacement `Photos Mike` — était déjà
fait en session 52. L'ordre reprend donc à ce qui reste.

**1. Les boutons de `gallery` — FAIT, y compris l'œil TÉLÉPHONE (27/08,
session 59) ; reste `.fchip`.** Le banc vivant, l'œil bureau (session 58) puis
l'œil à 390 px (session 59) sont passés — et le passage mobile a trouvé et
corrigé un vrai défaut : la rangée de la visionneuse débordait, « Fermer »
était hors écran. Ne reste que la décision `.fchip` (question ouverte dans
`QUESTIONS_MIKE.md`).

**1 bis. Ce qui restait de l'option 1 tranchée le 26/08 :** Les cinq familles maison (`.tb` 34 px, `.geobtn`
28 px, `.fchip` 35 px, `.georow button` 34 px, `#ss-stop` 34 px) passent au
`.btn` canonique. Coût mesuré et accepté : **+19 px** de hauteur de barres.
Aperçu validé (artefact « Boutons de la Galerie »). Preuve dans l'ordre
habituel : `verifier_css_cascade --page` (feuille commune EN PREMIER dans
`--apres`), `verifier_cibles`, `verifier_contraste`, `verifier_controles`,
tests UI, banc des pages composants sur le serveur VIVANT, l'œil en dernier.

**1 ter. La résilience des fils de travail : FAIT (session 61)** — superviseur,
relance à attente doublante, cinq morts consécutives alertent (`/sante` + journal).

**1 quinquies. Google — VÉRIFIÉ (29/08, session 64) : Mike EFFACE chez
Google, le correctif de réparation est MESURÉ.** Les 297 « Google porte
mieux » sont rapatriés ; la vérification finale : ABSENT 0, et les **199
« NAS plus petit » sont nos propres copies** — 14 Motion Photos passées par
`repair_file` (trailer jeté, `_original` intact 14/14) et 185 à −2…−57 Ko
de padding, zéro tag perdu. Mike a le feu vert (voir la marche dans le fil du
29/08). **Correctif tranché par le banc** (`verifier_reparation_exif.py`, sur
une COPIE d'un Motion Photo) : sur un fichier où l'écriture EXIF normale
échoue (« Error reading OtherImageStart »), il ne faut PAS appeler
`repair_file` (candidats A et B détruisent le trailer ou l'ICC) — il faut
retomber sur une écriture **XMP+IPTC seulement** (candidat C : +501 o, SEFT
gardé, ftyp gardé, ICC gardé, 189 tags, mots-clés écrits). Donc :
`write_metadata` détecte l'échec « OtherImageStart » et bascule sur
`-XMP-dc:Subject`/`-IPTC:Keywords` au lieu de réparer ; un banc l'exige sur
un Motion Photo. Ne PAS toucher au Takeout de `C:\GOOGLE PHOTOS\extrait`
avant la copie hors site (seule 2e copie des Motion Photos complets).

**1 sexies. Le rangement des 1 217 A REBONDI (29/08) — cause : le plan n'est
régénéré QUE par le bouton Réglages, jamais au démarrage.** `cible()` était
corrigé et gravé, mais le plan `docs/plan_rangement_annee.json` datait du 28/08
18:57 (cibles RACINE) ; bat 26 l'a relu et re-rangé à la racine ; bat 34 a
refusé les 17 dossiers (pleins) — rien perdu. **Garde-fou posé + testé**
(`appliquer_plan_annee.plan_vise_la_racine`) : bat 26 refuse un plan qui vise
la racine. **Deuxième étage posé (29/08, session 65, CODÉ, à observer au
redémarrage)** : `_run_plan_annee()` tourne à chaque démarrage (`fil_surveille`,
un coup) et `appliquer_plan_annee.plan_perime` refuse un plan plus vieux que la
dernière bannière `DEMARRAGE` du journal (test 7 vert). Un plan applicable est
donc toujours un plan calculé sur l'index qu'on vient d'arrêter. Reprise :
redémarrer (le plan sort au démarrage : ligne `🗂 plan rangement annee` au
journal) → vérifier qu'il vise `Photos Mike` → arrêt → bat 26 → bat 34. `_Uploads` → boîte de réception par propriétaire : TRANCHÉ
(`eval/DECISIONS.md`).
**Session 66 (29/08, 13:22)** : bat 26 a tourné, **29 rangés** sur 38 ; les
**9 restants** sont des ré-encodages Google (9 des 21 `IMAGE_DIFFERENTE`)
dont le fonds a déjà l'homonyme — même noms, et le NAS a le GPS que Google a
retiré. Décision Mike : quarantaine des 9 → **bat 37** (`deplacer_doublons_atrier
--homonymes-differents`, opt-in, règle des noms tenue). **FAIT et OBSERVÉ**
(13:49 → index −9 à 13:53 → plan **0 à ranger** à 14:11). Reste bat 34.

**1 quater. Le 9 septembre au matin : VÉRIFIER que Windows a demandé.** Patch
Tuesday tombe le 8 ; le redémarrage arrivait toujours vers 01:30 la nuit
suivante. Trois réglages ont été posés le 28/08 (notification ACTIVÉE,
préversions coupées, `NoAutoRebootWithLoggedOnUsers=1`) et **aucun n'est
prouvé**. Lire `Get-WinEvent -FilterHashtable @{LogName='System'; Id=1074}` et
la bannière du journal : si le serveur a tourné sans interruption, les
réglages tiennent ; sinon la stratégie de groupe n'a pas été honorée et il
faut regarder « Stratégies de mise à jour configurées ».

**1 septies. RÈGLE Motion Photo — MÉTHODE VÉRIFIÉE, à mettre en oeuvre (29/08).**
Règle tranchée (`eval/DECISIONS.md`) : une Motion Photo ne garde que son image,
la vidéo embarquée est jetée. **Méthode confirmée par banc**
(`verifier_strip_motionphoto.py`, sur copie) : `exiftool -trailer:all=` rend
l'image IDENTIQUE au pixel, retire trailer+vidéo, JPEG valide, **−61 %**
(5,45→2,14 Mo). Troncature = JPEG invalide (rejetée), Pillow = perte (rejetée).
Mise en oeuvre en deux temps, réversible : (1) strip sur le fonds — `exiftool
-trailer:all= -ext jpg -ext jpeg -r <racine>`, qui laisse un `*.jpg_original`
(la version complète) POUR les seuls fichiers modifiés et ne touche pas les
autres ; (2) après vérif des stills, purge des `*.jpg_original`. Les paires
`.jpg`/`.jpg_original` déjà présentes dans `Google porte mieux` SONT l'état (1)
— leur purge relève de (2). **À faire** : bat de strip + bat de purge (ou
intégrer à `25 - Maintenance`), et compter d'abord (`mesure_` ou exiftool).

**1 octies. CHANTIER : intégrer les VIDÉOS (comme les images).** Aujourd'hui
les `.mp4` vivent dans `_A TRIER` mais ne sont NI indexées (le scan filtre
`IMAGE_EXT`), NI taguées, NI rangées, NI cherchables. `recensement_doublons.py`
les compte déjà (il inclut `VIDEO_EXT`), mais c'est tout. Plan par phases, la
valeur d'abord :
- **Phase 0 — RANGEMENT par année : OUTILLÉ (session 66), à appliquer par
  Mike (bat 39)**. Sans passer par l'index : `inventaire_videos.py` (lecture
  seule, 21 s sur le NAS) date par le NOM (`AAAAMMJJ_HHMMSS`, `VID-…-WA`),
  sinon ExifTool `-fast` (QuickTime), sinon le dossier année du Takeout —
  jamais le mtime — et écrit `docs/plan_rangement_videos.json` avec la règle
  des photos (`rangement_annee.construire_plan`) ; `appliquer_plan_annee.py
  --plan …` le range (mêmes gardes, même undo). **Mesuré** : 3 073 vidéos,
  73,7 Go, 3 066 datées par le nom, 7 par ExifTool, **0 sans date**, 0 conflit,
  → `Photos Mike\2016…2026` (2024 : 1 509). Question à Mike : les 5 vidéos de
  `180328 Samsung Floflo` vont chez Mike par la règle 17c (`QUESTIONS_MIKE.md`).
- **Phase 1 — vignette/poster** : une image-clé par `ffmpeg` (milieu), affichée
  dans la galerie avec un badge lecture ; lecture dans la visionneuse.
- **Phase 2 — tagging IA** : passer le pipeline vision existant sur 1..N
  images-clés, agréger, ÉCRIRE les mots-clés dans le conteneur MP4 (`exiftool`
  QuickTime/XMP) — analogue à `write_metadata`.
- **Phase 3 — visages/animaux** sur les images-clés, rattachés aux fiches.
- **Phase 4 — recherche sémantique** : encoder l'image-clé, comme une photo.
- Transverse : dédup vidéo (déjà par `recensement_doublons`), gros fichiers
  (le rename gère déjà), coût CPU/GPU de l'extraction+inférence à mesurer,
  `ffmpeg` à installer côté Windows. **Dépendance** : Phase 0 profite du
  correctif `cible()` (rangement par propriétaire) déjà posé.

**2. Le pense-bête des raccourcis DANS l'interface** (point 6 du plancher).
Il manque la brique : **un fichier JS commun injecté sur toutes les pages**,
comme `tokens.css` et `base.css` (`_UI_GLOBAL_FILES`). Il n'y en a aucun. La
brique d'abord, le panneau `?` ensuite, l'instrument en dernier. Contenu
déjà relevé : `docs/RACCOURCIS.md`.

**3. La suite du chantier 17 (multi-utilisateurs)** : la notion de
PROPRIÉTAIRE, puis l'attribution rétroactive des 3 767 décisions à Mike.
Spécifié — six décisions de Mike, plus bas dans ce fichier : l'exécuter, ne
pas le rouvrir. Deux questions ouvertes dans `QUESTIONS_MIKE.md` bloquent
l'écriture partagée.

**3 bis. Le garde-fou de la confidentialité (chantier 18, demandé le 27/08)** :
signaler à l'envoi les photos qui portent des données personnelles — factures,
fiches de paie, pièces d'identité — pour que leur auteur les déplace dans son
`PRIVE` ou les efface. **Le détecteur se greffe sur la passe de tagging qui
regarde déjà chaque photo** : pas de cinquième pipeline. Le geste « déplacer
dans PRIVE » attend 17a ; le reste, non. C'est la seule fuite de ce projet qui
ne demande AUCUNE erreur de manipulation — juste l'oubli d'un geste.

**4. UNIFIER le re-clé** — la réparation est faite (27/08, voir l'état de
session 57), mais la primitive complète existe désormais **TROIS fois** :
`server.rekey_everywhere`, `deplacer_dossiers.recle_une_cle` et
`appliquer_plan.rekey_stores`. Trois endroits où la même règle peut diverger,
et elle a déjà divergé une fois pendant cinq jours. Une seule doit rester.

**5. Le reste d'audit** : O8–O9, O11, O13–O15 ; **I1** visible dans
`/reglages` ; `animal:luna` en minuscule sur 3 photos à côté de `animal:Luna`
sur 355. Puis les quatre pages sans `components.css` (`browse`, `faces`,
`map`, `reglages`). O15 balaie au passage les 3 047 vignettes orphelines du
déplacement — effet de bord attendu, pas une panne.

**Ce qui a changé de nature (26/08)** : les animaux non nommés ne sont plus un
chantier. Deux noms posés par Mike ont fait tomber les groupes de **189 à 99**
et les apparitions non nommées à **442**, plus gros groupe à 31. C'est une
finition, à faire au fil de l'eau.

**En fin de projet, dans cet ordre** : le chantier 17, PUIS la copie hors site
— choix de Mike du 26/08.

**Le Takeout Google : CLOS** (27→29/08) — les 3 776 absentes sont rapatriées,
ABSENT = 0, les paires indéterminées tranchées (`eval/DECISIONS.md`).

## État (29/08/2026, session 63) — LE SERVEUR PREND SA PROPRE TEMPÉRATURE

**La machine s'est coupée net à 23:10:15 sous charge** — `Kernel-Power 41`,
aucun minidump, rien au journal. Aucune mise à jour n'y est pour rien (pas de
1074), et le BIOS date de **juillet 2023** : il n'a jamais été flashé, contre
l'hypothèse de départ.

**Le seul indice était indirect, et je l'ai d'abord MAL LU.** J'ai comparé les
durées de tagging *à l'intérieur* de la session — plates — et conclu « pas de
signature thermique ». Le signal était *entre* les sessions :

| session | photos | moyenne | médiane |
|---|---|---|---|
| 07:08 · 07:48 · 08:44 | 173 | 14,6 → 18,8 s | 13–18 s |
| 20:21 · 20:47 | 80 | 22,8 · **9,7 s** | 22 · 9 s |
| **22:36 — celle qui est morte** | 47 | **27,2 s** | **28 s** |
| 23:16 — après redémarrage à froid | 69 | **14,0 s** | 12 s |

Deux à trois fois plus lente, puis plus rien, et la vitesse revenue après un
démarrage à froid **sur le même travail**. **Mauvaise échelle de mesure,
mauvaise conclusion** — la leçon du jour.

### Le thermomètre est désormais DANS le journal

Sur une idée de Mike, et c'est mieux qu'un CSV externe : le journal porte déjà
les durées de tagging, **y joindre la température les corrèle par
construction**.

- **`mesure_thermique.py`** (neuf) interroge `nvidia-smi` **champ par champ**
  et rend l'inventaire de ce que la carte accepte. Il a payé immédiatement :
  **`power.limit` et `temperature.memory` rendent `[N/A]`** sur cette
  RTX 3050, et un seul champ refusé fait échouer TOUTE la requête groupée —
  sans dire lequel. Les avoir mis à l'aveugle aurait **aveuglé `hw_state` sur
  sa propre VRAM**, donc cassé l'arbitre GPU.
- **`hw_state`** gagne `temp_c`, `clocks_mhz`, `clocks_max_mhz`, `watts`,
  `bridage` et `bride_thermique` — via un lecteur tolérant `_nombre` qui rend
  `None` au lieu de lever : **une sonde ne doit jamais priver le serveur de
  `hw_state`**. Le jugement se fait sur les **deux drapeaux booléens**
  (`hw/sw_thermal_slowdown`, rendus en toutes lettres) et non sur le masque
  NVML, dont il faudrait connaître les constantes par cœur.
- **`thermique_loop`** écrit au journal : une ligne de référence au démarrage,
  puis une toutes les 10 min ; **chaque relevé** au-delà de 85 °C ou dès que la
  carte avoue brider ; et le **basculement** du bridage dans les deux sens —
  c'est l'instant qu'on cherchera après coup. Lancée sous `fil_surveille`.

**État mesuré ce soir** : 60–73 °C, horloges 1 620–1 747 / 2 100 MHz, 38 W en
charge, les trois drapeaux de ralentissement à « Not Active ». **La machine va
bien en ce moment** — d'où l'intérêt d'enregistrer dans la durée plutôt que
d'échantillonner une minute.

`test_thermique.py`, 9 contrôles, **9 rouges sur le code d'avant**. Deux ont
rougi sur MOI d'abord : l'un lisait `power.limit` dans le commentaire qui
explique son exclusion (**un commentaire est de la PROSE** — le test lit
maintenant la chaîne de la requête), l'autre attendait une ligne là où le code
en écrit deux, la première étant la référence de démarrage — le code avait
raison.

### Ce que le CPU ne dira pas

`psutil.sensors_temperatures()` ne rend rien sous Windows et
`MSAcpi_ThermalZoneTemperature` n'est presque jamais implémentée sur un
portable. **La température CPU demande un logiciel tiers** (HWiNFO64). Le GPU
suffit ici : c'est lui qui sature.

## État (28/08/2026, session 62) — LE SECOND CAS GOOGLE EST OUTILLÉ, ET LE DOSSIER EST RANGÉ

**`copier_absentes.py` sait désormais rapatrier le SECOND cas.** Jusqu'ici il
ne connaissait que les ABSENTES. Deux options l'ouvrent — `--verdict` (répétable)
et `--nas-plus-petit-de OCTETS` — sans rien changer par défaut. Sur le rapport
du 28/08 : **100 fichiers, 1,26 Go, 91 photos et 9 vidéos**. Le `.bat 33` les
dépose dans un dossier À PART.

**Un test a trouvé un défaut que la relecture n'avait pas vu** : le seuil de
taille s'appliquait AUSSI aux ABSENTES — or une absente n'a pas de contrepartie
sur le NAS, donc « plus petite d'un mégaoctet » l'écartait toujours. Cumuler
les deux verdicts aurait fait disparaître le rapatriement des absentes **en
silence**. Six contrôles neufs.

**Le dossier est rangé.** Huit corbeilles et 53 journaux d'annulation
antérieurs au 25/08 (**43 Mo**) sont dans `_to_delete/`, en deux sous-dossiers
nommés. **Gardés délibérément** : `_corbeille_copies` (le rapatriement Google
du 27/08, dont on se sert encore), `_corbeille_deplacements` (26/08) et les
deux `undo_annee` du 27/08. Vider le filet de sécurité de l'opération en cours
aurait été le seul vrai risque de ce rangement.

**Les docs sont taillées** : `QUESTIONS_MIKE.md` passe de 15 000 à 3 500
octets — dix-neuf entrées réglées retirées, trois vraies questions restent.

**L'ŒIL EST POSÉ** (28/08, après relance de Chrome). Sur le serveur vivant :
- la barre de dossiers de `/files?dir=` — « ⬆️ Dossiers », « 📄 Liste » —
  rend deux `<a>` de **44 px exactement**, même forme que la barre d'outils
  au-dessus, sans soulignement. Un seul vocabulaire ;
- la bande « même jour » rend **17 `.fetiquette`** : des `<span>`, `border:
  none`, fond transparent, `cursor: auto`, et les millésimes en `ui-monospace`
  avec leur compte en gras. Elles ne ressemblent plus à des boutons, et c'était
  tout l'enjeu ;
- **zéro `.fchip` dans le DOM rendu**, sur les deux pages.

Ce que l'œil ajoute au banc : les instruments disaient que les règles étaient
là ; ils ne pouvaient pas dire que l'étiquette avait cessé de ressembler à un
bouton. C'est un jugement de forme, et il se pose avec les yeux.

## État (28/08/2026, session 61) — LES VINGT FILS ONT UN FILET, ET GOOGLE A SON COMPTE

**Le superviseur de fils est écrit, et les vingt fils y passent.** Règle de
Mike : le fil mort SE RELANCE, cinq morts consécutives ALERTENT. `fil_surveille`
enregistre chaque fil dans `FILS`, relance avec une attente qui double (1 → 300 s),
remet le compteur à zéro dès qu'une reprise tient 5 min, et **`/sante` affiche
désormais les fils avant les fichiers** — c'était le manque exact du 27/08 : la
mort était dans le journal, elle n'était sur aucune page.

**Qui BOUCLE et qui REND a été MESURÉ, pas supposé** : un balayage AST des
`while True:` a classé les vingt fonctions. Quinze bouclent (elles se
relancent), cinq rendent — les trois `_backfill`, `reconcile_named_tags` — et
celles-là ont le DROIT de finir : les relancer leur ferait refaire leur travail
sans le savoir. C'est le mode de panne que ce mécanisme pouvait CRÉER.

**Un piège évité, et il valait la peine** : en rattrapant l'exception, le
superviseur prive `threading.excepthook` de son passage. Sans réimprimer la
trace, on échangerait huit heures d'arrêt contre la PERTE du diagnostic qui a
permis de comprendre la panne. Un test tient cette ligne.

`test_fils_surveilles.py`, 10 contrôles, **10 rouges sur le code d'avant** —
dont un seul l'est pour une raison de FOND (le garde de source qui interdit un
`threading.Thread` nu sur un fil de travail) ; les neuf autres le sont parce
que le mécanisme n'existait pas, ce qui est le seul rouge possible pour du
neuf. Le dire vaut mieux qu'un compte flatteur.

**`.fchip` est mort, et deux noms l'ont remplacé** (décision de Mike) : les
`<a>` de navigation prennent `.btn btn--nav` (cible 44 px, un seul
vocabulaire), les `<span>` d'information deviennent `.fetiquette` — sans
bordure ni curseur, pour qu'on ne puisse plus les confondre en les LISANT.
Instruments verts, banc des pages composants vert sur le serveur vivant.
**L'œil manque** : l'extension Chrome n'était pas connectée après le
redémarrage du PC. À poser au prochain passage.

### Google : ABSENT = 0, et un écart qui se lit en deux paquets

Vérification d'après rapatriement (244 s) : sur **13 905 médias**,
**4 293 CERTAIN** (55,6 Go), **9 612 « taille différente »**, **0 ABSENT**.

Les 9 612 se séparent nettement. Le NAS est plus GROS dans 9 315 cas, écart
médian **4 101 octets** — la taille d'un bloc XMP : ce sont nos propres tags,
le NAS porte la photo de Google PLUS nos noms. Mais **297 fois le NAS est plus
PETIT, dont 89 de plus d'un mégaoctet**, et ça ne s'explique pas par des
métadonnées.

**Les vidéos** : 3 114, dont **3 104 identiques au bit près**. Les 10 autres
sont plus petites côté NAS, lourdement (−73 Mo, −40 Mo, −22 Mo). Côté photos,
`Luzarches 2016 (33).jpg` fait 8,5 Mo chez Google et 0,6 Mo sur le NAS.
**Ces ~106 fichiers-là ne doivent pas être effacés chez Google avant d'être
rapatriés.** Le reste peut partir. Détail et recommandation :
`QUESTIONS_MIKE.md`.

## État (28/08/2026, session 60) — LE TAGUEUR EST MORT D'AVOIR VOULU NOTER SA MORT

Condensé (le récit vit dans git, `docs/DECISIONS_OUTILLAGE.md` et `eval/DECISIONS.md`) :
le tagueur mourait sur `database is locked` en essayant de JOURNALISER son échec —
un rattrapage ne dépend jamais de la ressource qui vient de tomber. Corrigé, observé ;
le superviseur de fils (session 61) en est la suite.

## État (27/08/2026, session 59) — LA VISIONNEUSE DÉBORDAIT SUR TÉLÉPHONE

**Le rendu 390 px a enfin été vu — en contournant le zoom.** Le
redimensionnement de fenêtre ne changeait pas la capture (session 58) parce
que le zoom du navigateur (~50 %) maintenait ~1 023 px CSS de viewport quelle
que soit la fenêtre. Contournement : une **iframe de 390 px** posée sur une
page du même origine — les media/wrap s'y évaluent à 390, le serveur VIVANT
sert la page, et on n'a touché ni au zoom de Mike ni à sa fenêtre.

**Le défaut trouvé : `#lb-bar` en `nowrap`, 566 px dans 370.** Sur téléphone,
« 🗑️ Supprimer » était à moitié coupé et **« Fermer » entièrement HORS
ÉCRAN, sans aucun défilement pour l'atteindre** (pas d'Échap au doigt). Et le
libellé dynamique « 📅 Même jour (31 mai) » se pliait en **quatre lignes de
78 px**. Les cinq familles de la session 58 étaient conformes une à une — le
défaut était dans la RANGÉE, que personne ne mesurait : `verifier_cibles`
juge chaque cible, pas leur tenue collective à une largeur donnée.

**Correctif : deux déclarations, zéro restart** (`gallery.html` est relu à
chaud) : `flex-wrap: wrap` sur `#lb-bar`, `white-space: nowrap` sur ses
`.btn` — le BOUTON passe à la ligne, jamais son texte. Preuves : cascade
0 disparue / 0 changée / 2 apparues (les voulues) ; cibles 0 manquement ;
contraste et contrôles verts ; 35 tests UI OK ; l'œil à 390 px (trois
rangées, tout à 44 px, Supprimer rouge plein, Fermer revenu) et à 1 200 px
(une rangée, barre 68 px — rien ne bouge sur bureau). La barre d'outils et
les chips, eux, se replient proprement à 390 : le coût +19 px tient sur
mobile, rien d'autre à corriger.

**Le tableau de corrélation trailer/tag (point 3) a rencontré le plafond du
banc.** `croiser --exclure Takeout` sur le fonds entier lit ~70 000 queues de
JPEG sur SMB : bien au-delà des 600 s (`TIMEOUT_S` de `banc_agent`, plafond
1 800 non levable par ordre). Relancé en
**échantillon** (3 000 tirés des 72 584 hors Takeout, 574 s) : **la
corrélation N'EST PAS LÀ.** Sur 975 JPEG Samsung jugés, les photos NOMMÉES
par notre écriture gardent leur SEF à **86,9 %** (Wilson 95 % : 83,4–89,8),
les non nommées à **83,9 %** (80,5–86,7). Les intervalles se recouvrent et
le signe est du MAUVAIS côté pour accuser : **rien n'accuse notre écriture
XMP.** Les 99 paires Google au trailer zéro étaient un sous-ensemble biaisé,
pas le fonds. La CAUSE reste à prouver dans les deux sens — le juge est
l'avant/après sur le MÊME fichier, armé (`_rapport_sef_avant.json`), que le
travail du curateur fera parler.

## État (27/08/2026, session 58) — LES BOUTONS DE `gallery`, ET UN « SUPPRIMER » JAMAIS MESURÉ

**Six familles de boutons maison passent au `.btn` canonique.** Cinq étaient
prévues (`.tb`, `.geobtn`, `.georow button`, `#ss-stop`, `.fchip`) ; la
sixième, la barre de la visionneuse, ne l'était pas — et c'est elle qui
portait la trouvaille.

### Ce que la cascade dit du changement

`verifier_css_cascade --page` : **69 déclarations disparues, 0 apparue,
0 valeur changée.** Rien n'a été ajouté ni redéfini : la taille, la forme, la
police et les états survol/pressé viennent maintenant de `components.css`, qui
figurait déjà des deux côtés. Ce qui reste dans la page ne PEINT que l'état.

### Ce que ça change pour le pouce

| `gallery`, 31 cibles | avant | après |
|---|---|---|
| plancher 44 px **prouvé** | 9 | **22** |
| hauteur **non déclarée** | 16 | **3** |
| sous 44 px prouvé | 0 | 0 |

**Le gain n'est pas « des boutons trop petits réparés »** — aucun n'était
prouvé trop petit. C'est « je ne sais pas » qui devient « prouvé » : seize
cibles dont aucune règle ne déclarait la hauteur, contre trois. Ne pas voir
une cible ne la rendait pas conforme, ça retirait le dénominateur.

### Le « Supprimer » de la visionneuse était en CONTOUR

`#lb-del` — le bouton qui **supprime une photo** — posait `--encre` en TEXTE
sur un fond hérité. C'est exactement la forme que le système a mesurée à
**3,03:1** et remplacée par du plein (`.btn--destructif`, 5,34:1). Elle avait
survécu là **parce que `verifier_contraste` ne lit que `tokens.css` et
`components.css`** : une couleur écrite dans le `<style>` d'une page n'était
jugée par personne. L'instrument le DIT dans sa portée — encore fallait-il
lire sa portée. Le convertir le fait entrer dans le périmètre mesuré.

Deux autres divergences tombent au passage : `#lb-sim`/`#lb-jour` posaient un
survol `--salle-2` par un sélecteur d'ID, qui gagnait sur la marche commune —
deux profondeurs de survol pour un même registre de bouton.

### Ce qui n'est PAS fait

- **`.fchip` reste**, et pour une raison qui mérite une décision : la classe
  habille à la fois des `<a>` de navigation ET des `<span>` d'information
  (« Cette photo n'a pas encore été analysée », le libellé de jour). Les
  convertir en bloc ferait des étiquettes qui ressemblent à des boutons.
  Question ouverte dans `QUESTIONS_MIKE.md`. Elle vit dans `server.py`, donc
  elle demandera un redémarrage.
### L'ŒIL, fait (27/08, serveur relancé)

`verifier_pages_composants` sur le serveur VIVANT : les 7 pages converties
reçoivent la feuille commune et gardent le dernier mot, la page témoin
(`/map`) est intacte. Puis regardé, pour de vrai :

- la barre d'outils (`IA`, `Date ↑`, `Nom A-Z`, `▶ Demo`, `▶ Aléatoire`,
  `▶ Association`) et la puce `Géo` — même hauteur, même forme, l'actif en
  `--fixateur`. Un seul vocabulaire ;
- la visionneuse : `←`, `→`, `🔍 Semblables`, `📅 Même jour`, `Fermer`
  alignés, et **`🗑️ Supprimer` en rouge PLEIN**. Le contour à 3,03:1 a
  disparu de l'écran, pas seulement du CSS.

**Ce qui n'a PAS été regardé** : le rendu en largeur de téléphone. Le
redimensionnement de la fenêtre n'a pas changé la capture, et je n'ai pas
insisté — le coût accepté de **+19 px** de hauteur de barres reste donc
vérifié sur bureau seulement. À faire au premier passage sur mobile.

## État (27/08/2026, session 57) — LE RANGEMENT PAR ANNÉE DÉCROCHAIT ENCORE LES DÉCISIONS

**Mike allait lancer `26 - Ranger par annee.bat` sur 559 photos. Deux défauts
l'attendaient, et aucun des deux ne se serait annoncé.**

**Le premier : `appliquer_plan.rekey_stores` n'était pas le miroir qu'elle
disait être.** Son docstring affirmait « miroir de `server.rekey_everywhere` » ;
elle bouclait sur les quatre magasins de sujets en appelant
`store.rekey(ancien_chemin, nouveau_chemin)`. Or **`people` et `pets` sont
keyés par NOM** — leurs chemins vivent DANS la fiche. `rekey` y cherche une
entrée dont la clé serait un chemin, n'en trouve jamais, renvoie faux, **et la
boucle ne regardait même pas le retour**. Quatre magasins à l'écran, deux en
vrai. Le correctif (`recle_decisions.recler_fiche`) existait depuis le 22/08 —
**branché dans `server.py` et nulle part ailleurs**. L'applicateur hors ligne,
que portent le rangement par année ET le dédoublonnage, décrochait donc encore
des décisions cinq jours plus tard.

Ce qui se perdait n'a jamais été le NOM (il vit dans l'index et dans le XMP,
règle 2 tenue) : c'est la **vérité terrain** — quel visage est qui, quelles
photos ont été écartées d'un nom, lesquelles ont été confirmées. Une exclusion
perdue est un faux positif qui revient. Le compte du 22/08 : **928 décisions
sur 3 364** décrochées, sur 804 clés.

**Le second : l'en-tête disait « À LANCER SERVEUR ARRÊTÉ » et personne ne le
vérifiait.** Le serveur de Mike tournait. Deux écrivains sur `photos.db`, c'est
l'invariant 4 du projet. Le script le **PROUVE** désormais, comme
`deplacer_dossiers` — et avec **deux** preuves, parce qu'une seule ne suffit
pas : la base est en **WAL**, donc le serveur ne tient le verrou d'écriture que
pendant ses transactions, et `BEGIN IMMEDIATE` peut l'obtenir alors qu'il est
bel et bien vivant. On demande donc AUSSI au serveur s'il répond
(`GET /api/serveur`) — une preuve qui ne dépend pas de l'instant. `--forcer`
lève les deux, explicitement.

**Et les décisions re-clées se COMPTENT** (`Bilan : … dont N décision(s)
humaine(s) re-clée(s) `) : ce qui n'est pas compté n'est pas diagnosticable
après coup, et c'est précisément ce qui a laissé 928 décisions partir en
silence.

### PROUVÉ EN RÉEL, le soir même : **27 décisions**

Le rangement des 559 photos a rendu
`{'ok': 539, 'dry': 0, 'skip': 20, 'decisions': 27}`. **27 rattachements,
exclusions ou confirmations ont suivi leur photo** — et l'ancien code les
aurait laissés sur l'ancien chemin, sans erreur, sans trace. Le premier lot de
20 en avait rendu **zéro**, ce qui ne prouvait rien : ces vingt-là n'en
portaient simplement aucune. C'est le lot complet qui a produit le chiffre, et
c'est pour ça qu'on ne conclut pas sur un échantillon qu'on n'a pas choisi.

**18 tests neufs** (`test_recle_hors_ligne.py`), dont le ROUGE observé : la
boucle des quatre magasins laissée telle quelle, qui ne déplace ni le
rattachement, ni l'exclusion, ni la confirmation — et ne lève aucune erreur.
Au passage, mon premier jeu d'essai écrivait l'`avatar` en chaîne alors que
c'est une PAIRE `[chemin, index]` : **c'était le test qui était faux, pas
l'instrument.**

## Ce qu'il faut garder des sessions 54 → 56 (le récit vit dans git)

- **Le rapatriement Google est OUTILLÉ** (56) : `copier_absentes.py` +
  `32 - Copier les absentes de Google.bat`. Rien n'est jamais écrasé, la cible
  doit être sous `_A TRIER`, chaque copie est RELUE, journal d'annulation dans
  `_corbeille_copies/`.
- **Le soupçon sur le trailer Samsung a eu son banc** (56) —
  `verifier_trailer_samsung.py`, qui refuse de conclure quand rien n'a été
  nommé plutôt que de rendre vert. Verdict tombé le 27/08 : **rien n'accuse
  notre écriture XMP**.

## État (27/08/2026, session 54) — 3 776 PHOTOS N'EXISTENT QUE CHEZ GOOGLE

**L'export est ouvert, prouvé, et confronté au NAS.** 45 lots, 89,2 Go,
**25 864 fichiers** — `verifier_takeout_ouvert.py` : **0 absent, 0 tronqué,
0 refusé**, aucun trou dans la numérotation. Le bat de Mike et le banc
arrivent au même compte par les deux bouts.

`verifier_photos_google.py` sur **13 905 médias** de l'export :

| verdict | n | quoi |
|---|---|---|
| CERTAIN | 1 112 | 44,0 Go — et **1 087 sont des `.mp4`** |
| PROBABLE | 9 017 | même nom, taille différente — **8 996 `.jpg`** |
| AMBIGU | 0 | |
| **ABSENT** | **3 776** | **12,6 Go, dont 2 017 vidéos** |

### Ce que la mesure a renversé

La documentation de l'instrument posait que PROBABLE = « Google a
probablement ré-encodé en mode économiseur de stockage ». **C'est faux, et
d'un facteur qui saute aux yeux** : le NAS est plus gros **8 741 fois sur
9 017**, ratio médian **1,001** — quelques kilo-octets, toujours du même
côté, et **uniquement sur les JPEG** ; les vidéos tombent exactes au bit près.
Or ce projet écrit ses noms dans les **XMP des fichiers**, à l'exiftool, et
seulement dans les images.

`verifier_google_pixels.py` (neuf) transforme l'hypothèse en compte. Il
compare ce qui fait l'IMAGE — tables de quantification, tables de Huffman,
cadre, en-tête de balayage, longueur du flux compressé — en SAUTANT les
segments `APPn`/`COM`, là où vivent EXIF, XMP et IPTC. Sur les 9 017 :

| | n |
|---|---|
| **MÊME IMAGE** (écart médian **+4,2 Ko**, de la métadonnée) | **8 802** |
| même image, mais un TRAILER d'un seul côté | 99 |
| flux non départageable par la voie rapide | 74 |
| image vraiment différente (ré-encodage) | 21 |
| hors portée (`.gif`, `.mp4`, `.png` — pas un JPEG des deux côtés) | 21 |

### L'instrument s'est trompé une fois, et le chiffre l'a dit

Première version : **173 paires en « flux différent »** — j'ai écrit dans ce
fichier qu'il s'agissait probablement de deux photos DIFFÉRENTES de même nom.
Le chiffre disait le contraire et je ne l'avais pas écouté : l'écart était
**toujours du même signe** (le NAS plus court, médiane −2 046). Contrôle
direct sur les 173 : **toutes portent, côté Google, des octets APRÈS le
`EOI`** — médiane 2 046, exactement l'écart. L'instrument rangeait le TRAILER
dans l'image. Corrigé : le trailer est mesuré à part, et 99 des 173 sont la
même image. Les 74 restantes ont un trailer qui contient lui-même un `FF D9`
(médiane 52 Ko au-delà) : la recherche à reculons y tombe, le verdict sort
ROUGE — **l'erreur possible va du côté prudent, et c'est écrit dans le code.**

**Portée déclarée** : la preuve comparée est la LONGUEUR du flux, pas ses
octets. `--octets` les hache — ~32 Go à lire côté NAS, trois ou quatre
tranches de banc. À faire AVANT d'effacer 75 Go chez un tiers, pas après.

### Ce qui se déduit, et ce qui ne se déduit pas

**Se déduit** : le NAS couvre **9 914 des 13 905** médias de l'export
(1 112 CERTAIN + 8 802 même image). **Ne se déduit pas** : que le reste soit
négligeable — 3 776 ABSENTES, 99 dont le NAS a perdu le trailer (une « photo
animée » vit là), 95 indéterminées, 21 vraiment différentes. Toutes listées
NOMMÉMENT dans `_google.json` et `_pix_reprise.json`.

**Le geste qui suit n'appartient pas à un instrument** : copier les ABSENTES
sur le NAS. Rien ne s'efface chez Google avant, et le rapport le dit lui-même
(code de sortie 1, « NE RIEN EFFACER »).

## Ce qu'il faut garder des sessions 50 → 53 (le récit vit dans git)

- **Un filtre qui ment ne ment plus (53).** Un jeton `<axe>:<valeur>`
  insatisfaisable rend RIEN et le DIT, sur les cinq axes ; la barre comprend ce
  que les pastilles écrivent. Contrôle NÉGATIF outillé :
  `verifier_filtre_negatif.py`, 15 contrôles, deux canaux. **Le banc a payé son
  écriture à sa première exécution.**
- **Le Takeout a de quoi s'ouvrir (53 bis).** `dezipper_takeout.py` +
  `31 - Dezipper le Takeout Google.bat`.
- **Le déplacement `Photos Mike` est FAIT et VÉRIFIÉ (51–52).** Contrôle par
  comparaison de la base d'AVANT et d'APRÈS, pas par relecture du code. Le
  défaut trouvé au passage aurait coûté **983 décisions humaines** :
  `deplacer_dossiers` re-cléait des magasins keyés par NOM, où
  `store.rekey(chemin)` ne trouve jamais rien. Même faute retrouvée dans
  `appliquer_plan` cinq jours plus tard (session 57) — d'où le point 4 :
  **UNIFIER le re-clé**, la primitive existe TROIS fois.
- **Caline, et le filtre qui n'en était pas un (50).** Deux noms posés par Mike
  ont fait tomber les groupes d'animaux de **189 à 99** et les apparitions non
  nommées à **442** : ce n'est plus un chantier, c'est une finition au fil de
  l'eau. Et ma propre erreur ce jour-là : une requête maison contre
  l'instrument du projet — **mesurer avec l'instrument du PROJET**, trois fois
  vérifié le 26/08.

## Ce qu'il faut garder des sessions 47 → 49 (le récit vit dans git)

- **Le plancher tactile était un VŒU, il a un instrument.** `verifier_cibles.py`
  (65 tests, huit rouges observés gravés) lit le HTML statique, les chaînes JS
  **et** ce que `document.createElement` bâtit — **31 cibles lui étaient
  invisibles**. Verdict : **221 cibles, 0 manquement prouvé**, 66 dont la
  hauteur n'est pas déclarée. Ne pas voir une cible ne la rend pas conforme :
  ça retire seulement le dénominateur.
- **Un contrôle qui n'en était pas un (47).** Deux instruments lisaient les
  `<button>` cités dans les COMMENTAIRES d'un `<style>` comme des éléments
  réels. Un commentaire est de la prose, CSS compris — règle de lecture unique
  et partagée : `verifier_controles.sans_le_css`. L'exception est une
  DÉCLARATION (`/* cible: hors-portee -- … */`), qui se lit AVANT le retrait et
  se ferme sur `*/`, pas sur la fin de ligne.
- **Le chip est FINI (49).** `.chip` vit dans `components.css` seul, `font:`
  compris ; `.pchip` supprimé ; **7 pages sur 11** reçoivent la feuille
  commune. La cascade a QUATRE étages, et c'est la moitié de toute preuve CSS :
  `components.css` (au marqueur) → la page → `tokens.css` → `base.css` (à
  `</head>`, il gagne les égalités). Une feuille qui ne change pas doit figurer
  **des deux côtés** de `--avant`/`--apres`.
- **Changer une BALISE change son style par défaut** : `<span>` → `<button>`
  change police, alignement et surtout `display` — ce qui **réveille** un
  `min-height` qui dormait. Un `<button>` n'admet que du contenu de PHRASE ;
  sinon `tabindex` + `role` + `keydown` Entrée **et** Espace avec
  `preventDefault` — les trois.
- **Un verdict tiré à pile ou face est pire qu'un aveu d'ignorance.** « La
  dernière règle écrite gagne » n'est vrai que **si les deux s'appliquent** ; et
  une règle non prouvable AFFIRMÉE disait « trop petit » là où il fallait lire
  « pas de plancher ». Ce qui doit s'accorder, c'est le VERDICT, pas la valeur :
  `44px` et `var(--touch)` sont la même hauteur.

## Ce qu'il faut garder de la session 46 (le récit vit dans git)

- **Le CSS commun ne valait pas le chantier, et c'est sa PREUVE qui l'a tué** :
  200 déclarations hissables sur 1 754, dont 171 partagées par deux pages
  seulement — **6,2 Ko sur 67**. Ne pas reproposer l'extraction.
- **Le vrai sujet était la DIVERGENCE** : `.btn` ne voulait pas dire la même
  chose selon la page. `components.css` existe pour ça, en **opt-in** page par
  page (`<!--UI:components-->`, placé AVANT le `<style>` de la page pour
  qu'elle garde le dernier mot). **6 pages sur 11 ont adopté ; le `.btn` est
  FINI** — les cinq restantes n'en ont pas. Trois l'écrivaient sous d'autres
  noms (`.prim`/`.warn`, `.primary`/`.danger`).
- **Les trois universelles** (`body{background|color|font-family}`) vivent dans
  `base.css` seul — elles étaient trois, pas six : le reset `*` ne vit que dans
  NEUF pages, et neuf sur onze ne se hisse pas sans preuve page par page.
- **L'ordre de la cascade a QUATRE étages** : `components.css` → la page →
  `tokens.css` → `base.css`. `--apres` prend la feuille commune EN PREMIER,
  sinon elle gagne une cascade qu'elle ne gagne pas en vrai.
- **Le plancher AA est devenu une mesure** : trois échecs trouvés au premier
  lancement, `--fixateur` assombri `#4A8C7B` → `#448172`, destructif passé au
  plein (5,34:1 sans toucher au token). `--salle-4`, `--fixateur-p`,
  `--encre-p`, l'état pressé hors du garde `hover` et `.hors-ecran` sont
  canoniques (approuvés par Mike).
- **Niveau A, déjà corrigé le 25/08** : les deux `<input type="file">` de `/`
  étaient en `display:none` derrière des `<label for>`.
- **Le chantier XMP est clos** : 0 écart sur 1 614 couples (Wilson 0,0–0,2 %).

## État (25/08/2026, session 46) — libérer Google sans rien perdre

**`verifier_photos_google.py`** (neuf, famille `verifier_`, lecture seule,
19 vérifications) répond à la seule question qui autorise à effacer 75 Go chez
un tiers : **pour chaque photo que Google détient, le NAS la porte-t-il ?**

**Pourquoi un export Takeout et pas l'API.** Depuis le **31 mars 2025** l'API
Google Photos ne laisse plus une application tierce voir que ce qu'elle a
elle-même envoyé — rclone le dit noir sur blanc. Aucun outil ne peut énumérer
la photothèque à distance. Takeout, lui, dépose à côté de chaque média un
`.json` portant son **nom d'origine** et sa **date de prise de vue** : deux
choses que le nom exporté peut avoir perdues (Takeout tronque les noms longs
et suffixe les collisions). Se fier au nom du fichier ferait déclarer ABSENTES
des photos que le NAS porte — c'est le premier test du banc.

**Quatre verdicts, un seul autorise.** CERTAIN (même nom, même taille) ·
PROBABLE (taille différente : Google a ré-encodé en mode économiseur) ·
AMBIGU · **ABSENT — et un seul ABSENT interdit tout**. Le rapport écrit
alors NE RIEN EFFACER, et le code de sortie vaut 1 : un banc qui rendrait 0
sur un fonds incomplet serait un feu vert.

**Ce qu'il ne voit pas, et qui compte** : une photo arrivée chez Google par un
autre chemin — album partagé, WhatsApp, le téléphone de quelqu'un d'autre —
n'a aucune raison d'être sur le NAS. Elle sort ABSENTE, et c'est un ordre de
COPIE, pas un écart à écarter.

## État (25/08/2026, session 45 quater) — la copie hors site est SPÉCIFIÉE

**Le point 12 bis n'attend plus qu'un geste.** Tout ce qui manquait est mesuré
ou vérifié :

| | |
|---|---|
| à sauvegarder | **290,9 Go** (109 photos + 180 vidéo) + ~300 Mo de décisions |
| source | NAS **Synology DS224+**, DSM 7.3.2 (7.4.1 en attente) |
| cible | **Infomaniak Swiss Backup**, Hyper Backup/Swift, ~**CHF 6 TTC/mois** pour 1 To, données en Suisse ×3 |
| ligne, mesurée | **22,4 / 13,8 Mbit/s** — premier envoi **~50 h** |
| ligne, CAPACITÉ à l'adresse | **425 / 100 Mbit/s** (fibre seulement entre déc. 2027 et mars 2028) |
| ligne, offre à +CHF 1/mois | **100 Mbit/s** — premier envoi **~8 h**, une nuit |

**Le débit décide, pas l'hébergeur.** La ligne peut déjà donner sept fois plus
en montée que ce qu'elle donne : ce n'est pas une limite physique, c'est le
plafond de l'abonnement. Un franc par mois achète un facteur 7 sur le seul
chiffre qui rend cette sauvegarde faisable ou non.

**Le débit n'est PAS un préalable.** À 13,8 Mbit/s le premier envoi tient en
**~8 nuits** (photos ~3, vidéos ~5), avec une limite de débit pour ne pas
étrangler la ligne ; ensuite les deltas quotidiens sont de quelques minutes.
Passer à 100 Mbit/s ramène le premier envoi à une nuit — c'est du confort, pas
une condition. **Ne pas attendre l'abonnement pour commencer la sauvegarde.**

**Et un compte Google à 96 % — 3,8 Go de la panne.** `one.google.com` :
**96,23 Go sur 100**, dont **Google Photos 75,03**, Gmail 12,82, Drive 1,13,
divers 7,2. Quand le quota est plein, **Gmail cesse de RECEVOIR**. Deux
conséquences : (1) résilier Google One est impossible en l'état — hors Photos
le compte pèse déjà **21,2 Go**, contre 15 Go gratuits ; (2) les 75 Go de
Google Photos sont un DOUBLON de ce que le NAS reçoit déjà par
`_Uploads` — les libérer ramène le compte à ~21 % pour le même CHF 2/mois.
Ordre impératif : vérifier que le NAS a bien les photos AVANT d'effacer quoi
que ce soit chez Google (l'app Photos efface aussi du téléphone quand la
synchro est active).

## État (25/08/2026, session 45 ter)

**La copie hors site a une cible, un prix et un obstacle chiffré.** NAS
**Synology DS224+** → **Infomaniak Swiss Backup** par **Hyper Backup/Swift**,
~**CHF 6 TTC/mois** pour 1 To (CHF 4,18/To + CHF 1,84/appareil, −10 % annuel),
données en Suisse. L'obstacle n'est pas le prix : c'est le **lien montant
mesuré à 13,8 Mbit/s** — 291 Go = **~50 h de ligne saturée** au premier envoi.
L'offre du même opérateur à **+CHF 1/mois donne 100 Mbit/s symétriques** et
ramène l'envoi à **~8 h**. Le débit, pas l'hébergeur, est ce qui décide de la
faisabilité — et c'est le seul point où un franc par mois achète un facteur 7.

## État (25/08/2026, session 45 bis)

**Le fonds est MESURÉ, et la copie hors site cesse d'être une opinion.**
`inventaire_fonds.py` (neuf, famille `inventaire_`, lecture seule, 14
vérifications) : **76 947 fichiers, 290,9 Go** — **109 Go de photos** (73 079
fichiers) et **180 Go de vidéos** (2 453 fichiers). **62 % du poids dans 3 %
des fichiers.** Le tiers des décisions humaines pèse ~300 Mo.

**Et la première version de l'instrument s'est fait tuer par le plafond du
banc** : `os.walk` + `os.path.getsize` demande un aller-retour SMB PAR FICHIER
pour une réponse que l'énumération du dossier portait déjà — plus de 600 s.
`os.scandir` rend la même mesure en **193 s**. Sur un disque local la
différence ne se verrait pas ; c'est le réseau qui la fait.

## État (24/08/2026, session 45)

Condensé le 29/08 — le récit vit dans git (commits du 24/08, session 45).


## État (24/08/2026, session 44)

Condensé le 29/08 — le récit vit dans git. À retenir : la réparation du fonds
est FINIE (18 828 balayées, 3 128 réécrites, 0,2 % d'écart contre 18,7 %) ;
un nom qui n'a pas atterri ne se note pas atterri ; un `_exiftool_tmp`
fantôme bloque sa photo pour toujours — fuite chronique, comptée et dite.


## Ce qu'il faut garder des sessions 36 → 43 (le récit vit dans git)

Condensé le 26/08 : ces huit sessions sont CLOSES, leurs acquis vivent dans
« Acquis », leurs rejets dans `eval/DECISIONS.md`, leur détail dans git. Ce
qui reste utile à qui reprend :

- **Le MCP en lecture seule est livré et observé** (23/08) — `mcp_serveur.py`,
  sept outils, 48 vérifications, mesuré contre le serveur vivant. L'écriture
  n'est pas faite et ne se fera pas sans décision.
- **Le chantier XMP est clos** : 0 écart sur 1 614 couples. Les noms attribués
  vivent dans les fichiers ; ils survivent à la base. C'est l'invariant 2.
- **Flo → Florine et le groupe de Stéphane Plouvin sont appliqués et vérifiés
  sur le DISQUE** (200/200 et 58/58).
- **La répétition de restauration a réussi** (22/08) : six tables identiques,
  363 noms des deux côtés, aucun écart de décision. Elle a trouvé au passage
  trois défauts que rien d'autre n'aurait vus — dont un garde-fou qui testait
  le NOM du fichier et refusait donc la base restaurée.
- **Les rattachements, le résidu et le recalage sont clos et mesurés** : ne
  pas rouvrir sans chiffre neuf.
- **`ui/` : les onze gabarits sont sortis de `server.py`** (17 200 → 11 986
  lignes), les onze pages identiques au caractère près.


## Ce qu'il faut garder des sessions 28 → 35 (le récit vit dans git)

**Rattachements (31 → 35).** `rekey_everywhere` ne transportait pas les
décisions humaines : `PEOPLE`/`PETS` sont keyés par NOM, leurs chemins vivent
DANS la fiche — chaque rangement décrochait des jugements en silence. Corrigé
(préventif `recle_decisions.py`) puis réparé : **787 décisions re-clées sur 685
clés**, et l'audit de quarantaine — **788 sorties, 734 appariées, 54 fusions, 0
sans contrepartie** — est ce qui distingue « déplacé » de « perdu » ; un total
ne l'aurait jamais dit. Vérité terrain : **3 310** décisions.
Puis la CIBLE : `reembed_one_batch` remplace `e['faces']`, l'ordre change, le
couple `[photo, index]` survit et désigne quelqu'un d'autre **de la même
photo** — **42 décalés (3,5 %)**, 41 sur des photos re-détectées. Recalage
appliqué : **33 sur 17 fiches**, décalés **→ 9 (0,8 %)**, 1 194 couples avant
comme après. Résidu jugé par Mike : **2 retirés, 45 confirmés** (1 194 → 1 192).

**Trois leçons de méthode, payées cher.** (1) *Un fichier n'est pas une scène* :
une page d'album photographiée porte cinq tirages, un test géométrique la
déclarait impossible et rendait 0,0 sur 15 cas sur 15. (2) *« Décalé » nomme un
ÉCART DE SCORE, pas une identité fausse* — sur 13 couples scorant 0,06–0,295,
Mike en a confirmé **12** : cette colonne mesure la cécité de l'empreinte.
(3) *Un drapeau que tout le monde porte ne croise rien* (`reemb` rendait 100 %).

**Seuils et jugements (33).** Tranche 0,35–0,40 : 30 jugements, **92,6 %**
justes, **Wilson 76,6 %–97,9 %** → file « À vérifier », **jamais** l'auto-ajout ;
`CUR_ADD_SIM` ne bouge pas. La planche de référence servait l'état d'AVANT le
recalage (3 planches sur 30 périmées) — elle se relit désormais à l'affichage.
Et le résidu est CONCENTRÉ : 43 cas sur **10 fiches**, Didier en portant 4 —
**compter par FICHE, pas seulement sur le fonds**.

**Purge et propagation (30).** La purge du 17/08 n'avait traité qu'un magasin
sur deux (la cascade suit l'index, aveugle à une clé déjà oubliée) : `visages`
**44 450 → 42 196**, hors index **2 374 → 120**, quarantaine réversible.
Chantier 16(a) clos par la mesure : la propagation a convergé (14 rattachements
auto, 33 photos).

**Noms, espèce, outillage (28).** Le filtre des noms partage l'AUTORITÉ de
l'affichage (`_autorite_des_noms`) : la fiche fait foi, un nom retiré ne sort
plus d'une recherche. Portée du filtre : **92,74 %** des photos à fait non-date.
`det_score` **ne dit pas l'espèce** — c'est la CONCORDANCE de deux regards
(YOLO ∧ tagueur) qui fait le 5ᵉ axe. Trois canaux (serveur, git, bancs) et un
seul `canal.py` ; livraison `commit` (branche) / `livrer` (fusion), et l'ordre
qui en découle : éditer → redémarrer → **observer** → livrer.

## À faire — par ordre de valeur

0ter. **La file XMP : réparable (fait), durable (fait), rapide (à moitié).**
   **(a)** `verifier_xmp_personnes.py` recompte depuis le disque ce qu'elle
   doit, `appliquer_xmp_personnes.py` le refait. **Le vérificateur a tourné à
   17:47, file à 0, et il n'y a RIEN à réparer** : sur 200 fichiers tirés à
   graine fixe, **200 portent `personne:Florine`, 0 portent encore `Flo`, 0
   manquent, 0 illisibles.** Le même échantillon donnait 19 et 119 à 10:37 :
   la file a fait le travail en entier. `appliquer_xmp_personnes.py` reste donc
   livré et JAMAIS passé en réel — faute d'emploi, et c'est la bonne nouvelle. **(b1)** Les deux gestes d'une photo en UNE invocation : **fait** (÷2).
   **(b2)** Le journal qui la fait survivre à un arrêt : **fait**. **(b3)**
   `-stay_open` : mesuré à **25 %** de mieux sur une écriture, pas 12× — un
   processus qui vit longtemps et tient le NAS pour ce prix-là, **après le
   reste**. (b1), (b2) touchent `server.py` : livrables après redémarrage.

0. **Chantier des rattachements : CLOS (22/08).** Recalage appliqué (33, dont
   29 vraies réparations), résidu jugé (28 cas), retrait appliqué (2). Couples
   1 194 → 1 192, aucune décision perdue. Ce qui reste est mesuré et sain.
   **Ne pas rouvrir sans chiffre neuf** — et surtout ne pas relire les 13
   « faux positifs » comme des défauts : ils sont jugés JUSTES à 12 sur 13.
   **`PETS` est mesuré à son tour (22/08) et son index est SAIN** : 0 hors
   bornes, 2 vrais décalés sur 330. Le recalage n'y sera pas porté. Ce qui
   **Les 21 couples « à trancher » sont TRANCHÉS (22/08, `--a-juger`) et ne
   demandent aucun geste** : les 6 « espèce » sont justes 6 sur 6 (chats
   étiquetés `dog` — H4 réfutée), les 15 clés mortes n'ont aucune contrepartie
   (journaux, même nom, disque : 115 entrées ARZOPA, 0 présente) et sont
   GARDÉES. Ce qui reste ouvert côté animaux : le plafond de l'empreinte
   DINOv2 — 37 % des rattachements confirmés sous le seuil — et **l'étiquette
   d'espèce de YOLO, fausse au moins 6 fois sur 351, jamais mesurée sur le
   fonds entier**.

0bis. **Le résidu « ambigu » : CLOS (22/08).** Instrument et page livrés,
   15 cas jugés par Mike, **34 confirmés, 0 à retirer**. `mesure_rattachements.py --residu` écrit
   **15 cas sur 9 fiches, 34 couples cités** — Didier 4 cas, Res Jordi 4, puis
   Céline Gauchat, Flo, Jenny, Maryline Baudère, Rosario, Sylvie Chatelain,
   Val. Le rapport NOMME ce qu'il écarte (autres motifs de refus : aucun
   aujourd'hui). La page **`/residu`** (18 tests) montre les visages candidats
   côte à côte avec la planche de référence — **planche VIVANTE, et la photo en
   cause en est retirée** : le visage qu'on juge ne peut pas servir de référence
   à son propre jugement. Elle **n'attribue rien et ne retire rien** ; un
   verdict ne peut désigner qu'un visage MONTRÉ (refusé en 400 sinon). « Aucun
   n'est X » est un verdict à part entière, et le bouton le DIT avant le clic.
   Observé en réel (`code_a_jour` vrai) : 15 cas servis, planches vivantes,
   bascule sans écriture (0 verdict écrit après sélection). Ensuite :
   `--bilan-residu` sépare **à retirer** / **confirmé** / **à AJOUTER** (une
   attribution, autre geste, hors plan de retrait), et le retrait revient dans
   `/reglages`, geste de Mike. Et **`PETS` n'a jamais été mesuré** : son
   magasin porte des empreintes DINOv2 et `assigned_keys` ne le lit pas.

1. **Vérité terrain — PARQUÉE pour l'algo, mais 141 décisions sont EN DANGER
   (21/08).** Sur les 2 374 clés que l'index a oubliées et que le magasin de
   visages garde, **141 décisions humaines** (118 rattachements, 13 exclusions,
   10 confirmations) réparties sur **120 clés** (Alix Baudère, Luna…). **L'ordre est imposé par la
   règle 2** : d'abord un instrument qui, pour chacune, cherche si la photo vit
   sous une AUTRE clé (les doublons `ARZOPA/x` ↔ `…\_Uploads\ARZOPA\x` le
   suggèrent) et nomme celles qui n'ont pas de jumeau ; le report des noms et
   la purge — quarantaine réversible, comme le 17/08 — viennent après. Choix de
   Mike, 21/08. **Et la CAUSE reste à trouver** : pourquoi le scan retire une
   clé de l'index sans retirer sa fiche de visages ? Purger sans le savoir
   reconduit l'incident, comme le 17/08 l'a fait sans que ça se voie.
   **Le correctif est LIVRÉ et OBSERVÉ (21/08)** : la purge de démarrage
   cascade enfin, et un balayage retire au démarrage ce que `_sync_dir` ne peut
   plus voir — sans jamais toucher une clé jugée par un humain, et seulement
   quand l'index ne la reprendra jamais. **4 511 détections purgées** (quarantaine
   réversible `_corbeille_detections/`), `visages` 44 450 → **42 196**, hors index
   2 374 → **120** — exactement les protégées. Reste à faire : **reporter la
   décision de Luna** (la seule qui se sauve) et décider du sort des 120.
   **Le sauvetage a été REMESURÉ (22/08), et le compte du 21/08 était faux** :
   « 13 jumeaux, une seule décision à reporter, 787 déjà perdues » venait d'une
   recherche restreinte à 141 clés et à deux preuves faibles. En suivant les
   **journaux d'annulation** (19 331 déplacements connus), **698** des **804**
   clés mortes retrouvent leur photo et **748** décisions se re-clent (462
   rattachements, 230 exclusions, 56 confirmations), 56 y sont déjà, **124**
   sont perdues. La CAUSE est structurelle et corrigée : `rekey_everywhere` ne
   transportait pas les décisions, `PEOPLE` et `PETS` étant keyés par NOM.
   **Correctif préventif + réparation rétroactive LIVRÉS (22/08)** ; l'aperçu à
   blanc annonçait 685 clés à re-clé. **LE SAUVETAGE A EU LIEU — vérifié le
   26/08 sur le serveur vivant** : l'aperçu à blanc rend désormais
   « **0 clé(s) à re-clé sur 119 orpheline(s) ; 119 sans destination connue,
   0 hors bornes** ». Le clic qui manquait a donc été fait ; il ne reste que
   les clés dont aucun journal ne dit où le fichier est parti — l'ordre de
   grandeur des 124 annoncées perdues. **La doc annonçait une action en
   attente qui ne l'était plus.**
   La vérité terrain réelle est de **3 364** décisions (1 576
   rattachements — 1 196 comptait des CLÉS —, 1 496 exclusions, 292
   confirmations).
   **Le reste du point est parqué, et son chiffre avait déjà été corrigé la
   veille : deux mesures portaient le même nom.** Ce dont le PRODUIT a
   besoin — « qui est sur cette photo » — est à **18 863 photos nommées**
   (44,8 % du fonds vivant, 352 noms, Flo 5 919, Mike 5 566) : les gens qu'on
   connaît sont couverts. Ce dont un ALGORITHME a besoin — « CE visage est
   Flo » — est à **1 196 visages rattachés sur 71 868** (1,66 %). Seul le
   chantier 9 en dépend, pas le produit. Et le compte à rouvrir n'est pas
   1 196 : les **1 496 exclusions** sont des étiquettes humaines elles aussi —
   « ce visage n'est PAS Flo » évalue un clustering aussi bien qu'un
   rattachement. **Vérité terrain réelle : 3 364 décisions** — 1 576
   rattachements (le « 1 196 » comptait des CLÉS, or un rattachement est
   `[clé, index]`), 1 496 exclusions, 292 confirmations. Sous-comptée TROIS
   fois : d'abord sans les négatifs, puis sans les confirmations, puis en
   confondant clés et visages.
2. **Observer en réel ce qui est livré** — **fait ✔**. Reste : re-upload = une
   entrée, seek vidéo mobile, test du Z.
3. **Chaîne « noms → descriptions → recherche » — 3a, 3b, 3c CLOS le 16/08.**
   La re-passe ne se fera pas. Reste ouvert : **le prompt de PRODUCTION est celui
   qui hallucine le plus** (adopté sur un 25-15 ; toute photo taguée le paie).
   **Pas de retour à V0 sans protocole.**
4. **Gestes Mike** : `gps_place` ✔ ; renommage appliqué ✔ (7 058) ; **Flo →
   Florine ✔ (23/08 — 11 heures de file, 5 909 photos, vérifié 200/200 sur le
   DISQUE)** ; **groupe de Stéphane Plouvin ✔ (23/08 — 58/58 sur le DISQUE)** ;
   **re-rejeter Caline : SANS OBJET (vérifié le 26/08 sur le serveur vivant)**
   — « Caline » n'existe nulle part : ni fiche personne, ni fiche animal (les
   12 nommés sont Inti, Luna, Mutz, Pticon, Ava, Pins, Puma, Kevin, Wilbur,
   Dolly, Yuri, Le chat de Bremblens), ni résultat de recherche, ni
   proposition en file. **Troisième ligne de cette doc qui annonçait un geste
   sans objet.** L'outil cross-pipeline (point 8) reste là si un nom d'animal
   ressort un jour en `personne:`.
5. **Correctifs d'audit** : **I4, I5, I6, I7 et I8 CLOS (22/08)**, tous
   observés en réel, 32 tests neufs. I7 — règle unique `parse_tag_nomme`,
   mesurée avant (3 tags en casse divergente sur 37 707 : défaut latent) et
   observée après (Luna 207 → 210 dans `/api/names`). I5/I6 — le moteur des
   visages se DIT au lieu de s'affirmer, et l'arbitre VRAM est enfin visible
   dans `/reglages` (baux, refus, évictions). I4 — 57 lignes mortes retirées de
   `classifier.py`, et l'en-tête cesse de décrire une correction rejetée le
   30/07. I8 — deux routes orphelines retirées (404 vérifiés). Restent
   O7–O9, O11–O15. O1 clos ; O15 (purge de
   `photo_thumbs/`) gagne en poids. **Ce que I7 a laissé ouvert** :
   `personne:Florine`, 153 photos sans fiche — **CLOS** : Mike a répondu « c'est
   Flo », la fusion a été faite le 23/08 et **vérifiée le 26/08 sur le serveur
   vivant** (`/api/names` : `Florine` porte une fiche de **5 907** photos,
   `Flo` n'existe plus, 364 noms au total). La ligne annonçait une question
   déjà répondue.
6. **Navigation par similarité et par date** : « Semblables » et « même jour »
   livrés et observés. Reste : doublons proches bridés (>0,98 + même journée →
   quarantaine réversible, 50 paires jugées avant geste).
7. **Extraction `ui/` : COMMENCÉE (22/08), et la mécanique est faite.**
   `ui_page(nom)` lit `ui/pages/<nom>.html` (relu à chaud quand le fichier
   change), se replie sur le gabarit CUIT par `bundle.py` quand `ui/` est
   absent, et **DIT quel fichier manque** si les deux manquent — une page
   blanche enverrait chercher le défaut dans les données. `bundle.py` cuit
   désormais les gabarits en plus du CSS : le mono-fichier reste déployable
   seul. **Première page sortie : `browse` (141 lignes)**, et la preuve est au
   caractère près — `/browse` rend **19 103 caractères, mêmes empreintes**
   avant et après ; `/sante` et `/browse/0`, qui partagent le gabarit, servent
   aussi. 13 tests neufs tiennent les trois pannes muettes (fichier non
   déployé, gabarit non cuit, marqueur `__ROWS__` perdu).
   **LES ONZE GABARITS SONT SORTIS (22/08)** : `server.py` passe de **~17 200
   à 11 986 lignes**, et **les onze pages sont identiques au caractère près** —
   `/`, `/files`, `/browse`, `/reglages`, `/map`, `/pets`, `/faces`,
   `/tranche`, `/residu`, `/sujets`, `/people`, mêmes longueurs et mêmes
   empreintes avant et après. Le geste, pour mémoire : extraire la VALEUR de la
   constante (jamais son source — les `\\u00e0` du JavaScript y sont échappés
   deux fois), écrire `ui/pages/<nom>.html`, remplacer les usages par
   `ui_page('<nom>')`, comparer l'empreinte de la page servie.
   **Ce que ça a déplacé, et qu'il fallait rattraper** : quatre bancs lisaient
   les gabarits DANS le source du serveur (`test_gallery_placeholders`,
   `test_tranche_jugements`, `test_residu_jugements`, `test_faits_affichage`).
   Ils passent par `ui_gabarits.py`, qui **lève** quand un gabarit manque au
   lieu de se replier : un test qui se rabat en silence sur une copie périmée
   ne mesure plus rien, il rassure. Les quatre sont verts (78 cas).
   **Reste** : le CSS commun (chaque page porte encore son `<style>`), et le
   redesign — deux chantiers SÉPARÉS de celui-ci, exprès.
8. **Cross-pipeline (Mutz/Caline)** : outil livré, réversible. Fix auto REJETÉ
   (18 % faux rejets). Relancer si un nom d'animal sort en `personne:`.
9. **Reconnaissance — algo. PARQUÉ (21/08, choix de Mike).** *Chiffre neuf
   (22/08) : 3,5 % des rattachements désignaient le mauvais visage — une
   vérité terrain bruitée à ce point aurait faussé toute évaluation de
   clustering. À relire si le point se rouvre.* HDBSCAN /
   Chinese Whispers / AdaFace restent inévaluables — 3 364 décisions humaines
   sur 71 868 visages. Ce n'est pas une dette : le produit n'en dépend pas, et
   la couverture des noms au niveau PHOTO est déjà là (point 1). À rouvrir si
   quelqu'un veut nommer des visages en série, pas avant.
10. **Données / finitions**, dans cet ordre :
    (a) **Compter ce que le scan OUBLIE — CLOS (18/08), et le carnet SURVIT
    désormais au redémarrage (22/08, observé).** `_comptes_index.json`, écrit
    atomiquement dès le démarrage puis à chaque cycle ; `cycles_vus` ne plafonne
    plus à 10. Deux constats mineurs restent : un ajout vu PAR LE SCAN est
    étiqueté `tagging` ; `dict.__ior__` non redéfini dans `TrackedDict`.
    (b) **Garde-fou du repli sur le NOM + noms périmés — CLOS (19/08), observé.**
    **`taken` en base : REJETÉ (19/08)** — le garde-fou est passé à la LECTURE
    (voir l'État). Rien n'est écrit.
    (c) Réglages éditables depuis `/reglages` ; 2ᵉ passe des 945 illisibles +
    `recuperees/` → NAS ; purge des undo > 30 j (I12) ; deux images TRONQUÉES
    visibles dans `erreurs_images` à chaque démarrage.
11. **UI — harmonisation des vues (12/08, skill `photo-ui`)** : (a) clic sur
    l'image d'une personne → sa démo aléatoire ; (b) lieux : texte sous l'image
    en tooltip ; (c) harmoniser visages/lieux/animaux — mêmes fonctions partout,
    **sauf** l'effacement, réservé à Classification ; (d) zoom pinch + molette —
    `maximum-scale=1` retiré ✔ ; (e) **boutons de tri : CLOS (19/08), observé** — l'ordre du serveur
    s'appelle « Pertinence », un seul ordre allumé, le clic n'est plus avalé.
    **(f) Les trois derniers écarts sont CLOS (22/08), observés** : le bandeau
    `#pending` s'annonce (`role="status"`) et ne se tait plus définitivement —
    il ne se re-programmait QUE tant que la file n'était pas vide, donc un envoi
    depuis le téléphone n'allumait plus rien ; `/pets` parle d'ANIMAUX partout
    (le pipeline reconnaît six espèces, la page disait « chat ») ; et
    « Même jour (30 juillet) » porte ses accents, le tableau des mois venant
    désormais du serveur (`meme_jour.MOIS_FR`) au lieu d'être recopié.
12. **Assurance-vie : CHANTIER CLOS (22/08, 22:51). La répétition a eu lieu,
    et elle est RÉUSSIE.** Base restaurée depuis le NAS sur un dossier neuf,
    puis comparée au vivant : **intégrité ok**, les **six tables identiques**
    (tags 43 065, faces 42 195, animals 42 195, vectors 123 294, people 351,
    pets 12), **363 noms des deux côtés**, et **AUCUN écart de décision, nom
    par nom**. « On a une sauvegarde » a cessé d'être une promesse.
    Coût mesuré : **60 s** pour les 250 Mo de la base, quelques secondes pour
    les artefacts, hors clone et hors modèles re-téléchargeables. Les 6
    artefacts absents du dossier restauré sont tous *recalculables* ou
    *re-téléchargeables* — **tous les IRRÉCUPÉRABLES sont revenus.**
    **Un écart qui n'en est pas un, et que le rapport EXPLIQUE désormais** :
    la base restaurée pèse 249,5 Mo contre 276,5 vivants. C'est `VACUUM INTO`
    (la sauvegarde est compactée) face à une base vivante qui porte son espace
    libre et son WAL. Sans cette ligne, 27 Mo d'écart se lisent comme une perte.
    **Ce que la répétition a trouvé en chemin — c'est pour ça qu'elle existe.**
    (1) L'inventaire ne regardait que **3 quarantaines sur 6** : deux nées le
    matin même n'étaient sauvegardées nulle part, et il annonçait quand même
    « Total exposé : 0 o ». Les deux côtés découvrent par motif désormais.
    (2) Le garde-fou « ne jamais ouvrir `photos.db` » testait le NOM du
    fichier : il refusait donc la base RESTAURÉE — **la comparaison nom par
    nom n'avait jamais pu tourner une seule fois**. (3) Sur un dossier vide, le
    rapport disait « 0 o exposé » au lieu de « rien n'a été restauré ».
    (4) `robocopy` meurt en `ERREUR 59` après ~72 s sur les 250 Mo, quatre fois
    de suite, serveur arrêté ou non, avec `/J` comme sans — et il RECOMMENCE à
    chaque essai. `copier_reprise.py` (11 tests) passe en 60 s, zéro reprise,
    et REPREND à l'octet si le partage lâche. (5) Trois défauts de lanceur
    `.bat`, dont une parenthèse dans un `echo` au sein d'un bloc — que
    `verifier_bat.py` sait maintenant voir (15 tests).
    **Ce qui reste ouvert, et c'est un choix de Mike** : la copie **hors site**.
    Un sinistre qui emporte le PC ET le NAS emporte tout.

13. **Serveur exposé en MCP, lecture seule : LIVRÉ et OBSERVÉ (23/08).**
    `mcp_serveur.py` — JSON-RPC 2.0 sur stdio, stdlib pure, six outils
    (`ml_chercher`, `ml_semblables`, `ml_meme_jour`, `ml_sujets`,
    `ml_photos_de`, `ml_etat`). **41 vérifications + 15 pour le banc**, et
    **13 mutations vues sur 13** — un module neuf n'a pas d'ancien code à
    rougir, la mutation est ce qui en tient lieu. Observé contre le serveur
    vivant par `mesure_mcp.py` (12 étapes, 0 rouge) : une VRAIE poignée de main
    sur un VRAI tuyau, 0,09 s, 351 personnes, `espece:chat` filtré.
    **Et `faits` a sa route (23/08).** La ligne de faits n'existait que dans
    `_serve_browse` : rien d'autre que le HTML ne pouvait la lire — ni un banc,
    ni le MCP. `/api/faits?key=…` (répétable, 200 au plus) la rend pour un LOT,
    contexte bâti UNE fois ; **16 vérifications, 8 mutations vues sur 8**, et
    l'outil `ml_faits` s'y branche (48 vérifications au total côté MCP).
    **Trois états qui ne se confondent pas** : les faits ; `null` pour une photo
    connue qui ne porte ni date, ni lieu, ni nom ; la clé citée dans
    `inconnues` quand l'index l'ignore. **C'est la seule route NEUVE du lot** —
    elle attend le redémarrage, et le banc le dit au lieu de le taire (« la
    route existe-t-elle dans le code qui TOURNE ? »).
    **Reste** : l'écriture, plus tard, et pas sans décision. Briques de 14a.
14. **Recherche IA locale contextuelle.**
    (a) **Déterministe — CLOS et OBSERVÉ.** (i)–(iii) le 19/08 : `faits` est une
    VUE, la règle de LIEU est unifiée, la vue s'affiche. (iv) le 20/08 : le
    FILTRE partage l'autorité des noms avec l'affichage.
    **Le 5ᵉ axe `espece:` : LIVRÉ et OBSERVÉ (21/08)** — jeton explicite
    (forme A), filtrant sur la CONCORDANCE YOLO ∧ tagueur, règle partagée par
    le serveur et le banc (`faits_vue.dit_l_espece`). Le gain mesuré n'est pas
    celui qu'on attendait : **1 018** photos qu'aucun des six mots ne rend, mais
    surtout la PRÉCISION — `q=mouton` rend 1 500 photos dont 28 moutons,
    `espece:mouton` en rend 32, tous confirmés. **Puces livrées et observées** :
    six sous la barre, elles INSÈRENT le jeton (il se compose avec les autres
    axes) et relancent la requête côté serveur. **Le plafond de page se DÉCLARE (22/08, observé)** :
    `espece:chat` affiche « 1500 photo(s) … 886 de plus non affichées (sur 2386
    au total) ». Le filtre déterministe connaît son total avant de couper ; un
    plafond silencieux se lisait comme une exhaustivité.
    La barre de recherche ne ment plus sur une page de résultats : elle attend
    **Entrée** et relance côté serveur (choix de Mike, 21/08).
    (b) ensuite seulement, **escalade ponctuelle** vers un modèle chargé à la
    demande (bail GpuArbiter, déchargé après) — `vision-eval`, jamais câblé
    sans mesure.
15. **À évaluer (`vision-eval`)** : Florence-2 léger. **Parqué** faute
    d'hypothèse (banc 3b).
16. **« La médiathèque s'améliore à chaque information humaine »
    (Mike, 21/08) — TROIS COUCHES, une seule a besoin d'un LLM.**
    Le cas : une photo porte Florine et Caline ; quand Flora devient
    identifiable, sa PRÉSENCE s'ajoute, et peut-être son RÔLE dans la
    description. **6 287 photos** sont dans ce cas — un nom posé et au moins
    un visage non couvert, sur 25 020 photos à visage (4 338 n'ont aucun nom,
    12 565 sont couvertes ; 29 898 visages sans nom, borne haute).
    (a) **PRÉSENCE — CLOS par la mesure (21/08), et il n'y avait rien dedans.**
    Le mécanisme existait et il a convergé : **14 rattachements automatiques et
    24 cartes en file, 33 photos, 38 noms** — et **17** photos dans le cas
    exact du chantier, sur 18 745 qui y ressemblent. Rien à écrire ni dans le
    modèle ni dans l'UI. Le réservoir sous le seuil (28 684 visages, meilleur
    voisin médian **0,21**) n'est pas un gisement de noms : ce sont des gens
    sans fiche. **Seule suite ouverte** : juger 30 propositions de la tranche
    0,35–0,40 (1 328 visages, 1 106 photos vivantes) avant de toucher un seuil
    — choix de Mike, 21/08 ; sans ce jugement, abaisser `CUR_ADD_SIM` est un
    pari sur des noms, et le plafond de 400 n'en montrerait que 386.
    **CLOS PAR LA MESURE (22/08, session 33)** : 30 propositions jugées par
    Mike — **92,6 %** justes, **Wilson 76,6 %–97,9 %**. La tranche va dans la
    file « À vérifier », **jamais dans l'auto-ajout** ; `CUR_ADD_SIM` ne bouge
    pas. Et le jugement a révélé deux défauts d'instrument, tous deux traités
    ou nommés : la planche de référence était FIGÉE dans le tirage (corrigé et
    observé), et le résidu du recalage est CONCENTRÉ sur 10 fiches (point 1bis,
    ci-dessous).
    (b) **FAITS — déjà acquis.** `faits` étant une VUE, `personne:Flora`
    apparaît instantanément dans la ligne de faits, le filtre et `/sujets`.
    (c) **RÔLE dans la description — le seul étage LLM, et une hypothèse
    NEUVE.** Injecter les noms a été rejeté le 31/07 (ignoré 84 %, ×2,6) —
    mais c'était une LISTE PLATE : le modèle n'avait aucun moyen de savoir qui
    est qui, donc il ignorait ou inventait. Chaque visage rattaché porte
    désormais sa `bbox` : « le visage en [x,y,w,h] est Flora » est une autre
    expérience, jamais tentée. L'hypothèse n'est plus « re-décrire avec plus de
    faits » (direction mesurée dangereuse : hallucinations doublées) mais
    **« décrire avec des noms ANCRÉS à des positions »**.
    Conditions inchangées pour (c) : banc en aveugle sur un ET (apport **et**
    hallucination), FRONTIÈRE DE PROVENANCE, journal avant/après.

    Le socle reste : agent INCRÉMENTAL sur événement de connaissance — Non pas la re-passe en LOT —
    celle-là reste close (50 h GPU, 147 paires, hallucinations doublées) —
    mais un agent qui re-décrit **les seules photos dont la connaissance a
    changé** : un nom attribué, un lieu corrigé, une espèce confirmée. Le
    goutte-à-goutte résout l'obstacle des 4 Go de VRAM que le lot ne résolvait
    pas. **Ce que ça n'a PAS besoin de faire** : la médiathèque apprend déjà
    sans LLM — `faits` est une VUE recalculée à la lecture, un nom attribué
    change instantanément la ligne de faits de toutes les photos concernées.
    Ce que le LLM ajouterait, c'est la seule **prose de la description**.
    Trois conditions, dans cet ordre :
    (a) **un banc AVANT tout code** : N photos dont la connaissance a changé,
    re-décrites, jugées en aveugle sur un ET — apport réel **et** hallucination
    (la leçon du 16/08 : un critère non appliqué est une intention) ;
    (b) **une frontière de provenance, non négociable** : ce que le modèle a VU
    ne se mélange jamais à ce qu'on lui a DIT. Sinon l'agent détruit le 5ᵉ axe
    en silence — la concordance cesserait d'être deux regards indépendants et
    mesurerait son propre écho (les 82 photos qui RÉCITENT, 20/08) ;
    (c) **un journal avant/après** à chaque re-tag — sans l'AVANT, on ne saura
    jamais si l'agent améliore ou dérive.

17. **Gestion multi-utilisateurs — SPÉCIFIÉ par Mike le 26/08. Dernier
    chantier avant la copie hors site.** ~20 comptes, médiathèque familiale.
    Les six questions ouvertes sont TRANCHÉES ; ce qui suit fait foi.

    **(a) Le partage se fait par DOSSIER.** Chaque utilisateur a un dossier à
    lui sous `\\NAS-Bremblens\home\Photos`, où il dépose ses photos. Tout
    y est PARTAGÉ avec tous, **sauf un sous-dossier `PRIVE`** qui n'est visible
    que de lui. Pas de marquage photo par photo : rendre une photo privée, c'est
    la déplacer. Simple à comprendre, impossible à contourner par erreur.
    **Contrainte qui en découle** : l'onboarding d'un nouvel utilisateur doit
    l'expliquer NOIR SUR BLANC, avant son premier envoi. Une règle de
    confidentialité qu'on découvre après coup est une fuite.

    **(b) Le privé ne se trahit PAS, y compris par un compteur.** Si Florine
    est identifiée sur une photo du `PRIVE` de Mike, la fiche de Florine ne
    doit pas la compter **pour les autres**. Chacun voit les compteurs de ce
    qu'il a le droit de voir. C'est la contrainte la plus structurante du
    chantier : `faits` est une VUE recalculée à la lecture, donc elle devient
    une vue **par utilisateur** — et tout ce qui agrège (fiches, `/api/names`,
    chips de filtre, `/sujets`, la carte) hérite du même filtre. **Un compteur
    qui fuit est un défaut de niveau A de ce chantier.**

    **(c) Le fonds existant appartient à Mike.** 43 065 photos. Deux dossiers
    sont DÉJÀ ceux de leur propriétaire : `Photos Flo` (Florine) et
    `Photos Papa` (le père de Mike). **Tout le reste part dans un
    `Photos Mike` à créer** — et ce déplacement est une opération à préparer
    avec soin : c'est un `rekey` massif de l'index, exactement ce qui a coûté
    748 décisions humaines le 22/08. **Le déplacement se fait par l'outillage
    du projet (plan à blanc, journal, quarantaine réversible), jamais à la
    main dans l'explorateur.** Mike a demandé de l'aide pour ce geste : c'est
    une tâche à part entière, à faire AVANT le code des comptes.

    **(d) Effacer, c'est effacer du NAS — via une corbeille de 6 MOIS.**
    Chacun n'efface que ses propres photos. La corbeille actuelle est
    réversible mais sans rétention définie : il faut une purge datée, et un
    endroit où l'admin voit ce qui va expirer.

    **(e) Les 3 364 décisions humaines existantes sont attribuées à Mike.**
    Rétroactivement, en une migration. Les nouvelles portent leur auteur.

    **(f) HTTPS : par TAILSCALE, et c'est presque gratuit.** L'accès passe
    déjà par Tailscale, qui chiffre le transport. Pour avoir en plus un vrai
    certificat — donc plus d'avertissement de navigateur, et des mots de passe
    qui ne circulent jamais en clair même sur le LAN :
    activer MagicDNS + « Enable HTTPS » dans la console Tailscale, puis, sur
    le PC qui héberge le serveur :
    `tailscale serve --bg --https=443 localhost:8080`.
    Tailscale termine le TLS, **le serveur Python n'a pas une ligne à
    changer**, le certificat Let's Encrypt est obtenu et renouvelé tout seul
    (DNS-01), et `--bg` le fait survivre au redémarrage. Ni port forwarding,
    ni nom de domaine public. L'adresse devient
    `https://<machine>.<tailnet>.ts.net`. **Caveat à dire à Mike** : le nom de
    la machine est publié dans les journaux publics de Certificate
    Transparency — choisir un nom qui ne dit rien de la famille.
    *Alternative si un jour il faut l'accès LAN SANS Tailscale* : le reverse
    proxy de DSM 7 + certificat Let's Encrypt par défi DNS, côté NAS. À ne
    faire que si le besoin apparaît.

    **Ce que ça change dans les invariants du projet.** La règle 2 (« les noms
    humains ne se perdent jamais ») devient « les noms de QUI ». Un conflit
    entre deux jugements contradictoires n'a aujourd'hui **aucune règle** —
    à trancher avant d'ouvrir l'écriture à d'autres que Mike.

    **Le coût.** C'est le premier chantier qui touche TOUTES les routes du
    serveur : chacune devient un point de contrôle. `monolith-surgery`
    s'applique. Et il n'y a **aucun test d'autorisation** aujourd'hui : le
    plancher de ce chantier, c'est un banc qui prouve qu'un utilisateur B ne
    voit RIEN du `PRIVE` de A — ni photo, ni vignette, ni compteur, ni
    suggestion.

    **Ordre de travail proposé** :
    1. le déplacement `Photos Mike` (avant tout code) — FAIT (session 52) ;
    2. la notion de propriétaire + l'attribution rétroactive à Mike —
       **CODÉ le 29/08 (session 65), à observer au redémarrage** : `auteurs.py`
       (règle pure : `proprietaire_de`, `reconcilier`, `arbitre`, `recler`,
       `garnir` ; 22 tests) branché au goulot `PEOPLE_STORE.set`/`PETS_STORE.set`
       — les trente écritures de décisions sont couvertes sans être touchées ;
       `utilisateur_courant()` (thread-local, admin tant que l'étape 4 n'existe
       pas) ; `migrer_auteurs()` au démarrage (idempotent, journal
       `docs/migration_auteurs.json`) ; le re-clé transporte `auteurs` par
       `recle_decisions` (serveur ET applicateur hors-ligne, 3 tests).
       **`#contesté` VISIBLE (session 66)** : `auteurs.contestations` (règle
       pure, 5 tests : qui a perdu, qui l'emporte, le MOTIF recalculé —
       propriétaire / admin / antériorité — et un gagnant annulé reste listé),
       `/api/people/contestes?name=`, compte `contestes` dans `/api/people/list`,
       badge « ⚖ N contesté(s) » sur la carte et bouton dans la fiche qui liste
       vignette + « Flo a retiré · **Mike** a confirmé et l'emporte (propriétaire
       de la photo) ». Observé à vide (aucun contesté tant qu'il n'y a que Mike
       — le premier vrai s'observera à l'étape 4). Reste : un conflit de
       `faces` ENTRE fiches n'a pas de règle (hors `exclude`↔`confirmed`) ;
    3. la VUE par utilisateur — **MÉCANISME POSÉ (session 66)** : `visibilite.py`
       (règle pure : `visible(chemin, utilisateur)` — tout est partagé sauf le
       `PRIVE` d'un autre, le `PRIVE` sans propriétaire est à l'admin, un fil
       de fond voit tout ; `VueFiltree` / `VueFiches` en lecture seule ;
       `brancher(store, utilisateur)` pose la vue sur `.data`, `get`, `has` ;
       14 tests dont le vrai `SqliteStore`), branchée aux CINQ magasins dans
       `server.py` via `utilisateur_vu()` (None tant que le routeur ne pose pas
       de compte — étape 4 — donc DORMANT, observé : mêmes compteurs), plus le
       garde `chemin_visible` sur `/media`, `/uploads`, `/api/thumb` (404,
       jamais 403). **Reste** : le banc de non-fuite SUR LES ROUTES (vignette,
       fichier, recherche, chips, carte) — il exige de dire QUI regarde, donc
       l'étape 4 ; et l'écriture sous vue (`STORE.data[k] = …` en direct
       tomberait sur la lecture seule : passer par `store.set`) — étape 5 ;
    4. les comptes — **POSÉS (session 66, choix de Mike : un mot de passe par
       compte)** : `comptes.py` (PBKDF2 300 000 tours + sel, jeton signé HMAC
       30 j, frein 5 échecs/5 min, porte `ouvert`/`ok`/`connexion`/`refus`,
       relecture du fichier à chaud ; 15 tests), `comptes.json` HORS git,
       `creer_compte.py` (amorçage sur le PC), page `/connexion`, routes
       `/api/connexion`, `/api/deconnexion`, `/api/moi`, `/api/comptes*`
       (admin ; chacun son mot de passe), section « Comptes » de Réglages.
       Le routeur ouvre CHAQUE requête (`_ouvrir`) : cookie → `_UTILISATEUR.nom`
       → la vue de l'étape 3 s'arme et les décisions portent leur auteur.
       **Sans compte, rien ne change** (observé : `🔓 comptes : aucun`,
       `/api/moi` → `porte: false`, Réglages rend la section). **À faire par
       Mike** : `creer_compte.py Mike` (ferme la porte), puis un compte `Flo`,
       une photo dans `Photos Mike\PRIVE`, et **`verifier_non_fuite.py`**
       (7 contrôles : thumb, faits, /media, compteur, fiche, recherche, porte)
       — le plancher du chantier, enfin prouvable ;
    5. l'écriture restreinte (effacement, nommage, renommage) ;
    6. la corbeille à 6 mois ;
    7. l'onboarding rédigé.

18. **Le garde-fou de la confidentialité — DEMANDÉ par Mike le 27/08.**
    Un agent repère les photos qui portent des **données personnelles**
    (factures, fiches de paie, pièces d'identité, relevés bancaires,
    ordonnances, captures de messages) et **prévient celui qui les envoie**,
    au moment où il les envoie, pour qu'il les déplace dans son dossier
    `PRIVE` ou les efface.

    **Pourquoi c'est un chantier et pas une finition.** Une fiche de paie
    photographiée pour la transmettre au comptable finit dans la pellicule,
    la pellicule se synchronise, et la photo se retrouve dans un dossier que
    ~20 personnes voient. Personne ne l'a décidé ; personne ne le sait. C'est
    la seule fuite de ce projet qui ne demande AUCUNE erreur de manipulation
    — juste l'oubli d'un geste.

    **(a) Le détecteur se greffe sur la passe qui existe déjà.** Le tagueur
    (`qwen3-vl:2b`) regarde DÉJÀ chaque photo, modèle chargé et image
    décodée. Une question de plus dans la même invocation ne coûte ni un
    deuxième pipeline, ni une seconde de GPU sur les 4 Go de VRAM. **Ne pas
    écrire un cinquième pipeline** : c'est l'invariant n° 4 de
    `monolith-surgery`.

    **(b) Le verdict est un AXE, pas un mot-clé.** `sensible:facture`,
    `sensible:paie`, `sensible:identite`… — comme `espece:`, donc couvert par
    le garde-fou du 26/08 : une valeur inventée rend zéro et le dit. Un tag
    libre se noierait dans les 43 000 autres.

    **(c) Le verdict NE VA PAS dans le XMP du fichier.** C'est l'exception à
    la règle du projet, et elle est délibérée : un fichier qui porte
    `sensible:fiche_de_paie` dans ses métadonnées ANNONCE son contenu à qui
    le reçoit — l'étiquette devient elle-même la fuite. Elle vit dans la base
    seulement. Corollaire : elle ne survit pas à la base, et c'est accepté.

    **(d) Ce que l'utilisateur voit.** À la fin d'un envoi : « 3 photos
    ressemblent à des documents personnels », les vignettes, et **deux
    gestes** — « déplacer dans mon dossier PRIVE » (dépend de 17a) et
    « supprimer » (par la corbeille réversible, jamais en dur). Plus un
    troisième, indispensable : **« non, ce n'en est pas un »**, mémorisé, qui
    ne repose plus jamais la question sur cette photo. Une alerte qu'on ne
    peut pas faire taire finit par être ignorée en bloc.

    **(e) Les deux erreurs ne coûtent PAS le même prix.** Un faux négatif est
    une fiche de paie visible par vingt personnes ; un faux positif est une
    photo de vacances signalée à tort, que l'on écarte d'un clic. Le seuil
    penche donc vers le signalement — **et c'est une décision, donc elle se
    mesure** : jeu étiqueté et banc `vision-eval` avant tout réglage. Sans
    banc, le seuil est une opinion ; et un score parfait serait une alarme.

    **(f) La passe rétroactive.** Les 43 000 photos déjà là n'ont jamais été
    regardées sous cet angle. La passe est longue mais sans risque (lecture
    seule + écriture en base) ; son résultat est une LISTE à trancher par
    Mike, jamais un déplacement automatique. Rien ne bouge sans un humain.

    **Ce qui dépend de 17** : le geste « déplacer dans PRIVE » et la notion de
    propriétaire. **Ce qui n'en dépend pas** : le détecteur, l'axe
    `sensible:`, le banc, et l'écran d'envoi — livrables avant 17, pour Mike
    seul d'abord.

    **Questions ouvertes** (à instruire, pas à trancher ici) : (1) quelle
    liste de catégories, et qui la fixe ? (2) que fait-on des photos DÉJÀ
    partagées quand la passe rétroactive en trouve une — on prévient les
    autres, ou on la retire en silence ? (3) le signalement doit-il bloquer
    l'envoi ou seulement l'accompagner ?

### Résiduels faible valeur (ne pas prioriser)
**MESURÉ le 15/08, et c'est pourquoi on n'y touche pas** : les deux planchers
1990 (`_fname_time`, `meme_jour.ANNEE_MIN`) coûtent **7** photos et **0**, et ils
sont **couplés** ; il subsiste aussi dans `plan_rangement.py`,
`recensement_doublons.py`, `diagnostic_dates.py`, sans effet tant qu'aucun
dossier d'avant 1990 n'y passe. Le **plafond 2100** (`22082010141.jpg` → 2082) :
72 en base, coût 0. Enfin `/files?dir=1&rec=1` (racine NAS) ne répond pas en
6 min, cause non cherchée.

## Acquis — ne pas reproposer (détail : git + `eval/DECISIONS.md`)

- **Le chip est FINI (26/08)** : `.chip` vit dans `components.css` seul,
  `font:` compris, et **7 pages sur 11** reçoivent la feuille commune.
  `.pchip` n'existe plus. Ne pas re-proposer de re-déclarer un chip dans une
  page : ce qui reste local doit DIFFÉRER et se dire (`subjects` :
  `padding: 0 var(--e-4)` ; `gallery` : `user-select` et l'état `.on`).

- **Cibles tactiles (26/08)** : les **221** cibles des onze pages sont
  comptées — **0 manquement prouvé** (0 sous le plancher, 0 inerte), 112
  planchers déclarés et honorés, 10 non décidables, 66 dont la hauteur n'est
  pas déclarée (le contenu décide) et 33 exemptées. Mesuré par
  `verifier_cibles.py`, qui lit l'imbrication du HTML, ce que
  `document.createElement` bâtit, et la cascade à quatre étages. **Ne pas
  re-parcourir les pages à l'œil pour ça, et ne pas re-proposer de lire la
  LARGEUR** : angle mort assumé, dit dans le rapport.

- **Accessibilité des contrôles (26/08)** : les **154** gestionnaires de clic
  des onze pages sont posés sur des contrôles — 138 natifs, 3 opérables à la
  main, 13 déclarés redondants, **0 grief de niveau A**. Mesuré par
  `verifier_controles.py`, pas supposé. Ne pas reprendre à l'œil.

- **Stockage** : SQLite local WAL (**43 064 entrées**), embeddings BLOB, backup
  NAS snapshot + `backup_verify`.
- **Reconnaissance** : SigLIP 2 (90 % r1) ; animaux 97,4 % r1 ; prototypes
  multiples ; vérif d'espèce.
- **Nommage** : attribution unifiée personnes+animaux (multi-noms, annulation
  10 s), rejets réversibles, reclassement `personne:`→`animal:` réversible.
- **Fichiers/Rangement** : `/browse` réversible, dédoublonnage (8,4 Go),
  rangement par année, orchestrateur de maintenance.
- **Renommage** : cœur + plan + applicateur réversibles ; **7 058 renommages
  appliqués et observés** (0 sauté, noms humains intacts) ; `gps_place` actif
  dans les noms (1 175 en portent un) ; garde-fou date de SCAN
  (`date_de_scan_presumee`, asymétrique, toléré à un an).
- **UI** : design system « chambre noire » (tokens, plancher a11y), planche
  contact, `/reglages`, `/people`, `/sujets` guichet unique ; **faits
  `date · lieu · noms` sous chaque vignette et dans la visionneuse**, avec
  leur SOURCE (exif / nom du fichier / année du dossier — gps / chemin),
  produits par la VUE et par un seul rendu partagé.
- **Correction** : faux positifs « Corriger »/« Nettoyer », retrait SÛR
  (`untag`→`exclude`), `exclude` autorité partout + auto-guérison.
- **Perf** : scoring vectorisé (156 s → qq s) ; `/api/thumb` (−98 % octets NAS) ;
  `_send_file` Range/streaming ; workers sous ordonnanceur ; GpuArbiter 27/27.
- **Tagging** : `qwen3-vl:2b`, prompt v2ctx ; Knowledge Builder : faits
  noms/date/lieu structurés et sourcés (`faits`), noms JAMAIS via le prompt ;
  `TAGGING_PIPELINE_VERSION` estampillée (`pipe`) — **sur les 81 photos taguées
  DEPUIS**, pas sur le fonds ; 1 lecture exiftool/photo.
- **Index/vecteurs** : cascade `forget_everywhere` au scan — **pilotée par
  l'index, donc aveugle à une clé déjà oubliée (21/08)** ; **re-clé complet
  (22/08)** : `rekey_everywhere` transporte enfin les DÉCISIONS humaines des
  fiches `PEOPLE`/`PETS` (`recle_decisions.py`), et `journaux_deplacements.py`
  relit les journaux d'annulation comme carte des déplacements ; **2 374 vecteurs
  orphelins purgés et observés** (0 muet sur 1 600 résultats, contre 2,6 %),
  quarantaine réversible `_corbeille_vecteurs/`.
- **Observabilité** : boucle scan/backup (O5), `backup_verify`, trois tâches de
  fond EXIF dans `/reglages` ; comptes de l'index au goulot (`comptes_index.py`).
- **Recherche** : quatre dimensions (noms · lieux · période · sens) ; **une
  seule règle de date** (filtre, tri, « même jour », `_best_time`, fait — la
  date de SCAN écartée à la lecture), **une seule règle de LIEU** (`faits_vue`,
  segments + mots collés découpés — jamais de sous-chaîne) et **une seule
  autorité des NOMS** (`_autorite_des_noms` : le filtre et l'affichage ne
  peuvent plus se contredire), partagées par le renommage, le KB, `/sujets` et
  la recherche.
- **Mesure** : `mesure_dates_scan.py` (`--lecture`), `mesure_tri_recherche.py`,
  `mesure_faits_backfill.py`, `mesure_faits_vue.py`, `mesure_lieu_visible.py` —
  `mesure_propagation_noms.py` (la règle d'AJOUT du curateur, garde-fou des
  clés fantômes compris), `mesure_visages_orphelins.py` (les décisions
  humaines posées sur des clés oubliées, et POURQUOI elles survivent) —
  lecture seule sur COPIE, jamais sur `photos.db` ; **`mesure_copie_base.py`
  fabrique cette copie** (API `backup`, source en `mode=ro`, copie DATÉE) — plus un
  geste de Mike, plus un aller-retour clavier avant de mesurer.
- **Pilotage** : trois canaux-fichiers, une seule façon de les lire
  (`canal.py`) — `_commande_serveur.txt` (redémarrer/arrêter, `pilotage.py`),
  `_commande_git.txt` (livrer, `git_agent.py`), `_commande_banc.txt` (mesurer,
  `banc_agent.py`). Les superviseurs se retirent quand la **génération**
  change. `GET /api/serveur` dit `demarre_a` et **`code_a_jour`**.
- **Hygiène et livraison** : nettoyage réversible (29) ; `27 - Git.bat` reste
  le guichet des gestes de Mike (état, commit guidé, fusion sans checkout,
  purge des branches, GitHub, rapport de l'agent au choix 8) ; **`git_agent.py`
  livre pour la sandbox** — `commit` ou `livrer` dans `_commande_git.txt`,
  **après contrôles** (serveur à jour, tests des modules touchés, `.bat` ASCII,
  lint). L'ordre s'inverse : **observer AVANT de commiter**.

## Pistes ouvertes par Mike (22/08) — à instruire, pas encore priorisées

- **Tirer plus d'intelligence du LLM local À MATÉRIEL CONSTANT.** Demande de
  Mike : évaluer ce que l'outillage actuel permet de gagner sans changer de
  modèle — le plafond de 4 Go de VRAM ne bouge pas, et « modèle plus gros »
  est déjà PARQUÉ pour cette raison (16/08). Axes à instruire, du moins cher au
  plus cher : sortie **contrainte** (grammaire / JSON forcé, qui supprime une
  classe entière d'erreurs de format sans coûter un octet de VRAM) ;
  **auto-cohérence** (plusieurs tirages, on garde ce qui se répète) ;
  **décodage spéculatif** ; quantifications récentes ; modèles petits parus
  depuis (le fonds tourne sur `qwen3-vl:2b`) ; et le **temps de calcul au
  moment de la réponse** plutôt que la taille. Source de départ donnée par
  Mike : `xda-developers.com/local-llms-used-prove-not-just-smaller-versions-cloud-models/`.
  **Habitude demandée** : se renseigner à l'ouverture de toute session qui
  touche au tagging, à la description ou à la recherche — ce domaine bouge vite
  et une doc de six mois est périmée.
  **Condition non négociable, et elle est déjà écrite** : rien ne se câble sans
  banc en aveugle sur un ET — apport réel **et** hallucination (`eval/METHODE.md`,
  et les trois conditions du point 16(c)). Le prompt de PRODUCTION double déjà
  les hallucinations, adopté sur un 25-15 : ce chantier-là commence par une
  mesure, pas par un modèle.

- **Ouvrir la médiathèque à TOUTE LA FAMILLE, avec la vie privée au centre.**
  Aujourd'hui l'outil est pour Mike et Flo. La cible : chacun a son **dossier
  perso**, y dépose ses photos, et **contrôle qui voit quoi** — partages
  explicites, révocables, et le compte rendu de ce qui est partagé. L'outil
  rend alors ce qu'il sait faire : classer, ranger, retrouver.
  **Ce que ça change de nature** : le projet passe d'un outil mono-poste à un
  service multi-utilisateur, et la vie privée cesse d'être un réglage pour
  devenir la contrainte qui gouverne le modèle de données. Trois questions à
  trancher AVANT toute ligne de code — (a) l'unité de propriété : la photo, le
  dossier, ou la personne reconnue dessus ? une photo de Flo prise par Mike
  appartient à qui ? (b) ce que la RECHERCHE laisse fuir : un compte de
  résultats, un nom qui complète, une vignette de prévisualisation suffisent à
  révéler ce qu'on croyait caché ; (c) les **visages** : nommer quelqu'un dans
  la photo d'un autre, c'est écrire sur son bien — et les noms partent dans les
  XMP des fichiers (règle 2), donc hors de portée de tout réglage.
  **Absorbe l'item « mode Flo »** de la Réserve, dont le déclencheur était
  tombé le 21/08 : la file de nommage à plusieurs redevient utile ici, mais
  comme conséquence, pas comme préalable.

## Réserve — futur, non prioritaire (triée le 12/08)

- **Multi-utilisateur** — « mode Flo » minimal (file de nommage des visages).
  **Son déclencheur est tombé le 21/08**, et l'item est désormais **absorbé par
  la piste « toute la famille »** ci-dessus (Mike, 22/08) : nommer à plusieurs
  est une conséquence du partage, pas un préalable à la vérité terrain.
- **Vidéo → audio** : coût élevé, valeur incertaine, aucun déclencheur.
- **Bibliothèque Figma** : le design system vit dans le code ; un miroir serait
  de la doc à double entretien.
- Récits LLM auto : écartés (hallucination).

**Vision** : mémoire familiale à provenance — deux tests : « PC mort lundi,
tout revit vendredi » (**promu** : chantier 12) et « aucun fait affirmé sans
provenance » (en cours : `faits` sourcés livrés, composition d'affichage au
point 3, MCP lecture au point 13).

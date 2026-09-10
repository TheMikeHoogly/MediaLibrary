# Feuille de route — MediaLibrary

Carte des **priorités**, rien d'autre. Les récits de travaux terminés vivent
dans **git** ; les rejets dans `eval/DECISIONS.md` (photothèque) et
`docs/DECISIONS_OUTILLAGE.md` (canaux, pilotage, livraison) ; la méthode dans
`eval/METHODE.md` ; l'éphémère dans `PROMPT_NOUVELLE_SESSION.md`. Audits :
`docs/AUDIT_INTERNE_2026-08.md`, `docs/AUDIT_EXTERNE_2026.md`, `docs/RANGEMENT_2026.md`.

> **`N:\\Photos` se connecte à chaque session** — règle dans `CLAUDE.md`
> (« Tester en réel »), depuis le 29/08.

## Priorité — repriorisée le 09/09/2026 (à lire en premier)

**Pourquoi cette section existe.** Celle du 26/08 avait cessé d'être une
priorité : 1 126 lignes, 39 jalons, dont **24 portent « FAIT », « CLOS » ou
« MESURÉ » dans leur propre titre**, et un numérotage en *bis / ter / quater /
… / quindecies* où **trois étiquettes désignent chacune deux chantiers
différents** — `1 septies` (l'espace disque et la règle Motion Photo),
`1 octies` (les 942 perdues et les vidéos), `1 nonies` (effacer l'extrait et
la recherche IA). Une liste ordonnée dont les numéros se
télescopent n'ordonne plus rien : elle est conservée plus bas comme archive de
preuve, pas comme plan. **Décision de Mike du 09/09 : la copie hors site passe
en fin de roadmap.**

**CE QUI COMMANDE TOUT : la campagne de retag tourne** (2 quater, lancée le
05/09). ~27 800 photos restantes au 08/09, **~190 photos/heure comptées dans le
journal** → environ six jours. Elle occupe le GPU et **elle interdit de toucher
au prompt** : le prompt EST la version du pipeline, une phrase ajoutée
rendrait candidates les 12 000 photos déjà refaites (3 bis (c)). L'ordre
ci-dessous en découle : pendant qu'elle tourne, on ne fait que ce qui n'a
besoin ni du GPU, ni du prompt, ni du serveur arrêté.

### A. Ce qui appartient à Mike

**A1. Finir la chaîne Takeout — FAIT par Mike le 09/09 à 12h.** Le bat 49 est
passé de bout en bout : les cinq contrôles, l'étape 3 bis qui a jugé les
**14 absentes jetables** (moitiés vidéo de Motion Photos sans extension, deux
preuves chacune), le `EFFACER` écrit en toutes lettres. **C: est passé de
171,2 à 236 Go libres sur 932** — les 96 Go annoncés, à la mesure près. **Le
chantier Google est clos pour de bon** : plus de Takeout, ni en `.zip` ni en
extrait, et le NAS porte tout ce qui devait l'être.

> Ce que ce bat aura appris, et qui vaut plus que les 96 Go : un garde-fou qui
> ne sait dire que « bloqué » finit par être contourné. Celui-ci a appris à
> distinguer — deux preuves pour déclarer une absente jetable, et l'arrêt sinon.
> C'est la différence entre un verrou et un jugement.

**A2. Trier les 213 photos sensibles — FAIT par Mike le 09/09, il en reste UNE.**
Le chantier 18 est clos pour l'essentiel : 60 documents à la corbeille, 7 rangés
en privé, le reste rendu à la galerie. **Deux défauts trouvés en le regardant
faire**, tous deux corrigés et observés en réel : l'onglet se rechargeait depuis
le haut après chaque verdict (invivable sur 213), et l'API ressuscitait
**67 dossiers déjà clos** parce que le drapeau `sensible` survit au déménagement
d'une photo — 68 annoncées là où il y en avait 1. Détail dans `eval/DECISIONS.md`
et `eval/DECISIONS_UI.md`.

**A2 bis. Ce qui reste du chantier 18** (ancien libellé, conservé) L'onglet existe, les
photos sont masquées, le geste par défaut est la corbeille — « la médiathèque
conserve des SOUVENIRS, pas des documents » (Mike, 07/09). **Zéro GPU, zéro
NAS, lecture d'index** : c'est le seul vrai chantier qui avance pendant la
campagne, et c'est celui qui protège des relevés bancaires. Il ne dépend que
du temps que Mike veut y mettre.

**A3. Lire la page `/aide`** (chantier 17, étape 7). Elle est posée et
vérifiée ; ce qui reste n'est pas une tâche mais un jugement — c'est sa
famille qui lira ce texte.

### B. Pendant la campagne, de mon côté

**B0. LE POINT LE PLUS IMPORTANT DE LA PROCHAINE SESSION : réviser `CLAUDE.md`
et `MARCHE_A_SUIVRE.md`.** Annoncé deux fois le 09/09, pas fait, et dit tel
quel à Mike. Ce sont les fichiers de RÈGLES — ce qu'une session lit avant tout
le reste — et la journée du 09/09 a produit cinq règles mesurées qui n'existent
aujourd'hui que dans un carnet éphémère : *un outil qui juge ne témoigne pas* ;
*une protection doit nommer la place, pas seulement le nom* ; *quand on corrige
un angle mort, on cherche ses autres portes, et un compteur d'étendue imprimé
les rend visibles* ; *ne jamais réécrire un `.bat` pendant qu'il tourne* ; et la
parade au pont qui écrit une version périmée (re-stager, comparer la TAILLE,
re-committer) — le défaut d'outillage le plus coûteux du projet, écrit nulle
part. Zéro GPU, zéro NAS, zéro serveur arrêté : c'est le meilleur usage d'une
session pendant que la machine calcule.

**B0 bis. Le ménage — à fermer.** Bat 50 passé deux fois le 09/09 : 14 puis
**506 fichiers / 49,3 Mo** dans `_corbeille_menage\20260909_212726\`. Il
reste **47 fichiers / 34,8 Mo** au prochain lancement (34 journaux d'annulation
de plus de 30 jours, 7 rapports périmés, 6 reliquats de quarantaine), puis une
décision de Mike sur les **283 Mo** de `_to_delete\menage_20260908\
_avant_deplacement\photos.db` — copie de la base, que le veto retient parce
que l'instrument ne peut pas la distinguer de la base vivante. Enfin, vider
`_corbeille_menage\` à la main après quelques jours.


**B1. Le reste d'audit** (ancien point 5) : **O11 FAIT le 09/09** — compression
HTTP, `/files` 157 → 48 ko et `/pets` 88 → 29 ko, mesuré sur le fil. Restent
**O14 FAIT le 10/09, et mesuré AVANT d'être touché** : `_reconcilier`
re-empreintait les **44 121 entrées à chaque `save()` — 627,2 ms sous le verrou
pour trouver ZÉRO changement**, contre 0,1 ms pour le flush signalé, soit
**6 547 ×**. Le point d'appel coûteux n'était pas le tagging (il passe par
`set()`, chemin rapide) mais **`_sync_dir`, qui termine CHAQUE DOSSIER par un
`save()`** — le chemin même qui avait gelé l'interface le 06/09. Trois points
d'appel passent à `flush()`, chacun avec sa preuve écrite à côté ; `save()` et
sa garantie sur les mutations profondes ne bougent pas, et un banc tient la
limite (`test_flush_o14.py`). Restent O8–O9 (matmul par visage et backfill
sémantique : les deux touchent des boucles de calcul, à faire quand la campagne
sera finie) et **O15** (les caches de vignettes). **L'adoption de
`components.css` par `browse`, `faces` et `reglages` — LIGNE CLOSE le 09/09,
et aucune des trois n'était ce qu'elle annonçait.** `reglages` : sa famille
maison `.b` borde à 5,97:1 là où `.btn--discret` bordait à 1,18 — c'est elle
qui avait raison. `browse` : même famille, tokens, 44 px, rien à corriger.
`faces` : **la page n'est plus servie du tout**, `/faces` est un 302 vers
`/people` depuis son retrait, et `ui/pages/faces.html` n'est lu par personne —
6 Ko de code mort derrière une redirection. **Balayage à l'appui** : les sept
pages servies mesurées en vrai, un seul contrôle sous 44 px, et c'est un lien
DANS une phrase, l'exception que le système a écrite. `/map` reste le témoin. **`animal:luna` sort aussi : SANS
OBJET** — 2 photos et non 3, et aucun consommateur ne lit la casse de ce tag
(`_kw_has` replie, la fiche est clé sur `name.lower()`, la recherche rend le
même compte). Détail dans `eval/DECISIONS.md`. Tout le reste est hors GPU et
hors prompt.

**B2. Les dettes nommées, petites et sûres** : `git rm --cached _collage6.py
_collage7.py` (ignorés mais suivis) ; le libellé du bat 32 ; et ce carnet
lui-même — voir B3.

**B2 bis. La question du 9 septembre sur Windows Update : RÉPONDUE, et par
Mike.** Trois réglages posés le 28/08 (notification activée, préversions
coupées, `NoAutoRebootWithLoggedOnUsers=1`) attendaient une preuve, à prendre
« le 9 au matin » — le Patch Tuesday tombant la veille. La preuve est arrivée
d'elle-même : *« L'appareil n'a pas redémarré tout seul cette fois. C'est moi
qui l'ai fait. »* Les réglages tiennent. Le piège que la consigne signalait —
confondre un redémarrage Windows avec une coupure thermique (Id 41) — n'a pas
eu à servir.

**B3. LE BUDGET DU CARNET — FAIT le 09/09, et pas comme annoncé.** J'avais dit
« scinder par domaine » ; en allant lire la règle, le domaine n'existait pas :
ce qui pesait était un RÉCIT de travaux finis, et l'entête du fichier dit
lui-même qu'il vit dans git. Retiré plutôt que déplacé — **108 881 → environ
30 000 octets, de 87 % à ~24 % du budget.** Une scission par statut aurait
refait l'erreur rejetée le 20/08.

### C. Quand la campagne s'arrête, et pas avant

**C1. La question au tagueur sur les documents sensibles** (3 bis (c)) — elle
n'est pas reportée par prudence, elle est **empêchée** : la toucher rouvrirait
12 000 photos déjà refaites.

**C2. Re-mesurer les Motion Photos arrivées depuis le 03/09** — demande le
serveur arrêté.

**C3. Le bilan de la campagne** : ce que `qwen3.5:4b|v3fr|kb1` a changé,
mesuré, pas supposé — c'est la première passe officielle du fonds, elle mérite
son compte rendu.

### D. Fin de projet

**D1. La copie hors site (12 bis) — repoussée en fin de roadmap par Mike le
09/09.** Le choix est le sien et il est noté tel quel. Ce qui reste vrai et qui
n'a pas besoin d'être répété à chaque session : après l'effacement de
l'extrait, le NAS est le seul exemplaire des ~40 000 photos, et un NAS chez soi
ne protège ni du feu, ni du vol, ni d'une fausse manœuvre. Le jour où Mike
rouvre le sujet, deux choses sont à faire *ensemble* : choisir le fournisseur,
et écrire le banc qui prouve que la copie distante contient ce que le NAS
contient — une sauvegarde qu'on ne vérifie jamais n'est pas une sauvegarde.

**D2. Les 633 photos sans copie connue.** Le registre `docs/photos_perdues.md`
est leur seule trace, il vit dans git. Rien à faire de plus tant qu'un vieux
disque ne réapparaît pas.

---

## Où on en est — état détaillé au 07-09/09/2026 (le plan est dans la Priorité ci-dessus)

**LA CAMPAGNE DE RETAG TOURNE** (chantier 2 quater, lancée le 05/09 à 16:50).
C'est le fait qui commande tout le reste : `retag_actif.txt` est posé. **Lu sur
la machine le 07/09 à 07:30** (`/api/maint/status` → `config.retag`) :
**8 368 photos re-taguées** en `qwen3.5:4b|v3fr|kb1`, **reste 31 629**,
débit instantané 12–16 s/photo → « encore ~5 jours ». Retirer le
fichier l'arrête au lot suivant sans rien perdre (la progression vit dans le
`pipe` de chaque entrée).

**Le 08/09 au matin, le débit a été COMPTÉ au lieu d'être calculé** — et il ne
dit pas la même chose. Huit heures de journal, heure par heure : 200, 196, 172,
191, 216, 175, 178, 230, soit **~190 photos/heure**, et **16 s médian** sur les
500 dernières. Reste ~27 800 → **~6 jours**, pas 4 ni 5. L'écart n'est pas une
dérive du GPU : une durée par photo divisée par 24 h suppose le GPU occupé sans
interruption, alors que la maintenance et le reste s'intercalent. *Le débit se
lit dans le journal ; le reste est une hypothèse déguisée en mesure.*

**Sur les « abandons », j'ai eu tort deux fois dans la même journée, et la
seconde fois est instructive.** Le matin j'ai lu 13 lignes « abandon » dans le
journal et corrigé le « 0 abandon » de la veille. L'après-midi,
`/api/maint/status` → `config.retag` dit **`abandons: 0`**. Les deux sont VRAIS,
et ils ne parlent pas de la même chose : le compteur compte les photos que le
tagueur a PRISES puis lâchées — il n'y en a aucune ; les 13 lignes du journal
sont des **refus d'entrée**, des fichiers déjà listés sur `/sante` que le
tagueur ne prend jamais (Mumi 6, Sandra 5, Sista 2, tous dans `Photos Flo`).
Le mot « abandon » désigne deux gestes différents dans deux instruments
différents, et j'ai corrigé un compteur juste avec une lecture de journal.
**Un chiffre ne se corrige pas par un autre instrument sans vérifier qu'ils
comptent la même chose** — et le journal, ici, était le mauvais.

**DÉFAUT DU 07/09 AU SOIR — FERMÉ LE SOIR MÊME, OBSERVÉ.** Quand l'écriture XMP dépasse le délai
(`_run_exiftool`, 180 s), Python TUE ExifTool — mais le
`<photo>.jpg_exiftool_tmp` qu'il avait déjà créé sur le NAS reste, et le
`finally` ne ramasse que l'argfile. **Toute écriture ultérieure sur cette photo
échoue alors pour toujours** (« Temporary file already exists »), réparation de
dernier recours comprise, et la photo est abandonnée. **Compté ce soir : 13
photos depuis 14:05, 29 échecs**, dans trois dossiers de `Photos Flo` — un
toutes les 30 à 60 min, ~0,5 % des re-tags. Sur les 5 jours qui restent :
60 à 80 photos. **Aucune n'est abîmée** — vérifié fichier par fichier : la
photo d'origine est là, plus grosse que le tmp (qui est une copie tronquée), et
sa date remonte à août. Ce qui manque, c'est le XMP du FICHIER ; les mots-clés,
eux, sont bien dans l'index. Deux gestes, tous deux à Mike : effacer les 13 tmp
sur preuve, et ramasser le tmp dans le `except TimeoutExpired` — un nettoyage
derrière notre propre processus tué, sur un chemin connu, pas le « balayage »
que `CLAUDE.md` interdit.

**LE CORRECTIF, posé et observé le soir même** (`ecriture_meta.tmp_orphelin`,
`server.ramasser_tmp_exiftool`, `retenter_tmp_orphelins`, 13 bancs) : la règle
pure reconnaît CE refus et pas un autre ; `write_metadata` ramasse sur preuve
puis réessaie UNE fois ; et le `except` du timeout ramasse ce qu'il vient
d'orpheliner — c'est là que le défaut naissait. Une passe unique à jeton rouvre
ce qui était déjà fermé. **Deux corrections de méthode payées en chemin** : la
passe cherchait `retag_fail`, la marque du TAGUEUR, alors que ces photos-là
sont fermées par `retro_write_metadata` (`write_fails` + `file_error`) — elle a
rendu « 0 photo » sur quatorze tmp bien présents, banc vert à l'appui ; et
« pas de tmp » n'est pas « échec », 9 photos restaient fermées alors que plus
rien ne les fermait. **Observé** : 22 entrées examinées, 13 tmp retirés, 9
marques devenues sans objet, **0 tmp restant, 0 gardée faute de preuve**.

**Deux dettes du 06/09 sont fermées, MESURÉES en réel le 07/09 au matin.**

1. **Le GPU ne jeûne plus au redémarrage.** `remplir_file_retag()` était en
   tête de `scan_uploads` — mais `scan_uploads` n'est appelée qu'APRÈS le
   travail de démarrage de `maintenance_loop`. Le délai entre la bannière
   `DEMARRAGE` et le premier lot enfilé, relevé sur les quatre redémarrages du
   06/09 : **69 s, 99 s, 51 min, 81 min** — il ne dépendait pas du code mais de
   l'humeur du NAS, ce qui est pire qu'un coût fixe : rien ne le prédisait.
   Le remplissage passe désormais en TÊTE de `maintenance_loop`, avant
   ExifTool et avant les trois passes de purge. **Observé deux fois** :
   bannière 07:25:51 → lot enfilé **07:26:00** (9 s), puis à 07:28 un
   `/api/serveur` à **9,4 s d'uptime** montrait déjà `en_file: 500`. Les 9 s
   sont le chargement des cinq magasins SQLite, rien d'autre.
2. **La maintenance cède maintenant à un balayage NAS en cours.** `is_busy()`
   comptait l'UI (`ui_recent`) et la charge machine (`system_busy`), jamais le
   SCAN — la seule des trois qui tient le disque, et exactement l'ordre observé
   le 06/09 à 11h38. Un compteur `SCAN_NAS_EN_COURS` posé avant le `try` du
   scan et levé dans son `finally` (un scan qui meurt ne doit pas laisser la
   maintenance en retrait pour toujours). **Observé** : `boucle.scan_nas` à
   `true` à 88 s d'uptime, pendant l'énumération initiale. Et le journal ne
   ment plus : il disait « UI active, reporte » quoi qu'il arrive — il aurait
   donc nommé l'UI le 06/09 ; `raison_busy()` nomme la vraie cause.
   **Ce qui RESTE ouvert, et c'est l'autre moitié** : dans l'ordre INVERSE
   (une étape lourde de maintenance déjà partie, puis le scan qui arrive
   dessus), rien n'arrête le scan. Pas touché : la ligne `nas = first or deep
   or …` porte un garde-fou voulu (banc
   `test_un_cycle_approfondi_implique_le_nas`) et ce n'est pas une correction
   à faire sans l'avoir mesurée.
3. **L'outil qui rend au fonds les photos sans jumeau connu est ÉCRIT**
   (`restaurer_corbeille.py`, `47 - Restaurer les photos sans jumeau
   connu.bat`, 10 bancs sur un faux fonds). Il ne supprime rien, refuse une
   origine déjà occupée, refuse un sha256 qui ne colle plus au manifeste,
   s'annule par journal, et compte « déjà fait » comme un succès. **Les trois
   cas vérifiés en vrai le 07/09** : fichiers présents, empreintes conformes,
   dossiers d'origine existants et LIBRES (`Photos Flo\Floufline`,
   `Photos Flo\2015 Bolivie`, `Photos Flo\Sista\40 ans Val et Thierry`).
   **Pas lancé** : déplacer des fichiers de l'archive est un geste de bat, et
   l'agent banc n'accepte que les familles qui MESURENT.

**Ce qui est SÛR pendant qu'elle tourne** : doc, UI, CSS, le reste de l'audit
interne, l'adoption de `components.css` par `browse`/`faces`/`reglages`
(`/map` est le témoin, on n'y touche pas). **À ÉVITER** : la phase 2 des vidéos
(transcodage), tout banc qui appelle Ollama avec un AUTRE modèle, tout bump
d'une autre version de pipeline, et l'unification du re-clé (chemin de mutation
de l'index ; les trois copies ont été comparées le 05/09 et sont cohérentes).

**Ce qui attendait un geste de Mike au 06/09 — TOUT FAIT DEPUIS** : bat 46
puis bat 24 (corbeille de rangement réancrée et purgée, 25,36 Go rendus), les
6 photos sensibles de l'échantillon tranchées, et le 09/09 les 213 candidates
triées. `QUESTIONS_MIKE.md` est vide.

**LA PANNE DU 06/09 MIDI — corrigée, à comprendre avant de retoucher le scan.**
La campagne s'est arrêtée seule à 11h34, GPU à 0 % pendant deux heures, sans
rien casser. Cause : le remplissage de la file de retag vivait dans
`_sync_dir`, appelée APRÈS l'énumération de la racine — un `rglob` de 44 000
fichiers sur SMB, **mesuré entre 632 s et 1 473 s** selon la charge, et **plus
de 85 minutes** ce jour-là quand la passe de maintenance puis 2 139 vignettes
de galerie sont tombées dessus. La correction du 05/09 avait détaché ce bloc
du scan APPROFONDI ; il restait attaché à l'énumération elle-même, par `cur`.
Or `cur` ne servait qu'à fournir des CLÉS, et l'index les a toutes, en
mémoire. → `remplir_file_retag()`, appelée EN TÊTE de `scan_uploads`, avant
tout contact avec le disque (6 bancs neufs dans `test_retag_campagne.py`, dont
un qui refuse `rglob`/`cur`/`Path(` dans son corps).
**Ne pas confondre avec le comportement NORMAL** : quand Mike navigue dans la
photothèque, le tagueur s'efface — c'est l'invariant « l'UI cède la priorité
au NAS », et c'est voulu. Le défaut, c'est l'arrêt de 11h34 à 12h48, sans
aucune activité UI.
**(a) À MOITIÉ FERMÉ le 07/09** : la maintenance ne se reporte plus seulement
sur « UI active » — elle se reporte aussi quand un balayage NAS tourne
(`SCAN_NAS_EN_COURS`, observé à `true` pendant l'énumération initiale). C'est
l'ordre du 06/09, donc la cause directe des 85 minutes. **Reste l'ordre
inverse** : une étape lourde déjà partie, puis le scan qui arrive dessus.

**(b) VIGNETTES — OBSERVÉ EN RÉEL le 06/09 au soir.** Sur
`2026/260531_Samsung_MHU/Camera` : **585 tuiles, 30 chargées, 555 encore en
attente**, plafond à 4 requêtes en vol. Avant, les 585 partaient d'un coup.**
Une page de dossier demandait une vignette 512 px pour CHAQUE fichier : 2 139
lectures NAS à froid pour `Photos Mike/2022`, une par seconde. Les tuiles
portaient pourtant `loading="lazy"` — **l'attribut natif ne borne rien** : une
fois qu'il décide de charger N images, il pose N requêtes, et un navigateur
n'ouvre que six connexions par hôte. Les six sont restées prises pendant des
dizaines de minutes, au point qu'un AUTRE onglet vers le même serveur
n'obtenait plus de connexion — sa requête n'apparaît même pas dans le journal.
→ `window.Vignettes` dans `ui/global.js` : un IntersectionObserver à marge
choisie (400 px) **et** une file unique qui plafonne à `EN_VOL_MAX = 4`
requêtes en vol, pour qu'il reste deux connexions pour naviguer. La vue
Dossiers passe à `data-src` (plus aucun `src` en dur, plus de `lazy` natif) ;
la galerie garde son observateur mais passe par la même file. Banc :
`verifier_vignettes.py` (vert). Mesuré au navigateur, pas déduit.

**Trois mesures du 06/09 après-midi, à ne pas refaire** :
1. **La corbeille de rangement ne se purgeait pas** parce que le rangement par
   année a déplacé les canoniques : 389 groupes, **15** seulement avec leur
   canonique au chemin noté, **27,6 Go** bloqués. 357 canoniques retrouvées
   vivantes ailleurs — mais sur 40 vérifiées au sha256, **3 étaient une AUTRE
   photo** portant le même nom. Le nom se trompe à ~7 % : à cette échelle, une
   purge sur le nom détruirait la seule copie d'une vingtaine de photos.
   → `verifier_corbeille_canoniques.py`, `docs/corbeille_canoniques.json`.
2. **Le banc « sensibles » a mesuré `qwen3-vl:2b`**, l'ANCIEN modèle de prod —
   `modele.txt` dit `qwen3.5:4b` depuis le 05/09. La mesure du 04/09 ne dit
   donc rien du modèle qui tourne. Et son verdict `illisible` (19/90) n'est
   pas « fichier illisible » mais « le modèle n'a pas répondu » : les 24
   photos ont toutes été ouvertes sans erreur par `verifier_planches_sensibles.py`.
3. **La barre de filtres était DÉJÀ repliée par défaut** ; ce qui mangeait le
   haut de l'écran, c'était l'EMPILEMENT (nav + barre + attente + dossiers +
   filtres + personnes). Une bascule commande désormais les deux barres de
   filtre — une ligne de moins avant la première vignette.

## La priorité du 26/08 — RETIRÉE le 09/09, elle est dans git

> **Pourquoi elle n'est pas devenue un second fichier.** L'entête de ce carnet
> dit ce qu'il est : *« Carte des priorités, rien d'autre. Les récits de travaux
> terminés vivent dans git. »* Cette section pesait **79 287 octets, 73 % du
> fichier**, pour 39 jalons dont la quasi-totalité portait « FAIT », « CLOS » ou
> « MESURÉ » dans son propre titre — et trois étiquettes en double (`1 septies`,
> `1 octies`, `1 nonies` désignaient chacune deux chantiers). Ce n'était plus une
> priorité, c'était un récit.
>
> **Et la scinder vers `docs/ARCHIVE_*.md` aurait refait une erreur déjà payée** :
> le découpage par ÂGE ou par STATUT a été rejeté le 20/08 (`nettoyer_session.py`,
> commentaire de `TRACKING_MD`) parce qu'il oblige à relire les deux fichiers pour
> retrouver une chose. Les carnets se découpent par DOMAINE — c'est ce qu'ont fait
> `DECISIONS_OUTILLAGE`, `DECISIONS_UI`, `DECISIONS_TAGGING`. Un récit terminé,
> lui, n'a pas de domaine : il a une date, et git la garde mieux que nous.
>
> **Rien n'est perdu, et rien n'est orphelin.** Chaque jalon a été relu avant
> d'être retiré : les clos sont dans l'historique git (`git log -p ROADMAP.md`,
> juste avant le commit du 09/09) ; les cinq encore vivants — la campagne de
> retag, le chantier 17, le chantier 18, la question au tagueur, le reste
> d'audit — sont repris nommément dans la Priorité en tête de ce fichier.

## Historique détaillé (sessions ≤ 63, pré-05/09) — archivé dans git

Les comptes-rendus session par session (57→63, 54→56, 50→53, 47→49, 46,
45 bis/ter/quater, 44, 36→43, 28→35) sont retirés d'ici : ce fichier
grossissait vers le seuil de 100 000 octets (`nettoyer_session.py
--lint-only`), et leur contenu — chiffres, dates, décisions — est déjà dans
l'historique git de CE fichier (`git log -- ROADMAP.md`) ainsi que dans les
commits des chantiers eux-mêmes. Rien n'y était encore ouvert : tout ce qui
restait actionnable en a été extrait vers « Priorité » (ci-dessus) avant ce
nettoyage (05/09). Ne pas reproposer une mesure déjà faite sans motif neuf
— voir « Acquis » plus bas.

## Détail historique des chantiers 0–18 (pré-26/08) — archivé dans git

Le détail complet (specs, mesures, sous-étapes) des chantiers listés ici
entre le 12/08 et le 26/08 — rattachements, résidu ambigu, vérité terrain,
extraction `ui/`, cross-pipeline Mutz/Caline, reconnaissance (parquée), UI
onze pages, assurance-vie, MCP lecture seule, recherche IA contextuelle,
chantier 17 (multi-utilisateurs) et 18 (confidentialité) — vit dans
l'historique git de ce fichier, pas ici. Leur état COURANT (ce qui reste
vraiment ouvert) est dans « Priorité » en tête de fichier : chantier 17 →
point 3, chantier 18 → point 3 bis, les autres sont CLOS ou PARQUÉS et
listés dans « Acquis » ci-dessous. Retiré le 05/09 pour la même raison de
taille que l'historique par session.

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

  **Mise à jour (05/09)** : chantier ouvert par la décision FR-only
  (2 quater) — modèles « petits parus depuis » enfin exploré :
  `qwen3.5:4b` trouvé et retenu (la campagne, en tête de la Priorité). **La condition non
  négociable ci-dessus n'est qu'à MOITIÉ remplie** : la comparaison a
  mesuré l'apport réel (calico, lac, pas de fuite de noms) mais PAS en
  aveugle (le nom du modèle était connu en lisant le rapport) et sur un
  tirage CIBLÉ (8 photos difficiles), pas un vrai A/B comme celui qui a
  adopté v2ctx (25-15). À instruire si Mike veut la rigueur complète avant
  de lancer la campagne, ou à accepter tel quel — son choix, pas le mien à
  trancher seul.

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

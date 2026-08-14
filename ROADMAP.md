# Feuille de route — MediaLibrary

Carte des **priorités**, rien d'autre. Les récits de travaux terminés vivent
dans **git** ; les rejets dans `eval/DECISIONS.md` ; l'éphémère (état de
session, choses à observer) dans `PROMPT_NOUVELLE_SESSION.md`. Audits :
`docs/AUDIT_INTERNE_2026-08.md` (I1–I17, O1–O15, A–F),
`docs/AUDIT_EXTERNE_2026.md`, `docs/RANGEMENT_2026.md`.

## État (14/08/2026, session 14)

**Session 13 OBSERVÉE EN RÉEL, tout passe** (casse des clés + « même jour ») :
dossier NAS ancien → tags, description, personnes, Géo, date précise (2 août au
lieu du 1ᵉʳ janvier) ; bouton « Même jour » → 115 photos sur 11 années, référence
exclue ; photo sans date précise → bouton caché ; diaporama aléatoire NAS →
19/20 clés NAS, 0 sans tags, 0 sans description ; et la chaîne complète sur une
clé NAS (`/api/similar` encodée, `/api/thumb` 200, `/api/jour` précise).

**Le plancher 1990 des années du CHEMIN — CORRIGÉ (s14), à observer en réel.**
`_path_years` filtrait à `1990 <= y`, ce qui va pour une date d'appareil photo et
pas pour un nom de dossier : un dossier « 1985 » ne rendait AUCUNE année. Deux
dégâts mesurés : (1) `_path_year` rendait 0, `_best_time` tombait sur `mtime` et
**714 photos de 1982-1989 étaient datées de 2026**, la date de copie sur le NAS ;
(2) le garde-fou anti-scan de `date_fiable` se désarme quand le chemin n'a aucune
année — les 13 photos de `1985\19850601 …` portent la date de la numérisation
(16/11/2006). Plancher à **1900**, dans `server._path_years` ET
`renommage_facts.path_year` (mêmes semantics, même bug). Au passage, `_path_years`
**exclut désormais le nom de fichier**, comme `renommage_facts` le faisait déjà et
le documentait : `119-1908_IMG.JPG` dans un dossier 2002 rendait `{1908, 2002}` et
`min()` reculait la photo de 94 ans — trou masqué jusqu'ici par le plancher 1990.
Mesuré sur 19 384 fichiers : 38 photos tirées en arrière par leur nom, 0 qui perd
son repli. Tests : `test_plan_renommage.py` 11/11 (2 cas ajoutés),
`test_tagging_meta.py`, `test_meme_jour.py` verts.

**OBSERVÉ EN RÉEL (s14)** : 716 photos de 1982-1989 datées par leur dossier (1986 :
306, 1984 : 152, 1983 : 138, 1985 : 100…), les 38 photos tirées en arrière par un
numéro de scanner corrigées, et **0 régression sur 20 239 fichiers** vérifiés
(Photos Papa, Photos Flo, 2010, 2008, _A TRIER) — aucune photo n'a perdu son
repli. Restent 15 photos hors de leur année : elles portent une date PRÉCISE
fausse (numérisation du 16/11/2006), cas classé REJETÉ.

**Conséquence pour les gestes de renommage** : `docs/plan_renommage.json` a été
produit AVANT ce correctif — les photos des années 80 y sont en « sans date ».
**Régénérer le plan**, avant tout lot.

**ExifTool disparu en silence — CORRIGÉ (s14), à observer au prochain
démarrage.** Symptôme : « ExifTool indisponible (HTTP 404) » au lancement alors
que `exiftool-13.59_64\exiftool.exe` est bien là ; `EXIFTOOL = None`, donc les
trois tâches de fond sortent aussitôt et les tags de noms repassent en plan B
`piexif` (JPEG, sans XMP). Chaîne complète : `server.py` faisait
`DATA_DIR.mkdir()` / `UPLOAD_DIR.mkdir()` **au niveau module**, donc à l'IMPORT ;
sous POSIX (VM du pont, sandbox) l'antislash est un caractère ordinaire, et ces
lignes ont fabriqué deux répertoires nommés `\\NAS-Bremblens\home\Photos\_Uploads`
et `\\nas-bremblens\home\Uploads` (04 et 31/07, vides) à la racine du projet ;
Windows relit ces noms comme des chemins UNC, le `rglob` de `ensure_exiftool` est
parti interroger le NAS, l'`except OSError` était MUET, et le seul message
restant était le 404 du téléchargement de secours. Trois correctifs : les deux
`mkdir` passent par `_creer_dossier_si_absolu` (refuse et le DIT si le chemin
n'est pas absolu sur la plateforme courante) ; `ensure_exiftool` regarde d'abord
les emplacements probables sans rien parcourir ; le parcours de secours élague
(`EXIFTOOL_SKIP_DIRS`, noms à séparateur) et **rend compte** de ce qu'il n'a pas
pu lire. Les deux dossiers fantômes sont dans `_to_delete\faux_dossiers_unc\`.

## État (14/08/2026, session 13)

**Trois tâches de fond mortes en silence — réparées et observées** (`fix/backfills-silencieux`,
fusionné) : garde `if not EXIFTOOL: return` placée AVANT le `sleep`, alors que
`maintenance_loop` affecte `EXIFTOOL` dans le même souffle. Résultat de la nuit du 13
au 14/08, 0 fichier muet et 0 erreur : **32 822 dates** sur 42 060 lues (2008 : 0 % →
60 % de dates précises ; 2010 : 2 % → 98 %), **184 tags de noms** rapatriés des XMP
(cette passe n'avait jamais tourné), **5 394 photos géolocalisées** de plus — la carte
passe de 1 220 à **6 614 points**.

**Casse des clés dans la vue dossier — CORRIGÉE (s13), à observer en réel.**
`Path.resolve()` minuscule le nom d'hôte SMB, `STORE.get(str(f))` est un accès de
dictionnaire : la galerie par dossier ratait TOUTE la racine NAS et affichait la
photothèque sans tags, sans description, sans GPS, au 1ᵉʳ janvier. `_serve_gallery` et
`_serve_random` (même bug, non repéré) passent maintenant par `_index_key_for_path`,
adossé à `fichiers.build_key_index`. La clé rendue au client est désormais la clé
d'index EXACTE : `/api/thumb`, `/api/similar` et la suppression par clé visent juste.

**Chantier 6a « même jour, autres années » — LIVRÉ (s13), à observer en réel.**
Moteur pur `meme_jour.py` (+ `test_meme_jour.py`, 40 vérifications), route `/api/jour`,
page `/files?jour=<clé|MM-JJ>`, bouton « Même jour » dans la visionneuse. **Dates
PRÉCISES uniquement** (EXIF `taken` + date du nom de fichier) : le repli « année du
dossier » est exclu par construction, sinon des milliers de photos se rangeraient sous
un 1ᵉʳ janvier qui n'a jamais existé. Toutes les années, groupées, référence exclue
(tranché par Mike le 14/08). Zéro IA, zéro GPU, zéro accès NAS.

## À faire — par ordre de valeur (réordonné au triple audit du 11/08)

1. **Vérité terrain humaine — au fil de l'eau, ce n'est PAS un blocage.**
   ~0,8 % de confirmations (91/12 072) ; instrumentation livrée, files garnies
   (18 personnes + 120 animaux). **Cadrage tranché par Mike (12/08)** : le
   stock est limité par la **connaissance**, pas par l'outillage ni la volonté
   — beaucoup de groupes portent des visages que Mike ne sait pas nommer, et
   **Flo les nommera** quand l'outil sera à ~90 %. **300 personnes déjà
   reconnues** : l'essentiel du travail humain est fait. On juge donc **quand
   l'occasion se présente**. Métrique = erreurs découvertes, pas l'accord
   modèle-humain. Conséquence : le point 9 (algo) reste parqué — ordre de
   travaux, pas dette.
2. **Observer en réel ce qui est livré** : v2ctx/Knowledge Builder, purge des
   19 doublons, bouton « Semblables », vignettes Lieux, **et les trois tâches
   de fond réparées** — tous **faits ✔**. Reste : re-upload = une entrée, seek
   vidéo mobile, test du Z. Veille v2ctx sur un lot plus grand : astre/objet,
   fuite de la date en prose — tout geste de prompt passe par `vision-eval`.
3. **Knowledge Builder + version de pipeline : CÂBLÉS (s8) et OBSERVÉS (s9)** —
   suite naturelle : composition d'affichage date · lieu · noms depuis `faits`
   (choix tranché : structuré d'abord, affichage plus tard) ; re-tagging
   opt-in des entrées v0 si la qualité observée le justifie (~51 h GPU,
   jamais automatique).
4. **Gestes Mike, dans cet ordre** : nettoyer Flo (5 909 photos ; « Corriger »
   seuil ~0.2 ou « Nettoyer (référence) ») ; re-rejeter Caline une fois ;
   activer `gps_place` (`18 - …gazetteer.bat` → `enrichir_lieux.py` →
   `--ecrire` → redémarrer) — profite du backfill GPS enfin réparé ; lots de
   renommage **débloqués** (plan = 2114 ; **régénérer le plan d'abord**, cf. le
   plancher 1990 ; le banc `eval/tagging_v1.json`, keyé par chemin, en deviendra
   partiellement caduc — attendu).
5. **Correctifs d'audit restants** : I4–I8, O7–O9, O11–O15. **O1 clos partout** ;
   O15 (purge de `photo_thumbs/`) gagne en poids. La casse des clés de la vue
   dossier est **corrigée** (s13) — reste à l'observer en réel.
6. **Navigation par similarité et par date** : `/api/similar` + `/files?sim=` +
   bouton « Semblables » **observés bons (13/08)** ; « même jour, autres années »
   **livré et observé (s13/s14)**. Petits restes vus à l'observation : le bouton
   de la visionneuse dit « Meme jour (14 aout) » quand la page dit « 14 août »
   (`MOIS_JOUR` en ASCII dans le JS, sur la foi d'un commentaire faux — la règle
   ASCII vaut pour les `.bat`) ; et le 14 août contient du bruit (bloc 2010 en
   triple sur trois chemins NAS, 14 captures d'écran sur 115). Reste aussi :
   doublons proches bridés (>0,98 + même
   journée → quarantaine réversible, 50 paires jugées avant tout geste). Élargir
   « même jour » à une fenêtre ±1 j n'est PAS décidé : à ne faire que si la
   moisson au jour strict se révèle trop maigre en réel.
7. **Extraction `ui/` — décision nette à prendre** : session dédiée `bundle.py`
   ou parcage explicite (item zombie ; préparatoire fait et vérifié, détail git).
8. **Cross-pipeline (Mutz/Caline)** : outil livré, réversible. Fix auto REJETÉ
   (18 % faux rejets) ; seule piste : re-mesurer sur découpes SANS marge.
   Relancer si un nouveau nom d'animal apparaît en `personne:`.
9. **Reconnaissance — algo (BARRIÈRE : vérité terrain ≥ ~5 %).**
   HDBSCAN/Chinese Whispers/AdaFace inévaluables à 0,8 % ; écrire les tags
   SigLIP = mutation XMP → la version de pipeline tagging existe désormais
   (session 8), la barrière vérité terrain reste.
10. **Données / finitions** : édition des réglages depuis `/reglages` (wagon :
    Pause globale des workers, résiduel rattaché le 12/08) ; 2ᵉ passe des 945
    illisibles + `recuperees/` → NAS ; `docs/journaux/` gitignoré + purge des
    undo appliqués > 30 j (I12).
11. **UI — harmonisation des vues (demandé 12/08, skill `photo-ui`)** :
    (a) personnes : clic sur l'image d'une personne → lancer sa démo aléatoire ;
    (b) lieux : le texte sous chaque image d'un dossier lieu passe en tooltip
    (gain de place dans la grille) ; (c) harmoniser les possibilités
    d'affichage visages/lieux/animaux — le maximum de fonctionnalités pour
    tous, **sauf** l'effacement d'image, réservé à l'onglet Classification ;
    (d) zoom/redimensionnement des images aux doigts (pinch) et à la souris
    (molette) dans les démos et l'affichage plein écran ; (e) wagons résiduels
    rattachés le 12/08 : retrait de l'ancien bandeau `#pending`, libellé
    `/pets` « empreintes calculées » (affiche 0 après redémarrage).
12. **Assurance-vie : restauration à blanc (PROMU 12/08).** Le test « PC mort
    lundi, tout revit vendredi » : restaurer le snapshot NAS sur un dossier
    vierge, chronométrer, noter chaque manque (dont la copie hors-site de
    `journal_jugements.jsonl`, aujourd'hui locale et gitignorée). Tant que ce
    drill n'a pas tourné une fois, la sauvegarde « vérifiée » est une promesse.
13. **Serveur exposé en MCP, lecture seule d'abord (PROMU 12/08, prérequis
    soldé).** Recherche (sémantique + tags), fiches personnes/animaux et
    `faits` sourcés en outils MCP locaux (JSON-RPC stdio, zéro dépendance —
    skill `mcp-builder`) : interroger la bibliothèque depuis une conversation
    Claude, premier fruit concret de la provenance. Écriture : plus tard, après
    usage réel en lecture.
14. **Recherche IA locale contextuelle (demandé 12/08).** Le champ de
    recherche comprend une demande en langage naturel et la décompose. Ordre :
    (a) **déterministe** d'abord — parser en filtres structurés depuis
    l'existant (noms = fiches, dates, lieux = `gps_place`/`faits`, tags, reste
    → SigLIP) : zéro GPU, couvre l'essentiel ; (b) ensuite seulement,
    **escalade ponctuelle** vers un modèle chargé à la demande (bail
    GpuArbiter, 4 Go, déchargé après). Modèle et seuil = éval `vision-eval`,
    jamais câblé sans mesure. Mêmes briques que le MCP (13).
15. **À évaluer (`vision-eval`)** : Florence-2 léger.

### Résiduels faible valeur (ne pas prioriser)
Vidé le 12/08 : les trois résiduels sont rattachés en wagons aux chantiers 10
(Pause globale des workers) et 11e (bandeau `#pending`, libellé `/pets`).
Ajoutés le 14/08, chiffrés et volontairement non traités : (a) le plancher 1990
subsiste dans `plan_rangement.py`, `recensement_doublons.py` et
`diagnostic_dates.py` — sans effet mesuré tant qu'aucun dossier d'avant 1990
n'est rangé ni recensé, mais c'est la même erreur ; (b) `/files?dir=1&rec=1` (toute
la racine NAS) ne répond pas en 6 minutes — la galerie récursive à la racine est
inutilisable, cause non cherchée.

## Acquis — ne pas reproposer (détail : git + `eval/DECISIONS.md`)

- **Stockage** : SQLite local WAL (**43 048 entrées** au 12/08 — le 64 676 de
  la première version datait du 31/07, avant dédoublonnage et purges de dossiers
  cachés ; ce chiffre porte désormais sa date), embeddings BLOB, backup NAS
  snapshot + `backup_verify`.
- **Reconnaissance** : SigLIP 2 (90 % r1) ; animaux 97,4 % r1 ; prototypes
  multiples ; vérif d'espèce.
- **Nommage** : attribution unifiée personnes+animaux (multi-noms, annulation
  10 s), rejets réversibles, reclassement `personne:`→`animal:` réversible.
- **Fichiers/Rangement** : `/browse` réversible, dédoublonnage appliqué
  (8,4 Go), rangement par année, orchestrateur de maintenance.
- **Renommage** : cœur + plan + applicateur réversibles prêts (plan = 2114) ;
  `gps_place` codé (pas activé).
- **UI** : design system « chambre noire » (tokens, plancher a11y — dont
  `:focus-visible` sur la galerie, s13), planche
  contact, `/reglages`, `/people` réorganisé, `/sujets` guichet unique
  (sous-nav + onglet Classification + files « À vérifier » miroir
  personnes/animaux, clavier Espace/X/Z/lettre).
- **Correction** : faux positifs « Corriger »/« Nettoyer (référence) », retrait
  SÛR (`untag`→`exclude`), `exclude` autorité partout + auto-guérison.
- **Perf** : scoring vectorisé (156 s → qq s) ; `/api/thumb` (−98 % octets NAS,
  vérifié) ; `_send_file` Range/streaming (206 vérifié) ; workers sous
  ordonnanceur ; GpuArbiter 27/27.
- **Tagging** : `qwen3-vl:2b`, prompt v2ctx (assertions en contexte, sans
  impératif — éval 12/08) ; Knowledge Builder : faits noms/date/lieu structurés
  et sourcés (`faits`), noms JAMAIS via le prompt (fusion `_noms_attendus`,
  exclude = autorité) ; `TAGGING_PIPELINE_VERSION` estampillée (`pipe`) ;
  1 lecture exiftool/photo (élargie à la date de prise de vue).
- **Observabilité** : boucle scan/backup (O5), `backup_verify`, et les trois
  tâches de fond EXIF (dates, noms, GPS) — état, avancement et « fichiers
  muets » dans `/reglages`. Leçon : *un travail de fond qui ne rend pas de
  comptes finit par ne plus travailler du tout*, et personne ne le voit.
- **Hygiène** : nettoyage de session réversible (bat 29) ; commit guidé
  `SESSION_COMMIT.txt` (bat 27) ; fusion fast-forward sans checkout, serveur
  allumé (bat 28) ; **suppression des branches déjà fusionnées (bat 30)** —
  `git branch -d` refuse tout ce qui n'est pas dans `main`, donc sans risque.

## Réserve — futur, non prioritaire (triée le 12/08)

- **Multi-utilisateur** — reste en réserve, mais avec un **déclencheur nommé** :
  la première marche utile est un « mode Flo » minimal (file de nommage des
  visages qu'elle seule sait nommer, rien d'autre), à ouvrir quand l'outil est
  à ~90 % (cadrage du point 1). C'est le multi-utilisateur qui débloque la
  vérité terrain, pas l'inverse.
- **Vidéo → audio** — inchangé : coût élevé, valeur incertaine, aucun
  déclencheur en vue.
- **Bibliothèque Figma** — inchangé : le design system « chambre noire » vit
  déjà dans le code ; une bibliothèque miroir serait de la doc à double
  entretien sans consommateur.
- Récits LLM auto : écartés (hallucination).

**Vision** : mémoire familiale à provenance — deux tests : « PC mort lundi,
tout revit vendredi » (**promu** : chantier 12) et « aucun fait affirmé sans
provenance » (en cours : `faits` sourcés livrés, composition d'affichage au
point 3, MCP lecture au point 13).

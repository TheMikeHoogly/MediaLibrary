# Feuille de route — MediaLibrary

Carte des **priorités**, rien d'autre. Les récits de travaux terminés vivent
dans **git** ; les rejets dans `eval/DECISIONS.md` (photothèque),
`eval/DECISIONS_UI.md` (écran), `eval/DECISIONS_TAGGING.md` (ce que le modèle
écrit) et `docs/DECISIONS_OUTILLAGE.md` (canaux, pilotage, livraison) ; la
méthode dans `eval/METHODE.md` ; le chantier performance dans
`PERFORMANCE.md` ; l'éphémère dans `PROMPT_NOUVELLE_SESSION.md`.

> **Ce fichier se relit en entier en début de session.** Un jalon qui porte
> « FAIT » dans son titre n'est plus une priorité : il sort d'ici et reste
> dans git. Un carnet dont les trois quarts sont finis n'ordonne plus rien —
> il l'a été deux fois, le 05/09 et le 09/09.

> **`N:\\Photos` se connecte à chaque session** — règle dans `CLAUDE.md`
> (« Tester en réel »), depuis le 29/08.

---

## Ce qui commande tout : la campagne de retag

Lancée le 05/09, modèle `qwen3.5:4b`, cible `qwen3.5:4b|v3fr|kb1`.
**Relevé le 12/09 à 12h15** (`/api/maint/status` → `config.retag`, la seule
source juste — `counts.tagues` compte les photos taguées un jour, pas celles
de CETTE passe) : **3 537 restantes**, 936 en file, **1 abandon**. 119 photos
en 35 min → **~17,6 s/photo**, donc fin **au petit matin du 13/09**. Index :
44 605 entrées, 354 personnes, 17 animaux, 40 583 visages.

Tant qu'elle tourne : **le prompt est intouchable** (le prompt EST la version
du pipeline — une phrase ajoutée rendrait candidates les 12 000 photos déjà
refaites), le GPU est pris, et on ne fait que ce qui n'a besoin ni du GPU, ni
du prompt, ni du serveur arrêté. **Quand elle s'arrête, la section C s'ouvre
— et elle s'ouvre bientôt.**

---

## A. Ce qui appartient à Mike

**A1. Trier les 248 dépôts d'`Uploads`.** La lampe de l'entête y mène
(`/tri`), le tableau se trie et se filtre, la sélection multiple et les gestes
groupés fonctionnent. Le plus ancien attend depuis 30 jours. **Rien ne bouge
sans lui** : c'est le principe du chantier.

**A2. La dernière photo sensible.** Le chantier 18 est clos pour l'essentiel
(213 triées le 09/09) ; il en reste **une**. L'onglet n'apparaît que s'il y a
quelque chose à juger.

**A3. Lire la page `/aide`.** Posée et vérifiée. Ce qui reste n'est pas une
tâche mais un jugement : c'est sa famille qui lira ce texte.

**A4. Le ménage — deux restes.** Au prochain lancement du bat 50 :
**47 fichiers / 34,8 Mo** (34 journaux d'annulation de plus de 30 jours, 7
rapports périmés, 6 reliquats de quarantaine). Puis **une décision** sur les
**283 Mo** de `_to_delete\menage_20260908\_avant_deplacement\photos.db` — une
copie de la base, que le veto retient parce que l'instrument ne sait pas la
distinguer de la base vivante. Enfin, vider `_corbeille_menage\` à la main
après quelques jours. **Et trois `_test_claude_tri.jpg` de 160 octets** dans
la corbeille : mes témoins du 12/09, à purger.

**A5. Windows : ne pas laisser revenir KB5124008.** Il casse Plan9, donc
`device_bash` (reconnu par Microsoft et Anthropic ; correctif annoncé « dans
un cumulatif suivant »). La machine tourne en **UBR 9278**, Windows Update est
**en pause jusqu'au 17.10**. **Vers le 16.10** : masquer le KB s'il est
reproposé (le bloc PowerShell est dans l'historique de la session du 12/09).
`Get-HotFix` MENT sur ce sujet ; la vérité est
`(Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion').UBR`.

---

## B. Ce qui avance pendant la campagne

**B1. La performance — le plan vit dans `PERFORMANCE.md` § 5, pas ici.**
État au 12/09 à 13 h 30 : la page `/files` d'un dossier de 2 519 photos est
passée de **1 493–1 870 ms à ~690–800 ms**, et la même page filtrée par un tag
de **1 200 à 750 ms**. `index` (§ 3.17), `marques` (§ 3.18), le lieu (§ 3.19)
et les DEUX lecteurs de date réduits à un (§ 3.20) sont faits — le thème
« date » passe de 118 à **85 ms**. **Plus de gros caillou** : `enrichir`
reste premier à 280 ms, mais aucun de ses morceaux ne dépasse 60 ms. Ce qui
suit, par ordre : le dernier partage de lecture du `taken` (sans prémisse à
vérifier désormais), `motifs` (63 ms) et le `Path(...)` de `_resolve_key`
(41 ms). La machine tague pendant les mesures : ce sont les sous-phases qui
font foi, pas le total. Compatible avec la campagne : chemin
de service seulement, jamais le calcul IA.

**B2. Le tri des dépôts, à éprouver.** Le premier tour est livré (A1). Ce qui
reste dépend de l'usage : le **mur de 7 jours** est-il le bon ? faut-il un
geste groupé pour le lot hérité ? Ne rien changer avant que Mike s'en soit
servi une fois.

**B3. L'ordre inverse maintenance / scan — À MOITIÉ FERMÉ.** Depuis le 07/09
la maintenance se reporte aussi quand un balayage NAS tourne
(`SCAN_NAS_EN_COURS`) : c'était la cause directe des 85 minutes de GPU à zéro
du 06/09. **Reste l'ordre inverse** : une étape lourde déjà partie, puis le
scan qui arrive dessus. Non mesuré, non corrigé.

**B4. Le reste d'audit : O8 et O9.** Matmul par visage et backfill sémantique
— les deux touchent des boucles de CALCUL, donc **après** la campagne.
**O15 est outillé** : les trois caches de vignettes pèsent 722 Mo dont
**541 Mo d'orphelins**, et `51 - Purger les vignettes orphelines.bat` attend
un geste de Mike ; la réversibilité y est la RÉGÉNÉRATION, pas une corbeille.

**B5. Les dettes nommées, petites et sûres** : `git rm --cached _collage6.py
_collage7.py` (ignorés mais suivis) ; le libellé du bat 32.

---

## C. Quand la campagne s'arrête — c'est imminent

**C0. Les vignettes de grille.** `/api/serveur` → `vignettes` dit
« attend la fin du tagging » ; il passera à `fabrique`. Relancer alors
`mesure_couverture_vignettes.py` : 98 % du fonds n'avait pas de vignette de
grille au 11/09, le tagueur en pose une au passage depuis, et le fil de fond
prend le reste.

**C1. La mémoire de la machine, et donc le modèle de vision.** Tranché le
12/09 : pendant la campagne on vit avec les **13,5 Go privés dont 7,8
résidents** du moteur d'Ollama, qui laissent 0,5 Go de RAM libre et font
paginer le serveur (`PERFORMANCE.md` § 3.10). La piste CUDA est écartée par la
mesure. GPU libéré, la question redevient un choix de MODÈLE : celui qui tient
entièrement dans les 4 Go de VRAM ne garde pas 7,8 Go en RAM — protocole
`vision-eval`, et changer de modèle est un changement de pipeline.

**C2. La question au tagueur sur les documents sensibles.** Pas reportée par
prudence : **empêchée** tant que la campagne tourne — la toucher rouvrirait
12 000 photos déjà refaites.

**C3. Re-mesurer les Motion Photos arrivées depuis le 03/09** — demande le
serveur arrêté.

**C4. Le bilan de la campagne** : ce que `qwen3.5:4b|v3fr|kb1` a changé,
mesuré et pas supposé. C'est la première passe officielle du fonds, elle
mérite son compte rendu — et elle a **1 abandon** à expliquer.

---

## D. Fin de projet

**D1. La copie hors site — repoussée en fin de roadmap par Mike le 09/09.**
Le choix est le sien. Ce qui reste vrai sans être répété à chaque session :
après l'effacement de l'extrait Takeout, le NAS est le **seul exemplaire** des
~40 000 photos, et un NAS chez soi ne protège ni du feu, ni du vol, ni d'une
fausse manœuvre. Le jour où le sujet se rouvre, deux choses vont *ensemble* :
choisir le fournisseur, et écrire le banc qui prouve que la copie distante
contient ce que le NAS contient — une sauvegarde qu'on ne vérifie jamais n'est
pas une sauvegarde.

**D2. Les 633 photos sans copie connue.** `docs/photos_perdues.md` est leur
seule trace et vit dans git. Rien à faire de plus tant qu'un vieux disque ne
réapparaît pas.

---

## Pistes ouvertes par Mike (22/08) — à instruire, pas encore priorisées

**Tirer plus d'intelligence du LLM local À MATÉRIEL CONSTANT.** Le plafond de
4 Go de VRAM ne bouge pas, et « modèle plus gros » est PARQUÉ pour cette
raison (16/08). Axes, du moins cher au plus cher : sortie **contrainte**
(grammaire / JSON forcé, qui supprime une classe entière d'erreurs de format
sans coûter un octet de VRAM) ; **auto-cohérence** (plusieurs tirages, on
garde ce qui se répète) ; décodage spéculatif ; quantifications récentes ;
petits modèles parus depuis ; et le **temps de calcul au moment de la
réponse** plutôt que la taille.
**Habitude demandée** : se renseigner à l'ouverture de toute session qui
touche au tagging, à la description ou à la recherche — ce domaine bouge vite,
une doc de six mois est périmée.
**Condition non négociable** : rien ne se câble sans banc **en aveugle** sur
un ET — apport réel **et** hallucination (`eval/METHODE.md`). Le prompt de
production double déjà les hallucinations, adopté sur un 25-15.
**Reste ouvert (05/09)** : `qwen3.5:4b` a été retenu sur une comparaison qui a
mesuré l'apport réel mais **pas en aveugle** et sur un tirage CIBLÉ de
8 photos difficiles, pas un A/B comme celui qui a adopté v2ctx. À reprendre
avec la rigueur complète, ou à accepter tel quel — choix de Mike.

**Ouvrir la médiathèque à TOUTE LA FAMILLE, avec la vie privée au centre.**
Aujourd'hui l'outil est pour Mike et Flo (deux comptes, et ce sont les deux
seuls habitants). La cible : chacun a son **dossier perso**, y dépose ses
photos, et **contrôle qui voit quoi** — partages explicites, révocables, avec
le compte rendu de ce qui est partagé.
**Ce que ça change de nature** : le projet passe d'un outil mono-poste à un
service multi-utilisateur, et la vie privée cesse d'être un réglage pour
devenir la contrainte qui gouverne le modèle de données. Trois questions à
trancher AVANT toute ligne de code — (a) l'unité de propriété : la photo, le
dossier, ou la personne reconnue dessus ? une photo de Flo prise par Mike
appartient à qui ? (b) ce que la RECHERCHE laisse fuir : un compte de
résultats, un nom qui complète, une vignette suffisent à révéler ce qu'on
croyait caché ; (c) les **visages** : nommer quelqu'un dans la photo d'un
autre, c'est écrire sur son bien — et les noms partent dans les XMP des
fichiers (règle 2), donc hors de portée de tout réglage.
**Absorbe l'item « mode Flo »** de la Réserve.

---

## Acquis — ne pas reproposer (détail : git + `eval/DECISIONS.md`)

- **Le chip est FINI (26/08)** : `.chip` vit dans `components.css` seul,
  `font:` compris. `.pchip` n'existe plus. Ce qui reste local doit DIFFÉRER et
  se dire (`subjects` : `padding` ; `gallery` : `user-select` et l'état `.on`).
- **Cibles tactiles (26/08)** : les **221** cibles des onze pages sont
  comptées — **0 manquement prouvé**. `verifier_cibles.py` lit l'imbrication
  du HTML, ce que `createElement` bâtit et la cascade à quatre étages. Ne pas
  re-parcourir à l'œil, et ne pas proposer de lire la LARGEUR : angle mort
  assumé, dit dans le rapport.
- **Accessibilité des contrôles (26/08)** : les **154** gestionnaires de clic
  sont posés sur des contrôles — 138 natifs, 3 opérables à la main, 13
  déclarés redondants, **0 grief de niveau A** (`verifier_controles.py`).
- **`[hidden]` gagne contre `display:` depuis le 12/09** (`ui/base.css`, sans
  `!important`). Ne pas reposer une rustine locale par page.
- **UNE seule règle lit la date dans un nom de fichier** (12/09) :
  `server._fname_time` délègue à `faits_vue.epoch_du_nom`, mémoïsée. Les deux
  lecteurs étaient déclarés miroirs et ne l'étaient pas tout à fait — une
  heure impossible basculait au jour SUIVANT d'un côté.
  `mesure_miroir_dates.py` : **0 désaccord sur 44 966 fichiers**, mais le cas
  limite existe, et c'est la règle STRICTE qui a été retenue.
- **`git_agent.tests_pour` lance aussi les bancs qui CITENT un module touché**
  (12/09) : l'appariement par NOM seul laissait **63 bancs** invisibles, dont
  59 citent `server.py` — **cinq étaient ROUGES**, tous accrochés à une
  ORTHOGRAPHE du source qu'une correction avait changée ; réécrits sur
  l'arbre. Large par construction : c'est un filet, pas un filtre. Son seul
  trou est NOMMÉ (`BANCS_A_LA_MAIN`) : `test_tagging.py` tague pour de vrai et
  veut le serveur arrêté.
- **Stockage** : SQLite local WAL (**44 605 entrées**), embeddings BLOB,
  backup NAS snapshot + `backup_verify`.
- **Reconnaissance** : SigLIP 2 (90 % r1) ; animaux 97,4 % r1 ; prototypes
  multiples ; vérif d'espèce.
- **Nommage** : attribution unifiée personnes+animaux (multi-noms, annulation
  10 s), rejets réversibles, reclassement `personne:`→`animal:` réversible.
- **Fichiers / rangement** : `/browse` réversible, dédoublonnage (8,4 Go),
  rangement par année, orchestrateur de maintenance.
- **Renommage** : cœur + plan + applicateur réversibles ; **7 058 renommages
  appliqués et observés** (0 sauté, noms humains intacts) ; garde-fou date de
  SCAN (asymétrique, toléré à un an).
- **Un nom de fichier se trompe à ~7 %** (06/09, 40 canoniques vérifiées au
  sha256, 3 étaient une AUTRE photo). Toute purge ou tout rapprochement qui
  s'appuie sur le NOM seul détruirait des originaux à cette échelle.
- **UI** : design system « chambre noire » (tokens, plancher a11y), planche
  contact, `/reglages`, `/people`, `/sujets` guichet unique ; faits
  `date · lieu · noms` sous chaque vignette et dans la visionneuse, avec leur
  SOURCE, produits par la VUE et par un seul rendu partagé.
- **Vignettes côté client** : `window.Vignettes` (`ui/global.js`) —
  IntersectionObserver à 400 px **et** file unique plafonnée à 4 requêtes en
  vol. `loading="lazy"` natif **ne borne rien** : il pose N requêtes d'un coup
  et un navigateur n'ouvre que six connexions par hôte (mesuré au navigateur
  le 06/09 : 585 tuiles demandées d'un coup bloquaient un AUTRE onglet).
- **Correction** : faux positifs « Corriger »/« Nettoyer », retrait SÛR
  (`untag`→`exclude`), `exclude` autorité partout + auto-guérison.
- **Perf acquise** : scoring vectorisé (156 s → qq s) ; `/api/thumb` (−98 %
  d'octets NAS) ; `_send_file` Range/streaming ; workers sous ordonnanceur ;
  GpuArbiter 27/27 ; compression HTTP (O11) ; `flush()` au lieu de `save()`
  (O14, 627 ms sous verrou → 0,1) ; HTTP/1.1 et `Last-Modified` (12/09) ;
  ramasse-miettes gelé et espacé (×3,8).
- **Tagging** : `qwen3.5:4b`, prompt v3fr ; Knowledge Builder : faits
  noms/date/lieu structurés et sourcés (`faits`), noms JAMAIS via le prompt ;
  `TAGGING_PIPELINE_VERSION` estampillée (`pipe`) ; 1 lecture exiftool/photo ;
  **`exiftool -P` depuis le 12/09** — le tagueur ne détruit plus la date des
  fichiers.
- **Index / vecteurs** : cascade `forget_everywhere` au scan — pilotée par
  l'index, donc aveugle à une clé déjà oubliée (21/08) ; re-clé complet
  (22/08) : `rekey_everywhere` transporte les DÉCISIONS humaines des fiches
  `PEOPLE`/`PETS` ; **2 374 vecteurs orphelins purgés et observés**,
  quarantaine réversible.
- **Observabilité** : boucle scan/backup (O5), `backup_verify`, trois tâches
  de fond EXIF dans `/reglages` ; comptes de l'index au goulot ; horloge des
  routes et des PHASES (`_perf_routes.json`, `/api/perf`).
- **Recherche** : quatre dimensions (noms · lieux · période · sens) ; **une
  seule règle de date**, **une seule règle de LIEU** (`faits_vue`) et **une
  seule autorité des NOMS** (`_autorite_des_noms`), partagées par le
  renommage, le KB, `/sujets` et la recherche.
- **Mesure** : les bancs `mesure_*` lisent une COPIE, jamais `photos.db` ;
  `mesure_copie_base.py` fabrique cette copie (API `backup`, source en
  `mode=ro`) — plus un geste de Mike avant de mesurer.
- **Pilotage** : trois canaux-fichiers, une seule façon de les lire
  (`canal.py`) — `_commande_serveur.txt`, `_commande_git.txt`,
  `_commande_banc.txt`. Les superviseurs se retirent quand la **génération**
  change. `GET /api/serveur` dit `demarre_a` et `code_a_jour`.
- **Hygiène et livraison** : nettoyage réversible (bat 29) ; `27 - Git.bat`
  reste le guichet des gestes de Mike ; `git_agent.py` livre pour la sandbox
  **après contrôles** (serveur à jour, tests des modules touchés, `.bat` ASCII
  pur, lint). L'ordre ne s'inverse pas : **observer AVANT de commiter**.

---

## Réserve — futur, non prioritaire

- **Vidéo → audio** : coût élevé, valeur incertaine, aucun déclencheur.
- **Bibliothèque Figma** : le design system vit dans le code ; un miroir
  serait de la doc à double entretien.
- **Récits LLM auto** : écartés (hallucination).

**Vision** : une mémoire familiale à provenance. Deux tests — « PC mort lundi,
tout revit vendredi » et « aucun fait affirmé sans provenance ».

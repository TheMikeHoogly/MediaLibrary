# Feuille de route — MediaLibrary

Carte des **priorités**, rien d'autre. Les récits de travaux terminés vivent
dans **git** ; les rejets dans `eval/DECISIONS.md` (photothèque) et
`docs/DECISIONS_OUTILLAGE.md` (canaux, pilotage, livraison) ; la méthode dans
`eval/METHODE.md` ; l'éphémère dans `PROMPT_NOUVELLE_SESSION.md`. Audits :
`docs/AUDIT_INTERNE_2026-08.md`, `docs/AUDIT_EXTERNE_2026.md`, `docs/RANGEMENT_2026.md`.

## État (22/08/2026, session 31)

**Le trou n'était pas la purge : c'est le RANGEMENT qui décrochait les décisions
humaines, et il le faisait en silence.** `rekey_everywhere` transporte sept
magasins quand une photo change de chemin, et quatre « stores de sujets »
passent dans la même boucle. Mais `PEOPLE` et `PETS` sont les seuls keyés par
**NOM** : leurs chemins vivent DANS la fiche — `faces` = [[chemin, index]],
`exclude`, `confirmed`, `avatar`. `store.rekey(ancien_chemin, nouveau_chemin)`
y cherche une entrée dont la CLÉ serait un chemin, n'en trouve jamais, renvoie
faux **et ne dit rien**. La boucle avait l'air de couvrir quatre magasins ; elle
en couvrait deux. Chaque rangement par année et chacun des **7 058** renommages
a donc pu décrocher un jugement.

**Ce que ça coûtait, mesuré** : sur **3 364** décisions humaines, **928**
pointent vers une clé absente de l'index (596 rattachements, 249 exclusions, 83
confirmations), sur **804** clés. Le TAG survivait — il vit dans `tags` et dans
le XMP — donc la photo gardait son nom et la règle 2 tenait ; c'est la VÉRITÉ
TERRAIN qui partait, et une exclusion perdue est un faux positif qui revient.

**« 787 décisions déjà perdues » est FAUX**, et c'était un défaut de recherche,
pas une mesure : personne ne leur avait cherché de jumeau. Les **journaux
d'annulation** de `docs/` — écrits pour défaire, relus à l'endroit — donnent
**19 331** déplacements et retrouvent **698** des 804 clés. Les trois preuves
comparées : journal **685**, nom de fichier **346** (36 homonymes refusés),
vecteur **13** (la purge du 21/08 a emporté les détections des clés mortes).
Résultat : **748 décisions se re-clent**, 56 y sont déjà, **124** sont vraiment
perdues. Le « une seule décision à reporter (Luna) » tombe avec.

**LIVRÉ.** (1) Préventif — `recle_decisions.py`, règle pure, 15 tests, branchée
dans `rekey_everywhere` : une photo qui bouge emmène désormais ses jugements,
index de vignette compris. (2) `journaux_deplacements.py`, une seule lecture
des journaux, partagée par le serveur et le banc. (3) Rétroactif — trois
boutons dans `/reglages` (aperçu / appliquer / annuler), quarantaine
`_corbeille_decisions/`, qui passent par **la même fonction** que le préventif.
(4) Instruments : `mesure_report_orphelines.py` et
`verifier_recle_decisions.py`. Aperçu à blanc **sur le serveur vivant** :
804 clés mortes, **685 à re-clé**, 119 sans destination, **0 hors bornes** —
les mêmes nombres que le banc, deux chemins.

**RESTE À FAIRE, et c'est un clic de Mike** : `/reglages` → « Décisions humaines
restées sur l'ancien chemin » → **2 · Appliquer**. La sandbox n'a pas le droit
d'écrire sur le fonds ; l'aperçu et l'annulation sont là pour encadrer le geste.

## État (21/08/2026, session 30)

**La purge du 17/08 n'avait traité qu'un magasin sur deux**, et la cascade de
suppression était pilotée par l'INDEX : une clé déjà absente de l'index est
invisible à `_sync_dir`, donc `forget_everywhere` n'est jamais appelé pour elle.
**Corrigé et observé** : `purge_detections_hors_index()` balaie au démarrage ce
que la cascade ne voit plus, sans jamais toucher une clé jugée par un humain —
`visages` **44 450 → 42 196**, hors index **2 374 → 120** (les protégées), index
intact à 43 065, quarantaine réversible `_corbeille_detections/`.

**Le chantier 16(a) est CLOS par la mesure** : la propagation des noms ne dort
pas, elle a convergé — **14 rattachements automatiques, 24 cartes en file, 33
photos**, et **17** photos dans le cas exact du chantier sur 18 745 qui y
ressemblent. Trois nombres du banc contre trois du serveur vivant, identiques.

## État (20/08/2026, session 28)

**Ce qu'on cherche est ce qu'on voit — 14a-(iv) CLOS et OBSERVÉ.** Le filtre
des noms lisait les `kw` bruts de l'index pendant que la ligne de faits lisait
les fiches : **13 photos** sortaient d'une recherche par un nom qu'`exclude`
avait retiré, **0** dans l'autre sens (363 tags balayés sur copie).
`_autorite_des_noms()` est l'unique implémentation, partagée par l'affichage et
le filtre. Observé : Silvio **495 → 494**, Danica **325 → 324**, clés exclues
absentes. La fiche fait foi sur l'orthographe (« Luna · luna » a disparu).

**Portée du filtre : 92,74 %** — nom ou lieu atteint **27 936** des **30 122**
photos à fait NON-date. Les **2 186** autres n'ont qu'une ESPÈCE.

**Le 5ᵉ axe est LIVRÉ (21/08).** `espece:chat` filtre sur la concordance des
deux regards ; observé en réel : 2 386 photos concordantes, 0 en trop face à la
règle, `espece:licorne` rend zéro et le DIT. Le vrai gain est la précision, pas
le rappel — voir `eval/DECISIONS.md`. La sandbox fabrique désormais sa propre
copie de la base (`mesure_copie_base.py`) : plus un aller-retour clavier avant
de mesurer.

**L'espèce est mesurée, et elle a réfuté deux fois.** SigLIP ne rend dans son
top-1500 que la moitié des détections de YOLO (chat 50,1 %, chien 50,3 %,
oiseau 48,3 %, cheval 72,6 %) — elles ont pourtant TOUTES un vecteur : mal
classées, pas muettes. Mais `det_score` **ne dit pas l'espèce** : `cheval`
0,934 sur *chien, homme, barrière*. Ce qui tient, c'est la **CONCORDANCE** de
deux regards indépendants — YOLO et le tagueur : chat **2 316** (92,6 %
d'accord), **3 065** en tout. C'est la matière du 5ᵉ axe, forme A (choix de
Mike) : un jeton `espece:` explicite, jamais une promotion silencieuse.

**Un TROISIÈME canal : la sandbox peut MESURER.** Elle n'atteint pas le LAN
(`blocked-by-allowlist`), donc un banc qui interroge le serveur ne pouvait pas
tourner chez elle — le 20/08, il a fallu le clavier de Mike, et sa sortie a
réfuté une conclusion tirée de deux échantillons. `banc_agent.py` (fenêtre
« MediaLibrary - Bancs ») lit `_commande_banc.txt`, ne lance QUE les familles
qui MESURENT, sans shell ni chemin ni `force=`, et écrit `_banc_sortie.txt`.
Les trois canaux partagent enfin `canal.py` — une seule façon de lire un ordre.

**La livraison git est une PORTE — et elle POUSSE.** `commit` = branche + push,
`main` intacte ; `livrer` ajoute le fast-forward. L'ordre s'inverse : éditer →
redémarrer → **observer** → livrer. `_etat_git.json` dit ce qu'il a TENTÉ,
`.git/logs/*` ce qui s'est PASSÉ. Le bat 0 retire les anciens superviseurs par
une **génération** : le `taskkill` par titre ne tuait rien.

## À faire — par ordre de valeur

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
   blanc tourne sur le serveur vivant (685 clés, 0 hors bornes). Reste **un clic
   de Mike** : `/reglages` → « Décisions humaines restées sur l'ancien chemin »
   → 2 · Appliquer. La vérité terrain réelle est de **3 364** décisions (1 576
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
4. **Gestes Mike** : `gps_place` ✔ ; renommage appliqué ✔ (7 058) ; nettoyer
   Flo (5 909 photos) ; re-rejeter Caline.
5. **Correctifs d'audit** : I4–I8, O7–O9, O11–O15. O1 clos ; O15 (purge de
   `photo_thumbs/`) gagne en poids.
6. **Navigation par similarité et par date** : « Semblables » et « même jour »
   livrés et observés. Reste : doublons proches bridés (>0,98 + même journée →
   quarantaine réversible, 50 paires jugées avant geste).
7. **Extraction `ui/`** : décision à prendre — session dédiée `bundle.py` ou
   parcage explicite (item zombie ; préparatoire fait).
8. **Cross-pipeline (Mutz/Caline)** : outil livré, réversible. Fix auto REJETÉ
   (18 % faux rejets). Relancer si un nom d'animal sort en `personne:`.
9. **Reconnaissance — algo. PARQUÉ (21/08, choix de Mike).** HDBSCAN /
   Chinese Whispers / AdaFace restent inévaluables — 3 364 décisions humaines
   sur 71 868 visages. Ce n'est pas une dette : le produit n'en dépend pas, et
   la couverture des noms au niveau PHOTO est déjà là (point 1). À rouvrir si
   quelqu'un veut nommer des visages en série, pas avant.
10. **Données / finitions**, dans cet ordre :
    (a) **Compter ce que le scan OUBLIE — CLOS (18/08).** Trois constats mineurs
    non traités : un ajout vu PAR LE SCAN est étiqueté `tagging` ; `dict.__ior__`
    non redéfini dans `TrackedDict` ; `cycles_vus` affiche « 10 » à vie.
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
    Reste : bandeau `#pending`, libellé `/pets`, « Meme jour (14 aout) » là où
    la page dit « 14 août ».
12. **Assurance-vie : restauration à blanc (PROMU 12/08).** « PC mort lundi,
    tout revit vendredi » : restaurer le snapshot NAS sur un dossier vierge,
    chronométrer, noter chaque manque (dont la copie hors-site de
    `journal_jugements.jsonl`). Tant qu'il n'a pas tourné, c'est une promesse.
13. **Serveur exposé en MCP, lecture seule d'abord (PROMU 12/08).** Recherche,
    fiches et `faits` en outils MCP locaux (JSON-RPC stdio, zéro dépendance —
    skill `mcp-builder`). Écriture plus tard. Briques de 14a.
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
    axes) et relancent la requête côté serveur. Reste : le plafond de page
    (`espece:chat` rend 1 500 sur 2 386 — limite de `/files?q=`, pas de l'axe),
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

### Résiduels faible valeur (ne pas prioriser)
**MESURÉ le 15/08, et c'est pourquoi on n'y touche pas** : les deux planchers
1990 (`_fname_time`, `meme_jour.ANNEE_MIN`) coûtent **7** photos et **0**, et ils
sont **couplés** ; il subsiste aussi dans `plan_rangement.py`,
`recensement_doublons.py`, `diagnostic_dates.py`, sans effet tant qu'aucun
dossier d'avant 1990 n'y passe. Le **plafond 2100** (`22082010141.jpg` → 2082) :
72 en base, coût 0. Enfin `/files?dir=1&rec=1` (racine NAS) ne répond pas en
6 min, cause non cherchée.

## Acquis — ne pas reproposer (détail : git + `eval/DECISIONS.md`)

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

## Réserve — futur, non prioritaire (triée le 12/08)

- **Multi-utilisateur** — « mode Flo » minimal (file de nommage des visages).
  **Son déclencheur est tombé le 21/08** : il existait pour débloquer la vérité
  terrain, or celle-ci ne bloque que le chantier 9, désormais parqué. À rouvrir
  pour ce qu'il vaut par lui-même — nommer à plusieurs — pas comme préalable.
- **Vidéo → audio** : coût élevé, valeur incertaine, aucun déclencheur.
- **Bibliothèque Figma** : le design system vit dans le code ; un miroir serait
  de la doc à double entretien.
- Récits LLM auto : écartés (hallucination).

**Vision** : mémoire familiale à provenance — deux tests : « PC mort lundi,
tout revit vendredi » (**promu** : chantier 12) et « aucun fait affirmé sans
provenance » (en cours : `faits` sourcés livrés, composition d'affichage au
point 3, MCP lecture au point 13).

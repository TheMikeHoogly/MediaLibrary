# Feuille de route — MediaLibrary

Carte des **priorités**, rien d'autre. Les récits de travaux terminés vivent
dans **git** ; les rejets dans `eval/DECISIONS.md` (photothèque) et
`docs/DECISIONS_OUTILLAGE.md` (canaux, pilotage, livraison) ; la méthode dans
`eval/METHODE.md` ; l'éphémère dans `PROMPT_NOUVELLE_SESSION.md`. Audits :
`docs/AUDIT_INTERNE_2026-08.md`, `docs/AUDIT_EXTERNE_2026.md`, `docs/RANGEMENT_2026.md`.

## État (23/08/2026, session 39)

**La fusion Flo → Florine a été lancée pour de vrai, et elle s'est battue une
heure contre le curateur du projet.** `SubjectStore.rename` balaye les 5 907
photos une par une (un `stat` NAS chacune, ~1 h) et ne supprimait la fiche
absorbée qu'**à la fin** : pendant tout ce temps la signature de Flo restait
vivante, et `AUTO_ADD` la ré-attribuait toutes les 240 s aux photos que la
fusion venait de lui retirer. Mesuré sur le fonds vivant : `Flo` descend de
**5 907 à 4 487**, puis **REMONTE à 5 703** ; **60 auto-ajouts « Flo » en une
heure** dans `/api/curator/list` ; **17 092 écritures XMP en attente** pour un
geste qui en demande 11 814, et une file qui se vidait à **0,09 op/s** — plus
de **50 heures** de NAS pour graver le résultat d'une bagarre. Redémarrage : la
file fausse est jetée, l'index garde 5 725 `Flo` et ≥ 2 000 `Florine`.

**Mais ce n'est pas la bagarre qui l'a tuée — c'est un VERROU dans la fiche.**
La console du serveur, seule à l'avoir su :
`TypeError: cannot pickle '_thread.RLock' object`, dans le
`copy.deepcopy(self.store.data.get(old))` de `rename`. La fiche `Flo` porte, en
mémoire, un objet vivant. Et cette ligne venait **APRÈS** la boucle : les 5 907
photos étaient renommées, puis la fusion mourait — ni fiche `Florine`, ni
journal, rien à annuler, et pas un mot à l'écran. **Le nouvel ordre a déplacé
ce mur de la 60ᵉ minute à la 1ʳᵉ milliseconde** : c'est ce qui l'a rendu
visible. Le journal prend désormais une copie **JSON-sûre** de la fiche —
`_journal_fusion` sérialise, donc ce champ aurait tué le journal juste après le
deepcopy — et **NOMME dans la console** ce qu'il écarte. **Reste à savoir qui
met un verrou dans une fiche de personne** : la ligne le dira au prochain
renommage.

**Corrigé — l'ORDRE du geste.** Les fiches sont fusionnées **AVANT** la boucle
sur les photos : plus de fiche, plus de signature, plus de course. Elle
disparaît par construction au lieu d'être arbitrée. Deux propriétés viennent
avec : le journal s'écrit dans un `finally` — une boucle interrompue reste
annulable, et **relancer REPREND** le travail — et les photos qui portent déjà
le nom d'arrivée voient quand même leur **fichier** réécrit, ce qui empêche un
nom fantôme de renaître au prochain balayage des modifiés. **`delete()` avait
exactement la même forme** : corrigé aussi. **45 tests**, dont **5 rouges sur
l'ancien code**, et un qui fabrique la fiche à verrou.

**`verifier_fusion.py` (22 tests) : le geste le plus lourd a enfin un juge.**
Il lit `_corbeille_fusions/` et le serveur vivant et répond par l'arithmétique
— l'union des décisions des deux fiches se retrouve-t-elle après (règle 2),
quel journal peut VRAIMENT annuler (dès qu'il y a eu plusieurs passes, le
dernier ment), l'ancien nom a-t-il disparu, que reste-t-il en file. Sans
serveur joignable il juge les journaux et DIT ce qu'il n'a pas vérifié.

**LA FUSION EST FAITE (23/08, 08:31), et elle est vérifiée.** Mike a cliqué,
la fiche `Florine` a paru **dans la seconde** et `Flo` a disparu du même coup.
La boucle qui mettait une heure hier a mis **deux minutes** — les 5 725 photos
à ~55/s : la lenteur d'hier était la BAGARRE, pas le coût du `stat`. Journal
`fusion_20260823_083124.jsonl`, et `verifier_fusion.py` lancé au banc rend :
**règle 2 tenue — confirmations 143 → 143, exclusions 1 215 → 1 215, visages
84 → 84, avatar présent, date la plus ancienne** ; un seul journal, annulable ;
côté serveur **un seul nom, `Florine`, 5 909 photos**, plus aucun `Flo`. La
file XMP (11 800 opérations) se vide à **0,95 op/s — ~3,4 h**, contre 0,09 op/s
hier : là encore, c'était la bagarre.

**Une nuance à connaître avant de cliquer « Annuler la derniere fusion »** :
**5 724 des 5 725 photos portaient DÉJÀ `Florine`** — séquelle de la passe
morte d'hier, qui avait fait tout le travail d'index avant de tomber. Annuler
leur rendrait donc `Flo` **sans** leur retirer `Florine` : c'est fidèle à
l'état d'avant la fusion d'aujourd'hui, pas à celui d'avant-hier. L'annulation
ne remonte pas plus loin que le dernier geste.

## État (22/08/2026, session 38)

**Mike a tranché : Flo et Florine sont la même personne** (5 907 photos portent
Flo, 153 Florine, 149 les deux). En préparant la fusion, `SubjectStore.rename`
s'est révélée perdre des décisions humaines : elle transportait `refs`,
`exclude` et `faces` mais **pas `confirmed`, `avatar`, `nomerge`** — les **143**
« oui, c'est bien elle » de la fiche Flo, et autant à **chaque fusion du
curateur** depuis que la fonction existe. Règle 2, corrigé. Et la fusion est
devenue **réversible** : `_corbeille_fusions/` note les deux fiches et, photo
par photo, si elle portait **déjà** le nom d'arrivée — sans quoi annuler
volerait Florine aux 149. Bouton `Annuler la derniere fusion` dans `/reglages`.

**Trouvé en chemin — les deux portes du projet ne jugeaient pas la même
chose.** Deux livraisons refusées d'affilée sur « FAILED (errors=11) », sans
que le message nomme sa cause : le banc lance les tests avec `PYTHONUTF8=1`,
l'agent git SANS. Sur une console cp1252, le « ↻ » de la ligne de journal levait
une `UnicodeEncodeError` qui faisait tomber 11 tests. La ligne est passée en
ASCII pur (deux tests la tiennent) — mais **la divergence d'environnement entre
`banc_agent.py` et `git_agent.py` reste ouverte** : un test vert d'un côté et
rouge de l'autre n'enseigne rien.

## État (22/08/2026, session 37)

**Les 21 couples d'animaux « à trancher » ne demandent AUCUN geste sur le
fonds — et c'est l'instrument qui avait tort.** `--a-juger` (17 tests neufs)
cherche la contrepartie de chaque couple ; ce qu'il a trouvé retourne les deux
tas.

**Les 6 « espèce incohérente » sont JUSTES, 6 sur 6. H4 est réfutée.** Le banc
tenait l'espèce pour son verdict le plus solide — « faux sans qu'aucun seuil
ait à le dire ». Le score de la détection DÉSIGNÉE, qui manquait, dit
l'inverse : **0,441 / 0,594 / 0,604 / 0,623 / 0,666** contre une médiane de
**0,603** sur les couples confirmés. Les six crops ouverts dans
`/api/animalcrop` : **six chats crème**, dont un vu deux fois sous deux
chemins. **C'est l'ÉTIQUETTE d'espèce de YOLO qui ment, pas le rattachement.**
Et l'erreur est VISIBLE : ces photos rangent Luna sous « chien » dans l'axe
espèce. Deux détails qui valent leçon : un couple à **0,441** — sous le
seuil — est juste (un seuil bas nomme une cécité, encore) ; et le seul
« recalage évident », i=0 → i=1 à **+0,036**, était deux BOÎTES du même chat —
recaler aurait été un rebrassage, exactement l'erreur que le 22/08 avait déjà
nommée côté visages.

**Les 15 clés mortes n'ont aucune contrepartie, et trois chemins le disent.**
Les journaux d'annulation (19 331 déplacements) n'en connaissent aucune ;
aucune clé VIVANTE ne porte le même nom de fichier ; et le DISQUE tranche —
`verifier_orphelins --filtre ARZOPA --table animals` rend **115 entrées, 0
présente, 115 « disparu »**, dont 12 jugées par un humain. Ces photos
n'existent plus nulle part. Suite du choix du 22/08 sur le résidu des visages :
on **garde**. Leurs détections survivent sous l'ancien chemin — un humain peut
encore les regarder, ce qu'une purge lui retirerait pour rien.

**Ce que ça ouvre** : l'étiquette d'espèce se trompe au moins **6 fois sur 351**
couples d'animaux nommés (1,7 %), en silence, et l'axe espèce en dépend. Aucun
instrument ne mesure aujourd'hui cette erreur-là sur le fonds entier.

## État (22/08/2026, session 36)

**`PETS` est mesuré pour la première fois, et le mal n'est pas où on le
cherchait.** 12 fiches, **351 couples** `[photo, animal]`, 330 mesurables.
**0 index hors bornes**, et **10 décalés dont 8 sur des photos que la fiche
cite plusieurs fois** — Mutz cité **7 fois** sur `111-1103_IMG.JPG`, qui porte
10 animaux : c'est le nommage d'un GROUPE, pas un index qui glisse. Restent
**2 vrais candidats sur 330 (0,6 %)**, contre 3,5 % côté visages avant
réparation. Le code disait pourquoi : rien ne ré-embarque une photo déjà connue
côté animaux (`animal_worker` saute `ANIMAL_STORE.has`), et
`migrate_animal_pipeline` vide TOUT puis remet `faces = []`. **Porter le
recalage aux animaux est donc rejeté** : il traiterait 2 couples.

**Le résultat qui compte porte, là encore, sur l'INSTRUMENT.** Sur 330 couples
**confirmés par des humains**, **122 (37 %) scorent sous `PET_MATCH_SIM =
0,55`** — médiane 0,603, p10 0,392, min 0,231. Le seuil coupe au MILIEU de la
distribution des rattachements justes ; la même colonne vaut **1,1 %** côté
visages. DINOv2 lit une robe, une posture, une lumière — pas une identité.
C'est ce plafond-là qui limite tout ce qu'on voudrait automatiser sur les
animaux, et il ne se règle pas sur ce chiffre seul : il faudra des jugements,
comme pour la tranche 0,35–0,40.

**Deux petits tas précis, pour un geste humain.** **15 clés mortes** (4,3 % —
Inti 7, Luna 5, Pins 2, Pticon 1), corroborées par un **second chemin** : le
croisement par le tag `animal:` en rend exactement 15, les mêmes fiches. Et
**6 couples d'espèce incohérente** — Luna, un chat, posée sur une détection
**`dog`**, sur 4 photos : faux certains, sans qu'aucun seuil ait à le dire.

**Une réserve, qui n'est pas un défaut : 651 photos portent un nom d'animal
sans aucun rattachement** (Inti 420, Mutz 111, Luna 94). Puma, Kevin et Le chat
de Bremblens ont **zéro couple** pour 7, 6 et 2 photos taguées.

**Deux corroborations gratuites.** Toutes les empreintes sont en **768** — la
protection de dimension du code n'a rien à attraper aujourd'hui. Et **4 628
détections sur 7 704** portent une empreinte : l'écart de **3 076** est
*exactement* bird 1 729 + sheep 710 + cow 637, les espèces non nommables. Aucun
trou.

**Le banc s'est trompé le premier, et c'est son ZÉRO qui l'a dit** : première
version, « 0 photo taguée » pour les **douze** fiches. Il lisait `kw` ; la prod
écrit `kw_fr`. Un compte identique sur toutes les lignes d'un tableau accuse la
COLONNE, pas les lignes.

## État (22/08/2026, session 38)

**I7 est corrigé, et la mesure dit que c'était un défaut LATENT — sauf sur
trois tags.** L'audit du 11/08 annonçait « un `personne:nom` importé n'est
jamais auto-guéri » ; personne n'avait demandé au FONDS s'il en portait la
trace. `mesure_noms_casse.py` (18 tests) le demande : sur **37 707 tags nommés,
0 préfixe non canonique, 0 doublon de casse, 3 tags en casse divergente** —
`animal:luna` là où la fiche dit `Luna`. Le correctif reste juste, mais il
s'annonce pour ce qu'il est : de la robustesse, pas une réparation.
**Une règle unique** — `tagging_meta.parse_tag_nomme` — remplace six lectures
(trois normalisées, trois en casse sensible) dans `server.py`, `tagging_meta`
et `renommage_facts` : le préfixe se lit sans égard à la casse, le NOM ne
s'abaisse jamais (règle 2), et la fiche fait foi sur l'orthographe partout où
un nom part dans une suggestion, un retrait ou un fichier XMP.
**Observé en réel** (`code_a_jour` vrai) : `/api/names` passe Luna de **207 à
210** — exactement les trois tags que la mesure avait nommés — et les 351 noms
de personnes ne bougent pas d'un compte.

**Quatre défauts d'audit qui ne cassaient rien sont corrigés — et le premier
d'entre eux en a rendu un cinquième VISIBLE.** I5 : `/reglages` affirmait
« Reconnaissance des visages : CPU (seul Ollama utilise le GPU) » en dur, faux
depuis le GPU adaptatif ; le libellé vient maintenant du serveur et DIT la
raison (« choix delibere : la VRAM va au tagging »). I6 : l'arbitre VRAM et
l'ordonnanceur n'existaient que dans `/api/search/status` — un mécanisme qu'on
ne voit pas ne se diagnostique pas ; la carte « Arbitre VRAM » montre les baux,
les Mo libres, les refus et les évictions (observé : bail `semantique` 1 400 Mo,
1 811 Mo libres, 0 refus). **Et elle a immédiatement montré I1** : `tours` reste
à `visages: 0, animaux: 0` — les deux boucles les plus lourdes ne passent
toujours pas par `creneau()`, exactement ce que l'audit du 11/08 annonçait.
I8 : `/api/pets/name` et `/api/hardware` retirés (404 vérifiés), les chemins
vivants intacts. I4 : 57 lignes rejetées le 30/07 retirées de `classifier.py` —
le défaut n'était pas le code mort mais l'en-tête, qui décrivait depuis 22 jours
un comportement que le logiciel n'avait pas.

**Le chiffre neuf est ailleurs, et il ne se répare pas tout seul : `personne:
Florine` vit sur 153 photos SANS AUCUNE FICHE.** C'est le seul nom du fonds
dans ce cas. Conséquence visible : la galerie propose « Florine » comme puce de
filtre (les puces viennent des `kw` des photos) pendant que `/api/names` — donc
`/people`, l'autocomplétion et tout curateur — l'ignore. **Deux autorités
divergent sur « qui est une personne ».** Et **149 de ces 153 photos portent
aussi `personne:Flo`** : soit Florine EST Flo et c'est un doublon d'identité à
fusionner, soit c'est quelqu'un d'autre et il lui manque une fiche. Aucune
colonne ne tranche ça — c'est un jugement, il est dans `QUESTIONS_MIKE.md`.

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
   `personne:Florine`, 153 photos sans fiche — question posée à Mike.
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

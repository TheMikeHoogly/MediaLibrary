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
> il l'a été trois fois, les 05/09, 09/09 et **13/09**.

> **`N:\Photos` se connecte à chaque session** — règle dans `CLAUDE.md`
> (« Tester en réel »), depuis le 29/08.

---

## La campagne est FINIE — et c'est ce qui change tout

Lancée le 05/09, finie **dans la nuit du 12 au 13/09**. Relevé le 13/09 à
15 h, chiffres pris sur la machine et non sur une doc :

| | |
|---|---:|
| photos portant `qwen3.5:4b\|v3fr\|kb1` | **40 525 / 40 525** |
| abandons | **1** (voir B4) |
| vignettes de grille présentes | **40 525 — 100 %** |
| GPU | **0 %**, 3 773 Mo libres sur 4 096 |
| RAM disponible | **5,2 Go (33 %)**, défauts durs ≈ 0 |

**Trois contraintes tombent en même temps**, et c'est la vraie nouvelle :
le **prompt redevient touchable**, le **GPU est rendu**, et la **machine ne
pagine plus** — elle vivait sur 0,5 Go libre depuis une semaine
(`PERFORMANCE.md` § 3.10). Tout ce qui attendait « après la campagne » est
ouvert d'un coup ; la difficulté n'est plus d'attendre, c'est de CHOISIR.

**Deux garde-fous ont tenu, vérifiés le 13/09 et pas supposés :**

- **L'élargissement FR→EN n'est pas mort en silence.** Le retag FR seul a bien
  vidé `kw_en` — **0 sur 40 525 photos**, mesuré. Le dictionnaire appris n'a
  donc plus une paire (`appris: 0`) et l'élargissement aurait disparu SANS
  UNE LIGNE D'ERREUR. Le gel du 05/09 (`dico_fr_en.json`, tranché par Mike)
  le sert : `source: gelé`, **3 862 paires**, une recherche française
  continue de voir l'anglais. **C'est le garde-fou qui valait le plus cher de
  tout le projet** : il défendait +0,075 de rappel contre une panne muette.
- **`exiftool -P`** (12/09) : le tagueur a réécrit 40 000 XMP pendant la nuit
  sans détruire une date de fichier.

---

## A. Ce qui appartient à Mike

**A1. Trier les 248 dépôts d'`Uploads`.** La lampe de l'entête y mène
(`/tri`), le tableau se trie et se filtre, la sélection multiple et les gestes
groupés fonctionnent. Le plus ancien attend depuis **31 jours**. **Rien ne
bouge sans lui** : c'est le principe du chantier, et c'est le seul point de la
roadmap qui n'ait pas avancé d'un pas depuis le 12/09.

**A2. La dernière photo sensible — probablement close.** `/api/sensibles`
répond **0 en attente de verdict** le 13/09. La liste est PAR UTILISATEUR :
seul Mike, en ouvrant l'onglet, peut confirmer qu'il n'en reste vraiment
aucune. Si l'onglet n'apparaît pas, il n'y a rien — et ce jalon sort d'ici.

**A3. Lire la page `/aide`.** Posée et vérifiée. Ce qui reste n'est pas une
tâche mais un jugement : c'est sa famille qui lira ce texte.

**A4. Le ménage — ce qui reste VRAIMENT (revérifié le 13/09).** Cette entrée
annonçait une décision sur les **283 Mo** de
`_to_delete\menage_20260908\_avant_deplacement\photos.db` : **le fichier
n'existe plus**, `_to_delete\` pèse aujourd'hui **14 Mo** et ne contient plus
aucune base. La décision a donc été prise sans moi — et je l'ai recopiée deux
fois sans la vérifier. Ce qui reste, mesuré :

- **`_corbeille_menage\` : 63 Mo**, à vider à la main quand Mike juge le délai
  passé. C'est le vrai gisement.
- `_corbeille_session\` : 5,5 Mo.
- Le prochain bat 50 proposera de nouveau ce qu'il trouvera : **ne pas citer de
  chiffre ici**, l'instrument le dira, et les deux fois où un chiffre a été
  recopié dans cette roadmap il était faux.
- Les trois `_test_claude_tri.jpg` de 160 octets (mes témoins du 12/09) ne sont
  plus dans le dépôt ; s'ils traînent encore, c'est dans la corbeille du NAS.

**A5. Windows : ne pas laisser revenir KB5124008.** Il casse Plan9, donc
`device_bash` (reconnu par Microsoft et Anthropic ; correctif annoncé « dans
un cumulatif suivant »). La machine tourne en **UBR 9278**, Windows Update est
**en pause jusqu'au 17.10**. **Vers le 16.10** : masquer le KB s'il est
reproposé (le bloc PowerShell est dans l'historique de la session du 12/09).
`Get-HotFix` MENT sur ce sujet ; la vérité est
`(Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion').UBR`.

**A6. Les deux gestes git que je ne peux pas faire.** L'agent ne connaît que
`ping`, `commit` et `livrer` : `git rm --cached _collage6.py _collage7.py`
(ignorés mais suivis) passe par `27 - Git.bat`. Rien d'urgent, mais ça ne
partira pas tout seul.

---

## B. Ce que la fin de la campagne vient d'ouvrir

Par ordre de valeur, et non de facilité. Les quatre premiers étaient
**empêchés**, pas reportés.

**B1. Le bilan de la campagne — et ce qu'on ne pourra PAS mesurer.** Première
passe officielle du fonds entier : 40 525 photos, 1 abandon, 100 % de
vignettes. Reste la vraie question : **ce que `v3fr|kb1` a changé**.

**Mauvaise nouvelle, vérifiée le 13/09** : il n'existe plus d'instantané
d'AVANT. La copie de 283 Mo était la dernière (A4) et elle a été effacée ;
`photos.db.bak` est un roulement rafraîchi toutes les heures. `mesure_retag_
gain.py`, lui, compare deux GÉNÉRATIONS de pipeline dans le même index — or
les 40 525 photos portent désormais la même. **Le lancer maintenant ne
mesurerait plus que le bruit du modèle.**

**Le bilan DESCRIPTIF, lui, est fait** (13/09, sur la copie) — ce que le fonds
porte aujourd'hui :

| | |
|---|---:|
| photos taguées | **40 525** (+ 4 133 vidéos, 8 illisibles) |
| sans aucun mot-clé | **0** |
| sans description | **0** |
| mots-clés par photo | médiane **6**, moyenne 6,9, de 3 à 23 |
| au moins un fait | **99,7 %** — date 99,2, personne 44,1, lieu 28,2, espèce 10,3 |
| vocabulaire | **44 744 mots-clés distincts** pour 280 315 occurrences |
| vus UNE seule fois | **28 774 — 64,3 % du vocabulaire** |

Couverture parfaite : pas une photo sans mots-clés ni description. **Le chiffre
qui interroge est le dernier** : deux tiers du vocabulaire n'apparaissent
qu'une fois (« carrelage beige », « campagne andine »). C'est de la
description riche, et c'est très bien pour une recherche par le SENS — mais un
mot-clé vu une fois ne sera jamais une facette de filtre utile, et il ne peut
pas non plus apprendre une paire FR→EN. **À instruire** : les facettes
doivent-elles se bâtir sur la fréquence plutôt que sur la liste brute ?

**Leçon pour la prochaine campagne : copier la base AVANT de la lancer** —
quatre secondes (`mesure_copie_base.py`), et c'est la seule fenêtre.

**B2. Le modèle de vision — la question redevient un CHOIX.** La décision du
12/09 (« on vit avec les 13,5 Go d'Ollama ») est **périmée par la fin de la
campagne** : le moteur a rendu la mémoire, il ne reste rien de lui dans le
relevé du 13/09, et la RAM libre est passée de 0,5 à 5,2 Go. Le sujet n'est
donc plus « la machine pagine », c'est « **quel modèle pour la PROCHAINE
passe** » — un qui tient entièrement dans les 4 Go de VRAM ne reprendra pas
7,8 Go en RAM. Protocole `vision-eval` ; changer de modèle est un changement
de pipeline, donc une campagne de plus.

**B3. La question au tagueur sur les documents sensibles.** Elle était
**empêchée**, pas reportée : la toucher pendant la campagne aurait rendu
candidates les 12 000 photos déjà refaites. Le prompt est de nouveau
touchable — et toute modification relance une passe complète. À instruire
AVANT d'écrire une ligne : est-ce que ça vaut une campagne ?

**B4. L'abandon, et ce qu'il cache.** `Photos Mike\2018\08 Août\
20180805_095733.jpg` porte `retag_fail` avec le message **« another row
available »**. Trois choses, dans l'ordre où elles comptent :
1. **La photo va bien.** Elle est taguée — 7 mots-clés, description, faits —
   et son `pipe` est à jour. Le drapeau est une cicatrice, pas un trou.
2. **Le message n'est pas du modèle, c'est de SQLite.** Un `step()` qui rend
   une ligne là où l'appelant attendait la fin. C'est un défaut de LECTURE
   concurrente sous charge, pas une photo difficile.
3. **Donc ça peut recommencer, et plus fort.** Une passe de 40 000 photos l'a
   déclenché une fois. Le chercher maintenant, à froid, coûte moins cher que
   de le revoir sur une campagne de nuit.

**B5. Re-mesurer les Motion Photos arrivées depuis le 03/09** — demande le
serveur arrêté, donc impossible pendant la campagne, trivial maintenant.

**B6. Le reste d'audit : O8 et O9.** Matmul par visage et backfill sémantique
— les deux touchent des boucles de CALCUL, donc le GPU : c'est maintenant
qu'elles sont mesurables. **O15 est outillé** : les trois caches de vignettes
pèsent 722 Mo dont **541 Mo d'orphelins**, et `51 - Purger les vignettes
orphelines.bat` attend un geste de Mike ; la réversibilité y est la
RÉGÉNÉRATION, pas une corbeille. **À re-mesurer d'abord** : le chiffre date
d'avant que la campagne pose 40 000 vignettes.

**B7. L'ordre inverse maintenance / scan — FERMÉ, et je l'ai vu tourner.**
Cette ligne disait « non mesuré, non corrigé » ; **c'était faux**, et je
l'avais recopiée sans la vérifier en réorganisant la roadmap deux heures plus
tôt. Le garde-fou existe des DEUX côtés depuis longtemps :
`maint_lourde_en_cours()` fait reporter le volet NAS du scan, avec un plafond
de trois tours (`NAS_REPORTS_MAX`) pour qu'une maintenance qui n'en finit pas
n'affame pas l'indexation. **Observé en production le 13/09** : trois reports
à 17h05, 17h10, 17h15, puis « ▶ scan NAS repris apres 3 report(s) » à 17h20.

**Ce que cette vérification a trouvé, en revanche** : le recensement avait
annoncé son départ à 16h43 et **plus rien pendant quarante minutes** — ni fin,
ni durée, ni verdict. Pour savoir s'il tournait encore il fallait croiser le
journal, `maintenance_report.json` (écrit seulement à la FIN du cycle) et la
date de `recensement.json`. Et les codes de retour des deux sous-processus
partaient dans un JSON que personne n'ouvre : **un recensement qui ÉCHOUE
emportait le plan de rangement avec lui, en silence.** C'est le mode de panne
que ce projet paye le plus cher (les backfills EXIF morts pendant des mois).
Corrigé le 13/09 : toute étape lourde dit sa fin, sa durée en clair et son
verdict — **y compris quand elle lève** —, la conséquence d'un échec est dite
(« le plan n'a PAS été lancé »), et `/api/maint/status` porte `maint.lourde`
(ce qui tourne MAINTENANT, et depuis quand — lu à 23,6 min pendant que
j'écrivais ces lignes). Bancs dans `test_maintenance.py`.

**Et le découpage que la mesure a imposé** : « recensement + plan » est en fait
DEUX sous-processus très inégaux — `recensement_doublons.py` a mis **9 min**,
`plan_rangement.py` en était à **23 et tournait encore**. Une seule ligne pour
les deux ne disait pas dans quelle moitié on était, ce qui est justement la
question devant une étape qui dure. Chacune annonce désormais la sienne.

**Ce qui reste ouvert, et qui est né de là** : le recensement n'a pas abouti
depuis le **06/09**. Il est dû tous les 7 jours, il dure **plus de 40 minutes**,
et **chaque redémarrage du serveur le tue** — or le protocole de livraison en
impose un à chaque changement de `server.py`. Une journée de travail à mon
rythme suffit à le rendre impossible. Deux pistes : lui laisser une fenêtre (ne
pas livrer pendant qu'il tourne — `maint.lourde` le dit maintenant), ou le
rendre REPRENABLE.

**Deux mesures, dont une qui m'a contredit dans l'heure** — et c'est le nouvel
instrument qui l'a permis :

- **Ce qui est SÛR.** Pendant l'étape lourde, le CPU est à **0 %** et la RAM
  intacte : ce n'est pas du calcul, c'est de **l'attente SMB** (même signature
  que le `parcours` de la galerie, 15 ms de CPU pour 692 ms). Et le plafond de
  trois reports laisse partir le scan NAS **par-dessus** l'étape lourde :
  l'énumération qui prend d'ordinaire **305 s** en était à **22 minutes** ce
  jour-là. **La concurrence coûte cher, c'est mesuré.**
- **Ce que j'avais écrit et qui est FAUX.** J'en avais conclu que les deux
  balayages se ralentissaient « d'un facteur quatre ». L'observation suivante
  dit le contraire : `recensement_doublons.py` a mis **8 min** pendant que le
  scan tournait, et **plus de 27 min** en tournant SEUL, une demi-heure plus
  tard. Hypothèse non vérifiée : le scan venait d'énumérer le fonds, donc le
  cache de métadonnées SMB était CHAUD. **Ce n'est qu'une hypothèse** — la
  durée de cette étape varie du simple au triple et personne ne sait pourquoi.

**La question à instruire n'est donc pas « le plafond de trois est-il bon ? »
mais « de quoi dépend la durée de cette étape ? »** — sans cette réponse, tout
réglage du plafond serait un chiffre choisi à l'aveugle. L'instrument pour y
répondre existe maintenant : chaque moitié annonce sa durée à chaque passage,
il suffit d'en lire quelques-unes.

**B8. Le tri des dépôts, à éprouver.** Ce qui reste dépend de l'usage : le
**mur de 7 jours** est-il le bon ? faut-il un geste groupé pour le lot
hérité ? Ne rien changer avant que Mike s'en soit servi une fois (A1).

---

## C. La performance — le chantier des redites est CLOS

Le détail vit dans `PERFORMANCE.md` § 3.13 à 3.23 et § 5, pas ici. Ce qui
compte pour ordonner :

**C1. Ce qui est acquis.** La page `/files` d'un dossier de 2 519 photos est
passée de **1 493–1 870 ms à 544–763 ms** (12/09), en retirant **douze calculs
refaits** : le dossier énuméré deux fois, le lien de dossier par photo, la
date précise calculée trois fois, la vue consultée 44 605 fois pour 2 519
réponses, le lieu demandé 2 519 fois pour deux réponses, les années du dossier
relues quatre fois par photo, la classification de motif faite deux fois, le
`Path` de `_resolve_key`. Chacun avec sa mesure avant/après et son banc.

**C2. Ce qui reste n'est plus du travail refait, c'est du travail.**
`enrichir` reste le premier poste (220 ms) mais aucun de ses morceaux ne
dépasse 55 ms, et ~90 ms vont à fabriquer les 2 519 dictionnaires eux-mêmes.
Deux petits restes nommés, sans urgence : le dernier partage de lecture du
`taken` (~15 ms, avec le piège du § 3.20 — minimum contre priorité : on
partage les lectures, jamais la réponse) et `marques` (~27 ms).

**C3. LE PROCHAIN GAIN EST DÉCIDÉ — chargement à la demande.** Le plus gros
poste hors calcul est devenu `envoi` : **93 ms pour 1,86 Mo** sur le réseau
local. Le gain n'est plus une mémoïsation, c'est **envoyer moins**. Trois
formes ont été posées à Mike le 12/09 ; **il a tranché le 13/09 : (c), le
chargement à la demande** — la page rend les 300 premières fiches, le reste
arrive en scrollant. C'est la seule des trois qui ne retire rien à l'usage.

Ce que la décision engage, et qu'il faut instruire AVANT de coder :
- **Le tri et les filtres restent faits par le SERVEUR.** S'ils passaient au
  client, ils ne porteraient que sur ce qui est déjà chargé — une grille qui
  ment sur ce qu'elle a trié est pire que lente.
- **Les quatre modes « la grille est un résultat »** (tags, recherche,
  semblables, même jour) remplacent déjà `file_data` (§ 3.14) : la pagination
  doit se poser DERRIÈRE eux, pas à côté.
- **`window.Vignettes` existe déjà** (IntersectionObserver + file plafonnée à
  4 requêtes) : le chargement à la demande s'y branche, il ne le refait pas.
- **Un compteur qui ment est le mode de panne de ce projet.** Le bandeau doit
  dire le total RÉEL, pas ce qui est chargé.

**C4. Le premier chargement reste cher** : ~2,5 s après un redémarrage,
partage et caches froids. Aucun mémo ne fabrique quoi que ce soit, ils évitent
de refaire. Ce n'est pas un défaut, c'est la nature d'un cache — mais c'est ce
que Mike voit en ouvrant le matin.

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
avec la rigueur complète, ou à accepter tel quel — choix de Mike. **Le fonds
entier porte maintenant ce modèle** (13/09) : la question n'est plus « fallait-il
le choisir » mais « qu'est-ce qui mériterait la campagne SUIVANTE » (B2).

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
- **UNE seule règle lit la date dans un nom de fichier, UNE seule lit les
  années du dossier** (12/09) : `server._fname_time` et `server._path_years`
  délèguent à `faits_vue.epoch_du_nom` et `renommage_facts.path_years`, toutes
  deux mémoïsées. Les lecteurs étaient déclarés miroirs sans jamais avoir été
  comparés. `mesure_miroir_dates.py`, deux couples, **0 désaccord sur 44 966
  fichiers** — mais un cas limite réel côté nom (une heure impossible
  basculait au jour SUIVANT), tranché en faveur de la règle STRICTE.
- **`git_agent.tests_pour` lance aussi les bancs qui CITENT un module touché**
  (12/09) : l'appariement par NOM seul laissait **63 bancs** invisibles, dont
  59 citent `server.py` — **cinq étaient ROUGES**, tous accrochés à une
  ORTHOGRAPHE du source qu'une correction avait changée ; réécrits sur
  l'arbre. Une **règle 3** a suivi le jour même : le GRAPHE des imports, parce
  que la 2 ne voyait pas le banc qui fait `import x` (`renommage_facts.py`
  livré avec 1 banc sur 11). Large par construction : c'est un filet, pas un
  filtre. Son seul trou est NOMMÉ (`BANCS_A_LA_MAIN`) : `test_tagging.py`
  tague pour de vrai et veut le serveur arrêté.
- **Stockage** : SQLite local WAL (**44 665 entrées**, 119 772 vecteurs),
  embeddings BLOB, backup NAS snapshot + `backup_verify`.
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
  fichiers. **Le fonds ENTIER porte `qwen3.5:4b|v3fr|kb1` depuis la nuit du
  12 au 13/09** : 40 525 photos, 1 abandon.
- **Les vignettes de grille sont à 100 %** (13/09, `mesure_couverture_
  vignettes.py` sur les quatre fonds) — elles manquaient sur 98 % du fonds le
  11/09. Le tagueur en a posé une au passage ; le fil de fond n'a pas eu à
  rattraper quoi que ce soit. Les **4 133 vidéos** sont hors de ce compte.
- **Le gel du dictionnaire FR→EN a tenu** (posé le 05/09, observé le 13/09) :
  le retag FR seul a vidé `kw_en` sur **40 525 photos sur 40 525**, le
  dictionnaire appris est tombé à **0 paire**, et l'élargissement sert
  désormais les **3 862 paires GELÉES** (`source: gelé`). Sans ce garde-fou la
  recherche élargie serait morte sans une ligne d'erreur. **Ne pas « nettoyer »
  `dico_fr_en.json`** : c'est la seule copie de cette matière.
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

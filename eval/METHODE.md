# Méthode — invariants à ne pas réapprendre

> `eval/DECISIONS.md` dit **ce qui a été tranché** ; ici, **comment on tranche**.
> Chaque ligne a été payée par une mesure ratée ; la date dit laquelle.

- **Circularité de l'auto-évaluation** : un système qui apprend de ses décisions contamine son
  banc — et une règle qui LIT ce qu'un autre pan du projet a ÉCRIT aussi (71 des 132 lieux lus
  dans un nom de fichier y avaient été mis par le renommage). Vérité terrain = **confirmations
  humaines**.
- **Comparaison à armes égales** : vérifier ce que chaque modèle *reçoit vraiment* (30/07). Et
  **un banc qui RECOPIE la prod mesure autre chose qu'elle** (14/08) : il l'IMPORTE.
- **Un proxy n'est pas le juge final** : ils disaient « V2 ≈ V0 », l'humain a tranché. Noter à
  l'aveugle. Un bon score MOYEN n'est pas un feu vert : les faux rejets priment.
- **Ordre imposé (`vision-eval`)** : hypothèse + protocole *avant* de mesurer, puis décider et
  câbler. **5 photos d'écart n'est pas un vainqueur** (14/08) : 25-15 → p = 0,15.
- **Un critère est un ET, et c'est l'OUTIL qui l'applique** (16/08) : `--depouiller` testait la
  préférence puis imprimait « vérifier les hallucinations ». Un critère non appliqué est une
  intention.
- **Une préférence globale peut être portée par une seule strate** (16/08) : 63,9 % au total,
  83 % sur les 30 pièges, **59 % sur les vraies photos**. Dépouiller par strate n'est pas un
  raffinement : c'est la mesure. Et **comparer deux TOTAUX jette l'appariement** — 24-13 en
  totaux, 15-4 en discordantes (p = 0,019).
- **Un échantillon figé fige des CHEMINS, pas des photos** (15/08) : un rangement par année a
  tué 43 % des clés d'un banc, qui a tourné sur 57 % sans le dire.
- **Mesurer la matière première avant de bâtir dessus** (13/08), et **par le chemin de code de
  la DONNÉE, pas par une vue** (14/08) : par clé, 0 % devenait 60 %. **Un avant/après n'existe
  que si l'AVANT a été enregistré.**
- **Un chiffre devient une mesure quand deux chemins y tombent** (15/08) : `sans_date` = 3 824,
  annoncé par le serveur vivant ET retrouvé sur une COPIE de la base.
- **Et quand les deux chemins se CONTREDISENT, l'écart est le vrai résultat** (17/08) : les
  dates de scan se comptent par le dossier (15) ou par la trace `YYYY0000` du nom (27). Le
  désaccord n'était pas du bruit : **1 cas où le repli sur le NOM réinscrit ce que le garde-fou
  venait d'écarter**, **15 noms périmés**. Un accord parfait n'aurait rien appris.
- **Un « déjà perdu » se mesure, il ne se déduit pas d'une recherche qu'on n'a pas faite**
  (22/08) : 787 décisions ont été déclarées perdues parce que le banc ne fouillait qu'une autre
  population. En cherchant vraiment, 698 clés sur 804 retrouvent leur photo. Une population
  écartée d'une mesure doit être NOMMÉE dans le rapport, sinon elle devient une conclusion.
- **Le meilleur témoin d'un déplacement est le programme qui l'a fait** (22/08) : avant de
  comparer des noms ou des vecteurs, chercher si le geste a laissé une trace. Les journaux
  d'annulation de `docs/`, écrits pour DÉFAIRE, relus à l'endroit disent où chaque photo est
  partie — 685 clés retrouvées là où le nom en rendait 346 et le vecteur 13.
- **Un déplacement en masse se vérifie par CONTREPARTIE, pas par un total**
  (22/08) : après avoir re-clé 787 décisions humaines, le total est passé de
  3 364 à 3 310. Un total ne dit pas si les 54 manquantes ont fusionné ou
  disparu. L'audit de la quarantaine apparie chaque SORTIE à une ARRIVÉE de
  même type et de même index — 734 appariées, 54 fusions, **0 sans
  contrepartie**. C'est la seule forme qui distingue « déplacé » de « perdu ».
- **Un garde-fou qui ne se déclenche jamais est aussi une mesure** (22/08) : « 0 index hors
  bornes » sur 462 rattachements n'est pas un contrôle inutile, c'est une corroboration — un
  jumeau faux aurait fait déborder les index.
- **Un no-op silencieux est le pire mode de panne** (22/08) : `store.rekey` renvoyait faux sur
  deux magasins sur quatre, sans un mot, pendant des semaines. Une boucle qui traite des objets
  de natures différentes doit VÉRIFIER qu'elle a agi, ou les traiter séparément.
- **« Le fichier existe » ne dit pas « il sera repris »** (17/08) : 91 photos présentes, mais
  hors de toute racine scannée — muettes à vie. Répliquer la règle de SÉLECTION du producteur.
- **Une limite ÉCRITE n'est pas une limite gérée** (17/08) : `date_fiable` annonçait dans sa
  docstring que le scanner remplissant `DateTimeOriginal` passait au travers. Vrai, assumé, sans
  conséquence — jusqu'au chantier qui la rend coûteuse. Relire les limites documentées à l'entrée
  de chaque chantier qui écrit.
- **Deux gestes réversibles enchaînés ne sont pas réversibles** (17/08) : renommer en 2007 puis
  ranger par année déplace la photo dans `2007/`, et `1990_Achumani` disparaît. Juger la CHAÎNE.
- **La direction d'un écart porte le sens** (17/08) : une date EXIF postérieure au dossier est
  un artefact de scan ; antérieure, c'est l'EXIF qui corrige un dossier d'import. **1 347
  antérieures** contre 72 : un garde-fou symétrique ferait dix-huit fois plus de mal que de bien.
- **Un écart mémoire/disque se tranche par un REDÉMARRAGE, pas par une déduction** (17/08) :
  trois hypothèses plausibles, toutes tombées ; le redémarrage a répondu en dix secondes.
- **Ce qui n'est pas compté n'est pas diagnosticable APRÈS** (17/08) : `forget_everywhere` rend
  un nombre que personne n'enregistre — incident clos sans cause. Compter au moment du GESTE.
- **Un compte spectaculaire est d'abord une erreur de clé** (15/08) : `vectors` contre `tags`
  sans le `kind` annonçait 86 181 orphelins ; le vrai : 2 374.
- **Compter les faux qu'on retire sans compter les VRAIS qu'on emporte, c'est mesurer une
  moitié** (19/08) : les segments entiers évitaient 546 faux « Ins » et jetaient ~330 lieux RÉELS
  collés à leur année (« Yani2004 »). Le chiffre qui décide : « photos qui perdent leur SEUL
  lieu ». Et un AVANT qu'on doit RECOPIER se vérifie contre le vivant (banc et `/sujets` : 493).
- **Quatre façons de perdre une capacité en silence** : un **effet de bord à l'import** court
  chez tous ceux qui LISENT le fichier ; un **repli silencieux déguise la cause en symptôme** ;
  une **protection qui s'annule** doit se COMPTER ; un **invariant tacite** finit par être faux.
- **Une sortie REDIRIGÉE n'est pas une console** (15/08) : `import server` mourait d'un
  `UnicodeEncodeError` dès que stdout était un tuyau. Corriger la POLITIQUE D'ERREUR.
- **Un référentiel générique nomme mal le particulier** (14/08) : `cities1000` a nommé le
  domicile d'après la commune voisine (1 257 photos). Prévoir la reprise en main humaine.
- **Chercher un défaut en trouve un autre, plus gros** — une mesure pour CLASSER 62 photos en a
  exhumé 714 (14/08) ; un banc censé trancher une re-passe a mesuré le prompt de PROD (16/08) ;
  compter les dates de scan a montré un trou dans le garde-fou (17/08) ; unifier la règle de lieu
  a montré que ses « faux positifs » contenaient 330 vrais (19/08).
- **Une approximation DÉCLARÉE finit par se voir, et c'est le BANC qui a tort** (19/08) : sous
  UTC, deux des six divergences « vue ↔ champ écrit » étaient des photos prises à 00h06 et 00h40.
  Sous `TZ=Europe/Zurich` : 4, toutes réelles. Relancer sous le bon fuseau coûte dix secondes.
- **Un chiffre publié sans le CODE qui l'a produit n'est pas reproductible** (21/08) : la
  concordance du 20/08 (3 065 photos) ne vivait que dans un tableau de décisions ; réécrite en
  code le lendemain, elle rend 3 134 — même famille, pas le même trait. Écrire le chiffre ET le
  banc, ou ne pas bâtir dessus.
- **Compter les décisions POSITIVES seulement sous-estime la vérité terrain** (21/08) : 1 196
  visages rattachés, mais **1 496 exclusions** — « ce visage n'est PAS Flo » évalue un
  clustering aussi bien qu'un rattachement. Et deux mesures ne doivent jamais porter le même
  nom : « photos nommées » (44,8 %) et « visages étiquetés » (1,66 %) répondent à des
  questions différentes ; les confondre a fait passer le produit pour bloqué.
- **Répliquer la RÈGLE d'un producteur sans ses GARDE-FOUS, c'est mesurer son cousin** (21/08) :
  le banc de propagation annonçait **3 698** rattachements en attente ; en appliquant le
  garde-fou des clés fantômes que `build_suggestions` applique, il en reste **14**. Les 3 684
  autres pointaient vers des fichiers disparus. Le chiffre juste n'était pas 100 fois plus petit
  par hasard : il l'était de tout ce que le banc avait omis de refuser.
- **Un incident clos par son symptôme revient par l'autre bout** (21/08) : la purge du 17/08 a
  retiré les vecteurs SigLIP de 2 374 clés orphelines — et laissé leurs VISAGES. Quatre jours
  plus tard, exactement les mêmes 2 374 clés, mesurées par un autre chemin, faisaient re-scorer
  3 698 visages morts toutes les 240 s. Purger sans avoir trouvé la CAUSE reconduit l'incident.
- **Deux contrôles qui ne se croisent pas laissent un angle mort en forme de troisième** (21/08) :
  le diagnostic comparait les détections au DISQUE et les vecteurs à l'INDEX. Il manquait
  détections contre INDEX — et c'est là que 2 374 fiches de visages ont vécu quatre jours après
  une purge « observée ». Quand deux instruments couvrent A-B et B-C, demander qui couvre A-C.
- **Un compteur qui ne survit pas au redémarrage ne diagnostique rien** (21/08) : `comptes_index`
  a été bâti pour rendre les −250 explicables après coup ; il vit en mémoire. Au redémarrage
  suivant, `par_motif` est vide. La cause des 2 283 orphelines ne sera jamais établie
  rétrospectivement. Compter au moment du geste ne suffit pas : il faut l'ÉCRIRE.
- **Un échantillon se FIGE, une référence se LIT MAINTENANT** (22/08) : le tirage de la tranche
  emportait avec lui les visages de référence. Tiré à 21:26, jugé à 22:53, il montrait encore les
  couples d'avant le recalage appliqué à 22:19 — **3 planches sur 30**, dont Didier et Mathieu,
  exactement les deux fiches signalées à l'œil la veille. Figer le tirage est ce qui le rend
  uniforme ; figer la référence est faux, car la référence n'est pas ce qu'on mesure mais ce
  CONTRE QUOI on mesure. Et elle ne vieillit pas au hasard : elle vieillit précisément là où une
  réparation vient de passer, donc là où l'on cherche à constater un progrès.
- **« Aucune amélioration » est un chiffre à chercher, pas un verdict à croire ni à écarter**
  (22/08) : l'œil disait vrai deux fois pour deux raisons différentes — une planche périmée (3
  items) ET un résidu réel que la règle refuse de réparer (9 décalés, 34 refus). Un taux global
  de 0,8 % les cachait tous les deux, parce qu'il est **concentré** : Didier porte 4 des 9.
  Un défaut réparti se dilue dans un taux ; un défaut concentré se voit à chaque ouverture de la
  fiche. Compter par FICHE, pas seulement sur le fonds.
- **Un FICHIER n'est pas une SCÈNE** (22/08) : pour réfuter quinze jugements humains, un test
  géométrique a posé que deux visages aux boîtes disjointes sont deux personnes. Il a rendu
  **0,0 sur 15 cas sur 15** — et la première photo ouverte était une **page d'album
  photographiée** : un fichier de 3735×1378 contenant cinq tirages. `Flyer_Jenny.jpg` en porte
  quatre. Pages scannées, montages, flyers : la même personne y paraît plusieurs fois, à des
  endroits différents. Toute règle qui suppose une scène par fichier se trompe ici — et elle s'y
  trompe exactement sur la population qui fait citer deux fois le même fichier, donc là où on
  l'invoque.
- **Un score parfait est une alarme — y compris quand c'est le sien** (22/08) : la règle était
  écrite dans `CLAUDE.md` et appliquée à tous les bancs du projet, sauf à celui qui venait de
  servir à contredire un humain. 15/15 aurait dû faire relire l'instrument AVANT la conclusion.
- **Un écart de score n'est pas une identité fausse** (22/08) : le critère « décalé » dit qu'un
  autre visage de la même photo dépasse le désigné de 0,10 — pas que le désigné soit le mauvais.
  Le chiffre qui sépare les deux est le SCORE DU VISAGE DÉSIGNÉ : les 9 décalés restants tiennent
  **0,594–0,745** (des apparitions multiples), les 13 « sous le seuil de faux positif » tiennent
  **0,06–0,295** (des inconnus). Vérifié dans l'autre sens sur les 33 recalages appliqués :
  **29 réparations** (ancien score sous 0,30, jusqu'à **−0,13**) contre **4 rebrassages**. La
  règle avait tranché presque exactement au bon endroit — mais ce n'est pas le mot « décalé »
  qui le disait, c'est le score.
- **Un seuil bas ne nomme pas une erreur, il nomme une cécité** (22/08) : sur les 13
  rattachements dont le visage désigné scorait 0,06–0,295, l'humain en a confirmé **12**. Le
  seuil ne disait pas « ce n'est pas elle », il disait « je ne la reconnais pas » — deux
  phrases différentes, et seule la seconde est vraie. Avant de traiter un score faible comme un
  défaut du fonds, se demander s'il n'est pas un aveu de l'instrument.
- **Fragilité du corpus** : clés corrompues et mutations concurrentes ont invalidé des runs ;
  `--mesurer` alerte au-delà de 15 % de clés mortes.

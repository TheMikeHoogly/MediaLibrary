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
- **Fragilité du corpus** : clés corrompues et mutations concurrentes ont invalidé des runs ;
  `--mesurer` alerte au-delà de 15 % de clés mortes.

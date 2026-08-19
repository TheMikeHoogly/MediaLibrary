# Méthode — invariants à ne pas réapprendre

> `eval/DECISIONS.md` dit **ce qui a été tranché** ; ici, **comment on tranche**.
> Chaque ligne a été payée par une mesure ratée ; la date dit laquelle.

- **Circularité de l'auto-évaluation** : un système qui apprend de ses décisions contamine son
  banc. Vérité terrain = **confirmations humaines** seules.
- **Comparaison à armes égales** : vérifier ce que chaque modèle *reçoit vraiment* (30/07). Et
  **un banc qui RECOPIE la prod mesure autre chose qu'elle** (14/08) : il l'IMPORTE.
- **Un proxy n'est pas le juge final** : ils disaient « V2 ≈ V0 », l'humain a tranché. Noter à
  l'aveugle. Un bon score MOYEN n'est pas un feu vert : le coût des faux rejets prime.
- **Ordre imposé (`vision-eval`)** : hypothèse + protocole *avant* de mesurer, puis décider et
  câbler. **Un écart de 5 photos n'est pas un vainqueur** (14/08) : 25-15 → p = 0,15.
  Dimensionner le banc AVANT.
- **Un critère est un ET, et c'est l'OUTIL qui l'applique** (16/08) : `--depouiller` testait la
  préférence puis imprimait « vérifier les hallucinations ». Un critère que l'outil n'applique pas
  est une intention.
- **Une préférence globale peut être portée par une seule strate** (16/08) : 63,9 % au total,
  mais 83 % sur les 30 pièges et **59 %, sous le seuil, sur les vraies photos**. Dépouiller par
  strate n'est pas un raffinement : c'est la mesure. Et **comparer deux TOTAUX jette
  l'appariement** — les deux variantes voient la même photo : 24-13 en totaux, 15-4 en
  discordantes (p = 0,019).
- **Un échantillon figé fige des CHEMINS, pas des photos** (15/08) : un rangement par année a tué
  43 % des clés d'un banc, qui a tourné sur 57 % sans le dire. Suivre le renommage ; jamais
  régénérer.
- **Mesurer la matière première avant de bâtir dessus** (13/08), et **par le chemin de code de
  la DONNÉE, pas par une vue** (14/08) : par clé, 0 % devenait 60 %. **Un avant/après n'existe
  que si l'AVANT a été enregistré.**
- **Un chiffre devient une mesure quand deux chemins y tombent** (15/08) : `sans_date` = 3 824
  et 260, annoncés par le serveur vivant ET retrouvés sur une COPIE de la base.
- **Et quand les deux chemins se CONTREDISENT, l'écart est le vrai résultat** (17/08) : les dates
  de scan se comptent par le dossier (15) ou par la trace `YYYY0000` du nom (27). Le désaccord
  n'était pas du bruit : 12 communs, **1 cas où le repli sur le NOM réinscrit ce que le garde-fou
  venait d'écarter**, **15 noms périmés**. Un accord parfait n'aurait rien appris.
- **« Le fichier existe » ne dit pas « il sera repris »** (17/08) : 91 photos bien présentes,
  mais dans un dossier caché hors de toute racine scannée — muettes à vie. Répliquer la règle de
  SÉLECTION du producteur, pas seulement tester l'existence.
- **Une limite ÉCRITE n'est pas une limite gérée** (17/08) : `date_fiable` annonçait dans sa
  propre docstring que le scanner remplissant `DateTimeOriginal` passait au travers. Vrai,
  assumé, sans conséquence — jusqu'au chantier qui rend la limite coûteuse. Relire les limites
  documentées à l'entrée de chaque chantier qui écrit.
- **Deux gestes réversibles enchaînés ne sont pas réversibles** (17/08) : renommer en 2007 puis
  ranger par année déplace la photo dans `2007/`, et `1990_Achumani` disparaît. Juger la
  réversibilité de la CHAÎNE.
- **La direction d'un écart porte le sens** (17/08) : une date EXIF postérieure au dossier est un
  artefact de scan ; antérieure, c'est l'EXIF qui corrige un dossier d'import. Le compte l'a
  confirmé : **1 369 antérieures** contre 72 postérieures — un garde-fou symétrique aurait fait
  vingt fois plus de dégâts que de bien.
- **Un écart mémoire/disque se tranche par un REDÉMARRAGE, pas par une déduction** (17/08) : trois
  hypothèses plausibles, toutes tombées ; le redémarrage a répondu en dix secondes.
- **Ce qui n'est pas compté n'est pas diagnosticable APRÈS** (17/08) : `forget_everywhere` renvoie
  un nombre que personne n'enregistre — incident clos sans cause. Compter au moment du GESTE.
- **Un compte spectaculaire est d'abord une erreur de clé** (15/08) : `vectors` contre `tags`
  sans filtrer le `kind` annonçait 86 181 orphelins ; le vrai : 2 374.
- **Quatre façons de perdre une capacité en silence** : un **effet de bord à l'import** court
  chez tous ceux qui LISENT le fichier ; un **repli silencieux déguise la cause en symptôme** ;
  une **protection qui s'annule** doit se COMPTER ; un **invariant tacite** finit par être faux
  (« retirer les accents conserve la longueur » : pas devant un accent COMBINANT).
- **Une sortie REDIRIGÉE n'est pas une console** (15/08) : `import server` mourait d'un
  `UnicodeEncodeError` dès que stdout était un tuyau (cp1252). Corriger la POLITIQUE D'ERREUR.
- **Un référentiel générique nomme mal le particulier** (14/08) : `cities1000` a nommé le domicile
  d'après la commune voisine (1 257 photos). Prévoir la reprise en main humaine.
- **Chercher un défaut en trouve un autre, plus gros** — la mesure faite pour CLASSER une piste
  de 62 photos en a exhumé 714 (14/08) ; un correctif d'une ligne a exhumé un import mortel sous
  redirection (15/08) ; un banc censé trancher une re-passe a mesuré le prompt de PROD (16/08) ;
  compter les dates de scan a montré un trou dans le garde-fou (17/08).
- **Une approximation DÉCLARÉE finit par se voir, et c'est le BANC qui a tort** (19/08) : sous UTC,
  deux des six divergences « vue ↔ champ écrit » étaient des photos prises à 00h06 et 00h40. Sous
  `TZ=Europe/Zurich` : 4, toutes réelles. Une note en tête de rapport ne suffit pas — relancer sous
  le bon fuseau coûte dix secondes et transforme la note en mesure.
- **Fragilité du corpus** : clés corrompues et mutations concurrentes ont invalidé des runs ;
  `--mesurer` alerte au-delà de 15 % de clés mortes — le banc aussi.

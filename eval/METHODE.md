# Méthode — invariants à ne pas réapprendre

> Sorti de `eval/DECISIONS.md` le 16/08/2026 : ce registre-là dit **ce qui a été
> tranché**, celui-ci **comment on tranche**. Chaque ligne a été payée par une
> mesure ratée ou une panne muette ; la date dit laquelle. À lire en début de
> session, avec `ROADMAP.md` et `eval/DECISIONS.md`.

- **Circularité de l'auto-évaluation** : un système qui apprend de ses décisions contamine son
  banc. Vérité terrain = **confirmations humaines** seules.
- **Comparaison à armes égales** : vérifier ce que chaque modèle *reçoit vraiment* (30/07). Et
  **un banc qui RECOPIE la prod mesure autre chose qu'elle** (14/08) : il l'IMPORTE.
- **Un proxy n'est pas le juge final** : ils disaient « V2 ≈ V0 », l'humain a tranché. Noter à
  l'aveugle. Un bon score MOYEN n'est pas un feu vert : le coût des faux rejets prime.
- **Ordre imposé (`vision-eval`)** : hypothèse + protocole *avant* de mesurer, puis décider et
  câbler. **Un écart de 5 photos n'est pas un vainqueur** (14/08) : 25-15 sur 40 → p = 0,15.
  Dimensionner le banc AVANT.
- **Un critère est un ET, et c'est l'OUTIL qui l'applique** (16/08) : `--depouiller` testait la
  préférence puis imprimait « vérifier les hallucinations ». Sur les vraies notes il aurait
  affiché « écart démontré » alors que les hallucinations avaient doublé. Un critère écrit
  d'avance que l'outil n'applique pas est une intention, pas un critère.
- **Une préférence globale peut être portée par une seule strate** (16/08) : 63,9 % au total,
  mais 83 % sur les 30 pièges et **59 %, sous le seuil, sur les vraies photos**. Dépouiller par
  strate n'est pas un raffinement, c'est la mesure.
- **Comparer deux TOTAUX jette l'appariement** (16/08) : les deux variantes voient la même
  photo. 24 contre 13 en totaux ; 15 contre 4 en discordantes, p = 0,019. Le signal est dans
  les paires.
- **Un échantillon figé fige des CHEMINS, pas des photos** (15/08) : un rangement par année a
  tué 43 % des clés du banc, qui a tourné 25 min sur 57 % de l'échantillon sans le dire. Suivre
  le renommage (re-clé) ; ne jamais régénérer.
- **Mesurer la matière première avant de bâtir dessus** (13/08), et **par le chemin de code de
  la DONNÉE, pas par une vue** (14/08) : par clé, 0 % devenait 60 %. **Un avant/après n'existe
  que si l'AVANT a été enregistré** — sinon, tautologie.
- **« Le fichier existe » ne dit pas « il sera repris »** (17/08) : 91 photos bien
  présentes, mais dans un dossier caché hors de toute racine scannée — aucun scan ne les
  reprendrait, donc muettes à vie. Répliquer la règle de SÉLECTION du producteur, pas
  seulement tester l'existence.
- **Une limite ÉCRITE n'est pas une limite gérée** (17/08) : `tagging_meta.date_fiable` annonçait dans sa propre docstring que le scanner remplissant `DateTimeOriginal` passait au travers. Vrai, assumé, sans conséquence — jusqu'au chantier qui rend la limite coûteuse. Ici le renommage : ce qui n'était qu'une photo mal triée devenait un NOM DE FICHIER en 2007 sur un tirage de 1990. Relire les limites documentées à l'entrée de chaque chantier qui écrit.
- **Deux gestes réversibles enchaînés ne sont pas réversibles** (17/08) : renommer en 2007 puis ranger par année déplace la photo dans `2007/` — et le dossier `1990_Achumani`, dernier témoin du fait humain, disparaît. Juger la réversibilité de la CHAÎNE, pas du geste.
- **La direction d'un écart porte le sens** (17/08) : une date EXIF postérieure au dossier est un artefact de scan ; antérieure, c'est l'EXIF qui corrige un dossier d'import. Même écart, deux verdicts opposés — un garde-fou symétrique aurait détruit les 20 bonnes corrections en sauvant les 12 mauvaises.
- **Un compte spectaculaire est d'abord une erreur de clé** (15/08) : `vectors` contre `tags`
  sans filtrer le `kind` annonçait 86 181 orphelins ; le vrai chiffre : 2 374.
- **Un chiffre devient une mesure quand deux chemins y tombent** (15/08) : `sans_date` = 3 824
  et 260, annoncés par le serveur vivant ET retrouvés sur une COPIE de la base.
- **Quatre façons de perdre une capacité en silence** : un **effet de bord à l'import**
  s'exécute chez tous ceux qui LISENT le fichier ; un **repli silencieux déguise la cause en
  symptôme** ; une **protection qui s'annule** doit se COMPTER ; un **invariant tacite** finit
  par être faux — « retirer les accents conserve la longueur » est faux d'un accent COMBINANT,
  et « éte 2015 » se coupait en « éte 5 » sans lever d'erreur (15/08).
- **Une sortie REDIRIGÉE n'est pas une console** (15/08) : `import server` mourait d'un
  `UnicodeEncodeError` dès que stdout était un tuyau (cp1252). Corriger la POLITIQUE D'ERREUR,
  pas l'encodage.
- **Un référentiel générique nomme mal le particulier** (14/08) : `cities1000` a nommé le
  domicile d'après la commune voisine (1 257 photos). Prévoir la reprise en main humaine.
- **Chercher un défaut en trouve un autre, plus gros** — la mesure faite pour CLASSER une piste
  de 62 photos en a exhumé 714 (14/08) ; un correctif d'une ligne a exhumé un import mortel
  sous redirection (15/08) ; un banc censé trancher une re-passe a mesuré le prompt de PROD
  (16/08).
- **Fragilité du corpus** : clés corrompues et mutations concurrentes ont invalidé des runs ;
  `--mesurer` alerte au-delà de 15 % de clés mortes — désormais le banc aussi.

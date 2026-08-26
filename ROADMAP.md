# Feuille de route — MediaLibrary

Carte des **priorités**, rien d'autre. Les récits de travaux terminés vivent
dans **git** ; les rejets dans `eval/DECISIONS.md` (photothèque) et
`docs/DECISIONS_OUTILLAGE.md` (canaux, pilotage, livraison) ; la méthode dans
`eval/METHODE.md` ; l'éphémère dans `PROMPT_NOUVELLE_SESSION.md`. Audits :
`docs/AUDIT_INTERNE_2026-08.md`, `docs/AUDIT_EXTERNE_2026.md`, `docs/RANGEMENT_2026.md`.

## État (26/08/2026, session 49) — `gallery` ADOPTE, ET LE CHIP EST FINI

**Sept pages sur onze reçoivent `components.css`**, et `gallery` — la page la
plus utilisée — en fait partie. Ce n'est pas un rangement : c'est la fin de la
divergence du chip.

**Le chip canonique était INCOMPLET, et deux pages l'avaient réparé chacune
de son côté.** `components.css` ne donnait pas de `font:` à `.chip`. Or un
`<button>` n'hérite pas de `body` : il prend Arial 13,3 px. `subjects` et
`gallery` avaient donc écrit `font: 500 var(--t-sm)/1 var(--f-texte)`,
**à l'identique et sans se concerter** — exactement le critère que la feuille
commune se donne pour promouvoir un vocabulaire. Livrer un composant
« canonique » qui n'est complet qu'accompagné d'une règle locale, c'est
programmer la divergence de la page suivante.

| | avant | après |
|---|---|---|
| pages adoptantes | 6/11 | **7/11** |
| déclarations lues, `subjects` | 396 | **384** |
| déclarations lues, `gallery` | 624 | **590** |
| **gagnantes changées après la cascade** | — | **2, toutes deux voulues** |

**`subjects` : 12 déclarations en moins, 383 gagnantes des deux côtés, ZÉRO
écart après la cascade.** Douze lignes qui recopiaient la feuille commune :
deux endroits où changer le même chip.

**`gallery` : `.pchip` était un ALIAS EXACT de `.chip`** — même bloc, même
état, un seul usage. Retiré ; 20 déclarations disparaissent et l'instrument
les compte INERTES (plus aucun élément ne les porte). Les deux seuls écarts
réels sont voulus : le compteur `.n` passe du graphite plein à l'opacité 0,7
de la feuille commune — **ce que `subjects` montre déjà**.

**Observé en réel** : 67 chips sur `/files`, tous `<button>`, tous à 44 px,
police canonique, `gap` 8 px, compteur en monospace à 0,7 ; Entrée sur
`personne:Florine` filtre 20 vignettes à 8, `aria-pressed` passe à `true`,
le fond devient `#448172`.

### Le banc a signalé sa propre configuration périmée

`verifier_pages_composants` a rendu ROUGE avant qu'on pense à le mettre à
jour : « une page NON convertie reçoit la feuille commune ». C'est le
comportement voulu — une page non déclarée qui reçoit la feuille est
indiscernable d'un opt-in cassé. `/files` rejoint les adoptantes.

### Deux instruments lisaient la PROSE d'une feuille de style

**Un commentaire est de la prose, quel que soit le langage** — sixième fois.
`gallery` documentait sa conversion en citant `<button>` et `<span>` dans un
commentaire CSS. `verifier_cibles` y lisait deux cibles : il annonçait
**223** cibles là où il y en a **221**. Et le rouge PROVOQUÉ sur
`verifier_controles` a montré qu'il avait le même trou : un
`<span onclick="f()">` cité en commentaire CSS y comptait comme un grief de
niveau A. Les onze pages n'en portaient aucun — **à un `onclick=` près**.
Une feuille de style ne porte pas de balise : son contenu est écarté, par
une règle de lecture unique (`verifier_controles.sans_le_css`) que les deux
instruments partagent. Une règle de lecture écrite deux fois est une
divergence qui attend son heure.

## État (26/08/2026, session 48) — LE PLANCHER TACTILE ÉTAIT UN VŒU

**Le point 3 du plancher a son instrument, et c'est le troisième point sur
sept qui trouve un manquement réel au premier lancement.** Contraste (25/08),
contrôles (26/08), cibles (26/08) : trois pour trois. **Une règle qu'on ne
mesure pas n'est pas un plancher, c'est une intention** — et cette phrase
n'est plus une leçon, c'est un compte.

`verifier_cibles.py` (neuf, famille `verifier_`, lecture seule, 52 tests)
apparie chaque élément interactif des onze pages à sa hauteur DÉCLARÉE, dans
la cascade à quatre étages, et compare à `--touch`.

| sur les onze pages | avant | après |
|---|---|---|
| cibles lues | 192 puis **223** | **223** |
| plancher déclaré, honoré, ≥ 44 px | 88 | **112** |
| **sous le plancher** | **3** | **0** |
| **inertes** (déclaré, mais le `display` l'ignore) | **2** | **0** |
| non décidables | 21 | **10** |
| hauteur NON DÉCLARÉE (le contenu décide) | 59 | 68 |
| exemptées (déclarée, hors-écran, non peinte, lien en ligne) | 27 | 33 |

**192 puis 223 : le banc ne lisait que le HTML.** `document.createElement`
bâtit **49 contrôles** sur les onze pages, dont **12 dans `gallery`** — la
page la plus utilisée. **31 cibles n'existaient pas pour lui**, et il rendait
« 0 sous le plancher » sur deux règles qui étaient sous le plancher. **Ne pas
voir une cible ne la rend pas conforme : ça retire seulement le
dénominateur.** C'est le septième rouge, et le plus grave.

**Ce qui était cassé, et c'est le même motif que le chip du 26/08 :**
`subjects` adopte `components.css` — donc `.btn { min-height: var(--touch) }`
— **puis annule ce plancher** sur deux boutons avec
`.ctype h3 .btn { min-height: 0 }`. Une règle que le système s'écrit à
lui-même et ne tient pas ailleurs n'est pas une règle. Retirée : les deux
boutons « Rafraîchir » passent à 44 px, **observés à 44 px sur le serveur
vivant**, et **quinze boutons cessent d'être NON DÉCIDABLES** — dans un
fragment assemblé en JS, rien ne disait si l'ancêtre `.ctype h3` était là,
donc `0` et `--touch` restaient deux lectures possibles. **Une seule règle
en trop rendait douze boutons illisibles à leur propre instrument.**

**Ce que la lecture du JS a fait tomber ensuite, et qui dormait depuis
toujours :**

- **`gallery` déclarait `.mchip { min-height: 32px }` sur des `<a>` bâtis en
  JS** — donc `display: inline` par défaut, et **un élément inline non
  remplacé ignore `min-height`**. La règle était écrite, elle était lue, et
  elle ne faisait rien : les chips de motif faisaient la hauteur de leur
  texte. Même piège que les chips en `<span>` de la session 47, un étage plus
  bas. Passés en `inline-flex` + `--touch` : **observés à 44 px sur le
  serveur vivant**, à la hauteur exacte des chips de tags voisins.
- **Les deux boutons « Annuler » des toasts** — `gallery` (`.gtoast .b`) et
  `browse` (`.fxtoast .b`) — étaient à **36 px**. C'est le bouton qui annule
  une action DESTRUCTIVE différée de 10 s : celui qu'il faut viser vite. Dans
  `browse`, la barre d'actions juste au-dessus tenait le plancher et le toast
  ne le tenait pas — **même bouton, même geste, deux hauteurs**.

**La loupe des vignettes d'animaux (26 px) reste, et se DÉCLARE** — tranché
par Mike le 26/08. Elle est le seul chemin vers la visionneuse, donc pas
redondante ; mais une pastille de 44 px sur une vignette de ~160 px mange un
quart de l'image. Les deux décisions du jour ne se contredisent pas : le chip
de filtre est un geste RÉPÉTÉ du tri, la loupe est accessoire.

**La case à cocher de 18 px de `people` n'est pas un défaut, et ça se
DÉCLARE** : c'est un indicateur posé sur une vignette ; la cible est le
`<label class="prop">` entier. `/* cible: hors-portee -- raison */`, à côté
du code, jamais en dur dans l'instrument. Une seule déclaration sur les onze
pages.

### L'instrument s'est corrigé SEPT fois, sur sept rouges OBSERVÉS

Jamais sur une hypothèse. Les sept sont gravés dans `test_verifier_cibles.py`
(62 tests, **trois mutations posées, trois vues**).

| ce qui le trompait | ce qu'il rendait | correction |
|---|---|---|
| il comparait le TEXTE de deux valeurs | **52 non-décidables sur 192**, dont aucune ne l'était : `44px` et `var(--touch)` sont la même hauteur | ce qui doit s'accorder n'est pas la valeur, c'est le **VERDICT** |
| il jugeait un sélecteur descendant sur son seul SUJET | cinq boutons de 44 px accusés d'en faire 36 (`.actbar .b` contre `.fxtoast .b`, même poids) | l'imbrication du HTML statique est LUE |
| `calc(var(--touch) + var(--e-2))` | non décidable | une addition de pixels se calcule |
| un fragment JS était traité comme sans contexte | `.prop input { height: 18px }` mis au débit d'un `<input type="number">` cent lignes plus loin | la chaîne d'ancêtres d'un fragment est PARTIELLE : elle prouve, elle ne réfute pas |
| une seule règle non prouvable était AFFIRMÉE | « trop petit » là où « pas de plancher » | quand rien n'est prouvé, que RIEN ne s'applique reste une lecture |
| une déclaration liait tout dans un rayon d'octets | le bouton « Valider » exempté par la déclaration de la case voisine | une déclaration couvre le PROCHAIN élément, un seul |
| il ne lisait que le HTML | **31 cibles invisibles**, dont les douze contrôles que `gallery` bâtit en JS — et « 0 sous le plancher » sur deux règles qui l'étaient | `document.createElement` est lu, de la création à la prochaine affectation du même nom |

**Le deuxième est le plus instructif : sans l'ancêtre, deux règles de même
poids rendent un verdict au HASARD.** « La dernière écrite gagne » n'est
vrai que si les deux s'appliquent. Un verdict tiré à pile ou face est pire
qu'un aveu d'ignorance : il fait corriger ce qui va bien.

### Le verdict a DEUX chiffres, et ils ne disent pas la même chose

**0 manquement prouvé** ; **68 cibles dont le plancher n'est pas DÉCLARÉ**.
La seconde moitié n'est pas un feu vert — c'est là où l'instrument s'arrête
(une hauteur qui vient du contenu demande le navigateur, pas le texte) **et
c'est, page par page, là où `components.css` n'est pas adopté** :

    browse 0/7 · faces 1/2 · gallery 17/32 · map 14/16 · reglages 7/33
    contre  people 11/48 · pets 10/29 · residu 1/6 · subjects 3/35 · tranche 0/6

**La convergence du design system a maintenant un chiffre qui la réclame.**

### Deux angles morts assumés, dits dans le rapport

La **LARGEUR** n'est pas lue : elle vient du texte et serait « non déclarée »
partout. Les **liens en ligne** (27) sont une catégorie NOMMÉE — exception
WCAG 2.5.8 — que l'instrument ne sait pas distinguer d'un lien servant de
bouton : à relire à l'œil, une fois. Même forme que le « SÉMANTIQUE, PAS
NIVEAU A » de `verifier_controles`.

### Une portée qui se sous-estime fait re-faire un correctif qui existe

`verifier_controles.py` déclarait encore, dans son docstring ET dans sa
sortie, que les littéraux d'expression régulière JS ne sont pas distingués
d'une division — **alors qu'il les distingue depuis le 26/08**, c'était sa
quatrième correction. Corrigé des deux côtés. Le paragraphe reste, pour ce
qu'il enseigne : nommer un angle mort dit où l'on ne voit pas ; le fermer
demande de RÉÉCRIRE ce qu'on a nommé.

### ✔ L'action en attente est LEVÉE

La skill `photo-ui` du COMPTE est enregistrée et **identique au fichier du
dépôt** (md5 `0389708e…`, 18 776 o, vérifié des deux côtés). Deux sessions
d'attente closes. Une session qui s'y fie ne réintroduit plus `#4A8C7B`.

## État (26/08/2026, session 47) — UN CONTRÔLE QUI N'EN ÉTAIT PAS UN

**Le chantier de l'accessibilité des contrôles est CLOS, et il a son chiffre.**
`verifier_controles.py` (neuf, famille `verifier_`, lecture seule,
**42 vérifications**) apparie chaque élément CLIQUABLE à la balise qui le
porte — attribut `onclick` écrit, `onclick` dans une chaîne HTML assemblée en
JS, gestionnaire posé en JS — et compte ce qui n'est pas un contrôle.

| sur les onze pages | avant | après |
|---|---|---|
| gestionnaires de clic | 154 | 154 |
| posés sur un contrôle **natif** | 132 | **138** |
| rendus opérables à la main (`role`+`tabindex`+clavier) | 0 | 3 |
| **déclarés redondants dans la source** | — | 13 |
| **griefs de niveau A (WCAG 2.1.1)** | **18** | **0** |
| cibles non remontées | 1 | 0 |

**`subjects` sortait blanche des deux côtés** — elle écrivait déjà
`<button class="chip" aria-pressed>`. C'est ce qui rendait la divergence
lisible : elle n'est pas visuelle, elle est SÉMANTIQUE, donc invisible à
l'écran comme à une relecture qui ne la cherche pas.

**Ce qui était réellement cassé, par ordre de gravité :**

- **le filtre de la page la plus utilisée.** `gallery` fabriquait ses chips de
  tags ET de personnes en `createElement('span')` + `.onclick` : ni focus, ni
  clavier, ni annonce. Cinq chips convertis en `<button aria-pressed>`.
- **ouvrir une photo était un geste de SOURIS.** La cellule de la planche
  contact n'avait aucun chemin clavier — 43 000 photos.
- **sélectionner une photo d'animal** (`pets`), **ouvrir la fiche d'un
  animal**, **choisir une photo de référence** (`people`) : idem.

**Trois éléments gardent leur mise en page et reçoivent les trois marques**
(`tabindex`, `role="button"`, `keydown` Entrée + Espace avec
`preventDefault`) au lieu d'un `<button>` : une vignette porte une image, une
ligne de faits et une légende — c'est-à-dire des `<div>`, qu'un bouton lirait
**tous** comme son libellé. Un bouton qui s'annonce sur trois lignes n'est pas
un progrès.

### Ce qui ne se DÉCIDE pas se DÉCLARE — dans la source, avec sa raison

Dix des dix-huit griefs n'en étaient pas : une bande latérale à côté d'un
bouton « Suivant », une croix à côté d'Échap, une carte cliquable qui CONTIENT
déjà son bouton « Gérer ». La fonctionnalité existe au clavier ; l'élément
reste un `<div>`, et WCAG 2.1.1 porte sur la fonctionnalité.

Cette exception **ne se calcule pas** : elle demande de savoir qu'un autre
chemin existe. Elle se déclare donc à côté du code —
`/* controle: redondant -- raison */`, ou `natif` quand la cible est un vrai
contrôle que l'instrument ne sait pas remonter — **jamais en dur dans
l'instrument, sinon il devient aveugle au cas suivant sans qu'on le sache**.
C'est la règle que `verifier_contraste` s'est donnée le 25/08, appliquée au
même problème. Les treize sont COMPTÉES et listées : une exception qui
prolifère n'en est plus une.

### L'instrument s'est corrigé SIX fois, sur six rouges OBSERVÉS

Jamais sur une hypothèse. Les six sont gravés dans `test_verifier_controles.py`.

| ce qui le trompait | ce qu'il rendait | correction |
|---|---|---|
| `var b = getElementById(…)` puis `b.onclick` — **119 fois** sur les onze pages | non décidable | table des alias |
| le `<` d'une comparaison JS (`1<t`) | une balise `<t>` inventée, sur de l'arithmétique | le HTML ne se cherche que dans les CHAÎNES |
| `a.href` posé en JS | « lien hors tabulation » sur un lien qui y est | ce qu'une balise porte ne se lit pas qu'au même endroit |
| **`/[&<>"]/g`** en tête de `subjects` | le `"` de la regex ouvrait une fausse chaîne : un bouton écrit cent lignes plus bas cessait d'exister | un scanner qui distingue regex et division |
| `querySelectorAll('.chip').forEach(c => …)` | la page qui fait CORRECTEMENT ses chips passait pour non décidable | le paramètre du rappel EST l'élément |
| `button.btn--principal`, `.actes .btn` | non décidable | un sélecteur écrit sa balise ; le dernier segment décide |

**Le quatrième est le plus instructif : mon propre docstring nommait les
littéraux d'expression régulière comme un angle mort THÉORIQUE.** Il était
réel et il mordait. **Nommer un angle mort dit où l'on ne voit pas ; ça ne
fait pas voir.**

### Le chip passe à 44 px — la contradiction que le système portait

`components.css` donnait `min-height: 32px` au chip pendant que son propre
plancher exigeait « cibles ≥ 44 px ». 32 px passe WCAG 2.5.8 (24 px), donc
rien n'était faux — mais **une règle que le système s'écrit à lui-même et ne
tient pas ailleurs n'est plus une règle, c'est une intention.** Mike a tranché
le 26/08 : une seule, partout (`components.css`, `subjects`, `gallery`).
Observé en réel : le chip fait exactement la hauteur du champ de filtre à
côté de lui — l'alignement était cassé par la contradiction.

**Changements visuels volontaires, à l'œil de Mike** : les chips de `gallery`
passent de 32 à 44 px et de la graisse 400 à 500 (le `font:` canonique) ;
l'écart libellé-compteur passe du `margin-left` de 4 px au `gap` de 8 px,
comme sur `subjects` — une seule façon d'écarter deux choses.

**Preuves, dans cet ordre** : `verifier_css_cascade --page` sur les trois
pages au CSS touché (gallery 4 disparues / 10 apparues / 4 changées, subjects
1 changée, people 7 apparues — **toutes attendues, aucune parasite**) ;
`verifier_contraste` 24/24 ; 157 tests UI verts ; le banc des pages
composants vert sur le **serveur vivant** ; et l'observation au clavier dans
Chrome — Entrée sur `personne:Florine` filtre 20 photos à 8, anneau de focus
visible, Entrée sur une vignette ouvre la visionneuse sans faire défiler la
page.

**Les pages `ui/pages/` sont relues À CHAUD** (signature mtime + taille) : les
six pages ont changé de taille sur le serveur sans redémarrage. Seul
`server.py` l'exige.

**L'action qui attendait Mike est LEVÉE le 26/08 (session 48)** : la skill
`photo-ui` du compte est enregistrée et identique au fichier du dépôt.
Ce qu'elle a coûté, pour mémoire : deux sessions à travailler avec une
référence dont on savait qu'elle mentait.

## Ce qu'il faut garder de la session 46 (le récit vit dans git)

- **Le CSS commun ne valait pas le chantier, et c'est sa PREUVE qui l'a tué** :
  200 déclarations hissables sur 1 754, dont 171 partagées par deux pages
  seulement — **6,2 Ko sur 67**. Ne pas reproposer l'extraction.
- **Le vrai sujet était la DIVERGENCE** : `.btn` ne voulait pas dire la même
  chose selon la page. `components.css` existe pour ça, en **opt-in** page par
  page (`<!--UI:components-->`, placé AVANT le `<style>` de la page pour
  qu'elle garde le dernier mot). **6 pages sur 11 ont adopté ; le `.btn` est
  FINI** — les cinq restantes n'en ont pas. Trois l'écrivaient sous d'autres
  noms (`.prim`/`.warn`, `.primary`/`.danger`).
- **Les trois universelles** (`body{background|color|font-family}`) vivent dans
  `base.css` seul — elles étaient trois, pas six : le reset `*` ne vit que dans
  NEUF pages, et neuf sur onze ne se hisse pas sans preuve page par page.
- **L'ordre de la cascade a QUATRE étages** : `components.css` → la page →
  `tokens.css` → `base.css`. `--apres` prend la feuille commune EN PREMIER,
  sinon elle gagne une cascade qu'elle ne gagne pas en vrai.
- **Le plancher AA est devenu une mesure** : trois échecs trouvés au premier
  lancement, `--fixateur` assombri `#4A8C7B` → `#448172`, destructif passé au
  plein (5,34:1 sans toucher au token). `--salle-4`, `--fixateur-p`,
  `--encre-p`, l'état pressé hors du garde `hover` et `.hors-ecran` sont
  canoniques (approuvés par Mike).
- **Niveau A, déjà corrigé le 25/08** : les deux `<input type="file">` de `/`
  étaient en `display:none` derrière des `<label for>`.
- **Le chantier XMP est clos** : 0 écart sur 1 614 couples (Wilson 0,0–0,2 %).

## Priorité (26/08/2026, refixée session 48) — la convergence a un CHIFFRE

**`gallery` a adopté le 26/08 (session 49) — reste QUATRE pages** : `browse`,
`faces`, `map`, `reglages`. Et l'adoption seule ne suffit plus : sur les 16
cibles sans plancher de `gallery`, aucune n'est un chip — ce sont ses boutons
maison (`.tb`, `.geobtn`, `.fchip`, `#lb-*`). **Le prochain gain n'est pas
d'ajouter le marqueur, c'est de converger les NOMS vers `.btn`** — et ça, ça
change ce qu'on voit : c'est un choix de Mike, pas un rangement.

**Ce qui prenait la tête : les cinq pages qui n'avaient pas adopté
`components.css`.** Ce n'était jusqu'ici qu'un rangement à moitié fait ;
c'est devenu une mesure. Les 59 cibles dont le plancher tactile n'est pas
déclaré vivent **à 39 sur 68 dans ces cinq pages-là** (browse 0, faces 1,
gallery 17, map 14, reglages 7). Adopter la feuille commune ne range pas du CSS : ça
DÉCLARE un plancher là où il n'y en a aucun, et ça rend mesurable ce qui ne
l'est pas. **`gallery` d'abord** — c'est la page la plus utilisée, elle écrit
déjà le chip canonique sous ses propres noms, et elle porte 17 des 39.

Ensuite : le reste d'audit (O8–O9, O11, O13–O15 ; **I1** visible dans
`/reglages`), puis le point 7 (l'extraction `ui/`, dont il ne reste que le
CSS commun de chaque page).

**Le point 3 du plancher est CLOS côté instrument** (session 48). Les trois
points du plancher qui avaient un instrument en ont trouvé un manquement
réel au premier lancement, trois fois sur trois. **Les quatre autres n'en ont
toujours pas** : mouvement réduit (4), sémantique (5) — partiellement couvert
par `verifier_controles` —, navigation clavier des tâches répétitives (6),
états vides et erreurs rédigés (7). Le pari le plus rentable des trois
dernières sessions a été d'instrumenter un vœu ; il reste quatre vœux.

Choix de Mike (25/08) : le Takeout Google et l'hébergement Infomaniak sont
**décidés et chiffrés**, il ne leur manque que du temps de transfert. Ils
passent donc **après** le code.

Ce n'est pas un renoncement : rien n'est exposé de plus qu'hier, et les deux
points sont écrits assez précisément dans `PROMPT_NOUVELLE_SESSION.md` pour
être exécutés sans les rouvrir.

## État (25/08/2026, session 46) — libérer Google sans rien perdre

**`verifier_photos_google.py`** (neuf, famille `verifier_`, lecture seule,
19 vérifications) répond à la seule question qui autorise à effacer 75 Go chez
un tiers : **pour chaque photo que Google détient, le NAS la porte-t-il ?**

**Pourquoi un export Takeout et pas l'API.** Depuis le **31 mars 2025** l'API
Google Photos ne laisse plus une application tierce voir que ce qu'elle a
elle-même envoyé — rclone le dit noir sur blanc. Aucun outil ne peut énumérer
la photothèque à distance. Takeout, lui, dépose à côté de chaque média un
`.json` portant son **nom d'origine** et sa **date de prise de vue** : deux
choses que le nom exporté peut avoir perdues (Takeout tronque les noms longs
et suffixe les collisions). Se fier au nom du fichier ferait déclarer ABSENTES
des photos que le NAS porte — c'est le premier test du banc.

**Quatre verdicts, un seul autorise.** CERTAIN (même nom, même taille) ·
PROBABLE (taille différente : Google a ré-encodé en mode économiseur) ·
AMBIGU · **ABSENT — et un seul ABSENT interdit tout**. Le rapport écrit
alors NE RIEN EFFACER, et le code de sortie vaut 1 : un banc qui rendrait 0
sur un fonds incomplet serait un feu vert.

**Ce qu'il ne voit pas, et qui compte** : une photo arrivée chez Google par un
autre chemin — album partagé, WhatsApp, le téléphone de quelqu'un d'autre —
n'a aucune raison d'être sur le NAS. Elle sort ABSENTE, et c'est un ordre de
COPIE, pas un écart à écarter.

## État (25/08/2026, session 45 quater) — la copie hors site est SPÉCIFIÉE

**Le point 12 bis n'attend plus qu'un geste.** Tout ce qui manquait est mesuré
ou vérifié :

| | |
|---|---|
| à sauvegarder | **290,9 Go** (109 photos + 180 vidéo) + ~300 Mo de décisions |
| source | NAS **Synology DS224+**, DSM 7.3.2 (7.4.1 en attente) |
| cible | **Infomaniak Swiss Backup**, Hyper Backup/Swift, ~**CHF 6 TTC/mois** pour 1 To, données en Suisse ×3 |
| ligne, mesurée | **22,4 / 13,8 Mbit/s** — premier envoi **~50 h** |
| ligne, CAPACITÉ à l'adresse | **425 / 100 Mbit/s** (fibre seulement entre déc. 2027 et mars 2028) |
| ligne, offre à +CHF 1/mois | **100 Mbit/s** — premier envoi **~8 h**, une nuit |

**Le débit décide, pas l'hébergeur.** La ligne peut déjà donner sept fois plus
en montée que ce qu'elle donne : ce n'est pas une limite physique, c'est le
plafond de l'abonnement. Un franc par mois achète un facteur 7 sur le seul
chiffre qui rend cette sauvegarde faisable ou non.

**Le débit n'est PAS un préalable.** À 13,8 Mbit/s le premier envoi tient en
**~8 nuits** (photos ~3, vidéos ~5), avec une limite de débit pour ne pas
étrangler la ligne ; ensuite les deltas quotidiens sont de quelques minutes.
Passer à 100 Mbit/s ramène le premier envoi à une nuit — c'est du confort, pas
une condition. **Ne pas attendre l'abonnement pour commencer la sauvegarde.**

**Et un compte Google à 96 % — 3,8 Go de la panne.** `one.google.com` :
**96,23 Go sur 100**, dont **Google Photos 75,03**, Gmail 12,82, Drive 1,13,
divers 7,2. Quand le quota est plein, **Gmail cesse de RECEVOIR**. Deux
conséquences : (1) résilier Google One est impossible en l'état — hors Photos
le compte pèse déjà **21,2 Go**, contre 15 Go gratuits ; (2) les 75 Go de
Google Photos sont un DOUBLON de ce que le NAS reçoit déjà par
`_Uploads` — les libérer ramène le compte à ~21 % pour le même CHF 2/mois.
Ordre impératif : vérifier que le NAS a bien les photos AVANT d'effacer quoi
que ce soit chez Google (l'app Photos efface aussi du téléphone quand la
synchro est active).

## État (25/08/2026, session 45 ter)

**La copie hors site a une cible, un prix et un obstacle chiffré.** NAS
**Synology DS224+** → **Infomaniak Swiss Backup** par **Hyper Backup/Swift**,
~**CHF 6 TTC/mois** pour 1 To (CHF 4,18/To + CHF 1,84/appareil, −10 % annuel),
données en Suisse. L'obstacle n'est pas le prix : c'est le **lien montant
mesuré à 13,8 Mbit/s** — 291 Go = **~50 h de ligne saturée** au premier envoi.
L'offre du même opérateur à **+CHF 1/mois donne 100 Mbit/s symétriques** et
ramène l'envoi à **~8 h**. Le débit, pas l'hébergeur, est ce qui décide de la
faisabilité — et c'est le seul point où un franc par mois achète un facteur 7.

## État (25/08/2026, session 45 bis)

**Le fonds est MESURÉ, et la copie hors site cesse d'être une opinion.**
`inventaire_fonds.py` (neuf, famille `inventaire_`, lecture seule, 14
vérifications) : **76 947 fichiers, 290,9 Go** — **109 Go de photos** (73 079
fichiers) et **180 Go de vidéos** (2 453 fichiers). **62 % du poids dans 3 %
des fichiers.** Le tiers des décisions humaines pèse ~300 Mo.

**Et la première version de l'instrument s'est fait tuer par le plafond du
banc** : `os.walk` + `os.path.getsize` demande un aller-retour SMB PAR FICHIER
pour une réponse que l'énumération du dossier portait déjà — plus de 600 s.
`os.scandir` rend la même mesure en **193 s**. Sur un disque local la
différence ne se verrait pas ; c'est le réseau qui la fait.

## État (24/08/2026, session 45)

**LE CHANTIER DES XMP EST CLOS, à zéro.** `verifier_xmp_toutes_personnes.py`,
machine calme, mêmes paramètres que la mesure de référence : **1 614 couples
nom–photo lus, 0 en écart, 0 nom en écart — taux 0,0 % (Wilson 0,0 – 0,2 %)**,
contre **255 sur 1 364 (18,7 %, Wilson 16,7 – 20,9 %)** le 23/08 et 0,2 % ce
matin. Les intervalles ne se touchent à aucun moment. Les 21 fantômes effacés, les 13 échecs repris
(3 réécrits, le reste déjà conforme), `Val` rattrapé. Le fonds ne porte plus un
seul nom que l'index connaît et que le fichier ignore.

**Et il n'y a plus un seul fantôme sur le fonds.** `inventaire_fantomes.py`
(nouveau, famille `inventaire_`, lecture seule, lançable au banc) balaie les
deux racines du serveur en 3 min 30 : **0 trouvé**. Il sépare les deux cas —
fantôme dont l'original est intact **à côté** (effaçable sans risque) et
fantôme **sans original** (ExifTool peut être mort entre le remplacement et le
renommage : c'est alors la seule copie qui reste, et l'effacer en lot serait
une perte). **17 vérifications, dont celle qui interdit tout `unlink` dans le
module.**

**`/api/search` rend enfin `total` et `tronque`** — observé en réel :
`total 5898, rendus 1500, tronque 4398`. Ils étaient CALCULÉS puis jetés ;
seule la page `/files?q=` les recevait. Quand le moteur ne SAIT pas — la
branche sémantique classe tout le fonds par cosinus — la route rend `null` et
non `len(results)` : rendre le nombre de résultats ferait passer une page pour
un fonds entier, c'est-à-dire réinventer le plafond muet à l'autre bout.
**8 vérifications neuves, 5 rouges sur l'ancien code**, et
`mesure_recherche_nommee` VÉRIFIE désormais le plafond au lieu de le
commenter : une requête nommée est déterministe, un `total` absent est une
régression que le rapport nomme.

**La mesure calme renverse le verdict d'O7, et le chantier `/api/names` est
FAIT.** Coût fixe du filtre nommé : **139, 141, 146 ms** sur trois passes
calmes (contre 191–208 sous charge) — **mineur**, sous le seuil de 200, à
classer avec son chiffre. C'était bien `/api/names` le sujet : **292 ms**, payés
au chargement de CHAQUE page. La liste des noms ne coûtait rien ; c'est le
COMPTAGE qui balayait les 43 000 fiches et lisait chaque mot-clé, à chaque
appel. Il est mis en cache 60 s — **le compte seulement, jamais la liste** :
un nom créé à l'instant doit paraître tout de suite, sinon on le recrée en
« Nouveau » (c'est le défaut I7). Observé : **281 ms au premier appel, 0,6 ms
ensuite**, avec 364 noms et les mêmes comptes qu'avant (Florine 5 907) —
le cache ne change pas un chiffre.

**Et le banc a crié avant qu'on se réjouisse.** « Un score parfait est une
ALARME » : sur 0,3 ms il a répondu *suspect*, ce qui était juste pour un banc
qui ne connaissait qu'un prix. `/api/names` en a deux depuis le cache — celui
du premier appel après expiration, et celui que paie une page. Le banc les
mesure et les dit séparément ; les fondre dans une médiane ferait deux
mensonges à la fois. **7 vérifications neuves, 7 rouges sur l'ancien code.**

## État (24/08/2026, session 44)

**La réparation du fonds est FINIE.** Relancée à 22:38, terminée à 03:07 :
**18 828 photos balayées, 3 128 réécrites** (181 la nuit d'avant + 2 947),
**13 échecs**, aucun nom sauté. **Et le chiffre est tombé** :
`verifier_xmp_toutes_personnes.py`, machine calme, mêmes paramètres que la
mesure de référence — **0,2 % d'écart** (Wilson 0,1–0,5 %, 5 écarts sur
2 247 couples lus, 352 noms), contre **18,7 %** (Wilson 16,7–20,9 %) le 23/08.
Les intervalles ne se touchent pas. Ordre de grandeur restant : **19 couples**,
contre ~5 800 photos.

**Et le résidu est EXACTEMENT les échecs.** Les 5 noms encore en écart —
Jessica Giallara, Pami, Sabrina Camiolo, Petit, Ismet — sont tous portés par
les 13 photos dont l'écriture a raté. Rien d'autre ne manque : la fuite est
bouchée, l'arriéré est épongé, et ce qui reste a une cause nommée dans un
fichier. Contrôlé nom par nom : **Val 1 091/1 094** (3 manquent, un vrai
rattrapage), **Yann Mamin 13/13** (les deux noms sautés par la passe de 21:38 ;
un seul avait besoin d'être repris).

**Et le fichier de reprise MENTAIT sur les échecs.** Toute photo VUE y était
notée faite, l'échec compris : les 13 photos qui ont raté leur écriture
étaient marquées « faites » et **aucune relance ne les aurait jamais
reprises**. Règle 2 côté reprise : un nom qui n'a pas atterri ne se note pas
atterri. Corrigé — la reprise ne note que ce qui a réussi ; l'échec repasse à
la relance, et lui seul.

**Un échec a maintenant une CAUSE, pas seulement un compte.** La console
disait `en echec : 3`, ce qui ne se répare pas. Les journaux, relus à la main,
disaient tout autre chose : **11 des 13 sont un `_exiftool_tmp` fantôme**
laissé par un ExifTool tué en route, qui **bloque définitivement** la
réécriture de sa photo tant qu'il est là ; les 2 autres sont des JPEG tronqués
(famille des illisibles). Les causes sont désormais comptées et dites, avec le
geste quand il est connu.

**Et les `_exiftool_tmp` ne sont pas un accident, c'est une FUITE
CHRONIQUE.** La liste demandée à Mike en rend **21**, pas 11 — datés du
**06/07 au 24/08**, dont un fabriqué par la réparation de la nuit même, et deux
de 0 octet. Onze bloquaient des photos qu'on savait à réparer ; **les dix
autres bloquaient en silence**, sans figurer dans aucun journal, donc hors de
portée de `--reprendre-echecs`. Le mécanisme : ExifTool recopie la photo dans
`<photo>_exiftool_tmp` avant d'écrire, et **refuse d'écrire tant que ce
temporaire existe**, sans option pour l'écraser — une écriture tuée en route
condamne donc sa photo, définitivement et sans bruit. `--balayer-fantomes`
(jamais par défaut : effacer sur le fonds reste voulu) l'efface et réessaie
UNE fois. **5 vérifications neuves, 5 rouges sur l'ancien code, 92/92 vertes.**

**`--reprendre-echecs`** refait ce que les journaux disent en échec, par
PHOTO, sans rebalayer 18 828 photos pour en retrouver 13 — et sans croire le
journal : les tags sont relus avant d'écrire, comme partout ici.
**Et « jamais deux écrivains » vaut enfin aussi contre soi-même.** Le fichier
tenait cet invariant contre le SERVEUR uniquement : deux passes lancées à la
main, ou une passe et un rattrapage `--nom`, s'ignoraient. Un verrou
d'écriture les fait se voir — preuve par FRAÎCHEUR et non par PID (une fenêtre
fermée laisse un fichier, pas un écrivain ; un verrou de plus de 10 min sans
signe de vie se reprend tout seul), rafraîchi à chaque tranche, rendu dans un
`finally`, et jamais posé par une passe à blanc.
**11 vérifications neuves, 14 rouges sur l'ancien code, 79/79 vertes.**

## État (23/08/2026, session 43)

**Le contrôle 5 de l'agent git cesse de réclamer une preuve qui n'existe pas.**
Il jugeait sur le NOM — tout `.py` sauf `test_`/`mesure_` — et exigeait donc de
`mcp_serveur.py`, `banc_agent.py`, `git_agent.py` lui-même et des familles
`appliquer_`/`verifier_` qu'un serveur les fasse tourner. Le serveur ne les
importe jamais. C'est ce qui obligeait à forcer, et un contrôle qu'on contourne
par habitude ne contrôle plus rien. Il lit maintenant le GRAPHE des imports de
`server.py`, imports paresseux compris : **29 modules dedans, 134 dehors**. Un
import dynamique illisible est un TROU nommé, qui fait retomber sur la vieille
règle, plus large. **17 vérifications neuves, 13 rouges sur l'ancien code,
45/45 vertes sous Windows** — dont quatre sur le VRAI dépôt.

**Et la réparation des XMP est morte au bout de 31 minutes — la cause est
trouvée et bouchée.** Lancée à 21:38, arrêtée à **22:09:40, à 4 800 photos sur
~18 900**, onze secondes après un `🤖 Auto-ajout : 14 visage(s)` du curateur.
Celui-ci rattache des visages TOUT SEUL toutes les quatre à cinq minutes, et
chaque auto-ajout remplit `PERSON_QUEUE` : la passe, qui s'arrêtait au premier
signe, ne pouvait pas finir. Elle **ATTEND** désormais que la file retombe
(patience bornée, temps attendu compté), l'invariant « jamais deux écrivains »
intact — aucune invocation d'ExifTool pendant l'attente. **7 fonctions de test
neuves, 7 rouges sur l'ancien code, 56/56 vertes sous Windows.**

**O7 est MESURÉ, et ce n'est pas lui le sujet.** Le filtre nommé coûte
**191–208 ms** de coût fixe (deux passes, seuil écrit d'avance à 200 ms : le
verdict bascule d'une passe à l'autre — mesure prise pendant que le tagueur
tourne). Mais `/api/names`, appelé au chargement de **chaque** page pour
l'autocomplétion, coûte **359–364 ms** : même index, même balayage, plus
`parse_tag_nomme` sur chaque mot-clé. `mesure_recherche_nommee.py` (21
vérifications) le dit, et signale au passage que `/api/search` **calcule**
`total`/`tronque` et ne les rend PAS — le plafond silencieux corrigé pour la
page le 22/08 et pour le MCP le 23/08 est toujours dans la route.

Gestes de fin de la réparation : `PROMPT_NOUVELLE_SESSION.md`.

## État (23/08/2026, session 42)

**Le canal des bancs portait tout, sauf un nom humain.** Mike nomme le groupe
de « Stéphane Plouvin » ; la preuve DISQUE de son geste —
`verifier_xmp_personnes.py --nom "Stéphane Plouvin"` — est refusée par
`banc_agent` : `ARG_OK` n'admet ni accent ni espace. Le chiffre trouvé en
comptant : **168 des 352 noms, 6 119 photos**, hors de portée du seul
instrument qui vérifie la règle 2 dans les fichiers. Le jeton **`b64:`** rend
la valeur **sans desserrer la porte** — ce qui transite est du base64url,
qu'`ARG_OK` admettait déjà ; les trois barrières jugent la forme écrite ; la
valeur ne renaît qu'APRÈS elles, pour la LISTE de `subprocess.run`.
**11 vérifications neuves, 8 rouges sur l'ancien code**, 32 vertes au banc.

**Et le geste de Mike est PROUVÉ sur le disque.** `personne:Stéphane Plouvin` :
**58 photos à l'index, 58 lues par ExifTool, 58 portent le nom, 0 manque, 0
illisible**, file à 0.

**Puis le canal débloqué a trouvé une FUITE, et c'est le vrai sujet de la 42.**
Un second geste de Mike (confirmation sur Ellie) a fait poser la question au
bon nom : `personne:Ellie` — **342 photos à l'index, 54 dont le fichier ne
porte pas le nom**, file à ZÉRO, donc rien ne viendra les combler. Mike :
**37 sur 200** tirées. Florine : **200/200**. Le balayage de tous les noms
(`verifier_xmp_toutes_personnes.py`, 21 vérifications) tranche :
**18,7 % des couples nom–photo** (Wilson 16,7–20,9 %, 255 écarts sur 1 364 lus,
352 noms) — soit **~5 800 photos** que l'index nomme et que le fichier ignore.
La règle 2 était en défaut depuis des mois, sans une ligne nulle part.

**La cause, et elle est bouchée.** `_enqueue_person_write` testait
`p.is_file()` avant de noter : sur un « non », le geste disparaissait en
silence. Or `is_file()` interroge un partage SMB, qui répond « non » quand le
NAS hoquette. `_file_personnes_reprise` faisait de même AU DÉMARRAGE — le pire
moment, le partage n'étant pas toujours monté : la prudence de la reprise
jetait la file que le journal existait pour sauver. Les deux jugent désormais
zéro ; le seul qui déclare une écriture impossible est celui qui l'a TENTÉE.
**4 rouges observés sur l'ancien code reconstitué**, dont deux tests de la 41
qui affirmaient l'inverse.

**La réparation est PROUVÉE sur un premier lot.** Mike a passé
`appliquer_xmp_personnes.py` sur Ellie : **54 réécrites, 0 en échec**, journal
d'annulation de 54 lignes portant l'état AVANT de chaque photo. Vérifié
ensuite par l'instrument indépendant, qui relit le disque : **346 à l'index,
346 portent le nom, 0 manque** (292 avant). **Débit mesuré : 191 s pour 54
photos, soit 3,5 s/photo** — au-dessus des 2,91 s/op du matin, le NAS étant
chargé. Le reste (~5 700) coûtera donc **~5 h 30**, pas 4 h 40.
**Et l'outil pour le reste est livré** : `appliquer_xmp_personnes.py --tous`
balaie le fonds **par PHOTO** (une photo à deux noms manquants coûte UNE
invocation, pas deux), **reprend** où il s'arrête, et **s'arrête** si la file
du serveur repart — jamais deux écrivains sur les mêmes fichiers.
**13 vérifications neuves, 6 des 7 fonctions rouges** sur le code sans `--tous`
(41/41 vertes après).

**Et le premier lancement réel a trouvé un défaut en trois minutes.** Sur 352
requêtes enchaînées, le serveur en ferme deux (« Remote end closed connection
without response ») : **`Val` — 1 205 photos — a été SAUTÉ**, et ses photos
marquées « faites » parce qu'elles portent un autre nom. La reprise ne les
rattrapait donc jamais. Corrigé : `cles_du_nom` **réessaie trois fois** et
LÈVE si ça échoue encore (rendre une liste vide ferait passer un nom perdu
pour un nom sans photo) ; les noms sautés sont écrits dans
`_corbeille_xmp/_tous_noms_sautes.txt` et **redits à la fin**, la console
défilant cinq heures. **5 vérifications neuves.**

**Aussi vu au lancement, et à ne pas mal lire** : sur les 1 400 premières
photos, **5 réécritures** — 0,4 %, loin des 18,7 %. Le balayage suit l'ordre
alphabétique des CHEMINS, donc les années anciennes d'abord ; les 54 écarts
d'Ellie étaient sur 2022 et 2024. Le taux doit monter à mesure qu'il avance.

## État (23/08/2026, session 41)

**La file XMP ne prend plus onze heures en otage : elle a un journal.** Elle
n'existait qu'en `queue.Queue()` — un redémarrage, une coupure ou un plantage
perdait le travail restant SANS RIEN pour le retrouver, et des milliers de
fichiers auraient gardé `Flo` quand l'index dit `Florine`. Désormais chaque
geste est noté sur disque **avant** d'être enfilé (`_file_personnes.jsonl`) ;
l'écrivain étant unique et consommant dans l'ordre, **une position suffit**
(`_file_personnes.pos`), et au démarrage ce qui est au-delà repart en file. Une
ligne tronquée par la coupure est sautée, une photo rangée ailleurs est suivie
par sa CLÉ, la position avance MÊME sur échec — sans quoi un fichier illisible
serait rejoué à jamais — et ce qui échoue est NOMMÉ
(`_file_personnes_echecs.jsonl`). File vide, le journal se remet à zéro.

**Et le prix n'est plus payé deux fois.** `person_writer` lançait un processus
ExifTool par GESTE, or un renommage en pose deux par photo, coup sur coup. Les
gestes qui se suivent sur la MÊME photo partent maintenant ensemble, en UNE
invocation (`write_person_tags`) ; le dernier geste posé sur un tag l'emporte,
exactement comme deux appels successifs. **21 vérifications neuves, 21 ROUGES
sur l'ancien code**, vertes au banc sous Windows.

**`-stay_open` : le chiffre le range APRÈS le reste.** Mesuré sur 30 photos du
fonds (`mesure_xmp_debit.py`, lecture seule, trois régimes) : un processus par
photo coûte **0,80 s**, `-stay_open` **0,07 s** — 12×. Mais ce 12× est celui de
la LECTURE ; il isole le seul terme que `-stay_open` supprime, le **démarrage
du processus : 0,74 s**. Une écriture réelle coûte **2,91 s/op** (mesurée sur
7 172 s de file vivante), dont la réécriture du fichier sur SMB, à laquelle
`-stay_open` ne touche pas. Gain réel : **2,91 → 2,17 s/op, soit 25 %**, quand
le groupement, lui, valait un facteur 2.

**Vu en chemin, et payé 600 s :** `-q` emporte le `{ready}` de `-stay_open`. Le
banc a attendu sans fin, et la fenêtre des bancs avec lui, jusqu'à ce que
l'agent le tue. Deux parades : `-q` retiré, et **un délai par ordre** — un banc
doit ÉCHOUER, jamais se figer.

**Les quatre branches sont FUSIONNÉES** (23/08, 17:50) : `main`
**8f48b26 → 9df303d** en fast-forward, ce qui emporte d'un coup la chaîne
entière — les trois de la 40 (`fix/la-fiche-est-le-verrou`,
`feat/ce-que-la-file-xmp-doit-encore`,
`feat/reparer-ce-que-la-file-xmp-n-a-pas-fait`) et celle du jour, qui en
descend. Vérifié dans `.git/logs/refs/heads/main`, pas dans le rapport de
l'agent. **Le contrôle 5 avait raison, et il a fini par s'ouvrir tout seul** :
il suffisait que le serveur tourne enfin le code qu'on gravait.

**La file a fini, le serveur a redémarré, et le fonds porte ce que l'index
dit.** 17:45 : `queues.personnes` à 0 après onze heures ; redémarrage, bannière
neuve dans `_journal_serveur.log`, **aucun `THREAD MORT`**, `code_a_jour` vrai.
17:47 : `verifier_xmp_personnes.py` lit 200 fichiers du disque — **200 portent
`Florine`, 0 portent `Flo`** (19 et 119 le matin même). La fusion décidée le
22/08 est ACQUISE, et `appliquer_xmp_personnes.py` n'a rien à réparer.
**Une seule chose n'a PAS été observée** : le journal de la file sur un geste
VIVANT. `_file_personnes.jsonl` naît au premier geste de nom, et il n'y en a pas
eu depuis le redémarrage — l'observer coûte une vraie écriture XMP dans une
vraie photo. Les 21 vérifications tiennent la mécanique (21 rouges sur l'ancien
code) ; le prochain nom attribué produira la preuve gratuitement.

**La photothèque s'ouvre à un agent — et le chantier a trouvé DEUX plafonds
muets, aucun par la lecture du code.** `mcp_serveur.py`
(point 13) n'appelle aucune route neuve : c'est ce qui l'a rendu observable un
jour où `server.py` a changé sous un serveur qui n'a pas redémarré. Le chiffre
du chantier est le COÛT EN CONTEXTE : `/api/people/photos` rend **4 013 486
octets** pour Florine, l'outil en rend **5 775** — **695× moins, 0,14 %
gardé**. Les deux plafonds, eux, se sont vus en OBSERVANT : le mien, qui
annonçait « 5 trouvées » pour `espece:chat` parce qu'il comptait ce qu'il avait
demandé ; et celui de la route, qui rend **2 000** photos pour Florine — elle en
porte **5 909** — sans le dire. `total_est_un_plancher` distingue désormais un
compte d'un plafond atteint. La leçon de la page de recherche (14a), re-payée
deux fois le même jour dans un module écrit pour l'appliquer.

**Deux demandes de Mike, faites le jour même.** (1) Le budget des docs de
suivi passe à **100 000** octets — quatrième relèvement, et pour la même raison
que les trois premiers : rogner sous le plafond coûte la PRÉCISION des raisons.
(2) **Le serveur a un JOURNAL** (`journal_serveur.py`, 15 vérifications) : sa
console est mirée, datée, dans `_journal_serveur.log`, lisible à distance et
sans lui. Ce qu'il attrape et que rien n'attrapait : les **threads qui meurent**
— un worker tombe, sa file se remplit, le serveur a l'air vivant — et les
plantages durs des libs natives (`faulthandler`). Une bannière par démarrage
rend « qu'est-ce qui a planté depuis que ce serveur tourne ? » lisible d'un
`sed`. Désormais : **lire le journal avant de supposer.**

## État (23/08/2026, session 40)

**La question ouverte de la 39 est répondue — et reproduite en trois lignes,
sans serveur ni NAS. Personne ne met de verrou dans une fiche : la fiche EST le
verrou.** `store.data.get(nom)` ne rend pas un `dict` mais un **`TrackedEntry`**
(sous-classe de `dict`, `__slots__ = ('_store', '_key')`). `copy.deepcopy` d'une
sous-classe de dict copie AUSSI l'état d'instance : il suit `_store` jusqu'au
`SqliteStore` et bute sur son `lock`, un **RLock** délibéré (`store_sqlite.py`,
en-tête). Ce n'était donc pas la fiche de Flo — **toute fiche vivante de tout
index SQLite** était indeepcopyable, hier comme demain. Conséquence directe :
**la ligne console de `_fiche_pour_journal` ne nommera jamais rien**, aucun
CHAMP n'étant en faute. **Parade** : `__deepcopy__` / `__copy__` / `__reduce__`
sur `TrackedEntry` et `TrackedDict` rendent un **dict NU** — une copie n'a ni
clé ni store à prévenir. **4 vérifications rouges sur l'ancien code, 52/52 sur
le nouveau**, dont une qui deepcopy le store LUI-MÊME pour prouver que le piège
existe toujours.

**La file XMP est 3× plus lente que ne le disait la session 39** : **0,28 op/s**
mesuré sur le fonds vivant (deux fenêtres indépendantes), soit ~11 h et non
3,4 h. Le 0,95 venait d'une fenêtre courte juste après la fusion.

**L'accident est maintenant RÉPARABLE : `verifier_xmp_personnes.py` (29 tests)
recompte, DEPUIS LE DISQUE, ce que la file doit encore.** Il ne lit pas la file
— elle est en mémoire, donc invisible — il compare les deux choses qui
survivent : ce que l'index dit (`/api/people/photos`) et ce que les fichiers
portent (ExifTool, une invocation par lot de 300). Il NOMME les photos en écart
(`--json`), n'écrit rien, et compte à part ce qu'il n'a pas pu lire.

**Ce qu'il a mesuré au banc (23/08, 10:37, échantillon de 200 tiré à graine
fixe sur les 5 909) : seules 19 photos sur 200 portent `personne:Florine` dans
leur FICHIER, et 119 portent encore `Flo`.** Le fonds est donc à ~10 % du geste,
neuf heures après le clic. Les deux chiffres indépendants concordent — 10 801
opérations en file ≈ 2 × 5 400 photos restantes : **la file ne se répète pas,
elle est seulement lente**. 70 s pour 200 fichiers (~2,9 f/s sur SMB) : une
passe complète demande `--echantillon`, ou plus que les 600 s du banc.

**Et l'autre moitié : `appliquer_xmp_personnes.py` (23 tests) REFAIT ce que la
file n'a pas fait.** Il REFUSE net tant que `queues.personnes` n'est pas à 0 —
deux écrivains sur les mêmes fichiers, c'est la bagarre du 22/08 en pire ; il
est à blanc par défaut ; il relit les tags avant d'écrire, donc **relancer
reprend** et une photo déjà réparée n'est pas réécrite ; son journal
(`_corbeille_xmp/`) s'écrit dans un `finally` et note l'état d'AVANT, donc une
passe interrompue reste annulable. Il fait le retrait et l'ajout d'une photo en
**UNE** invocation exiftool, là où `person_writer` en lance deux. **Il n'a
jamais écrit un vrai fichier** : famille `appliquer_`, hors de portée du banc —
la première passe à blanc est un geste de Mike.


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

0ter. **La file XMP : réparable (fait), durable (fait), rapide (à moitié).**
   **(a)** `verifier_xmp_personnes.py` recompte depuis le disque ce qu'elle
   doit, `appliquer_xmp_personnes.py` le refait. **Le vérificateur a tourné à
   17:47, file à 0, et il n'y a RIEN à réparer** : sur 200 fichiers tirés à
   graine fixe, **200 portent `personne:Florine`, 0 portent encore `Flo`, 0
   manquent, 0 illisibles.** Le même échantillon donnait 19 et 119 à 10:37 :
   la file a fait le travail en entier. `appliquer_xmp_personnes.py` reste donc
   livré et JAMAIS passé en réel — faute d'emploi, et c'est la bonne nouvelle. **(b1)** Les deux gestes d'une photo en UNE invocation : **fait** (÷2).
   **(b2)** Le journal qui la fait survivre à un arrêt : **fait**. **(b3)**
   `-stay_open` : mesuré à **25 %** de mieux sur une écriture, pas 12× — un
   processus qui vit longtemps et tient le NAS pour ce prix-là, **après le
   reste**. (b1), (b2) touchent `server.py` : livrables après redémarrage.

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
4. **Gestes Mike** : `gps_place` ✔ ; renommage appliqué ✔ (7 058) ; **Flo →
   Florine ✔ (23/08 — 11 heures de file, 5 909 photos, vérifié 200/200 sur le
   DISQUE)** ; **groupe de Stéphane Plouvin ✔ (23/08 — 58/58 sur le DISQUE)** ;
   re-rejeter Caline.
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

13. **Serveur exposé en MCP, lecture seule : LIVRÉ et OBSERVÉ (23/08).**
    `mcp_serveur.py` — JSON-RPC 2.0 sur stdio, stdlib pure, six outils
    (`ml_chercher`, `ml_semblables`, `ml_meme_jour`, `ml_sujets`,
    `ml_photos_de`, `ml_etat`). **41 vérifications + 15 pour le banc**, et
    **13 mutations vues sur 13** — un module neuf n'a pas d'ancien code à
    rougir, la mutation est ce qui en tient lieu. Observé contre le serveur
    vivant par `mesure_mcp.py` (12 étapes, 0 rouge) : une VRAIE poignée de main
    sur un VRAI tuyau, 0,09 s, 351 personnes, `espece:chat` filtré.
    **Et `faits` a sa route (23/08).** La ligne de faits n'existait que dans
    `_serve_browse` : rien d'autre que le HTML ne pouvait la lire — ni un banc,
    ni le MCP. `/api/faits?key=…` (répétable, 200 au plus) la rend pour un LOT,
    contexte bâti UNE fois ; **16 vérifications, 8 mutations vues sur 8**, et
    l'outil `ml_faits` s'y branche (48 vérifications au total côté MCP).
    **Trois états qui ne se confondent pas** : les faits ; `null` pour une photo
    connue qui ne porte ni date, ni lieu, ni nom ; la clé citée dans
    `inconnues` quand l'index l'ignore. **C'est la seule route NEUVE du lot** —
    elle attend le redémarrage, et le banc le dit au lieu de le taire (« la
    route existe-t-elle dans le code qui TOURNE ? »).
    **Reste** : l'écriture, plus tard, et pas sans décision. Briques de 14a.
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

# Chantier 19 — la vie privée à la demande (17/09)

> Demandé par **Flo** pendant qu'elle essayait la photothèque, relayé par Mike.
> Cinq briques, un seul sujet : **la photothèque s'ouvre à la famille, donc ce
> qui n'était gênant pour personne le devient**. Ce fichier est le PLAN ; les
> verdicts iront dans `eval/DECISIONS.md`, l'état dans `ROADMAP.md`.

## Ce qui existe déjà et ne se refait pas

- **Chantier 17** : le partage se fait par DOSSIER. `Photos <Nom>` est visible
  de tous, `Photos <Nom>/PRIVE` de son seul propriétaire. Règle pure dans
  `visibilite.py`, filtre posé AU MAGASIN (`brancher`) — donc les 166 lectures
  du serveur sont couvertes sans être touchées, compteurs et fiches compris.
- **Chantier 18** : une photo peut être **masquée sans être déplacée**
  (`sensible: en_attente`), visible de son propriétaire et de l'admin, en
  attente d'un verdict humain (`/sensibles`). Le filet qui la désigne ne
  connaît que les **documents** (mots-clés imposés par le prompt).
- **`refus_rendre_privee`** : « Rendre privée » DÉPLACE la photo dans le PRIVE
  du propriétaire — geste réservé au propriétaire, par construction.

## Les cinq briques demandées

### 1. Le filet s'élargit : intime, et captures de conversation

**MESURÉ le 17/09** (`mesure_filet_intime.py`, zéro-shot SigLIP 2 sur les
40 330 vecteurs déjà en base, 45 s, aucune image relue) — et **le résultat
refuse le masquage automatique** :

| | p50 | p99 | max |
|---|---:|---:|---:|
| score « intime » | 0,059 | 0,115 | 0,180 |
| score « témoin » (plage, piscine, sport, bain de bébé) | 0,048 | 0,133 | 0,163 |
| **marge intime − témoin** | 0,015 | 0,075 | **0,138** |

Le maximum des TÉMOINS dépasse le p99 des intimes : sur ce modèle, une photo de
plage et une photo intime ne se séparent pas proprement. À marge ≥ 0,10 il ne
reste que **18 photos** sur 40 330 — un filet qui laisserait presque tout
passer. **Conclusion : SigLIP zéro-shot vaut comme FILE DE REVUE (classer les
photos de la plus suspecte à la moins), pas comme verdict.** Le modèle
(webli, filtré à l'entraînement) n'a presque rien vu de ce qu'on lui demande.

Deux suites possibles, à trancher :
- **(a) File de revue** : les N plus fortes marges vont dans l'onglet
  Sensibles du PROPRIÉTAIRE, qui tranche. Coût nul, aucun faux masquage,
  mais ne protège que ce que quelqu'un a regardé.
- **(b) Modèle dédié** (NudeNet ou équivalent, CPU possible) : à éprouver sur
  un jeu de validation **constitué par Flo et Mike** — je ne regarde pas ces
  photos, et un banc qui les afficherait serait exactement ce qu'on veut
  empêcher. Protocole : `vision-eval`, mesure en aveugle, apport ET faux
  positifs.

Les **captures d'écran**, elles, se détectent sans modèle : pas d'appareil
dans l'EXIF, format PNG, dimensions d'écran. Signal franc, à mesurer avant
d'être câblé. Le mot-clé `capture d ecran` existe déjà dans le filet documents.

### 2. Quarantaine à l'arrivée (tranché par Mike, 17/09)

Toute photo déposée reste **invisible aux autres** (visible de son déposant et
de l'admin) jusqu'à ce que les détecteurs soient passés. Garantie simple :
rien n'apparaît dans la galerie familiale avant d'avoir été regardé par la
machine. Mécanique : même axe que le chantier 18, posé À L'ARRIVÉE par
`/upload`, levé par le tagueur quand le filet n'a rien dit.

### 3. « Masquer cette photo » pour une personne reconnue (tranché)

Une personne reconnue sur la photo d'un autre peut la masquer. **La photo ne
bouge pas** : elle reste chez son propriétaire.
- Visible ensuite : le **propriétaire**, la **personne** qui a masqué, l'admin.
- **Seule la personne** lève son masque (l'admin en secours). Le propriétaire
  peut effacer sa photo, jamais la redévoiler.
- L'état vit **en base**, jamais dans le XMP : un masque posé par un tiers ne
  se grave pas dans le fichier de quelqu'un (règle 18c).
- Le geste n'apparaît que là où il peut aboutir : la personne connectée doit
  être parmi les `personne:` de la photo (CLAUDE.md n° 9).

### 4. Les personnes reconnues VOIENT leurs photos (nouveau, 17/09)

Si `personne:Flo` est sur une photo, Flo la voit — même si son propriétaire ne
partage pas avec elle. **Sauf** si la photo est dans un `PRIVE`, masquée
(chantier 18), ou masquée par quelqu'un d'autre (brique 3).

### 5. Onglet « Partage » : chacun choisit qui voit ses photos (nouveau, 17/09)

Une page qui liste les comptes avec une coche par personne : « qui peut voir
mes photos ». Ce que ça change de nature : **la visibilité cesse d'être une
propriété du CHEMIN pour devenir une relation entre deux comptes.**

## L'ordre d'évaluation — et c'est lui qui fait la sécurité

Une règle de plus n'est pas une ligne de plus : c'est un ordre à fixer, sinon
une brique en annule une autre. Ordre proposé, du plus fort au plus faible :

1. **PRIVE** — rien ne l'ouvre (ni le partage, ni la reconnaissance).
2. **Masque personnel** (brique 3) — seul le propriétaire, la personne, l'admin.
3. **Masque machine** (chantier 18, quarantaine comprise) — propriétaire + admin.
4. **Liste de partage** du propriétaire (brique 5).
5. **Reconnaissance** (brique 4) — n'ouvre QUE ce que 1-3 n'ont pas fermé.

Autrement dit : les masques ferment, le partage et la reconnaissance ouvrent,
et **ce qui ferme passe toujours avant ce qui ouvre**.

## Les questions à trancher AVANT le code

- ~~**Le défaut du partage.**~~ **TRANCHÉ par Mike le 17/09 : une liste vide
  vaut « tout le monde » — mais UNIQUEMENT pour les comptes qui existent
  aujourd'hui** (Mike, Flo, Papa). Un compte créé ensuite part **fermé** :
  liste vide = personne, à lui de cocher.
  Ce que ça impose au code, et c'est le piège : « liste vide » ne peut pas
  porter deux sens selon l'âge du compte sans qu'on l'écrive quelque part. Le
  partage se stocke donc en TROIS états, jamais en deux —
  `partage: null` (jamais réglé), `partage: []` (réglé, personne),
  `partage: [noms]`. La MIGRATION pose `null` sur les trois comptes existants
  (qui restent ouverts) et les créations futures posent `[]`. Une seule
  fonction lit ce champ (`visibilite.partage_ouvert`), et son banc porte les
  trois cas — un défaut implicite est exactement ce qui fait fuiter une
  photothèque le jour d'une migration.
- **Le partage est-il par DOSSIER ou par PERSONNE ?** Aujourd'hui `Photos Flo`
  est une seule chose. Recommandation : par propriétaire (donc par dossier),
  comme le chantier 17 — une exception par photo se fait avec le PRIVE.
- **Ce que la recherche laisse fuir** (déjà écrit dans la ROADMAP) : un compte
  de résultats, un nom qui complète, une vignette suffisent à révéler ce qu'on
  croyait caché. Le filtre reste AU MAGASIN, jamais dans les routes.
- **Le coût.** `visible()` est appelé par clé sur chaque lecture agrégée
  (44 445 clés). La brique 4 exige de connaître les NOMS d'une photo : il faut
  un index clé → noms en mémoire, et une mesure avant/après — la grille du
  fonds entier est à 3,7 s, elle ne doit pas y retourner.
- **Les noms dans les XMP.** Nommer quelqu'un écrit dans le fichier (règle 2).
  Le partage et les masques, eux, restent en base.

## L'ordre de construction proposé

1. **Quarantaine à l'arrivée** (brique 2) — petite, indépendante, protège tout
   de suite ce que Flo dépose pendant qu'elle essaie.
2. **Masque personnel** (brique 3) + le geste dans la page photo.
3. **Onglet Partage** (brique 5) et l'ordre d'évaluation ci-dessus, avec le
   banc qui prouve qu'une photo non partagée ne fuit ni par un compteur, ni
   par une fiche, ni par la recherche.
4. **Reconnaissance** (brique 4), qui ne se pose que sur 3.
5. **Filet intime** : file de revue d'abord (a), modèle dédié seulement si la
   mesure le justifie (b).


## Brique 6 — les comptes, pour de bon (17/09, demande de Mike)

« Pour faire pro » : un compte doit pouvoir changer son mot de passe, et
porter une adresse e-mail.

**Ce qui existe déjà (16/09)** : « Changer mon mot de passe » est dans le menu
du compte, pour tout le monde, dans un panneau à deux champs masqués.

**Ce qui manque, et c'est un vrai trou** : ce geste ne demande PAS le mot de
passe actuel. N'importe qui devant une session ouverte — un téléphone déverrouillé,
un ordinateur laissé sans surveillance — change le mot de passe et ferme la
porte derrière lui. `comptes.changer_mdp` doit exiger l'actuel pour soi-même ;
l'admin, lui, réinitialise sans le connaître (c'est le sens d'un admin), et ce
cas se DIT à l'écran.

**L'adresse e-mail** : un champ par compte dans `comptes.json` (déjà hors git),
posé par la personne elle-même dans « Mon compte », visible d'elle et de
l'admin — jamais des autres. Elle sert à trois choses, et il faut trancher
laquelle on construit :

- **(a) Le rappel** : l'admin sait à qui écrire quand un compte est bloqué.
  Coût nul, aucun envoi, aucune dépendance.
- **(b) La réinitialisation PAR L'ADMIN** : Mike pose un mot de passe
  temporaire, à changer à la première connexion. Aucun envoi automatique.
- **(c) Le vrai « mot de passe oublié »** : le serveur envoie un lien à durée
  limitée. Il faut alors un compte SMTP (Gmail et son mot de passe
  d'application), un secret de plus sur la machine, et un serveur maison qui
  écrit à l'extérieur — ce que ce projet n'a jamais fait.

**Recommandation** : (a) + (b) maintenant, (c) seulement si quelqu'un reste
vraiment bloqué. La famille compte trois comptes et l'admin dort dans la même
maison que deux d'entre eux.

**Ce qui ne change pas** : l'e-mail est une donnée personnelle. Elle reste
dans `comptes.json`, hors git, hors XMP, et ne sort jamais dans une page que
les autres comptes peuvent lire.

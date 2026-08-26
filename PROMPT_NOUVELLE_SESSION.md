# Amorce de reprise — MediaLibrary

> À coller après connexion de `C:\Prog\Claude\MediaLibrary`. Règles et
> protocole : `CLAUDE.md`. Ici : **l'état et le prochain pas, rien d'autre.**

Tu reprends **MediaLibrary**. **VÉRIFIE avant de lire** : `.git/HEAD`,
`.git/logs/HEAD` et `.git/logs/refs/heads/main` disent ce qui a été commité et
FUSIONNÉ — ce document, non. Puis `ROADMAP.md`, `eval/DECISIONS.md`,
`eval/METHODE.md` — et `docs/DECISIONS_OUTILLAGE.md` si le sujet touche aux
canaux, à la livraison ou au MCP. Débrief en 2–3 lignes, puis on attaque.

## Où on en est (26/08/2026, fin de session 52)

**Le serveur TOURNE, tout est fusionné, rien n'attend.** `main` à `fb63a3c`,
trois fenêtres vivantes, canaux au repos. Dernier démarrage 22:35:09, aucune
exception depuis.

**Le fonds a changé de forme aujourd'hui : `Photos Mike` existe.** 26 dossiers,
**25 559 photos**, **2 271 décisions humaines** re-clées. Prouvé base contre
base (`_avant_deplacement/`) : 43 065 clés et **3 767 décisions des deux
côtés**, 140 orphelines sur les MÊMES 119 clés (elles pré-existaient), tous les
compteurs de noms identiques au photo près, **0 clé restée sur un ancien
chemin**. Restent à la racine : `Photos Flo` 12 084, `Photos Papa` 4 843,
`_A TRIER` 559. Journal d'annulation dans `_corbeille_deplacements/`.

**Effet de bord attendu, ce n'est pas une panne** : la clé du cache de
vignettes contient le chemin, donc les 3 047 vignettes en cache sont
orphelines et se refont au premier affichage. À balayer avec O15.

### Les quatre choses de la journée qui changent la suite

1. **Le plancher tactile a son instrument.** `verifier_cibles.py` (65 tests,
   huit rouges observés gravés) : **221 cibles, 0 manquement prouvé**, 66 dont
   la hauteur n'est pas déclarée. Il lit le HTML statique, les chaînes JS ET ce
   que `document.createElement` bâtit — 31 cibles lui étaient invisibles.
2. **Le chip est fini.** `.chip` vit dans `components.css` seul, `font:`
   compris ; `.pchip` supprimé ; **7 pages sur 11** reçoivent la feuille
   commune.
3. **Un filtre qui ment.** `/files?q=animal:Zzzznexistepas` rend
   « 1500 photo(s) ». `_extraire_noms` cherche le nom NU et **ne connaît aucun
   préfixe** `personne:` / `animal:` : le jeton part en recherche sémantique et
   la page l'annonce comme un filtre. Défaut corrigé le 21/08 pour
   `espece:licorne`, oublié sur les quatre autres axes — **et l'interface écrit
   elle-même ce vocabulaire sur ses pastilles.** C'est la priorité 1.
4. **Le chantier 17 (multi-utilisateurs) est SPÉCIFIÉ** — six décisions de
   Mike dans `ROADMAP.md`. Ne pas le rouvrir : l'exécuter.

**Caline, pour mémoire** : elle n'était pas perdue, elle n'avait jamais été
SAISIE. Deux noms posés à la main → 730 photos, et les groupes d'animaux non
nommés sont tombés de **189 à 99** (442 apparitions, plus gros groupe 31). La
thèse du point 16 enfin chiffrée : le mécanisme n'était pas à écrire, il
attendait une décision humaine.

## Prochain pas

1. **Le garde-fou du filtre.** Un jeton `<axe>:<valeur>` que le filtre ne sait
   pas satisfaire rend RIEN et le DIT — comme `espece:` déjà. Puis la barre de
   recherche comprend ce que les pastilles écrivent (ou les pastilles cessent
   de l'écrire). Puis **un banc de contrôle NÉGATIF** : pour chaque axe, une
   valeur inventée doit rendre 0. C'est le test qui manquait.
2. **Les boutons de `gallery` — option 1, tranchée par Mike : tout convertir.**
   `.tb` 34 px, `.geobtn` 28 px, `.fchip` 35 px, `.georow button` 34 px,
   `#ss-stop` 34 px → `.btn` canonique. Coût accepté : **+19 px** de hauteur de
   barres. Preuve dans l'ordre : `verifier_css_cascade --page` (feuille commune
   EN PREMIER dans `--apres`), `verifier_cibles`, `verifier_contraste`,
   `verifier_controles`, tests UI, banc des pages composants sur le **serveur
   vivant**, puis l'œil.
3. **Le panneau `?` des raccourcis**, et d'abord sa brique : **un JS commun
   injecté sur toutes les pages**, comme `tokens.css` et `base.css`
   (`_UI_GLOBAL_FILES`). Il n'en existe aucun ; ce serait le premier. Contenu
   déjà relevé dans `docs/RACCOURCIS.md`.
4. **La suite du chantier 17** : la notion de PROPRIÉTAIRE, puis l'attribution
   rétroactive des 3 767 décisions à Mike (ordre de travail complet : ROADMAP,
   point 17). Deux questions restent ouvertes dans `QUESTIONS_MIKE.md` et
   bloquent l'écriture partagée.
5. **Réparer `appliquer_plan.rekey_stores`** — elle re-clé cinq magasins sur
   sept, et le rangement par année comme le dédoublonnage la portent. Puis
   **unifier** : la primitive complète existe maintenant DEUX fois
   (`server.rekey_everywhere` et `deplacer_dossiers`).
6. **Reste d'audit** : O8–O9, O11, O13–O15 ; **I1** dans `/reglages` ;
   `animal:luna` en minuscule sur 3 photos à côté de `animal:Luna` sur 355.
   Puis les quatre pages sans `components.css` : `browse`, `faces`, `map`,
   `reglages`.

## En fin de projet — décidé, mesuré, en attente d'un geste

**La copie hors site attend que le chantier 17 soit fini** (choix de Mike,
26/08). Le Takeout, lui, ne dépend de rien.

- **Le Takeout Google** : en téléchargement depuis le 26/08, ~2 jours. À son
  arrivée : dézipper, puis `verifier_photos_google.py --takeout "<dossier>"`.
  Quatre verdicts, et **un seul ABSENT interdit tout effacement**. Effacer se
  fait sur `photos.google.com` — jamais depuis l'app du téléphone, qui efface
  aussi l'appareil — et le quota ne bouge qu'une fois la CORBEILLE vidée
  (60 j). **Le compte est à 96 %** : quand il est plein, Gmail cesse de
  RECEVOIR.
- **La copie hors site (12 bis)** : Synology DS224+ → **Infomaniak Swiss
  Backup**, Hyper Backup/Swift, ~**CHF 6 TTC/mois** pour 1 To, données en
  Suisse. Fonds mesuré : **291 Go**. Clé de chiffrement imprimée et rangée
  ailleurs. Et une restauration d'épreuve : une sauvegarde jamais restaurée
  n'est pas une sauvegarde.
- **HTTPS : FAIT** (26/08). `tailscale serve --bg --https=443 localhost:8080`
  → `https://msi-mike.goat-draco.ts.net/`. Zéro ligne de code changée.

## Réflexes

### Mesurer, oui — mais avec l'instrument du PROJET

**Trois fois dans la journée du 26/08, une requête maison s'est trompée là où
l'instrument du projet avait raison.** « Caline n'existe nulle part » (lu dans
`/api/names`, qui ne connaît que les FICHES) ; `total: null` lu comme un zéro ;
983 décisions au lieu de 2 271 (ma requête exigeait des paires `[clé, index]`,
or `exclude` et `confirmed` sont des listes de clés SIMPLES). L'outillage a
déjà payé pour connaître ses cas limites.

**Un nom inventé doit rendre ZÉRO.** Avant de croire un filtre, demande-lui une
valeur qui n'existe pas. Le contrôle négatif coûte une requête et vaut un
verdict.

**Avant de croire une ABSENCE, vérifie que l'instrument mesure la bonne
chose.** Trois instruments, trois questions différentes : les fiches
(`/api/names`), les tags (`kw` de l'index), les détections (`animals`).

**Un docstring qui dit « miroir de » n'est pas une preuve.**
`appliquer_plan.rekey_stores` l'affirmait et re-cléait cinq magasins sur sept —
`people` et `pets` sont keyés par NOM, donc `.rekey(chemin)` n'y trouve rien et
**ne dit rien**. Quand deux chemins font « la même chose », c'est un test qui
doit le dire, pas un commentaire.

### Lire

**Le serveur a un journal : `_journal_serveur.log`** — miroir daté de sa
console, lisible depuis la sandbox, il porte les tracebacks des threads qui
meurent. **Le lire AVANT de supposer**, depuis la DERNIÈRE bannière :

    L=$(grep -n "===== DEMARRAGE" _journal_serveur.log | tail -1 | cut -d: -f1)
    tail -n +$L _journal_serveur.log | grep -n "THREAD MORT\|EXCEPTION\|Traceback"

**Un commentaire est de la PROSE, quel que soit le langage** — CSS compris.
Deux instruments lisaient les `<button>` cités dans les commentaires de
`<style>` comme des éléments réels. Règle de lecture unique et partagée :
`verifier_controles.sans_le_css`. **L'exception est une DÉCLARATION**
(`/* cible: hors-portee -- … */`, `controle:`, `contraste:`) : elle vit dans un
commentaire, donc elle se lit AVANT le retrait, et se ferme sur `*/`, pas sur
la première fin de ligne.

**Un banc en lecture seule tourne aussi dans la VM** : les `verifier_*` qui ne
lisent que des fichiers se relancent en une seconde par `device_bash` — c'est
ce qui permet d'itérer. Le banc Windows reste la PREUVE (console cp1252) et le
seul chemin vers le serveur : la VM n'atteint pas le LAN. **Ce qui ÉCRIT n'est
pas lançable au banc** — c'est un geste de Mike, et l'agent le refuse.

### Juger

**Un verdict tiré à pile ou face est pire qu'un aveu d'ignorance.** Deux règles
CSS de même poids : « la dernière écrite gagne » n'est vrai que **si les deux
s'appliquent**. Et l'inverse existe — une seule règle non prouvable AFFIRMÉE
disait « trop petit » là où il fallait lire « pas de plancher ».

**Ce qui doit s'accorder, c'est le VERDICT, pas la valeur.** `44px` et
`var(--touch)` sont la même hauteur.

**Une chaîne d'ancêtres PARTIELLE prouve, elle ne réfute pas.** Un fragment
assemblé en JS dit ce qu'il contient, jamais ce qu'il y a au-dessus.

**Ne pas voir une cible ne la rend pas conforme** — ça retire seulement le
dénominateur. Avant de croire un « 0 grief », demander sur COMBIEN.

**Un banc qui ne SAIT pas ne rend pas vert.** Tout rapport dit sa PORTÉE, et
**ce qui ne se calcule pas se DÉCLARE dans la source avec une raison
obligatoire — jamais en dur dans l'instrument.**

### Toucher

**`ui/pages/` et `ui/*.css` sont relus À CHAUD** ; seul `server.py` exige un
redémarrage. Ça ne dispense pas d'OBSERVER.

**L'ordre de la cascade a QUATRE étages**, et il est la moitié de toute preuve
CSS : `components.css` (au marqueur, AVANT le `<style>` de la page) → la page →
`tokens.css` → `base.css` (à `</head>`, il gagne les égalités). Une feuille qui
ne change pas doit figurer **des deux côtés** de `--avant`/`--apres`.

**Changer une BALISE change son style par défaut** : `<span>` → `<button>`
change la police, l'alignement et surtout `display` (inline → inline-block, ce
qui **rend actif** un `min-height` qui dormait). Un `<button>` n'admet que du
contenu de PHRASE ; sinon `tabindex` + `role` + `keydown` Entrée **et** Espace
avec `preventDefault` — **les trois**.

**Jamais deux écrivains sur `photos.db`.** Le serveur est l'écrivain unique ;
un script hors-ligne le PROUVE (`BEGIN IMMEDIATE`) au lieu de le demander.

**Un `_exiftool_tmp` condamne sa photo** : ExifTool refuse d'écrire tant qu'il
est là. Balayage possible mais **jamais par défaut** (`--balayer-fantomes`).
Un fantôme SANS original à côté ne s'efface pas en lot.

**Un nom accentué passe au banc par le jeton `b64:`** :

    verifier_xmp_personnes.py --nom b64:U3TDqXBoYW5lIFBsb3V2aW4

> **Piège d'horloge** : `device_bash` tourne dans une VM en **UTC** — deux
> heures de moins que chez Mike. Les epochs du serveur sont la seule heure
> fiable.
>
> **Et le dossier monté a un cache** : `tail` peut rendre un contenu vieux de
> 25 min. Le `mtime` (`ls -l`, `date -r`) dit la vérité.

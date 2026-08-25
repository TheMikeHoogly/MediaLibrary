# Amorce de reprise — MediaLibrary

> À coller après connexion de `C:\Prog\Claude\MediaLibrary`. Règles et
> protocole : `CLAUDE.md`. Ici : **l'état et le prochain pas, rien d'autre.**

Tu reprends **MediaLibrary**. **VÉRIFIE avant de lire** : `.git/HEAD`,
`.git/logs/HEAD` et `.git/logs/refs/heads/main` disent ce qui a été commité et
FUSIONNÉ — ce document, non. Puis `ROADMAP.md`, `eval/DECISIONS.md`,
`eval/METHODE.md` — et `docs/DECISIONS_OUTILLAGE.md` si le sujet touche aux
canaux, à la livraison ou au MCP. Débrief en 2–3 lignes, puis on attaque.

## Où on en est (25/08/2026, fin de session 46)

**Rien ne tourne, rien n'attend.** Le serveur a été redémarré et **observé**
après chaque incrément. Le chantier des XMP est clos (**0 écart** sur 1 614
couples, Wilson 0,0–0,2 %).

**Le chantier CSS a changé de nature trois fois, et chaque fois c'est une
mesure qui l'a fait.**

1. *Extraire le CSS commun* → **tué par sa propre preuve** : 200 déclarations
   hissables sur 1 754, dont 171 partagées par deux pages seulement, 6,2 Ko
   sur 67. Le sujet n'est pas la duplication.
2. *Faire converger les composants* → **6 pages sur 11 ont adopté**
   `ui/components.css` (`residu`, `tranche`, `subjects`, `people`, `pets`,
   `upload`). **Le `.btn` est FINI** : les cinq pages restantes n'en ont pas.
   Trois d'entre elles écrivaient le canonique **sous d'autres noms**
   (`.prim`/`.warn`, `.primary`/`.danger`) — la divergence la plus chère,
   celle qui ne se voit pas à l'écran. Deux n'avaient pas
   `min-height: var(--touch)`.
3. *Le sujet réel est l'ACCESSIBILITÉ*, et il n'était pas dans le plan de
   départ. Voir « Prochain pas ».

**Les trois universelles** (`body{background|color|font-family}`) vivent dans
`ui/base.css` seul — **11 preuves sur 11, IDENTIQUE APRÈS LA CASCADE**. Elles
étaient **trois, pas six** : le reset `*` ne vit que dans NEUF pages.

**Le design system a gagné quatre choses, toutes approuvées par Mike** :
`--salle-4` (élévation 3, la marche du survol), `--fixateur-p` / `--encre-p`
(la marche pressée des deux accents pleins), l'état **pressé** hors du garde
`hover` (sur tactile c'est le SEUL retour), et `.hors-ecran` dans `base.css`.

**Et deux manquements réels ont été trouvés et corrigés** :
- **AA** : `.btn--confirmer`, `.chip[aria-pressed]` à 3,94:1 et
  `.btn--destructif` à 3,03:1. `--fixateur` assombri `#4A8C7B` → **`#448172`**,
  bouton destructif **passé au plein** (5,34:1, sans toucher `--encre`).
  **24 couples mesurés, tous au-dessus.**
- **Niveau A** : les deux `<input type="file">` de `/` étaient en
  `display:none` derrière des `<label for>` — **les deux actions principales
  du site étaient injoignables au clavier**.

**⚠ ACTION EN ATTENTE DE MIKE** : la skill `photo-ui` a été mise à jour et
envoyée en fichier. **Si elle n'a pas été enregistrée, sa table de tokens dit
encore `#4A8C7B` et ne connaît ni `--salle-4`, ni les `-p`, ni `.hors-ecran`
— la prochaine session réintroduira la couleur corrigée.** Vérifier AVANT de
toucher au CSS.

## Prochain pas

1. **UN CONTRÔLE QUI N'EN EST PAS UN — le chantier est nommé et chiffré.**
   `gallery` construit ses chips de personnes en `document.createElement
   ('span')` + `.onclick` : pas de `tabindex`, pas de `role`, pas
   d'`aria-pressed`. **Le filtre le plus utilisé de la page la plus utilisée
   est inaccessible au clavier** — même manquement de niveau A que les champs
   de fichier corrigés aujourd'hui. `subjects` fait `<button class="chip"
   aria-pressed>` : correct. **La divergence n'est pas visuelle, elle est
   sémantique.**

   Gisement compté d'avance : **7** `onclick` en dur sur `<span>`/`<div>`
   (`map` 3, `pets` 4) et **7 pages** qui fabriquent des `span`/`div` en JS
   (`gallery` 8 créations / 22 `.onclick`, `people` 7/34, `pets` 5/17,
   `subjects` 3/20). Tous les `.onclick` ne sont pas fautifs.

   **Premier geste : l'INSTRUMENT, pas la correction.**
   `verifier_controles.py` (famille `verifier_`, lecture seule) apparie chaque
   `createElement` à son `.onclick` et compte ce qui est cliquable sans être
   un contrôle. **Rouges d'abord** — les trois instruments existants se sont
   corrigés **six fois** sur des rouges observés, jamais sur une hypothèse.
   Puis corriger avec un chiffre au lieu d'une impression.

2. **`.chip` suivra presque gratuitement.** Deux pages seulement le déclarent
   et l'écart tient en trois lignes (32 px vs 36 ; `--e-1 --e-3` vs
   `0 --e-4` ; compteur par `margin-left` vs par `gap`). **Contradiction à
   trancher avec Mike** : `components.css` donne `min-height: 32px` au chip
   alors que le plancher du même document exige « cibles ≥ 44 px ». 32 px
   passe WCAG 2.5.8 (24 px) mais viole la règle que le projet s'est donnée.

3. **Reste d'audit** : O8–O9, O11, O13–O15 ; **I1** visible dans `/reglages`.
   O15 (purge de `photo_thumbs/`) gagne en poids.

## En fin de projet — décidé, mesuré, en attente d'un geste

Ces deux points ne sont plus des questions ouvertes : tout est chiffré, il ne
manque que le temps. **Ne pas les faire passer devant le code.**

3. **Le Takeout Google tourne** (lancé le 25/08 par Mike, ~75 Go, plusieurs
   heures). À son arrivée : dézipper, puis
   `verifier_photos_google.py --takeout "<dossier>"`. Quatre verdicts, et
   **un seul ABSENT interdit tout effacement**. Effacer se fait ensuite sur
   `photos.google.com` — jamais depuis l'app du téléphone, qui efface aussi
   l'appareil — et le quota ne bouge qu'une fois la CORBEILLE vidée (60 j).
4. **La copie hors site (12 bis)** : Synology DS224+ → **Infomaniak Swiss
   Backup**, Hyper Backup/Swift, ~**CHF 6 TTC/mois** pour 1 To, données en
   Suisse. Premier envoi **~8 nuits** à 13,8 Mbit/s avec limite de débit
   (photos ~3, vidéos ~5) — **le débit n'est PAS un préalable**. Compte
   Infomaniak **personnel**. Clé de chiffrement imprimée et rangée ailleurs.
   Et une restauration d'épreuve : une sauvegarde jamais restaurée n'est pas
   une sauvegarde.

## Réflexes

**Le serveur a un journal : `_journal_serveur.log`** (`journal_serveur.py`),
miroir daté de sa console, lisible depuis la sandbox et qui survit à sa mort.
Il porte les **tracebacks des threads qui meurent**. **Le lire avant de
supposer** :

    tail -80 _journal_serveur.log
    sed -n '/===== DEMARRAGE/,$p' _journal_serveur.log
    grep -n "THREAD MORT\|EXCEPTION\|Traceback" _journal_serveur.log

Plantage dur d'une lib native : `_journal_serveur_crash.log`.

**Un nom accentué passe au banc par le jeton `b64:`** (23/08) :

    verifier_xmp_personnes.py --nom b64:U3TDqXBoYW5lIFBsb3V2aW4

`python3 -c "import base64;print(base64.urlsafe_b64encode('Béa'.encode()).decode().rstrip('='))"`.

**Le contrôle 5 ne réclame plus de redémarrage pour l'outillage** (23/08) : il
lit le graphe des imports de `server.py`. `git_agent.py`, `banc_agent.py`,
`mcp_serveur.py`, `appliquer_*`, `verifier_*`, `inventaire_*`, `bundle.py`,
`ui_gabarits.py` sont DEHORS — plus besoin de `force=` pour eux.

**Un `_exiftool_tmp` condamne sa photo** (24/08). ExifTool recopie la photo à
côté avant d'écrire et REFUSE d'écrire tant que ce temporaire est là, sans
option pour l'écraser : une écriture tuée en route rend la photo non
réécrivable, définitivement et sans bruit. 21 dormaient sur le fonds, du 06/07
au 24/08, dont dix qu'aucun journal ne connaissait. Balayage possible mais
**jamais par défaut** (`--balayer-fantomes`) ; surveillance par
`inventaire_fantomes.py`. **Un fantôme SANS original à côté ne s'efface pas
en lot** : c'est peut-être la seule copie qui reste.

**Un compte d'échecs ne se répare pas ; une cause, si** (24/08). La passe
disait `en echec : 3` et il a fallu relire le jsonl pour voir que onze des
treize étaient le même fantôme. Les causes sont comptées et dites.

**Jamais deux écrivains, y compris contre soi-même** (24/08) :
`appliquer_xmp_personnes.py` pose un verrou (`_corbeille_xmp/_ecriture.lock`,
preuve par FRAÎCHEUR, repris après 10 min sans signe de vie).

**Un commentaire est de la PROSE, quel que soit le langage** (25/08, appris
**quatre fois le même jour**). Un commentaire CSS disant « la feuille
commune » a rendu six règles `.feuille` actives sur une page qui n'en porte
aucune. Un commentaire JS (« légende + chip + position ») a rendu treize
règles `.chip` actives. Une phrase dans un commentaire de `tokens.css`
(« en bordure sur `--salle` : 4,33:1 ») a fait **disparaître le token qui la
suivait**, parce que le lecteur avalait tout jusqu'au premier `;`. Et une
fois, mon propre garde `assert` a échoué parce que ma note explicative
contenait le marqueur qu'il cherchait. **Retirer les commentaires AVANT de
lire** — et un nom de classe est un **jeton entier**, pas un morceau de mot
(`toastP`, `vues`, `--f-donnees` faisaient passer `.toast`, `.vue`, `.donnee`
pour actives).

**Un banc qui ne SAIT pas ne rend pas vert** (25/08). `verifier_contraste.py`
a affiché « le plancher AA tient sur tout ce qui est déclaré » et rendu 0,
avec quatre couples listés juste au-dessus comme non décidables : trois
avaient cessé d'être mesurés et rien ne criait. **Un couple non mesuré compte
comme un grief**, et tout rapport dit sa PORTÉE. Ce qui ne se calcule pas se
**DÉCLARE** dans la source, avec une raison obligatoire
(`/* contraste: hors-portee -- raison */`) — jamais en dur dans l'instrument,
sinon il devient aveugle au cas suivant sans qu'on le sache.

**L'ordre de la cascade a QUATRE étages** (25/08), et il est la moitié de
toute preuve CSS : `components.css` (au marqueur, AVANT le `<style>` de la
page) → la page → `tokens.css` → `base.css` (à `</head>`, il gagne les
égalités). Une feuille qui ne change pas doit figurer **des deux côtés**,
sinon elle apparaît en entier (84 fausses « apparues » sur `residu`).

**Un style de focus sur un élément qui ne reçoit jamais le focus est un
aveu** (25/08). `.pick-btn:focus-visible` existait depuis toujours et ne
pouvait pas se déclencher : le contrôle réel était en `display:none`. Quand
une règle d'accessibilité semble inutile, chercher pourquoi elle a été
écrite.

**La mise en page n'est pas une variante de composant** (25/08). `upload`
passait pour le cas différent du chantier avec son bouton pleine largeur :
c'était `.btn--principal` plus quatre déclarations de layout. Un composant
décrit ce qu'une chose EST, la page décide de la place qu'elle prend.

**Un banc d'observation ment de deux façons** (25/08). Il peut manquer une
panne — et il peut déclarer vert ce qu'il n'a **pas pu regarder**.
`verifier_pages_composants.py` a fait le second à son premier lancement réel :
son témoin pointait sur une route inexistante et il a écrit « rien n'a pu être
vérifié » alors qu'il venait de lire et de juger bonnes deux pages sur trois.
Un 404 (mauvaise adresse) et un refus de connexion (serveur mort) envoient
chercher la panne à deux endroits opposés : **ils ne se disent pas pareil**.

**Un opt-in se prouve par son TÉMOIN** (25/08). Un banc qui ne regarde que les
pages converties passerait au vert sur un serveur qui injecte partout — c'est-
à-dire exactement le jour où les huit pages restantes cassent. Le témoin coûte
une requête et vaut la garantie. **Encore faut-il l'avoir lu** : `/upload`
n'est pas une route (404), et `/faces` répond **302 vers `/people`** —
urllib suit sans rien dire, et le banc a écrit « la page témoin (/faces) reste
intacte » après avoir lu `/people`. Il compare désormais le chemin demandé au
chemin servi. Témoin actuel : `/map`.

**Ce qu'une classe PORTE ne se lit ni dans le CSS ni par sous-chaîne** (25/08).
Le filtre « cette règle peut-elle mordre ici ? » cherchait le nom de classe
n'importe où dans la page : un commentaire CSS disant « la feuille commune »
rendait les six règles `.feuille` actives, et `toastP`, `vues`, `--f-donnees`
rendaient `.toast`, `.vue`, `.donnee` actives. Le CSS décrit ce qui SERAIT
peint ; seuls le markup et le JS disent ce qui EXISTE — et un nom de classe
est un **jeton entier**.

**Un cache donne DEUX prix à une mesure** (24/08). Le banc a crié « score
parfait = ALARME » sur `/api/names` à 0,3 ms, et il avait raison de crier :
il ne connaissait qu'un prix. Il en mesure deux depuis — premier appel après
expiration, et ce que paie une page. Tout banc qui mesure une route mise en
cache doit faire pareil, sinon il ment deux fois : fausse alarme d'un côté,
coût réel escamoté de l'autre.

> **Piège d'horloge, payé le 23/08** : `device_bash` tourne dans une VM en
> **UTC**. `date` y annonce 14:25 quand il est 16:25 chez Mike. Les epochs du
> serveur (`/api/maint/status`, `now`) sont la seule heure fiable.
>
> **Et le dossier monté a un cache** (24/08) : `tail` peut rendre un contenu
> vieux de 25 min alors que le fichier vient d'être écrit. Le `mtime` (`ls -l`,
> `date -r`) dit la vérité ; `device_stage_files` attend le cache.

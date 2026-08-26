# Amorce de reprise — MediaLibrary

> À coller après connexion de `C:\Prog\Claude\MediaLibrary`. Règles et
> protocole : `CLAUDE.md`. Ici : **l'état et le prochain pas, rien d'autre.**

Tu reprends **MediaLibrary**. **VÉRIFIE avant de lire** : `.git/HEAD`,
`.git/logs/HEAD` et `.git/logs/refs/heads/main` disent ce qui a été commité et
FUSIONNÉ — ce document, non. Puis `ROADMAP.md`, `eval/DECISIONS.md`,
`eval/METHODE.md` — et `docs/DECISIONS_OUTILLAGE.md` si le sujet touche aux
canaux, à la livraison ou au MCP. Débrief en 2–3 lignes, puis on attaque.

## Où on en est (26/08/2026, fin de session 47)

**Rien ne tourne, rien n'attend.** Le serveur porte le code livré et il a été
OBSERVÉ page par page, au clavier, dans Chrome.

**Le chantier de l'accessibilité des contrôles est CLOS.**
`verifier_controles.py` (neuf, 42 vérifications) apparie chaque élément
cliquable à sa balise, sur les onze pages :

| | avant | après |
|---|---|---|
| gestionnaires de clic | 154 | 154 |
| sur un contrôle **natif** | 132 | **138** |
| opérables à la main | 0 | 3 |
| déclarés redondants | — | 13 |
| **griefs de niveau A** | **18** | **0** |

Ce qui était cassé : **le filtre de la page la plus utilisée** (les chips de
`gallery`, en `span` + `onclick`), **ouvrir une photo** (43 000 vignettes sans
chemin clavier), sélectionner une photo d'animal, ouvrir une fiche d'animal,
choisir une photo de référence. Tout est joignable au clavier, mesuré et
observé.

**Le chip est passé de 32 px à `--touch` (44)** — Mike a tranché la
contradiction que `components.css` portait contre son propre plancher. Effet
de bord observé : le chip fait maintenant exactement la hauteur du champ de
filtre voisin.

**⚠ ACTION EN ATTENTE DE MIKE, deuxième session de suite** : la skill
`photo-ui` du COMPTE date du 30/07 — `#4A8C7B`, destructif en contour, ni
`--salle-4`, ni les `-p`, ni `.hors-ecran`, ni le chip à 44 px. **Le fichier
du dépôt est à jour ; c'est la copie du compte qui manque.** Tant qu'elle
n'est pas enregistrée, une session qui s'y fie réintroduit la couleur qui
échoue l'AA. **Vérifier AVANT de toucher au CSS** — et se fier à
`ui/tokens.css` + `ui/components.css`, qui sont la vérité.

## Prochain pas

1. **Le point 3 du plancher n'a toujours pas d'instrument.** « Cibles ≥ 44 px »
   est écrit depuis le début et n'a jamais été COMPTÉ — exactement l'histoire
   du contraste (25/08) et des contrôles (26/08), deux fois sur deux avec des
   manquements réels au bout. Un cas est déjà tombé par hasard pendant la
   session : `browse` déclare `.fxtoast .b { min-height: 36px }`. Un
   `verifier_cibles.py` (famille `verifier_`, lecture seule) lirait la taille
   déclarée de chaque élément interactif des onze pages. **Deux pièges connus
   d'avance** : une hauteur ne se lit pas toujours dans le CSS (un `<span>`
   inline ignore `min-height` — c'est ce qui dormait dans `gallery`), et la
   taille réelle demande le navigateur, pas le texte. Dire la portée, comme
   toujours.
2. **`gallery` peut adopter `components.css`** — 7 pages sur 11. Elle écrit
   maintenant le chip canonique (44 px, `inline-flex`, `gap`, `font`) sous ses
   propres noms `.chip`/`.pchip`, et son `.btn` n'existe pas. **L'ordre de
   `--apres` est la moitié de la preuve** : la feuille commune EN PREMIER.
3. **Reste d'audit** : O8–O9, O11, O13–O15 ; **I1** visible dans `/reglages`.
   O15 (purge de `photo_thumbs/`) gagne en poids.

## En fin de projet — décidé, mesuré, en attente d'un geste

Ces deux points ne sont plus des questions ouvertes : tout est chiffré, il ne
manque que le temps. **Ne pas les faire passer devant le code.**

- **Le Takeout Google** (lancé le 25/08 par Mike, ~75 Go). À son arrivée :
  dézipper, puis `verifier_photos_google.py --takeout "<dossier>"`. Quatre
  verdicts, et **un seul ABSENT interdit tout effacement**. Effacer se fait
  sur `photos.google.com` — jamais depuis l'app du téléphone, qui efface aussi
  l'appareil — et le quota ne bouge qu'une fois la CORBEILLE vidée (60 j).
  **Le compte est à 96 %** : quand il est plein, Gmail cesse de RECEVOIR.
- **La copie hors site (12 bis)** : Synology DS224+ → **Infomaniak Swiss
  Backup**, Hyper Backup/Swift, ~**CHF 6 TTC/mois** pour 1 To, données en
  Suisse. Fonds mesuré : **291 Go**. Premier envoi **~8 nuits** à 13,8 Mbit/s —
  **le débit n'est PAS un préalable**. Compte Infomaniak **personnel**. Clé de
  chiffrement imprimée et rangée ailleurs. Et une restauration d'épreuve : une
  sauvegarde jamais restaurée n'est pas une sauvegarde.

## Réflexes

**Le serveur a un journal : `_journal_serveur.log`** (`journal_serveur.py`),
miroir daté de sa console, lisible depuis la sandbox et qui survit à sa mort.
Il porte les **tracebacks des threads qui meurent**. **Le lire avant de
supposer** — et depuis la DERNIÈRE bannière, pas la première :

    L=$(grep -n "===== DEMARRAGE" _journal_serveur.log | tail -1 | cut -d: -f1)
    tail -n +$L _journal_serveur.log | grep -n "THREAD MORT\|EXCEPTION\|Traceback"

Plantage dur d'une lib native : `_journal_serveur_crash.log`.

**`ui/pages/` et `ui/*.css` sont relus À CHAUD** (signature mtime + taille) :
une page corrigée est servie sans redémarrage — vérifié le 26/08, six pages
ont changé de taille sur le serveur vivant. **Seul `server.py` exige le
redémarrage.** Ça ne dispense pas d'OBSERVER.

**Un nom accentué passe au banc par le jeton `b64:`** (23/08) :

    verifier_xmp_personnes.py --nom b64:U3TDqXBoYW5lIFBsb3V2aW4

`python3 -c "import base64;print(base64.urlsafe_b64encode('Béa'.encode()).decode().rstrip('='))"`.

**Le contrôle 5 ne réclame plus de redémarrage pour l'outillage** (23/08) : il
lit le graphe des imports de `server.py`. `git_agent.py`, `banc_agent.py`,
`mcp_serveur.py`, `appliquer_*`, `verifier_*`, `inventaire_*`, `bundle.py`,
`ui_gabarits.py` sont DEHORS — plus besoin de `force=` pour eux.

**Un `_exiftool_tmp` condamne sa photo** (24/08). ExifTool recopie la photo à
côté avant d'écrire et REFUSE d'écrire tant que ce temporaire est là : une
écriture tuée en route rend la photo non réécrivable, définitivement et sans
bruit. Balayage possible mais **jamais par défaut** (`--balayer-fantomes`) ;
surveillance par `inventaire_fantomes.py`. **Un fantôme SANS original à côté
ne s'efface pas en lot** : c'est peut-être la seule copie qui reste.

**Un compte d'échecs ne se répare pas ; une cause, si** (24/08). La passe
disait `en echec : 3` et onze des treize étaient le même fantôme.

**Jamais deux écrivains, y compris contre soi-même** (24/08) :
`appliquer_xmp_personnes.py` pose un verrou (`_corbeille_xmp/_ecriture.lock`,
preuve par FRAÎCHEUR, repris après 10 min sans signe de vie).

**Un commentaire est de la PROSE, quel que soit le langage** (25/08, appris
quatre fois le même jour ; 26/08, une cinquième). Un commentaire CSS disant
« la feuille commune » a rendu six règles `.feuille` actives sur une page qui
n'en porte aucune. **Retirer les commentaires AVANT de lire** — et un nom de
classe est un **jeton entier**, pas un morceau de mot. **L'exception est une
DÉCLARATION** (`/* contraste: hors-portee -- … */`, `/* controle: redondant
-- … */`) : elle vit dans un commentaire, donc elle se lit AVANT le retrait.

**Un banc qui ne SAIT pas ne rend pas vert** (25/08). Un couple non mesuré
compte comme un grief, et tout rapport dit sa PORTÉE. **Ce qui ne se calcule
pas se DÉCLARE dans la source, avec une raison obligatoire — jamais en dur
dans l'instrument**, sinon il devient aveugle au cas suivant sans qu'on le
sache.

**Nommer un angle mort ne le ferme pas** (26/08). Le docstring de
`verifier_controles.py` listait les littéraux d'expression régulière JS comme
un angle mort THÉORIQUE. Il était réel : le `"` de `/[&<>"]/g`, en tête de
`subjects`, ouvrait une fausse chaîne et faisait disparaître un bouton écrit
cent lignes plus bas — l'instrument rendait « non décidable » là où il fallait
lire « c'est un bouton, donc c'est vert ». **Nommer dit où l'on ne voit pas ;
ça ne fait pas voir.** Quand un angle mort nommé MORD, il se ferme.

**L'ordre de la cascade a QUATRE étages** (25/08), et il est la moitié de
toute preuve CSS : `components.css` (au marqueur, AVANT le `<style>` de la
page) → la page → `tokens.css` → `base.css` (à `</head>`, il gagne les
égalités). Une feuille qui ne change pas doit figurer **des deux côtés**.

**Changer une BALISE change son style par défaut** (26/08). `<span>` →
`<button>` : la police (Arial 13,3 px, un bouton n'hérite pas de `body`),
l'alignement (centré d'office) et surtout `display` (inline → inline-block,
ce qui **rend actif** un `min-height` qui dormait). Les trois se reposent
explicitement, sinon la correction sémantique se voit à l'écran.

**Un `<button>` n'admet que du contenu de PHRASE** (26/08). Les navigateurs
tolèrent un `<div>` dedans, mais un lecteur d'écran lit alors tout le contenu
comme libellé : une vignette s'annoncerait sur trois lignes. Pour ces cas-là,
`tabindex` + `role="button"` + `keydown` Entrée **et** Espace (avec
`preventDefault`, sinon Espace fait défiler la page) — **les trois**.

**Un banc d'observation ment de deux façons** (25/08). Il peut manquer une
panne — et il peut déclarer vert ce qu'il n'a **pas pu regarder**. Un 404
(mauvaise adresse) et un refus de connexion (serveur mort) envoient chercher
la panne à deux endroits opposés : ils ne se disent pas pareil. Et un opt-in
se prouve par son TÉMOIN, encore faut-il l'avoir lu (`/faces` répond **302
vers `/people`** ; urllib suit sans rien dire). Témoin actuel : `/map`.

**Un cache donne DEUX prix à une mesure** (24/08) : premier appel après
expiration, et ce que paie une page.

> **Piège d'horloge, payé le 23/08** : `device_bash` tourne dans une VM en
> **UTC**. `date` y annonce 14:25 quand il est 16:25 chez Mike. Les epochs du
> serveur (`/api/maint/status`, `now`) sont la seule heure fiable.
>
> **Et le dossier monté a un cache** (24/08) : `tail` peut rendre un contenu
> vieux de 25 min alors que le fichier vient d'être écrit. Le `mtime` (`ls -l`,
> `date -r`) dit la vérité ; `device_stage_files` attend le cache.

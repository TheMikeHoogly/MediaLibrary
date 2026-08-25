# Amorce de reprise — MediaLibrary

> À coller après connexion de `C:\Prog\Claude\MediaLibrary`. Règles et
> protocole : `CLAUDE.md`. Ici : **l'état et le prochain pas, rien d'autre.**

Tu reprends **MediaLibrary**. **VÉRIFIE avant de lire** : `.git/HEAD`,
`.git/logs/HEAD` et `.git/logs/refs/heads/main` disent ce qui a été commité et
FUSIONNÉ — ce document, non. Puis `ROADMAP.md`, `eval/DECISIONS.md`,
`eval/METHODE.md` — et `docs/DECISIONS_OUTILLAGE.md` si le sujet touche aux
canaux, à la livraison ou au MCP. Débrief en 2–3 lignes, puis on attaque.

## Où on en est (25/08/2026, session 46)

**Rien ne tourne, rien n'attend.** Le chantier des XMP est CLOS (1 614 couples
nom–photo lus, **0 en écart**, Wilson 0,0 – 0,2 %, contre 18,7 % le 23/08) ;
les 21 fantômes `_exiftool_tmp` sont effacés. Le serveur a été **redémarré et
observé** après le dernier increment.

**Le CSS commun a été mesuré, et la mesure a tué le chantier d'extraction** :
200 déclarations hissables sur 1 754, dont **171 partagées par deux pages
seulement** — 6,2 Ko sur 67. Le vrai sujet est la **divergence** : `.btn` ne
veut pas dire la même chose selon la page.

**La convergence a donc commencé, en opt-in : 5 pages sur 11.** `residu`,
`tranche`, `subjects`, `people` et `pets` posent `<!--UI:components-->` et
reçoivent `ui/components.css`. Les trois dernières écrivaient le canonique
**sous d'autres noms** (`.prim`/`.warn`, `.primary`/`.danger`, valeurs
identiques) — la divergence la plus chère, celle qui ne se voit pas à l'écran.
**Et `people` comme `pets` n'avaient pas `min-height: var(--touch)`** : une
cible tactile sous 44 px, donc une brèche du plancher d'accessibilité, refermée
par le bouton canonique.

**Les trois universelles sont hissées** : `body { background | color |
font-family }`, écrit onze fois à l'identique, vit désormais dans `ui/base.css`
seul — **11 pages sur 11 prouvées IDENTIQUE APRÈS LA CASCADE**. Elles étaient
**trois, pas six** : le reset `*` ne vit que dans NEUF pages (`pets` et
`subjects` ne l'ont jamais eu), donc le hisser serait un CHANGEMENT sur deux
pages, pas un rangement.

**L'ordre réel de la cascade est à quatre étages** : `components.css` (au
marqueur) → `<style>` de la page → `tokens.css` → `base.css` (à `</head>`,
donc il gagne les égalités). C'est pourquoi les trois déclarations ont été
RETIRÉES des onze pages, et pas seulement ajoutées à `base.css` : laissées en
place elles auraient été écrasées sans bruit. **Le marqueur vit AVANT le `<style>` de la page**
— sinon la feuille commune gagnerait la cascade et la page perdrait le dernier
mot au moment même où elle converge. Trois preuves, dans l'ordre : cascade
(`verifier_css_cascade.py --page`), mécanisme (`test_ui_composants.py`, 12),
**serveur vivant** (`verifier_pages_composants.py`, 18 tests) — les trois
vertes, la troisième après redémarrage réel.

**Les deux instruments se sont corrigés cinq fois, sur cinq rouges OBSERVÉS.**
Trois sur la preuve de cascade (l'ordre de `--apres` ; un mot dans un
commentaire CSS ; la recherche par sous-chaîne) : sur `subjects`, elles font
passer les « apparues » de 69 à 25. Deux sur le banc d'observation (un témoin
qui n'était pas une route ; un témoin qui **redirige**, lu ailleurs et jugé
quand même — en vert).

**Le survol et l'état désactivé sont devenus canoniques** (approuvés le
25/08) : token **`--salle-4: #24201D`** (élévation 3), `cursor: not-allowed`,
sous `@media (hover: hover)`, et **chaque variante à fond repose le sien** —
`.btn:hover` pèse (0,2,0) et repeindrait sinon le bouton primaire en gris.

**Et c'est en écrivant ce survol qu'un défaut plus grave est sorti** : le
plancher AA n'avait jamais été calculé. `verifier_contraste.py` (neuf, 20
vérifications) le calcule ; voir « Prochain pas ».

## Prochain pas

1. **Le plancher AA est tenu, et mesuré.** Les trois échecs trouvés le 25/08
   sont corrigés : `--fixateur` assombri `#4A8C7B` → **`#448172`** (4,54:1
   sous `#fff`, teinte et saturation intactes) et le bouton destructif passe
   du **contour au PLEIN** (5,34:1, **sans toucher `--encre`** — l'éclaircir
   aurait cassé son usage comme texte d'erreur sur papier : 2,91:1).
   **19 couples sur 19 mesurés tiennent.** `verifier_contraste.py` rend 0.
   **⚠ La skill `photo-ui` a été mise à jour et envoyée à Mike en fichier —
   si elle n'a pas été enregistrée, sa table de tokens dit encore `#4A8C7B`
   et la prochaine session le réintroduira.** Vérifier avant de toucher au CSS.

2. **Finir la convergence `.btn`** : `upload` est le seul cas restant avec un
   vrai bouton, et son composant est **réellement différent** (pleine
   largeur) — à décider avec Mike, pas à forcer. Les cinq autres pages
   (`gallery`, `browse`, `map`, `reglages`, `faces`) n'ont pas de `.btn`.
   Ensuite `.chip`, même méthode.
   **La procédure est fixée** :
   `cp ui/pages/X.html _avant_css/` → convertir → **prouver** :

       verifier_css_cascade.py --avant _avant_css/X.html \
           --apres ui/components.css ui/pages/X.html --page ui/pages/X.html

   **`ui/components.css` en PREMIER dans `--apres`** : c'est là que le serveur
   l'injecte. Passée en dernier elle gagne une cascade qu'elle ne gagne pas en
   vrai, et invente des changements (deux `.chip` sur `subjects`).
   Puis : ajouter la page à `CONVERTIES` (`test_ui_composants.py`) **et** à
   `ADOPTANTES` (`verifier_pages_composants.py`) → **redémarrer** → le banc →
   livrer. Toute règle « apparue » qui MORD se dit à Mike avant de partir.

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

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

**La convergence a donc commencé, en opt-in.** `residu` et `tranche` posent
`<!--UI:components-->` et reçoivent `ui/components.css` ; leurs `<style>` ne
redéclarent plus le bouton. **Le marqueur vit AVANT le `<style>` de la page**
— sinon la feuille commune gagnerait la cascade et la page perdrait le dernier
mot au moment même où elle converge. Trois preuves, dans l'ordre : cascade
(`verifier_css_cascade.py --page`), mécanisme (`test_ui_composants.py`, 11),
**serveur vivant** (`verifier_pages_composants.py`, 14 tests) — les trois
vertes, la troisième après redémarrage réel.

**Un changement visuel volontaire est parti avec** : dans `residu`, le
`<h3 id="legref">` est dans `<section class="feuille">` et prend donc la police
d'affichage condensée. Seule des 17 règles « apparues » à mordre vraiment.

## Prochain pas

1. **Continuer la convergence `.btn`, par coût croissant.**
   - `subjects` : 3 propriétés + un `padding` différents, à trancher.
   - `people` et `pets` : **les deux manquent `min-height: var(--touch)`**.
     C'est une brèche du plancher d'accessibilité (cible < 44 px), pas un
     goût — elle se corrige donc *avec* la convergence, pas après. `pets`
     porte en plus un `#ffffff0d` en dur.
   - Unifier le vocabulaire : `.prim` / `.warn` / `.primary` / `.danger`
     → `.btn--confirmer` / `--destructif` / `--discret`.
   - `upload` : composant réellement différent (pleine largeur). **À décider
     avec Mike, pas à forcer.**
   **La procédure est fixée** : convertir → `verifier_css_cascade.py --avant
   <copie> --apres <page> --page <page>.html` → ajouter la page à `ADOPTANTES`
   dans `verifier_pages_composants.py` → **redémarrer** → le banc → livrer.
   Toute règle « apparue » qui MORD se dit à Mike avant de partir.

2. **Les six déclarations universelles dans `base.css`** (approuvé, pas fait) :
   `body{background|color|font-family}` (11 pages) et `*{box-sizing|margin|
   padding}` (9 pages). Gain en octets nul ; une source de vérité au lieu de
   onze. Même preuve `--avant/--apres`.

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
à-dire exactement le jour où les neuf pages restantes cassent. Le témoin
(`/faces`) coûte une requête et vaut la garantie.

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

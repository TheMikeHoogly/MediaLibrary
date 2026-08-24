# Amorce de reprise — MediaLibrary

> À coller après connexion de `C:\Prog\Claude\MediaLibrary`. Règles et
> protocole : `CLAUDE.md`. Ici : **l'état et le prochain pas, rien d'autre.**

Tu reprends **MediaLibrary**. **VÉRIFIE avant de lire** : `.git/HEAD`,
`.git/logs/HEAD` et `.git/logs/refs/heads/main` disent ce qui a été commité et
FUSIONNÉ — ce document, non. Puis `ROADMAP.md`, `eval/DECISIONS.md`,
`eval/METHODE.md` — et `docs/DECISIONS_OUTILLAGE.md` si le sujet touche aux
canaux, à la livraison ou au MCP. Débrief en 2–3 lignes, puis on attaque.

## La réparation des XMP est FINIE, et PROUVÉE

Terminée le 24/08 à 03:07 : **18 828 photos balayées, 3 128 réécrites**
(181 + 2 947), **13 échecs**, **aucun nom sauté**. Plus rien ne tourne : le
serveur peut redémarrer, les bancs NAS peuvent tourner, on peut renommer.

**Le chiffre qui comptait est pris** : `verifier_xmp_toutes_personnes.py`,
machine calme — **0,2 % d'écart** (Wilson 0,1–0,5 %, 5 sur 2 247 couples lus)
contre **18,7 %** le 23/08. Les intervalles ne se touchent pas.

**Ce qui reste tient en deux gestes de Mike** (famille `appliquer_`, hors de
portée du banc) — et le résidu mesuré est EXACTEMENT ça :

1. **Les fantômes `_exiftool_tmp` — il y en a 21, pas 11.** ExifTool recopie
   la photo dans `<photo>_exiftool_tmp` avant d'écrire et **refuse d'écrire
   tant que ce temporaire existe** : une écriture tuée en route condamne sa
   photo, définitivement et sans bruit. Datés du 06/07 au 24/08, dix d'entre
   eux ne figurent dans AUCUN journal. Effacer est sans risque — l'original
   est le fichier d'à côté, intact :

       Get-ChildItem \\NAS-Bremblens\home\Photos -Recurse -Filter *_exiftool_tmp | Remove-Item -Force -Verbose

   puis `python appliquer_xmp_personnes.py --reprendre-echecs --appliquer`.
   Le script sait aussi le faire lui-même — `--balayer-fantomes`, jamais par
   défaut. Les 2 derniers échecs sont des JPEG tronqués — illisibles, bat 17.
2. **`Val` : 3 photos.** Mesuré fichiers en main : Val 1 091/1 094, Yann Mamin
   13/13. Des deux noms sautés par la passe de 21:38, un seul est à reprendre.

       python appliquer_xmp_personnes.py --nom Val --appliquer

Après ces deux gestes, relancer `verifier_xmp_toutes_personnes.py` doit rendre
**0 écart**. C'est la fin du chantier.

## Ensuite

3. **`/api/names`, pas O7.** Le filtre nommé coûte 191–208 ms ; `/api/names`
   coûte **359–364 ms** et part au chargement de CHAQUE page. Re-mesurer
   `mesure_recherche_nommee.py` sur une machine CALME (le verdict d'O7 bascule
   autour de son seuil sous charge), puis traiter l'autocomplétion : même
   cause — un balayage complet de l'index par requête — sans doute même
   remède. **Et rendre `total`/`tronque` dans `/api/search`** : la route les
   calcule et ne les rend pas ; seule la page `/files?q=` les reçoit.
4. **Suite de `ui/`** : le CSS commun — chaque page porte encore son `<style>`.
   L'octet servi CHANGE, donc la preuve « identique au caractère près » qui a
   tenu les onze gabarits ne s'applique plus : une autre preuve, décidée AVANT
   le code.
5. **Copie HORS SITE (12 bis)** — un sinistre qui emporte le PC ET le NAS
   emporte tout. Décision de Mike avant du code.
6. **Reste d'audit** : O8–O9, O11, O13–O15 ; **I1** visible dans `/reglages`.

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
`mcp_serveur.py`, `appliquer_*`, `verifier_*`, `bundle.py`, `ui_gabarits.py`
sont DEHORS — plus besoin de `force=` pour eux.

**Jamais deux écrivains, y compris contre soi-même** (24/08) :
`appliquer_xmp_personnes.py` pose un verrou d'écriture
(`_corbeille_xmp/_ecriture.lock`, preuve par fraîcheur, repris après 10 min
sans signe de vie). Deux passes lancées à la main se voient enfin.

**Un compte d'échecs ne se répare pas ; une cause, si** (24/08). La passe
disait `en echec : 3` et il a fallu relire le jsonl pour voir que onze des
treize étaient le même fantôme. Les causes sont maintenant comptées et dites.

> **Piège d'horloge, payé le 23/08** : `device_bash` tourne dans une VM en
> **UTC**. `date` y annonce 14:25 quand il est 16:25 chez Mike. Les epochs du
> serveur (`/api/maint/status`, `now`) sont la seule heure fiable.

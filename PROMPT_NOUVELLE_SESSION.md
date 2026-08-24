# Amorce de reprise — MediaLibrary

> À coller après connexion de `C:\Prog\Claude\MediaLibrary`. Règles et
> protocole : `CLAUDE.md`. Ici : **l'état et le prochain pas, rien d'autre.**

Tu reprends **MediaLibrary**. **VÉRIFIE avant de lire** : `.git/HEAD`,
`.git/logs/HEAD` et `.git/logs/refs/heads/main` disent ce qui a été commité et
FUSIONNÉ — ce document, non. Puis `ROADMAP.md`, `eval/DECISIONS.md`,
`eval/METHODE.md` — et `docs/DECISIONS_OUTILLAGE.md` si le sujet touche aux
canaux, à la livraison ou au MCP. Débrief en 2–3 lignes, puis on attaque.

## Le chantier des XMP est CLOS, à zéro

`verifier_xmp_toutes_personnes.py`, machine calme : **1 614 couples nom–photo
lus, 0 en écart, 0 nom en écart** — contre **18,7 %** le 23/08. La réparation a
réécrit 3 128 photos sur 18 828 balayées ; les 21 fantômes `_exiftool_tmp` sont
effacés ; `inventaire_fantomes.py` en trouve **0** sur les deux racines.
Il n'y a plus rien à faire de ce côté. Ce qui reste vaut pour la MÉTHODE :

- **Un `_exiftool_tmp` condamne sa photo.** ExifTool refuse d'écrire tant que
  son temporaire est là et n'a pas d'option pour l'écraser : une écriture tuée
  en route rend la photo non réécrivable, définitivement et sans bruit. Le
  balayage est possible mais **jamais par défaut** :
  `appliquer_xmp_personnes.py --reprendre-echecs --balayer-fantomes --appliquer`.
  Le surveiller : `inventaire_fantomes.py` (banc, lecture seule).
- **Un fantôme SANS original à côté ne s'efface pas en lot** : ExifTool est
  peut-être mort entre le remplacement et le renommage, et c'est alors la
  seule copie qui reste. L'inventaire les compte à part et les nomme.

## Ensuite

3. **`/api/names`, et O7 est classé.** Mesure CALME du 24/08 : le filtre
   nommé coûte **139 ms** — sous le seuil de 200, verdict **mineur**, à peser
   contre le reste de la feuille et non à traiter par réflexe. `/api/names`
   coûte **298 ms** et part au chargement de CHAQUE page : c'est lui le
   chantier. La cause est identifiée et le remède écrit (non livré) : la liste
   des noms ne coûte rien, c'est le COMPTAGE qui balaie les 43 000 fiches et
   lit chaque mot-clé à chaque appel. Mettre en cache le COMPTE, jamais la
   LISTE — un nom créé à l'instant doit paraître tout de suite, sinon on le
   recrée en « Nouveau » (défaut I7). `total`/`tronque` : **fait le 24/08**,
   observé en réel (`total 5898, rendus 1500, tronque 4398`).
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

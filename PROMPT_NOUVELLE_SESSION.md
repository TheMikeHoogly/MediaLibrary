# Amorce de reprise — MediaLibrary

> À coller après connexion de `C:\Prog\Claude\MediaLibrary`. Règles et
> protocole : `CLAUDE.md`. Ici : **l'état et le prochain pas, rien d'autre.**

Tu reprends **MediaLibrary**. **VÉRIFIE avant de lire** : `.git/HEAD`,
`.git/logs/HEAD` et `.git/logs/refs/heads/main` disent ce qui a été commité et
FUSIONNÉ — ce document, non. Puis `ROADMAP.md`, `eval/DECISIONS.md`,
`eval/METHODE.md` — et `docs/DECISIONS_OUTILLAGE.md` si le sujet touche aux
canaux, à la livraison ou au MCP. Débrief en 2–3 lignes, puis on attaque.

## La réparation des XMP est FINIE — reste à la PROUVER

Terminée le 24/08 à 03:07 : **18 828 photos balayées, 3 128 réécrites**
(181 + 2 947), **13 échecs**, **aucun nom sauté**. Plus rien ne tourne : le
serveur peut redémarrer, les bancs NAS peuvent tourner, on peut renommer.

**Le seul chiffre qui compte n'est pas encore pris.** Dans cet ordre :

1. **Rattraper `Val` et `Yann Mamin`** — sautés par la passe de 21:38 (une
   connexion fermée) ; leurs photos qui portaient un AUTRE nom sont marquées
   « faites », la reprise ne les rattrapera pas. `--nom` l'ignore, lui :

       python appliquer_xmp_personnes.py --nom Val --appliquer
       python appliquer_xmp_personnes.py --nom "Yann Mamin" --appliquer

   Famille `appliquer_` : **geste de Mike**, hors de portée du banc.
2. **Les 13 échecs.** 11 sont un `_exiftool_tmp` fantôme sur le NAS, laissé par
   un ExifTool tué en route, qui **empêche définitivement** de réécrire sa
   photo ; 2 sont des JPEG tronqués (illisibles, bat 17). Effacer les fantômes
   (`Get-ChildItem \\NAS-Bremblens\home\Photos -Recurse -Filter *_exiftool_tmp`),
   puis `python appliquer_xmp_personnes.py --reprendre-echecs --appliquer` :
   il relit les journaux, refait ces photos-là et pas 18 828.
3. **`verifier_xmp_toutes_personnes.py`** — il relit le DISQUE et dit si les
   **18,7 %** de couples nom–photo perdus sont tombés. C'EST LE CHIFFRE.
   Par le canal des bancs (`_commande_banc.txt`), il est long.

## Ensuite

4. **`/api/names`, pas O7.** Le filtre nommé coûte 191–208 ms ; `/api/names`
   coûte **359–364 ms** et part au chargement de CHAQUE page. Re-mesurer
   `mesure_recherche_nommee.py` sur une machine CALME (le verdict d'O7 bascule
   autour de son seuil sous charge), puis traiter l'autocomplétion : même
   cause — un balayage complet de l'index par requête — sans doute même
   remède. **Et rendre `total`/`tronque` dans `/api/search`** : la route les
   calcule et ne les rend pas ; seule la page `/files?q=` les reçoit.
5. **Suite de `ui/`** : le CSS commun — chaque page porte encore son `<style>`.
   L'octet servi CHANGE, donc la preuve « identique au caractère près » qui a
   tenu les onze gabarits ne s'applique plus : une autre preuve, décidée AVANT
   le code.
6. **Copie HORS SITE (12 bis)** — un sinistre qui emporte le PC ET le NAS
   emporte tout. Décision de Mike avant du code.
7. **Reste d'audit** : O8–O9, O11, O13–O15 ; **I1** visible dans `/reglages`.

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

**Un compte d'échecs ne se répare pas ; une cause, si** (24/08). La passe
disait `en echec : 3` et il a fallu relire le jsonl pour voir que onze des
treize étaient le même fantôme. Les causes sont maintenant comptées et dites.

> **Piège d'horloge, payé le 23/08** : `device_bash` tourne dans une VM en
> **UTC**. `date` y annonce 14:25 quand il est 16:25 chez Mike. Les epochs du
> serveur (`/api/maint/status`, `now`) sont la seule heure fiable.

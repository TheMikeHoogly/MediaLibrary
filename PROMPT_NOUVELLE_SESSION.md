# Amorce de reprise — MediaLibrary

> À coller après connexion de `C:\Prog\Claude\MediaLibrary`. Règles et
> protocole : `CLAUDE.md`. Ici : **l'état et le prochain pas, rien d'autre.**

Tu reprends **MediaLibrary**. **VÉRIFIE avant de lire** : `.git/HEAD`,
`.git/logs/HEAD` et `.git/logs/refs/heads/main` disent ce qui a été commité et
FUSIONNÉ — ce document, non. Puis `ROADMAP.md`, `eval/DECISIONS.md`,
`eval/METHODE.md` — et `docs/DECISIONS_OUTILLAGE.md` si le sujet touche aux
canaux, à la livraison ou au MCP. Débrief en 2–3 lignes, puis on attaque.

## Où on en est (25/08/2026, fin de session 45)

**Rien ne tourne, rien n'attend.** Le chantier des XMP est CLOS et le serveur
est à jour. `main` = `b6943f3`.

**Le chiffre de clôture** : `verifier_xmp_toutes_personnes.py`, machine calme
— **1 614 couples nom–photo lus, 0 en écart** (Wilson 0,0 – 0,2 %), contre
**255 sur 1 364 (18,7 %)** le 23/08. La réparation a réécrit 3 128 photos sur
18 828 balayées ; les 21 fantômes `_exiftool_tmp` sont effacés ;
`inventaire_fantomes.py` en trouve **0**. La règle 2 tient dans les fichiers.

**Trois défauts trouvés en chemin, tous corrigés** : la reprise notait un échec
comme fait (les 13 échecs étaient irrattrapables) ; un échec ne disait que son
compte, jamais sa cause ; « jamais deux écrivains » ne valait pas contre
soi-même. **Et `/api/search` rend enfin `total`/`tronque`**, `/api/names` passe
de 292 ms à 0,6 ms par page, O7 est classé *mineur* (139–146 ms, calme).

## Prochain pas

1. **Suite de `ui/` : le CSS commun.** Chaque page porte encore son `<style>`.
   L'octet servi CHANGE, donc la preuve « identique au caractère près » qui a
   tenu les onze gabarits ne s'applique plus. **La preuve proposée, à trancher
   avant le code** : « identique APRÈS LA CASCADE » — un instrument qui lit le
   `<style>` d'avant et l'ensemble (commun + reste de la page) d'après, et
   compare les règles résolues, sélecteur par sélecteur, déclaration par
   déclaration, dans l'ordre du cascade. Ce qu'il ne saura pas décider —
   `@media` imbriqués, `!important`, ordre entre deux feuilles — il doit le
   NOMMER, pas le laisser passer : c'est là que se cacherait la régression.
   Une page à la fois, la plus simple d'abord.
2. **Copie HORS SITE (12 bis)** — un sinistre qui emporte le PC ET le NAS
   emporte tout. **Décision de Mike avant du code** : quel support, quelle
   cadence, quel chiffrement.
3. **Reste d'audit** : O8–O9, O11, O13–O15 ; **I1** visible dans `/reglages`.
   O15 (purge de `photo_thumbs/`) gagne en poids.
4. **Ce que les 24 h ont laissé ouvert, sans urgence** : le serveur, lui aussi,
   laisse des fantômes quand une de ses écritures est tuée — `person_writer`,
   `tag_worker`. `inventaire_fantomes.py` le dira ; il n'a aucun `--balayer`.
   Le lancer de temps en temps suffit tant que le chiffre reste à 0.

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

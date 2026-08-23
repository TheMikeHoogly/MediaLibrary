# Amorce de reprise — MediaLibrary

> À coller après connexion de `C:\Prog\Claude\MediaLibrary`. Règles et
> protocole : `CLAUDE.md`. Ici : **l'état et le prochain pas, rien d'autre.**

Tu reprends **MediaLibrary**. **VÉRIFIE avant de lire** : `.git/HEAD`,
`.git/logs/HEAD` et `.git/logs/refs/heads/main` disent ce qui a été commité et
FUSIONNÉ — ce document, non. Puis `ROADMAP.md`, `eval/DECISIONS.md`,
`eval/METHODE.md` — et `docs/DECISIONS_OUTILLAGE.md` si le sujet touche aux
canaux, à la livraison ou au MCP. Débrief en 2–3 lignes, puis on attaque.

## ⚠ EN COURS depuis le 23/08 21:38 — une réparation des XMP

`appliquer_xmp_personnes.py --tous --appliquer` réécrit les XMP du fonds dans
la fenêtre PowerShell de Mike. **D'abord, savoir si elle tourne encore** :
`_corbeille_xmp/_tous_faits.txt` grossit-il ? Repère du 23/08 à 22:02 —
**4 596 photos balayées sur ~18 900, 118 réécrites**, débit soutenu
**0,47 photo/s**, donc une fin attendue entre **04 h et 07 h**, pas 03 h.
Le taux de réécriture doit MONTER : le balayage suit l'ordre alphabétique des
chemins, donc les années anciennes d'abord, et les écarts connus étaient sur
2022–2024.

Tant qu'elle tourne :

- **Ne PAS nommer, renommer ou fusionner** dans l'interface : la file du
  serveur repartirait et le script s'arrêterait (proprement — il reprend —
  mais la nuit serait perdue).
- **Ne PAS ARRÊTER LE SERVEUR** (nuance du 23/08, session 43). L'amorce
  précédente disait « redémarrer ne casse rien » : c'est vrai des écritures,
  faux du reste. La passe tourne sur le code d'AVANT le correctif de
  `cles_du_nom` — une requête qui échoue fait SAUTER un nom en silence, et ses
  photos sont marquées « faites ». Un serveur absent, c'est 352 noms sautés.
- **Ne PAS lancer de banc qui lit le NAS en masse** (`verifier_xmp_*`,
  `mesure_xmp_*`) : ils se disputent ExifTool et le partage, et toute mesure de
  débit prise pendant ce temps est fausse.
- **Ne JAMAIS supprimer `_corbeille_xmp/_tous_faits.txt`** : c'est la reprise.
- Le TAGUEUR tourne en même temps (une photo toutes les ~22 s) et écrit les
  mêmes fichiers. **Ce n'est pas une fuite de la règle 2** : `tag_worker`
  re-fusionne `_noms_attendus()` depuis l'index juste avant d'écrire, exprès
  pour cette course. Il coûte du NAS, pas des noms.

**À la fin, dans cet ordre** : rattraper les noms sautés — la liste
(`_corbeille_xmp/_tous_noms_sautes.txt`) n'existe QUE sur le code neuf, donc
cette passe-ci ne la laissera pas ; au moins `Val` et `Yann Mamin`, par
`--nom X --appliquer` (ce mode ignore le fichier de reprise). Puis
`verifier_xmp_toutes_personnes.py`, qui relit le DISQUE : c'est lui qui
NOMMERA le résidu, donc les noms sautés qu'on ne connaît pas.

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

> **Piège d'horloge, payé le 23/08** : `device_bash` tourne dans une VM en
> **UTC**. `date` y annonce 14:25 quand il est 16:25 chez Mike. Les epochs du
> serveur (`/api/maint/status`, `now`) sont la seule heure fiable.

## Où on en est (23/08/2026, fin de session 43)

**La 42 a trouvé, chiffré et bouché une fuite de la règle 2** : l'index portait
des noms que les FICHIERS ignoraient — **18,7 % des couples nom–photo**, soit
~5 800 photos. Cause : `_enqueue_person_write` et `_file_personnes_reprise`
jugeaient de l'existence par `p.is_file()`, qui interroge un partage SMB et
répond « non » sur un fichier qui existe. Les deux jugent désormais zéro. La
réparation de l'arriéré est ce qui tourne cette nuit.

**La 43 a réparé le contrôle 5 de l'agent git.** Il jugeait sur le NOM et
réclamait à l'outillage une preuve qui n'existe pas ; il lit maintenant le
graphe des imports (29 modules dedans, 134 dehors). 17 vérifications neuves,
13 rouges sur l'ancien code, 45/45 vertes sous Windows.

## Prochain pas

1. **La fin de la réparation** (ci-dessus) — puis `verifier_xmp_toutes_personnes.py`,
   qui dira si les 18,7 % sont tombés. C'est le seul chiffre qui compte.
2. **O7 — la recherche nommée** : `_cles_portant` balaie 64 676 entrées en
   `lower()` à CHAQUE requête. **Mesurer d'abord** (banc contre le serveur, pas
   de lecture NAS), coder ensuite, et seulement si le chiffre le justifie.
3. **Suite de `ui/`** : le CSS commun — chaque page porte encore son `<style>`.
   L'octet servi CHANGE, donc la preuve « identique au caractère près » qui a
   tenu les onze gabarits ne s'applique plus telle quelle : il faut une autre
   preuve, décidée AVANT le code.
4. **Copie HORS SITE (12 bis)** — un sinistre qui emporte le PC ET le NAS
   emporte tout. Décision de Mike avant du code.
5. **Reste d'audit** : O8–O9, O11, O13–O15 ; **I1** visible dans `/reglages`.

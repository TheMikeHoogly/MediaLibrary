# Amorce de reprise — MediaLibrary

> À coller après connexion de `C:\Prog\Claude\MediaLibrary`. Règles et
> protocole : `CLAUDE.md`. Ici : **l'état et le prochain pas, rien d'autre.**

Tu reprends **MediaLibrary**. **VÉRIFIE avant de lire** : `.git/HEAD`,
`.git/logs/HEAD` et `.git/logs/refs/heads/main` disent ce qui a été commité et
FUSIONNÉ — ce document, non. Puis `ROADMAP.md`, `eval/DECISIONS.md`,
`eval/METHODE.md` — et `docs/DECISIONS_OUTILLAGE.md` si le sujet touche aux
canaux, à la livraison ou au MCP. Débrief en 2–3 lignes, puis on attaque.

## ⚠ LA RÉPARATION DES XMP — reprise le 23/08 vers 23 h

`appliquer_xmp_personnes.py --tous --appliquer` réécrit les XMP du fonds dans
la fenêtre PowerShell de Mike. **D'abord, savoir si elle tourne encore** :
`_corbeille_xmp/_tous_faits.txt` grossit-il ? Repères : **4 800 photos sur
~18 900** au premier arrêt, débit soutenu **0,3 à 0,5 photo/s**.

**Elle est déjà morte une fois, et il faut savoir pourquoi.** Lancée à 21:38,
arrêtée à **22:09:40**, onze secondes après un `🤖 Auto-ajout : 14 visage(s)`.
Le curateur rattache des visages TOUT SEUL toutes les quatre à cinq minutes ;
chaque auto-ajout remplit `PERSON_QUEUE` ; la passe s'arrêtait au premier
signe. **Corrigé le 23/08** : elle ATTEND que la file retombe (patience 30 min,
`--patience`), sans jamais écrire pendant ce temps. Si elle s'arrête encore,
**lire la raison** — ce n'est plus celle-là.

Tant qu'elle tourne :

- **Ne PAS nommer, renommer ou fusionner** dans l'interface : elle attendra
  poliment, mais un gros geste (un renommage = des milliers d'opérations)
  épuisera sa patience et l'arrêtera.
- **Ne PAS ARRÊTER LE SERVEUR.** L'amorce du 42 disait « redémarrer ne casse
  rien » : c'est vrai des écritures, faux du reste. La passe demande au serveur
  les clés de chaque nom — un serveur absent, et sur le code d'avant le
  correctif de `cles_du_nom`, ce sont des noms sautés en silence.
- **Ne PAS lancer de banc qui lit le NAS en masse** (`verifier_xmp_*`,
  `mesure_xmp_*`) : ils se disputent ExifTool et le partage, et toute mesure de
  débit prise pendant ce temps est fausse.
- **Ne JAMAIS supprimer `_corbeille_xmp/_tous_faits.txt`** : c'est la reprise.
- Le TAGUEUR tourne en même temps (une photo toutes les ~22 s) et écrit les
  mêmes fichiers. **Ce n'est pas une fuite de la règle 2** : `tag_worker`
  re-fusionne `_noms_attendus()` depuis l'index juste avant d'écrire, exprès
  pour cette course. Il coûte du NAS, pas des noms.

**À la fin, dans cet ordre** : rattraper les noms sautés — la liste
(`_corbeille_xmp/_tous_noms_sautes.txt`) n'existe QUE sur le code neuf ; au
moins `Val` et `Yann Mamin`, par `--nom X --appliquer` (ce mode ignore le
fichier de reprise). Puis `verifier_xmp_toutes_personnes.py`, qui relit le
DISQUE : c'est lui qui NOMMERA le résidu, donc les noms sautés inconnus.

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

**La 43 a fait trois choses.** (1) Le **contrôle 5** de l'agent git jugeait sur
le NOM et réclamait à l'outillage une preuve qui n'existe pas ; il lit
maintenant le graphe des imports (29 modules dedans, 134 dehors) — 17
vérifications, 13 rouges sur l'ancien code. (2) La **réparation attend** la
file du serveur au lieu d'abandonner : le curateur la tuait toutes les quatre
minutes (voir plus haut) — 7 fonctions neuves, 7 rouges, 56/56 vertes.
(3) **O7 est mesuré** : le filtre nommé coûte **191–208 ms** (seuil écrit
d'avance à 200 : le verdict bascule d'une passe à l'autre, mesure prise sous
charge), mais **`/api/names` coûte 359–364 ms** et part au chargement de CHAQUE
page. C'est lui le sujet, pas O7 — même index, même balayage, plus
`parse_tag_nomme` sur chaque mot-clé.

**Et une trouvaille de chemin** : `/api/search` calcule `detail['total']` et
`detail['tronque']` puis **ne les rend pas**. Seule la page `/files?q=` les
reçoit. Un consommateur de l'API voit 1 500 photos sans savoir qu'il y en avait
5 832 — le plafond silencieux corrigé pour la page le 22/08 et pour le MCP le
23/08 est toujours là, dans la route.

## Prochain pas

1. **La fin de la réparation** (ci-dessus) — puis `verifier_xmp_toutes_personnes.py`,
   qui dira si les 18,7 % sont tombés. C'est le seul chiffre qui compte.
2. **`/api/names`, pas O7.** Re-mesurer `mesure_recherche_nommee.py` sur une
   machine CALME (la réparation finie, le tagueur au repos) : le verdict d'O7
   bascule autour de son seuil sous charge. Puis traiter l'autocomplétion, qui
   coûte le double et part à chaque page. Les deux ont la même cause — un
   balayage complet de l'index par requête — et sans doute le même remède.
   **Et rendre `total`/`tronque` dans `/api/search`** : ils sont calculés.
3. **Suite de `ui/`** : le CSS commun — chaque page porte encore son `<style>`.
   L'octet servi CHANGE, donc la preuve « identique au caractère près » qui a
   tenu les onze gabarits ne s'applique plus telle quelle : il faut une autre
   preuve, décidée AVANT le code.
4. **Copie HORS SITE (12 bis)** — un sinistre qui emporte le PC ET le NAS
   emporte tout. Décision de Mike avant du code.
5. **Reste d'audit** : O8–O9, O11, O13–O15 ; **I1** visible dans `/reglages`.

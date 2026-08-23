# Amorce de reprise — MediaLibrary

> À coller après connexion de `C:\Prog\Claude\MediaLibrary`. Règles et
> protocole : `CLAUDE.md`. Ici : **l'état et le prochain pas, rien d'autre.**

Tu reprends **MediaLibrary**. **VÉRIFIE avant de lire** : `.git/HEAD`,
`.git/logs/HEAD` et `.git/logs/refs/heads/main` disent ce qui a été commité et
FUSIONNÉ — ce document, non. Puis `ROADMAP.md`, `eval/DECISIONS.md`,
`eval/METHODE.md` — et `docs/DECISIONS_OUTILLAGE.md` si le sujet touche aux
canaux, à la livraison ou au MCP. Débrief en 2–3 lignes, puis on attaque.

## Réflexes

**Le serveur a un journal : `_journal_serveur.log`** (`journal_serveur.py`),
miroir daté de sa console, lisible depuis la sandbox et qui survit à sa mort.
Il porte les **tracebacks des threads qui meurent** — le cas qui n'apparaissait
nulle part. **Le lire avant de supposer** :

    tail -80 _journal_serveur.log
    sed -n '/===== DEMARRAGE/,$p' _journal_serveur.log
    grep -n "THREAD MORT\|EXCEPTION\|Traceback" _journal_serveur.log

Plantage dur d'une lib native : `_journal_serveur_crash.log`.

> **Piège d'horloge, payé le 23/08** : `device_bash` tourne dans une VM en
> **UTC**. `date` y annonce 14:25 quand il est 16:25 chez Mike. Les epochs du
> serveur (`/api/maint/status`, `now`) sont la seule heure fiable.

## Où on en est (23/08/2026, fin de session 41)

**Flo → Florine est ACQUIS, et vérifié sur le DISQUE.** Onze heures de file XMP,
5 909 photos ; à 17:45 `queues.personnes` est tombée à 0, le serveur a
redémarré sur le code neuf (`code_a_jour` vrai, bannière neuve, **aucun
`THREAD MORT`**), et `verifier_xmp_personnes.py` a lu 200 fichiers tirés à
graine fixe : **200 portent `Florine`, 0 portent encore `Flo`**, contre 19 et
119 le matin même. `appliquer_xmp_personnes.py` n'a rien à réparer.

**La file XMP a un journal, et ne paie plus deux fois le même geste.** Chaque
geste est noté sur disque AVANT d'être enfilé (`_file_personnes.jsonl`) ; une
POSITION suffit (`_file_personnes.pos`) ; les gestes qui se suivent sur la MÊME
photo partent en UNE invocation ExifTool. **21 vérifications, 21 ROUGES sur
l'ancien code.** `-stay_open` est mesuré et rangé APRÈS le reste : 25 % sur une
écriture, pas les 12× que montre la lecture.

**La photothèque s'ouvre en MCP, lecture seule (point 13).** `mcp_serveur.py` —
JSON-RPC 2.0 sur stdio, stdlib pure, **sept** outils, plus la route
`/api/faits`. 79 vérifications neuves, **21 mutations posées, 21 vues**, et
`mesure_mcp.py` l'interroge en vrai : **13 étapes, 0 rouge**, `ml_faits` servi
depuis le redémarrage. Chiffre du chantier : `/api/people/photos` rend
**4 013 486 o** pour Florine, l'outil **5 775 o** — 695× moins. Deux plafonds
MUETS trouvés en observant : le mien, et celui de la route (2 000 photos là où
elle en porte 5 909). `total_est_un_plancher` les déclare.

## La seule chose NON observée

**Le journal de la file sur un geste vivant.** `_file_personnes.jsonl` naît au
premier geste de nom ; il n'y en a pas eu depuis le redémarrage, et l'observer
coûte une vraie écriture XMP dans une vraie photo — geste de Mike. Les 21
vérifications tiennent la mécanique ; le prochain nom attribué produira la
preuve gratuitement. **À regarder ce jour-là** : le fichier naît, se vide, et le
débit d'un renommage tombe vers **~2,9 s par PHOTO** (au lieu de 5,8).

## Prochain pas

1. **Copie HORS SITE (12 bis)** — le seul manque qui reste à l'assurance-vie :
   un sinistre qui emporte le PC ET le NAS emporte tout. Demande une décision de
   Mike (quoi, où, à quelle fréquence, chiffré ou non) avant du code.
2. **Suite de `ui/`** : le CSS commun (chaque page porte encore son `<style>` ;
   `tokens.css`, `base.css`, `components.css` attendent) puis le redesign —
   deux chantiers SÉPARÉS, exprès (`photo-ui`).
3. **Reste d'audit** : O7–O9, O11, O13–O15 (**O12 est clos** par la file de la
   41) ; **I1** est VISIBLE dans `/reglages` (`tours: visages 0, animaux 0`).
4. **Point 13, la suite** : l'ÉCRITURE en MCP — plus tard, et pas sans décision.
5. **`py_a_observer` est trop grossier** (`docs/DECISIONS_OUTILLAGE.md`) : le
   contrôle 5 exige qu'un serveur fasse tourner des modules qu'il n'importe
   jamais (`mcp_serveur.py`, familles `appliquer_`, `verifier_`). C'est ce qui a
   obligé la session 40 à forcer.

**Rien n'attend Mike dans `QUESTIONS_MIKE.md`.**

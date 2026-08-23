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
Il porte les **tracebacks des threads qui meurent**. **Le lire avant de
supposer** :

    tail -80 _journal_serveur.log
    sed -n '/===== DEMARRAGE/,$p' _journal_serveur.log
    grep -n "THREAD MORT\|EXCEPTION\|Traceback" _journal_serveur.log

Plantage dur d'une lib native : `_journal_serveur_crash.log`.

**Un nom accentué passe au banc par le jeton `b64:`** (23/08) :

    verifier_xmp_personnes.py --nom b64:U3TDqXBoYW5lIFBsb3V2aW4

`python3 -c "import base64;print(base64.urlsafe_b64encode('Béa'.encode()).decode().rstrip('='))"`.
`ARG_OK` n'a pas bougé — le jeton transite dans son alphabet, et la valeur ne
renaît qu'après les contrôles.

> **Piège d'horloge, payé le 23/08** : `device_bash` tourne dans une VM en
> **UTC**. `date` y annonce 14:25 quand il est 16:25 chez Mike. Les epochs du
> serveur (`/api/maint/status`, `now`) sont la seule heure fiable.

## Où on en est (23/08/2026, fin de session 42)

**Une FUITE de la règle 2 a été trouvée, chiffrée et bouchée.** L'index porte
des noms que les FICHIERS ignorent : **18,7 % des couples nom–photo** (Wilson
16,7–20,9 %, 255 écarts sur 1 364 lus, 352 noms) — soit **~5 800 photos**.
Ellie : 342 à l'index, **54 sans le nom dans le fichier**, file à zéro. Mike :
37 sur 200. Florine : **200/200**, comme Stéphane Plouvin 58/58 — les deux
seuls dont les fichiers ont été RÉÉCRITS en entier.

**La cause** : `_enqueue_person_write` testait `p.is_file()` avant de noter le
geste ; sur un « non », rien n'était noté, enfilé, ni dit. Or `is_file()`
interroge un partage SMB, qui répond « non » sur un fichier qui existe.
`_file_personnes_reprise` faisait pareil AU DÉMARRAGE — la prudence de la
reprise jetait la file que le journal existait pour sauver. **Les deux jugent
désormais zéro** : on note, on enfile, et seul celui qui a TENTÉ l'écriture
peut la déclarer impossible (`_file_personnes_echecs.jsonl`). **4 rouges
observés sur l'ancien code reconstitué**, dont deux tests de la 41 qui
affirmaient l'inverse. Serveur redémarré à 19:42 sur le code neuf.

**Le canal des bancs porte enfin les noms humains** (jeton `b64:`) — sans quoi
rien de ce qui précède n'aurait été trouvé : `ARG_OK` mettait 168 des 352 noms
hors de portée du seul instrument qui vérifie la règle 2 dans les fichiers.

**Instruments** : `verifier_xmp_personnes.py --nom X` (un nom, exact),
`verifier_xmp_toutes_personnes.py` (tous, échantillonné, 21 vérifications —
il REFUSE de classer un nom lu moins de 8 fois, et DIT ce qu'il n'a pas lu).

## Ce qui attend Mike

**`QUESTIONS_MIKE.md` n'est PAS vide.** Ellie est FAITE et vérifiée — 54
réécrites, 0 échec, puis **346/346 sur le disque**. Débit réel **3,5 s/photo**
(191 s pour 54). Restent ~5 700 photos sur 351 noms, et
**`appliquer_xmp_personnes.py --tous` est livré** : par PHOTO, avec reprise
(`_corbeille_xmp/_tous_faits.txt`), et arrêt propre si la file du serveur
repart. Reste à le LANCER (~5 h) : `--tous --max-photos 300` d'abord, puis
`--tous --appliquer`.

## La seule chose NON observée

**Le journal de la file sur un geste VIVANT.** Deux gestes ont été manqués de
quelques secondes : pour UNE photo, le journal vit ~3 s puis s'auto-efface.
**Et la réparation ne le montrera PAS** — `appliquer_xmp_personnes.py` est un
processus SÉPARÉ qui écrit lui-même, il ne passe jamais par `PERSON_QUEUE`
(erreur que j'ai faite en le promettant à Mike). Ce qu'il faut : un geste dans
l'INTERFACE portant sur beaucoup de photos — un groupe nommé, un renommage.
À regarder ce jour-là : `_file_personnes.jsonl` naît, `.pos` avance, il
disparaît quand la file se vide.

## Prochain pas

1. **La réparation** (geste de Mike, ci-dessus) — et l'observer.
2. **Copie HORS SITE (12 bis)** — un sinistre qui emporte le PC ET le NAS
   emporte tout. Décision de Mike avant du code.
3. **Suite de `ui/`** : le CSS commun, puis le redesign — séparés, exprès.
4. **Reste d'audit** : O7–O9, O11, O13–O15 ; **I1** visible dans `/reglages`.
5. **`py_a_observer` est trop grossier** (`docs/DECISIONS_OUTILLAGE.md`) : le
   contrôle 5 exige qu'un serveur fasse tourner des modules qu'il n'importe
   jamais. C'est ce qui oblige à forcer.

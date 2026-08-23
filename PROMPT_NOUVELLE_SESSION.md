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

**Le geste de Mike sur le groupe de « Stéphane Plouvin » est PROUVÉ sur le
disque** : 58 photos à l'index, **58 portent le nom, 0 manque, 0 illisible**,
file à 0, aucun `_file_personnes_echecs.jsonl`. Le journal de la file s'était
auto-effacé avant qu'on regarde — c'est ce qu'il fait quand tout est consommé.

**Le canal des bancs porte enfin les noms humains.** `ARG_OK` refusait accent
et espace : **168 des 352 noms, 6 119 photos** étaient hors de portée du seul
instrument qui vérifie la règle 2 dans les FICHIERS. Le jeton `b64:` rend la
valeur sans desserrer la porte (`docs/DECISIONS_OUTILLAGE.md`).
**11 vérifications neuves, 8 rouges sur l'ancien code**, 32 vertes au banc.

**Rappel de la 41, intact** : file XMP journalisée et réparable, `-stay_open`
rangé APRÈS le reste (25 %, pas 12×), photothèque ouverte en MCP lecture seule
(sept outils, `/api/faits`).

## La seule chose NON observée

**Le journal de la file sur un geste VIVANT, et son débit.** On est arrivé
après le drainage du geste de Mike. À regarder au prochain nom attribué, dans
les secondes qui suivent : `_file_personnes.jsonl` naît, `.pos` avance, le
fichier disparaît une fois la file vide — et le débit d'un renommage doit
tomber vers **~2,9 s par PHOTO** (au lieu de 5,8). Ça ne coûte rien de plus
que d'être là au bon moment.

## Prochain pas

1. **Copie HORS SITE (12 bis)** — le seul manque qui reste à l'assurance-vie :
   un sinistre qui emporte le PC ET le NAS emporte tout. Demande une décision de
   Mike (quoi, où, à quelle fréquence, chiffré ou non) avant du code.
2. **Suite de `ui/`** : le CSS commun (chaque page porte encore son `<style>` ;
   `tokens.css`, `base.css`, `components.css` attendent) puis le redesign —
   deux chantiers SÉPARÉS, exprès (`photo-ui`).
3. **Reste d'audit** : O7–O9, O11, O13–O15 ; **I1** est VISIBLE dans
   `/reglages` (`tours: visages 0, animaux 0`).
4. **Point 13, la suite** : l'ÉCRITURE en MCP — plus tard, et pas sans décision.
5. **`py_a_observer` est trop grossier** (`docs/DECISIONS_OUTILLAGE.md`) : le
   contrôle 5 exige qu'un serveur fasse tourner des modules qu'il n'importe
   jamais (`mcp_serveur.py`, `banc_agent.py`, familles `appliquer_`,
   `verifier_`). C'est ce qui oblige à forcer.

**Rien n'attend Mike dans `QUESTIONS_MIKE.md`.**

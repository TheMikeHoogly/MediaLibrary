# Amorce de reprise — MediaLibrary

> À coller après connexion de `C:\Prog\Claude\MediaLibrary`. Règles et
> protocole : `CLAUDE.md`. Ici : **l'état et le prochain pas, rien d'autre.**

Tu reprends **MediaLibrary**. **VÉRIFIE avant de lire** : `.git/HEAD`,
`.git/logs/HEAD` et `.git/logs/refs/heads/main` disent ce qui a été commité et
FUSIONNÉ depuis — ce document, non. Puis `ROADMAP.md`, `eval/DECISIONS.md`,
`eval/METHODE.md`. Débrief en 2–3 lignes, puis on attaque.

## Où on en est (19/08/2026, fin de session 26)

**Le lieu n'a plus qu'UNE règle, et c'est celle qu'on voit.** `places_list` et
`_cles_du_lieu` délèguent à `faits_vue.lieux_du_chemin`. Observé après
redémarrage : **« Ins » 493 → 5**, recherche **499 → 11 dont 0** venant de
« Cousins&Cousines », page **2 119 → 1 539 ms**.

Le banc `mesure_lieu_visible.py` a corrigé la règle elle-même : **les 876
« collés » n'étaient pas tous faux** — « Yani2004 », « AchumaniAlto »,
« CuevaMarkusIrpavi » sont de VRAIS lieux (~330). D'où la découpe des mots sur
les frontières de casse et de chiffres, les groupes de mots contigus, le trait
d'union conservé. Gains : **Sud France 315 · San Borja 82 · Vallée d'Aoste 81 ·
Rurrenabaque 55**. « France & Belgique » compte pour **les deux**.

**`taken` en base : REJETÉ ; le garde-fou est passé à la LECTURE.**
`faits_vue.date_credible` injecté dans `meme_jour.epoch_precis` — **70** photos
perdent une date précise fausse. `_best_time` en était une copie : la galerie
datait de 2006 ce que la recherche datait de 1985.

**Deux boutons qui mentaient : corrigés, observés.** L'ordre du serveur
s'appelle « Pertinence ».

**Pas encore observé** : la branche KB de `faits_vue` (`pending` = 0) — le
premier tagging sera son observation.

## Prochain pas

1. **Brancher la vue** (14a-iii) : affichage **date · lieu · noms** depuis
   `faits_vue`, là où le point 3 du ROADMAP l'attend. `_noms_attendus` balaie
   toutes les fiches à chaque appel — en balayage complet, **index inversé
   construit UNE fois** (13,9 ms pour 50 clés sinon).
2. **Le filtre ensuite** (14a-iv), mesuré sur **69,14 %** (photos avec un fait
   NON-date), jamais sur 99,79 %.
3. **Gestes Mike** : nettoyer Flo (5 909 photos) ; re-rejeter Caline.
4. **Le reste** (`ROADMAP.md`) : prompt de PROD qui hallucine ; doublons
   proches ; UI (11) ; restauration à blanc (12) ; MCP lecture (13).

**Ne pas rouvrir sans chiffre neuf** : `taken` en base (rejeté 19/08) ;
planchers 1990 : 7 et 0, couplés ; plafond 2100 : 0.

**Limite assumée, à basculer si elle gêne** : le nom de FICHIER compte comme
source de lieu — 52 vrais contre **9 faux** qu'aucune règle syntaxique
n'attrapera (« Grupo en la Laguna », « MisionSuiza » — en Bolivie).
`faits_vue.lieux_du_chemin(..., avec_fichier=False)`.

**À vider à la main** : `_corbeille_vecteurs/` et `_corbeille_session/plan_avant/`.

**Tu peux redémarrer le serveur toi-même** : écrire `redemarrer` dans
`_commande_serveur.txt` via `device_bash`, puis VÉRIFIER `GET /api/serveur`
(`demarre_a` bougé, `code_a_jour` vrai). Détail : `CLAUDE.md`, « Tester en réel ».

**Git : `27 - Git.bat`, 1 (commit) → 2 (fusion).**

# Amorce de reprise — MediaLibrary

> À coller après connexion de `C:\Prog\Claude\MediaLibrary`. Règles et
> protocole : `CLAUDE.md`. Ici : **l'état et le prochain pas, rien d'autre.**

Tu reprends **MediaLibrary**. **VÉRIFIE avant de lire** : `.git/HEAD`,
`.git/logs/HEAD` et `.git/logs/refs/heads/main` disent ce qui a été commité et
FUSIONNÉ depuis — ce document, non. Puis `ROADMAP.md`, `eval/DECISIONS.md`,
`eval/METHODE.md`. Débrief en 2–3 lignes, puis on attaque.

## Où on en est (19/08/2026, fin de session 27)

**La vue s'affiche.** `date · lieu · noms` sous chaque vignette et dans la
visionneuse, avec leurs SOURCES. Un seul producteur client (`faitsHtml`), un
seul assembleur serveur (`faits_vue.assertions`), les quatre modes de `/files`
sur le même objet-photo. 14a-**iii** est clos.

**L'index inversé est mesuré** : page de 50 à **1,11 ms** contre **9,65 ms** en
balayage naïf (**×8,7**) ; index entier 2,234 s. `_faits_ctx()` le bâtit en
**deux passes** — tous les `exclude` avant tous les `faces` — sinon l'autorité
d'un retrait dépendrait de l'ordre du dict.

**Observé en réel** : `q=Ins` → 11 photos, **11 dates · 11 lieux · 5 noms**,
page **1 048–1 462 ms** (contre 1 539) ; `q=montagne` → 1 500 photos en
**477–1 082 ms**. 11 tests verts (`test_faits_affichage.py`), dont la
comparaison des deux voies de noms et l'inversion de l'ordre des fiches.

**Le chiffre honnête est 69,95 %**, pas 69,14 % (30 122 photos avec un fait
NON-date) — `lieux.txt` a grossi.

## Prochain pas

1. **Le filtre (14a-iv)** : filtrer la recherche sur les faits, mesuré sur les
   **69,95 %**, jamais sur 99,79 %. `mesure_faits_vue.py` donne la matière par
   type (personne 43,79 %, lieu 31,11 %, espèce 11,03 %, animal 2,17 %).
2. **À trancher, vu à l'écran** : dans la visionneuse, les noms apparaissent
   DEUX fois — dans la ligne de faits et dans les tags `personne:…` en dessous.
   Redondance à assumer ou à retirer des tags affichés.
3. **Gestes Mike** : nettoyer Flo (5 909 photos) ; re-rejeter Caline.
4. **Le reste** (`ROADMAP.md`) : prompt de PROD qui hallucine ; doublons
   proches ; UI (11) ; restauration à blanc (12) ; MCP lecture (13).

**Ne pas rouvrir sans chiffre neuf** : `taken` en base (rejeté 19/08) ; backfill
ÉCRIT de `faits` (rejeté 19/08) ; index des noms en UNE passe (rejeté 19/08) ;
planchers 1990 : 7 et 0, couplés ; plafond 2100 : 0.

**Pas encore observé** : la branche KB de `faits_vue` (`pending` = 0) — le
premier tagging sera son observation.

**Limite assumée** : le nom de FICHIER compte comme source de lieu — 52 vrais
contre **9 faux** qu'aucune règle syntaxique n'attrapera.
`faits_vue.lieux_du_chemin(..., avec_fichier=False)`.

**À vider à la main** : `_corbeille_vecteurs/` et `_corbeille_session/plan_avant/`.

**Tu peux redémarrer le serveur toi-même** : écrire `redemarrer` dans
`_commande_serveur.txt` via `device_bash`, puis VÉRIFIER `GET /api/serveur`
(`demarre_a` bougé, `code_a_jour` vrai). Détail : `CLAUDE.md`, « Tester en réel ».

**Git : `27 - Git.bat`, 1 (commit) → 2 (fusion).**

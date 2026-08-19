# Amorce de reprise — MediaLibrary

> À coller après connexion de `C:\Prog\Claude\MediaLibrary`. Règles et
> protocole : `CLAUDE.md`. Ici : **l'état et le prochain pas, rien d'autre.**

Tu reprends **MediaLibrary**. **Commence par VÉRIFIER, pas par lire** :
`.git/HEAD`, `.git/logs/HEAD` et `.git/logs/refs/heads/main` disent ce qui a été
commité et FUSIONNÉ depuis — ce document, non. Puis `ROADMAP.md`,
`eval/DECISIONS.md`, `eval/METHODE.md`. Débrief en 2–3 lignes, puis on attaque.

## Où on en est (19/08/2026, fin de session 25)

**`faits` est une VUE — le backfill est REJETÉ.** `faits_vue.py` (pur, 26 tests)
calcule les faits à la demande ; `server` lui délègue la règle de lieu
(`_lieu_pour_cle`, `_lieu_plausible`, `_chemin_relatif`) : **0 différence sur
43 064 clés**. Rien n'est écrit en base, aucune migration.

**Ce que la mesure a dit** (`mesure_faits_vue.py`, sur COPIE) : couverture
**42 974 (99,79 %)**, mais le chiffre honnête est **29 775 (69,14 %)** avec un
fait NON-date. Sur les **81** entrées pourvues, la vue en **corrige 4** — 3 noms
« Flo » retirés depuis, **1 photo qui a reçu 6 noms APRÈS son tagging** : un champ
écrit aurait gravé les deux erreurs 43 064 fois. Coût : **1,4 ms** par page de 50,
**3,8 s** sur l'index entier ; seule prudence, `_noms_attendus` balaie toutes les
fiches à chaque appel (13,9 ms pour 50 clés) — en balayage complet, index inversé
construit **une fois**.

**Le LIEU n'est prêt pour aucune des deux règles.** Celle du KB évite **577**
lieux collés dans un mot, mais en RATE **378** en mot entier et répond AUTREMENT
sur **591** : **1 546** désaccords. C'est l'argument décisif pour la vue — une
règle corrigée vaudra pour les 43 064 sans migration.

## Prochain pas

1. **Corriger la règle de lieu, par ordre de gain.** (a) **124 libellés
   MULTI-MOTS jamais essayés** — « Weekend Vallée d'Aoste » : la règle ne teste
   que le segment entier ou ses mots un par un ; essayer aussi le libellé DANS le
   segment. Plus gros lot, plus simple. (b) le **seuil de 5 lettres** coûte 47
   (« Bâle », « Yani ») — mesurer les faux qu'il rattrape AVANT de le baisser.
   (c) **« France & Belgique »** (157) demande une décision, pas un correctif :
   deux lieux, ou aucun. (d) 207 effacés au nettoyage du segment : en dernier,
   la cause n'est pas unique.
2. **Brancher la vue** là où le point 3 du ROADMAP l'attend (affichage
   date · lieu · noms), index inversé construit une fois par balayage. **Le
   filtre ensuite**, mesuré sur 69,14 %, jamais sur 99,79 %.
3. **Deux boutons qui mentent** (petit, `photo-ui`) : « Date ↑ » reste allumé
   sur `/files?q=` alors que l'ordre affiché est celui du serveur ; en mode IA
   les boutons de tri avalent le clic. Ancres : `sortBy`, `updateSortButtons`,
   `applyFilter`, bloc `if (SEARCHQ)` de `GALLERY_PAGE`.
4. **Le prompt de PRODUCTION hallucine plus que V0** : inchangé, chaque photo
   taguée le paie. **Pas de retour à V0 sans protocole.**
5. **Le reste** (`ROADMAP.md`) : trois constats du registre 10a ; gestes Mike
   (Flo, Caline) ; doublons proches ; UI (11) ; restauration à blanc (12) ;
   MCP lecture (13).

**Ne pas rouvrir sans chiffre neuf** : `taken` en base reste NON DÉCIDÉ (72
photos contre **1 369** dates antérieures) ; les planchers 1990 coûtent 7 et 0,
couplés ; le plafond 2100 coûte 0.

**À vider à la main** : `_corbeille_vecteurs/` (5,1 Mo) et
`_corbeille_session/plan_avant/`.

**Gestes git : `27 - Git.bat`, 1 (commit) → 7 (redémarrage) → observation →
2 (fusion), puis 3 si des branches traînent.** À observer après redémarrage :
les lieux affichés ne doivent **pas bouger** — la délégation est mesurée
équivalente, une différence visible serait un bug.

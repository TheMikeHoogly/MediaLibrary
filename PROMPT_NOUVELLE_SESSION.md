# Amorce de reprise — MediaLibrary

> À coller dans une nouvelle conversation après connexion de
> `C:\Prog\Claude\MediaLibrary`. Règles, protocole, architecture, tests en réel :
> `CLAUDE.md` (chargé auto). Ici : **uniquement l'état et le prochain pas.**

Tu reprends **MediaLibrary**. Lis `ROADMAP.md` puis `eval/DECISIONS.md`, débrief
en 2–3 lignes, puis on attaque.

## Où on en est (14/08/2026, fin de session 15)

Sessions 13-14 livrées **et observées**. Session 15 n'a **pas touché
`server.py`** : une mesure, un outil, un protocole.

**Mesure 3a — re-passe de tagging PARKÉE, pas rejetée** (`mesure_repasse.py`,
copie de la base, zéro GPU ; 18 tests verts, recoupée par un second chemin de
code ; détail `mesure_repasse.txt`) :

- **42 060 des 42 078 entrées taguées sont en `pipe` v0**, taguées jusqu'au
  11/08, donc **toutes au prompt V0 = image seule** : aucun fait en contexte, par
  construction du prompt et non par défaut d'enregistrement.
- Elles recevraient aujourd'hui : date 41 818 · nom 18 886 · lieu 5 814 ·
  espèce 4 753. **Mais ces faits sont déjà dans l'index** : la re-passe n'achète
  que la DESCRIPTION, et son seul fondement est un 25-15 sur 40 photos, **p = 0,15**.
- **6 317 photos ont un GPS et aucun lieu** — gisement de faits à zéro GPU.

**Protocole 3b écrit, banc réparé.** `docs/PROTOCOLE_3B_TAGGING.md` fige
hypothèse, strates et **critère de décision AVANT la mesure** (≥ 88 préférences
sur 150). En l'écrivant, trois défauts du banc sont sortis — vérifiés dans
`eval/tagging_results.json` : la **date** asserted était un **epoch brut sur
150/150** (`strftime('%-d %B %Y')`, invalide sous Windows) ; le **lieu** venait
de la branche de secours de `lieux_connus`, soit « TRIER », « Calinous »,
« Visite » sous provenance inventée — **118 des 150 faux** ; et les **prompts du
banc avaient dérivé** de la prod, les sorties du 12/08 n'ayant jamais été
écrites dans un fichier (verdict non reproductible). `eval_tagging.py` importe
désormais `tagging_meta` et `_assertions_pour` au lieu de les recopier ;
variante **V2CTX** = prompt de prod verbatim ; **150 paires** notées au lieu de
40 ; `--depouiller` applique le critère (il reproduit le 25-15 / p = 0,15).

## Prochain pas — par valeur

1. **Bat 18** (geste Mike, zéro GPU) : `enrichir_lieux.py` → `--ecrire` →
   redémarrer. 6 317 faits « lieu » qui servent la recherche, le renommage et le
   banc — avant de discuter des 50 h.
2. **Lancer le banc 3b** : `python eval_tagging.py` (~25 min GPU), noter
   `eval/rating.html` à l'aveugle, puis `--depouiller`. **Après** le bat 18,
   **avant** les lots de renommage qui rendront l'échantillon caduc. Le résultat
   se consigne dans `eval/DECISIONS.md` quel qu'il soit.
3. **14a — recherche déterministe**, indépendante du GPU et de la re-passe : la
   matière est déjà là, la mesure 3a vient de le confirmer.
4. **Régénérer `docs/plan_renommage.json`** avant tout lot de renommage (le plan
   est antérieur au correctif du plancher : les années 80 y sont « sans date »).
5. **Le reste** (`ROADMAP.md`) : gestes Mike (Flo, Caline) ; doublons proches ;
   UI (11) ; restauration à blanc (12) ; MCP lecture (13).

**Un piège trouvé, non corrigé** (résiduel `ROADMAP.md`) : `server.py` prend
`sys.argv[1]` comme `UPLOAD_DIR` (l. 72) — tout script qui l'importe avec un
drapeau hérite d'un `UPLOAD_DIR` faux. Sans effet observé, désormais bruyant.
Correctif d'une ligne, mais il demande un redémarrage et une observation : en
début de session, pas en fin.

**Ordre des gestes git : 27 → 0 → 28.** Session 14 est observée, sa branche peut
partir dans `main`. Session 15 n'a rien à observer côté serveur — l'observation
qui manque, c'est le banc.

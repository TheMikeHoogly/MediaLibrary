# Amorce de reprise — MediaLibrary

> À coller dans une nouvelle conversation après connexion de
> `C:\Prog\Claude\MediaLibrary`. Règles, protocole, architecture, tests en réel :
> `CLAUDE.md` (chargé auto). Ici : **uniquement l'état et le prochain pas.**

Tu reprends **MediaLibrary**. Lis `ROADMAP.md` puis `eval/DECISIONS.md`, débrief
en 2–3 lignes, puis on attaque.

## Où on en est (14/08/2026, fin de session 15)

Sessions 13-14 livrées et observées. Session 15 n'a **pas touché `server.py`** :
une mesure, un outil, un protocole, et l'activation des lieux GPS.

**1. Mesure 3a — re-passe de tagging PARKÉE, pas rejetée** (`mesure_repasse.py`,
copie de la base, zéro GPU ; 18 tests verts, recoupée par un second chemin de
code ; `mesure_repasse.txt`) : **42 060 des 42 078 entrées taguées sont en `pipe`
v0**, toutes au prompt V0 = image seule, donc **aucun fait en contexte, par
construction du prompt** — pas par défaut d'enregistrement. Elles recevraient
aujourd'hui date 41 818 · nom 18 886 · lieu 12 459 · espèce 4 753. **Mais ces
faits sont déjà dans l'index** : la re-passe n'achète que la DESCRIPTION, sur un
25-15 à **p = 0,15**.

**2. `gps_place` activé et observé.** 6 614 photos GPS → 221 amas → 6 595
nommées ; `lieux.txt` +151 (bloc marqué, backup). Faits « lieu » **5 814 →
12 459**, photos à GPS sans lieu **6 317 → 18**. Le gazetteer s'arrêtant à
1 000 habitants, le domicile (1 257 photos) sortait « Bussigny » : **`lieux_locaux.txt`**
reprend la main (lieux locaux prioritaires + alias), tests 52/52 et 30/30.

**3. Protocole 3b écrit, banc réparé.** `docs/PROTOCOLE_3B_TAGGING.md` fige
hypothèse, strates et **critère de décision AVANT la mesure** (≥ 88 préférences
sur 150). Trois défauts du banc corrigés, tous vérifiés dans les données : dates
asserted en **epoch brut sur 150/150**, lieux venant de la branche de secours de
`lieux_connus` (« TRIER », « Calinous » — 118 des 150 faux), prompts dérivés de
la prod. `eval_tagging.py` importe désormais `tagging_meta` et
`_assertions_pour` ; variante **V2CTX** = prompt de prod verbatim ; **150
paires** notées au lieu de 40 ; `--depouiller` applique le critère.

## Prochain pas — par valeur

1. **Lancer le banc 3b** — c'est l'observation qui manque. `python
   eval_tagging.py` (V0 vs V2CTX, ~25 min GPU), noter `eval/rating.html` à
   l'aveugle, puis `python eval_tagging.py --depouiller`. **Avant** les lots de
   renommage, qui rendront l'échantillon caduc. Le résultat se consigne dans
   `eval/DECISIONS.md` quel qu'il soit : c'est lui qui débloque ou enterre 50 h.
2. **14a — recherche déterministe**, zéro GPU, indépendante de la re-passe : sa
   matière vient de doubler côté lieux (12 459 faits).
3. **Régénérer `docs/plan_renommage.json`** avant tout lot (le plan est antérieur
   au correctif du plancher ET aux lieux GPS).
4. **Le reste** (`ROADMAP.md`) : gestes Mike (Flo, Caline) ; doublons proches ;
   UI (11) ; restauration à blanc (12) ; MCP lecture (13).

**Un piège trouvé, non corrigé** (résiduel `ROADMAP.md`) : `server.py` prend
`sys.argv[1]` comme `UPLOAD_DIR` (l. 72) — tout script qui l'importe avec un
drapeau hérite d'un `UPLOAD_DIR` faux. Sans effet observé, désormais bruyant.
Correctif d'une ligne, mais il demande un redémarrage et une observation : en
début de session, pas en fin.

**Ordre des gestes git : 27 → 0 → 28.** Session 14 est observée, sa branche peut
partir dans `main`. Session 15 : rien à observer côté serveur — l'observation qui
manque est le banc.

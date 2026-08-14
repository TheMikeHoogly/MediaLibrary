# Amorce de reprise — MediaLibrary

> À coller dans une nouvelle conversation après connexion de
> `C:\Prog\Claude\MediaLibrary`. Règles, protocole, architecture, tests en réel :
> `CLAUDE.md` (chargé auto). Ici : **uniquement l'état et le prochain pas.**

Tu reprends **MediaLibrary**. Lis `ROADMAP.md` puis `eval/DECISIONS.md`, débrief
en 2–3 lignes, puis on attaque.

## Où on en est (14/08/2026, fin de session 15)

Session 14 (plancher des années à 1900, ExifTool disparu en silence, « même
jour ») : livrée **et observée en réel**, rien en attente. Session 15 n'a
produit **aucune modification de `server.py`** — une mesure et son outil.

**Mesure 3a — la re-passe de tagging est PARKÉE, pas rejetée.**
`mesure_repasse.py` (lecture seule sur une copie de la base, zéro GPU, zéro
NAS ; `test_mesure_repasse.py` 18/18, recoupée par un second chemin de code) :

- **42 060 des 42 078 entrées taguées sont en `pipe` v0**, taguées en juillet et
  jusqu'au 11/08 — donc **toutes avec le prompt V0 = image seule**, sans aucun
  fait en contexte. Ce n'est pas un défaut d'enregistrement : le prompt n'en
  recevait pas.
- Aujourd'hui elles recevraient : **date 41 818** · **nom 18 886** ·
  **lieu 5 814** · **espèce 4 753**. 58 photos resteraient sans aucun fait.
- **Mais ces faits sont déjà dans l'index** : la re-passe n'achète que la
  DESCRIPTION. Son seul fondement est l'A/B 25-15 sur 40 photos, **p = 0,15**.
- **6 317 photos ont un GPS et aucun lieu** — gisement de faits à zéro GPU.

Détail : `mesure_repasse.txt`, `eval/mesure_repasse.json`, `ROADMAP.md` (État s15).

## Prochain pas — par valeur

1. **Bat 18 d'abord** (geste Mike, zéro GPU) : `enrichir_lieux.py` → `--ecrire`
   → redémarrer. 6 317 faits « lieu » qui servent la recherche, le renommage et
   tout banc de tagging — avant de discuter des 50 h.
2. **3b — le banc qui débloque (ou enterre) la re-passe** (`vision-eval` :
   protocole AVANT mesure). 200 photos stratifiées (contexte riche / date seule),
   notation à l'aveugle, deux questions d'un coup : v2ctx bat-il vraiment V0
   (25-15 ne suffit pas ; ~123 photos nécessaires) et un modèle plus gros
   apporte-t-il encore quelque chose quand les faits sont donnés en contexte
   (plafond DUR 4 Go de VRAM) ? **~0,5 h GPU contre 50 h.**
3. **14a — recherche déterministe**, indépendante de tout GPU et de la re-passe :
   la matière (dates, noms, lieux, tags) est déjà là, la mesure vient de le
   confirmer. C'est le chantier qui rend ces faits utiles tout de suite.
4. **Régénérer `docs/plan_renommage.json`** avant tout lot de renommage : le plan
   actuel est antérieur au correctif du plancher, les années 80 y sont en
   « sans date ».
5. **Le reste** (`ROADMAP.md`) : gestes Mike (Flo, Caline) ; doublons proches
   bridés ; UI — harmonisation (11) ; restauration à blanc (12) ; MCP lecture (13).

**Ordre des gestes git : 27 → 0 → 28.** On ne fusionne dans `main` qu'après
observation en réel. Session 14 est observée : sa branche peut partir dans
`main`. Session 15 n'a rien à observer en réel (aucun code serveur touché).

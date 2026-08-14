# Amorce de reprise — MediaLibrary

> À coller dans une nouvelle conversation après connexion de
> `C:\Prog\Claude\MediaLibrary`. Règles, protocole, architecture, tests en réel :
> `CLAUDE.md` (chargé auto). Ici : **uniquement l'état et le prochain pas.**

Tu reprends **MediaLibrary**. Lis `ROADMAP.md` puis `eval/DECISIONS.md`, débrief
en 2–3 lignes, puis on attaque.

## Où on en est (14/08/2026, fin de session 14)

Trois chantiers livrés **et observés en réel** — rien en attente de vérification :

- **Session 13** (casse des clés SMB, « même jour, autres années ») : tout passe.
- **Plancher des années du CHEMIN à 1900, nom de fichier exclu** : 716 photos de
  1982-1989 rendues à leur année (elles affichaient avril 2026), 38 photos tirées
  en arrière par un numéro de scanner corrigées, 0 régression sur 20 239 fichiers.
- **ExifTool disparu en silence** : deux répertoires fantômes nés d'un `mkdir` au
  niveau module exécuté sous POSIX égaraient la recherche ; l'`OSError` était
  muette. Vérifié au redémarrage.

Branche `fix/plancher-annees-chemin` (elle porte aussi `feat/meme-jour-et-casse`).
Tests verts : `test_plan_renommage.py` 11/11, `test_tagging_meta.py`,
`test_meme_jour.py`. Chiffres et raisons : `ROADMAP.md` (État s14).

## Prochain pas — par valeur

1. **Chantier 3 — chaîne « noms → descriptions → recherche »** (demandé par Mike
   le 14/08, détail dans `ROADMAP.md`). Commencer par **3a, une mesure** :
   combien d'entrées sont encore en `pipe` v0, et combien portent aujourd'hui des
   `faits` qu'elles n'avaient pas au moment de leur tagging. C'est ce chiffre qui
   dit si les ~51 h GPU de re-passe valent le coup — pas l'intuition. **Ne pas
   lancer de re-tagging avant d'avoir tranché le modèle (3b, `vision-eval`).**
2. **Régénérer `docs/plan_renommage.json`** avant tout lot de renommage : le plan
   actuel est antérieur au correctif du plancher, les années 80 y sont en
   « sans date ».
3. **Gestes Mike** : nettoyer Flo (5 909 photos) ; re-rejeter Caline une fois ;
   activer `gps_place` (bat 18 → `enrichir_lieux.py` → `--ecrire` → redémarrer).
4. **Le reste** (`ROADMAP.md`) : file « À vérifier » ; doublons proches bridés ;
   UI — harmonisation (11) ; restauration à blanc (12) ; MCP lecture (13).

**Ordre des gestes git : 27 → 0 → 28.** On ne fusionne dans `main` qu'après
observation en réel.

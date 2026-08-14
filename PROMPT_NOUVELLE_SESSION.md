# Amorce de reprise — MediaLibrary

> À coller dans une nouvelle conversation après connexion de
> `C:\Prog\Claude\MediaLibrary`. Règles, protocole, architecture, tests en réel :
> `CLAUDE.md` (chargé auto). Ici : **uniquement l'état et le prochain pas.**

Tu reprends **MediaLibrary**. Lis `ROADMAP.md` puis `eval/DECISIONS.md`, débrief
en 2–3 lignes, puis on attaque.

## Où on en est (14/08/2026, fin de session 14)

- **Session 13 observée en réel, tout passe** : correctif de casse des clés SMB
  (dossier NAS ancien → tags, description, personnes, Géo, vraie date) et
  chantier « même jour, autres années » (115 photos sur 11 années au 14 août,
  référence exclue, bouton caché quand la date n'est pas au jour près). La
  branche `feat/meme-jour-et-casse` est donc **prête à fusionner (bat 28)**.
- **Plancher des années du CHEMIN à 1900 + nom de fichier exclu — livré ET
  observé** : 716 photos de 1982-1989 ont retrouvé leur année (elles affichaient
  avril 2026), 38 photos tirées en arrière par un numéro de scanner corrigées,
  0 régression sur 20 239 fichiers vérifiés.
- **ExifTool disparu en silence — corrigé, PAS ENCORE OBSERVÉ** (il faut un
  démarrage) : deux répertoires fantômes nommés `\\NAS-Bremblens\home\…`, nés
  d'un `mkdir` au niveau module exécuté sous POSIX, égaraient la recherche
  d'ExifTool ; l'`OSError` était muette. Détail : `ROADMAP.md` (État s14).
- Branche `fix/plancher-annees-chemin`. Tests verts : `test_plan_renommage.py`
  11/11, `test_tagging_meta.py`, `test_meme_jour.py`.

## Prochain pas — par valeur

1. **Observer ExifTool au démarrage** : la console ne doit plus dire
   « ExifTool indisponible » ; les trois tâches de fond (dates, noms, GPS)
   doivent repartir et rendre des comptes dans `/reglages`. Si un dossier est
   illisible, le serveur le NOMME désormais au lieu de se taire.
2. **Régénérer `docs/plan_renommage.json`** avant tout lot de renommage : le
   plan actuel a été produit avant le correctif du plancher, les années 80 y
   sont en « sans date ».
3. **Gestes Mike, dans cet ordre** : nettoyer Flo (5 909 photos) ; re-rejeter
   Caline une fois ; activer `gps_place` (bat 18 → `enrichir_lieux.py` →
   `--ecrire` → redémarrer) ; lots de renommage (après le point 2).
4. **Le reste inchangé** (détail : `ROADMAP.md`) : file « À vérifier » ;
   doublons proches bridés ; UI — harmonisation (11) ; restauration à blanc
   (12) ; serveur MCP lecture (13).

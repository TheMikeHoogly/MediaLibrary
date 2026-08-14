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
- **Livré en session 14, branche `fix/plancher-annees-chemin`, PAS ENCORE
  OBSERVÉ EN RÉEL** (redémarrage nécessaire) : le plancher 1990 des années lues
  dans un CHEMIN passe à **1900**, et `_path_years` **exclut le nom de fichier**.
  Détail et chiffres : `ROADMAP.md` (État s14) + `eval/DECISIONS.md`.
  Tests verts : `test_plan_renommage.py` 11/11, `test_tagging_meta.py`,
  `test_meme_jour.py`.

## Prochain pas — par valeur

1. **Observer en réel le plancher** (192.168.0.13:8080, après
   `0 - Démarrer le serveur.bat`) : (a) `/files?dir=1/Photos%20Papa&rec=1` →
   les photos de `1982`…`1989` doivent porter leur année de dossier, plus
   avril 2026 ; **714 photos attendues** ; (b) une photo de `1986` ouverte
   → date affichée 1986 ; (c) vérifier qu'aucune photo de `2002`
   (`119-1908_IMG.JPG`) n'a reculé — le nom de fichier ne doit plus compter ;
   (d) contre-mesure honnête : compter combien de photos changent d'année et
   dans quel sens, pas seulement celles qu'on espérait.
2. **Régénérer `docs/plan_renommage.json`** avant tout lot de renommage : le
   plan actuel a été produit avant le correctif, les années 80 y sont en
   « sans date ».
3. **Gestes Mike, dans cet ordre** : nettoyer Flo (5 909 photos) ; re-rejeter
   Caline une fois ; activer `gps_place` (bat 18 → `enrichir_lieux.py` →
   `--ecrire` → redémarrer) ; lots de renommage (après le point 2).
4. **Le reste inchangé** (détail : `ROADMAP.md`) : file « À vérifier » ;
   doublons proches bridés ; UI — harmonisation (11) ; restauration à blanc
   (12) ; serveur MCP lecture (13).

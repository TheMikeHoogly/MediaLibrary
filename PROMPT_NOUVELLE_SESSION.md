# Amorce de reprise — MediaLibrary

> À coller dans une nouvelle conversation après connexion de
> `C:\Prog\Claude\MediaLibrary`. Règles, protocole, architecture, tests en réel :
> `CLAUDE.md` (chargé auto). Ici : **uniquement l'état et le prochain pas.**

Tu reprends **MediaLibrary**. Lis `ROADMAP.md` puis `eval/DECISIONS.md`, débrief
en 2–3 lignes, puis on attaque.

## Où on en est (13/08/2026, fin de session 10)

- **Navigation par similarité livrée ET validée en réel** : bouton
  « Semblables » de la lightbox → `/files?sim=<clé>`, navigation de proche
  en proche. `feat/similar` committée + fusionnée (bat 27/28/29 passés,
  `_tmp_obs/` supprimé). Base : 43 067 entrées, purge des doublons OK.
- **Session 11 livrée (à commiter, `fix/lieux-thumb`)** : le résidu O1 a été
  **confirmé sur le serveur en marche** (25 cartes Lieux via `/media/…`,
  0 via `/api/thumb`) puis corrigé — `places_list()` rend maintenant
  `/api/thumb?key=…&s=512`. Mesuré sur clé réelle : 41 Ko vs 2 435 Ko
  (**−98 %**, ~60 Mo de NAS épargnés par ouverture de `/sujets`).
  `py_compile` OK ; **pas encore observé en réel** (nécessite bat 0).
- Veille v2ctx inchangée (n=2) : astre/objet (éclipse), date en prose.

## Prochain pas — par valeur

1. **Gestes Mike** : bat 27 (commit `fix/lieux-thumb`) → bat 0 → ouvrir
   `/sujets`, section Lieux : les 25 vignettes doivent s'afficher (et vite)
   → bat 28. Puis : file « À vérifier » (Espace/X/Z) ; lots de renommage
   (plan = 2114) ; nettoyer Flo ; re-rejeter Caline ; activer `gps_place`
   — ce dernier fait aussi basculer la section Lieux du repli « dossiers »
   vers le géocodage GPS, donc c'est le bon moment.
2. **Suite chantier 6, sans brique nouvelle** (`similar_by_key` suffit) :
   (a) rangée « même jour, autres années » — requête date pure, zéro IA,
   la moins risquée ; (b) doublons proches bridés (>0,98 + même journée →
   quarantaine réversible) — **50 paires jugées par Mike avant tout geste**,
   décision déjà écrite.
3. **Autres chantiers, par valeur** (détail : `ROADMAP.md`) : reste des
   correctifs d'audit (5 — O15 purge `photo_thumbs/` a gagné en poids,
   toutes les grilles alimentent le cache maintenant) ; UI — harmonisation
   (11, skill `photo-ui`) ; restauration à blanc (12) ; serveur MCP lecture
   (13 — `/api/similar` a déjà la forme d'un outil) ; recherche IA
   contextuelle (14 — déterministe d'abord).

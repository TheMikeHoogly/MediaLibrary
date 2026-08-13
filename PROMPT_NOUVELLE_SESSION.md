# Amorce de reprise — MediaLibrary

> À coller dans une nouvelle conversation après connexion de
> `C:\Prog\Claude\MediaLibrary`. Règles, protocole, architecture, tests en réel :
> `CLAUDE.md` (chargé auto). Ici : **uniquement l'état et le prochain pas.**

Tu reprends **MediaLibrary**. Lis `ROADMAP.md` puis `eval/DECISIONS.md`, débrief
en 2–3 lignes, puis on attaque.

## Où on en est (12/08/2026, fin de session 10)

- **Purge des doublons vérifiée en réel** : total 43 067 pile, plus aucune
  clé absolue `\\NAS…\_Uploads`, file « À vérifier » propre → bat 28
  débloqué. Test d'occasion restant : re-upload téléphone = UNE entrée.
- **Session 10 livrée (à commiter, `feat/similar`)** : chantier 6, tranche 1 —
  `similar_by_key` (vecteur SigLIP déjà en base : zéro GPU, zéro NAS),
  `GET /api/similar?key=&n=`, page `/files?sim=<clé>` (réutilise la branche
  résultats de `?q=`, ordre de pertinence, état vide rédigé si photo pas
  encore encodée), bouton « Semblables » dans la lightbox galerie —
  navigation de proche en proche. Testé hors serveur (py_compile +
  micro-banc VectorStore synthétique) ; **pas encore observé en réel**.
- Veille v2ctx inchangée (n=2) : astre/objet (éclipse), date en prose.
- Ménage : supprimer `_tmp_obs/` (285 Mo, gitignoré — la VM ne peut pas).

## Prochain pas — par valeur

1. **Gestes Mike, dans l'ordre** : bat 28 (fusionne le fix doublons) →
   bat 27 (commit `feat/similar`) → bat 0 (redémarrer) → tester en réel :
   lightbox → « Semblables » (pertinence ? vitesse ?), re-clic de proche en
   proche, photo fraîche → message « pas encore analysée » → bat 28 après
   validation.
2. **Autres gestes Mike** : file « À vérifier » (Espace/X/Z) ; lots de
   renommage (plan = 2114) ; nettoyer Flo ; re-rejeter Caline ; `gps_place`.
3. **Chantiers code, par valeur** (détail : `ROADMAP.md`) : suite chantier 6
   (doublons proches bridés, « même jour autres années ») ; correctifs
   d'audit (5, dont résidu O1) ; UI — harmonisation (11, skill `photo-ui`) ;
   restauration à blanc (12) ; serveur MCP lecture (13) ; recherche IA
   contextuelle (14 — déterministe d'abord).

# Amorce de reprise — MediaLibrary

> À coller dans une nouvelle conversation après connexion de
> `C:\Prog\Claude\MediaLibrary`. Règles, protocole, architecture, tests en réel :
> `CLAUDE.md` (chargé auto). Ici : **uniquement l'état et le prochain pas.**

Tu reprends **MediaLibrary**. Lis `ROADMAP.md` puis `eval/DECISIONS.md`, débrief
en 2–3 lignes, puis on attaque.

## Où on en est (12/08/2026, fin de session 8)

- **Knowledge Builder câblé + `TAGGING_PIPELINE_VERSION` créée** (audit D
  soldé pour le tagging) : prompt de prod = v2ctx « assertions en contexte,
  sans impératif » (éval du 12/08), lecture exiftool AVANT le VLM (élargie à
  la date, toujours 1 seule), noms/date/lieu en post-traitement déterministe
  (`faits` sourcés — provenance), version + comptage v0/courant dans
  `/reglages`. Diff relu 2× : course sur les noms pendant l'appel VLM corrigée
  (re-fusion `_noms_attendus` depuis les fiches ; exclude = autorité).
  **Livré, PAS observé** — le serveur tourne encore sur l'ancien code.
- **À commiter** : `SESSION_COMMIT.txt` prêt (`feat/knowledge-builder`) →
  bat 27, puis redémarrage (bat 0) pour charger v2ctx, puis bat 28 après
  validation en réel. Session 7 (`feat/eval-a-distance`) committée le 12/08.
- Tests : `python test_tagging_meta.py` (42 vérifications, tout passe).

## Prochain pas — par valeur

1. **Observer v2ctx + O6 d'un coup** : redémarrer, déposer ~30 photos neuves,
   vérifier `pending` qui s'écoule, la qualité des descriptions, les `faits`
   sourcés d'une entrée, et la ligne « Pipeline tagging » dans `/reglages`
   (comptage v0 vs courant). Un nom nommé PENDANT un tagging ne doit plus
   pouvoir se perdre.
2. **Lots de renommage débloqués** (gestes Mike, plan = 2114, 4 étapes dans
   `/reglages`).
3. **Gestes Mike restants** : nettoyer Flo ; re-rejeter Caline ; activer
   `gps_place` (le Knowledge Builder l'affichera comme source `gps`).
4. **Correctifs d'audit** I4–I8, O7–O9, O11–O15 ; puis composition d'affichage
   date · lieu · noms depuis `faits`. Ordre : `ROADMAP.md`.

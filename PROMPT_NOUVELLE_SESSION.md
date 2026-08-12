# Amorce de reprise — MediaLibrary

> À coller dans une nouvelle conversation après connexion de
> `C:\Prog\Claude\MediaLibrary`. Règles, protocole, architecture, tests en réel :
> `CLAUDE.md` (chargé auto). Ici : **uniquement l'état et le prochain pas.**

Tu reprends **MediaLibrary**. Lis `ROADMAP.md` puis `eval/DECISIONS.md`, débrief
en 2–3 lignes, puis on attaque.

## Où on en est (12/08/2026, fin de session 7)

- **Sauvegarde vérifiée : OBSERVÉE ok en réel** (premier tour après
  redémarrage : integrity ok, 292 confirmés + 1 496 exclusions relus dans le
  snapshot, journal exporté). Le fix mtime de la session 6 est un **acquis** —
  ce point sort des réflexes de reprise.
- **Éval tagging V2 tranchée** : « assertions en contexte, sans impératif de
  noms » **ADOPTÉE** (aveugle A/B : 25–15 vs V0 ; 4,26 s/photo, plus rapide
  que V0 ; hallucinations 6 vs 4). Zéro GPU dépensé — réponses relues de
  `tagging_results.v2avant.json`. Détail : `eval/DECISIONS.md`.
- **Livré session 7** : `GET /eval` + `POST /eval/notes` (notation à distance
  via VPN, écriture atomique, fichiers fixes — pas de traversée). **Utilisé en
  réel** par Mike hors de chez lui le soir même.
- **À commiter** : `SESSION_COMMIT.txt` prêt (`feat/eval-a-distance`) →
  bat 27, puis bat 28 (le serveur tourne déjà sur le code patché).

## Prochain pas — par valeur

1. **Câbler le Knowledge Builder + version de pipeline tagging**
   (`TAGGING_PIPELINE_VERSION`, modèle `ANIMAL_PIPELINE_VERSION`) : le prompt
   de prod est la V2 sans impératif ; noms/date/lieu fusionnés en
   post-traitement déterministe, jamais via le prompt. C'est LE déblocage que
   l'éval attendait.
2. **Lots de renommage débloqués** (gestes Mike, plan = 2114, 4 étapes dans
   `/reglages`).
3. **Observer** : O6 (déposer ~30 photos neuves), seek vidéo mobile, test du Z.
4. **Correctifs d'audit** I4–I8, O7–O9, O11–O15 ; nettoyer Flo ; `gps_place`.
   Ordre : `ROADMAP.md`.

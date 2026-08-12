# Amorce de reprise — MediaLibrary

> Colle ce bloc dans une nouvelle conversation Cowork, après avoir connecté
> `C:\Prog\Claude\MediaLibrary`. L'état vit dans les fichiers, pas dans l'historique.
> Règles + protocole = `CLAUDE.md` (chargé auto). Ici : juste l'état et le prochain pas.

Tu reprends **MediaLibrary** — photothèque familiale locale à IA (~30 000 photos NAS,
serveur Python stdlib pur, 5 pipelines Ollama/InsightFace/YOLO/DINOv2/SigLIP2,
RTX 3050 4 Go arbitrée par baux/priorités/éviction).

## Ordre de lecture

1. `CLAUDE.md` (auto) — règles absolues, protocole, architecture.
2. `ROADMAP.md` — priorités (réordonnées au triple audit du 11/08).
3. `eval/DECISIONS.md` — pistes tranchées (ne rien reproposer).
4. `docs/AUDIT_INTERNE_2026-08.md` — constats I1–I17 / O1–O15 / A–F.
5. Selon le sujet : skills `monolith-surgery` (avant tout edit de `server.py`),
   `photo-ui` (dès qu'on touche l'UI).

## Où on en est (12/08/2026, session 5)

- Commité jusqu'à `daa9cbc` (branche `feat/verification-classification`) :
  files « À vérifier » sous `/sujets?vue=classification`, personnes + **animaux
  en miroir** (même clavier Espace/X/Z/lettre, même journal). Serveur redémarré ;
  vérif programmatique OK (files affichées 18+120, thumb 200, Range 206).
- **Session (5) LIVRÉE, à commiter (bat 27, `SESSION_COMMIT.txt` prêt) +
  redémarrer** : **audit O6** — encodage sémantique en **sous-lots de 4**
  (`SEMANTIC_SUBBATCH`), `SEMANTIC_LOCK` rendu entre deux sous-lots (une
  recherche s'intercale au lieu d'attendre 10–30 s) ; arrêt du lot si
  `ui_recent()` ; seules les clés **tentées** vont dans `SEMANTIC_SKIP`.

## Prochain pas — par valeur (détail : ROADMAP « À faire »)

1. **Commiter + redémarrer (O6)**, puis observer : une recherche pendant
   « encodage de N photo(s) » répond en ~1 s.
2. **Vérifier au clavier la session (4)** : jugements Espace/X/Z dans
   Classification ; Z sur une acceptation d'animal → la carte REVIENT.
3. **Session (3), restes** : seek vidéo mobile ; carte « Sauvegarde
   vérifiée : ok » après le prochain backup horaire (⚠ URI UNC jamais vue
   passer sur Windows).
4. **Vérité terrain** (geste Mike, outillage prêt) : confirmer ~100 propositions
   dans `/sujets?vue=classification` — compteur de séance affiché.
5. **Éval tagging V2 AVANT lots de renommage** (banc keyé par chemin). Protocole :
   `eval/PLAN_assertions_vs_pixels.md`. Si V2 confirme → câbler Knowledge Builder.
6. **Correctifs d'audit restants** : I4–I8, O7–O9, O11–O15 (+ résidu O1 : section
   Lieux de /sujets en originaux `/media`). Gestes Mike : nettoyer Flo ;
   activer `gps_place`.

## Rappels opérationnels

- Tester en réel : **192.168.0.13:8080** via Claude-in-Chrome. **Pas de hot-reload** →
  redémarrer (`0 - Démarrer le serveur.bat`) après toute modif de `server.py`. Captures =
  onglet au premier plan ; état par `fetch` GET (marche onglet caché). État GPU/ordo :
  `GET /api/search/status` → `etat['gpu']`, `etat['ordonnanceur']`.
- Livraison sandbox → disque : `SendUserFile` puis `device_commit_files`. **Git +
  redémarrage = gestes Mike.** Ne pas ouvrir `photos.db` depuis le sandbox (le serveur
  est l'écrivain unique). Tests : `python test_ordonnanceur.py` (27 vérifications).

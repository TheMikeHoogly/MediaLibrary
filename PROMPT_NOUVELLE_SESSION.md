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

## Où on en est (12/08/2026, session 3)

- Commité jusqu'à `d9eda80` (branche `feat/verite-terrain-marge`) : vérité
  terrain instrumentée + fix « Gérer » (2 causes), tout vérifié en réel.
- **Session (3) LIVRÉE, à commiter (bat 27) + redémarrer + vérifier en réel** :
  - Correctifs d'audit **I1, I2, O1–O5, O10** (thumb 512/1600 + Range/streaming +
    cache media_roots + index vectors(k) + locks + workers sous ordonnanceur).
  - **Assurance-vie (audit A)** : `backup_verify()` + `export_jugements()` à
    chaque backup horaire ; cartes « Dernier scan » / « Sauvegarde vérifiée »
    dans /reglages. ⚠ Jamais observée sur Windows (URI SQLite UNC) — réflexe
    n°2 : la voir passer UNE fois.
  - **/sujets guichet unique** : sous-nav partagée + onglet **Classification**
    (`/sujets?vue=classification`, compteurs + liens ancrés #verifier/#groupes/
    #inconnus). Diff relu par agent adversarial, correctifs appliqués.

## Prochain pas — par valeur (détail : ROADMAP « À faire »)

1. **Vérifier en réel la session (3)** : grille galerie via `/api/thumb` (onglet
   Réseau), seek vidéo, `/sujets?vue=classification`, carte « Sauvegarde
   vérifiée : ok » après le prochain backup horaire.
2. **Vérité terrain** (geste Mike, outillage prêt) : confirmer ~100 propositions
   dans `/people` (Espace=oui, X=non, Z=annuler) — compteur de séance affiché.
3. **Éval tagging V2 AVANT lots de renommage** (banc keyé par chemin). Protocole :
   `eval/PLAN_assertions_vs_pixels.md`. Si V2 confirme → câbler Knowledge Builder.
4. **Correctifs d'audit restants** : O6 (recherche vs lot d'encodage), puis
   I4–I8, O7–O9, O11–O15 (dont purge `photo_thumbs/`).
5. Gestes Mike : nettoyer Flo ; activer `gps_place` (plus de préalable technique).

## Rappels opérationnels

- Tester en réel : **192.168.0.13:8080** via Claude-in-Chrome. **Pas de hot-reload** →
  redémarrer (`0 - Démarrer le serveur.bat`) après toute modif de `server.py`. Captures =
  onglet au premier plan ; état par `fetch` GET (marche onglet caché). État GPU/ordo :
  `GET /api/search/status` → `etat['gpu']`, `etat['ordonnanceur']`.
- Livraison sandbox → disque : `SendUserFile` puis `device_commit_files`. **Git +
  redémarrage = gestes Mike.** Ne pas ouvrir `photos.db` depuis le sandbox (le serveur
  est l'écrivain unique). Tests : `python test_ordonnanceur.py` (27 vérifications).

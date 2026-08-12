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

## Où on en est (12/08/2026, session 4)

- Commité jusqu'à `e17ac2d` (branche `feat/audit-assurance-sujets`) : correctifs
  d'audit **I1, I2, O1–O5, O10**, **assurance-vie** (`backup_verify()` +
  `export_jugements()` à chaque backup horaire), **/sujets guichet unique**
  (sous-nav + onglet Classification).
- **Session (4) LIVRÉE, à commiter (bat 27) + redémarrer + vérifier en réel** :
  - Les files **« À vérifier » ont quitté `/people`** : elles se jugent dans
    `/sujets?vue=classification`, avec une **file ANIMAUX créée en miroir**
    (`build_cat_suggestions()`, `GET /api/pets/curator/list`, bande « ajoutés
    automatiquement » annulable, jugements animaux dans le même journal).
    Clavier unifié : Espace = oui, X = non, Z = annuler, une lettre = corriger.
  - 3 correctifs de relecture adversariale : `par_humain` (animaux) **annulable** ;
    garde **anti-course** `_note_juge`/`_juges_depuis` sur les deux files ; garde
    **clés fantômes** côté animaux. + verrou « une carte ne se juge qu'une fois ».

## Prochain pas — par valeur (détail : ROADMAP « À faire »)

1. **Vérifier en réel la session (4)** : les deux files s'affichent et se jugent
   dans Classification ; annuler (Z) une acceptation d'animal doit faire REVENIR
   la carte après rafraîchissement.
2. **Vérifier en réel la session (3)** : galerie via `/api/thumb` (onglet
   Réseau), seek vidéo, carte « Sauvegarde vérifiée : ok » après le prochain
   backup horaire (⚠ jamais observée sur Windows — URI UNC).
3. **Vérité terrain** (geste Mike, outillage prêt) : confirmer ~100 propositions
   dans `/sujets?vue=classification` — compteur de séance affiché.
4. **Éval tagging V2 AVANT lots de renommage** (banc keyé par chemin). Protocole :
   `eval/PLAN_assertions_vs_pixels.md`. Si V2 confirme → câbler Knowledge Builder.
5. **Correctifs d'audit restants** : O6 (recherche vs lot d'encodage), puis
   I4–I8, O7–O9, O11–O15 (dont purge `photo_thumbs/`).
6. Gestes Mike : nettoyer Flo ; activer `gps_place` (plus de préalable technique).

## Rappels opérationnels

- Tester en réel : **192.168.0.13:8080** via Claude-in-Chrome. **Pas de hot-reload** →
  redémarrer (`0 - Démarrer le serveur.bat`) après toute modif de `server.py`. Captures =
  onglet au premier plan ; état par `fetch` GET (marche onglet caché). État GPU/ordo :
  `GET /api/search/status` → `etat['gpu']`, `etat['ordonnanceur']`.
- Livraison sandbox → disque : `SendUserFile` puis `device_commit_files`. **Git +
  redémarrage = gestes Mike.** Ne pas ouvrir `photos.db` depuis le sandbox (le serveur
  est l'écrivain unique). Tests : `python test_ordonnanceur.py` (27 vérifications).

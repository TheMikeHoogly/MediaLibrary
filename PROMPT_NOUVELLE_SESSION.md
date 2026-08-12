# Amorce de reprise — MediaLibrary

> Colle ce bloc dans une nouvelle conversation Cowork, après avoir connecté
> `C:\Prog\Claude\MediaLibrary`. L'état vit dans les fichiers, pas dans l'historique.
> Règles + protocole = `CLAUDE.md` (chargé auto). Ici : juste l'état et le prochain pas.

Tu reprends **MediaLibrary** — photothèque familiale locale à IA (~30 000 photos NAS,
serveur Python stdlib pur, 5 pipelines Ollama/InsightFace/YOLO/DINOv2/SigLIP2,
RTX 3050 4 Go arbitrée par baux/priorités/éviction).

## Ordre de lecture

1. `CLAUDE.md` (auto) — règles absolues, protocole, architecture.
2. `ROADMAP.md` — priorités réordonnées au triple audit du 11/08.
3. `eval/DECISIONS.md` — pistes tranchées (ne rien reproposer).
4. `docs/AUDIT_INTERNE_2026-08.md` — constats détaillés I1–I17 / O1–O15 / A–F.
5. Selon le sujet : skills `monolith-surgery` (avant tout edit de `server.py`),
   `photo-ui` (dès qu'on touche l'UI).

## Où on en est (12/08/2026)

- Commité jusqu'à `15e3204` (branche `feat/verite-terrain-marge`) : Arbitre GPU
  (`72d1946`), instrumentation vérité terrain (`a9a7d8b`, vérifiée en réel) + fix
  purge (`15e3204`). Triple audit → `docs/AUDIT_INTERNE_2026-08.md`.
- **12/08 — régression « Gérer » (/people) : 2 causes.** (1) `#panel` après la
  grille par lots (cible mouvante) → panneau AVANT la grille : **vérifié en réel**.
  (2) `curMark()` scrollait vers la file au chargement (cascade de lots, lien
  profond caché) → scroll au tri clavier seulement : **à commiter (bat 27) +
  redémarrer.** Vérif : `/people?name=Val` → le panneau doit rester visible en haut.

## Prochain pas — par valeur (détail : ROADMAP « À faire »)

1. **Vérité terrain** (geste Mike, outillage prêt) : confirmer ~100 propositions
   dans `/people` (Espace=oui, X=non, Z=annuler) — la file présente d'abord les
   cas les plus incertains ; le compteur de séance mesure le rythme.
2. **`/sujets` guichet unique** : réunir toutes les fonctions de gestion
   (personne/animal/lieu) dans `/sujets` + onglet **« Classification »** (groupes à
   nommer, faux positifs, … par type) — ROADMAP pt 2 (régression « Gérer » : corrigée).
3. **Assurance-vie de la vérité terrain** : tâche `backup_verify` + export NAS des
   jugements (`journal_jugements.jsonl` existe déjà — le copier hors site).
   Session courte, stdlib pur, angle mort majeur de l'audit.
4. **Correctifs d'audit prioritaires** (une session) : I1 (workers hors ordonnanceur),
   I2+O10 (`gps_places.json` dans `rekey_everywhere` + index `vectors(k)` — PRÉREQUIS
   des gestes gps_place/renommage), O3, O4, O5.
5. **Éval tagging V2 AVANT lots de renommage** (banc keyé par chemin). Protocole prêt :
   `eval/PLAN_assertions_vs_pixels.md`. Session perf quand tu veux : **O1 `/api/thumb`**.

## Rappels opérationnels

- Tester en réel : **192.168.0.13:8080** via Claude-in-Chrome. **Pas de hot-reload** →
  redémarrer (`0 - Démarrer le serveur.bat`) après toute modif de `server.py`. Captures =
  onglet au premier plan ; état par `fetch` GET (marche onglet caché). État GPU/ordo :
  `GET /api/search/status` → `etat['gpu']`, `etat['ordonnanceur']`.
- Livraison sandbox → disque : `SendUserFile` puis `device_commit_files`. **Git +
  redémarrage = gestes Mike.** Ne pas ouvrir `photos.db` depuis le sandbox (le serveur
  est l'écrivain unique). Tests : `python test_ordonnanceur.py` (27 vérifications).

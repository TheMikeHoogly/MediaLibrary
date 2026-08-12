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

## Où on en est (11/08/2026, fin de nuit)

- Matin+après-midi+soir du 11/08 : **commités** jusqu'à `ea4aa00` (fusion `/sujets`,
  recherche Carte, passe DESIGN 7 pages — tout vérifié en réel). Détail dans git.
- **Session nuit — GpuArbiter : livré, VÉRIFIÉ en réel** (bail `semantique` matérialisé,
  SigLIP sur cuda, 0 refus ; `GET /api/search/status` → `etat['gpu']`), tests 27/27
  (+11 vérifications ArbitreGPU). **À commiter si pas encore fait.**
- **Triple audit du projet** (incohérences / optimisations / stratégie) →
  `docs/AUDIT_INTERNE_2026-08.md` ; ROADMAP réordonnée en conséquence.

## Prochain pas — par valeur (détail : ROADMAP « À faire »)

1. **Vérité terrain** (geste Mike) : confirmer ~100 propositions dans `/people`
   (Espace=oui, X=non, Z=annuler). Chantier code associé : tri par **marge**
   d'incertitude (jamais le score absolu — circularité).
2. **Assurance-vie de la vérité terrain** : tâche `backup_verify` (integrity_check +
   restauration à blanc + comptage confirmed/exclude) + export JSONL append-only des
   jugements humains. Session courte, stdlib pur, angle mort majeur de l'audit.
3. **Correctifs d'audit prioritaires** (une session) : I1 (workers visages/animaux hors
   ordonnanceur), I2+O10 (`gps_places.json` dans `rekey_everywhere` + index `vectors(k)`
   — PRÉREQUIS des gestes gps_place/renommage), O3 (cache `media_roots`), O5 (try/except
   `maintenance_loop`), O4 (écritures vectors sous `STORE.lock`).
4. **Éval tagging V2 AVANT lots de renommage** (le banc de 150 photos est keyé par
   chemin). Protocole prêt : `eval/PLAN_assertions_vs_pixels.md`.
5. Gros gain UX quand tu veux une session perf : **O1 `/api/thumb`** (vignettes de
   grille : −98 % d'octets NAS).

## Rappels opérationnels

- Tester en réel : **192.168.0.13:8080** via Claude-in-Chrome. **Pas de hot-reload** →
  redémarrer (`0 - Démarrer le serveur.bat`) après toute modif de `server.py`. Captures =
  onglet au premier plan ; état par `fetch` GET (marche onglet caché). État GPU/ordo :
  `GET /api/search/status` → `etat['gpu']`, `etat['ordonnanceur']`.
- Livraison sandbox → disque : `SendUserFile` puis `device_commit_files`. **Git +
  redémarrage = gestes Mike.** Ne pas ouvrir `photos.db` depuis le sandbox (le serveur
  est l'écrivain unique). Tests : `python test_ordonnanceur.py` (27 vérifications).

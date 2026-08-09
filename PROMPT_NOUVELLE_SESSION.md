# Amorce de reprise — MediaLibrary

> Colle ce bloc dans une nouvelle conversation Cowork, après avoir connecté le dossier
> `C:\Prog\Claude\MediaLibrary`. L'état vit dans les fichiers, pas dans l'historique.
> Les **règles** et le **protocole** sont dans `CLAUDE.md` (chargé automatiquement) —
> ce fichier ne les répète pas : il donne juste l'état et le prochain pas.

Tu reprends **MediaLibrary** — photothèque familiale locale à IA (~30 000 photos NAS,
serveur Python stdlib pur, pipelines Ollama/InsightFace/YOLO/DINOv2, RTX 3050 4 Go).

## Ordre de lecture

1. `CLAUDE.md` (auto) — règles absolues, protocole, architecture.
2. `ROADMAP.md` — état + priorités.
3. `eval/DECISIONS.md` — idées déjà rejetées/tranchées (ne rien reproposer).
4. Selon le sujet : `docs/RANGEMENT_2026.md`, `docs/AUDIT_EXTERNE_2026.md`, et les
   skills `.claude/skills/` (`monolith-surgery` avant tout edit de `server.py`).

## Où on en est (10/08/2026)

- **#3 archive « Inconnus » + fix curateur : validés en réel.** Détail : `ROADMAP.md`.
- Serveur : tourne la branche `feat/menage-ui-gpu-0807` (== `main`). Le code validé
  tourne déjà. **Reste éventuellement : commit/push** (geste Mike, `docs/GIT_WORKFLOW.md`).
- **Ouvert** : activer le géocodage `gps_place` (gestes Mike : bat 18 → `enrichir_lieux.py`
  → `--ecrire` → redémarrer).

## Prochain chantier — au choix par valeur (cf. ROADMAP)

1. Confirmer ~100 propositions dans `/people` (vérité terrain, priorité n°1).
2. `/reglages` en **tour de contrôle** + centre de tâches (demande Mike ; renforcé par le
   constat perf : `/people` rend ~11 300 vignettes d'un coup → lenteurs).
3. Appliquer les lots de renommage / activer `gps_place` (gestes Mike).
4. Page « Sujets » unifiée.

## Rappels opérationnels

- Tester en réel : **192.168.0.13:8080**, via Claude-in-Chrome. Le serveur **ne recharge
  pas à chaud** → redémarrer (`0 - Démarrer le serveur.bat`) pour activer une modif de
  `server.py`. ⚠ Les clics/captures Claude-in-Chrome ne marchent que si l'onglet est **au
  premier plan** (onglet caché = rendu gelé, clics ignorés) ; vérifs d'état par `fetch` GET.
- Garde-fous détaillés dans `CLAUDE.md` (noms humains sacrés, `.bat` ASCII, zéro dépendance,
  SQLite local). Mutations = vrais clics UI ; ne pas ouvrir `photos.db` depuis le sandbox.

Une phrase suffit pour démarrer : « Lis ROADMAP.md et DECISIONS.md, puis attaque le point N. »

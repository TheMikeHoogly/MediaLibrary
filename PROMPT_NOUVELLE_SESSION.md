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

## Où on en est (9/08/2026)

- **✅ Reclassement Mutz/Caline : FAIT & vérifié le 9/08.** 88 photos passées de
  `personne:` à `animal:` (Mutz 5, Caline 83), fiche Caline en double retirée, aucune
  perte (88/88 vérifiées). Outil réversible dans `/reglages` → « Reclassement ». Le vrai
  journal `docs/undo_reclassement_1786307562.json` existe encore : **cliquer Annuler
  reviendrait à revenir en arrière** — ne pas y toucher sauf pour ça.
- **⏳ À confirmer visuellement (déployé, serveur redémarré) :** (a) **`/people` allégé**
  (rendu par lots `renderInBatches` — défiler doit être fluide, nommer un groupe, Inconnus) ;
  (b) carte **« Empreintes animaux »** (stock réel ~4826) dans `/reglages`. Détail : `ROADMAP.md`.
- **Nettoyage de session : LIVRÉ** — `29 - Nettoyage de session.bat` /
  `nettoyer_session.py` (quarantaine réversible + lint `*.md`), étape ajoutée à `CLAUDE.md`.
  Passe initiale faite. À lancer en fin de chaque session.
- **#3 archive « Inconnus » + fix curateur : validés en réel.** Détail : `ROADMAP.md`.
- Serveur : branche `feat/menage-ui-gpu-0807` (== `main`). **Reste : commit/push** de la
  session (geste Mike, `docs/GIT_WORKFLOW.md`).
- **Ouvert** : activer le géocodage `gps_place` (gestes Mike : bat 18 → `enrichir_lieux.py`
  → `--ecrire` → redémarrer).

## Prochain chantier — au choix par valeur (cf. ROADMAP)

1. **Valider en réel** `/people` allégé + carte « Empreintes chats » (après redémarrage).
2. Confirmer ~100 propositions dans `/people` (vérité terrain, priorité n°1).
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

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

Session 9/08 **commitée + fusionnée dans `main`**, serveur redémarré. Tout est validé,
rien en attente. Acquis de la session (détail : `ROADMAP.md` + git) :
- **`/people` allégé** — rendu par lots (`renderInBatches`), défilement fluide.
- **Tour de contrôle `/reglages`** complétée : carte « Empreintes animaux » = stock réel.
- **Nettoyage de fin de session** — `29 - Nettoyage de session.bat` / `nettoyer_session.py`
  (quarantaine réversible `_corbeille_session/` + lint `*.md`). **À lancer en fin de chaque
  session** (au protocole `CLAUDE.md`).
- **Reclassement `personne:`→`animal:`** dans `/reglages` : Mutz + Caline reclassés, doublon
  de fiche Caline retiré, vérifié 88/88 sans perte. Réversible ; relancer l'outil (Aperçu →
  Appliquer) dès qu'un nouveau nom d'animal se retrouve tagué en `personne:`.

- **Ouvert (gestes Mike)** : lots de renommage + géocodage `gps_place` (bat 18 →
  `enrichir_lieux.py` → `--ecrire` → redémarrer) ; `git push` si pas déjà fait.

## Prochain chantier — au choix par valeur (cf. ROADMAP)

1. **Vérité terrain (priorité n°1)** : confirmer ~100 propositions dans `/people` (tri
   clavier Espace/X/Z ; la page est désormais fluide).
2. Appliquer les lots de renommage + activer `gps_place` (gestes Mike).
3. Page « Sujets » unifiée (Personnes + Animaux).
4. Recherche en langue naturelle (SigLIP 2).

## Rappels opérationnels

- Tester en réel : **192.168.0.13:8080**, via Claude-in-Chrome. Le serveur **ne recharge
  pas à chaud** → redémarrer (`0 - Démarrer le serveur.bat`) pour activer une modif de
  `server.py`. ⚠ Les clics/captures Claude-in-Chrome ne marchent que si l'onglet est **au
  premier plan** (onglet caché = rendu gelé, clics ignorés) ; vérifs d'état par `fetch` GET.
- Garde-fous détaillés dans `CLAUDE.md` (noms humains sacrés, `.bat` ASCII, zéro dépendance,
  SQLite local). Mutations = vrais clics UI ; ne pas ouvrir `photos.db` depuis le sandbox.

Une phrase suffit pour démarrer : « Lis ROADMAP.md et DECISIONS.md, puis attaque le point N. »

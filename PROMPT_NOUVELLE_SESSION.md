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

Session 10/08 centrée sur `/people` et la **correction des faux positifs** (fiche Flo,
~6300 photos, très polluée par des profils tagués). Code **livré sur le disque et validé en
réel**, mais **PAS encore commité** → lancer `27 - Commit de session.bat` (+ `28 - Fusionner…`
/ `git push` = gestes Mike). Acquis (détail : `ROADMAP.md` + git) :
- **`/people` réorganisé** : personnes identifiées + panneau de correction EN TÊTE, files de
  travail (à vérifier / groupes / inconnus) dessous → plus de saut de scroll au rendu par
  lots ; **filtre par nom** ; panneau ancré en haut à l'ouverture.
- **Correction des faux positifs** : « Corriger » et « Nettoyer (référence) » partagent
  `scoredRemoval` (seuil ajustable, compteur « N sous le seuil », retrait de masse par seuil
  piloté par les données, rendu par lots) ; grille de références « plus ressemblantes
  d'abord ». Retrait **sûr** : `untag`→`exclude`, respecté par le curateur auto.
- **Perf** : scoring vectorisé (`_best_sims_for_tag`) + `media_roots()` calculé une fois →
  re-score d'une personne à 6338 photos **156 s → quelques s** (diagnostiqué en réel via
  Claude-in-Chrome).
- **Indicateur d'activité réseau global** (spinner « Traitement… ») sur les 7 pages.

- **Ouvert (gestes Mike)** : **nettoyer Flo** (Corriger seuil ~0.2 / Nettoyer référence) ;
  lots de renommage + `gps_place` (bat 18 → `enrichir_lieux.py` → `--ecrire` → redémarrer) ;
  commit/push ; nettoyage de fin de session (`29 - …bat`).

## Prochain chantier — au choix par valeur (cf. ROADMAP)

1. **Vérité terrain (priorité n°1)** : confirmer ~100 propositions dans `/people` — la page
   est maintenant réorganisée + filtrable, la revue est directe.
2. **Page « Sujets » unifiée — cadrée le 10/08, à reprendre** : surcouche `/sujets` d'abord
   (coexiste, cartes → détails existants) puis fusion ; Lieux = 3ᵉ type d'entité (dépend de
   `gps_place`).
3. Appliquer les lots de renommage + activer `gps_place` (gestes Mike).
4. Recherche en langue naturelle (SigLIP 2).

## Rappels opérationnels

- Tester en réel : **192.168.0.13:8080**, via Claude-in-Chrome. Le serveur **ne recharge
  pas à chaud** → redémarrer (`0 - Démarrer le serveur.bat`) pour activer une modif de
  `server.py`. ⚠ Les clics/captures Claude-in-Chrome ne marchent que si l'onglet est **au
  premier plan** (onglet caché = rendu gelé, clics ignorés) ; vérifs d'état par `fetch` GET.
- Garde-fous détaillés dans `CLAUDE.md` (noms humains sacrés, `.bat` ASCII, zéro dépendance,
  SQLite local). Mutations = vrais clics UI ; ne pas ouvrir `photos.db` depuis le sandbox.

Une phrase suffit pour démarrer : « Lis ROADMAP.md et DECISIONS.md, puis attaque le point N. »
